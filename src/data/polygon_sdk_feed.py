"""
Polygon.io SDK-based feed handler for TEPM system.

Uses the official polygon-api-client Python SDK for WebSocket streaming.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from polygon import WebSocketClient
from polygon.websocket.models import Feed, Market

from ..core.config import settings
from ..core.logger import LoggerMixin, logger
from ..core.models import EventType, Quote, Tick, Trade
from ..core.state import SessionState
from ..data.orderbook import get_orderbook_manager
from ..data.symbol_map import get_symbol_mapper
from ..signals.microstructure import get_microstructure_signals


class PolygonSDKFeedHandler(LoggerMixin):
    """Polygon.io SDK-based WebSocket feed handler."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state
        self.is_running = False
        
        # Get API key from config or file
        self.api_key = self._get_api_key()
        
        if not self.api_key or self.api_key == "your_polygon_key":
            raise ValueError("Valid Polygon API key not found. Set POLYGON_API_KEY env var or update polygon_api.txt")
        
        # WebSocket client
        self.ws_client: Optional[WebSocketClient] = None
        self._ws_thread = None
        
        # Symbols to subscribe
        self.symbols = self.session_state.symbols
        
        # Components
        self.orderbook_manager = get_orderbook_manager()
        self.microstructure = get_microstructure_signals()
        self.symbol_mapper = get_symbol_mapper()
        
        # Statistics
        self.message_count = 0
        self.last_message_time = None
        
        self.logger.info(f"Initialized Polygon SDK feed handler for symbols: {self.symbols}")

    def _get_api_key(self) -> str:
        """Get Polygon API key from environment or file."""
        import os
        
        # Try environment variable first
        api_key = os.getenv("POLYGON_API_KEY")
        if api_key:
            return api_key
        
        # Try reading from polygon_api.txt
        try:
            with open("polygon_api.txt", "r") as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key
        except FileNotFoundError:
            pass
        
        # Try from settings (might have ${POLYGON_API_KEY} placeholder)
        config_key = settings.data_feed.polygon.api_key
        if config_key and not config_key.startswith("${"):
            return config_key
        
        return None

    async def start(self) -> None:
        """Start the Polygon SDK WebSocket feed."""
        self.is_running = True
        
        try:
            # Build subscription strings for crypto
            # Format: "XT.{symbol}" for trades, "XQ.{symbol}" for quotes
            subscriptions = []
            for symbol in self.symbols:
                # Map to Polygon format (e.g., BTC-USD -> X:BTCUSD)
                polygon_symbol = self.symbol_mapper.execution_to_polygon(symbol)
                # Remove "X:" prefix and dash for subscription format
                clean_symbol = polygon_symbol.replace("X:", "").replace("-", "")
                
                subscriptions.append(f"XT.{clean_symbol}")  # Trades
                subscriptions.append(f"XQ.{clean_symbol}")  # Quotes
            
            # Create WebSocket client
            # raw=False ensures we get parsed message objects, not raw strings
            self.ws_client = WebSocketClient(
                api_key=self.api_key,
                market=Market.Crypto,
                feed=Feed.RealTime,
                subscriptions=subscriptions,
                raw=False,  # Parse messages into objects
                verbose=True
            )
            
            self.logger.info(f"Starting Polygon SDK WebSocket connection...")
            self.logger.info(f"Subscriptions: {subscriptions}")
            
            # Run WebSocket in a thread (the SDK's connect() doesn't work properly with asyncio)
            import threading
            
            def run_ws():
                print("🚀 Starting WebSocket in thread...")
                print(f"   Thread ID: {threading.current_thread().name}")
                print(f"   Client: {self.ws_client}")
                print(f"   Handler: {self._handle_message_sync}")
                try:
                    # Use synchronous run() instead of async connect()
                    print("   Calling ws_client.run()...")
                    self.ws_client.run(self._handle_message_sync)
                    print("   ws_client.run() returned (shouldn't happen)")
                except Exception as e:
                    print(f"❌ WebSocket error: {e}")
                    import traceback
                    traceback.print_exc()
            
            self._ws_thread = threading.Thread(target=run_ws, daemon=True)
            self._ws_thread.start()
            self.logger.info("WebSocket thread started")
            
        except Exception as e:
            self.logger.error(f"Error starting Polygon SDK feed: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Polygon SDK WebSocket feed."""
        self.is_running = False
        
        if self.ws_client:
            try:
                self.ws_client.close_connection()
                self.logger.info("Polygon SDK WebSocket connection closed")
            except Exception as e:
                self.logger.error(f"Error closing Polygon SDK connection: {e}")

    def _handle_message_sync(self, messages) -> None:
        """Handle incoming messages from Polygon SDK (synchronous version for thread)."""
        # IMMEDIATE DEBUG - is this even being called?
        print(f"🔔 _handle_message_sync called! Got {len(messages) if isinstance(messages, list) else 1} message(s)")
        
        if not isinstance(messages, list):
            messages = [messages]
        
        for msg in messages:
            try:
                # Log first few messages for debugging
                if self.message_count < 5:
                    print(f"DEBUG: Received message type: {type(msg)}")
                    print(f"DEBUG: Message: {msg}")
                    if hasattr(msg, '__dict__'):
                        print(f"DEBUG: Message attrs: {list(msg.__dict__.keys())}")
                
                # Check message type - Polygon SDK uses 'ev' attribute
                event_type = None
                if hasattr(msg, 'ev'):
                    event_type = msg.ev
                elif hasattr(msg, 'event_type'):
                    event_type = msg.event_type
                
                if event_type == 'XT':  # Crypto Trade
                    self._handle_crypto_trade(msg)
                elif event_type == 'XQ':  # Crypto Quote
                    self._handle_crypto_quote(msg)
                elif event_type in ['status', 'auth']:
                    # Status/auth messages
                    print(f"Polygon status: {event_type}")
                    
            except Exception as e:
                print(f"❌ Error handling message: {e}")
                import traceback
                traceback.print_exc()
    
    def _handle_crypto_trade(self, trade_data) -> None:
        """Handle incoming crypto trade from Polygon SDK."""
        try:
            self.message_count += 1
            self.last_message_time = time.time()
            
            # Extract symbol and map to execution format
            polygon_symbol = trade_data.symbol
            symbol = self.symbol_mapper.polygon_to_execution(polygon_symbol)
            
            # Create Trade object
            trade = Trade(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(trade_data.timestamp / 1000, tz=timezone.utc),
                price=Decimal(str(trade_data.price)),
                size=Decimal(str(trade_data.size)),
                side="buy" if hasattr(trade_data, 'side') and trade_data.side == 'buy' else "sell",
                conditions=[]
            )
            
            # Wrap in Tick
            tick = Tick(
                symbol=symbol,
                timestamp=trade.timestamp,
                event_type=EventType.TRADE,
                data=trade
            )
            
            # Process
            self.microstructure.add_tick(tick)
            asyncio.create_task(self.session_state.add_tick(tick))
            
            # Log periodically
            if self.message_count % 100 == 0:
                self.logger.info(
                    f"Processed {self.message_count} messages | "
                    f"Latest: {symbol} @ ${trade.price} (size: {trade.size})"
                )
            
        except Exception as e:
            self.logger.error(f"Error handling crypto trade: {e}")

    def _handle_crypto_quote(self, quote_data) -> None:
        """Handle incoming crypto quote from Polygon SDK."""
        try:
            self.message_count += 1
            self.last_message_time = time.time()
            
            # Extract symbol and map to execution format
            polygon_symbol = quote_data.symbol
            symbol = self.symbol_mapper.polygon_to_execution(polygon_symbol)
            
            # Create Quote object
            quote = Quote(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(quote_data.timestamp / 1000, tz=timezone.utc),
                bid_price=Decimal(str(quote_data.bid_price)),
                ask_price=Decimal(str(quote_data.ask_price)),
                bid_size=Decimal(str(quote_data.bid_size)) if hasattr(quote_data, 'bid_size') else Decimal("0"),
                ask_size=Decimal(str(quote_data.ask_size)) if hasattr(quote_data, 'ask_size') else Decimal("0"),
                conditions=[]
            )
            
            # Wrap in Tick
            tick = Tick(
                symbol=symbol,
                timestamp=quote.timestamp,
                event_type=EventType.QUOTE,
                data=quote
            )
            
            # Process
            self.microstructure.add_tick(tick)
            asyncio.create_task(self.session_state.add_tick(tick))
            
            # Update order book with quote
            self.orderbook_manager.update_book_from_quote(symbol, quote)
            
        except Exception as e:
            self.logger.error(f"Error handling crypto quote: {e}")

    def get_stats(self) -> dict:
        """Get feed handler statistics."""
        return {
            "is_running": self.is_running,
            "message_count": self.message_count,
            "last_message_time": self.last_message_time,
            "subscribed_symbols": list(self.symbols),
        }


def create_polygon_sdk_feed(session_state: SessionState) -> PolygonSDKFeedHandler:
    """Factory function to create Polygon SDK feed handler."""
    return PolygonSDKFeedHandler(session_state)

