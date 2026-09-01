"""
Tests for student learning pathways (core/student_learning_service.py) and
the teach_student governance contract.
"""

import uuid

import pytest
from unittest.mock import MagicMock

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, HITLAction, WorkflowExecutionLog
from core.student_learning_service import (
    StudentLearningService,
    format_lessons_block,
    get_agent_lessons,
    learn_user_style,
)


def _make_student(db_session, status="student", confidence=0.1, capabilities=None):
    agent = AgentRegistry(
        id=f"student-{uuid.uuid4().hex[:8]}",
        name="Learner",
        category="General",
        description="test student",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status=status,
        confidence_score=confidence,
        capabilities=capabilities or ["send_email"],
        configuration={},
        workspace_id="default",
        tenant_id="default",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


class TestTeacherPathway:
    def test_teacher_lesson_boosts_confidence_and_logs(self, db_session):
        student = _make_student(db_session)
        service = StudentLearningService(db_session)

        result = service.learn_from_teacher(student.id, "atom_main", "Always double-check invoice totals", topic="invoices")

        assert result["status"] == "ok"
        assert result["confidence_boost"] == pytest.approx(0.05)
        db_session.refresh(student)
        assert student.confidence_score == pytest.approx(0.15)
        entry = student.configuration["learning"]["log"][0]
        assert entry["source"] == "teacher"
        assert entry["teacher_agent_id"] == "atom_main"
        assert entry["topic"] == "invoices"
        assert student.configuration["learning"]["pathways_used"] == ["teacher"]

    def test_teaching_cannot_cross_learning_ceiling(self, db_session):
        student = _make_student(db_session, confidence=0.43)
        service = StudentLearningService(db_session)

        result = service.learn_from_teacher(student.id, "atom_main", "final lesson")

        db_session.refresh(student)
        assert student.confidence_score == pytest.approx(0.45)
        assert result["at_learning_ceiling"] is True
        # Still a STUDENT — promotion belongs to training/graduation only
        assert student.status == "student"

    def test_non_student_agents_do_not_learn(self, db_session):
        intern = _make_student(db_session, status="intern")
        service = StudentLearningService(db_session)

        result = service.learn_from_teacher(intern.id, "atom_main", "lesson")

        assert result["status"] == "error"
        assert result["reason"] == "student_not_found"

    def test_missing_student_returns_error(self, db_session):
        service = StudentLearningService(db_session)
        result = service.learn_from_teacher("nope", "atom_main", "lesson")
        assert result["status"] == "error"


class TestObservationPathway:
    def test_observation_boost_is_smaller(self, db_session):
        student = _make_student(db_session, capabilities=["send_email"])
        service = StudentLearningService(db_session)

        result = service.learn_from_observation(student.id, "hitl_approval", "A human approved 'send_email'")

        assert result["status"] == "ok"
        assert result["confidence_boost"] == pytest.approx(0.01)
        db_session.refresh(student)
        entry = student.configuration["learning"]["log"][0]
        assert entry["source"] == "observation"
        assert entry["observation_type"] == "hitl_approval"

    def test_both_pathways_recorded(self, db_session):
        student = _make_student(db_session)
        service = StudentLearningService(db_session)
        service.learn_from_teacher(student.id, "atom_main", "lesson")
        service.learn_from_observation(student.id, "workflow_execution", "watched a step complete")

        db_session.refresh(student)
        assert student.configuration["learning"]["pathways_used"] == ["observation", "teacher"]

    def test_observe_workspace_absorbs_approvals_and_runs(self, db_session):
        student = _make_student(db_session)
        db_session.add(HITLAction(
            workspace_id="default",
            agent_id="some-agent",
            action_type="send_email",
            platform="internal",
            params={},
            status="approved",
            reason="looked safe",
        ))
        db_session.add(WorkflowExecutionLog(
            execution_id="exec-1",
            workflow_id="wf-1",
            step_id="s1",
            step_type="action",
            status="completed",
        ))
        db_session.commit()

        service = StudentLearningService(db_session)
        result = service.observe_workspace(student.id, workspace_id="default", limit=10)

        assert result["status"] == "ok"
        assert result["observations_absorbed"] == 2
        db_session.refresh(student)
        log = student.configuration["learning"]["log"]
        assert {e["observation_type"] for e in log} == {"hitl_approval", "workflow_execution"}


class TestTeachGovernance:
    """Teaching must be permitted regardless of the teacher's own maturity."""

    @pytest.mark.parametrize("teacher_status", ["student", "intern", "supervised", "autonomous"])
    def test_teach_student_allowed_at_every_maturity(self, db_session, teacher_status):
        teacher = _make_student(db_session, status=teacher_status)
        gov = AgentGovernanceService(db_session, workspace_id="default", tenant_id="default")

        decision = gov.can_perform_action(agent_id=teacher.id, action_type="teach_student")

        assert decision["allowed"] is True, f"teach_student must be allowed at {teacher_status}: {decision}"

    def test_suggest_still_requires_intern(self, db_session):
        """The meta agent's INTER floor for suggestions stays enforced."""
        student = _make_student(db_session, status="student")
        intern = _make_student(db_session, status="intern")
        gov = AgentGovernanceService(db_session, workspace_id="default", tenant_id="default")

        assert gov.can_perform_action(agent_id=student.id, action_type="suggest")["allowed"] is False
        assert gov.can_perform_action(agent_id=intern.id, action_type="suggest")["allowed"] is True


class TestWorkTimeLessons:
    """Lessons are PERMANENT training: get_agent_lessons/format_lessons_block
    are the work-time half — they must return what was taught (including for
    graduated agents) so chat, canvas edits, and task execution can apply it."""

    def test_returns_teacher_lessons_newest_first(self, db_session):
        agent = _make_student(db_session)
        service = StudentLearningService(db_session)
        service.learn_from_teacher(agent.id, "atom_main", "first lesson", topic="email")
        service.learn_from_teacher(agent.id, "atom_main", "second lesson", topic="tone")

        lessons = get_agent_lessons(db_session, agent.id)

        assert [l["lesson"] for l in lessons] == ["second lesson", "first lesson"]

    def test_lessons_survive_graduation(self, db_session):
        """Permanence: a graduated (non-STUDENT) agent keeps and serves its
        taught lessons — training must persist into autonomy. learn_from_
        teacher refuses non-students, so seed the log directly."""
        agent = _make_student(db_session, status="intern")
        agent.configuration = {
            "learning": {"log": [
                {"source": "teacher", "teacher_agent_id": "atom_main",
                 "topic": "invoices", "lesson": "Always double-check invoice totals",
                 "learned_at": "2026-08-01T00:00:00+00:00"},
            ]}
        }
        db_session.commit()

        lessons = get_agent_lessons(db_session, agent.id)

        assert len(lessons) == 1
        assert lessons[0]["lesson"] == "Always double-check invoice totals"

    def test_human_correction_observations_count_but_plain_events_do_not(self, db_session):
        agent = _make_student(db_session)
        agent.configuration = {"learning": {"log": [
            {"source": "observation", "observation_type": "human_correction",
             "summary": "Supervisor rewrote the greeting formally", "details": {},
             "learned_at": "2026-08-01T00:00:00+00:00"},
            {"source": "observation", "observation_type": "hitl_approval",
             "summary": "A human approved send_email", "details": {},
             "learned_at": "2026-08-02T00:00:00+00:00"},
        ]}}
        db_session.commit()

        lessons = get_agent_lessons(db_session, agent.id)

        assert [l.get("observation_type") for l in lessons] == ["human_correction"]

    def test_query_relevance_orders_lessons(self, db_session):
        agent = _make_student(db_session)
        agent.configuration = {"learning": {"log": [
            {"source": "teacher", "topic": "email", "lesson": "Sign every email with the client's name",
             "learned_at": "2026-08-02T00:00:00+00:00"},
            {"source": "teacher", "topic": "pricing", "lesson": "Quotes over $50k need supervisor review",
             "learned_at": "2026-08-01T00:00:00+00:00"},
        ]}}
        db_session.commit()

        lessons = get_agent_lessons(db_session, agent.id, query="draft a pricing quote for the client")

        assert lessons[0]["lesson"] == "Quotes over $50k need supervisor review"

    def test_missing_agent_returns_empty(self, db_session):
        assert get_agent_lessons(db_session, "nope") == []

    def test_corrupt_configuration_returns_empty(self, db_session):
        agent = _make_student(db_session)
        agent.configuration = {"learning": {"log": "not-a-list"}}
        db_session.commit()
        assert get_agent_lessons(db_session, agent.id) == []

    def test_format_block_frames_permanence_and_caps_length(self):
        lessons = [
            {"topic": "tone", "lesson": "x" * 500},
            {"topic": "email", "lesson": "Sign with the client's name"},
        ]
        block = format_lessons_block(lessons)

        assert "PERMANENT INSTRUCTIONS" in block
        assert "[tone]" in block and "[email]" in block
        assert len(block) < 1600 + 400  # per-lesson trim + header headroom
        # the over-budget first lesson is trimmed, not dropped
        assert "…" in block

    def test_format_block_empty_without_lessons(self):
        assert format_lessons_block([]) == ""
        assert format_lessons_block([{"topic": "t", "lesson": ""}]) == ""


class TestUserStyleLesson:
    """Agents sending email on a user's behalf learn THAT user's formatting
    (signature, fonts, closing style) as a PERMANENT user_style lesson —
    refreshed in place, never accumulated, included at work time."""

    def test_learn_user_style_creates_permanent_entry(self, db_session):
        agent = _make_student(db_session)
        out = learn_user_style(db_session, agent.id, "user-1", "<b>Rish M.</b>")
        assert out["status"] == "ok"

        db_session.refresh(agent)
        lessons = get_agent_lessons(db_session, agent.id)
        assert any(
            l.get("observation_type") == "user_style"
            and (l.get("details") or {}).get("signature_html") == "<b>Rish M.</b>"
            for l in lessons
        )

    def test_learn_user_style_refreshes_instead_of_accumulating(self, db_session):
        agent = _make_student(db_session)
        learn_user_style(db_session, agent.id, "user-1", "<b>old style</b>")
        learn_user_style(db_session, agent.id, "user-1", "<b>new style</b>")
        learn_user_style(db_session, agent.id, "user-2", "<i>other user</i>")

        db_session.refresh(agent)
        log = agent.configuration["learning"]["log"]
        style_entries = [e for e in log if e.get("observation_type") == "user_style"]
        assert len(style_entries) == 2  # one per user
        user1 = [e for e in style_entries if e["details"]["user_id"] == "user-1"]
        assert len(user1) == 1 and user1[0]["details"]["signature_html"] == "<b>new style</b>"

    def test_user_style_renders_in_work_time_block(self, db_session):
        agent = _make_student(db_session)
        learn_user_style(db_session, agent.id, "user-1", "<b>Sig</b>")

        lessons = get_agent_lessons(db_session, agent.id)
        block = format_lessons_block(lessons)
        assert "PERMANENT INSTRUCTIONS" in block
        assert "Email style" in block


class TestTeachingCircuit:
    """A teaching point must travel the WHOLE circuit: journal + confidence,
    pedagogy mastery (so scaffolding withdraws), and — for supervisor
    corrections on canvas work — the permanent work-time lesson block."""

    def test_teacher_lesson_records_mastery_exposure(self, db_session):
        student = _make_student(db_session)
        service = StudentLearningService(db_session)

        service.learn_from_teacher(
            student.id, "human_supervisor", "Keep refund emails short", topic="refunds"
        )

        db_session.refresh(student)
        pedagogy = student.configuration["pedagogy"]
        assert pedagogy["mastery"]["refunds"] == 1
        assert pedagogy["mastery_history"][0]["positive"] is True
        assert "Keep refund emails short" in pedagogy["mastery_history"][0]["note"]

    def test_mastery_failure_never_breaks_lesson_intake(self, db_session, monkeypatch):
        """Journal + confidence are the contract — pedagogy tracking is
        best-effort and must not fail the lesson."""
        student = _make_student(db_session)
        service = StudentLearningService(db_session)

        def _boom(*args, **kwargs):
            raise RuntimeError("pedagogy down")

        monkeypatch.setattr(
            "core.agent_pedagogy.PedagogicalFramework.record_mastery_exposure", _boom
        )
        result = service.learn_from_teacher(student.id, "human_supervisor", "still lands")
        assert result["status"] == "ok"

    def test_canvas_correction_becomes_permanent_work_time_lesson(self, db_session):
        """The strongest teaching signal — the supervisor fixing the hire's
        work ON the canvas — must land in the journal as a human_correction
        observation, which IS injected at work time (chat, edits, tasks),
        not just stored as an RLHF row."""
        from core.models import CanvasContext
        from services.canvas_context_service import CanvasContextService

        student = _make_student(db_session)
        db_session.add(CanvasContext(
            canvas_id="cv-circ",
            tenant_id="default",
            canvas_type="email",
            user_id="user-1",
            agent_id=student.id,
            user_corrections=[],
            session_history=[],
            current_state={},
            user_preferences={},
        ))
        db_session.commit()

        svc = CanvasContextService(db_session)
        assert svc.record_user_correction(
            "cv-circ", "user-1",
            original_action={"type": "canvas_edit", "content": "Hey there"},
            corrected_action={"type": "canvas_edit", "content": "Hi Mark,"},
            context_info="greeting",
        ) is True

        db_session.refresh(student)
        log = student.configuration["learning"]["log"]
        assert log[-1]["source"] == "observation"
        assert log[-1]["observation_type"] == "human_correction"
        # Permanent: retrieved by the work-time lesson lookup
        lessons = get_agent_lessons(db_session, student.id, query="greeting")
        assert any("corrected" in str(l.get("summary", "")).lower() for l in lessons)

    def test_teacher_lesson_invalidates_governance_cache(self, db_session, monkeypatch):
        """Confidence moved → any cached governance snapshot (trigger path,
        5-min maturity TTL) must drop NOW, so the next gated decision sees
        the updated agent — not a 5-minute-stale one."""
        student = _make_student(db_session)
        service = StudentLearningService(db_session)
        invalidated = []

        class _Cache:
            def invalidate_agent(self, agent_id):
                invalidated.append(agent_id)

        monkeypatch.setattr(
            "core.governance_cache.get_governance_cache", lambda: _Cache()
        )
        service.learn_from_teacher(student.id, "human_supervisor", "real-time lesson")
        assert invalidated == [student.id]

    def test_canvas_correction_invalidates_governance_cache(self, db_session, monkeypatch):
        from core.models import CanvasContext
        from services.canvas_context_service import CanvasContextService

        student = _make_student(db_session)
        db_session.add(CanvasContext(
            canvas_id="cv-rt",
            tenant_id="default",
            canvas_type="email",
            user_id="user-1",
            agent_id=student.id,
            user_corrections=[],
            session_history=[],
            current_state={},
            user_preferences={},
        ))
        db_session.commit()
        invalidated = []

        class _Cache:
            def invalidate_agent(self, agent_id):
                invalidated.append(agent_id)

        monkeypatch.setattr(
            "core.governance_cache.get_governance_cache", lambda: _Cache()
        )
        svc = CanvasContextService(db_session)
        assert svc.record_user_correction(
            "cv-rt", "user-1",
            original_action={"type": "canvas_edit", "content": "a"},
            corrected_action={"type": "canvas_edit", "content": "b"},
            context_info="tone",
        ) is True
        # The journal write AND the correction flow each drop the snapshot —
        # idempotent, so once is enough to observe; both firing is fine.
        assert set(invalidated) == {student.id}
