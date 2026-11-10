"""Referrer-Policy preservation across both shared security-header variants.

W3C Referrer Policy: a response may explicitly choose a stricter policy than
the application's default. A generic security-header middleware must not
weaken that explicit choice (for example, the OIDC sensitive callback/exchange
responses use ``no-referrer``). Unsafe, weak, unknown or absent values still
fall back to the existing default.
"""
import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from core.security.middleware import SecurityHeadersMiddleware as CoreHeaders
from middleware.security import SecurityHeadersMiddleware as ParallelHeaders

DEFAULT_REFERRER_POLICY = "strict-origin-when-cross-origin"


def _client(middleware_cls, policy=None, path="/sensitive"):
    app = FastAPI()

    @app.get(path)
    def sensitive():
        headers = {}
        if policy is not None:
            headers["Referrer-Policy"] = policy
        return Response(
            content="ok",
            media_type="text/plain",
            headers=headers,
        )

    app.add_middleware(middleware_cls)
    return TestClient(app)


@pytest.mark.parametrize("middleware_cls", [CoreHeaders, ParallelHeaders])
@pytest.mark.parametrize("policy", [
    "no-referrer",
    "same-origin",
    "strict-origin",
])
def test_explicit_stricter_policy_is_preserved(middleware_cls, policy):
    response = _client(middleware_cls, policy).get("/sensitive")
    assert response.status_code == 200
    assert response.headers["referrer-policy"] == policy


@pytest.mark.parametrize("middleware_cls", [CoreHeaders, ParallelHeaders])
def test_missing_policy_keeps_existing_default(middleware_cls):
    response = _client(middleware_cls).get("/sensitive")
    assert response.headers["referrer-policy"] == DEFAULT_REFERRER_POLICY


@pytest.mark.parametrize("middleware_cls", [CoreHeaders, ParallelHeaders])
@pytest.mark.parametrize("policy", [
    "unsafe-url",
    "origin",
    "origin-when-cross-origin",
    "no-referrer-when-downgrade",
    "strict-origin-when-cross-origin",
    "bogus-policy",
    "",
])
def test_weak_unsafe_unknown_or_default_policy_falls_back(middleware_cls, policy):
    response = _client(middleware_cls, policy).get("/sensitive")
    assert response.headers["referrer-policy"] == DEFAULT_REFERRER_POLICY


@pytest.mark.parametrize("middleware_cls", [CoreHeaders, ParallelHeaders])
def test_case_and_whitespace_strong_policy_is_preserved(middleware_cls):
    response = _client(middleware_cls, "  No-Referrer  ").get("/sensitive")
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize("middleware_cls", [CoreHeaders, ParallelHeaders])
@pytest.mark.parametrize("policy,expected", [
    # A header list resolves to its last valid member (W3C delivery rules).
    ("unsafe-url, no-referrer", "no-referrer"),
    ("no-referrer, unsafe-url", DEFAULT_REFERRER_POLICY),
    ("no-referrer, bogus-policy", "no-referrer"),
    ("bogus-policy", DEFAULT_REFERRER_POLICY),
])
def test_header_list_uses_last_valid_effective_policy(
        middleware_cls, policy, expected):
    response = _client(middleware_cls, policy).get("/sensitive")
    assert response.headers["referrer-policy"] == expected


@pytest.mark.parametrize("middleware_cls", [CoreHeaders, ParallelHeaders])
def test_existing_csp_hsts_and_frame_headers_remain(middleware_cls):
    response = _client(middleware_cls).get("/sensitive")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert "Content-Security-Policy" in response.headers
    assert "Permissions-Policy" in response.headers


def test_core_api_route_still_skips_large_headers():
    response = _client(CoreHeaders, path="/api/sensitive").get("/api/sensitive")
    assert response.headers["referrer-policy"] == DEFAULT_REFERRER_POLICY
    assert "Content-Security-Policy" not in response.headers
    assert "Strict-Transport-Security" not in response.headers
