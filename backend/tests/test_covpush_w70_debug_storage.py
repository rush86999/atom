# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/debug_storage (in-memory SQLite + fake Redis, no network).

- HybridDebugStorage: store_event (hot+warm, hot-only, warm-only, commit
  failure → False), get_event (hot hit, warm hit + promote, cold archive hit,
  miss), query_events (per-filter narrowing, time range, pagination, exception),
  store_insight (hot+warm round-trip incl. resolution_notes/expires_at —
  BUG-FIX W70-3 regression — commit failure), get_insight (hot, warm promote,
  miss), query_insights (type/severity/scope/resolved filters, time range,
  exception), store_state_snapshot (hot+warm, commit failure), get_state_snapshot
  (latest, miss, exception), migrate_hot_to_warm no-op, migrate_warm_to_cold
  (archive+delete, none-old, exception→rollback), cleanup_expired_data (old
  archive removed, fresh kept, glob failure), hot-tier RedisError paths for
  events/insights/snapshots, warm-tier getters (found/miss/exception), cold-tier
  get (found/miss/exception), _write_archive/_read_archive (±failure),
  serializers (±timestamps), _parse_time_range (all 5 branches).
"""
import gzip
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401 (register models)
    DebugEvent,
    DebugInsight,
    DebugMetric,
    DebugStateSnapshot,
)
from core.debug_storage import HybridDebugStorage


class _FakeRedis:
    """dict-backed redis double with per-call failure injection."""

    def __init__(self):
        self.data = {}

    def setex(self, key, ttl, value):
        if getattr(self, "fail_setex", False):
            raise RedisError("redis down")
        self.data[key] = (ttl, value)

    def get(self, key):
        if getattr(self, "fail_get", False):
            raise RedisError("redis down")
        entry = self.data.get(key)
        return entry[1] if entry else None


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def redis():
    return _FakeRedis()


@pytest.fixture()
def storage(db, redis, tmp_path):
    return HybridDebugStorage(db_session=db, redis_client=redis, archive_path=str(tmp_path))


def _event(db, eid, *, component_type="agent", component_id="agent-1",
           correlation_id="corr-1", level="INFO", event_type="log",
           ts=None, message="msg"):
    event = DebugEvent(
        id=eid,
        event_type=event_type,
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=message,
        data={"k": "v"},
        timestamp=ts if ts is not None else datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    return event


def _insight(db, iid, **overrides):
    fields = dict(
        id=iid, insight_type="error", severity="warning", title=f"T {iid}",
        description="D", summary="S", evidence={"e": 1}, confidence_score=0.9,
        suggestions=["s1"], resolved=False, scope="component",
        affected_components=[{"type": "agent", "id": "agent-1"}],
        generated_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    insight = DebugInsight(**fields)
    db.add(insight)
    db.commit()
    return insight


def _snapshot(db, sid, *, component_type="agent", component_id="agent-1",
              snapshot_type="full", state_data=None, captured_at=None):
    snap = DebugStateSnapshot(
        id=sid,
        component_type=component_type,
        component_id=component_id,
        snapshot_type=snapshot_type,
        state_data=state_data if state_data is not None else {"status": "ok"},
        captured_at=captured_at if captured_at is not None else datetime.now(timezone.utc),
    )
    db.add(snap)
    db.commit()
    return snap


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")


# ============================================================================
# Event storage
# ============================================================================

class TestEventStorage:
    async def test_store_event_hot_and_warm(self, db, redis, storage):
        event = _event(db, "e-1")
        assert await storage.store_event(event) is True
        assert redis.data[f"debug:event:e-1"][1] is not None
        assert db.query(DebugEvent).filter(DebugEvent.id == "e-1").count() == 1

    async def test_store_event_hot_only(self, db, redis, storage):
        event = _event(db, "e-2")
        assert await storage.store_event(event, store_warm=False) is True
        assert f"debug:event:e-2" in redis.data

    async def test_store_event_warm_only(self, db, redis, storage):
        event = _event(db, "e-3")
        assert await storage.store_event(event, store_hot=False) is True
        assert f"debug:event:e-3" not in redis.data

    async def test_store_event_no_redis_no_db(self, db, storage):
        event = _event(db, "e-4")
        assert await storage.store_event(event, store_hot=False, store_warm=False) is True

    async def test_store_event_commit_failure(self, storage):
        event = MagicMock()
        event.id = "e-5"
        with patch.object(storage.db, "commit", side_effect=RuntimeError("commit failed")):
            with patch.object(storage.logger, "error") as err:
                assert await storage.store_event(event) is False
        err.assert_called_once()

    async def test_get_event_hot_hit(self, db, redis, storage):
        event = _event(db, "e-hot")
        await storage.store_event(event, store_warm=False)
        result = await storage.get_event("e-hot")
        assert result["id"] == "e-hot"
        assert result["event_type"] == "log"

    async def test_get_event_warm_hit_promotes(self, db, redis, storage):
        event = _event(db, "e-warm")
        result = await storage.get_event("e-warm")
        assert result["id"] == "e-warm"
        assert f"debug:event:e-warm" in redis.data  # promoted to hot

    async def test_get_event_cold_hit(self, storage):
        await storage._write_archive(
            storage.archive_path / "events_2026-08-01.json.gz",
            [{"id": "e-cold", "event_type": "log"}],
        )
        result = await storage.get_event("e-cold")
        assert result["id"] == "e-cold"

    async def test_get_event_miss(self, db, storage):
        assert await storage.get_event("e-missing") is None

    async def test_query_events_filters(self, db, storage):
        _event(db, "q1", component_type="agent", component_id="a-1",
               correlation_id="c1", level="INFO", event_type="log")
        _event(db, "q2", component_type="agent", component_id="a-1",
               correlation_id="c2", level="ERROR", event_type="log")
        _event(db, "q3", component_type="browser", component_id="b-1",
               correlation_id="c3", level="INFO", event_type="error")
        assert len(await storage.query_events(component_type="agent")) == 2
        assert len(await storage.query_events(component_id="a-1")) == 2
        assert len(await storage.query_events(correlation_id="c2")) == 1
        assert len(await storage.query_events(event_type="error")) == 1
        assert len(await storage.query_events(level="ERROR")) == 1
        assert len(await storage.query_events(
            component_type="agent", component_id="a-1", correlation_id="c1",
            event_type="log", level="INFO")) == 1

    async def test_query_events_time_range_and_pagination(self, db, storage):
        old_ts = datetime.now(timezone.utc) - timedelta(hours=2)
        _event(db, "old-1", ts=old_ts)
        _event(db, "new-1")
        _event(db, "new-2")
        results = await storage.query_events(time_range="last_1h")
        assert {r["id"] for r in results} == {"new-1", "new-2"}
        paged = await storage.query_events(time_range="last_1h", limit=1, offset=1)
        assert len(paged) == 1

    async def test_query_events_bad_time_range_ignored(self, db, storage):
        _event(db, "t-1", ts=datetime.now(timezone.utc) - timedelta(days=40))
        results = await storage.query_events(time_range="bogus")
        assert len(results) == 1

    async def test_query_events_exception(self):
        storage = HybridDebugStorage(db_session=_BadSession(), redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        assert await storage.query_events() == []


# ============================================================================
# Insight storage
# ============================================================================

class TestInsightStorage:
    async def test_store_insight_round_trip_with_all_fields(self, db, redis, storage):
        """BUG-FIX W70-3 regression: insight serialization must not blow up on
        resolution_notes/expires_at (columns were lost from the model)."""
        insight = _insight(
            db, "ins-full",
            resolution_notes="fixed via retry",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert await storage.store_insight(insight) is True
        raw = redis.data["debug:insight:ins-full"][1]
        decoded = json.loads(raw)
        assert decoded["resolution_notes"] == "fixed via retry"
        assert decoded["expires_at"] is not None

    async def test_store_insight_hot_only(self, db, redis, storage):
        insight = _insight(db, "ins-hot")
        assert await storage.store_insight(insight, store_warm=False) is True
        assert "debug:insight:ins-hot" in redis.data

    async def test_store_insight_commit_failure(self, storage):
        insight = MagicMock()
        insight.id = "ins-fail"
        with patch.object(storage.db, "commit", side_effect=RuntimeError("nope")):
            with patch.object(storage.logger, "error"):
                assert await storage.store_insight(insight) is False

    async def test_get_insight_hot(self, db, redis, storage):
        insight = _insight(db, "ins-get-hot")
        await storage.store_insight(insight, store_warm=False)
        result = await storage.get_insight("ins-get-hot")
        assert result["id"] == "ins-get-hot"
        assert result["title"] == "T ins-get-hot"

    async def test_get_insight_warm_promotes(self, db, redis, storage):
        _insight(db, "ins-get-warm")
        result = await storage.get_insight("ins-get-warm")
        assert result["id"] == "ins-get-warm"
        assert "debug:insight:ins-get-warm" in redis.data

    async def test_get_insight_miss(self, db, storage):
        assert await storage.get_insight("ins-missing") is None

    async def test_query_insights_filters(self, db, storage):
        _insight(db, "i1", insight_type="error", severity="critical",
                 scope="system", resolved=False)
        _insight(db, "i2", insight_type="performance", severity="warning",
                 scope="component", resolved=True)
        assert len(await storage.query_insights(insight_type="error")) == 1
        assert len(await storage.query_insights(severity="warning")) == 1
        assert len(await storage.query_insights(scope="system")) == 1
        assert len(await storage.query_insights(resolved=True)) == 1
        assert len(await storage.query_insights()) == 2

    async def test_query_insights_time_range(self, db, storage):
        _insight(db, "i-old", generated_at=datetime.now(timezone.utc) - timedelta(days=2))
        _insight(db, "i-new", generated_at=datetime.now(timezone.utc))
        results = await storage.query_insights(time_range="last_24h")
        assert [r["id"] for r in results] == ["i-new"]

    async def test_query_insights_exception(self):
        storage = HybridDebugStorage(db_session=_BadSession(), redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        assert await storage.query_insights() == []


# ============================================================================
# State snapshot storage
# ============================================================================

class TestStateSnapshotStorage:
    async def test_store_snapshot_hot_and_warm(self, db, redis, storage):
        snap = _snapshot(db, "snap-1")
        assert await storage.store_state_snapshot(snap) is True
        assert "debug:state:snap-1" in redis.data

    async def test_store_snapshot_hot_only(self, db, redis, storage):
        snap = _snapshot(db, "snap-2")
        assert await storage.store_state_snapshot(snap, store_warm=False) is True
        assert "debug:state:snap-2" in redis.data

    async def test_store_snapshot_commit_failure(self, storage):
        snap = MagicMock()
        snap.id = "snap-fail"
        with patch.object(storage.db, "commit", side_effect=RuntimeError("nope")):
            with patch.object(storage.logger, "error"):
                assert await storage.store_state_snapshot(snap) is False

    async def test_get_snapshot_latest(self, db, storage):
        _snapshot(db, "snap-old", state_data={"step": 1},
                  captured_at=datetime.now(timezone.utc) - timedelta(minutes=5))
        _snapshot(db, "snap-new", state_data={"step": 2},
                  captured_at=datetime.now(timezone.utc))
        result = await storage.get_state_snapshot("agent", "agent-1")
        assert result["id"] == "snap-new"
        assert result["state_data"] == {"step": 2}
        assert result["snapshot_metadata"] is None

    async def test_get_snapshot_miss(self, db, storage):
        assert await storage.get_state_snapshot("agent", "ghost") is None

    async def test_get_snapshot_exception(self):
        storage = HybridDebugStorage(db_session=_BadSession(), redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        with patch.object(storage.logger, "error"):
            assert await storage.get_state_snapshot("agent", "a") is None


# ============================================================================
# Migration / archival / cleanup
# ============================================================================

class TestMigrationAndCleanup:
    async def test_migrate_hot_to_warm_noop(self, storage):
        await storage.migrate_hot_to_warm()  # no-op, must not raise

    async def test_migrate_warm_to_cold_archives_and_deletes(self, db, storage):
        old_ts = datetime.now(timezone.utc) - timedelta(hours=200)
        _event(db, "arch-1", ts=old_ts)
        _event(db, "arch-2", ts=old_ts)
        _event(db, "fresh-1", ts=datetime.now(timezone.utc))
        with patch.object(storage.logger, "info"):
            await storage.migrate_warm_to_cold()
        archive_files = list(storage.archive_path.glob("events_*.json.gz"))
        assert len(archive_files) == 1
        with gzip.open(archive_files[0], "rt", encoding="utf-8") as f:
            archived = json.load(f)
        assert {e["id"] for e in archived} == {"arch-1", "arch-2"}
        remaining = [e.id for e in db.query(DebugEvent).all()]
        assert remaining == ["fresh-1"]

    async def test_migrate_warm_to_cold_no_old_events(self, db, storage):
        await storage.migrate_warm_to_cold()
        assert list(storage.archive_path.glob("events_*.json.gz")) == []

    async def test_migrate_warm_to_cold_exception_rolls_back(self, storage):
        with patch.object(storage.db, "query", side_effect=RuntimeError("db down")):
            with patch.object(storage.db, "rollback") as rb:
                with patch.object(storage.logger, "error") as err:
                    await storage.migrate_warm_to_cold()
        err.assert_called_once()
        rb.assert_called_once()

    async def test_cleanup_expired_removes_old_archive(self, storage):
        old_file = storage.archive_path / "events_2020-01-01.json.gz"
        old_file.write_text("[]")
        os.utime(old_file, (time.time() - 91 * 86400, time.time() - 91 * 86400))
        fresh_file = storage.archive_path / "events_2026-08-01.json.gz"
        fresh_file.write_text("[]")
        await storage.cleanup_expired_data()
        assert not old_file.exists()
        assert fresh_file.exists()

    async def test_cleanup_expired_glob_failure(self, storage):
        with patch.object(Path, "glob", side_effect=RuntimeError("io")):
            with patch.object(storage.logger, "error") as err:
                await storage.cleanup_expired_data()
        err.assert_called_once()


# ============================================================================
# Hot tier (Redis) details
# ============================================================================

class TestHotTier:
    async def test_store_event_hot_redis_error(self, db, redis, storage):
        redis.fail_setex = True
        with patch.object(storage.logger, "error") as err:
            await storage._store_event_hot("e", {})
        err.assert_called_once()

    async def test_get_event_hot_found_and_missing(self, db, redis, storage):
        redis.data["debug:event:e1"] = (60, json.dumps({"id": "e1"}))
        assert (await storage._get_event_hot("e1"))["id"] == "e1"
        assert await storage._get_event_hot("nope") is None

    async def test_get_event_hot_redis_error(self, db, redis, storage):
        redis.fail_get = True
        with patch.object(storage.logger, "error"):
            assert await storage._get_event_hot("e") is None

    async def test_store_insight_hot_redis_error(self, db, redis, storage):
        redis.fail_setex = True
        with patch.object(storage.logger, "error") as err:
            await storage._store_insight_hot("i", {})
        err.assert_called_once()

    async def test_get_insight_hot_found_and_missing(self, db, redis, storage):
        redis.data["debug:insight:i1"] = (60, json.dumps({"id": "i1"}))
        assert (await storage._get_insight_hot("i1"))["id"] == "i1"
        assert await storage._get_insight_hot("nope") is None

    async def test_get_insight_hot_redis_error(self, db, redis, storage):
        redis.fail_get = True
        with patch.object(storage.logger, "error"):
            assert await storage._get_insight_hot("i") is None

    async def test_store_snapshot_hot_redis_error(self, db, redis, storage):
        redis.fail_setex = True
        with patch.object(storage.logger, "error") as err:
            await storage._store_snapshot_hot("s", {})
        err.assert_called_once()


# ============================================================================
# Warm / cold tier details
# ============================================================================

class TestWarmColdTier:
    async def test_get_event_warm_found_miss_error(self, db, storage):
        _event(db, "w-1")
        assert (await storage._get_event_warm("w-1"))["id"] == "w-1"
        assert await storage._get_event_warm("nope") is None
        with patch.object(storage.db, "query", side_effect=RuntimeError("db down")):
            with patch.object(storage.logger, "error"):
                assert await storage._get_event_warm("w-1") is None

    async def test_get_insight_warm_found_and_error(self, db, storage):
        _insight(db, "w-ins")
        assert (await storage._get_insight_warm("w-ins"))["id"] == "w-ins"
        with patch.object(storage.db, "query", side_effect=RuntimeError("db down")):
            with patch.object(storage.logger, "error"):
                assert await storage._get_insight_warm("w-ins") is None

    async def test_get_event_cold_found_miss(self, storage):
        await storage._write_archive(
            storage.archive_path / "events_2026-01-01.json.gz",
            [{"id": "c-1", "event_type": "log"}, {"id": "c-2", "event_type": "log"}],
        )
        assert (await storage._get_event_cold("c-2"))["id"] == "c-2"
        assert await storage._get_event_cold("nope") is None

    async def test_get_event_cold_error(self, storage):
        with patch.object(Path, "glob", side_effect=RuntimeError("io")):
            with patch.object(storage.logger, "error"):
                assert await storage._get_event_cold("c") is None

    async def test_write_archive_success_and_failure(self, storage):
        target = storage.archive_path / "sub" / "events_2026-08-01.json.gz"
        await storage._write_archive(target, [{"id": "x"}])  # missing dir → error
        assert not target.exists()
        ok_target = storage.archive_path / "events_2026-08-02.json.gz"
        await storage._write_archive(ok_target, [{"id": "y"}])
        assert ok_target.exists()

    async def test_read_archive_success_and_failure(self, storage):
        good = storage.archive_path / "events_good.json.gz"
        await storage._write_archive(good, [{"id": "g"}])
        assert (await storage._read_archive(good))[0]["id"] == "g"
        corrupt = storage.archive_path / "events_corrupt.json.gz"
        corrupt.write_text("this is not gzip data at all")
        assert await storage._read_archive(corrupt) == []


# ============================================================================
# Serializers + time range parsing
# ============================================================================

class TestSerializers:
    def test_event_to_dict_with_and_without_timestamp(self, db):
        storage = HybridDebugStorage(db_session=db, redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        _event(db, "ser-1")
        event = db.query(DebugEvent).filter(DebugEvent.id == "ser-1").first()
        d = storage._event_to_dict(event)
        assert d["id"] == "ser-1"
        assert d["timestamp"] is not None
        event.timestamp = None
        assert storage._event_to_dict(event)["timestamp"] is None

    def test_insight_to_dict_timestamps(self, db):
        storage = HybridDebugStorage(db_session=db, redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        _insight(db, "ser-ins")
        insight = db.query(DebugInsight).filter(DebugInsight.id == "ser-ins").first()
        d = storage._insight_to_dict(insight)
        assert d["generated_at"] is not None
        assert d["expires_at"] is None
        insight.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert storage._insight_to_dict(insight)["expires_at"] is not None

    def test_snapshot_to_dict(self, db):
        storage = HybridDebugStorage(db_session=db, redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        snap = _snapshot(db, "ser-snap")
        d = storage._snapshot_to_dict(snap)
        assert d["id"] == "ser-snap"
        assert d["captured_at"] is not None
        snap.captured_at = None
        assert storage._snapshot_to_dict(snap)["captured_at"] is None

    def test_parse_time_range_all_branches(self, db):
        storage = HybridDebugStorage(db_session=db, redis_client=None,
                                     archive_path="/tmp/atom_debug_archive_test")
        now = datetime.now(timezone.utc)
        for label, delta in [
            ("last_1h", timedelta(hours=1)),
            ("last_24h", timedelta(hours=24)),
            ("last_7d", timedelta(days=7)),
            ("last_30d", timedelta(days=30)),
        ]:
            cutoff = storage._parse_time_range(label)
            assert abs((now - delta - cutoff).total_seconds()) < 5, label
        assert storage._parse_time_range("bogus") is None
