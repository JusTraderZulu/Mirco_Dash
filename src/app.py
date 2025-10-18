"""
Main application orchestrator for TEPM system.

Coordinates all asyncio tasks: feed, signals, portfolio, execution, and API.
"""

import asyncio
import signal
import sys
import time
from typing import Optional

from .core.config import settings
from .core.logger import LoggerMixin, logger, set_session_context
from .core.state import SessionState
from .data.feed_handler import create_feed_handler
from .data.orderbook import get_orderbook_manager
from .db.schema import get_db_manager
from .execution.router import ExecutionRouter
from .portfolio.manager import PortfolioManager
from .portfolio.risk_agent import get_risk_agent
from .signals.engine import SignalEngine


class TEPMApp(LoggerMixin):
    """Main TEPM application orchestrator."""

    def __init__(self):
        self.is_running = False

        # Core components
        self.session_state: Optional[SessionState] = None
        self.feed_handler = None
        self.signal_engine: Optional[SignalEngine] = None
        self.portfolio_manager: Optional[PortfolioManager] = None
        self.execution_router: Optional[ExecutionRouter] = None

        # Shutdown handling
        self.shutdown_event = asyncio.Event()

    async def start(self, symbols: list, env: str = "paper", start_api: bool = False) -> None:
        """Start the TEPM application."""
        self.is_running = True
        
        logger.info("🚀 Starting TEPM Analytics Dashboard (Data Collection Only)")

        # Initialize database
        get_db_manager().init_db()

        # Create session state
        session_id = f"session_{int(time.time())}"
        self.session_state = SessionState(session_id, symbols, env)
        set_session_context(session_id)

        # Create data collection components only (NO TRADING)
        self.signal_engine = SignalEngine(self.session_state)
        self.feed_handler = create_feed_handler(self.session_state)

        try:
            # Start data collection
            logger.info("Starting data collection components...")

            await self.signal_engine.start()
            await self.feed_handler.start()
            
            logger.info("📊 Data collection active - NO TRADING EXECUTION")
            logger.info(f"TEPM system started successfully - Session: {session_id}")
            logger.info("✅ Polygon data flowing - microstructure metrics being calculated")
            logger.info("💡 Start API server separately: uvicorn src.api.server:app --host 0.0.0.0 --port 8000")

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except Exception as e:
            logger.error(f"Error starting TEPM system: {e}")
            await self.stop()
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the TEPM application gracefully."""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping TEPM system...")

        # Stop data collection components
        if self.feed_handler:
            await self.feed_handler.stop()

        if self.signal_engine:
            await self.signal_engine.stop()

        # Stop execution components if they exist
        if hasattr(self, 'execution_router') and self.execution_router:
            await self.execution_router.stop()

        if hasattr(self, 'portfolio_manager') and self.portfolio_manager:
            await self.portfolio_manager.stop()

        logger.info("TEPM system stopped successfully")

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request

        # Handle Windows signals
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, signal_handler)


async def run_tepm(symbols: list, env: str = "paper") -> None:
    """Run the TEPM application."""
    app = TEPMApp()
    app.setup_signal_handlers()

    try:
        await app.start(symbols, env)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"TEPM application error: {e}")
        raise
    finally:
        await app.stop()


def main():
    """Main entry point for TEPM application."""
    import argparse

    parser = argparse.ArgumentParser(description="TEPM Analytics Dashboard - Data Collection Only")
    parser.add_argument("--symbols", nargs="+", default=["BTC-USD", "ETH-USD"], help="Symbols to analyze")
    parser.add_argument("--env", default="paper", choices=["dev", "paper", "live"], help="Environment")

    args = parser.parse_args()

    # Run the application
    asyncio.run(run_tepm(args.symbols, args.env))


if __name__ == "__main__":
    main()
