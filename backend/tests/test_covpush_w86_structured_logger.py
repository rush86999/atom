# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/structured_logger (fields, redaction, context, handlers).

StructuredLogger tested with a capturing handler (no real console/file I/O
beyond setup coverage):

- __init__: env-driven default level, explicit level, invalid env level →
  INFO, handler auto-setup, no duplicate handlers.
- _setup_handlers: console handler present; LOG_FILE env → file handler.
- _log / level methods: request_id injection via contextvar, timestamp +
  logger fields, debug/info/warning/error/critical, exception() inside and
  outside an except block.
- StructuredFormatter: JSON output with structured context, exc_info records,
  and the fallback when JSON serialization fails.
- set_request_id/clear_request_id/get_logger and module-level log_* helpers.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import core.structured_logger as sl


class _CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture()
def fresh_logger_name():
    return "w86.structured_logger.test"


@pytest.fixture()
def capturing(fresh_logger_name, monkeypatch):
    """A StructuredLogger isolated to a unique name with a capture handler."""
    monkeypatch.delenv("LOG_FILE", raising=False)
    logger = sl.StructuredLogger(fresh_logger_name, level=logging.DEBUG)
    handler = _CapturingHandler()
    logger.logger.addHandler(handler)
    logger.logger.propagate = False
    yield logger, handler
    logger.logger.removeHandler(handler)
    logger.logger.propagate = True


# ---------------------------------------------------------------------------
# __init__ / level resolution
# ---------------------------------------------------------------------------

def test_level_from_env(monkeypatch, fresh_logger_name):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    logger = sl.StructuredLogger(fresh_logger_name)
    assert logger.logger.level == logging.WARNING
    logger.logger.handlers.clear()


def test_level_from_env_invalid_falls_back_to_info(monkeypatch, fresh_logger_name):
    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")
    logger = sl.StructuredLogger(fresh_logger_name)
    assert logger.logger.level == logging.INFO
    logger.logger.handlers.clear()


def test_explicit_level_wins(monkeypatch, fresh_logger_name):
    monkeypatch.setenv("LOG_LEVEL", "CRITICAL")
    logger = sl.StructuredLogger(fresh_logger_name, level=logging.DEBUG)
    assert logger.logger.level == logging.DEBUG
    logger.logger.handlers.clear()


def test_no_duplicate_handlers(fresh_logger_name):
    logger = sl.StructuredLogger(fresh_logger_name, level=logging.DEBUG)
    first_count = len(logger.logger.handlers)
    logger2 = sl.StructuredLogger(fresh_logger_name, level=logging.DEBUG)
    assert len(logger2.logger.handlers) == first_count
    logger2.logger.handlers.clear()


def test_setup_handlers_with_log_file(fresh_logger_name, tmp_path, monkeypatch):
    log_file = tmp_path / "atom_test.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logger = sl.StructuredLogger(fresh_logger_name)
    names = [type(h).__name__ for h in logger.logger.handlers]
    assert "StreamHandler" in names
    assert "FileHandler" in names
    logger.info("file log test")
    logger.logger.handlers.clear()
    assert "file log test" in log_file.read_text()


def test_console_handler_uses_stdout(fresh_logger_name, monkeypatch):
    monkeypatch.delenv("LOG_FILE", raising=False)
    logger = sl.StructuredLogger(fresh_logger_name, level=logging.DEBUG)
    console = [h for h in logger.logger.handlers if isinstance(h, logging.StreamHandler)]
    assert any(h.stream is sys.stdout for h in console)
    logger.logger.handlers.clear()


# ---------------------------------------------------------------------------
# _log and level methods
# ---------------------------------------------------------------------------

def test_log_includes_request_id_timestamp_and_logger(capturing):
    logger, handler = capturing
    sl.set_request_id("req-abc")
    try:
        logger.info("hello", user_id="u1")
    finally:
        sl.clear_request_id()
    record = handler.records[-1]
    ctx = record.structured_context
    assert ctx["request_id"] == "req-abc"
    assert ctx["user_id"] == "u1"
    assert ctx["logger"] == logger.logger.name
    assert "timestamp" in ctx
    datetime.fromisoformat(ctx["timestamp"])  # valid ISO timestamp


def test_log_preserves_explicit_timestamp(capturing):
    logger, handler = capturing
    ts = "2026-01-01T00:00:00+00:00"
    logger.info("msg", timestamp=ts)
    assert handler.records[-1].structured_context["timestamp"] == ts


def test_log_no_request_id(capturing):
    logger, handler = capturing
    sl.clear_request_id()
    logger.info("plain")
    assert "request_id" not in handler.records[-1].structured_context


def test_all_level_methods(capturing):
    logger, handler = capturing
    logger.debug("d", k=1)
    logger.info("i", k=2)
    logger.warning("w", k=3)
    logger.error("e", k=4)
    logger.critical("c", k=5)
    levels = [(r.levelno, r.getMessage(), r.structured_context["k"])
              for r in handler.records]
    assert levels == [
        (logging.DEBUG, "d", 1),
        (logging.INFO, "i", 2),
        (logging.WARNING, "w", 3),
        (logging.ERROR, "e", 4),
        (logging.CRITICAL, "c", 5),
    ]


def test_exception_inside_except_block(capturing):
    logger, handler = capturing
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed op", op="x")
    record = handler.records[-1]
    assert record.levelno == logging.ERROR
    ctx = record.structured_context
    assert ctx["exception_type"] == "ValueError"
    assert ctx["exception_message"] == "boom"
    assert "Traceback" in ctx["exception_traceback"]


def test_exception_outside_except_block(capturing):
    logger, handler = capturing
    logger.exception("no active exception")
    record = handler.records[-1]
    assert "exception_type" not in record.structured_context


# ---------------------------------------------------------------------------
# StructuredFormatter
# ---------------------------------------------------------------------------

def test_formatter_outputs_json_with_context(capturing):
    logger, handler = capturing
    formatter = sl.StructuredFormatter()
    logger.info("json msg", foo="bar", num=5)
    out = formatter.format(handler.records[-1])
    entry = json.loads(out)
    assert entry["level"] == "INFO"
    assert entry["message"] == "json msg"
    assert entry["logger"] == logger.logger.name
    assert entry["module"] == "structured_logger"
    assert entry["foo"] == "bar"
    assert entry["num"] == 5
    assert "timestamp" in entry
    assert "line" in entry


def test_formatter_with_exc_info(capturing):
    logger, handler = capturing
    formatter = sl.StructuredFormatter()
    try:
        raise KeyError("k")
    except KeyError:
        logger.logger.error("err", exc_info=True)  # raw logger carries exc_info
    record = handler.records[-1]
    out = formatter.format(record)
    entry = json.loads(out)
    assert entry["exception"]["type"] == "KeyError"
    assert entry["exception"]["message"] == "'k'"
    assert "Traceback" in entry["exception"]["traceback"]


def test_formatter_fallback_on_json_failure(capturing, monkeypatch):
    logger, handler = capturing
    formatter = sl.StructuredFormatter()

    def _boom(*a, **k):
        raise TypeError("not serializable")

    monkeypatch.setattr("json.dumps", _boom)
    logger.info("msg")
    out = formatter.format(handler.records[-1])
    assert out == "INFO - msg"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def test_get_logger_and_convenience_functions(capturing, monkeypatch):
    logger = sl.get_logger("w86.helper")
    assert isinstance(logger, sl.StructuredLogger)
    logger.logger.handlers.clear()

    # Module-level helpers route into a structured logger (capture via patch)
    with patch("core.structured_logger.StructuredLogger") as fake_cls:
        instance = fake_cls.return_value
        sl.log_debug("d", a=1)
        sl.log_info("i", a=2)
        sl.log_warning("w", a=3)
        sl.log_error("e", a=4)
        sl.log_critical("c", a=5)
        sl.log_exception("x", a=6)
        assert fake_cls.call_count == 6
        assert instance.debug.call_count == 1
        assert instance.info.call_count == 1
        assert instance.warning.call_count == 1
        assert instance.error.call_count == 1
        assert instance.critical.call_count == 1
        assert instance.exception.call_count == 1


def test_request_id_context_helpers(capturing):
    assert sl.request_id_ctx.get() is None
    sl.set_request_id("req-1")
    assert sl.request_id_ctx.get() == "req-1"
    sl.clear_request_id()
    assert sl.request_id_ctx.get() is None
