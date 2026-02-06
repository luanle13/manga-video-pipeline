"""Tests for structured JSON logging configuration."""

import json
import logging
from io import StringIO

import pytest

from src.common.logging_config import (
    REDACTED_VALUE,
    get_correlation_id,
    set_correlation_id,
    setup_logger,
)


@pytest.fixture
def log_capture() -> StringIO:
    """Create a StringIO to capture log output."""
    return StringIO()


@pytest.fixture
def test_logger(log_capture: StringIO) -> logging.Logger:
    """Create a test logger that writes to StringIO."""
    # Create a unique logger name to avoid conflicts
    logger_name = f"test_logger_{id(log_capture)}"
    logger = logging.getLogger(logger_name)

    # Clear any existing handlers
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    # Use the setup_logger to get proper formatting, then redirect output
    configured_logger = setup_logger(logger_name, "DEBUG")

    # Replace the handler's stream with our capture
    for handler in configured_logger.handlers:
        handler.stream = log_capture

    return configured_logger


def parse_log_output(log_capture: StringIO) -> dict:
    """Parse the captured log output as JSON."""
    log_capture.seek(0)
    content = log_capture.read().strip()
    if not content:
        return {}
    # Get the last line if multiple lines
    lines = content.split("\n")
    return json.loads(lines[-1])


class TestLoggerOutputsValidJson:
    """Tests for valid JSON output."""

    def test_basic_log_is_valid_json(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that logger outputs valid JSON."""
        test_logger.info("Test message")
        log_data = parse_log_output(log_capture)

        assert isinstance(log_data, dict)
        assert "message" in log_data
        assert log_data["message"] == "Test message"

    def test_log_contains_required_fields(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that log contains timestamp, level, logger, message fields."""
        test_logger.info("Test message")
        log_data = parse_log_output(log_capture)

        assert "timestamp" in log_data
        assert "level" in log_data
        assert "logger" in log_data
        assert "message" in log_data

    def test_log_level_is_correct(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that log level is correctly set."""
        test_logger.info("Info message")
        log_data = parse_log_output(log_capture)
        assert log_data["level"] == "INFO"

    def test_extra_fields_included(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that extra fields are included in JSON output."""
        test_logger.info("Test message", extra={"user_id": "123", "action": "login"})
        log_data = parse_log_output(log_capture)

        assert log_data["user_id"] == "123"
        assert log_data["action"] == "login"


class TestSensitiveFieldFilter:
    """Tests for sensitive field redaction."""

    def test_api_key_is_redacted(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that api_key field is redacted."""
        test_logger.info("API call", extra={"api_key": "test123"})
        log_data = parse_log_output(log_capture)

        assert log_data["api_key"] == REDACTED_VALUE

    def test_secret_is_redacted(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that secret field is redacted."""
        test_logger.info("Secret operation", extra={"secret": "mysecret"})
        log_data = parse_log_output(log_capture)

        assert log_data["secret"] == REDACTED_VALUE

    def test_password_is_redacted(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that password field is redacted."""
        test_logger.info("Login attempt", extra={"password": "pass123"})
        log_data = parse_log_output(log_capture)

        assert log_data["password"] == REDACTED_VALUE

    def test_token_is_redacted(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that token field is redacted."""
        test_logger.info("Auth check", extra={"access_token": "abc123"})
        log_data = parse_log_output(log_capture)

        assert log_data["access_token"] == REDACTED_VALUE

    def test_case_insensitive_redaction(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that redaction is case-insensitive."""
        test_logger.info("Test", extra={"API_KEY": "test", "Secret_Value": "hidden"})
        log_data = parse_log_output(log_capture)

        assert log_data["API_KEY"] == REDACTED_VALUE
        assert log_data["Secret_Value"] == REDACTED_VALUE

    def test_partial_match_redaction(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that partial matches are redacted."""
        test_logger.info(
            "Test",
            extra={
                "aws_secret_key": "secret",
                "auth_token_value": "token",
                "user_password_hash": "hash",
            },
        )
        log_data = parse_log_output(log_capture)

        assert log_data["aws_secret_key"] == REDACTED_VALUE
        assert log_data["auth_token_value"] == REDACTED_VALUE
        assert log_data["user_password_hash"] == REDACTED_VALUE

    def test_non_sensitive_fields_not_redacted(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that non-sensitive fields are not redacted."""
        test_logger.info(
            "Test", extra={"user_id": "123", "email": "test@example.com", "status": "ok"}
        )
        log_data = parse_log_output(log_capture)

        assert log_data["user_id"] == "123"
        assert log_data["email"] == "test@example.com"
        assert log_data["status"] == "ok"


class TestCorrelationId:
    """Tests for correlation ID functionality."""

    def test_correlation_id_appears_in_output(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that correlation_id appears in log output."""
        set_correlation_id("req-12345")
        try:
            test_logger.info("Request started")
            log_data = parse_log_output(log_capture)

            assert "correlation_id" in log_data
            assert log_data["correlation_id"] == "req-12345"
        finally:
            set_correlation_id(None)

    def test_correlation_id_can_be_changed(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that correlation_id can be changed between requests."""
        set_correlation_id("req-1")
        test_logger.info("First request")
        log_data1 = parse_log_output(log_capture)
        assert log_data1["correlation_id"] == "req-1"

        # Clear and write second log
        log_capture.truncate(0)
        log_capture.seek(0)

        set_correlation_id("req-2")
        test_logger.info("Second request")
        log_data2 = parse_log_output(log_capture)
        assert log_data2["correlation_id"] == "req-2"

        set_correlation_id(None)

    def test_no_correlation_id_when_not_set(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test that correlation_id is not included when not set."""
        set_correlation_id(None)
        test_logger.info("No correlation")
        log_data = parse_log_output(log_capture)

        # correlation_id should either be absent or None
        assert log_data.get("correlation_id") is None

    def test_get_correlation_id(self) -> None:
        """Test get_correlation_id function."""
        set_correlation_id("test-123")
        assert get_correlation_id() == "test-123"
        set_correlation_id(None)
        assert get_correlation_id() is None


class TestLogLevels:
    """Tests for different log levels."""

    def test_debug_level(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test DEBUG level logging."""
        test_logger.debug("Debug message")
        log_data = parse_log_output(log_capture)

        assert log_data["level"] == "DEBUG"
        assert log_data["message"] == "Debug message"

    def test_info_level(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test INFO level logging."""
        test_logger.info("Info message")
        log_data = parse_log_output(log_capture)

        assert log_data["level"] == "INFO"
        assert log_data["message"] == "Info message"

    def test_warning_level(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test WARNING level logging."""
        test_logger.warning("Warning message")
        log_data = parse_log_output(log_capture)

        assert log_data["level"] == "WARNING"
        assert log_data["message"] == "Warning message"

    def test_error_level(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test ERROR level logging."""
        test_logger.error("Error message")
        log_data = parse_log_output(log_capture)

        assert log_data["level"] == "ERROR"
        assert log_data["message"] == "Error message"

    def test_critical_level(
        self, test_logger: logging.Logger, log_capture: StringIO
    ) -> None:
        """Test CRITICAL level logging."""
        test_logger.critical("Critical message")
        log_data = parse_log_output(log_capture)

        assert log_data["level"] == "CRITICAL"
        assert log_data["message"] == "Critical message"


class TestSetupLogger:
    """Tests for setup_logger function."""

    def test_returns_logger_instance(self) -> None:
        """Test that setup_logger returns a Logger instance."""
        logger = setup_logger("test_setup")
        assert isinstance(logger, logging.Logger)

    def test_respects_level_parameter(self) -> None:
        """Test that setup_logger respects the level parameter."""
        logger = setup_logger("test_level", level="WARNING")
        assert logger.level == logging.WARNING

    def test_default_level_is_info(self) -> None:
        """Test that default level is INFO."""
        logger = setup_logger("test_default_level")
        assert logger.level == logging.INFO

    def test_case_insensitive_level(self) -> None:
        """Test that level parameter is case-insensitive."""
        logger = setup_logger("test_case", level="debug")
        assert logger.level == logging.DEBUG

    def test_idempotent_setup(self) -> None:
        """Test that calling setup_logger multiple times doesn't add duplicate handlers."""
        logger_name = "test_idempotent"
        logger1 = setup_logger(logger_name)
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logger(logger_name)
        handler_count2 = len(logger2.handlers)

        assert logger1 is logger2
        assert handler_count1 == handler_count2
