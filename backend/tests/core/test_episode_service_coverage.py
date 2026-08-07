"""
Coverage + bug-hunt tests for core/episode_service.py.

Focuses on the public & helper methods that can be exercised without a live
PostgreSQL/pgvector/LanceDB backend:
  - readiness score calculation & threshold gating
  - readiness / supervision / skill-diversity / proposal-quality metrics
  - constitutional score & step efficiency helpers
  - level helpers (_get_next_level, thresholds, min episodes)
  - episode feedback CRUD + domain feedback metrics
  - canvas action linking / retrieval
  - skill performance stats / usage / mastery
  - get_agent_episodes query filtering

The DB session is mocked so we never touch a real DB. Pure-Python dataclasses
and lightweight model stand-ins are used so the metrics math is exercised
exactly as production runs it.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core import episode_service as es_mod
from core.episode_service import (
    DetailLevel,
    EpisodeService,
    PROGRESSIVE_QUERIES,
    ReadinessThresholds,
)
from core.models import AgentStatus, EpisodeOutcome


# ---------------------------------------------------------------------------
# Lightweight stand-ins for ORM rows. Namedtuple fields match the attribute
# access used inside episode_service.py.
# ---------------------------------------------------------------------------

class Episode:
    """Mutable stand-in for AgentEpisode (some code paths write to .metadata_json)."""

    def __init__(self, **over):
        base = dict(
            id=str(uuid.uuid4()),
            success=True,
            human_intervention_count=0,
            constitutional_score=1.0,
            confidence_score=0.5,
            outcome="success",
            step_efficiency=1.0,
            proposal_id=None,
            supervision_decision=None,
            execution_followed_proposal=None,
            supervisor_type=None,
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc),
            task_description="do thing",
            metadata_json={},
            tenant_id="t1",
            agent_id="a1",
            maturity_at_time="student",
        )
        base.update(over)
        for k, v in base.items():
            setattr(self, k, v)


def make_episode(**over) -> Episode:
    return Episode(**over)


def make_agent(status="student", confidence_score=0.5):
    agent = Mock()
    agent.id = "a1"
    agent.tenant_id = "t1"
    agent.status = status
    agent.confidence_score = confidence_score
    return agent


class FakeQuery:
    """A tiny query-builder double that supports .filter/.order_by/.limit/.count/.all.

    `order_by` actually sorts the underlying list when given an InstrumentedAttribute,
    so tests that depend on ordering (e.g. trend analysis) are exercised faithfully."""

    def __init__(self, items):
        self._items = list(items)

    def filter(self, *args, **kwargs):
        # Filters are not evaluated here; tests control the underlying list.
        return self

    def order_by(self, *args, **kwargs):
        # Sort by the requested column when possible. Handles both bare
        # columns (key) and ascending/descending clauses (.element.key).
        for arg in args:
            key = getattr(arg, "key", None)
            if key is None:
                element = getattr(arg, "element", None)
                key = getattr(element, "key", None)
            if key:
                try:
                    self._items.sort(key=lambda o: getattr(o, key))
                except (AttributeError, TypeError):
                    pass
        return self

    def limit(self, n):
        return self

    def count(self):
        return len(self._items)

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class FakeDB:
    """Mock session whose .query(model) returns a FakeQuery over `data[model]`."""

    def __init__(self):
        self.data = {}  # model_name -> list
        self.added = []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        return FakeQuery(self.data.get(name, []))

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        return None

    def flush(self):
        return None


@pytest.fixture
def service():
    db = FakeDB()
    emb = Mock()
    emb.get_embedding_dimension.return_value = 8
    svc = EpisodeService(db, embedding_service=emb)
    return svc


# ===========================================================================
# _calculate_constitutional_score
# ===========================================================================


class TestConstitutionalScore:
    def test_no_violations_returns_perfect(self, service):
        assert service._calculate_constitutional_score([]) == 1.0

    def test_none_violations_returns_perfect(self, service):
        assert service._calculate_constitutional_score(None) == 1.0

    def test_low_severity_subtracts_0_1(self, service):
        score = service._calculate_constitutional_score([{"severity": "low"}])
        assert score == pytest.approx(0.9)

    def test_critical_caps_penalty_at_1(self, service):
        # Two criticals = 2.0 penalty -> capped -> score 0.0
        score = service._calculate_constitutional_score(
            [{"severity": "critical"}, {"severity": "critical"}]
        )
        assert score == 0.0

    def test_unknown_severity_defaults_to_low_weight(self, service):
        score = service._calculate_constitutional_score([{"severity": "banana"}])
        assert score == pytest.approx(0.9)

    def test_severity_is_case_insensitive(self, service):
        score = service._calculate_constitutional_score([{"severity": "HIGH"}])
        assert score == pytest.approx(0.3)

    def test_mixed_severities(self, service):
        # 1.0 + 0.7 + 0.4 + 0.1 = 2.2 -> capped at 1.0 -> score 0.0
        score = service._calculate_constitutional_score(
            [
                {"severity": "critical"},
                {"severity": "high"},
                {"severity": "medium"},
                {"severity": "low"},
            ]
        )
        assert score == 0.0


# ===========================================================================
# Level / threshold helpers
# ===========================================================================


class TestLevelHelpers:
    def test_next_level_progression(self, service):
        assert service._get_next_level(AgentStatus.STUDENT.value) == AgentStatus.INTERN.value
        assert service._get_next_level(AgentStatus.INTERN.value) == AgentStatus.SUPERVISED.value
        assert (
            service._get_next_level(AgentStatus.SUPERVISED.value)
            == AgentStatus.AUTONOMOUS.value
        )

    def test_next_level_max_stays_autonomous(self, service):
        assert service._get_next_level(AgentStatus.AUTONOMOUS.value) == AgentStatus.AUTONOMOUS.value

    def test_next_level_unknown_defaults_to_intern(self, service):
        assert service._get_next_level("unknown") == AgentStatus.INTERN.value

    def test_thresholds_for_each_level(self, service):
        assert service._get_threshold_for_level("intern") == ReadinessThresholds.STUDENT_TO_INTERN["overall"]
        assert service._get_threshold_for_level("supervised") == ReadinessThresholds.INTERN_TO_SUPERVISED["overall"]
        assert service._get_threshold_for_level("autonomous") == ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS["overall"]

    def test_threshold_unknown_defaults_0_7(self, service):
        assert service._get_threshold_for_level("nope") == 0.70

    def test_min_episodes_for_each_level(self, service):
        assert service._get_min_episodes_for_level("intern") == 10
        assert service._get_min_episodes_for_level("supervised") == 25
        assert service._get_min_episodes_for_level("autonomous") == 50

    def test_min_episodes_unknown_defaults_10(self, service):
        assert service._get_min_episodes_for_level("nope") == 10

    def test_required_skills_for_level_is_case_insensitive(self, service):
        assert service.get_required_skills_for_level("Autonomous") == 10
        assert service.get_required_skills_for_level("SUPERVISED") == 5
        assert service.get_required_skills_for_level("nope") == 1


# ===========================================================================
# calculate_readiness_metrics
# ===========================================================================


class TestReadinessMetrics:
    def test_empty_episodes_returns_zeros(self, service):
        m = service.calculate_readiness_metrics([])
        assert m["success_rate"] == 0.0
        assert m["zero_intervention_ratio"] == 0.0
        assert m["avg_constitutional_score"] == 0.0
        assert m["avg_confidence_score"] == 0.0
        assert m["avg_step_efficiency"] == 0.0
        assert m["episodes_by_outcome"] == {}
        assert m["total_interventions"] == 0

    def test_success_rate_calculation(self, service):
        eps = [
            make_episode(success=True),
            make_episode(success=True),
            make_episode(success=False),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["success_rate"] == pytest.approx(2 / 3)

    def test_zero_intervention_ratio(self, service):
        eps = [
            make_episode(human_intervention_count=0),
            make_episode(human_intervention_count=0),
            make_episode(human_intervention_count=2),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["zero_intervention_ratio"] == pytest.approx(2 / 3)

    def test_total_interventions_sums_counts(self, service):
        eps = [
            make_episode(human_intervention_count=0),
            make_episode(human_intervention_count=3),
            make_episode(human_intervention_count=1),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["total_interventions"] == 4

    def test_episodes_by_outcome(self, service):
        eps = [
            make_episode(outcome="success"),
            make_episode(outcome="success"),
            make_episode(outcome="failure"),
            make_episode(outcome="partial"),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["episodes_by_outcome"] == {"success": 2, "failure": 1, "partial": 1}

    def test_avg_step_efficiency_skips_none(self, service):
        # None step_efficiency entries must NOT be treated as 0
        eps = [
            make_episode(step_efficiency=None),
            make_episode(step_efficiency=0.8),
            make_episode(step_efficiency=0.6),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["avg_step_efficiency"] == pytest.approx(0.7)

    def test_avg_step_efficiency_all_none_is_zero(self, service):
        eps = [make_episode(step_efficiency=None), make_episode(step_efficiency=None)]
        m = service.calculate_readiness_metrics(eps)
        assert m["avg_step_efficiency"] == 0.0


# ===========================================================================
# calculate_supervision_metrics
# ===========================================================================


class TestSupervisionMetrics:
    def test_empty_episodes(self, service):
        m = service.calculate_supervision_metrics([])
        assert m["supervision_success_rate"] == 0.0
        assert m["approval_rate"] == 0.0
        assert m["total_proposals"] == 0

    def test_no_supervision_episodes(self, service):
        eps = [make_episode(proposal_id=None), make_episode(proposal_id=None)]
        m = service.calculate_supervision_metrics(eps)
        assert m["supervision_success_rate"] == 0.0
        assert m["total_proposals"] == 0

    def test_all_approved_and_executed(self, service):
        eps = [
            make_episode(
                proposal_id="p1",
                supervision_decision="approved",
                execution_followed_proposal=True,
            ),
            make_episode(
                proposal_id="p2",
                supervision_decision="approved",
                execution_followed_proposal=True,
            ),
        ]
        m = service.calculate_supervision_metrics(eps)
        assert m["approval_rate"] == 1.0
        assert m["execution_success_rate"] == 1.0
        # 1.0*0.6 + 1.0*0.4
        assert m["supervision_success_rate"] == pytest.approx(1.0)

    def test_mixed_approvals_rejections(self, service):
        eps = [
            make_episode(proposal_id="p1", supervision_decision="approved", execution_followed_proposal=True),
            make_episode(proposal_id="p2", supervision_decision="rejected"),
            make_episode(proposal_id="p3", supervision_decision="approved", execution_followed_proposal=False),
        ]
        m = service.calculate_supervision_metrics(eps)
        assert m["total_proposals"] == 3
        assert m["approved_proposals"] == 2
        assert m["rejected_proposals"] == 1
        # approval_rate is rounded to 4 decimals in the source
        assert m["approval_rate"] == round(2 / 3, 4)
        # 1 of 2 approved was executed
        assert m["execution_success_rate"] == 0.5
        # 2/3 * 0.6 + 0.5 * 0.4 (rounded to 4 decimals)
        assert m["supervision_success_rate"] == round((2 / 3) * 0.6 + 0.5 * 0.4, 4)

    def test_zero_approved_no_div_by_zero(self, service):
        eps = [make_episode(proposal_id="p1", supervision_decision="rejected")]
        m = service.calculate_supervision_metrics(eps)
        assert m["execution_success_rate"] == 0.0

    def test_supervisor_type_breakdown(self, service):
        eps = [
            make_episode(proposal_id="p1", supervisor_type="user"),
            make_episode(proposal_id="p2", supervisor_type="autonomous_agent"),
        ]
        m = service.calculate_supervision_metrics(eps)
        assert m["supervisor_type_breakdown"] == {"user": 1, "autonomous_agent": 1}


# ===========================================================================
# calculate_skill_diversity_metrics / get_agent_skill_usage / mastery
# ===========================================================================


class TestSkillMetrics:
    def test_skill_diversity_empty(self, service, monkeypatch):
        monkeypatch.setattr(service, "get_agent_skill_usage", lambda **kw: [])
        m = service.calculate_skill_diversity_metrics("a1", "t1")
        assert m["unique_skill_count"] == 0
        assert m["skill_diversity_score"] == 0.0
        assert m["avg_skill_success_rate"] == 0.0
        assert m["total_skill_executions"] == 0

    def test_skill_diversity_caps_at_one(self, service, monkeypatch):
        SkillSum = es_mod.EpisodeService.SkillUsageSummary
        summaries = [SkillSum(skill_id=f"s{i}", skill_name=f"S{i}", execution_count=5, success_rate=1.0, last_executed_at=None) for i in range(15)]
        monkeypatch.setattr(service, "get_agent_skill_usage", lambda **kw: summaries)
        m = service.calculate_skill_diversity_metrics("a1", "t1")
        assert m["unique_skill_count"] == 15
        assert m["skill_diversity_score"] == 1.0  # capped
        assert m["total_skill_executions"] == 75
        assert len(m["top_skills"]) == 5

    def test_skill_diversity_partial(self, service, monkeypatch):
        SkillSum = es_mod.EpisodeService.SkillUsageSummary
        summaries = [SkillSum(skill_id="s1", skill_name="S1", execution_count=2, success_rate=0.5, last_executed_at=None)]
        monkeypatch.setattr(service, "get_agent_skill_usage", lambda **kw: summaries)
        m = service.calculate_skill_diversity_metrics("a1", "t1")
        assert m["skill_diversity_score"] == pytest.approx(0.1)
        assert m["avg_skill_success_rate"] == pytest.approx(0.5)


class TestAssessSkillMastery:
    def test_mastery_no_skills(self, service, monkeypatch):
        monkeypatch.setattr(service, "get_agent_skill_usage", lambda **kw: [])
        a = service.assess_skill_mastery("a1", "t1", "intern")
        assert a.mastery_score == 0.0
        assert a.skill_diversity == 0.0
        assert a.skills_used == set()

    def test_mastery_full_diversity(self, service, monkeypatch):
        SkillSum = es_mod.EpisodeService.SkillUsageSummary
        summaries = [
            SkillSum(skill_id=f"s{i}", skill_name=f"S{i}", execution_count=2, success_rate=1.0, last_executed_at=None)
            for i in range(3)
        ]
        monkeypatch.setattr(service, "get_agent_skill_usage", lambda **kw: summaries)
        a = service.assess_skill_mastery("a1", "t1", "intern")
        # diversity = min(3/3,1)=1.0 ; success_rate avg=1.0 -> 1.0*0.6 + 1.0*0.4
        assert a.skill_diversity == 1.0
        assert a.skill_success_rate == 1.0
        assert a.mastery_score == pytest.approx(1.0)
        assert a.required_skills_for_level == 3
        assert a.skills_used == {"s0", "s1", "s2"}


# ===========================================================================
# calculate_proposal_quality_metrics
# ===========================================================================


class TestProposalQualityMetrics:
    def test_no_proposal_episodes(self, service):
        # FakeDB returns empty list for AgentEpisode
        m = service.calculate_proposal_quality_metrics("a1", "t1")
        assert m["proposal_episode_count"] == 0
        assert m["proposal_quality_score"] == 0.0
        assert m["avg_proposal_quality"] == 0.0

    def test_quality_score_capped_at_one(self, service, monkeypatch):
        PropEp = namedtuple("PropEp", ["metadata_json"])
        eps = [PropEp({"quality_score": 0.9}), PropEp({"quality_score": 1.0})]
        monkeypatch.setattr(
            FakeQuery, "all", lambda self: eps
        )
        m = service.calculate_proposal_quality_metrics("a1", "t1")
        # avg = 0.95 -> *1.2 = 1.14 capped to 1.0
        assert m["proposal_quality_score"] == 1.0
        assert m["high_quality_proposal_count"] == 2
        assert m["avg_proposal_quality"] == pytest.approx(0.95)


# ===========================================================================
# get_graduation_readiness (integration of the metric helpers)
# ===========================================================================


class TestGraduationReadiness:
    def test_agent_not_found_raises(self, service):
        with pytest.raises(ValueError):
            service.get_graduation_readiness("nope", "t1")

    def test_no_episodes_zero_readiness(self, service, monkeypatch):
        service.db.data["AgentRegistry"] = [make_agent()]
        # episodes empty by default
        resp = service.get_graduation_readiness("a1", "t1")
        assert resp.readiness_score == 0.0
        assert resp.threshold_met is False
        assert resp.episodes_analyzed == 0

    def test_readiness_threshold_met_requires_min_episodes(self, service, monkeypatch):
        # Student -> intern needs >= 10 episodes by default.
        service.db.data["AgentRegistry"] = [make_agent(status="student")]
        eps = [
            make_episode(success=True, human_intervention_count=0, constitutional_score=1.0, confidence_score=1.0)
            for _ in range(5)
        ]
        service.db.data["AgentEpisode"] = eps
        monkeypatch.setattr(service, "calculate_supervision_metrics", lambda e: {"supervision_success_rate": 1.0})
        monkeypatch.setattr(service, "calculate_skill_diversity_metrics", lambda **kw: {"skill_diversity_score": 1.0})
        monkeypatch.setattr(service, "calculate_proposal_quality_metrics", lambda **kw: {"proposal_quality_score": 1.0})

        resp = service.get_graduation_readiness("a1", "t1")
        # Score should be high but min-episodes gate (10) fails with only 5.
        assert resp.readiness_score >= ReadinessThresholds.STUDENT_TO_INTERN["overall"]
        assert resp.threshold_met is False

    def test_readiness_threshold_met_with_override(self, service, monkeypatch):
        service.db.data["AgentRegistry"] = [make_agent(status="student")]
        eps = [make_episode(success=True, human_intervention_count=0, constitutional_score=1.0, confidence_score=1.0) for _ in range(5)]
        service.db.data["AgentEpisode"] = eps
        monkeypatch.setattr(service, "calculate_supervision_metrics", lambda e: {"supervision_success_rate": 1.0})
        monkeypatch.setattr(service, "calculate_skill_diversity_metrics", lambda **kw: {"skill_diversity_score": 1.0})
        monkeypatch.setattr(service, "calculate_proposal_quality_metrics", lambda **kw: {"proposal_quality_score": 1.0})

        # Override min-episodes to 1 so the score gate alone applies.
        resp = service.get_graduation_readiness("a1", "t1", min_episodes_override=1)
        assert resp.threshold_met is True

    def test_readiness_uses_target_level_when_provided(self, service, monkeypatch):
        service.db.data["AgentRegistry"] = [make_agent(status="intern")]
        # Provide at least one episode so we don't take the early-return path.
        service.db.data["AgentEpisode"] = [make_episode()]
        monkeypatch.setattr(service, "calculate_supervision_metrics", lambda e: {"supervision_success_rate": 0.0})
        monkeypatch.setattr(service, "calculate_skill_diversity_metrics", lambda **kw: {"skill_diversity_score": 0.0})
        monkeypatch.setattr(service, "calculate_proposal_quality_metrics", lambda **kw: {"proposal_quality_score": 0.0})
        resp = service.get_graduation_readiness("a1", "t1", target_level="supervised")
        assert resp.breakdown["target_level"] == "supervised"


# ===========================================================================
# _calculate_step_efficiency
# ===========================================================================


class TestStepEfficiency:
    def test_no_steps_returns_one(self, service):
        # Default FakeDB returns [] for AgentReasoningStep
        assert service._calculate_step_efficiency("ex1") == 1.0

    def test_steps_return_one_when_present(self, service):
        Step = namedtuple("Step", ["step_type"])
        steps = [Step("thought"), Step("action"), Step("observation")]
        service.db.data["AgentReasoningStep"] = steps
        eff = service._calculate_step_efficiency("ex1")
        assert eff == 1.0  # redundant_count stays 0 -> optimal=actual

    def test_steps_thought_observation_cycle(self, service):
        # Covers the `continue` branch for thought->observation.
        Step = namedtuple("Step", ["step_type"])
        service.db.data["AgentReasoningStep"] = [Step("thought"), Step("observation")]
        assert service._calculate_step_efficiency("ex1") == 1.0

    def test_steps_react_cycle_three(self, service):
        # Covers the `continue` branch for thought->action->observation.
        Step = namedtuple("Step", ["step_type"])
        service.db.data["AgentReasoningStep"] = [
            Step("thought"), Step("action"), Step("observation"), Step("final_answer")
        ]
        assert service._calculate_step_efficiency("ex1") == 1.0


# ===========================================================================
# get_skill_performance_stats / get_agent_skill_usage (DB-backed)
# ===========================================================================


class TestSkillPerformanceStats:
    def test_no_episodes_returns_empty_stats(self, service):
        service.db.data["AgentEpisode"] = []
        stats = service.get_skill_performance_stats("a1", "t1", "skill-1")
        assert stats.total_executions == 0
        assert stats.success_rate == 0.0
        assert stats.avg_execution_time is None
        assert stats.last_executed_at is None

    def test_with_episodes_computes_stats(self, service):
        service.db.data["AgentEpisode"] = [
            make_episode(
                success=True,
                metadata_json={"skill_type": "openclaw", "skill_id": "skill-1"},
                started_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                completed_at=datetime(2024, 1, 1, 12, 1, tzinfo=timezone.utc),
            ),
            make_episode(
                success=False,
                metadata_json={"skill_type": "openclaw", "skill_id": "skill-1"},
                started_at=datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc),
                completed_at=datetime(2024, 1, 2, 12, 0, 30, tzinfo=timezone.utc),
            ),
        ]
        stats = service.get_skill_performance_stats("a1", "t1", "skill-1")
        assert stats.total_executions == 2
        assert stats.successful_executions == 1
        assert stats.success_rate == 0.5
        # avg of 60s and 30s = 45s
        assert stats.avg_execution_time == 45.0
        assert stats.last_executed_at is not None


class TestGetAgentSkillUsage:
    def test_groups_by_skill_id(self, service):
        service.db.data["AgentEpisode"] = [
            make_episode(success=True, metadata_json={"skill_type": "openclaw", "skill_id": "s1"}),
            make_episode(success=True, metadata_json={"skill_type": "openclaw", "skill_id": "s1"}),
            make_episode(success=False, metadata_json={"skill_type": "openclaw", "skill_id": "s2"}),
            make_episode(success=True, metadata_json={"skill_type": "openclaw"}),  # no skill_id -> skipped
            make_episode(success=True, metadata_json=None),  # None -> skipped
        ]
        summaries = service.get_agent_skill_usage("a1", "t1")
        ids = {s.skill_id for s in summaries}
        assert ids == {"s1", "s2"}
        s1 = next(s for s in summaries if s.skill_id == "s1")
        assert s1.execution_count == 2
        assert s1.success_rate == 1.0

    def test_sorted_by_execution_count_desc(self, service):
        service.db.data["AgentEpisode"] = [
            make_episode(metadata_json={"skill_type": "openclaw", "skill_id": "rare"}),
            make_episode(metadata_json={"skill_type": "openclaw", "skill_id": "common"}),
            make_episode(metadata_json={"skill_type": "openclaw", "skill_id": "common"}),
        ]
        summaries = service.get_agent_skill_usage("a1", "t1")
        assert summaries[0].skill_id == "common"
        assert summaries[0].execution_count == 2
        assert summaries[1].execution_count == 1


# ===========================================================================
# _extract_canvas_metadata (session-based canvas capture path)
# ===========================================================================


class TestExtractCanvasMetadata:
    @pytest.mark.asyncio
    async def test_execution_not_found_returns_empty(self, service):
        service.db.data["AgentExecution"] = []
        out = await service._extract_canvas_metadata("missing")
        assert out == {}

    @pytest.mark.asyncio
    async def test_no_metadata_captures_canvas_actions(self, service, monkeypatch):
        # Execution exists but has no metadata_json -> session-based capture.
        Ex = namedtuple("Ex", ["id", "session_id", "tenant_id", "metadata_json", "started_at", "completed_at", "created_at"])
        when = datetime(2024, 1, 1, tzinfo=timezone.utc)
        service.db.data["AgentExecution"] = [Ex("ex1", "sess1", "t1", None, when, when, when)]
        Action = namedtuple("Action", ["id", "canvas_id", "canvas_type", "action_type", "details_json", "created_at"])
        service.db.data["CanvasAudit"] = [
            Action("a1", "c1", "form", "submit", {"x": 1}, when),
            Action("a2", "c1", "form", "close", None, when),
        ]
        out = await service._extract_canvas_metadata("ex1")
        assert out["canvas_action_count"] == 2
        assert set(out["canvas_action_ids"]) == {"a1", "a2"}

    @pytest.mark.asyncio
    async def test_no_metadata_no_session_returns_empty(self, service, monkeypatch):
        Ex = namedtuple("Ex", ["id", "session_id", "tenant_id", "metadata_json", "started_at", "completed_at", "created_at"])
        when = datetime(2024, 1, 1, tzinfo=timezone.utc)
        service.db.data["AgentExecution"] = [Ex("ex1", None, "t1", None, when, when, when)]
        out = await service._extract_canvas_metadata("ex1")
        assert out == {}


# ===========================================================================
# Episode feedback
# ===========================================================================


class TestEpisodeFeedback:
    def test_update_feedback_episode_not_found(self, service):
        service.db.data["AgentEpisode"] = []
        with pytest.raises(ValueError):
            service.update_episode_feedback("missing", 0.5)

    def test_update_feedback_success(self, service):
        ep = make_episode(metadata_json={})
        service.db.data["AgentEpisode"] = [ep]
        # Block the LanceDB sync path (no running loop).
        fid = service.update_episode_feedback(
            ep.id, 0.8, feedback_notes="great", feedback_category="accuracy"
        )
        assert fid
        assert service.db.committed is True
        assert ep.metadata_json["feedback_score"] == 0.8
        assert service.db.added  # feedback row added

    def test_update_feedback_truncates_long_notes(self, service):
        ep = make_episode(metadata_json={})
        service.db.data["AgentEpisode"] = [ep]
        long_notes = "x" * 1000
        fid = service.update_episode_feedback(ep.id, 0.5, feedback_notes=long_notes)
        assert fid
        # The stored feedback object should have notes truncated to 500 chars.
        feedback_obj = next(o for o in service.db.added if hasattr(o, "feedback_notes"))
        assert feedback_obj.feedback_notes == "x" * 500

    def test_update_feedback_with_capability_tracks_usage(self, service):
        ep = make_episode(metadata_json={})
        service.db.data["AgentEpisode"] = [ep]
        grad_service = Mock()
        with patch("core.capability_graduation_service.CapabilityGraduationService") as Cap:
            Cap.return_value = grad_service
            fid = service.update_episode_feedback(
                ep.id, 0.9, capability_domain="data_analysis", capability_name="chart_gen"
            )
        assert fid
        # Positive feedback (0.9 >= 0.7) -> success=True
        grad_service.record_capability_usage.assert_called_once()
        _, kwargs = grad_service.record_capability_usage.call_args
        assert kwargs["success"] is True
        assert kwargs["capability_name"] == "chart_gen"

    def test_update_feedback_negative_score_is_not_success(self, service):
        ep = make_episode(metadata_json={})
        service.db.data["AgentEpisode"] = [ep]
        grad_service = Mock()
        with patch("core.capability_graduation_service.CapabilityGraduationService") as Cap:
            Cap.return_value = grad_service
            service.update_episode_feedback(
                ep.id, -0.5, capability_domain="code", capability_name="lint"
            )
        _, kwargs = grad_service.record_capability_usage.call_args
        assert kwargs["success"] is False

    def test_get_episode_feedback_empty(self, service):
        service.db.data["EpisodeFeedback"] = []
        assert service.get_episode_feedback("x") == []

    def test_get_episode_feedback_returns_records(self, service):
        F = namedtuple("F", ["id", "feedback_score", "feedback_notes", "feedback_category", "provider_id", "provider_type", "provided_at"])
        when = datetime(2024, 1, 1, tzinfo=timezone.utc)
        service.db.data["EpisodeFeedback"] = [
            F("f1", 0.9, "nice", "accuracy", "u1", "human", when),
        ]
        out = service.get_episode_feedback("ep1")
        assert len(out) == 1
        assert out[0]["feedback_score"] == 0.9
        assert out[0]["provided_at"] == when.isoformat()


class TestDomainFeedbackMetrics:
    def test_no_feedback_returns_no_data(self, service):
        service.db.data["EpisodeFeedback"] = []
        m = service.get_domain_feedback_metrics("t1", "data_analysis")
        assert m["trend"] == "no_data"
        assert m["feedback_count"] == 0

    def test_trend_improving(self, service):
        F = namedtuple("F", ["feedback_score", "capability_name", "capability_domain", "provided_at"])
        now = datetime(2024, 6, 1, tzinfo=timezone.utc)
        # 4 records: first half low, second half high -> improving
        service.db.data["EpisodeFeedback"] = [
            F(0.1, "cap1", "data_analysis", now),
            F(0.1, "cap1", "data_analysis", now),
            F(0.9, "cap1", "data_analysis", now),
            F(0.9, "cap1", "data_analysis", now),
        ]
        m = service.get_domain_feedback_metrics("t1", "data_analysis")
        assert m["trend"] == "improving"
        assert m["positive_count"] == 2
        assert m["by_capability"]["cap1"]["avg_score"] == pytest.approx(0.5)

    def test_trend_declining(self, service):
        F = namedtuple("F", ["feedback_score", "capability_name", "capability_domain", "provided_at"])
        now = datetime(2024, 6, 1, tzinfo=timezone.utc)
        service.db.data["EpisodeFeedback"] = [
            F(0.9, None, "x", now),
            F(0.9, None, "x", now),
            F(0.1, None, "x", now),
            F(0.1, None, "x", now),
        ]
        m = service.get_domain_feedback_metrics("t1", "x")
        assert m["trend"] == "declining"

    def test_trend_stable_within_threshold(self, service):
        F = namedtuple("F", ["feedback_score", "capability_name", "capability_domain", "provided_at"])
        now = datetime(2024, 6, 1, tzinfo=timezone.utc)
        # Difference of 0.05 (< 0.1) -> stable
        service.db.data["EpisodeFeedback"] = [
            F(0.5, None, "x", now),
            F(0.55, None, "x", now),
        ]
        m = service.get_domain_feedback_metrics("t1", "x")
        assert m["trend"] == "stable"

    def test_neutral_count_excludes_positive_and_negative(self, service):
        F = namedtuple("F", ["feedback_score", "capability_name", "capability_domain", "provided_at"])
        now = datetime(2024, 6, 1, tzinfo=timezone.utc)
        service.db.data["EpisodeFeedback"] = [
            F(0.8, None, "x", now),   # positive (>=0.7)
            F(-0.8, None, "x", now),  # negative (<=-0.7)
            F(0.2, None, "x", now),   # neutral
        ]
        m = service.get_domain_feedback_metrics("t1", "x")
        assert m["positive_count"] == 1
        assert m["negative_count"] == 1
        assert m["neutral_count"] == 1

    def test_bug_trend_respects_chronological_order(self, service):
        """BUG: get_domain_feedback_metrics did not order feedback by provided_at,
        so the trend (comparing first half vs second half) was computed against
        DB-default order and produced arbitrary/misleading trend labels.

        Here the rows are stored newest-first (DESC). The fix must sort by
        provided_at ASC so 'first half' = older, 'second half' = newer, and a
        rising trend is correctly labelled 'improving'."""
        F = namedtuple("F", ["feedback_score", "capability_name", "capability_domain", "provided_at"])
        old = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new = datetime(2024, 6, 1, tzinfo=timezone.utc)
        # Inserted newest-first; scores rise over time (old low, new high).
        service.db.data["EpisodeFeedback"] = [
            F(0.9, None, "x", new),
            F(0.9, None, "x", new),
            F(0.1, None, "x", old),
            F(0.1, None, "x", old),
        ]
        m = service.get_domain_feedback_metrics("t1", "x")
        assert m["trend"] == "improving"


# ===========================================================================
# Canvas action linking / retrieval
# ===========================================================================


class TestCanvasActions:
    def test_get_canvas_actions_episode_missing(self, service):
        service.db.data["AgentEpisode"] = []
        assert service.get_canvas_actions_for_episode("x") == []

    def test_get_canvas_actions_no_ids_in_metadata(self, service):
        ep = make_episode(metadata_json={})
        service.db.data["AgentEpisode"] = [ep]
        assert service.get_canvas_actions_for_episode(ep.id) == []

    def test_get_canvas_actions_returns_actions(self, service):
        ep = make_episode(metadata_json={"canvas_action_ids": ["ca1", "ca2"]})
        service.db.data["AgentEpisode"] = [ep]
        Action = namedtuple("Action", ["id", "action_type", "canvas_id", "user_id", "details_json", "created_at"])
        when = datetime(2024, 1, 1, tzinfo=timezone.utc)
        service.db.data["CanvasAudit"] = [
            Action("ca1", "create", "c1", "u1", {"k": "v"}, when),
            Action("ca2", "close", "c1", "u1", None, when),
        ]
        out = service.get_canvas_actions_for_episode(ep.id)
        assert len(out) == 2
        assert out[0]["action_type"] == "create"
        assert out[0]["created_at"] == when.isoformat()

    @pytest.mark.asyncio
    async def test_link_canvas_actions_episode_missing(self, service):
        service.db.data["AgentEpisode"] = []
        # Episode-not-found is an early `return False` (not an exception),
        # so rollback is NOT invoked.
        assert await service.link_canvas_actions_to_episode("x", ["ca1"]) is False
        assert service.db.committed is False

    @pytest.mark.asyncio
    async def test_link_canvas_actions_success(self, service):
        ep = make_episode(metadata_json=None)
        service.db.data["AgentEpisode"] = [ep]
        ok = await service.link_canvas_actions_to_episode(ep.id, ["ca1", "ca2"])
        assert ok is True
        assert ep.metadata_json["canvas_action_ids"] == ["ca1", "ca2"]
        assert service.db.committed is True


# ===========================================================================
# get_agent_episodes filtering
# ===========================================================================


class TestGetAgentEpisodes:
    def test_basic_query(self, service):
        eps = [make_episode(), make_episode()]
        service.db.data["AgentEpisode"] = eps
        out = service.get_agent_episodes("a1", "t1")
        assert out == eps

    def test_filters_return_same_query_object(self, service):
        eps = [make_episode(outcome="failure")]
        service.db.data["AgentEpisode"] = eps
        out = service.get_agent_episodes("a1", "t1", outcome_filter="failure")
        assert out == eps


# ===========================================================================
# get_skill_usage_count / get_proposal_episodes_for_learning
# ===========================================================================


class TestSkillUsageCount:
    def test_count(self, service):
        service.db.data["AgentEpisode"] = [make_episode(), make_episode()]
        # FakeQuery.count returns len of underlying list.
        assert service.get_skill_usage_count("a1", "t1") == 2


class TestProposalEpisodesForLearning:
    def test_returns_empty_list(self, service):
        service.db.data["AgentEpisode"] = []
        out = service.get_proposal_episodes_for_learning("t1", "a1")
        assert out == []

    def test_returns_matching_episodes(self, service):
        PropEp = namedtuple(
            "PropEp",
            ["id", "metadata_json", "task_description", "started_at"],
        )
        service.db.data["AgentEpisode"] = [
            PropEp(
                "e1",
                {
                    "episode_type": "meta_agent_proposal",
                    "quality_score": "0.9",
                    "proposal_id": "p1",
                    "teaching_value": "high",
                    "capability_tags": ["data_analysis"],
                    "meta_agent_guidance": "do x",
                    "quality_breakdown": {"k": "v"},
                },
                "task A",
                datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        out = service.get_proposal_episodes_for_learning("t1", "a1", capability_tags=["data_analysis"])
        assert len(out) == 1
        assert out[0]["episode_id"] == "e1"
        assert out[0]["proposal_id"] == "p1"

    def test_filters_out_by_capability_tags(self, service):
        PropEp = namedtuple("PropEp", ["id", "metadata_json", "task_description", "started_at"])
        service.db.data["AgentEpisode"] = [
            PropEp("e1", {"capability_tags": ["code_execution"]}, "task", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ]
        out = service.get_proposal_episodes_for_learning("t1", "a1", capability_tags=["data_analysis"])
        assert out == []


# ===========================================================================
# Archive to cold storage
# ===========================================================================


class TestArchiveColdStorage:
    @pytest.mark.asyncio
    async def test_episode_not_found(self, service):
        service.db.data["AgentEpisode"] = []
        assert await service.archive_episode_to_cold_storage("missing") is False

    @pytest.mark.asyncio
    async def test_lancedb_unavailable_returns_false(self, service):
        ep = make_episode()
        service.db.data["AgentEpisode"] = [ep]
        service.embedding_service.generate_embedding = AsyncMock(return_value=[0.1] * 8)
        # Force _get_lancedb to return None.
        service._get_lancedb = lambda: None
        assert await service.archive_episode_to_cold_storage(ep.id) is False

    @pytest.mark.asyncio
    async def test_archive_success(self, service):
        ep = make_episode()
        service.db.data["AgentEpisode"] = [ep]
        service.embedding_service.generate_embedding = AsyncMock(return_value=[0.1] * 8)
        lancedb = Mock()
        lancedb.add_episode.return_value = True
        service._get_lancedb = lambda: lancedb
        # The success branch imports core.acu_billing_service (which may not
        # exist); the surrounding try/except swallows ImportError. No patching
        # needed - we just assert archival returns True.
        ok = await service.archive_episode_to_cold_storage(ep.id)
        assert ok is True
        lancedb.add_episode.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_fallback_uses_zeros(self, service):
        ep = make_episode()
        service.db.data["AgentEpisode"] = [ep]
        service.embedding_service.generate_embedding = AsyncMock(side_effect=RuntimeError("boom"))
        service.embedding_service.get_embedding_dimension.return_value = 8
        captured = {}

        def fake_get_lancedb():
            ldb = Mock()

            def _add(episode, emb):
                captured["emb"] = emb
                return True

            ldb.add_episode.side_effect = _add
            return ldb

        service._get_lancedb = fake_get_lancedb
        ok = await service.archive_episode_to_cold_storage(ep.id)
        assert ok is True
        assert captured["emb"] == [0.0] * 8


# ===========================================================================
# create_episode_from_execution
# ===========================================================================


class TestCreateEpisodeFromExecution:
    @pytest.mark.asyncio
    async def test_execution_not_found_raises(self, service):
        service.db.data["AgentExecution"] = []
        with pytest.raises(ValueError):
            await service.create_episode_from_execution("nope", "task", "success", True)

    @pytest.mark.asyncio
    async def test_agent_not_found_raises(self, service):
        Ex = namedtuple("Ex", ["id", "agent_id", "tenant_id", "human_intervention_count", "started_at", "completed_at", "metadata_json", "session_id"])
        service.db.data["AgentExecution"] = [Ex("ex1", "a1", "t1", 0, None, None, {}, None)]
        service.db.data["AgentRegistry"] = []
        with pytest.raises(ValueError):
            await service.create_episode_from_execution("ex1", "task", "success", True)

    @pytest.mark.asyncio
    async def test_success_creates_episode(self, service, monkeypatch):
        Ex = namedtuple("Ex", ["id", "agent_id", "tenant_id", "human_intervention_count", "started_at", "completed_at", "metadata_json", "session_id"])
        service.db.data["AgentExecution"] = [Ex("ex1", "a1", "t1", 0, None, None, {}, None)]
        service.db.data["AgentRegistry"] = [make_agent(status="student", confidence_score=0.7)]
        monkeypatch.setattr(service, "_calculate_step_efficiency", lambda eid: 0.9)
        monkeypatch.setattr(service, "_extract_canvas_metadata", AsyncMock(return_value={}))

        ep = await service.create_episode_from_execution(
            "ex1", "my task", "success", True, constitutional_violations=[], metadata={"foo": "bar"}
        )
        assert ep.task_description == "my task"
        assert ep.constitutional_score == 1.0
        assert ep.step_efficiency == 0.9
        assert ep.confidence_score == 0.7
        assert ep.metadata_json["foo"] == "bar"
        assert service.db.committed is True
        assert service.db.added  # episode was added

    @pytest.mark.asyncio
    async def test_with_violations_lowers_score(self, service, monkeypatch):
        Ex = namedtuple("Ex", ["id", "agent_id", "tenant_id", "human_intervention_count", "started_at", "completed_at", "metadata_json", "session_id"])
        service.db.data["AgentExecution"] = [Ex("ex1", "a1", "t1", 1, None, None, {}, None)]
        service.db.data["AgentRegistry"] = [make_agent(status="student")]
        monkeypatch.setattr(service, "_calculate_step_efficiency", lambda eid: 1.0)
        monkeypatch.setattr(service, "_extract_canvas_metadata", AsyncMock(return_value={}))

        ep = await service.create_episode_from_execution(
            "ex1", "task", "failure", False,
            constitutional_violations=[{"severity": "high"}, {"severity": "medium"}],
        )
        # 1.0 - (0.7 + 0.4) = -0.1 -> max 0.0
        assert ep.constitutional_score == 0.0
        assert ep.success is False

    @pytest.mark.asyncio
    async def test_activity_publisher_called(self, service, monkeypatch):
        Ex = namedtuple("Ex", ["id", "agent_id", "tenant_id", "human_intervention_count", "started_at", "completed_at", "metadata_json", "session_id"])
        service.db.data["AgentExecution"] = [Ex("ex1", "a1", "t1", 0, None, None, {}, None)]
        service.db.data["AgentRegistry"] = [make_agent()]
        monkeypatch.setattr(service, "_calculate_step_efficiency", lambda eid: 1.0)
        monkeypatch.setattr(service, "_extract_canvas_metadata", AsyncMock(return_value={}))
        pub = Mock()
        service.activity_publisher = pub

        await service.create_episode_from_execution("ex1", "task", "success", True)
        # Two publishes: "working" then "idle"
        assert pub.publish_episode_recording.call_count == 2


# ===========================================================================
# recall_episodes_with_detail (raw SQL path — mock the session.execute)
# ===========================================================================


class TestRecallEpisodes:
    @pytest.mark.asyncio
    async def test_agent_not_owned_returns_empty(self, service):
        async def fake_execute(stmt, params=None):
            res = Mock()
            res.scalar_one_or_none.return_value = None
            return res

        service.db.execute = fake_execute
        out = await service.recall_episodes_with_detail("a1", "t1")
        assert out == []

    @pytest.mark.asyncio
    async def test_returns_rows(self, service):
        call_count = {"n": 0}

        async def fake_execute(stmt, params=None):
            call_count["n"] += 1
            res = Mock()
            if call_count["n"] == 1:
                # ownership check
                res.scalar_one_or_none.return_value = "a1"
                return res
            # query
            row = Mock()
            row._mapping = {"id": "e1", "agent_id": "a1"}
            res.fetchall.return_value = [row]
            return res

        service.db.execute = fake_execute
        out = await service.recall_episodes_with_detail("a1", "t1", detail_level=DetailLevel.SUMMARY)
        assert out == [{"id": "e1", "agent_id": "a1"}]

    @pytest.mark.asyncio
    async def test_returns_rows_full_detail(self, service):
        call_count = {"n": 0}

        async def fake_execute(stmt, params=None):
            call_count["n"] += 1
            res = Mock()
            if call_count["n"] == 1:
                res.scalar_one_or_none.return_value = "a1"
                return res
            row = Mock()
            row._mapping = {"id": "e2", "audit_trail": []}
            res.fetchall.return_value = [row]
            return res

        service.db.execute = fake_execute
        out = await service.recall_episodes_with_detail("a1", "t1", detail_level=DetailLevel.FULL)
        assert out == [{"id": "e2", "audit_trail": []}]

    @pytest.mark.asyncio
    async def test_unknown_detail_level_falls_back_to_summary(self, service):
        # Default query is SUMMARY when an unknown level is passed.
        async def fake_execute(stmt, params=None):
            res = Mock()
            res.scalar_one_or_none.return_value = "a1"
            res.fetchall.return_value = []
            return res

        service.db.execute = fake_execute
        # Pass an invalid level — should still resolve to SUMMARY query.
        out = await service.recall_episodes_with_detail("a1", "t1", detail_level="bogus")
        assert out == []
