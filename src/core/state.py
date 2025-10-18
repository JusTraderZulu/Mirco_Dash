"""
Session state container for TEPM system.

Manages in-memory state for the current trading session.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from .logger import LoggerMixin
from .models import (
    Fill,
    Incident,
    Order,
    Position,
    Scenario,
    Session as SessionModel,
    Tick,
)


class SessionState(LoggerMixin):
    """Container for session state."""

    def __init__(self, session_id: str, symbols: List[str], env: str):
        self.session_id = session_id
        self.symbols = set(symbols)
        self.env = env
        self.started_at = datetime.now(timezone.utc)

        # Session status
        self.is_active = True
        self.is_paused = False

        # Data structures
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.fills: Dict[str, Fill] = {}
        self.scenarios: List[Scenario] = []
        self.incidents: List[Incident] = []

        # Symbol-specific data
        self.order_books: Dict[str, Dict] = defaultdict(dict)  # symbol -> book data
        self.ticks: Dict[str, List[Tick]] = defaultdict(list)  # symbol -> recent ticks
        self.last_tick_times: Dict[str, datetime] = {}

        # Performance tracking
        self.daily_pnl = 0.0
        self.session_pnl = 0.0
        self.total_fees = 0.0

        # Risk tracking
        self.consecutive_losses = 0
        self.last_loss_time: Optional[datetime] = None
        self.cooldown_until: Optional[datetime] = None

        # Synchronization
        self._lock = asyncio.Lock()

    async def add_tick(self, tick: Tick) -> None:
        """Add a tick to the state."""
        async with self._lock:
            if tick.symbol not in self.symbols:
                return

            self.ticks[tick.symbol].append(tick)
            self.last_tick_times[tick.symbol] = tick.timestamp

            # Keep only recent ticks (last 1000 per symbol)
            if len(self.ticks[tick.symbol]) > 1000:
                self.ticks[tick.symbol] = self.ticks[tick.symbol][-1000:]

    async def update_position(self, position: Position) -> None:
        """Update or add a position."""
        async with self._lock:
            self.positions[position.symbol] = position

            # Update P&L tracking
            if position.symbol not in self.positions:
                # New position
                if position.quantity != 0:
                    self.logger.info(
                        f"Opened position for {position.symbol}: {position.quantity} @ {position.average_price}"
                    )

            # Update session P&L
            self.session_pnl += float(position.realized_pnl)

    async def add_order(self, order: Order) -> None:
        """Add an order to the state."""
        async with self._lock:
            self.orders[order.order_id] = order

    async def update_order(self, order: Order) -> None:
        """Update an existing order."""
        async with self._lock:
            if order.order_id in self.orders:
                self.orders[order.order_id] = order

    async def add_fill(self, fill: Fill) -> None:
        """Add a fill to the state."""
        async with self._lock:
            self.fills[fill.fill_id] = fill

            # Update order status if filled
            if fill.order_id in self.orders:
                order = self.orders[fill.order_id]
                order.filled_quantity += fill.quantity
                order.average_fill_price = fill.price  # Simplified - should calculate weighted average
                order.fees += fill.fees

                if order.filled_quantity >= order.quantity:
                    order.status = "filled"  # Simplified status update

    async def add_scenario(self, scenario: Scenario) -> None:
        """Add a trading scenario."""
        async with self._lock:
            self.scenarios.append(scenario)

            # Keep only recent scenarios (last 100)
            if len(self.scenarios) > 100:
                self.scenarios = self.scenarios[-100:]

    async def add_incident(self, incident: Incident) -> None:
        """Add an incident."""
        async with self._lock:
            self.incidents.append(incident)

            # Keep only recent incidents (last 50)
            if len(self.incidents) > 50:
                self.incidents = self.incidents[-50:]

            self.logger.warning(
                f"Incident recorded: {incident.severity} - {incident.message}",
                component=incident.component
            )

    async def get_positions_summary(self) -> Dict:
        """Get summary of current positions."""
        async with self._lock:
            return {
                "total_positions": len([p for p in self.positions.values() if p.quantity != 0]),
                "total_unrealized_pnl": float(sum(p.unrealized_pnl for p in self.positions.values())),
                "total_realized_pnl": float(sum(p.realized_pnl for p in self.positions.values())),
                "symbols": list(self.positions.keys())
            }

    async def get_orders_summary(self) -> Dict:
        """Get summary of current orders."""
        async with self._lock:
            by_status = defaultdict(int)
            for order in self.orders.values():
                by_status[order.status] += 1

            return {
                "total_orders": len(self.orders),
                "by_status": dict(by_status)
            }

    def is_healthy(self) -> bool:
        """Check if session is healthy."""
        return (
            self.is_active and
            not self.is_paused and
            len(self.incidents) == 0 or
            all(i.severity.lower() != 'critical' for i in self.incidents[-5:])
        )

    def should_cooldown(self) -> bool:
        """Check if system should be in cooldown."""
        return (
            self.cooldown_until is not None and
            datetime.now(timezone.utc) < self.cooldown_until
        )
