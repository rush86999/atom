"""Lesson SCOPE — some teaching points are goal-specific, others general.

The gap this locks: every permanent lesson used to apply to ALL of an agent's
work. A supervisor coaching one long goal ("confirm the FX rate before asking
me" — true for that deal, noise everywhere else) had no way to say so, and a
rule taught in chat had no way to say "only for this goal".

Scope is data on the lesson, and the READER decides:
- ``global`` (default, and what every pre-scope row reads as) — applies to
  chat, canvas edits, every task and every goal;
- ``goal`` — applies only while working ``goal_id``.

Work-time readers omit ``goal_id`` (chat, canvas edits, ordinary task runs) and
therefore see global guidance only; the goal-run router and goal-step agent
pass the goal they are working.
"""

import contextlib
import uuid

import pytest

from core.models import AgentRegistry
from core.student_learning_service import (
    deliver_teacher_lesson,
    get_agent_lessons,
    list_agent_lessons,
)


def _agent(db, status="intern"):
    agent = AgentRegistry(
        id=f"scope-{uuid.uuid4().hex[:8]}",
        name="Scoped Learner", category="sales", description="t",
        module_path="core.generic_agent", class_name="GenericAgent",
        status=status, confidence_score=0.5, configuration={},
        capabilities=["send_email"], workspace_id="default", tenant_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _texts(lessons):
    return [l.get("lesson") or l.get("summary") for l in lessons]


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class TestLessonScope:
    def test_global_lesson_applies_everywhere(self, db_session):
        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "Always CC the lead")

        # No goal (chat / canvas / task run) → applies.
        assert "Always CC the lead" in _texts(get_agent_lessons(db_session, agent.id))
        # Working any goal → also applies.
        assert "Always CC the lead" in _texts(
            get_agent_lessons(db_session, agent.id, goal_id="goal-1"))

    def test_goal_scoped_lesson_applies_only_to_its_goal(self, db_session):
        agent = _agent(db_session)
        deliver_teacher_lesson(
            db_session, agent.id, "Confirm the FX rate before asking me",
            scope="goal", goal_id="goal-1",
        )

        # Working THAT goal → applies.
        assert "Confirm the FX rate before asking me" in _texts(
            get_agent_lessons(db_session, agent.id, goal_id="goal-1"))
        # Ordinary work (no goal) → must NOT leak.
        assert "Confirm the FX rate before asking me" not in _texts(
            get_agent_lessons(db_session, agent.id))
        # A DIFFERENT goal → must NOT leak.
        assert "Confirm the FX rate before asking me" not in _texts(
            get_agent_lessons(db_session, agent.id, goal_id="goal-2"))

    def test_goal_scoped_lesson_rides_alongside_global_ones(self, db_session):
        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "Always sign off warmly")
        deliver_teacher_lesson(db_session, agent.id, "Use the Q3 price book",
                               scope="goal", goal_id="goal-1")

        working = _texts(get_agent_lessons(db_session, agent.id, goal_id="goal-1"))
        assert set(working) == {"Always sign off warmly", "Use the Q3 price book"}

        elsewhere = _texts(get_agent_lessons(db_session, agent.id, goal_id="goal-2"))
        assert elsewhere == ["Always sign off warmly"]

    def test_pre_scope_rows_read_as_global(self, db_session):
        """Rows written before scope existed carry no field — they must stay
        global (the historical behaviour), not vanish."""
        agent = _agent(db_session)
        from sqlalchemy.orm import attributes
        agent.configuration = {"learning": {"log": [{
            "id": "legacy-1", "source": "teacher", "topic": "general",
            "lesson": "Legacy rule with no scope field",
            "learned_at": "2026-01-01T00:00:00+00:00",
        }]}}
        attributes.flag_modified(agent, "configuration")
        db_session.commit()

        assert "Legacy rule with no scope field" in _texts(
            get_agent_lessons(db_session, agent.id))
        assert "Legacy rule with no scope field" in _texts(
            get_agent_lessons(db_session, agent.id, goal_id="goal-1"))


# ---------------------------------------------------------------------------
# Dedup across scopes
# ---------------------------------------------------------------------------

class TestScopeDedup:
    def test_same_rule_different_goals_is_not_a_duplicate(self, db_session):
        """Coaching goal A with a phrase must not block goal B."""
        agent = _agent(db_session)
        first = deliver_teacher_lesson(db_session, agent.id, "Ask before discounting",
                                       scope="goal", goal_id="goal-1")
        second = deliver_teacher_lesson(db_session, agent.id, "Ask before discounting",
                                        scope="goal", goal_id="goal-2")

        assert first["status"] == "ok"
        assert second["status"] == "ok"
        # Each goal's view carries its own copy (and listing with no goal_id
        # deliberately hides both — that is the isolation this test is about).
        g1 = [r["text"] for r in list_agent_lessons(db_session, agent.id,
                                                    goal_id="goal-1", limit=50)]
        g2 = [r["text"] for r in list_agent_lessons(db_session, agent.id,
                                                    goal_id="goal-2", limit=50)]
        assert g1 == ["Ask before discounting"]
        assert g2 == ["Ask before discounting"]
        assert list_agent_lessons(db_session, agent.id, limit=50) == []

    def test_repeat_of_the_same_goal_lesson_is_a_duplicate(self, db_session):
        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "Ask before discounting",
                               scope="goal", goal_id="goal-1")
        again = deliver_teacher_lesson(db_session, agent.id, "Ask before discounting",
                                       scope="goal", goal_id="goal-1")
        assert again["status"] == "duplicate"

    def test_a_global_rule_covers_a_goal_scoped_repeat(self, db_session):
        """Once it is global it already applies everywhere — adding a
        goal-scoped copy would be redundant."""
        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "Never quote below cost")
        covered = deliver_teacher_lesson(db_session, agent.id, "Never quote below cost",
                                         scope="goal", goal_id="goal-1")
        assert covered["status"] == "duplicate"

    def test_goal_scoped_repeat_is_covered_by_an_existing_global_rule(self, db_session):
        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "Never quote below cost",
                               scope="goal", goal_id="goal-1")
        promoted = deliver_teacher_lesson(db_session, agent.id, "Never quote below cost")
        assert promoted["status"] == "ok"   # widening scope is allowed
        assert "Never quote below cost" in _texts(get_agent_lessons(db_session, agent.id))


# ---------------------------------------------------------------------------
# Display reader + the goal-run router
# ---------------------------------------------------------------------------

class TestLessonDisplayAndGoalRunRetrieval:
    def test_list_agent_lessons_reports_scope(self, db_session):
        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "General rule")
        deliver_teacher_lesson(db_session, agent.id, "Deal-specific rule",
                               scope="goal", goal_id="goal-1")

        rows = list_agent_lessons(db_session, agent.id, goal_id="goal-1", limit=20)
        by_text = {r["text"]: r for r in rows}
        assert by_text["General rule"]["scope"] == "global"
        assert by_text["Deal-specific rule"]["scope"] == "goal"
        assert by_text["Deal-specific rule"]["goal_id"] == "goal-1"

        # A different goal's view keeps the global rule, drops the deal one.
        other = list_agent_lessons(db_session, agent.id, goal_id="goal-2", limit=20)
        assert [r["text"] for r in other] == ["General rule"]

    def test_goal_run_router_sees_its_goal_lessons_and_not_another_goals(
        self, db_session, monkeypatch
    ):
        """The router prompt is the decision-time injection point: a lesson
        taught against THIS goal must reach it, and another goal's
        deal-specific lesson must not."""
        from core.goals.goal_run_router import GoalRunRouter

        agent = _agent(db_session)
        deliver_teacher_lesson(db_session, agent.id, "Always log the discount reason")
        deliver_teacher_lesson(db_session, agent.id, "Use the Q3 price book",
                               scope="goal", goal_id="goal-1")
        deliver_teacher_lesson(db_session, agent.id, "Escalate to Dana",
                               scope="goal", goal_id="goal-2")

        monkeypatch.setattr(
            "core.database.get_db_session",
            lambda: contextlib.nullcontext(db_session),
        )
        router = GoalRunRouter(tenant_id="default")
        advisory = router._role_context(
            {"id": "run-1", "goal_id": "goal-1", "agent_id": agent.id}
        )

        assert "Always log the discount reason" in advisory   # global
        assert "Use the Q3 price book" in advisory            # this goal
        assert "Escalate to Dana" not in advisory             # another goal


# ---------------------------------------------------------------------------
# Chat: explicit goal context, then inference
# ---------------------------------------------------------------------------
# A rule taught while an agent works a long goal is usually ABOUT that goal.
# Explicit context (chat opened from a run) is deterministic; inference is
# suggestion-grade with a hallucination guard and a confidence floor.

def _goal(db, goal_id="goal-1", title="Prepare a quote for the Acme lead"):
    from core.models import GoalObjective
    row = GoalObjective(
        id=goal_id, tenant_id="default", workspace_id="default",
        title=title, status="active",
    )
    db.add(row)
    db.commit()
    return row


def _run(db, goal_id="goal-1", agent_id="agent-1", run_id="run-1",
         status="active"):
    from core.models import GoalRun
    row = GoalRun(
        id=run_id, tenant_id="default", workspace_id="default",
        goal_id=goal_id, agent_id=agent_id, status=status,
    )
    db.add(row)
    db.commit()
    return row


class TestGoalContextResolution:
    def test_run_gives_its_goal_and_title(self, db_session):
        from core.chat_teaching import goal_context_for_run

        _goal(db_session)
        _run(db_session)

        ctx = goal_context_for_run(db_session, "run-1")
        assert ctx == {"goal_id": "goal-1",
                       "title": "Prepare a quote for the Acme lead"}

    def test_unknown_run_resolves_to_nothing(self, db_session):
        from core.chat_teaching import goal_context_for_run
        assert goal_context_for_run(db_session, "nope") is None
        assert goal_context_for_run(db_session, None) is None

    def test_only_live_goals_are_inference_candidates(self, db_session):
        """You cannot scope new coaching to a goal whose run has finished."""
        from core.chat_teaching import active_goals_for_agent

        _goal(db_session, "goal-live", "Acme quote")
        _goal(db_session, "goal-done", "Old won deal")
        _run(db_session, "goal-live", "agent-1", "run-live", status="active")
        _run(db_session, "goal-done", "agent-1", "run-done", status="achieved")
        _run(db_session, "goal-live", "agent-2", "run-other-agent", status="waiting")

        ids = [c["goal_id"] for c in active_goals_for_agent(db_session, "agent-1")]
        assert ids == ["goal-live"]

    def test_no_live_goals_means_no_candidates(self, db_session):
        from core.chat_teaching import active_goals_for_agent
        assert active_goals_for_agent(db_session, "agent-with-nothing") == []


class TestLessonGoalInference:
    """The LLM only ever NARROWS a lesson, and only when it is confident."""

    def _patch_llm(self, monkeypatch, returned):
        async def _fake(llm_service, **kwargs):
            return returned
        monkeypatch.setattr(
            "core.llm.pinned_planning.pinned_structured_call", _fake)

    def _match(self, goal_id, confidence):
        from core.chat_teaching import LessonGoalMatch
        return LessonGoalMatch(goal_id=goal_id, confidence=confidence, reason="r")

    CANDIDATES = [{"goal_id": "goal-1", "title": "Acme quote"}]

    @pytest.mark.asyncio
    async def test_confident_match_scopes_to_that_goal(self, monkeypatch):
        from core.chat_teaching import infer_lesson_goal
        self._patch_llm(monkeypatch, self._match("goal-1", 0.9))

        out = await infer_lesson_goal(
            object(), lesson="Use the Q3 price book", candidates=self.CANDIDATES)
        assert out["goal_id"] == "goal-1"
        assert out["confidence"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_low_confidence_is_left_general(self, monkeypatch):
        from core.chat_teaching import infer_lesson_goal
        self._patch_llm(monkeypatch, self._match("goal-1", 0.4))

        assert await infer_lesson_goal(
            object(), lesson="Be concise", candidates=self.CANDIDATES) is None

    @pytest.mark.asyncio
    async def test_null_goal_is_left_general(self, monkeypatch):
        from core.chat_teaching import infer_lesson_goal
        self._patch_llm(monkeypatch, self._match(None, 0.99))

        assert await infer_lesson_goal(
            object(), lesson="Always CC the lead", candidates=self.CANDIDATES) is None

    @pytest.mark.asyncio
    async def test_a_goal_we_never_offered_is_ignored(self, monkeypatch):
        from core.chat_teaching import infer_lesson_goal
        self._patch_llm(monkeypatch, self._match("goal-invented", 0.99))

        assert await infer_lesson_goal(
            object(), lesson="Use the Q3 price book",
            candidates=self.CANDIDATES) is None

    @pytest.mark.asyncio
    async def test_no_candidates_or_no_llm_never_calls_out(self):
        from core.chat_teaching import infer_lesson_goal
        assert await infer_lesson_goal(
            object(), lesson="x", candidates=[]) is None
        assert await infer_lesson_goal(
            None, lesson="x", candidates=self.CANDIDATES) is None

    @pytest.mark.asyncio
    async def test_a_provider_failure_is_swallowed(self, monkeypatch):
        from core.chat_teaching import infer_lesson_goal

        async def _boom(llm_service, **kwargs):
            raise RuntimeError("provider down")
        monkeypatch.setattr(
            "core.llm.pinned_planning.pinned_structured_call", _boom)

        assert await infer_lesson_goal(
            object(), lesson="x", candidates=self.CANDIDATES) is None


class TestTeachWithGoalScope:
    def test_teaching_with_a_goal_records_that_scope(self, db_session):
        from core.chat_teaching import teach_from_chat

        agent = _agent(db_session)
        notice = teach_from_chat(
            db_session, agent_id=agent.id, lesson="Use the Q3 price book",
            goal_id="goal-1", goal_title="Acme quote",
        )

        assert notice["status"] == "saved"
        assert notice["scope"] == "goal"
        assert notice["goal_id"] == "goal-1"
        assert notice["goal_title"] == "Acme quote"
        assert "Acme quote" in notice["message"]
        # Scoped to the goal — not visible to ordinary work.
        assert get_agent_lessons(db_session, agent.id) == []

    def test_inferred_scope_says_so_and_offers_the_way_out(self, db_session):
        from core.chat_teaching import teach_from_chat

        agent = _agent(db_session)
        notice = teach_from_chat(
            db_session, agent_id=agent.id, lesson="Use the Q3 price book",
            goal_id="goal-1", goal_title="Acme quote", goal_inferred=True,
        )

        assert notice["goal_inferred"] is True
        assert "inferred" in notice["message"].lower()
        assert "all of their work" in notice["message"]

    def test_no_goal_keeps_the_lesson_global(self, db_session):
        from core.chat_teaching import teach_from_chat

        agent = _agent(db_session)
        notice = teach_from_chat(
            db_session, agent_id=agent.id, lesson="Always CC the lead")

        assert notice["scope"] == "global"
        assert notice["goal_id"] is None
        assert "Always CC the lead" in _texts(get_agent_lessons(db_session, agent.id))
