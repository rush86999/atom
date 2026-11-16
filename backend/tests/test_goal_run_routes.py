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
from core.models import (
    AuditLog, GoalObjective, GoalRun, HITLAction, HITLActionStatus, User,
    UserRole,
)


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
        workspace_id="ws-test",
    ))
    db_session.add(User(
        id="gr-emp", email="gr-emp@example.com", first_name="Emp",
        last_name="Loyee", role=UserRole.MEMBER.value, status="active",
        workspace_id="ws-test",
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
    reviewed = created["run"]["pending_decision"]
    resumed = client.post(
        f"/api/goal-runs/{run_id}/resume",
        json={"approved": True,
              "decision_id": reviewed["decision_id"],
              "decision_binding": reviewed["decision_binding"]}).json()
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

    # Workspace-bound like every surface (the route created the run in the
    # requester's workspace "ws-test"; the service is scoped to it since
    # the 2026-09-13 cross-workspace IDOR fix).
    svc = GoalRunService(workspace_id="ws-test", tenant_id="default",
                         session_factory=_sess)
    svc.set_plan(run_id, [{"id": "seed-3", "kind": "human_checkpoint",
                           "title": "Quote approval"}])
    out = client.post(f"/api/goal-runs/{run_id}/advance").json()
    assert out["advanced"] is True
    run = client.get(f"/api/goal-runs/{run_id}").json()
    assert run["status"] == "waiting"
    hitl_id = run["waiting_on"]["match"]["hitl_id"]
    resolved_resp = client.post(
        f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
        json={"approved": True, "guidance": "quote looks right"})
    assert resolved_resp.status_code == 200, resolved_resp.text
    resolved = resolved_resp.json()
    assert resolved["resumed"] is True
    run = client.get(f"/api/goal-runs/{run_id}").json()
    assert run["status"] != "waiting"
    hitl = svc_env.query(HITLAction).filter(HITLAction.id == hitl_id).one()
    assert hitl.status == HITLActionStatus.APPROVED.value


def _make_waiting_checkpoint(
    client: TestClient, db, title: str = "Quote approval",
    *, plan=None, cursor=None,
):
    """Create one dormant run and drive it to a real checkpoint wait."""
    from contextlib import contextmanager
    from core.goals.goal_run_service import GoalRunService

    run_id = client.post("/api/goal-runs", json={
        "goal_id": "goal-1", "supervision_mode": "shadow",
        "start": False}).json()["id"]

    @contextmanager
    def _sess():
        yield db

    svc = GoalRunService(workspace_id="ws-test", tenant_id="default",
                         session_factory=_sess)
    svc.set_plan(run_id, plan or [{
        "id": "step-approval", "kind": "human_checkpoint", "title": title,
    }])
    if cursor:
        svc._set_cursor(run_id, cursor)
    advanced = client.post(f"/api/goal-runs/{run_id}/advance")
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["advanced"] is True
    run = client.get(f"/api/goal-runs/{run_id}").json()
    assert run["status"] == "waiting"
    hitl_id = run["waiting_on"]["match"]["hitl_id"]
    db.expire_all()
    return run_id, hitl_id


def _checkpoint_state(db, run_id: str, hitl_id: str):
    db.expire_all()
    run = db.query(GoalRun).filter(GoalRun.id == run_id).one()
    hitl = db.query(HITLAction).filter(HITLAction.id == hitl_id).one()
    return {
        "run_status": run.status,
        "waiting_on": run.waiting_on,
        "plan": list(run.plan or []),
        "cursor": run.cursor,
        "steps_executed": run.steps_executed,
        "revision": run.material_revision,
        "decision_log": list(run.decision_log or []),
        "hitl_status": hitl.status,
        "hitl_reviewed_by": hitl.reviewed_by,
        "hitl_feedback": hitl.user_feedback,
        "audit_count": db.query(AuditLog).count(),
    }


def test_cancelled_checkpoint_resolution_refuses_without_mutation(
    supervisor_env, monkeypatch,
):
    """The reported defect: cancelled run + pending checkpoint must not mark
    HITL approved, change wait/plan/cursor/decision, or invoke advance."""
    client = _make_client(supervisor_env, "gr-lead")
    run_id, hitl_id = _make_waiting_checkpoint(client, supervisor_env)
    cancelled = client.post(f"/api/goal-runs/{run_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    before = _checkpoint_state(supervisor_env, run_id, hitl_id)
    assert before["run_status"] == "cancelled"
    assert before["hitl_status"] == HITLActionStatus.PENDING.value

    from core.goals.goal_run_service import GoalRunService
    advance_calls = []

    async def no_advance(self, *args, **kwargs):
        advance_calls.append((args, kwargs))
        raise AssertionError("stale checkpoint must not invoke advance")

    monkeypatch.setattr(GoalRunService, "advance", no_advance)

    response = client.post(
        f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
        json={"approved": True, "guidance": "late approval"},
    )
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["detail"]["error"]["code"] == "CHECKPOINT_STALE"
    assert "refresh" in body["detail"]["error"]["message"].lower()
    assert advance_calls == []

    after = _checkpoint_state(supervisor_env, run_id, hitl_id)
    assert after == before
    assert after["hitl_status"] == HITLActionStatus.PENDING.value


def test_checkpoint_rejection_preserves_rewind_semantics(
    supervisor_env, monkeypatch,
):
    client = _make_client(supervisor_env, "gr-lead")
    run_id, hitl_id = _make_waiting_checkpoint(
        client, supervisor_env,
        plan=[
            {"id": "step-work", "kind": "canvas_work", "title": "Draft"},
            {"id": "step-approval", "kind": "human_checkpoint",
             "title": "Quote approval"},
        ],
        cursor="step-approval",
    )

    from core.goals.goal_run_service import GoalRunService

    async def no_advance(self, *args, **kwargs):
        return {"advanced": True, "decision": "ADVANCE"}

    monkeypatch.setattr(GoalRunService, "advance", no_advance)
    response = client.post(
        f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
        json={"approved": False, "guidance": "revise the quote"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["resumed"] is True
    after = _checkpoint_state(supervisor_env, run_id, hitl_id)
    assert after["run_status"] == "active"
    assert after["waiting_on"] is None
    assert after["hitl_status"] == HITLActionStatus.REJECTED.value
    assert after["hitl_feedback"] == "revise the quote"
    assert after["cursor"] == "step-work"
    checkpoint_step = next(
        s for s in after["plan"] if s["id"] == "step-approval")
    assert checkpoint_step.get("done") is not True


def test_checkpoint_replay_refuses_without_second_advance(
    supervisor_env, monkeypatch,
):
    client = _make_client(supervisor_env, "gr-lead")
    run_id, hitl_id = _make_waiting_checkpoint(client, supervisor_env)

    from core.goals.goal_run_service import GoalRunService
    original_advance = GoalRunService.advance
    advance_calls = []

    async def counted_advance(self, *args, **kwargs):
        advance_calls.append((args, kwargs))
        return await original_advance(self, *args, **kwargs)

    monkeypatch.setattr(GoalRunService, "advance", counted_advance)
    first = client.post(
        f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
        json={"approved": True, "guidance": "quote looks right"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["resumed"] is True
    assert len(advance_calls) == 1
    after_first = _checkpoint_state(supervisor_env, run_id, hitl_id)

    replay = client.post(
        f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
        json={"approved": True, "guidance": "again"},
    )
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["error"]["code"] == (
        "CHECKPOINT_ALREADY_RESOLVED")
    assert len(advance_calls) == 1
    after_replay = _checkpoint_state(supervisor_env, run_id, hitl_id)
    assert after_replay == after_first
    assert after_replay["hitl_status"] == HITLActionStatus.APPROVED.value


def test_wrong_checkpoint_and_foreign_authority_refuse_without_mutation(
    supervisor_env, monkeypatch,
):
    client = _make_client(supervisor_env, "gr-lead")
    run_a, hitl_a = _make_waiting_checkpoint(client, supervisor_env, "A")
    run_b, hitl_b = _make_waiting_checkpoint(client, supervisor_env, "B")
    before_a = _checkpoint_state(supervisor_env, run_a, hitl_a)
    before_b = _checkpoint_state(supervisor_env, run_b, hitl_b)

    from core.goals.goal_run_service import GoalRunService
    advance_calls = []

    async def no_advance(self, *args, **kwargs):
        advance_calls.append((args, kwargs))
        raise AssertionError("refused checkpoint must not invoke advance")

    monkeypatch.setattr(GoalRunService, "advance", no_advance)

    # A real checkpoint id from another run is not a current checkpoint for A.
    wrong = client.post(
        f"/api/goal-runs/{run_a}/checkpoints/{hitl_b}/resolve",
        json={"approved": True},
    )
    assert wrong.status_code == 404, wrong.text
    assert advance_calls == []
    assert _checkpoint_state(supervisor_env, run_a, hitl_a) == before_a
    assert _checkpoint_state(supervisor_env, run_b, hitl_b) == before_b

    # A non-owner member cannot act on someone else's run.
    member = _make_client(supervisor_env, "gr-emp")
    foreign = member.post(
        f"/api/goal-runs/{run_a}/checkpoints/{hitl_a}/resolve",
        json={"approved": True},
    )
    assert foreign.status_code == 403, foreign.text
    assert advance_calls == []
    assert _checkpoint_state(supervisor_env, run_a, hitl_a) == before_a


def test_peer_cancel_between_snapshot_and_claim_refuses(
    supervisor_env, monkeypatch,
):
    """A peer cancel that lands after the snapshot but before the conditional
    claim must win wholly; the first request may not leave HITL approved."""
    client = _make_client(supervisor_env, "gr-lead")
    run_id, hitl_id = _make_waiting_checkpoint(client, supervisor_env)

    from sqlalchemy.orm import sessionmaker
    from core.goals.goal_run_service import GoalRunService

    PeerSession = sessionmaker(bind=supervisor_env.get_bind())
    peer_db = PeerSession()
    peer_client = _make_client(peer_db, "gr-lead")
    original_snapshot = GoalRunService._checkpoint_claim_snapshot
    fired = {"value": False}

    def peer_then_snapshot(self, session, rid, hid):
        snapshot = original_snapshot(self, session, rid, hid)
        if not fired["value"]:
            fired["value"] = True
            peer = peer_client.post(f"/api/goal-runs/{rid}/cancel")
            assert peer.status_code == 200, peer.text
        return snapshot

    monkeypatch.setattr(
        GoalRunService, "_checkpoint_claim_snapshot", peer_then_snapshot)

    try:
        response = client.post(
            f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
            json={"approved": True, "guidance": "racing approval"},
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["error"]["code"] == "CHECKPOINT_STALE"
        after = _checkpoint_state(supervisor_env, run_id, hitl_id)
        assert after["run_status"] == "cancelled"
        assert after["hitl_status"] == HITLActionStatus.PENDING.value
        assert after["hitl_reviewed_by"] is None
    finally:
        peer_db.close()


def test_peer_resolve_between_snapshot_and_claim_refuses(
    supervisor_env, monkeypatch,
):
    """A peer resolution may win; the loser must not mark/replay or advance."""
    client = _make_client(supervisor_env, "gr-lead")
    run_id, hitl_id = _make_waiting_checkpoint(client, supervisor_env)

    from sqlalchemy.orm import sessionmaker
    from core.goals.goal_run_service import GoalRunService

    PeerSession = sessionmaker(bind=supervisor_env.get_bind())
    peer_db = PeerSession()
    peer_client = _make_client(peer_db, "gr-lead")
    original_snapshot = GoalRunService._checkpoint_claim_snapshot
    original_advance = GoalRunService.advance
    advance_calls = []
    fired = {"value": False}

    async def counted_advance(self, *args, **kwargs):
        advance_calls.append((args, kwargs))
        return await original_advance(self, *args, **kwargs)

    def peer_then_snapshot(self, session, rid, hid):
        snapshot = original_snapshot(self, session, rid, hid)
        if not fired["value"]:
            fired["value"] = True
            peer = peer_client.post(
                f"/api/goal-runs/{rid}/checkpoints/{hid}/resolve",
                json={"approved": True, "guidance": "peer approval"},
            )
            assert peer.status_code == 200, peer.text
        return snapshot

    monkeypatch.setattr(GoalRunService, "advance", counted_advance)
    monkeypatch.setattr(
        GoalRunService, "_checkpoint_claim_snapshot", peer_then_snapshot)

    try:
        response = client.post(
            f"/api/goal-runs/{run_id}/checkpoints/{hitl_id}/resolve",
            json={"approved": True, "guidance": "late approval"},
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["error"]["code"] == (
            "CHECKPOINT_ALREADY_RESOLVED")
        assert len(advance_calls) == 1  # peer's valid resolution only
        after = _checkpoint_state(supervisor_env, run_id, hitl_id)
        assert after["hitl_status"] == HITLActionStatus.APPROVED.value
    finally:
        peer_db.close()


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

    svc = GoalRunService(workspace_id="ws-test", tenant_id="default",
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
