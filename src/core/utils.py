"""
Utility functions for TEPM system.

Includes tick/lot rounding, idempotency keys, time helpers, and other common operations.
"""

import hashlib
import random
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Optional, Union

from .logger import logger


def round_to_tick(price: Union[Decimal, float, str], tick_size: Union[Decimal, float] = 0.01) -> Decimal:
    """Round price to nearest tick size."""
    price = Decimal(str(price))
    tick_size = Decimal(str(tick_size))

    return (price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size


def round_to_lot(quantity: Union[Decimal, float, str], lot_size: Union[Decimal, float] = 1) -> Decimal:
    """Round quantity to nearest lot size."""
    quantity = Decimal(str(quantity))
    lot_size = Decimal(str(lot_size))

    if lot_size == 0:
        return quantity

    return (quantity / lot_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * lot_size


def calculate_notional(price: Union[Decimal, float, str], quantity: Union[Decimal, float, str]) -> Decimal:
    """Calculate notional value of a trade."""
    price = Decimal(str(price))
    quantity = Decimal(str(quantity))

    return price * quantity


def generate_idempotency_key(prefix: str = "order", ttl_seconds: int = 3600) -> str:
    """Generate an idempotency key with TTL."""
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)

    key_data = f"{prefix}:{timestamp}:{random_suffix}"
    key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]

    return f"{prefix}_{key_hash}_{timestamp}"


def is_market_open() -> bool:
    """Check if US markets are currently open (simplified)."""
    now = datetime.now(timezone.utc)

    # Convert to Eastern Time (simplified - doesn't handle DST properly)
    eastern = now.hour - 4  # UTC to ET conversion
    if eastern < 0:
        eastern += 24

    # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
    is_weekday = now.weekday() < 5
    is_market_hours = 9.5 <= eastern <= 16

    return is_weekday and is_market_hours


def calculate_slippage(actual_price: Decimal, expected_price: Decimal) -> float:
    """Calculate slippage in basis points."""
    if expected_price == 0:
        return 0.0

    return float(abs(actual_price - expected_price) / expected_price * 10000)  # Convert to bps


def format_price(price: Union[Decimal, float, str], precision: int = 8) -> str:
    """Format price for display."""
    price = Decimal(str(price))
    return f"{price:.{precision}f}".rstrip('0').rstrip('.')


def format_quantity(quantity: Union[Decimal, float, str], precision: int = 8) -> str:
    """Format quantity for display."""
    quantity = Decimal(str(quantity))
    return f"{quantity:.{precision}f}".rstrip('0').rstrip('.')


def calculate_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """Calculate Average True Range (ATR)."""
    if len(highs) < period or len(lows) < period or len(closes) < period:
        return 0.0

    true_ranges = []
    for i in range(1, len(closes)):
        tr1 = highs[i] - lows[i]
        tr2 = abs(highs[i] - closes[i-1])
        tr3 = abs(lows[i] - closes[i-1])
        true_ranges.append(max(tr1, tr2, tr3))

    return sum(true_ranges[-period:]) / period


def normalize_symbol_polygon_to_execution(symbol: str) -> str:
    """Normalize Polygon symbol format to execution venue format.

    Polygon format: "X:BTC-USD" -> "BTC-USD"
    """
    if symbol.startswith("X:"):
        return symbol[2:]
    return symbol


def normalize_symbol_execution_to_polygon(symbol: str) -> str:
    """Normalize execution venue symbol format to Polygon format.

    Execution format: "BTC-USD" -> "X:BTC-USD"
    """
    # Add crypto prefix for crypto symbols (simplified heuristic)
    if "-" in symbol and len(symbol.split("-")[0]) <= 5:
        return f"X:{symbol}"
    return symbol


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator for retrying async functions with exponential backoff."""
    import asyncio

    async def wrapper(*args, **kwargs):
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == max_retries:
                    logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                    raise

                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = random.uniform(0.1, 0.3) * delay  # Add jitter
                sleep_time = delay + jitter

                logger.warning(
                    f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {sleep_time:.1f}s..."
                )

                await asyncio.sleep(sleep_time)

        raise last_exception

    return wrapper


def validate_price(price: Union[Decimal, float, str], symbol: str) -> Decimal:
    """Validate and normalize price for a symbol."""
    price = Decimal(str(price))

    if price <= 0:
        raise ValueError(f"Invalid price for {symbol}: {price}")

    return price


def validate_quantity(quantity: Union[Decimal, float, str], symbol: str) -> Decimal:
    """Validate and normalize quantity for a symbol."""
    quantity = Decimal(str(quantity))

    if quantity <= 0:
        raise ValueError(f"Invalid quantity for {symbol}: {quantity}")

    return quantity
