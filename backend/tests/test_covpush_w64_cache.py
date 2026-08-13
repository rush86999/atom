"""Coverage wave 64 — core/cache.py (TDD, mocked redis/httpx, no network).

Covers the RedisCircuitBreaker state machine (closed -> open -> half-open
-> closed), SyncLocalCache LRU/TTL semantics, UniversalCacheService env
initialization (direct Redis / Upstash REST / local fallback / disabled),
sync+async get/set/delete/incr with tenant namespacing, the REST API
helpers, get_status health reporting, and delete_tenant_all tenant-scoped
purging (regression: it referenced non-existent `_store`/`_lock` attrs and
raised AttributeError on every call).
"""
import importlib
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import core.cache as cache_module
from core.cache import (
    CircuitState,
    CircuitBreakerOpenError,
    RedisCircuitBreaker,
    SyncLocalCache,
    UniversalCacheService,
)


class FakeSocketKeepAlive:
    TCP_KEEPINTVL = 10
    TCP_KEEPCNT = 3
    TCP_KEEPALIVE = 60


class FakeSocketKeepIdle:
    TCP_KEEPINTVL = 10
    TCP_KEEPCNT = 3
    TCP_KEEPIDLE = 60


class FakeSocketMinimal:
    TCP_KEEPINTVL = 10
    TCP_KEEPCNT = 3


def make_fake_redis_client(**kw):
    client = MagicMock()
    client.ping.return_value = True
    for k, v in kw.items():
        setattr(client, k, v)
    return client


def http_ok(payload=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload if payload is not None else {"result": "val"}
    return resp


@pytest.fixture
def make_service(monkeypatch):
    prev = UniversalCacheService._instance

    def _make(env=None):
        UniversalCacheService._instance = None
        env = env or {}
        monkeypatch.setenv("ENABLE_CACHE", str(env.get("ENABLE_CACHE", "true")).lower())
        for var in (
            "DRAGONFLY_URL", "CACHE_REDIS_URL", "REDIS_URL",
            "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN",
            "REDIS_CIRCUIT_THRESHOLD", "REDIS_CIRCUIT_TIMEOUT",
            "LOCAL_CACHE_SIZE", "LOCAL_CACHE_TTL",
        ):
            if var in env:
                monkeypatch.setenv(var, str(env[var]))
            else:
                monkeypatch.delenv(var, raising=False)
        return UniversalCacheService()

    yield _make
    UniversalCacheService._instance = prev


def local_service(make_service):
    return make_service({"ENABLE_CACHE": "true"})


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        assert RedisCircuitBreaker().get_state() == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        breaker = RedisCircuitBreaker(failure_threshold=2)
        failing = lambda: (_ for _ in ()).throw(ConnectionError("boom"))
        with pytest.raises(ConnectionError):
            breaker.call(failing)
        with pytest.raises(ConnectionError):
            breaker.call(failing)
        assert breaker.get_state() == CircuitState.OPEN
        assert breaker._failure_count == 2
        breaker._state = CircuitState.CLOSED
        breaker._failure_count = 2
        assert breaker.call(lambda: "ok") == "ok"
        assert breaker._failure_count == 0
        assert breaker.get_state() == CircuitState.CLOSED

    def test_failures_open_circuit_and_reject(self):
        breaker = RedisCircuitBreaker(failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert breaker.get_state() == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "never")

    def test_open_transitions_to_half_open_after_timeout(self):
        breaker = RedisCircuitBreaker(failure_threshold=1, recovery_timeout=0.5)
        with pytest.raises(RuntimeError):
            breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert breaker.get_state() == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(lambda: "never")
        time.sleep(0.6)
        assert breaker.call(lambda: "recovered") == "recovered"
        assert breaker.get_state() == CircuitState.CLOSED

    def test_half_open_success_closes(self):
        breaker = RedisCircuitBreaker()
        breaker._state = CircuitState.HALF_OPEN
        breaker._failure_count = 2
        breaker.call(lambda: "ok")
        assert breaker.get_state() == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_half_open_failure_reopens_after_threshold(self):
        breaker = RedisCircuitBreaker(failure_threshold=2)
        breaker._state = CircuitState.HALF_OPEN
        breaker._failure_count = 0
        failing = lambda: (_ for _ in ()).throw(ConnectionError("boom"))
        with pytest.raises(ConnectionError):
            breaker.call(failing)
        assert breaker.get_state() == CircuitState.HALF_OPEN
        assert breaker._failure_count == 1
        assert breaker._last_failure_time is not None
        with pytest.raises(ConnectionError):
            breaker.call(failing)
        assert breaker.get_state() == CircuitState.OPEN

    def test_reset_manually_closes(self):
        breaker = RedisCircuitBreaker(failure_threshold=1)
        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert breaker.get_state() == CircuitState.OPEN
        breaker.reset()
        assert breaker.get_state() == CircuitState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._last_failure_time is None
        assert breaker.call(lambda: "ok") == "ok"

    def test_open_with_no_last_failure_attempts_reset(self):
        breaker = RedisCircuitBreaker()
        breaker._state = CircuitState.OPEN
        breaker._last_failure_time = None
        assert breaker._should_attempt_reset() is True
        assert breaker.call(lambda: "ok") == "ok"
        assert breaker.get_state() == CircuitState.CLOSED

    def test_should_attempt_reset_waits_for_timeout(self):
        breaker = RedisCircuitBreaker(recovery_timeout=3600)
        breaker._state = CircuitState.OPEN
        breaker._last_failure_time = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        assert breaker._should_attempt_reset() is False

    def test_expected_exception_mismatch_propagates_uncounted(self):
        breaker = RedisCircuitBreaker(expected_exception=ValueError)
        with pytest.raises(TypeError):
            breaker.call(lambda: (_ for _ in ()).throw(TypeError("wrong")))
        assert breaker._failure_count == 0
        assert breaker.get_state() == CircuitState.CLOSED

    def test_call_runs_func_and_returns_result(self):
        breaker = RedisCircuitBreaker()
        assert breaker.call(lambda a, b=2: a + b, 3) == 5


class TestSyncLocalCache:
    def test_miss_increments_misses(self):
        cache = SyncLocalCache()
        assert cache.get("nope") is None
        assert cache.misses == 1
        assert cache.hits == 0

    def test_set_get_roundtrip(self):
        cache = SyncLocalCache(default_ttl=60)
        cache.set("k", "v")
        assert cache.get("k") == "v"
        assert cache.hits == 1
        assert cache.misses == 0

    def test_expired_entry_is_one_miss_and_deleted(self):
        cache = SyncLocalCache()
        cache.set("k", "v", ttl=60)
        cache._expire_times["k"] = time.time() - 1
        assert cache.get("k") is None
        assert cache.misses == 1
        assert "k" not in cache._cache

    def test_ttl_zero_falls_back_to_default(self):
        cache = SyncLocalCache(default_ttl=60)
        cache.set("k", "v", ttl=0)
        assert cache._expire_times["k"] > time.time() + 59

    def test_lru_eviction_of_oldest(self):
        cache = SyncLocalCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_update_moves_key_to_mru(self):
        cache = SyncLocalCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("a", 10)
        cache.set("c", 3)
        assert cache.get("a") == 10
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_delete(self):
        cache = SyncLocalCache()
        cache.set("k", "v")
        cache.delete("k")
        assert cache.get("k") is None
        assert "k" not in cache._expire_times

    def test_clear_resets_stats(self):
        cache = SyncLocalCache()
        cache.set("k", "v")
        assert cache.get("k") == "v"
        cache.clear()
        assert cache._cache == {}
        assert cache._expire_times == {}
        assert cache.hits == 0
        assert cache.misses == 0

    def test_has_lock(self):
        assert SyncLocalCache()._lock is not None


class TestSingleton:
    def test_singleton_returns_same_instance(self, make_service):
        svc = local_service(make_service)
        assert UniversalCacheService() is svc

    def test_singleton_reset_creates_fresh(self, make_service):
        svc = local_service(make_service)
        UniversalCacheService._instance = None
        svc2 = UniversalCacheService()
        assert svc2 is not svc
        assert svc2.client is None


class TestInitialization:
    def test_connects_direct_redis(self, make_service):
        fake_client = make_fake_redis_client()
        with patch.object(cache_module.redis, "from_url", return_value=fake_client) as m:
            svc = make_service({"REDIS_URL": "redis://localhost:6379/0"})
        m.assert_called_once()
        kwargs = m.call_args[1]
        assert kwargs["decode_responses"] is True
        assert kwargs["socket_connect_timeout"] == 5
        assert svc.client is fake_client
        fake_client.ping.assert_called_once()

    def test_dragonfly_url_priority(self, make_service):
        fake_client = make_fake_redis_client()
        with patch.object(cache_module.redis, "from_url", return_value=fake_client) as m:
            make_service({
                "DRAGONFLY_URL": "redis://dragonfly:6379/0",
                "CACHE_REDIS_URL": "redis://cache:6379/0",
                "REDIS_URL": "redis://legacy:6379/0",
            })
        assert m.call_args[0][0] == "redis://dragonfly:6379/0"

    def test_keepalive_tcp_keepalive_branch(self, make_service, monkeypatch):
        fake_client = make_fake_redis_client()
        monkeypatch.setattr(cache_module, "socket", FakeSocketKeepAlive)
        with patch.object(cache_module.redis, "from_url", return_value=fake_client) as m:
            make_service({"REDIS_URL": "redis://x:1/0"})
        options = m.call_args[1]["socket_keepalive_options"]
        assert options[FakeSocketKeepAlive.TCP_KEEPALIVE] == 60
        assert FakeSocketKeepAlive.TCP_KEEPINTVL in options

    def test_keepalive_tcp_keepidle_branch(self, make_service, monkeypatch):
        fake_client = make_fake_redis_client()
        monkeypatch.setattr(cache_module, "socket", FakeSocketKeepIdle)
        with patch.object(cache_module.redis, "from_url", return_value=fake_client) as m:
            make_service({"REDIS_URL": "redis://x:1/0"})
        options = m.call_args[1]["socket_keepalive_options"]
        assert options[FakeSocketKeepIdle.TCP_KEEPIDLE] == 60

    def test_keepalive_neither_branch(self, make_service, monkeypatch):
        fake_client = make_fake_redis_client()
        monkeypatch.setattr(cache_module, "socket", FakeSocketMinimal)
        with patch.object(cache_module.redis, "from_url", return_value=fake_client) as m:
            make_service({"REDIS_URL": "redis://x:1/0"})
        options = m.call_args[1]["socket_keepalive_options"]
        assert set(options) == {FakeSocketMinimal.TCP_KEEPINTVL, FakeSocketMinimal.TCP_KEEPCNT}

    def test_redis_connect_failure_falls_back(self, make_service):
        with patch.object(cache_module.redis, "from_url", side_effect=ConnectionError("refused")):
            svc = make_service({"REDIS_URL": "redis://bad:1/0"})
        assert svc.client is None
        assert svc.use_rest_api is False
        assert svc.enabled is True

    def test_upstash_rest_fallback(self, make_service):
        svc = make_service({
            "UPSTASH_REDIS_REST_URL": "https://us1-clean-dog-12345.upstash.io",
            "UPSTASH_REDIS_REST_TOKEN": "tok",
        })
        assert svc.use_rest_api is True
        assert svc.client is None

    def test_disabled_via_env(self, make_service):
        svc = make_service({"ENABLE_CACHE": "false"})
        assert svc.enabled is False
        assert svc.client is None

    def test_no_distributed_cache_uses_local(self, make_service):
        svc = local_service(make_service)
        assert svc.enabled is True
        assert svc.client is None
        assert svc.use_rest_api is False

    def test_circuit_breaker_env_knobs(self, make_service):
        svc = make_service({"REDIS_CIRCUIT_THRESHOLD": "5", "REDIS_CIRCUIT_TIMEOUT": "99"})
        assert svc.circuit_breaker.failure_threshold == 5
        assert svc.circuit_breaker.recovery_timeout == 99

    def test_local_cache_env_knobs(self, make_service):
        svc = make_service({"LOCAL_CACHE_SIZE": "10", "LOCAL_CACHE_TTL": "30"})
        assert svc.sync_local_cache.max_size == 10
        assert svc.sync_local_cache.default_ttl == 30
        assert svc.async_local_cache.max_size == 10


class TestNamespaceKey:
    def test_with_tenant(self):
        svc = SimpleNamespace()
        assert UniversalCacheService._namespace_key(svc, "k", "t1") == "tenant:t1:k"

    def test_without_tenant(self):
        svc = SimpleNamespace()
        assert UniversalCacheService._namespace_key(svc, "k") == "k"


class TestEncodeDecode:
    def test_encode_dict_and_list(self):
        assert UniversalCacheService._encode(None, {"a": 1}) == '{"a": 1}'
        assert UniversalCacheService._encode(None, [1, 2]) == "[1, 2]"

    def test_encode_scalar(self):
        assert UniversalCacheService._encode(None, 42) == "42"
        assert UniversalCacheService._encode(None, None) == "None"
        assert UniversalCacheService._encode(None, "str") == "str"

    def test_decode_json(self):
        assert UniversalCacheService._decode(None, '{"a": 1}') == {"a": 1}

    def test_decode_plain_string(self):
        assert UniversalCacheService._decode(None, "plain") == "plain"

    def test_decode_non_string(self):
        assert UniversalCacheService._decode(None, 123) == 123


class TestAsyncCrud:
    def test_roundtrip_dict(self, make_service):
        svc = local_service(make_service)
        assert await_helper(svc.set_async("k", {"a": 1})) is True
        assert await_helper(svc.get_async("k")) == {"a": 1}

    def test_roundtrip_list_and_string(self, make_service):
        svc = local_service(make_service)
        await_helper(svc.set_async("l", [1, 2]))
        await_helper(svc.set_async("s", "hello"))
        assert await_helper(svc.get_async("l")) == [1, 2]
        assert await_helper(svc.get_async("s")) == "hello"

    def test_miss_returns_none(self, make_service):
        svc = local_service(make_service)
        assert await_helper(svc.get_async("nope")) is None

    def test_disabled(self, make_service):
        svc = make_service({"ENABLE_CACHE": "false"})
        assert await_helper(svc.get_async("k")) is None
        assert await_helper(svc.set_async("k", "v")) is False
        assert await_helper(svc.incr_async("k")) == 1

    def test_tenant_isolation(self, make_service):
        svc = local_service(make_service)
        await_helper(svc.set_async("k", "t1-val", tenant_id="t1"))
        assert await_helper(svc.get_async("k", tenant_id="t1")) == "t1-val"
        assert await_helper(svc.get_async("k")) is None
        assert await_helper(svc.get_async("k", tenant_id="t2")) is None

    def test_client_hit(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.return_value = '{"a": 1}'
        assert await_helper(svc.get_async("k")) == {"a": 1}
        svc.client.get.assert_called_once_with("k")

    def test_client_miss_falls_to_local(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.return_value = None
        await_helper(svc.set_async("k", "local"))
        assert await_helper(svc.get_async("k")) == "local"

    def test_client_exception_falls_to_local(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.side_effect = ConnectionError("down")
        await_helper(svc.set_async("k", "local"))
        assert await_helper(svc.get_async("k")) == "local"

    def test_breaker_open_falls_to_local(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        for _ in range(3):
            with pytest.raises(ConnectionError):
                svc.circuit_breaker.call(lambda: (_ for _ in ()).throw(ConnectionError("boom")))
        await_helper(svc.set_async("k", "local"))
        assert await_helper(svc.get_async("k")) == "local"
        assert svc.circuit_breaker.get_state() == CircuitState.OPEN

    def test_delete_async(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.return_value = None
        await_helper(svc.set_async("k", "v"))
        await_helper(svc.delete_async("k"))
        assert await_helper(svc.get_async("k")) is None
        svc.client.delete.assert_called_once_with("k")

    def test_delete_async_client_exception_tolerated(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.delete.side_effect = ConnectionError("down")
        await_helper(svc.delete_async("k"))

    def test_get_async_rest_hit(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": '{"a": 1}'})):
            assert await_helper(svc.get_async("k")) == {"a": 1}

    def test_get_async_rest_miss_falls_to_local(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        await_helper(svc.set_async("k", "local"))
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": None})):
            assert await_helper(svc.get_async("k")) == "local"

    def test_set_async_writes_rest(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "post", return_value=http_ok()) as m:
            assert await_helper(svc.set_async("k", {"a": 1}, ttl=30)) is True
        m.assert_called_once_with(
            "https://rest.example.com/set/k",
            headers={"Authorization": "Bearer tok"},
            params={"ex": 30},
            content='{"a": 1}',
            timeout=2.0,
        )

    def test_delete_async_writes_rest(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "get", return_value=http_ok()) as m:
            await_helper(svc.delete_async("k"))
        assert m.call_args[0][0] == "https://rest.example.com/del/k"


class TestSyncCrud:
    def test_roundtrip(self, make_service):
        svc = local_service(make_service)
        assert svc.set("k", "v") is True
        assert svc.get("k") == "v"

    def test_disabled(self, make_service):
        svc = make_service({"ENABLE_CACHE": "false"})
        assert svc.get("k") is None
        assert svc.set("k", "v") is False

    def test_tenant_isolation(self, make_service):
        svc = local_service(make_service)
        svc.set("k", "t1-val", tenant_id="t1")
        assert svc.get("k", tenant_id="t1") == "t1-val"
        assert svc.get("k") is None

    def test_client_hit_and_local_fallback(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.return_value = '["x"]'
        assert svc.get("k") == ["x"]
        svc.client.get.return_value = None
        svc.set("k", "local")
        assert svc.get("k") == "local"

    def test_client_exception_falls_back(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.side_effect = ConnectionError("down")
        svc.set("k", "local")
        assert svc.get("k") == "local"

    def test_set_with_client(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        assert svc.set("k", {"a": 1}, ttl=77) is True
        svc.client.setex.assert_called_once_with("k", 77, '{"a": 1}')

    def test_set_client_exception_still_returns_true(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.setex.side_effect = ConnectionError("down")
        assert svc.set("k", "v") is True

    def test_delete(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.return_value = None
        svc.set("k", "v")
        svc.delete("k")
        assert svc.get("k") is None
        svc.client.delete.assert_called_once_with("k")

    def test_delete_client_exception_tolerated(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.delete.side_effect = ConnectionError("down")
        svc.delete("k")

    def test_delete_tenant_namespaced(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.get.return_value = None
        svc.set("k", "v", tenant_id="t1")
        svc.delete("k", tenant_id="t1")
        assert svc.get("k", tenant_id="t1") is None
        svc.client.delete.assert_called_once_with("tenant:t1:k")

    def test_get_rest_hit(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": "5"})):
            assert svc.get("k") == 5

    def test_get_rest_miss_falls_to_local(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        svc.set("k", "local")
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": None})):
            assert svc.get("k") == "local"

    def test_set_writes_rest(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "post", return_value=http_ok()) as m:
            assert svc.set("k", "v", ttl=30) is True
        m.assert_called_once_with(
            "https://rest.example.com/set/k",
            headers={"Authorization": "Bearer tok"},
            params={"ex": 30},
            content="v",
            timeout=2.0,
        )

    def test_delete_writes_rest(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "get", return_value=http_ok()) as m:
            svc.delete("k")
        assert m.call_args[0][0] == "https://rest.example.com/del/k"


class TestRestHelpers:
    def _rest_service(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        return svc

    def test_rest_get_result(self, make_service):
        svc = self._rest_service(make_service)
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": "5"})) as m:
            assert svc._rest_get("k") == "5"
        m.assert_called_once_with(
            "https://rest.example.com/get/k",
            headers={"Authorization": "Bearer tok"},
            timeout=2.0,
        )

    def test_rest_get_non_200(self, make_service):
        svc = self._rest_service(make_service)
        resp = MagicMock()
        resp.status_code = 500
        with patch.object(cache_module.httpx, "get", return_value=resp):
            assert svc._rest_get("k") is None

    def test_rest_get_exception(self, make_service):
        svc = self._rest_service(make_service)
        with patch.object(cache_module.httpx, "get", side_effect=ConnectionError("down")):
            assert svc._rest_get("k") is None

    def test_rest_get_disabled(self, make_service):
        svc = local_service(make_service)
        assert svc._rest_get("k") is None

    def test_rest_set_ok(self, make_service):
        svc = self._rest_service(make_service)
        with patch.object(cache_module.httpx, "post", return_value=http_ok()) as m:
            assert svc._rest_set("k", "v", 60) is True
        assert m.call_args[0][0] == "https://rest.example.com/set/k"
        assert m.call_args[1]["params"] == {"ex": 60}
        assert m.call_args[1]["content"] == "v"

    def test_rest_set_failure(self, make_service):
        svc = self._rest_service(make_service)
        resp = MagicMock()
        resp.status_code = 400
        with patch.object(cache_module.httpx, "post", return_value=resp):
            assert svc._rest_set("k", "v", 60) is False

    def test_rest_set_exception(self, make_service):
        svc = self._rest_service(make_service)
        with patch.object(cache_module.httpx, "post", side_effect=ConnectionError("down")):
            assert svc._rest_set("k", "v", 60) is False

    def test_rest_set_disabled(self, make_service):
        svc = local_service(make_service)
        assert svc._rest_set("k", "v", 60) is False

    def test_rest_delete_ok(self, make_service):
        svc = self._rest_service(make_service)
        with patch.object(cache_module.httpx, "get", return_value=http_ok()):
            assert svc._rest_delete("k") is True

    def test_rest_delete_failure_and_exception(self, make_service):
        svc = self._rest_service(make_service)
        resp = MagicMock()
        resp.status_code = 404
        with patch.object(cache_module.httpx, "get", return_value=resp):
            assert svc._rest_delete("k") is False
        with patch.object(cache_module.httpx, "get", side_effect=ConnectionError("down")):
            assert svc._rest_delete("k") is False

    def test_rest_delete_disabled(self, make_service):
        svc = local_service(make_service)
        assert svc._rest_delete("k") is False

    def test_rest_incr_ok(self, make_service):
        svc = self._rest_service(make_service)
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": 3})):
            assert svc._rest_incr("k") == 3

    def test_rest_incr_failure_and_exception(self, make_service):
        svc = self._rest_service(make_service)
        resp = MagicMock()
        resp.status_code = 429
        with patch.object(cache_module.httpx, "get", return_value=resp):
            assert svc._rest_incr("k") is None
        with patch.object(cache_module.httpx, "get", side_effect=ConnectionError("down")):
            assert svc._rest_incr("k") is None

    def test_rest_incr_disabled(self, make_service):
        svc = local_service(make_service)
        assert svc._rest_incr("k") is None


class TestAsyncIncr:
    def test_pipeline_path(self, make_service):
        svc = local_service(make_service)
        client = make_fake_redis_client()
        pipe = MagicMock()
        pipe.execute.return_value = [3]
        client.pipeline.return_value = pipe
        svc.client = client
        assert await_helper(svc.incr_async("k")) == 3
        pipe.incr.assert_called_once_with("k")
        pipe.expire.assert_called_once_with("k", 60)

    def test_pipeline_exception_falls_to_local(self, make_service):
        svc = local_service(make_service)
        client = make_fake_redis_client()
        client.pipeline.return_value.execute.side_effect = ConnectionError("down")
        svc.client = client
        await_helper(svc.set_async("k", 2))
        assert await_helper(svc.incr_async("k")) == 3

    def test_rest_path_new_key_sets_expire(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "get", side_effect=[
            http_ok({"result": 1}),
            http_ok(),
        ]) as m:
            assert await_helper(svc.incr_async("k", ttl=30)) == 1
        assert m.call_count == 2
        assert m.call_args_list[1][0][0] == "https://rest.example.com/expire/k/30"

    def test_rest_path_existing_key_no_expire(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(cache_module.httpx, "get", return_value=http_ok({"result": 5})) as m:
            assert await_helper(svc.incr_async("k")) == 5
        assert m.call_count == 1

    def test_rest_path_expire_call_failure_tolerated(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        with patch.object(
            cache_module.httpx, "get",
            side_effect=[http_ok({"result": 1}), ConnectionError("down")],
        ) as m:
            assert await_helper(svc.incr_async("k")) == 1
        assert m.call_count == 2

    def test_local_fallback_increments(self, make_service):
        svc = local_service(make_service)
        assert await_helper(svc.incr_async("k")) == 1
        assert await_helper(svc.incr_async("k")) == 2


class TestDeleteTenantAll:
    def test_scoped_local_deletion_both_caches(self, make_service):
        svc = local_service(make_service)
        await_helper(svc.set_async("tenant:t1:a", 1))
        await_helper(svc.set_async("tenant:t1:b", 2))
        await_helper(svc.set_async("tenant:t2:c", 3))
        await_helper(svc.set_async("other", 4))
        assert await_helper(svc.delete_tenant_all("t1")) == 0
        assert await_helper(svc.get_async("tenant:t1:a")) is None
        assert await_helper(svc.get_async("tenant:t1:b")) is None
        assert await_helper(svc.get_async("tenant:t2:c")) == 3
        assert await_helper(svc.get_async("other")) == 4
        assert svc.get("tenant:t1:a") is None
        assert svc.get("tenant:t2:c") == 3

    def test_pattern_prefix_passthrough(self, make_service):
        svc = local_service(make_service)
        await_helper(svc.set_async("tenant:t1:a", 1))
        assert await_helper(svc.delete_tenant_all("tenant:t1:")) == 0
        assert await_helper(svc.get_async("tenant:t1:a")) is None

    def test_with_redis_client(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.scan_iter.return_value = ["tenant:t1:a", "tenant:t1:b"]
        svc.client.delete.return_value = 2
        assert await_helper(svc.delete_tenant_all("t1")) == 2
        svc.client.scan_iter.assert_called_once_with(match="tenant:t1:*")
        svc.client.delete.assert_called_once_with("tenant:t1:a", "tenant:t1:b")

    def test_client_empty_keys_no_delete_call(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.scan_iter.return_value = []
        assert await_helper(svc.delete_tenant_all("t1")) == 0
        svc.client.delete.assert_not_called()

    def test_client_exception_tolerated(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.scan_iter.side_effect = ConnectionError("down")
        assert await_helper(svc.delete_tenant_all("t1")) == 0

    def test_disabled_still_purges_local(self, make_service):
        svc = make_service({"ENABLE_CACHE": "false"})
        svc.set("tenant:t1:a", 1)
        assert await_helper(svc.delete_tenant_all("t1")) == 0
        assert svc.get("tenant:t1:a") is None


class TestGetStatus:
    def test_disabled(self, make_service):
        svc = make_service({"ENABLE_CACHE": "false"})
        status = svc.get_status()
        assert status["status"] == "disabled"
        assert status["mode"] == "local_memory"
        assert status["enabled"] is False

    def test_local_operational(self, make_service):
        svc = local_service(make_service)
        status = svc.get_status()
        assert status["status"] == "operational"
        assert status["mode"] == "local_memory"
        assert status["circuit_breaker"] == "closed"

    def test_redis_operational(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        status = svc.get_status()
        assert status["status"] == "operational"
        assert status["mode"] == "redis"

    def test_redis_degraded(self, make_service):
        svc = local_service(make_service)
        svc.client = make_fake_redis_client()
        svc.client.ping.side_effect = ConnectionError("down")
        status = svc.get_status()
        assert status["status"] == "degraded"
        assert status["mode"] == "redis"

    def test_rest_operational(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = "https://rest.example.com"
        svc.rest_api_token = "tok"
        status = svc.get_status()
        assert status["status"] == "operational"
        assert status["mode"] == "upstash_rest"

    def test_rest_misconfigured_degraded(self, make_service):
        svc = local_service(make_service)
        svc.use_rest_api = True
        svc.rest_api_url = ""
        svc.rest_api_token = ""
        status = svc.get_status()
        assert status["status"] == "degraded"
        assert status["mode"] == "upstash_rest"

    def test_get_circuit_state(self, make_service):
        svc = local_service(make_service)
        assert svc.get_circuit_state() == "closed"
        svc.circuit_breaker._state = CircuitState.OPEN
        assert svc.get_circuit_state() == "open"


class TestRedisImportFallback:
    def test_import_error_sets_redis_none(self, monkeypatch):
        real_redis = sys.modules.get("redis")
        monkeypatch.setitem(sys.modules, "redis", None)
        importlib.reload(cache_module)
        try:
            assert cache_module.redis is None
        finally:
            monkeypatch.setitem(sys.modules, "redis", real_redis)
            importlib.reload(cache_module)
        assert cache_module.redis is real_redis


def await_helper(awaitable):
    import asyncio
    return asyncio.run(awaitable)
