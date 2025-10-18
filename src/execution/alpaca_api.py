"""
Alpaca API client for TEPM system.

Async client for Alpaca paper and live trading.
"""

import asyncio
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import httpx

from ..core.config import settings
from ..core.logger import LoggerMixin, logger
from ..core.models import Fill, Order, OrderSide, OrderStatus, OrderType
from ..core.utils import generate_idempotency_key


class AlpacaClient(LoggerMixin):
    """Async Alpaca API client."""

    def __init__(self, base_url: Optional[str] = None, key_id: Optional[str] = None, secret_key: Optional[str] = None):
        self.base_url = base_url or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self.key_id = key_id or os.getenv("ALPACA_KEY_ID")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

        if not self.key_id or not self.secret_key:
            raise ValueError("Alpaca API credentials not configured")

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "APCA-API-KEY-ID": self.key_id,
                "APCA-API-SECRET-KEY": self.secret_key,
            },
            timeout=30.0
        )

    async def get_account(self) -> Dict:
        """Get account information."""
        try:
            response = await self.client.get("/v2/account")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get account: {e}")
            raise

    async def get_positions(self) -> List[Dict]:
        """Get current positions."""
        try:
            response = await self.client.get("/v2/positions")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []

    async def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """Get orders."""
        try:
            params = {}
            if status:
                params["status"] = status

            response = await self.client.get("/v2/orders", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get orders: {e}")
            return []

    async def place_order(self, symbol: str, qty: float, side: str,
                         order_type: str = "limit", time_in_force: str = "ioc",
                         limit_price: Optional[float] = None,
                         stop_price: Optional[float] = None,
                         client_order_id: Optional[str] = None) -> Dict:
        """Place an order."""
        try:
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": order_type,
                "time_in_force": time_in_force,
            }

            if limit_price:
                order_data["limit_price"] = limit_price
            if stop_price:
                order_data["stop_price"] = stop_price
            if client_order_id:
                order_data["client_order_id"] = client_order_id

            response = await self.client.post("/v2/orders", json=order_data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            response = await self.client.delete(f"/v2/orders/{order_id}")
            return response.status_code < 400
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID."""
        try:
            response = await self.client.get(f"/v2/orders/{order_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class SimulatedAlpacaClient(LoggerMixin):
    """Simulated Alpaca client for testing."""

    def __init__(self):
        self.account = {
            "id": "sim_paper",
            "status": "ACTIVE",
            "currency": "USD",
            "buying_power": "100000.00",
            "cash": "100000.00",
            "portfolio_value": "100000.00"
        }

        self.positions = []
        self.orders = []
        self.order_counter = 0

    async def get_account(self) -> Dict:
        """Get simulated account."""
        return self.account.copy()

    async def get_positions(self) -> List[Dict]:
        """Get simulated positions."""
        return self.positions.copy()

    async def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """Get simulated orders."""
        orders = self.orders.copy()
        if status:
            orders = [o for o in orders if o["status"] == status]
        return orders

    async def place_order(self, symbol: str, qty: float, side: str,
                         order_type: str = "limit", time_in_force: str = "ioc",
                         limit_price: Optional[float] = None,
                         stop_price: Optional[float] = None,
                         client_order_id: Optional[str] = None) -> Dict:
        """Place simulated order."""
        self.order_counter += 1

        order = {
            "id": f"sim_order_{self.order_counter}",
            "client_order_id": client_order_id or f"client_{self.order_counter}",
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "status": "filled",  # Simulate immediate fill
            "filled_qty": qty,
            "filled_avg_price": limit_price or 50000.0,  # Default price
            "submitted_at": datetime.now().isoformat(),
            "filled_at": datetime.now().isoformat(),
        }

        self.orders.append(order)

        # Simulate fill event
        asyncio.create_task(self._simulate_fill(order))

        return order

    async def _simulate_fill(self, order: Dict) -> None:
        """Simulate order fill."""
        await asyncio.sleep(0.1)  # Small delay

        # Create fill record
        fill = {
            "id": f"sim_fill_{self.order_counter}",
            "order_id": order["id"],
            "symbol": order["symbol"],
            "qty": order["filled_qty"],
            "price": order["filled_avg_price"],
            "fee": 0.0,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"Simulated fill: {fill}")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel simulated order."""
        for order in self.orders:
            if order["id"] == order_id:
                order["status"] = "cancelled"
                return True
        return False

    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Get simulated order."""
        for order in self.orders:
            if order["id"] == order_id:
                return order.copy()
        return None

    async def close(self) -> None:
        """Close simulated client."""
        pass


def create_alpaca_client() -> AlpacaClient:
    """Factory function to create Alpaca client."""
    if settings.execution.dry_run:
        return SimulatedAlpacaClient()
    else:
        return AlpacaClient()
