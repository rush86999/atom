# -*- coding: utf-8 -*-
"""HITL approval parameter history (F4: no silent review rewrite).

The edit-before-approve flow used to overwrite ``HITLAction.params`` in place:
the row kept only the effective payload, so the originally reviewed proposal
was gone after the first approval. This suite locks the replacement contract:

* the deep-copied reviewed proposal and the exact effective payload are kept
  in the row's EXISTING ``context_snapshot`` JSON (append-only history key),
* approval/execution still consume the effective payload,
* actor/time/reason are recorded when the surface actually supplied them,
* a denied/foreign actor, a rejection, or a duplicate decision mutates nothing,
* a restart/cold session can still read original + effective,
* historical approved rows without a receipt report the original as UNKNOWN
  (never rebuilt from the rewritten ``params``),
* the general read projection uses the existing credential sanitizer.

No provider/model/network call, no live app server, no owner DB. Every test
uses a file-backed scratch SQLite database whose URL is asserted below.
"""

import asyncio
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.auth import get_current_user
from core.database import Base
from core.database import get_db as _get_db
from core.intervention_service import (
    HITL_PARAMETER_HISTORY_KEY,
    InterventionService,
    describe_parameter_history,
    pending_decision_conditions,
    record_approved_parameters,
)
from core.models import HITLAction, HITLActionStatus, User, UserRole

WORKSPACE = "ws-param"
TENANT = "tenant-param"


class ScratchDB:
    """A real file-backed database that can be closed/reopened as a restart."""

    def __init__(self, path):
        self.path = path
        self.engine = None
        self.Session = None
        self.db = None

    def open(self):
        url = f"sqlite:///{self.path}"
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        # TEST-ONLY guard requested by the workorder: never the dev DB.
        assert str(engine.url).startswith("sqlite:///")
        assert str(self.path) in str(engine.url)
        assert "atom.db" not in str(engine.url)
        Base.metadata.create_all(engine)
        self.engine = engine
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        return self.db

    def close(self):
        if self.db is not None:
            self.db.close()
        if self.engine is not None:
            self.engine.dispose()
        self.db = None

    def reopen(self):
        self.close()
        return self.open()


def _user(uid, role, *, workspace=WORKSPACE, active=True):
    return User(
        id=uid,
        email=f"{uid}@example.com",
        hashed_password="x",
        first_name="T",
        last_name="U",
        role=role.value if hasattr(role, "value") else role,
        status="active" if active else "inactive",
        is_active=active,
        workspace_id=workspace,
        tenant_id=TENANT,
    )


def _seed_users(db):
    db.add_all([
        _user("lead-1", UserRole.TEAM_LEAD),
        _user("admin-1", UserRole.ADMIN),
        _user("super-1", UserRole.SUPER_ADMIN),
        _user("member-1", UserRole.MEMBER),
        _user("member-2", UserRole.MEMBER),
        _user("foreign-admin", UserRole.ADMIN, workspace="ws-other"),
        _user("inactive-admin", UserRole.ADMIN, active=False),
    ])


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    store = ScratchDB(tmp_path / "hitl-parameter-history.db")
    db = store.open()
    _seed_users(db)
    db.commit()

    @contextmanager
    def _session():
        # Resolve ``store.db`` at call time so reopen() is a true cold session.
        yield store.db

    monkeypatch.setattr("core.intervention_service.get_db_session", _session)
    monkeypatch.setattr("core.database.get_db_session", _session)
    monkeypatch.setattr("core.workflow_engine.get_db_session", _session)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def concurrent_scratch(tmp_path, monkeypatch):
    """A real file DB where every service call gets its OWN session.

    This is the two-session/two-writer shape the concurrency controls need:
    both callers load the pending row, then race the atomic claim.
    """
    store = ScratchDB(tmp_path / "hitl-parameter-race.db")
    db = store.open()
    _seed_users(db)
    db.commit()

    @contextmanager
    def _session():
        session = store.Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("core.intervention_service.get_db_session", _session)
    monkeypatch.setattr("core.database.get_db_session", _session)
    monkeypatch.setattr("core.workflow_engine.get_db_session", _session)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture()
def svc():
    return InterventionService()


def _new_action(
    db,
    *,
    params=None,
    action_type="send_email",
    required_role=None,
    context_snapshot=None,
):
    action = HITLAction(
        id=f"hitl-{uuid.uuid4()}",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        user_id="member-1",
        action_type=action_type,
        platform="governance_policy",
        params=params if params is not None else {"to": "original@example.com"},
        reason="Needs review",
        required_role=required_role,
        context_snapshot=context_snapshot,
        status=HITLActionStatus.PENDING.value,
    )
    db.add(action)
    db.commit()
    return action.id


def _action(db, action_id):
    db.expire_all()
    return db.query(HITLAction).filter(HITLAction.id == action_id).one()


def _route_client(db, user_id, router):
    user = db.query(User).filter(User.id == user_id).one()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _alias_client(db, user_id):
    from api.approvals_routes import router as approvals_router

    return _route_client(db, user_id, approvals_router)


def _agent_client(db, user_id):
    from api.agent_routes import router as agent_router

    return _route_client(db, user_id, agent_router)


def _concurrent_agent_client(store, user_id):
    """Legacy mounted route with a FRESH DB session per request (race shape)."""
    from api.agent_routes import router as agent_router

    user = store.db.query(User).filter(User.id == user_id).one()
    app = FastAPI()
    app.include_router(agent_router)
    app.dependency_overrides[get_current_user] = lambda: user

    def _fresh_session():
        session = store.Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[_get_db] = _fresh_session
    return TestClient(app, raise_server_exceptions=False)


def _run_racing_calls(calls, *, monkeypatch, svc, gate="role_denial"):
    """Start both callers, hold them after the authority READ, release together.

    The barrier is placed on a read (role check or reviewer resolution) so
    neither caller has taken a SQLite write lock yet; both then attempt the
    atomic claim. Without the fix both would commit.
    """
    barrier = threading.Barrier(len(calls))
    if gate == "role_denial":
        original = svc._required_role_denial

        def gated(db, action, actor):
            result = original(db, action, actor)
            barrier.wait(timeout=30)
            return result

        monkeypatch.setattr(svc, "_required_role_denial", gated)
    else:
        import core.intervention_service as intervention_module

        original_resolve = intervention_module.resolve_decision_reviewer

        def gated(*args, **kwargs):
            result = original_resolve(*args, **kwargs)
            barrier.wait(timeout=30)
            return result

        monkeypatch.setattr(
            intervention_module, "resolve_decision_reviewer", gated)

    results = {}

    def run(name, call):
        try:
            results[name] = call()
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertions
            results[name] = {"exception": repr(exc)}

    threads = [
        threading.Thread(target=run, args=(name, call))
        for name, call in calls
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "race deadlocked"
    return results


def _only_success(results):
    winners = {name: value for name, value in results.items()
               if value.get("success")}
    losers = {name: value for name, value in results.items()
              if not value.get("success")}
    assert len(winners) == 1, results
    assert len(losers) == 1, results
    return next(iter(winners)), next(iter(losers.values()))


# ============================================================================
# Service decision path
# ============================================================================


def test_modified_approval_records_reviewed_and_effective(scratch, svc):
    original = {
        "to": "original@example.com",
        "subject": "Original subject",
        "nested": {"items": [{"id": 1}]},
    }
    modified = {
        "to": "corrected@example.com",
        "subject": "Corrected subject",
        "nested": {"items": [{"id": 2}]},
    }
    action_id = _new_action(
        scratch.db,
        params=original,
        required_role="admin",
        context_snapshot={"required_role": "admin", "business": "kept"},
    )

    result = asyncio.run(svc.approve_intervention(
        action_id, "admin-1", modified_params=modified,
        reason="recipient corrected"))

    assert result["success"] is True, result
    action = _action(scratch.db, action_id)
    assert action.params == modified, "execution must consume the effective payload"
    assert action.status == HITLActionStatus.APPROVED.value
    assert action.reviewed_by == "admin-1"

    snapshot = action.context_snapshot
    assert snapshot["required_role"] == "admin", "authority policy was clobbered"
    assert snapshot["business"] == "kept", "unrelated snapshot data was clobbered"
    entries = snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["revision"] == 1
    assert entry["reviewed_params"] == original
    assert entry["approved_params"] == modified
    assert entry["modified"] is True
    assert entry["modified_by"] == "admin-1"
    assert entry["reason"] == "recipient corrected"
    assert datetime.fromisoformat(entry["modified_at"])

    view = describe_parameter_history(action)
    assert view["original_known"] is True
    assert view["original_params"] == original
    assert view["effective_params"] == modified
    assert view["modified"] is True
    assert view["history_entries"] == 1
    assert view["legacy_unrecorded"] is False
    assert view["redacted"] is True


def test_unchanged_approval_records_the_same_review_and_effective(scratch, svc):
    original = {"to": "same@example.com", "subject": "Same"}
    action_id = _new_action(scratch.db, params=original)

    result = asyncio.run(svc.approve_intervention(action_id, "lead-1"))

    assert result["success"] is True, result
    action = _action(scratch.db, action_id)
    assert action.params == original
    entry = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY][0]
    assert entry["reviewed_params"] == original
    assert entry["approved_params"] == original
    assert entry["modified"] is False
    assert entry["modified_by"] == "lead-1"
    assert entry["reason"] is None, "an absent reason must stay unknown"
    view = describe_parameter_history(action)
    assert view["original_params"] == original
    assert view["effective_params"] == original
    assert view["modified"] is False


def test_rejection_does_not_rewrite_params_or_claim_approval(scratch, svc):
    original = {"to": "reject@example.com", "subject": "Keep me"}
    action_id = _new_action(
        scratch.db, params=original,
        context_snapshot={"required_role": "admin"})

    result = asyncio.run(svc.reject_intervention(
        action_id, "admin-1", "not approved"))

    assert result["success"] is True, result
    action = _action(scratch.db, action_id)
    assert action.status == HITLActionStatus.REJECTED.value
    assert action.params == original
    assert action.context_snapshot == {"required_role": "admin"}
    assert HITL_PARAMETER_HISTORY_KEY not in action.context_snapshot
    view = describe_parameter_history(action)
    assert view["status"] == HITLActionStatus.REJECTED.value
    assert view["original_params"] == original
    assert view["effective_params"] is None
    assert view["legacy_unrecorded"] is False


def test_denied_actor_leaves_no_history_and_no_params_mutation(scratch, svc):
    original = {"to": "guarded@example.com"}
    protected = _new_action(
        scratch.db, params=original,
        required_role="admin",
        context_snapshot={"required_role": "admin"})

    denied = asyncio.run(svc.approve_intervention(
        protected, "lead-1", modified_params={"to": "sneaky@example.com"}))

    assert denied["success"] is False
    assert denied["error_code"] == "AUTHORITY_REQUIRED"
    assert denied["http_status"] == 403
    guarded = _action(scratch.db, protected)
    assert guarded.status == HITLActionStatus.PENDING.value
    assert guarded.params == original
    assert guarded.context_snapshot == {"required_role": "admin"}

    inactive = _new_action(
        scratch.db, params={"to": "inactive@example.com"})
    denied = asyncio.run(svc.approve_intervention(
        inactive, "inactive-admin", modified_params={"to": "x@example.com"}))
    assert denied["success"] is False
    row = _action(scratch.db, inactive)
    assert row.status == HITLActionStatus.PENDING.value
    assert row.params == {"to": "inactive@example.com"}
    assert row.context_snapshot is None


# ============================================================================
# Mounted approval surfaces
# ============================================================================


def test_alias_route_records_history_and_does_not_export_secrets(scratch):
    original = {
        "to": "original@example.com",
        "api_key": "sk-live-should-not-leak",
        "nested": {"items": [{"id": 1}]},
    }
    modified = {
        "to": "corrected@example.com",
        "api_key": "sk-live-should-not-leak",
        "nested": {"items": [{"id": 2}]},
    }
    action_id = _new_action(scratch.db, params=original)
    client = _alias_client(scratch.db, "lead-1")
    secret_in_reason = "sk-" + ("a" * 48)
    reason = f"route correction; avoid pasting {secret_in_reason}"

    response = client.post(
        f"/api/agents/approvals/{action_id}",
        json={
            "decision": "approved",
            "modified_params": modified,
            "reason": reason,
        },
    )

    assert response.status_code == 200, response.text
    assert "api_key" not in response.text
    assert "sk-live-should-not-leak" not in response.text
    assert secret_in_reason not in response.text
    assert "context_snapshot" not in response.text

    action = _action(scratch.db, action_id)
    assert action.params == modified
    entry = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY][0]
    assert entry["reviewed_params"] == original
    assert entry["approved_params"] == modified
    assert entry["modified_by"] == "lead-1"
    assert entry["reason"] == reason, "raw authority row keeps the real note"

    safe_view = describe_parameter_history(action)
    assert "api_key" not in safe_view["original_params"]
    assert "api_key" not in safe_view["effective_params"]
    assert secret_in_reason not in safe_view["reason"]
    assert "[REDACTED_OPENAI_KEY]" in safe_view["reason"]
    raw_view = describe_parameter_history(action, redact=False)
    assert raw_view["effective_params"]["api_key"] == "sk-live-should-not-leak"
    assert raw_view["reason"] == reason


def test_legacy_agent_route_records_the_same_history(scratch):
    original = {"to": "original@example.com", "subject": "Original"}
    modified = {"to": "legacy@example.com", "subject": "Legacy corrected"}
    action_id = _new_action(scratch.db, params=original)
    client = _agent_client(scratch.db, "admin-1")

    response = client.post(
        f"/api/agents/approvals/{action_id}",
        json={
            "decision": "approved",
            "modified_params": modified,
            "feedback": "legacy route correction",
        },
    )

    assert response.status_code == 200, response.text
    action = _action(scratch.db, action_id)
    assert action.params == modified
    entry = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY][0]
    assert entry["reviewed_params"] == original
    assert entry["approved_params"] == modified
    assert entry["modified"] is True
    assert entry["modified_by"] == "admin-1"
    assert entry["reason"] == "legacy route correction"


def test_foreign_actor_and_duplicate_decision_do_not_rewrite_history(scratch):
    original = {"to": "owner@example.com"}
    modified = {"to": "approved@example.com"}
    action_id = _new_action(scratch.db, params=original)

    foreign = _alias_client(scratch.db, "foreign-admin").post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved",
              "modified_params": {"to": "foreign@example.com"}})
    assert foreign.status_code == 404, foreign.text
    row = _action(scratch.db, action_id)
    assert row.status == HITLActionStatus.PENDING.value
    assert row.params == original
    assert row.context_snapshot is None

    client = _alias_client(scratch.db, "lead-1")
    first = client.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved", "modified_params": modified})
    assert first.status_code == 200, first.text
    # Duplicate decision is refused without touching params/history.
    duplicate = client.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved",
              "modified_params": {"to": "duplicate@example.com"}})
    assert duplicate.status_code in (400, 409), duplicate.text

    row = _action(scratch.db, action_id)
    assert row.params == modified
    entries = row.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert len(entries) == 1
    assert entries[0]["approved_params"] == modified
    assert row.status == HITLActionStatus.APPROVED.value


def test_legacy_duplicate_decision_is_idempotent(scratch):
    original = {"to": "original@example.com"}
    modified = {"to": "first@example.com"}
    action_id = _new_action(scratch.db, params=original)
    client = _agent_client(scratch.db, "admin-1")

    first = client.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved", "modified_params": modified,
              "feedback": "first"})
    assert first.status_code == 200, first.text
    duplicate = client.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved",
              "modified_params": {"to": "second@example.com"},
              "feedback": "second"})
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json().get("data", {}).get("already_resolved") is True

    row = _action(scratch.db, action_id)
    assert row.params == modified
    entries = row.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert len(entries) == 1
    assert entries[0]["approved_params"] == modified
    assert entries[0]["reason"] == "first"


# ============================================================================
# Durability / restart / aliasing
# ============================================================================


def test_cold_session_readback_retains_original_and_effective(scratch, svc):
    original = {"to": "before-restart@example.com", "nested": {"id": 1}}
    modified = {"to": "after-restart@example.com", "nested": {"id": 2}}
    action_id = _new_action(
        scratch.db, params=original,
        context_snapshot={"required_role": "admin"})

    result = asyncio.run(svc.approve_intervention(
        action_id, "admin-1", modified_params=modified, reason="survives"))
    assert result["success"] is True, result

    scratch.reopen()  # dispose the engine, open a new one on the same file
    action = _action(scratch.db, action_id)
    assert action.params == modified
    assert action.context_snapshot["required_role"] == "admin"
    entries = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert entries[0]["reviewed_params"] == original
    assert entries[0]["approved_params"] == modified
    assert entries[0]["modified_by"] == "admin-1"
    assert entries[0]["reason"] == "survives"

    view = describe_parameter_history(action)
    assert view["original_known"] is True
    assert view["original_params"] == original
    assert view["effective_params"] == modified
    assert view["reviewed_by"] == "admin-1"


def test_nested_original_and_effective_are_not_aliased(scratch, svc):
    original = {"to": "alias@example.com", "nested": {"items": [{"id": 1}]}}
    modified = {"to": "effective@example.com", "nested": {"items": [{"id": 2}]}}
    action_id = _new_action(scratch.db, params=original)

    result = asyncio.run(svc.approve_intervention(
        action_id, "lead-1", modified_params=modified))
    assert result["success"] is True, result

    action = _action(scratch.db, action_id)
    entry = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY][0]
    assert entry["reviewed_params"] is not original
    assert entry["approved_params"] is not modified

    # Mutating either live/caller object after approval must not mutate the
    # stored receipt (deep-copied before the params column was rewritten).
    modified["nested"]["items"][0]["id"] = 999
    modified["to"] = "caller-mutated"
    original["nested"]["items"][0]["id"] = 888
    assert entry["reviewed_params"]["nested"]["items"][0]["id"] == 1
    assert entry["approved_params"]["nested"]["items"][0]["id"] == 2
    assert entry["approved_params"]["to"] == "effective@example.com"

    action = _action(scratch.db, action_id)
    assert action.params == {"to": "effective@example.com",
                             "nested": {"items": [{"id": 2}]}}


def test_history_is_append_only_when_a_row_is_decided_again(scratch):
    action = HITLAction(
        id=f"hitl-{uuid.uuid4()}",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        action_type="send_email",
        platform="governance_policy",
        params={"to": "v1@example.com"},
        reason="append-only",
        context_snapshot={"keep": True},
        status=HITLActionStatus.PENDING.value,
    )
    record_approved_parameters(
        action,
        reviewed_params={"to": "v1@example.com"},
        approved_params={"to": "v2@example.com"},
        actor_id="lead-1",
        reason="first",
    )
    record_approved_parameters(
        action,
        reviewed_params={"to": "v2@example.com"},
        approved_params={"to": "v3@example.com"},
        actor_id="admin-1",
        reason="second",
    )

    entries = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert [entry["revision"] for entry in entries] == [1, 2]
    assert entries[0]["reviewed_params"] == {"to": "v1@example.com"}
    assert entries[0]["approved_params"] == {"to": "v2@example.com"}
    assert entries[1]["reviewed_params"] == {"to": "v2@example.com"}
    assert entries[1]["approved_params"] == {"to": "v3@example.com"}
    assert action.context_snapshot["keep"] is True


# ============================================================================
# Historical rows / unknown originals
# ============================================================================


def test_legacy_approved_row_without_receipt_reports_unknown(scratch):
    legacy = HITLAction(
        id=f"hitl-{uuid.uuid4()}",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        action_type="send_email",
        platform="governance_policy",
        params={"to": "rewritten-before-receipt@example.com"},
        reason="legacy",
        context_snapshot=None,
        status=HITLActionStatus.APPROVED.value,
        reviewed_by="admin-1",
    )
    scratch.db.add(legacy)
    scratch.db.commit()

    view = describe_parameter_history(legacy)
    assert view["original_known"] is False
    assert view["original_params"] is None, "must not invent a reviewed original"
    assert view["effective_params"] == {
        "to": "rewritten-before-receipt@example.com"}
    assert view["modified"] is None
    assert view["legacy_unrecorded"] is True
    assert view["history_entries"] == 0
    assert view["reviewed_by"] == "admin-1"


# ============================================================================
# Real execution consumer
# ============================================================================


def test_execution_consumer_reads_effective_params_once(scratch, svc):
    original = {
        "execution_id": "exec-param-1",
        "step_id": "step-param-1",
        "parameters": {"to": "reviewed@example.com"},
    }
    modified = {
        "execution_id": "exec-param-1",
        "step_id": "step-param-1",
        "parameters": {"to": "effective@example.com"},
    }
    action_id = _new_action(scratch.db, params=original)

    result = asyncio.run(svc.approve_intervention(
        action_id, "lead-1", modified_params=modified,
        reason="effect corrected"))
    assert result["success"] is True, result

    from core.workflow_engine import WorkflowEngine

    engine = WorkflowEngine.__new__(WorkflowEngine)  # method is DB-only
    base_input = {"approved": True, "hitl_action_id": action_id}
    approval = asyncio.run(engine._durable_step_approval(
        "exec-param-1", "step-param-1", "send_email", base_input,
        payload={"to": "effective@example.com"},
        workspace_id=WORKSPACE))
    assert approval is not None
    assert approval["hitl_action_id"] == action_id
    assert approval["approved_by"] == "lead-1"

    # The reviewed-original payload is NOT what execution is authorized for.
    stale = asyncio.run(engine._durable_step_approval(
        "exec-param-1", "step-param-1", "send_email", base_input,
        payload={"to": "reviewed@example.com"},
        workspace_id=WORKSPACE))
    assert stale is None

    # Once the execution has recorded this approval as consumed, it is not
    # authorized a second time.
    consumed = dict(base_input, consumed_hitl_action_ids=[action_id])
    replay = asyncio.run(engine._durable_step_approval(
        "exec-param-1", "step-param-1", "send_email", consumed,
        payload={"to": "effective@example.com"},
        workspace_id=WORKSPACE))
    assert replay is None


# ============================================================================
# Atomic two-session decision controls (real file SQLite)
# ============================================================================


def _race_payload(target):
    return {
        "execution_id": "exec-race",
        "step_id": "step-race",
        "parameters": {"to": target},
    }


def test_two_sessions_approve_approve_commit_exactly_one(concurrent_scratch,
                                                         monkeypatch):
    aid = _new_action(concurrent_scratch.db, params=_race_payload(
        "original@example.com"))
    svc = InterventionService()

    def approve(actor, target):
        return lambda: asyncio.run(svc.approve_intervention(
            aid, actor,
            modified_params=_race_payload(target),
            reason=f"{actor} edited the recipient",
        ))

    results = _run_racing_calls(
        [("lead-1", approve("lead-1", "first@example.com")),
         ("admin-1", approve("admin-1", "second@example.com"))],
        monkeypatch=monkeypatch, svc=svc,
    )
    winner, loser = _only_success(results)
    assert loser.get("http_status") == 409, results
    assert loser.get("error_code") == "DECISION_CONFLICT", results

    expected = {
        "lead-1": "first@example.com",
        "admin-1": "second@example.com",
    }[winner]
    final = _action(concurrent_scratch.db, aid)
    assert final.status == HITLActionStatus.APPROVED.value
    assert final.reviewed_by == winner
    assert final.params["parameters"] == {"to": expected}
    view = describe_parameter_history(final)
    assert view["history_entries"] == 1, "the loser must not append history"
    assert view["reviewed_by"] == winner
    assert view["modified_by"] == winner
    assert view["original_params"]["parameters"] == {
        "to": "original@example.com"}
    assert view["effective_params"]["parameters"] == {"to": expected}
    assert view["reason"] == f"{winner} edited the recipient"

    # Cold readback sees the same winner and payload.
    concurrent_scratch.reopen()
    cold = _action(concurrent_scratch.db, aid)
    cold_view = describe_parameter_history(cold)
    assert cold_view["effective_params"]["parameters"] == {"to": expected}
    assert cold_view["modified_by"] == winner
    assert cold_view["history_entries"] == 1

    # Exactly one downstream consumption of the effective payload.
    from core.workflow_engine import WorkflowEngine

    engine = WorkflowEngine.__new__(WorkflowEngine)
    base_input = {"approved": True, "hitl_action_id": aid}
    binding = asyncio.run(engine._durable_step_approval(
        "exec-race", "step-race", "send_email", base_input,
        payload={"to": expected}, workspace_id=WORKSPACE))
    assert binding is not None
    assert binding["approved_by"] == winner
    assert asyncio.run(engine._durable_step_approval(
        "exec-race", "step-race", "send_email", base_input,
        payload={"to": "original@example.com"},
        workspace_id=WORKSPACE)) is None
    consumed = dict(base_input, consumed_hitl_action_ids=[aid])
    assert asyncio.run(engine._durable_step_approval(
        "exec-race", "step-race", "send_email", consumed,
        payload={"to": expected}, workspace_id=WORKSPACE)) is None


def test_two_sessions_approve_versus_reject_commit_exactly_one(
        concurrent_scratch, monkeypatch):
    aid = _new_action(concurrent_scratch.db, params=_race_payload(
        "original@example.com"))
    svc = InterventionService()

    results = _run_racing_calls(
        [
            ("lead-1", lambda: asyncio.run(svc.approve_intervention(
                aid, "lead-1",
                modified_params=_race_payload("approved@example.com")))),
            ("admin-1", lambda: asyncio.run(svc.reject_intervention(
                aid, "admin-1", "not this effect"))),
        ],
        monkeypatch=monkeypatch, svc=svc,
    )
    winner, loser = _only_success(results)
    assert loser.get("http_status") == 409, results
    assert loser.get("error_code") == "DECISION_CONFLICT", results

    final = _action(concurrent_scratch.db, aid)
    view = describe_parameter_history(final)
    if winner == "lead-1":
        assert final.status == HITLActionStatus.APPROVED.value
        assert final.reviewed_by == "lead-1"
        assert final.params["parameters"] == {"to": "approved@example.com"}
        assert view["history_entries"] == 1
        assert view["effective_params"]["parameters"] == {
            "to": "approved@example.com"}
    else:
        assert final.status == HITLActionStatus.REJECTED.value
        assert final.reviewed_by == "admin-1"
        assert final.params["parameters"] == {"to": "original@example.com"}
        assert final.user_feedback == "not this effect"
        assert final.context_snapshot is None
        assert view["history_entries"] == 0


def test_reviewer_role_scope_and_activity_drift_are_refused_at_the_claim(
        scratch, monkeypatch):
    """The CURRENT reviewer, not the token/object that loaded the row, wins."""
    svc = InterventionService()

    def _mutate(store, actor, **fields):
        session = store.Session()
        try:
            user = session.query(User).filter(User.id == actor).one()
            for key, value in fields.items():
                setattr(user, key, value)
            session.commit()
        finally:
            session.close()

    def _drift(actor, **fields):
        original = svc._required_role_denial

        def mutated(db, action, checked_actor):
            result = original(db, action, checked_actor)
            _mutate(scratch, checked_actor, **fields)
            return result

        return mutated

    cases = [
        ({"role": "member"}, 403, "AUTHORITY_REQUIRED"),
        ({"is_active": False, "status": "inactive"}, 403,
         "ACCOUNT_INACTIVE"),
        ({"workspace_id": "ws-other"}, 404, "DECISION_SCOPE_DENIED"),
        ({"tenant_id": "tenant-other"}, 404, "DECISION_SCOPE_DENIED"),
    ]
    for fields, status, code in cases:
        aid = _new_action(
            scratch.db,
            params={"to": "drift@example.com"},
            required_role="admin" if "role" in fields else None,
        )
        actor = "admin-1" if "role" in fields else "lead-1"
        monkeypatch.setattr(
            svc, "_required_role_denial", _drift(actor, **fields))
        result = asyncio.run(svc.approve_intervention(
            aid, actor, modified_params={"to": "sneaky@example.com"}))
        assert result["success"] is False, (fields, result)
        assert result["http_status"] == status, (fields, result)
        assert result["error_code"] == code, (fields, result)
        row = _action(scratch.db, aid)
        assert row.status == HITLActionStatus.PENDING.value, fields
        assert row.params == {"to": "drift@example.com"}, fields
        assert row.context_snapshot is None, fields

        # Restore the actor for the next case.
        session = scratch.Session()
        try:
            user = session.query(User).filter(User.id == actor).one()
            user.role = "admin" if actor == "admin-1" else "team_lead"
            user.is_active = True
            user.status = "active"
            user.workspace_id = WORKSPACE
            user.tenant_id = TENANT
            session.commit()
        finally:
            session.close()
        monkeypatch.setattr(svc, "_required_role_denial",
                            InterventionService._required_role_denial)


def test_duplicate_service_decision_is_a_conflict_without_rewrite(scratch, svc):
    aid = _new_action(scratch.db, params={"to": "original@example.com"})
    first = asyncio.run(svc.approve_intervention(
        aid, "lead-1", modified_params={"to": "first@example.com"}))
    assert first["success"] is True, first

    duplicate = asyncio.run(svc.approve_intervention(
        aid, "lead-1", modified_params={"to": "duplicate@example.com"}))
    assert duplicate["success"] is False
    assert duplicate["http_status"] == 409
    assert duplicate["error_code"] == "DECISION_CONFLICT"

    final = _action(scratch.db, aid)
    assert final.params == {"to": "first@example.com"}
    entries = final.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert len(entries) == 1
    assert entries[0]["approved_params"] == {"to": "first@example.com"}


def test_legacy_mounted_route_two_sessions_commit_exactly_one(
        concurrent_scratch, monkeypatch):
    aid = _new_action(concurrent_scratch.db, params={
        "to": "original@example.com", "subject": "Legacy race"})
    clients = {
        "admin-1": _concurrent_agent_client(concurrent_scratch, "admin-1"),
        "super-1": _concurrent_agent_client(concurrent_scratch, "super-1"),
    }

    def post(actor, target):
        response = clients[actor].post(
            f"/api/agents/approvals/{aid}",
            json={
                "decision": "approved",
                "modified_params": {"to": target},
                "feedback": f"{actor} routed the merge",
            },
        )
        return response.status_code, response.json()

    results = _run_racing_calls(
        [
            ("admin-1", lambda: post("admin-1", "first@example.com")),
            ("super-1", lambda: post("super-1", "second@example.com")),
        ],
        monkeypatch=monkeypatch, svc=InterventionService(), gate="resolve",
    )
    assert not {
        name: value for name, value in results.items()
        if "exception" in value
    }, results
    statuses = {name: value[0] for name, value in results.items()}
    assert sorted(statuses.values()) == [200, 409], results
    winner = next(name for name, code in statuses.items() if code == 200)
    expected = {
        "admin-1": "first@example.com",
        "super-1": "second@example.com",
    }[winner]

    final = _action(concurrent_scratch.db, aid)
    assert final.status == HITLActionStatus.APPROVED.value
    assert final.reviewed_by == winner
    # Legacy surface keeps its MERGE (replace one key, preserve the rest).
    assert final.params == {"to": expected, "subject": "Legacy race"}
    entries = final.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert len(entries) == 1
    assert entries[0]["reviewed_params"] == {
        "to": "original@example.com", "subject": "Legacy race"}
    assert entries[0]["approved_params"] == {
        "to": expected, "subject": "Legacy race"}
    loser_actor = "super-1" if winner == "admin-1" else "admin-1"
    loser_body = results[loser_actor][1]
    assert loser_body["detail"]["error"]["code"] == "DECISION_CONFLICT"


# ============================================================================
# Bounded, permission-scoped decision history readback
# ============================================================================


def test_malformed_history_elements_survive_append_and_are_reported(scratch):
    action = HITLAction(
        id=f"hitl-{uuid.uuid4()}",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        user_id="member-1",
        action_type="send_email",
        platform="governance_policy",
        params={"to": "v3@example.com"},
        reason="malformed",
        context_snapshot={
            "keep": True,
            HITL_PARAMETER_HISTORY_KEY: [
                {
                    "revision": 1,
                    "reviewed_params": {"to": "v1@example.com"},
                    "approved_params": {"to": "v2@example.com"},
                    "modified": True,
                    "modified_by": "lead-1",
                    "modified_at": "2026-01-01T00:00:00",
                    "reason": "first",
                },
                "corrupt-entry",
                7,
            ],
        },
        status=HITLActionStatus.APPROVED.value,
        reviewed_by="lead-1",
    )
    scratch.db.add(action)
    scratch.db.commit()

    record_approved_parameters(
        action,
        reviewed_params={"to": "v2@example.com"},
        approved_params={"to": "v3@example.com"},
        actor_id="admin-1",
        reason="second",
    )
    raw = action.context_snapshot[HITL_PARAMETER_HISTORY_KEY]
    assert action.context_snapshot["keep"] is True
    assert raw[1] == "corrupt-entry", "invalid list element was dropped"
    assert raw[2] == 7, "invalid list element was dropped"
    assert raw[3]["revision"] == 2

    view = describe_parameter_history(action)
    assert view["history_entries"] == 2
    assert view["malformed_history_entries"] == 2
    assert view["history_complete"] is False
    assert view["effective_params"] == {"to": "v3@example.com"}
    assert [entry["revision"] for entry in view["revisions"]] == [1, 2]


def test_unreadable_history_container_is_never_overwritten(scratch):
    action = HITLAction(
        id=f"hitl-{uuid.uuid4()}",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        user_id="member-1",
        action_type="send_email",
        platform="governance_policy",
        params={"to": "rewritten@example.com"},
        reason="unreadable",
        context_snapshot={
            "keep": True, HITL_PARAMETER_HISTORY_KEY: "not-a-list"},
        status=HITLActionStatus.APPROVED.value,
        reviewed_by="admin-1",
    )
    scratch.db.add(action)
    scratch.db.commit()

    assert record_approved_parameters(
        action,
        reviewed_params={"to": "a@example.com"},
        approved_params={"to": "b@example.com"},
        actor_id="lead-1",
    ) is None
    assert action.context_snapshot == {
        "keep": True, HITL_PARAMETER_HISTORY_KEY: "not-a-list"}

    view = describe_parameter_history(action)
    assert view["history_unreadable"] is True
    assert view["history_complete"] is False
    assert view["original_known"] is False
    assert view["original_params"] is None
    assert view["effective_params"] == {"to": "rewritten@example.com"}
    assert view["legacy_unrecorded"] is True


def test_decision_history_read_route_is_scoped_redacted_and_bounded(scratch, svc):
    original = {
        "to": "original@example.com",
        "api_key": "sk-live-should-not-leak",
        "nested": {"items": [{"id": 1}]},
    }
    modified = {
        "to": "corrected@example.com",
        "api_key": "sk-live-should-not-leak",
        "nested": {"items": [{"id": 2}]},
    }
    aid = _new_action(scratch.db, params=original)
    row = _action(scratch.db, aid)
    record_approved_parameters(
        row,
        reviewed_params=original,
        approved_params={"to": "mid@example.com", "api_key": "sk-live-should-not-leak"},
        actor_id="lead-1",
        reason="intermediate",
    )
    # A real earlier approval leaves the effective payload in the live column.
    row.params = {"to": "mid@example.com", "api_key": "sk-live-should-not-leak"}
    scratch.db.commit()

    secret_reason = "sk-" + ("b" * 48)
    result = asyncio.run(svc.approve_intervention(
        aid, "lead-1", modified_params=modified,
        reason=f"final correction; token {secret_reason}"))
    assert result["success"] is True, result

    reviewer_client = _alias_client(scratch.db, "lead-1")
    response = reviewer_client.get(
        f"/api/agents/approvals/{aid}/history?revision_limit=1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approval_id"] == aid
    assert body["status"] == HITLActionStatus.APPROVED.value
    assert body["original_known"] is True
    assert body["original_params"]["to"] == "mid@example.com"
    assert body["effective_params"]["to"] == "corrected@example.com"
    assert body["reviewed_by"] == "lead-1"
    assert body["history_entries"] == 2
    assert body["history_complete"] is True
    assert body["malformed_history_entries"] == 0
    assert body["revisions_truncated"] is True
    assert len(body["revisions"]) == 1
    assert body["revisions"][0]["revision"] == 2
    assert "context_snapshot" not in body
    assert "api_key" not in response.text
    assert "sk-live-should-not-leak" not in response.text
    assert secret_reason not in response.text

    # Ordinary member: own subject is readable; an unrelated member is 403.
    assert _alias_client(scratch.db, "member-1").get(
        f"/api/agents/approvals/{aid}/history").status_code == 200
    denied = _alias_client(scratch.db, "member-2").get(
        f"/api/agents/approvals/{aid}/history")
    assert denied.status_code == 403, denied.text

    # Cross-scope and guessed ids are 404 (never confirmed).
    assert _alias_client(scratch.db, "foreign-admin").get(
        f"/api/agents/approvals/{aid}/history").status_code == 404
    assert reviewer_client.get(
        "/api/agents/approvals/does-not-exist/history").status_code == 404

    # Recent decisions are bounded and never carry params/snapshots.
    recent = reviewer_client.get("/api/agents/approvals/recent?limit=5")
    assert recent.status_code == 200, recent.text
    recent_ids = [item["id"] for item in recent.json()]
    assert aid in recent_ids
    assert "api_key" not in recent.text
    assert "original@example.com" not in recent.text
    assert "member-1" not in recent.text
    assert all("params" not in item for item in recent.json())

    # A member sees only their own subject/reviewed decisions.
    member_recent = _alias_client(scratch.db, "member-1").get(
        "/api/agents/approvals/recent")
    assert [item["id"] for item in member_recent.json()] == [aid]
    unrelated_recent = _alias_client(scratch.db, "member-2").get(
        "/api/agents/approvals/recent")
    assert unrelated_recent.status_code == 200
    assert unrelated_recent.json() == []
    foreign_recent = _alias_client(scratch.db, "foreign-admin").get(
        "/api/agents/approvals/recent")
    assert foreign_recent.status_code == 200
    assert foreign_recent.json() == []


def _scoped_user(uid, role, *, workspace, tenant, active=True):
    """A real User row with independently chosen workspace AND tenant."""
    user = _user(uid, role, workspace=workspace, active=active)
    user.tenant_id = tenant
    return user


def _scoped_action(
    db,
    *,
    workspace,
    tenant,
    user_id="member-1",
    reviewed_by=None,
    status=HITLActionStatus.APPROVED.value,
    params=None,
):
    """A decided HITLAction in an explicitly chosen canonical scope."""
    action = HITLAction(
        id=f"hitl-{uuid.uuid4()}",
        workspace_id=workspace,
        tenant_id=tenant,
        user_id=user_id,
        reviewed_by=reviewed_by,
        action_type="send_email",
        platform="governance_policy",
        params=params if params is not None else {
            "to": "synthetic@example.com"},
        reason="Needs review",
        status=status,
    )
    db.add(action)
    db.commit()
    return action.id


def test_default_supervisor_and_admin_cannot_read_foreign_named_decision(scratch):
    """The counter shape: Personal/default TEAM_LEAD and ADMIN, named row.

    Personal/default authority is NOT a wildcard for another named
    tenant/workspace on the new history/recent reads — and it does not become
    one for ADMIN either (no invented global-admin privilege).
    """
    scratch.db.add_all([
        _scoped_user(
            "personal-lead", UserRole.TEAM_LEAD, workspace=None, tenant=None),
        _scoped_user(
            "personal-admin", UserRole.ADMIN, workspace=None, tenant=None),
    ])
    scratch.db.commit()
    aid = _scoped_action(
        scratch.db,
        workspace="ws-named",
        tenant="tenant-named",
        reviewed_by="lead-1",
    )

    for uid in ("personal-lead", "personal-admin"):
        client = _alias_client(scratch.db, uid)
        history = client.get(f"/api/agents/approvals/{aid}/history")
        assert history.status_code == 404, (uid, history.text)
        assert history.json()["detail"]["error"]["code"] == (
            "APPROVAL_NOT_FOUND")
        recent = client.get("/api/agents/approvals/recent")
        assert recent.status_code == 200, (uid, recent.text)
        assert aid not in [item["id"] for item in recent.json()]


@pytest.mark.parametrize(
    "actor_ws,actor_tenant,action_ws,action_tenant,allowed",
    [
        # Same canonical default scope (None / "" / "default" one scope).
        (None, None, None, None, True),
        ("default", "default", "", "", True),
        ("", "", None, None, True),
        # Same named scope.
        ("ws-a", "tenant-a", "ws-a", "tenant-a", True),
        # Same mixed scope (named tenant, default workspace) is the SAME scope.
        (None, "tenant-a", "", "tenant-a", True),
        # Default actor vs named action, both dimensions and each one alone.
        (None, None, "ws-a", "tenant-a", False),
        (None, None, "ws-a", None, False),
        (None, None, None, "tenant-a", False),
        # Reverse direction: named-on-one-axis actor vs default action.
        ("ws-a", None, None, None, False),
        (None, "tenant-a", None, None, False),
        # Named mismatches.
        ("ws-a", "tenant-a", "ws-b", "tenant-a", False),
        ("ws-a", "tenant-a", "ws-a", "tenant-b", False),
        # Mixed named/default in BOTH directions on one axis.
        ("ws-a", None, "ws-a", "tenant-a", False),
        ("ws-a", "tenant-a", "ws-a", None, False),
    ],
)
def test_read_scope_is_exact_not_a_default_wildcard(
    scratch, actor_ws, actor_tenant, action_ws, action_tenant, allowed,
):
    """Scope is exact canonical equality — default never wildcards a named peer.

    Both the per-decision history and the discoverability list must apply the
    SAME rule in both directions, for workspace and tenant independently.
    """
    uid = "lead-" + uuid.uuid4().hex[:10]
    scratch.db.add(_scoped_user(
        uid, UserRole.TEAM_LEAD, workspace=actor_ws, tenant=actor_tenant))
    scratch.db.commit()
    aid = _scoped_action(
        scratch.db, workspace=action_ws, tenant=action_tenant,
        reviewed_by="lead-1")

    client = _alias_client(scratch.db, uid)
    history = client.get(f"/api/agents/approvals/{aid}/history")
    recent = client.get("/api/agents/approvals/recent")
    assert recent.status_code == 200, recent.text
    listed = aid in [item["id"] for item in recent.json()]

    if allowed:
        assert history.status_code == 200, history.text
        assert listed, recent.text
    else:
        assert history.status_code == 404, history.text
        assert history.json()["detail"]["error"]["code"] == (
            "APPROVAL_NOT_FOUND")
        assert not listed, recent.text


def test_default_member_scope_beats_subject_and_reviewer_identity(scratch):
    """A historical reviewer/subject identity never overrides CURRENT scope.

    A Personal/default member who is the row's reviewer or its subject still
    cannot read across into a named tenant/workspace (404, never 403 —an id is
    not confirmed), and it never appears in their recent list. Same-scope
    default rows remain readable: the fence is exact scope, not "members can
    read nothing".
    """
    scratch.db.add_all([
        _scoped_user(
            "personal-member", UserRole.MEMBER, workspace=None, tenant=None),
        _scoped_user(
            "personal-lead", UserRole.TEAM_LEAD, workspace=None, tenant=None),
    ])
    scratch.db.commit()
    as_reviewer = _scoped_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        user_id="member-1", reviewed_by="personal-member")
    as_subject = _scoped_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        user_id="personal-member", reviewed_by="lead-1")
    lead_reviewed = _scoped_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        user_id="member-1", reviewed_by="personal-lead")
    own_default = _scoped_action(
        scratch.db, workspace=None, tenant=None,
        user_id="personal-member", reviewed_by="personal-lead")

    member = _alias_client(scratch.db, "personal-member")
    for aid in (as_reviewer, as_subject, lead_reviewed):
        denied = member.get(f"/api/agents/approvals/{aid}/history")
        assert denied.status_code == 404, denied.text
        assert denied.json()["detail"]["error"]["code"] == (
            "APPROVAL_NOT_FOUND")
    assert [item["id"] for item in member.get(
        "/api/agents/approvals/recent").json()] == [own_default]
    assert member.get(
        f"/api/agents/approvals/{own_default}/history").status_code == 200

    lead = _alias_client(scratch.db, "personal-lead")
    for aid in (as_reviewer, as_subject, lead_reviewed):
        assert lead.get(
            f"/api/agents/approvals/{aid}/history").status_code == 404
    assert [item["id"] for item in lead.get(
        "/api/agents/approvals/recent").json()] == [own_default]


def test_default_scope_reads_its_own_canonical_default_history(
        scratch, monkeypatch):
    """NULL / "" / "default" are ONE legitimate Personal/default scope.

    Legitimate own default-scope history must still read (list + detail), stay
    redacted and bounded, and a storage failure must stay a 503 — the exact
    scope fence must never turn into "default sees nothing" or a 404.
    """
    scratch.db.add(_scoped_user(
        "personal-lead", UserRole.TEAM_LEAD, workspace=None, tenant=None))
    scratch.db.commit()
    own = {}
    for label, ws, tid in (
            ("null", None, None),
            ("empty", "", ""),
            ("literal", "default", "default")):
        own[label] = _scoped_action(
            scratch.db, workspace=ws, tenant=tid,
            reviewed_by="personal-lead",
            params={"to": "own@example.com", "api_key": "sk-own-secret"})
    named = _scoped_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        reviewed_by="personal-lead")

    client = _alias_client(scratch.db, "personal-lead")
    for label, aid in own.items():
        history = client.get(f"/api/agents/approvals/{aid}/history")
        assert history.status_code == 200, (label, history.text)
        assert history.json()["approval_id"] == aid
        assert "sk-own-secret" not in history.text
        assert "api_key" not in history.text
    recent = client.get("/api/agents/approvals/recent?limit=10")
    assert recent.status_code == 200, recent.text
    assert {item["id"] for item in recent.json()} == set(own.values())
    assert named not in [item["id"] for item in recent.json()]
    bounded = client.get("/api/agents/approvals/recent?limit=2")
    assert len(bounded.json()) == 2
    assert "own@example.com" not in bounded.text

    def _boom(*args, **kwargs):
        raise SQLAlchemyError("history store unavailable")

    monkeypatch.setattr(
        "core.intervention_service.describe_parameter_history", _boom)
    unavailable = client.get(
        f"/api/agents/approvals/{own['literal']}/history")
    assert unavailable.status_code == 503, unavailable.text
    assert unavailable.json()["detail"]["error"]["code"] == (
        "HISTORY_UNAVAILABLE")


def test_production_mount_order_keeps_default_reads_exact(scratch):
    """Real production mount order: legacy agent router FIRST, then the alias.

    The default actor keeps its own canonical-default row on both read paths
    while the named row stays a 404 / is absent from the list.
    """
    from api.agent_routes import router as agent_router
    from api.approvals_routes import router as approvals_router

    scratch.db.add(_scoped_user(
        "personal-lead", UserRole.TEAM_LEAD, workspace=None, tenant=None))
    scratch.db.commit()
    own = _scoped_action(
        scratch.db, workspace=None, tenant=None, reviewed_by="personal-lead")
    named = _scoped_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        reviewed_by="personal-lead")

    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(approvals_router)
    user = scratch.db.query(User).filter(User.id == "personal-lead").one()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: scratch.db
    client = TestClient(app, raise_server_exceptions=False)

    recent = client.get("/api/agents/approvals/recent")
    assert recent.status_code == 200, recent.text
    assert [item["id"] for item in recent.json()] == [own]
    assert client.get(
        f"/api/agents/approvals/{own}/history").status_code == 200
    denied = client.get(f"/api/agents/approvals/{named}/history")
    assert denied.status_code == 404, denied.text
    assert denied.json()["detail"]["error"]["code"] == "APPROVAL_NOT_FOUND"


def test_decision_history_reports_unavailable_instead_of_empty(scratch, monkeypatch):
    aid = _new_action(scratch.db, params={"to": "pending@example.com"})

    def _boom(*args, **kwargs):
        raise SQLAlchemyError("history store unavailable")

    monkeypatch.setattr(
        "core.intervention_service.describe_parameter_history", _boom)
    response = _alias_client(scratch.db, "lead-1").get(
        f"/api/agents/approvals/{aid}/history")
    assert response.status_code == 503, response.text
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "HISTORY_UNAVAILABLE"


def test_claim_fence_traces_semantic_postgresql_jsonb_cas():
    """Compile-only trace: PostgreSQL compares JSONB semantically, SQLite text.

    No database is opened and no PostgreSQL run is claimed. The permanent
    race controls above run on a real file SQLite database; this pins the
    dialect-specific statement shape they rely on.
    """
    action = HITLAction(
        id="hitl-cas",
        action_type="send_email",
        required_role="admin",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        params={"to": "x@example.com"},
        context_snapshot={"required_role": "admin"},
    )
    stmt = update(HITLAction).where(
        *pending_decision_conditions(action)).values(status="approved")
    sql = str(stmt.compile(dialect=postgresql.dialect())).upper()

    assert "HITL_ACTIONS.STATUS = " in sql
    assert "HITL_ACTIONS.PARAMS = " in sql and "::JSONB" in sql
    assert "HITL_ACTIONS.CONTEXT_SNAPSHOT = " in sql and "::JSONB" in sql
    assert "CAST(HITL_ACTIONS.PARAMS AS VARCHAR)" not in sql

    action.context_snapshot = None
    null_sql = str(update(HITLAction).where(
        *pending_decision_conditions(action)).values(
            status="approved").compile(dialect=postgresql.dialect())).upper()
    assert "HITL_ACTIONS.CONTEXT_SNAPSHOT IS NULL" in null_sql
    assert "CAST(HITL_ACTIONS.CONTEXT_SNAPSHOT AS VARCHAR)" in null_sql


def test_mounted_route_order_exposes_reads_and_keeps_legacy_decision_surface(scratch):
    """Both mounted surfaces, in production order (legacy agent router first).

    The legacy one-segment GET catch-all must not swallow the new nested read
    paths; the alias history handler's refusal shape proves which surface
    answered. The decision POST intentionally stays on the legacy route,
    which now shares the atomic claim rather than owning a second writer.
    """
    from api.agent_routes import router as agent_router
    from api.approvals_routes import router as approvals_router

    app = FastAPI()
    app.include_router(agent_router)  # production mount order: legacy first
    app.include_router(approvals_router)
    user = scratch.db.query(User).filter(User.id == "admin-1").one()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: scratch.db
    client = TestClient(app, raise_server_exceptions=False)

    recent = client.get("/api/agents/approvals/recent")
    assert recent.status_code == 200, recent.text
    assert recent.json() == []

    history = client.get("/api/agents/approvals/missing/history")
    assert history.status_code == 404, history.text
    assert history.json()["detail"]["error"]["code"] == "APPROVAL_NOT_FOUND"

    # The legacy pending surface is still mounted and unchanged.
    pending = client.get("/api/agents/approvals/pending")
    assert pending.status_code == 200, pending.text
    assert isinstance(pending.json(), list)


# ============================================================================
# Pending queue read scope (legacy + alias + governance mounted surfaces)
# ============================================================================


def _pending_action(
    db,
    *,
    workspace,
    tenant,
    user_id="member-1",
    params=None,
):
    """A pending HITLAction in an explicitly chosen canonical scope."""
    return _scoped_action(
        db,
        workspace=workspace,
        tenant=tenant,
        user_id=user_id,
        status=HITLActionStatus.PENDING.value,
        params=params,
    )


def _governance_client(db, user_id):
    from api.agent_governance_routes import router as governance_router

    return _route_client(db, user_id, governance_router)


def _client_for_actor_object(db, actor, router):
    """Mount one router with a STALE request-token actor object.

    ``get_current_user`` is replaced deliberately: the pending read must
    re-resolve the durable row instead of trusting this object's raw scope.
    """
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[_get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_legacy_pending_queue_is_exact_scope_for_default_admin(scratch):
    """Actual production legacy route: default ADMIN + named pending row.

    This is the adjudicated counter shape for the queue: a real ADMIN with
    ``tenant_id=None``/``workspace_id=None`` passes the route's AGENT_MANAGE
    gate, so the scope fence must live in the read itself. The TEAM_LEAD arm
    stays the preserved negative control: it is refused by permission BEFORE
    any scope decision (403), not by the new scope predicate.
    """
    scratch.db.add_all([
        _scoped_user(
            "personal-admin", UserRole.ADMIN, workspace=None, tenant=None),
        _scoped_user(
            "personal-lead", UserRole.TEAM_LEAD, workspace=None, tenant=None),
    ])
    scratch.db.commit()
    named = _pending_action(
        scratch.db,
        workspace="ws-named",
        tenant="tenant-named",
        params={"to": "named-secret@example.com"},
    )
    own = _pending_action(
        scratch.db,
        workspace=None,
        tenant=None,
        params={"to": "own@example.com"},
    )

    response = _agent_client(scratch.db, "personal-admin").get(
        "/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [own]
    assert named not in [item["id"] for item in response.json()]
    assert "named-secret" not in response.text
    assert response.json()[0]["params"] == {"to": "own@example.com"}

    lead = _agent_client(scratch.db, "personal-lead").get(
        "/api/agents/approvals/pending")
    assert lead.status_code == 403, lead.text


def test_alias_pending_queue_is_exact_scope_for_default_actor(scratch):
    """Alias surface proven independently of the shadowing legacy route."""
    scratch.db.add(_scoped_user(
        "personal-member", UserRole.MEMBER, workspace=None, tenant=None))
    scratch.db.commit()
    named = _pending_action(
        scratch.db,
        workspace="ws-named",
        tenant="tenant-named",
        params={"to": "named-secret@example.com"},
    )
    own = _pending_action(
        scratch.db,
        workspace=None,
        tenant=None,
        params={"to": "own@example.com"},
    )

    response = _alias_client(scratch.db, "personal-member").get(
        "/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [own]
    assert named not in [item["id"] for item in response.json()]
    assert "named-secret" not in response.text


def test_governance_pending_queue_ignores_client_approver_as_scope(scratch):
    """The old positional call bound ``approver_id`` to ``workspace_id``.

    Actual mounted route evidence: a foreign-tenant pending row whose
    ``workspace_id`` equals the client-supplied ``approver_id`` must not be
    exported, and the actor's own default row must still be returned.
    """
    scratch.db.add(_scoped_user(
        "personal-admin", UserRole.ADMIN, workspace=None, tenant=None))
    scratch.db.commit()
    foreign = _pending_action(
        scratch.db,
        workspace="lead-1",
        tenant="tenant-foreign",
        params={"to": "foreign-secret@example.com"},
    )
    own = _pending_action(
        scratch.db,
        workspace=None,
        tenant=None,
        params={"to": "own@example.com"},
    )

    response = _governance_client(scratch.db, "personal-admin").get(
        "/api/agent-governance/pending-approvals?approver_id=lead-1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert [item["id"] for item in body["pending_approvals"]] == [own]
    assert foreign not in [item["id"] for item in body["pending_approvals"]]
    assert "foreign-secret" not in response.text


def test_governance_pending_queue_is_exact_scope_without_client_filter(scratch):
    scratch.db.add(_scoped_user(
        "personal-member", UserRole.MEMBER, workspace=None, tenant=None))
    scratch.db.commit()
    named = _pending_action(
        scratch.db,
        workspace="ws-named",
        tenant="tenant-named",
        params={"to": "named-secret@example.com"},
    )
    own = _pending_action(
        scratch.db,
        workspace=None,
        tenant=None,
        params={"to": "own@example.com"},
    )

    response = _governance_client(scratch.db, "personal-member").get(
        "/api/agent-governance/pending-approvals")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert [item["id"] for item in body["pending_approvals"]] == [own]
    assert named not in [item["id"] for item in body["pending_approvals"]]
    assert "named-secret" not in response.text


@pytest.mark.parametrize(
    "actor_ws,actor_tenant,action_ws,action_tenant,allowed",
    [
        # Same canonical default scope (None / "" / "default" one scope).
        (None, None, None, None, True),
        ("default", "default", "", "", True),
        ("", "", None, None, True),
        # Same named scope.
        ("ws-a", "tenant-a", "ws-a", "tenant-a", True),
        # Same mixed scope (named tenant, default workspace) is the SAME scope.
        (None, "tenant-a", "", "tenant-a", True),
        # Default actor vs named action, both dimensions and each one alone.
        (None, None, "ws-a", "tenant-a", False),
        (None, None, "ws-a", None, False),
        (None, None, None, "tenant-a", False),
        # Reverse direction: named-on-one-axis actor vs default action.
        ("ws-a", None, None, None, False),
        (None, "tenant-a", None, None, False),
        # Named mismatches.
        ("ws-a", "tenant-a", "ws-b", "tenant-a", False),
        ("ws-a", "tenant-a", "ws-a", "tenant-b", False),
        # Mixed named/default in BOTH directions on one axis.
        ("ws-a", None, "ws-a", "tenant-a", False),
        ("ws-a", "tenant-a", "ws-a", None, False),
    ],
)
def test_pending_scope_is_exact_not_a_default_wildcard(
    scratch, actor_ws, actor_tenant, action_ws, action_tenant, allowed,
):
    """Every public pending queue applies exact canonical scope in SQL.

    Same 14-case matrix as the history/recent read: default is grouped, never
    a wildcard for a named peer, in either direction and on each axis alone.
    """
    uid = "pending-admin-" + uuid.uuid4().hex[:10]
    scratch.db.add(_scoped_user(
        uid, UserRole.ADMIN, workspace=actor_ws, tenant=actor_tenant))
    scratch.db.commit()
    aid = _pending_action(
        scratch.db,
        workspace=action_ws,
        tenant=action_tenant,
        params={"to": "matrix-secret@example.com"},
    )

    client = _alias_client(scratch.db, uid)
    response = client.get("/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    listed = aid in [item["id"] for item in response.json()]

    if allowed:
        assert listed, response.text
        assert response.json()[0]["params"] == {
            "to": "matrix-secret@example.com"}
    else:
        assert not listed, response.text
        assert "matrix-secret" not in response.text


def test_pending_default_scope_reads_own_canonical_rows_and_stays_bounded(
        scratch):
    """NULL / "" / "default" are ONE legitimate Personal/default queue.

    Own default rows stay readable on the legacy + alias surfaces, with the
    established field/limit shapes; a named row never joins them.
    """
    scratch.db.add(_scoped_user(
        "personal-admin", UserRole.ADMIN, workspace=None, tenant=None))
    scratch.db.commit()
    own = {}
    for label, ws, tid in (
            ("null", None, None),
            ("empty", "", ""),
            ("literal", "default", "default")):
        own[label] = _pending_action(
            scratch.db,
            workspace=ws,
            tenant=tid,
            params={"to": f"{label}@example.com"},
        )
    named = _pending_action(
        scratch.db,
        workspace="ws-named",
        tenant="tenant-named",
        params={"to": "named-secret@example.com"},
    )

    legacy = _agent_client(scratch.db, "personal-admin").get(
        "/api/agents/approvals/pending")
    assert legacy.status_code == 200, legacy.text
    ids = [item["id"] for item in legacy.json()]
    assert set(ids) == set(own.values())
    assert named not in ids
    assert "named-secret" not in legacy.text
    assert set(legacy.json()[0]) == {
        "id", "agent_id", "action_type", "params", "reason", "created_at"}
    assert {
        item["params"]["to"] for item in legacy.json()
    } == {f"{label}@example.com" for label in own}

    bounded = _agent_client(scratch.db, "personal-admin").get(
        "/api/agents/approvals/pending?limit=2")
    assert bounded.status_code == 200, bounded.text
    assert len(bounded.json()) == 2

    alias = _alias_client(scratch.db, "personal-admin").get(
        "/api/agents/approvals/pending")
    assert alias.status_code == 200, alias.text
    assert set(item["id"] for item in alias.json()) == set(own.values())
    assert named not in [item["id"] for item in alias.json()]
    assert all(item["status"] == "pending" for item in alias.json())
    assert all("agent_name" in item for item in alias.json())


def test_pending_named_scope_remains_usable_on_every_surface(scratch):
    """A named ADMIN/member still sees legitimate named local approvals."""
    scratch.db.add_all([
        _scoped_user(
            "named-admin", UserRole.ADMIN,
            workspace="ws-a", tenant="tenant-a"),
        _scoped_user(
            "named-member", UserRole.MEMBER,
            workspace="ws-a", tenant="tenant-a"),
    ])
    scratch.db.commit()
    own = _pending_action(
        scratch.db, workspace="ws-a", tenant="tenant-a",
        params={"to": "named-own@example.com"})
    foreign = _pending_action(
        scratch.db, workspace="ws-b", tenant="tenant-b",
        params={"to": "foreign-secret@example.com"})

    legacy = _agent_client(scratch.db, "named-admin").get(
        "/api/agents/approvals/pending")
    assert legacy.status_code == 200, legacy.text
    assert [item["id"] for item in legacy.json()] == [own]
    assert foreign not in [item["id"] for item in legacy.json()]

    alias = _alias_client(scratch.db, "named-member").get(
        "/api/agents/approvals/pending")
    assert alias.status_code == 200, alias.text
    assert [item["id"] for item in alias.json()] == [own]
    assert foreign not in [item["id"] for item in alias.json()]

    governance = _governance_client(scratch.db, "named-admin").get(
        "/api/agent-governance/pending-approvals")
    assert governance.status_code == 200, governance.text
    assert [item["id"] for item in governance.json()["pending_approvals"]] \
        == [own]
    assert "foreign-secret" not in governance.text


def test_pending_scope_follows_current_durable_actor_after_move(scratch):
    """A stale request-token workspace must not keep the old queue open."""
    scratch.db.add(_scoped_user(
        "drift-user", UserRole.ADMIN,
        workspace="ws-old", tenant="tenant-old"))
    scratch.db.commit()
    old_action = _pending_action(
        scratch.db, workspace="ws-old", tenant="tenant-old",
        params={"to": "old-secret@example.com"})
    new_action = _pending_action(
        scratch.db, workspace="ws-new", tenant="tenant-new",
        params={"to": "new@example.com"})

    # The durable actor moves AND is demoted; the request object still carries
    # the old ADMIN role and old scope.
    scratch.db.query(User).filter(User.id == "drift-user").update({
        User.workspace_id: "ws-new",
        User.tenant_id: "tenant-new",
        User.role: UserRole.MEMBER.value,
    })
    scratch.db.commit()
    stale = SimpleNamespace(
        id="drift-user",
        role=UserRole.ADMIN.value,
        status="active",
        is_active=True,
        workspace_id="ws-old",
        tenant_id="tenant-old",
    )

    from api.approvals_routes import router as approvals_router

    client = _client_for_actor_object(scratch.db, stale, approvals_router)
    response = client.get("/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [new_action]
    assert old_action not in [item["id"] for item in response.json()]
    assert "old-secret" not in response.text


def test_pending_missing_or_deactivated_actor_fails_closed(scratch):
    """The durable actor check runs even when auth handed us a live object."""
    scratch.db.add(_scoped_user(
        "soon-gone", UserRole.ADMIN, workspace=None, tenant=None))
    scratch.db.commit()
    _pending_action(
        scratch.db, workspace=None, tenant=None,
        params={"to": "own@example.com"})
    stale = SimpleNamespace(
        id="soon-gone",
        role=UserRole.ADMIN.value,
        status="active",
        is_active=True,
        workspace_id=None,
        tenant_id=None,
    )

    from api.approvals_routes import router as approvals_router

    scratch.db.query(User).filter(User.id == "soon-gone").update({
        User.is_active: False,
        User.status: "inactive",
    })
    scratch.db.commit()
    inactive = _client_for_actor_object(
        scratch.db, stale, approvals_router).get(
            "/api/agents/approvals/pending")
    assert inactive.status_code == 403, inactive.text
    assert inactive.json()["detail"]["error"]["code"] == "ACCOUNT_INACTIVE"

    scratch.db.query(User).filter(User.id == "soon-gone").delete()
    scratch.db.commit()
    missing = _client_for_actor_object(
        scratch.db, stale, approvals_router).get(
            "/api/agents/approvals/pending")
    assert missing.status_code == 401, missing.text
    assert missing.json()["detail"]["error"]["code"] == "UNAUTHENTICATED"


def test_pending_storage_failure_is_a_refusal_not_empty_success(
        scratch, monkeypatch):
    """Unreadable storage must never look like "no pending approvals"."""
    scratch.db.add_all([
        _scoped_user(
            "personal-admin", UserRole.ADMIN, workspace=None, tenant=None),
        _scoped_user(
            "personal-member", UserRole.MEMBER, workspace=None, tenant=None),
    ])
    scratch.db.commit()
    _pending_action(
        scratch.db, workspace=None, tenant=None,
        params={"to": "own@example.com"})

    def _boom(*args, **kwargs):
        raise SQLAlchemyError("pending store unavailable")

    monkeypatch.setattr(
        InterventionService, "_pending_interventions_query", _boom)

    surfaces = (
        (_agent_client(scratch.db, "personal-admin"),
         "/api/agents/approvals/pending"),
        (_alias_client(scratch.db, "personal-member"),
         "/api/agents/approvals/pending"),
        (_governance_client(scratch.db, "personal-member"),
         "/api/agent-governance/pending-approvals"),
    )
    for client, path in surfaces:
        response = client.get(path)
        assert response.status_code == 503, response.text
        assert "PENDING_APPROVALS_UNAVAILABLE" in response.text


def test_governance_pending_caller_uses_named_actor_scope(scratch, monkeypatch):
    """Prove the fixed caller passes the CURRENT actor by keyword.

    The old call ``get_pending_interventions(approver_id)`` bound the client
    filter to ``workspace_id``. The new call names ``actor_id`` explicitly and
    never forwards the optional client value as scope.
    """
    scratch.db.add(_scoped_user(
        "personal-admin", UserRole.ADMIN, workspace=None, tenant=None))
    scratch.db.commit()
    calls = []
    original = InterventionService.get_pending_interventions_for_actor

    def _spy(self, *args, **kwargs):
        calls.append((args, kwargs))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(
        InterventionService, "get_pending_interventions_for_actor", _spy)

    response = _governance_client(scratch.db, "personal-admin").get(
        "/api/agent-governance/pending-approvals?approver_id=lead-1")
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ()
    assert kwargs["actor_id"] == "personal-admin"
    assert "db" in kwargs
    assert "approver_id" not in kwargs


def test_pending_production_mount_order_keeps_default_reads_exact(scratch):
    """Real production order: legacy agent router first, then the alias."""
    from api.agent_routes import router as agent_router
    from api.approvals_routes import router as approvals_router

    scratch.db.add(_scoped_user(
        "personal-admin", UserRole.ADMIN, workspace=None, tenant=None))
    scratch.db.commit()
    own = _pending_action(
        scratch.db, workspace=None, tenant=None,
        params={"to": "own@example.com"})
    named = _pending_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        params={"to": "named-secret@example.com"})

    app = FastAPI()
    app.include_router(agent_router)  # production mount order: legacy first
    app.include_router(approvals_router)
    user = scratch.db.query(User).filter(User.id == "personal-admin").one()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[_get_db] = lambda: scratch.db
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [own]
    assert named not in [item["id"] for item in response.json()]
    assert "named-secret" not in response.text


def test_pending_scope_survives_a_cold_reopen(scratch):
    """The queue's scope is durable data, not an in-memory request cache."""
    scratch.db.add(_scoped_user(
        "personal-admin", UserRole.ADMIN, workspace=None, tenant=None))
    scratch.db.commit()
    own = _pending_action(
        scratch.db, workspace=None, tenant=None,
        params={"to": "own@example.com"})
    named = _pending_action(
        scratch.db, workspace="ws-named", tenant="tenant-named",
        params={"to": "named-secret@example.com"})
    scratch.db.commit()

    scratch.reopen()
    response = _agent_client(scratch.db, "personal-admin").get(
        "/api/agents/approvals/pending")
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [own]
    assert named not in [item["id"] for item in response.json()]
    assert "named-secret" not in response.text
