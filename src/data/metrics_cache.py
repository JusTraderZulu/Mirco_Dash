"""
Simple SQLite cache for microstructure metrics.
Allows sharing metrics between API server and data collection processes.
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from pathlib import Path


class MetricsCache:
    """SQLite cache for microstructure metrics."""
    
    def __init__(self, db_path: str = "data/metrics_cache.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Current/latest metrics (for fast access)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    symbol TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    current_price REAL,
                    ofi REAL,
                    spread_bps REAL,
                    realized_vol REAL,
                    depth_imbalance REAL,
                    liquidity_concentration REAL,
                    microprice REAL,
                    price_impact_lambda REAL,
                    market_depth_elasticity REAL,
                    effective_spread_bps REAL,
                    quadratic_variation REAL,
                    aggressive_ratio REAL,
                    passive_ratio REAL,
                    trade_count INTEGER,
                    features_json TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Historical time-series (stores every update)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_timeseries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    current_price REAL,
                    ofi REAL,
                    spread_bps REAL,
                    realized_vol REAL,
                    bias TEXT,
                    confidence REAL,
                    timeframe TEXT,
                    data_window_seconds INTEGER,
                    full_data_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts_symbol_time ON metrics_timeseries(symbol, timestamp DESC)")
            
            conn.commit()
    
    def store_metrics(self, symbol: str, features: Dict, scenario: Dict = None, monte_carlo: Dict = None, timing: Dict = None):
        """Store metrics for a symbol (both current and historical)."""
        now = datetime.now(timezone.utc)
        
        with sqlite3.connect(self.db_path) as conn:
            # Store latest (for fast access)
            conn.execute("""
                INSERT OR REPLACE INTO metrics (
                    symbol, timestamp, current_price, ofi, spread_bps, realized_vol,
                    depth_imbalance, liquidity_concentration, microprice, 
                    price_impact_lambda, market_depth_elasticity, effective_spread_bps,
                    quadratic_variation, aggressive_ratio, passive_ratio, trade_count,
                    features_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                now.isoformat(),
                features.get("current_price"),
                features.get("ofi"),
                features.get("spread_bps"),
                features.get("realized_vol"),
                features.get("depth_imbalance"),
                features.get("liquidity_concentration"),
                features.get("microprice"),
                features.get("price_impact_lambda"),
                features.get("market_depth_elasticity"),
                features.get("effective_spread_bps"),
                features.get("quadratic_variation"),
                features.get("aggressive_ratio"),
                features.get("passive_ratio"),
                features.get("trade_count"),
                json.dumps({"features": features, "scenario": scenario, "monte_carlo": monte_carlo, "timing": timing}),
                now.isoformat()
            ))
            
            # Also store in time-series for history
            conn.execute("""
                INSERT INTO metrics_timeseries (
                    symbol, timestamp, current_price, ofi, spread_bps, realized_vol,
                    bias, confidence, timeframe, data_window_seconds, full_data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol,
                now.isoformat(),
                features.get("current_price"),
                features.get("ofi"),
                features.get("spread_bps"),
                features.get("realized_vol"),
                scenario.get("bias") if scenario else None,
                scenario.get("confidence") if scenario else None,
                timing.get("suggested_timeframe") if timing else None,
                timing.get("data_window_seconds") if timing else None,
                json.dumps({"features": features, "scenario": scenario, "monte_carlo": monte_carlo, "timing": timing}),
                now.isoformat()
            ))
            
            conn.commit()
    
    def get_metrics(self, symbol: str) -> Optional[Dict]:
        """Get latest metrics for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM metrics WHERE symbol = ? ORDER BY updated_at DESC LIMIT 1",
                (symbol,)
            )
            row = cursor.fetchone()
            
            if row:
                full_data = json.loads(row["features_json"])
                return {
                    "symbol": row["symbol"],
                    "timestamp": row["timestamp"],
                    "features": full_data.get("features", {}),
                    "scenario": full_data.get("scenario", {}),
                    "monte_carlo": full_data.get("monte_carlo", {}),
                    "updated_at": row["updated_at"]
                }
            return None
    
    def get_all_symbols(self) -> list:
        """Get all symbols with cached metrics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT DISTINCT symbol FROM metrics ORDER BY updated_at DESC")
            return [row[0] for row in cursor.fetchall()]
    
    def get_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get historical time-series data."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT timestamp, current_price, ofi, spread_bps, realized_vol, 
                       bias, confidence, timeframe
                FROM metrics_timeseries 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """, (symbol, since.isoformat()))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_data_stats(self, symbol: str) -> Dict:
        """Get statistics about data coverage and gaps."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest
                FROM metrics_timeseries
                WHERE symbol = ?
            """, (symbol,))
            
            row = cursor.fetchone()
            
            if row and row[0] > 0:
                earliest = datetime.fromisoformat(row[1])
                latest = datetime.fromisoformat(row[2])
                coverage_hours = (latest - earliest).total_seconds() / 3600
                
                return {
                    "total_records": row[0],
                    "earliest": row[1],
                    "latest": row[2],
                    "coverage_hours": coverage_hours,
                    "has_gap": (datetime.now(timezone.utc) - latest).total_seconds() / 60 > 5
                }
            
            return {
                "total_records": 0,
                "has_gap": True
            }


# Global cache instance
_metrics_cache = MetricsCache()

def get_metrics_cache() -> MetricsCache:
    """Get the global metrics cache instance."""
    return _metrics_cache

