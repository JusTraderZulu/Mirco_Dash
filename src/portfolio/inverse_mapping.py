"""
Inverse instrument mapping for short exposure.

Maps crypto symbols to their inverse ETFs for shorting via long positions.
"""

from typing import Dict, Optional


class InverseMapper:
    """Maps symbols to inverse instruments."""
    
    def __init__(self):
        # Crypto -> Inverse ETF mapping
        self.crypto_to_inverse = {
            "BTC-USD": "BITI",   # ProShares Short Bitcoin ETF
            "ETH-USD": "None",   # No widely traded inverse ETH ETF yet
        }
        
        # Reverse mapping
        self.inverse_to_crypto = {v: k for k, v in self.crypto_to_inverse.items() if v != "None"}
    
    def get_inverse_symbol(self, symbol: str) -> Optional[str]:
        """Get inverse instrument for a symbol."""
        return self.crypto_to_inverse.get(symbol)
    
    def is_inverse_instrument(self, symbol: str) -> bool:
        """Check if symbol is an inverse instrument."""
        return symbol in self.inverse_to_crypto
    
    def get_underlying_symbol(self, inverse_symbol: str) -> Optional[str]:
        """Get the underlying symbol from an inverse instrument."""
        return self.inverse_to_crypto.get(inverse_symbol)
    
    def supports_inverse(self, symbol: str) -> bool:
        """Check if symbol has inverse instrument available."""
        inverse = self.get_inverse_symbol(symbol)
        return inverse is not None and inverse != "None"


# Global instance
_inverse_mapper: Optional[InverseMapper] = None


def get_inverse_mapper() -> InverseMapper:
    """Get the singleton inverse mapper instance."""
    global _inverse_mapper
    if _inverse_mapper is None:
        _inverse_mapper = InverseMapper()
    return _inverse_mapper

