"""
CLI interface for TEPM system using Typer.

Provides commands for session management, backtesting, and system operations.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import List, Optional

import typer
from rich import print as rich_print
from rich.console import Console
from rich.table import Table

from ..core.config import settings
from ..core.logger import logger
from ..core.state import SessionState
from ..data.feed_handler import create_feed_handler
from ..data.orderbook import get_orderbook_manager
from ..db.schema import init_db
from ..execution.router import ExecutionRouter
from ..portfolio.manager import PortfolioManager
# Risk agent will be initialized when session starts
from ..signals.engine import SignalEngine

# Global components
cli_session_state: Optional[SessionState] = None
cli_feed_handler = None
cli_signal_engine: Optional[SignalEngine] = None
cli_portfolio_manager: Optional[PortfolioManager] = None
cli_execution_router: Optional[ExecutionRouter] = None

# CLI app
app = typer.Typer()
console = Console()


@app.command()
def session_start(
    symbols: List[str] = typer.Argument(..., help="Trading symbols to monitor"),
    env: str = typer.Option("paper", help="Environment: dev, paper, or live")
):
    """Start a new trading session."""
    global cli_session_state, cli_feed_handler, cli_signal_engine, cli_portfolio_manager, cli_execution_router

    try:
        # Create session state
        session_id = f"session_{int(time.time())}"
        rich_print(f"[cyan]Creating SessionState...[/cyan]")
        cli_session_state = SessionState(session_id, symbols, env)
        rich_print(f"[cyan]✓ SessionState created[/cyan]")

        # Create system components
        rich_print(f"[cyan]Creating SignalEngine...[/cyan]")
        cli_signal_engine = SignalEngine(cli_session_state)
        rich_print(f"[cyan]✓ SignalEngine created[/cyan]")
        
        rich_print(f"[cyan]Creating ExecutionRouter...[/cyan]")
        cli_execution_router = ExecutionRouter(cli_session_state)
        rich_print(f"[cyan]✓ ExecutionRouter created[/cyan]")
        
        rich_print(f"[cyan]Creating PortfolioManager...[/cyan]")
        cli_portfolio_manager = PortfolioManager(cli_session_state, cli_execution_router)
        rich_print(f"[cyan]✓ PortfolioManager created[/cyan]")
        
        # Initialize global risk agent
        rich_print(f"[cyan]Creating RiskAgent...[/cyan]")
        from ..portfolio.risk_agent import create_risk_agent
        create_risk_agent(cli_session_state)
        rich_print(f"[cyan]✓ RiskAgent created[/cyan]")

        # Start feed handler
        rich_print(f"[cyan]Creating FeedHandler...[/cyan]")
        cli_feed_handler = create_feed_handler(cli_session_state)
        rich_print(f"[cyan]✓ FeedHandler created[/cyan]")

        # Start all components and keep running
        async def run_session():
            await cli_signal_engine.start()
            await cli_portfolio_manager.start()
            await cli_execution_router.start()
            await cli_feed_handler.start()
            
            rich_print(f"[green]✅ Started session {session_id} with symbols: {symbols}[/green]")
            rich_print(f"[yellow]Press Ctrl+C to stop the session[/yellow]")
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                rich_print(f"\n[yellow]Stopping session...[/yellow]")
                
                # Stop all components
                await cli_feed_handler.stop()
                await cli_execution_router.stop()
                await cli_portfolio_manager.stop()
                await cli_signal_engine.stop()
                
                rich_print(f"[green]Session stopped[/green]")

        rich_print(f"[cyan]Starting components...[/cyan]")
        asyncio.run(run_session())

    except Exception as e:
        import traceback
        rich_print(f"[red]Error starting session: {e}[/red]")
        rich_print(f"[red]{traceback.format_exc()}[/red]")
        raise typer.Exit(1)


@app.command()
def session_stop(save: bool = True):
    """Stop the current trading session."""
    global cli_session_state, cli_feed_handler, cli_signal_engine, cli_portfolio_manager, cli_execution_router

    try:
        async def stop_components():
            if cli_feed_handler:
                await cli_feed_handler.stop()
            if cli_signal_engine:
                await cli_signal_engine.stop()
            if cli_portfolio_manager:
                await cli_portfolio_manager.stop()
            if cli_execution_router:
                await cli_execution_router.stop()

        asyncio.run(stop_components())

        rich_print("[green]Session stopped successfully[/green]")

    except Exception as e:
        rich_print(f"[red]Error stopping session: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def session_status():
    """Show current session status."""
    if not cli_session_state:
        rich_print("[yellow]No active session[/yellow]")
        return

    table = Table(title="Session Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Session ID", cli_session_state.session_id)
    table.add_row("Status", "Active" if cli_session_state.is_active else "Inactive")
    table.add_row("Symbols", ", ".join(cli_session_state.symbols))
    table.add_row("Environment", cli_session_state.env)
    table.add_row("Started At", cli_session_state.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"))

    console.print(table)


@app.command()
def positions():
    """Show current positions."""
    if not cli_session_state:
        rich_print("[yellow]No active session[/yellow]")
        return

    positions = cli_session_state.positions

    if not positions:
        rich_print("[yellow]No open positions[/yellow]")
        return

    table = Table(title="Current Positions")
    table.add_column("Symbol", style="cyan")
    table.add_column("Quantity", style="white")
    table.add_column("Avg Price", style="white")
    table.add_column("Unrealized P&L", style="green")
    table.add_column("State", style="yellow")

    for symbol, pos in positions.items():
        unrealized_color = "green" if pos.unrealized_pnl >= 0 else "red"
        table.add_row(
            symbol,
            f"{pos.quantity:.8f}",
            f"{pos.average_price:.2f}",
            f"[{unrealized_color}]{pos.unrealized_pnl:.2f}[/]",
            pos.state.value
        )

    console.print(table)


@app.command()
def orders(status: Optional[str] = None):
    """Show current orders."""
    if not cli_session_state:
        rich_print("[yellow]No active session[/yellow]")
        return

    orders = cli_session_state.orders

    if not orders:
        rich_print("[yellow]No orders[/yellow]")
        return

    # Filter by status if provided
    if status:
        orders = {k: v for k, v in orders.items() if v.status.value == status}

    table = Table(title="Current Orders")
    table.add_column("Order ID", style="cyan")
    table.add_column("Symbol", style="white")
    table.add_column("Side", style="green")
    table.add_column("Type", style="white")
    table.add_column("Quantity", style="white")
    table.add_column("Price", style="white")
    table.add_column("Status", style="yellow")

    for order_id, order in orders.items():
        status_color = {
            "pending": "yellow",
            "open": "blue",
            "filled": "green",
            "cancelled": "red",
            "rejected": "red"
        }.get(order.status.value, "white")

        table.add_row(
            order_id[:12] + "...",  # Truncate long IDs
            order.symbol,
            order.side.value,
            order.order_type.value,
            f"{order.quantity:.8f}",
            f"{order.price:.2f}" if order.price else "Market",
            f"[{status_color}]{order.status.value}[/]"
        )

    console.print(table)


@app.command()
def signals(limit: int = 10):
    """Show recent trading signals."""
    # Read from database instead of in-memory state
    import sqlite3
    
    try:
        conn = sqlite3.connect("data/tepm.sqlite")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ts, symbol, bias, confidence, risk_regime, rec_entry, rec_tp, rec_sl
            FROM signals
            ORDER BY ts DESC
            LIMIT ?
        """, (limit,))
        
        signals_data = cursor.fetchall()
        conn.close()
        
        if not signals_data:
            rich_print("[yellow]No signals generated yet. System needs to run for 5+ minutes to generate first signal.[/yellow]")
            return
        
        # Display signals from database
        table = Table(title="Recent Trading Signals")
        table.add_column("Symbol", style="cyan")
        table.add_column("Timestamp", style="white")
        table.add_column("Bias", style="green")
        table.add_column("Confidence", style="white")
        table.add_column("Risk Regime", style="yellow")
        table.add_column("Entry", style="white")
        table.add_column("TP", style="white")
        table.add_column("SL", style="white")

        for row in signals_data:
            ts, symbol, bias, confidence, risk_regime, entry, tp, sl = row
            
            bias_color = {
                "long": "green",
                "short": "red",
                "neutral": "yellow"
            }.get(bias, "white")

            table.add_row(
                symbol,
                ts,
                f"[{bias_color}]{bias.upper()}[/]",
                f"{confidence*100:.1f}%",
                risk_regime,
                f"${entry:.2f}",
                f"${tp:.2f}",
                f"${sl:.2f}"
            )

        console.print(table)
        
    except Exception as e:
        rich_print(f"[red]Error reading signals: {e}[/red]")


@app.command()
def market():
    """Show market data summary."""
    orderbook_manager = get_orderbook_manager()
    summary = orderbook_manager.get_market_summary()

    if not summary:
        rich_print("[yellow]No market data available[/yellow]")
        return

    table = Table(title="Market Summary")
    table.add_column("Symbol", style="cyan")
    table.add_column("Best Bid", style="green")
    table.add_column("Best Ask", style="red")
    table.add_column("Mid Price", style="white")
    table.add_column("Spread", style="yellow")
    table.add_column("Spread (bps)", style="white")

    for symbol, data in summary.items():
        table.add_row(
            symbol,
            f"{data['best_bid']:.2f}" if data['best_bid'] else "N/A",
            f"{data['best_ask']:.2f}" if data['best_ask'] else "N/A",
            f"{data['mid_price']:.2f}" if data['mid_price'] else "N/A",
            f"{data['spread']:.4f}" if data['spread'] else "N/A",
            f"{data['spread_bps']:.2f}" if data['spread_bps'] else "N/A"
        )

    console.print(table)


@app.command()
def risk():
    """Show risk management status."""
    if not cli_session_state:
        rich_print("[yellow]No active session[/yellow]")
        return

    # Calculate risk summary from session state
    from ..core.config import settings

    open_positions = len([
        p for p in cli_session_state.positions.values()
        if p.quantity != 0
    ])

    risk_summary = {
        "max_daily_loss_pct": settings.risk.max_daily_loss_pct / 100,
        "max_position_pct": settings.risk.max_position_pct / 100,
        "max_open_positions": settings.risk.max_open_positions,
        "current_open_positions": open_positions,
        "consecutive_losses": cli_session_state.consecutive_losses,
        "cooldown_active": cli_session_state.should_cooldown(),
        "cooldown_until": cli_session_state.cooldown_until.isoformat() if cli_session_state.cooldown_until else None,
        "daily_pnl": cli_session_state.session_pnl,
        "daily_loss_pct": abs(cli_session_state.session_pnl) / 100000 * 100  # Assuming $100k starting equity
    }

    table = Table(title="Risk Management Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Max Daily Loss %", f"{risk_summary['max_daily_loss_pct'] * 100:.1f}%")
    table.add_row("Max Position %", f"{risk_summary['max_position_pct'] * 100:.1f}%")
    table.add_row("Max Open Positions", str(risk_summary['max_open_positions']))
    table.add_row("Current Open Positions", str(risk_summary['current_open_positions']))
    table.add_row("Consecutive Losses", str(risk_summary['consecutive_losses']))
    table.add_row("Cooldown Active", "Yes" if risk_summary['cooldown_active'] else "No")

    if risk_summary['cooldown_until']:
        table.add_row("Cooldown Until", risk_summary['cooldown_until'])

    table.add_row("Daily P&L", f"${risk_summary['daily_pnl']:.2f}")

    console.print(table)


@app.command()
def export_logs(session_id: str, output: Path):
    """Export session logs to a file."""
    try:
        # This is a simplified version - in a real implementation,
        # you would read from the actual log files
        logs_data = {
            "session_id": session_id,
            "exported_at": time.time(),
            "logs": "Session logs would be exported here"
        }

        with open(output, 'w') as f:
            json.dump(logs_data, f, indent=2)

        rich_print(f"[green]Logs exported to {output}[/green]")

    except Exception as e:
        rich_print(f"[red]Error exporting logs: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def health():
    """Check system health."""
    # Check database
    try:
        init_db()
        db_status = "[green]OK[/green]"
    except Exception:
        db_status = "[red]ERROR[/red]"

    # Check configuration
    config_status = "[green]OK[/green]" if settings else "[red]ERROR[/red]"

    # Check components
    components_status = "OK" if cli_session_state else "No active session"

    table = Table(title="System Health")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")

    table.add_row("Database", db_status)
    table.add_row("Configuration", config_status)
    table.add_row("Active Components", components_status)

    console.print(table)


def main():
    """Main CLI entry point."""
    # Initialize database
    init_db()

    # Run CLI
    app()


if __name__ == "__main__":
    main()
