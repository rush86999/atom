"""Coverage wave 20 — core/agent_world_model uncovered branches (TDD).

Covers the remaining missed lines after the pre-existing world-model suites:
- get_business_fact / get_fact_by_id edge branches
- archive_session_to_cold_storage_with_cleanup full path (verify+soft-delete+audit)
- hard_delete_archived_sessions retention filtering + delete path
- record_episode / sync_episode_to_lancedb / archive_episode_to_cold_storage
- recall_episodes scoring (canvas/feedback boosts, min_feedback filter)
- recall_experiences_with_detail (agent_id path, FULL path)
- _format_episodes_as_experiences detail levels
- get_recent_episodes / get_episode_feedback_for_decision
- recommend_skills_for_task / get_successful_skills_for_agent
- canvas family: recall_experiences_with_canvas, get_canvas_type_preferences,
  recommend_canvas_type, record_canvas_outcome, _extract_canvas_insights
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agent_world_model import (
    AgentExperience,
    BusinessFact,
    DetailLevel,
    WorldModelService,
)
from core.models import AgentRegistry, ChatMessage


@pytest.fixture
def mock_handler():
    handler = Mock()
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=["agent_experience", "business_facts"])
    handler.workspace_id = "test_workspace"
    handler.add_document = Mock(return_value=True)
    handler.search = Mock(return_value=[])
    handler.create_table = Mock()
    handler.get_table = Mock(return_value=None)
    return handler


@pytest.fixture
def svc(mock_handler):
    with patch("core.agent_world_model.get_lancedb_handler", return_value=mock_handler):
        return WorldModelService(workspace_id="test_workspace")


@pytest.fixture
def experience():
    return AgentExperience(
        id=str(uuid.uuid4()),
        agent_id="agent_1",
        task_type="reconciliation",
        input_summary="Reconcile SKU-123",
        outcome="Success",
        learnings="Timing mismatch",
        confidence_score=0.8,
        feedback_score=0.5,
        artifacts=["r1.pdf"],
        step_efficiency=1.0,
        metadata_trace={"steps": 5},
        agent_role="Finance",
        specialty="accounting",
        timestamp=datetime.now(timezone.utc),
    )


def _msg(conversation_id, content="hello", role="user", metadata_json=None):
    m = Mock(spec=ChatMessage)
    m.conversation_id = conversation_id
    m.tenant_id = "test_workspace"
    m.role = role
    m.content = content
    m.created_at = datetime.now(timezone.utc)
    m.metadata_json = metadata_json if metadata_json is not None else {}
    return m


class TestSessionCleanup:
    async def test_archive_with_cleanup_no_messages(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            result = await svc.archive_session_to_cold_storage_with_cleanup("conv-x")
        assert result["status"] == "failed"
        assert result["error"] == "No messages found"

    async def test_archive_with_cleanup_lancedb_failure(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                _msg("conv-x")
            ]
            svc.db.add_document = Mock(return_value=False)
            result = await svc.archive_session_to_cold_storage_with_cleanup("conv-x")
        assert result["status"] == "failed"
        assert result["error"] == "Failed to archive to LanceDB"

    async def test_archive_with_cleanup_verification_failure(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                _msg("conv-x")
            ]
            svc.db.search = Mock(return_value=[])
            result = await svc.archive_session_to_cold_storage_with_cleanup("conv-x")
        assert result["status"] == "failed"
        assert result["error"] == "Verification failed: document not found in LanceDB"

    async def test_archive_with_cleanup_full_success(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            messages = [_msg("conv-x"), _msg("conv-x", content="hi2", role="assistant")]
            db.query.return_value.filter.return_value.order_by.return_value.all.return_value = messages
            svc.db.search = Mock(return_value=[{"id": "doc1"}])
            result = await svc.archive_session_to_cold_storage_with_cleanup("conv-x")
        assert result["status"] == "success"
        assert result["archived"] is True
        assert result["soft_deleted"] is True
        assert result["scheduled_for_hard_delete"]
        assert "_archived" in messages[0].metadata_json
        assert db.commit.called

    async def test_archive_with_cleanup_exception_rolls_back(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = await svc.archive_session_to_cold_storage_with_cleanup("conv-x")
        assert result["status"] == "failed"
        assert result["error"] == "Archival with cleanup failed"
        assert db.rollback.called

    async def test_hard_delete_past_retention(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            old = _msg("c1", metadata_json={
                "_archived": True,
                "_retention_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            })
            fresh = _msg("c2", metadata_json={
                "_archived": True,
                "_retention_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            })
            db.query.return_value.filter.return_value.all.return_value = [old, fresh]
            result = await svc.hard_delete_archived_sessions(older_than_days=30)
        assert result["status"] == "success"
        assert result["deleted_count"] == 1
        assert db.commit.called

    async def test_hard_delete_uses_created_at_fallback(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            no_retention = _msg("c1", metadata_json={"_archived": True})
            no_retention.created_at = datetime.now(timezone.utc) - timedelta(days=60)
            db.query.return_value.filter.return_value.all.return_value = [no_retention]
            result = await svc.hard_delete_archived_sessions(older_than_days=30)
        assert result["deleted_count"] == 1

    async def test_hard_delete_none_past_retention(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.all.return_value = []
            result = await svc.hard_delete_archived_sessions()
        assert result["status"] == "success"
        assert result["deleted_count"] == 0

    async def test_hard_delete_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = await svc.hard_delete_archived_sessions()
        assert result["status"] == "failed"
        assert result["error"] == "Hard delete of archived sessions failed"


class TestFactEdges:
    async def test_get_business_fact_table_missing(self, svc):
        svc.db.get_table = Mock(return_value=None)
        result = await svc.get_business_fact("fact-1")
        assert result is None

    async def test_get_business_fact_empty(self, svc):
        table = Mock()
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = Mock(empty=True)
        svc.db.get_table = Mock(return_value=table)
        result = await svc.get_business_fact("fact-1")
        assert result is None

    async def test_get_business_fact_found_with_string_metadata(self, svc):
        import pandas as pd
        table = Mock()
        row = {
            "id": "fact-1",
            "text": "Fact: quarterly revenue",
            "metadata": json.dumps({
                "fact": "quarterly revenue up",
                "citations": ["r1"],
                "reason": "audited",
                "source_agent_id": "a1",
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_verified": "2026-01-02T00:00:00+00:00",
            }),
        }
        table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = pd.DataFrame([row])
        svc.db.get_table = Mock(return_value=table)
        result = await svc.get_business_fact("fact-1")
        assert result is not None
        assert result.id == "fact-1"
        assert result.verification_status == "unverified"

    async def test_get_business_fact_exception(self, svc):
        svc.db.get_table = Mock(side_effect=RuntimeError("boom"))
        result = await svc.get_business_fact("fact-1")
        assert result is None

    async def test_get_fact_by_id_found(self, svc):
        svc.db.search = Mock(return_value=[{
            "metadata": {
                "id": "f9",
                "fact": "invoices > 500 need approval",
                "citations": [],
                "reason": "policy",
                "source_agent_id": "sys",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        }])
        result = await svc.get_fact_by_id("f9")
        assert result is not None
        assert result.id == "f9"

    async def test_get_fact_by_id_not_found(self, svc):
        svc.db.search = Mock(return_value=[{"metadata": {"id": "other"}}])
        result = await svc.get_fact_by_id("f9")
        assert result is None


class TestEpisodes:
    async def test_record_episode_with_metadata(self, svc):
        result = await svc.record_episode(
            episode_id="e1", agent_id="a1", tenant_id="t1",
            task_description="analyze", outcome="success",
            learnings="learned", agent_role="Finance",
            maturity_at_time="SUPERVISED", constitutional_score=0.9,
            human_intervention_count=2, confidence_score=0.7,
            metadata={"canvas_id": "cv1"},
        )
        assert result is True
        call_args = svc.db.add_document.call_args[1]
        assert call_args["table_name"] == "agent_episodes"
        assert call_args["metadata"]["episode_id"] == "e1"
        assert call_args["metadata"]["canvas_id"] == "cv1"

    async def test_sync_episode_to_lancedb_delegates(self, svc):
        result = await svc.sync_episode_to_lancedb(
            episode_id="e2", agent_id="a1", tenant_id="t1",
            task_description="x", outcome="failure", learnings="y",
            agent_role="Ops", maturity_at_time="INTERN",
        )
        assert result is True
        assert svc.db.add_document.call_args[1]["metadata"]["outcome"] == "failure"

    async def test_archive_episode_success(self, svc):
        with patch.object(svc, "sync_episode_to_lancedb", new=AsyncMock(return_value=True)):
            result = await svc.archive_episode_to_cold_storage(
                episode_id="e3", agent_id="a1", tenant_id="t1",
                task_description="x", outcome="success", learnings="y",
                agent_role="Finance", maturity_at_time="AUTONOMOUS",
            )
        assert result is True

    async def test_archive_episode_failure(self, svc):
        with patch.object(svc, "sync_episode_to_lancedb", new=AsyncMock(return_value=False)):
            result = await svc.archive_episode_to_cold_storage(
                episode_id="e3", agent_id="a1", tenant_id="t1",
                task_description="x", outcome="success", learnings="y",
                agent_role="Finance", maturity_at_time="AUTONOMOUS",
            )
        assert result is False

    async def test_recall_episodes_scoring(self, svc):
        svc.db.search = Mock(return_value=[
            {
                "score": 0.9,
                "text": "Episode: reconcile\nOutcome: success\nLearnings: a\nMaturity: X",
                "metadata": {
                    "agent_role": "Finance", "agent_id": "a1", "type": "episode",
                    "episode_id": "e1", "outcome": "success", "canvas_id": "cv1",
                    "feedback_score": 0.8, "maturity_at_time": "SUPERVISED",
                },
            },
            {
                "score": 0.7,
                "text": "Episode: reconcile\nOutcome: failure\nLearnings: b\nMaturity: X",
                "metadata": {
                    "agent_role": "Finance", "agent_id": "a1", "type": "episode",
                    "episode_id": "e2", "outcome": "failure", "canvas_id": "cv2",
                    "feedback_score": -0.9, "maturity_at_time": "INTERN",
                },
            },
        ])
        result = await svc.recall_episodes(
            task_description="reconcile", agent_role="Finance",
            agent_id="a1", canvas_id="cv1", min_feedback_score=-1.0,
        )
        assert len(result) == 2
        by_id = {r["episode_id"]: r for r in result}
        assert by_id["e1"]["canvas_boost"] == 0.3
        assert by_id["e1"]["feedback_boost"] == 0.2
        assert by_id["e2"]["canvas_boost"] == -0.05
        assert by_id["e2"]["feedback_boost"] == -0.3
        assert result[0]["episode_id"] == "e1"

    async def test_recall_episodes_filters(self, svc):
        svc.db.search = Mock(return_value=[
            {
                "score": 0.8,
                "text": "Episode: x\nOutcome: success\nLearnings: a\nMaturity: Y",
                "metadata": {
                    "agent_role": "Ops", "agent_id": "a2", "type": "episode",
                    "episode_id": "e1", "outcome": "success",
                },
            },
            {
                "score": 0.8,
                "text": "Episode: x\nOutcome: success\nLearnings: a\nMaturity: Y",
                "metadata": {
                    "agent_role": "Finance", "agent_id": "a2", "type": "episode",
                    "episode_id": "e2", "outcome": "success", "feedback_score": 0.2,
                },
            },
        ])
        result = await svc.recall_episodes(
            task_description="x", agent_role="Finance",
            agent_id="a1", min_feedback_score=0.5,
        )
        assert result == []

    async def test_recall_episodes_exception_returns_empty(self, svc):
        svc.db.search = Mock(side_effect=RuntimeError("boom"))
        result = await svc.recall_episodes(task_description="x", agent_role="Finance")
        assert result == []

    async def test_recall_experiences_with_detail_agent_id(self, svc):
        episode_service = Mock()
        episode_service.recall_episodes_with_detail = AsyncMock(return_value=[
            {"id": "e1", "task_description": "task", "presentation_summary": "sum", "outcome": "success"}
        ])
        with patch("core.episode_service.EpisodeService", return_value=episode_service):
            result = await svc.recall_experiences_with_detail(
                tenant_id="t1", agent_role="Finance", task_description="x",
                detail_level=DetailLevel.FULL, agent_id="a1",
            )
        assert result[0]["episode_id"] == "e1"
        assert result[0]["detail_level"] == "full"

    async def test_recall_experiences_with_detail_full(self, svc):
        with patch.object(svc, "recall_episodes", new=AsyncMock(return_value=[{"episode_id": "e1"}])):
            result = await svc.recall_experiences_with_detail(
                tenant_id="t1", agent_role="Finance", task_description="x",
                detail_level=DetailLevel.FULL,
            )
        assert result == [{"episode_id": "e1"}]

    async def test_format_episodes_as_experiences_levels(self, svc):
        episodes = [{"id": "e1", "task_description": "abcd", "presentation_summary": "s", "outcome": "ok"}]
        summary = svc._format_episodes_as_experiences(episodes, DetailLevel.SUMMARY)
        assert summary[0]["detail_level"] == "summary"
        standard = svc._format_episodes_as_experiences(episodes, DetailLevel.STANDARD)
        assert "visual_elements" in standard[0]
        full = svc._format_episodes_as_experiences(episodes, DetailLevel.FULL)
        assert "audit_trail" in full[0]


class TestFeedbackAndRecent:
    async def test_get_recent_episodes_success(self, svc):
        ep = SimpleNamespace(
            id="e1", task_description="t", outcome="success", success=True,
            maturity_at_time="INTERN", constitutional_score=0.9,
            human_intervention_count=0, confidence_score=0.6,
            step_efficiency=1.0,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        with patch("core.database.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [ep]
            result = await svc.get_recent_episodes("a1", "t1")
        assert len(result) == 1
        assert result[0]["episode_id"] == "e1"

    async def test_get_recent_episodes_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = await svc.get_recent_episodes("a1", "t1")
        assert result == []

    def test_get_episode_feedback_empty(self, svc):
        assert svc.get_episode_feedback_for_decision([]) == {}

    def test_get_episode_feedback_success(self, svc):
        fb = SimpleNamespace(
            id="fb1", episode_id="e1", feedback_score=0.8, feedback_notes="good",
            feedback_category="approval", provider_id="u1", provider_type="user",
            provided_at=datetime.now(timezone.utc),
        )
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.all.return_value = [fb]
            result = svc.get_episode_feedback_for_decision(["e1"])
        assert result["e1"][0]["id"] == "fb1"

    def test_get_episode_feedback_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = svc.get_episode_feedback_for_decision(["e1"])
        assert result == {}


class TestSkillRecommendations:
    def _agent(self, category="Finance"):
        a = Mock(spec=AgentRegistry)
        a.id = "a1"
        a.category = category
        return a

    def test_recommend_skills_agent_not_found(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.first.return_value = None
            result = svc.recommend_skills_for_task("task", "a1", "t1")
        assert result == []

    def test_recommend_skills_no_skill_episodes(self, svc):
        agent = self._agent()
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.first.return_value = agent
            with patch.object(svc, "recall_episodes", new=AsyncMock(return_value=[])):
                result = svc.recommend_skills_for_task("task", "a1", "t1")
        assert result == []

    def test_recommend_skills_success(self, svc):
        agent = self._agent()
        similar = [
            {
                "episode_id": "e1", "metadata": {"skill_type": "openclaw", "skill_id": "sk1"},
                "outcome": "success", "similarity_score": 0.8, "final_score": 0.9,
            },
            {
                "episode_id": "e2", "metadata": {"skill_type": "openclaw", "skill_id": "sk2"},
                "outcome": "failure", "similarity_score": 0.6, "final_score": 0.5,
            },
        ]
        episode = SimpleNamespace(
            id="e9", agent_id="a1", success=True, completed_at=datetime.now(timezone.utc),
            metadata_json={"skill_type": "openclaw", "skill_id": "sk1"},
        )
        skill = SimpleNamespace(id="sk1", name="Skill One")
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            first_mock = Mock()
            first_mock.first = Mock(return_value=agent)
            db.query = Mock(return_value=first_mock)
            with patch.object(svc, "recall_episodes", new=AsyncMock(return_value=similar)):
                def query_side(*args, **kwargs):
                    model = args[0] if args else None
                    if model and getattr(model, "__name__", "") == "AgentEpisode":
                        q = Mock()
                        q.filter.return_value.all.return_value = [episode]
                        return q
                    if model and getattr(model, "__name__", "") == "Skill":
                        q = Mock()
                        q.filter.return_value.first.return_value = skill
                        return q
                    return first_mock
                db.query.side_effect = query_side
                result = svc.recommend_skills_for_task("task", "a1", "t1")
        assert len(result) == 2
        assert result[0].skill_id == "sk1"
        assert result[0].success_rate == 1.0
        assert result[1].skill_id == "sk2"

    def test_recommend_skills_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = svc.recommend_skills_for_task("task", "a1", "t1")
        assert result == []

    def test_get_successful_skills(self, svc):
        ep = SimpleNamespace(metadata_json={"skill_type": "openclaw", "skill_id": "sk1"})
        ep2 = SimpleNamespace(metadata_json={"skill_type": "openclaw", "skill_id": "sk2"})
        ep3 = SimpleNamespace(metadata_json=None)
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.return_value.filter.return_value.limit.return_value.all.return_value = [ep, ep2, ep3]
            result = svc.get_successful_skills_for_agent("a1", "t1")
        assert result == {"sk1", "sk2"}

    def test_get_successful_skills_exception(self, svc):
        with patch("core.agent_world_model.SessionLocal") as sl:
            db = Mock()
            sl.return_value = db
            db.query.side_effect = RuntimeError("boom")
            result = svc.get_successful_skills_for_agent("a1", "t1")
        assert result == set()


class TestCanvasFamily:
    async def test_recall_experiences_with_canvas_filters(self, svc):
        svc.db.search = Mock(return_value=[
            {
                "id": "e1", "metadata": {
                    "agent_id": "a1", "canvas_types": ["sheets"],
                    "outcome": "Success", "task_type": "t", "input_summary": "in",
                    "learnings": "l", "confidence_score": 0.8, "feedback_score": 0.5,
                    "artifacts": [], "step_efficiency": 1.0, "trace": {"x": 1},
                    "agent_role": "Finance", "specialty": "acc",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
            {
                "id": "e2", "metadata": {"agent_id": "a2", "outcome": "Success"},
            },
            {
                "id": "e3", "metadata": {"agent_id": "a1", "canvas_types": ["charts"], "outcome": "Failure"},
            },
        ])
        result = await svc.recall_experiences_with_canvas("a1", "task", preferred_canvas_type="sheets")
        assert len(result) == 1
        assert result[0].id == "e1"

    async def test_recall_experiences_with_canvas_error(self, svc):
        svc.db.search = Mock(side_effect=RuntimeError("boom"))
        result = await svc.recall_experiences_with_canvas("a1", "task")
        assert result == []

    async def test_canvas_preferences(self, svc):
        now = datetime.now(timezone.utc).isoformat()
        svc.db.search = Mock(return_value=[
            {"metadata": {
                "agent_id": "a1", "canvas_types": ["sheets", "charts"],
                "outcome": "success", "feedback_score": 0.8, "engagement_time_seconds": 40,
            }},
            {"metadata": {
                "agent_id": "a1", "canvas_types": ["sheets"],
                "outcome": "failure", "engagement_time_seconds": 10,
            }},
            {"metadata": {"agent_id": "a2", "canvas_types": ["sheets"], "outcome": "success"}},
            {"metadata": {"agent_id": "a1", "canvas_types": [], "outcome": "success"}},
        ])
        result = await svc.get_canvas_type_preferences("a1")
        assert result["sheets"]["count"] == 2
        assert result["sheets"]["success_rate"] == 0.5
        assert result["sheets"]["avg_engagement"] == 25.0
        assert result["sheets"]["avg_feedback_score"] == 0.8
        assert result["charts"]["count"] == 1

    async def test_canvas_preferences_error(self, svc):
        svc.db.search = Mock(side_effect=RuntimeError("boom"))
        result = await svc.get_canvas_type_preferences("a1")
        assert result == {}

    async def test_recommend_canvas_no_preferences(self, svc):
        with patch.object(svc, "get_canvas_type_preferences", new=AsyncMock(return_value={})):
            result = await svc.recommend_canvas_type("a1", "reporting")
        assert result["canvas_type"] == "generic"

    async def test_recommend_canvas_insufficient_data(self, svc):
        with patch.object(svc, "get_canvas_type_preferences", new=AsyncMock(return_value={
            "sheets": {"count": 1, "success_rate": 1.0, "avg_engagement": 50.0, "avg_feedback_score": 0.5}
        })):
            result = await svc.recommend_canvas_type("a1", "reporting")
        assert result["canvas_type"] == "generic"
        assert result["reason"] == "Insufficient data for recommendation"

    async def test_recommend_canvas_ranked(self, svc):
        with patch.object(svc, "get_canvas_type_preferences", new=AsyncMock(return_value={
            "sheets": {"count": 5, "success_rate": 0.8, "avg_engagement": 60.0, "avg_feedback_score": 0.6},
            "charts": {"count": 4, "success_rate": 0.5, "avg_engagement": 20.0, "avg_feedback_score": 0.1},
        })):
            result = await svc.recommend_canvas_type("a1", "reporting")
        assert result["canvas_type"] == "sheets"
        assert "High success rate" in result["reason"]
        assert result["alternatives"] == ["charts"]

    async def test_recommend_canvas_error(self, svc):
        with patch.object(svc, "get_canvas_type_preferences", new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await svc.recommend_canvas_type("a1", "reporting")
        assert result is None

    async def test_record_canvas_outcome(self, svc, experience):
        result = await svc.record_canvas_outcome(
            experience, ["sheets"], engagement_time_seconds=42.0, user_feedback=0.9
        )
        assert result is True
        call_args = svc.db.add_document.call_args[1]
        trace = call_args["metadata"]["trace"]
        assert trace["canvas_types"] == ["sheets"]
        assert trace["engagement_time_seconds"] == 42.0
        assert trace["user_feedback"] == 0.9
        assert trace["canvas_count"] == 1
        assert call_args["metadata"]["feedback_score"] == 0.9

    async def test_record_canvas_outcome_no_feedback(self, svc, experience):
        result = await svc.record_canvas_outcome(experience, ["charts"])
        assert result is True
        assert svc.db.add_document.call_args[1]["metadata"]["trace"]["canvas_count"] == 1

    async def test_record_canvas_outcome_error(self, svc, experience):
        svc.db.add_document = Mock(side_effect=RuntimeError("boom"))
        result = await svc.record_canvas_outcome(experience, ["sheets"])
        assert result is False

    def test_extract_canvas_insights(self, svc):
        episodes = [
            {
                "canvas_context": [
                    {"canvas_type": "sheets", "action": "present", "id": "c1"},
                    {"canvas_type": None, "action": "close"},
                ],
                "feedback_context": [{"rating": 5}],
            },
            {
                "canvas_context": [{"canvas_type": "charts", "action": "close", "id": "c2"}],
                "feedback_context": [{"rating": 2}],
            },
            {
                "canvas_context": [{"canvas_type": "markdown", "action": "submit", "id": "c3"}],
                "feedback_context": [],
            },
        ]
        result = svc._extract_canvas_insights(episodes)
        assert result["canvas_type_counts"] == {"sheets": 1, "charts": 1, "markdown": 1}
        assert result["user_actions"] == {"present": 1, "close": 1, "submit": 1}
        assert result["preferred_canvas_types"] == ["sheets", "charts", "markdown"]
        assert len(result["high_engagement_canvases"]) == 1
        assert result["high_engagement_canvases"][0]["canvas_type"] == "sheets"
        assert result["user_interaction_patterns"]["engages"] == ["sheets"]
        assert result["user_interaction_patterns"]["closes_quickly"] == ["charts"]
        assert result["user_interaction_patterns"]["submits"] == ["markdown"]

    def test_extract_canvas_insights_empty(self, svc):
        result = svc._extract_canvas_insights([])
        assert result["canvas_type_counts"] == {}
        assert result["preferred_canvas_types"] == []

    def test_extract_canvas_insights_error(self, svc):
        result = svc._extract_canvas_insights([None])
        assert "canvas_type_counts" in result
