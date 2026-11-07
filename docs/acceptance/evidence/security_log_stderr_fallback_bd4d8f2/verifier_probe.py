"""Synthetic-only formatter failure twin; never emits the secret to test output."""
import contextlib
import io
import logging
import secrets
import pytest
from core.log_redaction import LogRedactionFilter

@pytest.mark.parametrize('malformed', [False, True])
def test_secret_does_not_escape_either_logging_output(malformed):
    secret = secrets.token_urlsafe(24)
    output, errors = io.StringIO(), io.StringIO()
    logger = logging.Logger('verifier.request', level=logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(output)
    handler.addFilter(LogRedactionFilter())
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    previous = logging.raiseExceptions
    logging.raiseExceptions = True
    try:
        with contextlib.redirect_stderr(errors):
            logger.info('WebSocket %d' if malformed else 'WebSocket %s',
                        '/ws?token=' + secret)
    finally:
        logging.raiseExceptions = previous
        handler.close()
    escaped = secret in output.getvalue() or secret in errors.getvalue()
    assert not escaped, 'synthetic secret escaped through a logging output'
    if not malformed:
        assert '/ws?token=<redacted>' in output.getvalue()
