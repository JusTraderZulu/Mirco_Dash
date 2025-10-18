"""
Pytest configuration and fixtures for TEPM tests.
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from src.core.state import SessionState
from src.core.models import BookDelta, Quote, Trade


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_session_state():
    """Create a sample session state for testing."""
    return SessionState("test_session", ["BTC-USD", "ETH-USD"], "paper")


@pytest.fixture
def sample_book_delta():
    """Create a sample book delta for testing."""
    return BookDelta(
        symbol="BTC-USD",
        bids=[
            {"price": Decimal("50000"), "size": Decimal("1.0")},
            {"price": Decimal("49999"), "size": Decimal("0.5")},
        ],
        asks=[
            {"price": Decimal("50001"), "size": Decimal("1.0")},
            {"price": Decimal("50002"), "size": Decimal("0.5")},
        ],
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_quote():
    """Create a sample quote for testing."""
    return Quote(
        symbol="BTC-USD",
        bid_price=Decimal("50000"),
        bid_size=Decimal("1.0"),
        ask_price=Decimal("50001"),
        ask_size=Decimal("1.0"),
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_trade():
    """Create a sample trade for testing."""
    return Trade(
        symbol="BTC-USD",
        price=Decimal("50000"),
        size=Decimal("0.1"),
        timestamp=datetime.now(timezone.utc),
        conditions=["regular"],
        exchange=1
    )


@pytest.fixture
def sample_tick(sample_book_delta):
    """Create a sample tick for testing."""
    class MockEventType:
        BOOK_DELTA = "book_delta"

    class MockTick:
        def __init__(self, symbol, timestamp, event_type, data):
            self.symbol = symbol
            self.timestamp = timestamp
            self.event_type = event_type
            self.data = data

    return MockTick(
        symbol="BTC-USD",
        timestamp=datetime.now(timezone.utc),
        event_type=MockEventType.BOOK_DELTA,
        data=sample_book_delta
    )
