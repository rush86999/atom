"""Coverage wave 25 — core/episode_service.py deterministic paths (TDD).

Drives the readiness/supervision/skill/proposal metrics, feedback CRUD,
canvas-action linking, cold-storage archival, skill usage stats and
graduation helpers with a mocked db — no LLM, no LanceDB, no spend.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.episode_service import (
    DetailLevel,
    EpisodeService,
    ReadinessResponse,
    ReadinessThresholds,
)


def make_episode(**kw):
    defaults = dict(
        id="ep-1", agent_id="ag-1", tenant_id="t-1", task_description="task",
        outcome="success", success=True, human_intervention_count=0,
        constitutional_score=0.9, confidence_score=0.8, step_efficiency=0.7,
        metadata_json={}, proposal_id=None, supervision_decision=None,
        supervisor_type=None, execution_followed_proposal=None,
        maturity_at_time="intern", started_at=datetime.now(timezone.utc) - timedelta(days=1),
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestReadinessMetrics:
    def test_empty_episodes(self):
        svc = EpisodeService(MagicMock())
        metrics = svc.calculate_readiness_metrics([])
        assert metrics["success_rate"] == 0.0
        assert metrics["total_interventions"] == 0

    def test_full_metrics_with_none_scores(self):
        svc = EpisodeService(MagicMock())
        episodes = [
            make_episode(success=True, human_intervention_count=0,
                         constitutional_score=None, confidence_score=None,
                         step_efficiency=None, outcome="success"),
            make_episode(success=False, human_intervention_count=2,
                         constitutional_score=0.5, confidence_score=0.4,
                         step_efficiency=0.8, outcome="failure"),
        ]
        metrics = svc.calculate_readiness_metrics(episodes)
        assert metrics["success_rate"] == 0.5
        assert metrics["zero_intervention_ratio"] == 0.5
        # Recorded-only averaging (maturity-adjusted readiness): None means
        # "no credit recorded", so the averages cover recorded episodes
        # only and the counts expose how many that was — previously None
        # averaged in as 0.0 and made tier thresholds unreachable.
        assert metrics["avg_constitutional_score"] == 0.5  # over 1 recorded
        assert metrics["constitutional_recorded"] == 1
        assert metrics["avg_confidence_score"] == 0.4
        assert metrics["confidence_recorded"] == 1
        assert metrics["episodes_by_outcome"] == {"success": 1, "failure": 1}
        assert metrics["total_interventions"] == 2
        assert metrics["avg_step_efficiency"] == 0.8  # only non-None counted


class TestSupervisionMetrics:
    def test_empty(self):
        svc = EpisodeService(MagicMock())
        metrics = svc.calculate_supervision_metrics([])
        assert metrics["total_proposals"] == 0

    def test_no_proposal_episodes(self):
        svc = EpisodeService(MagicMock())
        metrics = svc.calculate_supervision_metrics([make_episode()])
        assert metrics["total_proposals"] == 0

    def test_mixed_decisions(self):
        svc = EpisodeService(MagicMock())
        episodes = [
            make_episode(proposal_id="p1", supervision_decision="approved",
                         supervisor_type="user", execution_followed_proposal=True),
            make_episode(proposal_id="p2", supervision_decision="approved",
                         supervisor_type="user", execution_followed_proposal=False),
            make_episode(proposal_id="p3", supervision_decision="rejected",
                         supervisor_type="autonomous_agent", execution_followed_proposal=None),
            make_episode(proposal_id="p4", supervision_decision="approved",
                         supervisor_type="autonomous_agent", execution_followed_proposal=True),
        ]
        metrics = svc.calculate_supervision_metrics(episodes)
        assert metrics["total_proposals"] == 4
        assert metrics["approved_proposals"] == 3
        assert metrics["rejected_proposals"] == 1
        assert metrics["approval_rate"] == 0.75
        assert metrics["execution_success_rate"] == round(2 / 3, 4)
        assert metrics["supervisor_type_breakdown"] == {"user": 2, "autonomous_agent": 2}
        assert metrics["supervision_success_rate"] == round(0.75 * 0.6 + (2 / 3) * 0.4, 4)


class TestSkillAndProposalMetrics:
    def test_skill_diversity(self):
        svc = EpisodeService(MagicMock())
        summaries = [
            svc.SkillUsageSummary("s1", "Alpha", 5, 1.0, None),
            svc.SkillUsageSummary("s2", "Beta", 3, 0.5, None),
        ]
        with patch.object(svc, "get_agent_skill_usage", return_value=summaries):
            metrics = svc.calculate_skill_diversity_metrics("ag-1", "t-1")
        assert metrics["unique_skill_count"] == 2
        assert metrics["skill_diversity_score"] == 0.2
        assert metrics["avg_skill_success_rate"] == 0.75
        assert metrics["total_skill_executions"] == 8
        assert len(metrics["top_skills"]) == 2

    def test_skill_diversity_empty(self):
        svc = EpisodeService(MagicMock())
        with patch.object(svc, "get_agent_skill_usage", return_value=[]):
            metrics = svc.calculate_skill_diversity_metrics("ag-1", "t-1")
        assert metrics["skill_diversity_score"] == 0.0
        assert metrics["avg_skill_success_rate"] == 0.0

    def test_proposal_quality_empty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = EpisodeService(db)
        metrics = svc.calculate_proposal_quality_metrics("ag-1", "t-1")
        assert metrics["proposal_episode_count"] == 0
        assert metrics["proposal_quality_score"] == 0.0

    def test_proposal_quality_with_scores(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            make_episode(metadata_json={"quality_score": 0.9}),
            make_episode(metadata_json={"quality_score": 0.6}),
            make_episode(metadata_json={"quality_score": 0.0}),
        ]
        svc = EpisodeService(db)
        metrics = svc.calculate_proposal_quality_metrics("ag-1", "t-1")
        assert metrics["proposal_episode_count"] == 3
        assert metrics["avg_proposal_quality"] == 0.75
        assert metrics["high_quality_proposal_count"] == 1
        assert metrics["proposal_quality_score"] == round(min(0.75 * 1.2, 1.0), 4)


class TestGetAgentEpisodes:
    def test_all_filters_applied(self):
        db = MagicMock()
        query = db.query.return_value.filter.return_value
        svc = EpisodeService(db)
        episodes = svc.get_agent_episodes(
            "ag-1", "t-1", limit=10, outcome_filter="success",
            start_date=datetime(2026, 1, 1), end_date=datetime(2026, 2, 1))
        assert episodes == query.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value

    def test_no_filters(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = ["a"]
        svc = EpisodeService(db)
        episodes = svc.get_agent_episodes("ag-1", "t-1")
        assert episodes == ["a"]


class TestArchiveToColdStorage:
    def test_episode_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        assert asyncio.run(svc.archive_episode_to_cold_storage("ghost")) is False

    def test_embedding_failure_uses_zero_vector(self):
        db = MagicMock()
        episode = make_episode(tenant_id="t-1")
        db.query.return_value.filter.return_value.first.return_value = episode
        svc = EpisodeService(db)
        emb = MagicMock()
        emb.generate_embedding = AsyncMock(side_effect=RuntimeError("emb down"))
        svc.embedding_service = emb
        lancedb = MagicMock()
        lancedb.add_episode.return_value = True
        with patch.object(svc, "_get_lancedb", return_value=lancedb):
            result = asyncio.run(svc.archive_episode_to_cold_storage("ep-1"))
        assert result is True
        call = lancedb.add_episode.call_args
        embedding = call.args[1]
        assert all(v == 0.0 for v in embedding)

    def test_lancedb_unavailable(self):
        db = MagicMock()
        episode = make_episode()
        db.query.return_value.filter.return_value.first.return_value = episode
        svc = EpisodeService(db)
        svc.embedding_service = MagicMock()
        svc.embedding_service.generate_embedding = AsyncMock(return_value=[0.1])
        with patch.object(svc, "_get_lancedb", return_value=None):
            result = asyncio.run(svc.archive_episode_to_cold_storage("ep-1"))
        assert result is False

    def test_success_with_billing(self):
        db = MagicMock()
        episode = make_episode(tenant_id="t-1")
        db.query.return_value.filter.return_value.first.return_value = episode
        svc = EpisodeService(db)
        svc.embedding_service = MagicMock()
        svc.embedding_service.generate_embedding = AsyncMock(return_value=[0.1])
        lancedb = MagicMock()
        lancedb.add_episode.return_value = True
        with patch.object(svc, "_get_lancedb", return_value=lancedb), \
             patch("core.usage_tracking_service.UsageTrackingService") as uts:
            result = asyncio.run(svc.archive_episode_to_cold_storage("ep-1"))
        assert result is True
        uts.assert_called_once()

    def test_add_episode_failure(self):
        db = MagicMock()
        episode = make_episode()
        db.query.return_value.filter.return_value.first.return_value = episode
        svc = EpisodeService(db)
        svc.embedding_service = MagicMock()
        svc.embedding_service.generate_embedding = AsyncMock(return_value=[0.1])
        lancedb = MagicMock()
        lancedb.add_episode.return_value = False
        with patch.object(svc, "_get_lancedb", return_value=lancedb):
            result = asyncio.run(svc.archive_episode_to_cold_storage("ep-1"))
        assert result is False

    def test_outer_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = EpisodeService(db)
        assert asyncio.run(svc.archive_episode_to_cold_storage("ep-1")) is False


class TestConstitutionalAndEfficiency:
    def test_constitutional_no_violations(self):
        svc = EpisodeService(MagicMock())
        assert svc._calculate_constitutional_score([]) == 1.0

    def test_constitutional_severities(self):
        svc = EpisodeService(MagicMock())
        violations = [
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "low"},
            {"severity": "unknown"},  # defaults to low weight
        ]
        score = svc._calculate_constitutional_score(violations)
        # penalty 2.3 is capped at 1.0 → score 0.0
        assert score == 0.0

    def test_constitutional_capped_at_zero(self):
        svc = EpisodeService(MagicMock())
        score = svc._calculate_constitutional_score([{"severity": "critical"}] * 5)
        assert score == 0.0

    def test_step_efficiency_no_steps(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc = EpisodeService(db)
        assert svc._calculate_step_efficiency("ex-1") == 1.0

    def test_step_efficiency_with_steps(self):
        db = MagicMock()
        steps = [
            SimpleNamespace(step_type="thought"),
            SimpleNamespace(step_type="action"),
            SimpleNamespace(step_type="observation"),
        ]
        db.query.return_value.filter.return_value.all.return_value = steps
        svc = EpisodeService(db)
        assert svc._calculate_step_efficiency("ex-1") == 1.0

    def test_get_next_level(self):
        from core.models import AgentStatus
        svc = EpisodeService(MagicMock())
        assert svc._get_next_level(AgentStatus.STUDENT.value) == AgentStatus.INTERN.value
        assert svc._get_next_level(AgentStatus.INTERN.value) == AgentStatus.SUPERVISED.value
        assert svc._get_next_level(AgentStatus.SUPERVISED.value) == AgentStatus.AUTONOMOUS.value
        assert svc._get_next_level(AgentStatus.AUTONOMOUS.value) == AgentStatus.AUTONOMOUS.value
        assert svc._get_next_level("bogus") == AgentStatus.INTERN.value

    def test_threshold_and_min_episodes(self):
        from core.models import AgentStatus
        svc = EpisodeService(MagicMock())
        assert svc._get_threshold_for_level(AgentStatus.INTERN.value) == ReadinessThresholds.STUDENT_TO_INTERN["overall"]
        assert svc._get_threshold_for_level(AgentStatus.SUPERVISED.value) == ReadinessThresholds.INTERN_TO_SUPERVISED["overall"]
        assert svc._get_threshold_for_level(AgentStatus.AUTONOMOUS.value) == ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS["overall"]
        assert svc._get_threshold_for_level("bogus") == 0.70
        assert svc._get_min_episodes_for_level(AgentStatus.INTERN.value) == 10
        assert svc._get_min_episodes_for_level(AgentStatus.SUPERVISED.value) == 25
        assert svc._get_min_episodes_for_level(AgentStatus.AUTONOMOUS.value) == 50
        assert svc._get_min_episodes_for_level("bogus") == 10


class TestEpisodeFeedback:
    def test_update_feedback_episode_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        with pytest.raises(ValueError, match="not found"):
            svc.update_episode_feedback("ghost", 0.9)

    def test_update_feedback_success(self):
        db = MagicMock()
        episode = make_episode(metadata_json={})
        db.query.return_value.filter.return_value.first.return_value = episode
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.rollback = MagicMock()
        feedback = SimpleNamespace(id="fb-1")
        db.add.side_effect = lambda f: None
        svc = EpisodeService(db)
        with patch("core.models.EpisodeFeedback", lambda **kw: feedback), \
             patch.object(svc, "_sync_feedback_to_lancedb", new=AsyncMock()):
            fb_id = svc.update_episode_feedback(
                "ep-1", 0.95, feedback_notes="x" * 600,
                feedback_category="accuracy", provider_id="u1",
                capability_domain="data_analysis", capability_name="analysis")
        assert fb_id == "fb-1"
        assert episode.metadata_json["feedback_id"] == "fb-1"

    def test_update_feedback_capability_tracking_failure_tolerated(self):
        db = MagicMock()
        episode = make_episode(metadata_json={})
        db.query.return_value.filter.return_value.first.return_value = episode
        db.commit = MagicMock()
        db.refresh = MagicMock()
        feedback = SimpleNamespace(id="fb-2")
        svc = EpisodeService(db)
        with patch("core.models.EpisodeFeedback", lambda **kw: feedback), \
             patch("core.capability_graduation_service.CapabilityGraduationService",
                   side_effect=RuntimeError("grad down")), \
             patch.object(svc, "_sync_feedback_to_lancedb", new=AsyncMock()):
            fb_id = svc.update_episode_feedback(
                "ep-1", 0.5, capability_domain="d", capability_name="n")
        assert fb_id == "fb-2"

    def test_get_episode_feedback(self):
        db = MagicMock()
        rec = SimpleNamespace(
            id="fb-1", feedback_score=0.8, feedback_notes="notes",
            feedback_category="accuracy", provider_id="u1", provider_type="human",
            provided_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rec]
        svc = EpisodeService(db)
        result = svc.get_episode_feedback("ep-1")
        assert result[0]["id"] == "fb-1"
        assert result[0]["provided_at"].endswith("+00:00")

    def test_get_episode_feedback_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = EpisodeService(db)
        assert svc.get_episode_feedback("ep-1") == []


class TestDomainFeedbackMetrics:
    def test_no_feedback(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        svc = EpisodeService(db)
        result = svc.get_domain_feedback_metrics("t-1", "data_analysis")
        assert result["feedback_count"] == 0
        assert result["trend"] == "no_data"

    def test_improving_trend_and_capability_grouping(self):
        db = MagicMock()
        def _mk(score, cap=None):
            return SimpleNamespace(
                feedback_score=score, capability_domain="data_analysis",
                capability_name=cap, provided_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _mk(0.2, "analysis"), _mk(0.3, "analysis"), _mk(0.9), _mk(0.95),
        ]
        svc = EpisodeService(db)
        result = svc.get_domain_feedback_metrics("t-1", "data_analysis", days=30)
        assert result["feedback_count"] == 4
        assert result["trend"] == "improving"
        assert result["by_capability"]["analysis"]["count"] == 2
        assert result["positive_count"] == 2
        assert result["negative_count"] == 0
        assert result["neutral_count"] == 2

    def test_declining_trend(self):
        db = MagicMock()
        def _mk(score):
            return SimpleNamespace(
                feedback_score=score, capability_domain="code",
                capability_name=None, provided_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _mk(0.9), _mk(0.8), _mk(0.1),
        ]
        svc = EpisodeService(db)
        result = svc.get_domain_feedback_metrics("t-1", "code")
        assert result["trend"] == "declining"

    def test_stable_trend(self):
        db = MagicMock()
        def _mk(score):
            return SimpleNamespace(
                feedback_score=score, capability_domain="code",
                capability_name=None, provided_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _mk(0.5), _mk(0.55),
        ]
        svc = EpisodeService(db)
        result = svc.get_domain_feedback_metrics("t-1", "code")
        assert result["trend"] == "stable"

    def test_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = EpisodeService(db)
        result = svc.get_domain_feedback_metrics("t-1", "code")
        assert result["feedback_count"] == 0
        assert "error" in result

    def test_insufficient_data_trend(self):
        db = MagicMock()
        rec = SimpleNamespace(
            feedback_score=0.5, capability_domain="d", capability_name=None,
            provided_at=datetime.now(timezone.utc))
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [rec]
        svc = EpisodeService(db)
        result = svc.get_domain_feedback_metrics("t-1", "d")
        assert result["trend"] == "insufficient_data"


class TestCanvasActions:
    def test_episode_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        assert svc.get_canvas_actions_for_episode("ghost") == []

    def test_no_action_ids(self):
        db = MagicMock()
        episode = make_episode(metadata_json={})
        db.query.return_value.filter.return_value.first.return_value = episode
        svc = EpisodeService(db)
        assert svc.get_canvas_actions_for_episode("ep-1") == []

    def test_with_actions(self):
        db = MagicMock()
        episode = make_episode(metadata_json={"canvas_action_ids": ["c1", "c2"]})
        db.query.return_value.filter.return_value.first.return_value = episode
        action = SimpleNamespace(
            id="c1", action_type="submit", canvas_id="cv-1", user_id="u1",
            details_json={"form": 1}, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        db.query.return_value.filter.return_value.all.return_value = [action]
        svc = EpisodeService(db)
        result = svc.get_canvas_actions_for_episode("ep-1")
        assert result[0]["action_type"] == "submit"
        assert result[0]["details"] == {"form": 1}

    def test_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = EpisodeService(db)
        assert svc.get_canvas_actions_for_episode("ep-1") == []

    def test_link_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        assert asyncio.run(svc.link_canvas_actions_to_episode("ghost", ["c1"])) is False

    def test_link_success(self):
        db = MagicMock()
        episode = make_episode(metadata_json={})
        db.query.return_value.filter.return_value.first.return_value = episode
        db.commit = MagicMock()
        svc = EpisodeService(db)
        result = asyncio.run(svc.link_canvas_actions_to_episode("ep-1", ["c1", "c2"]))
        assert result is True
        assert episode.metadata_json["canvas_action_ids"] == ["c1", "c2"]

    def test_link_exception(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = RuntimeError("db down")
        db.rollback = MagicMock()
        svc = EpisodeService(db)
        assert asyncio.run(svc.link_canvas_actions_to_episode("ep-1", ["c1"])) is False


class TestSkillStats:
    def test_empty_stats_with_skill_name(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        skill = SimpleNamespace(name="web_search")
        db.query.return_value.filter.return_value.first.return_value = skill
        svc = EpisodeService(db)
        stats = svc.get_skill_performance_stats("ag-1", "t-1", "skill-1")
        assert stats.total_executions == 0
        assert stats.skill_name == "web_search"
        assert stats.success_rate == 0.0

    def test_empty_stats_no_skill(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        stats = svc.get_skill_performance_stats("ag-1", "t-1", "skill-x")
        assert stats.skill_name is None

    def test_stats_with_episodes(self):
        db = MagicMock()
        episodes = [
            make_episode(success=True, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                         completed_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)),
            make_episode(success=False, started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                         completed_at=datetime(2026, 1, 2, 0, 2, tzinfo=timezone.utc)),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        skill = SimpleNamespace(name="web_search")
        db.query.return_value.filter.return_value.first.return_value = skill
        svc = EpisodeService(db)
        stats = svc.get_skill_performance_stats("ag-1", "t-1", "skill-1")
        assert stats.total_executions == 2
        assert stats.successful_executions == 1
        assert stats.success_rate == 0.5
        assert stats.avg_execution_time == 90.0
        assert stats.last_executed_at is not None

    def test_skill_usage_grouping(self):
        db = MagicMock()
        episodes = [
            make_episode(metadata_json={"skill_type": "openclaw", "skill_id": "s1"}, success=True),
            make_episode(metadata_json={"skill_type": "openclaw", "skill_id": "s1"}, success=False),
            make_episode(metadata_json={"skill_type": "openclaw", "skill_id": "s2"}, success=True),
            make_episode(metadata_json={"skill_type": "openclaw"}, success=True),  # no skill_id → skipped
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        skill = SimpleNamespace(name="Skill One")
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = skill
        svc = EpisodeService(db)
        summaries = svc.get_agent_skill_usage("ag-1", "t-1")
        assert len(summaries) == 2
        assert summaries[0].skill_id == "s1"  # 2 executions sorts first
        assert summaries[0].execution_count == 2
        assert summaries[0].success_rate == 0.5

    def test_skill_usage_count(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 7
        svc = EpisodeService(db)
        assert svc.get_skill_usage_count("ag-1", "t-1") == 7

    def test_required_skills(self):
        svc = EpisodeService(MagicMock())
        assert svc.get_required_skills_for_level("student") == 1
        assert svc.get_required_skills_for_level("intern") == 3
        assert svc.get_required_skills_for_level("supervised") == 5
        assert svc.get_required_skills_for_level("autonomous") == 10
        assert svc.get_required_skills_for_level("bogus") == 1

    def test_assess_skill_mastery(self):
        db = MagicMock()
        svc = EpisodeService(db)
        summaries = [
            svc.SkillUsageSummary("s1", "A", 4, 1.0, None),
            svc.SkillUsageSummary("s2", "B", 2, 0.5, None),
            svc.SkillUsageSummary("s3", "C", 1, 1.0, None),
        ]
        with patch.object(svc, "get_agent_skill_usage", return_value=summaries):
            result = svc.assess_skill_mastery("ag-1", "t-1", "supervised")
        assert result.required_skills_for_level == 5
        assert result.skill_diversity == round(3 / 5, 4)
        assert result.skill_execution_count == 7
        assert result.skills_used == {"s1", "s2", "s3"}
        assert result.mastery_score == round((3 / 5) * 0.6 + (2.5 / 3) * 0.4, 4)

    def test_assess_skill_mastery_empty(self):
        db = MagicMock()
        svc = EpisodeService(db)
        with patch.object(svc, "get_agent_skill_usage", return_value=[]):
            result = svc.assess_skill_mastery("ag-1", "t-1", "intern")
        assert result.skill_diversity == 0.0
        assert result.skill_success_rate == 0.0
        assert result.mastery_score == 0.0


class TestProposalEpisodesForLearning:
    def test_with_capability_tags(self):
        db = MagicMock()
        episodes = [
            make_episode(id="e1", metadata_json={
                "episode_type": "meta_agent_proposal", "quality_score": 0.9,
                "proposal_id": "p1", "capability_tags": ["code_execution"],
                "teaching_value": "high", "meta_agent_guidance": "g",
                "quality_breakdown": {"a": 1}}),
            make_episode(id="e2", metadata_json={
                "episode_type": "meta_agent_proposal", "quality_score": 0.8,
                "proposal_id": "p2", "capability_tags": ["data_analysis"]}),
        ]
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        svc = EpisodeService(db)
        result = svc.get_proposal_episodes_for_learning(
            "t-1", "ag-1", capability_tags=["code_execution"], limit=5)
        assert len(result) == 1
        assert result[0]["episode_id"] == "e1"
        assert result[0]["quality_score"] == 0.9
        assert result[0]["teaching_value"] == "high"

    def test_no_capability_tags(self):
        db = MagicMock()
        episodes = [make_episode(id="e1", metadata_json={
            "episode_type": "meta_agent_proposal", "quality_score": 0.85})]
        db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        svc = EpisodeService(db)
        result = svc.get_proposal_episodes_for_learning("t-1", "ag-1")
        assert len(result) == 1
        assert result[0]["created_at"] is not None


class TestGraduationReadiness:
    def test_agent_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = EpisodeService(db)
        with pytest.raises(ValueError, match="not found"):
            svc.get_graduation_readiness("ag-1", "t-1")

    def test_no_episodes(self):
        db = MagicMock()
        agent = SimpleNamespace(status="intern", confidence_score=0.5)
        db.query.return_value.filter.return_value.first.return_value = agent
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        svc = EpisodeService(db)
        result = svc.get_graduation_readiness("ag-1", "t-1")
        assert result.readiness_score == 0.0
        assert result.threshold_met is False
        assert result.episodes_analyzed == 0
        assert result.breakdown == {"reason": "No episodes found"}

    def test_full_path_with_override(self):
        db = MagicMock()
        agent = SimpleNamespace(status="intern", confidence_score=0.8)
        db.query.return_value.filter.return_value.first.return_value = agent
        episodes = [
            make_episode(success=True, human_intervention_count=0,
                         constitutional_score=0.9, confidence_score=0.9,
                         outcome="success"),
            make_episode(success=True, human_intervention_count=0,
                         constitutional_score=0.8, confidence_score=0.7,
                         outcome="success"),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        svc = EpisodeService(db)
        with patch.object(svc, "calculate_supervision_metrics",
                          return_value={"supervision_success_rate": 0.9}), \
             patch.object(svc, "calculate_skill_diversity_metrics",
                          return_value={"skill_diversity_score": 0.5}), \
             patch.object(svc, "calculate_proposal_quality_metrics",
                          return_value={"proposal_quality_score": 0.8}):
            result = svc.get_graduation_readiness("ag-1", "t-1", target_level="intern",
                                                  min_episodes_override=1)
        assert result.episodes_analyzed == 2
        assert result.current_level == "intern"
        assert isinstance(result.readiness_score, float)
        assert result.breakdown["target_level"] == "intern"
        assert "skill_metrics" in result.breakdown
        assert "proposal_quality_metrics" in result.breakdown

    def test_to_dict(self):
        response = ReadinessResponse(
            agent_id="ag-1", current_level="intern", readiness_score=0.7,
            threshold_met=True, zero_intervention_ratio=0.8,
            avg_constitutional_score=0.9, avg_confidence_score=0.8,
            success_rate=1.0, episodes_analyzed=10,
            supervision_success_rate=0.9, breakdown={"k": "v"})
        d = response.to_dict()
        assert d["agent_id"] == "ag-1"
        assert d["threshold_met"] is True
        assert d["episodes_analyzed"] == 10


class TestSyncFeedbackToLancedb:
    async def test_success(self):
        db = MagicMock()
        svc = EpisodeService(db)
        episode = make_episode(metadata_json={"learnings": "l1"})
        feedback = SimpleNamespace(feedback_notes="good")
        world = MagicMock()
        world.record_episode = AsyncMock(return_value=True)
        with patch("core.agent_world_model.WorldModelService", return_value=world):
            result = await svc._sync_feedback_to_lancedb(episode, feedback)
        assert result is True
        recorded = world.record_episode.call_args.kwargs
        assert "[Feedback: good]" in recorded["learnings"]

    async def test_failure(self):
        db = MagicMock()
        svc = EpisodeService(db)
        episode = make_episode(metadata_json={})
        feedback = SimpleNamespace(feedback_notes=None)
        with patch("core.agent_world_model.WorldModelService",
                   side_effect=RuntimeError("wm down")):
            result = await svc._sync_feedback_to_lancedb(episode, feedback)
        assert result is False


class TestEmbeddingDimension:
    def test_dimension_prefers_getter(self):
        svc = EpisodeService(MagicMock())
        svc.embedding_service = MagicMock()
        svc.embedding_service.get_embedding_dimension.return_value = 512
        assert svc._get_embedding_dimension() == 512

    def test_dimension_model_based(self):
        svc = EpisodeService(MagicMock())
        svc.embedding_service = MagicMock()
        svc.embedding_service.get_embedding_dimension.side_effect = TypeError
        svc.embedding_service.model = "text-embedding-3-small"
        assert svc._get_embedding_dimension() == 1536
        svc.embedding_service.model = "bge-large"
        svc.embedding_service.provider = "cohere"
        assert svc._get_embedding_dimension() == 1024
        svc.embedding_service.model = "bge-small"
        svc.embedding_service.provider = "fastembed"
        assert svc._get_embedding_dimension() == 384
