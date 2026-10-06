"""Do-NOT-route counterexamples for calculation follow-up binding.

Owner directive (2026-10-06): "Do not route every subsequent message into
calculation. Pin these counterexamples: unrelated question, cancellation,
topic change, ambiguous answer, multiple pending calculations, and changed
teaching."

The positive paths (answer resumes the recorded calculation; recalculate
rebinds established inputs; partial answers keep asking) are pinned in
test_calculate_toolplan_boundary.py. THIS file pins the negatives: while a
pending-input question is open, ordinary messages must NOT be pulled into
the calculate lane, other conversations' pendings must not leak, and a
completion after changed teaching must carry the CURRENT policy version —
never the stale one.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager

os.environ.setdefault("ATOM_TASK_LIFECYCLE_ENABLED", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import AgentRegistry, Base, User

LESSON_150 = {
    "id": "counter-lesson-150", "source": "teacher",
    "teacher_agent_id": "human_supervisor", "topic": "service estimates",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 150 per hour."),
    "scope": "global",
}
LESSON_200 = {
    **LESSON_150, "id": "counter-lesson-200",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 200 per hour."),
}

Q_ASK = "Estimate this service job using our taught rates."

_STATE = {}


@pytest.fixture()
def world():
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    import core.database as dbmod
    old = dbmod.get_db_session
    dbmod.get_db_session = scratch
    with scratch() as db:
        db.add(User(id="u-cx", email="cx@example.com", first_name="C",
                    last_name="X", role="user", status="active"))
        db.add(AgentRegistry(
            id="cx-agent", name="cx agent", status="active",
            category="trainee", module_path="agents.cx",
            class_name="CxAgent",
            configuration={"learning": {"log": [LESSON_150]}}))
    _STATE["factory"] = factory
    yield {"user": "u-cx", "ws": "default"}
    dbmod.get_db_session = old
    engine.dispose()


def _plan(query):
    from core.chat_tool_planner import ToolPlan
    return ToolPlan(use_tool=True, service="datasets.calculate", query=query)


def _run(plan, conv, user="u-cx"):
    from core.chat_tool_planner import execute_tool_plan
    return asyncio.run(execute_tool_plan(
        plan, user, tenant_id="default",
        context={"conversation_id": conv, "workspace_id": "default"}))


def _ask(conv, query=Q_ASK, user="u-cx"):
    """Open the pending-input question on `conv` (returns the block)."""
    return _run(_plan(query), conv, user)


def _followup(conv, message, user="u-cx"):
    from core.pricing_calculation import calculate_followup_from_query
    return asyncio.run(calculate_followup_from_query(
        message, user, "default", conversation_id=conv))


def _dispatch(message, conv, user="u-cx"):
    from core.pricing_calculation import _calc_followup_dispatch
    return _calc_followup_dispatch(message, conv, "default")


def _job_snapshot(conv):
    """(n_calculate_ops, n_open_pending_questions) for the conversation."""
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=_STATE["factory"]),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=_STATE["factory"]))
    task = tl.find_active_task(conv)
    if not task:
        return (0, 0)
    ops = [o for o in (task.get("operations") or [])
           if o.get("operation_type") == "calculate"]
    pend = [q for q in ((task.get("task_revision") or {}).get("unresolved")
                        or [])
            if str(q.get("status") or "") == "open"
            and (q.get("inputs") or {}).get("pending_calc_inputs")]
    return (len(ops), len(pend))


def _requires_calc(message):
    from core.pricing_calculation import message_requires_calculation
    return message_requires_calculation(message)


# -- 1. unrelated question ----------------------------------------------
def test_unrelated_question_not_routed(world):
    _ask("cx-unrelated")
    msg = "What's the capital of France?"
    assert _requires_calc(msg) is False
    assert _dispatch(msg, "cx-unrelated") is False
    assert _followup("cx-unrelated", msg) is None
    assert _job_snapshot("cx-unrelated") == (0, 1)  # pending intact


# -- 2. cancellation -----------------------------------------------------
def test_cancellation_not_routed(world):
    _ask("cx-cancel")
    msg = "Actually, cancel that estimate — we won't need it."
    assert _requires_calc(msg) is False
    assert _dispatch(msg, "cx-cancel") is False
    assert _followup("cx-cancel", msg) is None
    # the pending question is NOT silently consumed
    assert _job_snapshot("cx-cancel")[1] == 1


# -- 3. topic change -----------------------------------------------------
def test_topic_change_not_routed(world):
    _ask("cx-topic")
    msg = "Let's talk about the delivery schedule instead."
    assert _requires_calc(msg) is False
    assert _dispatch(msg, "cx-topic") is False
    assert _followup("cx-topic", msg) is None
    assert _job_snapshot("cx-topic") == (0, 1)


# -- 4. ambiguous answer -------------------------------------------------
def test_ambiguous_answer_not_routed(world):
    _ask("cx-ambiguous")
    msg = "hmm, maybe twenty-ish hours? not sure yet"
    assert _dispatch(msg, "cx-ambiguous") is False
    assert _followup("cx-ambiguous", msg) is None
    assert _job_snapshot("cx-ambiguous") == (0, 1)


# -- 5. multiple pending calculations ------------------------------------
def test_other_conversations_pending_does_not_leak(world):
    """Two conversations, each with its own open pending question: one
    conversation's answer must complete ONLY its own calculation — no
    cross-conversation record reuse or question consumption."""
    _ask("cx-multi-a")
    _ask("cx-multi-b")
    block = _followup("cx-multi-a", "17.5 hours, no materials")
    assert block and "2625" in block
    ops_a, pend_a = _job_snapshot("cx-multi-a")
    assert ops_a == 1 and pend_a == 0        # A completed, its question closed
    ops_b, pend_b = _job_snapshot("cx-multi-b")
    assert ops_b == 0 and pend_b == 1        # B untouched


# -- 6. changed teaching --------------------------------------------------
def test_completion_after_changed_teaching_uses_current_policy(world):
    """The pending question was recorded under v(rate=150). Teaching
    changes (rate=200) before the owner answers. The resumed calculation
    must carry the CURRENT content-derived policy version and value —
    never silently complete the stale policy."""
    _ask("cx-teaching")
    import core.database as dbmod
    with dbmod.get_db_session() as db:
        db.query(AgentRegistry).filter(
            AgentRegistry.id == "cx-agent").update(
            {"configuration": {"learning": {"log": [LESSON_200]}}})
    block = _followup("cx-teaching", "17.5 hours, no materials")
    assert block and "3500" in block
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=_STATE["factory"]),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=_STATE["factory"]))
    task = tl.find_active_task("cx-teaching")
    ops = [o for o in (task.get("operations") or [])
           if o.get("operation_type") == "calculate"]
    assert len(ops) == 1
    rec = ops[0].get("calculation") or {}
    # the current version, derived from the rate-200 lesson content
    ver = str(rec.get("policy_version"))
    assert ver and ver != "unknown"
    from core.pricing_calculation import parse_taught_expressions
    fresh = parse_taught_expressions([LESSON_200])[0]
    assert ver == str(fresh.get("version"))
    assert str(((rec.get("proposed") or {}).get("amount"))).startswith("3500")


# -- 4b. two pending calculations in ONE conversation ---------------
def test_same_conversation_two_pendings_is_ambiguous(world):
    """Two open pending-input questions in the SAME conversation: a
    bare answer cannot be attributed to one of them — the deterministic
    binding must NOT route, and neither pending is consumed.

    The second pending is recorded through the lane's own recording
    function with a DISTINCT item (same-item questions dedupe by
    (item, text) — a repeated identical ask is tracked, never a second
    open question)."""
    _ask("cx-amb-1")
    from core.pricing_calculation import (_open_pending_questions,
                                          _record_pending_calc_inputs)
    _record_pending_calc_inputs(
        "cx-amb-1", "default", "Freight estimate", ["weight"],
        {"rate": "0.5"}, "weight * rate", "v-freight-1")
    assert len(_open_pending_questions("cx-amb-1", "default")) == 2
    msg = "17.5 hours, no materials"
    assert _dispatch(msg, "cx-amb-1") is False
    assert _followup("cx-amb-1", msg) is None
    # neither pending was consumed, no calculation was recorded
    assert len(_open_pending_questions("cx-amb-1", "default")) == 2
    assert _job_snapshot("cx-amb-1")[0] == 0


# -- 5b. teaching-change disclosure -----------------------------------
def test_changed_taught_default_is_disclosed(world):
    """One identifiable CURRENT policy version; explicit user inputs
    preserved; when a changed taught default moved an input the owner
    did not state, the completion DISCLOSES it — never old defaults
    under a new version label."""
    _ask("cx-disclose")
    import core.database as dbmod
    with dbmod.get_db_session() as db:
        db.query(AgentRegistry).filter(
            AgentRegistry.id == "cx-agent").update(
            {"configuration": {"learning": {"log": [LESSON_200]}}})
    block = _followup("cx-disclose", "17.5 hours, no materials")
    assert block and "3500" in block
    # the disclosure names the moved default and the direction
    assert "taught rate changed" in block
    assert "150" in block and "200" in block
    assert "current teaching" in block
    # user-stated inputs survived the teaching change verbatim
    assert "hours=17.5" in block and "materials=0" in block
    # the record carries ONE version — the CURRENT one
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=_STATE["factory"]),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=_STATE["factory"]))
    task = tl.find_active_task("cx-disclose")
    ops = [o for o in (task.get("operations") or [])
           if o.get("operation_type") == "calculate"]
    assert len(ops) == 1
    rec = ops[0].get("calculation") or {}
    from core.pricing_calculation import parse_taught_expressions
    fresh = parse_taught_expressions([LESSON_200])[0]
    assert str(rec.get("policy_version")) == str(fresh.get("version"))
    assert str(((rec.get("proposed") or {}).get("amount"))
               ).startswith("3500")
