"""Coverage wave 59 — core/agent_graduation_service.py (50% → 90%+).

Readiness score (missing agent, unknown maturity, enriched contract with
gaps), experience-driven readiness, learning consistency (POMDP-gated,
insufficient data, full computation), score + recommendation helpers,
graduation exam (missing episodes, full run), constitutional validation
(missing episode, no segments, validator), promote (missing agent, invalid
level, success, notification), audit trail, supervision metrics (empty/full,
trend improving/declining/stable), supervision validation + scoring, skill
usage metrics, readiness with skills, exam execution.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentStatus


def _agent(**kw):
    base = dict(id="a1", name="Agent 1", category="general",
                status=AgentStatus.SUPERVISED.value, confidence_score=0.8,
                module_path="core.agents.generic_agent",
                class_name="GenericAgent", workspace_id="default",
                tenant_id="default", configuration={},
                user_id="u1")
    base.update(kw)
    return MagicMock(**base)


def _episode(**kw):
    base = dict(id="e1", agent_id="a1", task_description="Task",
                human_intervention_count=1, constitutional_score=0.9,
                maturity_at_time="supervised", started_at=datetime.now(),
                metadata_json={})
    base.update(kw)
    return MagicMock(**base)


def _session(**kw):
    base = dict(id="s1", agent_id="a1", status="completed",
                duration_seconds=3600, intervention_count=1,
                supervisor_rating=4.5, started_at=datetime.now())
    base.update(kw)
    return MagicMock(**base)


@pytest.fixture
def svc():
    return AgentGraduationService(Mock())


class TestReadinessScore:
    async def test_missing_agent(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        result = await svc.calculate_readiness_score("a1", "INTERN")
        assert "error" in result

    async def test_unknown_maturity(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _agent()
        result = await svc.calculate_readiness_score("a1", "BOGUS")
        assert "error" in result

    async def test_full_result_with_gaps(self, svc):
        agent = _agent(status=AgentStatus.STUDENT.value)
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        readiness = SimpleNamespace(
            to_dict=lambda: {"threshold_met": False},
            readiness_score=0.5, episodes_analyzed=10,
            breakdown={"total_interventions": 3},
            zero_intervention_ratio=0.5, avg_constitutional_score=0.6,
        )
        with patch("core.agent_graduation_service.get_episode_service",
                   return_value=SimpleNamespace(
                       get_graduation_readiness=Mock(
                           return_value=readiness))):
            result = await svc.calculate_readiness_score("a1", "INTERN")
        assert result["score"] == 50.0
        assert result["episode_count"] == 10
        assert result["total_human_interventions"] == 3
        assert result["gaps"]  # episode + intervention gaps present
        assert result["ready"] is False


class TestLearningConsistency:
    async def test_pomdp_unavailable(self, svc):
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            result = await svc.analyze_learning_consistency("a1")
        assert "POMDP" in result["recommendation"]

    async def test_insufficient_data(self, svc):
        svc.memory_manager = Mock()
        svc.memory_manager.recall_by_quality.return_value = [1, 2]
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc.analyze_learning_consistency("a1")
        assert "Insufficient" in result["recommendation"]

    async def test_full_computation(self, svc):
        svc.memory_manager = Mock()
        memories = [SimpleNamespace(quality_score=0.9, intervention_required=False)
                    for _ in range(8)]
        svc.memory_manager.recall_by_quality.return_value = memories
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc.analyze_learning_consistency("a1")
        assert result["consistency_score"] > 0.6
        assert result["sample_size"] == 8


class TestScoreHelpers:
    def test_calculate_score(self, svc):
        score = svc._calculate_score(30, 30, 0.1, 0.5, 0.9, 0.5)
        assert score > 80

    def test_generate_recommendation_branches(self, svc):
        assert "ready" in svc._generate_recommendation(True, 90, "INTERN").lower()
        assert "training needed" in svc._generate_recommendation(False, 40, "INTERN")
        assert "progress" in svc._generate_recommendation(False, 60, "INTERN")
        assert "close to ready" in svc._generate_recommendation(False, 80, "INTERN")


class TestExam:
    async def test_run_exam_skips_missing_episodes(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.sandbox_executor.get_sandbox_executor") as gse:
            result = await svc.run_graduation_exam("a1", ["e1", "e2"])
        assert result["passed"] is True  # no cases -> all([]) True
        assert result["total_cases"] == 2

    async def test_run_exam_full(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _episode()
        executor = Mock()
        executor.execute_in_sandbox = AsyncMock(return_value=SimpleNamespace(
            passed=True, interventions=0, safety_violations=0,
            replayed_actions=[]))
        with patch("core.sandbox_executor.get_sandbox_executor",
                   return_value=executor):
            result = await svc.run_graduation_exam("a1", ["e1"])
        assert result["passed"] is True
        assert result["score"] == 100.0

    async def test_execute_graduation_exam(self, svc):
        with patch("core.agent_graduation_service.get_graduation_exam_executor") as gge:
            ex = gge.return_value
            ex.execute_exam = AsyncMock(return_value={
                "success": True, "score": 90.0, "constitutional_compliance": 1.0,
                "passed": True, "constitutional_violations": []})
            result = await svc.execute_graduation_exam("a1", "ws", "INTERN")
        assert result["exam_completed"] is True
        ex.execute_exam = AsyncMock(return_value={"success": False, "error": "x"})
        with patch("core.agent_graduation_service.get_graduation_exam_executor",
                   return_value=ex):
            failed = await svc.execute_graduation_exam("a1", "ws", "INTERN")
        assert failed["exam_completed"] is False


class TestConstitutional:
    async def test_missing_episode(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        result = await svc.validate_constitutional_compliance("e1")
        assert "error" in result

    async def test_no_segments(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _episode()
        svc.db.query.return_value.filter.return_value.all.return_value = None
        result = await svc.validate_constitutional_compliance("e1")
        assert result["compliant"] is True
        assert "No segments" in result["note"]

    async def test_with_validator(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _episode()
        svc.db.query.return_value.filter.return_value.all.return_value = [1, 2]
        with patch("core.constitutional_validator.ConstitutionalValidator") as cv:
            v = cv.return_value
            v.validate_actions.return_value = {
                "compliant": True, "score": 1.0, "violations": [],
                "total_actions": 2, "checked_actions": 2}
            result = await svc.validate_constitutional_compliance("e1")
        assert result["compliant"] is True
        assert result["total_actions"] == 2


class TestPromote:
    async def test_missing_agent(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        assert await svc.promote_agent("a1", "INTERN", "u1") is False

    async def test_invalid_level(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _agent()
        assert await svc.promote_agent("a1", "BOGUS", "u1") is False

    async def test_success(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        with patch("core.notification_service.NotificationService") as ns, \
             patch("core.personal_scope.resolve_workspace_id",
                   return_value="w1"), \
             patch("core.personal_scope.resolve_tenant_id",
                   return_value="t1"), \
             patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            ns.return_value.send_notification = AsyncMock()
            result = await svc.promote_agent("a1", "INTERN", "u1")
        assert result is True
        assert agent.status == AgentStatus.INTERN
        svc.db.commit.assert_called()

    async def test_db_error(self, svc):
        svc.db.query.side_effect = RuntimeError("boom")
        assert await svc.promote_agent("a1", "INTERN", "u1") is False

    async def test_commit_error_rolls_back(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        svc.db.commit.side_effect = RuntimeError("boom")
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            assert await svc.promote_agent("a1", "INTERN", "u1") is False
        svc.db.rollback.assert_called()


class TestAuditTrail:
    async def test_missing_agent(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        result = await svc.get_graduation_audit_trail("a1")
        assert "error" in result

    async def test_full_trail(self, svc):
        agent = _agent()
        svc.db.query.return_value.filter.return_value.first.return_value = agent
        svc.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _episode(constitutional_score=0.8, maturity_at_time="intern"),
            _episode(constitutional_score=None, maturity_at_time="intern"),
        ]
        result = await svc.get_graduation_audit_trail("a1")
        assert result["total_episodes"] == 2
        assert result["avg_constitutional_score"] == 0.8
        assert result["episodes_by_maturity"]["intern"] == 2


class TestSupervisionMetrics:
    async def test_empty(self, svc):
        svc.db.query.return_value.filter.return_value.all.return_value = []
        result = await svc.calculate_supervision_metrics("a1", AgentStatus.SUPERVISED)
        assert result["total_sessions"] == 0
        assert result["intervention_rate"] == 1.0

    async def test_full_metrics(self, svc):
        svc.db.query.return_value.filter.return_value.all.return_value = [
            _session(intervention_count=2, supervisor_rating=4.5),
            _session(intervention_count=0, supervisor_rating=5.0),
            _session(intervention_count=1, supervisor_rating=2.0),
        ]
        result = await svc.calculate_supervision_metrics("a1", AgentStatus.SUPERVISED)
        assert result["total_sessions"] == 3
        assert result["total_supervision_hours"] == 3.0
        assert result["high_rating_sessions"] == 2
        assert result["low_intervention_sessions"] == 2
        assert result["average_supervisor_rating"] == 3.83

    def test_performance_trend_branches(self, svc):
        base = [datetime.now() - timedelta(days=i) for i in range(10)]
        improving = [_session(started_at=base[i],
                              supervisor_rating=5 if i < 5 else 3,
                              intervention_count=0 if i < 5 else 2)
                     for i in range(10)]
        assert svc._calculate_performance_trend(improving) == "improving"
        declining = [_session(started_at=base[i],
                              supervisor_rating=3 if i < 5 else 5,
                              intervention_count=2 if i < 5 else 0)
                     for i in range(10)]
        assert svc._calculate_performance_trend(declining) == "declining"
        short = [_session() for _ in range(3)]
        assert svc._calculate_performance_trend(short) == "stable"


class TestSupervisionValidation:
    async def test_validation_flow(self, svc):
        with patch.object(svc, "calculate_readiness_score",
                          new=AsyncMock(return_value={
                              "ready": True, "score": 90.0, "gaps": [],
                              "current_maturity": "supervised"})), \
             patch.object(svc, "calculate_supervision_metrics",
                          new=AsyncMock(return_value={
                              "high_rating_sessions": 10,
                              "low_intervention_sessions": 8,
                              "average_supervisor_rating": 4.5,
                              "intervention_rate": 0.2,
                              "recent_performance_trend": "improving",
                              "total_sessions": 12})):
            result = await svc.validate_graduation_with_supervision(
                "a1", AgentStatus.SUPERVISED)
        assert result["ready"] is True
        assert result["score"] > 80
        assert "ready for promotion" in result["recommendation"].lower()

    async def test_validation_with_gaps(self, svc):
        with patch.object(svc, "calculate_readiness_score",
                          new=AsyncMock(return_value={
                              "ready": False, "score": 40.0, "gaps": ["x"],
                              "current_maturity": "student"})), \
             patch.object(svc, "calculate_supervision_metrics",
                          new=AsyncMock(return_value={
                              "high_rating_sessions": 0,
                              "low_intervention_sessions": 0,
                              "average_supervisor_rating": 2.0,
                              "intervention_rate": 5.0,
                              "recent_performance_trend": "declining",
                              "total_sessions": 2})):
            result = await svc.validate_graduation_with_supervision(
                "a1", AgentStatus.SUPERVISED)
        assert result["ready"] is False
        assert len(result["gaps"]) >= 4

    def test_supervision_score(self, svc):
        metrics = {"average_supervisor_rating": 4.0, "intervention_rate": 0.2,
                   "total_sessions": 10, "high_rating_sessions": 8,
                   "recent_performance_trend": "improving"}
        score = svc._supervision_score(metrics, {"max_intervention_rate": 0.5})
        assert score > 70


class TestSkills:
    async def test_skill_usage_metrics(self, svc):
        svc.db.execute.side_effect = None
        exec_result = Mock()
        exec_result.scalars.return_value.all.return_value = [
            SimpleNamespace(status="success", skill_id="s1"),
            SimpleNamespace(status="success", skill_id="s1"),
            SimpleNamespace(status="failure", skill_id="s2"),
        ]
        ep_result = Mock()
        ep_result.scalars.return_value.all.return_value = [1, 2]
        svc.db.execute.return_value = ep_result
        svc.db.execute.side_effect = [exec_result, ep_result]
        result = await svc.calculate_skill_usage_metrics("a1")
        assert result["total_skill_executions"] == 3
        assert result["success_rate"] == pytest.approx(2 / 3)
        assert result["unique_skills_used"] == 2
        assert result["skill_episodes_count"] == 2

    async def test_readiness_with_skills(self, svc):
        with patch.object(svc, "calculate_readiness_score",
                          new=AsyncMock(return_value={"score": 50.0})), \
             patch.object(svc, "calculate_skill_usage_metrics",
                          new=AsyncMock(return_value={
                              "unique_skills_used": 5, "total_skill_executions": 0,
                              "successful_executions": 0, "success_rate": 0,
                              "skill_episodes_count": 0,
                              "skill_learning_velocity": 0})):
            result = await svc.calculate_readiness_score_with_skills("a1", "INTERN")
        assert result["readiness_score"] == 0.55  # 0.5 + 0.05 bonus
        assert result["skill_diversity_bonus"] == 0.05


class TestExperienceDriven:
    async def test_pomdp_fallback(self, svc):
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", False), \
             patch.object(svc, "calculate_readiness_score",
                          new=AsyncMock(return_value={"score": 50})):
            result = await svc.calculate_experience_driven_readiness("a1", "INTERN")
        assert result["score"] == 50

    async def test_missing_agent(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True), \
             patch.object(svc, "experience_calculator", Mock()):
            result = await svc.calculate_experience_driven_readiness("a1", "INTERN")
        assert "error" in result

    async def test_unknown_maturity(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _agent()
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True), \
             patch.object(svc, "experience_calculator", Mock()):
            result = await svc.calculate_experience_driven_readiness("a1", "BOGUS")
        assert "error" in result

    async def test_full_flow(self, svc):
        svc.db.query.return_value.filter.return_value.first.return_value = _agent()
        calc = Mock()
        calc.calculate_readiness_score.return_value = {
            "ready": True, "score": 90.0, "gaps": [],
            "learning_consistency": 0.8}
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True), \
             patch.object(svc, "experience_calculator", calc), \
             patch.object(svc, "_analyze_intervention_trajectory",
                          new=AsyncMock(return_value={
                              "is_improving": True, "trend": "improving"})):
            result = await svc.calculate_experience_driven_readiness("a1", "INTERN")
        assert result["ready"] is True
        assert result["intervention_trajectory"]["trend"] == "improving"
        assert "ready for promotion" in result["recommendation"].lower()

    async def test_trajectory_pomdp_missing(self, svc):
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", False):
            result = await svc._analyze_intervention_trajectory("a1")
        assert result["trend"] == "unknown"

    async def test_trajectory_insufficient(self, svc):
        svc.memory_manager = Mock()
        svc.memory_manager.recall_by_quality.return_value = [1, 2]
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc._analyze_intervention_trajectory("a1")
        assert result["trend"] == "insufficient_data"

    async def test_trajectory_improving(self, svc):
        svc.memory_manager = Mock()
        memories = (
            [SimpleNamespace(intervention_required=False)] * 10 +  # recent: none
            [SimpleNamespace(intervention_required=True)] * 10     # historical: high
        )
        svc.memory_manager.recall_by_quality.return_value = memories
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc._analyze_intervention_trajectory("a1")
        assert result["trend"] == "improving"
        assert result["is_improving"] is True

    async def test_trajectory_declining(self, svc):
        svc.memory_manager = Mock()
        memories = (
            [SimpleNamespace(intervention_required=True)] * 10 +   # recent: high
            [SimpleNamespace(intervention_required=True)] * 2 +    # historical: 0.2
            [SimpleNamespace(intervention_required=False)] * 8
        )
        svc.memory_manager.recall_by_quality.return_value = memories
        with patch("core.agent_graduation_service.POMDP_AVAILABLE", True):
            result = await svc._analyze_intervention_trajectory("a1")
        assert result["trend"] == "declining"
        assert result["is_improving"] is False

    def test_experience_recommendation(self, svc):
        r = svc._generate_experience_driven_recommendation(
            True, 90, "INTERN", [], {"trend": "improving"})
        assert "ready for promotion" in r.lower()
        r2 = svc._generate_experience_driven_recommendation(
            False, 30, "INTERN", ["g1", "g2"], {"trend": "declining"})
        assert "Significant training" in r2
        assert "declining" in r2
        assert "g1" in r2
        r3 = svc._generate_experience_driven_recommendation(
            False, 80, "INTERN", [], {"trend": "improving"})
        assert "Close to ready" in r3
