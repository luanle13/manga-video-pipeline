"""Structured JSON logging configuration."""

import logging
import re
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger.json import JsonFormatter

# Context variable for correlation ID (can be set per-request/invocation)
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Pattern to match sensitive field names (case-insensitive)
SENSITIVE_PATTERN = re.compile(r".*(secret|password|token|key).*", re.IGNORECASE)
REDACTED_VALUE = "[REDACTED]"


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get the correlation ID for the current context."""
    return correlation_id_var.get()


class SensitiveFieldFilter(logging.Filter):
    """Filter that redacts sensitive fields from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive fields in the log record."""
        # Check all attributes in the record's __dict__
        for key in list(record.__dict__.keys()):
            if SENSITIVE_PATTERN.match(key):
                setattr(record, key, REDACTED_VALUE)
        return True


class CorrelationIdFilter(logging.Filter):
    """Filter that adds correlation_id to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record."""
        record.correlation_id = get_correlation_id()
        return True


class CustomJsonFormatter(JsonFormatter):
    """Custom JSON formatter with timestamp and standard fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)

        # Ensure standard fields are present with correct names
        log_record["timestamp"] = self.formatTime(record)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["message"] = record.getMessage()

        # Add correlation_id if present
        if hasattr(record, "correlation_id") and record.correlation_id is not None:
            log_record["correlation_id"] = record.correlation_id

        # Redact any sensitive fields in the final log record
        for key in list(log_record.keys()):
            if SENSITIVE_PATTERN.match(key):
                log_record[key] = REDACTED_VALUE


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Set up a logger with JSON formatting.

    Args:
        name: The name of the logger.
        level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        A configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    # Set up JSON formatter
    formatter = CustomJsonFormatter()
    handler.setFormatter(formatter)

    # Add filters
    handler.addFilter(SensitiveFieldFilter())
    handler.addFilter(CorrelationIdFilter())

    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    return logger
