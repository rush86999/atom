"""WAIT wait_spec hardening — router fallback and native run boundary.

The router contract used to accept malformed WAIT output:
``wait_spec`` null or ``{}`` silently became an eventless timer, lists raised
inside ``_coerce`` (500 at the public route), ``event=None`` raised later in
``set_wait``, and unparseable timer deadlines were persisted with no wake
source. These tests pin the hardening:

* real ``GoalRunRouter.decide`` degrades malformed WAIT to the EXISTING
  ASK_HUMAN fallback (controlled output; no model call);
* the public native goal-run route returns a usable held decision, executes
  nothing, and cannot approve-replay the invalid concrete WAIT;
* valid custom events / ``human_input`` / timers (deadline and
  ``timer_seconds``) are preserved, never allow-listed away.

Scratch SQLite only; TESTING=1 is set before core imports.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("TESTING", "1")

import core.models_registration as registration
from api.goal_run_routes import router as goal_run_router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.goals.goal_plan_validation import validate_goal_plan
from core.goals.goal_run_events import due_timer_runs
from core.goals.goal_run_router import GoalRunRouter
from core.goals.goal_run_service import GoalRunService
from core.models import (
    Canvas,
    CanvasAudit,
    GoalObjective,
    GoalRun,
    HITLAction,
    User,
    UserRole,
)

PLAN = [
    {"id": "s1", "kind": "canvas_work", "title": "Research"},
    {"id": "s2", "kind": "canvas_work", "title": "Draft"},
]


# --------------------------------------------------------------- service env

@pytest.fixture()
def backend(tmp_path, monkeypatch):
    async def _noop_outcome(service, run, outcome):
        return None

    monkeypatch.setattr(
        "core.goals.goal_run_learning.record_run_outcome", _noop_outcome)
    monkeypatch.setattr(
        "core.goals.goal_run_notifications.schedule_notification",
        lambda coro: coro.close() if hasattr(coro, "close") else None)

    engine = create_engine(f"sqlite:///{tmp_path}/wait_spec.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  Canvas.__table__, CanvasAudit.__table__,
                  HITLAction.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    svc = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                         session_factory=factory)
    with factory() as session:
        session.add(GoalObjective(
            id="goal-1", workspace_id="ws_test", tenant_id="t_test",
            title="Prepare a quote for the Acme lead", status="active",
            criteria=[], key_results=[]))
        session.commit()

    def make(plan=None, **kw):
        rid = svc.create_run("goal-1", plan=plan or PLAN, **kw)["id"]
        svc.transition(rid, "active")
        return rid

    return svc, factory, make


class Stub:
    def __init__(self, decision):
        self.decision = decision

    async def decide(self, context):
        return self.decision


def advance(svc, rid, decision, **kw):
    return asyncio.run(svc.advance(rid, router=Stub(decision), **kw))


def _reviewed_resume(svc, run_id, **kwargs):
    reviewed = svc.get_run(run_id)["pending_decision"]
    return asyncio.run(svc.resume(
        run_id,
        expected_decision_id=reviewed["decision_id"],
        expected_decision_binding=reviewed["decision_binding"],
        **kwargs))


MALFORMED_WAIT_SPECS = [
    {},
    {"event": None},
    {"event": {}},
    {"event": ["email_reply"]},
    {"event": 7},
    {"event": "   "},
    {"event": "timer"},
    {"event": "timer", "deadline": "not-a-timestamp"},
    {"event": "email_reply", "match": ["from"]},
    [],
    "email_reply",
]

# JSON-shaped numerics can be arbitrarily large. float()/timedelta() must
# never raise out of validation; these are rejected, never clamped.
OVERFLOW_TIMER_SPECS = [
    pytest.param({"timer_seconds": 1e300}, id="float-1e300"),
    pytest.param({"timer_seconds": 10 ** 400}, id="int-1e400"),
]


# ---------------------------------------------------------- real router tests

def _router_context():
    return {
        "run": {"id": "run-1", "goal_id": "goal-1", "role": "sales",
                "plan": [], "parameters": {}, "decision_log": []},
        "goal": {"status": "active", "satisfied": 0, "total": 0,
                 "utility": {}},
        "step_digest": {}, "event": {}, "maturity_tier": "unknown",
    }


def _scripted_router(monkeypatch, raw_output):
    router = GoalRunRouter(tenant_id="t_test", workspace_id="ws_test")
    monkeypatch.setattr(router, "_role_context", lambda run: "")

    async def _structured(prompt, deadline):
        return raw_output, None

    monkeypatch.setattr(router, "_structured", _structured)
    return router


@pytest.mark.parametrize("spec", MALFORMED_WAIT_SPECS)
def test_router_decide_degrades_malformed_wait_to_ask_human(
        monkeypatch, spec):
    router = _scripted_router(monkeypatch, {
        "decision": "WAIT", "rationale": "need a fact",
        "wait_spec": spec, "confidence": 0.9})

    out = asyncio.run(router.decide(_router_context()))

    assert out["decision"] == "ASK_HUMAN", out
    assert out["wait_spec"] is None
    assert "unusable decision" in out["rationale"]
    # Never silently swallowed into an eventless timer.
    assert "event" not in str(out.get("wait_spec"))


@pytest.mark.parametrize("spec", OVERFLOW_TIMER_SPECS)
def test_router_decide_rejects_overflowing_timer_seconds(monkeypatch, spec):
    router = _scripted_router(monkeypatch, {
        "decision": "WAIT", "rationale": "follow up eventually",
        "wait_spec": spec, "confidence": 0.9})

    out = asyncio.run(router.decide(_router_context()))

    assert out["decision"] == "ASK_HUMAN", out
    assert out["wait_spec"] is None
    assert "unusable decision" in out["rationale"]


@pytest.mark.parametrize("spec,expected_event", [
    ({"event": "email_reply", "match": {"from": "acme@x.com"}},
     "email_reply"),
    ({"event": "crm_sync_done",
      "match_exact": {"record_id": "R-1"}}, "crm_sync_done"),
    ({"event": "human_input", "match": {"from": "lead@x.com"}},
     "human_input"),
    ({"event": "inventory_ready",
      "match": {"payload": {"sku": "A1"}}}, "inventory_ready"),
    ({"event": "timer",
      "deadline": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
     "timer"),
])
def test_router_decide_preserves_valid_wait_specs(
        monkeypatch, spec, expected_event):
    router = _scripted_router(monkeypatch, {
        "decision": "WAIT", "rationale": "legitimate wait",
        "wait_spec": spec, "confidence": 0.9})

    out = asyncio.run(router.decide(_router_context()))

    assert out["decision"] == "WAIT", out
    assert out["wait_spec"]["event"] == expected_event


def test_router_converts_timer_seconds_once(monkeypatch):
    router = _scripted_router(monkeypatch, {
        "decision": "WAIT", "rationale": "follow up",
        "wait_spec": {"timer_seconds": 90}, "confidence": 0.9})

    out = asyncio.run(router.decide(_router_context()))

    assert out["decision"] == "WAIT", out
    spec = out["wait_spec"]
    assert spec["event"] == "timer"
    assert "timer_seconds" not in spec
    parsed = datetime.fromisoformat(spec["deadline"])
    assert parsed > datetime.now(timezone.utc)


# ------------------------------------------------------------ service tests

@pytest.mark.parametrize("spec", MALFORMED_WAIT_SPECS)
def test_malformed_wait_holds_answerable_ask_human_without_execution(
        backend, spec):
    svc, factory, make = backend
    rid = make()
    before = svc.get_run(rid)

    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "need a fact only the human has",
        "wait_spec": spec, "confidence": 0.9})

    assert out["advanced"] is True
    assert out["decision"] == "ASK_HUMAN"
    assert out["held"] is True
    run = svc.get_run(rid)
    assert run["status"] == "paused_hitl"
    assert run["waiting_on"] is None
    pending = run["pending_decision"]
    assert pending["decision"] == "ASK_HUMAN"
    assert pending["invalid_decision"]["decision"] == "WAIT"
    assert pending["validation_errors"]
    # No original_decision → approval cannot replay the invalid WAIT.
    assert "original_decision" not in pending
    assert run["steps_executed"] == before["steps_executed"]
    with factory() as session:
        assert session.query(Canvas).count() == 0

    resumed = _reviewed_resume(
        svc, rid, approved=True, reviewer="sup",
        guidance="The approved budget is 50k.")
    assert resumed["resumed"] is True
    after = svc.get_run(rid)
    assert after["status"] != "waiting"
    assert after["waiting_on"] is None
    assert after["pending_decision"] is None


@pytest.mark.parametrize("spec", OVERFLOW_TIMER_SPECS)
def test_overflowing_timer_seconds_holds_ask_human_without_deadline(
        backend, spec):
    svc, factory, make = backend
    rid = make()

    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "follow up eventually",
        "wait_spec": spec, "confidence": 0.9})

    assert out["decision"] == "ASK_HUMAN", out
    assert out["held"] is True
    run = svc.get_run(rid)
    assert run["status"] == "paused_hitl"
    assert run["waiting_on"] is None
    assert run["pending_decision"]["invalid_decision"]["wait_spec"] == spec
    with factory() as session:
        assert session.query(Canvas).count() == 0


def test_invalid_wait_strips_supplied_original_decision_replay_link(backend):
    """Injected/persisted malformed WAIT may smuggle ``original_decision``;
    the synthesized invalid hold must not let approval replay it."""
    svc, factory, make = backend
    rid = make()

    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "need a fact",
        "wait_spec": [],
        "original_decision": {
            "decision": "ADVANCE", "rationale": "smuggled concrete work",
            "confidence": 0.9},
        "confidence": 0.9})

    assert out["decision"] == "ASK_HUMAN", out
    pending = svc.get_run(rid)["pending_decision"]
    assert "original_decision" not in pending
    assert pending["invalid_decision"]["original_decision"]["decision"] == (
        "ADVANCE")

    resumed = _reviewed_resume(
        svc, rid, approved=True, reviewer="sup", guidance="Budget is 50k.")
    assert resumed["resumed"] is True
    after = svc.get_run(rid)
    assert after["waiting_on"] is None
    assert after["pending_decision"] is None
    assert after["status"] != "waiting"
    # The smuggled ADVANCE never ran.
    with factory() as session:
        assert session.query(Canvas).count() == 0
    assert after["steps_executed"] == 0


def test_nested_match_values_keep_existing_stringified_semantics(backend):
    """Custom-integration match values were already consumable via
    _match_wait's str() comparison; hardening must not prohibit them."""
    svc, _, make = backend
    rid = make()
    spec = {"event": "inventory_ready",
            "match": {"payload": {"sku": "A1"}}}

    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "wait for inventory",
        "wait_spec": spec, "confidence": 0.9})

    assert out["decision"] == "WAIT", out
    assert svc.get_run(rid)["waiting_on"]["match"] == spec["match"]
    wake = svc.consume_wake(rid, {
        "event": "inventory_ready", "payload": str({"sku": "A1"})})
    assert wake["consumed"] is True


@pytest.mark.parametrize("spec", [
    {"event": "email_reply", "match": {"from": "acme@x.com"}},
    {"event": "crm_sync_done", "match_exact": {"record_id": "R-1"}},
    {"event": "human_input", "match": {"from": "lead@x.com"}},
])
def test_valid_event_waits_persist_exact_identity(backend, spec):
    svc, _, make = backend
    rid = make()

    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "wait for the event",
        "wait_spec": spec, "confidence": 0.9})

    assert out["decision"] == "WAIT", out
    run = svc.get_run(rid)
    assert run["status"] == "waiting"
    for key, value in spec.items():
        assert run["waiting_on"][key] == value


def test_valid_timer_wait_is_sweepable(backend):
    svc, factory, make = backend
    rid = make()
    deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    out = advance(svc, rid, {
        "decision": "WAIT", "rationale": "follow up later",
        "wait_spec": {"event": "timer", "deadline": deadline},
        "confidence": 0.9})

    assert out["decision"] == "WAIT", out
    run = svc.get_run(rid)
    assert run["waiting_on"]["event"] == "timer"
    assert run["waiting_on"]["deadline"] == deadline
    due = due_timer_runs(
        workspace_id="ws_test", tenant_id="t_test",
        session_factory=factory,
        now=datetime.fromisoformat(deadline) + timedelta(seconds=1))
    assert [r["id"] for r in due] == [rid]


def test_wait_for_timer_seconds_is_executable_and_sweepable(backend):
    svc, factory, make = backend
    rid = make(plan=[{
        "id": "wait-1", "kind": "wait_for", "title": "Follow up in a minute",
        "wait_spec": {"timer_seconds": 60}}])

    out = advance(svc, rid, {
        "decision": "ADVANCE", "rationale": "start the wait",
        "confidence": 0.9})

    assert out["advanced"] is True
    run = svc.get_run(rid)
    assert run["status"] == "waiting"
    assert run["waiting_on"]["event"] == "timer"
    deadline = datetime.fromisoformat(run["waiting_on"]["deadline"])
    due = due_timer_runs(
        workspace_id="ws_test", tenant_id="t_test",
        session_factory=factory,
        now=deadline + timedelta(seconds=1))
    assert [r["id"] for r in due] == [rid]


def test_plan_validator_rejects_unconsumable_wait_for_specs():
    for spec in ({}, {"event": None}, {"event": "timer"},
                 {"event": "timer", "deadline": "nope"},
                 {"timer_seconds": 1e300}, {"timer_seconds": 10 ** 400}):
        errors = validate_goal_plan([{
            "id": "wait-1", "kind": "wait_for", "title": "Wait",
            "wait_spec": spec}])
        assert errors, spec
    assert validate_goal_plan([{
        "id": "wait-1", "kind": "wait_for", "title": "Wait",
        "wait_spec": {"event": "crm_sync_done",
                      "match_exact": {"record_id": "R-1"}}}]) == []


# ------------------------------------------------- public native boundary

def _make_client(db, viewer_id):
    app = FastAPI()
    app.include_router(goal_run_router)
    user = Mock(id=viewer_id, tenant_id=None, status="active",
                workspace_id="ws-test")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def route_world(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/wait_spec_routes.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool)
    registration.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    db.add(User(id="gr-lead", email="gr-lead@example.com", first_name="Goal",
                last_name="Lead", role=UserRole.TEAM_LEAD.value,
                status="active"))
    db.add(User(id="gr-emp", email="gr-emp@example.com", first_name="Emp",
                last_name="Loyee", role=UserRole.MEMBER.value,
                status="active"))
    db.add(GoalObjective(
        id="goal-1", workspace_id="default", tenant_id=None,
        title="Prepare a quote for the Acme lead", status="active",
        criteria=[], key_results=[]))
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _script_default_router(monkeypatch, *decisions):
    queue = list(decisions)

    class _Scripted:
        async def decide(self, context):
            if queue:
                return queue.pop(0)
            return {"decision": "ASK_HUMAN", "rationale": "done",
                    "confidence": 0.9}

    monkeypatch.setattr(GoalRunService, "_default_router",
                        lambda self: _Scripted())


def _create_dormant(client):
    resp = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "supervision_mode": "shadow", "start": False})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.parametrize("spec", MALFORMED_WAIT_SPECS)
def test_public_advance_holds_malformed_wait_instead_of_500(
        route_world, monkeypatch, spec):
    _script_default_router(monkeypatch, {
        "decision": "WAIT", "rationale": "need a fact",
        "wait_spec": spec, "confidence": 0.9})
    client = _make_client(route_world, "gr-lead")
    run_id = _create_dormant(client)

    resp = client.post(f"/api/goal-runs/{run_id}/advance")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "ASK_HUMAN"
    assert body["held"] is True
    detail = client.get(f"/api/goal-runs/{run_id}").json()
    assert detail["status"] == "paused_hitl"
    assert detail["waiting_on"] is None
    reviewed = detail["pending_decision"]
    assert reviewed["invalid_decision"]["decision"] == "WAIT"

    resumed = client.post(f"/api/goal-runs/{run_id}/resume", json={
        "approved": True, "guidance": "Budget is 50k.",
        "decision_id": reviewed["decision_id"],
        "decision_binding": reviewed["decision_binding"]})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["resumed"] is True
    after = client.get(f"/api/goal-runs/{run_id}").json()
    assert after["waiting_on"] is None
    assert after["pending_decision"] is None


@pytest.mark.parametrize("spec", OVERFLOW_TIMER_SPECS)
def test_public_advance_overflow_timer_holds_usable_ask_human(
        route_world, monkeypatch, spec):
    _script_default_router(monkeypatch, {
        "decision": "WAIT", "rationale": "follow up eventually",
        "wait_spec": spec, "confidence": 0.9})
    client = _make_client(route_world, "gr-lead")
    run_id = _create_dormant(client)

    resp = client.post(f"/api/goal-runs/{run_id}/advance")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "ASK_HUMAN"
    assert body["held"] is True
    detail = client.get(f"/api/goal-runs/{run_id}").json()
    assert detail["status"] == "paused_hitl"
    assert detail["waiting_on"] is None
    reviewed = detail["pending_decision"]
    assert reviewed["invalid_decision"]["wait_spec"] == spec

    resumed = client.post(f"/api/goal-runs/{run_id}/resume", json={
        "approved": True, "guidance": "Budget is 50k.",
        "decision_id": reviewed["decision_id"],
        "decision_binding": reviewed["decision_binding"]})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["resumed"] is True
    assert client.get(f"/api/goal-runs/{run_id}").json()["waiting_on"] is None
    assert route_world.query(Canvas).count() == 0


def test_public_invalid_wait_cannot_replay_supplied_original(
        route_world, monkeypatch):
    _script_default_router(monkeypatch, {
        "decision": "WAIT", "rationale": "need a fact",
        "wait_spec": None,
        "original_decision": {"decision": "ADVANCE",
                              "rationale": "smuggled work",
                              "confidence": 0.9},
        "confidence": 0.9})
    client = _make_client(route_world, "gr-lead")
    run_id = _create_dormant(client)

    resp = client.post(f"/api/goal-runs/{run_id}/advance")
    assert resp.status_code == 200, resp.text
    reviewed = client.get(f"/api/goal-runs/{run_id}").json()["pending_decision"]
    assert "original_decision" not in reviewed

    resumed = client.post(f"/api/goal-runs/{run_id}/resume", json={
        "approved": True, "guidance": "Budget is 50k.",
        "decision_id": reviewed["decision_id"],
        "decision_binding": reviewed["decision_binding"]})
    assert resumed.status_code == 200, resumed.text
    after = client.get(f"/api/goal-runs/{run_id}").json()
    assert after["waiting_on"] is None
    assert after["pending_decision"] is None
    assert route_world.query(Canvas).count() == 0


def test_public_valid_custom_wait_survives_and_inbox_wakes(
        route_world, monkeypatch):
    _script_default_router(
        monkeypatch,
        {"decision": "WAIT", "rationale": "wait for the CRM sync",
         "wait_spec": {"event": "crm_sync_done",
                       "match_exact": {"record_id": "R-1"}},
         "confidence": 0.9},
        {"decision": "ASK_HUMAN", "rationale": "woke", "confidence": 0.9},
    )
    client = _make_client(route_world, "gr-lead")
    run_id = _create_dormant(client)

    resp = client.post(f"/api/goal-runs/{run_id}/advance")
    assert resp.status_code == 200, resp.text
    detail = client.get(f"/api/goal-runs/{run_id}").json()
    assert detail["status"] == "waiting"
    assert detail["waiting_on"]["event"] == "crm_sync_done"
    assert detail["waiting_on"]["match_exact"] == {"record_id": "R-1"}

    woken = client.post("/api/goal-runs/events", json={
        "event": "crm_sync_done", "payload": {"record_id": "R-1"}})
    assert woken.status_code == 200, woken.text
    assert woken.json()["woke"] == [run_id]
