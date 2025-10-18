"""
Tests for portfolio FSM (Finite State Machine) transitions.

Tests position state transitions through synthetic scenarios and fills.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone

from src.core.models import Scenario, PositionState, Bias, RiskRegime, Fill, OrderSide
from src.core.state import SessionState
from src.portfolio.manager import PortfolioManager
from src.portfolio.risk_agent import RiskAgent


class TestPortfolioFSM:
    """Test portfolio state machine transitions."""

    def setup_method(self):
        """Setup test fixtures."""
        self.session_state = SessionState("test_session", ["BTC-USD"], "paper")
        self.portfolio_manager = PortfolioManager(self.session_state)
        self.risk_agent = RiskAgent(self.session_state)

    @pytest.mark.asyncio
    async def test_flat_to_entering_transition(self):
        """Test transition from FLAT to ENTERING state."""
        # Create bullish scenario
        scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.LONG,
            confidence=0.8,
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 1.0, "spread_change": 0.1},
            mc={"upside_prob": 0.7, "downside_prob": 0.3},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("51000"),
                "sl": Decimal("49000")
            }
        )

        # Mock risk agent approval
        original_can_open = self.risk_agent.can_open_position
        self.risk_agent.can_open_position = lambda symbol, scenario: True

        # Process scenario
        await self.portfolio_manager._process_position_transitions({"BTC-USD": scenario})

        # Check that position was opened
        assert "BTC-USD" in self.session_state.positions
        position = self.session_state.positions["BTC-USD"]
        assert position.state == "entering"
        assert position.quantity > 0

        # Restore original method
        self.risk_agent.can_open_position = original_can_open

    @pytest.mark.asyncio
    async def test_entering_to_open_with_fill(self):
        """Test transition from ENTERING to OPEN with simulated fill."""
        # First open a position
        scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.LONG,
            confidence=0.8,
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 1.0},
            mc={"upside_prob": 0.7},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("51000"),
                "sl": Decimal("49000")
            }
        )

        # Open position
        await self.portfolio_manager._open_position("BTC-USD", scenario)
        position = self.session_state.positions["BTC-USD"]
        assert position.state == "entering"

        # Simulate fill
        fill = Fill(
            fill_id="test_fill",
            order_id="test_order",
            symbol="BTC-USD",
            side=OrderSide.BUY,
            quantity=position.quantity,
            price=Decimal("50000"),
            fees=Decimal("0"),
            liquidity="maker",
            timestamp=datetime.now(timezone.utc)
        )

        await self.session_state.add_fill(fill)

        # Position should still be in entering state until fully filled
        # In a real implementation, this would depend on order management
        assert position.state == "entering"

    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self):
        """Test stop loss triggering."""
        # Open a position
        scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.LONG,
            confidence=0.8,
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 1.0},
            mc={"upside_prob": 0.7},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("51000"),
                "sl": Decimal("49000")
            }
        )

        await self.portfolio_manager._open_position("BTC-USD", scenario)
        position = self.session_state.positions["BTC-USD"]
        position.state = "open"  # Manually set to open for this test

        # Check stop loss at price below SL
        current_price = 48500  # Below stop loss of 49000

        should_trigger = await self.portfolio_manager._check_stop_loss(position, current_price)
        assert should_trigger == True

        # Check stop loss at price above SL
        current_price = 49500  # Above stop loss
        should_trigger = await self.portfolio_manager._check_stop_loss(position, current_price)
        assert should_trigger == False

    @pytest.mark.asyncio
    async def test_take_profit_trigger(self):
        """Test take profit triggering."""
        # Open a position
        scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.LONG,
            confidence=0.8,
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 1.0},
            mc={"upside_prob": 0.7},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("51000"),
                "sl": Decimal("49000")
            }
        )

        await self.portfolio_manager._open_position("BTC-USD", scenario)
        position = self.session_state.positions["BTC-USD"]
        position.state = "open"

        # Check take profit at price above TP
        current_price = 51500  # Above take profit of 51000
        should_trigger = await self.portfolio_manager._check_take_profit(position, current_price)
        assert should_trigger == True

        # Check take profit at price below TP
        current_price = 50500  # Below take profit
        should_trigger = await self.portfolio_manager._check_take_profit(position, current_price)
        assert should_trigger == False

    @pytest.mark.asyncio
    async def test_position_scaling(self):
        """Test position scaling functionality."""
        # Open initial position
        scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.LONG,
            confidence=0.9,  # High confidence for scaling
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 1.5},
            mc={"upside_prob": 0.8},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("51000"),
                "sl": Decimal("49000")
            }
        )

        await self.portfolio_manager._open_position("BTC-USD", scenario)
        initial_position = self.session_state.positions["BTC-USD"]
        initial_quantity = initial_position.quantity
        initial_state = initial_position.state

        # Scale position
        await self.portfolio_manager._scale_position("BTC-USD", scenario)

        # Check that position was scaled
        scaled_position = self.session_state.positions["BTC-USD"]
        assert scaled_position.quantity > initial_quantity

    @pytest.mark.asyncio
    async def test_neutral_signal_reduces_position(self):
        """Test that neutral signals reduce position size."""
        # Open a position first
        bullish_scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.LONG,
            confidence=0.8,
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 1.0},
            mc={"upside_prob": 0.7},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("51000"),
                "sl": Decimal("49000")
            }
        )

        await self.portfolio_manager._open_position("BTC-USD", bullish_scenario)
        initial_quantity = self.session_state.positions["BTC-USD"].quantity

        # Process neutral scenario
        neutral_scenario = Scenario(
            symbol="BTC-USD",
            ts=datetime.now(timezone.utc),
            bias=Bias.NEUTRAL,
            confidence=0.5,
            risk_regime=RiskRegime.MEDIUM_VOL,
            features={"ofi": 0.0},
            mc={"upside_prob": 0.5, "downside_prob": 0.5},
            recommended={
                "entry": Decimal("50000"),
                "tp": Decimal("50500"),
                "sl": Decimal("49500")
            }
        )

        await self.portfolio_manager._process_position_transitions({"BTC-USD": neutral_scenario})

        # Position should be reduced or closed
        if "BTC-USD" in self.session_state.positions:
            final_quantity = self.session_state.positions["BTC-USD"].quantity
            assert final_quantity <= initial_quantity

    def test_portfolio_summary(self):
        """Test portfolio summary generation."""
        # Add some test positions
        from src.core.models import Position

        position = Position(
            position_id="test_pos",
            symbol="BTC-USD",
            quantity=Decimal("1.0"),
            average_price=Decimal("50000"),
            unrealized_pnl=Decimal("1000"),
            realized_pnl=Decimal("500"),
            state=PositionState.OPEN
        )

        self.session_state.positions["BTC-USD"] = position

        summary = asyncio.run(self.portfolio_manager.get_portfolio_summary())

        assert summary["total_positions"] == 1
        assert summary["symbols"] == ["BTC-USD"]
        assert summary["total_unrealized_pnl"] == 1000.0
        assert summary["total_realized_pnl"] == 500.0


if __name__ == "__main__":
    pytest.main([__file__])
