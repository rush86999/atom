"""
TDD bug-hunt tests for core/graduation_exam.py.

Each test documents a concrete bug discovered in the graduation / scoring /
state-machine logic and asserts the CORRECT behavior, so it fails today.

These tests are intentionally isolated: the DB session and EpisodeService are
mocked so they exercise only the logic inside GraduationExamService itself.
"""
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

# Mock EpisodeService before importing graduation_exam (mirrors the pattern
# used in tests/core/test_graduation_exam_coverage.py so we can construct the
# service without pulling in the full persistence stack).
_mock_episode_service = Mock()
_mock_episode_service.EpisodeService = Mock
_mock_episode_service.ReadinessThresholds = Mock
sys.modules.setdefault('core.episode_service', _mock_episode_service)

from core.graduation_exam import GraduationExamService
from core.models import (
    AgentRegistry,
    AgentEpisode,
    EdgeCaseLibrary,
    AgentStatus,
    PromotionType,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _query_chain(rows):
    """Build a fluent query mock that returns `rows` from .all()/.first()."""
    q = Mock()
    q.filter = Mock(return_value=q)
    q.order_by = Mock(return_value=q)
    q.limit = Mock(return_value=q)
    q.all = Mock(return_value=list(rows))
    q.first = Mock(return_value=rows[0] if rows else None)
    return q


def _make_agent(status=AgentStatus.STUDENT.value, promotion_count=0):
    """Build a mock AgentRegistry row."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent-1"
    agent.tenant_id = "tenant-1"
    agent.status = status
    agent.promotion_count = promotion_count
    agent.last_promotion_at = None
    agent.last_exam_id = None
    agent.exam_eligible_at = None
    return agent


def _passing_readiness():
    r = Mock()
    r.readiness_score = 0.9
    r.threshold_met = True
    r.zero_intervention_ratio = 0.95
    r.avg_constitutional_score = 0.97
    r.avg_confidence_score = 0.9
    r.success_rate = 0.95
    r.episodes_analyzed = 30
    return r


def _passing_mastery():
    m = Mock()
    m.mastery_score = 0.9
    m.skill_diversity = 0.8
    m.skills_used = ["a", "b", "c"]
    m.skill_execution_count = 30
    m.required_skills_for_level = 2
    m.skill_success_rate = 0.9
    return m


@pytest.fixture
def db_session():
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def service(db_session):
    return GraduationExamService(db_session)


# ===========================================================================
# Bug 1: constitutional check ignores human interventions for pass/fail
# ===========================================================================

class TestConstitutionalCheckBugs:
    def test_human_intervention_does_not_fail_constitutional_check(self, service, db_session):
        """BUG: human interventions record a violation but never flip `passed` to False.

        _constitutional_guardrail_check() appends a violation when an episode
        has human_intervention_count > 0, but only the constitutional_score < 0.95
        branch sets passed = False. As a result the check returns passed=True
        while simultaneously reporting violations, and execute_graduation_exam
        (which keys off `passed`) lets the agent graduate despite interventions.
        """
        episode = Mock(spec=AgentEpisode)
        episode.id = "ep-1"
        episode.constitutional_score = 0.99  # above threshold
        episode.human_intervention_count = 5  # clear intervention signal
        episode.started_at = datetime.utcnow()

        db_session.query.return_value = _query_chain([episode])

        result = service._constitutional_guardrail_check(
            agent_id="agent-1", tenant_id="tenant-1"
        )

        # Correct behavior: interventions imply a violation, so the check
        # should NOT pass while violations are present.
        assert result["violations"], "expected at least one violation recorded"
        assert result["passed"] is False, (
            "check must fail when human interventions are present, but it reports passed=True"
        )


# ===========================================================================
# Bug 2: manual promotion allows demotion (no level ordering check)
# ===========================================================================

class TestManualPromotionBugs:
    def test_manual_promotion_allows_downgrade(self, service, db_session):
        """BUG: promote_agent_manually() accepts a target level lower than current.

        Unlike demote_agent(), promote_agent_manually() validates only that
        new_level is one of the known statuses -- it never checks that new_level
        is actually higher than the agent's current level. An admin can
        therefore "promote" an AUTONOMOUS agent down to STUDENT and have it
        recorded as promotion_type=MANUAL (and increment promotion_count).
        """
        agent = _make_agent(status=AgentStatus.AUTONOMOUS.value, promotion_count=3)
        db_session.query.return_value = _query_chain([agent])

        with patch('core.graduation_exam.EpisodeService') as ep:
            ep.return_value.get_graduation_readiness.return_value = Mock(readiness_score=0.5)

            result = service.promote_agent_manually(
                agent_id="agent-1",
                tenant_id="tenant-1",
                new_level=AgentStatus.STUDENT.value,  # LOWER than AUTONOMOUS
                promoted_by="admin",
                justification="oops",
            )

        # Correct behavior: a "promotion" to a lower level must be rejected.
        assert result.success is False, (
            "promote_agent_manually must refuse to move an agent to a lower level"
        )


# ===========================================================================
# Bug 3: edge case stats are mutated but the failure counts are wrong when
# the simulator returns no "passed" key.
# ===========================================================================

class TestEdgeCaseSimulationBugs:
    def test_edge_case_simulation_missing_passed_key_counts_as_pass(self, service, db_session):
        """BUG: _run_edge_case_simulations() uses simulation_result["passed"]
        without .get(), so a result dict missing the key raises KeyError
        instead of being treated as a failure / skipped case.

        The companion code that reads simulation_result.get("violations") and
        simulation_result.get("reason") defensively, but indexed access on
        "passed" assumes every simulator implementation includes that exact key.
        """
        edge = Mock(spec=EdgeCaseLibrary)
        edge.id = "ec-1"
        edge.name = "scenario"
        edge.violation_type = "safety"
        edge.times_tested = 0
        edge.times_passed = 0
        edge.last_tested_at = None

        db_session.query.return_value = _query_chain([edge])

        with patch('core.graduation_exam.EdgeCaseSimulator') as sim_cls, \
             patch('core.graduation_exam.asyncio.run') as arun:
            # Simulator returns a dict WITHOUT the "passed" key.
            arun.return_value = {"violations": ["v1"], "reason": "boom"}
            sim_cls.return_value = Mock()

            # Correct behavior: a malformed/failed simulation result should be
            # handled gracefully (treated as a failure or skipped), NOT raise.
            try:
                result = service._run_edge_case_simulations(
                    agent_id="agent-1", tenant_id="tenant-1"
                )
            except KeyError:
                pytest.fail(
                    "missing 'passed' key in simulation result raised KeyError "
                    "instead of being handled defensively"
                )

            # And such a result must not be silently counted as a pass.
            assert result["passed"] == 0


# ===========================================================================
# Bug 5: execute_graduation_exam does not validate target_level against
# the agent's current level, allowing "promotion" to the SAME level.
# ===========================================================================

class TestExamTargetLevelBugs:
    def test_execute_graduation_exam_allows_same_level_target(self, service, db_session):
        """BUG: execute_graduation_exam() accepts a target_level equal to the
        agent's current level. Combined with _get_next_level() this lets an
        agent "pass" an exam whose net effect is a no-op promotion that still
        increments promotion_count and writes a promotion history record.

        The only terminal-state guard is the AUTONOMOUS check; every other
        level pair (including current==target) is accepted.
        """
        agent = _make_agent(status=AgentStatus.INTERN.value, promotion_count=1)
        agent_query = _query_chain([agent])

        def query_side_effect(model):
            if model is AgentEpisode:
                return _query_chain([])
            if model is EdgeCaseLibrary:
                return _query_chain([])
            return agent_query

        db_session.query = Mock(side_effect=query_side_effect)

        with patch('core.graduation_exam.EpisodeService') as ep, \
             patch('core.graduation_exam.EdgeCaseSimulator') as sim, \
             patch('core.graduation_exam.asyncio.run') as arun:
            ep.return_value.get_graduation_readiness.return_value = _passing_readiness()
            ep.return_value.assess_skill_mastery.return_value = _passing_mastery()
            sim.return_value = Mock()
            arun.return_value = {"passed": True, "violations": []}

            result = service.execute_graduation_exam(
                agent_id="agent-1",
                tenant_id="tenant-1",
                target_level=AgentStatus.INTERN.value,  # SAME as current
            )

        # Correct behavior: an exam targeting the agent's current level is a
        # no-op and must be rejected (passed=False / promoted=False), not a
        # successful promotion.
        assert result.promoted is False, (
            "execute_graduation_exam must not promote an agent to its current level"
        )
        assert agent.promotion_count == 1, (
            "promotion_count must not increment for a same-level exam"
        )


# ===========================================================================
# Bug 6: _skill_performance_check counts duplicate skills toward diversity
# ===========================================================================

class TestSkillPerformanceBugs:
    def test_duplicate_skills_inflate_unique_skill_count(self, service, db_session):
        """BUG: _skill_performance_check() computes unique_skill_count via
        len(mastery.skills_used) without de-duplicating. If skills_used is a
        list containing repeats (e.g. ["x", "x", "x"]) the agent can satisfy
        required_skills_for_level=3 with a single skill repeated three times.
        """
        mastery = Mock()
        mastery.mastery_score = 0.9
        mastery.skill_diversity = 0.1
        mastery.skills_used = ["only_skill", "only_skill", "only_skill"]  # repeats
        mastery.skill_execution_count = 30
        mastery.required_skills_for_level = 3
        mastery.skill_success_rate = 0.9

        with patch('core.graduation_exam.EpisodeService') as ep:
            ep.return_value.assess_skill_mastery.return_value = mastery

            result = service._skill_performance_check(
                agent_id="agent-1",
                tenant_id="tenant-1",
                target_level=AgentStatus.SUPERVISED.value,
            )

        # Correct behavior: 3 copies of the same skill is only 1 unique skill,
        # which is below required_skills_for_level=3, so requirements must NOT
        # be met.
        assert result["requirements_met"] is False, (
            "duplicate skill entries must not count toward the unique-skill requirement"
        )


# ===========================================================================
# Bug 7: _run_edge_case_simulations mutates ORM objects but never commits
# within the method, AND execute_graduation_exam commits only `exam`.
# ===========================================================================

class TestEdgeCaseStatsPersistence:
    def test_edge_case_stats_incremented_before_commit(self, service, db_session):
        """BUG: _run_edge_case_simulations() increments edge_case.times_tested
        and edge_case.times_passed in-place, but the method itself never calls
        db.commit() and execute_graduation_exam() only refreshes the exam
        object. When the session is not autoflush/autocommit, the mutated
        EdgeCaseLibrary rows are lost. The test asserts the increments happen
        AND are committed (flushed) within the simulation stage.
        """
        edge = Mock(spec=EdgeCaseLibrary)
        edge.id = "ec-1"
        edge.name = "scenario"
        edge.violation_type = "safety"
        edge.times_tested = 5
        edge.times_passed = 4
        edge.last_tested_at = None

        db_session.query.return_value = _query_chain([edge])

        with patch('core.graduation_exam.EdgeCaseSimulator') as sim, \
             patch('core.graduation_exam.asyncio.run') as arun:
            arun.return_value = {"passed": True, "violations": []}
            sim.return_value = Mock()

            service._run_edge_case_simulations(
                agent_id="agent-1", tenant_id="tenant-1"
            )

        # Correct behavior: the statistics must be incremented...
        assert edge.times_tested == 6
        assert edge.times_passed == 5
        # ...and the change must be flushed to the session for durability.
        assert db_session.commit.called or db_session.flush.called, (
            "edge case stat mutations are never committed/flushed inside "
            "_run_edge_case_simulations()"
        )


# ===========================================================================
# Bug 8: GEA evaluate_evolved_agent double-defaults readiness_score on failure
# ===========================================================================

class TestGEAEvaluationBugs:
    def test_evaluate_evolved_agent_readiness_exception_swallowed_silently(self, service, db_session):
        """BUG: evaluate_evolved_agent() wraps the readiness call in try/except
        and on failure sets readiness_score = 0.5 with only a debug log. A
        candidate config whose readiness cannot be computed therefore scores a
        *neutral* 0.5 instead of being penalised, masking real evaluation
        failures. The exception is swallowed rather than surfaced.
        """
        with patch.object(
            service, 'calculate_readiness_score', side_effect=RuntimeError("db down")
        ), patch.object(
            service, '_constitutional_guardrail_check', return_value={"passed": True, "violations": []}
        ):
            result = service.evaluate_evolved_agent(
                agent_id="agent-1",
                tenant_id="tenant-1",
                evolved_config={
                    "system_prompt": "x" * 200,
                    "evolution_history": [],
                },
            )

        # Correct behavior: a readiness lookup failure should be recorded as a
        # failure reason (or yield readiness_score 0.0), NOT silently treated
        # as a healthy 0.5.
        assert result["readiness_score"] != 0.5, (
            "readiness exception is swallowed and assigned a neutral 0.5 score"
        )
        assert any("readiness" in r.lower() for r in result["failure_reasons"]), (
            "readiness exception must be surfaced as a failure reason"
        )
