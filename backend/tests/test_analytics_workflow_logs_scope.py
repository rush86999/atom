"""RED regression — analytics workflow-log reader must stay user/tenant scoped.

The new ``analytics.routes.workflow_logs_router`` is expected to mount the same
secured handler at both:

    /api/v1/analytics/workflows/{workflow_id}/logs
    /api/v1/analytics/analytics/workflows/{workflow_id}/logs   (legacy alias)

The handler must authorize the caller against the workflow execution's real
ownership columns before returning anything, and even for a permitted read it
must return execution-log *metadata only* — never the persisted
``trigger_data`` / ``results`` payloads that the legacy unscoped reader emits.

The scratch DB/actor fixtures come from the existing R89 scope suite so this
file exercises the same real ``User`` / ``WorkflowExecution`` /
``WorkflowExecutionLog`` models and the same real bearer-token contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json

import pytest
from fastapi.testclient import TestClient

from tests.test_round89_workflow_execution_scope import seeded  # noqa: F401

# Both mounted spellings of the same secured handler.
ROUTES = (
    "/api/v1/analytics/workflows/{workflow_id}/logs",
    "/api/v1/analytics/analytics/workflows/{workflow_id}/logs",
)

PAYLOAD_MARKERS = (
    "SECRET-ALICE-TRIGGER",
    "SECRET-ALICE-RESULTS",
    "SECRET-BOB-TRIGGER",
    "SECRET-BOB-RESULTS",
    "SECRET-ORPHAN-TRIGGER",
    "SECRET-ORPHAN-RESULTS",
    "SECRET-MISMATCH-TRIGGER",
    "SECRET-MISMATCH-RESULTS",
)

PAYLOAD_FIELDS = {
    "trigger_data",
    "results",
    "input_data",
    "output_data",
    "context",
    "execution_context",
    "payload",
}

REQUIRED_METADATA = {"id", "step_id", "status", "duration_ms", "created_at"}


@pytest.fixture
def db():
    """Seed the same isolated database used by route and middleware auth."""
    from core.database import SessionLocal, engine
    from core.models import Base, User, WorkflowExecution, WorkflowExecutionLog

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.rollback()
            session.query(WorkflowExecutionLog).filter(
                WorkflowExecutionLog.step_id.in_(
                    ("step-alice", "step-bob", "step-orphan", "step-mismatch")
                )
            ).delete(synchronize_session=False)
            session.query(WorkflowExecution).filter(
                WorkflowExecution.execution_id.in_(
                    ("exec-alice-1", "exec-bob-1", "exec-legacy", "exec-t1-nouser")
                )
            ).delete(synchronize_session=False)
            session.query(User).filter(User.id.in_(
                ("user-alice", "user-bob")
            )).delete(synchronize_session=False)
            session.commit()


@pytest.fixture
def log_seeded(db, seeded):
    """Add one readable receipt plus outside-authority and broken bindings."""
    from core.models import WorkflowExecution, WorkflowExecutionLog

    base = datetime(2026, 1, 1, 12, 0, 0)
    alice = db.query(WorkflowExecution).filter_by(execution_id="exec-alice-1").one()
    alice.context = json.dumps({"variables": {
        "tenant_id": "tenant-1", "workspace_id": "default",
    }})
    db.add(
        # A run owned by Bob in another tenant.
        WorkflowExecution(
            execution_id="exec-bob-1",
            workflow_id="wf-bob",
            status="COMPLETED",
            context=json.dumps({
                "variables": {"tenant_id": "tenant-2", "workspace_id": "default"},
                "results": {"crm_export": "SECRET-BOB-RESULTS"},
            }),
            user_id="user-bob",
            owner_id="user-bob",
            tenant_id="tenant-2",
        )
    )
    db.add_all(
        [
            # Readable receipt: Alice's own run.
            WorkflowExecutionLog(
                workflow_id="wf-alice",
                execution_id="exec-alice-1",
                step_id="step-alice",
                status="COMPLETED",
                duration_ms=11,
                created_at=base,
                trigger_data={"token": "SECRET-ALICE-TRIGGER"},
                results={"body": "SECRET-ALICE-RESULTS"},
            ),
            # Outside authority: Bob's run, same log shape.
            WorkflowExecutionLog(
                workflow_id="wf-bob",
                execution_id="exec-bob-1",
                step_id="step-bob",
                status="COMPLETED",
                duration_ms=22,
                created_at=base + timedelta(seconds=1),
                trigger_data={"token": "SECRET-BOB-TRIGGER"},
                results={"body": "SECRET-BOB-RESULTS"},
            ),
            # Orphan: no WorkflowExecution carries this workflow/execution id.
            WorkflowExecutionLog(
                workflow_id="wf-orphan",
                execution_id="exec-orphan-999",
                step_id="step-orphan",
                status="COMPLETED",
                duration_ms=33,
                created_at=base + timedelta(seconds=2),
                trigger_data={"token": "SECRET-ORPHAN-TRIGGER"},
                results={"body": "SECRET-ORPHAN-RESULTS"},
            ),
            # Mismatched binding: claims Alice's workflow id but points at Bob's
            # execution. It must never be folded into Alice's authorized read.
            WorkflowExecutionLog(
                workflow_id="wf-alice",
                execution_id="exec-bob-1",
                step_id="step-mismatch",
                status="COMPLETED",
                duration_ms=44,
                created_at=base + timedelta(seconds=3),
                trigger_data={"token": "SECRET-MISMATCH-TRIGGER"},
                results={"body": "SECRET-MISMATCH-RESULTS"},
            ),
        ]
    )
    db.commit()
    return {**seeded, "base": base}


@pytest.fixture
def client(db, log_seeded):
    """Real app router + real auth contract over the scratch DB."""
    from main_api_app import app
    with TestClient(app) as client:
        client.atom_actors = {
            actor.id: actor for actor in (log_seeded["alice"], log_seeded["bob"])
        }
        yield client


def _auth(client, user_id):
    from core.auth import create_access_token

    client.headers["Authorization"] = "Bearer " + create_access_token(
        {"sub": user_id}, user=client.atom_actors[user_id]
    )


def _logs(client, workflow_id, route):
    return client.get(route.format(workflow_id=workflow_id))


def _items(response):
    payload = response.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("logs", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _assert_no_payload_leak(response):
    body = response.text or ""
    for marker in PAYLOAD_MARKERS:
        assert marker not in body, f"payload marker leaked: {marker}"


def _assert_denied(response):
    assert response.status_code in (401, 403, 404), (
        f"expected auth/permission denial, got {response.status_code}: "
        f"{response.text}"
    )
    _assert_no_payload_leak(response)


@pytest.mark.parametrize("route", ROUTES)
def test_owner_reads_metadata_only_receipt_on_both_aliases(client, route):
    _auth(client, "user-alice")
    response = _logs(client, "wf-alice", route)
    assert response.status_code == 200, response.text

    items = _items(response)
    assert items, "permitted read returned no log metadata"
    assert {item["step_id"] for item in items} == {"step-alice"}, (
        "authorized read must contain only the caller's own execution logs; "
        "orphan/mismatched bindings leaked into the result"
    )

    for item in items:
        assert REQUIRED_METADATA <= set(item), (
            f"missing metadata keys: {REQUIRED_METADATA - set(item)}"
        )
        leaked_fields = PAYLOAD_FIELDS & set(item)
        assert not leaked_fields, (
            f"metadata-only contract violated by fields: {leaked_fields}"
        )

    _assert_no_payload_leak(response)


def _assert_no_visible_receipts(response):
    assert response.status_code == 200, response.text
    assert response.json() == []
    _assert_no_payload_leak(response)


@pytest.mark.parametrize("route", ROUTES)
def test_outside_authority_denied_without_payload_leak(client, route):
    # Alice must not read Bob's workflow in another tenant.
    _auth(client, "user-alice")
    _assert_no_visible_receipts(_logs(client, "wf-bob", route))

    # And Bob must not read Alice's workflow.
    _auth(client, "user-bob")
    _assert_no_visible_receipts(_logs(client, "wf-alice", route))


@pytest.mark.parametrize("route", ROUTES)
def test_orphan_and_mismatched_ids_never_authorize(client, route):
    _auth(client, "user-alice")

    # Orphan workflow id: no execution row to authorize against.
    _assert_no_visible_receipts(_logs(client, "wf-orphan", route))

    # Unknown workflow id is equally opaque.
    _assert_no_visible_receipts(_logs(client, "wf-does-not-exist", route))

    # The mismatched log lives under Alice's workflow id but binds to Bob's
    # execution; it must be absent from her permitted read and never leak.
    permitted = _logs(client, "wf-alice", route)
    assert permitted.status_code == 200, permitted.text
    assert {item["step_id"] for item in _items(permitted)} == {"step-alice"}
    _assert_no_payload_leak(permitted)


@pytest.mark.parametrize("route", ROUTES)
def test_unauthenticated_requests_are_denied(client, route):
    client.headers.pop("Authorization", None)
    _assert_denied(_logs(client, "wf-alice", route))
