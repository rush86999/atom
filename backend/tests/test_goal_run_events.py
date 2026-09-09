"""Slice 4 tests — event ingestion + timer wakes
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §3.4, §7 slice 4)."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import Base, Canvas, CanvasAudit, GoalObjective, GoalRun, HITLAction
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_run_events import check_due_waits, due_timer_runs, ingest_event


@pytest.fixture()
def backend(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/goal_run_events_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__, HITLAction.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def make(**kwargs):
        return GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                              session_factory=factory, **kwargs)

    svc = make()
    with factory() as session:
        session.add(GoalObjective(id="goal-1", workspace_id="ws_test",
                                  tenant_id="t_test",
                                  title="Prepare a quote for the Acme lead",
                                  status="active"))
        session.commit()
    rid = svc.create_run("goal-1", plan=[
        {"id": "s1", "kind": "canvas_work", "title": "Research"}])["id"]
    svc.transition(rid, "active")
    svc.set_wait(rid, {"event": "email_reply", "match": {"from": "acme@x.com"}})
    return svc, make, rid


class NoopRouter:
    async def decide(self, context):
        return {"decision": "ASK_HUMAN", "rationale": "woken — check in",
                "confidence": 0.9}


def test_ingest_wakes_matching_run_only(backend):
    svc, make, rid = backend
    out = asyncio.run(ingest_event(
        {"event": "email_reply", "from": "acme@x.com", "subject": "Re: quote"},
        workspace_id="ws_test", tenant_id="t_test",
        session_factory=svc._session_factory))
    assert out["woke"] == [rid]
    run = svc.get_run(rid)
    assert run["status"] == "paused_hitl"   # advanced into an ASK_HUMAN hold
    kinds = [e.get("kind") for e in run["decision_log"]]
    assert "wake" in kinds


def test_ingest_ignores_non_matching(backend):
    svc, make, rid = backend
    out = asyncio.run(ingest_event(
        {"event": "email_reply", "from": "other@y.com"},
        workspace_id="ws_test", tenant_id="t_test",
        session_factory=svc._session_factory))
    assert out["woke"] == []
    assert svc.get_run(rid)["status"] == "waiting"


def test_ingest_is_fault_isolated(backend):
    svc, make, rid = backend
    # A run whose advance blows up must not break ingestion of others.
    svc.append_decision(rid, {"kind": "decision"})
    out = asyncio.run(ingest_event(
        {"event": "email_reply", "from": "acme@x.com"},
        workspace_id="ws_test", tenant_id="t_test",
        session_factory=svc._session_factory, ))
    assert isinstance(out, dict) and "woke" in out


def test_due_timer_wake(backend):
    svc, make, rid = backend
    # A second run waiting on a PASSED timer deadline.
    rid2 = svc.create_run("goal-1", plan=[
        {"id": "s1", "kind": "canvas_work", "title": "Follow up"}])["id"]
    svc.transition(rid2, "active")
    svc.set_wait(rid2, {"event": "timer",
                        "deadline": (datetime.now(timezone.utc)
                                     - timedelta(hours=1)).isoformat()})
    due = due_timer_runs("ws_test", "t_test", svc._session_factory)
    assert [r["id"] for r in due] == [rid2]
    out = asyncio.run(check_due_waits("ws_test", "t_test",
                                      svc._session_factory))
    assert out["woke"] == [rid2]
    assert svc.get_run(rid2)["status"] == "paused_hitl"  # woke → ASK_HUMAN hold
    assert svc.get_run(rid)["status"] == "waiting"       # email wait untouched


def test_unparseable_deadline_is_skipped_not_raised(backend):
    svc, make, rid = backend
    rid2 = svc.create_run("goal-1", plan=[
        {"id": "s1", "kind": "canvas_work", "title": "x"}])["id"]
    svc.transition(rid2, "active")
    svc.set_wait(rid2, {"event": "timer", "deadline": "not-a-date"})
    due = due_timer_runs("ws_test", "t_test", svc._session_factory)
    assert [r["id"] for r in due] == []


def test_notify_canvas_done_no_link_is_noop(backend, monkeypatch):
    """Most canvases have no goal-run link: the hook must be a silent no-op
    (it fires after EVERY canvas edit in the orchestrator)."""
    from core.goals.goal_run_events import notify_canvas_done
    monkeypatch.setattr(
        "core.database.get_db_session", backend[0]._session_factory)
    out = asyncio.run(notify_canvas_done("cv-nothing"))
    assert out["advanced"] is False


def test_notify_canvas_done_advances_active_run(backend, monkeypatch):
    """An ACTIVE run whose canvas finishes a step re-decides via the
    router. (A WAITING run is NOT advanced — a canvas edit is not the
    external event it sleeps on.)"""
    from core.models import Canvas
    from core.goals.goal_run_events import notify_canvas_done
    from core.goals.goal_run_service import GoalRunService

    svc, make, _rid = backend
    rid2 = svc.create_run("goal-1", plan=[
        {"id": "s1", "kind": "canvas_work", "title": "Research"}])["id"]
    svc.transition(rid2, "active")

    class Stub:
        async def decide(self, context):
            return {"decision": "ADVANCE", "rationale": "research looks done",
                    "confidence": 0.9,
                    "parameter_updates": {"lead_stage": "researched"}}

    monkeypatch.setattr(GoalRunService, "_default_router",
                        lambda self: Stub())
    factory = svc._session_factory
    with factory() as session:
        session.add(Canvas(id="cv-linked", tenant_id="t_test",
                           workspace_id="ws_test", created_by="u",
                           name="Lead research", canvas_type="document",
                           goal_run_id=rid2, goal_run_step_id="s1"))
        session.commit()

    monkeypatch.setattr("core.database.get_db_session", factory)
    out = asyncio.run(notify_canvas_done("cv-linked", reason="no_change"))
    assert out.get("advanced") is True and out.get("decision") == "ADVANCE"
    run = svc.get_run(rid2)
    assert run["parameters"]["lead_stage"] == "researched"
    entry = next(e for e in run["decision_log"] if e.get("kind") == "decision")
    assert entry["canvas_id"] == "cv-linked"
    # Waiting run untouched by canvas edits (not its awaited event):
    assert svc.get_run(_rid)["status"] == "waiting"


def test_notify_canvas_done_leaves_waiting_run_asleep(backend, monkeypatch):
    from core.models import Canvas
    from core.goals.goal_run_events import notify_canvas_done

    svc, make, rid = backend   # fixture run is waiting on an email reply
    factory = svc._session_factory
    with factory() as session:
        session.add(Canvas(id="cv-waiting", tenant_id="t_test",
                           workspace_id="ws_test", created_by="u",
                           name="Quote", canvas_type="spreadsheet",
                           goal_run_id=rid))
        session.commit()
    monkeypatch.setattr("core.database.get_db_session", factory)
    out = asyncio.run(notify_canvas_done("cv-waiting"))
    assert out["advanced"] is False
    assert svc.get_run(rid)["status"] == "waiting"
