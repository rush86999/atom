"""
Bug-hunt + coverage tests for core.episode_service (round 2).

Targets UNcovered code paths and verifies REAL bugs found via TDD.
Each bug test is prefixed ``BUG:`` and was written BEFORE the source fix,
confirmed to fail for the right reason, then verified to pass after the fix.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from core.episode_service import (
    EpisodeService,
    ReadinessThresholds,
    DetailLevel,
)


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def service(mock_db):
    svc = EpisodeService.__new__(EpisodeService)
    svc.db = mock_db
    svc.lancedb = None
    svc._tenant_api_key = None
    svc._embedding_service = None
    svc.activity_publisher = None
    return svc


def _make_episode(**kwargs):
    """Build a mock AgentEpisode with sensible defaults."""
    e = Mock()
    e.success = kwargs.get("success", True)
    e.human_intervention_count = kwargs.get("human_intervention_count", 0)
    e.constitutional_score = kwargs.get("constitutional_score", 0.9)
    e.confidence_score = kwargs.get("confidence_score", 0.5)
    e.outcome = kwargs.get("outcome", "success")
    e.step_efficiency = kwargs.get("step_efficiency", None)
    e.proposal_id = kwargs.get("proposal_id", None)
    e.supervision_decision = kwargs.get("supervision_decision", None)
    e.execution_followed_proposal = kwargs.get("execution_followed_proposal", None)
    e.supervisor_type = kwargs.get("supervisor_type", None)
    e.agent_id = kwargs.get("agent_id", "a1")
    e.tenant_id = kwargs.get("tenant_id", "t1")
    e.id = kwargs.get("id", "ep1")
    e.task_description = kwargs.get("task_description", "task")
    e.metadata_json = kwargs.get("metadata_json", {})
    e.started_at = kwargs.get("started_at", datetime(2026, 1, 1))
    e.completed_at = kwargs.get("completed_at", datetime(2026, 1, 2))
    e.maturity_at_time = kwargs.get("maturity_at_time", "intern")
    return e


# ============================================================================
# BUG #3: calculate_readiness_metrics crashes on None constitutional_score or
# confidence_score (sum() of None + float -> TypeError). Episodes created via
# proposal workflow set constitutional_score=None.
# ============================================================================
class TestReadinessMetricsNoneCrashBug:
    """BUG: calculate_readiness_metrics does
        ``sum(e.constitutional_score for e in episodes)`` and
        ``sum(e.confidence_score for e in episodes)``
    without filtering None. A single episode with a None score crashes the
    ENTIRE readiness calculation with TypeError, blocking graduation.
    Episodes created via ProposalService._create_proposal_episode set
    constitutional_score=None, so any intern with proposal-history episodes
    hits this.
    """

    def test_bug_constitutional_score_none_does_not_crash(self, service):
        """BUG: None constitutional_score must be treated as 0, not crash."""
        eps = [
            _make_episode(constitutional_score=None),   # legacy / proposal episode
            _make_episode(constitutional_score=0.9),
        ]
        metrics = service.calculate_readiness_metrics(eps)
        # None treated as 0 -> (0 + 0.9) / 2 = 0.45
        assert metrics["avg_constitutional_score"] == pytest.approx(0.45)

    def test_bug_confidence_score_none_does_not_crash(self, service):
        """BUG: None confidence_score must be treated as 0, not crash."""
        eps = [
            _make_episode(confidence_score=None),
            _make_episode(confidence_score=0.8),
        ]
        metrics = service.calculate_readiness_metrics(eps)
        assert metrics["avg_confidence_score"] == pytest.approx(0.4)

    def test_all_none_scores_yields_zero(self, service):
        eps = [
            _make_episode(constitutional_score=None, confidence_score=None),
            _make_episode(constitutional_score=None, confidence_score=None),
        ]
        metrics = service.calculate_readiness_metrics(eps)
        assert metrics["avg_constitutional_score"] == 0.0
        assert metrics["avg_confidence_score"] == 0.0


# ============================================================================
# Coverage: calculate_readiness_metrics core (success, interventions, efficiency)
# ============================================================================
class TestReadinessMetricsCore:
    def test_empty_episodes_returns_zeros(self, service):
        m = service.calculate_readiness_metrics([])
        assert m["success_rate"] == 0.0
        assert m["avg_step_efficiency"] == 0.0
        assert m["episodes_by_outcome"] == {}

    def test_success_rate_and_interventions(self, service):
        eps = [
            _make_episode(success=True, human_intervention_count=0, outcome="success"),
            _make_episode(success=True, human_intervention_count=2, outcome="success"),
            _make_episode(success=False, human_intervention_count=1, outcome="failure"),
        ]
        m = service.calculate_readiness_metrics(eps)
        assert m["success_rate"] == pytest.approx(2 / 3)
        assert m["zero_intervention_ratio"] == pytest.approx(1 / 3)
        assert m["total_interventions"] == 3
        assert m["episodes_by_outcome"] == {"success": 2, "failure": 1}

    def test_avg_step_efficiency_ignores_none(self, service):
        """None step_efficiency means 'not computed', must be excluded from the
        average (not counted as 0)."""
        eps = [
            _make_episode(step_efficiency=None),
            _make_episode(step_efficiency=0.8),
            _make_episode(step_efficiency=0.6),
        ]
        m = service.calculate_readiness_metrics(eps)
        # (0.8 + 0.6) / 2 only
        assert m["avg_step_efficiency"] == pytest.approx(0.7)

    def test_avg_step_efficiency_all_none_is_zero(self, service):
        eps = [_make_episode(step_efficiency=None), _make_episode(step_efficiency=None)]
        m = service.calculate_readiness_metrics(eps)
        assert m["avg_step_efficiency"] == 0.0


# ============================================================================
# Coverage: calculate_supervision_metrics
# ============================================================================
class TestSupervisionMetrics:
    def test_empty_episodes(self, service):
        m = service.calculate_supervision_metrics([])
        assert m["supervision_success_rate"] == 0.0
        assert m["total_proposals"] == 0

    def test_no_proposal_episodes(self, service):
        eps = [_make_episode(proposal_id=None)]
        m = service.calculate_supervision_metrics(eps)
        assert m["total_proposals"] == 0
        assert m["supervision_success_rate"] == 0.0

    def test_approval_and_execution_rates(self, service):
        eps = [
            _make_episode(proposal_id="p1", supervision_decision="approved",
                          execution_followed_proposal=True, supervisor_type="user"),
            _make_episode(proposal_id="p2", supervision_decision="approved",
                          execution_followed_proposal=False, supervisor_type="user"),
            _make_episode(proposal_id="p3", supervision_decision="rejected",
                          execution_followed_proposal=None, supervisor_type="autonomous_agent"),
        ]
        m = service.calculate_supervision_metrics(eps)
        assert m["total_proposals"] == 3
        assert m["approved_proposals"] == 2
        assert m["rejected_proposals"] == 1
        # approval_rate is rounded to 4 decimals in source
        assert m["approval_rate"] == pytest.approx(round(2 / 3, 4))
        # execution_success_rate = followed / approved = 1/2
        assert m["execution_success_rate"] == pytest.approx(0.5)
        # supervision_success_rate = approval*0.6 + execution*0.4 (using rounded inputs)
        expected = (round(2 / 3, 4) * 0.6) + (0.5 * 0.4)
        assert m["supervision_success_rate"] == pytest.approx(round(expected, 4))
        assert m["supervisor_type_breakdown"] == {"user": 2, "autonomous_agent": 1}

    def test_zero_approved_proposals_no_division_error(self, service):
        eps = [
            _make_episode(proposal_id="p1", supervision_decision="rejected",
                          execution_followed_proposal=None),
        ]
        m = service.calculate_supervision_metrics(eps)
        assert m["execution_success_rate"] == 0.0


# ============================================================================
# Coverage: _calculate_constitutional_score
# ============================================================================
class TestConstitutionalScore:
    def test_no_violations_is_perfect(self, service):
        assert service._calculate_constitutional_score([]) == 1.0
        assert service._calculate_constitutional_score(None) == 1.0

    def test_severity_weights_critical(self, service):
        assert service._calculate_constitutional_score([{"severity": "critical"}]) == 0.0

    def test_severity_weights_high(self, service):
        assert service._calculate_constitutional_score([{"severity": "high"}]) == pytest.approx(0.3)

    def test_severity_weights_medium(self, service):
        assert service._calculate_constitutional_score([{"severity": "medium"}]) == pytest.approx(0.6)

    def test_severity_weights_low(self, service):
        assert service._calculate_constitutional_score([{"severity": "low"}]) == pytest.approx(0.9)

    def test_penalties_cap_at_one(self, service):
        # multiple criticals should not go negative
        score = service._calculate_constitutional_score(
            [{"severity": "critical"}, {"severity": "critical"}]
        )
        assert score == 0.0

    def test_unknown_severity_defaults_to_low(self, service):
        score = service._calculate_constitutional_score([{"severity": "bogus"}])
        assert score == pytest.approx(0.9)  # 1.0 - 0.1

    def test_severity_case_insensitive(self, service):
        assert service._calculate_constitutional_score([{"severity": "CRITICAL"}]) == 0.0

    def test_missing_severity_key_defaults_to_low(self, service):
        # no 'severity' key -> default 'low'
        assert service._calculate_constitutional_score([{}]) == pytest.approx(0.9)


# ============================================================================
# Coverage: level helpers
# ============================================================================
class TestLevelHelpers:
    def test_get_next_level_progression(self, service):
        from core.models import AgentStatus
        assert service._get_next_level(AgentStatus.STUDENT.value) == AgentStatus.INTERN.value
        assert service._get_next_level(AgentStatus.INTERN.value) == AgentStatus.SUPERVISED.value
        assert service._get_next_level(AgentStatus.SUPERVISED.value) == AgentStatus.AUTONOMOUS.value
        # autonomous stays autonomous (max)
        assert service._get_next_level(AgentStatus.AUTONOMOUS.value) == AgentStatus.AUTONOMOUS.value

    def test_get_next_level_unknown_defaults_intern(self, service):
        from core.models import AgentStatus
        assert service._get_next_level("weird") == AgentStatus.INTERN.value

    def test_threshold_for_level(self, service):
        assert service._get_threshold_for_level("intern") == ReadinessThresholds.STUDENT_TO_INTERN["overall"]
        assert service._get_threshold_for_level("supervised") == ReadinessThresholds.INTERN_TO_SUPERVISED["overall"]
        assert service._get_threshold_for_level("autonomous") == ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS["overall"]
        assert service._get_threshold_for_level("unknown") == 0.70

    def test_min_episodes_for_level(self, service):
        assert service._get_min_episodes_for_level("intern") == 10
        assert service._get_min_episodes_for_level("supervised") == 25
        assert service._get_min_episodes_for_level("autonomous") == 50
        assert service._get_min_episodes_for_level("unknown") == 10


# ============================================================================
# Coverage: get_required_skills_for_level + assess_skill_mastery
# ============================================================================
class TestSkillMastery:
    def test_required_skills_case_insensitive(self, service):
        assert service.get_required_skills_for_level("INTERN") == 3
        assert service.get_required_skills_for_level("Autonomous") == 10
        assert service.get_required_skills_for_level("unknown") == 1

    def test_assess_skill_mastery_empty(self, service):
        service.get_agent_skill_usage = Mock(return_value=[])
        assessment = service.assess_skill_mastery("a1", "t1", "supervised")
        assert assessment.mastery_score == 0.0
        assert assessment.skill_diversity == 0.0
        assert assessment.required_skills_for_level == 5
        assert assessment.skills_used == set()

    def test_assess_skill_mastery_partial(self, service):
        from core.episode_service import EpisodeService
        summaries = []
        for i in range(3):
            s = EpisodeService.SkillUsageSummary(
                skill_id=f"s{i}", skill_name=f"Skill {i}",
                execution_count=5, success_rate=0.8,
                last_executed_at=None,
            )
            summaries.append(s)
        service.get_agent_skill_usage = Mock(return_value=summaries)
        # target supervised -> required 5; 3/5 diversity
        assessment = service.assess_skill_mastery("a1", "t1", "supervised")
        assert assessment.skill_diversity == pytest.approx(0.6)
        assert assessment.skill_success_rate == pytest.approx(0.8)
        assert assessment.skill_execution_count == 15
        # mastery = 0.6*0.6 + 0.8*0.4
        assert assessment.mastery_score == pytest.approx(round(0.6 * 0.6 + 0.8 * 0.4, 4))


# ============================================================================
# Coverage: calculate_skill_diversity_metrics + calculate_proposal_quality_metrics
# ============================================================================
class TestSkillAndProposalMetrics:
    def test_skill_diversity_score_capped_at_one(self, service):
        from core.episode_service import EpisodeService
        summaries = [
            EpisodeService.SkillUsageSummary(skill_id=f"s{i}", skill_name=f"S{i}",
                                             execution_count=2, success_rate=1.0,
                                             last_executed_at=None)
            for i in range(15)  # > 10 -> capped
        ]
        service.get_agent_skill_usage = Mock(return_value=summaries)
        m = service.calculate_skill_diversity_metrics("a1", "t1")
        assert m["skill_diversity_score"] == 1.0
        assert m["unique_skill_count"] == 15
        assert m["total_skill_executions"] == 30
        assert len(m["top_skills"]) == 5  # top 5 only

    def test_proposal_quality_no_episodes(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.all.return_value = []
        mock_db.query.return_value.filter.return_value = chain
        m = service.calculate_proposal_quality_metrics("a1", "t1")
        assert m["proposal_quality_score"] == 0.0
        assert m["proposal_episode_count"] == 0

    def test_proposal_quality_with_scores(self, service, mock_db):
        eps = []
        for q in [0.9, 0.5, 0.0]:  # last has no quality
            ep = Mock()
            ep.metadata_json = {"quality_score": q} if q > 0 else {}
            eps.append(ep)
        chain = Mock()
        chain.filter.return_value = chain
        chain.all.return_value = eps
        mock_db.query.return_value.filter.return_value = chain
        m = service.calculate_proposal_quality_metrics("a1", "t1")
        assert m["proposal_episode_count"] == 3
        # avg of [0.9, 0.5] = 0.7; score = min(0.7*1.2, 1.0) = 0.84
        assert m["avg_proposal_quality"] == pytest.approx(0.7)
        assert m["proposal_quality_score"] == pytest.approx(0.84)
        assert m["high_quality_proposal_count"] == 1  # only 0.9 >= 0.8


# ============================================================================
# Coverage: get_episode_feedback + get_canvas_actions_for_episode
# ============================================================================
class TestFeedbackAndCanvas:
    def test_get_episode_feedback_returns_empty_on_error(self, service, mock_db):
        mock_db.query.side_effect = Exception("db down")
        result = service.get_episode_feedback("ep1")
        assert result == []

    def test_get_canvas_actions_no_episode(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        mock_db.query.return_value = chain
        assert service.get_canvas_actions_for_episode("missing") == []

    def test_get_canvas_actions_no_action_ids(self, service, mock_db):
        ep = Mock()
        ep.metadata_json = {}
        chain = Mock()
        chain.filter.return_value = chain
        chain.first.return_value = ep
        mock_db.query.return_value = chain
        assert service.get_canvas_actions_for_episode("ep1") == []


# ============================================================================
# Coverage: get_domain_feedback_metrics (trend + by_capability)
# ============================================================================
class TestDomainFeedbackMetrics:
    def _feedback(self, score, cap=None, when=None):
        f = Mock()
        f.feedback_score = score
        f.capability_name = cap
        f.provided_at = when or datetime(2026, 1, 1, tzinfo=timezone.utc)
        return f

    def test_no_data_returns_no_data_trend(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = []
        mock_db.query.return_value = chain
        m = service.get_domain_feedback_metrics("t1", "data_analysis")
        assert m["trend"] == "no_data"
        assert m["feedback_count"] == 0

    def test_improving_trend(self, service, mock_db):
        # Ordered ascending: first half worse, second half better -> improving
        records = (
            [self._feedback(-0.5, "cap_a") for _ in range(3)] +
            [self._feedback(0.9, "cap_a") for _ in range(3)]
        )
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = records
        mock_db.query.return_value = chain
        m = service.get_domain_feedback_metrics("t1", "data_analysis")
        assert m["trend"] == "improving"
        assert m["by_capability"]["cap_a"]["count"] == 6

    def test_declining_trend(self, service, mock_db):
        records = (
            [self._feedback(0.9) for _ in range(3)] +
            [self._feedback(-0.9) for _ in range(3)]
        )
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = records
        mock_db.query.return_value = chain
        m = service.get_domain_feedback_metrics("t1", "data_analysis")
        assert m["trend"] == "declining"

    def test_sentiment_counts(self, service, mock_db):
        records = [
            self._feedback(0.8),   # positive
            self._feedback(-0.8),  # negative
            self._feedback(0.0),   # neutral
        ]
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.all.return_value = records
        mock_db.query.return_value = chain
        m = service.get_domain_feedback_metrics("t1", "data_analysis")
        assert m["positive_count"] == 1
        assert m["negative_count"] == 1
        assert m["neutral_count"] == 1


# ============================================================================
# Coverage: _calculate_step_efficiency
# ============================================================================
class TestStepEfficiency:
    def test_no_steps_returns_one(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.all.return_value = []
        mock_db.query.return_value = chain
        assert service._calculate_step_efficiency("ex1") == 1.0

    def test_with_steps_returns_le_one(self, service, mock_db):
        from core.models import AgentReasoningStep
        steps = []
        for stype in ["thought", "action", "observation", "thought", "action", "observation"]:
            s = Mock()
            s.step_type = stype
            steps.append(s)
        chain = Mock()
        chain.filter.return_value = chain
        chain.all.return_value = steps
        mock_db.query.return_value = chain
        eff = service._calculate_step_efficiency("ex1")
        assert 0.0 < eff <= 1.0


# ============================================================================
# Coverage: get_agent_episodes filters
# ============================================================================
class TestGetAgentEpisodes:
    def test_filters_applied(self, service, mock_db):
        chain = Mock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = ["ep"]
        mock_db.query.return_value = chain

        result = service.get_agent_episodes(
            "a1", "t1", limit=5, outcome_filter="success",
            start_date=datetime(2026, 1, 1), end_date=datetime(2026, 2, 1),
        )
        assert result == ["ep"]
        # filter called for: base + outcome + start + end = 4
        assert chain.filter.call_count == 4
