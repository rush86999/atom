"""
Coverage tests for core/circuit_breaker.py.

Covers:
- record_success / record_failure (in-memory + Redis)
- is_enabled (cooldown expiry, in-memory + Redis)
- get_stats / get_all_stats
- get_state (CLOSED/OPEN/HALF_OPEN)
- _should_disable (min_calls, consecutive, failure rate)
- reset (single + all + Redis)
- callbacks (on_open/register_on_open/on_reset/register_on_reset; sync + async)
- circuit_breaker_decorator (open/success/exception)
- Redis error fallback paths
"""
import asyncio
import json
import time
from unittest.mock import MagicMock

import pytest

from core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    IntegrationStats,
    circuit_breaker,
    circuit_breaker_decorator,
    circuit_breaker_func,
)


# ---------------------------------------------------------------------------
# Fake async Redis
# ---------------------------------------------------------------------------
class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)

    def scan_iter(self, match=None):
        import fnmatch

        keys = [k for k in list(self.store.keys()) if match is None or fnmatch.fnmatch(k, match)]

        async def gen():
            for k in keys:
                yield k

        return gen()


class BrokenRedis(FakeRedis):
    async def get(self, key):
        raise RuntimeError("redis down")

    async def set(self, key, value, ex=None):
        raise RuntimeError("redis down")

    async def delete(self, key):
        raise RuntimeError("redis down")


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------
class TestCallbacks:
    def test_on_open_and_alias(self):
        cb = CircuitBreaker()

        @cb.on_open
        def cb1(name):
            pass

        assert cb1 in cb._on_open_callbacks

        @cb.register_on_open
        def cb2(name):
            pass

        assert cb2 in cb._on_open_callbacks

    def test_on_reset_and_alias(self):
        cb = CircuitBreaker()

        @cb.on_reset
        def r1(name):
            pass

        assert r1 in cb._on_reset_callbacks

        @cb.register_on_reset
        def r2(name):
            pass

        assert r2 in cb._on_reset_callbacks


# ---------------------------------------------------------------------------
# _should_disable
# ---------------------------------------------------------------------------
class TestShouldDisable:
    @pytest.mark.asyncio
    async def test_below_min_calls(self):
        cb = CircuitBreaker(min_calls=5)
        stats = IntegrationStats(total_calls=2, failures=2, consecutive_failures=2)
        assert await cb._should_disable("x", stats) is False

    @pytest.mark.asyncio
    async def test_consecutive_failure_limit(self):
        cb = CircuitBreaker(min_calls=2, consecutive_failure_limit=3)
        stats = IntegrationStats(total_calls=5, failures=3, consecutive_failures=3)
        assert await cb._should_disable("x", stats) is True

    @pytest.mark.asyncio
    async def test_failure_rate_threshold(self):
        cb = CircuitBreaker(min_calls=5, failure_threshold=0.5, consecutive_failure_limit=100)
        stats = IntegrationStats(total_calls=10, failures=6, consecutive_failures=1)
        # 6/10 = 0.6 >= 0.5
        assert await cb._should_disable("x", stats) is True

    @pytest.mark.asyncio
    async def test_failure_rate_below_threshold(self):
        cb = CircuitBreaker(min_calls=5, failure_threshold=0.5, consecutive_failure_limit=100)
        stats = IntegrationStats(total_calls=10, failures=2, consecutive_failures=1)
        assert await cb._should_disable("x", stats) is False

    @pytest.mark.asyncio
    async def test_zero_total_calls_no_division_error(self):
        """BUG: _should_disable divided failures/total_calls without guarding
        total_calls==0. With min_calls=0 (or a freshly-seeded stats object)
        record_failure crashed with ZeroDivisionError. Must return False instead.
        """
        cb = CircuitBreaker(min_calls=0, failure_threshold=0.5, consecutive_failure_limit=100)
        stats = IntegrationStats(total_calls=0, failures=0, consecutive_failures=0)
        # Previously raised ZeroDivisionError
        assert await cb._should_disable("x", stats) is False


# ---------------------------------------------------------------------------
# record_success / record_failure (in-memory)
# ---------------------------------------------------------------------------
class TestRecordInMemory:
    @pytest.mark.asyncio
    async def test_record_success_increments_and_resets_consecutive(self):
        cb = CircuitBreaker()
        await cb.record_success("svc")
        stats = cb.stats["svc"]
        assert stats.total_calls == 1
        assert stats.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_record_failure_sets_error_fields_in_memory(self):
        """BUG: in-memory record_failure path did NOT persist last_error_type /
        last_error_message (only the Redis path did), so single-instance
        deployments always reported empty error info in get_stats().
        """
        cb = CircuitBreaker()
        err = ValueError("boom")
        await cb.record_failure("svc", err)
        stats = cb.stats["svc"]
        assert stats.total_calls == 1
        assert stats.failures == 1
        assert stats.consecutive_failures == 1
        assert stats.last_error_type == "ValueError"
        assert stats.last_error_message == "boom"
        assert stats.last_failure_time > 0

    @pytest.mark.asyncio
    async def test_record_failure_without_error(self):
        cb = CircuitBreaker()
        await cb.record_failure("svc", None)
        stats = cb.stats["svc"]
        assert stats.failures == 1
        assert stats.last_error_type == ""

    @pytest.mark.asyncio
    async def test_success_after_failure_resets_consecutive(self):
        cb = CircuitBreaker(min_calls=5, consecutive_failure_limit=3)
        await cb.record_failure("svc")
        await cb.record_success("svc")
        stats = cb.stats["svc"]
        assert stats.consecutive_failures == 0
        assert stats.total_calls == 2

    @pytest.mark.asyncio
    async def test_record_success_triggers_reenable_after_cooldown(self):
        cb = CircuitBreaker(min_calls=1, consecutive_failure_limit=1, cooldown_seconds=0.05)
        await cb.record_failure("svc")  # opens circuit
        assert "svc" in cb.disabled
        await asyncio.sleep(0.06)
        await cb.record_success("svc")  # should re-enable
        assert "svc" not in cb.disabled


# ---------------------------------------------------------------------------
# Open circuit flow (end-to-end in-memory)
# ---------------------------------------------------------------------------
class TestOpenFlow:
    @pytest.mark.asyncio
    async def test_circuit_opens_on_consecutive_failures_and_calls_callbacks(self):
        triggered = []

        cb = CircuitBreaker(
            min_calls=1, consecutive_failure_limit=2,
            failure_threshold=2.0,  # above 1.0 so rate never trips; rely on consecutive
            cooldown_seconds=60,
        )

        @cb.on_open
        def on_open(name):
            triggered.append(name)

        await cb.record_failure("svc", RuntimeError("e1"))
        assert "svc" not in cb.disabled  # not yet
        await cb.record_failure("svc", RuntimeError("e2"))
        assert "svc" in cb.disabled
        assert triggered == ["svc"]
        assert (await cb.is_enabled("svc")) is False

    @pytest.mark.asyncio
    async def test_is_enabled_true_for_unknown_integration(self):
        cb = CircuitBreaker()
        assert (await cb.is_enabled("never_seen")) is True

    @pytest.mark.asyncio
    async def test_is_enabled_false_then_true_after_cooldown(self):
        cb = CircuitBreaker(
            min_calls=1, consecutive_failure_limit=1, cooldown_seconds=0.05
        )
        await cb.record_failure("svc", RuntimeError("x"))
        assert (await cb.is_enabled("svc")) is False
        await asyncio.sleep(0.06)
        assert (await cb.is_enabled("svc")) is True


# ---------------------------------------------------------------------------
# get_state
# ---------------------------------------------------------------------------
class TestGetState:
    def test_closed_for_unknown(self):
        cb = CircuitBreaker()
        assert cb.get_state("x") == CircuitState.CLOSED

    def test_open_when_disabled(self):
        cb = CircuitBreaker()
        cb.disabled.add("x")
        assert cb.get_state("x") == CircuitState.OPEN

    def test_open_when_disabled_until_in_future(self):
        cb = CircuitBreaker()
        cb.disabled_until["x"] = time.time() + 1000
        assert cb.get_state("x") == CircuitState.OPEN

    def test_half_open_when_cooldown_expired(self):
        cb = CircuitBreaker()
        cb.disabled_until["x"] = time.time() - 1  # expired
        assert cb.get_state("x") == CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# get_stats / get_all_stats
# ---------------------------------------------------------------------------
class TestGetStats:
    @pytest.mark.asyncio
    async def test_get_stats_in_memory(self):
        cb = CircuitBreaker()
        await cb.record_failure("svc", RuntimeError("boom"))
        stats = await cb.get_stats("svc")
        assert stats["total_calls"] == 1
        assert stats["failures"] == 1
        assert stats["consecutive_failures"] == 1
        assert stats["failure_rate"] == 1.0
        assert stats["is_enabled"] is True
        assert stats["last_error_type"] == "RuntimeError"
        assert stats["disabled_until"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_zero_calls_no_div_by_zero(self):
        cb = CircuitBreaker()
        stats = await cb.get_stats("fresh")
        assert stats["failure_rate"] == 0
        assert stats["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_get_all_stats_in_memory(self):
        cb = CircuitBreaker()
        await cb.record_failure("a")
        await cb.record_success("b")
        all_stats = await cb.get_all_stats()
        assert "a" in all_stats
        assert "b" in all_stats

    @pytest.mark.asyncio
    async def test_get_all_stats_redis(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=1, consecutive_failure_limit=1)
        await cb.record_failure("redis_svc", RuntimeError("boom"))
        # stats are NOT in redis (no seed) but disabled key IS, and in-memory
        # stats exist. get_all_stats merges in-memory + redis scans.
        all_stats = await cb.get_all_stats()
        assert "redis_svc" in all_stats


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------
class TestReset:
    @pytest.mark.asyncio
    async def test_reset_single_in_memory(self):
        cb = CircuitBreaker()
        await cb.record_failure("a")
        await cb.record_failure("b")
        await cb.reset("a")
        assert "a" not in cb.stats
        assert "b" in cb.stats

    @pytest.mark.asyncio
    async def test_reset_all_in_memory(self):
        cb = CircuitBreaker()
        await cb.record_failure("a")
        await cb.reset()
        assert len(cb.stats) == 0
        assert len(cb.disabled) == 0

    @pytest.mark.asyncio
    async def test_reset_triggers_callbacks(self):
        cb = CircuitBreaker()
        events = []

        @cb.on_reset
        def on_reset(name):
            events.append(name)

        await cb.record_failure("a")
        await cb.reset("a")
        assert "a" in events

    @pytest.mark.asyncio
    async def test_reset_async_callback_awaited(self):
        cb = CircuitBreaker()
        events = []

        @cb.on_reset
        async def on_reset(name):
            await asyncio.sleep(0)
            events.append(name)

        await cb.record_failure("a")
        await cb.reset("a")
        assert "a" in events

    @pytest.mark.asyncio
    async def test_reset_callback_exception_swallowed(self):
        cb = CircuitBreaker()

        @cb.on_reset
        def bad(name):
            raise RuntimeError("callback boom")

        await cb.record_failure("a")
        # should not raise
        await cb.reset("a")

    @pytest.mark.asyncio
    async def test_reset_all_redis(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=1, consecutive_failure_limit=1)
        await cb.record_failure("a")
        await cb.record_failure("b")
        await cb.reset()
        assert len(redis.store) == 0

    @pytest.mark.asyncio
    async def test_reset_single_redis(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=1, consecutive_failure_limit=1)
        await cb.record_failure("a")
        await cb.record_failure("b")
        await cb.reset("a")
        # a disabled key removed, b remains
        assert "cb:disabled:a" not in redis.store
        assert "cb:disabled:b" in redis.store


# ---------------------------------------------------------------------------
# Redis error fallback paths
# ---------------------------------------------------------------------------
class TestRedisFallback:
    @pytest.mark.asyncio
    async def test_record_success_redis_get_fails_falls_back(self):
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis)
        await cb.record_success("svc")
        # in-memory state should be updated
        assert cb.stats["svc"].total_calls == 1

    @pytest.mark.asyncio
    async def test_record_failure_redis_get_fails_falls_back(self):
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=10, consecutive_failure_limit=100)
        await cb.record_failure("svc", RuntimeError("x"))
        assert cb.stats["svc"].failures == 1

    @pytest.mark.asyncio
    async def test_is_enabled_redis_get_fails_falls_back(self):
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis)
        # should fall back to in-memory (which says enabled)
        assert (await cb.is_enabled("svc")) is True

    @pytest.mark.asyncio
    async def test_get_stats_redis_get_fails_falls_back(self):
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis)
        await cb.record_failure("svc", RuntimeError("x"))
        stats = await cb.get_stats("svc")
        assert stats["failures"] == 1

    @pytest.mark.asyncio
    async def test_redis_disable_set_fails_falls_back(self):
        """When redis.set raises during disable, in-memory disabled state
        must still be set so the breaker opens locally."""
        redis = FakeRedis()

        async def boom_set(key, value, ex=None):
            raise RuntimeError("set failed")

        redis.set = boom_set
        cb = CircuitBreaker(redis_client=redis, min_calls=1, consecutive_failure_limit=1)
        await cb.record_failure("svc", RuntimeError("x"))
        # in-memory disabled must be set even though redis.set failed
        assert "svc" in cb.disabled

    @pytest.mark.asyncio
    async def test_get_all_stats_redis_scan_fails(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)

        async def boom_scan(match=None):
            raise RuntimeError("scan failed")
            yield  # make it a generator

        redis.scan_iter = lambda match=None: boom_scan(match)
        # should not raise
        all_stats = await cb.get_all_stats()
        assert isinstance(all_stats, dict)

    @pytest.mark.asyncio
    async def test_reset_all_redis_scan_fails_handled(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)

        async def boom_scan(match=None):
            raise RuntimeError("scan failed")
            yield

        redis.scan_iter = lambda match=None: boom_scan(match)
        await cb.reset()  # no raise


# ---------------------------------------------------------------------------
# Redis happy paths for coverage
# ---------------------------------------------------------------------------
class TestRedisHappy:
    @pytest.mark.asyncio
    async def test_record_success_redis(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)
        # Seed redis with an existing stats entry so the redis code path is taken
        redis.store["cb:stats:svc"] = json.dumps(
            {"total_calls": 0, "failures": 0, "last_failure_time": 0,
             "consecutive_failures": 0, "last_error_type": "", "last_error_message": ""}
        )
        await cb.record_success("svc")
        # stats persisted in redis
        stored = json.loads(redis.store["cb:stats:svc"])
        assert stored["total_calls"] == 1
        assert stored["consecutive_failures"] == 0

    @pytest.mark.asyncio
    async def test_record_failure_redis_persists_error(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=10, consecutive_failure_limit=100)
        redis.store["cb:stats:svc"] = json.dumps(
            {"total_calls": 0, "failures": 0, "last_failure_time": 0,
             "consecutive_failures": 0, "last_error_type": "", "last_error_message": ""}
        )
        await cb.record_failure("svc", ValueError("err"))
        stored = json.loads(redis.store["cb:stats:svc"])
        assert stored["failures"] == 1
        assert stored["last_error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_redis_is_enabled_cooldown_passed_reenables(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)
        # set disabled key in the past
        redis.store["cb:disabled:svc"] = str(time.time() - 10)
        result = await cb.is_enabled("svc")
        assert result is True
        # key should be deleted
        assert "cb:disabled:svc" not in redis.store

    @pytest.mark.asyncio
    async def test_redis_try_reenable_redis_disabled_in_past(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)
        redis.store["cb:disabled:svc"] = str(time.time() - 10)
        result = await cb._try_reenable("svc")
        # disabled_until in the past -> redis deletes, then in-memory path:
        # integration not in self.disabled -> returns True
        assert result is True
        assert "cb:disabled:svc" not in redis.store

    @pytest.mark.asyncio
    async def test_redis_try_reenable_still_in_cooldown(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)
        redis.store["cb:disabled:svc"] = str(time.time() + 1000)
        result = await cb._try_reenable("svc")
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_disable_persists_disabled_key(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=1, consecutive_failure_limit=1)
        await cb.record_failure("svc", RuntimeError("x"))
        assert "cb:disabled:svc" in redis.store


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------
class TestDecorator:
    @pytest.mark.asyncio
    async def test_decorator_records_success(self):
        @circuit_breaker_decorator("svc")
        async def call(**kwargs):
            return {"ok": True}

        result = await call()
        assert result == {"ok": True}
        # global circuit_breaker recorded success
        stats = await circuit_breaker.get_stats("svc")
        assert stats["total_calls"] >= 1

    @pytest.mark.asyncio
    async def test_decorator_records_failure_and_reraises(self):
        breaker = CircuitBreaker()

        @circuit_breaker_decorator("svc2")
        async def call(**kwargs):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await call(circuit_breaker=breaker)
        stats = await breaker.get_stats("svc2")
        assert stats["failures"] == 1

    @pytest.mark.asyncio
    async def test_decorator_blocks_when_open(self):
        breaker = CircuitBreaker(
            min_calls=1, consecutive_failure_limit=1, cooldown_seconds=60
        )
        # force open
        await breaker.record_failure("svc3", RuntimeError("x"))
        assert (await breaker.is_enabled("svc3")) is False

        @circuit_breaker_decorator("svc3")
        async def call(**kwargs):
            return {"ok": True}

        result = await call(circuit_breaker=breaker)
        assert result["success"] is False
        assert "temporarily disabled" in result["error"]

    def test_circuit_breaker_func_alias(self):
        assert circuit_breaker_func is circuit_breaker_decorator


class TestGlobalInstance:
    def test_global_circuit_breaker_exists(self):
        assert circuit_breaker is not None
        assert isinstance(circuit_breaker, CircuitBreaker)


# ---------------------------------------------------------------------------
# Targeted branch coverage for remaining lines
# ---------------------------------------------------------------------------
class TestBranchCoverage:
    @pytest.mark.asyncio
    async def test_get_stats_from_redis_invalid_json(self):
        """_get_stats_from_redis returns None when stored JSON is corrupt."""
        redis = FakeRedis()
        redis.store["cb:stats:svc"] = "not valid json{"
        cb = CircuitBreaker(redis_client=redis)
        stats = await cb._get_stats_from_redis("svc")
        assert stats is None

    @pytest.mark.asyncio
    async def test_save_stats_to_redis_failure_swallowed(self):
        """_save_stats_to_redis must not raise when redis.set fails."""
        redis = FakeRedis()

        async def boom(key, value, ex=None):
            raise RuntimeError("set failed")

        redis.set = boom
        cb = CircuitBreaker(redis_client=redis)
        stats = IntegrationStats(total_calls=1, failures=1)
        # should not raise
        await cb._save_stats_to_redis("svc", stats)

    @pytest.mark.asyncio
    async def test_is_enabled_redis_get_raises_falls_back(self):
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis)
        # Falls back to in-memory (enabled)
        assert (await cb.is_enabled("svc")) is True

    @pytest.mark.asyncio
    async def test_try_reenable_redis_get_raises_falls_back(self):
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis)
        # integration not in in-memory disabled -> returns True
        assert (await cb._try_reenable("svc")) is True

    @pytest.mark.asyncio
    async def test_try_reenable_redis_disabled_present_falls_back(self):
        """_try_reenable: redis.get raises -> except branch -> in-memory path."""
        redis = BrokenRedis()
        cb = CircuitBreaker(redis_client=redis)
        # put in in-memory disabled state with future expiry
        cb.disabled.add("svc")
        cb.disabled_until["svc"] = time.time() + 1000
        assert (await cb._try_reenable("svc")) is False

    @pytest.mark.asyncio
    async def test_get_all_stats_redis_present_and_inmemory(self):
        """get_all_stats merges redis-scanned entries with in-memory entries."""
        redis = FakeRedis()
        # Seed an entry directly in redis stats
        redis.store["cb:stats:from_redis"] = json.dumps(
            {"total_calls": 5, "failures": 2, "last_failure_time": 0,
             "consecutive_failures": 0, "last_error_type": "", "last_error_message": ""}
        )
        cb = CircuitBreaker(redis_client=redis)
        # Also add an in-memory entry
        await cb.record_success("from_inmemory")
        all_stats = await cb.get_all_stats()
        assert "from_redis" in all_stats
        assert "from_inmemory" in all_stats

    @pytest.mark.asyncio
    async def test_disable_async_callback_invoked(self):
        """Cover async on_open callback branch in _disable_integration."""
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis, min_calls=1, consecutive_failure_limit=1)
        called = []

        @cb.on_open
        async def on_open(name):
            called.append(name)

        await cb.record_failure("svc", RuntimeError("x"))
        assert called == ["svc"]

    @pytest.mark.asyncio
    async def test_disable_callback_exception_swallowed(self):
        """Cover callback exception branch in _disable_integration."""
        cb = CircuitBreaker(min_calls=1, consecutive_failure_limit=1)

        @cb.on_open
        def bad(name):
            raise RuntimeError("callback boom")

        # must not raise
        await cb.record_failure("svc", RuntimeError("x"))
        assert "svc" in cb.disabled

    @pytest.mark.asyncio
    async def test_try_reenable_redis_still_in_cooldown(self):
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)
        redis.store["cb:disabled:svc"] = str(time.time() + 1000)
        # integration not in in-memory disabled; redis says still in cooldown -> False
        result = await cb._try_reenable("svc")
        assert result is False

    @pytest.mark.asyncio
    async def test_try_reenable_redis_disabled_present_in_past(self):
        """redis disabled key present but in the past -> redis deletes, returns
        through the in-memory path (not in disabled) -> True."""
        redis = FakeRedis()
        cb = CircuitBreaker(redis_client=redis)
        redis.store["cb:disabled:svc"] = str(time.time() - 10)
        result = await cb._try_reenable("svc")
        assert result is True
        assert "cb:disabled:svc" not in redis.store
