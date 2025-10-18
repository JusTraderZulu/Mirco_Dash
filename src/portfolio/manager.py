"""
Portfolio manager for TEPM system.

Handles position state machine, sizing, and portfolio-level decisions.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from ..core.config import settings
from ..core.logger import LoggerMixin, logger, set_session_context
from ..core.models import Position, PositionState, Scenario
from ..core.state import SessionState
from ..portfolio.inverse_mapping import get_inverse_mapper
from ..portfolio.risk_agent import get_risk_agent


class PortfolioManager(LoggerMixin):
    """Portfolio manager with state machine."""

    def __init__(self, session_state: SessionState, execution_router=None):
        self.session_state = session_state
        self.execution_router = execution_router  # Will be set after initialization
        self.is_running = False

        # Portfolio state
        self.positions: Dict[str, Position] = {}
        self.target_allocations: Dict[str, float] = {}

        # Rebalance cadence
        self.rebalance_interval = settings.portfolio.rebalance_cadence_sec

        # Risk parameters
        self.tp_atr_mult = settings.portfolio.take_profit_atr_mult
        self.sl_atr_mult = settings.portfolio.stop_atr_mult
        self.scale_out_levels = settings.portfolio.scale_out_levels

        # Tasks
        self._rebalance_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start portfolio manager."""
        self.is_running = True
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())

        self.logger.info("Portfolio manager started")

    async def stop(self) -> None:
        """Stop portfolio manager."""
        self.is_running = False

        if self._rebalance_task:
            self._rebalance_task.cancel()

        self.logger.info("Portfolio manager stopped")

    async def _rebalance_loop(self) -> None:
        """Main rebalance loop."""
        while self.is_running:
            try:
                await asyncio.sleep(self.rebalance_interval)

                if not self.is_running:
                    break

                await self._rebalance_portfolio()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in rebalance loop: {e}")
                await asyncio.sleep(10)

    async def _rebalance_portfolio(self) -> None:
        """Rebalance portfolio based on latest scenarios."""
        print(f"\n💼 Portfolio Manager: Rebalancing...")
        
        # Get recent scenarios for each symbol
        recent_scenarios = {}
        for symbol in self.session_state.symbols:
            scenarios = [s for s in self.session_state.scenarios if s.symbol == symbol]
            if scenarios:
                recent_scenarios[symbol] = scenarios[-1]  # Most recent
        
        print(f"   📊 Found {len(recent_scenarios)} scenarios to process")
        for symbol, scenario in recent_scenarios.items():
            print(f"      {symbol}: {scenario.bias.value.upper()} (conf: {scenario.confidence:.1%})")

        # Update target allocations based on scenarios
        await self._update_target_allocations(recent_scenarios)

        # Check for position transitions
        await self._process_position_transitions(recent_scenarios)

    async def _update_target_allocations(self, scenarios: Dict[str, Scenario]) -> None:
        """Update target portfolio allocations based on scenarios."""
        total_confidence = 0
        weighted_allocations = {}

        for symbol, scenario in scenarios.items():
            if scenario.bias == "neutral":
                continue

            # Weight by confidence and risk regime
            risk_multiplier = {
                "low_vol": 1.2,
                "medium_vol": 1.0,
                "high_vol": 0.8
            }.get(scenario.risk_regime.value, 1.0)

            weight = scenario.confidence * risk_multiplier
            weighted_allocations[symbol] = weight
            total_confidence += weight

        # Normalize to get target allocations
        if total_confidence > 0:
            self.target_allocations = {
                symbol: weight / total_confidence
                for symbol, weight in weighted_allocations.items()
            }
        else:
            self.target_allocations = {}

    async def _process_position_transitions(self, scenarios: Dict[str, Scenario]) -> None:
        """Process position state transitions based on scenarios."""
        print(f"   🔄 _process_position_transitions called with {len(scenarios)} scenarios")
        
        for symbol, scenario in scenarios.items():
            print(f"\n   🔍 Processing {symbol}:")
            print(f"      Scenario bias: {scenario.bias} (type: {type(scenario.bias)})")
            print(f"      Scenario bias.value: {scenario.bias.value}")
            
            current_position = self.positions.get(symbol)
            print(f"      Current position: {current_position}")

            if scenario.bias.value == "neutral":
                print(f"      ⏭️  Skipping - neutral bias")
                # No strong signal - consider reducing position
                if current_position and current_position.state != "flat":
                    await self._reduce_position(symbol, "neutral_signal")
                continue
            
            # Handle SHORT signals for crypto via inverse ETFs
            target_symbol = symbol  # The symbol to actually trade
            is_inverse_trade = False
            
            if scenario.bias.value == "short":
                broker_route = settings.execution.routes.get(symbol, settings.execution.default_broker)
                if "alpaca" in broker_route.lower():
                    # Check if we have an inverse instrument
                    inverse_mapper = get_inverse_mapper()
                    if inverse_mapper.supports_inverse(symbol):
                        inverse_symbol = inverse_mapper.get_inverse_symbol(symbol)
                        print(f"      🔄 SHORT {symbol} → LONG {inverse_symbol} (inverse ETF)")
                        target_symbol = inverse_symbol
                        is_inverse_trade = True
                        # Flip the scenario to LONG for the inverse instrument
                        from ..core.models import Bias
                        scenario.bias = Bias.LONG
                    else:
                        print(f"      ⏭️  Skipping SHORT signal - No inverse instrument for {symbol}")
                        continue

            # Check risk rules first
            print(f"      🛡️  Checking risk agent...")
            risk_agent = get_risk_agent()
            if not risk_agent:
                print(f"      ❌ No risk agent available!")
                continue
            
            print(f"      Risk agent found: {type(risk_agent).__name__}")
            
            try:
                can_open = await risk_agent.can_open_position(symbol, scenario)
                print(f"      Risk agent says: {'✅ OK' if can_open else '❌ BLOCKED'}")
            except Exception as e:
                print(f"      ❌ Risk agent error: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            if not can_open:
                self.logger.info(f"Risk agent blocked position for {symbol}")
                continue

            # Handle position based on current state and signal
            if not current_position or current_position.state == PositionState.FLAT:
                # Open new position
                print(f"      💼 No current position - will open new position")
                await self._open_position(target_symbol, scenario, original_symbol=symbol if is_inverse_trade else None)
            elif current_position.state == PositionState.OPEN:
                # Manage existing position
                await self._manage_open_position(symbol, scenario)
            elif current_position.state == PositionState.SCALING:
                # Continue scaling
                await self._scale_position(symbol, scenario)

    async def _open_position(self, symbol: str, scenario: Scenario, original_symbol: Optional[str] = None) -> None:
        """Open a new position."""
        print(f"   💼 Attempting to OPEN position for {symbol}...")
        if original_symbol:
            print(f"      (Inverse trade: {original_symbol} SHORT → {symbol} LONG)")
        try:
            # Calculate position size
            size = await self._calculate_position_size(symbol, scenario)

            if size <= 0:
                return

            # Create position
            position = Position(
                position_id=f"pos_{symbol}_{int(time.time())}",
                symbol=symbol,
                quantity=Decimal(str(size)),
                average_price=Decimal(str(scenario.recommended["entry"])),
                state=PositionState.ENTERING,
                entry_time=datetime.now(timezone.utc),
                stop_loss=Decimal(str(scenario.recommended["sl"])),
                take_profit=Decimal(str(scenario.recommended["tp"]))
            )

            self.positions[symbol] = position
            await self.session_state.update_position(position)

            self.logger.info(
                f"Opened position for {symbol}: {size} @ {scenario.recommended['entry']} "
                f"(TP: {scenario.recommended['tp']}, SL: {scenario.recommended['sl']})"
            )
            
            # Actually place the order through execution router
            if self.execution_router:
                print(f"      📈 Placing order through execution router...")
                side = "buy" if scenario.bias.value == "long" else "sell"
                entry_price = float(scenario.recommended["entry"])
                
                # Use market orders for inverse ETFs (no orderbook data), limit for direct instruments
                from ..portfolio.inverse_mapping import get_inverse_mapper
                inverse_mapper = get_inverse_mapper()
                is_inverse = inverse_mapper.is_inverse_instrument(symbol)
                
                order_type = "market" if is_inverse else "limit"
                price = None if is_inverse else entry_price
                
                print(f"         Order type: {order_type.upper()}")
                
                order = await self.execution_router.route_order(
                    symbol=symbol,
                    side=side,
                    quantity=size,
                    order_type=order_type,
                    price=price,
                    reason=f"{scenario.bias.value}_signal_conf_{scenario.confidence:.0%}"
                )
                
                if order:
                    print(f"      ✅ Order placed: {order.order_id}")
                else:
                    print(f"      ❌ Order placement failed")
            else:
                print(f"      ⚠️  No execution router - position created but no order placed")

        except Exception as e:
            self.logger.error(f"Error opening position for {symbol}: {e}")
            import traceback
            traceback.print_exc()

    async def _manage_open_position(self, symbol: str, scenario: Scenario) -> None:
        """Manage an open position."""
        position = self.positions[symbol]

        # Check TP/SL levels
        current_price = await self._get_current_price(symbol)
        
        print(f"      📊 Monitoring {symbol} position:")
        print(f"         Current: ${current_price:.2f}")
        print(f"         Entry: ${float(position.average_price):.2f}")
        print(f"         TP: ${float(position.take_profit):.2f}" if position.take_profit else "         TP: None")
        print(f"         SL: ${float(position.stop_loss):.2f}" if position.stop_loss else "         SL: None")

        if await self._check_stop_loss(position, current_price):
            print(f"      🛑 STOP LOSS HIT! Closing position...")
            await self._close_position(symbol, "stop_loss")
            return

        if await self._check_take_profit(position, current_price):
            print(f"      🎯 TAKE PROFIT HIT! Scaling out 50%...")
            await self._partial_close_position(symbol, 0.5)  # Scale out 50%
            return
        
        print(f"      ✅ Position OK (within TP/SL range)")

        # Check for scaling opportunity
        if scenario.confidence > 0.8 and position.state == PositionState.OPEN:
            await self._scale_position(symbol, scenario)

    async def _scale_position(self, symbol: str, scenario: Scenario) -> None:
        """Scale into an existing position."""
        position = self.positions[symbol]

        if position.state != "open":
            return

        # Calculate additional size
        additional_size = await self._calculate_position_size(symbol, scenario, scale_factor=0.5)

        if additional_size > 0:
            # Update position
            total_quantity = position.quantity + Decimal(str(additional_size))
            weighted_avg_price = (position.quantity * position.average_price +
                                Decimal(str(additional_size)) * scenario.recommended["entry"]) / total_quantity

            position.quantity = total_quantity
            position.average_price = weighted_avg_price
            position.state = "scaling"

            await self.session_state.update_position(position)

            self.logger.info(f"Scaled position for {symbol}: +{additional_size} @ {scenario.recommended['entry']}")

    async def _reduce_position(self, symbol: str, reason: str) -> None:
        """Reduce position size."""
        position = self.positions.get(symbol)

        if not position or position.state == PositionState.FLAT:
            return

        # Reduce by 50% for now
        reduction_ratio = 0.5
        remaining_quantity = position.quantity * (1 - reduction_ratio)

        if remaining_quantity <= 0:
            await self._close_position(symbol, reason)
        else:
            position.quantity = remaining_quantity
            await self.session_state.update_position(position)

            self.logger.info(f"Reduced position for {symbol} ({reason}): {remaining_quantity}")

    async def _partial_close_position(self, symbol: str, close_ratio: float) -> None:
        """Partially close a position."""
        position = self.positions.get(symbol)

        if not position:
            return

        close_quantity = position.quantity * close_ratio

        if close_quantity >= position.quantity:
            await self._close_position(symbol, "full_close")
        else:
            # Update position for partial close
            position.quantity -= close_quantity
            await self.session_state.update_position(position)

            self.logger.info(f"Partially closed position for {symbol}: -{close_quantity}")

    async def _close_position(self, symbol: str, reason: str) -> None:
        """Close a position completely."""
        position = self.positions.get(symbol)

        if not position:
            return

        # Set exit time and state
        position.exit_time = datetime.now(timezone.utc)
        position.state = "flat"

        await self.session_state.update_position(position)

        # Remove from active positions
        del self.positions[symbol]

        self.logger.info(f"Closed position for {symbol} ({reason})")

    async def _calculate_position_size(self, symbol: str, scenario: Scenario, scale_factor: float = 1.0) -> float:
        """Calculate position size based on sizing configuration."""
        # Get account equity (simplified)
        account_equity = 100000  # Default $100k

        # Fixed fractional sizing
        if settings.sizing.method == "fixed_fractional":
            target_dollars = account_equity * settings.sizing.fraction_of_equity
            
            print(f"         Target position size: ${target_dollars:.2f}")

            # Get current price to convert dollars to shares/quantity
            current_price = float(scenario.recommended.get("entry", 0))
            
            # For inverse instruments, fetch actual market price from Alpaca
            from ..portfolio.inverse_mapping import get_inverse_mapper
            inverse_mapper = get_inverse_mapper()
            if inverse_mapper.is_inverse_instrument(symbol):
                # Fetch current price from Alpaca
                if self.execution_router and self.execution_router.alpaca_client:
                    try:
                        # Get latest trade price from Alpaca
                        import httpx
                        # Use Alpaca's data API to get last trade
                        alpaca_key = self.execution_router.alpaca_client.key_id
                        alpaca_secret = self.execution_router.alpaca_client.secret_key
                        
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                                headers={
                                    "APCA-API-KEY-ID": alpaca_key,
                                    "APCA-API-SECRET-KEY": alpaca_secret
                                }
                            )
                            if response.status_code == 200:
                                data = response.json()
                                current_price = data['trade']['p']  # Price
                                print(f"         {symbol} current market price: ${current_price:.2f} (from Alpaca)")
                            else:
                                current_price = 20.0  # Fallback
                                print(f"         {symbol} fallback price: ${current_price:.2f}")
                    except Exception as e:
                        current_price = 20.0  # Fallback
                        print(f"         {symbol} fallback price: ${current_price:.2f} (fetch error)")
                else:
                    current_price = 20.0
                    print(f"         {symbol} fallback price: ${current_price:.2f}")
            
            if current_price > 0:
                quantity = target_dollars / current_price
                
                # Round to whole shares for stocks (Alpaca requirement with IOC)
                if inverse_mapper.is_inverse_instrument(symbol):
                    quantity = round(quantity)  # Whole shares only
                    print(f"         Calculated quantity: {quantity} shares (rounded to whole shares)")
                else:
                    print(f"         Calculated quantity: {quantity:.8f}")
            else:
                quantity = target_dollars  # Fallback
            
            # Adjust for symbol-specific risk
            symbol_config = settings.risk.per_symbol.get(symbol)
            max_qty = symbol_config.max_qty if symbol_config else float('inf')

            size = min(quantity, max_qty * scale_factor)

        else:
            size = account_equity * 0.02  # Default 2% sizing

        return size

    async def _get_current_price(self, symbol: str) -> float:
        """Get current market price for a symbol."""
        from ..data.orderbook import get_orderbook_manager
        
        orderbook_manager = get_orderbook_manager()
        book = orderbook_manager.get_book(symbol)
        if book:
            mid_price = book.get_mid_price()
            if mid_price:
                return float(mid_price)

        return 0.0

    async def _check_stop_loss(self, position: Position, current_price: float) -> bool:
        """Check if stop loss should be triggered."""
        if not position.stop_loss:
            return False

        if position.quantity > 0:  # Long position
            return current_price <= float(position.stop_loss)
        else:  # Short position
            return current_price >= float(position.stop_loss)

    async def _check_take_profit(self, position: Position, current_price: float) -> bool:
        """Check if take profit should be triggered."""
        if not position.take_profit:
            return False

        if position.quantity > 0:  # Long position
            return current_price >= float(position.take_profit)
        else:  # Short position
            return current_price <= float(position.take_profit)

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_realized = sum(p.realized_pnl for p in self.positions.values())

        return {
            "total_positions": len(self.positions),
            "symbols": list(self.positions.keys()),
            "total_unrealized_pnl": float(total_unrealized),
            "total_realized_pnl": float(total_realized),
            "target_allocations": self.target_allocations
        }


# Global portfolio manager instance
def create_portfolio_manager(session_state: SessionState) -> PortfolioManager:
    """Factory function to create portfolio manager."""
    return PortfolioManager(session_state)
