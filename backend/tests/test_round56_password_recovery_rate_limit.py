"""
Round 56 — Password-recovery endpoints: missing rate limits
(Red-Green-Refactor).

login/register/refresh got AuthRateLimiter deps in R14, and verify/TOTP in
R15/16 — but the three unauthenticated password-recovery endpoints have NO
rate limiting:

  A. POST /forgot-password — any caller can spam reset emails for any known
     address (mailbox flooding + mailer DoS).
  B. POST /reset-password — unthrottled token-guessing surface (256-bit
     tokens make brute force infeasible, but defense in depth + per-IP
     throttling is the pattern for every other auth endpoint).
  C. POST /verify-token — same class.

Fix: AuthRateLimiter deps on all three endpoints (5/5min forgot+reset,
10/5min verify), mirroring login_rate_limit.
"""

import pytest
from fastapi import HTTPException, Request

from core.auth_endpoints import (
    forgot_password_rate_limit,
    reset_password_rate_limit,
    verify_token_rate_limit,
)


@pytest.fixture(autouse=True)
def _clear_limiters(monkeypatch):
    """Isolate limiter state per test + neutralize the TESTING bypass."""
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("BYPASS_RATE_LIMIT", raising=False)
    import core.auth_endpoints as mod

    for name in ("_recovery_limiter", "_verify_limiter", "_reset_limiter"):
        getattr(mod, name)._hits.clear()
    yield


def _fake_request(ip="1.2.3.4"):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [],
        "client": (ip, 12345),
    }
    return Request(scope)


class TestForgotPasswordRateLimit:
    def test_allows_up_to_limit_then_429(self):
        for _ in range(5):
            forgot_password_rate_limit(_fake_request())
        with pytest.raises(HTTPException) as exc:
            forgot_password_rate_limit(_fake_request())
        assert exc.value.status_code == 429

    def test_limit_is_per_ip(self):
        for _ in range(5):
            forgot_password_rate_limit(_fake_request(ip="1.1.1.1"))
        with pytest.raises(HTTPException):
            forgot_password_rate_limit(_fake_request(ip="1.1.1.1"))
        # Different IP is unaffected
        forgot_password_rate_limit(_fake_request(ip="2.2.2.2"))


class TestVerifyTokenRateLimit:
    def test_allows_up_to_limit_then_429(self):
        for _ in range(10):
            verify_token_rate_limit(_fake_request())
        with pytest.raises(HTTPException) as exc:
            verify_token_rate_limit(_fake_request())
        assert exc.value.status_code == 429


class TestResetPasswordRateLimit:
    def test_allows_up_to_limit_then_429(self):
        for _ in range(5):
            reset_password_rate_limit(_fake_request())
        with pytest.raises(HTTPException) as exc:
            reset_password_rate_limit(_fake_request())
        assert exc.value.status_code == 429

    def test_endpoint_level_429(self):
        """POST /forgot-password returns 429 once the IP is exhausted."""
        from unittest.mock import MagicMock

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.auth_endpoints import router
        from core.database import get_db

        app = FastAPI()
        app.include_router(router)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(5):
            resp = client.post(
                "/api/auth/forgot-password", json={"email": "nobody@example.com"}
            )
            assert resp.status_code == 200
        resp = client.post(
            "/api/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        assert resp.status_code == 429, (
            "forgot-password accepted unlimited reset-email requests — "
            "email-bombing / mailer DoS"
        )
