"""
Tests for OFI (Order Flow Imbalance) calculations.

Tests microstructure signal calculations with synthetic data.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.core.models import BookDelta, Quote
from src.signals.microstructure import MicrostructureSignals


class TestOFI:
    """Test OFI calculation functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.signals = MicrostructureSignals(lookback_window=100)

    def test_ofi_from_book_delta_balanced(self):
        """Test OFI calculation with balanced bid/ask changes."""
        # Create balanced delta
        delta = BookDelta(
            symbol="BTC-USD",
            bids=[
                {"price": Decimal("50000"), "size": Decimal("1.0")}
            ],
            asks=[
                {"price": Decimal("50001"), "size": Decimal("1.0")}
            ],
            timestamp=datetime.now(timezone.utc)
        )

        # Calculate OFI
        ofi = self.signals._calculate_ofi(delta)

        # Should be close to 0 (balanced)
        assert abs(ofi) < 0.1

    def test_ofi_from_book_delta_bid_heavy(self):
        """Test OFI calculation with bid-heavy changes."""
        # Create bid-heavy delta
        delta = BookDelta(
            symbol="BTC-USD",
            bids=[
                {"price": Decimal("50000"), "size": Decimal("2.0")}
            ],
            asks=[
                {"price": Decimal("50001"), "size": Decimal("0.5")}
            ],
            timestamp=datetime.now(timezone.utc)
        )

        # Calculate OFI
        ofi = self.signals._calculate_ofi(delta)

        # Should be positive (buying pressure)
        assert ofi > 0.5

    def test_ofi_from_book_delta_ask_heavy(self):
        """Test OFI calculation with ask-heavy changes."""
        # Create ask-heavy delta
        delta = BookDelta(
            symbol="BTC-USD",
            bids=[
                {"price": Decimal("50000"), "size": Decimal("0.5")}
            ],
            asks=[
                {"price": Decimal("50001"), "size": Decimal("2.0")}
            ],
            timestamp=datetime.now(timezone.utc)
        )

        # Calculate OFI
        ofi = self.signals._calculate_ofi(delta)

        # Should be negative (selling pressure)
        assert ofi < -0.5

    def test_ofi_from_quote_improvement(self):
        """Test OFI calculation from quote improvement."""
        # Create quote with improved bid
        quote = Quote(
            symbol="BTC-USD",
            bid_price=Decimal("50000"),
            bid_size=Decimal("1.5"),
            ask_price=Decimal("50001"),
            ask_size=Decimal("1.0"),
            timestamp=datetime.now(timezone.utc)
        )

        # Add previous quote for comparison
        prev_quote = Quote(
            symbol="BTC-USD",
            bid_price=Decimal("49999"),
            bid_size=Decimal("1.0"),
            ask_price=Decimal("50001"),
            ask_size=Decimal("1.0"),
            timestamp=datetime.now(timezone.utc)
        )

        # Manually set previous quote in history
        self.signals.price_history["BTC-USD"].append(50000.0)

        # Calculate OFI
        ofi = self.signals._calculate_quote_ofi(quote)

        # Should be positive due to bid improvement
        assert ofi > 0

    def test_ofi_statistics(self):
        """Test OFI statistics calculation."""
        symbol = "BTC-USD"

        # Add some test data
        for i in range(10):
            delta = BookDelta(
                symbol=symbol,
                bids=[{"price": Decimal("50000"), "size": Decimal("1.0" if i % 2 == 0 else "0.5")}],
                asks=[{"price": Decimal("50001"), "size": Decimal("0.5" if i % 2 == 0 else "1.0")}],
                timestamp=datetime.now(timezone.utc)
            )
            self.signals.add_tick(type('MockTick', (), {
                'symbol': symbol,
                'timestamp': datetime.now(timezone.utc),
                'event_type': type('EventType', (), {'BOOK_DELTA': 'book_delta'})(),
                'data': delta
            })())

        # Get statistics
        stats = self.signals.get_ofi(symbol)

        assert stats["count"] > 0
        assert "mean" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats

    def test_empty_book_ofi(self):
        """Test OFI calculation with empty book."""
        delta = BookDelta(
            symbol="BTC-USD",
            bids=[],
            asks=[],
            timestamp=datetime.now(timezone.utc)
        )

        ofi = self.signals._calculate_ofi(delta)
        assert ofi == 0.0


if __name__ == "__main__":
    pytest.main([__file__])
