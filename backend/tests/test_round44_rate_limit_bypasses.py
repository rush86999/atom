"""
Round 44 — Rate-limit bypasses (Red-Green-Refactor).

  A. core/security/middleware.py RateLimitMiddleware — the global rate limiter
     (120/min, 5000/day) bypasses when ANY request carries an
     `X-Scheduler-Secret` header — presence check only, no value validation,
     and nothing in the codebase ever sets the header. `/api/scheduler` paths
     are already exempted by prefix, so the header check is dead weight that
     lets any client strip rate limiting on every endpoint.
  B. core/security/auth_rate_limit.py AuthRateLimiter._client_ip — trusts the
     LAST entry of X-Forwarded-For as the rate-limit key. That is only safe
     behind a proxy that appends the peer IP; the Personal Edition runs
     standalone (uvicorn main:app), where the client's own header value is
     used verbatim — rotate the header and login/register/refresh limits
     (10/min, 3/5min, 30/min) vanish.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request


def make_http_request(path: str, headers: dict, client_ip: str = "1.2.3.4"):
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "headers": raw_headers,
        "client": (client_ip, 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


# ============================================================================
# A. Global rate limiter — X-Scheduler-Secret presence bypass
# ============================================================================

class TestRateLimitSchedulerBypass:
    def _mw(self):
        from core.security.middleware import RateLimitMiddleware

        mw = RateLimitMiddleware(app=MagicMock())
        mw._get_tenant_limits_sync = lambda tenant: (120, 5000)
        checked = MagicMock(return_value=(False, {}))
        mw._check_rate_limit_sync = checked
        return mw, checked

    def test_scheduler_secret_header_does_not_bypass(self):
        """Any X-Scheduler-Secret value must NOT strip rate limiting."""
        mw, checked = self._mw()
        req = make_http_request(
            "/api/some-endpoint", {"x-scheduler-secret": "anything"}
        )
        call_next = AsyncMock(return_value=MagicMock(headers={}))
        asyncio.run(mw.dispatch(req, call_next))
        assert checked.called, "rate-limit check must run despite the header"

    def test_scheduler_path_is_still_exempt(self):
        """Legitimate scheduler callbacks keep their path-based exemption."""
        mw, checked = self._mw()
        req = make_http_request("/api/scheduler/jobs", {})
        call_next = AsyncMock(return_value=MagicMock(headers={}))
        asyncio.run(mw.dispatch(req, call_next))
        assert not checked.called, "scheduler path must stay exempt"

    def test_normal_request_is_rate_limited(self):
        mw, checked = self._mw()
        req = make_http_request("/api/some-endpoint", {})
        call_next = AsyncMock(return_value=MagicMock(headers={}))
        asyncio.run(mw.dispatch(req, call_next))
        assert checked.called


# ============================================================================
# B. Auth rate limiter — X-Forwarded-For key spoofing
# ============================================================================

class TestAuthRateLimitKey:
    @pytest.fixture(autouse=True)
    def _no_bypass_env(self, monkeypatch):
        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)

    def test_xff_spoofing_does_not_rotate_bucket(self):
        """Different XFF values must not reset the per-IP attempt counter."""
        from core.security.auth_rate_limit import AuthRateLimiter

        limiter = AuthRateLimiter(limit=3, window_seconds=60)
        r1 = make_http_request("/api/auth/login", {"x-forwarded-for": "spoofed-1"})
        r2 = make_http_request("/api/auth/login", {"x-forwarded-for": "spoofed-2"})
        r3 = make_http_request("/api/auth/login", {"x-forwarded-for": "spoofed-3"})

        assert limiter.check(r1)[0] is True
        assert limiter.check(r1)[0] is True
        assert limiter.check(r1)[0] is True

        # Same client (same TCP peer), new spoofed header → still blocked
        allowed, _ = limiter.check(r2)
        assert allowed is False
        allowed, _ = limiter.check(r3)
        assert allowed is False

    def test_missing_xff_uses_socket_peer(self):
        from core.security.auth_rate_limit import AuthRateLimiter

        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        req = make_http_request("/api/auth/login", {})
        assert limiter.check(req)[0] is True
        assert limiter.check(req)[0] is True
        allowed, _ = limiter.check(req)
        assert allowed is False
