"""Effect-family controls for the native goal-run family.

These are consumer controls, not discovery rows:

* wrong workspace: another workspace's supervisor cannot read or mutate a run
  (404 before any decision/executor effect);
* terminal/no-effect: advancing a finished run is a 409 and appends no
  decision;
* duplicate: a retried resume claims the exact pending-decision generation;
  only one caller may clear it, record the approval, or execute the turn;
* restart/fresh session: a new service/session sees the persisted pending
  decision and can consume it exactly once;
* registered-action consumer: an agent may start only its own role run in the
  goal's workspace, and a retried tool call cannot stack a duplicate run.

The concurrency controls use a file-backed SQLite database with separate
sessions, not the shared scratch session. They are fresh-session/thread
controls, not claims of a process restart or soak.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from api.goal_run_routes import router as goal_run_router
from core.action_registry import action_registry
from core.auth import get_current_user
from core.database import get_db
from core.goals import goal_run_executors
from core.goals.goal_run_service import GoalRunService
from core.models import (
    AgentRegistry,
    Canvas,
    CanvasAudit,
    GoalObjective,
    GoalRun,
    HITLAction,
    HITLActionStatus,
    User,
    UserRole,
)

PLAN = [
    {"id": "step-research", "kind": "canvas_work",
     "title": "Research the lead", "canvas_type": "document"},
    {"id": "step-quote", "kind": "canvas_work",
     "title": "Draft the quote", "canvas_type": "spreadsheet"},
]


def _file_engine(tmp_path, name="goal-family.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def _wal(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    for table in (GoalObjective.__table__, GoalRun.__table__,
                  HITLAction.__table__, Canvas.__table__, CanvasAudit.__table__,
                  AgentRegistry.__table__):
        table.create(engine)
    return engine


def _add_goal(factory, goal_id="goal-family", workspace_id="ws-a",
              tenant_id="t-a"):
    with factory() as session:
        session.add(GoalObjective(
            id=goal_id, workspace_id=workspace_id, tenant_id=tenant_id,
            title="Prepare a quote for the Acme lead", status="active",
            criteria=[], key_results=[]))
        session.commit()


def _add_agent(factory, agent_id="agent-a", workspace_id="ws-a"):
    with factory() as session:
        session.add(AgentRegistry(
            id=agent_id, name=f"Agent {agent_id}", category="operations",
            module_path="test.mod", class_name="Agent",
            status="intern", workspace_id=workspace_id, tenant_id="t-a",
            specialty="sales"))
        session.commit()


def _hold(svc, run_id, decision=None):
    return svc._hold_for_approval(
        run_id,
        decision or {"decision": "ADVANCE", "rationale": "next step"},
        reason="test checkpoint")


def _review(held):
    return {
        "decision_id": held["decision_id"],
        "decision_binding": held["decision_binding"],
    }


def _client(db, user):
    app = FastAPI()
    app.include_router(goal_run_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def users(db_session):
    lead_a = User(
        id="lead-a", email="lead-a@example.com", first_name="Lead",
        last_name="A", role=UserRole.TEAM_LEAD.value, status="active",
        workspace_id="ws-a", tenant_id="t-a")
    lead_b = User(
        id="lead-b", email="lead-b@example.com", first_name="Lead",
        last_name="B", role=UserRole.TEAM_LEAD.value, status="active",
        workspace_id="ws-b", tenant_id="t-b")
    db_session.add_all([lead_a, lead_b])
    db_session.add(GoalObjective(
        id="goal-a", workspace_id="ws-a", tenant_id="t-a",
        title="Prepare a quote for the Acme lead", status="active",
        criteria=[], key_results=[]))
    db_session.commit()
    return lead_a, lead_b


def _service(db, workspace_id="ws-a"):
    @contextlib.contextmanager
    def _session():
        yield db

    return GoalRunService(
        workspace_id=workspace_id, tenant_id="t-a", session_factory=_session)


# ---------------------------------------------------------------------------
# Route-level controls
# ---------------------------------------------------------------------------


def test_wrong_workspace_supervisor_reads_and_mutations_are_404(
        db_session, users):
    lead_a, lead_b = users
    svc = _service(db_session)
    run_id = svc.create_run("goal-a", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    before = len(svc.get_decisions(run_id))

    other = _client(db_session, lead_b)
    assert other.get(f"/api/goal-runs/{run_id}").status_code == 404
    assert other.get(f"/api/goal-runs/{run_id}/decisions").status_code == 404
    assert other.post(f"/api/goal-runs/{run_id}/advance").status_code == 404
    assert other.post(f"/api/goal-runs/{run_id}/resume",
                      json={"approved": True}).status_code == 404
    assert other.post(f"/api/goal-runs/{run_id}/cancel").status_code == 404

    # The foreign supervisor's refusals append nothing to the owner's run.
    assert len(svc.get_decisions(run_id)) == before
    assert db_session.query(GoalRun).filter(
        GoalRun.id == run_id).one().workspace_id == "ws-a"


def test_terminal_run_advance_is_409_and_appends_no_decision(
        db_session, users, monkeypatch):
    lead_a, _ = users
    svc = _service(db_session)
    run_id = svc.create_run("goal-a", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    svc.transition(run_id, "cancelled")
    before = len(svc.get_decisions(run_id))

    calls = {"executor": 0}

    async def _never(*args, **kwargs):  # pragma: no cover - must not run
        calls["executor"] += 1
        return {"executed": True}

    monkeypatch.setattr(
        goal_run_executors.GoalRunExecutors, "execute", _never)
    client = _client(db_session, lead_a)
    response = client.post(f"/api/goal-runs/{run_id}/advance")
    assert response.status_code == 409
    assert calls["executor"] == 0
    assert len(svc.get_decisions(run_id)) == before


def test_duplicate_resume_executes_once_and_keeps_first_reviewer(
        db_session, users, monkeypatch):
    lead_a, _lead_b = users
    second_lead = User(
        id="lead-a2", email="lead-a2@example.com", first_name="Lead",
        last_name="A2", role=UserRole.TEAM_LEAD.value, status="active",
        workspace_id="ws-a", tenant_id="t-a")
    db_session.add(second_lead)
    db_session.commit()
    svc = _service(db_session)
    run_id = svc.create_run("goal-a", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    held = _hold(svc, run_id)
    assert held["hitl_id"]

    calls = {"executor": 0}

    async def _execute(self, run, decision):
        calls["executor"] += 1
        time.sleep(0.05)
        return {"executed": decision.get("decision")}

    monkeypatch.setattr(
        goal_run_executors.GoalRunExecutors, "execute", _execute)

    review = _review(held)
    first = _client(db_session, lead_a).post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review})
    second = _client(db_session, second_lead).post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review})

    assert first.status_code == 200, first.text
    assert first.json()["resumed"] is True
    assert second.status_code == 200, second.text
    assert second.json()["resumed"] is False
    assert calls["executor"] == 1

    run = svc.get_run(run_id)
    assert run["pending_decision"] is None
    approved = [d for d in run["decision_log"] if d.get("kind") == "approved"]
    assert len(approved) == 1
    assert approved[0]["reviewer"] == "lead-a"

    hitl = db_session.query(HITLAction).filter(
        HITLAction.id == held["hitl_id"]).one()
    assert hitl.status == HITLActionStatus.APPROVED.value
    assert hitl.reviewed_by == "lead-a"


# ---------------------------------------------------------------------------
# Concurrent / fresh-session controls
# ---------------------------------------------------------------------------


def test_two_simultaneous_resumes_execute_one_turn(tmp_path, monkeypatch):
    engine = _file_engine(tmp_path, "resume-race.db")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory)
    barrier = threading.Barrier(2)
    state = {"race": False, "waiters": 0}
    lock = threading.Lock()

    class RacingService(GoalRunService):
        def get_run(self, run_id):
            run = super().get_run(run_id)
            with lock:
                wait_here = bool(
                    state["race"] and run and run.get("pending_decision"))
                if wait_here:
                    state["waiters"] += 1
                    if state["waiters"] >= 2:
                        state["race"] = False
            if wait_here:
                barrier.wait(timeout=10)
            return run

    calls = {"executor": 0}

    async def _execute(self, run, decision):
        calls["executor"] += 1
        time.sleep(0.2)
        return {"executed": decision.get("decision")}

    monkeypatch.setattr(
        goal_run_executors.GoalRunExecutors, "execute", _execute)

    creator = RacingService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    run_id = creator.create_run(
        "goal-family", role="sales", plan=PLAN)["id"]
    creator.transition(run_id, "active")
    held = _hold(creator, run_id)
    review = _review(held)
    state["race"] = True

    results = []

    def worker(reviewer):
        svc = RacingService(
            workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
        try:
            results.append(asyncio.run(
                svc.resume(
                    run_id, approved=True, reviewer=reviewer,
                    expected_decision_id=review["decision_id"],
                    expected_decision_binding=review["decision_binding"])))
        except Exception as exc:  # noqa: BLE001 - surfaced in assertion
            results.append({"error": f"{type(exc).__name__}: {exc}"})

    threads = [threading.Thread(target=worker, args=(name,))
               for name in ("lead-a", "lead-b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    engine.dispose()

    assert len(results) == 2
    assert [bool(r.get("resumed")) for r in results].count(True) == 1
    assert calls["executor"] == 1
    assert not any("error" in r for r in results), results

    with factory() as session:
        row = session.query(GoalRun).filter(GoalRun.id == run_id).one()
        approved = [d for d in (row.decision_log or [])
                    if d.get("kind") == "approved"]
        assert row.pending_decision is None
        assert len(approved) == 1
        assert approved[0]["reviewer"] in ("lead-a", "lead-b")


def test_stale_resume_snapshot_cannot_claim_newer_pending(
        tmp_path, monkeypatch):
    """A caller that read pending decision 1 must not clear decision 2."""
    engine = _file_engine(tmp_path, "stale-pending.db")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory)

    calls = {"executor": 0}

    async def _execute(self, run, decision):
        calls["executor"] += 1
        return {"executed": decision.get("decision")}

    monkeypatch.setattr(
        goal_run_executors.GoalRunExecutors, "execute", _execute)

    writer = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    run_id = writer.create_run("goal-family", role="sales", plan=PLAN)["id"]
    writer.transition(run_id, "active")
    held = _hold(writer, run_id,
                 {"decision": "ADVANCE", "rationale": "old"})
    review = _review(held)
    stale_snapshot = writer.get_run(run_id)
    old_generation = stale_snapshot["human_interventions"]

    class StaleService(GoalRunService):
        installed = False

        def get_run(self, run_id):
            if not self.installed:
                self.installed = True
                newer = GoalRunService(
                    workspace_id="ws-a", tenant_id="t-a",
                    session_factory=factory)
                _hold(newer, run_id,
                      {"decision": "ASK_HUMAN", "rationale": "newer"})
                return stale_snapshot
            return super().get_run(run_id)

    stale = StaleService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    out = asyncio.run(stale.resume(
        run_id, approved=True, reviewer="lead-a",
        expected_decision_id=review["decision_id"],
        expected_decision_binding=review["decision_binding"]))

    assert out["resumed"] is False
    assert calls["executor"] == 0
    current = writer.get_run(run_id)
    assert current["human_interventions"] > old_generation
    assert current["pending_decision"]["rationale"] == "newer"
    assert [d for d in current["decision_log"]
            if d.get("kind") == "approved"] == []
    engine.dispose()


def test_fresh_session_resumes_persisted_pending_once(tmp_path, monkeypatch):
    engine = _file_engine(tmp_path, "fresh-session.db")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory)

    calls = {"executor": 0}

    async def _execute(self, run, decision):
        calls["executor"] += 1
        return {"executed": decision.get("decision")}

    monkeypatch.setattr(
        goal_run_executors.GoalRunExecutors, "execute", _execute)

    first = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    run_id = first.create_run("goal-family", role="sales", plan=PLAN)["id"]
    first.transition(run_id, "active")
    held = _hold(first, run_id)
    review = _review(held)

    # Fresh process-like boundary: no shared session/identity map.
    second = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    pending = second.get_run(run_id)
    assert pending["pending_decision"]["decision"] == "ADVANCE"
    assert asyncio.run(second.resume(
        run_id, approved=True, reviewer="lead-b",
        expected_decision_id=review["decision_id"],
        expected_decision_binding=review["decision_binding"]))["resumed"] is True

    third = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    after = third.get_run(run_id)
    assert after["pending_decision"] is None
    assert len([d for d in after["decision_log"]
                if d.get("kind") == "approved"]) == 1
    assert asyncio.run(third.resume(
        run_id, approved=True, reviewer="lead-a",
        expected_decision_id=review["decision_id"],
        expected_decision_binding=review["decision_binding"]))["resumed"] is False
    assert calls["executor"] == 1
    engine.dispose()


# ---------------------------------------------------------------------------
# Registered-action consumer
# ---------------------------------------------------------------------------


def test_goal_action_start_wrong_workspace_refuses_without_rows(
        tmp_path, monkeypatch):
    engine = _file_engine(tmp_path, "action-wrong-ws.db")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory, goal_id="goal-other", workspace_id="ws-b")
    _add_agent(factory, agent_id="agent-a", workspace_id="ws-a")

    @contextlib.contextmanager
    def _session():
        with factory() as session:
            yield session

    monkeypatch.setattr("core.database.get_db_session", _session)
    out = asyncio.run(action_registry.execute_action(
        "goal_runs.start",
        {"goal_id": "goal-other", "agent_id": "agent-a", "start": False},
        {"workspace_id": "ws-a", "tenant_id": "t-a",
         "agent_id": "agent-a"}))

    assert out["success"] is False
    assert "another workspace" in out["error"]
    with factory() as session:
        assert session.query(GoalRun).count() == 0
    engine.dispose()


def test_goal_action_start_refuses_self_impersonation(tmp_path, monkeypatch):
    engine = _file_engine(tmp_path, "action-self.db")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory, goal_id="goal-self", workspace_id="ws-a")
    _add_agent(factory, agent_id="agent-a", workspace_id="ws-a")
    _add_agent(factory, agent_id="agent-b", workspace_id="ws-a")

    @contextlib.contextmanager
    def _session():
        with factory() as session:
            yield session

    monkeypatch.setattr("core.database.get_db_session", _session)
    out = asyncio.run(action_registry.execute_action(
        "goal_runs.start",
        {"goal_id": "goal-self", "agent_id": "agent-b", "start": False},
        {"workspace_id": "ws-a", "tenant_id": "t-a",
         "agent_id": "agent-a"}))

    assert out["success"] is False
    assert "only for itself" in out["error"]
    with factory() as session:
        assert session.query(GoalRun).count() == 0
    engine.dispose()


def test_goal_action_duplicate_active_run_is_refused(tmp_path, monkeypatch):
    engine = _file_engine(tmp_path, "action-duplicate.db")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory, goal_id="goal-dup", workspace_id="ws-a")
    _add_agent(factory, agent_id="agent-a", workspace_id="ws-a")

    @contextlib.contextmanager
    def _session():
        with factory() as session:
            yield session

    monkeypatch.setattr("core.database.get_db_session", _session)
    context = {"workspace_id": "ws-a", "tenant_id": "t-a",
               "agent_id": "agent-a"}
    args = {"goal_id": "goal-dup", "agent_id": "agent-a", "start": False}
    first = asyncio.run(action_registry.execute_action(
        "goal_runs.start", dict(args), dict(context)))
    second = asyncio.run(action_registry.execute_action(
        "goal_runs.start", dict(args), dict(context)))

    assert first["success"] is True, first
    assert second["success"] is False
    assert "already has run" in second["error"]
    with factory() as session:
        assert session.query(GoalRun).count() == 1
    engine.dispose()


def _file_client(tmp_path, name="route-replay.db"):
    engine = _file_engine(tmp_path, name)
    User.__table__.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    _add_goal(factory)
    db = factory()
    user = User(
        id="lead-a", email="lead-a@example.invalid", first_name="Lead",
        last_name="A", role=UserRole.TEAM_LEAD.value, status="active",
        workspace_id="ws-a", tenant_id="t-a")
    db.add(user)
    db.commit()
    svc = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    return engine, factory, db, user, svc


def _execute_counter(monkeypatch, svc, on_first=None):
    calls = []

    async def execute(run_id, decision):
        calls.append(decision)
        if on_first and len(calls) == 1:
            on_first()
        return {"run": svc.get_run(run_id)}

    monkeypatch.setattr(svc, "execute_decision", execute)
    return calls


def test_public_resume_replay_cannot_execute_a_newer_pending_decision(
        tmp_path, monkeypatch):
    """A's exact HTTP request replayed after A opens B must fail closed."""
    from api import goal_run_routes as routes

    engine, factory, db, user, svc = _file_client(
        tmp_path, "http-replay-binding.db")
    run_id = svc.create_run("goal-family", role="sales", plan=[])["id"]
    svc.transition(run_id, "active")
    held_a = _hold(svc, run_id, {
        "decision": "ADVANCE", "rationale": "Reviewed decision A"})
    review_a = _review(held_a)

    def create_b():
        _hold(svc, run_id, {
            "decision": "REPLAN",
            "new_plan": [{"id": "new", "title": "Unreviewed replacement"}],
            "rationale": "New decision B"})

    calls = _execute_counter(monkeypatch, svc, on_first=create_b)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)
    request = {"approved": True, **review_a}

    first = client.post(f"/api/goal-runs/{run_id}/resume", json=request)
    assert first.status_code == 200, first.text
    assert first.json()["resumed"] is True
    assert svc.get_run(run_id)["pending_decision"]["rationale"] == (
        "New decision B")

    replay = client.post(f"/api/goal-runs/{run_id}/resume", json=request)
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["error"] == "stale_decision_review"
    assert len(calls) == 1
    current = svc.get_run(run_id)
    assert current["pending_decision"]["rationale"] == "New decision B"
    b_row = (
        db.query(HITLAction)
        .filter(HITLAction.status == HITLActionStatus.PENDING.value,
                HITLAction.action_type == "goal_run_decision")
        .all())
    assert any((row.params or {}).get("decision", {}).get(
        "rationale") == "New decision B" for row in b_row)
    db.close()
    engine.dispose()


def test_public_resume_without_review_binding_is_refused(
        tmp_path, monkeypatch):
    from api import goal_run_routes as routes

    engine, factory, db, user, svc = _file_client(
        tmp_path, "unbound-resume.db")
    run_id = svc.create_run("goal-family", role="sales", plan=[])["id"]
    svc.transition(run_id, "active")
    held = _hold(
        svc, run_id, {"decision": "ADVANCE", "rationale": "review me"})
    calls = _execute_counter(monkeypatch, svc)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)

    response = client.post(
        f"/api/goal-runs/{run_id}/resume", json={"approved": True})
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "decision_review_required"
    assert calls == []
    assert svc.get_run(run_id)["pending_decision"]["rationale"] == "review me"
    hitl = db.query(HITLAction).filter(
        HITLAction.id == held["hitl_id"]).one()
    assert hitl.status == HITLActionStatus.PENDING.value
    db.close()
    engine.dispose()


def test_changed_plan_after_review_is_stale(
        tmp_path, monkeypatch):
    from api import goal_run_routes as routes

    engine, factory, db, user, svc = _file_client(
        tmp_path, "changed-plan.db")
    run_id = svc.create_run("goal-family", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    held = _hold(svc, run_id, {
        "decision": "ADVANCE", "rationale": "reviewed plan"})
    review = _review(held)
    held_hitl = db.query(HITLAction).filter(
        HITLAction.id == held["hitl_id"]).one()
    svc.set_plan(run_id, [{"id": "other", "kind": "canvas_work",
                           "title": "Changed after review"}])
    calls = _execute_counter(monkeypatch, svc)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)

    response = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == "stale_decision_review"
    assert calls == []
    assert svc.get_run(run_id)["pending_decision"] is not None
    db.refresh(held_hitl)
    assert held_hitl.status == HITLActionStatus.PENDING.value
    db.close()
    engine.dispose()


def test_duplicate_rejection_of_one_reviewed_decision_is_noop(
        tmp_path, monkeypatch):
    from api import goal_run_routes as routes

    engine, factory, db, user, svc = _file_client(
        tmp_path, "duplicate-rejection.db")
    run_id = svc.create_run("goal-family", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    held = _hold(svc, run_id, {
        "decision": "ADVANCE", "rationale": "reject me"})
    review = _review(held)
    calls = _execute_counter(monkeypatch, svc)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)
    request = {"approved": False, "guidance": "try another approach",
               **review}

    first = client.post(f"/api/goal-runs/{run_id}/resume", json=request)
    second = client.post(f"/api/goal-runs/{run_id}/resume", json=request)
    assert first.status_code == 200, first.text
    assert first.json()["resumed"] is True
    assert second.status_code == 409 or second.json().get("resumed") is False
    assert calls == []
    overrides = [d for d in svc.get_decisions(run_id)
                 if d.get("kind") == "override"]
    assert len(overrides) == 1
    db.close()
    engine.dispose()


def test_changed_decision_material_after_review_is_stale(
        tmp_path, monkeypatch):
    from api import goal_run_routes as routes
    from core.models import GoalRun

    engine, factory, db, user, svc = _file_client(
        tmp_path, "changed-decision.db")
    run_id = svc.create_run("goal-family", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    held = _hold(svc, run_id, {
        "decision": "ADVANCE", "rationale": "reviewed rationale"})
    review = _review(held)

    row = db.query(GoalRun).filter(GoalRun.id == run_id).one()
    mutated = dict(row.pending_decision or {})
    mutated["rationale"] = "changed after review"
    row.pending_decision = mutated
    db.commit()

    calls = _execute_counter(monkeypatch, svc)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)
    response = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == "stale_decision_review"
    assert calls == []
    assert svc.get_run(run_id)["pending_decision"]["rationale"] == (
        "changed after review")
    db.close()
    engine.dispose()


def test_new_checkpoint_created_during_execution_stays_pending(
        tmp_path, monkeypatch):
    """Closing A's row after execution must not close a new checkpoint row."""
    from api import goal_run_routes as routes

    engine, factory, db, user, svc = _file_client(
        tmp_path, "checkpoint-during-execution.db")
    run_id = svc.create_run("goal-family", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    held = _hold(svc, run_id, {
        "decision": "ADVANCE", "rationale": "reviewed A"})
    review = _review(held)
    checkpoint_ids = []

    async def execute(run_id, decision):
        checkpoint = HITLAction(
            workspace_id="ws-a", tenant_id="t-a",
            action_type="goal_run_checkpoint", platform="in_app",
            params={"run_id": run_id, "step_id": "cp-new"},
            status=HITLActionStatus.PENDING.value)
        db.add(checkpoint)
        db.commit()
        checkpoint_ids.append(checkpoint.id)
        return {"run": svc.get_run(run_id)}

    monkeypatch.setattr(svc, "execute_decision", execute)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)
    response = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review})
    assert response.status_code == 200, response.text
    assert len(checkpoint_ids) == 1
    checkpoint = db.query(HITLAction).filter(
        HITLAction.id == checkpoint_ids[0]).one()
    assert checkpoint.status == HITLActionStatus.PENDING.value
    a_row = db.query(HITLAction).filter(
        HITLAction.id == held["hitl_id"]).one()
    assert a_row.status == HITLActionStatus.APPROVED.value
    db.close()
    engine.dispose()


def test_integration_action_carries_reviewed_operation_identity(monkeypatch):
    """The same reviewed decision/step resolves to one durable operation id."""
    from core.action_registry import action_registry
    from core.goals.goal_run_executors import GoalRunExecutors

    captured = {}

    async def fake_execute(name, arguments, context):
        captured.update({
            "name": name, "arguments": arguments, "context": context})
        return {"success": True, "remote_id": "remote-1"}

    monkeypatch.setattr(action_registry, "execute_action", fake_execute)
    run = {
        "id": "run-op", "workspace_id": "ws-a", "tenant_id": "t-a",
        "agent_id": "agent-a", "goal_id": "goal-a",
    }
    decision = {"decision": "ADVANCE", "decision_id": "dec-a"}
    step = {
        "id": "step-op", "kind": "integration_action",
        "action": "goal_runs.list", "arguments": {},
    }
    result = asyncio.run(
        GoalRunExecutors(None)._integration_action(run, decision, step))
    assert captured["context"]["operation_id"] == (
        "goal-run:run-op:dec-a:step-op")
    assert result["operation_id"] == "goal-run:run-op:dec-a:step-op"
    assert captured["context"]["goal_run_id"] == "run-op"

    # Retry of the SAME reviewed decision/step is the same operation; a new
    # decision generation is a different one.
    retry = asyncio.run(
        GoalRunExecutors(None)._integration_action(run, decision, step))
    assert retry["operation_id"] == result["operation_id"]
    other = asyncio.run(GoalRunExecutors(None)._integration_action(
        run, {**decision, "decision_id": "dec-b"}, step))
    assert other["operation_id"] != result["operation_id"]


def test_cancelled_run_cannot_dispatch_its_old_held_decision(
        tmp_path, monkeypatch):
    from api import goal_run_routes as routes

    engine, factory, db, user, svc = _file_client(
        tmp_path, "cancelled-held.db")
    run_id = svc.create_run("goal-family", role="sales", plan=PLAN)["id"]
    svc.transition(run_id, "active")
    held = _hold(svc, run_id, {
        "decision": "ADVANCE", "rationale": "would have run"})
    review = _review(held)
    svc.cancel(run_id, reason="operator cancelled")
    calls = _execute_counter(monkeypatch, svc)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db, user)

    response = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"] == "run_terminal"
    assert calls == []
    db.close()
    engine.dispose()


def test_restart_review_effect_and_replay_journey(tmp_path, monkeypatch):
    """One ordinary journey: persisted review -> restart -> effect -> replay."""
    from api import goal_run_routes as routes

    engine, factory, db1, user, creator = _file_client(
        tmp_path, "restart-review-journey.db")
    run_id = creator.create_run(
        "goal-family", role="sales", plan=[])["id"]
    creator.transition(run_id, "active")
    held_a = _hold(creator, run_id, {
        "decision": "ADVANCE", "rationale": "reviewed action A"})
    db1.close()

    db2 = factory()
    svc = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    pending = svc.get_run(run_id)["pending_decision"]
    assert pending["decision_id"] == held_a["decision_id"]
    assert pending["decision_binding"] == held_a["decision_binding"]

    effects = []

    async def execute(run_id, decision):
        effects.append(decision.get("decision_id"))
        if len(effects) == 1:
            _hold(svc, run_id, {
                "decision": "REPLAN",
                "new_plan": [{"id": "new", "kind": "canvas_work",
                              "title": "Unreviewed next decision"}],
                "rationale": "new decision B",
            })
        return {"run": svc.get_run(run_id)}

    monkeypatch.setattr(svc, "execute_decision", execute)
    monkeypatch.setattr(routes, "_service", lambda user, db: svc)
    client = _client(db2, user)
    review_a = {
        "decision_id": pending["decision_id"],
        "decision_binding": pending["decision_binding"],
    }

    first = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review_a})
    assert first.status_code == 200, first.text
    assert effects == [held_a["decision_id"]]
    current = svc.get_run(run_id)
    assert current["pending_decision"]["rationale"] == "new decision B"

    replay = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True, **review_a})
    assert replay.status_code == 409
    assert replay.json()["detail"]["error"] == "stale_decision_review"
    assert effects == [held_a["decision_id"]]

    db3 = factory()
    restarted = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    final = restarted.get_run(run_id)
    assert final["pending_decision"]["rationale"] == "new decision B"
    assert final["pending_decision"]["decision_binding"]
    db2.close(); db3.close()
    engine.dispose()
