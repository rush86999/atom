# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/security/auth_rate_limit.py to 100%.

Covers: sliding-window counting (allowed/blocked/remaining), window expiry,
per-IP bucketing, XFF trust gating (TRUST_X_FORWARDED_FOR=1 last-entry vs
unconditional ignore), client-None fallback, TESTING/BYPASS_RATE_LIMIT env
bypass, reset_ip, and the three FastAPI dependencies (login/register/refresh)
for both the allow and 429 paths. Fully mocked — no network, no DB.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import core.security.auth_rate_limit as arl
from core.security.auth_rate_limit import AuthRateLimiter


_MISSING = object()


def _request(headers=None, client_host="203.0.113.7", client=_MISSING):
    if client is _MISSING:
        client = SimpleNamespace(host=client_host)
    return SimpleNamespace(headers=headers or {}, client=client)


@pytest.fixture(autouse=True)
def _clean_singletons():
    """Isolate the module-level singleton limiters between tests."""
    for limiter in (arl._login_limiter, arl._register_limiter, arl._refresh_limiter):
        limiter._hits.clear()
    yield
    for limiter in (arl._login_limiter, arl._register_limiter, arl._refresh_limiter):
        limiter._hits.clear()


# ============================================================================
# Client IP extraction
# ============================================================================

class TestClientIp:
    def test_uses_tcp_peer_by_default(self):
        limiter = AuthRateLimiter()
        assert limiter._client_ip(_request(client_host="10.0.0.5")) == "10.0.0.5"

    def test_xff_ignored_when_flag_unset(self, monkeypatch):
        monkeypatch.delenv("TRUST_X_FORWARDED_FOR", raising=False)
        limiter = AuthRateLimiter()
        req = _request(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}, client_host="9.9.9.9")
        # R44 security: spoofed XFF must NOT change the bucket
        assert limiter._client_ip(req) == "9.9.9.9"

    def test_xff_last_entry_used_when_flag_set(self, monkeypatch):
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "1")
        try:
            limiter = AuthRateLimiter()
            req = _request(
                headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"},
                client_host="9.9.9.9",
            )
            # Last entry = closest proxy — most trustworthy
            assert limiter._client_ip(req) == "5.6.7.8"
        finally:
            monkeypatch.delenv("TRUST_X_FORWARDED_FOR")

    def test_unknown_client_fallback(self):
        limiter = AuthRateLimiter()
        assert limiter._client_ip(_request(client=None)) == "unknown"

    def test_blank_xff_uses_peer(self, monkeypatch):
        monkeypatch.setenv("TRUST_X_FORWARDED_FOR", "1")
        try:
            limiter = AuthRateLimiter()
            assert limiter._client_ip(_request(headers={"x-forwarded-for": ""})) == "203.0.113.7"
        finally:
            monkeypatch.delenv("TRUST_X_FORWARDED_FOR")


# ============================================================================
# Sliding-window check()
# ============================================================================

class TestCheck:
    def test_first_request_allowed_with_full_remaining(self):
        limiter = AuthRateLimiter(limit=3, window_seconds=60)
        allowed, remaining = limiter.check(_request())
        assert allowed is True
        assert remaining == 2

    def test_remaining_decrements(self):
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        allowed, remaining = limiter.check(_request())
        assert allowed is True
        assert remaining == 1
        allowed, remaining = limiter.check(_request())
        assert allowed is True
        assert remaining == 0
        # limit+1th request is denied
        allowed, remaining = limiter.check(_request())
        assert allowed is False
        assert remaining == 0

    def test_limit_reached_blocks(self):
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        limiter.check(_request())
        limiter.check(_request())
        allowed, remaining = limiter.check(_request())
        assert allowed is False
        assert remaining == 0

    def test_requests_outside_window_expire(self):
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        limiter.check(_request())
        limiter.check(_request())
        # All timestamps older than the window → allowed again
        with patch("time.time", return_value=time.time() + 120):
            allowed, remaining = limiter.check(_request())
        assert allowed is True

    def test_mixed_old_and_new_timestamps_dropped(self):
        limiter = AuthRateLimiter(limit=2, window_seconds=60)
        with patch("core.security.auth_rate_limit.time.time", return_value=1000.0):
            limiter.check(_request())
            limiter.check(_request())
            allowed, _ = limiter.check(_request())
            assert allowed is False
        # Two timestamps expire; one (current) stays
        with patch("core.security.auth_rate_limit.time.time", return_value=1100.0):
            limiter.check(_request())
            allowed, remaining = limiter.check(_request())
            assert allowed is True
            assert remaining == 0

    def test_per_ip_buckets_independent(self):
        limiter = AuthRateLimiter(limit=1, window_seconds=60)
        allowed, _ = limiter.check(_request(client_host="1.1.1.1"))
        assert allowed is True
        # Different IP unaffected
        allowed, _ = limiter.check(_request(client_host="2.2.2.2"))
        assert allowed is True
        # Same IP blocked
        allowed, _ = limiter.check(_request(client_host="1.1.1.1"))
        assert allowed is False

    def test_testing_env_bypasses(self, monkeypatch):
        monkeypatch.setenv("TESTING", "1")
        try:
            limiter = AuthRateLimiter(limit=1, window_seconds=60)
            limiter.check(_request())
            allowed, remaining = limiter.check(_request())
            assert allowed is True
            assert remaining == limiter.limit
        finally:
            monkeypatch.delenv("TESTING")

    def test_bypass_rate_limit_env(self, monkeypatch):
        monkeypatch.setenv("BYPASS_RATE_LIMIT", "1")
        try:
            limiter = AuthRateLimiter(limit=1, window_seconds=60)
            limiter.check(_request())
            allowed, remaining = limiter.check(_request())
            assert allowed is True
            assert remaining == 1
        finally:
            monkeypatch.delenv("BYPASS_RATE_LIMIT")

    def test_reset_ip_clears_bucket(self):
        limiter = AuthRateLimiter(limit=1, window_seconds=60)
        limiter.check(_request(client_host="1.1.1.1"))
        assert limiter.check(_request(client_host="1.1.1.1"))[0] is False
        limiter.reset_ip("1.1.1.1")
        assert limiter.check(_request(client_host="1.1.1.1"))[0] is True

    def test_reset_ip_unknown_ip_noop(self):
        limiter = AuthRateLimiter(limit=1, window_seconds=60)
        limiter.reset_ip("nobody")  # must not raise


# ============================================================================
# FastAPI dependencies
# ============================================================================

class TestDependencies:
    def test_login_allowed_passthrough(self):
        with patch.object(arl._login_limiter, "check", return_value=(True, 9)):
            arl.login_rate_limit(_request())  # must not raise

    def test_login_blocked_raises_429(self):
        with patch.object(arl._login_limiter, "check", return_value=(False, 0)):
            with pytest.raises(HTTPException) as exc:
                arl.login_rate_limit(_request())
            assert exc.value.status_code == 429
            assert exc.value.headers == {"Retry-After": "60"}
            assert "login" in exc.value.detail.lower()

    def test_register_allowed_passthrough(self):
        with patch.object(arl._register_limiter, "check", return_value=(True, 2)):
            arl.register_rate_limit(_request())

    def test_register_blocked_raises_429(self):
        with patch.object(arl._register_limiter, "check", return_value=(False, 0)):
            with pytest.raises(HTTPException) as exc:
                arl.register_rate_limit(_request())
            assert exc.value.status_code == 429
            assert exc.value.headers == {"Retry-After": "300"}

    def test_refresh_allowed_passthrough(self):
        with patch.object(arl._refresh_limiter, "check", return_value=(True, 29)):
            arl.refresh_rate_limit(_request())

    def test_refresh_blocked_raises_429(self):
        with patch.object(arl._refresh_limiter, "check", return_value=(False, 0)):
            with pytest.raises(HTTPException) as exc:
                arl.refresh_rate_limit(_request())
            assert exc.value.status_code == 429
            assert exc.value.headers == {"Retry-After": "60"}

    def test_singleton_limits_match_documented(self):
        assert arl._login_limiter.limit == 10
        assert arl._login_limiter.window == 60
        assert arl._register_limiter.limit == 3
        assert arl._register_limiter.window == 300
        assert arl._refresh_limiter.limit == 30
        assert arl._refresh_limiter.window == 60


import time  # noqa: E402  (used by window-expiry tests)
