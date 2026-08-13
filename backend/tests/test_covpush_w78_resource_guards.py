# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/resource_guards (timeouts, retries, memory/CPU/disk/
pool guards, rate limiter). Fully mocked — no network, no real psutil.

- IntegrationTimeoutError: message/timeout_seconds/operation attributes.
- ResourceGuard.with_timeout: success + timeout (IntegrationTimeoutError raised
  with operation name) and the asyncio.TimeoutError branch.
- ResourceGuard.timeout_decorator: wraps async functions (__name__ preserved),
  passes through args/kwargs, propagates timeout error.
- ResourceGuard.with_retry: success on first attempt, success after retries
  (exponential backoff 1,2,4s), exhaustion raises last exception, logs.
- MemoryGuard: get_memory_usage_mb with mocked psutil, psutil ImportError
  branch, check_memory_limit over/under limit.
- CPUGuard: get_cpu_usage_percent success/exception/ImportError,
  check_cpu_limit over/under.
- DiskSpaceGuard: get_available_disk_mb success/exception/ImportError,
  check_disk_space under/over minimum.
- ConnectionPoolGuard: SQLAlchemy pool (pool.status().checkout_count) over/under
  limit, pool.size() path, neither-path, exception path.
- RateLimiter: within limit, exceeded limit, window pruning via time.time
  patch, get_remaining_calls.
"""
import sys
import time
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.resource_guards as rg
from core.resource_guards import (
    ConnectionPoolGuard,
    CPUGuard,
    DiskSpaceGuard,
    IntegrationTimeoutError,
    MemoryGuard,
    RateLimiter,
    ResourceGuard,
)


class _FakePsutilModule(types.ModuleType):
    """Minimal stand-in for the psutil module."""

    def __init__(self, process=None, disk=None):
        super().__init__("psutil")
        self._process = process or MagicMock()
        self._disk = disk or MagicMock()
        self.Process = MagicMock(return_value=self._process)
        self.disk_usage = MagicMock(return_value=self._disk)


class TestIntegrationTimeoutError:
    def test_attributes(self):
        err = IntegrationTimeoutError("boom", timeout_seconds=5, operation="op")
        assert err.timeout_seconds == 5
        assert err.operation == "op"
        assert err.message == "boom"
        assert "boom" in str(err)


class TestWithTimeout:
    def test_success_returns_result(self):
        async def coro():
            return 42

        assert asyncio_run(ResourceGuard.with_timeout(coro(), 10)) == 42

    def test_timeout_raises_integration_timeout_error(self):
        async def coro():
            await asyncio_sleep(5)

        with pytest.raises(IntegrationTimeoutError) as ei:
            asyncio_run(ResourceGuard.with_timeout(coro(), 0.01, "my_op"))
        assert "my_op" in str(ei.value)
        assert "my_op timeout after 0.01s" == str(ei.value)


class TestTimeoutDecorator:
    def test_wraps_function_and_passes_args(self):
        @ResourceGuard.timeout_decorator(10)
        async def add(a, b, **kw):
            return a + b + kw.get("c", 0)

        assert asyncio_run(add(1, 2, c=3)) == 6
        assert add.__name__ == "add"

    def test_decorator_propagates_timeout(self):
        @ResourceGuard.timeout_decorator(0.01)
        async def slow():
            await asyncio_sleep(5)

        with pytest.raises(IntegrationTimeoutError):
            asyncio_run(slow())


class TestWithRetry:
    def test_success_on_first_attempt(self):
        fn = MagicMock(side_effect=lambda: AsyncMock(return_value="ok")())
        assert asyncio_run(ResourceGuard.with_retry(fn, max_retries=3)) == "ok"
        assert fn.call_count == 1

    def test_success_after_retries_with_backoff(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 3:
                return AsyncMock(side_effect=RuntimeError("flaky"))()
            return AsyncMock(return_value="recovered")()

        with patch.object(rg.asyncio, "sleep", new=AsyncMock()) as sleep_mock:
            result = asyncio_run(ResourceGuard.with_retry(fn, max_retries=4, backoff_sec=1.0))
        assert result == "recovered"
        assert calls["n"] == 3
        assert sleep_mock.await_args_list[0].args == (1.0,)
        assert sleep_mock.await_args_list[1].args == (2.0,)

    def test_exhaustion_raises_last_exception(self):
        def fn():
            return AsyncMock(side_effect=ValueError("always"))()

        with patch.object(rg.asyncio, "sleep", new=AsyncMock()):
            with pytest.raises(ValueError, match="always"):
                asyncio_run(ResourceGuard.with_retry(fn, max_retries=2))


class TestMemoryGuard:
    def test_get_memory_usage_with_psutil(self):
        fake = _FakePsutilModule()
        fake._process.memory_info.return_value = MagicMock(rss=512 * 1024 * 1024)
        with patch.dict(sys.modules, {"psutil": fake}):
            mb = MemoryGuard.get_memory_usage_mb()
        assert mb == pytest.approx(512.0, abs=0.5)

    def test_get_memory_usage_without_psutil(self):
        with patch.dict(sys.modules, {"psutil": None}):
            assert MemoryGuard.get_memory_usage_mb() == 0.0

    def test_check_within_limit(self):
        fake = _FakePsutilModule()
        fake._process.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)
        with patch.dict(sys.modules, {"psutil": fake}):
            assert MemoryGuard.check_memory_limit(max_mb=1024) is True

    def test_check_over_limit(self):
        fake = _FakePsutilModule()
        fake._process.memory_info.return_value = MagicMock(rss=2048 * 1024 * 1024)
        with patch.dict(sys.modules, {"psutil": fake}):
            assert MemoryGuard.check_memory_limit(max_mb=1024) is False


class TestCpuGuard:
    def test_get_cpu_usage(self):
        fake = _FakePsutilModule()
        fake._process.cpu_percent.return_value = 25.0
        with patch.dict(sys.modules, {"psutil": fake}):
            assert CPUGuard.get_cpu_usage_percent(interval=0.2) == 25.0
        fake._process.cpu_percent.assert_called_once_with(interval=0.2)

    def test_get_cpu_usage_exception(self):
        fake = _FakePsutilModule()
        fake._process.cpu_percent.side_effect = OSError("permission")
        with patch.dict(sys.modules, {"psutil": fake}):
            assert CPUGuard.get_cpu_usage_percent() == 0.0

    def test_get_cpu_usage_without_psutil(self):
        with patch.dict(sys.modules, {"psutil": None}):
            assert CPUGuard.get_cpu_usage_percent() == 0.0

    def test_check_cpu_within_limit(self):
        fake = _FakePsutilModule()
        fake._process.cpu_percent.return_value = 30.0
        with patch.dict(sys.modules, {"psutil": fake}):
            assert CPUGuard.check_cpu_limit(max_percent=80.0) is True

    def test_check_cpu_over_limit(self):
        fake = _FakePsutilModule()
        fake._process.cpu_percent.return_value = 95.0
        with patch.dict(sys.modules, {"psutil": fake}):
            assert CPUGuard.check_cpu_limit(max_percent=80.0) is False


class TestDiskSpaceGuard:
    def test_get_available_disk_mb(self):
        fake = _FakePsutilModule()
        fake._disk.free = 2048 * 1024 * 1024
        with patch.dict(sys.modules, {"psutil": fake}):
            assert DiskSpaceGuard.get_available_disk_mb("/tmp") == pytest.approx(2048.0)
        fake.disk_usage.assert_called_once_with("/tmp")

    def test_get_available_disk_exception(self):
        fake = _FakePsutilModule()
        fake.disk_usage.side_effect = OSError("io")
        with patch.dict(sys.modules, {"psutil": fake}):
            assert DiskSpaceGuard.get_available_disk_mb() == 0.0

    def test_get_available_disk_without_psutil(self):
        with patch.dict(sys.modules, {"psutil": None}):
            assert DiskSpaceGuard.get_available_disk_mb() == 0.0

    def test_check_disk_above_minimum(self):
        fake = _FakePsutilModule()
        fake._disk.free = 5000 * 1024 * 1024
        with patch.dict(sys.modules, {"psutil": fake}):
            assert DiskSpaceGuard.check_disk_space(min_free_mb=1024) is True

    def test_check_disk_below_minimum(self):
        fake = _FakePsutilModule()
        fake._disk.free = 512 * 1024 * 1024
        with patch.dict(sys.modules, {"psutil": fake}):
            assert DiskSpaceGuard.check_disk_space(min_free_mb=1024) is False


class TestConnectionPoolGuard:
    def test_sqlalchemy_pool_within_limit(self):
        pool = MagicMock()
        pool.pool.status.return_value.checkout_count = 5
        assert ConnectionPoolGuard.check_pool_limit(pool, max_connections=100) is True

    def test_sqlalchemy_pool_over_limit(self):
        pool = MagicMock()
        pool.pool.status.return_value.checkout_count = 150
        assert ConnectionPoolGuard.check_pool_limit(pool, max_connections=100) is False

    def test_size_api_within_limit(self):
        pool = SimpleNamespace(size=lambda: 3)
        assert ConnectionPoolGuard.check_pool_limit(pool, max_connections=10) is True

    def test_size_api_over_limit(self):
        pool = SimpleNamespace(size=lambda: 20)
        assert ConnectionPoolGuard.check_pool_limit(pool, max_connections=10) is False

    def test_unknown_pool_shape_returns_true(self):
        assert ConnectionPoolGuard.check_pool_limit(SimpleNamespace(), max_connections=10) is True

    def test_exception_returns_true(self):
        pool = MagicMock()
        pool.pool.status.side_effect = RuntimeError("broken")
        assert ConnectionPoolGuard.check_pool_limit(pool, max_connections=10) is True


def _fake_time(side_effect):
    """RateLimiter does `import time` locally — patch sys.modules instead."""
    fake = types.ModuleType("time")
    fake.time = MagicMock(side_effect=side_effect)
    return fake


class TestRateLimiter:
    def test_within_limit(self):
        limiter = RateLimiter(max_calls=3, time_window_seconds=60)
        with patch.dict(sys.modules, {"time": _fake_time([1.0, 2.0, 3.0, 3.0])}):
            assert limiter.check_rate_limit() is True
            assert limiter.check_rate_limit() is True
            assert limiter.check_rate_limit() is True
            assert limiter.get_remaining_calls() == 0

    def test_exceeds_limit(self):
        limiter = RateLimiter(max_calls=2, time_window_seconds=60)
        with patch.dict(sys.modules, {"time": _fake_time([1.0, 2.0, 3.0])}):
            assert limiter.check_rate_limit() is True
            assert limiter.check_rate_limit() is True
            assert limiter.check_rate_limit() is False

    def test_window_pruning_expired_calls(self):
        limiter = RateLimiter(max_calls=2, time_window_seconds=60)
        with patch.dict(sys.modules, {"time": _fake_time([0.0, 1.0, 100.0])}):
            assert limiter.check_rate_limit() is True
            assert limiter.check_rate_limit() is True
            # 100s later: the old calls have fallen out of the window
            assert limiter.check_rate_limit() is True

    def test_get_remaining_calls(self):
        limiter = RateLimiter(max_calls=10, time_window_seconds=60)
        with patch.dict(sys.modules, {"time": _fake_time([1.0, 2.0])}):
            assert limiter.check_rate_limit() is True
            assert limiter.get_remaining_calls() == 9

    def test_get_remaining_calls_never_negative(self):
        limiter = RateLimiter(max_calls=1, time_window_seconds=60)
        with patch.dict(sys.modules, {"time": _fake_time([1.0, 2.0])}):
            limiter.check_rate_limit()
            assert limiter.get_remaining_calls() == 0


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def asyncio_sleep(seconds):
    import asyncio

    return asyncio.sleep(seconds)
