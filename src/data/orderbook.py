"""
In-memory order book management for TEPM system.

Maintains top-k depth per side, applies deltas, and generates snapshots.
"""

import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

from ..core.logger import LoggerMixin
from ..core.models import BidLevel, AskLevel, BookDelta, OrderBookSnapshot
from ..core.config import settings


class OrderBookLevel:
    """Order book level with price and size."""

    def __init__(self, price: Decimal, size: Decimal):
        self.price = price
        self.size = size

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "price": float(self.price),
            "size": float(self.size)
        }


class OrderBook(LoggerMixin):
    """In-memory order book for a single symbol."""

    def __init__(self, symbol: str, max_depth: int = 50):
        self.symbol = symbol
        self.max_depth = max_depth

        # Order book data: price -> size
        self.bids: Dict[Decimal, Decimal] = {}
        self.asks: Dict[Decimal, Decimal] = {}

        # Metadata
        self.last_update = datetime.now(timezone.utc)
        self.sequence: Optional[int] = None
        self.checksum: Optional[str] = None

        # Snapshot management
        self.snapshot_count = 0
        self._snapshot_task: Optional[asyncio.Task] = None
        self._snapshots_dir = Path(settings.storage.object_path)
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)

    def apply_delta(self, delta: BookDelta) -> None:
        """Apply a book delta to the order book."""
        self.last_update = datetime.now(timezone.utc)

        # Apply bid changes
        for bid in delta.bids:
            if bid.size == 0:
                self.bids.pop(bid.price, None)
            else:
                self.bids[bid.price] = bid.size

        # Apply ask changes
        for ask in delta.asks:
            if ask.size == 0:
                self.asks.pop(ask.price, None)
            else:
                self.asks[ask.price] = ask.size

        # Update sequence if provided
        if delta.timestamp and hasattr(delta, 'sequence'):
            self.sequence = getattr(delta, 'sequence', None)

        # Calculate checksum
        self._calculate_checksum()

    def get_top_levels(self, depth: Optional[int] = None) -> Tuple[List[BidLevel], List[AskLevel]]:
        """Get top-k levels for bids and asks."""
        depth = depth or self.max_depth

        # Get sorted bids (highest price first) and asks (lowest price first)
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])

        # Convert to BidLevel and AskLevel objects
        bids = [
            BidLevel(price=price, size=size)
            for price, size in sorted_bids[:depth]
        ]
        asks = [
            AskLevel(price=price, size=size)
            for price, size in sorted_asks[:depth]
        ]

        return bids, asks

    def get_best_bid(self) -> Optional[Decimal]:
        """Get best bid price."""
        if not self.bids:
            return None
        return max(self.bids.keys())

    def get_best_ask(self) -> Optional[Decimal]:
        """Get best ask price."""
        if not self.asks:
            return None
        return min(self.asks.keys())

    def get_mid_price(self) -> Optional[Decimal]:
        """Get mid price."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid is None or best_ask is None:
            return None

        return (best_bid + best_ask) / 2

    def get_spread(self) -> Optional[Decimal]:
        """Get bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()

        if best_bid is None or best_ask is None:
            return None

        return best_ask - best_bid

    def get_spread_bps(self) -> Optional[float]:
        """Get bid-ask spread in basis points."""
        spread = self.get_spread()
        mid_price = self.get_mid_price()

        if spread is None or mid_price is None or mid_price == 0:
            return None

        return float(spread / mid_price * 10000)

    def _calculate_checksum(self) -> None:
        """Calculate order book checksum for integrity verification."""
        # Simple checksum based on top 10 levels
        levels = []
        bids, asks = self.get_top_levels(10)

        for bid in bids:
            levels.append(f"{bid.price}:{bid.size}")
        for ask in asks:
            levels.append(f"{ask.price}:{ask.size}")

        checksum_data = "|".join(levels)
        self.checksum = hashlib.md5(checksum_data.encode()).hexdigest()[:8]

    def to_snapshot(self) -> OrderBookSnapshot:
        """Create a snapshot of the current order book."""
        bids, asks = self.get_top_levels()

        return OrderBookSnapshot(
            symbol=self.symbol,
            bids=bids,
            asks=asks,
            checksum=self.checksum,
            sequence=self.sequence
        )

    def save_snapshot(self) -> str:
        """Save current snapshot to Parquet file."""
        snapshot = self.to_snapshot()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{self.symbol}_snapshot_{timestamp}_{self.snapshot_count}.parquet"
        filepath = self._snapshots_dir / filename

        # Convert to PyArrow table
        data = {
            "symbol": [self.symbol],
            "timestamp": [self.last_update.isoformat()],
            "bids": [json.dumps([bid.to_dict() for bid in snapshot.bids])],
            "asks": [json.dumps([ask.to_dict() for ask in snapshot.asks])],
            "checksum": [self.checksum],
            "sequence": [self.sequence]
        }

        table = pa.Table.from_pydict(data)
        pq.write_table(table, filepath)

        self.snapshot_count += 1
        self.logger.info(f"Saved snapshot for {self.symbol} to {filepath}")

        return str(filepath)

    def is_empty(self) -> bool:
        """Check if order book is empty."""
        return len(self.bids) == 0 and len(self.asks) == 0


class OrderBookManager(LoggerMixin):
    """Manager for multiple order books."""

    def __init__(self):
        self.books: Dict[str, OrderBook] = {}
        self.snapshot_interval = settings.data_feed.polygon.snapshot_interval_sec
        self._snapshot_tasks: Dict[str, asyncio.Task] = {}

    def get_or_create_book(self, symbol: str) -> OrderBook:
        """Get or create order book for symbol."""
        if symbol not in self.books:
            self.books[symbol] = OrderBook(symbol)
            self.logger.info(f"Created order book for {symbol}")

        return self.books[symbol]

    def update_book_from_quote(self, symbol: str, quote) -> None:
        """Update order book from a quote (best bid/ask)."""
        book = self.get_or_create_book(symbol)
        
        # Update best bid
        if quote.bid_price and quote.bid_size:
            book.bids[quote.bid_price] = quote.bid_size
        
        # Update best ask
        if quote.ask_price and quote.ask_size:
            book.asks[quote.ask_price] = quote.ask_size
        
        book.last_update = quote.timestamp

    def apply_delta(self, delta: BookDelta) -> None:
        """Apply delta to the appropriate order book."""
        book = self.get_or_create_book(delta.symbol)
        book.apply_delta(delta)

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        """Get order book for symbol."""
        return self.books.get(symbol)

    def get_all_books(self) -> Dict[str, OrderBook]:
        """Get all order books."""
        return self.books.copy()

    def start_snapshot_scheduler(self) -> None:
        """Start periodic snapshot saving for all books."""
        for symbol, book in self.books.items():
            if symbol not in self._snapshot_tasks or self._snapshot_tasks[symbol].done():
                self._snapshot_tasks[symbol] = asyncio.create_task(
                    self._snapshot_loop(symbol, book)
                )

    def stop_snapshot_scheduler(self) -> None:
        """Stop all snapshot scheduling tasks."""
        for task in self._snapshot_tasks.values():
            if not task.done():
                task.cancel()

        self._snapshot_tasks.clear()

    async def _snapshot_loop(self, symbol: str, book: OrderBook) -> None:
        """Periodic snapshot loop for a single book."""
        while True:
            try:
                await asyncio.sleep(self.snapshot_interval)
                if not book.is_empty():
                    book.save_snapshot()
            except asyncio.CancelledError:
                self.logger.info(f"Snapshot loop cancelled for {symbol}")
                break
            except Exception as e:
                self.logger.error(f"Error in snapshot loop for {symbol}: {e}")
                await asyncio.sleep(1)  # Brief pause before retry

    def get_market_summary(self) -> Dict:
        """Get market summary across all books."""
        summary = {}

        for symbol, book in self.books.items():
            if not book.is_empty():
                summary[symbol] = {
                    "best_bid": float(book.get_best_bid()) if book.get_best_bid() else None,
                    "best_ask": float(book.get_best_ask()) if book.get_best_ask() else None,
                    "mid_price": float(book.get_mid_price()) if book.get_mid_price() else None,
                    "spread": float(book.get_spread()) if book.get_spread() else None,
                    "spread_bps": book.get_spread_bps(),
                    "last_update": book.last_update.isoformat()
                }

        return summary


# Global order book manager instance
orderbook_manager = OrderBookManager()


def get_orderbook_manager() -> OrderBookManager:
    """Get the global order book manager instance."""
    return orderbook_manager
