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


def _open_qs(conv):
    from core.pricing_calculation import _open_pending_questions
    return _open_pending_questions(conv, "default")


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


# -- timeout-to-follow-up boundary (owner directive 2026-10-07) --------
def test_failed_calc_ask_retains_pending_context_for_the_answer(world):
    """A calculation-shaped ask whose turn FAILED before the calculate
    lane ran (provider distress / timeout) must still record the durable
    pending-calculation context (policy/version, known inputs, missing
    fields). The owner's NEXT message then binds to unfinished
    calculation work and the ENGINE executes — teaching-based narrated
    arithmetic cannot substitute."""
    import asyncio
    from core import pricing_calculation as pc

    conv = "cx-timeout-1"
    ok = pc.record_pending_for_failed_calc_ask(
        "Estimate this service job using our taught rates.",
        "u-cx", "default", conv)
    assert ok is True
    # the durable context: one open pending question with the taught
    # policy/version, the known default input, and the missing fields
    qs = _open_qs(conv)
    assert len(qs) == 1
    inputs = qs[0].get("inputs") or {}
    assert sorted(inputs.get("missing") or []) == ["hours", "materials"]
    assert (inputs.get("bound") or {}).get("rate") == "150"
    assert inputs.get("expr") == "ROUNDUP(hours * rate + materials, 0)"
    assert inputs.get("policy_version")

    # the ANSWER turn binds and the engine executes + records
    block = _followup(conv, "17.5 hours, no materials")
    assert block and "2625" in block
    assert "the model did not compute this" in block
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=_STATE["factory"]),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=_STATE["factory"]))
    task = tl.find_active_task(conv)
    calc_ops = [o for o in (task.get("operations") or [])
                if o.get("operation_type") == "calculate"]
    assert len(calc_ops) == 1
    assert calc_ops[0].get("status") == "applied"
    assert str((((calc_ops[0].get("calculation") or {})
                 .get("proposed") or {}).get("amount"))).startswith("2625")
    # the pending question closed with the completion
    assert _open_qs(conv) == []


def test_failed_ask_recording_is_idempotent_and_scoped(world):
    """Re-recording on a second failed attempt does not duplicate the
    pending question (the lane's own question stands), and an
    unrelated-shape failed ask records nothing."""
    from core import pricing_calculation as pc
    conv = "cx-timeout-2"
    assert pc.record_pending_for_failed_calc_ask(
        "Estimate this service job using our taught rates.",
        "u-cx", "default", conv) is True
    assert pc.record_pending_for_failed_calc_ask(
        "Estimate this service job using our taught rates.",
        "u-cx", "default", conv) is False  # question already open
    assert pc.record_pending_for_failed_calc_ask(
        "What is the capital of France?", "u-cx", "default",
        "cx-timeout-3") is False
    assert _open_qs("cx-timeout-3") == []


# -- timeout wording rule (owner directive 2026-10-07) -----------------
def test_unrecorded_teaching_figure_is_the_false_shape():
    """The detector mirrors the acceptance gate: figure + teaching/
    formula authority with NO engine record and NO disclosure is the
    false shape; disclosed figures and bare non-calc turns are not."""
    from integrations.chat_orchestrator import (
        _calc_bound_turn, _reply_claims_unrecorded_teaching_figure)

    false1 = ("Using our taught service rate of $150/hr with no "
              "materials: 17.5 hrs × $150 = $2,625.00 — estimate "
              "**$2,625**.")
    false2 = ("**Service estimate: $2,625.00**\n\nUsing our taught "
              "formula — estimate = ROUNDUP(hours × rate + materials, 0) "
              "— per training guidance.")
    assert _reply_claims_unrecorded_teaching_figure(false1)
    assert _reply_claims_unrecorded_teaching_figure(false2)
    # disclosed figure — honest shape, left alone
    assert not _reply_claims_unrecorded_teaching_figure(
        "That would be $2,625 hand-computed — not run through the "
        "engine, so treat it as a draft only.")
    # refuse-with-retry — no figure, honest
    assert not _reply_claims_unrecorded_teaching_figure(
        "The live estimate lookup timed out and couldn't complete right "
        "now. Please try again in a moment.")
    # no authority claim
    assert not _reply_claims_unrecorded_teaching_figure(
        "The quote total is $2,902 per the vendor quote.")
    # turn binding: explicit asks and follow-ups bind; ordinary doesn't
    assert _calc_bound_turn(
        "Estimate this service job using our taught rates.", None, None)
    assert _calc_bound_turn("Recalculate — 12 hours.", "conv-x", "ws")
    assert not _calc_bound_turn("What is the capital of France?",
                                "conv-x", "ws")


def test_honest_replacement_wording_passes_the_gate():
    """The deterministic replacement the seam installs satisfies the
    acceptance gate: refuse-with-retry, no figure, no authority claim,
    WITH an explicit no-calculation-ran disclosure."""
    from integrations.chat_orchestrator import (
        _reply_claims_unrecorded_teaching_figure)

    replacement = (
        "I couldn't complete the calculation just now — no calculation "
        "was run, so there is no estimate to report yet. Please try "
        "again in a moment and I'll run the taught-rate calculation "
        "with your inputs.")
    assert not _reply_claims_unrecorded_teaching_figure(replacement)
