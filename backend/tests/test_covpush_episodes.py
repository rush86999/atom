"""
Coverage-push tests for core/episode_service.py and
core/episode_segmentation_service.py.

Bug-hunt tests are written red-first; fixes are minimal and in the modules.
"""
import os
import sys
import types
import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from sqlalchemy.orm import Session

from core.episode_service import (
    DetailLevel,
    EpisodeService,
    ReadinessResponse,
    ReadinessThresholds,
)
from core.episode_segmentation_service import (
    EpisodeBoundaryDetector,
    EpisodeSegmentationService,
)
from core.models import (
    AgentEpisode,
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    ChatMessage,
    EpisodeSegment,
)


def make_execution(**over):
    e = Mock(spec=AgentExecution)
    e.id = over.get("id", "exec-1")
    e.agent_id = over.get("agent_id", "agent-1")
    e.tenant_id = over.get("tenant_id", "tenant-1")
    e.human_intervention_count = over.get("human_intervention_count", 0)
    e.started_at = over.get("started_at", datetime.now(timezone.utc))
    e.completed_at = over.get("completed_at", datetime.now(timezone.utc))
    e.created_at = over.get("created_at", datetime.now(timezone.utc))
    e.metadata_json = over.get("metadata_json", {})
    e.status = over.get("status", "completed")
    e.result_summary = over.get("result_summary", "done")
    e.task_description = over.get("task_description", "task")
    e.input_summary = over.get("input_summary", None)
    e.session_id = over.get("session_id", None)
    return e


def make_agent(**over):
    a = Mock(spec=AgentRegistry)
    a.id = over.get("id", "agent-1")
    a.tenant_id = over.get("tenant_id", "tenant-1")
    a.status = over.get("status", AgentStatus.STUDENT)
    a.confidence_score = over.get("confidence_score", 0.75)
    a.name = over.get("name", "Agent One")
    return a


def make_episode(**over):
    ep = Mock(spec=AgentEpisode)
    ep.id = over.get("id", "ep-1")
    ep.agent_id = over.get("agent_id", "agent-1")
    ep.tenant_id = over.get("tenant_id", "tenant-1")
    ep.execution_id = over.get("execution_id", "exec-1")
    ep.task_description = over.get("task_description", "do the thing")
    ep.maturity_at_time = over.get("maturity_at_time", AgentStatus.STUDENT)
    ep.constitutional_score = over.get("constitutional_score", 1.0)
    ep.human_intervention_count = over.get("human_intervention_count", 0)
    ep.confidence_score = over.get("confidence_score", 0.8)
    ep.outcome = over.get("outcome", "success")
    ep.success = over.get("success", True)
    ep.step_efficiency = over.get("step_efficiency", 1.0)
    ep.metadata_json = over.get("metadata_json", {})
    ep.started_at = over.get("started_at", datetime.now(timezone.utc))
    ep.completed_at = over.get("completed_at", datetime.now(timezone.utc))
    ep.proposal_id = over.get("proposal_id", None)
    ep.supervision_decision = over.get("supervision_decision", None)
    ep.supervisor_type = over.get("supervisor_type", None)
    ep.execution_followed_proposal = over.get("execution_followed_proposal", False)
    return ep


def query_chain(mock_db, results, order=None):
    """Configure mock_db.query to return the given results for .filter().first()/.all()."""
    q = Mock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.count.return_value = 5
    if order is None:
        q.all.return_value = results
        q.first.return_value = results[0] if results else None
    else:
        q.all.side_effect = results
        q.first.side_effect = results
    mock_db.query.return_value = q
    return q


def make_chain(first=None, all_=None, count=0):
    """A self-referential query chain mock: filter/order_by/limit/join return self."""
    q = Mock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.join.return_value = q
    q.first.return_value = first
    q.all.return_value = all_
    q.count.return_value = count
    return q


class TestEpisodeServiceCanvasMetadata:
    """_extract_canvas_metadata branches."""

    @pytest.fixture
    def service(self):
        return EpisodeService(db=Mock(spec=Session))

    async def test_no_execution_returns_empty(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        assert await service._extract_canvas_metadata("missing") == {}

    async def test_no_canvas_id_returns_empty(self, service):
        execution = make_execution(metadata_json={"other": 1}, session_id=None)
        service.db.query.return_value.filter.return_value.first.return_value = execution
        assert await service._extract_canvas_metadata("exec-1") == {}

    async def test_execution_missing_but_session_canvas_actions(self, service):
        execution = make_execution(metadata_json={}, session_id="sess-1")
        audit = Mock()
        audit.id = "ca-1"
        audit.canvas_id = "cv-1"
        audit.canvas_type = "sheets"
        audit.action_type = "update"
        audit.details_json = {"cell": "A1"}
        service.db.query.return_value.filter.return_value.first.return_value = execution
        service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [audit]
        out = await service._extract_canvas_metadata("exec-1")
        assert out["canvas_action_ids"] == ["ca-1"]
        assert out["canvas_action_count"] == 1
        assert "presentation_summary" in out

    async def test_canvas_id_with_full_context(self, service):
        execution = make_execution(
            metadata_json={"canvas_id": "cv-1"}, session_id="sess-1"
        )
        canvas = Mock()
        canvas.canvas_type = "sheets"
        actions = [Mock(id="ca-1"), Mock(id="ca-2")]
        service.db.query.side_effect = [
            make_chain(first=execution),
            make_chain(first=canvas),
            make_chain(count=5),
            make_chain(count=3),
            make_chain(all_=actions),
        ]

        provider = Mock()
        provider.get_canvas.return_value = SimpleNamespace(data={"components": [{"type": "chart"}]})
        summary_service = Mock()
        summary_service.generate_summary = AsyncMock(return_value="semantic summary")
        with patch(
            "core.episode_service._get_canvas_context_provider", return_value=provider
        ), patch(
            "core.episode_service._get_canvas_summary_service", return_value=summary_service
        ):
            out = await service._extract_canvas_metadata("exec-1", task_description="t")
        assert out["canvas_id"] == "cv-1"
        assert out["canvas_action_ids"] == ["ca-1", "ca-2"]
        assert out["presentation_summary"] == "semantic summary"
        assert out["canvas_artifact_count"] == 5

    async def test_canvas_not_found_fallback(self, service):
        execution = make_execution(
            metadata_json={"canvas_id": "cv-ghost"}, session_id="sess-1"
        )
        service.db.query.side_effect = [
            make_chain(first=execution),
            make_chain(first=None),
        ]
        out = await service._extract_canvas_metadata("exec-1")
        assert out == {"canvas_id": "cv-ghost"}

    async def test_semantic_summary_failure_swallowed(self, service):
        execution = make_execution(
            metadata_json={"canvas_id": "cv-1"}, session_id="sess-1"
        )
        canvas = Mock()
        canvas.canvas_type = "sheets"
        service.db.query.side_effect = [
            make_chain(first=execution),
            make_chain(first=canvas),
            make_chain(count=0),
            make_chain(count=0),
            make_chain(all_=[]),
        ]
        provider = Mock()
        provider.get_canvas.return_value = SimpleNamespace(data={})
        with patch(
            "core.episode_service._get_canvas_context_provider", return_value=provider
        ):
            out = await service._extract_canvas_metadata("exec-1")
        assert out["canvas_id"] == "cv-1"
        assert out["presentation_summary"] is None

    async def test_query_error_returns_empty(self, service):
        service.db.query.side_effect = RuntimeError("secret db boom")
        assert await service._extract_canvas_metadata("exec-1") == {}


class TestEpisodeServiceCreationErrors:
    """create_episode_from_execution error and hook paths."""

    @pytest.fixture
    def service(self):
        s = EpisodeService(db=Mock(spec=Session))
        s.activity_publisher = None
        return s

    async def test_missing_execution_raises(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="not found"):
            await service.create_episode_from_execution(
                "exec-x", "task", "success", True
            )

    async def test_missing_agent_raises(self, service):
        service.db.query.return_value.filter.return_value.first.side_effect = [
            make_execution(), None
        ]
        with pytest.raises(ValueError, match="not found"):
            await service.create_episode_from_execution(
                "exec-1", "task", "success", True
            )

    async def test_activity_publisher_failure_swallowed(self, service):
        publisher = Mock()
        publisher.publish_episode_recording.side_effect = RuntimeError("publisher down")
        service.activity_publisher = publisher
        service.db.query.return_value.filter.return_value.first.side_effect = [
            make_execution(), make_agent()
        ]
        service.db.query.return_value.filter.return_value.all.return_value = []
        with patch.object(EpisodeService, "_extract_canvas_metadata", AsyncMock(return_value={})):
            episode = await service.create_episode_from_execution(
                "exec-1", "task", "success", True
            )
        assert episode is not None
        assert publisher.publish_episode_recording.call_count == 2

    async def test_failed_outcome_emits_fail_event(self, service):
        from core.auto_dev.event_hooks import event_bus as real_bus
        event_bus = Mock()
        event_bus.emit_task_fail = AsyncMock()
        with patch("core.auto_dev.event_hooks.event_bus", event_bus), \
             patch("core.auto_dev.event_hooks.TaskEvent"), \
             patch.object(EpisodeService, "_extract_canvas_metadata", AsyncMock(return_value={})):
            service.db.query.return_value.filter.return_value.first.side_effect = [
                make_execution(), make_agent()
            ]
            service.db.query.return_value.filter.return_value.all.return_value = []
            await service.create_episode_from_execution(
                "exec-1", "task", "failure", False
            )
        assert event_bus.emit_task_fail.called


class TestEpisodeServiceReadiness:
    """Readiness metrics, thresholds and helpers."""

    @pytest.fixture
    def service(self):
        return EpisodeService(db=Mock(spec=Session))

    def test_readiness_response_to_dict(self):
        r = ReadinessResponse(
            agent_id="a", current_level="student", readiness_score=0.8,
            threshold_met=True, zero_intervention_ratio=0.5,
            avg_constitutional_score=1.0, avg_confidence_score=0.8,
            success_rate=1.0, episodes_analyzed=10, breakdown={},
            supervision_success_rate=0.9,
        )
        d = r.to_dict()
        assert d["supervision_success_rate"] == 0.9
        assert d["threshold_met"] is True

    def test_calculate_readiness_metrics_empty(self, service):
        m = service.calculate_readiness_metrics([])
        assert m["success_rate"] == 0.0
        assert m["avg_step_efficiency"] == 0.0

    def test_calculate_readiness_metrics_full(self, service):
        eps = [
            make_episode(success=True, human_intervention_count=0,
                         constitutional_score=1.0, confidence_score=0.9,
                         outcome="success", step_efficiency=1.0),
            make_episode(success=False, human_intervention_count=2,
                         constitutional_score=0.6, confidence_score=0.5,
                         outcome="failure", step_efficiency=0.5),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["success_rate"] == 0.5
        assert m["zero_intervention_ratio"] == 0.5
        assert m["avg_constitutional_score"] == 0.8
        assert m["total_interventions"] == 2
        assert m["episodes_by_outcome"] == {"success": 1, "failure": 1}

    def test_calculate_readiness_metrics_step_efficiency_denominator(self, service):
        """BUG-HUNT: avg_step_efficiency must average only the episodes that
        HAVE a step_efficiency — a None entry must not deflate the mean."""
        eps = [
            make_episode(step_efficiency=0.5),
            make_episode(step_efficiency=0.5),
            make_episode(step_efficiency=None),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["avg_step_efficiency"] == pytest.approx(0.5)

    def test_calculate_supervision_metrics_empty_and_no_proposals(self, service):
        m = service.calculate_supervision_metrics([])
        assert m["total_proposals"] == 0
        m2 = service.calculate_supervision_metrics([make_episode(proposal_id=None)])
        assert m2["total_proposals"] == 0
        assert m2["supervision_success_rate"] == 0.0

    def test_calculate_supervision_metrics_full(self, service):
        eps = [
            make_episode(proposal_id="p1", supervision_decision="approved",
                         supervisor_type="user", execution_followed_proposal=True),
            make_episode(proposal_id="p2", supervision_decision="approved",
                         supervisor_type="autonomous_agent",
                         execution_followed_proposal=False),
            make_episode(proposal_id="p3", supervision_decision="rejected",
                         supervisor_type="user"),
        ]
        m = service.calculate_supervision_metrics(eps)
        assert m["total_proposals"] == 3
        assert m["approved_proposals"] == 2
        assert m["rejected_proposals"] == 1
        assert m["approval_rate"] == pytest.approx(2 / 3, abs=0.001)
        assert m["execution_success_rate"] == pytest.approx(0.5)
        assert m["supervisor_type_breakdown"] == {"user": 2, "autonomous_agent": 1}

    def test_calculate_skill_diversity_metrics(self, service):
        summaries = [
            SimpleNamespace(skill_id="s1", skill_name="web", execution_count=3,
                            success_rate=1.0),
            SimpleNamespace(skill_id="s2", skill_name="db", execution_count=5,
                            success_rate=0.8),
        ]
        with patch.object(service, "get_agent_skill_usage", return_value=summaries):
            m = service.calculate_skill_diversity_metrics("a", "t")
        assert m["unique_skill_count"] == 2
        assert m["skill_diversity_score"] == pytest.approx(0.2)
        assert m["avg_skill_success_rate"] == pytest.approx(0.9)
        assert m["total_skill_executions"] == 8
        assert len(m["top_skills"]) == 2

    def test_calculate_proposal_quality_metrics_empty(self, service):
        service.db.query.return_value.filter.return_value.all.return_value = []
        m = service.calculate_proposal_quality_metrics("a", "t")
        assert m["proposal_quality_score"] == 0.0

    def test_calculate_proposal_quality_metrics_full(self, service):
        eps = [
            make_episode(metadata_json={"episode_type": "meta_agent_proposal",
                                        "quality_score": 0.9}),
            make_episode(metadata_json={"episode_type": "meta_agent_proposal",
                                        "quality_score": 0.5}),
            make_episode(metadata_json={"episode_type": "meta_agent_proposal"}),
        ]
        service.db.query.return_value.filter.return_value.all.return_value = eps
        m = service.calculate_proposal_quality_metrics("a", "t")
        assert m["proposal_episode_count"] == 3
        assert m["avg_proposal_quality"] == pytest.approx(0.7)
        assert m["high_quality_proposal_count"] == 1
        assert m["proposal_quality_score"] == pytest.approx(0.84)

    def test_get_agent_episodes_filters(self, service):
        service.db.query.return_value = make_chain(all_=[])
        out = service.get_agent_episodes(
            "a", "t", outcome_filter="failure",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
        )
        assert out == []

    def test_next_level_and_thresholds(self, service):
        assert service._get_next_level(AgentStatus.STUDENT.value) == AgentStatus.INTERN.value
        assert service._get_next_level(AgentStatus.INTERN.value) == AgentStatus.SUPERVISED.value
        assert service._get_next_level(AgentStatus.SUPERVISED.value) == AgentStatus.AUTONOMOUS.value
        assert service._get_next_level(AgentStatus.AUTONOMOUS.value) == AgentStatus.AUTONOMOUS.value
        assert service._get_next_level("bogus") == AgentStatus.INTERN.value
        assert service._get_threshold_for_level(AgentStatus.INTERN.value) == 0.70
        assert service._get_threshold_for_level("bogus") == 0.70
        assert service._get_min_episodes_for_level(AgentStatus.AUTONOMOUS.value) == 50
        assert service._get_min_episodes_for_level("bogus") == 10

    def test_graduation_readiness_with_target_and_override(self, service):
        agent = make_agent(status=AgentStatus.STUDENT)
        eps = [make_episode() for _ in range(3)]
        q = Mock()
        q.first.side_effect = [agent, None]
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = eps
        service.db.query.return_value = q
        with patch.object(service, "calculate_readiness_metrics",
                          return_value={
                              "zero_intervention_ratio": 1.0,
                              "avg_constitutional_score": 1.0,
                              "avg_confidence_score": 1.0,
                              "success_rate": 1.0,
                              "episodes_by_outcome": {"success": 3},
                              "total_interventions": 0,
                              "avg_step_efficiency": 1.0,
                          }), \
             patch.object(service, "calculate_supervision_metrics",
                          return_value={"supervision_success_rate": 1.0}), \
             patch.object(service, "calculate_skill_diversity_metrics",
                          return_value={"skill_diversity_score": 1.0}), \
             patch.object(service, "calculate_proposal_quality_metrics",
                          return_value={"proposal_quality_score": 1.0}):
            r = service.get_graduation_readiness(
                "agent-1", "tenant-1", target_level=AgentStatus.INTERN.value,
                min_episodes_override=1,
            )
        assert r.episodes_analyzed == 3
        assert r.readiness_score > 0.9
        assert r.threshold_met is True
        assert r.breakdown["target_level"] == AgentStatus.INTERN.value


class TestEpisodeServiceFeedback:
    """Feedback CRUD + domain metrics."""

    @pytest.fixture
    def service(self):
        return EpisodeService(db=Mock(spec=Session))

    def test_update_episode_feedback_missing_episode(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            service.update_episode_feedback("ep-x", 0.9)

    def test_update_episode_feedback_success(self, service):
        episode = make_episode(metadata_json={"learnings": "x"})
        service.db.query.return_value = make_chain(first=episode)
        service.db.refresh.return_value = Mock(id="fb-1")
        with patch("core.capability_graduation_service.CapabilityGraduationService") as CGS:
            grad = CGS.return_value
            fid = service.update_episode_feedback(
                "ep-1", 0.9, feedback_notes="n" * 600, feedback_category="accuracy",
                capability_domain="reasoning", capability_name="planning",
            )
        assert isinstance(fid, str)
        assert grad.record_capability_usage.called

    def test_update_episode_feedback_capability_tracking_failure(self, service):
        episode = make_episode()
        service.db.query.return_value = make_chain(first=episode)
        with patch("core.capability_graduation_service.CapabilityGraduationService",
                   side_effect=RuntimeError("cap down")):
            fid = service.update_episode_feedback(
                "ep-1", 0.5, capability_domain="d", capability_name="c"
            )
        assert isinstance(fid, str)

    def test_get_episode_feedback(self, service):
        fb = SimpleNamespace(
            id="f1", feedback_score=0.8, feedback_notes="good", feedback_category="x",
            provider_id="u1", provider_type="human",
            provided_at=datetime.now(timezone.utc),
        )
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = [fb]
        service.db.query.return_value = q
        out = service.get_episode_feedback("ep-1")
        assert out[0]["feedback_score"] == 0.8

    def test_get_domain_feedback_metrics_empty(self, service):
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = []
        service.db.query.return_value = q
        m = service.get_domain_feedback_metrics("t", "reasoning")
        assert m["trend"] == "no_data"

    def test_get_domain_feedback_metrics_improving(self, service):
        def fb(score):
            return SimpleNamespace(
                feedback_score=score, capability_name="planning",
                provided_at=datetime.now(timezone.utc),
            )
        records = [fb(0.3), fb(0.3), fb(0.9), fb(0.9)]
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = records
        service.db.query.return_value = q
        m = service.get_domain_feedback_metrics("t", "reasoning")
        assert m["trend"] == "improving"
        assert m["feedback_count"] == 4
        assert m["avg_rating"] == pytest.approx(0.6)
        assert m["by_capability"]["planning"]["count"] == 4

    def test_get_domain_feedback_metrics_declining(self, service):
        def fb(score):
            return SimpleNamespace(
                feedback_score=score, capability_name=None,
                provided_at=datetime.now(timezone.utc),
            )
        records = [fb(0.9), fb(0.9), fb(0.1)]
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.all.return_value = records
        service.db.query.return_value = q
        m = service.get_domain_feedback_metrics("t", "reasoning")
        assert m["trend"] == "declining"

    def test_get_domain_feedback_metrics_error_no_str_leak(self, service):
        """BUG-HUNT: the error response must not leak internal exception text."""
        service.db.query.side_effect = RuntimeError("secret-db-token-99")
        m = service.get_domain_feedback_metrics("t", "reasoning")
        assert "secret-db-token-99" not in m["error"]

    async def test_sync_feedback_to_lancedb_success(self, service):
        episode = make_episode(metadata_json={"learnings": "L", "agent_role": "x"})
        feedback = SimpleNamespace(feedback_notes="note")
        with patch("core.agent_world_model.WorldModelService") as WM:
            wm = WM.return_value
            wm.record_episode = AsyncMock(return_value=True)
            ok = await service._sync_feedback_to_lancedb(episode, feedback)
        assert ok is True

    async def test_sync_feedback_to_lancedb_failure(self, service):
        episode = make_episode(metadata_json={})
        feedback = SimpleNamespace(feedback_notes=None)
        with patch("core.agent_world_model.WorldModelService",
                   side_effect=RuntimeError("wm down")):
            ok = await service._sync_feedback_to_lancedb(episode, feedback)
        assert ok is False


class TestEpisodeServiceCanvasAndRecall:
    """Canvas action linking and progressive recall."""

    @pytest.fixture
    def service(self):
        return EpisodeService(db=Mock(spec=Session))

    def test_get_canvas_actions_missing_episode(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        assert service.get_canvas_actions_for_episode("ep-x") == []

    def test_get_canvas_actions_no_ids(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = make_episode()
        assert service.get_canvas_actions_for_episode("ep-1") == []

    def test_get_canvas_actions_with_records(self, service):
        episode = make_episode(metadata_json={"canvas_action_ids": ["ca-1"]})
        action = Mock()
        action.id = "ca-1"
        action.action_type = "update"
        action.canvas_id = "cv-1"
        action.user_id = "u1"
        action.details_json = {"cell": "A1"}
        action.created_at = datetime.now(timezone.utc)
        service.db.query.side_effect = [
            make_chain(first=episode),
            make_chain(all_=[action]),
        ]
        out = service.get_canvas_actions_for_episode("ep-1")
        assert out[0]["id"] == "ca-1"

    async def test_recall_episodes_with_detail_ok(self, service):
        result = Mock()
        result.scalar_one_or_none.return_value = "agent-1"
        row = Mock()
        row._mapping = {"id": "ep-1", "task_description": "t"}
        result.fetchall.return_value = [row]
        # W35: Session.execute is synchronous (no await) — plain Mock, not AsyncMock
        service.db.execute = Mock(return_value=result)
        out = await service.recall_episodes_with_detail(
            "agent-1", "tenant-1", detail_level=DetailLevel.FULL, limit=5
        )
        assert out[0]["id"] == "ep-1"

    async def test_recall_episodes_tenant_mismatch(self, service):
        result = Mock()
        result.scalar_one_or_none.return_value = None
        service.db.execute = Mock(return_value=result)
        out = await service.recall_episodes_with_detail("agent-1", "tenant-2")
        assert out == []

    async def test_link_canvas_actions(self, service):
        episode = make_episode()
        service.db.query.return_value.filter.return_value.first.return_value = episode
        assert await service.link_canvas_actions_to_episode("ep-1", ["ca-1"]) is True
        assert episode.metadata_json["canvas_action_ids"] == ["ca-1"]

    async def test_link_canvas_actions_missing_episode(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        assert await service.link_canvas_actions_to_episode("ep-x", ["ca-1"]) is False


class TestEpisodeServiceSkills:
    """Skill performance / mastery surface."""

    @pytest.fixture
    def service(self):
        return EpisodeService(db=Mock(spec=Session))

    def test_get_skill_performance_stats_empty(self, service):
        skill = Mock()
        skill.name = "web_search"
        service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        service.db.query.return_value.filter.return_value.first.return_value = skill
        stats = service.get_skill_performance_stats("a", "t", "skill-1")
        assert stats.total_executions == 0
        assert stats.skill_name == "web_search"
        assert stats.avg_execution_time is None

    def test_get_skill_performance_stats_full(self, service):
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        eps = [
            make_episode(success=True, started_at=start, completed_at=end),
            make_episode(success=False, started_at=start, completed_at=end),
        ]
        skill = Mock()
        skill.name = "db_query"
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.side_effect = [eps, None]
        q.first.return_value = skill
        service.db.query.return_value = q
        stats = service.get_skill_performance_stats("a", "t", "skill-1")
        assert stats.total_executions == 2
        assert stats.success_rate == 0.5
        assert stats.avg_execution_time == 60.0

    def test_get_agent_skill_usage_and_count(self, service):
        eps = [
            make_episode(success=True, metadata_json={"skill_id": "s1",
                                                      "skill_type": "openclaw"}),
            make_episode(success=False, metadata_json={"skill_id": "s1",
                                                       "skill_type": "openclaw"}),
            make_episode(success=True, metadata_json={"skill_type": "openclaw"}),
        ]
        skill = Mock()
        skill.name = "s1 name"
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.count.return_value = 2
        q.all.side_effect = [eps, [skill], [skill]]
        q.first.return_value = skill
        service.db.query.return_value = q
        summaries = service.get_agent_skill_usage("a", "t")
        assert len(summaries) == 1
        assert summaries[0].skill_id == "s1"
        assert summaries[0].success_rate == 0.5
        assert service.get_skill_usage_count("a", "t") == 2

    def test_get_required_skills_for_level(self, service):
        assert service.get_required_skills_for_level("student") == 1
        assert service.get_required_skills_for_level("intern") == 3
        assert service.get_required_skills_for_level("supervised") == 5
        assert service.get_required_skills_for_level("autonomous") == 10
        assert service.get_required_skills_for_level("bogus") == 1

    def test_assess_skill_mastery(self, service):
        summaries = [
            SimpleNamespace(skill_id="s1", skill_name="a", execution_count=2,
                            success_rate=1.0),
            SimpleNamespace(skill_id="s2", skill_name="b", execution_count=1,
                            success_rate=0.0),
        ]
        with patch.object(service, "get_agent_skill_usage", return_value=summaries):
            m = service.assess_skill_mastery("a", "t", "intern")
        assert m.required_skills_for_level == 3
        assert m.skill_diversity == pytest.approx(2 / 3, abs=0.001)
        assert m.skill_success_rate == 0.5
        assert m.skills_used == {"s1", "s2"}
        assert m.mastery_score == pytest.approx(0.6)

    def test_get_proposal_episodes_for_learning(self, service):
        ep = make_episode(
            metadata_json={
                "episode_type": "meta_agent_proposal",
                "quality_score": 0.9,
                "proposal_id": "p1",
                "capability_tags": ["web"],
                "teaching_value": "tv",
                "meta_agent_guidance": "g",
                "quality_breakdown": {},
            }
        )
        q = Mock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [ep]
        service.db.query.return_value = q
        out = service.get_proposal_episodes_for_learning("t", "a", capability_tags=["web"])
        assert out[0]["episode_id"] == ep.id
        assert out[0]["proposal_id"] == "p1"
        out2 = service.get_proposal_episodes_for_learning("t", "a", capability_tags=["other"])
        assert out2 == []


class TestEpisodeServiceArchival:
    """archive_episode_to_cold_storage paths."""

    @pytest.fixture
    def service(self):
        return EpisodeService(db=Mock(spec=Session))

    async def test_archive_missing_episode(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = None
        assert await service.archive_episode_to_cold_storage("ep-x") is False

    async def test_archive_lancedb_unavailable(self, service):
        service.db.query.return_value.filter.return_value.first.return_value = make_episode()
        embedding = Mock()
        embedding.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        service.embedding_service = embedding
        assert await service.archive_episode_to_cold_storage("ep-1") is False

    async def test_archive_success_with_billing(self, service):
        episode = make_episode(tenant_id="tenant-1")
        service.db.query.return_value = make_chain(first=episode)
        embedding = Mock()
        embedding.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        embedding.get_embedding_dimension.return_value = 384
        service.embedding_service = embedding
        lancedb = Mock()
        lancedb.connect.return_value = True
        lancedb.add_episode.return_value = True
        # W25: the phantom core.acu_billing_service was replaced with the real
        # UsageTrackingService shim (track_acu_usage) — assert the new contract.
        billing = Mock()
        with patch("core.usage_tracking_service.UsageTrackingService",
                   return_value=billing), \
             patch("core.episode_service.LanceDBService", return_value=lancedb):
            ok = await service.archive_episode_to_cold_storage("ep-1")
        assert ok is True
        assert billing.track_acu_usage.called

    async def test_archive_embedding_failure_uses_zero_vector(self, service):
        episode = make_episode()
        service.db.query.return_value = make_chain(first=episode)
        embedding = Mock()
        embedding.generate_embedding = AsyncMock(side_effect=RuntimeError("embed down"))
        embedding.get_embedding_dimension.return_value = 384
        service.embedding_service = embedding
        lancedb = Mock()
        lancedb.connect.return_value = True
        lancedb.add_episode.return_value = True
        fake_module = types.ModuleType("core.acu_billing_service")
        fake_module.ACUBillingService = Mock(side_effect=RuntimeError("billing down"))
        with patch.dict(sys.modules, {"core.acu_billing_service": fake_module}), \
             patch("core.episode_service.LanceDBService", return_value=lancedb):
            ok = await service.archive_episode_to_cold_storage("ep-1")
        assert ok is True

    async def test_archive_billing_module_missing_is_soft_fail(self, service):
        episode = make_episode()
        service.db.query.return_value = make_chain(first=episode)
        embedding = Mock()
        embedding.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        service.embedding_service = embedding
        lancedb = Mock()
        lancedb.connect.return_value = True
        lancedb.add_episode.return_value = True
        with patch.dict(sys.modules, {"core.acu_billing_service": None}), \
             patch("core.episode_service.LanceDBService", return_value=lancedb):
            ok = await service.archive_episode_to_cold_storage("ep-1")
        assert ok is True

    async def test_archive_add_failure(self, service):
        episode = make_episode()
        service.db.query.return_value.filter.return_value.first.return_value = episode
        embedding = Mock()
        embedding.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        service.embedding_service = embedding
        lancedb = Mock()
        lancedb.connect.return_value = True
        lancedb.add_episode.return_value = False
        with patch("core.episode_service.LanceDBService", return_value=lancedb):
            ok = await service.archive_episode_to_cold_storage("ep-1")
        assert ok is False


class TestStepEfficiency:
    """TRACE step efficiency computation."""

    def test_no_steps_returns_one(self):
        service = EpisodeService(db=Mock(spec=Session))
        service.db.query.return_value.filter.return_value.all.return_value = []
        assert service._calculate_step_efficiency("exec-1") == 1.0

    def test_steps_with_normal_cycles(self):
        service = EpisodeService(db=Mock(spec=Session))
        steps = [
            SimpleNamespace(step_type="thought"),
            SimpleNamespace(step_type="action"),
            SimpleNamespace(step_type="observation"),
        ]
        service.db.query.return_value.filter.return_value.all.return_value = steps
        eff = service._calculate_step_efficiency("exec-1")
        assert 0.0 < eff <= 1.0


def make_message(content="hello", role="user", created_at=None):
    m = Mock(spec=ChatMessage)
    m.content = content
    m.role = role
    m.id = f"msg-{id(m)}"
    m.created_at = created_at or datetime.now(timezone.utc)
    return m


class TestBoundaryDetector:
    """EpisodeBoundaryDetector signals."""

    def test_time_gap_exclusive_threshold(self):
        now = datetime.now(timezone.utc)
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        msgs = [
            make_message(created_at=now),
            make_message(created_at=now + timedelta(minutes=30)),
            make_message(created_at=now + timedelta(minutes=61)),
        ]
        assert detector.detect_time_gap(msgs) == [2]

    def test_no_time_gap(self):
        now = datetime.now(timezone.utc)
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        msgs = [
            make_message(created_at=now),
            make_message(created_at=now + timedelta(minutes=5)),
        ]
        assert detector.detect_time_gap(msgs) == []

    def test_topic_changes_embedding_similarity(self):
        db = Mock()
        db.embed_text.side_effect = [[1.0, 0.0], [0.0, 1.0]]
        detector = EpisodeBoundaryDetector(lancedb_handler=db)
        msgs = [
            make_message(content="finance report"),
            make_message(content="puppy photos"),
        ]
        changes = detector.detect_topic_changes(msgs)
        assert changes == [1]

    def test_topic_changes_embedding_none_falls_back_to_keywords(self):
        db = Mock()
        db.embed_text.return_value = None
        detector = EpisodeBoundaryDetector(lancedb_handler=db)
        msgs = [
            make_message(content="alpha beta gamma delta"),
            make_message(content="alpha beta gamma delta"),
        ]
        assert detector.detect_topic_changes(msgs) == []

    def test_topic_changes_requires_two_messages(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=None)
        assert detector.detect_topic_changes([make_message()]) == []
        detector2 = EpisodeBoundaryDetector(lancedb_handler=None)
        assert detector2.detect_topic_changes([]) == []

    def test_detect_task_completion(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        execs = [
            make_execution(status="completed", result_summary="done"),
            make_execution(status="failed", result_summary=None),
        ]
        assert detector.detect_task_completion(execs) == [0]

    def test_cosine_similarity_numpy_and_fallback(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        assert detector._cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
        assert detector._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
        assert detector._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
        assert detector._cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)

    def test_keyword_similarity(self):
        detector = EpisodeBoundaryDetector(lancedb_handler=Mock())
        assert detector._keyword_similarity("", "") == 0.0
        assert detector._keyword_similarity("a b c", "a b c") == 1.0
        assert detector._keyword_similarity("a b", "c d") == 0.0
        assert detector._keyword_similarity("x y z w", "x y z w") == pytest.approx(1.0)


class TestSegmentationEpisodeCreation:
    """create_episode_from_session paths."""

    def _service(self, db, lancedb=None):
        return EpisodeSegmentationService(db=db, lancedb=lancedb)

    async def test_session_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = self._service(db)
        assert await svc.create_episode_from_session("sess-x", "agent-1") is None

    async def test_too_small_session(self):
        db = Mock()
        session = Mock()
        session.id = "sess-1"
        session.user_id = "u1"
        session.created_at = datetime.now(timezone.utc)
        db.query.side_effect = [
            make_chain(first=session),
            make_chain(all_=[make_message()]),
            make_chain(all_=[]),
            make_chain(all_=[]),
            make_chain(first=None),
        ]
        svc = self._service(db)
        out = await svc.create_episode_from_session("sess-1", "agent-1")
        assert out is None

    async def test_force_create_small_session(self):
        db = Mock()
        session = Mock()
        session.id = "sess-1"
        session.user_id = "u1"
        session.created_at = datetime.now(timezone.utc)
        db.query.side_effect = [
            make_chain(first=session),
            make_chain(all_=[make_message(content="hi")]),
            make_chain(all_=[]),
            make_chain(all_=[]),
            make_chain(first=None),
        ]
        svc = self._service(db)
        with patch.object(EpisodeSegmentationService, "_create_segments",
                          AsyncMock()), \
             patch.object(EpisodeSegmentationService, "_archive_to_lancedb",
                          AsyncMock()):
            out = await svc.create_episode_from_session(
                "sess-1", "agent-1", force_create=True
            )
        assert out is not None
        assert out["status"] == "completed"

    async def test_no_data_returns_none(self):
        db = Mock()
        session = Mock()
        session.id = "sess-1"
        session.user_id = "u1"
        session.created_at = datetime.now(timezone.utc)
        db.query.side_effect = [
            make_chain(first=session),
            make_chain(all_=[]),
            make_chain(all_=[]),
            make_chain(all_=[]),
            make_chain(first=None),
        ]
        svc = self._service(db)
        out = await svc.create_episode_from_session("sess-1", "agent-1")
        assert out is None

    async def test_full_creation_with_canvas_and_feedback(self):
        db = Mock()
        session = Mock()
        session.id = "sess-1"
        session.user_id = "u1"
        session.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msgs = [
            make_message(content="start task", role="user",
                         created_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)),
            make_message(content="done", role="assistant",
                         created_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)),
        ]
        execution = make_execution(
            status="completed", result_summary="ok",
            started_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        )
        agent = make_agent()
        db.query.side_effect = [
            make_chain(first=session),
            make_chain(all_=msgs),
            make_chain(all_=[execution]),
            make_chain(all_=[]),
            make_chain(all_=[]),
            make_chain(first=agent),
        ]
        svc = self._service(db, lancedb=Mock(db=None))
        with patch.object(svc.canvas_summary_service, "generate_summary",
                          AsyncMock(return_value="presented chart")):
            out = await svc.create_episode_from_session("sess-1", "agent-1")
        assert out is not None
        assert out["outcome"] == "success"
        assert out["maturity_at_time"] == "student"
        assert out["canvas_action_count"] == 0
        assert out["feedback_ids"] == []
        db.commit.assert_called()

    async def test_boundary_creation_with_segments(self):
        db = Mock()
        session = Mock()
        session.id = "sess-1"
        session.user_id = "u1"
        session.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msgs = [
            make_message(content="first topic", created_at=now),
            make_message(content="second topic", created_at=now + timedelta(minutes=45)),
            make_message(content="third", created_at=now + timedelta(minutes=46)),
        ]
        db.query.return_value = make_chain(first=session, all_=[])
        # Identical embeddings -> no topic-change boundaries, only the time gap.
        lancedb = Mock(db=None)
        lancedb.embed_text.return_value = [1.0, 0.0]
        svc = self._service(db, lancedb=lancedb)
        boundaries = set(svc.detector.detect_time_gap(msgs))
        assert boundaries == {1}
        episode = {
            "id": "ep-1", "title": "t", "description": "d", "summary": "s",
            "agent_id": "a", "user_id": "u", "workspace_id": "default",
            "session_id": "sess-1", "status": "completed", "outcome": "unknown",
        }
        with patch.object(EpisodeSegmentationService, "_archive_to_lancedb",
                          AsyncMock()):
            await svc._create_segments(episode, msgs, [], boundaries, {})
        added = [c.args[0] for c in db.add.call_args_list]
        assert len(added) == 2
        assert all(isinstance(s, EpisodeSegment) for s in added)
        assert added[0].sequence_order == 0
        assert added[1].sequence_order == 1
        db.commit.assert_called()


class TestSegmentationHelpers:
    """Title/description/summary/topics/entities/duration/importance."""

    @pytest.fixture
    def svc(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        return EpisodeSegmentationService(db=db, lancedb=Mock(db=None))

    def test_generate_title_variants(self, svc):
        msgs = [make_message(content="x" * 60, role="user")]
        title = svc._generate_title(msgs, [])
        assert title.endswith("...")
        assert len(title) == 50
        msgs2 = [make_message(content="short", role="assistant")]
        assert svc._generate_title(msgs2, []) == "Episode from " + svc._generate_title([], []).split("from ")[1]
        assert svc._generate_title([], []).startswith("Episode from")

    def test_generate_description_and_summary(self, svc):
        msgs = [make_message(content="hello world", role="user")]
        assert "1 messages" in svc._generate_description(msgs, [])
        assert svc._generate_summary(msgs, []).startswith("Started: hello")
        assert svc._generate_summary([], []) == "Episode summary"

    def test_calculate_duration(self, svc):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        execution = make_execution(started_at=start, completed_at=end)
        assert svc._calculate_duration([], [execution]) == 60
        assert svc._calculate_duration([], []) is None

    def test_extract_topics(self, svc):
        msgs = [make_message(content="alpha beta gamma delta epsilon")] 
        topics = svc._extract_topics(msgs, [])
        assert "alpha" in topics
        execution = make_execution(task_description="zephyr kappa lambda")
        topics2 = svc._extract_topics([], [execution])
        assert "zephyr" in topics2

    def test_extract_entities(self, svc):
        msg = make_message(
            content="Contact bob@example.com at 555-123-4567 https://example.com"
        )
        entities = svc._extract_entities([msg], [])
        assert "bob@example.com" in entities
        assert "555-123-4567" in entities
        assert "https://example.com" in entities
        exec_entity = make_execution(task_description="ACME Corp deal")
        entities2 = svc._extract_entities([], [exec_entity])
        assert "ACME" in entities2

    def test_calculate_importance(self, svc):
        assert svc._calculate_importance([], []) == 0.5
        many_msgs = [make_message() for _ in range(11)]
        assert svc._calculate_importance(many_msgs, []) == 0.7
        assert svc._calculate_importance([], [make_execution()]) == 0.6

    def test_get_agent_maturity(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        assert svc._get_agent_maturity("a") == "STUDENT"
        agent = make_agent(status=AgentStatus.SUPERVISED)
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        assert svc._get_agent_maturity("a") == "supervised"

    def test_count_interventions_and_human_edits(self, svc):
        execs = [
            make_execution(metadata_json={"human_intervention": True}),
            make_execution(metadata_json={}),
            make_execution(metadata_json={"human_corrections": ["fix1", "fix2"]}),
        ]
        assert svc._count_interventions(execs) == 1
        assert svc._extract_human_edits(execs) == ["fix1", "fix2"]

    def test_derive_outcome(self, svc):
        assert svc._derive_outcome([]) == "unknown"
        assert svc._derive_outcome([make_execution(status="failed")]) == "failure"
        assert svc._derive_outcome([make_execution(status="completed")]) == "success"
        assert svc._derive_outcome([make_execution(status="max_steps_exceeded")]) == "partial"
        assert svc._derive_outcome([make_execution(status=None)]) == "partial"

    def test_world_model_version(self, svc):
        with patch.dict(os.environ, {"WORLD_MODEL_VERSION": "v9"}):
            assert svc._get_world_model_version() == "v9"
        config = Mock()
        config.value = "v2"
        chain = make_chain(first=config)
        svc.db.query.return_value = chain
        with patch("core.models.SystemConfig", Mock(), create=True):
            assert svc._get_world_model_version() == "v2"
        chain.first.return_value = None
        assert svc._get_world_model_version() == "v1.0"

    def test_format_messages_summarize_execution(self, svc):
        msgs = [make_message(content="hi", role="user"), make_message(content="yo", role="assistant")]
        formatted = svc._format_messages(msgs)
        assert "user: hi" in formatted
        assert svc._summarize_messages([]) == ""
        assert svc._summarize_messages(msgs[:1]) == "hi"
        assert "(2 messages)" in svc._summarize_messages(msgs)
        exec_ = make_execution(task_description="do x", result_summary="did it")
        out = svc._format_execution(exec_)
        assert "Task: do x" in out
        assert "Result: did it" in out
        assert "Status: completed" in out
        out2 = svc._format_execution(make_execution(task_description=None, input_summary="in"))
        assert "Task: in" in out2


class TestSegmentationLancedb:
    """Archival and column-ensuring branches."""

    @pytest.fixture
    def svc(self):
        return EpisodeSegmentationService(db=Mock(), lancedb=Mock(db=None))

    def test_ensure_episode_columns_adds_missing(self, svc):
        table = Mock()
        table.schema = [SimpleNamespace(name="id")]
        svc.lancedb.get_table.return_value = table
        svc._ensure_episode_columns("episodes")
        table.add_columns.assert_called()

    def test_ensure_episode_columns_existing(self, svc):
        table = Mock()
        table.schema = [SimpleNamespace(name="outcome"), SimpleNamespace(name="agent_id")]
        svc.lancedb.get_table.return_value = table
        svc._ensure_episode_columns("episodes")
        table.add_columns.assert_not_called()

    def test_ensure_episode_columns_error(self, svc):
        svc.lancedb.get_table.side_effect = RuntimeError("boom")
        svc._ensure_episode_columns("episodes")

    async def test_archive_skipped_when_no_db(self, svc):
        await svc._archive_to_lancedb({"id": "ep-1", "title": "t"})

    async def test_archive_with_canvas_summary(self, svc):
        svc.lancedb.db = Mock()
        svc.lancedb.db.table_names.return_value = ["episodes"]
        table = Mock()
        table.schema = [SimpleNamespace(name="id")]
        svc.lancedb.get_table.return_value = table
        episode = {
            "id": "ep-1", "title": "T", "description": "D", "summary": "S",
            "agent_id": "a", "user_id": "u", "workspace_id": "default",
            "session_id": "s", "status": "completed", "outcome": "success",
            "topics": ["x"], "maturity_at_time": "student",
            "human_intervention_count": 0, "constitutional_score": None,
        }
        await svc._archive_to_lancedb(
            episode,
            {"presentation_summary": "chart showed revenue", "canvas_type": "sheets"},
        )
        _, kwargs = svc.lancedb.add_document.call_args
        assert kwargs["table_name"] == "episodes"
        assert kwargs["extra_columns"]["outcome"] == "success"
        assert "Canvas (sheets)" in kwargs["text"]

    async def test_archive_error_logged(self, svc):
        svc.lancedb.db = Mock()
        svc.lancedb.db.table_names.side_effect = RuntimeError("lancedb down")
        episode = {
            "id": "ep-1", "title": "T", "description": "D", "summary": "S",
            "agent_id": "a", "user_id": "u", "workspace_id": "default",
            "session_id": "s", "status": "completed", "outcome": "success",
            "topics": [], "maturity_at_time": None,
            "human_intervention_count": 0, "constitutional_score": None,
        }
        await svc._archive_to_lancedb(episode)

    async def test_archive_supervision_skipped_no_db(self, svc):
        await svc._archive_supervision_episode_to_lancedb(SimpleNamespace())

    async def test_archive_supervision_success(self, svc):
        svc.lancedb.db = Mock()
        svc.lancedb.db.table_names.return_value = []
        episode = SimpleNamespace(
            id="se-1", title="T", description="D", summary="S",
            agent_id="a", user_id="u", workspace_id="default",
            status="completed", topics=["t"], maturity_at_time="supervised",
            human_intervention_count=1, constitutional_score=None,
            supervisor_rating=4, intervention_count=1, intervention_types=["correct"],
        )
        await svc._archive_supervision_episode_to_lancedb(episode)
        _, kwargs = svc.lancedb.add_document.call_args
        assert kwargs["metadata"]["type"] == "supervision_episode"


class TestSegmentationCanvasContext:
    """Canvas context extraction (legacy + LLM paths)."""

    @pytest.fixture
    def svc(self):
        return EpisodeSegmentationService(db=Mock(), lancedb=Mock(db=None))

    def make_audit(self, details=None, action="present", canvas_type="sheets"):
        audit = Mock()
        audit.id = "ca-1"
        audit.details_json = details or {"canvas_type": canvas_type,
                                         "component": "pie_chart"}
        audit.action_type = action
        return audit

    def test_fetch_canvas_context_error_returns_empty(self, svc):
        svc.db.query.side_effect = RuntimeError("db down")
        assert svc._fetch_canvas_context("sess-1") == []

    def test_extract_canvas_context_full(self, svc):
        audit = self.make_audit(
            details={"canvas_type": "orchestration", "workflow_id": "wf-1",
                     "approval_status": "pending", "component_name": "workflow"}
        )
        ctx = svc._extract_canvas_context([audit])
        assert ctx["canvas_type"] == "orchestration"
        assert ctx["critical_data_points"]["workflow_id"] == "wf-1"
        assert "workflow" in ctx["presentation_summary"]

    def test_extract_canvas_context_interactions(self, svc):
        ctx = svc._extract_canvas_context([self.make_audit(action="submit")])
        assert ctx["user_interaction"] == "user submitted"
        ctx2 = svc._extract_canvas_context([self.make_audit(action="weird")])
        assert "user performed weird" in ctx2["user_interaction"]

    def test_extract_canvas_context_empty(self, svc):
        assert svc._extract_canvas_context([]) == {}

    def test_extract_canvas_context_error(self, svc):
        audit = Mock()
        audit.details_json = None
        audit.action_type = None
        audit.component_name = None
        svc._extract_canvas_context([audit])

    def test_fetch_feedback_context(self, svc):
        svc.db.query.return_value.filter.return_value.all.return_value = []
        assert svc._fetch_feedback_context("sess-1", "agent-1", []) == []
        assert svc._fetch_feedback_context("sess-1", "agent-1", ["e1"]) == []

    def test_calculate_feedback_score(self, svc):
        from core.models import AgentFeedback
        def fb(feedback_type=None, thumbs=None, rating=None):
            f = Mock(spec=AgentFeedback)
            f.feedback_type = feedback_type
            f.thumbs_up_down = thumbs
            f.rating = rating
            return f
        assert svc._calculate_feedback_score([]) is None
        assert svc._calculate_feedback_score([fb("thumbs_up")]) == 1.0
        assert svc._calculate_feedback_score([fb("thumbs_down")]) == -1.0
        assert svc._calculate_feedback_score([fb(None, True)]) == 1.0
        assert svc._calculate_feedback_score([fb(None, False)]) == -1.0
        assert svc._calculate_feedback_score([fb("rating", rating=4)]) == 0.5
        assert svc._calculate_feedback_score([fb("rating", rating=1)]) == -1.0
        assert svc._calculate_feedback_score([fb("other")]) is None

    def test_filter_canvas_context_detail_levels(self, svc):
        ctx = {
            "canvas_type": "sheets",
            "presentation_summary": "s",
            "critical_data_points": {"a": 1},
            "visual_elements": ["chart"],
        }
        s = svc._filter_canvas_context_detail(ctx, "summary")
        assert "visual_elements" not in s
        std = svc._filter_canvas_context_detail(ctx, "standard")
        assert "critical_data_points" in std
        full = svc._filter_canvas_context_detail(ctx, "full")
        assert full["visual_elements"] == ["chart"]
        unknown = svc._filter_canvas_context_detail(ctx, "bogus")
        assert "presentation_summary" in unknown
        assert svc._filter_canvas_context_detail({}, "summary") == {}

    async def test_extract_canvas_context_llm_verified(self, svc):
        audit = self.make_audit(
            details={"canvas_type": "sheets", "components": [{"type": "chart"}],
                     "revenue": 100, "workflow_id": "wf-1"}
        )
        svc.canvas_summary_service.generate_summary = AsyncMock(
            return_value="The canvas showed revenue and workflow progress."
        )
        ctx = await svc._extract_canvas_context_llm(audit, agent_task="task", outcome="success")
        assert ctx["summary_verification"] == "verified"
        assert ctx["outcome"] == "success"
        assert ctx["summary_source"] == "llm"
        assert ctx["visual_elements"] == ["chart"]
        assert ctx["critical_data_points"]["revenue"] == 100

    async def test_extract_canvas_context_llm_flagged(self, svc):
        audit = self.make_audit(details={"canvas_type": "generic"})
        svc.canvas_summary_service.generate_summary = AsyncMock(
            return_value="Summary referencing missing-workflow-987."
        )
        with patch.object(svc.canvas_summary_service, "_detect_hallucination",
                          return_value=True):
            ctx = await svc._extract_canvas_context_llm(audit)
        assert ctx["summary_verification"] == "flagged"

    async def test_extract_canvas_context_llm_low_quality(self, svc):
        audit = self.make_audit(details={"canvas_type": "generic"})
        svc.canvas_summary_service.generate_summary = AsyncMock(return_value="ok")
        with patch.object(svc.canvas_summary_service, "_detect_hallucination",
                          return_value=False), \
             patch.object(svc.canvas_summary_service, "_calculate_semantic_richness",
                          return_value=0.05):
            ctx = await svc._extract_canvas_context_llm(audit)
        assert ctx["summary_verification"] == "low_quality"

    async def test_extract_canvas_context_llm_exception_fallback(self, svc):
        audit = self.make_audit(details={"canvas_type": "sheets", "component": "x"})
        svc.canvas_summary_service.generate_summary = AsyncMock(
            side_effect=RuntimeError("llm down")
        )
        ctx = await svc._extract_canvas_context_llm(audit, outcome="failure")
        assert ctx["summary_verification"] == "unverified"
        assert ctx["summary_source"] == "metadata"
        assert ctx["outcome"] == "failure"

    async def test_extract_canvas_context_llm_checker_failure(self, svc):
        audit = self.make_audit(details={"canvas_type": "generic"})
        svc.canvas_summary_service.generate_summary = AsyncMock(
            return_value="Some summary text for checking."
        )
        with patch.object(svc.canvas_summary_service, "_detect_hallucination",
                          side_effect=RuntimeError("checker boom")), \
             patch.object(svc.canvas_summary_service, "_calculate_semantic_richness",
                          return_value=0.9):
            ctx = await svc._extract_canvas_context_llm(audit)
        # Checker failure falls back to a 0.0 richness reading -> low_quality.
        assert ctx["summary_verification"] == "low_quality"

    def test_extract_canvas_context_metadata(self, svc):
        audit = self.make_audit(details={"canvas_type": "sheets", "component": "x"})
        ctx = svc._extract_canvas_context_metadata(audit)
        assert ctx["summary_source"] == "metadata"


class TestSegmentationSupervision:
    """Supervision episode creation."""

    @pytest.fixture
    def svc(self):
        return EpisodeSegmentationService(db=Mock(), lancedb=Mock(db=None))

    def make_session(self, **over):
        s = Mock()
        s.id = "sup-1"
        s.agent_id = "agent-1"
        s.supervisor_id = "sup-user"
        s.agent_name = "Test Agent"
        s.workspace_id = "default"
        s.interventions = over.get("interventions", [
            {"type": "correct", "timestamp": "2026-01-01", "guidance": "do it"},
            {"type": "correct", "timestamp": "2026-01-01T00:01", "guidance": ""},
        ])
        s.intervention_count = over.get("intervention_count", 2)
        s.supervisor_rating = over.get("supervisor_rating", 4)
        s.supervisor_feedback = over.get("supervisor_feedback", "good")
        s.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        s.completed_at = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        s.duration_seconds = 60
        s.confidence_boost = 0.2
        return s

    async def test_create_supervision_episode_success(self, svc):
        session = self.make_session()
        execution = make_execution()
        with patch.object(svc, "_archive_supervision_episode_to_lancedb",
                          AsyncMock()):
            ep = await svc.create_supervision_episode(session, execution, svc.db)
        assert ep is not None
        assert ep.maturity_at_time == "supervised"
        assert ep.intervention_types == ["correct"]
        assert len(svc.db.add.call_args_list) == 4

    async def test_create_supervision_episode_exception(self, svc):
        session = self.make_session()
        execution = make_execution()
        svc.db.commit.side_effect = RuntimeError("db down")
        with patch.object(svc, "_archive_supervision_episode_to_lancedb",
                          AsyncMock()):
            ep = await svc.create_supervision_episode(session, execution, svc.db)
        assert ep is None
        svc.db.rollback.assert_called()

    def test_format_agent_actions(self, svc):
        execution = make_execution()
        out = svc._format_agent_actions([], execution)
        assert "Task: task" in out
        out2 = svc._format_agent_actions([], None)
        assert out2 == "No agent actions recorded"
        assert "Total interventions: 2" in svc._format_agent_actions(
            [{"type": "a"}, {"type": "b"}], execution
        )

    def test_format_interventions(self, svc):
        assert svc._format_interventions([]) == "No interventions"
        out = svc._format_interventions([
            {"type": "correct", "timestamp": "t1", "guidance": "fix"},
            {"type": "hint", "timestamp": "t2"},
        ])
        assert "[correct] at t1" in out
        assert "Guidance: fix" in out

    def test_format_supervision_outcome(self, svc):
        session = self.make_session(supervisor_feedback=None, duration_seconds=None)
        out = svc._format_supervision_outcome(session)
        assert "Supervisor Rating: 4/5" in out
        assert "Confidence Boost: +0.200" in out
        session2 = self.make_session()
        assert "Feedback: good" in svc._format_supervision_outcome(session2)

    def test_extract_supervision_topics(self, svc):
        session = self.make_session()
        execution = make_execution(task_description="kappa lambda topic")
        topics = svc._extract_supervision_topics(session, execution)
        assert topics[0] == "intervention_correct"
        session2 = self.make_session(interventions=[])
        topics2 = svc._extract_supervision_topics(session2, None)
        assert topics2 == ["agent"]

    def test_extract_supervision_entities(self, svc):
        session = self.make_session()
        entities = svc._extract_supervision_entities(session, None)
        assert "session:sup-1" in entities
        assert "agent:agent-1" in entities
        assert "supervisor:sup-user" in entities

    def test_calculate_supervision_importance(self, svc):
        assert svc._calculate_supervision_importance(
            self.make_session(supervisor_rating=5, intervention_count=0)
        ) == 1.0
        assert svc._calculate_supervision_importance(
            self.make_session(supervisor_rating=1, intervention_count=6)
        ) == 0.1
        assert svc._calculate_supervision_importance(
            self.make_session(supervisor_rating=None, intervention_count=1)
        ) == 0.6
        assert svc._calculate_supervision_importance(
            self.make_session(supervisor_rating=4, intervention_count=2)
        ) == 0.75


class TestSegmentationSkills:
    """Skill episode segmentation."""

    @pytest.fixture
    def svc(self):
        return EpisodeSegmentationService(db=Mock(), lancedb=Mock(db=None))

    def test_extract_skill_metadata(self, svc):
        meta = svc.extract_skill_metadata({
            "skill_name": "web", "error_type": None, "execution_time": 3.2,
            "input_summary": "input data",
        })
        assert meta["skill_name"] == "web"
        assert meta["execution_successful"] is True
        assert meta["input_hash"]
        meta2 = svc.extract_skill_metadata({"skill_name": "web"})
        assert meta2["execution_successful"] is True

    async def test_create_skill_episode_success_and_failure(self, svc):
        svc.db.refresh.return_value = Mock(id="seg-1")
        sid = await svc.create_skill_episode("agent-1", "web_search", {"q": "x"},
                                             "results", None, 0.5)
        assert sid is not None
        svc.db.commit.side_effect = RuntimeError("boom")
        assert await svc.create_skill_episode("agent-1", "web_search",
                                              {"q": "x"}, "r", RuntimeError("e"), 0.5) is None
        svc.db.rollback.assert_called()

    def test_summarize_skill_inputs(self, svc):
        assert svc._summarize_skill_inputs({}) == "{}"
        out = svc._summarize_skill_inputs({"big": "x" * 200, "small": "y"})
        assert "small" in out
        assert "..." in out

    def test_format_skill_content(self, svc):
        out = svc._format_skill_content("web", {"ok": 1}, None)
        assert "Status: Success" in out
        out2 = svc._format_skill_content("web", None, ValueError("bad input"))
        assert "Status: Failed" in out2
        assert "bad input" in out2


class TestSegmentationServiceInit:
    """Constructor precedence rules."""

    def test_llm_service_precedence(self):
        llm = Mock()
        svc = EpisodeSegmentationService(db=Mock(), llm_service=llm,
                                         byok_handler=Mock(), lancedb=Mock())
        assert svc.llm_service is llm
        assert svc.byok_handler is not None

    def test_byok_handler_as_llm(self):
        handler = Mock()
        svc = EpisodeSegmentationService(db=Mock(), byok_handler=handler,
                                         lancedb=Mock())
        assert svc.llm_service is handler

    def test_default_llm_service(self):
        with patch.object(EpisodeSegmentationService, "_init_default_llm_service",
                          return_value=Mock()) as init:
            svc = EpisodeSegmentationService(db=Mock(), lancedb=Mock())
            init.assert_called_once()
            assert svc.llm_service is not None
