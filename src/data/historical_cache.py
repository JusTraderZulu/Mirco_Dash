"""
Historical time-series cache for microstructure metrics.
Stores every data point with timestamps and supports backfilling gaps.
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from pathlib import Path


class HistoricalCache:
    """Time-series cache for microstructure metrics with backfill capability."""
    
    def __init__(self, db_path: str = "data/historical_data.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema for time-series storage."""
        with sqlite3.connect(self.db_path) as conn:
            # Main time-series table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume REAL,
                    source TEXT DEFAULT 'live',
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, timestamp)
                )
            """)
            
            # Metrics history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ofi REAL,
                    spread_bps REAL,
                    realized_vol REAL,
                    depth_imbalance REAL,
                    liquidity_concentration REAL,
                    aggressive_ratio REAL,
                    trade_count INTEGER,
                    bias TEXT,
                    confidence REAL,
                    risk_regime TEXT,
                    data_window_seconds INTEGER,
                    full_data_json TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, timestamp)
                )
            """)
            
            # Backfill tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backfill_status (
                    symbol TEXT PRIMARY KEY,
                    last_backfill_attempt TEXT,
                    last_successful_timestamp TEXT,
                    earliest_data_timestamp TEXT,
                    latest_data_timestamp TEXT,
                    total_records INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes for fast queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_symbol_time ON price_history(symbol, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_symbol_time ON metrics_history(symbol, timestamp DESC)")
            
            conn.commit()
    
    def store_price(self, symbol: str, timestamp: datetime, price: float, volume: float = None, source: str = 'live'):
        """Store a price data point."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO price_history (symbol, timestamp, price, volume, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timestamp.isoformat(),
                    price,
                    volume,
                    source,
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                # Already exists, skip
                pass
    
    def store_metrics(self, symbol: str, timestamp: datetime, features: Dict, scenario: Dict = None, 
                     timing: Dict = None, monte_carlo: Dict = None, source: str = 'live'):
        """Store a complete metrics snapshot."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                full_data = {
                    "features": features,
                    "scenario": scenario,
                    "timing": timing,
                    "monte_carlo": monte_carlo
                }
                
                conn.execute("""
                    INSERT INTO metrics_history (
                        symbol, timestamp, ofi, spread_bps, realized_vol, depth_imbalance,
                        liquidity_concentration, aggressive_ratio, trade_count, bias, confidence,
                        risk_regime, data_window_seconds, full_data_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timestamp.isoformat(),
                    features.get("ofi"),
                    features.get("spread_bps"),
                    features.get("realized_vol"),
                    features.get("depth_imbalance"),
                    features.get("liquidity_concentration"),
                    features.get("aggressive_ratio"),
                    features.get("trade_count"),
                    scenario.get("bias") if scenario else None,
                    scenario.get("confidence") if scenario else None,
                    scenario.get("risk_regime") if scenario else None,
                    timing.get("data_window_seconds") if timing else None,
                    json.dumps(full_data),
                    datetime.now(timezone.utc).isoformat()
                ))
                
                # Update backfill status
                self._update_backfill_status(conn, symbol, timestamp)
                
                conn.commit()
            except sqlite3.IntegrityError:
                # Already exists, skip
                pass
    
    def _update_backfill_status(self, conn, symbol: str, timestamp: datetime):
        """Update backfill tracking."""
        conn.execute("""
            INSERT INTO backfill_status (symbol, last_successful_timestamp, latest_data_timestamp, total_records)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(symbol) DO UPDATE SET
                last_successful_timestamp = excluded.last_successful_timestamp,
                latest_data_timestamp = excluded.latest_data_timestamp,
                total_records = total_records + 1
        """, (symbol, timestamp.isoformat(), timestamp.isoformat()))
    
    def get_last_timestamp(self, symbol: str) -> Optional[datetime]:
        """Get the most recent timestamp for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT latest_data_timestamp FROM backfill_status WHERE symbol = ?",
                (symbol,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None
    
    def get_data_gap(self, symbol: str) -> Optional[tuple]:
        """Get the time gap that needs backfilling (last_timestamp, now)."""
        last_ts = self.get_last_timestamp(symbol)
        now = datetime.now(timezone.utc)
        
        if last_ts:
            gap_minutes = (now - last_ts).total_seconds() / 60
            if gap_minutes > 5:  # Only report gaps > 5 minutes
                return (last_ts, now, gap_minutes)
        
        return None
    
    def get_metrics_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get historical metrics for a symbol."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM metrics_history 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (symbol, since.isoformat()))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "timestamp": row["timestamp"],
                    "ofi": row["ofi"],
                    "spread_bps": row["spread_bps"],
                    "realized_vol": row["realized_vol"],
                    "bias": row["bias"],
                    "confidence": row["confidence"],
                    "trade_count": row["trade_count"]
                })
            
            return results
    
    def get_price_history(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get historical prices for a symbol."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM price_history 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (symbol, since.isoformat()))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "timestamp": row["timestamp"],
                    "price": row["price"],
                    "volume": row["volume"],
                    "source": row["source"]
                })
            
            return results
    
    def get_stats(self, symbol: str) -> Dict:
        """Get statistics about stored data."""
        with sqlite3.connect(self.db_path) as conn:
            # Get record counts
            cursor = conn.execute(
                "SELECT COUNT(*) FROM metrics_history WHERE symbol = ?",
                (symbol,)
            )
            metrics_count = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM price_history WHERE symbol = ?",
                (symbol,)
            )
            price_count = cursor.fetchone()[0]
            
            # Get time range
            cursor = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM metrics_history WHERE symbol = ?",
                (symbol,)
            )
            time_range = cursor.fetchone()
            
            # Get backfill status
            cursor = conn.execute(
                "SELECT * FROM backfill_status WHERE symbol = ?",
                (symbol,)
            )
            backfill_row = cursor.fetchone()
            
            return {
                "symbol": symbol,
                "metrics_count": metrics_count,
                "price_count": price_count,
                "earliest_data": time_range[0] if time_range[0] else None,
                "latest_data": time_range[1] if time_range[1] else None,
                "total_records": backfill_row[4] if backfill_row else 0
            }
    
    async def backfill_from_polygon(self, symbol: str, api_key: str, hours: int = 24):
        """Backfill historical data from Polygon for missing time periods."""
        import httpx
        
        # Check for gaps
        gap = self.get_data_gap(symbol)
        if not gap:
            return {"status": "no_gap", "message": "Data is up to date"}
        
        last_ts, now_ts, gap_minutes = gap
        
        # Polygon symbol mapping
        symbol_map = {
            "BTC-USD": "X:BTCUSD", "ETH-USD": "X:ETHUSD", "SOL-USD": "X:SOLUSD",
            "DOGE-USD": "X:DOGEUSD", "XRP-USD": "X:XRPUSD", "ADA-USD": "X:ADAUSD"
        }
        polygon_symbol = symbol_map.get(symbol, f"X:{symbol.split('-')[0]}USD")
        
        # Fetch historical aggregate bars to fill the gap
        # Using minute bars for microstructure data
        from_ms = int(last_ts.timestamp() * 1000)
        to_ms = int(now_ts.timestamp() * 1000)
        
        backfilled_count = 0
        
        try:
            async with httpx.AsyncClient(base_url="https://api.polygon.io", timeout=30.0) as client:
                # Get minute bars
                response = await client.get(
                    f"/v2/aggs/ticker/{polygon_symbol}/range/1/minute/{from_ms}/{to_ms}",
                    params={"adjusted": "true", "sort": "asc", "limit": 50000},
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    
                    for bar in results:
                        bar_time = datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc)
                        self.store_price(
                            symbol=symbol,
                            timestamp=bar_time,
                            price=bar["c"],  # Close price
                            volume=bar["v"],
                            source="backfill"
                        )
                        backfilled_count += 1
                    
                    return {
                        "status": "success",
                        "backfilled_count": backfilled_count,
                        "gap_filled_minutes": gap_minutes,
                        "from": last_ts.isoformat(),
                        "to": now_ts.isoformat()
                    }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "gap_minutes": gap_minutes
            }
        
        return {"status": "no_data", "gap_minutes": gap_minutes}


# Global instance
_historical_cache = HistoricalCache()

def get_historical_cache() -> HistoricalCache:
    """Get the global historical cache instance."""
    return _historical_cache

