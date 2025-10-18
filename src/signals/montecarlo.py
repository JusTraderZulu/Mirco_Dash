"""
Monte Carlo simulation module for TEPM system.

Implements GBM with EWMA volatility for generating probabilistic forecasts.
"""

import random
import statistics
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import numpy as np

from ..core.logger import LoggerMixin
from ..core.models import Scenario


class MonteCarloSimulator(LoggerMixin):
    """Monte Carlo simulator for price forecasting."""

    def __init__(self):
        self.random_seed = 42  # Deterministic for reproducibility

        # EWMA parameters for volatility estimation
        self.ewma_lambda = 0.94  # Standard EWMA parameter
        self.volatility_window = 100

        # Data storage
        self.price_history: Dict[str, deque] = {}
        self.return_history: Dict[str, deque] = {}
        self.volatility_history: Dict[str, deque] = {}

    def add_price_data(self, symbol: str, price: float, timestamp: datetime) -> None:
        """Add price data point for volatility estimation."""
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=1000)
            self.return_history[symbol] = deque(maxlen=1000)
            self.volatility_history[symbol] = deque(maxlen=self.volatility_window)

        self.price_history[symbol].append((timestamp, price))

        # Calculate return if we have previous price
        if len(self.price_history[symbol]) > 1:
            prev_timestamp, prev_price = self.price_history[symbol][-2]
            if (timestamp - prev_timestamp).total_seconds() < 3600:  # Within 1 hour
                ret = (price - prev_price) / prev_price
                self.return_history[symbol].append(ret)

        # Update EWMA volatility
        self._update_ewma_volatility(symbol)

    def _update_ewma_volatility(self, symbol: str) -> None:
        """Update EWMA volatility estimate."""
        if symbol not in self.return_history or len(self.return_history[symbol]) < 10:
            return

        returns = list(self.return_history[symbol])

        # Calculate realized volatility (squared returns)
        realized_var = np.mean([r**2 for r in returns[-self.volatility_window:]])

        # EWMA update
        if symbol in self.volatility_history and len(self.volatility_history[symbol]) > 0:
            prev_vol = self.volatility_history[symbol][-1]
            current_vol = self.ewma_lambda * prev_vol + (1 - self.ewma_lambda) * realized_var
        else:
            current_vol = realized_var

        self.volatility_history[symbol].append(current_vol)

    def get_current_volatility(self, symbol: str) -> float:
        """Get current EWMA volatility estimate."""
        if symbol not in self.volatility_history or len(self.volatility_history[symbol]) == 0:
            return 0.02  # Default 2% daily volatility

        return np.sqrt(self.volatility_history[symbol][-1])

    def simulate_gbm(self, symbol: str, current_price: float, horizon_seconds: int,
                    num_paths: int = 1000) -> Dict[str, List[float]]:
        """Simulate Geometric Brownian Motion paths."""
        random.seed(self.random_seed)  # Deterministic seeding

        if symbol not in self.price_history:
            # No data available, use default parameters
            mu = 0.0  # No drift
            sigma = 0.02  # Default daily volatility
        else:
            # Use recent data for drift and volatility estimation
            recent_returns = list(self.return_history[symbol])
            if len(recent_returns) > 20:
                mu = np.mean(recent_returns[-20:]) * 252  # Annualized drift
                sigma = self.get_current_volatility(symbol) * np.sqrt(252)  # Annualized volatility
            else:
                mu = 0.0
                sigma = 0.02

        # Time parameters
        dt = horizon_seconds / (252 * 24 * 3600)  # Convert to fraction of year
        sqrt_dt = np.sqrt(dt)

        # Generate paths
        paths = []
        final_prices = []

        for _ in range(num_paths):
            path = [current_price]
            price = current_price

            # Generate random walk
            for _ in range(int(horizon_seconds / 60)):  # 1-minute steps
                Z = random.gauss(0, 1)
                d_price = price * (mu * dt + sigma * sqrt_dt * Z)
                price += d_price
                path.append(price)

            paths.append(path)
            final_prices.append(price)

        return {
            "paths": paths,
            "final_prices": final_prices
        }

    def calculate_hit_probabilities(self, symbol: str, current_price: float,
                                  take_profit: float, stop_loss: float,
                                  horizon_seconds: int = 300) -> Dict[str, float]:
        """Calculate probabilities of hitting TP/SL levels."""
        simulation = self.simulate_gbm(symbol, current_price, horizon_seconds)

        final_prices = simulation["final_prices"]

        # Calculate hit probabilities
        tp_hit = sum(1 for p in final_prices if p >= take_profit) / len(final_prices)
        sl_hit = sum(1 for p in final_prices if p <= stop_loss) / len(final_prices)

        # Risk-reward ratio
        avg_win = np.mean([p - current_price for p in final_prices if p >= take_profit]) if tp_hit > 0 else 0
        avg_loss = np.mean([current_price - p for p in final_prices if p <= stop_loss]) if sl_hit > 0 else 0
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        return {
            "tp_hit_prob": tp_hit,
            "sl_hit_prob": sl_hit,
            "rr_ratio": rr_ratio,
            "expected_value": tp_hit * avg_win - sl_hit * avg_loss
        }

    def calculate_var(self, symbol: str, current_price: float, confidence_level: float = 0.05,
                     horizon_seconds: int = 300) -> Dict[str, float]:
        """Calculate Value at Risk (VaR) at given confidence level."""
        simulation = self.simulate_gbm(symbol, current_price, horizon_seconds)
        final_prices = simulation["final_prices"]

        # Calculate returns
        returns = [(p - current_price) / current_price for p in final_prices]

        # Calculate VaR (negative return at confidence level)
        var_pct = np.percentile(returns, confidence_level * 100)
        var_usd = -var_pct * current_price  # Loss amount

        # Expected Shortfall (conditional VaR)
        worst_returns = [r for r in returns if r <= var_pct]
        esf = -np.mean(worst_returns) * current_price if worst_returns else 0

        return {
            "var_usd": var_usd,
            "var_pct": -var_pct,
            "expected_shortfall": esf,
            "confidence_level": confidence_level
        }

    def calculate_percentiles(self, symbol: str, current_price: float,
                            horizon_seconds: int = 300) -> Dict[str, float]:
        """Calculate price percentiles from simulation."""
        simulation = self.simulate_gbm(symbol, current_price, horizon_seconds)
        final_prices = simulation["final_prices"]

        percentiles = {
            "p1": np.percentile(final_prices, 1),
            "p5": np.percentile(final_prices, 5),
            "p10": np.percentile(final_prices, 10),
            "p25": np.percentile(final_prices, 25),
            "p50": np.percentile(final_prices, 50),
            "p75": np.percentile(final_prices, 75),
            "p90": np.percentile(final_prices, 90),
            "p95": np.percentile(final_prices, 95),
            "p99": np.percentile(final_prices, 99),
        }

        return percentiles

    def generate_scenario(self, symbol: str, current_price: float,
                         features: Dict[str, float]) -> Scenario:
        """Generate a complete trading scenario."""
        # Get microstructure features
        upside_prob = features.get("ofi", 0) + features.get("aggressive_ratio", 0)
        downside_prob = features.get("spread_mean", 0) + features.get("realized_vol", 0)

        # Normalize probabilities
        total = upside_prob + downside_prob
        if total > 0:
            upside_prob = upside_prob / total
            downside_prob = downside_prob / total
        else:
            upside_prob = downside_prob = 0.5

        # Determine bias and confidence
        if upside_prob > 0.6:
            bias = "long"
            confidence = upside_prob
        elif downside_prob > 0.6:
            bias = "short"
            confidence = downside_prob
        else:
            bias = "neutral"
            confidence = 0.5

        # Risk regime based on volatility
        vol = features.get("realized_vol", 0.02)
        if vol < 0.01:
            risk_regime = "low_vol"
        elif vol > 0.05:
            risk_regime = "high_vol"
        else:
            risk_regime = "medium_vol"

        # Generate TP/SL levels based on ATR-like calculation
        spread = features.get("spread_mean", 0.01)
        atr_mult = 2.0 if risk_regime == "low_vol" else 1.5

        tp_distance = spread * atr_mult
        sl_distance = spread * 1.0

        if bias == "long":
            entry = current_price
            tp = current_price * (1 + tp_distance / current_price)
            sl = current_price * (1 - sl_distance / current_price)
        elif bias == "short":
            entry = current_price
            tp = current_price * (1 - tp_distance / current_price)
            sl = current_price * (1 + sl_distance / current_price)
        else:
            entry = current_price
            tp = current_price * (1 + tp_distance / current_price * 0.5)
            sl = current_price * (1 - sl_distance / current_price * 0.5)

        # Monte Carlo probabilities
        mc_probs = self.calculate_hit_probabilities(symbol, current_price, tp, sl)
        var_stats = self.calculate_var(symbol, current_price)

        return Scenario(
            symbol=symbol,
            ts=datetime.now(timezone.utc),
            bias=bias,
            confidence=confidence,
            risk_regime=risk_regime,
            features=features,
            mc={
                "upside_prob": upside_prob,
                "downside_prob": downside_prob,
                "tp_hit_prob": mc_probs["tp_hit_prob"],
                "sl_hit_prob": mc_probs["sl_hit_prob"],
                "var_5pct": var_stats["var_usd"]
            },
            recommended={
                "entry": Decimal(str(entry)),
                "tp": Decimal(str(tp)),
                "sl": Decimal(str(sl))
            }
        )


# Global Monte Carlo simulator instance
_monte_carlo: Optional[MonteCarloSimulator] = None


def get_monte_carlo() -> MonteCarloSimulator:
    """Get the singleton Monte Carlo simulator instance."""
    global _monte_carlo
    if _monte_carlo is None:
        _monte_carlo = MonteCarloSimulator()
    return _monte_carlo
