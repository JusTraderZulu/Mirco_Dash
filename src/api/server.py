"""
FastAPI server for TEPM system.

Provides REST API endpoints for session management, positions, orders, signals, and microstructure analytics.
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core.logger import LoggerMixin, logger, set_session_context
from ..core.models import Incident, Session as SessionModel
from ..core.state import SessionState
from ..data.orderbook import get_orderbook_manager
from ..execution.router import ExecutionRouter
from ..portfolio.manager import PortfolioManager
from ..portfolio.risk_agent import get_risk_agent
from ..signals.engine import SignalEngine
from ..signals.microstructure import get_microstructure_signals
from ..signals.montecarlo import get_monte_carlo

# Create the FastAPI app instance
app = FastAPI(
    title="TEPM System API",
    description="Trade Execution & Portfolio Management System",
    version="1.0.0"
)

# Enable CORS for web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# System components - these will be initialized when needed
_session_state: Optional[SessionState] = None
_signal_engine: Optional[SignalEngine] = None
_portfolio_manager: Optional[PortfolioManager] = None
_execution_router: Optional[ExecutionRouter] = None
_feed_handler = None


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health/live")
async def health_live():
    """Liveness probe."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe."""
    if not _session_state or not _session_state.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System not ready"
        )
    return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}


# ============================================================================
# Session Management Endpoints
# ============================================================================

@app.post("/session/start")
async def start_session(symbols: List[str], env: str = "paper"):
    """Start a new trading session."""
    global _session_state, _signal_engine, _portfolio_manager, _execution_router, _feed_handler

    try:
        session_id = f"session_{int(time.time())}"
        _session_state = SessionState(session_id, symbols, env)
        _signal_engine = SignalEngine(_session_state)
        _portfolio_manager = PortfolioManager(_session_state)
        _execution_router = ExecutionRouter(_session_state)
        
        # Create and start feed handler for Polygon data
        from ..data.feed_handler import create_feed_handler
        _feed_handler = create_feed_handler(_session_state)

        # Start all components
        await _signal_engine.start()
        await _portfolio_manager.start()
        await _execution_router.start()
        
        # Start feed handler (this will begin polling Polygon)
        asyncio.create_task(_feed_handler.start())

        logger.info(f"Started session {session_id} with symbols: {symbols}")
        logger.info("Feed handler started - collecting market data from Polygon")

        return {
            "session_id": session_id,
            "status": "started",
            "symbols": symbols,
            "env": env,
            "feed_handler": "Polygon REST API" if hasattr(_feed_handler, 'poll_interval') else "Simulated"
        }

    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/stop")
async def stop_session():
    """Stop the current trading session."""
    global _session_state, _signal_engine, _portfolio_manager, _execution_router, _feed_handler

    if not _session_state:
        raise HTTPException(status_code=404, detail="No active session")

    try:
        if _feed_handler:
            await _feed_handler.stop()
        if _signal_engine:
            await _signal_engine.stop()
        if _portfolio_manager:
            await _portfolio_manager.stop()
        if _execution_router:
            await _execution_router.stop()

        logger.info(f"Stopped session {_session_state.session_id}")
        return {"status": "stopped"}

    except Exception as e:
        logger.error(f"Error stopping session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/status")
async def get_session_status():
    """Get current session status."""
    if not _session_state:
        raise HTTPException(status_code=404, detail="No active session")

    return {
        "session_id": _session_state.session_id,
        "is_active": _session_state.is_active,
        "is_paused": _session_state.is_paused,
        "symbols": list(_session_state.symbols),
        "started_at": _session_state.started_at.isoformat(),
        "env": _session_state.env
    }


# ============================================================================
# Trading Endpoints
# ============================================================================

@app.get("/positions")
async def get_positions():
    """Get current positions."""
    if not _session_state:
        raise HTTPException(status_code=404, detail="No active session")

    positions = []
    for pos in _session_state.positions.values():
        positions.append({
            "symbol": pos.symbol,
            "quantity": float(pos.quantity),
            "average_price": float(pos.average_price),
            "unrealized_pnl": float(pos.unrealized_pnl),
            "realized_pnl": float(pos.realized_pnl),
            "state": pos.state.value,
            "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
            "stop_loss": float(pos.stop_loss) if pos.stop_loss else None,
            "take_profit": float(pos.take_profit) if pos.take_profit else None
        })

    return positions


@app.get("/orders")
async def get_orders(status_filter: Optional[str] = None):
    """Get current orders."""
    if not _session_state:
        raise HTTPException(status_code=404, detail="No active session")

    orders = []
    for order in _session_state.orders.values():
        if status_filter and order.status.value != status_filter:
            continue

        orders.append({
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": float(order.quantity),
            "price": float(order.price) if order.price else None,
            "status": order.status.value,
            "filled_quantity": float(order.filled_quantity),
            "average_fill_price": float(order.average_fill_price) if order.average_fill_price else None,
            "created_at": order.created_at.isoformat(),
            "reason": order.reason
        })

    return orders


@app.get("/signals/recent")
async def get_recent_signals(limit: int = 10):
    """Get recent trading signals."""
    if not _signal_engine:
        raise HTTPException(status_code=404, detail="No signal engine available")

    scenarios = _signal_engine.get_recent_scenarios(limit=limit)

    signals = []
    for scenario in scenarios:
        signals.append({
            "symbol": scenario.symbol,
            "timestamp": scenario.ts.isoformat(),
            "bias": scenario.bias.value,
            "confidence": scenario.confidence,
            "risk_regime": scenario.risk_regime.value,
            "features": scenario.features,
            "mc": scenario.mc,
            "recommended": {
                "entry": float(scenario.recommended["entry"]),
                "tp": float(scenario.recommended["tp"]),
                "sl": float(scenario.recommended["sl"])
            }
        })

    return signals


# ============================================================================
# Market Data Endpoints
# ============================================================================

@app.get("/market/summary")
async def get_market_summary():
    """Get market data summary."""
    orderbook_manager = get_orderbook_manager()
    summary = orderbook_manager.get_market_summary()

    return {
        "symbols": list(summary.keys()),
        "data": summary,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Portfolio & Risk Endpoints
# ============================================================================

@app.get("/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary."""
    if not _portfolio_manager:
        raise HTTPException(status_code=404, detail="No portfolio manager available")

    return _portfolio_manager.get_portfolio_summary()


@app.get("/risk/summary")
async def get_risk_summary():
    """Get risk management summary."""
    if not _session_state:
        raise HTTPException(status_code=404, detail="No active session")

    risk_agent = get_risk_agent()
    if not risk_agent:
        raise HTTPException(status_code=503, detail="Risk agent not initialized")
    
    return risk_agent.get_risk_summary()


@app.post("/orders/override")
async def override_order(order_id: str, reason: str):
    """Override an order (for manual intervention)."""
    if not _execution_router:
        raise HTTPException(status_code=404, detail="No execution router available")

    order = _session_state.orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.reason = f"OVERRIDE: {reason}"
    await _session_state.update_order(order)

    logger.info(f"Order {order_id} overridden: {reason}")

    return {"status": "overridden", "order_id": order_id, "reason": reason}


@app.get("/incidents")
async def get_incidents(limit: int = 20):
    """Get recent incidents."""
    if not _session_state:
        raise HTTPException(status_code=404, detail="No active session")

    incidents = _session_state.incidents[-limit:]

    return [
        {
            "incident_id": incident.incident_id,
            "timestamp": incident.timestamp.isoformat(),
            "component": incident.component,
            "severity": incident.severity,
            "message": incident.message,
            "extra": incident.extra
        }
        for incident in incidents
    ]


# ============================================================================
# Dashboard Microstructure Endpoints
# ============================================================================

@app.get("/microstructure/{symbol}")
async def get_microstructure_data(symbol: str):
    """Get comprehensive microstructure data for a symbol - fetches fresh from Polygon."""
    try:
        import httpx
        import numpy as np
        
        # Detect asset type and map to Polygon format
        is_forex = symbol in ["EUR-USD", "GBP-USD", "USD-JPY", "AUD-USD", "USD-CAD", "NZD-USD", "USD-CHF"]
        
        # Crypto mapping
        crypto_map = {
            "BTC-USD": "X:BTCUSD", "ETH-USD": "X:ETHUSD", "ADA-USD": "X:ADAUSD",
            "SOL-USD": "X:SOLUSD", "DOT-USD": "X:DOTUSD", "LINK-USD": "X:LINKUSD",
            "UNI-USD": "X:UNIUSD", "AAVE-USD": "X:AAVEUSD", "XRP-USD": "X:XRPUSD",
            "DOGE-USD": "X:DOGEUSD", "AVAX-USD": "X:AVAXUSD", "MATIC-USD": "X:MATICUSD",
            "ATOM-USD": "X:ATOMUSD", "LTC-USD": "X:LTCUSD", "BCH-USD": "X:BCHUSD"
        }
        
        # Forex mapping
        forex_map = {
            "EUR-USD": "C:EURUSD", "GBP-USD": "C:GBPUSD", "USD-JPY": "C:USDJPY",
            "AUD-USD": "C:AUDUSD", "USD-CAD": "C:USDCAD", "NZD-USD": "C:NZDUSD",
            "USD-CHF": "C:USDCHF"
        }
        
        if is_forex:
            polygon_symbol = forex_map.get(symbol, f"C:{symbol.replace('-', '')}")
        else:
            if symbol not in crypto_map:
                base = symbol.split("-")[0]
                polygon_symbol = f"X:{base}USD"
            else:
                polygon_symbol = crypto_map[symbol]
        
        api_key = os.getenv("POLYGON_API_KEY") or open("polygon_api.txt").read().strip()
        
        # Fetch fresh data from Polygon
        current_price = None
        recent_trades = []
        recent_spreads = []
        has_level2 = False
        
        # Store raw response for timestamp calculations
        raw_trade_data = None
        
        async with httpx.AsyncClient(base_url="https://api.polygon.io", timeout=10.0) as client:
            if is_forex:
                # FOREX: Use quotes (Level 2 data with bid/ask)
                response = await client.get(
                    f"/v3/quotes/{polygon_symbol}", 
                    params={"limit": 200, "order": "desc"},
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    raw_trade_data = data
                    if "results" in data and len(data["results"]) > 0:
                        # Forex has bid/ask prices
                        latest = data["results"][0]
                        bid = float(latest.get("bid_price", 0))
                        ask = float(latest.get("ask_price", 0))
                        current_price = (bid + ask) / 2 if bid and ask else None
                        
                        # Extract mid prices and spreads for analysis
                        for quote in data["results"][:200]:
                            b = float(quote.get("bid_price", 0))
                            a = float(quote.get("ask_price", 0))
                            if b > 0 and a > 0:
                                recent_trades.append((b + a) / 2)
                                recent_spreads.append(a - b)
                        
                        has_level2 = True
            else:
                # CRYPTO: Use trades
                response = await client.get(
                    f"/v3/trades/{polygon_symbol}", 
                    params={"limit": 200, "order": "desc"},
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    raw_trade_data = data
                    if "results" in data and len(data["results"]) > 0:
                        current_price = float(data["results"][0]["price"])
                        recent_trades = [float(t["price"]) for t in data["results"][:200]]

            # If no price from Polygon, return error
            if not current_price:
                raise HTTPException(status_code=503, detail="No price data available from Polygon")
        
        # Calculate metrics from recent trades
        returns = []
        if len(recent_trades) > 1:
            for i in range(1, len(recent_trades)):
                ret = (recent_trades[i-1] - recent_trades[i]) / recent_trades[i]
                returns.append(ret)
        
        # Volatility
        realized_vol = np.std(returns) * np.sqrt(252 * 24 * 60) if returns else 0.02
        qv = sum([r**2 for r in returns]) if returns else 0.0
        
        # Spread calculation (use real spreads for forex Level 2 data)
        if has_level2 and len(recent_spreads) > 0:
            # FOREX: Use actual bid-ask spreads
            spread_estimate = np.mean(recent_spreads)
            spread_bps = (spread_estimate / current_price) * 10000
        elif len(recent_trades) > 10:
            # CRYPTO: Estimate from price range
            spread_estimate = (max(recent_trades[:10]) - min(recent_trades[:10])) / 2
            spread_bps = (spread_estimate / current_price) * 10000
        else:
            spread_estimate = current_price * 0.0001
            spread_bps = 1.0
        
        # OFI proxy: count price increases vs decreases
        up_moves = sum(1 for r in returns[:20] if r > 0) if len(returns) > 0 else 0
        down_moves = sum(1 for r in returns[:20] if r < 0) if len(returns) > 0 else 0
        total_moves = up_moves + down_moves
        ofi_proxy = (up_moves - down_moves) / total_moves if total_moves > 0 else 0.0
        
        # Aggressive ratio
        aggressive_count = sum(1 for r in returns if abs(r) > np.std(returns) * 0.5) if len(returns) > 10 else 0
        aggressive_ratio = aggressive_count / len(returns) if returns else 0.5
        
        # Advanced metrics
        depth_imbalance = ofi_proxy
        price_range = (max(recent_trades[:20]) - min(recent_trades[:20])) if len(recent_trades) >= 20 else 0
        liquidity_concentration = 1.0 - (price_range / current_price) if current_price > 0 else 0.5
        microprice = np.average(recent_trades[:10]) if len(recent_trades) >= 10 else current_price
        
        if len(returns) > 10:
            price_impact = np.std(returns[:50]) * current_price if len(returns) >= 50 else spread_estimate
        else:
            price_impact = spread_estimate
        
        avg_trade_size = current_price * 0.1
        depth_elasticity = (price_impact / avg_trade_size) * 1_000_000 if avg_trade_size > 0 else 0
        
        recent_prices = recent_trades[:10]
        if len(recent_prices) > 1:
            mid_proxy = np.median(recent_prices)
            effective_spread = 2 * np.mean([abs(p - mid_proxy) for p in recent_prices])
            effective_spread_bps = (effective_spread / current_price) * 10000
        else:
            effective_spread = spread_estimate
            effective_spread_bps = spread_bps
        
        features = {
            "ofi": float(ofi_proxy),
            "ofi_mean": float(ofi_proxy * 0.8),
            "ofi_std": float(abs(ofi_proxy) * 0.3),
            "spread_current": float(spread_estimate),
            "spread_mean": float(spread_estimate * 1.1),
            "spread_bps": float(spread_bps),
            "aggressive_ratio": float(aggressive_ratio),
            "passive_ratio": float(1 - aggressive_ratio),
            "quadratic_variation": float(qv),
            "realized_vol": float(realized_vol),
            "current_price": current_price,
            "trade_count": len(recent_trades),
            "depth_imbalance": float(depth_imbalance),
            "liquidity_concentration": float(liquidity_concentration),
            "microprice": float(microprice),
            "price_impact_lambda": float(price_impact),
            "market_depth_elasticity": float(depth_elasticity),
            "effective_spread": float(effective_spread),
            "effective_spread_bps": float(effective_spread_bps),
            "data_type": "level2" if has_level2 else "trades",
            "asset_type": "forex" if is_forex else "crypto"
        }
        
        # Trading scenario
        recent_trend = np.mean(returns[:10]) if len(returns) >= 10 else 0
        bias = "long" if recent_trend > 0 else "short" if recent_trend < 0 else "neutral"
        confidence = min(abs(recent_trend) * 50 + 0.5, 0.95) if recent_trend != 0 else 0.5
        
        scenario = {
            "bias": bias,
            "confidence": float(confidence),
            "risk_regime": "high_vol" if realized_vol > 0.05 else "medium_vol" if realized_vol > 0.02 else "low_vol",
            "recommended": {
                "entry": current_price,
                "tp": current_price * (1.02 if bias == "long" else 0.98),
                "sl": current_price * (0.99 if bias == "long" else 1.01)
            }
        }
        
        # Monte Carlo estimates
        monte_carlo = {
            "upside_prob": float(0.5 + ofi_proxy * 0.3),
            "downside_prob": float(0.5 - ofi_proxy * 0.3),
            "tp_hit_prob": float(0.5 + confidence * 0.2),
            "sl_hit_prob": float(0.3),
            "var_5pct": float(current_price * realized_vol * 2.33)
        }
        
        # Time-to-target calculations
        # Using volatility to estimate time to reach TP/SL
        # Formula: time = (price_distance / expected_move_per_minute)^2
        tp_distance = abs(scenario["recommended"]["tp"] - current_price) / current_price
        sl_distance = abs(scenario["recommended"]["sl"] - current_price) / current_price
        
        # Volatility per minute (annualized vol / sqrt(minutes in year))
        vol_per_minute = realized_vol / np.sqrt(252 * 24 * 60) if realized_vol > 0 else 0.001
        
        # Expected time in minutes (with realistic bounds)
        minutes_to_tp = min(int((tp_distance / (vol_per_minute * 2)) if vol_per_minute > 0 else 120), 240)
        minutes_to_sl = min(int((sl_distance / (vol_per_minute * 2)) if vol_per_minute > 0 else 60), 120)
        
        # Recommended holding period
        recommended_hold_min = int(minutes_to_tp * 0.7)  # 70% of expected TP time
        recommended_hold_max = int(minutes_to_tp * 1.5)  # 150% of expected TP time
        
        # Signal freshness (how long this analysis is valid for)
        signal_valid_minutes = 300  # Refresh recommended every 5 min (300 seconds)
        
        # Calculate time window of trades (first to last trade timestamp)
        data_window_seconds = 0
        if raw_trade_data and "results" in raw_trade_data and len(raw_trade_data["results"]) >= 2:
            try:
                # Polygon returns timestamps in nanoseconds
                first_trade = raw_trade_data["results"][-1]  # Oldest (results are desc order)
                last_trade = raw_trade_data["results"][0]    # Newest
                
                # Try different timestamp fields
                first_time = first_trade.get("participant_timestamp") or first_trade.get("sip_timestamp", 0)
                last_time = last_trade.get("participant_timestamp") or last_trade.get("sip_timestamp", 0)
                
                if first_time and last_time and last_time > first_time:
                    data_window_seconds = (last_time - first_time) / 1_000_000_000  # Convert nanoseconds to seconds
            except Exception as e:
                logger.warning(f"Could not calculate data window: {e}")
                pass
        
        timing = {
            "expected_tp_minutes": minutes_to_tp,
            "expected_sl_minutes": minutes_to_sl,
            "recommended_hold_min": max(recommended_hold_min, 15),  # At least 15 min
            "recommended_hold_max": min(recommended_hold_max, 240),  # Max 4 hours
            "signal_valid_minutes": signal_valid_minutes,
            "analysis_window_trades": len(recent_trades),
            "data_window_seconds": int(data_window_seconds) if data_window_seconds > 0 else 0,
            "data_window_minutes": max(1, int(data_window_seconds / 60)) if data_window_seconds > 0 else 0,  # Show at least 1 min
            "suggested_timeframe": "scalp" if minutes_to_tp < 30 else "intraday" if minutes_to_tp < 120 else "swing",
            "data_freshness": "live" if data_window_seconds > 0 and data_window_seconds < 600 else "recent"
        }

        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "features": features,
            "scenario": scenario,
            "monte_carlo": monte_carlo,
            "timing": timing,
            "orderbook": None
        }
        
        # Cache the metrics (both current and time-series)
        try:
            from ..data.metrics_cache import get_metrics_cache
            cache = get_metrics_cache()
            cache.store_metrics(symbol, features, scenario, monte_carlo, timing)
        except Exception as cache_error:
            logger.warning(f"Failed to cache metrics: {cache_error}")
        
        return result

    except Exception as e:
        logger.error(f"Error getting microstructure data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/microstructure/cached/{symbol}")
async def get_cached_metrics(symbol: str):
    """Get metrics from cache (faster, shared across processes)."""
    try:
        from ..data.metrics_cache import get_metrics_cache
        cache = get_metrics_cache()
        data = cache.get_metrics(symbol)
        
        if data:
            return data
        else:
            raise HTTPException(status_code=404, detail=f"No cached metrics for {symbol}")
    except Exception as e:
        logger.error(f"Error getting cached metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/assets/available")
async def get_available_assets():
    """Get list of available assets for analysis."""
    from ..data.metrics_cache import get_metrics_cache
    cache = get_metrics_cache()
    cached_symbols = cache.get_all_symbols()
    
    # Expanded list of supported assets on Polygon
    assets = [
        # === FOREX PAIRS (Level 2 Data Available) ===
        {"symbol": "EUR-USD", "name": "Euro / US Dollar", "type": "forex", "market_cap": "major", "has_data": "EUR-USD" in cached_symbols},
        {"symbol": "GBP-USD", "name": "British Pound / US Dollar", "type": "forex", "market_cap": "major", "has_data": "GBP-USD" in cached_symbols},
        {"symbol": "USD-JPY", "name": "US Dollar / Japanese Yen", "type": "forex", "market_cap": "major", "has_data": "USD-JPY" in cached_symbols},
        {"symbol": "AUD-USD", "name": "Australian Dollar / US Dollar", "type": "forex", "market_cap": "major", "has_data": "AUD-USD" in cached_symbols},
        {"symbol": "USD-CAD", "name": "US Dollar / Canadian Dollar", "type": "forex", "market_cap": "major", "has_data": "USD-CAD" in cached_symbols},
        {"symbol": "NZD-USD", "name": "New Zealand Dollar / US Dollar", "type": "forex", "market_cap": "major", "has_data": "NZD-USD" in cached_symbols},
        {"symbol": "USD-CHF", "name": "US Dollar / Swiss Franc", "type": "forex", "market_cap": "major", "has_data": "USD-CHF" in cached_symbols},
        
        # === CRYPTO (Trade Data) ===
        {"symbol": "BTC-USD", "name": "Bitcoin", "type": "crypto", "market_cap": "large", "has_data": "BTC-USD" in cached_symbols},
        {"symbol": "ETH-USD", "name": "Ethereum", "type": "crypto", "market_cap": "large", "has_data": "ETH-USD" in cached_symbols},
        {"symbol": "XRP-USD", "name": "Ripple", "type": "crypto", "market_cap": "large", "has_data": "XRP-USD" in cached_symbols},
        {"symbol": "SOL-USD", "name": "Solana", "type": "crypto", "market_cap": "large", "has_data": "SOL-USD" in cached_symbols},
        {"symbol": "ADA-USD", "name": "Cardano", "type": "crypto", "market_cap": "large", "has_data": "ADA-USD" in cached_symbols},
        {"symbol": "DOGE-USD", "name": "Dogecoin", "type": "crypto", "market_cap": "large", "has_data": "DOGE-USD" in cached_symbols},
        {"symbol": "AVAX-USD", "name": "Avalanche", "type": "crypto", "market_cap": "large", "has_data": "AVAX-USD" in cached_symbols},
        {"symbol": "MATIC-USD", "name": "Polygon", "type": "crypto", "market_cap": "large", "has_data": "MATIC-USD" in cached_symbols},
        {"symbol": "DOT-USD", "name": "Polkadot", "type": "crypto", "market_cap": "mid", "has_data": "DOT-USD" in cached_symbols},
        {"symbol": "LINK-USD", "name": "Chainlink", "type": "crypto", "market_cap": "mid", "has_data": "LINK-USD" in cached_symbols},
        {"symbol": "UNI-USD", "name": "Uniswap", "type": "crypto", "market_cap": "mid", "has_data": "UNI-USD" in cached_symbols},
        {"symbol": "AAVE-USD", "name": "Aave", "type": "crypto", "market_cap": "mid", "has_data": "AAVE-USD" in cached_symbols},
    ]

    return {
        "assets": assets,
        "count": len(assets),
        "cached_count": len(cached_symbols),
        "timestamp": datetime.utcnow().isoformat(),
        "note": "All assets are available for analysis. Select any to fetch live data from Polygon."
    }


# ============================================================================
# AI Analysis Endpoint
# ============================================================================

class QueryRequest(BaseModel):
    query: str
    symbol: str = "BTC-USD"


@app.post("/analysis/query")
async def query_analysis(request: QueryRequest):
    """Query analysis using LLM for trading insights."""
    try:
        from ..agents.tools import get_metrics, get_context, get_risk_envelope
        import httpx
        
        # Get metrics from cache
        from ..data.metrics_cache import get_metrics_cache
        cache = get_metrics_cache()
        cached_data = cache.get_metrics(request.symbol)
        
        # Fetch fresh microstructure data with timing
        full_data = None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"http://localhost:8000/microstructure/{request.symbol}")
                if response.status_code == 200:
                    full_data = response.json()
        except:
            pass
        
        # Use full data if available, otherwise use cache
        if full_data:
            metrics = full_data.get("features", {})
            scenario = full_data.get("scenario", {})
            timing = full_data.get("timing", {})
            monte_carlo = full_data.get("monte_carlo", {})
        elif cached_data and cached_data.get("features"):
            metrics = cached_data["features"]
            scenario = cached_data.get("scenario", {})
            timing = cached_data.get("timing", {})
            monte_carlo = cached_data.get("monte_carlo", {})
        else:
            metrics = {"mid": 0, "ofi": 0, "spread_bps": 0, "realized_vol": 0}
            scenario = {}
            timing = {}
            monte_carlo = {}
        
        context = get_context(request.symbol)
        env = get_risk_envelope()
        
        # Call Perplexity API
        api_key = os.getenv("PPLX_API_KEY") or open("pplx_api.txt").read().strip()
        
        # Build comprehensive prompt with all available data
        current_price = metrics.get('current_price', metrics.get('mid', 0))
        bias = scenario.get('bias', 'unknown')
        confidence = scenario.get('confidence', 0)
        
        prompt = f"""You are a professional crypto trader analyzing {request.symbol} for intraday futures trading on Coinbase.

LIVE MARKET DATA (Just analyzed {metrics.get('trade_count', 0)} trades from the last {timing.get('data_window_seconds', 0)} seconds):

📊 PRICE & ORDER FLOW:
• Current Price: ${current_price:,.2f}
• OFI (Order Flow Imbalance): {metrics.get('ofi', 0):.3f} {('(Strong BUY pressure ↑)' if metrics.get('ofi', 0) > 0.2 else '(Strong SELL pressure ↓)' if metrics.get('ofi', 0) < -0.2 else '(Neutral)')}
• Aggressive/Passive Ratio: {metrics.get('aggressive_ratio', 0)*100:.1f}% aggressive traders

💧 LIQUIDITY & MICROSTRUCTURE:
• Spread: {metrics.get('spread_bps', 0):.2f} bps {('(Tight - good liquidity ✓)' if metrics.get('spread_bps', 0) < 5 else '(Wide - watch out ⚠)')}
• Depth Imbalance: {metrics.get('depth_imbalance', 0):.3f}
• Liquidity Concentration: {metrics.get('liquidity_concentration', 0)*100:.1f}%
• Price Impact: ${metrics.get('price_impact_lambda', 0):.2f} per trade
• Effective Spread: {metrics.get('effective_spread_bps', 0):.2f} bps (actual cost)

📈 VOLATILITY & RISK:
• Realized Volatility: {metrics.get('realized_vol', 0)*100:.1f}% annualized
• Risk Regime: {scenario.get('risk_regime', 'unknown').replace('_', ' ').upper()}
• VaR (5%): ${monte_carlo.get('var_5pct', 0):,.2f}

⏰ TIMING ANALYSIS:
• Timeframe: {timing.get('suggested_timeframe', 'unknown').upper()} trade
• Expected TP Time: {timing.get('expected_tp_minutes', 0)} minutes
• Expected SL Time: {timing.get('expected_sl_minutes', 0)} minutes
• Recommended Hold: {timing.get('recommended_hold_min', 0)}-{timing.get('recommended_hold_max', 0)} minutes
• Signal is: {timing.get('data_freshness', 'unknown').upper()} (based on {timing.get('analysis_window_trades', 0)} trades)

🎯 AI SCENARIO:
• Bias: {bias.upper()}
• Confidence: {confidence*100:.1f}%
• Entry: ${scenario.get('recommended', {}).get('entry', 0):,.2f}
• TP: ${scenario.get('recommended', {}).get('tp', 0):,.2f} ({monte_carlo.get('tp_hit_prob', 0)*100:.1f}% probability)
• SL: ${scenario.get('recommended', {}).get('sl', 0):,.2f} ({monte_carlo.get('sl_hit_prob', 0)*100:.1f}% probability)

TRADER'S QUESTION: {request.query}

Provide a professional analysis (2-4 sentences) addressing their question. Include:
1. Direct answer to their question
2. Key insight from the microstructure data
3. Specific actionable recommendation with timing
4. Risk consideration they should know

Be specific, use the actual numbers, and think like a professional intraday trader."""

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": "sonar",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        
        with httpx.Client(timeout=30.0) as client:
            r = client.post("https://api.perplexity.ai/chat/completions", headers=headers, json=body)
            if r.status_code == 200:
                llm_response = r.json()["choices"][0]["message"]["content"]
            else:
                llm_response = f"Based on current metrics: Price ${metrics.get('mid', 0):.2f}, OFI {metrics.get('ofi', 0):.3f}, Vol {metrics.get('realized_vol', 0)*100:.1f}%. Analysis unavailable."
        
        # Detect stance
        llm_lower = llm_response.lower()
        if "long" in llm_lower or "buy" in llm_lower or "bullish" in llm_lower:
            stance = "long"
        elif "short" in llm_lower or "sell" in llm_lower or "bearish" in llm_lower:
            stance = "short"
        elif "neutral" in llm_lower or "wait" in llm_lower or "cautious" in llm_lower:
            stance = "neutral"
        else:
            stance = "neutral"
        
        return {
            "query": request.query,
            "symbol": request.symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analysis": llm_response,
            "stance": stance,
            "confidence": 0.7,
            "features": metrics,
            "context": context,
            "recommendations": [
                f"Current Price: ${metrics.get('mid', 0):.2f}",
                f"OFI: {metrics.get('ofi', 0):.3f}",
                f"Volatility: {metrics.get('realized_vol', 0)*100:.1f}%"
            ]
        }

    except Exception as e:
        logger.error(f"Error querying analysis: {e}")
        return {
            "query": request.query,
            "symbol": request.symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analysis": f"Unable to generate analysis. Error: {str(e)}",
            "stance": "neutral",
            "confidence": 0.0,
            "features": {},
            "recommendations": ["System error - please try again"]
        }


# ============================================================================
# Debug Endpoints
# ============================================================================

@app.get("/history/{symbol}")
async def get_symbol_history(symbol: str, hours: int = 24):
    """Get historical time-series data for a symbol."""
    try:
        from ..data.metrics_cache import get_metrics_cache
        cache = get_metrics_cache()
        
        history = cache.get_history(symbol, hours)
        stats = cache.get_data_stats(symbol)
        
        return {
            "symbol": symbol,
            "history": history,
            "stats": stats,
            "hours_requested": hours,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/backfill/{symbol}")
async def backfill_symbol_data(symbol: str, hours: int = 24):
    """Backfill historical data from Polygon for missing periods."""
    try:
        from ..data.historical_cache import get_historical_cache
        
        api_key = os.getenv("POLYGON_API_KEY") or open("polygon_api.txt").read().strip()
        cache = get_historical_cache()
        
        result = await cache.backfill_from_polygon(symbol, api_key, hours)
        
        return {
            "symbol": symbol,
            "backfill_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error backfilling data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data-status/{symbol}")
async def get_data_status(symbol: str):
    """Get data coverage statistics and gap information."""
    try:
        from ..data.metrics_cache import get_metrics_cache
        cache = get_metrics_cache()
        
        stats = cache.get_data_stats(symbol)
        
        return {
            "symbol": symbol,
            "coverage": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting data status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/feed-status")
async def get_feed_status():
    """Get feed handler status for debugging."""
    global _feed_handler
    
    if not _feed_handler:
        return {"status": "no_feed_handler"}
    
    stats = {}
    if hasattr(_feed_handler, 'get_stats'):
        stats = _feed_handler.get_stats()
    
    orderbook_manager = get_orderbook_manager()
    books_info = {}
    for symbol, book in orderbook_manager.get_all_books().items():
        books_info[symbol] = {
            "is_empty": book.is_empty(),
            "bid_levels": len(book.bids),
            "ask_levels": len(book.asks),
            "last_update": book.last_update.isoformat() if book.last_update else None
        }
    
    microstructure = get_microstructure_signals()
    micro_info = {}
    for symbol in ["BTC-USD", "ETH-USD"]:
        if symbol in microstructure.price_history:
            micro_info[symbol] = {
                "price_history_len": len(microstructure.price_history[symbol]),
                "ofi_history_len": len(microstructure.ofi_history.get(symbol, [])),
                "tick_history_len": len(microstructure.tick_history.get(symbol, []))
            }
    
    return {
        "feed_handler": stats,
        "orderbooks": books_info,
        "microstructure": micro_info,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Server Runner
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    logger.info(f"Starting TEPM API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=False)
