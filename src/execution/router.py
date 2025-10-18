"""
Execution router for TEPM system.

Routes orders to appropriate brokers (Alpaca or Coinbase) based on symbol and configuration.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from ..core.config import settings
from ..core.logger import LoggerMixin, logger, set_session_context
from ..core.models import Fill, Order, OrderSide, OrderStatus, OrderType
from ..core.state import SessionState
from ..core.utils import calculate_slippage, generate_idempotency_key, round_to_tick
from ..data.orderbook import get_orderbook_manager
from ..portfolio.risk_agent import get_risk_agent

# Try to use SDK clients, fallback to original if not available
try:
    from ..execution.alpaca_sdk_client import create_alpaca_sdk_client as create_alpaca_client
except ImportError:
    from ..execution.alpaca_api import create_alpaca_client

try:
    from ..execution.coinbase_api import create_coinbase_client
except ImportError:
    create_coinbase_client = None


class ExecutionRouter(LoggerMixin):
    """Order execution router."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state

        # Broker clients
        self.alpaca_client = create_alpaca_client()
        print(f"🔧 Alpaca client type: {type(self.alpaca_client).__name__}")
        
        # Coinbase is optional - only create if credentials available
        try:
            self.coinbase_client = create_coinbase_client() if create_coinbase_client else None
            if self.coinbase_client:
                print(f"🔧 Coinbase client created")
        except ValueError as e:
            print(f"ℹ️  Coinbase not configured (optional): {e}")
            self.coinbase_client = None

        # Idempotency tracking
        self.idempotency_cache: Dict[str, datetime] = {}

        # Cleanup task for expired idempotency keys
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the execution router."""
        self._cleanup_task = asyncio.create_task(self._cleanup_idempotency_cache())
        self.logger.info("Execution router started")

    async def stop(self) -> None:
        """Stop the execution router."""
        if self._cleanup_task:
            self._cleanup_task.cancel()

        await self.alpaca_client.close()
        await self.coinbase_client.close()

        self.logger.info("Execution router stopped")

    async def route_order(self, symbol: str, side: str, quantity: float,
                         order_type: str = "limit", price: Optional[float] = None,
                         reason: Optional[str] = None) -> Optional[Order]:
        """Route an order to the appropriate broker."""
        print(f"         🔀 ExecutionRouter.route_order({symbol}, {side}, {quantity}, price={price})")
        try:
            # Determine broker for this symbol
            broker = self._get_broker_for_symbol(symbol)
            print(f"            Broker: {broker}")

            # Pre-flight checks
            print(f"            Running pre-flight checks...")
            if not await self._pre_flight_check(symbol, quantity, price):
                print(f"            ❌ Pre-flight check failed")
                return None
            print(f"            ✅ Pre-flight checks passed")

            # Generate idempotency key
            idempotency_key = generate_idempotency_key("order", settings.execution.idempotency_key_ttl_sec)

            # Create order object
            order = Order(
                order_id=f"order_{symbol}_{int(time.time())}",
                symbol=symbol,
                side=OrderSide(side.lower()),  # Enum values are lowercase
                order_type=OrderType(order_type.lower()),  # Enum values are lowercase
                quantity=Decimal(str(quantity)),
                price=Decimal(str(price)) if price else None,
                tif=settings.execution.tif,
                idempotency_key=idempotency_key,
                reason=reason
            )

            # Check if order is allowed by risk agent
            risk_agent = get_risk_agent()
            if risk_agent and not await risk_agent.can_place_order(symbol, quantity, price or 0):
                self.logger.warning(f"Order blocked by risk agent: {order.order_id}")
                return None

            # Execute based on broker
            print(f"            Executing order via {broker}...")
            if broker == "alpaca":
                await self._execute_alpaca_order(order)
            elif broker == "coinbase":
                await self._execute_coinbase_order(order)
            else:
                self.logger.error(f"Unknown broker: {broker}")
                print(f"            ❌ Unknown broker: {broker}")
                return None

            # Add to session state
            await self.session_state.add_order(order)

            self.logger.info(f"Routed {order.order_type.value} {order.side.value} order for {symbol}: {quantity} @ {price}")
            print(f"            ✅ Order routed successfully: {order.order_id}")

            return order

        except Exception as e:
            self.logger.error(f"Error routing order for {symbol}: {e}")
            print(f"            ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_broker_for_symbol(self, symbol: str) -> str:
        """Determine which broker to use for a symbol."""
        # Check symbol-specific routing
        route = settings.execution.routes.get(symbol)
        if route:
            if route == "coinbase_live":
                return "coinbase"
            elif route.startswith("alpaca_"):
                return "alpaca"

        # Default broker
        return settings.execution.default_broker

    async def _pre_flight_check(self, symbol: str, quantity: float, price: Optional[float]) -> bool:
        """Perform pre-flight checks before placing order."""
        # Check if we have market data (skip for inverse ETFs - they use underlying data)
        from ..portfolio.inverse_mapping import get_inverse_mapper
        inverse_mapper = get_inverse_mapper()
        
        book = None
        if not inverse_mapper.is_inverse_instrument(symbol):
            # Normal instrument - check orderbook
            orderbook_manager = get_orderbook_manager()
            book = orderbook_manager.get_book(symbol)
            if not book:
                print(f"               ⚠️  No order book for {symbol}, allowing order anyway")
                # For now, allow - in production you'd fetch current price
        else:
            print(f"               ℹ️  {symbol} is inverse instrument, skipping orderbook check")

        # Check price bands if price provided (and we have book data)
        if price and book:
            mid_price = book.get_mid_price()
            if mid_price:
                slippage = calculate_slippage(Decimal(str(price)), mid_price)
                if slippage > settings.risk.slippage_bps_limit / 10000:  # Convert bps to decimal
                    self.logger.warning(f"Price {price} exceeds slippage limit for {symbol}")
                    return False

        # Check minimum notional
        if price and quantity:
            notional = price * quantity
            min_notional = 5.0  # $5 minimum
            if notional < min_notional:
                self.logger.warning(f"Notional {notional} below minimum for {symbol}")
                return False

        return True

    async def _execute_alpaca_order(self, order: Order) -> None:
        """Execute order via Alpaca."""
        print(f"            📡 _execute_alpaca_order called")
        print(f"               Client type: {type(self.alpaca_client).__name__}")
        print(f"               Is simulated: {'Simulated' in type(self.alpaca_client).__name__}")
        try:
            # Convert to Alpaca format
            alpaca_side = "buy" if order.side == OrderSide.BUY else "sell"

            # Place order
            print(f"               Calling alpaca_client.place_order()...")
            print(f"               Params: symbol={order.symbol}, qty={float(order.quantity)}, side={alpaca_side}")
            
            try:
                # Get TIF - it might be a string or enum
                tif = settings.execution.tif
                tif_str = tif.value.lower() if hasattr(tif, 'value') else str(tif).lower()
                
                alpaca_order = await self.alpaca_client.place_order(
                    symbol=order.symbol,
                    qty=float(order.quantity),
                    side=alpaca_side,
                    order_type=order.order_type.value,
                    time_in_force=tif_str,
                    limit_price=float(order.price) if order.price else None,
                    client_order_id=order.idempotency_key
                )
                
                print(f"               ✅ Alpaca SDK place_order() returned")
                print(f"               Response type: {type(alpaca_order)}")
                print(f"               Response: {alpaca_order}")

                # Update order status
                order.status = OrderStatus.OPEN
                
                if alpaca_order and 'id' in alpaca_order:
                    order.external_id = alpaca_order['id']
                    print(f"               📝 Alpaca Order ID: {order.external_id}")
                    print(f"               ✅ Order is LIVE on Alpaca dashboard!")
                else:
                    print(f"               ⚠️  No order ID in response")

            except Exception as api_error:
                print(f"               ❌ Alpaca API error: {api_error}")
                import traceback
                traceback.print_exc()
                raise

        except Exception as e:
            self.logger.error(f"Error executing Alpaca order: {e}")
            order.status = OrderStatus.REJECTED

    async def _execute_coinbase_order(self, order: Order) -> None:
        """Execute order via Coinbase."""
        try:
            # Convert to Coinbase format
            coinbase_side = order.side.value.upper()

            # Create order configuration
            order_config = {
                "size": str(order.quantity)
            }

            if order.order_type == OrderType.LIMIT and order.price:
                order_config["limit_limit_gtc"] = {
                    "base_size": str(order.quantity),
                    "limit_price": str(order.price)
                }
            elif order.order_type == OrderType.MARKET:
                order_config["market_market_ioc"] = {
                    "base_size": str(order.quantity)
                }

            # Place order
            coinbase_response = await self.coinbase_client.place_order(
                product_id=order.symbol,
                side=coinbase_side,
                order_configuration=order_config
            )

            # Update order status
            order.status = OrderStatus.OPEN

            # Simulate fill if in dry run mode
            if settings.execution.dry_run:
                asyncio.create_task(self._simulate_coinbase_fill(order, coinbase_response))

        except Exception as e:
            self.logger.error(f"Error executing Coinbase order: {e}")
            order.status = OrderStatus.REJECTED

    async def _simulate_alpaca_fill(self, order: Order, alpaca_order: Dict) -> None:
        """Simulate Alpaca order fill."""
        await asyncio.sleep(0.1)  # Small delay

        # Create simulated fill
        fill_price = float(alpaca_order.get("limit_price", alpaca_order.get("filled_avg_price", 50000)))

        fill = Fill(
            fill_id=f"fill_{order.order_id}_{int(time.time())}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=Decimal(str(fill_price)),
            fees=Decimal("0"),  # No fees in simulation
            liquidity="taker" if order.order_type == OrderType.MARKET else "maker",
            timestamp=datetime.now(timezone.utc)
        )

        # Add fill to state
        await self.session_state.add_fill(fill)

        # Update order status
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = fill.price

        self.logger.info(f"Simulated Alpaca fill: {fill}")

    async def _simulate_coinbase_fill(self, order: Order, coinbase_response: Dict) -> None:
        """Simulate Coinbase order fill."""
        await asyncio.sleep(0.1)  # Small delay

        # Create simulated fill
        fill_price = 50000.0  # Default price

        fill = Fill(
            fill_id=f"fill_{order.order_id}_{int(time.time())}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=Decimal(str(fill_price)),
            fees=Decimal("0"),  # No fees in simulation
            liquidity="taker" if order.order_type == OrderType.MARKET else "maker",
            timestamp=datetime.now(timezone.utc)
        )

        # Add fill to state
        await self.session_state.add_fill(fill)

        # Update order status
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.average_fill_price = fill.price

        self.logger.info(f"Simulated Coinbase fill: {fill}")

    async def _cleanup_idempotency_cache(self) -> None:
        """Clean up expired idempotency keys."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                current_time = datetime.now(timezone.utc)
                expired_keys = [
                    key for key, timestamp in self.idempotency_cache.items()
                    if (current_time - timestamp).total_seconds() > settings.execution.idempotency_key_ttl_sec
                ]

                for key in expired_keys:
                    del self.idempotency_cache[key]

                if expired_keys:
                    self.logger.info(f"Cleaned up {len(expired_keys)} expired idempotency keys")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error cleaning up idempotency cache: {e}")

    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status from broker."""
        order = self.session_state.orders.get(order_id)
        if not order:
            return None

        try:
            if self._get_broker_for_symbol(order.symbol) == "alpaca":
                alpaca_order = await self.alpaca_client.get_order(order_id)
                if alpaca_order:
                    # Update order status based on Alpaca response
                    status_map = {
                        "new": OrderStatus.OPEN,
                        "partially_filled": OrderStatus.PARTIALLY_FILLED,
                        "filled": OrderStatus.FILLED,
                        "cancelled": OrderStatus.CANCELLED,
                        "rejected": OrderStatus.REJECTED
                    }
                    order.status = status_map.get(alpaca_order.get("status", ""), order.status)

            elif self._get_broker_for_symbol(order.symbol) == "coinbase":
                coinbase_order = await self.coinbase_client.get_order(order_id)
                if coinbase_order:
                    # Update order status based on Coinbase response
                    status_map = {
                        "PENDING": OrderStatus.OPEN,
                        "OPEN": OrderStatus.OPEN,
                        "FILLED": OrderStatus.FILLED,
                        "CANCELLED": OrderStatus.CANCELLED,
                        "REJECTED": OrderStatus.REJECTED
                    }
                    order.status = status_map.get(coinbase_order.get("status", ""), order.status)

        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")

        return order

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        order = self.session_state.orders.get(order_id)
        if not order:
            return False

        try:
            if self._get_broker_for_symbol(order.symbol) == "alpaca":
                return await self.alpaca_client.cancel_order(order_id)
            elif self._get_broker_for_symbol(order.symbol) == "coinbase":
                return await self.coinbase_client.cancel_order(order_id)
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False


# Global execution router instance
def create_execution_router(session_state: SessionState) -> ExecutionRouter:
    """Factory function to create execution router."""
    return ExecutionRouter(session_state)
