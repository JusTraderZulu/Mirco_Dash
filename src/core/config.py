"""
Configuration management for TEPM (Trade Execution & Portfolio Management) System.

Loads settings from YAML config file and environment variables using Pydantic.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


# Load environment variables from .env file
load_dotenv()


class ClockConfig(BaseModel):
    """Clock synchronization configuration."""
    timezone: str = "America/New_York"
    ntp_servers: List[str] = ["time.google.com", "pool.ntp.org"]
    max_clock_skew_ms: int = 30


class PolygonConfig(BaseModel):
    """Polygon.io WebSocket configuration."""
    ws_url: str = "wss://socket.polygon.io/crypto"
    api_key: str = Field(..., env="POLYGON_API_KEY")
    channels: List[str] = ["l2", "trades", "quotes"]
    symbols: List[str] = ["X:BTC-USD"]
    snapshot_interval_sec: int = 60


class DataFeedConfig(BaseModel):
    """Data feed configuration."""
    source: str = "polygon"
    polygon: PolygonConfig = Field(default_factory=PolygonConfig)


class ExecutionRoute(BaseModel):
    """Execution routing configuration per symbol."""
    routes: Dict[str, str] = {"BTC-USD": "coinbase_live"}


class RiskPerSymbol(BaseModel):
    """Risk configuration per symbol."""
    max_leverage: float = 1.0
    max_qty: float = 0.05


class RiskConfig(BaseModel):
    """Risk management configuration."""
    max_daily_loss_pct: float = 3.0
    max_position_pct: float = 25.0
    max_open_positions: int = 3
    slippage_bps_limit: int = 10
    cooldown_min: int = 15
    per_symbol: Dict[str, RiskPerSymbol] = {"BTC-USD": RiskPerSymbol()}


class SizingConfig(BaseModel):
    """Position sizing configuration."""
    method: str = "fixed_fractional"
    fraction_of_equity: float = 0.02
    atr_lookback: int = 14


class SignalsCadenceConfig(BaseModel):
    """Signal generation cadence configuration."""
    full_window_sec: int = 300
    light_window_sec: int = 60


class SignalsThresholdsConfig(BaseModel):
    """Signal thresholds configuration."""
    bias_confidence_min: float = 0.6


class SignalsConfig(BaseModel):
    """Signal generation configuration."""
    cadence: SignalsCadenceConfig = Field(default_factory=SignalsCadenceConfig)
    features: List[str] = ["ofi", "spread_change", "ap_ratio", "qv"]
    thresholds: SignalsThresholdsConfig = Field(default_factory=SignalsThresholdsConfig)


class MonteCarloConfig(BaseModel):
    """Monte Carlo simulation configuration."""
    horizon_sec: int = 300
    paths: int = 1000
    model: str = "gbm"
    vol_estimator: str = "ewma"


class PortfolioConfig(BaseModel):
    """Portfolio management configuration."""
    rebalance_cadence_sec: int = 60
    take_profit_atr_mult: float = 2.0
    stop_atr_mult: float = 1.2
    scale_out_levels: List[float] = [0.5, 1.0, 1.5]


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    json_format: bool = True
    file_path: str = "logs/session_{date}.jsonl"


class StorageConfig(BaseModel):
    """Storage configuration."""
    sqlite_path: str = "./data/tepm.sqlite"
    object_path: str = "./data/snapshots"


class FeatureFlagsConfig(BaseModel):
    """Feature flags configuration."""
    manual_approval_required: bool = False
    l3_support: bool = False


class ExecutionConfig(BaseModel):
    """Execution configuration."""
    default_broker: str = "alpaca"
    dry_run: bool = True
    tif: str = "IOC"
    order_type_preference: str = "limit_then_market"
    idempotency_key_ttl_sec: int = 3600
    routes: Dict[str, str] = {"BTC-USD": "coinbase_live"}


class Settings(BaseSettings):
    """Main application settings."""

    env: str = "paper"
    clock: ClockConfig = Field(default_factory=ClockConfig)
    data_feed: DataFeedConfig = Field(default_factory=DataFeedConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    sizing: SizingConfig = Field(default_factory=SizingConfig)
    signals: SignalsConfig = Field(default_factory=SignalsConfig)
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)
    portfolio: PortfolioConfig = Field(default_factory=PortfolioConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    feature_flags: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)

    @classmethod
    def from_yaml(cls, config_path: Union[str, Path] = "config/settings.yaml") -> "Settings":
        """Load settings from YAML file and merge with environment variables."""
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)

        # Create settings from YAML + env vars
        return cls(**yaml_config)

    @validator('env')
    def validate_env(cls, v):
        """Validate environment setting."""
        if v not in ["dev", "paper", "live"]:
            raise ValueError(f"env must be one of: dev, paper, live. Got: {v}")
        return v

    @validator('execution')
    def validate_execution_config(cls, v):
        """Validate execution configuration."""
        valid_brokers = ["alpaca", "coinbase"]
        if v.default_broker not in valid_brokers:
            raise ValueError(f"default_broker must be one of: {valid_brokers}")

        valid_routes = ["alpaca_live", "alpaca_paper", "coinbase_live"]
        for symbol, route in v.routes.items():
            if route not in valid_routes:
                raise ValueError(f"Invalid route '{route}' for {symbol}. Must be one of: {valid_routes}")

        return v


# Global settings instance
settings = Settings.from_yaml()
