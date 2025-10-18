"""
Coinbase Advanced Trade API client for TEPM system.

Async client for Coinbase live crypto trading.
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import httpx

from ..core.config import settings
from ..core.logger import LoggerMixin, logger
from ..core.models import Fill, Order, OrderSide, OrderStatus


class CoinbaseClient(LoggerMixin):
    """Async Coinbase Advanced Trade API client."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None,
                 passphrase: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("COINBASE_KEY")
        self.secret_key = secret_key or os.getenv("COINBASE_SECRET")
        self.passphrase = passphrase or os.getenv("COINBASE_PASSPHRASE")
        self.base_url = base_url or os.getenv("COINBASE_API_BASE", "https://api.coinbase.com")

        if not all([self.api_key, self.secret_key, self.passphrase]):
            raise ValueError("Coinbase API credentials not configured")

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0
        )

    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Generate Coinbase API signature."""
        message = f"{timestamp}{method}{path}{body}"
        secret = self.secret_key.encode('utf-8')
        signature = hmac.new(secret, message.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature

    def _get_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Get authentication headers for Coinbase API."""
        timestamp = str(int(time.time()))

        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": self._generate_signature(timestamp, method, path, body),
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

    async def get_accounts(self) -> List[Dict]:
        """Get user accounts."""
        try:
            path = "/api/v3/brokerage/accounts"
            headers = self._get_auth_headers("GET", path)

            response = await self.client.get(path, headers=headers)
            response.raise_for_status()
            return response.json().get("accounts", [])
        except Exception as e:
            self.logger.error(f"Failed to get accounts: {e}")
            raise

    async def get_account(self, account_uuid: str) -> Dict:
        """Get specific account."""
        try:
            path = f"/api/v3/brokerage/accounts/{account_uuid}"
            headers = self._get_auth_headers("GET", path)

            response = await self.client.get(path, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get account {account_uuid}: {e}")
            raise

    async def get_orders(self, status: Optional[str] = None,
                        product_id: Optional[str] = None) -> List[Dict]:
        """Get orders."""
        try:
            path = "/api/v3/brokerage/orders"
            headers = self._get_auth_headers("GET", path)

            params = {}
            if status:
                params["status"] = status
            if product_id:
                params["product_id"] = product_id

            if params:
                response = await self.client.get(path, headers=headers, params=params)
            else:
                response = await self.client.get(path, headers=headers)

            response.raise_for_status()
            return response.json().get("orders", [])
        except Exception as e:
            self.logger.error(f"Failed to get orders: {e}")
            return []

    async def place_order(self, product_id: str, side: str, order_configuration: Dict) -> Dict:
        """Place an order."""
        try:
            path = "/api/v3/brokerage/orders"
            body = json.dumps({
                "product_id": product_id,
                "side": side,
                "order_configuration": order_configuration
            })

            headers = self._get_auth_headers("POST", path, body)

            response = await self.client.post(path, headers=headers, content=body)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            path = f"/api/v3/brokerage/orders/{order_id}"
            headers = self._get_auth_headers("DELETE", path)

            response = await self.client.delete(path, headers=headers)
            return response.status_code < 400
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Get order by ID."""
        try:
            path = f"/api/v3/brokerage/orders/{order_id}"
            headers = self._get_auth_headers("GET", path)

            response = await self.client.get(path, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get order {order_id}: {e}")
            return None

    async def get_fills(self, product_id: Optional[str] = None) -> List[Dict]:
        """Get fills."""
        try:
            path = "/api/v3/brokerage/fills"
            headers = self._get_auth_headers("GET", path)

            params = {}
            if product_id:
                params["product_id"] = product_id

            if params:
                response = await self.client.get(path, headers=headers, params=params)
            else:
                response = await self.client.get(path, headers=headers)

            response.raise_for_status()
            return response.json().get("fills", [])
        except Exception as e:
            self.logger.error(f"Failed to get fills: {e}")
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


class SimulatedCoinbaseClient(LoggerMixin):
    """Simulated Coinbase client for testing."""

    def __init__(self):
        self.accounts = [
            {
                "uuid": "btc_account",
                "currency": "BTC",
                "balance": "0.00000000",
                "available": "0.00000000"
            },
            {
                "uuid": "usd_account",
                "currency": "USD",
                "balance": "100000.00",
                "available": "100000.00"
            }
        ]

        self.orders = []
        self.fills = []
        self.order_counter = 0

    async def get_accounts(self) -> List[Dict]:
        """Get simulated accounts."""
        return self.accounts.copy()

    async def get_account(self, account_uuid: str) -> Dict:
        """Get simulated account."""
        for account in self.accounts:
            if account["uuid"] == account_uuid:
                return account.copy()
        return {}

    async def get_orders(self, status: Optional[str] = None, product_id: Optional[str] = None) -> List[Dict]:
        """Get simulated orders."""
        orders = self.orders.copy()
        if status:
            orders = [o for o in orders if o["status"] == status]
        if product_id:
            orders = [o for o in orders if o["product_id"] == product_id]
        return orders

    async def place_order(self, product_id: str, side: str, order_configuration: Dict) -> Dict:
        """Place simulated order."""
        self.order_counter += 1

        order = {
            "order_id": f"cb_order_{self.order_counter}",
            "product_id": product_id,
            "side": side,
            "order_configuration": order_configuration,
            "status": "FILLED",  # Simulate immediate fill
            "filled_size": order_configuration.get("size", "0"),
            "executed_value": "0",
            "total_fees": "0",
            "created_time": datetime.now().isoformat(),
            "completed_time": datetime.now().isoformat(),
        }

        self.orders.append(order)

        # Simulate fill
        asyncio.create_task(self._simulate_fill(order))

        return {"order_id": order["order_id"]}

    async def _simulate_fill(self, order: Dict) -> None:
        """Simulate order fill."""
        await asyncio.sleep(0.1)

        fill = {
            "entry_id": f"cb_fill_{self.order_counter}",
            "trade_id": f"cb_trade_{self.order_counter}",
            "order_id": order["order_id"],
            "product_id": order["product_id"],
            "side": order["side"],
            "size": order["filled_size"],
            "price": "50000.00",  # Default BTC price
            "fee": "0.00",
            "timestamp": datetime.now().isoformat()
        }

        self.fills.append(fill)
        logger.info(f"Simulated Coinbase fill: {fill}")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel simulated order."""
        for order in self.orders:
            if order["order_id"] == order_id:
                order["status"] = "CANCELLED"
                return True
        return False

    async def get_order(self, order_id: str) -> Optional[Dict]:
        """Get simulated order."""
        for order in self.orders:
            if order["order_id"] == order_id:
                return order.copy()
        return None

    async def get_fills(self, product_id: Optional[str] = None) -> List[Dict]:
        """Get simulated fills."""
        fills = self.fills.copy()
        if product_id:
            fills = [f for f in fills if f["product_id"] == product_id]
        return fills

    async def close(self) -> None:
        """Close simulated client."""
        pass


def create_coinbase_client() -> CoinbaseClient:
    """Factory function to create Coinbase client."""
    if settings.execution.dry_run:
        return SimulatedCoinbaseClient()
    else:
        return CoinbaseClient()
