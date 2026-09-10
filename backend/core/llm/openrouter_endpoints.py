"""
OpenRouter endpoint telemetry (Phase 5').

The public ``GET /api/v1/models/{author}/{slug}/endpoints`` subresource
reports per-hosting-provider measured health over the last 30 minutes:
uptime, time-to-first-token latency percentiles and throughput percentiles.
This module turns that feed into routing signal for the BPC ranker
(``core.llm.byok_handler.get_ranked_providers``), replacing static
assumptions about OpenRouter-hosted models with measured reality.

Phase 0 spike findings (verified live against openrouter.ai, Aug 2026):
- Anonymous access works (no Authorization header required).
- ``status``: 0 = operational, non-zero = degraded.
- ``uptime_30m`` arrives either as float (99.9) or percent-string ("99.90%").
- ``latency_30m_ms.p50`` / ``throughput_30m_tokens_per_sec.p50`` are floats.
- Unknown query params on /api/v1/models are SILENTLY IGNORED (drift hazard);
  ``category`` rejects limit/offset; pricing sort blends completion/request
  prices — never assume strict prompt-price ordering.

Design contract (fail-open everywhere):
- No data / transport error / flag off ⇒ candidate untouched (factor 1.0).
- Measured uptime below the floor ⇒ candidate excluded.
- Measured p50 latency above the cap ⇒ value score multiplied by a soft
  penalty factor (ordering influence only).
- Cache reads are synchronous and never block; refreshes run in the
  background (asyncio task when a loop is running, daemon thread otherwise).

Kill switch: ATOM_OPENROUTER_ENDPOINT_TELEMETRY_ENABLED=false.
Knobs: ATOM_OPENROUTER_MIN_UPTIME_30M (percent, default 90),
ATOM_OPENROUTER_MAX_LATENCY_P50_MS (default 5000),
ATOM_OPENROUTER_ENDPOINTS_TTL_SECONDS (default 600).
"""

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_ENDPOINTS_URL_TMPL = "https://openrouter.ai/api/v1/models/{slug}/endpoints"

DEFAULT_TTL_SECONDS = 600
DEFAULT_MIN_UPTIME_PERCENT = 90.0
DEFAULT_MAX_LATENCY_P50_MS = 5000.0
LATENCY_PENALTY_FACTOR = 0.75
MAX_REFRESH_SLUGS = 50

# Speed is ALWAYS secondary (operator direction, 2026-09-08): measured
# throughput only breaks ties between candidates that price/quality
# already rank equally. The factor is capped to [1 - SPEED_TIEBREAK_MAX,
# 1.0] — a slow endpoint loses at most ~15% of its value score, which the
# common 2x+ cost/quality gaps between candidates overwhelm by
# construction. ATOM_OPENROUTER_FAST_TPS sets the "no penalty" reference
# (measured p50 tokens/sec at or above it score 1.0).
DEFAULT_FAST_TPS = 150.0
SPEED_TIEBREAK_MAX = 0.15


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def telemetry_enabled() -> bool:
    """Kill switch — default ON (additive, fail-open)."""
    return os.getenv("ATOM_OPENROUTER_ENDPOINT_TELEMETRY_ENABLED", "true").lower() != "false"


def min_uptime_percent() -> float:
    """Endpoints below this measured 30-min uptime are excluded from BPC."""
    return _env_float("ATOM_OPENROUTER_MIN_UPTIME_30M", DEFAULT_MIN_UPTIME_PERCENT)


def max_latency_p50_ms() -> float:
    """p50 TTFT above this (ms) earns the soft ordering penalty."""
    return _env_float("ATOM_OPENROUTER_MAX_LATENCY_P50_MS", DEFAULT_MAX_LATENCY_P50_MS)


def fast_tps() -> float:
    """Measured p50 tokens/sec at or above this score the full 1.0 speed
    factor. Defaults to 150 (the top of glm-5.3-flash's observed 40–155
    tps provider spread)."""
    return max(1.0, _env_float("ATOM_OPENROUTER_FAST_TPS", DEFAULT_FAST_TPS))


def throughput_speed_factor(health: "EndpointHealth") -> float:
    """Capped tiebreaker: 1.0 at/above the fast reference, tapering to
    1 - SPEED_TIEBREAK_MAX for very slow endpoints. Fail-open to 1.0 when
    no throughput was measured."""
    tps = float(getattr(health, "throughput_p50", 0.0) or 0.0)
    if tps <= 0.0:
        return 1.0
    ratio = min(1.0, tps / fast_tps())
    return 1.0 - SPEED_TIEBREAK_MAX * (1.0 - ratio)


def latency_penalty_factor(health: "EndpointHealth") -> float:
    """Multiplicative value-score factor for a known-health endpoint."""
    if health.latency_ms_p50 > max_latency_p50_ms():
        return LATENCY_PENALTY_FACTOR
    return 1.0


def endpoint_health_gate(model_id: str) -> Optional[float]:
    """BPC gate for one openrouter-hosted model.

    Returns:
        None          — exclude the candidate (measured uptime below floor)
        1.0           — healthy / unknown / no data / flag off (no change)
        0 < f < 1.0   — soft ordering penalty (degraded p50 latency and/or
                        measured throughput below the fast reference — the
                        speed term is tiebreaker-capped, never dominant)
    """
    if not telemetry_enabled():
        return 1.0
    health = get_endpoint_monitor().get_health(model_id)
    if health is None:
        return 1.0
    if health.uptime_30m < min_uptime_percent():
        logger.info(
            f"BPC endpoint gate excluded {model_id} — uptime_30m="
            f"{health.uptime_30m:.2f}% < floor {min_uptime_percent():.0f}%"
        )
        return None
    return latency_penalty_factor(health) * throughput_speed_factor(health)


def slug_from_model_id(model_id: str) -> Optional[str]:
    """``author/slug[:variant]`` → ``author/slug``; author-less ids rejected."""
    base = model_id.split(":", 1)[0]
    if "/" not in base:
        return None
    return base


@dataclass
class EndpointHealth:
    """Best operational hosting endpoint for one OpenRouter model slug."""

    slug: str
    provider_name: str
    uptime_30m: float  # percent 0–100
    latency_ms_p50: float
    throughput_p50: float
    status: int


def _parse_uptime(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip().rstrip("%")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_best_endpoint(payload: Dict[str, Any], slug: str) -> Optional[EndpointHealth]:
    """Pick the best endpoint: operational first, then max uptime, then min p50."""
    endpoints = ((payload or {}).get("data") or {}).get("endpoints") or []
    best = None
    best_key: Optional[tuple] = None
    for row in endpoints:
        if not isinstance(row, dict):
            continue
        uptime = _parse_uptime(row.get("uptime_30m"))
        status = int(row.get("status", 0) or 0)
        lat = ((row.get("latency_30m_ms") or {}).get("p50"))
        thr = ((row.get("throughput_30m_tokens_per_sec") or {}).get("p50"))
        try:
            latency_p50 = float(lat) if lat is not None else float("inf")
            throughput_p50 = float(thr) if thr is not None else 0.0
        except (TypeError, ValueError):
            continue
        if uptime is None:
            continue
        # Sort key: operational first (bigger), then uptime (bigger), then
        # lower p50 latency wins ties.
        key = (1 if status == 0 else 0, uptime, -latency_p50)
        if best_key is None or key > best_key:
            best_key = key
            best = EndpointHealth(
                slug=slug,
                provider_name=str(row.get("provider") or "unknown"),
                uptime_30m=uptime,
                latency_ms_p50=latency_p50,
                throughput_p50=throughput_p50,
                status=status,
            )
    return best


class OpenRouterEndpointMonitor:
    """TTL cache of per-slug measured health; background-only refresh."""

    def __init__(self, ttl_seconds: Optional[float] = None, transport: Optional[httpx.AsyncHTTPTransport] = None):
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else _env_float(
            "ATOM_OPENROUTER_ENDPOINTS_TTL_SECONDS", DEFAULT_TTL_SECONDS)
        self._transport = transport
        self._cache: Dict[str, EndpointHealth] = {}
        self._fetched_at: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._inflight = False

    def _make_client(self) -> httpx.AsyncClient:
        kwargs: Dict[str, Any] = {"timeout": 10.0}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    def get_health(self, model_id: str) -> Optional[EndpointHealth]:
        """Sync cache read — never blocks, never raises. Miss ⇒ None."""
        slug = slug_from_model_id(model_id)
        if slug is None:
            return None
        return self._cache.get(slug)

    def _stale_slugs(self, model_ids: List[str], force: bool) -> List[str]:
        now = time.monotonic()
        slugs: List[str] = []
        seen = set()
        for mid in model_ids:
            slug = slug_from_model_id(mid or "")
            if slug is None or slug in seen:
                continue
            seen.add(slug)
            fetched_at = self._fetched_at.get(slug)
            if force or fetched_at is None or (now - fetched_at) > self.ttl_seconds:
                slugs.append(slug)
        return slugs[:MAX_REFRESH_SLUGS]

    async def refresh(self, model_ids: List[str], force: bool = False) -> int:
        """Fetch stale slugs (bounded); publish atomically. Returns fetched count."""
        slugs = self._stale_slugs(model_ids, force)
        if not slugs:
            return 0
        sem = asyncio.Semaphore(4)

        async def fetch_one(client: httpx.AsyncClient, slug: str) -> Optional[EndpointHealth]:
            async with sem:
                resp = await client.get(OPENROUTER_ENDPOINTS_URL_TMPL.format(slug=slug))
                resp.raise_for_status()
                return parse_best_endpoint(resp.json(), slug)

        fetched: Dict[str, EndpointHealth] = {}
        # Slugs that got a DEFINITIVE "no telemetry" answer (200 with an
        # empty endpoints array, or a 404). These must still mark freshness,
        # otherwise every later BPC ranking re-fetches them until data
        # appears — observed live 2026-09-09 as 37 slugs × 10 fetches
        # (370 HTTP calls) inside a single chat request, a large share of
        # that request blowing the frontend's 120s timeout.
        answered: List[str] = []
        try:
            async with self._make_client() as client:
                results = await asyncio.gather(
                    *(fetch_one(client, s) for s in slugs), return_exceptions=True
                )
        except Exception as e:  # noqa: BLE001 — fail-open by contract
            logger.debug(f"Endpoint telemetry batch failed (fail-open): {e}")
            return 0
        for slug, result in zip(slugs, results):
            if isinstance(result, BaseException):
                # A 404 is definitive (no endpoints page for the slug).
                # Everything else — 429, 5xx, timeouts, connect errors — is
                # transient: leave the slug stale so the next ranking retries.
                if isinstance(result, httpx.HTTPStatusError) and result.response.status_code == 404:
                    answered.append(slug)
                else:
                    logger.debug(f"Endpoint telemetry failed for {slug}: {result}")
                continue
            answered.append(slug)
            if result is not None:
                fetched[slug] = result
        if answered:
            now = time.monotonic()
            with self._lock:
                self._cache.update(fetched)
                for slug in answered:
                    self._fetched_at[slug] = now
        return len(fetched)

    def ensure_refresh_started(self, model_ids: List[str]) -> bool:
        """Best-effort background refresh kickoff. Sync-safe, never blocks.

        Returns True when a refresh was actually started here.
        """
        if not telemetry_enabled():
            return False
        with self._lock:
            if self._inflight:
                return False
            if not self._stale_slugs(list(model_ids), force=False):
                return False
            self._inflight = True

        async def _run() -> None:
            try:
                await self.refresh(list(model_ids), force=False)
            finally:
                with self._lock:
                    self._inflight = False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            thread = threading.Thread(
                target=lambda: asyncio.run(_run()), daemon=True, name="or-endpoint-telemetry"
            )
            thread.start()
            return True
        loop.create_task(_run())
        return True


_monitor: Optional[OpenRouterEndpointMonitor] = None


def get_endpoint_monitor() -> OpenRouterEndpointMonitor:
    """Process-global singleton (tests may swap ``openrouter_endpoints._monitor``)."""
    global _monitor
    if _monitor is None:
        _monitor = OpenRouterEndpointMonitor()
    return _monitor
