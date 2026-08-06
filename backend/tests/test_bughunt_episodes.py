"""
TDD bug-hunt tests: findings + regressions for the ephemeral/episode services.

Redirects (red) first, then minimal fixes in:
  - core/episode_retrieval_service.py
  - core/episode_lifecycle_service.py
  - core/episode_segmentation_service.py
  - core/agent_graduation_service.py

Bugs covered:
  1. retrieve_semantic discards LanceDB relevance rank (returns arbitrary
     DB order) and does not dedup.
  2. retrieve_semantic / retrieve_canvas_aware / retrieve_by_business_data
     leak raw exception text (str(e)) to callers on failure.
  3. AgentGraduationService.calculate_readiness_score caps analyzed episodes
     at the EpisodeService default of 30, making the AUTONOMOUS min-50
     boundary structurally unreachable.
  4. Segmentation scoops in executions that started AFTER the session's last
     message (i.e. belong to a later session).
  5. consolidate_similar_episodes can link one agent's episode into another
     agent's parent (no agent_id scope on the child update).
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models_registration import Base
from core.models import (
    AgentEpisode,
    AgentExecution,
    ChatMessage,
    ChatSession,
    Episode,
    EpisodeSegment,
    Tenant,
)

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _seed_tenant(db, tenant_id="t1"):
    db.add(Tenant(id=tenant_id, name=f"T-{tenant_id}", subdomain=tenant_id))
    db.flush()


def _seed_episode(db, episode_id, agent_id, tenant_id="t1", started_at=None, **kw):
    ep = AgentEpisode(
        id=episode_id,
        agent_id=agent_id,
        tenant_id=tenant_id,
        maturity_at_time="student",
        outcome="success",
        success=True,
        status="completed",
        constitutional_score=1.0,
        human_intervention_count=0,
        confidence_score=0.9,
        step_efficiency=1.0,
        task_description=kw.pop("task_description", f"Task {episode_id}"),
        started_at=started_at
        or datetime.now(timezone.utc) - timedelta(days=1),
        **kw,
    )
    db.add(ep)
    return ep


class _FakeGovernance:
    def can_perform_action(self, **kwargs):
        return {"allowed": True}


# ============================================================================
# 1. Semantic retrieval relevance order + dedup
# ============================================================================

class TestSemanticRetrievalOrdering:
    @pytest.mark.asyncio
    async def test_semantic_retrieval_preserves_lancedb_relevance_order(self, db):
        """Episodes returned by retrieve_semantic must stay in LanceDB rank
        order (most-relevant first), not the arbitrary DB scan order."""
        _seed_tenant(db)
        _seed_episode(db, "ep-a", "a1")  # inserted first (low rowid)
        _seed_episode(db, "ep-b", "a1")   # inserted second
        db.commit()

        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {"id": "row-1", "metadata": {"episode_id": "ep-b"}, "_distance": 0.1},
            {"id": "row-2", "metadata": {"episode_id": "ep-a"}, "_distance": 0.5},
        ]

        with patch("core.episode_retrieval_service.get_lancedb_handler", return_value=mock_lancedb):
            from core.episode_retrieval_service import EpisodeRetrievalService
            service = EpisodeRetrievalService(db)
        service.governance = _FakeGovernance()
        service.lancedb = mock_lancedb

        result = await service.retrieve_semantic("a1", "beta task", limit=10)

        ids = [e["id"] for e in result["episodes"]]
        assert ids == ["ep-b", "ep-a"], f"Relevance order lost: {ids}"

    @pytest.mark.asyncio
    async def test_semantic_retrieval_dedupes_duplicate_rows(self, db):
        """The same episode archived twice must appear once in results."""
        _seed_tenant(db)
        _seed_episode(db, "ep-a", "a1")
        db.commit()

        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {"metadata": {"episode_id": "ep-a"}},
            {"metadata": {"episode_id": "ep-a"}},
        ]

        with patch("core.episode_retrieval_service.get_lancedb_handler", return_value=mock_lancedb):
            from core.episode_retrieval_service import EpisodeRetrievalService
            service = EpisodeRetrievalService(db)
        service.governance = _FakeGovernance()
        service.lancedb = mock_lancedb

        result = await service.retrieve_semantic("a1", "query", limit=5)

        assert [e["id"] for e in result["episodes"]] == ["ep-a"]


# ============================================================================
# 2. No str(e) leakage from retrieval error paths
# ============================================================================

class TestRetrievalErrorHandling:
    def _error_service(self, db, side_effect):
        mock_lancedb = Mock()
        mock_lancedb.search.side_effect = side_effect
        with patch("core.episode_retrieval_service.get_lancedb_handler", return_value=mock_lancedb):
            from core.episode_retrieval_service import EpisodeRetrievalService
            service = EpisodeRetrievalService(db)
        service.governance = _FakeGovernance()
        service.lancedb = mock_lancedb
        return service

    @pytest.mark.asyncio
    async def test_semantic_retrieval_error_does_not_leak_internal_exception(self, db):
        _seed_tenant(db)
        _seed_episode(db, "ep-a", "a1")
        db.commit()

        service = self._error_service(
            db, ValueError("DB blew up with secret-xyz-42")
        )

        result = await service.retrieve_semantic("a1", "query")
        assert result["episodes"] == []
        assert result.get("error")
        assert "secret-xyz-42" not in result["error"]

    @pytest.mark.asyncio
    async def test_canvas_aware_error_does_not_leak_internal_exception(self, db):
        _seed_tenant(db)
        _seed_episode(db, "ep-a", "a1")
        db.commit()

        service = self._error_service(
            db, ValueError("index corrupt row-id-abc123")
        )

        result = await service.retrieve_canvas_aware("a1", "query")
        assert result["episodes"] == []
        assert result.get("error")
        assert "row-id-abc123" not in result["error"]

    @pytest.mark.asyncio
    async def test_business_data_error_does_not_leak_internal_exception(self, db):
        _seed_tenant(db)
        _seed_episode(db, "ep-a", "a1")
        db.commit()

        mock_lancedb = Mock()

        from core.episode_retrieval_service import EpisodeRetrievalService

        class BoomQuery:
            def __init__(self, *a):
                pass

            def join(self, *a):
                return self

            def filter(self, *a, **kw):
                return self

            def limit(self, *a):
                raise RuntimeError("secret: /tmp/creds.pem")

        with patch("core.episode_retrieval_service.get_lancedb_handler", return_value=mock_lancedb):
            service = EpisodeRetrievalService(db)
        service.governance = _FakeGovernance()
        service.lancedb = mock_lancedb
        service.db.query = lambda *a, **kw: BoomQuery()

        result = await service.retrieve_by_business_data(
            "a1", {"approval_status": "approved"}
        )
        assert result["episodes"] == []
        assert result.get("error")
        assert "creds.pem" not in result["error"]


# ============================================================================
# 3. AUTONOMOUS graduation min-50 episodes must be analyzable
# ============================================================================

class TestGraduationEpisodeCount:
    def _service(self, db):
        with patch("core.agent_graduation_service.get_lancedb_handler"):
            from core.agent_graduation_service import AgentGraduationService
            return AgentGraduationService(db)

    @pytest.mark.asyncio
    async def test_graduation_autonomous_analyzes_all_50_episodes(self, db):
        """A 50-episode agent targeting AUTONOMOUS must have all 50 analyzed;
        the readiness gate may only fail on quality, never on the episode
        count being < 50."""
        _seed_tenant(db)
        from core.models import AgentRegistry
        db.add(AgentRegistry(
            id="a-grad", name="Grad", category="general", status="supervised",
            tenant_id="t1", module_path="core.generic_agent", class_name="GenericAgent",
        ))
        for i in range(50):
            _seed_episode(db, f"grad-{i:03d}", "a-grad",
                          started_at=datetime.now(timezone.utc) - timedelta(days=i))
        db.commit()

        service = self._service(db)
        result = await service.calculate_readiness_score("a-grad", "AUTONOMOUS")

        assert result["episode_count"] == 50, (
            f"episodes_analyzed capped at {result['episode_count']}"
        )
        insufficient = [g for g in result["gaps"] if "Insufficient episodes" in g]
        assert insufficient == []

    @pytest.mark.asyncio
    async def test_graduation_intern_boundary_gap_when_9_episodes(self, db):
        """9 episodes is strictly below the INTERN floor of 10."""
        _seed_tenant(db)
        from core.models import AgentRegistry
        db.add(AgentRegistry(
            id="a-grad-2", name="Grad", category="general", status="student",
            tenant_id="t1", module_path="core.generic_agent", class_name="GenericAgent",
        ))
        for i in range(9):
            _seed_episode(db, f"i9-{i:03d}", "a-grad-2",
                          started_at=datetime.now(timezone.utc) - timedelta(days=i))
        db.commit()

        service = self._service(db)
        result = await service.calculate_readiness_score("a-grad-2", "INTERN")

        assert result["episode_count"] == 9
        assert any("Insufficient episodes" in g for g in result["gaps"])
        assert "9/10" in [g for g in result["gaps"] if "Insufficient" in g][0]


# ============================================================================
# 4. Segmentation must not absorb executions from later sessions
# ============================================================================

class TestSegmentationSessionScoping:
    def _segment_service(self, db):
        mock_lancedb = MagicMock()
        mock_lancedb.db.table_names.return_value = []
        from core.episode_segmentation_service import EpisodeSegmentationService
        return EpisodeSegmentationService(
            db=db, llm_service=MagicMock(), lancedb=mock_lancedb
        )

    @pytest.mark.asyncio
    async def test_session_episode_excludes_later_session_executions(self, db):
        _seed_tenant(db)
        t0 = datetime.now() - timedelta(hours=1)
        db.add(ChatSession(id="s1", user_id="u1", created_at=t0 - timedelta(minutes=1)))
        db.add(ChatMessage(id="m1", conversation_id="s1", tenant_id="t1", role="user",
                           content="hello", created_at=t0))
        db.add(ChatMessage(id="m2", conversation_id="s1", tenant_id="t1", role="assistant",
                           content="hi there", created_at=t0 + timedelta(seconds=5)))
        # Execution started 30 minutes after the session's last message —
        # attribution-wise it belongs to a LATER session.
        db.add(AgentExecution(
            id="e1", agent_id="a1", tenant_id="t1", status="completed",
            input_summary="later unrelated task",
            started_at=t0 + timedelta(minutes=30),
            completed_at=t0 + timedelta(minutes=35),
            result_summary="done",
        ))
        db.commit()

        service = self._segment_service(db)
        episode = await service.create_episode_from_session("s1", "a1")
        assert episode is not None

        exec_segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode["id"],
            EpisodeSegment.segment_type == "execution",
        ).all()
        assert exec_segments == [], (
            f"Later-session execution leaked into episode: {exec_segments}"
        )


# ============================================================================
# 5. Consolidation must never cross agent boundaries
# ============================================================================

class TestConsolidationScoping:
    @pytest.mark.asyncio
    async def test_consolidation_never_links_cross_agent_episode(self, db):
        _seed_tenant(db)
        _seed_episode(db, "parent-a", "agentA", task_description="Parent alpha")
        _seed_episode(db, "child-b", "agentB", task_description="Child beta")
        db.commit()

        mock_lancedb = Mock()
        mock_lancedb.search.return_value = [
            {"metadata": {"episode_id": "child-b"}, "_distance": 0.0},
        ]

        with patch("core.episode_lifecycle_service.get_lancedb_handler", return_value=mock_lancedb):
            from core.episode_lifecycle_service import EpisodeLifecycleService
            service = EpisodeLifecycleService(db)
        service.lancedb = mock_lancedb

        result = await service.consolidate_similar_episodes("agentA")

        child = db.query(Episode).filter(Episode.id == "child-b").first()
        assert result["consolidated"] == 0
        assert child.consolidated_into is None, (
            f"agentB episode was linked into agentA parent: {child.consolidated_into}"
        )