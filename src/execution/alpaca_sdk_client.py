"""
Alpaca SDK-based client for TEPM system.

Uses the official alpaca-py SDK for trading operations.
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLimitOrderRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce, OrderType as AlpacaOrderType

from ..core.config import settings
from ..core.logger import LoggerMixin, logger
from ..core.models import Fill, Order, OrderSide, OrderStatus, OrderType


class AlpacaSDKClient(LoggerMixin):
    """Alpaca SDK-based trading client."""

    def __init__(self, paper: bool = True, key_id: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Initialize Alpaca SDK client.
        
        Args:
            paper: If True, use paper trading. If False, use live trading.
            key_id: Alpaca API key ID (optional, will check env/file)
            secret_key: Alpaca secret key (optional, will check env/file)
        """
        self.paper = paper
        
        # Get credentials
        self.key_id = key_id or self._get_credential("ALPACA_KEY_ID", "APCA-API-KEY-ID")
        self.secret_key = secret_key or self._get_credential("ALPACA_SECRET_KEY", "APCA-API-SECRET-KEY")
        
        print(f"      🔑 Alpaca credentials loaded:")
        print(f"         Key ID: {self.key_id[:15] if self.key_id else 'None'}...")
        print(f"         Secret: {self.secret_key[:15] if self.secret_key else 'None'}...")
        print(f"         Paper mode: {paper}")
        
        if not self.key_id or not self.secret_key:
            raise ValueError("Alpaca API credentials not configured. Set ALPACA_KEY_ID and ALPACA_SECRET_KEY")
        
        # Create Alpaca trading client
        self.client = TradingClient(
            api_key=self.key_id,
            secret_key=self.secret_key,
            paper=paper
        )
        
        print(f"      ✅ Alpaca TradingClient initialized")
        self.logger.info(f"Initialized Alpaca SDK client (paper={paper})")

    def _get_credential(self, env_var: str, alt_var: str = None) -> Optional[str]:
        """Get credential from environment or file."""
        # Try primary environment variable
        cred = os.getenv(env_var)
        if cred:
            return cred
        
        # Try alternative environment variable
        if alt_var:
            cred = os.getenv(alt_var)
            if cred:
                return cred
        
        # Try reading from alpaca.txt
        try:
            with open("alpaca.txt", "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                if env_var == "ALPACA_KEY_ID" and len(lines) > 0:
                    return lines[0]
                elif env_var == "ALPACA_SECRET_KEY" and len(lines) > 1:
                    return lines[1]
        except FileNotFoundError:
            pass
        
        return None

    async def get_account(self) -> Dict:
        """Get account information."""
        try:
            account = self.client.get_account()
            return {
                "id": account.id,
                "status": account.status.value,
                "currency": account.currency,
                "buying_power": str(account.buying_power),
                "cash": str(account.cash),
                "portfolio_value": str(account.portfolio_value),
                "equity": str(account.equity),
            }
        except Exception as e:
            self.logger.error(f"Failed to get account: {e}")
            raise

    async def get_positions(self) -> List[Dict]:
        """Get current positions."""
        try:
            positions = self.client.get_all_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "qty": str(pos.qty),
                    "side": "long" if float(pos.qty) > 0 else "short",
                    "market_value": str(pos.market_value),
                    "avg_entry_price": str(pos.avg_entry_price),
                    "current_price": str(pos.current_price),
                    "unrealized_pl": str(pos.unrealized_pl),
                    "unrealized_plpc": str(pos.unrealized_plpc),
                }
                for pos in positions
            ]
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []

    async def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """Get orders."""
        try:
            request = GetOrdersRequest(
                status=status if status else None
            )
            orders = self.client.get_orders(filter=request)
            
            return [
                {
                    "id": order.id,
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "type": order.type.value,
                    "qty": str(order.qty),
                    "filled_qty": str(order.filled_qty),
                    "limit_price": str(order.limit_price) if order.limit_price else None,
                    "stop_price": str(order.stop_price) if order.stop_price else None,
                    "status": order.status.value,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                }
                for order in orders
            ]
        except Exception as e:
            self.logger.error(f"Failed to get orders: {e}")
            return []

    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "limit",
        time_in_force: str = "ioc",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict:
        """Place an order using Alpaca SDK."""
        try:
            # Convert side
            alpaca_side = AlpacaOrderSide.BUY if side.lower() == "buy" else AlpacaOrderSide.SELL
            
            # Convert time in force
            tif_map = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "fok": TimeInForce.FOK,
            }
            alpaca_tif = tif_map.get(time_in_force.lower(), TimeInForce.IOC)
            
            # Create appropriate order request
            if order_type.lower() == "market":
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    client_order_id=client_order_id,
                )
            elif order_type.lower() == "limit":
                if not limit_price:
                    raise ValueError("Limit price required for limit orders")
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    limit_price=limit_price,
                    client_order_id=client_order_id,
                )
            elif order_type.lower() == "stop_limit":
                if not limit_price or not stop_price:
                    raise ValueError("Limit price and stop price required for stop-limit orders")
                order_request = StopLimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=alpaca_tif,
                    limit_price=limit_price,
                    stop_price=stop_price,
                    client_order_id=client_order_id,
                )
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            # Submit order
            order = self.client.submit_order(order_request)
            
            self.logger.info(f"Placed {side} order for {qty} {symbol} @ {limit_price or 'market'}")
            
            return {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.type.value,
                "qty": str(order.qty),
                "status": order.status.value,
                "created_at": order.created_at.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.client.cancel_order_by_id(order_id)
            self.logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID."""
        try:
            order = self.client.get_order_by_id(order_id)
            return {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "type": order.type.value,
                "qty": str(order.qty),
                "filled_qty": str(order.filled_qty),
                "status": order.status.value,
                "limit_price": str(order.limit_price) if order.limit_price else None,
            }
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None

    async def close(self):
        """Close the client connection."""
        # Alpaca SDK doesn't require explicit cleanup
        self.logger.info("Alpaca SDK client closed")


class SimulatedAlpacaSDKClient(LoggerMixin):
    """Simulated Alpaca client for testing (SDK-compatible)."""

    def __init__(self):
        self.account = {
            "id": "sim_paper",
            "status": "ACTIVE",
            "currency": "USD",
            "buying_power": "100000.00",
            "cash": "100000.00",
            "portfolio_value": "100000.00",
            "equity": "100000.00",
        }
        self.positions = []
        self.orders = []
        self.order_counter = 0
        self.logger.info("Initialized simulated Alpaca SDK client")

    async def get_account(self) -> Dict:
        return self.account.copy()

    async def get_positions(self) -> List[Dict]:
        return self.positions.copy()

    async def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        if status:
            return [o for o in self.orders if o["status"] == status]
        return self.orders.copy()

    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "limit",
        time_in_force: str = "ioc",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None
    ) -> Dict:
        self.order_counter += 1
        order_id = f"sim_{self.order_counter}"
        
        order = {
            "id": order_id,
            "client_order_id": client_order_id or f"client_{self.order_counter}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "qty": str(qty),
            "filled_qty": "0",
            "status": "accepted",
            "limit_price": str(limit_price) if limit_price else None,
            "stop_price": str(stop_price) if stop_price else None,
            "created_at": datetime.utcnow().isoformat(),
        }
        
        self.orders.append(order)
        self.logger.info(f"Simulated order: {side} {qty} {symbol}")
        
        return order

    async def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order["id"] == order_id:
                order["status"] = "canceled"
                return True
        return False

    async def get_order(self, order_id: str) -> Optional[Dict]:
        for order in self.orders:
            if order["id"] == order_id:
                return order.copy()
        return None

    async def close(self):
        pass


def create_alpaca_sdk_client(paper: bool = True):
    """Factory function to create Alpaca SDK client - ALWAYS uses real SDK."""
    print(f"🔍 Creating REAL Alpaca SDK client (paper={paper})")
    
    try:
        client = AlpacaSDKClient(paper=paper)
        print(f"   ✅ AlpacaSDKClient created successfully")
        return client
    except Exception as e:
        print(f"   ❌ Error creating Alpaca client: {e}")
        import traceback
        traceback.print_exc()
        raise

