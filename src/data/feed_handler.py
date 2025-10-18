"""
Polygon.io WebSocket feed handler for TEPM system.

Connects to Polygon crypto WebSocket, subscribes to L2 order book and trades/quotes,
and processes incoming market data.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Set

import websockets
from websockets.exceptions import ConnectionClosed

from ..core.config import settings
from ..core.logger import LoggerMixin, logger, set_session_context
from ..core.models import BookDelta, EventType, Quote, Tick, Trade
from ..core.state import SessionState
from ..data.orderbook import get_orderbook_manager
from ..data.symbol_map import get_symbol_mapper


class PolygonFeedHandler(LoggerMixin):
    """Polygon.io WebSocket feed handler."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None

        # Configuration
        self.ws_url = settings.data_feed.polygon.ws_url
        self.api_key = settings.data_feed.polygon.api_key
        self.channels = settings.data_feed.polygon.channels
        self.symbols = [
            get_symbol_mapper().execution_to_polygon(symbol)
            for symbol in settings.data_feed.polygon.symbols
        ]

        # Connection state
        self.is_connected = False
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0

        # Message handling
        self.message_handlers = {
            "l2": self._handle_l2_message,
            "trades": self._handle_trades_message,
            "quotes": self._handle_quotes_message,
        }

        # Heartbeat
        self.last_heartbeat = datetime.now(timezone.utc)
        self.heartbeat_interval = 30  # seconds

    async def connect(self) -> bool:
        """Connect to Polygon WebSocket."""
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}

            self.logger.info(f"Connecting to Polygon WebSocket: {self.ws_url}")

            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=headers,
                ping_interval=self.heartbeat_interval,
                ping_timeout=10,
                close_timeout=5,
            )

            self.is_connected = True
            self.reconnect_delay = 1.0  # Reset delay on successful connection

            self.logger.info("Connected to Polygon WebSocket successfully")

            # Subscribe to channels
            await self._subscribe()

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Polygon WebSocket: {e}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Polygon WebSocket."""
        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("Disconnected from Polygon WebSocket")
            except Exception as e:
                self.logger.warning(f"Error disconnecting from WebSocket: {e}")

        self.is_connected = False
        self.websocket = None

    async def _subscribe(self) -> None:
        """Subscribe to configured channels and symbols."""
        if not self.websocket:
            return

        for channel in self.channels:
            subscription = {
                "action": "subscribe",
                "params": f"{channel}.{'*,*,'.join(self.symbols) if self.symbols else '*'}"
            }

            try:
                await self.websocket.send(json.dumps(subscription))
                self.logger.info(f"Subscribed to {channel} for symbols: {self.symbols}")
            except Exception as e:
                self.logger.error(f"Failed to subscribe to {channel}: {e}")

    async def _handle_l2_message(self, message: Dict) -> None:
        """Handle L2 order book message."""
        try:
            # Parse L2 message
            events = message.get("events", [])
            symbol = message.get("symbol", "")

            # Map symbol back to execution format for internal use
            execution_symbol = get_symbol_mapper().polygon_to_execution(symbol)

            for event in events:
                if event.get("type") == "snapshot":
                    # Full snapshot - replace entire book
                    bids = [
                        {"price": Decimal(str(level[0])), "size": Decimal(str(level[1]))}
                        for level in event.get("bids", [])
                    ]
                    asks = [
                        {"price": Decimal(str(level[0])), "size": Decimal(str(level[1]))}
                        for level in event.get("asks", [])
                    ]

                    delta = BookDelta(
                        symbol=execution_symbol,
                        bids=bids,
                        asks=asks,
                        timestamp=datetime.fromtimestamp(event.get("timestamp", 0) / 1000, timezone.utc)
                    )

                elif event.get("type") == "update":
                    # Incremental update
                    bids = [
                        {"price": Decimal(str(level[0])), "size": Decimal(str(level[1]))}
                        for level in event.get("bids", [])
                    ]
                    asks = [
                        {"price": Decimal(str(level[0])), "size": Decimal(str(level[1]))}
                        for level in event.get("asks", [])
                    ]

                    delta = BookDelta(
                        symbol=execution_symbol,
                        bids=bids,
                        asks=asks,
                        timestamp=datetime.fromtimestamp(event.get("timestamp", 0) / 1000, timezone.utc)
                    )

                else:
                    continue

                # Apply to order book
                orderbook_manager = get_orderbook_manager()
                orderbook_manager.apply_delta(delta)

                # Create tick event
                tick = Tick(
                    symbol=execution_symbol,
                    timestamp=delta.timestamp,
                    event_type=EventType.BOOK_DELTA,
                    data=delta
                )

                # Add to session state
                await self.session_state.add_tick(tick)

        except Exception as e:
            self.logger.error(f"Error handling L2 message: {e}")

    async def _handle_trades_message(self, message: Dict) -> None:
        """Handle trades message."""
        try:
            events = message.get("events", [])
            symbol = message.get("symbol", "")

            # Map symbol back to execution format
            execution_symbol = get_symbol_mapper().polygon_to_execution(symbol)

            for event in events:
                trade = Trade(
                    symbol=execution_symbol,
                    price=Decimal(str(event.get("price", 0))),
                    size=Decimal(str(event.get("size", 0))),
                    timestamp=datetime.fromtimestamp(event.get("timestamp", 0) / 1000, timezone.utc),
                    conditions=event.get("conditions", []),
                    exchange=event.get("exchange"),
                    tape=event.get("tape")
                )

                # Create tick event
                tick = Tick(
                    symbol=execution_symbol,
                    timestamp=trade.timestamp,
                    event_type=EventType.TRADE,
                    data=trade
                )

                # Add to session state
                await self.session_state.add_tick(tick)

        except Exception as e:
            self.logger.error(f"Error handling trades message: {e}")

    async def _handle_quotes_message(self, message: Dict) -> None:
        """Handle quotes message."""
        try:
            events = message.get("events", [])
            symbol = message.get("symbol", "")

            # Map symbol back to execution format
            execution_symbol = get_symbol_mapper().polygon_to_execution(symbol)

            for event in events:
                quote = Quote(
                    symbol=execution_symbol,
                    bid_price=Decimal(str(event.get("bid_price", 0))),
                    bid_size=Decimal(str(event.get("bid_size", 0))),
                    ask_price=Decimal(str(event.get("ask_price", 0))),
                    ask_size=Decimal(str(event.get("ask_size", 0))),
                    timestamp=datetime.fromtimestamp(event.get("timestamp", 0) / 1000, timezone.utc),
                    bid_exchange=event.get("bid_exchange"),
                    ask_exchange=event.get("ask_exchange")
                )

                # Create tick event
                tick = Tick(
                    symbol=execution_symbol,
                    timestamp=quote.timestamp,
                    event_type=EventType.QUOTE,
                    data=quote
                )

                # Add to session state
                await self.session_state.add_tick(tick)

        except Exception as e:
            self.logger.error(f"Error handling quotes message: {e}")

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)

            # Update heartbeat
            self.last_heartbeat = datetime.now(timezone.utc)

            # Handle different message types
            if data.get("event_type") == "status":
                self.logger.info(f"Status message: {data.get('message', '')}")

            elif data.get("event_type") == "subscribed":
                channel = data.get("channel", "")
                self.logger.info(f"Successfully subscribed to {channel}")

            elif "channel" in data:
                channel = data.get("channel", "")
                handler = self.message_handlers.get(channel)

                if handler:
                    await handler(data)
                else:
                    self.logger.warning(f"No handler for channel: {channel}")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON message: {e}")
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")

    async def _heartbeat_check(self) -> None:
        """Check if heartbeat is still active."""
        while self.is_connected:
            await asyncio.sleep(self.heartbeat_interval)

            time_since_heartbeat = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()

            if time_since_heartbeat > self.heartbeat_interval * 2:
                self.logger.warning(f"No heartbeat for {time_since_heartbeat}s, reconnecting...")
                await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect to WebSocket with exponential backoff."""
        self.is_connected = False

        if self.websocket:
            await self.disconnect()

        # Exponential backoff with jitter
        import random
        jitter = random.uniform(0.8, 1.2)
        delay = min(self.reconnect_delay * jitter, self.max_reconnect_delay)

        self.logger.info(f"Reconnecting in {delay:.1f}s...")
        await asyncio.sleep(delay)

        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

        if await self.connect():
            self.logger.info("Successfully reconnected to Polygon WebSocket")
        else:
            await self._reconnect()  # Retry

    async def start(self) -> None:
        """Start the feed handler."""
        # Start heartbeat check
        asyncio.create_task(self._heartbeat_check())

        while True:
            try:
                if not self.is_connected:
                    if not await self.connect():
                        await asyncio.sleep(1)
                        continue

                # Main message loop
                async for message in self.websocket:
                    await self._handle_message(message)

            except ConnectionClosed:
                self.logger.warning("WebSocket connection closed, reconnecting...")
                await self._reconnect()

            except Exception as e:
                self.logger.error(f"Unexpected error in feed handler: {e}")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the feed handler."""
        self.is_connected = False
        await self.disconnect()


class SimulatedFeedHandler(LoggerMixin):
    """Simulated feed handler for development/testing when Polygon key is not available."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state
        self.is_running = False

    async def start(self) -> None:
        """Start simulated data feed."""
        self.is_running = True
        self.logger.info("Starting simulated data feed")

        symbols = settings.data_feed.polygon.symbols

        while self.is_running:
            try:
                for symbol in symbols:
                    # Generate simulated book delta
                    current_time = datetime.now(timezone.utc)

                    # Simple simulated price movement
                    base_price = 50000 if "BTC" in symbol else 3000
                    price_change = (current_time.second % 10 - 5) * 0.1  # Small oscillation
                    price = base_price + price_change

                    # Create simulated book delta
                    bids = [
                        {"price": Decimal(str(price - i * 0.5)), "size": Decimal(str(10 - i))}
                        for i in range(5)
                    ]
                    asks = [
                        {"price": Decimal(str(price + i * 0.5)), "size": Decimal(str(10 - i))}
                        for i in range(5)
                    ]

                    delta = BookDelta(
                        symbol=symbol,
                        bids=bids,
                        asks=asks,
                        timestamp=current_time
                    )

                    # Apply to order book
                    orderbook_manager = get_orderbook_manager()
                    orderbook_manager.apply_delta(delta)

                    # Create tick event
                    tick = Tick(
                        symbol=symbol,
                        timestamp=current_time,
                        event_type=EventType.BOOK_DELTA,
                        data=delta
                    )

                    # Add to session state
                    await self.session_state.add_tick(tick)

                await asyncio.sleep(0.1)  # Simulate high-frequency updates

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in simulated feed: {e}")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop simulated data feed."""
        self.is_running = False
        self.logger.info("Stopped simulated data feed")


def create_feed_handler(session_state: SessionState):
    """Factory function to create appropriate feed handler."""
    import os
    
    # Check for API key in multiple places
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        try:
            with open("polygon_api.txt", "r") as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            pass
    
    # Use Polygon REST API polling if we have a valid API key
    # (WebSocket SDK has issues with handler callbacks, REST polling works reliably)
    if api_key and api_key != "your_polygon_key":
        logger.info("Using Polygon REST API polling feed handler (reliable alternative to WebSocket)")
        from .polygon_rest_feed import create_polygon_rest_feed
        return create_polygon_rest_feed(session_state)
    else:
        logger.warning("No valid Polygon API key found, using simulated feed handler")
        return SimulatedFeedHandler(session_state)
