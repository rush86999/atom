"""Scoped tests for stock-invoice task admission review reuse.

The tests use the same scratch-SQLite pattern as the supplied invoice tests.
They exercise the real pending-review lookup in ``WorkflowEngine`` while the
invoice workflow material is supplied directly, so no provider, route or live
database is involved.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.autonomy_policy as autonomy_policy
import core.invoice_launch_admission as invoice_launch_admission
import core.task_classification as task_classification
import core.workflow_engine as workflow_engine
from core.autonomy_policy import (
    NEVER_TASK_ADMISSION_ACTION,
    decision_covers,
    warm_task_admission_receipt_denial,
)
from core.database import Base
from core.invoice_launch_admission import InvalidStockInvoiceAccountOwner
from core.models import HITLAction, Tenant, User, Workspace

TENANT_ID = "fixture-tenant"
WORKSPACE_ID = "fixture-workspace"
USER_ID = "fixture-user"
OTHER_USER_ID = "fixture-foreign-user"
FOREIGN_SCOPE_USER_ID = "fixture-foreign-scope-owner"
OTHER_TENANT_ID = "fixture-foreign-tenant"
OTHER_WORKSPACE_ID = "fixture-foreign-workspace"
EXECUTION_ID = "exec-invoice-review"
TASK_FINGERPRINT = "invoice-task-fingerprint"
WORKFLOW_ID = "htn_invoice_followup"


def _default_value(column):
    try:
        python_type = column.type.python_type
    except (AttributeError, NotImplementedError):
        python_type = str
    if python_type is bool:
        return False
    if python_type is int:
        return 0
    if python_type is float:
        return 0.0
    if python_type is bytes:
        return b""
    if python_type is dict:
        return {}
    if python_type is list:
        return []
    if python_type is datetime:
        return datetime.now(timezone.utc)
    if python_type is date:
        return date.today()
    if python_type is uuid.UUID:
        return uuid.uuid4()
    enums = getattr(column.type, "enums", None)
    if enums:
        return enums[0]
    return ""


def _make_model(model, **overrides):
    columns = {column.name: column for column in model.__table__.columns}
    values = {}
    for name, column in columns.items():
        if name in overrides:
            continue
        if column.nullable:
            continue
        if column.default is not None or column.server_default is not None:
            continue
        if column.primary_key and column.autoincrement in (True, "auto"):
            continue
        values[name] = _default_value(column)
    values.update({
        name: value for name, value in overrides.items() if name in columns
    })
    return model(**values)


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'invoice-pending-review.sqlite3'}",
        future=True,
    )
    assert engine.url.get_backend_name() == "sqlite"
    assert Path(engine.url.database).resolve().is_relative_to(
        tmp_path.resolve())
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, future=True, expire_on_commit=False)

    with session_factory() as db:
        db.add(_make_model(
            Tenant,
            id=TENANT_ID,
            name="Fixture Tenant",
            subdomain="fixture-tenant",
        ))
        db.add(_make_model(
            Workspace,
            id=WORKSPACE_ID,
            tenant_id=TENANT_ID,
            name="Fixture Workspace",
        ))
        db.add(_make_model(
            User,
            id=USER_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            email="fixture@example.invalid",
            first_name="Fixture",
            last_name="Owner",
            status="active",
            role="workspace_admin",
            is_active=True,
        ))
        db.add(_make_model(
            User,
            id=OTHER_USER_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            email="fixture-foreign@example.invalid",
            first_name="Fixture",
            last_name="Foreign",
            status="active",
            role="workspace_admin",
            is_active=True,
        ))
        db.commit()

    @contextmanager
    def get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(workflow_engine, "get_db_session", get_db_session)
    monkeypatch.setattr(
        invoice_launch_admission, "get_db_session", get_db_session)
    try:
        yield session_factory
    finally:
        engine.dispose()


class _Profile:
    owner_user_id = USER_ID

    def as_dict(self):
        return {
            "difficulty": "unknown",
            "category": "unknown",
            "domain": "unknown",
            "owner_user_id": USER_ID,
        }


class _Policy:
    """Return the same task under a revision the test controls."""

    def __init__(self):
        self.revision = 1

    def evaluate(self, _db, _profile, **_kwargs):
        return {
            "outcome": "review",
            "matched": True,
            "rule_ids": ["rule-invoice"],
            "rule_bindings": [
                {"id": "rule-invoice", "revision": self.revision},
            ],
            "owner_user_id": USER_ID,
            "task_fingerprint": TASK_FINGERPRINT,
            "reason": "A never-autonomous rule matched this invoice task.",
        }


class _Governance:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.requests = []

    def request_approval(self, **kwargs):
        self.requests.append(kwargs)
        action_id = f"hitl-invoice-{len(self.requests)}"
        with self.session_factory() as db:
            db.add(_make_model(
                HITLAction,
                id=action_id,
                action_type=kwargs.get("action_type"),
                status="pending",
                agent_id=kwargs.get("agent_id"),
                params=dict(kwargs.get("params") or {}),
                context_snapshot=dict(
                    kwargs.get("execution_context") or {}),
                reason=kwargs.get("reason"),
                user_id=kwargs.get("user_id"),
            ))
            db.commit()
        return action_id


class _StateManager:
    def __init__(self):
        self.status_updates = []

    async def update_execution_status(
            self, execution_id, status, error=None):
        self.status_updates.append((execution_id, status, error))
        return True


class _ConnectionManager:
    async def notify_workflow_status(self, *_args, **_kwargs):
        return None


@pytest.fixture()
def engine_bundle(scratch, monkeypatch):
    governance = _Governance(scratch)
    policy = _Policy()
    state_manager = _StateManager()
    connection_manager = _ConnectionManager()

    class _Factory:
        @staticmethod
        def get_governance_service(_db, **_kwargs):
            return governance

    monkeypatch.setattr(workflow_engine, "ServiceFactory", _Factory)
    monkeypatch.setattr(
        workflow_engine, "get_state_manager", lambda: state_manager)
    monkeypatch.setattr(
        workflow_engine, "get_connection_manager", lambda: connection_manager)
    monkeypatch.setattr(
        workflow_engine.WorkflowEngine,
        "_notify_workflow_paused",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        autonomy_policy, "evaluate_task_admission", policy.evaluate)
    monkeypatch.setattr(
        task_classification, "current_task_profile", lambda: _Profile())

    engine = workflow_engine.WorkflowEngine()
    engine.state_manager = state_manager
    return engine, governance, policy


WORKFLOW = {
    "id": WORKFLOW_ID,
    "name": "Stock invoice follow-up",
    "description": "Prepare and send the invoice reminder for INV-REVIEW",
    "goal": "Prepare and send the invoice reminder for INV-REVIEW",
    "objective": "Prepare and send the invoice reminder for INV-REVIEW",
    "created_by": USER_ID,
    "user_id": USER_ID,
    "agent_id": "system_agent",
    "tenant_id": TENANT_ID,
    "workspace_id": WORKSPACE_ID,
}


def _admit(engine):
    return engine.admit_never_autonomous_task(
        EXECUTION_ID,
        WORKFLOW,
        {},
        USER_ID,
        WORKSPACE_ID,
        TENANT_ID,
    )


def _pending_rows(scratch):
    with scratch() as db:
        return (
            db.query(HITLAction)
            .filter(
                HITLAction.action_type == NEVER_TASK_ADMISSION_ACTION,
                HITLAction.status == "pending",
            )
            .order_by(HITLAction.created_at.desc(), HITLAction.id.desc())
            .all()
        )


def _seed_pending(
    scratch,
    *,
    action_id,
    owner_user_id=USER_ID,
    tenant_id=TENANT_ID,
    workspace_id=WORKSPACE_ID,
    revision=1,
):
    params = {
        "execution_id": EXECUTION_ID,
        "task_fingerprint": TASK_FINGERPRINT,
        "rule_ids": ["rule-invoice"],
        "rule_bindings": [
            {"id": "rule-invoice", "revision": revision},
        ],
        "owner_user_id": owner_user_id,
    }
    snapshot = {
        "execution_id": EXECUTION_ID,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "user_id": owner_user_id,
    }
    with scratch() as db:
        db.add(_make_model(
            HITLAction,
            id=action_id,
            action_type=NEVER_TASK_ADMISSION_ACTION,
            status="pending",
            agent_id="system_agent",
            params=params,
            context_snapshot=snapshot,
            user_id=owner_user_id,
        ))
        db.commit()


@pytest.mark.asyncio
async def test_current_pending_review_is_reused(engine_bundle, scratch):
    engine, governance, _policy = engine_bundle

    assert await _admit(engine) == "paused"
    first = _pending_rows(scratch)
    assert len(first) == 1
    assert len(governance.requests) == 1
    first_id = first[0].id

    assert await _admit(engine) == "paused"

    assert len(governance.requests) == 1
    current = _pending_rows(scratch)
    assert [row.id for row in current] == [first_id]


@pytest.mark.asyncio
@pytest.mark.parametrize(("owner", "tenant", "workspace"), [
    (OTHER_USER_ID, TENANT_ID, WORKSPACE_ID),
    (USER_ID, OTHER_TENANT_ID, WORKSPACE_ID),
    (USER_ID, TENANT_ID, OTHER_WORKSPACE_ID),
])
async def test_foreign_pending_review_is_not_reused(
        engine_bundle, scratch, owner, tenant, workspace):
    engine, governance, _policy = engine_bundle
    _seed_pending(
        scratch,
        action_id="hitl-foreign",
        owner_user_id=owner,
        tenant_id=tenant,
        workspace_id=workspace,
    )

    assert await _admit(engine) == "paused"

    assert len(governance.requests) == 1
    request = governance.requests[0]
    assert request["params"]["owner_user_id"] == USER_ID
    assert request["execution_context"]["tenant_id"] == TENANT_ID
    assert request["execution_context"]["workspace_id"] == WORKSPACE_ID

    rows = _pending_rows(scratch)
    assert {row.id for row in rows} == {"hitl-foreign", "hitl-invoice-1"}

    # The local request is now current and is reused normally.
    assert await _admit(engine) == "paused"
    assert len(governance.requests) == 1


@pytest.mark.asyncio
async def test_policy_revision_renews_the_pending_review(
        engine_bundle, scratch):
    engine, governance, policy = engine_bundle

    policy.revision = 1
    assert await _admit(engine) == "paused"
    revision_one = _pending_rows(scratch)
    assert len(revision_one) == 1
    stale_id = revision_one[0].id
    assert revision_one[0].params["rule_bindings"] == [
        {"id": "rule-invoice", "revision": 1},
    ]

    policy.revision = 2
    assert await _admit(engine) == "paused"

    # The revision-1 request is stale and must not be reused. A new current
    # request must be filed even though the old row is still pending.
    assert len(governance.requests) == 2
    assert governance.requests[1]["params"]["rule_bindings"] == [
        {"id": "rule-invoice", "revision": 2},
    ]
    rows = _pending_rows(scratch)
    assert len(rows) == 2
    assert {row.id for row in rows} == {stale_id, "hitl-invoice-2"}

    # A reviewed revision 1 can never authorize revision 2; the current
    # revision 2 request can authorize itself.
    stale_review = {"outcome": "review", "rule_bindings": [
        {"id": "rule-invoice", "revision": 1},
    ]}
    current_review = {"outcome": "review", "rule_bindings": [
        {"id": "rule-invoice", "revision": 2},
    ]}
    assert decision_covers(stale_review, current_review) is False
    assert decision_covers(current_review, current_review) is True

    current_approval = dict(
        current_review,
        durable_admission={
            "hitl_action_id": "hitl-invoice-2",
            "approved_by": USER_ID,
        },
    )
    assert warm_task_admission_receipt_denial(
        stale_review, current_review,
        hitl_action_id=stale_id) == "policy_changed"
    assert warm_task_admission_receipt_denial(
        stale_review, current_approval,
        hitl_action_id=stale_id) == "policy_changed"
    assert warm_task_admission_receipt_denial(
        current_review, current_approval,
        hitl_action_id="hitl-invoice-2") is None

    # The new revision-2 request is the one reused while the stale row
    # remains present, so it cannot block the authorized approval.
    assert await _admit(engine) == "paused"
    assert len(governance.requests) == 2
    current = [
        row for row in _pending_rows(scratch)
        if row.params["rule_bindings"] == [
            {"id": "rule-invoice", "revision": 2},
        ]
    ]
    assert len(current) == 1
    assert current[0].id == "hitl-invoice-2"


class _LaunchStateManager:
    """Record reservation attempts without creating durable work."""

    def __init__(self):
        self.reservations = []
        self.status_updates = []

    async def reserve_invoice_launch(
            self,
            invoice_number,
            *,
            identity,
            idempotency_key,
            account_owner_user_id=None):
        self.reservations.append({
            "invoice_number": invoice_number,
            "identity": dict(identity),
            "idempotency_key": idempotency_key,
            "account_owner_user_id": account_owner_user_id,
        })
        return "exec-owner-guard", True

    async def get_execution_state(self, _execution_id):
        return {"status": "pending"}

    async def update_execution_status(
            self, execution_id, status, error=None):
        self.status_updates.append((execution_id, status, error))
        return True

    async def restore_paused_invoice_launch(self, _execution_id):
        return True


class _LaunchGate:
    """Record task-gate calls without filing a review."""

    def __init__(self):
        self.calls = []

    async def admit_never_autonomous_task(self, **kwargs):
        self.calls.append(kwargs)
        return "paused"


@pytest.mark.asyncio
async def test_foreign_scope_explicit_owner_is_rejected_before_new_work(
        scratch):
    with scratch() as db:
        db.add(_make_model(
            User,
            id=FOREIGN_SCOPE_USER_ID,
            tenant_id=OTHER_TENANT_ID,
            workspace_id=OTHER_WORKSPACE_ID,
            email="fixture-foreign-scope@example.invalid",
            first_name="Fixture",
            last_name="Foreign",
            status="active",
            role="workspace_admin",
            is_active=True,
        ))
        db.commit()

    state_manager = _LaunchStateManager()
    gate = _LaunchGate()

    with pytest.raises(InvalidStockInvoiceAccountOwner) as excinfo:
        await invoice_launch_admission.admit_stock_invoice_launch(
            "INV-OWNER-GUARD",
            identity={
                "tenant_id": TENANT_ID,
                "workspace_id": WORKSPACE_ID,
                "user_id": USER_ID,
            },
            idempotency_key="owner-guard-foreign-scope",
            account_owner_user_id=FOREIGN_SCOPE_USER_ID,
            state_manager=state_manager,
            engine=gate,
        )

    # The sanitized error cannot echo the selected owner or recipient detail.
    assert FOREIGN_SCOPE_USER_ID not in str(excinfo.value)
    # The guard precedes both the reservation and the human-review gate.
    assert state_manager.reservations == []
    assert gate.calls == []
