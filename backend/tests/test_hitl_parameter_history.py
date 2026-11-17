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
import uuid
from contextlib import contextmanager
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.auth import get_current_user
from core.database import Base
from core.database import get_db as _get_db
from core.intervention_service import (
    HITL_PARAMETER_HISTORY_KEY,
    InterventionService,
    describe_parameter_history,
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
        engine = create_engine(url, connect_args={"check_same_thread": False})
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


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    store = ScratchDB(tmp_path / "hitl-parameter-history.db")
    db = store.open()
    db.add_all([
        _user("lead-1", UserRole.TEAM_LEAD),
        _user("admin-1", UserRole.ADMIN),
        _user("super-1", UserRole.SUPER_ADMIN),
        _user("member-1", UserRole.MEMBER),
        _user("foreign-admin", UserRole.ADMIN, workspace="ws-other"),
        _user("inactive-admin", UserRole.ADMIN, active=False),
    ])
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
