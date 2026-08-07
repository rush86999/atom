"""Round 80 — ProviderHealthService coverage (LLM registry circuit breaker).

TDD targets:
- B3: ``record_success`` recovery only checked UNHEALTHY/DEGRADED states, so
  a provider that ever hit a ``rate_limited`` error stayed RATE_LIMITED
  (routing priority 2) forever — even after 10+ consecutive successes.
  Fixed: RATE_LIMITED participates in recovery.
- B4: ``get_health_state`` crashed with ``ValueError`` on any unknown/corrupt
  stored state string (e.g. a stale payload or a future enum value) — a
  single bad row took down the health check. Fixed: unknown state falls back
  to HEALTHY instead of raising.
"""
from __future__ import annotations

from core.llm.registry.provider_health import (
    CONSECUTIVE_FAILURES_THRESHOLD,
    CONSECUTIVE_SUCCESSES_RECOVERY,
    DEGRADED_ERROR_RATE,
    HEALTH_STATE_TTL,
    HealthState,
    ProviderHealthService,
)


class _FakeCache:
    """Dict-backed async cache faithful to UniversalCacheService's contract
    (get/set/delete of string values with TTL)."""

    def __init__(self, seed: dict | None = None):
        self._store = dict(seed or {})
        self.writes: list[tuple[str, str, int]] = []

    async def get_async(self, key: str, tenant_id: str | None = None):
        return self._store.get(key)

    async def set_async(self, key: str, value, ttl: int = 300, tenant_id: str | None = None) -> bool:
        self._store[key] = value
        self.writes.append((key, value, ttl))
        return True

    async def delete_async(self, key: str, tenant_id: str | None = None):
        self._store.pop(key, None)

    def last_state(self) -> str:
        import json

        return json.loads(self.writes[-1][1])["current_state"]


def _state_payload(state: HealthState, **overrides) -> dict:
    payload = {
        "current_state": state.value,
        "success_count": 0,
        "error_count": 0,
        "consecutive_failures": 0,
        "consecutive_successes": 0,
        "avg_latency_ms": None,
    }
    payload.update(overrides)
    return payload


class TestRecordSuccess:
    async def test_first_request_becomes_healthy(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=100)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_tracks_latency_and_streaks(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=100)
        await svc.record_success("openai", latency_ms=300)
        import json

        data = json.loads(cache.writes[-1][1])
        assert data["success_count"] == 2
        assert data["consecutive_successes"] == 2
        assert data["consecutive_failures"] == 0
        assert abs(data["avg_latency_ms"] - 200.0) < 1e-9
        assert data["last_success_ts"] is not None

    async def test_success_resets_failure_streak(self):
        cache = _FakeCache(seed={
            "llm_registry:provider_health:openai": '{"current_state": "unhealthy", "success_count": 3, "error_count": 6, "consecutive_failures": 5, "consecutive_successes": 0, "avg_latency_ms": 100}'
        })
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        import json

        data = json.loads(cache.writes[-1][1])
        assert data["consecutive_failures"] == 0
        assert data["consecutive_successes"] == 1

    async def test_unhealthy_recovers_after_threshold_successes(self):
        seed = _state_payload(HealthState.UNHEALTHY, success_count=3, error_count=6,
                              consecutive_failures=5,
                              consecutive_successes=CONSECUTIVE_SUCCESSES_RECOVERY - 1)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_unhealthy_does_not_recover_below_threshold(self):
        seed = _state_payload(HealthState.UNHEALTHY, success_count=3, error_count=6,
                              consecutive_failures=5, consecutive_successes=3)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.UNHEALTHY.value

    async def test_degraded_recovers_after_threshold_successes(self):
        seed = _state_payload(HealthState.DEGRADED, success_count=30, error_count=4,
                              consecutive_failures=0,
                              consecutive_successes=CONSECUTIVE_SUCCESSES_RECOVERY - 1)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    # ------------------------------------------------------------------ #
    # B3: RATE_LIMITED must recover like every other degraded state.
    # ------------------------------------------------------------------ #
    async def test_b3_rate_limited_recovers_after_threshold_successes(self):
        seed = _state_payload(HealthState.RATE_LIMITED, success_count=40, error_count=1,
                              consecutive_failures=0,
                              consecutive_successes=CONSECUTIVE_SUCCESSES_RECOVERY - 1)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.HEALTHY.value

    async def test_b3_rate_limited_stays_limited_below_threshold(self):
        seed = _state_payload(HealthState.RATE_LIMITED, success_count=40, error_count=1,
                              consecutive_failures=0, consecutive_successes=2)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.last_state() == HealthState.RATE_LIMITED.value


class TestRecordFailure:
    async def test_first_failure_tracks_counters(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="timeout")
        import json

        data = json.loads(cache.writes[-1][1])
        assert data["error_count"] == 1
        assert data["consecutive_failures"] == 1
        assert data["consecutive_successes"] == 0
        assert data["last_error"] == "timeout"
        assert data["last_error_ts"] is not None
        # No state transition on a single failure → still reads as HEALTHY.
        assert await svc.get_health_state("openai") == HealthState.HEALTHY

    async def test_consecutive_failures_reach_unhealthy(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        for i in range(CONSECUTIVE_FAILURES_THRESHOLD):
            await svc.record_failure("openai", error="api_error")
        assert cache.last_state() == HealthState.UNHEALTHY.value

    async def test_rate_limited_error_sets_rate_limited_state(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="rate_limited")
        assert cache.last_state() == HealthState.RATE_LIMITED.value

    async def test_error_rate_degraded_with_enough_samples(self):
        seed = _state_payload(HealthState.HEALTHY, success_count=20, error_count=1)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="api_error")  # 2/22 ≈ 0.09 → below 0.1
        await svc.record_failure("openai", error="api_error")  # 3/23 ≈ 0.13 → degraded
        assert cache.last_state() == HealthState.DEGRADED.value

    async def test_error_rate_unhealthy_with_enough_samples(self):
        seed = _state_payload(HealthState.HEALTHY, success_count=10, error_count=1)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_failure("openai", error="api_error")  # 2/12 ≈ 0.17
        await svc.record_failure("openai", error="api_error")  # 3/13 ≈ 0.23
        await svc.record_failure("openai", error="api_error")  # 4/14 ≈ 0.29 — still < 0.3
        assert cache.last_state() != HealthState.UNHEALTHY.value
        await svc.record_failure("openai", error="api_error")  # 5/15 ≈ 0.33 → unhealthy
        assert cache.last_state() == HealthState.UNHEALTHY.value

    async def test_no_state_flip_below_minimum_samples(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        await svc.record_success("openai", latency_ms=50)
        await svc.record_failure("openai", error="timeout")
        assert cache.last_state() == HealthState.HEALTHY.value


class TestHealthStateReads:
    async def test_default_state_for_unknown_provider(self):
        svc = ProviderHealthService(cache_service=_FakeCache())
        assert await svc.get_health_state("nobody") == HealthState.HEALTHY

    async def test_get_health_state_round_trip(self):
        seed = _state_payload(HealthState.DEGRADED, success_count=20, error_count=4)
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        assert await svc.get_health_state("openai") == HealthState.DEGRADED

    # ------------------------------------------------------------------ #
    # B4: corrupt/unknown stored state must not crash the health check.
    # ------------------------------------------------------------------ #
    async def test_b4_get_health_state_unknown_value_does_not_crash(self):
        cache = _FakeCache(seed={
            "llm_registry:provider_health:openai": '{"current_state": "swapping", "success_count": 2}'
        })
        svc = ProviderHealthService(cache_service=cache)
        state = await svc.get_health_state("openai")
        assert state == HealthState.HEALTHY

    async def test_get_health_metrics_unknown_value_does_not_crash(self):
        cache = _FakeCache(seed={
            "llm_registry:provider_health:openai": '{"current_state": "exploded", "success_count": 2}'
        })
        svc = ProviderHealthService(cache_service=cache)
        metrics = await svc.get_health_metrics("openai")
        assert metrics["state"] == HealthState.HEALTHY.value

    async def test_corrupt_json_treated_as_missing(self):
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": "{not json"})
        svc = ProviderHealthService(cache_service=cache)
        assert await svc.get_health_state("openai") == HealthState.HEALTHY
        metrics = await svc.get_health_metrics("openai")
        assert metrics["state"] == HealthState.HEALTHY.value
        assert metrics["success_count"] == 0

    async def test_get_health_metrics_full_shape(self):
        seed = _state_payload(HealthState.RATE_LIMITED, success_count=40, error_count=2,
                              consecutive_failures=1, consecutive_successes=5,
                              avg_latency_ms=120.5, last_error="rate_limited")
        cache = _FakeCache(seed={"llm_registry:provider_health:openai": _json(seed)})
        svc = ProviderHealthService(cache_service=cache)
        m = await svc.get_health_metrics("openai")
        assert m["provider"] == "openai"
        assert m["state"] == HealthState.RATE_LIMITED.value
        assert m["success_count"] == 40
        assert m["error_count"] == 2
        assert m["consecutive_failures"] == 1
        assert m["consecutive_successes"] == 5
        assert m["avg_latency_ms"] == 120.5
        assert m["last_error"] == "rate_limited"

    async def test_get_all_health_maps_providers(self):
        cache = _FakeCache(seed={
            "llm_registry:provider_health:openai": '{"current_state": "healthy", "success_count": 5, "error_count": 0, "consecutive_failures": 0, "consecutive_successes": 5}',
            "llm_registry:provider_health:anthropic": '{"current_state": "unhealthy", "success_count": 1, "error_count": 5, "consecutive_failures": 5, "consecutive_successes": 0}',
        })
        svc = ProviderHealthService(cache_service=cache)
        all_health = await svc.get_all_health(["openai", "anthropic", "missing"])
        assert all_health["openai"]["state"] == HealthState.HEALTHY.value
        assert all_health["anthropic"]["state"] == HealthState.UNHEALTHY.value
        assert all_health["missing"]["state"] == HealthState.HEALTHY.value


class TestPriorityAndKeying:
    def test_priority_ordering(self):
        svc = ProviderHealthService(cache_service=_FakeCache())
        assert svc.get_health_priority(HealthState.HEALTHY) == 0
        assert svc.get_health_priority(HealthState.DEGRADED) == 1
        assert svc.get_health_priority(HealthState.RATE_LIMITED) == 2
        assert svc.get_health_priority(HealthState.UNHEALTHY) == 3

    def test_key_prefix(self):
        svc = ProviderHealthService(cache_service=_FakeCache())
        assert svc._get_key("openai") == "llm_registry:provider_health:openai"

    async def test_health_data_stored_with_ttl(self):
        cache = _FakeCache()
        svc = ProviderHealthService(cache_service=cache)
        await svc.record_success("openai", latency_ms=50)
        assert cache.writes[-1][2] == HEALTH_STATE_TTL

    async def test_threshold_constants_sane(self):
        assert CONSECUTIVE_FAILURES_THRESHOLD == 5
        assert CONSECUTIVE_SUCCESSES_RECOVERY == 10
        assert DEGRADED_ERROR_RATE == 0.1


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload)
