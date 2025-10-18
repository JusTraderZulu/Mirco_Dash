"""
Polygon.io REST API polling feed handler for TEPM system.

Uses REST API polling as an alternative to WebSocket when WebSocket doesn't work.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import httpx

from ..core.config import settings
from ..core.logger import LoggerMixin, logger
from ..core.models import EventType, Quote, Tick, Trade
from ..core.state import SessionState
from ..data.orderbook import get_orderbook_manager
from ..data.symbol_map import get_symbol_mapper
from ..signals.microstructure import get_microstructure_signals
from ..signals.montecarlo import get_monte_carlo


class PolygonRestFeedHandler(LoggerMixin):
    """Polygon.io REST API polling feed handler."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state
        self.is_running = False
        
        # Get API key
        self.api_key = self._get_api_key()
        
        if not self.api_key or self.api_key == "your_polygon_key":
            raise ValueError("Valid Polygon API key not found")
        
        # HTTP client
        self.client = httpx.AsyncClient(
            base_url="https://api.polygon.io",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0
        )
        
        # Symbols to track
        self.symbols = self.session_state.symbols
        
        # Components
        self.orderbook_manager = get_orderbook_manager()
        self.microstructure = get_microstructure_signals()
        self.monte_carlo = get_monte_carlo()
        self.symbol_mapper = get_symbol_mapper()
        
        # Polling interval (seconds)
        self.poll_interval = 2.0  # Poll every 2 seconds
        
        # Statistics
        self.message_count = 0
        self.last_timestamps = {}  # Track last trade timestamp per symbol
        
        self.logger.info(f"Initialized Polygon REST feed handler for symbols: {self.symbols}")

    def _get_api_key(self) -> str:
        """Get Polygon API key from environment or file."""
        import os
        
        # Try environment variable
        api_key = os.getenv("POLYGON_API_KEY")
        if api_key:
            return api_key
        
        # Try file
        try:
            with open("polygon_api.txt", "r") as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key
        except FileNotFoundError:
            pass
        
        return None

    async def start(self) -> None:
        """Start the REST API polling."""
        self.is_running = True
        
        print("🚀 Starting Polygon REST API polling...")
        print(f"   Polling interval: {self.poll_interval}s")
        print(f"   Symbols: {self.symbols}")
        
        # Start polling tasks for each symbol
        self._poll_tasks = []
        for symbol in self.symbols:
            task = asyncio.create_task(self._poll_symbol(symbol))
            self._poll_tasks.append(task)
        
        self.logger.info("Polygon REST API polling started")

    async def stop(self) -> None:
        """Stop the REST API polling."""
        self.is_running = False
        
        # Cancel all polling tasks
        for task in self._poll_tasks:
            task.cancel()
        
        # Close HTTP client
        await self.client.aclose()
        
        self.logger.info("Polygon REST API polling stopped")

    async def _poll_symbol(self, symbol: str) -> None:
        """Poll trades and quotes for a symbol."""
        polygon_symbol = self.symbol_mapper.execution_to_polygon(symbol)
        
        print(f"🔄 Starting polling for {symbol} (Polygon: {polygon_symbol})")
        
        while self.is_running:
            try:
                # Fetch latest trades
                await self._fetch_trades(polygon_symbol, symbol)
                
                # Fetch latest quote
                await self._fetch_quote(polygon_symbol, symbol)
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                self.logger.error(f"Error polling {symbol}: {e}")
                print(f"❌ Error polling {symbol}: {e}")
                await asyncio.sleep(self.poll_interval)

    async def _fetch_trades(self, polygon_symbol: str, exec_symbol: str) -> None:
        """Fetch latest trades for a symbol."""
        try:
            # Get trades since last timestamp
            url = f"/v3/trades/{polygon_symbol}"
            params = {"limit": 10, "order": "desc"}
            
            response = await self.client.get(url, params=params)
            
            print(f"📊 Fetched trades for {polygon_symbol}: HTTP {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if "results" in data and len(data["results"]) > 0:
                    new_trades = 0
                    # Process trades (newest first, so reverse)
                    for trade_data in reversed(data["results"]):
                        trade_ts = trade_data.get("participant_timestamp", 0) / 1_000_000_000
                        
                        # Skip if we've already seen this trade
                        last_ts = self.last_timestamps.get(exec_symbol, 0)
                        if trade_ts <= last_ts:
                            continue
                        
                        new_trades += 1
                        self.last_timestamps[exec_symbol] = trade_ts
                        
                        # Create Trade object
                        trade = Trade(
                            symbol=exec_symbol,
                            timestamp=datetime.fromtimestamp(trade_ts, tz=timezone.utc),
                            price=Decimal(str(trade_data.get("price"))),
                            size=Decimal(str(trade_data.get("size"))),
                            side="buy",  # REST API doesn't provide side
                            conditions=[]
                        )
                        
                        # Wrap in Tick
                        tick = Tick(
                            symbol=exec_symbol,
                            timestamp=trade.timestamp,
                            event_type=EventType.TRADE,
                            data=trade
                        )
                        
                        # Process
                        # Add to microstructure (for OFI, spread, etc.)
                        self.microstructure.add_tick(tick)
                        
                        # Add to Monte Carlo (for volatility and scenarios)
                        self.monte_carlo.add_price_data(exec_symbol, float(trade.price), trade.timestamp)
                        
                        # Add to session state
                        await self.session_state.add_tick(tick)
                        
                        # Update order book with trade price
                        book = self.orderbook_manager.get_or_create_book(exec_symbol)
                        book.bids[trade.price] = trade.size
                        book.asks[trade.price] = trade.size
                        book.last_update = trade.timestamp
                        
                        self.message_count += 1
                    
                    if new_trades > 0 and self.message_count % 50 == 0:
                        # Show progress every 50 trades
                        print(f"📊 Processed {self.message_count} total trades from Polygon")
                            
        except Exception as e:
            self.logger.error(f"Error fetching trades for {exec_symbol}: {e}")

    async def _fetch_quote(self, polygon_symbol: str, exec_symbol: str) -> None:
        """Fetch latest quote for a symbol."""
        try:
            url = f"/v2/last/nbbo/{polygon_symbol}"
            
            response = await self.client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                if "results" in data:
                    result = data["results"]
                    
                    # Create Quote object
                    quote = Quote(
                        symbol=exec_symbol,
                        timestamp=datetime.now(timezone.utc),
                        bid_price=Decimal(str(result.get("P", 0))),  # Bid price
                        ask_price=Decimal(str(result.get("p", 0))),  # Ask price
                        bid_size=Decimal(str(result.get("S", 0))),   # Bid size
                        ask_size=Decimal(str(result.get("s", 0))),   # Ask size
                        conditions=[]
                    )
                    
                    # Update order book
                    self.orderbook_manager.update_book_from_quote(exec_symbol, quote)
                    
        except Exception as e:
            self.logger.error(f"Error fetching quote for {exec_symbol}: {e}")

    def get_stats(self) -> dict:
        """Get feed handler statistics."""
        return {
            "is_running": self.is_running,
            "message_count": self.message_count,
            "symbols": list(self.symbols),
            "method": "REST API Polling"
        }


def create_polygon_rest_feed(session_state: SessionState) -> PolygonRestFeedHandler:
    """Factory function to create Polygon REST feed handler."""
    return PolygonRestFeedHandler(session_state)

