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

    first = _client(db_session, lead_a).post(
        f"/api/goal-runs/{run_id}/resume", json={"approved": True})
    second = _client(db_session, second_lead).post(
        f"/api/goal-runs/{run_id}/resume", json={"approved": True})

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
    _hold(creator, run_id)
    state["race"] = True

    results = []

    def worker(reviewer):
        svc = RacingService(
            workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
        try:
            results.append(asyncio.run(
                svc.resume(run_id, approved=True, reviewer=reviewer)))
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
    _hold(writer, run_id, {"decision": "ADVANCE", "rationale": "old"})
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
        run_id, approved=True, reviewer="lead-a"))

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
    _hold(first, run_id)

    # Fresh process-like boundary: no shared session/identity map.
    second = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    pending = second.get_run(run_id)
    assert pending["pending_decision"]["decision"] == "ADVANCE"
    assert asyncio.run(second.resume(
        run_id, approved=True, reviewer="lead-b"))["resumed"] is True

    third = GoalRunService(
        workspace_id="ws-a", tenant_id="t-a", session_factory=factory)
    after = third.get_run(run_id)
    assert after["pending_decision"] is None
    assert len([d for d in after["decision_log"]
                if d.get("kind") == "approved"]) == 1
    assert asyncio.run(third.resume(
        run_id, approved=True, reviewer="lead-a"))["resumed"] is False
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
