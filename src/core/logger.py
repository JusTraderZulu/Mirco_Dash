"""
Structured logging for TEPM system using loguru.

Provides correlation IDs and JSON logging for production use.
"""

import json
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from .config import settings

# Context variables for correlation IDs
session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
order_id: ContextVar[Optional[str]] = ContextVar('order_id', default=None)
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class CorrelationFilter:
    """Custom filter to add correlation IDs to log records."""

    def __init__(self):
        self.session_id = None
        self.order_id = None
        self.request_id = None

    def __call__(self, record):
        record["extra"]["session_id"] = session_id.get()
        record["extra"]["order_id"] = order_id.get()
        record["extra"]["request_id"] = request_id.get()


def json_formatter(record: Dict[str, Any]) -> str:
    """Format log record as JSON."""
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add extra fields from context
    extra_fields = record.get("extra", {})
    log_entry.update(extra_fields)

    return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure logging with loguru."""

    # Remove default handlers
    logger.remove()

    # Console handler (always present)
    logger.add(
        sys.stdout,
        level=settings.logging.level,
        format=json_formatter if settings.logging.json_format else None,
        filter=CorrelationFilter(),
        colorize=not settings.logging.json_format,
    )

    # File handler (if configured)
    if settings.logging.file_path:
        log_file = settings.logging.file_path.format(
            date=datetime.now().strftime("%Y%m%d")
        )

        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            level=settings.logging.level,
            format=json_formatter if settings.logging.json_format else None,
            filter=CorrelationFilter(),
            rotation="1 day",
            retention="30 days",
            encoding="utf-8",
        )


class LoggerMixin:
    """Mixin to add logging methods to classes."""

    @property
    def logger(self):
        """Get logger for this class."""
        return logger.bind(module=self.__class__.__name__)


# Convenience functions for setting correlation IDs
def set_session_context(session_id_value: str):
    """Set session ID in logging context."""
    session_id.set(session_id_value)


def set_order_context(order_id_value: str):
    """Set order ID in logging context."""
    order_id.set(order_id_value)


def set_request_context(request_id_value: str):
    """Set request ID in logging context."""
    request_id.set(request_id_value)


def clear_context():
    """Clear all correlation IDs from context."""
    session_id.set(None)
    order_id.set(None)
    request_id.set(None)


# Initialize logging
setup_logging()
