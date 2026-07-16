"""
Universal integration HTTP wrapper — resilience for all third-party APIs.

Every third-party integration HTTP call should flow through IntegrationHTTP,
which handles:
  - Circuit breaking (skip calls when a provider is down)
  - Rate limiting (wait when a provider throttles us)
  - 429 Retry-After parsing and backoff
  - 500/502/503/504 exponential backoff retries
  - 401 token refresh and retry
  - Timeout standardization (connect=10s, read=30s)
  - Health monitoring (success rate + latency per integration)

This replaces the ad-hoc patterns in ~86 integration services that currently
make raw httpx calls with no resilience.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Standardized timeout: fast connect fail, reasonable read.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=5.0)

# Retry configuration.
_MAX_RETRIES = 3
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class IntegrationHTTP:
    """Universal HTTP wrapper for third-party API calls.

    Usage in an integration service:

        self.http = IntegrationHTTP()

        # Instead of: resp = await self.client.get(url)
        resp = await self.http.request("slack", "GET", url, headers=headers)
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_client = client is None

    async def request(
        self,
        integration: str,
        method: str,
        url: str,
        *,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        timeout: Optional[httpx.Timeout] = None,
        token_refresh_fn: Optional[Any] = None,
        **kwargs,
    ) -> httpx.Response:
        """Make a resilient HTTP request to a third-party API.

        Args:
            integration: Integration name (e.g. "slack", "hubspot") for
                circuit breaker / rate limiter / health monitoring.
            method: HTTP method (GET, POST, etc.).
            url: Full URL.
            headers, params, json, data: Standard httpx kwargs.
            timeout: Override the default timeout.
            token_refresh_fn: Optional async callable that refreshes the OAuth
                token and returns updated headers. Called on 401.

        Returns:
            httpx.Response on success (any status code after retries exhausted).

        Raises:
            httpx.HTTPStatusError: if the circuit breaker is OPEN.
            httpx.RequestError: on network failure after all retries.
        """
        # --- Lazy imports (avoid circular import at module load) ---
        try:
            from core.circuit_breaker import circuit_breaker
            from core.rate_limiter import rate_limiter, should_retry, calculate_backoff
        except ImportError:
            circuit_breaker = None
            rate_limiter = None
            should_retry = lambda s: s in _RETRY_STATUS_CODES
            calculate_backoff = lambda a: min(2 ** (a - 1), 60)

        try:
            from core.integration_health_monitor import get_integration_health_monitor
            health = get_integration_health_monitor()
        except ImportError:
            health = None

        # --- 1. Circuit breaker check ---
        if circuit_breaker:
            try:
                can_call = await circuit_breaker.is_enabled(integration)
                if not can_call:
                    logger.warning(f"[{integration}] Circuit breaker OPEN — skipping request to {url}")
                    raise httpx.HTTPStatusError(
                        f"Circuit breaker open for {integration}",
                        request=httpx.Request(method, url),
                        response=httpx.Response(503),
                    )
            except httpx.HTTPStatusError:
                raise
            except Exception:
                logger.debug("circuit breaker check failed for %s, proceeding without", integration, exc_info=True)  # Circuit breaker unavailable — proceed without it

        # --- 2. Rate limiter check ---
        if rate_limiter:
            try:
                is_limited, remaining = await rate_limiter.is_rate_limited(integration)
                if is_limited and remaining > 0:
                    logger.info(f"[{integration}] Rate limited — waiting {remaining}s")
                    await asyncio.sleep(remaining)
            except Exception:
                logger.debug("rate limiter check failed for %s, proceeding", integration, exc_info=True)  # Rate limiter unavailable

        # --- 3. Retry loop ---
        last_exc: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 2):  # 1 initial + 3 retries
            start_time = time.monotonic()
            try:
                resp = await self._client.request(
                    method, url,
                    headers=headers, params=params, json=json, data=data,
                    timeout=timeout or _DEFAULT_TIMEOUT,
                    **kwargs,
                )
                elapsed_ms = (time.monotonic() - start_time) * 1000

                # --- 429: rate limited by provider ---
                if resp.status_code == 429 and attempt <= _MAX_RETRIES:
                    retry_after = self._parse_retry_after(resp, integration)
                    logger.info(f"[{integration}] 429 rate limited — retrying after {retry_after}s (attempt {attempt})")
                    await asyncio.sleep(retry_after)
                    continue

                # --- 500/502/503/504: server error, retry with backoff ---
                if resp.status_code in {500, 502, 503, 504} and attempt <= _MAX_RETRIES:
                    backoff = calculate_backoff(attempt)
                    logger.warning(f"[{integration}] {resp.status_code} — retrying in {backoff}s (attempt {attempt})")
                    await asyncio.sleep(backoff)
                    continue

                # --- 401: token expired, refresh and retry once ---
                if resp.status_code == 401 and token_refresh_fn and attempt == 1:
                    logger.info(f"[{integration}] 401 — attempting token refresh")
                    try:
                        new_headers = await token_refresh_fn()
                        if new_headers:
                            headers = {**(headers or {}), **new_headers}
                            continue  # retry with refreshed token
                    except Exception as refresh_err:
                        logger.warning(f"[{integration}] Token refresh failed: {refresh_err}")

                # --- Success (or all retries exhausted) ---
                if resp.is_success:
                    if circuit_breaker:
                        try:
                            await circuit_breaker.record_success(integration)
                        except Exception as _e:
                            logger.debug("integration_http op failed: %s", _e, exc_info=True)
                    if health:
                        health.record(integration, success=True, latency_ms=elapsed_ms)
                else:
                    # Non-retryable error (4xx other than 401/429)
                    if circuit_breaker:
                        try:
                            await circuit_breaker.record_failure(integration)
                        except Exception as _e:
                            logger.debug("integration_http op failed: %s", _e, exc_info=True)
                    if health:
                        health.record(integration, success=False, latency_ms=elapsed_ms)

                return resp

            except httpx.RequestError as e:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                last_exc = e
                logger.warning(f"[{integration}] Network error: {e} (attempt {attempt})")
                if circuit_breaker:
                    try:
                        await circuit_breaker.record_failure(integration)
                    except Exception as _e:
                        logger.debug("integration_http op failed: %s", _e, exc_info=True)
                if health:
                    health.record(integration, success=False, latency_ms=elapsed_ms)

                if attempt <= _MAX_RETRIES:
                    backoff = calculate_backoff(attempt)
                    await asyncio.sleep(backoff)
                    continue

        # All retries exhausted
        raise last_exc or httpx.RequestError(f"All retries exhausted for {integration}")

    def _parse_retry_after(self, resp: httpx.Response, integration: str) -> float:
        """Parse Retry-After header (seconds or HTTP date)."""
        retry_after = resp.headers.get("Retry-After", resp.headers.get("retry-after", ""))
        if not retry_after:
            return 2.0  # default

        # Try integer seconds
        try:
            return float(retry_after)
        except ValueError:
            pass

        # Try HTTP date
        try:
            from email.utils import parsedate_to_datetime
            from datetime import datetime, timezone
            retry_dt = parsedate_to_datetime(retry_after)
            now = datetime.now(timezone.utc)
            delta = (retry_dt - now).total_seconds()
            return max(1.0, min(delta, 300.0))  # cap at 5 min
        except Exception:
            return 2.0

    async def close(self):
        """Close the underlying HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()

    # Convenience methods for common patterns.
    async def get(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return await self.request(integration, "GET", url, **kwargs)

    async def post(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return await self.request(integration, "POST", url, **kwargs)

    async def put(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return await self.request(integration, "PUT", url, **kwargs)

    async def patch(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return await self.request(integration, "PATCH", url, **kwargs)

    async def delete(self, integration: str, url: str, **kwargs) -> httpx.Response:
        return await self.request(integration, "DELETE", url, **kwargs)


# Module-level singleton (like ProviderHealthMonitor / CircuitBreaker).
_integration_http: Optional[IntegrationHTTP] = None


def get_integration_http() -> IntegrationHTTP:
    """Get the shared IntegrationHTTP instance."""
    global _integration_http
    if _integration_http is None:
        _integration_http = IntegrationHTTP()
    return _integration_http
