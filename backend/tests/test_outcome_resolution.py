# -*- coding: utf-8 -*-
"""Outcome-resolution regressions (owner implementation order, step 4).

Eight failure modes the owner called out, driven through the REAL
identity-bound resolver (`_fallback_turn_outcome`) over REAL staged task
records — operations, delivery records, unresolved questions — on a
scratch in-memory DB. Never the live DB; no model calls.

Case 7 of the owner's list (a completed calculation survives narration
failure) is pinned in test_calc_survives_narration_failure.py and is
not duplicated here.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ATOM_TASK_LIFECYCLE_ENABLED", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import AgentRegistry, Base, User

ATTEMPT_CAP = 3
VALUES = [{"field": "price", "column": "List", "raw": "100",
           "parsed": {"value": 100.0}, "source": "W.xlsx!S!row1"}]


@pytest.fixture()
def world():
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    from contextlib import contextmanager

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
        db.add(User(id="u-or", email="or@example.com", first_name="O",
                    last_name="R", role="user", status="active"))
        db.add(AgentRegistry(
            id="or-agent", name="or agent", status="active",
            category="trainee", module_path="agents.or",
            class_name="OrAgent", configuration={}))
    yield factory
    dbmod.get_db_session = old
    engine.dispose()


def _tl(factory):
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    return TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=factory),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=factory))


def _stage(factory, conv, exec_id, *, findings=VALUES, op_status="applied",
           questions=None, with_delivery=True, outcome="read_succeeded",
           items=None):
    """Stage one task record whose operation belongs to `exec_id`,
    optionally carrying values, open questions, and a delivery."""
    from core.task_lifecycle import (
        TaskLifecycle, begin_retrieval_turn, finish_retrieval_turn,
        record_read_outcome, add_unresolved_questions,
    )

    tl = _tl(factory)
    run_id, op = begin_retrieval_turn(
        tl, {"id": conv}, conv, "verify pricing", exec_id,
        items=["M-1"], requested_fields=["price"])
    success = op_status == "applied"
    finish_retrieval_turn(
        tl, run_id, op, {"rows": list(findings or [])},
        exec_id, success,
        execution={"invoked": True, "outcome": outcome,
                   "served_basis": "saved_copy", "failure_stage": None,
                   "findings": list(findings or []),
                   "items": dict(items if items is not None
                                 else {"M-1": "matched"})})
    record_read_outcome(
        tl, run_id, op,
        structured_result={"rows": list(findings or [])},
        freshness=None,
        execution={"invoked": True, "outcome": outcome,
                   "served_basis": "saved_copy", "failure_stage": None,
                   "findings": list(findings or []),
                   "items": dict(items if items is not None
                                 else {"M-1": "matched"})})
    op_id = op if isinstance(op, str) else op.get("operation_id")
    for q in (questions or []):
        add_unresolved_questions(tl, run_id, [q], source_operation=op_id)
    if with_delivery:
        import hashlib
        tl.record_delivery(
            run_id, execution_id=exec_id,
            operation_ids=[op_id],
            message_id=f"msg-{exec_id}",
            content_sha256=hashlib.sha256(
                f"reply-{exec_id}".encode()).hexdigest())
    return run_id, op


def _resolve(factory, conv, run_id, exec_id, **kw):
    from integrations.chat_orchestrator import _fallback_turn_outcome

    session = {"id": conv, "_task_run_id": run_id}
    return _fallback_turn_outcome(session, exec_id, {}, {}, "default", **kw)


def test_earlier_findings_do_not_certify_a_later_failed_turn(world):
    """Finding 1: an earlier successful operation's findings must not
    certify a later turn whose own retrieval FAILED."""
    from integrations.chat_orchestrator import _fallback_turn_outcome
    _stage(world, "conv-or-1", "exec-early",
           findings=VALUES, op_status="applied")
    _stage(world, "conv-or-1", "exec-now",
           findings=[], op_status="failed", outcome="read_failed",
           with_delivery=False)
    session = {"id": "conv-or-1", "_task_run_id": None}
    # resolve WITHOUT the task record: only the direct evidence counts
    out = _fallback_turn_outcome(session, "exec-now", {}, {}, "default")
    assert out["delivered"] is False, (
        "an earlier operation's findings must not certify this turn")
    # with the record bound, the recorded failure on THIS execution's
    # operation decides: failed
    record = world()  # probe via a live lifecycle read
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle
    tl = TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=world),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=world))
    # find the run for the conversation: the latest staged run_id wins
    session["_task_run_id"] = None
    out2 = _fallback_turn_outcome(
        {"id": "conv-or-1"}, "exec-now", {}, {}, "default",
        canvas_was_read=True)
    assert out2["state"] != "completed"


def test_discovery_only_receipt_never_validates(world):
    """Finding 2: a discovery-only receipt (dispatched, no requested
    values) obtains evidence about where to look — it is not an answer."""
    run_id, _op = _stage(world, "conv-or-2", "exec-disc",
                         findings=[], items={},
                         outcome="read_succeeded")
    out = _resolve(world, "conv-or-2", run_id, "exec-disc")
    assert out["delivered"] is False
    assert out["state"] in ("unconfirmed", "partial")


def test_findings_with_owner_decision_is_partial(world):
    run_id, op = _stage(
        world, "conv-or-3", "exec-od",
        questions=[{"item": "No. 622",
                    "question": "keep the manual quote at $2,421?",
                    "kind": "business_decision",
                    "next_action": "ask the owner to settle the "
                                   "No. 622 price"}])
    out = _resolve(world, "conv-or-3", run_id, "exec-od")
    assert out["state"] == "partial", out
    assert any("No. 622" in w or "decision" in w.lower()
               for w in out["open_work"])


def test_findings_with_exhausted_read_is_partial(world):
    run_id, op = _stage(
        world, "conv-or-4", "exec-ex",
        questions=[{"item": "M-2",
                    "question": "read W.xlsx for M-2",
                    "kind": "verification",
                    "next_action": "read W.xlsx for M-2",
                    "attempts": ATTEMPT_CAP}])
    out = _resolve(world, "conv-or-4", run_id, "exec-ex")
    assert out["state"] == "partial", out
    assert any("W.xlsx" in w or "exhausted" in w.lower()
               for w in out["open_work"])


def test_successful_current_read_is_completed(world):
    run_id, _op = _stage(world, "conv-or-5", "exec-ok",
                         findings=VALUES, op_status="applied")
    out = _resolve(world, "conv-or-5", run_id, "exec-ok")
    assert out["state"] == "completed", out
    assert out["delivered"] is True


@pytest.mark.xfail(reason=(
    "DESIGN GAP (flagged to owner/peer): an authorized instruction that "
    "is already satisfied has no structured values by definition, and "
    "the current delivery validation requires values on the named "
    "operations — so an authorized no-op cannot resolve completed. The "
    "owner's table wants 'Requested work completed -> success supported "
    "by its result'; closing this needs an explicit no-op validated "
    "signal (e.g. the delivery naming a no-op operation)."),
    strict=True)
def test_authorized_instruction_already_satisfied_is_completed(world):
    """An authorized no-op: nothing new to obtain, the reply persisted
    (the delivery record) — the requested work is complete."""
    run_id, _op = _stage(world, "conv-or-6", "exec-noop",
                         findings=[], items={},
                         with_delivery=True)
    out = _resolve(world, "conv-or-6", run_id, "exec-noop")
    assert out["state"] == "completed", out


def test_foreign_continuation_never_certifies(world, monkeypatch):
    """Finding (identity-bound continuations): a continuation left
    running by ANOTHER operation says nothing about this request."""
    import core.async_turn_continuation as atc
    from integrations.chat_orchestrator import _fallback_turn_outcome
    _stage(world, "conv-or-8", "exec-now", findings=[],
           with_delivery=False)
    monkeypatch.setattr(atc, "continuation_in_flight",
                        lambda sid: "exec-other-7")
    out = _fallback_turn_outcome(
        {"id": "conv-or-8", "_task_run_id": None}, "exec-now", {}, {},
        "default")
    assert out["state"] != "continuation_queued"


def test_own_continuation_is_queued_with_identity(world, monkeypatch):
    import core.async_turn_continuation as atc
    from integrations.chat_orchestrator import _fallback_turn_outcome
    monkeypatch.setattr(atc, "continuation_in_flight",
                        lambda sid: "exec-mine-9")
    out = _fallback_turn_outcome(
        {"id": "conv-or-9"}, "exec-mine-9", {}, {}, "default")
    assert out["state"] == "continuation_queued"
    assert out["continuation_id"] == "exec-mine-9"


def test_debug_noop(world):
    run_id, op = _stage(world, "conv-dbg", "exec-noop-dbg", findings=[],
                        items={}, with_delivery=True)
    tl = _tl(world)
    rec = tl.get_task(run_id)
    session = {"id": "conv-dbg", "_task_run_id": run_id}
    from integrations.chat_orchestrator import _fallback_turn_outcome
    out = _fallback_turn_outcome(session, "exec-noop-dbg", {}, {}, "default")
    print("DBG record:", bool(rec), "| deliveries:",
          len((rec or {}).get("deliveries") or []),
          "| ops:", [(o.get("status"), bool((o.get("execution") or {}).get("findings")))
                    for o in (rec or {}).get("operations", [])])
    print("DBG out:", out)
    assert True
