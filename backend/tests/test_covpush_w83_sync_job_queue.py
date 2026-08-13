# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/sync_job_queue.py to >=95% (fake in-memory Redis
async client + patched env; no real Redis, no network).

Covers:
- __init__: redis_url resolution order, suspended flag, fly app name default.
- client property: lazy sync client creation (rediss vs redis scheme),
  exception path, suspended/no-url -> None.
- async_client: lazy async client creation, exception path, cached.
- enqueue: missing job_id/tenant_id ValueError, metadata (enqueued_at,
  priority), scoring, no-client warning path.
- dequeue: empty queue timeout, empty queue poll loop, returns highest
  priority job, removes from queue.
- acquire_lock: default + custom timeout, nx semantics, no-client -> True.
- release_lock: no lock, wrong worker, correct worker deletes, no-client.
- complete: delegates to release_lock.
- get_queue_depth: with/without client.
- ensure_worker_running: always True.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.sync_job_queue as mod
from core.sync_job_queue import JobPriority, SyncJobQueue


class FakeAsyncRedis:
    """Minimal in-memory redis.asyncio stand-in with zset semantics."""

    def __init__(self):
        self.zsets = {}   # key -> {member: score}
        self.strings = {}  # key -> value

    async def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update(mapping)

    async def zrange(self, key, start, end):
        members = [m for m, _ in sorted(self.zsets.get(key, {}).items(), key=lambda kv: kv[1])]
        stop = None if end < 0 else end + 1
        return members[start:stop]

    async def zrem(self, key, *members):
        for m in members:
            self.zsets.get(key, {}).pop(m, None)

    async def zcard(self, key):
        return len(self.zsets.get(key, {}))

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.strings:
            return False
        self.strings[key] = value
        return True

    async def get(self, key):
        return self.strings.get(key)

    async def delete(self, key):
        self.strings.pop(key, None)
        return 1


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture()
def queue():
    with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
        q = SyncJobQueue()
        fake = FakeAsyncRedis()
        # Property cache-slot: async_client returns this directly.
        q._async_client = fake
        q._fake = fake
        yield q


def _job(**over):
    data = {"job_id": "j-1", "tenant_id": "t-1"}
    data.update(over)
    return data


# ============================================================================
# __init__ / client resolution
# ============================================================================

def test_init_url_resolution_order():
    with patch.dict(os.environ, {
        "DRAGONFLY_URL": "redis://dragonfly:6379",
        "UPSTASH_REDIS_URL": "redis://upstash:6379",
        "REDIS_URL": "redis://plain:6379",
    }, clear=True):
        assert SyncJobQueue().redis_url == "redis://dragonfly:6379"


def test_init_suspended_flag():
    with patch.dict(os.environ, {"SUSPEND_REDIS": "true", "REDIS_URL": ""}, clear=True):
        assert SyncJobQueue().suspended is True


def test_init_default_fly_app():
    with patch.dict(os.environ, {}, clear=True):
        assert SyncJobQueue().fly_app_name == "atom-upstream"


def test_client_property_creates_sync_redis():
    with patch.dict(os.environ, {"REDIS_URL": "rediss://:pass@host:6380"}, clear=True), \
         patch("redis.Redis") as redis_cls:
        q = SyncJobQueue()
        client = q.client
        assert client is redis_cls.return_value
        assert q.client is client  # cached


def test_client_property_none_when_suspended():
    with patch.dict(os.environ, {"SUSPEND_REDIS": "true", "REDIS_URL": "redis://x"}, clear=True):
        assert SyncJobQueue().client is None


def test_client_property_none_without_url():
    with patch.dict(os.environ, {}, clear=True):
        assert SyncJobQueue().client is None


def test_client_property_exception_returns_none():
    with patch.dict(os.environ, {"REDIS_URL": "redis://x"}, clear=True), \
         patch("redis.Redis", side_effect=RuntimeError("no redis lib")):
        assert SyncJobQueue().client is None


def test_async_client_creates_aioredis():
    with patch.dict(os.environ, {"REDIS_URL": "redis://host:6379"}, clear=True), \
         patch("redis.asyncio.from_url", new=AsyncMock(return_value="ac")) as from_url:
        q = SyncJobQueue()
        assert _run(q.async_client) == "ac"
        from_url.assert_awaited_once()


def test_async_client_none_when_suspended():
    with patch.dict(os.environ, {"SUSPEND_REDIS": "true", "REDIS_URL": "redis://x"}, clear=True):
        assert _run(SyncJobQueue().async_client) is None


def test_async_client_exception_returns_none():
    with patch.dict(os.environ, {"REDIS_URL": "redis://x"}, clear=True), \
         patch("redis.asyncio.from_url", side_effect=RuntimeError("no lib")):
        assert _run(SyncJobQueue().async_client) is None


# ============================================================================
# enqueue
# ============================================================================

def test_enqueue_requires_job_id():
    q = SyncJobQueue()
    with pytest.raises(ValueError, match="job_id"):
        _run(q.enqueue({"tenant_id": "t-1"}))


def test_enqueue_requires_tenant_id():
    q = SyncJobQueue()
    with pytest.raises(ValueError, match="tenant_id"):
        _run(q.enqueue({"job_id": "j-1"}))


def test_enqueue_zadd_called(queue):
    q = queue
    job_id = _run(q.enqueue(_job(), priority=JobPriority.HIGH))
    assert job_id == "j-1"
    assert len(q._fake.zsets[SyncJobQueue.QUEUE_KEY]) == 1
    (stored_json, score), = q._fake.zsets[SyncJobQueue.QUEUE_KEY].items()
    stored = json.loads(stored_json)
    assert stored["priority"] == "HIGH"
    assert stored["enqueued_at"]
    assert stored["job_id"] == "j-1"
    # HIGH(10) * 1e6 minus ms timestamp: negative but ordered by priority first
    assert score < 0


def test_enqueue_priority_ordering(queue):
    q = queue
    _run(q.enqueue(_job(job_id="low"), priority=JobPriority.LOW))
    _run(q.enqueue(_job(job_id="urgent"), priority=JobPriority.URGENT))
    first = _run(q.dequeue(timeout=1))
    assert first["job_id"] == "urgent"


def test_dequeue_fifo_order_for_same_priority(queue):
    # Same priority: earlier enqueued must be dequeued first (score =
    # priority*1e6 - timestamp_ms makes earlier timestamps larger scores).
    # Freeze + advance so the two enqueues can't land in the same
    # millisecond (equal zset scores sort lexicographically — flaky).
    from freezegun import freeze_time
    q = queue
    with freeze_time("2026-08-13 12:00:00"):
        _run(q.enqueue(_job(job_id="first")))
    with freeze_time("2026-08-13 12:00:01"):
        _run(q.enqueue(_job(job_id="second")))
    assert _run(q.dequeue(timeout=1))["job_id"] == "first"
    assert _run(q.dequeue(timeout=1))["job_id"] == "second"


def test_enqueue_no_client_logs_warning():
    with patch.dict(os.environ, {}, clear=True):
        q = SyncJobQueue()
        assert _run(q.enqueue(_job())) == "j-1"


# ============================================================================
# dequeue
# ============================================================================

def test_dequeue_no_client_returns_none():
    with patch.dict(os.environ, {}, clear=True):
        assert _run(SyncJobQueue().dequeue(timeout=1)) is None


def test_dequeue_empty_queue_times_out(queue):
    assert _run(queue.dequeue(timeout=1)) is None


def test_dequeue_empty_queue_polls_then_finds_job(queue):
    async def scenario():
        q = queue
        asyncio.get_event_loop().call_later(2, lambda: None)  # keep loop busy

        async def populate():
            await asyncio.sleep(0.2)
            await q.enqueue(_job(job_id="late"))
        task = asyncio.ensure_future(populate())
        result = await q.dequeue(timeout=5)
        await task
        return result
    result = _run(scenario())
    assert result["job_id"] == "late"


def test_dequeue_returns_and_removes_job(queue):
    q = queue
    _run(q.enqueue(_job(job_id="only")))
    result = _run(q.dequeue(timeout=1))
    assert result["job_id"] == "only"
    assert len(q._fake.zsets[SyncJobQueue.QUEUE_KEY]) == 0


# ============================================================================
# acquire_lock / release_lock / complete
# ============================================================================

def test_acquire_lock_default_timeout(queue):
    q = queue
    ok = _run(q.acquire_lock("j-1", "worker-1"))
    assert ok is True
    stored = json.loads(q._fake.strings[f"{SyncJobQueue.PROCESSING_KEY}:j-1"])
    assert stored["worker_id"] == "worker-1"
    expires = datetime.fromisoformat(stored["expires_at"])
    assert expires > datetime.now(timezone.utc) - timedelta(minutes=1)


def test_acquire_lock_custom_timeout_and_nx_semantics(queue):
    q = queue
    assert _run(q.acquire_lock("j-1", "w1", timeout=10)) is True
    assert _run(q.acquire_lock("j-1", "w2", timeout=10)) is False
    assert _run(q.acquire_lock("j-2", "w2", timeout=10)) is True


def test_acquire_lock_no_client_returns_true():
    with patch.dict(os.environ, {}, clear=True):
        assert _run(SyncJobQueue().acquire_lock("j-1", "w1")) is True


def test_release_lock_no_lock_returns_false(queue):
    assert _run(queue.release_lock("ghost", "w1")) is False


def test_release_lock_wrong_worker_returns_false(queue):
    q = queue
    _run(q.acquire_lock("j-1", "w1"))
    assert _run(q.release_lock("j-1", "w2")) is False
    assert f"{SyncJobQueue.PROCESSING_KEY}:j-1" in q._fake.strings


def test_release_lock_correct_worker_deletes(queue):
    q = queue
    _run(q.acquire_lock("j-1", "w1"))
    assert _run(q.release_lock("j-1", "w1")) is True
    assert f"{SyncJobQueue.PROCESSING_KEY}:j-1" not in q._fake.strings


def test_release_lock_no_client_returns_true():
    with patch.dict(os.environ, {}, clear=True):
        assert _run(SyncJobQueue().release_lock("j-1", "w1")) is True


def test_complete_delegates_to_release_lock(queue):
    q = queue
    _run(q.acquire_lock("j-1", "w1"))
    assert _run(q.complete("j-1", "w1")) is True
    assert f"{SyncJobQueue.PROCESSING_KEY}:j-1" not in q._fake.strings


# ============================================================================
# metrics / misc
# ============================================================================

def test_get_queue_depth(queue):
    q = queue
    _run(q.enqueue(_job(job_id="a")))
    _run(q.enqueue(_job(job_id="b")))
    assert _run(q.get_queue_depth()) == 2


def test_get_queue_depth_no_client():
    with patch.dict(os.environ, {}, clear=True):
        assert _run(SyncJobQueue().get_queue_depth()) == 0


def test_ensure_worker_running_placeholder():
    assert _run(SyncJobQueue().ensure_worker_running()) is True


def test_job_priority_values():
    assert JobPriority.LOW.value == 1
    assert JobPriority.NORMAL.value == 5
    assert JobPriority.HIGH.value == 10
    assert JobPriority.URGENT.value == 20
