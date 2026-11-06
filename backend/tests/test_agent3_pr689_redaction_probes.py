"""Agent 3 independent probes for merged PR689 credential-safe log redaction.

Independent review of #689 (re-submission of closed #688) at main
``66e09c5ee``. Adds only the cases the merged controls do not cover:

1. a record whose ``getMessage()`` raises must not leak the credential to
   EITHER logging output — the normal handler stream AND the standard
   ``handleError`` stderr diagnostic (``logging.raiseExceptions=True``).
   Agent 3 correction per lead review 2026-11-06: the original probe
   watched only the normal handler output; the stderr fallback diagnostic
   was unobserved and DOES carry the original args on current main. This
   test is the executable counterexample: it fails on unpatched main and
   is the valid twin for Agent 2's bounded repair;
2. the percent-encoding boundary: single-encoded sensitive keys are
   redacted; a double-encoded key is truthfully NOT redacted (a framework
   decoding once sees the same non-credential key, so no real credential
   rides on it) — pinned as a declared matching boundary, not proof that a
   value can never contain a credential;
3. semicolon-separated query pairs are redacted like ``&`` pairs.

All tokens are runtime-generated; no credential-shaped literal is committed.
"""
from __future__ import annotations

import contextlib
import io
import logging
import secrets

from core.log_redaction import LogRedactionFilter, redact_log_text

SYNTHETIC_JWT = ".".join(secrets.token_urlsafe(16) for _ in range(3))


def test_malformed_record_does_not_break_the_logging_call_path():
    """A record whose getMessage() raises must not be dropped by the filter,
    must not raise through the logging call path, AND must not let the
    credential escape through either the normal handler output or the
    standard handleError stderr diagnostic."""
    record = logging.LogRecord(
        "uvicorn.error", logging.INFO, __file__, 1,
        "WebSocket %d", ("/ws?token=" + SYNTHETIC_JWT,), None)
    filt = LogRedactionFilter()
    # Never drops a record, even one that cannot be formatted.
    assert filt.filter(record) is True

    logger = logging.getLogger("uvicorn.error")
    old_propagate = logger.propagate
    old_level = logger.level
    output, errors = io.StringIO(), io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    previous = logging.raiseExceptions
    logging.raiseExceptions = True
    try:
        logger.addFilter(filt)
        try:
            with contextlib.redirect_stderr(errors):
                # msg promises %d but the arg is a str: getMessage() raises
                # inside the filter, which swallows it and passes the record
                # through UNCHANGED. Handler.format then fails and
                # handleError writes the ORIGINAL ARGS to stderr — the
                # fallback diagnostic must not carry the credential either.
                logger.info("WebSocket %d", "/ws?token=" + SYNTHETIC_JWT)
        finally:
            logger.removeFilter(filt)
        normal, fallback = output.getvalue(), errors.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.propagate = old_propagate
        logger.setLevel(old_level)
        logging.raiseExceptions = previous
    # The logging call itself completed without raising. The credential
    # must not appear in EITHER output. On unpatched main the stderr
    # assertion FAILS — that is the leak Agent 2's repair must close.
    assert SYNTHETIC_JWT not in normal, (
        "credential reached the normal handler output")
    assert SYNTHETIC_JWT not in fallback, (
        "credential escaped through the handleError stderr diagnostic")


def test_single_encoded_key_redacted_double_encoded_boundary_pinned():
    # Single-encoded sensitive key: redacted.
    single = redact_log_text("/ws?%74oken=" + SYNTHETIC_JWT + "&x=1")
    assert SYNTHETIC_JWT not in single
    assert "%74oken=<redacted>" in single
    assert "x=1" in single
    # Double-encoded key: truthfully NOT redacted. A server decoding the
    # query once sees the key "%74oken", which is not a credential parameter
    # — so no real credential is transported under a double-encoded key and
    # this is a documented encoding boundary, not a bypass.
    double = redact_log_text("/ws?%2574oken=" + SYNTHETIC_JWT + "&x=1")
    assert "%2574oken=" + SYNTHETIC_JWT in double
    assert "x=1" in double


def test_semicolon_separated_sensitive_query_pairs_are_redacted():
    text = (
        "GET /ws?x=1;token=" + SYNTHETIC_JWT
        + ";api_key=" + SYNTHETIC_JWT + " 101")
    out = redact_log_text(text)
    assert SYNTHETIC_JWT not in out
    assert ";token=<redacted>" in out
    assert ";api_key=<redacted>" in out
    assert "x=1" in out
    assert "101" in out
