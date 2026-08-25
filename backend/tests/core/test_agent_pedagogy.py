"""
Tests for the pedagogical framework (core/agent_pedagogy.py):
ZPD classification, scaffold fading, mastery learning, and banded
grey-area judgment with a feedback loop.
"""

import uuid

import pytest

from core.agent_pedagogy import (
    GreyAreaDecision,
    MASTERY_THRESHOLD,
    PedagogicalFramework,
    ScaffoldLevel,
    TaskFit,
)
from core.models import AgentRegistry


def _make_agent(db_session, status="student", confidence=0.1, config=None):
    agent = AgentRegistry(
        id=f"ped-{uuid.uuid4().hex[:8]}",
        name="Learner",
        category="General",
        description="pedagogy test agent",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=status,
        confidence_score=confidence,
        configuration=config if config is not None else {},
        workspace_id="default",
        tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


class TestZPDClassification:
    def test_student_level1_is_zpd_level3_too_hard(self, db_session):
        agent = _make_agent(db_session, status="student")
        fw = PedagogicalFramework(db_session)

        assert fw.classify_task(agent, 1)["fit"] == TaskFit.IN_ZPD.value
        assert fw.classify_task(agent, 2)["fit"] == TaskFit.IN_ZPD.value
        assert fw.classify_task(agent, 3)["fit"] == TaskFit.TOO_HARD.value

    def test_intern_finds_level1_too_easy(self, db_session):
        agent = _make_agent(db_session, status="intern")
        fw = PedagogicalFramework(db_session)

        assert fw.classify_task(agent, 1)["fit"] == TaskFit.TOO_EASY.value
        assert fw.classify_task(agent, 2)["fit"] == TaskFit.IN_ZPD.value

    def test_supervised_stretches_to_level4(self, db_session):
        agent = _make_agent(db_session, status="supervised")
        fw = PedagogicalFramework(db_session)

        assert fw.classify_task(agent, 4)["fit"] == TaskFit.IN_ZPD.value


class TestScaffoldFading:
    def test_low_confidence_student_gets_full_guidance(self, db_session):
        agent = _make_agent(db_session, confidence=0.10)
        fw = PedagogicalFramework(db_session)

        assignment = fw.get_scaffold_level(agent, topic="invoices")
        assert assignment.level == ScaffoldLevel.FULL_GUIDANCE
        assert "teacher" in assignment.instructions.lower()

    def test_scaffold_fades_with_confidence(self, db_session):
        fw = PedagogicalFramework(db_session)

        levels = [
            fw.get_scaffold_level(_make_agent(db_session, confidence=c)).level
            for c in (0.10, 0.22, 0.33, 0.45)
        ]
        assert levels == [
            ScaffoldLevel.FULL_GUIDANCE,
            ScaffoldLevel.HINTS,
            ScaffoldLevel.CHECKLIST,
            ScaffoldLevel.INDEPENDENT,
        ]

    def test_mastered_topic_fades_even_at_low_confidence(self, db_session):
        agent = _make_agent(db_session, confidence=0.10)
        fw = PedagogicalFramework(db_session)
        for _ in range(MASTERY_THRESHOLD):
            fw.record_mastery_exposure(agent, "invoices", positive=True)
        db_session.refresh(agent)

        assignment = fw.get_scaffold_level(agent, topic="invoices")
        assert assignment.level in (ScaffoldLevel.CHECKLIST, ScaffoldLevel.INDEPENDENT)

    def test_unmastered_topic_caps_at_hints(self, db_session):
        agent = _make_agent(db_session, confidence=0.10)
        fw = PedagogicalFramework(db_session)
        fw.record_mastery_exposure(agent, "invoices", positive=True)
        db_session.refresh(agent)

        assignment = fw.get_scaffold_level(agent, topic="invoices")
        assert assignment.level == ScaffoldLevel.HINTS  # 1 exposure -> not mastered


class TestMasteryLearning:
    def test_mastery_requires_repeated_positive_exposures(self, db_session):
        agent = _make_agent(db_session)
        fw = PedagogicalFramework(db_session)

        r1 = fw.record_mastery_exposure(agent, "emailing", positive=True)
        assert not r1["mastered"] and r1["remaining"] == 2
        fw.record_mastery_exposure(agent, "emailing", positive=True)
        r3 = fw.record_mastery_exposure(agent, "emailing", positive=True)
        assert r3["mastered"]

    def test_mistakes_do_not_reset_progress(self, db_session):
        agent = _make_agent(db_session)
        fw = PedagogicalFramework(db_session)
        fw.record_mastery_exposure(agent, "emailing", positive=True)
        fw.record_mastery_exposure(agent, "emailing", positive=False, note="wrong recipient")
        db_session.refresh(agent)

        report = fw.get_mastery_report(agent)
        assert report["topics"]["emailing"] == 1  # progress kept
        corrections = agent.configuration["pedagogy"]["corrections"]
        assert corrections and corrections[0]["note"] == "wrong recipient"

    def test_mastery_report(self, db_session):
        agent = _make_agent(db_session)
        fw = PedagogicalFramework(db_session)
        for _ in range(3):
            fw.record_mastery_exposure(agent, "a", positive=True)
        fw.record_mastery_exposure(agent, "b", positive=True)
        db_session.refresh(agent)

        report = fw.get_mastery_report(agent)
        assert report["mastered"] == ["a"]
        assert report["in_progress"] == {"b": 1}


class TestGreyAreaJudgment:
    def test_low_confidence_asks_teacher(self, db_session):
        agent = _make_agent(db_session, confidence=0.20)
        fw = PedagogicalFramework(db_session)

        result = fw.judge_grey_area(agent, "unclear invoice format", action_complexity=2)
        assert result["decision"] == GreyAreaDecision.ASK_TEACHER.value
        assert "teacher" in result["rationale"] or result["rationale"]

    def test_mid_confidence_asks_human(self, db_session):
        agent = _make_agent(db_session, confidence=0.50)
        fw = PedagogicalFramework(db_session)

        result = fw.judge_grey_area(agent, "ambiguous vendor request", action_complexity=2)
        assert result["decision"] == GreyAreaDecision.ASK_HUMAN.value

    def test_high_confidence_proceeds_logged(self, db_session):
        agent = _make_agent(db_session, status="intern", confidence=0.80)
        fw = PedagogicalFramework(db_session)

        result = fw.judge_grey_area(agent, "minor formatting variance", action_complexity=2)
        assert result["decision"] == GreyAreaDecision.PROCEED_LOGGED.value
        assert "outcome review is mandatory" in result["guidance"].lower()

    def test_safety_floor_blocks_proceed_above_reach(self, db_session):
        """Grey does not mean unsafe: an agent never proceeds logged on an
        action complexity far above its maturity, whatever the confidence."""
        agent = _make_agent(db_session, status="student", confidence=0.90)
        fw = PedagogicalFramework(db_session)

        result = fw.judge_grey_area(agent, "deleting old records", action_complexity=4)
        assert result["decision"] == GreyAreaDecision.ASK_HUMAN.value

    def test_feedback_loop_closes_and_feeds_mastery(self, db_session):
        agent = _make_agent(db_session, confidence=0.80)
        fw = PedagogicalFramework(db_session)
        decision = fw.judge_grey_area(agent, "minor formatting variance", action_complexity=1)

        outcome = fw.record_decision_outcome(agent, decision["decision_id"], outcome="good", topic="formatting")
        db_session.refresh(agent)

        assert outcome["status"] == "ok"
        assert outcome["mastery"]["topic"] == "formatting"
        # Decision moved from pending to history (reflection record)
        pedagogy = agent.configuration["pedagogy"]
        assert decision["decision_id"] not in pedagogy["pending_decisions"]
        assert pedagogy["decision_history"][-1]["outcome"] == "good"

    def test_bad_outcome_becomes_corrective_lesson(self, db_session):
        agent = _make_agent(db_session, confidence=0.80)
        fw = PedagogicalFramework(db_session)
        decision = fw.judge_grey_area(agent, "risky bulk update", action_complexity=1)

        fw.record_decision_outcome(agent, decision["decision_id"], outcome="bad",
                                   topic="bulk_updates", note="should have asked human")
        db_session.refresh(agent)

        corrections = agent.configuration["pedagogy"]["corrections"]
        assert corrections and corrections[-1]["note"] == "should have asked human"
        # No mastery credit for a bad outcome
        assert agent.configuration["pedagogy"]["mastery"].get("bulk_updates", 0) == 0
