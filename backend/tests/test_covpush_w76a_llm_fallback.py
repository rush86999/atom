"""Coverage wave 76a — LLM fallback/routing stack (standalone-certifying suite).

Targets (before % measured against the pre-existing suites; this file alone
holds each module at >=95%):
  core/llm/fallback/circuit_breaker.py        33%
  core/llm/fallback/retry_policy.py           30%
  core/llm/minimax_integration.py            100% (verified)
  core/llm/rate_usage_persistence.py          99% (line 79 inner-lock return)
  core/llm/routing_overrides.py              100% (verified)
  core/llm/learning_router_registry.py        95% (lines 31, 69)

Bug found: ``circuit_breaker._should_allow_request`` never incremented
``_half_open_call_count``, so ``half_open_max_calls`` was dead — the HALF_OPEN
probe window was unlimited. Fixed in source; regression test:
``test_half_open_max_calls_blocks_extra_probes``.
"""
import sys
import threading
import time
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.llm.fallback.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)
from core.llm.fallback.retry_policy import (
    ExponentialBackoffStrategy,
    RetryPolicy,
    RetryableError,
)
from core.llm.minimax_integration import (
    MINIMAX_MODELS,
    MiniMaxIntegration,
    RateLimitedError,
    clamp_temperature,
)
from core.llm.routing_overrides import parse_routing_overrides


# ============================================================================
# circuit_breaker.py
# ============================================================================

class TestCircuitBreakerError:
    def test_message_without_last_failure(self):
        err = CircuitBreakerOpenError(CircuitBreakerState.OPEN)
        assert err.state is CircuitBreakerState.OPEN
        assert err.last_failure is None
        assert str(err) == "Circuit breaker is open"

    def test_message_with_last_failure(self):
        err = CircuitBreakerOpenError(CircuitBreakerState.CLOSED, "boom")
        assert err.last_failure == "boom"
        assert str(err) == "Circuit breaker is closed (last failure: boom)"


class TestCircuitBreaker:
    async def test_initial_state_closed(self):
        breaker = CircuitBreaker()
        assert breaker.get_state() is CircuitBreakerState.CLOSED
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 60.0
        assert breaker.success_threshold == 2
        assert breaker.half_open_max_calls == 3

    async def test_metrics_structure(self):
        breaker = CircuitBreaker()
        metrics = breaker.get_metrics()
        assert metrics["state"] == "closed"
        assert metrics["failure_count"] == 0
        assert metrics["success_count"] == 0
        assert metrics["failure_threshold"] == 5
        assert metrics["success_threshold"] == 2
        assert metrics["last_failure_time"] is None
        assert metrics["last_failure_message"] is None
        assert isinstance(metrics["last_state_change"], float)
        assert metrics["half_open_call_count"] == 0

    async def test_call_success(self):
        breaker = CircuitBreaker()
        func = AsyncMock(return_value="ok")
        result = await breaker.call(func, "arg", key="kw")
        assert result == "ok"
        func.assert_awaited_once_with("arg", key="kw")
        assert breaker.get_metrics()["failure_count"] == 0

    async def test_call_failure_records_and_reraises(self):
        breaker = CircuitBreaker(failure_threshold=5)
        func = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            await breaker.call(func)
        metrics = breaker.get_metrics()
        assert metrics["failure_count"] == 1
        assert metrics["last_failure_message"] == "boom"
        assert isinstance(metrics["last_failure_time"], float)

    async def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(failure_threshold=5)
        fail = AsyncMock(side_effect=ValueError("boom"))
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail)
        assert breaker.get_metrics()["failure_count"] == 2
        ok = AsyncMock(return_value="ok")
        await breaker.call(ok)
        assert breaker.get_metrics()["failure_count"] == 0

    async def test_trip_to_open_after_threshold(self):
        breaker = CircuitBreaker(failure_threshold=2)
        func = AsyncMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            await breaker.call(func)
        assert breaker.get_state() is CircuitBreakerState.CLOSED
        with pytest.raises(RuntimeError):
            await breaker.call(func)
        assert breaker.get_state() is CircuitBreakerState.OPEN

    async def test_open_blocks_requests(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        ok = AsyncMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await breaker.call(ok)
        assert exc_info.value.state is CircuitBreakerState.OPEN
        assert exc_info.value.last_failure == "boom"
        assert "Circuit breaker is open" in str(exc_info.value)
        assert "boom" in str(exc_info.value)
        ok.assert_not_awaited()

    async def test_open_with_no_failure_time_blocks(self):
        breaker = CircuitBreaker()
        breaker._state = CircuitBreakerState.OPEN
        breaker._last_failure_time = None
        func = AsyncMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(func)
        func.assert_not_awaited()

    async def test_open_blocks_when_recovery_not_elapsed(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        breaker._last_failure_time = time.time() - 1.0
        func = AsyncMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(func)
        assert breaker.get_state() is CircuitBreakerState.OPEN

    async def test_open_transitions_half_open_after_timeout(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        assert breaker.get_state() is CircuitBreakerState.OPEN
        breaker._last_failure_time = time.time() - 61.0
        breaker._success_count = 5
        ok = AsyncMock(return_value="ok")
        result = await breaker.call(ok)
        assert result == "ok"
        assert breaker.get_state() is CircuitBreakerState.HALF_OPEN
        metrics = breaker.get_metrics()
        assert metrics["half_open_call_count"] == 1
        assert metrics["success_count"] == 1

    async def test_half_open_successes_close_circuit(self):
        breaker = CircuitBreaker(
            failure_threshold=1, recovery_timeout=60.0, success_threshold=2)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        breaker._last_failure_time = time.time() - 61.0
        ok = AsyncMock(return_value="ok")
        await breaker.call(ok)
        assert breaker.get_state() is CircuitBreakerState.HALF_OPEN
        await breaker.call(ok)
        assert breaker.get_state() is CircuitBreakerState.CLOSED
        metrics = breaker.get_metrics()
        assert metrics["failure_count"] == 0
        assert metrics["half_open_call_count"] == 2

    async def test_half_open_failure_reopens(self):
        breaker = CircuitBreaker(
            failure_threshold=1, recovery_timeout=60.0,
            success_threshold=5, half_open_max_calls=3)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        breaker._last_failure_time = time.time() - 61.0
        ok = AsyncMock(return_value="ok")
        await breaker.call(ok)
        assert breaker.get_state() is CircuitBreakerState.HALF_OPEN
        with pytest.raises(ValueError):
            await breaker.call(fail)
        assert breaker.get_state() is CircuitBreakerState.OPEN
        assert breaker.get_metrics()["half_open_call_count"] == 0

    async def test_half_open_max_calls_blocks_extra_probes(self):
        breaker = CircuitBreaker(
            failure_threshold=1, recovery_timeout=60.0,
            success_threshold=3, half_open_max_calls=1)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        breaker._last_failure_time = time.time() - 61.0
        ok = AsyncMock(return_value="ok")
        await breaker.call(ok)
        assert breaker.get_state() is CircuitBreakerState.HALF_OPEN
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await breaker.call(ok)
        assert exc_info.value.state is CircuitBreakerState.HALF_OPEN
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(ok)
        assert ok.await_count == 1

    async def test_reset_restores_closed(self):
        breaker = CircuitBreaker(failure_threshold=1)
        fail = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            await breaker.call(fail)
        assert breaker.get_state() is CircuitBreakerState.OPEN
        await breaker.reset()
        metrics = breaker.get_metrics()
        assert breaker.get_state() is CircuitBreakerState.CLOSED
        assert metrics["failure_count"] == 0
        assert metrics["success_count"] == 0
        assert metrics["half_open_call_count"] == 0
        assert metrics["last_failure_time"] is None
        assert metrics["last_failure_message"] is None

    async def test_unknown_state_blocks(self):
        breaker = CircuitBreaker()
        breaker._state = "not-a-state"
        func = AsyncMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(func)
        func.assert_not_awaited()


# ============================================================================
# retry_policy.py
# ============================================================================

class TestExponentialBackoffStrategy:
    def test_delay_exponential_no_jitter(self):
        strategy = ExponentialBackoffStrategy(
            max_retries=3, initial_delay=1.0, max_delay=60.0, jitter=False)
        assert strategy.max_retries == 3
        assert strategy.initial_delay == 1.0
        assert strategy.max_delay == 60.0
        assert strategy.exponential_base == 2.0
        assert strategy.get_delay(0) == 1.0
        assert strategy.get_delay(1) == 2.0
        assert strategy.get_delay(2) == 4.0
        assert strategy.get_delay(3) == 8.0

    def test_delay_capped_at_max(self):
        strategy = ExponentialBackoffStrategy(
            max_retries=5, initial_delay=10.0, max_delay=30.0, jitter=False)
        assert strategy.get_delay(3) == 30.0

    def test_delay_jitter_applied(self):
        strategy = ExponentialBackoffStrategy(jitter=True)
        with patch("core.llm.fallback.retry_policy.random.uniform",
                   return_value=0.125) as mock_uniform:
            delay = strategy.get_delay(2)
        mock_uniform.assert_called_once_with(-1.0, 1.0)
        assert delay == 4.125

    def test_jitter_disabled_no_uniform_call(self):
        strategy = ExponentialBackoffStrategy(jitter=False)
        with patch("core.llm.fallback.retry_policy.random.uniform") as mock_uniform:
            assert strategy.get_delay(0) == 1.0
        mock_uniform.assert_not_called()

    async def test_sleep_with_backoff(self):
        strategy = ExponentialBackoffStrategy(jitter=False)
        with patch("core.llm.fallback.retry_policy.asyncio.sleep",
                   new=AsyncMock()) as mock_sleep:
            await strategy.sleep_with_backoff(1)
        mock_sleep.assert_awaited_once_with(2.0)


class TestRetryPolicy:
    def _policy(self, retryable_errors=None, **strategy_kwargs):
        strategy = ExponentialBackoffStrategy(**strategy_kwargs)
        policy = RetryPolicy(strategy=strategy, retryable_errors=retryable_errors)
        policy.strategy.sleep_with_backoff = AsyncMock()
        return policy

    def test_default_retryable_errors(self):
        policy = self._policy(jitter=False)
        assert policy.retryable_errors == {
            RetryableError.RATE_LIMIT,
            RetryableError.TIMEOUT,
            RetryableError.SERVER_ERROR,
            RetryableError.NETWORK_ERROR,
        }

    def test_custom_retryable_errors(self):
        policy = self._policy(retryable_errors={RetryableError.RATE_LIMIT})
        assert policy.retryable_errors == {RetryableError.RATE_LIMIT}

    async def test_execute_success_first_try(self):
        policy = self._policy(jitter=False)
        func = AsyncMock(return_value="ok")
        result = await policy.execute(func, "a", key="b")
        assert result == "ok"
        func.assert_awaited_once_with("a", key="b")
        policy.strategy.sleep_with_backoff.assert_not_awaited()

    async def test_execute_success_after_retries(self):
        policy = self._policy(max_retries=3, jitter=False)
        func = AsyncMock(side_effect=[
            ValueError("429 rate limit"),
            ValueError("request timed out"),
            "ok",
        ])
        result = await policy.execute(func)
        assert result == "ok"
        assert func.await_count == 3
        assert policy.strategy.sleep_with_backoff.await_count == 2

    async def test_execute_non_retryable_raises_immediately(self):
        policy = self._policy(max_retries=3, jitter=False)
        func = AsyncMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            await policy.execute(func)
        func.assert_awaited_once()
        policy.strategy.sleep_with_backoff.assert_not_awaited()

    async def test_execute_exhausts_retries_raises_last(self):
        policy = self._policy(max_retries=2, jitter=False)
        func = AsyncMock(side_effect=ValueError("429 rate limit"))
        with pytest.raises(ValueError, match="429 rate limit"):
            await policy.execute(func)
        assert func.await_count == 3
        assert policy.strategy.sleep_with_backoff.await_count == 2

    async def test_execute_non_retryable_mixed_in_retries(self):
        policy = self._policy(max_retries=2, jitter=False)
        func = AsyncMock(side_effect=[
            ValueError("429 rate limit"),
            ValueError("boom"),
        ])
        with pytest.raises(ValueError, match="boom"):
            await policy.execute(func)
        assert func.await_count == 2

    def test_is_retryable_true_for_rate_limit(self):
        policy = self._policy()
        assert policy.is_retryable(ValueError("429 too many requests")) is True

    def test_is_retryable_false_for_unknown(self):
        policy = self._policy()
        assert policy.is_retryable(ValueError("boom")) is False

    def test_is_retryable_respects_custom_set(self):
        policy = self._policy(retryable_errors={RetryableError.TIMEOUT})
        assert policy.is_retryable(ValueError("request timed out")) is True
        assert policy.is_retryable(ValueError("429 rate limit")) is False

    def test_map_exception_rate_limit_code(self):
        policy = self._policy()
        assert policy._map_exception_to_error(
            ValueError("API returned 429")) is RetryableError.RATE_LIMIT

    def test_map_exception_rate_limit_word(self):
        policy = self._policy()
        assert policy._map_exception_to_error(
            ValueError("rate limit exceeded")) is RetryableError.RATE_LIMIT

    def test_map_exception_timeout(self):
        policy = self._policy()
        assert policy._map_exception_to_error(
            TimeoutError("request timed out")) is RetryableError.TIMEOUT

    def test_map_exception_server_error(self):
        policy = self._policy()
        assert policy._map_exception_to_error(
            RuntimeError("503 service unavailable")) is RetryableError.SERVER_ERROR

    def test_map_exception_network_message(self):
        policy = self._policy()
        assert policy._map_exception_to_error(
            OSError("connection refused")) is RetryableError.NETWORK_ERROR

    def test_map_exception_network_error_type(self):
        policy = self._policy()
        assert policy._map_exception_to_error(
            ConnectionResetError("reset")) is RetryableError.NETWORK_ERROR

    def test_map_exception_retryable_attribute(self):
        policy = self._policy()
        err = ValueError("opaque message")
        err.retryable = True
        assert policy._map_exception_to_error(err) is RetryableError.RETRYABLE

    def test_map_exception_retryable_false_attribute(self):
        policy = self._policy()
        err = ValueError("opaque message")
        err.retryable = False
        assert policy._map_exception_to_error(err) is None

    def test_map_exception_none(self):
        policy = self._policy()
        assert policy._map_exception_to_error(ValueError("boom")) is None


# ============================================================================
# minimax_integration.py
# ============================================================================

class TestMiniMaxIntegration:
    @pytest.fixture(autouse=True)
    def _no_http(self):
        with patch("core.llm.minimax_integration.httpx.AsyncClient",
                   autospec=True) as client_cls:
            self._client_cls = client_cls
            yield

    def _make(self, model="MiniMax-M3", client=None):
        itg = MiniMaxIntegration("test-key", model=model)
        itg.client = client or AsyncMock()
        return itg

    @staticmethod
    def _resp(status=200, raise_err=None):
        resp = Mock()
        resp.status_code = status
        resp.raise_for_status = Mock(side_effect=raise_err)
        resp.json.return_value = {"choices": [{"message": {"content": "hi"}}]}
        return resp

    def test_init_creates_client_with_auth_header(self):
        MiniMaxIntegration("sk-test")
        self._client_cls.assert_called_once()
        _, kwargs = self._client_cls.call_args
        assert kwargs["base_url"] == "https://api.minimax.io/v1"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        assert kwargs["timeout"] == 30.0

    def test_init_custom_model(self):
        itg = MiniMaxIntegration("sk-test", model="MiniMax-M2.7-highspeed")
        assert itg.model == "MiniMax-M2.7-highspeed"

    def test_clamp_temperature_zero(self):
        assert clamp_temperature(0.0) == 0.01

    def test_clamp_temperature_negative(self):
        assert clamp_temperature(-3.0) == 0.01

    def test_clamp_temperature_high(self):
        assert clamp_temperature(1.5) == 1.0

    def test_clamp_temperature_valid_unchanged(self):
        assert clamp_temperature(0.7) == 0.7
        assert clamp_temperature(1.0) == 1.0

    async def test_generate_success(self):
        itg = self._make()
        itg.client.post = AsyncMock(return_value=self._resp())
        result = await itg.generate("hello", temperature=0.7, max_tokens=1000)
        assert result == "hi"
        body = itg.client.post.call_args.kwargs["json"]
        assert body["model"] == "MiniMax-M3"
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 1000
        assert body["messages"] == [{"role": "user", "content": "hello"}]
        itg.client.post.assert_awaited_once_with("/chat/completions", json=body)

    async def test_generate_model_override(self):
        itg = self._make()
        itg.client.post = AsyncMock(return_value=self._resp())
        await itg.generate("hello", model="MiniMax-M2.7")
        body = itg.client.post.call_args.kwargs["json"]
        assert body["model"] == "MiniMax-M2.7"

    async def test_generate_temperature_clamped_in_request(self):
        itg = self._make()
        itg.client.post = AsyncMock(return_value=self._resp())
        await itg.generate("hello", temperature=-1.0)
        body = itg.client.post.call_args.kwargs["json"]
        assert body["temperature"] == 0.01

    async def test_generate_rate_limit_raises(self):
        itg = self._make()
        request = httpx.Request("POST", "https://api.minimax.io/v1/chat/completions")
        err = httpx.HTTPStatusError(
            "Rate limit", request=request, response=httpx.Response(429))
        itg.client.post = AsyncMock(return_value=self._resp(raise_err=err))
        with pytest.raises(RateLimitedError):
            await itg.generate("hello")

    async def test_generate_http_error_returns_none(self):
        itg = self._make()
        request = httpx.Request("POST", "https://api.minimax.io/v1/chat/completions")
        err = httpx.HTTPStatusError(
            "Server error", request=request, response=httpx.Response(500))
        itg.client.post = AsyncMock(return_value=self._resp(raise_err=err))
        assert await itg.generate("hello") is None

    async def test_generate_generic_error_returns_none(self):
        itg = self._make()
        itg.client.post = AsyncMock(side_effect=RuntimeError("connection refused"))
        assert await itg.generate("hello") is None

    async def test_test_connection_true(self):
        itg = self._make()
        itg.client.post = AsyncMock(return_value=self._resp(status=200))
        assert await itg.test_connection() is True
        body = itg.client.post.call_args.kwargs["json"]
        assert body["max_tokens"] == 1
        assert body["temperature"] == 0.01

    async def test_test_connection_false_on_non_200(self):
        itg = self._make()
        itg.client.post = AsyncMock(return_value=self._resp(status=401))
        assert await itg.test_connection() is False

    async def test_test_connection_false_on_exception(self):
        itg = self._make()
        itg.client.post = AsyncMock(side_effect=httpx.ConnectError("no route"))
        assert await itg.test_connection() is False

    def test_get_pricing_returns_copy(self):
        itg = self._make()
        pricing = itg.get_pricing()
        assert pricing["input_cost_per_token"] == 0.000001
        assert pricing["output_cost_per_token"] == 0.000001
        assert pricing["max_tokens"] == 512000
        assert pricing is not itg.ESTIMATED_PRICING

    def test_get_capabilities(self):
        itg = self._make()
        caps = itg.get_capabilities()
        assert caps["quality_score"] == 92
        assert caps["supports_vision"] is True
        assert caps["supports_tools"] is True
        assert caps["supports_cache"] is False
        assert caps["tier"].value == "standard"

    def test_get_available_models(self):
        models = MiniMaxIntegration.get_available_models()
        assert set(models) == set(MINIMAX_MODELS)
        assert models is not MINIMAX_MODELS
        assert models["MiniMax-M3"]["context_window"] == 512000
        assert models["MiniMax-M2.7"]["context_window"] == 204000

    async def test_close_closes_client(self):
        itg = self._make()
        await itg.close()
        itg.client.aclose.assert_awaited_once()

    def test_rate_limited_error_constructible(self):
        err = RateLimitedError("MiniMax rate limit exceeded")
        assert str(err) == "MiniMax rate limit exceeded"


# ============================================================================
# rate_usage_persistence.py
# ============================================================================

class TestRateUsagePersistence:
    @staticmethod
    def _engine():
        return create_engine("sqlite://")

    def test_ensure_table_already_ready(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p._table_ready = True
        with patch("core.llm.rate_usage_persistence.Base.metadata.create_all",
                   side_effect=RuntimeError("must not be called")):
            p._ensure_table()
        assert p._table_ready is True

    def test_ensure_table_inner_lock_return(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p._table_ready = False
        entered = threading.Event()
        release = threading.Event()

        def holder():
            with p._lock:
                entered.set()
                release.wait(5)
                p._table_ready = True

        t = threading.Thread(target=holder)
        t.start()
        assert entered.wait(5)
        done = []

        def caller():
            p._ensure_table()
            done.append(True)

        t2 = threading.Thread(target=caller)
        t2.start()
        time.sleep(0.2)
        release.set()
        t.join(5)
        t2.join(5)
        assert done == [True]

    def test_ensure_table_create_all_failure(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        with patch("core.llm.rate_usage_persistence.Base.metadata.create_all",
                   side_effect=RuntimeError("db down")):
            p._ensure_table()
        assert p._table_ready is False

    def test_record_persists_rows(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 100, 50)
        p.record("openai", "gpt-4o", 100, 50)
        p.record("openai", "gpt-4o-mini", 10, 5)
        usage = p.monthly_usage("openai")
        assert usage["provider"] == "openai"
        assert usage["model"] is None
        assert usage["requests"] == 3
        assert usage["input_tokens"] == 210
        assert usage["output_tokens"] == 105
        assert usage["total_tokens"] == 315

    def test_monthly_usage_model_filter(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 100, 50)
        p.record("openai", "gpt-4o-mini", 10, 5)
        usage = p.monthly_usage("openai", "gpt-4o")
        assert usage["model"] == "gpt-4o"
        assert usage["requests"] == 1
        assert usage["period"] == f"{datetime.now(timezone.utc).year}-{datetime.now(timezone.utc).month:02d}"

    def test_monthly_usage_cache_hit_returns_copy(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 100, 50)
        first = p.monthly_usage("openai")
        cached = p.monthly_usage("openai")
        assert cached == first
        cached["requests"] = 999
        assert p.monthly_usage("openai")["requests"] == 1

    def test_monthly_usage_cache_expiry_recomputes(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 100, 50)
        now = datetime.now(timezone.utc)
        p._monthly_cache[("openai", None, (now.year, now.month))] = (
            time.time() - 61, {"requests": 999, "input_tokens": 0,
                               "output_tokens": 0, "total_tokens": 0})
        usage = p.monthly_usage("openai")
        assert usage["requests"] == 1

    def test_record_clears_monthly_cache(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 100, 50)
        assert p.monthly_usage("openai")["requests"] == 1
        p.record("openai", "gpt-4o", 50, 25)
        assert p.monthly_usage("openai")["requests"] == 2

    def test_record_none_tokens_default_zero(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", None, None, None)
        usage = p.monthly_usage("openai", None)
        assert usage["requests"] == 1
        assert usage["total_tokens"] == 0

    def test_record_table_not_ready_short_circuits(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        with patch("core.llm.rate_usage_persistence.Base.metadata.create_all",
                   side_effect=RuntimeError("db down")):
            p.record("openai", "gpt-4o", 1, 1)
            assert p.monthly_usage("openai") is None

    def test_record_commit_failure_nonfatal(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 1, 1)
        session = Mock()
        session.commit.side_effect = RuntimeError("write failed")
        p._session_factory = Mock(return_value=session)
        p.record("openai", "gpt-4o", 1, 1)
        session.close.assert_called_once()

    def test_record_session_factory_failure_nonfatal(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 1, 1)
        p._session_factory = Mock(side_effect=RuntimeError("no session"))
        p.record("openai", "gpt-4o", 1, 1)

    def test_monthly_usage_excludes_previous_months(self):
        from core.models import Base
        from core.llm.rate_usage_persistence import (
            RateUsagePersistence,
            RateUsageRecord,
        )
        engine = self._engine()
        Base.metadata.create_all(bind=engine, tables=[RateUsageRecord.__table__])
        session = sessionmaker(bind=engine)()
        session.add(RateUsageRecord(
            provider_id="openai", model_id="gpt-4o",
            input_tokens=500, output_tokens=500,
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)))
        session.commit()
        session.close()
        p = RateUsagePersistence(engine)
        usage = p.monthly_usage("openai")
        assert usage["requests"] == 0
        assert usage["total_tokens"] == 0

    def test_monthly_usage_query_failure_returns_none(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence
        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 1, 1)
        p._session_factory = Mock(side_effect=RuntimeError("db down"))
        assert p.monthly_usage("openai") is None

    def test_singleton_creates_once(self):
        import core.llm.rate_usage_persistence as rup
        old = rup._persistence
        rup._persistence = None
        try:
            s1 = rup.get_rate_usage_persistence()
            s2 = rup.get_rate_usage_persistence()
            assert s1 is s2
            assert isinstance(s1, rup.RateUsagePersistence)
        finally:
            rup._persistence = old

    def test_singleton_race_inner_check(self):
        import core.llm.rate_usage_persistence as rup
        old = rup._persistence
        rup._persistence = None
        try:
            sentinel = object()
            held = threading.Event()
            release = threading.Event()

            def holder():
                with rup._singleton_lock:
                    held.set()
                    release.wait(5)
                    rup._persistence = sentinel

            t = threading.Thread(target=holder)
            t.start()
            assert held.wait(5)
            results = []

            def caller():
                results.append(rup.get_rate_usage_persistence())

            t2 = threading.Thread(target=caller)
            t2.start()
            time.sleep(0.2)
            release.set()
            t.join(5)
            t2.join(5)
            assert results == [sentinel]
        finally:
            rup._persistence = old


# ============================================================================
# routing_overrides.py
# ============================================================================

class TestRoutingOverrides:
    @staticmethod
    def _block_module(name):
        fake = ModuleType(name)

        def raiser(*args, **kwargs):
            raise ImportError("blocked import")

        fake.__getattr__ = raiser
        return fake

    def test_parse_all_valid_mixed_case(self):
        headers = {
            "X-Atom-Tier": "  VERSATILE ",
            "x-atom-model": "gpt-4o",
            "X-ATOM-INTENT": "coding",
        }
        assert parse_routing_overrides(headers) == {
            "tier": "versatile", "model": "gpt-4o", "intent": "coding"}

    def test_parse_tier_lowercase_normalized(self):
        assert parse_routing_overrides({"x-atom-tier": "COMPLEX"}) == {
            "tier": "complex"}

    def test_parse_invalid_tier_dropped(self):
        assert parse_routing_overrides({"x-atom-tier": "bogus-tier"}) == {}

    def test_parse_invalid_intent_dropped(self):
        assert parse_routing_overrides({"x-atom-intent": "not-an-intent"}) == {}

    def test_parse_unknown_model_dropped(self):
        with patch("core.llm.byok_handler.BYOKHandler._model_registry", {},
                   create=True):
            result = parse_routing_overrides({"x-atom-model": "not-a-known-model"})
        assert "model" not in result

    def test_parse_blank_model_dropped(self):
        assert parse_routing_overrides({"x-atom-model": "   "}) == {}

    def test_parse_model_from_registry_key(self):
        spec = SimpleNamespace(model_name="custom-model", model_id="custom-model")
        with patch("core.llm.byok_handler.BYOKHandler._model_registry",
                   {"custom-model": spec}, create=True):
            result = parse_routing_overrides({"x-atom-model": "custom-model"})
        assert result == {"model": "custom-model"}

    def test_parse_model_by_model_name_field(self):
        spec = SimpleNamespace(model_name="alias-model", model_id="internal-key")
        with patch("core.llm.byok_handler.BYOKHandler._model_registry",
                   {"internal-key": spec}, create=True):
            result = parse_routing_overrides({"x-atom-model": "alias-model"})
        assert result == {"model": "alias-model"}

    def test_parse_model_known_prefix_accepted(self):
        with patch("core.llm.byok_handler.BYOKHandler._model_registry", {},
                   create=True):
            result = parse_routing_overrides({"x-atom-model": "claude-3-5-sonnet"})
        assert result == {"model": "claude-3-5-sonnet"}

    def test_parse_model_known_prefix_o4(self):
        with patch("core.llm.byok_handler.BYOKHandler._model_registry", {},
                   create=True):
            result = parse_routing_overrides({"x-atom-model": "o4-mini"})
        assert result == {"model": "o4-mini"}

    def test_parse_object_get_returns_none(self):
        class _HeaderWithGet:
            def get(self, name, default=None):
                return None

        assert parse_routing_overrides(_HeaderWithGet()) == {}

    def test_parse_object_without_get_returns_none(self):
        class _HeaderNoGet:
            pass

        assert parse_routing_overrides(_HeaderNoGet()) == {}

    def test_parse_empty_headers(self):
        assert parse_routing_overrides({}) == {}

    def test_is_valid_tier_import_failure_false(self):
        blocked = self._block_module("core.llm.cognitive_tier_system")
        with patch.dict(sys.modules, {"core.llm.cognitive_tier_system": blocked}):
            assert parse_routing_overrides({"x-atom-tier": "heavy"}) == {}

    def test_is_valid_intent_import_failure_false(self):
        blocked = self._block_module("core.llm.intent_detector")
        with patch.dict(sys.modules, {"core.llm.intent_detector": blocked}):
            assert parse_routing_overrides({"x-atom-intent": "coding"}) == {}

    def test_is_known_model_registry_failure_fail_open(self):
        blocked = self._block_module("core.llm.byok_handler")
        with patch.dict(sys.modules, {"core.llm.byok_handler": blocked}):
            assert parse_routing_overrides({"x-atom-model": "anything"}) == {
                "model": "anything"}


# ============================================================================
# learning_router_registry.py
# ============================================================================

class TestLearningRouterRegistry:
    @staticmethod
    def _fake_learning_module(router=None, side_effect=None):
        fake = ModuleType("core.learning_llm_router")
        fake.get_learning_router = Mock(
            return_value=router, side_effect=side_effect)
        return fake

    def test_learning_router_enabled_flag_variants(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        assert reg.learning_router_enabled() is True
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "TRUE")
        assert reg.learning_router_enabled() is True
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        assert reg.learning_router_enabled() is False
        monkeypatch.delenv("ATOM_LEARNING_ROUTER", raising=False)
        assert reg.learning_router_enabled() is False

    def test_ema_router_enabled_truthy_variants(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        for value in ("1", "true", "yes", "on", "TRUE"):
            monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", value)
            assert reg.ema_router_enabled() is True

    def test_ema_router_enabled_falsy_variants(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        for value in ("0", "false", "no", "off", "random", ""):
            monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", value)
            assert reg.ema_router_enabled() is False
        monkeypatch.delenv("ATOM_EMA_ROUTER_ENABLED", raising=False)
        assert reg.ema_router_enabled() is False

    def test_get_instance_disabled_returns_none(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "false")
        reg._SINGLETON = None
        assert reg.get_learning_router_instance() is None

    def test_get_instance_returns_existing_singleton(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        sentinel = object()
        reg._SINGLETON = sentinel
        try:
            assert reg.get_learning_router_instance() is sentinel
        finally:
            reg._SINGLETON = None

    def test_get_instance_builds_and_caches(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        router = Mock()
        router.load_feedback_from_db.return_value = 7
        fake = self._fake_learning_module(router=router)
        try:
            with patch.dict(sys.modules, {"core.learning_llm_router": fake}):
                result = reg.get_learning_router_instance()
                assert result is router
                assert reg.get_learning_router_instance() is router
            fake.get_learning_router.assert_called_once_with(None)
            router.load_feedback_from_db.assert_called_once_with()
        finally:
            reg._SINGLETON = None

    def test_get_instance_hydration_failure_still_returns(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        router = Mock()
        router.load_feedback_from_db.side_effect = RuntimeError("db down")
        fake = self._fake_learning_module(router=router)
        try:
            with patch.dict(sys.modules, {"core.learning_llm_router": fake}):
                assert reg.get_learning_router_instance() is router
        finally:
            reg._SINGLETON = None

    def test_get_instance_instantiation_failure_returns_none(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        fake = self._fake_learning_module(
            side_effect=RuntimeError("no router available"))
        try:
            with patch.dict(sys.modules, {"core.learning_llm_router": fake}):
                assert reg.get_learning_router_instance() is None
            assert reg._SINGLETON is None
        finally:
            reg._SINGLETON = None

    def test_double_checked_locking_returns_existing(self, monkeypatch):
        import core.llm.learning_router_registry as reg
        monkeypatch.setenv("ATOM_LEARNING_ROUTER", "true")
        reg._SINGLETON = None
        sentinel = object()
        held = threading.Event()
        release = threading.Event()

        def holder():
            with reg._LOCK:
                held.set()
                release.wait(5)
                reg._SINGLETON = sentinel

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(5)
        results = []

        def caller():
            results.append(reg.get_learning_router_instance())

        t2 = threading.Thread(target=caller)
        t2.start()
        time.sleep(0.2)
        release.set()
        t.join(5)
        t2.join(5)
        try:
            assert results == [sentinel]
        finally:
            reg._SINGLETON = None

    def test_reset_clears_singleton(self):
        import core.llm.learning_router_registry as reg
        reg._SINGLETON = object()
        try:
            reg.reset_learning_router_instance()
            assert reg._SINGLETON is None
        finally:
            reg._SINGLETON = None
