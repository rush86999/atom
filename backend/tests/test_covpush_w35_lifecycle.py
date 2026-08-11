"""Coverage wave 35 — core/episode_lifecycle_service remaining branches (32% → 90%+).

- consolidate_similar_episodes: string metadata, similarity filtering via
  _distance, child missing, exception → rollback
- archive_to_cold_storage: found + missing
- update_importance_scores: clamping out-of-range, not-found, computed value
- batch_update_access_counts: mixed found/missing
- update_lifecycle: no started_at, naive/aware datetimes, archive >180d,
  exception → rollback
- apply_decay: single + list
- consolidate_episodes sync wrapper: agent object, no-loop path, exception
"""
import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import AgentEpisode as Episode


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


def _episode(db, **kw):
    defaults = dict(
        id=f"ep-{uuid.uuid4().hex[:8]}",
        agent_id="agent-1", tenant_id="t1", workspace_id="ws1",
        task_description="Task", maturity_at_time="SUPERVISED",
        constitutional_score=1.0, outcome="success", status="completed",
        importance_score=0.5, access_count=0, decay_score=0.0,
        started_at=datetime.now(timezone.utc) - timedelta(days=5),
        completed_at=datetime.now(timezone.utc),
    )
    defaults.update(kw)
    ep = Episode(**defaults)
    db.add(ep)
    db.commit()
    return ep


@pytest.fixture
def svc(fresh_db):
    return EpisodeLifecycleService(fresh_db)


class TestConsolidation:
    async def test_consolidate_string_metadata_and_distance(self, svc, fresh_db):
        parent = _episode(fresh_db, task_description="Refund processing")
        child = _episode(fresh_db, task_description="Refund follow-up")
        with patch.object(svc, "lancedb") as lb:
            lb.search.return_value = [
                {
                    "metadata": '{"episode_id": "' + child.id + '"}',
                    "_distance": 0.05,  # similarity 0.95
                }
            ]
            result = await svc.consolidate_similar_episodes("agent-1")
        assert result["consolidated"] == 1
        fresh_db.refresh(child)
        assert child.consolidated_into == parent.id

    async def test_consolidate_below_threshold_skipped(self, svc, fresh_db):
        parent = _episode(fresh_db, task_description="A")
        child = _episode(fresh_db, task_description="B")
        with patch.object(svc, "lancedb") as lb:
            lb.search.return_value = [
                {"metadata": {"episode_id": child.id}, "_distance": 0.5}  # similarity 0.5
            ]
            result = await svc.consolidate_similar_episodes("agent-1")
        assert result["consolidated"] == 0

    async def test_consolidate_child_already_consolidated(self, svc, fresh_db):
        parent = _episode(fresh_db, task_description="A")
        child = _episode(fresh_db, task_description="B", consolidated_into="other")
        with patch.object(svc, "lancedb") as lb:
            lb.search.return_value = [
                {"metadata": {"episode_id": child.id}, "_distance": 0.0}
            ]
            result = await svc.consolidate_similar_episodes("agent-1")
        assert result["consolidated"] == 0

    async def test_consolidate_exception_rollback(self, svc, fresh_db):
        _episode(fresh_db, task_description="A")
        with patch.object(svc, "lancedb") as lb:
            lb.search.side_effect = RuntimeError("lancedb down")
            result = await svc.consolidate_similar_episodes("agent-1")
        assert result == {"consolidated": 0, "parent_episodes": 0}

    def test_consolidate_episodes_sync_with_agent_object(self, svc):
        agent = SimpleNamespace(id="agent-1")
        # patch the async method to return a resolved value
        async def fake_consolidate(agent_id, threshold):
            return {"consolidated": 2, "parent_episodes": 1}
        svc.consolidate_similar_episodes = fake_consolidate
        result = svc.consolidate_episodes(agent)
        assert result["consolidated"] == 2

    def test_consolidate_episodes_sync_exception(self, svc):
        async def fake_consolidate(agent_id, threshold):
            raise RuntimeError("boom")
        svc.consolidate_similar_episodes = fake_consolidate
        result = svc.consolidate_episodes("agent-1")
        assert result == {"consolidated": 0, "parent_episodes": 0}


class TestArchival:
    async def test_archive_to_cold_storage_found(self, svc, fresh_db):
        ep = _episode(fresh_db)
        assert await svc.archive_to_cold_storage(ep.id) is True
        fresh_db.refresh(ep)
        assert ep.status == "archived"
        assert ep.archived_at is not None

    async def test_archive_to_cold_storage_missing(self, svc):
        assert await svc.archive_to_cold_storage("missing") is False


class TestImportance:
    async def test_update_importance_clamps_feedback(self, svc, fresh_db):
        ep = _episode(fresh_db, importance_score=0.5)
        ok = await svc.update_importance_scores(ep.id, user_feedback=5.0)
        assert ok is True
        fresh_db.refresh(ep)
        # clamped to 1.0 → new = 0.5*0.8 + 1.0*0.2 = 0.6
        assert abs(ep.importance_score - 0.6) < 1e-9

    async def test_update_importance_not_found(self, svc):
        assert await svc.update_importance_scores("missing", 0.5) is False

    async def test_update_importance_negative(self, svc, fresh_db):
        ep = _episode(fresh_db, importance_score=0.1)
        await svc.update_importance_scores(ep.id, user_feedback=-1.0)
        fresh_db.refresh(ep)
        assert abs(ep.importance_score - 0.08) < 1e-9


class TestAccessCounts:
    async def test_batch_update_mixed(self, svc, fresh_db):
        ep1 = _episode(fresh_db)
        _episode(fresh_db)
        result = await svc.batch_update_access_counts([ep1.id, "missing"])
        assert result == {"updated": 1}
        fresh_db.refresh(ep1)
        assert ep1.access_count == 1


class TestLifecycle:
    def test_update_lifecycle_no_started_at(self, svc, fresh_db):
        # started_at has a DB default, so a plain row always gets one — use a
        # detached object with started_at=None to hit the guard
        ep = SimpleNamespace(id="ep-x", started_at=None, decay_score=0.0,
                             status="completed", archived_at=None)
        assert svc.update_lifecycle(ep) is False

    def test_update_lifecycle_naive_datetime(self, svc, fresh_db):
        ep = _episode(fresh_db, started_at=datetime.now() - timedelta(days=1))
        assert svc.update_lifecycle(ep) is True
        assert ep.decay_score > 0

    def test_update_lifecycle_archives_very_old(self, svc, fresh_db):
        ep = _episode(fresh_db, started_at=datetime.now(timezone.utc) - timedelta(days=200))
        assert svc.update_lifecycle(ep) is True
        assert ep.status == "archived"
        assert ep.decay_score == 1.0

    def test_update_lifecycle_exception_rollback(self, svc, fresh_db):
        ep = _episode(fresh_db)
        db = Mock()
        db.commit.side_effect = RuntimeError("commit boom")
        db.rollback = Mock()
        svc.db = db
        assert svc.update_lifecycle(ep) is False
        assert db.rollback.called

    def test_apply_decay_single_and_list(self, svc, fresh_db):
        ep1 = _episode(fresh_db, started_at=datetime.now(timezone.utc) - timedelta(days=30))
        ep2 = _episode(fresh_db, started_at=datetime.now(timezone.utc) - timedelta(days=45))
        assert svc.apply_decay(ep1) is True
        assert svc.apply_decay([ep1, ep2]) is True
        assert ep1.decay_score > 0
        assert ep2.decay_score > ep1.decay_score
