"""
Symbol normalization between Polygon and execution venues.

Handles mapping between Polygon format ("X:BTC-USD") and execution format ("BTC-USD").
"""

from typing import Dict, Optional

from ..core.logger import LoggerMixin


class SymbolMapper(LoggerMixin):
    """Symbol mapping utility."""

    def __init__(self):
        # Default mappings for crypto symbols
        self._polygon_to_execution_map = {
            "X:BTCUSD": "BTC-USD",   # REST API format
            "X:ETHUSD": "ETH-USD",
            "X:BTC-USD": "BTC-USD",  # WebSocket format (with dash)
            "X:ETH-USD": "ETH-USD",
            "X:X:BTC-USD": "BTC-USD",  # Handle double prefix
        }

        self._execution_to_polygon_map = {
            "BTC-USD": "X:BTCUSD",   # REST API uses X:BTCUSD (no dash)
            "ETH-USD": "X:ETHUSD",
        }

    def polygon_to_execution(self, polygon_symbol: str) -> str:
        """Convert Polygon symbol to execution venue format."""
        # Direct lookup
        if polygon_symbol in self._polygon_to_execution_map:
            return self._polygon_to_execution_map[polygon_symbol]

        # Handle cases with extra prefix
        if polygon_symbol.startswith("X:X:"):
            base_symbol = polygon_symbol[4:]  # Remove "X:X:"
            if base_symbol in self._polygon_to_execution_map:
                return self._polygon_to_execution_map[base_symbol]

        # Fallback: remove X: prefix if present
        if polygon_symbol.startswith("X:"):
            execution_symbol = polygon_symbol[2:]

            # Validate it's a reasonable crypto symbol format
            if "-" in execution_symbol and len(execution_symbol.split("-")[0]) <= 10:
                self.logger.warning(f"Using fallback mapping for {polygon_symbol} -> {execution_symbol}")
                return execution_symbol

        # No mapping found
        self.logger.warning(f"No mapping found for Polygon symbol: {polygon_symbol}")
        return polygon_symbol

    def execution_to_polygon(self, execution_symbol: str) -> str:
        """Convert execution venue symbol to Polygon format."""
        # Direct lookup
        if execution_symbol in self._execution_to_polygon_map:
            return self._execution_to_polygon_map[execution_symbol]

        # Fallback: add X: prefix for crypto symbols
        if "-" in execution_symbol and len(execution_symbol.split("-")[0]) <= 10:
            polygon_symbol = f"X:{execution_symbol}"
            self.logger.warning(f"Using fallback mapping for {execution_symbol} -> {polygon_symbol}")
            return polygon_symbol

        # No mapping found
        self.logger.warning(f"No mapping found for execution symbol: {execution_symbol}")
        return execution_symbol

    def add_mapping(self, polygon_symbol: str, execution_symbol: str):
        """Add a custom symbol mapping."""
        self._polygon_to_execution_map[polygon_symbol] = execution_symbol
        self._execution_to_polygon_map[execution_symbol] = polygon_symbol

        self.logger.info(f"Added symbol mapping: {polygon_symbol} <-> {execution_symbol}")

    def get_supported_symbols(self) -> Dict[str, str]:
        """Get all supported symbol mappings."""
        return self._polygon_to_execution_map.copy()


# Global symbol mapper instance
_symbol_mapper: Optional[SymbolMapper] = None


def get_symbol_mapper() -> SymbolMapper:
    """Get the singleton symbol mapper instance."""
    global _symbol_mapper
    if _symbol_mapper is None:
        _symbol_mapper = SymbolMapper()
    return _symbol_mapper
