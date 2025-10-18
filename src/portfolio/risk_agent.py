"""
Risk agent for TEPM system.

Enforces risk management rules including position limits, daily loss caps, and cooldowns.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from ..core.config import settings
from ..core.logger import LoggerMixin, logger
from ..core.models import Scenario
from ..core.state import SessionState
from ..data.orderbook import get_orderbook_manager


class RiskAgent(LoggerMixin):
    """Risk management agent."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state

        # Risk limits
        self.max_daily_loss_pct = settings.risk.max_daily_loss_pct / 100
        self.max_position_pct = settings.risk.max_position_pct / 100
        self.max_open_positions = settings.risk.max_open_positions
        self.slippage_bps_limit = settings.risk.slippage_bps_limit
        self.cooldown_min = settings.risk.cooldown_min

        # Daily tracking
        self.daily_pnl_start = 0.0
        self.session_start_equity = 100000  # Default $100k

        # Cooldown tracking
        self.consecutive_losses = 0
        self.last_loss_time: Optional[datetime] = None

    async def can_open_position(self, symbol: str, scenario: Scenario) -> bool:
        """Check if a new position can be opened."""
        # Check cooldown
        if self._is_in_cooldown():
            self.logger.warning(f"Position blocked for {symbol}: cooldown active")
            return False

        # Check daily loss limit
        if not self._check_daily_loss_limit():
            self.logger.warning(f"Position blocked for {symbol}: daily loss limit exceeded")
            return False

        # Check position limits
        if not self._check_position_limits(symbol):
            self.logger.warning(f"Position blocked for {symbol}: position limits exceeded")
            return False

        # Check symbol-specific limits
        if not self._check_symbol_limits(symbol):
            self.logger.warning(f"Position blocked for {symbol}: symbol limits exceeded")
            return False

        return True

    async def can_place_order(self, symbol: str, quantity: float, price: float) -> bool:
        """Check if an order can be placed."""
        # Check slippage
        if not self._check_slippage_limit(symbol, price):
            self.logger.warning(f"Order blocked for {symbol}: slippage limit exceeded")
            return False

        # Check position impact
        if not self._check_position_impact(symbol, quantity, price):
            self.logger.warning(f"Order blocked for {symbol}: position impact too high")
            return False

        return True

    def _is_in_cooldown(self) -> bool:
        """Check if system is in cooldown period."""
        if self.session_state.cooldown_until:
            return datetime.now(timezone.utc) < self.session_state.cooldown_until

        # Check consecutive losses cooldown
        if (self.consecutive_losses >= 2 and
            self.last_loss_time and
            (datetime.now(timezone.utc) - self.last_loss_time).total_seconds() < self.cooldown_min * 60):

            cooldown_until = self.last_loss_time + timedelta(minutes=self.cooldown_min)
            self.session_state.cooldown_until = cooldown_until

            return True

        return False

    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is exceeded."""
        current_pnl = self.session_state.session_pnl
        daily_loss = self.daily_pnl_start - current_pnl
        loss_pct = abs(daily_loss) / self.session_start_equity

        return loss_pct <= self.max_daily_loss_pct

    def _check_position_limits(self, symbol: str) -> bool:
        """Check global position limits."""
        # Count open positions (excluding flat)
        open_positions = sum(
            1 for p in self.session_state.positions.values()
            if p.quantity != 0
        )

        return open_positions < self.max_open_positions

    def _check_symbol_limits(self, symbol: str) -> bool:
        """Check symbol-specific limits."""
        # Get symbol config (Pydantic model, not dict)
        symbol_config = settings.risk.per_symbol.get(symbol)
        
        if not symbol_config:
            # No specific limits for this symbol, allow
            return True

        # Check max quantity (access as attribute, not dict)
        max_qty = symbol_config.max_qty if symbol_config else float('inf')
        current_qty = sum(
            abs(p.quantity) for p in self.session_state.positions.values()
            if p.symbol == symbol
        )

        if current_qty >= max_qty:
            return False

        # Check max leverage (simplified)
        max_leverage = symbol_config.max_leverage if symbol_config else 1.0

        return True  # Simplified - would need position value calculation

    def _check_slippage_limit(self, symbol: str, price: float) -> bool:
        """Check if slippage is within limits."""
        # Get current market price
        orderbook_manager = get_orderbook_manager()
        book = orderbook_manager.get_book(symbol)

        if not book:
            return True  # No book available, allow order

        mid_price = book.get_mid_price()
        if not mid_price:
            return True

        # Calculate slippage
        slippage_bps = abs(price - float(mid_price)) / float(mid_price) * 10000

        return slippage_bps <= self.slippage_bps_limit

    def _check_position_impact(self, symbol: str, quantity: float, price: float) -> bool:
        """Check if order would have excessive market impact."""
        notional = abs(quantity * price)

        # Simple check: notional should be < 1% of daily volume (simplified)
        max_notional = 1000000  # $1M default max order size

        return notional <= max_notional

    async def record_loss(self) -> None:
        """Record a losing trade for cooldown tracking."""
        self.consecutive_losses += 1
        self.last_loss_time = datetime.now(timezone.utc)

        if self.consecutive_losses >= 2:
            cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=self.cooldown_min)
            self.session_state.cooldown_until = cooldown_until

            self.logger.warning(
                f"Consecutive losses: {self.consecutive_losses}. "
                f"Cooldown activated until {cooldown_until}"
            )

    async def record_win(self) -> None:
        """Record a winning trade."""
        self.consecutive_losses = 0
        self.session_state.cooldown_until = None

    def get_risk_summary(self) -> Dict:
        """Get risk management summary."""
        open_positions = len([
            p for p in self.session_state.positions.values()
            if p.quantity != 0
        ])

        return {
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_position_pct": self.max_position_pct,
            "max_open_positions": self.max_open_positions,
            "current_open_positions": open_positions,
            "consecutive_losses": self.consecutive_losses,
            "cooldown_active": self._is_in_cooldown(),
            "cooldown_until": self.session_state.cooldown_until.isoformat() if self.session_state.cooldown_until else None,
            "daily_pnl": self.session_state.session_pnl,
            "daily_loss_pct": abs(self.session_state.session_pnl) / self.session_start_equity * 100
        }


# Global risk agent instance (will be initialized in main app)
risk_agent: Optional[RiskAgent] = None


def create_risk_agent(session_state: SessionState) -> RiskAgent:
    """Factory function to create risk agent."""
    global risk_agent
    risk_agent = RiskAgent(session_state)
    print(f"✅ Risk agent created: {id(risk_agent)}")
    return risk_agent


def get_risk_agent() -> Optional[RiskAgent]:
    """Get the current risk agent instance."""
    return risk_agent
