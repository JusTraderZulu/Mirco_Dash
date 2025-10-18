"""
Signal engine for TEPM system.

Orchestrates microstructure analysis and Monte Carlo simulations to generate trading scenarios.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..core.config import settings
from ..core.logger import LoggerMixin, logger, set_session_context
from ..core.models import Scenario
from ..core.state import SessionState
from ..data.orderbook import get_orderbook_manager
from ..db.schema import get_session
from ..signals.microstructure import get_microstructure_signals
from ..signals.montecarlo import get_monte_carlo


class SignalEngine(LoggerMixin):
    """Signal generation engine."""

    def __init__(self, session_state: SessionState):
        self.session_state = session_state
        self.is_running = False

        # Cadence settings
        self.full_window_sec = settings.signals.cadence.full_window_sec
        self.light_window_sec = settings.signals.cadence.light_window_sec

        # Feature settings
        self.enabled_features = set(settings.signals.features)

        # Tasks
        self._full_cycle_task: Optional[asyncio.Task] = None
        self._light_cycle_task: Optional[asyncio.Task] = None

        # Signal history
        self.recent_scenarios: List[Scenario] = []

    async def start(self) -> None:
        """Start the signal engine."""
        self.is_running = True

        # Start full cycle (every 5 minutes)
        self._full_cycle_task = asyncio.create_task(self._full_signal_cycle())

        # Start light cycle (every 1 minute)
        self._light_cycle_task = asyncio.create_task(self._light_signal_cycle())

        self.logger.info("Signal engine started")

    async def stop(self) -> None:
        """Stop the signal engine."""
        self.is_running = False

        if self._full_cycle_task:
            self._full_cycle_task.cancel()
        if self._light_cycle_task:
            self._light_cycle_task.cancel()

        self.logger.info("Signal engine stopped")

    async def _full_signal_cycle(self) -> None:
        """Run full signal generation cycle every 5 minutes."""
        while self.is_running:
            try:
                await asyncio.sleep(self.full_window_sec)

                if not self.is_running:
                    break

                await self._generate_signals(full_cycle=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in full signal cycle: {e}")
                await asyncio.sleep(10)  # Brief pause before retry

    async def _light_signal_cycle(self) -> None:
        """Run light signal generation cycle every 1 minute."""
        while self.is_running:
            try:
                await asyncio.sleep(self.light_window_sec)

                if not self.is_running:
                    break

                await self._generate_signals(full_cycle=False)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in light signal cycle: {e}")
                await asyncio.sleep(10)  # Brief pause before retry

    async def _generate_signals(self, full_cycle: bool = True) -> None:
        """Generate trading signals for all symbols."""
        symbols = list(self.session_state.symbols)

        for symbol in symbols:
            try:
                scenario = await self._generate_symbol_scenario(symbol, full_cycle)

                if scenario:
                    # Add to session state
                    await self.session_state.add_scenario(scenario)

                    # Add to recent scenarios
                    self.recent_scenarios.append(scenario)
                    if len(self.recent_scenarios) > 50:
                        self.recent_scenarios = self.recent_scenarios[-50:]

                    # Save to database
                    await self._save_scenario_to_db(scenario)

                    self.logger.info(
                        f"Generated {scenario.bias.value} scenario for {symbol}: "
                        f"confidence={scenario.confidence:.2f}, "
                        f"tp={scenario.recommended['tp']}, sl={scenario.recommended['sl']}"
                    )
                    
                    print(f"🎯 SIGNAL GENERATED: {scenario.bias.value.upper()} {symbol} (confidence: {scenario.confidence:.1%})")

            except Exception as e:
                self.logger.error(f"Error generating scenario for {symbol}: {e}")

    async def _generate_symbol_scenario(self, symbol: str, full_cycle: bool) -> Optional[Scenario]:
        """Generate trading scenario for a single symbol."""
        try:
            print(f"\n🎯 Signal Engine: Generating scenario for {symbol}...")
            
            # Get current market data
            orderbook_manager = get_orderbook_manager()
            book = orderbook_manager.get_book(symbol)
            if not book:
                print(f"   ⚠️  No order book available for {symbol}")
                self.logger.warning(f"No order book available for {symbol}")
                return None

            current_price = float(book.get_mid_price())
            if not current_price or current_price <= 0:
                self.logger.warning(f"Invalid mid price for {symbol}: {current_price}")
                return None

            # Get microstructure features
            microstructure_signals = get_microstructure_signals()
            
            # DEBUG: Check how much data we have
            tick_count = len(microstructure_signals.tick_history.get(symbol, []))
            price_count = len(microstructure_signals.price_history.get(symbol, []))
            print(f"   📊 Microstructure has: {tick_count} ticks, {price_count} prices")
            
            features = microstructure_signals.get_all_features(symbol)
            print(f"   📈 Calculated {len(features)} features")

            # Update Monte Carlo with current price
            monte_carlo = get_monte_carlo()
            mc_price_count = len(monte_carlo.price_history.get(symbol, []))
            print(f"   💹 Monte Carlo has: {mc_price_count} prices")
            
            if book.last_update:
                monte_carlo.add_price_data(symbol, current_price, book.last_update)

            # Generate scenario
            print(f"   🎲 Generating Monte Carlo scenario...")
            scenario = monte_carlo.generate_scenario(symbol, current_price, features)
            print(f"   ✅ Scenario: {scenario.bias.value.upper()} (confidence: {scenario.confidence:.1%})")

            # Apply confidence threshold filter
            if scenario.confidence < settings.signals.thresholds.bias_confidence_min:
                scenario.bias = "neutral"
                scenario.confidence = 0.5

            return scenario

        except Exception as e:
            self.logger.error(f"Error generating scenario for {symbol}: {e}")
            return None

    def get_recent_scenarios(self, symbol: Optional[str] = None, limit: int = 10) -> List[Scenario]:
        """Get recent trading scenarios."""
        scenarios = self.recent_scenarios

        if symbol:
            scenarios = [s for s in scenarios if s.symbol == symbol]

        return scenarios[-limit:]

    def get_signal_summary(self) -> Dict:
        """Get summary of recent signal activity."""
        if not self.recent_scenarios:
            return {"total_scenarios": 0, "by_bias": {}, "by_symbol": {}}

        # Count by bias
        by_bias = {}
        for scenario in self.recent_scenarios:
            bias = scenario.bias.value
            by_bias[bias] = by_bias.get(bias, 0) + 1

        # Count by symbol
        by_symbol = {}
        for scenario in self.recent_scenarios:
            symbol = scenario.symbol
            by_symbol[symbol] = by_symbol.get(symbol, 0) + 1

        return {
            "total_scenarios": len(self.recent_scenarios),
            "by_bias": by_bias,
            "by_symbol": by_symbol,
            "avg_confidence": sum(s.confidence for s in self.recent_scenarios) / len(self.recent_scenarios)
        }
    
    async def _save_scenario_to_db(self, scenario: Scenario) -> None:
        """Save scenario to database."""
        try:
            import json
            from ..db.schema import Signal
            
            db_session = get_session()
            
            signal = Signal(
                ts=scenario.ts,
                symbol=scenario.symbol,
                bias=scenario.bias.value,
                confidence=scenario.confidence,
                risk_regime=scenario.risk_regime.value,
                features_json=json.dumps(scenario.features),
                mc_json=json.dumps(scenario.mc),
                rec_entry=float(scenario.recommended.get('entry', 0)),
                rec_tp=float(scenario.recommended.get('tp', 0)),
                rec_sl=float(scenario.recommended.get('sl', 0))
            )
            
            db_session.add(signal)
            db_session.commit()
            db_session.close()
            
            print(f"   💾 Saved signal to database")
            
        except Exception as e:
            self.logger.error(f"Error saving scenario to database: {e}")
            import traceback
            traceback.print_exc()


# Global signal engine instance
def create_signal_engine(session_state: SessionState) -> SignalEngine:
    """Factory function to create signal engine."""
    return SignalEngine(session_state)
