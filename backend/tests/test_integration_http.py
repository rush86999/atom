"""
Tests for the integration resilience layer.

Tests the IntegrationHTTP wrapper (circuit breaker, rate limiting, retries,
429/Retry-After parsing, 401 token refresh, health monitoring) and the
IntegrationHealthMonitor (sliding window, scoring).
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


# ===========================================================================
# IntegrationHTTP wrapper tests
# ===========================================================================

class TestIntegrationHTTP:

    @pytest.fixture
    def http_wrapper(self):
        """Create an IntegrationHTTP with a mock client."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        return IntegrationHTTP_with_mock(mock_client), mock_client

    def test_wrapper_exists(self):
        from core.integration_http import IntegrationHTTP
        assert IntegrationHTTP is not None

    def test_get_integration_http_singleton(self):
        from core.integration_http import get_integration_http
        h1 = get_integration_http()
        h2 = get_integration_http()
        assert h1 is h2

    @pytest.mark.asyncio
    async def test_successful_request(self):
        """A 200 response is returned with no retries."""
        from core.integration_http import IntegrationHTTP

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.headers = {}
        mock_client.request = AsyncMock(return_value=mock_resp)

        http = IntegrationHTTP(client=mock_client)
        resp = await http.request("test_svc", "GET", "https://example.com/api")
        assert resp.status_code == 200
        assert mock_client.request.call_count == 1  # no retries

    @pytest.mark.asyncio
    async def test_429_retry_after_header(self):
        """A 429 with Retry-After triggers a retry after the wait."""
        from core.integration_http import IntegrationHTTP

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        ratelimited_resp = MagicMock(spec=httpx.Response)
        ratelimited_resp.status_code = 429
        ratelimited_resp.is_success = False
        ratelimited_resp.headers = {"Retry-After": "0"}  # instant retry

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.is_success = True
        success_resp.headers = {}

        mock_client.request = AsyncMock(side_effect=[ratelimited_resp, success_resp])

        http = IntegrationHTTP(client=mock_client)
        resp = await http.request("test_svc", "GET", "https://example.com/api")
        assert resp.status_code == 200
        assert mock_client.request.call_count == 2  # initial + 1 retry

    @pytest.mark.asyncio
    async def test_503_retries_with_backoff(self):
        """A 503 triggers retries with exponential backoff."""
        from core.integration_http import IntegrationHTTP

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 503
        err_resp.is_success = False
        err_resp.headers = {}

        ok_resp = MagicMock(spec=httpx.Response)
        ok_resp.status_code = 200
        ok_resp.is_success = True
        ok_resp.headers = {}

        mock_client.request = AsyncMock(side_effect=[err_resp, ok_resp])

        http = IntegrationHTTP(client=mock_client)
        resp = await http.request("test_svc", "GET", "https://example.com/api")
        assert resp.status_code == 200
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_401_triggers_token_refresh(self):
        """A 401 triggers the token_refresh_fn and retries once."""
        from core.integration_http import IntegrationHTTP

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        unauthorized = MagicMock(spec=httpx.Response)
        unauthorized.status_code = 401
        unauthorized.is_success = False
        unauthorized.headers = {}

        ok = MagicMock(spec=httpx.Response)
        ok.status_code = 200
        ok.is_success = True
        ok.headers = {}

        mock_client.request = AsyncMock(side_effect=[unauthorized, ok])

        refresh_fn = AsyncMock(return_value={"Authorization": "Bearer new_token"})

        http = IntegrationHTTP(client=mock_client)
        resp = await http.request("test_svc", "GET", "https://example.com/api",
                                   token_refresh_fn=refresh_fn)
        assert resp.status_code == 200
        assert refresh_fn.call_count == 1
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        """After max retries, the last error response is returned."""
        from core.integration_http import IntegrationHTTP

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        err_resp = MagicMock(spec=httpx.Response)
        err_resp.status_code = 503
        err_resp.is_success = False
        err_resp.headers = {}

        mock_client.request = AsyncMock(return_value=err_resp)

        http = IntegrationHTTP(client=mock_client)
        resp = await http.request("test_svc", "GET", "https://example.com/api")
        assert resp.status_code == 503
        # 1 initial + 3 retries = 4 calls
        assert mock_client.request.call_count == 4

    @pytest.mark.asyncio
    async def test_convenience_methods(self):
        """GET/POST/PUT/PATCH/DELETE convenience methods work."""
        from core.integration_http import IntegrationHTTP

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        ok = MagicMock(spec=httpx.Response)
        ok.status_code = 200
        ok.is_success = True
        ok.headers = {}
        mock_client.request = AsyncMock(return_value=ok)

        http = IntegrationHTTP(client=mock_client)
        await http.get("svc", "https://example.com")
        await http.post("svc", "https://example.com")
        await http.put("svc", "https://example.com")
        await http.patch("svc", "https://example.com")
        await http.delete("svc", "https://example.com")
        assert mock_client.request.call_count == 5

    def test_retry_after_header_parsing_seconds(self):
        """Retry-After as integer seconds is parsed correctly."""
        from core.integration_http import IntegrationHTTP

        http = IntegrationHTTP.__new__(IntegrationHTTP)
        resp = MagicMock(spec=httpx.Response)
        resp.headers = {"Retry-After": "5"}
        assert http._parse_retry_after(resp, "test") == 5.0

    def test_retry_after_header_parsing_missing(self):
        """Missing Retry-After defaults to 2 seconds."""
        from core.integration_http import IntegrationHTTP

        http = IntegrationHTTP.__new__(IntegrationHTTP)
        resp = MagicMock(spec=httpx.Response)
        resp.headers = {}
        assert http._parse_retry_after(resp, "test") == 2.0


# ===========================================================================
# IntegrationHealthMonitor tests
# ===========================================================================

class TestIntegrationHealthMonitor:

    def test_monitor_exists(self):
        from core.integration_health_monitor import IntegrationHealthMonitor
        assert IntegrationHealthMonitor is not None

    def test_singleton(self):
        from core.integration_health_monitor import get_integration_health_monitor
        m1 = get_integration_health_monitor()
        m2 = get_integration_health_monitor()
        assert m1 is m2

    def test_no_data_returns_healthy(self):
        """An integration with no samples scores 1.0 (assume healthy)."""
        from core.integration_health_monitor import IntegrationHealthMonitor
        monitor = IntegrationHealthMonitor()
        assert monitor.get_health("unknown") == 1.0

    def test_all_successes_high_score(self):
        """All successful calls with low latency produce a high score."""
        from core.integration_health_monitor import IntegrationHealthMonitor
        monitor = IntegrationHealthMonitor()
        for _ in range(10):
            monitor.record("slack", success=True, latency_ms=500)
        score = monitor.get_health("slack")
        assert score > 0.9, f"Expected high score, got {score}"

    def test_all_failures_low_score(self):
        """All failures produce a low score."""
        from core.integration_health_monitor import IntegrationHealthMonitor
        monitor = IntegrationHealthMonitor()
        for _ in range(10):
            monitor.record("slack", success=False, latency_ms=5000)
        score = monitor.get_health("slack")
        assert score < 0.1, f"Expected low score, got {score}"

    def test_unhealthy_detection(self):
        """get_unhealthy returns integrations below threshold."""
        from core.integration_health_monitor import IntegrationHealthMonitor
        monitor = IntegrationHealthMonitor()
        for _ in range(5):
            monitor.record("broken_svc", success=False, latency_ms=5000)
        for _ in range(5):
            monitor.record("good_svc", success=True, latency_ms=200)
        unhealthy = monitor.get_unhealthy(threshold=0.5)
        assert "broken_svc" in unhealthy
        assert "good_svc" not in unhealthy

    def test_stats_summary(self):
        """get_stats returns a dict with health metrics per integration."""
        from core.integration_health_monitor import IntegrationHealthMonitor
        monitor = IntegrationHealthMonitor()
        monitor.record("hubspot", success=True, latency_ms=300)
        monitor.record("hubspot", success=False, latency_ms=1000)
        stats = monitor.get_stats()
        assert "hubspot" in stats
        assert "health_score" in stats["hubspot"]
        assert "total_calls" in stats["hubspot"]
        assert stats["hubspot"]["total_calls"] == 2


# ===========================================================================
# OAuth fix verification
# ===========================================================================

class TestOAuthRefreshFix:

    def test_oauth_import_path_correct(self):
        """oauth_user_context.py imports from core.oauth_handler, not api.oauth_handler."""
        import core.oauth_user_context as mod
        source = open(mod.__file__).read()
        assert "from core.oauth_handler import" in source, \
            "oauth_user_context should import from core.oauth_handler (not api.oauth_handler)"
        assert "from api.oauth_handler import" not in source, \
            "oauth_user_context should NOT import from api.oauth_handler (module doesn't exist)"
