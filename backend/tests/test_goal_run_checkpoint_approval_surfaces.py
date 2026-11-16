"""Mounted-route tests: human-checkpoint decisions through EVERY live surface.

The same checkpoint operation is reachable through two mounted handlers at
``/api/agents/approvals/{id}`` — the legacy handler in ``api.agent_routes``
(mounted first by the app) and the UI-contract alias in
``api.approvals_routes`` — plus the shared ``resume_after_hitl_decision``
bridge. All three previously wrote the HITL status BEFORE consuming the
run's wake, so a cancelled/stale/replayed decision could leave a
``goal_run_checkpoint`` row approved while the run never resumed.

These lock the shared contract: the exact current-wait claim runs first (one
transaction), refusals mutate nothing and invoke no loop turn, and a valid
approve/reject still resumes exactly once. Scratch DB only (the conftest
worker database); no provider, app server, or live data.
"""

import asyncio
import os
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.auth import get_current_user
from core.database import get_db as _get_db
from core.models import (
    AuditLog, GoalObjective, GoalRun, HITLAction, HITLActionStatus, User,
    UserRole,
)


@pytest.fixture(autouse=True)
def stub_router(monkeypatch):
    """Deterministic decision router (the real one is covered elsewhere)."""

    class _Stub:
        async def decide(self, context):
            return {"decision": "ADVANCE", "rationale": "stub",
                    "confidence": 0.9}

    from core.goals.goal_run_service import GoalRunService
    monkeypatch.setattr(GoalRunService, "_default_router",
                        lambda self: _Stub())


def _user(uid: str, role: UserRole, workspace: str) -> User:
    return User(
        id=uid, email=f"{uid}@example.com", first_name="T", last_name="U",
        role=role.value, status="active", is_active=True,
        workspace_id=workspace,
    )


@pytest.fixture
def approval_env(db_session):
    db_session.add_all([
        _user("ck-admin", UserRole.ADMIN, "ws-test"),
        _user("ck-lead", UserRole.TEAM_LEAD, "ws-test"),
        _user("ck-member", UserRole.MEMBER, "ws-test"),
        _user("ck-other-admin", UserRole.ADMIN, "ws-other"),
        _user("ck-default-admin", UserRole.ADMIN, None),
    ])
    db_session.add(User(
        id="ck-other-tenant", email="ck-other-tenant@example.com",
        first_name="T", last_name="U", role=UserRole.ADMIN.value,
        status="active", is_active=True, workspace_id="ws-test",
        tenant_id="tenant-b",
    ))
    db_session.add(User(
        id="ck-inactive", email="ck-inactive@example.com",
        first_name="T", last_name="U", role=UserRole.ADMIN.value,
        status="inactive", is_active=False, workspace_id="ws-test",
    ))
    db_session.add(GoalObjective(
        id="goal-ck", workspace_id="ws-test", tenant_id=None,
        title="Prepare a quote for the Acme lead", status="active"))
    db_session.commit()
    return db_session


@contextmanager
def _session_over(db):
    yield db


def make_waiting_checkpoint(db, *, plan=None, cursor=None,
                            created_by="ck-lead", workspace="ws-test",
                            tenant="default"):
    """Create a real run and drive it onto a checkpoint wait."""
    from core.goals.goal_run_service import GoalRunService

    svc = GoalRunService(workspace_id=workspace, tenant_id=tenant,
                         session_factory=lambda: _session_over(db))
    plan = plan or [{
        "id": "step-cp", "kind": "human_checkpoint",
        "title": "Quote approval",
    }]
    run = svc.create_run("goal-ck", supervision_mode="shadow", plan=plan,
                         created_by=created_by)
    run_id = run["id"]
    if cursor:
        svc._set_cursor(run_id, cursor)
    svc.transition(run_id, "active")
    out = asyncio.run(svc.advance(run_id))
    assert out.get("advanced") is True, out
    run = svc.get_run(run_id)
    assert run["status"] == "waiting", run
    assert (run.get("waiting_on") or {}).get("event") == "human_checkpoint"
    return run_id, run["waiting_on"]["match"]["hitl_id"]


def _state(db, run_id: str, hitl_id: str):
    db.expire_all()
    run = db.query(GoalRun).filter(GoalRun.id == run_id).one()
    hitl = db.query(HITLAction).filter(HITLAction.id == hitl_id).one()
    return {
        "status": run.status,
        "waiting_on": run.waiting_on,
        "plan": [dict(s) for s in (run.plan or [])],
        "cursor": run.cursor,
        "steps": run.steps_executed,
        "revision": run.material_revision,
        "log": list(run.decision_log or []),
        "hitl": hitl.status,
        "reviewer": hitl.reviewed_by,
        "feedback": hitl.user_feedback,
        "audits": db.query(AuditLog).count(),
    }


def _client(db, user_id: str, router_obj):
    user = db.query(User).filter(User.id == user_id).one()
    app = FastAPI()
    app.include_router(router_obj)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


def _resume(body: dict) -> dict:
    """Both surfaces expose the bridge outcome; the legacy handler nests it
    under the standard success envelope, the alias returns it flat."""
    if isinstance(body.get("data"), dict):
        return body["data"].get("resume") or {}
    return body.get("resume") or {}


def _error_code(body: dict) -> str:
    detail = body.get("detail") or {}
    if isinstance(detail, dict):
        error = detail.get("error")
        if isinstance(error, dict):
            return str(error.get("code") or "")
        if isinstance(error, str):
            return error
    return ""


def _forbid_advance(monkeypatch, calls):
    from core.goals.goal_run_service import GoalRunService

    async def no_advance(self, *args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("refused checkpoint must not advance")

    monkeypatch.setattr(GoalRunService, "advance", no_advance)


def _count_advance(monkeypatch, calls):
    from core.goals.goal_run_service import GoalRunService

    original = GoalRunService.advance

    async def counted(self, *args, **kwargs):
        calls.append((args, kwargs))
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(GoalRunService, "advance", counted)


def _cancel_after_snapshot(monkeypatch, db):
    """Peer cancellation that lands between the claim's read and its write."""
    from core.goals.goal_run_service import GoalRunService

    original = GoalRunService._checkpoint_claim_snapshot
    fired = {"value": False}

    def peer_then_snapshot(self, session, run_id, hitl_id):
        snapshot = original(self, session, run_id, hitl_id)
        if not fired["value"]:
            fired["value"] = True
            PeerSession = sessionmaker(bind=db.get_bind())
            peer_db = PeerSession()
            try:
                @contextmanager
                def _peer_session():
                    yield peer_db

                GoalRunService(
                    workspace_id="ws-test", tenant_id="default",
                    session_factory=_peer_session,
                ).cancel(run_id, reason="peer cancel")
            finally:
                peer_db.close()
        return snapshot

    monkeypatch.setattr(
        GoalRunService, "_checkpoint_claim_snapshot", peer_then_snapshot)


# --------------------------------------------------------------- legacy surface


def _agent_router():
    from api.agent_routes import router
    return router


def test_agent_surface_cancelled_refuses_without_mutation(
    approval_env, monkeypatch,
):
    """Regression: the legacy handler used to flip the HITL row approved and
    return 200 while the cancelled run never resumed."""
    from core.goals.goal_run_service import GoalRunService
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    GoalRunService(workspace_id="ws-test", tenant_id="default",
                   session_factory=lambda: _session_over(db)).cancel(run_id)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    response = _client(db, "ck-admin", _agent_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert response.status_code == 409, response.text
    assert _error_code(response.json()) == "CHECKPOINT_STALE"
    assert calls == []
    after = _state(db, run_id, hitl_id)
    assert after == before
    assert after["hitl"] == HITLActionStatus.PENDING.value
    assert after["reviewer"] is None


def test_agent_surface_valid_approve_resumes_once(approval_env, monkeypatch):
    from core.goals.goal_run_service import GoalRunService
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _count_advance(monkeypatch, calls)

    response = _client(db, "ck-admin", _agent_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert _resume(body)["resumed"] is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.APPROVED.value
    assert after["reviewer"] == "ck-admin"
    assert after["status"] != "waiting"
    assert after["waiting_on"] is None
    step = next(s for s in after["plan"] if s["id"] == "step-cp")
    assert step.get("done") is True
    # Same counters as the previous valid path: complete_checkpoint counts
    # the checkpoint, then the resulting loop turn counts its decision.
    assert after["steps"] == before["steps"] + 2
    # The claim records the human wake; the loop turn then records its own
    # decision after it.
    assert any(entry.get("kind") == "wake" for entry in after["log"])


def test_agent_surface_valid_reject_rewinds(approval_env, monkeypatch):
    from core.goals.goal_run_service import GoalRunService
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(
        db,
        plan=[
            {"id": "step-work", "kind": "canvas_work", "title": "Draft"},
            {"id": "step-cp", "kind": "human_checkpoint",
             "title": "Quote approval"},
        ],
        cursor="step-cp",
    )
    calls = []

    async def no_loop(self, *args, **kwargs):
        calls.append((args, kwargs))
        return {"advanced": True}

    monkeypatch.setattr(GoalRunService, "advance", no_loop)

    response = _client(db, "ck-admin", _agent_router()).post(
        f"/api/agents/approvals/{hitl_id}",
        json={"decision": "rejected", "feedback": "revise the price"})

    assert response.status_code == 200, response.text
    assert _resume(response.json())["resumed"] is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.REJECTED.value
    assert after["feedback"] == "revise the price"
    assert after["status"] == "active"
    assert after["waiting_on"] is None
    assert after["cursor"] == "step-work"
    checkpoint = next(s for s in after["plan"] if s["id"] == "step-cp")
    assert checkpoint.get("done") is not True


def test_agent_surface_replay_refuses_without_second_advance(
    approval_env, monkeypatch,
):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    calls = []
    _count_advance(monkeypatch, calls)
    client = _client(db, "ck-admin", _agent_router())

    first = client.post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})
    assert first.status_code == 200, first.text
    assert len(calls) == 1
    after_first = _state(db, run_id, hitl_id)

    replay = client.post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert replay.status_code == 409, replay.text
    assert _error_code(replay.json()) == "CHECKPOINT_ALREADY_RESOLVED"
    assert len(calls) == 1
    assert _state(db, run_id, hitl_id) == after_first


def test_agent_surface_foreign_authority_refuses(approval_env, monkeypatch):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    member = _client(db, "ck-member", _agent_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})
    assert member.status_code == 403, member.text

    foreign = _client(db, "ck-other-admin", _agent_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})
    assert foreign.status_code == 404, foreign.text

    assert calls == []
    assert _state(db, run_id, hitl_id) == before
    assert before["hitl"] == HITLActionStatus.PENDING.value


def test_agent_surface_peer_cancel_between_snapshot_and_claim_refuses(
    approval_env, monkeypatch,
):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    calls = []
    _forbid_advance(monkeypatch, calls)
    _cancel_after_snapshot(monkeypatch, db)

    response = _client(db, "ck-admin", _agent_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert response.status_code == 409, response.text
    assert _error_code(response.json()) == "CHECKPOINT_STALE"
    assert calls == []
    after = _state(db, run_id, hitl_id)
    assert after["status"] == "cancelled"
    assert after["hitl"] == HITLActionStatus.PENDING.value
    assert after["reviewer"] is None


# ---------------------------------------------------------------- alias surface


def _alias_router():
    from api.approvals_routes import router
    return router


def test_alias_surface_cancelled_refuses_without_mutation(
    approval_env, monkeypatch,
):
    from core.goals.goal_run_service import GoalRunService
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    GoalRunService(workspace_id="ws-test", tenant_id="default",
                   session_factory=lambda: _session_over(db)).cancel(run_id)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    response = _client(db, "ck-lead", _alias_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert response.status_code == 409, response.text
    assert _error_code(response.json()) == "CHECKPOINT_STALE"
    assert calls == []
    after = _state(db, run_id, hitl_id)
    assert after == before
    assert after["hitl"] == HITLActionStatus.PENDING.value
    assert after["reviewer"] is None


def test_alias_surface_valid_approve_resumes_once(approval_env, monkeypatch):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _count_advance(monkeypatch, calls)

    response = _client(db, "ck-lead", _alias_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert _resume(body)["resumed"] is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.APPROVED.value
    assert after["reviewer"] == "ck-lead"
    assert after["status"] != "waiting"
    assert after["waiting_on"] is None
    step = next(s for s in after["plan"] if s["id"] == "step-cp")
    assert step.get("done") is True
    assert after["steps"] == before["steps"] + 2  # checkpoint + loop turn


def test_alias_surface_valid_reject_rewinds(approval_env, monkeypatch):
    from core.goals.goal_run_service import GoalRunService
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(
        db,
        plan=[
            {"id": "step-work", "kind": "canvas_work", "title": "Draft"},
            {"id": "step-cp", "kind": "human_checkpoint",
             "title": "Quote approval"},
        ],
        cursor="step-cp",
    )
    calls = []

    async def no_loop(self, *args, **kwargs):
        calls.append((args, kwargs))
        return {"advanced": True}

    monkeypatch.setattr(GoalRunService, "advance", no_loop)

    response = _client(db, "ck-lead", _alias_router()).post(
        f"/api/agents/approvals/{hitl_id}",
        json={"decision": "rejected", "reason": "price is too high"})

    assert response.status_code == 200, response.text
    assert _resume(response.json())["resumed"] is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.REJECTED.value
    assert after["feedback"] == "price is too high"
    assert after["status"] == "active"
    assert after["waiting_on"] is None
    assert after["cursor"] == "step-work"
    checkpoint = next(s for s in after["plan"] if s["id"] == "step-cp")
    assert checkpoint.get("done") is not True


def test_alias_surface_replay_refuses_without_second_advance(
    approval_env, monkeypatch,
):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    calls = []
    _count_advance(monkeypatch, calls)
    client = _client(db, "ck-lead", _alias_router())

    first = client.post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})
    assert first.status_code == 200, first.text
    assert len(calls) == 1
    after_first = _state(db, run_id, hitl_id)

    replay = client.post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "rejected"})

    assert replay.status_code == 409, replay.text
    assert _error_code(replay.json()) == "CHECKPOINT_ALREADY_RESOLVED"
    assert len(calls) == 1
    assert _state(db, run_id, hitl_id) == after_first


def test_alias_surface_foreign_authority_refuses(approval_env, monkeypatch):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    member = _client(db, "ck-member", _alias_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})
    assert member.status_code == 403, member.text

    foreign = _client(db, "ck-other-admin", _alias_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})
    assert foreign.status_code == 404, foreign.text

    assert calls == []
    assert _state(db, run_id, hitl_id) == before
    assert before["hitl"] == HITLActionStatus.PENDING.value


def test_alias_surface_peer_cancel_between_snapshot_and_claim_refuses(
    approval_env, monkeypatch,
):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    calls = []
    _forbid_advance(monkeypatch, calls)
    _cancel_after_snapshot(monkeypatch, db)

    response = _client(db, "ck-lead", _alias_router()).post(
        f"/api/agents/approvals/{hitl_id}", json={"decision": "approved"})

    assert response.status_code == 409, response.text
    assert _error_code(response.json()) == "CHECKPOINT_STALE"
    assert calls == []
    after = _state(db, run_id, hitl_id)
    assert after["status"] == "cancelled"
    assert after["hitl"] == HITLActionStatus.PENDING.value
    assert after["reviewer"] is None


# ------------------------------------------------ shared service guard


def test_intervention_service_approval_uses_claim(approval_env, monkeypatch):
    """Governance/messaging call InterventionService with arbitrary HITL ids.
    A checkpoint row must still claim before writing/resuming."""
    from core.intervention_service import InterventionService

    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    monkeypatch.setattr("core.intervention_service.get_db_session",
                        lambda: _session_over(db))
    calls = []
    _count_advance(monkeypatch, calls)

    result = asyncio.run(InterventionService().approve_intervention(
        hitl_id, "ck-admin"))

    assert result["success"] is True
    assert result.get("resumed") is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.APPROVED.value
    assert after["status"] != "waiting"


def test_intervention_service_cancelled_checkpoint_refuses(
    approval_env, monkeypatch,
):
    from core.goals.goal_run_service import GoalRunService
    from core.intervention_service import InterventionService

    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    GoalRunService(workspace_id="ws-test", tenant_id="default",
                   session_factory=lambda: _session_over(db)).cancel(run_id)
    before = _state(db, run_id, hitl_id)
    monkeypatch.setattr("core.intervention_service.get_db_session",
                        lambda: _session_over(db))
    calls = []
    _forbid_advance(monkeypatch, calls)

    result = asyncio.run(InterventionService().approve_intervention(
        hitl_id, "ck-admin"))

    assert result["success"] is False
    assert result["error_code"] == "CHECKPOINT_STALE"
    assert calls == []
    assert _state(db, run_id, hitl_id) == before


# ------------------------------------------- mounted governance approve/reject


def _governance_client(db, principal, monkeypatch):
    """Mount the PRODUCTION governance router with the test DB/principal."""
    from api.agent_governance_routes import router as governance_router

    monkeypatch.setattr(
        "core.intervention_service.get_db_session",
        lambda: _session_over(db))
    app = FastAPI()
    app.include_router(governance_router)
    app.dependency_overrides[get_current_user] = lambda: principal
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app)


def _governance_user_client(db, user_id, monkeypatch):
    principal = db.query(User).filter(User.id == user_id).one()
    return _governance_client(db, principal, monkeypatch)


def _operation(verb: str, hitl_id: str) -> str:
    if verb == "reject":
        return f"/api/agent-governance/reject/{hitl_id}"
    return f"/api/agent-governance/approve/{hitl_id}"


def _params(verb: str) -> dict:
    return {"reason": "not mine to decide"} if verb == "reject" else {}


@pytest.mark.parametrize("verb", ["approve", "reject"])
@pytest.mark.parametrize(
    "reviewer", ["ck-other-admin", "ck-other-tenant"])
def test_governance_foreign_workspace_or_tenant_refuses(
    approval_env, monkeypatch, verb, reviewer,
):
    """The reported escape: a foreign-scope team_lead/admin could POST the
    governance approve/reject endpoint for another workspace's checkpoint and
    receive 200. It must be a non-2xx scope denial with no durable effect."""
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    response = _governance_user_client(db, reviewer, monkeypatch).post(
        _operation(verb, hitl_id), params=_params(verb))

    assert response.status_code == 404, response.text
    assert _error_code(response.json()) == "CHECKPOINT_SCOPE_DENIED"
    assert calls == []
    after = _state(db, run_id, hitl_id)
    assert after == before
    assert after["hitl"] == HITLActionStatus.PENDING.value
    assert after["reviewer"] is None


def test_governance_inactive_actor_refuses(approval_env, monkeypatch):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    response = _governance_user_client(
        db, "ck-inactive", monkeypatch).post(
            _operation("approve", hitl_id), params=_params("approve"))

    assert response.status_code == 403, response.text
    assert _error_code(response.json()) == "ACCOUNT_INACTIVE"
    assert calls == []
    assert _state(db, run_id, hitl_id) == before


def test_governance_missing_actor_refuses(approval_env, monkeypatch):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)
    ghost = SimpleNamespace(
        id="ck-ghost", role=UserRole.ADMIN.value, status="active",
        is_active=True, workspace_id="ws-test", tenant_id=None)

    response = _governance_client(db, ghost, monkeypatch).post(
        _operation("approve", hitl_id), params=_params("approve"))

    assert response.status_code == 404, response.text
    assert calls == []
    assert _state(db, run_id, hitl_id) == before


def test_bridge_missing_and_inactive_reviewer_refuse(
    approval_env, monkeypatch,
):
    """The shared bridge is the mouth of every non-HTTP caller. A missing or
    inactive reviewer must be refused by the claim itself (401/403), not
    silently recorded as the reviewer."""
    from core.hitl_resume import resolve_goal_run_checkpoint

    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    missing = asyncio.run(resolve_goal_run_checkpoint(
        hitl_id, approved=True, reviewer_id="ck-ghost", db=db))
    assert missing["resumed"] is False
    assert missing["http_status"] == 401
    assert missing["error_code"] == "UNAUTHENTICATED"

    inactive = asyncio.run(resolve_goal_run_checkpoint(
        hitl_id, approved=True, reviewer_id="ck-inactive", db=db))
    assert inactive["resumed"] is False
    assert inactive["http_status"] == 403
    assert inactive["error_code"] == "ACCOUNT_INACTIVE"

    assert calls == []
    assert _state(db, run_id, hitl_id) == before


@pytest.mark.parametrize("verb", ["approve", "reject"])
def test_intervention_service_member_nonowner_refuses(
    approval_env, monkeypatch, verb,
):
    from core.intervention_service import InterventionService

    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    monkeypatch.setattr(
        "core.intervention_service.get_db_session",
        lambda: _session_over(db))
    calls = []
    _forbid_advance(monkeypatch, calls)

    service = InterventionService()
    if verb == "approve":
        result = asyncio.run(service.approve_intervention(
            hitl_id, "ck-member"))
    else:
        result = asyncio.run(service.reject_intervention(
            hitl_id, "ck-member", "no"))

    assert result["success"] is False
    assert result["http_status"] == 403
    assert result["error_code"] == "AUTHORITY_REQUIRED"
    assert calls == []
    assert _state(db, run_id, hitl_id) == before


def test_valid_owner_member_can_decide_own_run(
    approval_env, monkeypatch,
):
    """Owner authority is positive and independent of role band: the member
    who started the run can decide its checkpoint through the service."""
    from core.intervention_service import InterventionService

    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db, created_by="ck-member")
    monkeypatch.setattr(
        "core.intervention_service.get_db_session",
        lambda: _session_over(db))
    calls = []
    _count_advance(monkeypatch, calls)

    result = asyncio.run(InterventionService().approve_intervention(
        hitl_id, "ck-member"))

    assert result["success"] is True, result
    assert result.get("resumed") is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.APPROVED.value
    assert after["reviewer"] == "ck-member"


def test_valid_supervisor_decides_via_governance(approval_env, monkeypatch):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    calls = []
    _count_advance(monkeypatch, calls)

    response = _governance_user_client(db, "ck-lead", monkeypatch).post(
        _operation("approve", hitl_id), params=_params("approve"))

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.APPROVED.value
    assert after["reviewer"] == "ck-lead"
    assert after["status"] != "waiting"


def test_persisted_required_role_is_enforced_on_checkpoint(
    approval_env, monkeypatch,
):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    run_id_ok, hitl_ok = make_waiting_checkpoint(db)
    for checkpoint_id in (hitl_id, hitl_ok):
        hitl = db.query(HITLAction).filter(
            HITLAction.id == checkpoint_id).one()
        hitl.required_role = "admin"
    db.commit()
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    denied = _governance_user_client(db, "ck-lead", monkeypatch).post(
        _operation("approve", hitl_id), params=_params("approve"))

    assert denied.status_code == 403, denied.text
    assert _error_code(denied.json()) == "AUTHORITY_REQUIRED"
    assert calls == []
    assert _state(db, run_id, hitl_id) == before

    # The same required_role is a positive for an admin supervisor.
    monkeypatch.undo()
    allowed_calls = []
    _count_advance(monkeypatch, allowed_calls)
    allowed = _governance_user_client(db, "ck-admin", monkeypatch).post(
        _operation("approve", hitl_ok), params=_params("approve"))
    assert allowed.status_code == 200, allowed.text
    assert len(allowed_calls) == 1
    assert _state(db, run_id_ok, hitl_ok)["hitl"] == (
        HITLActionStatus.APPROVED.value)


def test_checkpoint_snapshot_required_role_is_enforced(
    approval_env, monkeypatch,
):
    """The governance-policy snapshot is the other persisted role source;
    a checkpoint must not ignore it either."""
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    hitl = db.query(HITLAction).filter(HITLAction.id == hitl_id).one()
    hitl.context_snapshot = {"required_role": "admin"}
    db.commit()
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    response = _governance_user_client(db, "ck-lead", monkeypatch).post(
        _operation("approve", hitl_id), params=_params("approve"))

    assert response.status_code == 403, response.text
    assert _error_code(response.json()) == "AUTHORITY_REQUIRED"
    assert calls == []
    assert _state(db, run_id, hitl_id) == before


def test_unknown_persisted_required_role_fails_closed(
    approval_env, monkeypatch,
):
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    hitl = db.query(HITLAction).filter(HITLAction.id == hitl_id).one()
    hitl.required_role = "grand_wizard"
    db.commit()
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)

    response = _governance_user_client(db, "ck-admin", monkeypatch).post(
        _operation("approve", hitl_id), params=_params("approve"))

    assert response.status_code == 403, response.text
    assert _error_code(response.json()) == "AUTHORITY_REQUIRED"
    assert calls == []
    assert _state(db, run_id, hitl_id) == before


def _peer_change_after_authority(monkeypatch, db, user_id, values):
    """A peer write that lands between the authority read and the claim."""
    import core.goal_run_decision_service as authority

    original = authority.resolve_checkpoint_reviewer
    fired = {"value": False}

    def resolve_then_peer(session, *, reviewer, run, action=None):
        result = original(
            session, reviewer=reviewer, run=run, action=action)
        if result.get("ok") and not fired["value"]:
            fired["value"] = True
            PeerSession = sessionmaker(bind=db.get_bind())
            peer = PeerSession()
            try:
                peer.query(User).filter(User.id == user_id).update(
                    values, synchronize_session=False)
                peer.commit()
            finally:
                peer.close()
        return result

    monkeypatch.setattr(
        authority, "resolve_checkpoint_reviewer", resolve_then_peer)
    return fired


@pytest.mark.parametrize("change", ["revoke", "move"])
def test_peer_revocation_or_move_between_authority_and_claim_refuses(
    approval_env, monkeypatch, change,
):
    """The fresh-actor fence, not a process mutex: a reviewer deactivated or
    moved to another workspace AFTER passing the authority read must make the
    atomic claim miss (409 AUTHORITY_CHANGED) with no effects."""
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(db)
    before = _state(db, run_id, hitl_id)
    calls = []
    _forbid_advance(monkeypatch, calls)
    if change == "revoke":
        values = {User.is_active: False, User.status: "inactive"}
    else:
        values = {User.workspace_id: "ws-other"}
    fired = _peer_change_after_authority(
        monkeypatch, db, "ck-admin", values)

    response = _governance_user_client(db, "ck-admin", monkeypatch).post(
        _operation("approve", hitl_id), params=_params("approve"))

    assert fired["value"] is True
    assert response.status_code == 409, response.text
    assert _error_code(response.json()) == "AUTHORITY_CHANGED"
    assert calls == []
    after = _state(db, run_id, hitl_id)
    assert after == before
    assert after["hitl"] == HITLActionStatus.PENDING.value
    assert after["reviewer"] is None


def test_personal_null_and_default_scope_are_the_same_authority(
    approval_env, monkeypatch,
):
    """Preserve Personal Edition semantics: a NULL/default user acts on a
    default-workspace run; a non-default workspace still does not."""
    db = approval_env
    run_id, hitl_id = make_waiting_checkpoint(
        db, workspace="default", tenant="default")
    calls = []
    _count_advance(monkeypatch, calls)

    response = _governance_user_client(
        db, "ck-default-admin", monkeypatch).post(
            _operation("approve", hitl_id), params=_params("approve"))

    assert response.status_code == 200, response.text
    assert len(calls) == 1
    after = _state(db, run_id, hitl_id)
    assert after["hitl"] == HITLActionStatus.APPROVED.value
    assert after["reviewer"] == "ck-default-admin"

    # A run in the Personal default scope is still foreign to ws-other.
    run_id2, hitl_id2 = make_waiting_checkpoint(
        db, workspace="default", tenant="default")
    before2 = _state(db, run_id2, hitl_id2)
    denied = _governance_user_client(
        db, "ck-other-admin", monkeypatch).post(
            _operation("reject", hitl_id2), params=_params("reject"))
    assert denied.status_code == 404, denied.text
    assert _error_code(denied.json()) == "CHECKPOINT_SCOPE_DENIED"
    assert _state(db, run_id2, hitl_id2) == before2
