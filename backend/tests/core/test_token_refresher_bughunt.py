# -*- coding: utf-8 -*-
"""Bug-hunt tests for core/token_refresher.py (OAuth token refresh, security).

Net-new bugs found via TDD (red -> green). See each ``BUG:`` docstring.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.token_refresher import TokenRefresher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _naive_future(seconds=3600):
    """A naive UTC datetime in the future — exactly what the four built-in
    refresh handlers (refresh_google_token / refresh_microsoft_token /
    refresh_salesforce_token / refresh_whatsapp_token) store in
    ``expires_at`` (they all do ``datetime.now() + timedelta(...)``)."""
    return datetime.utcnow() + timedelta(seconds=seconds)


def _aware_future(seconds=3600):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def _handler_returning_naive_expires_at(_metadata):
    """Mirrors refresh_google_token et al.: returns a NAIVE expires_at."""
    return {
        "expires_at": _naive_future(3600),
        "refresh_token": "rotated-rt",
        "access_token": "rotated-at",
    }


# ---------------------------------------------------------------------------
# BUG 1: tz-naive expires_at (from the built-in handlers) crashes
#        should_refresh() and get_status() with TypeError.
# ---------------------------------------------------------------------------

class TestNaiveExpiresAtCrashesRefreshCheck:
    """BUG: should_refresh() compares tz-aware ``datetime.now(timezone.utc)``
    against ``expires_at``, but every built-in refresh handler stores a NAIVE
    ``datetime.now()`` in ``expires_at``. After the first refresh (or if a
    service is registered with a naive expires_at), the next
    ``should_refresh`` / ``get_status`` / ``check_and_refresh_all`` raises
    ``TypeError: can't compare offset-naive and offset-aware datetimes`` —
    silently killing automatic refresh for that service forever.

    Root cause: inconsistency between should_refresh (tz-aware) and the
    handlers it feeds (tz-naive). Fix: normalize expires_at to tz-aware UTC
    in should_refresh before comparing.
    """

    def test_should_refresh_tolerates_naive_expires_at(self):
        """should_refresh must not crash when expires_at is naive (the shape
        every built-in handler produces)."""
        tr = TokenRefresher()
        tr.register_service(
            "svc",
            refresh_handler=_handler_returning_naive_expires_at,
            expires_at=_naive_future(-60),  # already expired
            refresh_token="rt",
        )
        # Must not raise.
        assert tr.should_refresh("svc") is True

    def test_get_status_tolerates_naive_expires_at(self):
        """get_status() calls should_refresh internally; it must not crash for
        services registered with a naive expires_at."""
        tr = TokenRefresher()
        tr.register_service(
            "svc",
            refresh_handler=_handler_returning_naive_expires_at,
            expires_at=_naive_future(-60),
            refresh_token="rt",
        )
        status = tr.get_status()  # must not raise
        assert "svc" in status
        assert status["svc"]["needs_refresh"] is True

    def test_refresh_then_should_refresh_does_not_crash(self):
        """End-to-end: after refresh_token stores a naive expires_at (what the
        real handlers do), a subsequent should_refresh must still work — this
        is the path that breaks auto-refresh in production."""
        tr = TokenRefresher()
        tr.register_service(
            "svc",
            refresh_handler=_handler_returning_naive_expires_at,
            expires_at=_aware_future(-60),  # expired -> triggers refresh
            refresh_token="rt",
        )
        # First refresh succeeds; handler stores a NAIVE expires_at.
        assert asyncio.run(tr.refresh_token("svc")) is True
        stored = tr.token_metadata["svc"]["expires_at"]
        assert stored.tzinfo is None, "handler stores naive expires_at (real-world shape)"

        # Previously raised TypeError here, killing further refresh checks.
        assert isinstance(tr.should_refresh("svc"), bool)
