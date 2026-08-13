# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/debug_collector (zero LLM spend, no network, no real DB).

- DebugCollector: start/stop (already-running + not-running guards), batch flush
  loop (sleep+flush, CancelledError break, generic error), collect_event (disabled,
  success ±Redis publish, generic publish exception → None), collect_state_snapshot
  (disabled, success — asserts operation_id/checkpoint_name/diff_from_previous are
  persisted on the model: BUG-FIX W70-1 regression, RedisError publish tolerated),
  collect_batch_events (disabled/empty/partial failure), _flush_batches (events +
  states with db commit, flush-error rollback, no-db-session drop), _publish_event /
  _publish_snapshot (RedisError branches), correlated_operation (provided + generated
  correlation id), get_buffer_stats, get_debug_collector/init_debug_collector
  (lazy singleton, already-initialized reuse, start on init).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.debug_collector as mod
from core.debug_collector import DebugCollector, get_debug_collector, init_debug_collector


class _FakeRedis:
    """Minimal redis client double: records publish payloads, optional errors."""

    def __init__(self, publish_error=None):
        self.published = []
        self.publish_error = publish_error

    def publish(self, channel, message):
        if self.publish_error is not None:
            raise self.publish_error
        self.published.append((channel, message))


@pytest.fixture()
def collector():
    return DebugCollector(batch_size_ms=5)


async def _drain(collector):
    """Let pending flush tasks finish and cancel the collector cleanly."""
    collector._running = False
    if collector._flush_task:
        collector._flush_task.cancel()
        try:
            await collector._flush_task
        except (asyncio.CancelledError, RuntimeError):
            pass
        collector._flush_task = None


# ============================================================================
# start / stop
# ============================================================================

class TestLifecycle:
    async def test_start_creates_flush_task_and_hooks(self, collector):
        collector.start()
        assert collector._running is True
        assert collector._flush_task is not None
        await _drain(collector)

    async def test_start_when_already_running_warns(self, collector):
        collector._running = True
        with patch.object(collector.logger, "warning") as warn:
            collector.start()
        warn.assert_called_once()
        await _drain(collector)

    async def test_stop_when_not_running_is_noop(self, collector):
        collector.stop()
        assert collector._running is False

    async def test_stop_cancels_task_and_flushes(self, collector):
        collector.start()
        with patch.object(collector, "_flush_batches", new=AsyncMock()) as flush:
            collector.stop()
            await asyncio.sleep(0.02)
        assert collector._running is False
        assert collector._flush_task is None
        assert flush.await_count == 1

    async def test_batch_flush_loop_sleep_flush_and_exit(self):
        collector = DebugCollector(batch_size_ms=1)
        collector.start()
        with patch.object(collector, "_flush_batches", new=AsyncMock()) as flush:
            await asyncio.sleep(0.03)
            collector._running = False
            await asyncio.wait_for(collector._flush_task, timeout=1)
        assert flush.await_count >= 1

    async def test_batch_flush_loop_cancelled_error_breaks(self):
        collector = DebugCollector(batch_size_ms=1)
        collector._running = True
        collector._flush_task = asyncio.create_task(collector._batch_flush_loop())
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
            await asyncio.wait_for(collector._flush_task, timeout=1)
        assert collector._flush_task.done()

    async def test_batch_flush_loop_generic_error_logged(self, collector):
        collector._running = True

        def _sleep(*a, **k):
            collector._running = False
            return asyncio.sleep(0)

        with patch("asyncio.sleep", side_effect=_sleep):
            with patch.object(collector, "_flush_batches", new=AsyncMock(side_effect=RuntimeError("boom"))):
                with patch.object(collector.logger, "error") as err:
                    await collector._batch_flush_loop()
        err.assert_called_once()
        assert "Batch flush loop error" in str(err.call_args)


# ============================================================================
# collect_event
# ============================================================================

class TestCollectEvent:
    async def test_collect_event_disabled(self, collector):
        with patch.object(mod, "DEBUG_SYSTEM_ENABLED", False):
            assert await collector.collect_event(
                "log", "agent", "agent-1", "corr-1", message="hi"
            ) is None

    async def test_collect_event_buffered_no_redis(self, collector):
        event = await collector.collect_event(
            "log", "agent", "agent-1", "corr-1", level="INFO", message="started",
            data={"k": "v"}, event_metadata={"tag": "t"}, parent_event_id="parent-1",
        )
        assert event is not None
        assert event.id and event.event_type == "log"
        assert event.component_id == "agent-1"
        assert event.correlation_id == "corr-1"
        assert event.parent_event_id == "parent-1"
        assert event.data == {"k": "v"}
        assert event.event_metadata == {"tag": "t"}
        assert event.timestamp is not None
        assert event in collector._event_buffer

    async def test_collect_event_publishes_to_redis(self, collector):
        redis = _FakeRedis()
        collector.redis_client = redis
        event = await collector.collect_event(
            "error", "agent", "agent-1", "corr-1", level="ERROR", message="boom"
        )
        assert event is not None
        assert len(redis.published) == 1
        channel, payload = redis.published[0]
        assert channel == "debug:events"
        assert "type" in payload and event.id in payload

    async def test_collect_event_redis_publish_rediserror_swallowed(self, collector):
        from redis.exceptions import RedisError

        collector.redis_client = _FakeRedis(publish_error=RedisError("down"))
        event = await collector.collect_event(
            "log", "agent", "agent-1", "corr-1", message="hi"
        )
        assert event is not None

    async def test_collect_event_generic_publish_error_returns_none(self, collector):
        collector.redis_client = _FakeRedis(publish_error=RuntimeError("hard"))
        with patch.object(collector.logger, "error") as err:
            event = await collector.collect_event(
                "log", "agent", "agent-1", "corr-1", message="hi"
            )
        assert event is None
        err.assert_called_once()

    async def test_collect_event_redis_disabled_flag(self, collector):
        redis = _FakeRedis()
        collector.redis_client = redis
        with patch.object(mod, "DEBUG_REDIS_ENABLED", False):
            event = await collector.collect_event(
                "log", "agent", "agent-1", "corr-1", message="hi"
            )
        assert event is not None
        assert redis.published == []


# ============================================================================
# collect_state_snapshot
# ============================================================================

class TestCollectStateSnapshot:
    async def test_collect_state_snapshot_disabled(self, collector):
        with patch.object(mod, "DEBUG_SYSTEM_ENABLED", False):
            assert await collector.collect_state_snapshot(
                "agent", "agent-1", "op-1", {"status": "running"}
            ) is None

    async def test_collect_state_snapshot_success_and_persists_operation(self, collector):
        """BUG-FIX W70-1 regression: DebugStateSnapshot must accept
        operation_id/checkpoint_name/diff_from_previous (lost columns)."""
        snapshot = await collector.collect_state_snapshot(
            "agent", "agent-1", "op-456",
            {"status": "running", "progress": 0.5},
            checkpoint_name="checkpoint-1",
            snapshot_type="incremental",
            diff_from_previous={"progress": 0.4},
        )
        assert snapshot is not None
        assert snapshot.operation_id == "op-456"
        assert snapshot.checkpoint_name == "checkpoint-1"
        assert snapshot.snapshot_type == "incremental"
        assert snapshot.diff_from_previous == {"progress": 0.4}
        assert snapshot.state_data == {"status": "running", "progress": 0.5}
        assert snapshot.captured_at is not None
        assert snapshot in collector._state_buffer

    async def test_collect_state_snapshot_publishes_to_redis(self, collector):
        redis = _FakeRedis()
        collector.redis_client = redis
        snapshot = await collector.collect_state_snapshot(
            "agent", "agent-1", "op-1", {"status": "ok"}
        )
        assert snapshot is not None
        assert len(redis.published) == 1
        assert "snapshot" in redis.published[0][1]

    async def test_collect_state_snapshot_redis_error_swallowed(self, collector):
        from redis.exceptions import RedisError

        collector.redis_client = _FakeRedis(publish_error=RedisError("down"))
        snapshot = await collector.collect_state_snapshot(
            "agent", "agent-1", "op-1", {"status": "ok"}
        )
        assert snapshot is not None

    async def test_collect_state_snapshot_generic_error_returns_none(self, collector):
        collector.redis_client = _FakeRedis(publish_error=RuntimeError("hard"))
        with patch.object(collector.logger, "error") as err:
            snapshot = await collector.collect_state_snapshot(
                "agent", "agent-1", "op-1", {"status": "ok"}
            )
        assert snapshot is None
        err.assert_called_once()


# ============================================================================
# batch collection + flushing
# ============================================================================

class TestBatch:
    async def test_collect_batch_events_disabled(self, collector):
        with patch.object(mod, "DEBUG_SYSTEM_ENABLED", False):
            assert await collector.collect_batch_events([{"event_type": "log"}]) == []

    async def test_collect_batch_events_all_success(self, collector):
        events = await collector.collect_batch_events(
            [
                {"event_type": "log", "component_type": "agent", "component_id": "a",
                 "correlation_id": "c1", "message": "one"},
                {"event_type": "error", "component_type": "agent", "component_id": "b",
                 "correlation_id": "c2", "level": "ERROR", "message": "two"},
            ]
        )
        assert len(events) == 2
        assert all(e is not None for e in events)

    async def test_collect_batch_events_partial_failure(self, collector):
        events = await collector.collect_batch_events(
            [
                {"event_type": "log", "component_type": "agent", "component_id": "a",
                 "correlation_id": "c1", "message": "ok"},
                {"event_type": "log"},  # missing required kwargs → None entry
            ]
        )
        assert events[0] is not None
        assert events[1] is None

    async def test_flush_batches_commits_events_and_states(self):
        collector = DebugCollector()
        db = MagicMock()
        collector.db_session = db
        await collector.collect_event("log", "agent", "a", "c", message="m")
        await collector.collect_state_snapshot("agent", "a", "op", {"x": 1})
        await collector._flush_batches()
        assert db.add_all.call_count == 2
        assert db.commit.call_count == 2
        assert collector._event_buffer == []
        assert collector._state_buffer == []

    async def test_flush_batches_event_commit_error_rolls_back(self):
        collector = DebugCollector()
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        collector.db_session = db
        await collector.collect_event("log", "agent", "a", "c", message="m")
        with patch.object(collector.logger, "error") as err:
            await collector._flush_batches()
        assert db.rollback.call_count == 1
        err.assert_called_once()

    async def test_flush_batches_state_commit_error_rolls_back(self):
        collector = DebugCollector()
        db = MagicMock()
        collector.db_session = db
        await collector.collect_state_snapshot("agent", "a", "op", {"x": 1})
        db.commit.side_effect = RuntimeError("db down")
        with patch.object(collector.logger, "error") as err:
            await collector._flush_batches()
        assert db.rollback.call_count == 1
        err.assert_called_once()

    async def test_flush_batches_without_db_drops_buffers(self):
        collector = DebugCollector()
        await collector.collect_event("log", "agent", "a", "c", message="m")
        await collector.collect_state_snapshot("agent", "a", "op", {"x": 1})
        await collector._flush_batches()
        assert collector._event_buffer == []
        assert collector._state_buffer == []

    async def test_publish_event_redis_error_logged(self):
        from redis.exceptions import RedisError

        collector = DebugCollector()
        collector.redis_client = _FakeRedis(publish_error=RedisError("down"))
        event = MagicMock()
        event.id = "e-1"
        event.event_type = "log"
        event.component_type = "agent"
        event.component_id = "a"
        event.correlation_id = "c"
        event.parent_event_id = None
        event.level = "INFO"
        event.message = "m"
        event.data = {}
        event.event_metadata = {}
        event.timestamp = None
        with patch.object(collector.logger, "error") as err:
            await collector._publish_event(event)
        err.assert_called_once()

    async def test_publish_event_no_redis_noop(self, collector):
        await collector._publish_event(MagicMock())  # no redis → return
        assert collector.redis_client is None

    async def test_publish_snapshot_redis_error_logged(self):
        from redis.exceptions import RedisError

        collector = DebugCollector()
        collector.redis_client = _FakeRedis(publish_error=RedisError("down"))
        snapshot = MagicMock()
        snapshot.id = "s-1"
        snapshot.component_type = "agent"
        snapshot.component_id = "a"
        snapshot.operation_id = "op-1"
        snapshot.checkpoint_name = None
        snapshot.state_data = {}
        snapshot.diff_from_previous = None
        snapshot.snapshot_type = "full"
        snapshot.captured_at = None
        with patch.object(collector.logger, "error") as err:
            await collector._publish_snapshot(snapshot)
        err.assert_called_once()

    async def test_publish_snapshot_no_redis_noop(self, collector):
        await collector._publish_snapshot(MagicMock())


# ============================================================================
# correlated operation + stats
# ============================================================================

class TestContextAndStats:
    async def test_correlated_operation_with_provided_id(self, collector):
        async with collector.correlated_operation(correlation_id="fixed-id") as corr:
            assert corr == "fixed-id"
            await collector.collect_event(
                "log", "agent", "a", corr, message="inside"
            )
        assert collector._event_buffer[-1].correlation_id == "fixed-id"

    async def test_correlated_operation_generates_id(self, collector):
        async with collector.correlated_operation(
            component_type="agent", component_id="a-1"
        ) as corr:
            assert corr is not None and len(corr) == 36

    async def test_correlated_operation_cleans_up_on_exception(self, collector):
        with pytest.raises(RuntimeError):
            async with collector.correlated_operation(correlation_id="x"):
                raise RuntimeError("inner")
        assert collector._running is False  # context exits cleanly

    async def test_get_buffer_stats(self, collector):
        await collector.collect_event("log", "agent", "a", "c", message="m")
        await collector.collect_state_snapshot("agent", "a", "op", {"x": 1})
        stats = collector.get_buffer_stats()
        assert stats["event_buffer_size"] == 1
        assert stats["state_buffer_size"] == 1
        assert stats["running"] is False


# ============================================================================
# global singleton
# ============================================================================

class TestGlobalInstance:
    def test_get_debug_collector_returns_none_before_init(self):
        with patch.object(mod, "_collector_instance", None):
            assert get_debug_collector() is None

    async def test_init_debug_collector_creates_and_starts(self):
        with patch.object(mod, "_collector_instance", None):
            instance = init_debug_collector()
            assert isinstance(instance, DebugCollector)
            assert instance._running is True
            assert get_debug_collector() is instance
            await _drain(instance)

    async def test_init_debug_collector_reuses_existing(self):
        with patch.object(mod, "_collector_instance", None):
            first = init_debug_collector()
            second = init_debug_collector()
            assert first is second
            await _drain(first)
