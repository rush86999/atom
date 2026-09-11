"""Slice 5 tests — /api/goal-runs routes (RBAC + lifecycle)
(docs/architecture/GOAL_RUN_ORCHESTRATION.md §5, §7 slice 5).

Pattern: isolated FastAPI app + dependency overrides (mirrors
test_canvas_training_context.py). The db_session fixture is the conftest's
worker-scoped scratch DB with transaction rollback — never the live dev DB.
"""

import os
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "1")

from api.goal_run_routes import router
from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import GoalObjective, HITLAction, HITLActionStatus, User, UserRole


def _make_client(db, viewer_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    # ONE user object per client (not per request): the workspace resolver
    # reads user.workspace_id, and a fresh Mock per request would mint a
    # different auto-attribute every call. Explicit string so both clients
    # (supervisor + employee) share the same workspace scope.
    user = Mock(id=viewer_id, tenant_id=None, status="active",
                workspace_id="ws-test")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_router(monkeypatch):
    """Deterministic router for route tests: always ADVANCE. (The real
    router is covered in test_goal_run_loop.py.)"""

    class _Stub:
        async def decide(self, context):
            return {"decision": "ADVANCE", "rationale": "stub",
                    "confidence": 0.9}

    from core.goals.goal_run_service import GoalRunService
    monkeypatch.setattr(GoalRunService, "_default_router",
                        lambda self: _Stub())


@pytest.fixture
def supervisor_env(db_session):
    db_session.add(User(
        id="gr-lead", email="gr-lead@example.com", first_name="Goal",
        last_name="Lead", role=UserRole.TEAM_LEAD.value, status="active",
    ))
    db_session.add(User(
        id="gr-emp", email="gr-emp@example.com", first_name="Emp",
        last_name="Loyee", role=UserRole.MEMBER.value, status="active",
    ))
    db_session.add(GoalObjective(
        id="goal-1", workspace_id="default", tenant_id=None,
        title="Prepare a quote for the Acme lead", status="active"))
    db_session.commit()
    return db_session


def test_member_create_requires_role_based_shape(supervisor_env):
    """Role-based access: a member may start their OWN role-based run, but
    not a role-less one (422) and not with supervisor-grade shape (403)."""
    client = _make_client(supervisor_env, "gr-emp")
    roleless = client.post("/api/goal-runs", json={"goal_id": "goal-1"})
    assert roleless.status_code == 422
    ok = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "role": "support", "supervision_mode": "training"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["run"]["created_by"] == "gr-emp"
    gated = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "role": "support",
        "plan": [{"id": "s1", "kind": "canvas_work", "title": "x"}]})
    assert gated.status_code == 403


def test_create_run_seeds_plan_and_kickoff(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    resp = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "agent_id": "agent-1", "role": "sales",
        "supervision_mode": "training"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["seed_source"] == "fallback"   # no playbooks match in scratch DB
    assert body["run"]["supervision_mode"] == "training"
    assert [s["kind"] for s in body["run"]["plan"]] == [
        "canvas_work", "canvas_work", "human_checkpoint"]
    # 2026-09-10 kickoff: the run starts working on create. In training mode
    # that means the very FIRST decision is held for the supervisor — the run
    # is not a dormant shell waiting for someone to find "Advance".
    assert body["started"]["held"] is True
    assert body["run"]["status"] == "paused_hitl"
    assert body["run"]["pending_decision"]["decision"] in ("ADVANCE", "ASK_HUMAN")


def test_create_unknown_goal_404(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    resp = client.post("/api/goal-runs", json={"goal_id": "nope"})
    assert resp.status_code == 404


def test_list_and_detail(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    # start=False stages a dormant run — the pre-kickoff contract, kept
    # available for callers that want to schedule a run rather than start it.
    run_id = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "supervision_mode": "shadow",
        "start": False}).json()["id"]
    listed = client.get("/api/goal-runs").json()["runs"]
    assert run_id in [r["id"] for r in listed]
    detail = client.get(f"/api/goal-runs/{run_id}").json()
    assert detail["id"] == run_id
    assert detail["decision_log"] == []
    missing = client.get("/api/goal-runs/does-not-exist")
    assert missing.status_code == 404


def test_advance_and_resume_flow(supervisor_env, monkeypatch):
    client = _make_client(supervisor_env, "gr-lead")
    created = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "supervision_mode": "training"}).json()
    run_id = created["id"]
    # Training mode: the kickoff decision already holds for approval, so the
    # loop is not advanced again here (a second advance would 409 nothing —
    # it is genuinely waiting on the human).
    assert created["started"]["held"] is True
    assert created["run"]["status"] == "paused_hitl"
    # Employee cannot resume; supervisor can.
    emp = _make_client(supervisor_env, "gr-emp")
    assert emp.post(f"/api/goal-runs/{run_id}/resume",
                    json={"approved": True}).status_code == 403
    resumed = client.post(f"/api/goal-runs/{run_id}/resume",
                          json={"approved": True}).json()
    assert resumed["resumed"] is True
    assert resumed["decision"] in ("ADVANCE", "ASK_HUMAN")


def test_checkpoint_resolution(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    run_id = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "supervision_mode": "shadow"}).json()["id"]
    # Drive the run onto a checkpoint step, then advance → the executor
    # creates the checkpoint HITL row and the run waits on it.
    svc_env = supervisor_env
    from core.goals.goal_run_service import GoalRunService
    from contextlib import contextmanager

    @contextmanager
    def _sess():
        yield svc_env

    svc = GoalRunService(workspace_id="default", tenant_id="default",
                         session_factory=_sess)
    svc.set_plan(run_id, [{"id": "seed-3", "kind": "human_checkpoint",
                           "title": "Quote approval"}])
    out = client.post(f"/api/goal-runs/{run_id}/advance").json()
    assert out["advanced"] is True
    run = client.get(f"/api/goal-runs/{run_id}").json()
    assert run["status"] == "waiting"
    hitl_id = run["waiting_on"]["match"]["hitl_id"]
    resolved = client.post(
        f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
        json={"approved": True, "guidance": "quote looks right"}).json()
    assert resolved["resumed"] is True
    run = client.get(f"/api/goal-runs/{run_id}").json()
    assert run["status"] != "waiting"
    hitl = svc_env.query(HITLAction).filter(HITLAction.id == hitl_id).one()
    assert hitl.status == HITLActionStatus.APPROVED.value


def test_event_ingestion_endpoint(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    run_id = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "supervision_mode": "shadow"}).json()["id"]
    svc_env = supervisor_env
    from core.goals.goal_run_service import GoalRunService
    from contextlib import contextmanager

    @contextmanager
    def _sess():
        yield svc_env

    svc = GoalRunService(workspace_id="default", tenant_id="default",
                         session_factory=_sess)
    svc.set_wait(run_id, {"event": "email_reply",
                          "match": {"from": "acme@x.com"}})
    out = client.post("/api/goal-runs/events", json={
        "event": "email_reply", "from": "acme@x.com",
        "subject": "Re: quote"}).json()
    assert out["woke"] == [run_id]


def test_event_ingestion_requires_supervisor(supervisor_env):
    """Inbound events wake runs and drive router decisions/executor actions —
    a member must not be able to inject them."""
    member = _make_client(supervisor_env, "gr-emp")
    resp = member.post("/api/goal-runs/events",
                       json={"event": "email_reply", "from": "acme@x.com"})
    assert resp.status_code == 403


def test_mode_change_requires_supervisor(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    run_id = client.post("/api/goal-runs", json={
        "goal_id": "goal-1"}).json()["id"]
    emp = _make_client(supervisor_env, "gr-emp")
    assert emp.post(f"/api/goal-runs/{run_id}/mode",
                    json={"supervision_mode": "autonomous"}).status_code == 403
    ok = client.post(f"/api/goal-runs/{run_id}/mode",
                     json={"supervision_mode": "shadow"}).json()
    assert ok["run"]["supervision_mode"] == "shadow"
    bad = client.post(f"/api/goal-runs/{run_id}/mode",
                      json={"supervision_mode": "solo"}).status_code
    assert bad == 422


def test_distill_route(supervisor_env, monkeypatch):
    client = _make_client(supervisor_env, "gr-lead")
    run_id = client.post("/api/goal-runs", json={
        "goal_id": "goal-1"}).json()["id"]
    # Thin run → nothing to distill → 409 (deterministic, no monkeypatch).
    thin = client.post(f"/api/goal-runs/{run_id}/distill")
    assert thin.status_code == 409
    # A finished run with decisions → draft (fn monkeypatched; covered in
    # test_goal_run_learning.py).
    from core.goals import goal_run_learning
    from core.goals.goal_run_service import GoalRunService
    from contextlib import contextmanager

    @contextmanager
    def _sess():
        yield supervisor_env

    svc = GoalRunService(workspace_id="ws-test", tenant_id="default",
                         session_factory=_sess)
    svc.transition(run_id, "cancelled")
    for d in ({"decision": "ADVANCE", "rationale": "a"},
              {"decision": "ADVANCE", "rationale": "b"},
              {"decision": "WAIT", "rationale": "c"}):
        svc.append_decision(run_id, {"kind": "decision", **d})
    monkeypatch.setattr(
        goal_run_learning, "distill_run_to_playbook_draft",
        lambda run, **kw: {"id": "pb-1", "name": "draft",
                           "approval_state": "draft", "steps": ["x"]})
    ok = client.post(f"/api/goal-runs/{run_id}/distill").json()
    assert ok["success"] is True and ok["draft"]["id"] == "pb-1"
    emp = _make_client(supervisor_env, "gr-emp")
    assert emp.post(f"/api/goal-runs/{run_id}/distill").status_code == 403


def test_promotion_endpoint(supervisor_env):
    client = _make_client(supervisor_env, "gr-lead")
    out = client.get("/api/goal-runs/promotion/agent-x").json()
    assert out["recommendation"] in ("training", "shadow", "autonomous")
    assert "evidence" in out
