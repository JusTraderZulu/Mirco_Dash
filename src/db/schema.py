"""
Database schema definitions for TEPM system using SQLAlchemy.

Defines tables for sessions, signals, orders, fills, positions, incidents, and metrics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..core.config import settings
from ..core.logger import logger

Base = declarative_base()


class Session(Base):
    """Trading session table."""
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    env = Column(String, nullable=False)  # dev, paper, live
    symbols = Column(Text, nullable=False)  # JSON array as string
    config_hash = Column(String, nullable=False)
    status = Column(String, default="active")


class TickL2(Base):
    """Level 2 tick data table (optional for Phase 1)."""
    __tablename__ = "ticks_l2"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # bid, ask
    price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    level = Column(Integer, nullable=False)


class BookSnapshot(Base):
    """Order book snapshot table."""
    __tablename__ = "book_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    depth = Column(Integer, nullable=False)
    payload_ptr = Column(String, nullable=False)  # Path to parquet file


class Signal(Base):
    """Trading signal table."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    bias = Column(String, nullable=False)  # long, short, neutral
    confidence = Column(Float, nullable=False)
    risk_regime = Column(String, nullable=False)  # low_vol, medium_vol, high_vol
    features_json = Column(Text, nullable=False)  # JSON string
    mc_json = Column(Text, nullable=False)  # JSON string
    rec_entry = Column(Float, nullable=True)
    rec_tp = Column(Float, nullable=True)
    rec_sl = Column(Float, nullable=True)


class Order(Base):
    """Order table."""
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # buy, sell
    order_type = Column(String, nullable=False)  # market, limit, stop_limit
    tif = Column(String, nullable=False)  # IOC, FOK, GTC
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    status = Column(String, nullable=False)  # pending, open, filled, etc.
    idempotency_key = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Fill(Base):
    """Fill table."""
    __tablename__ = "fills"

    fill_id = Column(String, primary_key=True)
    order_id = Column(String, nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    liquidity = Column(String, nullable=False)  # maker, taker


class Position(Base):
    """Position table."""
    __tablename__ = "positions"

    pos_id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    avg_px = Column(Float, nullable=False)
    unreal_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    state = Column(String, nullable=False)  # flat, entering, open, etc.
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)


class Incident(Base):
    """Incident table."""
    __tablename__ = "incidents"

    incident_id = Column(String, primary_key=True)
    ts = Column(DateTime, nullable=False, index=True)
    component = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    message = Column(Text, nullable=False)
    extra_json = Column(Text, nullable=True)  # JSON string


class Metric(Base):
    """Metrics table for observability."""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    value = Column(Float, nullable=False)
    labels_json = Column(Text, nullable=True)  # JSON string


class DatabaseManager:
    """Database manager for TEPM system."""

    def __init__(self):
        self.engine = create_engine(
            f"sqlite:///{settings.storage.sqlite_path}",
            echo=False,
            connect_args={"check_same_thread": False}  # Allow multiple threads
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self):
        """Initialize database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get the singleton database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def init_db():
    """Initialize the database."""
    get_db_manager().init_db()


def get_session():
    """Get a database session."""
    return get_db_manager().get_session()
