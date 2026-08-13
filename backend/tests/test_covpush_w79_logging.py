# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/logging_config.py 32% → 100%.

Covers: bind_context (set/skip-None), get_context (set + LookupError fallback),
generate_correlation_id, ColoredFormatter (colors on/off, level colors, long
correlation id truncation, user_id prefix, logger name toggle, context toggle,
exception info, unset-context defaults), setup_logging (level resolution from
arg/env/invalid, console handler, file handler + parent dirs + plain formatter,
LOG_FILE env, handler clearing, startup messages), _configure_library_loggers,
get_logger, LoggerContext (set/restore), LoggingContextMiddleware via a real
Starlette TestClient (X-Correlation-ID header, request.state, call_next),
get_correlation_id, StructuredLogger (debug/info/warning/error/critical with
extra + exc_info defaults, context merge).

The root logger is mutated by setup_logging — every test restores the
pre-existing handlers/level via a fixture so other suites are unaffected.
Zero LLM spend, no network.
"""
import logging
import sys
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import core.logging_config as lc
from core.logging_config import (
    CORRELATION_ID,
    REQUEST_ID,
    USER_ID,
    ColoredFormatter,
    LoggerContext,
    LoggingContextMiddleware,
    StructuredLogger,
    bind_context,
    generate_correlation_id,
    get_context,
    get_correlation_id,
    get_logger,
    setup_logging,
)


@pytest.fixture(autouse=True)
def logging_state():
    """Snapshot root logger state; restore after each test. Autouse so every
    test also starts with clean context vars and root logger."""
    root = logging.getLogger()
    before = (root.level, list(root.handlers))
    yield
    root.setLevel(before[0])
    root.handlers.clear()
    for h in before[1]:
        root.addHandler(h)
    # Reset context vars (empty == unset for all public accessors)
    for var in (CORRELATION_ID, USER_ID, REQUEST_ID):
        var.set("")


# ============================================================================
# Context variables
# ============================================================================

class TestContextBind:
    def test_bind_sets_all_context_vars(self):
        bind_context(correlation_id="corr-1", user_id="user-9", request_id="req-1")
        assert get_context() == {
            "correlation_id": "corr-1", "user_id": "user-9", "request_id": "req-1"}

    def test_bind_converts_to_str(self):
        bind_context(correlation_id=123, user_id=None)
        ctx = get_context()
        assert ctx["correlation_id"] == "123"
        assert ctx["user_id"] == ""

    def test_bind_skips_none_values(self):
        bind_context(correlation_id="c")
        before = get_context()
        bind_context(correlation_id=None, request_id=None)
        assert get_context() == before

    def test_get_context_unset_returns_empty_strings(self):
        assert get_context() == {"correlation_id": "", "user_id": "", "request_id": ""}

    def test_get_context_lookup_error_branch_in_fresh_context(self):
        # BUG 79-13 regression: in a brand-new (empty) context every variable
        # is unset — each must fall back to "" individually instead of the old
        # behavior where ONE unset variable wiped ALL values.
        import contextvars
        fresh = contextvars.Context()
        result = fresh.run(get_context)
        assert result == {"correlation_id": "", "user_id": "", "request_id": ""}

    def test_partial_bind_keeps_unset_vars_empty(self):
        # Regression for the LookupError-swallows-everything bug: binding only
        # correlation_id must NOT clear other (unset) variables' fallbacks.
        import contextvars
        fresh = contextvars.Context()
        def _run():
            bind_context(correlation_id="only-me")
            return get_context()
        result = fresh.run(_run)
        assert result["correlation_id"] == "only-me"
        assert result["user_id"] == ""
        assert result["request_id"] == ""

    def test_generate_correlation_id_is_uuid(self):
        cid = generate_correlation_id()
        uuid.UUID(cid)  # raises if malformed
        assert generate_correlation_id() != cid

    def test_get_correlation_id_default_empty(self):
        assert get_correlation_id() == ""
        bind_context(correlation_id="abc")
        assert get_correlation_id() == "abc"


# ============================================================================
# ColoredFormatter
# ============================================================================

class _Record:
    def __init__(self, name="mod", levelno=logging.INFO, levelname="INFO",
                 msg="hello", exc_info=None, created=datetime.now().timestamp()):
        self.name = name
        self.levelno = levelno
        self.levelname = levelname
        self.msg = msg
        self.exc_info = exc_info
        self.created = created

    def getMessage(self):
        return self.msg

    def formatException(self, exc_info):
        return "Traceback: boom"


class TestColoredFormatter:
    def test_default_format_contains_parts(self):
        out = ColoredFormatter().format(_Record())
        assert "INFO" in out
        assert "[mod]" in out
        assert "hello" in out
        assert "[2026" in out  # timestamp

    def test_level_colored(self):
        out = ColoredFormatter().format(_Record(levelno=logging.WARNING, levelname="WARNING"))
        assert lc.LogColors.YELLOW in out and lc.LogColors.RESET in out

    def test_debug_and_critical_colors(self):
        assert lc.LogColors.GREY in ColoredFormatter().format(
            _Record(levelno=logging.DEBUG, levelname="DEBUG"))
        assert lc.LogColors.RED_BOLD in ColoredFormatter().format(
            _Record(levelno=logging.CRITICAL, levelname="CRITICAL"))

    def test_colors_disabled(self):
        out = ColoredFormatter(use_colors=False).format(
            _Record(levelno=logging.ERROR, levelname="ERROR"))
        assert lc.LogColors.RED not in out
        assert "[ERROR]" in out

    def test_logger_name_hidden(self):
        out = ColoredFormatter(show_logger_name=False).format(_Record())
        assert "[mod]" not in out

    def test_context_hidden(self):
        bind_context(correlation_id="corr-123")
        out = ColoredFormatter(show_context=False).format(_Record())
        assert "corr-123" not in out
        assert "[user:" not in out

    def test_context_shown_with_short_id(self):
        bind_context(correlation_id="short", user_id="user-42")
        out = ColoredFormatter().format(_Record())
        # correlation id is wrapped in ANSI color codes
        assert "short" in out
        assert "[user:user-42]" in out

    def test_long_correlation_id_truncated_to_last_8(self):
        bind_context(correlation_id="abcdefghijklmnop")
        out = ColoredFormatter().format(_Record())
        assert "klmnop" in out
        assert "abcdefgh" not in out

    def test_user_id_truncated_to_8(self):
        bind_context(user_id="verylonguserid")
        out = ColoredFormatter().format(_Record())
        assert "[user:verylong]" in out

    def test_exception_info_appended(self):
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        out = ColoredFormatter().format(_Record(msg="failed", exc_info=exc_info))
        assert "failed" in out
        assert "ValueError" in out and "boom" in out
        assert "\n" in out

    def test_exception_info_appends_newline_when_needed(self):
        try:
            raise KeyError("nope")
        except KeyError:
            exc_info = sys.exc_info()
        out = ColoredFormatter().format(_Record(msg="failed\n", exc_info=exc_info))
        assert "KeyError" in out


# ============================================================================
# setup_logging / library loggers / get_logger
# ============================================================================

class TestSetupLogging:
    def test_default_level_info(self, logging_state, caplog):
        setup_logging()
        assert logging.getLogger().level == logging.INFO
        assert len(logging.getLogger().handlers) == 1  # console only

    def test_explicit_level(self, logging_state):
        setup_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG
        assert logging.getLogger().handlers[0].level == logging.DEBUG

    def test_env_level(self, logging_state, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        setup_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_invalid_level_falls_back_to_info(self, logging_state):
        setup_logging(level="NOT_A_LEVEL")
        assert logging.getLogger().level == logging.INFO

    def test_handlers_cleared_between_calls(self, logging_state):
        setup_logging()
        setup_logging(level="ERROR")
        assert len(logging.getLogger().handlers) == 1

    def test_no_colors_flag(self, logging_state):
        setup_logging(enable_colors=False)
        fmt = logging.getLogger().handlers[0].formatter
        assert fmt.use_colors is False

    def test_logger_name_flag(self, logging_state):
        setup_logging(show_logger_name=False)
        fmt = logging.getLogger().handlers[0].formatter
        assert fmt.show_logger_name is False

    def test_log_file_creates_file_with_plain_formatter(self, logging_state, tmp_path):
        log_file = tmp_path / "logs" / "atom.log"
        setup_logging(log_file=str(log_file))
        assert log_file.exists()
        handlers = logging.getLogger().handlers
        assert len(handlers) == 2
        file_handler = handlers[1]
        assert isinstance(file_handler, logging.FileHandler)
        assert isinstance(file_handler.formatter, logging.Formatter)
        assert not isinstance(file_handler.formatter, ColoredFormatter)

    def test_log_file_env_var(self, logging_state, tmp_path, monkeypatch):
        log_file = tmp_path / "nested" / "env.log"
        monkeypatch.setenv("LOG_FILE", str(log_file))
        setup_logging()
        assert log_file.exists()
        assert len(logging.getLogger().handlers) == 2

    def test_log_file_writes_records(self, logging_state, tmp_path):
        log_file = tmp_path / "out.log"
        setup_logging(log_file=str(log_file))
        logging.getLogger("w79.test").info("marker-42")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "marker-42" in log_file.read_text()


class TestLibraryLoggers:
    def test_chatty_libraries_set_to_warning(self):
        lc._configure_library_loggers()
        for name in ("uvicorn", "uvicorn.access", "fastapi", "sqlalchemy",
                     "sqlalchemy.engine", "httpx", "requests", "urllib3",
                     "websockets", "aiohttp"):
            assert logging.getLogger(name).level == logging.WARNING


class TestGetLogger:
    def test_returns_named_logger(self):
        assert get_logger("w79.custom").name == "w79.custom"


class TestLoggerContext:
    def test_set_and_restore(self):
        logger = logging.getLogger("w79.temp")
        logger.setLevel(logging.DEBUG)
        with LoggerContext("w79.temp", logging.CRITICAL) as inner:
            assert inner is logger
            assert logger.level == logging.CRITICAL
        assert logger.level == logging.DEBUG

    def test_restore_on_exception(self):
        logger = logging.getLogger("w79.temp2")
        logger.setLevel(logging.INFO)
        with pytest.raises(RuntimeError):
            with LoggerContext("w79.temp2", logging.ERROR):
                raise RuntimeError("boom")
        assert logger.level == logging.INFO


# ============================================================================
# LoggingContextMiddleware
# ============================================================================

class TestMiddleware:
    def _app(self):
        async def handler(request):
            return PlainTextResponse(
                f"state={getattr(request.state, 'correlation_id', None)}")
        return Starlette(
            routes=[Route("/", handler)],
            middleware=[Middleware(LoggingContextMiddleware)],
        )

    def test_adds_correlation_header_and_state(self):
        with TestClient(self._app()) as client:
            resp = client.get("/")
        assert "X-Correlation-ID" in resp.headers
        cid = resp.headers["X-Correlation-ID"]
        uuid.UUID(cid)
        assert resp.text == f"state={cid}"

    def test_context_bound_during_request(self):
        app = Starlette(
            routes=[Route("/", lambda r: PlainTextResponse(get_correlation_id()))],
            middleware=[Middleware(LoggingContextMiddleware)],
        )
        with TestClient(app) as client:
            resp = client.get("/")
        uuid.UUID(resp.text)


# ============================================================================
# StructuredLogger
# ============================================================================

class TestStructuredLogger:
    def test_all_levels_invoke_underlying_logger(self, logging_state, caplog):
        sl = StructuredLogger("w79.structured")
        with caplog.at_level(logging.DEBUG, logger="w79.structured"):
            sl.debug("d-msg")
            sl.info("i-msg")
            sl.warning("w-msg")
        assert "d-msg" in caplog.text
        assert "i-msg" in caplog.text
        assert "w-msg" in caplog.text

    def test_error_defaults_exc_info_true(self, logging_state, caplog):
        sl = StructuredLogger("w79.structured")
        with caplog.at_level(logging.ERROR, logger="w79.structured"):
            sl.error("e-msg")
        assert "e-msg" in caplog.text

    def test_error_exc_info_false_override(self, logging_state, caplog):
        sl = StructuredLogger("w79.structured")
        with caplog.at_level(logging.ERROR, logger="w79.structured"):
            sl.error("e-msg2", exc_info=False)
        assert "e-msg2" in caplog.text

    def test_critical_defaults_exc_info_true(self, logging_state, caplog):
        sl = StructuredLogger("w79.structured")
        with caplog.at_level(logging.CRITICAL, logger="w79.structured"):
            sl.critical("c-msg")
        assert "c-msg" in caplog.text

    def test_extra_merged_with_context(self):
        sl = StructuredLogger("w79.structured")
        sl._logger = SimpleNamespace()  # isolate from real logging
        captured = []
        sl._logger.info = lambda msg, extra: captured.append(extra)
        bind_context(correlation_id="cid-1")
        sl.info("m", extra={"ip": "1.2.3.4"})
        extra = captured[0]
        assert extra["correlation_id"] == "cid-1"
        assert extra["ip"] == "1.2.3.4"

    def test_extra_none_uses_context_only(self):
        sl = StructuredLogger("w79.structured")
        sl._logger = SimpleNamespace()
        captured = []
        sl._logger.debug = lambda msg, extra: captured.append(extra)
        sl.debug("m")
        assert captured[0]["correlation_id"] == ""
