"""Credential-safe logging: JWTs must never reach WebSocket/access output."""
from __future__ import annotations

import contextlib
import io
import logging
import secrets

from core.log_redaction import LogRedactionFilter, redact_log_text
from core.logging_config import install_log_redaction

# Generated at runtime; no credential-shaped literal is committed.
SYNTHETIC_JWT = ".".join(secrets.token_urlsafe(16) for _ in range(3))


def test_websocket_query_and_repeated_values_are_redacted():
    text = (
        "WebSocket /ws/workspace-1?token=" + SYNTHETIC_JWT
        + "&x=1&access_token=" + SYNTHETIC_JWT
        + "&token=" + SYNTHETIC_JWT + " [accepted]")
    out = redact_log_text(text)
    assert SYNTHETIC_JWT not in out
    assert "WebSocket /ws/workspace-1" in out
    assert "x=1" in out
    assert "[accepted]" in out
    assert out.count("&token=<redacted>") == 1
    assert "?token=<redacted>" in out
    assert "access_token=<redacted>" in out


def test_encoded_sensitive_keys_and_values_are_redacted():
    text = (
        "/ws?%74oken=" + SYNTHETIC_JWT
        + "&access%5Ftoken=" + SYNTHETIC_JWT
        + "&jwt=" + SYNTHETIC_JWT)
    out = redact_log_text(text)
    assert SYNTHETIC_JWT not in out
    assert out.count("<redacted>") == 3


def test_ordinary_queries_and_paths_are_preserved():
    text = "GET /api/agents?category=ops&page=2&token_budget=5 200"
    out = redact_log_text(text)
    assert out == text


def test_bearer_and_structured_assignments_are_redacted():
    text = (
        'Authorization: Bearer ' + SYNTHETIC_JWT
        + ' {"token": "' + SYNTHETIC_JWT
        + '", "status": 401, "path": "/ws"}')
    out = redact_log_text(text)
    assert SYNTHETIC_JWT not in out
    assert "Bearer <redacted>" in out
    assert '"status": 401' in out
    assert '"/ws"' in out


def test_uvicorn_websocket_logger_filter_redacts_preformatted_args():
    logger = logging.getLogger("uvicorn.error")
    old_propagate = logger.propagate
    old_level = logger.level
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        install_log_redaction()
        logger.info(
            "WebSocket %s [accepted]",
            f"/ws?token={SYNTHETIC_JWT}&path=safe")
        logger.info(
            '{"event": "rejected", "token": "%s", "status": 401}',
            SYNTHETIC_JWT)
        output = stream.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.propagate = old_propagate
        logger.setLevel(old_level)

    assert SYNTHETIC_JWT not in output
    assert "WebSocket /ws" in output
    assert "path=safe" in output
    assert "status" in output


def test_filter_replaces_record_message_before_formatting():
    record = logging.LogRecord(
        "uvicorn.error", logging.INFO, __file__, 1,
        "WebSocket %s", (f"/ws?token={SYNTHETIC_JWT}",), None)
    assert LogRedactionFilter().filter(record) is True
    assert SYNTHETIC_JWT not in record.getMessage()
    assert "/ws" in record.getMessage()


def test_setup_logging_accepts_the_main_app_format_keyword():
    import inspect
    from core.logging_config import setup_logging

    assert "format_type" in inspect.signature(setup_logging).parameters


def test_malformed_record_is_frozen_before_handler_diagnostics():
    """A record that cannot be formatted must not reach handleError's stderr."""
    secret = secrets.token_urlsafe(24)
    output, errors = io.StringIO(), io.StringIO()
    logger = logging.Logger("verifier.request", level=logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(output)
    handler.addFilter(LogRedactionFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    previous = logging.raiseExceptions
    logging.raiseExceptions = True
    try:
        with contextlib.redirect_stderr(errors):
            # Both the format string and the argument carry the synthetic
            # credential; %d cannot format a string argument.
            logger.info("WebSocket %d?token=" + secret, secret)
            logger.info("WebSocket %s", f"/ws/reject?token={secret}")
    finally:
        logging.raiseExceptions = previous
        handler.close()

    rendered = output.getvalue()
    assert secret not in rendered
    assert secret not in errors.getvalue()
    assert errors.getvalue() == "", "logging's fallback diagnostic reached stderr"
    assert "unformattable log record" in rendered
    assert "logger='verifier.request'" in rendered
    assert "level=INFO" in rendered
    assert "stage='test_malformed_record_is_frozen_before_handler_diagnostics'" in rendered
    assert "msg_type=str" in rendered
    assert "error=TypeError" in rendered
    # The following well-formed record still flows through normal redaction.
    assert "WebSocket /ws/reject?token=<redacted>" in rendered
    assert "WebSocket /ws/reject?token=" + secret not in rendered


def test_malformed_record_clears_args_and_exception_material():
    secret = secrets.token_urlsafe(24)
    record = logging.LogRecord(
        "uvicorn.error", logging.INFO, __file__, 1,
        "WebSocket %d?token=" + secret, (secret,), None)
    record.exc_info = (TypeError, TypeError("token=" + secret), None)

    assert LogRedactionFilter().filter(record) is True

    assert record.args == ()
    assert record.exc_info is None
    assert record.exc_text is None
    assert secret not in record.getMessage()
    assert "error=TypeError" in record.getMessage()
    assert "msg_type=str" in record.getMessage()


def test_install_log_redaction_freezes_malformed_uvicorn_record():
    """The centralized logger+handler installation covers malformed records."""
    secret = secrets.token_urlsafe(24)
    output, errors = io.StringIO(), io.StringIO()
    logger = logging.getLogger("uvicorn.error")
    old_propagate = logger.propagate
    old_level = logger.level
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    previous = logging.raiseExceptions
    logging.raiseExceptions = True
    try:
        install_log_redaction()
        with contextlib.redirect_stderr(errors):
            logger.info("WebSocket %d", f"/ws?token={secret}")
    finally:
        logging.raiseExceptions = previous
        logger.removeHandler(handler)
        logger.propagate = old_propagate
        logger.setLevel(old_level)
        handler.close()

    assert secret not in output.getvalue()
    assert secret not in errors.getvalue()
    assert errors.getvalue() == ""
    assert "unformattable log record" in output.getvalue()
    assert "logger='uvicorn.error'" in output.getvalue()
