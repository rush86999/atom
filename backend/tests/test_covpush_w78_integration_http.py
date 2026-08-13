# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/integration_http. Resilience wrapper: circuit
breaker, rate limiting, 429 Retry-After, 5xx backoff, 401 refresh, network
error retries, health monitoring, convenience methods and the ImportError
fallback ladder. httpx client fully mocked — no network.

Coverage:
- request(): circuit breaker open → HTTPStatusError; breaker check exception →
  proceed; rate limiter limited → wait; limiter exception → proceed.
- 429: Retry-After seconds / HTTP-date / missing / invalid / capped.
- 5xx backoff retry → eventual success.
- 401: refresh + retry, refresh returning None, refresh raising.
- Success records health; non-retryable 4xx records failure.
- Network error (httpx.RequestError) retried, exhaustion re-raises.
- ImportError fallbacks for circuit_breaker/rate_limiter/health.
- _parse_retry_after branches, close(), get/post/put/patch/delete,
  get_integration_http singleton.
"""
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import core.integration_http as ih
from core.integration_http import IntegrationHTTP, get_integration_http


def _resp(status_code, headers=None, request=None):
    return httpx.Response(status_code, headers=headers or {},
                          request=request or httpx.Request("GET", "https://api.x.test/v1"))


def _cb(open_=False, raise_check=False, record_ok=True):
    breaker = MagicMock()
    if raise_check:
        breaker.is_enabled = AsyncMock(side_effect=RuntimeError("cb down"))
    else:
        breaker.is_enabled = AsyncMock(return_value=not open_)
    breaker.record_success = AsyncMock()
    breaker.record_failure = AsyncMock()
    if not record_ok:
        breaker.record_success = AsyncMock(side_effect=RuntimeError("noop"))
        breaker.record_failure = AsyncMock(side_effect=RuntimeError("noop"))
    return breaker


def _rl(limited=False, remaining=0, raise_check=False):
    limiter = MagicMock()
    if raise_check:
        limiter.is_rate_limited = AsyncMock(side_effect=RuntimeError("rl down"))
    else:
        limiter.is_rate_limited = AsyncMock(return_value=(limited, remaining))
    return limiter


def _health():
    health = MagicMock()
    health.record = MagicMock()
    return health


def _patch_resilience(cb=None, rl=None, health=None):
    sleep_mock = AsyncMock()
    patches = [
        patch("core.circuit_breaker.circuit_breaker", cb),
        patch("core.rate_limiter.rate_limiter", rl),
        patch("core.rate_limiter.calculate_backoff", lambda a, **k: 0.01),
        patch("core.integration_health_monitor.get_integration_health_monitor",
              return_value=health),
        patch("core.integration_http.asyncio.sleep", new=sleep_mock),
    ]
    return patches, sleep_mock


class _Patches:
    def __init__(self, patches):
        self._patches = patches

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        return False


class TestCircuitBreaker:
    def test_open_raises_http_status_error(self):
        client = MagicMock()
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(open_=True), rl=_rl(), health=_health())[0]):
            with pytest.raises(httpx.HTTPStatusError) as ei:
                asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert ei.value.response.status_code == 503
        client.request.assert_not_called()

    def test_breaker_check_exception_proceeds(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(raise_check=True), rl=_rl(),
                                        health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200


class TestRateLimiter:
    def test_limited_waits_then_proceeds(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(limited=True, remaining=3),
                                        health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200

    def test_limiter_exception_proceeds(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(raise_check=True),
                                        health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200


class TestRetry429:
    def test_retry_after_seconds(self):
        client = MagicMock()
        client.request = AsyncMock(side_effect=[
            _resp(429, headers={"Retry-After": "4"}),
            _resp(200),
        ])
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200
        assert client.request.await_count == 2

    def test_retry_after_http_date(self):
        client = MagicMock()
        future = datetime.now(timezone.utc) + timedelta(seconds=120)
        client.request = AsyncMock(side_effect=[
            _resp(429, headers={"Retry-After": format_datetime(future)}),
            _resp(200),
        ])
        http = IntegrationHTTP(client=client)
        patches, sleep_mock = _patch_resilience(cb=_cb(), rl=_rl(), health=_health())
        with _Patches(patches):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200
        wait = sleep_mock.await_args.args[0]
        assert 110 <= wait <= 130

    def test_429_exhausts_returns_last_response(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(429, headers={"Retry-After": "1"}))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 429
        assert client.request.await_count == 4  # 1 initial + 3 retries


class TestRetryServerError:
    def test_500_retries_with_backoff_then_success(self):
        client = MagicMock()
        client.request = AsyncMock(side_effect=[
            _resp(500), _resp(502), _resp(200),
        ])
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200
        assert client.request.await_count == 3

    def test_503_exhausts_returns_last_response(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(503))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 503
        assert client.request.await_count == 4


class TestTokenRefresh:
    def test_401_refresh_and_retry(self):
        client = MagicMock()
        client.request = AsyncMock(side_effect=[
            _resp(401), _resp(200),
        ])
        http = IntegrationHTTP(client=client)
        refresh = AsyncMock(return_value={"Authorization": "Bearer new"})
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request(
                "slack", "GET", "https://api.x.test/v1",
                headers={"Authorization": "Bearer old"},
                token_refresh_fn=refresh,
            ))
        assert resp.status_code == 200
        refresh.assert_awaited_once()
        sent_headers = client.request.await_args_list[1].kwargs["headers"]
        assert sent_headers["Authorization"] == "Bearer new"

    def test_401_refresh_returns_none_returns_401(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(401))
        http = IntegrationHTTP(client=client)
        refresh = AsyncMock(return_value=None)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request(
                "slack", "GET", "https://api.x.test/v1", token_refresh_fn=refresh))
        assert resp.status_code == 401

    def test_401_refresh_raises_returns_401(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(401))
        http = IntegrationHTTP(client=client)
        refresh = AsyncMock(side_effect=RuntimeError("refresh failed"))
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request(
                "slack", "GET", "https://api.x.test/v1", token_refresh_fn=refresh))
        assert resp.status_code == 401
        client.request.await_count == 1


class TestStatusHandling:
    def test_success_records_health_and_breaker(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        cb = _cb()
        health = _health()
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=cb, rl=_rl(), health=health)[0]):
            asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        cb.record_success.assert_awaited_once()
        health.record.assert_called_once()
        assert health.record.call_args.kwargs["success"] is True

    def test_success_records_even_if_breaker_noop_raises(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(record_ok=False), rl=_rl(), health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200

    def test_non_retryable_4xx_records_failure(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(400))
        cb = _cb()
        health = _health()
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=cb, rl=_rl(), health=health)[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 400
        cb.record_failure.assert_awaited_once()
        assert health.record.call_args.kwargs["success"] is False

    def test_request_error_retries_then_raises(self):
        client = MagicMock()
        client.request = AsyncMock(
            side_effect=httpx.ConnectError("refused", request=httpx.Request("GET", "https://x"))
        )
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            with pytest.raises(httpx.RequestError):
                asyncio_run(http.request("slack", "GET", "https://x"))
        assert client.request.await_count == 4

    def test_breaker_failure_record_exception_swallowed_on_4xx(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(400))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(record_ok=False), rl=_rl(),
                                        health=_health())[0]):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 400

    def test_breaker_failure_record_exception_swallowed_on_network_error(self):
        client = MagicMock()
        client.request = AsyncMock(
            side_effect=httpx.ConnectError("refused", request=httpx.Request("GET", "https://x"))
        )
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(record_ok=False), rl=_rl(),
                                        health=_health())[0]):
            with pytest.raises(httpx.RequestError):
                asyncio_run(http.request("slack", "GET", "https://x"))


class TestImportErrorFallbacks:
    def test_fallback_ladder(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        http = IntegrationHTTP(client=client)
        with patch.dict(sys.modules, {
            "core.circuit_breaker": None,
            "core.rate_limiter": None,
            "core.integration_health_monitor": None,
        }):
            resp = asyncio_run(http.request("slack", "GET", "https://api.x.test/v1"))
        assert resp.status_code == 200
        client.request.assert_awaited_once()


class TestParseRetryAfter:
    def test_missing_header_default(self):
        http = IntegrationHTTP(client=MagicMock())
        assert http._parse_retry_after(_resp(429), "slack") == 2.0

    def test_integer_seconds(self):
        http = IntegrationHTTP(client=MagicMock())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": "7"}), "s") == 7.0

    def test_float_seconds(self):
        http = IntegrationHTTP(client=MagicMock())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": "2.5"}), "s") == 2.5

    def test_http_date_in_past_clamped_to_1(self):
        past = format_datetime(datetime.now(timezone.utc) - timedelta(seconds=600))
        http = IntegrationHTTP(client=MagicMock())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": past}), "s") == 1.0

    def test_http_date_capped_at_300(self):
        far = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=3600))
        http = IntegrationHTTP(client=MagicMock())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": far}), "s") == 300.0

    def test_garbage_default(self):
        http = IntegrationHTTP(client=MagicMock())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": "garbage"}), "s") == 2.0


class TestConvenienceAndLifecycle:
    def test_get_post_put_patch_delete(self):
        client = MagicMock()
        client.request = AsyncMock(return_value=_resp(200))
        http = IntegrationHTTP(client=client)
        with _Patches(_patch_resilience(cb=_cb(), rl=_rl(), health=_health())[0]):
            assert asyncio_run(http.get("slack", "https://x")).status_code == 200
            assert asyncio_run(http.post("slack", "https://x")).status_code == 200
            assert asyncio_run(http.put("slack", "https://x")).status_code == 200
            assert asyncio_run(http.patch("slack", "https://x")).status_code == 200
            assert asyncio_run(http.delete("slack", "https://x")).status_code == 200
        methods = [c.args[0] for c in client.request.await_args_list]
        assert methods == ["GET", "POST", "PUT", "PATCH", "DELETE"]

    def test_close_owned_client(self):
        http = IntegrationHTTP()
        with patch.object(http._client, "aclose", new=AsyncMock()) as close_mock:
            asyncio_run(http.close())
        close_mock.assert_awaited_once()

    def test_close_injected_client_not_closed(self):
        client = MagicMock()
        http = IntegrationHTTP(client=client)
        asyncio_run(http.close())
        client.aclose.assert_not_called()

    def test_get_integration_http_singleton(self):
        with patch.object(ih, "_integration_http", None):
            first = get_integration_http()
            assert get_integration_http() is first
            assert isinstance(first, IntegrationHTTP)

    def test_owns_client_flag(self):
        client = MagicMock()
        assert IntegrationHTTP(client=client)._owns_client is False
        assert IntegrationHTTP()._owns_client is True


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
