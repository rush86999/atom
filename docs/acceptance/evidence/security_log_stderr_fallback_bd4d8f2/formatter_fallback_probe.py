"""Formatter-fallback disclosure probe: prints only booleans/constants.

The synthetic credential is generated at runtime and never printed. A malformed
``%d`` record carries the credential in both its format string and its argument;
the probe reports whether it escapes through the normal handler stream or
through logging's fallback stderr diagnostic. Two well-formed records then
confirm ordinary WebSocket path/status redaction remains intact.
"""
from __future__ import annotations

import contextlib
import io
import logging
import secrets

from core.log_redaction import LogRedactionFilter


def main() -> int:
    secret = secrets.token_urlsafe(24)
    normal, errors = io.StringIO(), io.StringIO()
    logger = logging.Logger("verifier.request", level=logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(normal)
    handler.addFilter(LogRedactionFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    previous = logging.raiseExceptions
    logging.raiseExceptions = True
    try:
        with contextlib.redirect_stderr(errors):
            logger.info("WebSocket %d?token=" + secret, secret)
            logger.info("WebSocket %s [accepted]", "/ws?token=" + secret)
            logger.info("WebSocket %s 403", "/ws/reject?token=" + secret)
    finally:
        logging.raiseExceptions = previous
        handler.close()

    rendered = normal.getvalue()
    diagnostic = errors.getvalue()
    print("normal_stream_contains_secret", secret in rendered)
    print("fallback_stderr_contains_secret", secret in diagnostic)
    print("fallback_diagnostic_bytes", len(diagnostic))
    print("safe_fallback_line_present", "unformattable log record" in rendered)
    print("redacted_marker_count", rendered.count("<redacted>"))
    print("accepted_twin_present", "WebSocket /ws?token=<redacted> [accepted]" in rendered)
    print("rejected_twin_present", "WebSocket /ws/reject?token=<redacted> 403" in rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
