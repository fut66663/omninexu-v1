"""Tests for observability/logger.py — branch coverage for logger with handlers."""

import logging


class TestGetLogger:
    def test_get_logger_returns_logger(self):
        """get_logger() returns a standard Python Logger instance."""
        from omninexu.observability.logger import get_logger

        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_adds_handler_when_none_present(self):
        """First call adds a StreamHandler with custom JSON formatter.

        Branch coverage for logger.py:27→28 — ``not logger.handlers`` is True.
        """

        # Force a fresh logger with no handlers
        logger = logging.getLogger("test_fresh_logger_with_no_handlers")
        # Clean any pre-existing handlers
        logger.handlers.clear()

        # We test the internal logic: when handlers is empty, a handler is added
        from omninexu.observability.logger import get_logger

        result = get_logger("test_fresh_logger_with_no_handlers")
        assert len(result.handlers) >= 1

    def test_get_logger_skips_when_handlers_already_present(self):
        """Second call should not add duplicate handlers.

        Branch coverage for logger.py:27→37 — ``not logger.handlers`` is False
        (logger already has a handler attached).
        """
        from omninexu.observability.logger import get_logger

        name = "test_already_has_handler"
        first = get_logger(name)
        handler_count_before = len(first.handlers)

        # Call again — should NOT add more handlers
        second = get_logger(name)
        handler_count_after = len(second.handlers)

        assert handler_count_after == handler_count_before

    def test_get_logger_sets_info_level(self):
        """get_logger() sets the logger level to INFO."""
        from omninexu.observability.logger import get_logger

        name = "test_info_level_logger"
        logger = get_logger(name)
        assert logger.level == logging.INFO
