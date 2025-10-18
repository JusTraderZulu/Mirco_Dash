"""
Pydantic models for TEPM system data structures.

Defines schemas for ticks, orders, fills, positions, signals, and other core entities.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionState(str, Enum):
    """Position state enumeration."""
    FLAT = "flat"
    ENTERING = "entering"
    OPEN = "open"
    SCALING = "scaling"
    REDUCING = "reducing"
    EXITING = "exiting"


class TIF(str, Enum):
    """Time in Force enumeration."""
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTC = "GTC"  # Good 'til Cancelled


class Liquidity(str, Enum):
    """Liquidity indicator enumeration."""
    MAKER = "maker"
    TAKER = "taker"


class Bias(str, Enum):
    """Signal bias enumeration."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class RiskRegime(str, Enum):
    """Risk regime enumeration."""
    LOW_VOL = "low_vol"
    MEDIUM_VOL = "medium_vol"
    HIGH_VOL = "high_vol"


class EventType(str, Enum):
    """Market event type enumeration."""
    BOOK_DELTA = "book_delta"
    BOOK_SNAPSHOT = "book_snapshot"
    TRADE = "trade"
    QUOTE = "quote"
    HEARTBEAT = "heartbeat"
    INCIDENT = "incident"


# Base models for common fields
class TimestampedModel(BaseModel):
    """Base model with timestamp."""
    ts: datetime = Field(default_factory=datetime.utcnow)


class BaseOrderBookLevel(BaseModel):
    """Base order book level."""
    price: Decimal
    size: Decimal


class BidLevel(BaseOrderBookLevel):
    """Bid side order book level."""
    pass


class AskLevel(BaseOrderBookLevel):
    """Ask side order book level."""
    pass


class OrderBookSnapshot(BaseModel):
    """Order book snapshot."""
    symbol: str
    bids: List[BidLevel]
    asks: List[AskLevel]
    checksum: Optional[str] = None
    sequence: Optional[int] = None


class BookDelta(BaseModel):
    """Order book delta."""
    symbol: str
    bids: List[BidLevel] = []
    asks: List[AskLevel] = []
    timestamp: datetime


class Trade(BaseModel):
    """Trade event."""
    symbol: str
    price: Decimal
    size: Decimal
    timestamp: datetime
    conditions: List[str] = []
    exchange: Optional[int] = None
    tape: Optional[str] = None


class Quote(BaseModel):
    """Quote event."""
    symbol: str
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    timestamp: datetime
    bid_exchange: Optional[int] = None
    ask_exchange: Optional[int] = None


class Tick(BaseModel):
    """Generic tick event."""
    symbol: str
    timestamp: datetime
    event_type: EventType
    data: Union[BookDelta, Trade, Quote, OrderBookSnapshot, Dict[str, Any]]


class Scenario(BaseModel):
    """Trade scenario from signal engine."""
    symbol: str
    ts: datetime
    bias: Bias
    confidence: float
    risk_regime: RiskRegime
    features: Dict[str, float]
    mc: Dict[str, float]
    recommended: Dict[str, Decimal]


class Order(BaseModel):
    """Order entity."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None  # None for market orders
    tif: TIF = TIF.IOC
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    filled_quantity: Decimal = Decimal('0')
    average_fill_price: Optional[Decimal] = None
    fees: Decimal = Decimal('0')
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None
    external_id: Optional[str] = None  # Broker's order ID


class Fill(BaseModel):
    """Fill entity."""
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fees: Decimal
    liquidity: Liquidity
    timestamp: datetime
    exchange_fill_id: Optional[str] = None


class Position(BaseModel):
    """Position entity."""
    position_id: str
    symbol: str
    quantity: Decimal
    average_price: Decimal
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    state: PositionState = PositionState.FLAT
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    max_adverse_excursion: Decimal = Decimal('0')
    max_favorable_excursion: Decimal = Decimal('0')


class Incident(BaseModel):
    """Incident entity for tracking system issues."""
    incident_id: str
    timestamp: datetime
    component: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    message: str
    extra: Dict[str, Any] = {}


class Session(BaseModel):
    """Trading session entity."""
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    env: str  # dev, paper, live
    symbols: List[str]
    config_hash: str
    status: str = "active"  # active, paused, stopped


class Metric(BaseModel):
    """Metric entity for observability."""
    timestamp: datetime
    name: str
    value: float
    labels: Dict[str, str] = {}
