"""Focused tests for stock-invoice assignment persistence.

The tests use the real assignment module and real ORM models.  Each test gets
its own scratch SQLite database so nothing can reach a configured live DB.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core import invoice_workflow_assignment as iwa
from core.assignment_plan import (
    new_assignment,
    new_step,
    new_teaching_snapshot,
)
from core.database import Base
from core.models import (
    GoalObjective,
    GoalRun,
    Tenant,
    User,
    WorkflowExecution,
    Workspace,
)

TENANT_ID = "fixture-tenant"
WORKSPACE_ID = "fixture-workspace"
USER_ID = "fixture-user"
OWNER_ID = "fixture-account-owner"
OTHER_OWNER_ID = "fixture-other-owner"


# ---------------------------------------------------------------------------
# Scratch database and model helpers
# ---------------------------------------------------------------------------


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


def _as_json(value):
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    return value


@pytest.fixture()
def scratch(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'invoice-assignment.sqlite3'}",
        future=True,
    )
    assert engine.url.get_backend_name() == "sqlite"
    assert Path(engine.url.database).resolve().is_relative_to(
        tmp_path.resolve())
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, future=True, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(iwa, "get_db_session", get_db_session)
    try:
        yield session_factory
    finally:
        engine.dispose()


def _seed_scope(session_factory):
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
        db.commit()


def _add_recipient(session_factory, user_id=OWNER_ID,
                   status="active", is_active=True):
    with session_factory() as db:
        db.add(_make_model(
            User,
            id=user_id,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            email=f"{user_id}@example.invalid",
            first_name="Fixture",
            last_name="Recipient",
            status=status,
            role="workspace_admin",
            is_active=is_active,
        ))
        db.commit()


def _install_scope_validator(monkeypatch, result=None):
    calls = []

    def fake_scope_error(db, *, user_id, workspace_id, tenant_id):
        calls.append({
            "user_id": user_id,
            "workspace_id": workspace_id,
            "tenant_id": tenant_id,
        })
        return result

    monkeypatch.setattr(
        iwa.notification_service, "_workflow_scope_error", fake_scope_error)
    return calls


def _invoice_intent(invoice_number):
    return hashlib.sha256(invoice_number.encode("utf-8")).hexdigest()


def _add_execution(session_factory, execution_id, invoice_number,
                   status="PENDING", context=None):
    row = _make_model(
        WorkflowExecution,
        execution_id=execution_id,
        workflow_id=iwa._WORKFLOW_ID,
        status=status,
        input_data=json.dumps({
            "_atom_execution_scope": {
                "tenant_id": TENANT_ID,
                "workspace_id": WORKSPACE_ID,
                "user_id": USER_ID,
            },
            "_atom_invoice_intent": _invoice_intent(invoice_number),
        }),
        context=json.dumps(context or {}),
        owner_id=USER_ID,
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        workspace_id=WORKSPACE_ID,
    )
    with session_factory() as db:
        db.add(row)
        db.commit()
    return row


def _plan(invoice_number):
    return new_assignment(
        objective=f"Read fixture invoice {invoice_number}",
        employee_id=USER_ID,
        tenant_id=TENANT_ID,
        workspace_id=WORKSPACE_ID,
        teaching_snapshot=new_teaching_snapshot(),
        authorized_actions=["retrieve"],
        steps=[new_step(
            step_id="lookup",
            title="Read invoice",
            operation_type="retrieve",
            adapter="invoice.lookup",
            effect="read_only",
            inputs={"invoice_number": invoice_number},
        )],
    )


def _attach(execution_id, invoice_number, plan=None, **kwargs):
    return iwa.attach_stock_invoice_assignment(
        execution_id,
        invoice_number,
        identity={
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "user_id": USER_ID,
            "employee_id": USER_ID,
        },
        assignment=plan or _plan(invoice_number),
        **kwargs,
    )


def _counts(session_factory):
    with session_factory() as db:
        return db.query(GoalObjective).count(), db.query(GoalRun).count()


def _install_link_write_failure(session_factory):
    with session_factory() as db:
        db.execute(text("""
            CREATE TRIGGER synthetic_attach_fail
            BEFORE UPDATE ON workflow_executions
            BEGIN
                SELECT RAISE(ABORT, 'synthetic link write failure');
            END
        """))
        db.commit()


def _run(coro):
    return asyncio.run(coro)


def _deliver(execution_id, run_id, invoice_number, *, identity=None, **kwargs):
    return _run(iwa.deliver_stock_invoice_owner_handoff(
        execution_id=execution_id,
        run_id=run_id,
        invoice_number=invoice_number,
        identity=identity or {
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "user_id": USER_ID,
            "employee_id": USER_ID,
        },
        **kwargs,
    ))


def _install_notification_fake(monkeypatch, factory=None, error=None):
    calls = []

    class FakeNotificationService:
        def __init__(self, db_session=None):
            self.db = db_session

        async def send_workflow_notification(self, **kwargs):
            calls.append(dict(kwargs))
            if error is not None:
                raise error
            if factory is not None:
                return factory(kwargs, len(calls))
            return {
                "success": True,
                "notification_id": kwargs["operation_id"],
                "created": len(calls) == 1,
                "emailed": False,
                "error": None,
            }

    monkeypatch.setattr(
        iwa.notification_service,
        "NotificationService",
        FakeNotificationService,
    )
    return calls


# ---------------------------------------------------------------------------
# Persistence behavior
# ---------------------------------------------------------------------------


def test_link_write_failure_rolls_back_goal_and_run(scratch):
    _seed_scope(scratch)
    invoice_number = "INV-ROLLBACK"
    _add_execution(scratch, "exec-rollback", invoice_number)
    _install_link_write_failure(scratch)

    before = _counts(scratch)
    with pytest.raises(IntegrityError) as raised:
        _attach("exec-rollback", invoice_number)

    assert "synthetic link write failure" in str(raised.value.orig)
    assert _counts(scratch) == before
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-rollback")
        assert getattr(row.status, "value", row.status) == "PENDING"
        assert _as_json(row.context) == {}


def test_linked_terminal_execution_replays_existing_run(scratch):
    _seed_scope(scratch)
    invoice_number = "INV-TERMINAL"
    _add_execution(scratch, "exec-terminal", invoice_number)

    first = _attach("exec-terminal", invoice_number)
    baseline = _counts(scratch)

    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-terminal")
        row.status = "COMPLETED"
        db.commit()

    replay = _attach("exec-terminal", invoice_number)

    assert replay == first
    assert _counts(scratch) == baseline
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-terminal")
        context = _as_json(row.context)
        assert context["run_id"] == first["run_id"]
        assert db.get(GoalRun, first["run_id"]).goal_id == context["goal_id"]


# ---------------------------------------------------------------------------
# Explicit account owner
# ---------------------------------------------------------------------------


def test_explicit_account_owner_is_validated_and_persisted(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-OWNER-PERSIST"
    _add_execution(scratch, "exec-owner-persist", invoice_number)
    calls = _install_scope_validator(monkeypatch)

    result = _attach(
        "exec-owner-persist",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )

    assert calls == [{
        "user_id": OWNER_ID,
        "workspace_id": WORKSPACE_ID,
        "tenant_id": TENANT_ID,
    }]
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-persist")
        context = _as_json(row.context)
        assert context[iwa._ACCOUNT_OWNER_CONTEXT_KEY] == OWNER_ID
        assert context[iwa._ACCOUNT_OWNER_CONTEXT_KEY] != USER_ID
        assert context["user_id"] == USER_ID
        assert db.get(GoalRun, result["run_id"]) is not None


@pytest.mark.parametrize("value", ["", "   ", 123, False])
def test_invalid_account_owner_is_rejected_without_write(
        scratch, monkeypatch, value):
    _seed_scope(scratch)
    invoice_number = "INV-OWNER-INVALID"
    _add_execution(scratch, "exec-owner-invalid", invoice_number)
    calls = _install_scope_validator(monkeypatch)
    before = _counts(scratch)

    with pytest.raises(ValueError):
        _attach(
            "exec-owner-invalid",
            invoice_number,
            account_owner_user_id=value,
        )

    assert calls == []
    assert _counts(scratch) == before
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-invalid")
        assert getattr(row.status, "value", row.status) == "PENDING"
        assert _as_json(row.context) == {}


def test_recipient_scope_error_blocks_first_attach_without_write(
        scratch, monkeypatch):
    _seed_scope(scratch)
    invoice_number = "INV-OWNER-SCOPE"
    _add_execution(scratch, "exec-owner-scope", invoice_number)
    calls = _install_scope_validator(monkeypatch, "recipient_inactive")
    before = _counts(scratch)

    with pytest.raises(PermissionError) as raised:
        _attach(
            "exec-owner-scope",
            invoice_number,
            account_owner_user_id=OWNER_ID,
        )

    assert "recipient_inactive" in str(raised.value)
    assert calls == [{
        "user_id": OWNER_ID,
        "workspace_id": WORKSPACE_ID,
        "tenant_id": TENANT_ID,
    }]
    assert _counts(scratch) == before
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-scope")
        assert getattr(row.status, "value", row.status) == "PENDING"
        assert _as_json(row.context) == {}


def test_replay_with_unchanged_owner_returns_existing_run(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-OWNER-REPLAY"
    _add_execution(scratch, "exec-owner-replay", invoice_number)
    calls = _install_scope_validator(monkeypatch)

    first = _attach(
        "exec-owner-replay",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )
    baseline = _counts(scratch)

    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-replay")
        baseline_context = _as_json(row.context)
        row.status = "COMPLETED"
        db.commit()

    replay = _attach(
        "exec-owner-replay",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )

    assert replay == first
    assert _counts(scratch) == baseline
    assert len(calls) == 1
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-replay")
        assert _as_json(row.context) == baseline_context


@pytest.mark.parametrize(("first_owner", "replay_owner"), [
    (OWNER_ID, OTHER_OWNER_ID),
    (OWNER_ID, None),
    (None, OWNER_ID),
])
def test_replay_owner_conflict_does_not_write(
        scratch, monkeypatch, first_owner, replay_owner):
    _seed_scope(scratch)
    _add_recipient(scratch)
    _add_recipient(scratch, OTHER_OWNER_ID)
    invoice_number = "INV-OWNER-CONFLICT"
    _add_execution(scratch, "exec-owner-conflict", invoice_number)
    calls = _install_scope_validator(monkeypatch)

    first_kwargs = (
        {} if first_owner is None
        else {"account_owner_user_id": first_owner})
    _attach("exec-owner-conflict", invoice_number, **first_kwargs)
    baseline = _counts(scratch)
    with scratch() as db:
        stored_context = _as_json(
            db.get(WorkflowExecution, "exec-owner-conflict").context)

    replay_kwargs = (
        {} if replay_owner is None
        else {"account_owner_user_id": replay_owner})
    with pytest.raises(ValueError) as raised:
        _attach("exec-owner-conflict", invoice_number, **replay_kwargs)

    assert "conflict" in str(raised.value).lower()
    assert _counts(scratch) == baseline
    assert len(calls) == (1 if first_owner is not None else 0)
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-conflict")
        assert _as_json(row.context) == stored_context


def test_omitting_account_owner_keeps_legacy_behavior(scratch, monkeypatch):
    _seed_scope(scratch)
    invoice_number = "INV-OWNER-LEGACY"
    _add_execution(scratch, "exec-owner-legacy", invoice_number)
    calls = _install_scope_validator(monkeypatch)

    first = _attach("exec-owner-legacy", invoice_number)
    replay = _attach("exec-owner-legacy", invoice_number)

    assert replay == first
    assert calls == []
    with scratch() as db:
        context = _as_json(
            db.get(WorkflowExecution, "exec-owner-legacy").context)
        assert iwa._ACCOUNT_OWNER_CONTEXT_KEY not in context


def test_owner_link_write_failure_rolls_back_everything(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-OWNER-ROLLBACK"
    _add_execution(scratch, "exec-owner-rollback", invoice_number)
    _install_scope_validator(monkeypatch)
    _install_link_write_failure(scratch)

    before = _counts(scratch)
    with pytest.raises(IntegrityError) as raised:
        _attach(
            "exec-owner-rollback",
            invoice_number,
            account_owner_user_id=OWNER_ID,
        )

    assert "synthetic link write failure" in str(raised.value.orig)
    assert _counts(scratch) == before
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-owner-rollback")
        assert getattr(row.status, "value", row.status) == "PENDING"
        assert _as_json(row.context) == {}


# ---------------------------------------------------------------------------
# Exact duplicate-key detection
# ---------------------------------------------------------------------------


def _integrity_error(orig):
    return IntegrityError("INSERT INTO fixture VALUES (?)", (), orig)


@pytest.mark.parametrize("table", ["goal_objectives", "goal_runs"])
def test_sqlite_exact_duplicate_column_is_replayable(table):
    orig = sqlite3.IntegrityError(
        f"UNIQUE constraint failed: {table}.id")
    assert iwa._is_deterministic_pk_collision(_integrity_error(orig))


@pytest.mark.parametrize("message", [
    "UNIQUE constraint failed: goal_objectives.tenant_id",
    "UNIQUE constraint failed: goal_runs.tenant_id",
    "UNIQUE constraint failed: goal_objectives.id, goal_runs.id",
    "UNIQUE constraint failed: goal_objectives.id (duplicate)",
    "UNIQUE constraint failed: goal_objectives.idx",
    "UNIQUE constraint failed: other.id",
    "goal_objectives.id",
    "goal_objectives_pkey",
    "PRIMARY KEY must be unique",
])
def test_sqlite_only_exact_duplicate_column_messages_are_replayable(message):
    orig = sqlite3.IntegrityError(message)
    assert not iwa._is_deterministic_pk_collision(_integrity_error(orig))


def test_sqlite_message_on_non_sqlite_error_is_not_replayable():
    orig = Exception("UNIQUE constraint failed: goal_runs.id")
    assert not iwa._is_deterministic_pk_collision(_integrity_error(orig))


@pytest.mark.parametrize("constraint", [
    "goal_objectives_pkey",
    "goal_runs_pkey",
])
@pytest.mark.parametrize(("code_attr", "diag_attr"), [
    ("pgcode", "diag"),
    ("sqlstate", "diagnostic"),
])
def test_postgres_exact_sqlstate_and_pkey_is_replayable(
        constraint, code_attr, diag_attr):
    orig = SimpleNamespace(**{
        code_attr: "23505",
        diag_attr: SimpleNamespace(constraint_name=constraint),
    })
    assert iwa._is_deterministic_pk_collision(_integrity_error(orig))


@pytest.mark.parametrize("constraint", [
    "goal_objectives_pkey",
    "goal_runs_pkey",
])
def test_postgres_diag_sqlstate_and_pkey_is_replayable(constraint):
    orig = SimpleNamespace(diag=SimpleNamespace(
        sqlstate="23505",
        constraint_name=constraint,
    ))
    assert iwa._is_deterministic_pk_collision(_integrity_error(orig))


@pytest.mark.parametrize("constraint", [
    "goal_objectives_pkey",
    "goal_runs_pkey",
])
def test_postgres_asyncpg_cause_exact_pkey_is_replayable(constraint):
    cause = Exception()
    cause.sqlstate = "23505"
    cause.constraint_name = constraint
    orig = Exception("duplicate key value violates unique constraint")
    orig.__cause__ = cause
    assert iwa._is_deterministic_pk_collision(_integrity_error(orig))


@pytest.mark.parametrize("orig", [
    SimpleNamespace(
        pgcode="23503",
        diag=SimpleNamespace(constraint_name="goal_objectives_pkey"),
    ),
    SimpleNamespace(
        pgcode="23505",
        diag=SimpleNamespace(constraint_name="goal_objectives_id_key"),
    ),
    SimpleNamespace(
        pgcode="23505",
        diag=SimpleNamespace(constraint_name="goal_objectives_pkey_extra"),
    ),
    SimpleNamespace(
        pgcode="23505",
        diag=SimpleNamespace(constraint_name=None),
    ),
    SimpleNamespace(pgcode="23505"),
    SimpleNamespace(message="goal_objectives_pkey"),
])
def test_postgres_near_miss_is_not_replayable(orig):
    assert not iwa._is_deterministic_pk_collision(_integrity_error(orig))


def test_non_integrity_error_is_not_replayable():
    error = ValueError("UNIQUE constraint failed: goal_runs.id")
    assert not iwa._is_deterministic_pk_collision(error)


# ---------------------------------------------------------------------------
# Scoped in-app owner handoff delivery
# ---------------------------------------------------------------------------


def test_owner_handoff_requires_exact_scope_link_and_invoice(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-SCOPE"
    _add_execution(scratch, "exec-handoff-scope", invoice_number)
    attached = _attach(
        "exec-handoff-scope",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )
    calls = _install_notification_fake(monkeypatch)

    with pytest.raises(PermissionError):
        _deliver(
            "exec-handoff-scope",
            attached["run_id"],
            invoice_number,
            identity={
                "tenant_id": "other-tenant",
                "workspace_id": WORKSPACE_ID,
                "user_id": USER_ID,
                "employee_id": USER_ID,
            },
        )
    with pytest.raises(LookupError):
        _deliver(
            "exec-handoff-scope",
            str(uuid.uuid4()),
            invoice_number,
        )
    with pytest.raises(ValueError):
        _deliver(
            "exec-handoff-scope",
            attached["run_id"],
            "INV-WRONG",
        )

    assert calls == []


def test_owner_handoff_uses_immutable_owner_not_caller(scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-OWNER"
    _add_execution(scratch, "exec-handoff-owner", invoice_number)
    attached = _attach(
        "exec-handoff-owner",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )
    calls = _install_notification_fake(monkeypatch)

    receipt = _deliver(
        "exec-handoff-owner", attached["run_id"], invoice_number)

    assert receipt["delivered"] is True
    assert len(calls) == 1
    assert calls[0]["user_id"] == OWNER_ID
    assert calls[0]["user_id"] != USER_ID
    assert calls[0]["tenant_id"] == TENANT_ID
    assert calls[0]["workspace_id"] == WORKSPACE_ID
    assert receipt["notification_id"] == calls[0]["operation_id"]


def test_owner_handoff_refuses_absent_or_malformed_binding_without_call(
        scratch, monkeypatch):
    _seed_scope(scratch)
    invoice_number = "INV-HANDOFF-NO-OWNER"
    _add_execution(scratch, "exec-handoff-no-owner", invoice_number)
    attached = _attach("exec-handoff-no-owner", invoice_number)
    calls = _install_notification_fake(monkeypatch)

    with pytest.raises(LookupError):
        _deliver(
            "exec-handoff-no-owner",
            attached["run_id"],
            invoice_number,
        )

    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-handoff-no-owner")
        context = _as_json(row.context)
        context[iwa._ACCOUNT_OWNER_CONTEXT_KEY] = "  "
        row.context = json.dumps(context)
        db.commit()

    with pytest.raises(ValueError):
        _deliver(
            "exec-handoff-no-owner",
            attached["run_id"],
            invoice_number,
        )

    assert calls == []


def test_owner_handoff_retry_reuses_one_stable_operation(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-RETRY"
    _add_execution(scratch, "exec-handoff-retry", invoice_number)
    attached = _attach(
        "exec-handoff-retry",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )
    calls = _install_notification_fake(monkeypatch)

    first = _deliver(
        "exec-handoff-retry", attached["run_id"], invoice_number)

    # A different handoff trigger state must not become new notification
    # material or a new operation.
    with scratch() as db:
        row = db.get(WorkflowExecution, "exec-handoff-retry")
        context = _as_json(row.context)
        context["trigger_reason"] = "review_expired"
        context["review_expires_at"] = "2026-01-01T00:00:00+00:00"
        row.context = json.dumps(context)
        db.commit()

    retry = _deliver(
        "exec-handoff-retry", attached["run_id"], invoice_number)

    assert first["operation_id"] == retry["operation_id"]
    assert first["notification_id"] == retry["notification_id"]
    assert first["created"] is True
    assert retry["created"] is False
    assert retry["duplicate"] is True
    assert len(calls) == 2
    assert calls[0]["operation_id"] == calls[1]["operation_id"]
    assert calls[0]["title"] == calls[1]["title"]
    assert calls[0]["message"] == calls[1]["message"]
    assert calls[0]["message"] == (
        "Invoice INV-HANDOFF-RETRY has been handed off to you for review.")


def test_owner_handoff_failure_receipt_never_reports_delivery(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-FAIL"
    _add_execution(scratch, "exec-handoff-fail", invoice_number)
    attached = _attach(
        "exec-handoff-fail",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )
    _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: {
            "success": False,
            "notification_id": None,
            "created": False,
            "emailed": False,
            "error": "recipient_inactive",
        },
    )

    receipt = _deliver(
        "exec-handoff-fail", attached["run_id"], invoice_number)

    assert receipt["success"] is False
    assert receipt["delivered"] is False
    assert receipt["status"] == "failed"
    assert receipt["notification_id"] is None
    assert receipt["error"] == "recipient_inactive"
    assert receipt["operation_id"] == iwa._owner_handoff_operation_id(
        "exec-handoff-fail", attached["run_id"])


@pytest.mark.parametrize("malformed", [
    "absent_success",
    "wrong_notification_id",
    "emailed_true",
    "missing_created",
])
def test_owner_handoff_malformed_response_is_never_delivered(
        scratch, monkeypatch, malformed):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = f"INV-HANDOFF-{malformed.upper()}"
    execution_id = f"exec-handoff-{malformed}"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id,
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )

    def factory(kwargs, attempt):
        response = {
            "success": True,
            "notification_id": kwargs["operation_id"],
            "created": True,
            "emailed": False,
            "error": None,
        }
        if malformed == "absent_success":
            response.pop("success")
        elif malformed == "wrong_notification_id":
            response["notification_id"] = f"not-{kwargs['operation_id']}"
        elif malformed == "emailed_true":
            response["emailed"] = True
        elif malformed == "missing_created":
            response.pop("created")
        return response

    _install_notification_fake(monkeypatch, factory=factory)
    receipt = _deliver(execution_id, attached["run_id"], invoice_number)

    assert receipt["success"] is False
    assert receipt["delivered"] is False
    assert receipt["status"] == "failed"
    assert receipt["notification_id"] is None
    assert receipt["error"] == "notification_failed"


def test_owner_handoff_unavailable_service_raises(scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-UNAVAILABLE"
    _add_execution(scratch, "exec-handoff-unavailable", invoice_number)
    attached = _attach(
        "exec-handoff-unavailable",
        invoice_number,
        account_owner_user_id=OWNER_ID,
    )
    _install_notification_fake(
        monkeypatch, error=RuntimeError("synthetic unavailable"))

    with pytest.raises(iwa.OwnerHandoffDeliveryError):
        _deliver(
            "exec-handoff-unavailable",
            attached["run_id"],
            invoice_number,
        )


# ---------------------------------------------------------------------------
# Durable pending/delivered receipt and recovery
# ---------------------------------------------------------------------------


def _reconcile_stock_handoff_receipt(
        execution_id, run_id, invoice_number, trigger):
    return _run(iwa.reconcile_stock_invoice_owner_handoff(
        execution_id=execution_id,
        run_id=run_id,
        invoice_number=invoice_number,
        identity={
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "user_id": USER_ID,
            "employee_id": USER_ID,
        },
        trigger=trigger,
    ))


def _read_stock_handoff_context(scratch, execution_id):
    with scratch() as db:
        context = _as_json(db.get(WorkflowExecution, execution_id).context)
        return dict(context)


def test_owner_handoff_receipt_is_pending_before_effect_and_keeps_context(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-RECEIPT"
    execution_id = "exec-handoff-receipt"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)

    with scratch() as db:
        row = db.get(WorkflowExecution, execution_id)
        context = _as_json(row.context)
        context["unrelated"] = {"keep": True}
        row.context = json.dumps(context)
        db.commit()

    observed = []
    calls = []

    class ReceiptInspectingService:
        def __init__(self, db_session=None):
            self.db = db_session

        async def send_workflow_notification(self, **kwargs):
            calls.append(dict(kwargs))
            observed.append(_read_stock_handoff_context(scratch, execution_id)[
                iwa._OWNER_HANDOFF_CONTEXT_KEY])
            return {
                "success": True,
                "notification_id": kwargs["operation_id"],
                "created": True,
                "emailed": False,
                "error": None,
            }

    monkeypatch.setattr(
        iwa.notification_service,
        "NotificationService",
        ReceiptInspectingService,
    )

    receipt = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {
            "event": "invoice_reply_expired",
            "step_id": "reply",
            "source_operation_id": "send-op",
        },
    )

    assert observed[0]["status"] == "pending"
    assert observed[0]["trigger"]["event"] == "invoice_reply_expired"
    assert receipt["status"] == "delivered"
    assert receipt["notification_id"] == calls[0]["operation_id"]
    stored = _read_stock_handoff_context(scratch, execution_id)
    assert stored["unrelated"] == {"keep": True}
    assert stored["run_id"] == attached["run_id"]
    assert stored[iwa._OWNER_HANDOFF_CONTEXT_KEY]["status"] == "delivered"


def test_owner_handoff_failure_recovers_and_preserves_first_event(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-RECOVER"
    execution_id = "exec-handoff-recover"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: {
            "success": attempt > 1,
            "notification_id": (
                kwargs["operation_id"] if attempt > 1 else None),
            "created": attempt > 1,
            "emailed": False,
            "error": None if attempt > 1 else "temporarily_unavailable",
        },
    )

    first = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"},
    )
    assert first["status"] == "pending"
    assert first["delivered"] is False
    assert first["error"] == "temporarily_unavailable"
    assert first["attempts"] == 1

    second = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_commitment_review_expired",
         "step_id": "commitment"},
    )
    assert second["status"] == "delivered"
    assert second["delivered"] is True
    assert second["attempts"] == 2
    assert len(calls) == 2
    assert calls[0]["operation_id"] == calls[1]["operation_id"]
    stored = _read_stock_handoff_context(scratch, execution_id)
    assert stored[iwa._OWNER_HANDOFF_CONTEXT_KEY]["trigger"]["event"] == (
        "invoice_reply_expired")
    assert stored[iwa._OWNER_HANDOFF_CONTEXT_KEY][
        "first_source_event"]["event"] == "invoice_reply_expired"

    third = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_commitment_no_commitment"})
    assert third["status"] == "delivered"
    assert len(calls) == 2


def test_owner_handoff_cancelled_or_unbound_run_has_no_effect(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-CANCELLED"
    execution_id = "exec-handoff-cancelled"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(monkeypatch)

    with scratch() as db:
        row = db.get(WorkflowExecution, execution_id)
        row.status = "CANCELLED"
        db.commit()

    assert _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired"},
    ) is None
    assert calls == []

    invoice_number = "INV-HANDOFF-UNBOUND"
    unbound_execution = "exec-handoff-unbound"
    _add_execution(scratch, unbound_execution, invoice_number)
    unbound = _attach(unbound_execution, invoice_number)
    with pytest.raises(LookupError):
        _reconcile_stock_handoff_receipt(
            unbound_execution, unbound["run_id"], invoice_number,
            {"event": "invoice_reply_expired"},
        )
    assert calls == []


def test_owner_handoff_origin_actor_scope_loss_stays_pending(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-ACTOR-REVOKED"
    execution_id = "exec-handoff-actor-revoked"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)

    # The real fixture actor is an active row in the exact execution scope.
    with scratch() as db:
        assert iwa.notification_service._workflow_scope_error(
            db,
            user_id=USER_ID,
            workspace_id=WORKSPACE_ID,
            tenant_id=TENANT_ID,
        ) is None

    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: {
            "success": False,
            "notification_id": None,
            "created": False,
            "emailed": False,
            "error": "temporarily_unavailable",
        },
    )

    first = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"},
    )
    assert first["status"] == "pending"
    assert first["delivered"] is False
    assert first["attempts"] == 1
    assert len(calls) == 1

    # Only the originating actor loses scope; the bound recipient stays active.
    with scratch() as db:
        actor = db.get(User, USER_ID)
        actor.is_active = False
        db.commit()

    with scratch() as db:
        recipient = db.get(User, OWNER_ID)
        assert getattr(
            recipient.status, "value", recipient.status) == "active"
        assert recipient.is_active is True
        assert iwa.notification_service._workflow_scope_error(
            db,
            user_id=OWNER_ID,
            workspace_id=WORKSPACE_ID,
            tenant_id=TENANT_ID,
        ) is None
        assert iwa.notification_service._workflow_scope_error(
            db,
            user_id=USER_ID,
            workspace_id=WORKSPACE_ID,
            tenant_id=TENANT_ID,
        ) is not None
        context = _as_json(db.get(WorkflowExecution, execution_id).context)
        assert context[iwa._ACCOUNT_OWNER_CONTEXT_KEY] == OWNER_ID
        assert context[iwa._OWNER_HANDOFF_CONTEXT_KEY]["status"] == "pending"

    # A fresh executor resume must not deliver the pending notification.
    second = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_commitment_review_expired",
         "step_id": "commitment"},
    )

    assert second["status"] == "pending"
    assert second["delivered"] is False
    assert second["success"] is False
    assert second["error"] == "actor_scope_unavailable"
    assert second["last_error"] == "actor_scope_unavailable"
    assert second["attempts"] == 2
    assert len(calls) == 1

    stored = _read_stock_handoff_context(scratch, execution_id)
    pending = stored[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    assert pending["status"] == "pending"
    assert pending["delivery_status"] == "pending"
    assert pending["delivered"] is False
    assert pending["error"] == "actor_scope_unavailable"
    assert pending["trigger"]["event"] == "invoice_reply_expired"
    assert pending["first_source_event"]["event"] == "invoice_reply_expired"
    assert stored[iwa._ACCOUNT_OWNER_CONTEXT_KEY] == OWNER_ID
    assert stored["run_id"] == attached["run_id"]

    direct = _deliver(execution_id, attached["run_id"], invoice_number)
    assert direct["status"] == "failed"
    assert direct["delivered"] is False
    assert direct["success"] is False
    assert direct["notification_id"] is None
    assert direct["error"] == "actor_scope_unavailable"
    assert len(calls) == 1


def _run_terminal_handoff_recovery(*, limit=None):
    # Startup owns exactly one call to the public helper; generic assignment
    # recovery must not duplicate or steal that work.
    kwargs = {} if limit is None else {"limit": limit}
    return _run(iwa.recover_pending_stock_invoice_owner_handoffs(**kwargs))


def test_terminal_pending_handoff_recovers_original_operation_once(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-TERMINAL"
    execution_id = "exec-handoff-terminal"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: {
            "success": attempt > 1,
            "notification_id": (
                kwargs["operation_id"] if attempt > 1 else None),
            "created": attempt > 1,
            "emailed": False,
            "error": None if attempt > 1 else "acknowledgement_lost",
        },
    )

    first = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"},
    )
    assert first["status"] == "pending"
    operation_id = first["operation_id"]

    # The stock run is terminal, but its durable pending receipt remains.
    with scratch() as db:
        row = db.get(WorkflowExecution, execution_id)
        row.status = "COMPLETED"
        db.commit()

    assert _run_terminal_handoff_recovery() == 1

    stored = _read_stock_handoff_context(scratch, execution_id)
    receipt = stored[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    assert receipt["status"] == "delivered"
    assert receipt["delivered"] is True
    assert receipt["operation_id"] == operation_id
    assert receipt["notification_id"] == operation_id
    assert receipt["attempts"] == 2
    assert receipt["first_source_event"]["event"] == "invoice_reply_expired"
    assert [call["operation_id"] for call in calls] == [
        operation_id, operation_id]

    # A delivered receipt is terminal and is never retried by a later scan.
    assert _run_terminal_handoff_recovery() == 0
    assert len(calls) == 2


def test_terminal_pending_handoff_preserves_cancellation_and_actor_scope(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-TERMINAL-GUARD"
    execution_id = "exec-handoff-terminal-guard"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: {
            "success": False,
            "notification_id": None,
            "created": False,
            "emailed": False,
            "error": "temporarily_unavailable",
        },
    )

    first = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"},
    )
    assert first["status"] == "pending"
    with scratch() as db:
        row = db.get(WorkflowExecution, execution_id)
        row.status = "COMPLETED"
        db.commit()

    # Only the actor loses scope; recovery must not deliver the notification.
    with scratch() as db:
        actor = db.get(User, USER_ID)
        actor.is_active = False
        db.commit()

    assert _run_terminal_handoff_recovery() == 1
    assert len(calls) == 1
    stored = _read_stock_handoff_context(scratch, execution_id)
    pending = stored[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    assert pending["status"] == "pending"
    assert pending["delivered"] is False
    assert pending["error"] == "actor_scope_unavailable"
    assert pending["attempts"] == 2

    # Cancellation is preserved: a later scan discovers and touches nothing.
    with scratch() as db:
        row = db.get(WorkflowExecution, execution_id)
        row.status = "CANCELLED"
        db.commit()

    assert _run_terminal_handoff_recovery() == 0
    assert len(calls) == 1
    current = _read_stock_handoff_context(scratch, execution_id)
    assert current[iwa._OWNER_HANDOFF_CONTEXT_KEY]["attempts"] == 2


def _pending_for_scan(scratch, execution_id, invoice_number):
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    receipt = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"})
    assert receipt["status"] == "pending"
    return attached


def _failure_outcome():
    return {
        "success": False,
        "notification_id": None,
        "created": False,
        "emailed": False,
        "error": "temporarily_unavailable",
    }


def _success_outcome(kwargs):
    return {
        "success": True,
        "notification_id": kwargs["operation_id"],
        "created": True,
        "emailed": False,
        "error": None,
    }


def test_pending_handoff_scan_rotates_to_later_row_after_failed_retry(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    first_id = "exec-handoff-fair-a"
    second_id = "exec-handoff-fair-b"
    first_invoice = "INV-HANDOFF-FAIR-A"
    second_invoice = "INV-HANDOFF-FAIR-B"

    _install_notification_fake(
        monkeypatch, factory=lambda kwargs, attempt: _failure_outcome())
    attached = {
        first_id: _pending_for_scan(
            scratch, first_id, first_invoice),
        second_id: _pending_for_scan(
            scratch, second_id, second_invoice),
    }

    # A is the oldest pending row and also has the smallest execution id.
    # Once its retry fails, its workflow update moves it behind B.
    with scratch() as db:
        db.get(WorkflowExecution, first_id).status = "COMPLETED"
        db.get(WorkflowExecution, second_id).status = "COMPLETED"
        db.get(WorkflowExecution, first_id).updated_at = datetime(
            2024, 1, 1, tzinfo=timezone.utc)
        db.get(WorkflowExecution, second_id).updated_at = datetime(
            2024, 1, 2, tzinfo=timezone.utc)
        db.commit()

    first_operation = iwa._owner_handoff_operation_id(
        first_id, attached[first_id]["run_id"])
    second_operation = iwa._owner_handoff_operation_id(
        second_id, attached[second_id]["run_id"])
    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: (
            _failure_outcome()
            if kwargs["operation_id"] == first_operation
            else _success_outcome(kwargs)
        ),
    )

    assert _run_terminal_handoff_recovery(limit=1) == 1
    assert [call["operation_id"] for call in calls] == [first_operation]

    assert _run_terminal_handoff_recovery(limit=1) == 1
    assert [call["operation_id"] for call in calls] == [
        first_operation, second_operation]

    first_receipt = _read_stock_handoff_context(
        scratch, first_id)[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    second_receipt = _read_stock_handoff_context(
        scratch, second_id)[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    assert first_receipt["status"] == "pending"
    assert first_receipt["attempts"] == 2
    assert second_receipt["status"] == "delivered"
    assert second_receipt["attempts"] == 2


def test_pending_handoff_scan_excludes_cancelled_before_limit(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    cancelled_id = "exec-handoff-cancel-before-a"
    valid_id = "exec-handoff-cancel-before-b"
    cancelled_invoice = "INV-HANDOFF-CANCEL-BEFORE-A"
    valid_invoice = "INV-HANDOFF-CANCEL-BEFORE-B"

    _install_notification_fake(
        monkeypatch, factory=lambda kwargs, attempt: _failure_outcome())
    attached = {
        cancelled_id: _pending_for_scan(
            scratch, cancelled_id, cancelled_invoice),
        valid_id: _pending_for_scan(
            scratch, valid_id, valid_invoice),
    }

    with scratch() as db:
        db.get(WorkflowExecution, cancelled_id).status = "CANCELLED"
        db.get(WorkflowExecution, cancelled_id).updated_at = datetime(
            2024, 1, 1, tzinfo=timezone.utc)
        db.get(WorkflowExecution, valid_id).status = "COMPLETED"
        db.get(WorkflowExecution, valid_id).updated_at = datetime(
            2024, 1, 2, tzinfo=timezone.utc)
        db.commit()

    valid_operation = iwa._owner_handoff_operation_id(
        valid_id, attached[valid_id]["run_id"])
    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: _success_outcome(kwargs),
    )

    assert _run_terminal_handoff_recovery(limit=1) == 1
    assert [call["operation_id"] for call in calls] == [valid_operation]
    assert _read_stock_handoff_context(
        scratch, cancelled_id)[iwa._OWNER_HANDOFF_CONTEXT_KEY][
            "status"] == "pending"


def test_pending_handoff_recovers_terminal_run_while_execution_pending(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    execution_id = "exec-handoff-terminal-run"
    invoice_number = "INV-HANDOFF-TERMINAL-RUN"

    _install_notification_fake(
        monkeypatch, factory=lambda kwargs, attempt: _failure_outcome())
    attached = _pending_for_scan(scratch, execution_id, invoice_number)

    with scratch() as db:
        execution = db.get(WorkflowExecution, execution_id)
        assert getattr(execution.status, "value", execution.status) == (
            "PENDING")
        db.get(GoalRun, attached["run_id"]).status = "completed"
        db.commit()

    calls = _install_notification_fake(
        monkeypatch,
        factory=lambda kwargs, attempt: _success_outcome(kwargs),
    )

    assert _run_terminal_handoff_recovery(limit=1) == 1
    assert len(calls) == 1
    receipt = _read_stock_handoff_context(
        scratch, execution_id)[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    assert receipt["status"] == "delivered"
    assert receipt["attempts"] == 2


def test_pending_handoff_exception_does_not_persist_private_text(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    execution_id = "exec-handoff-private-error"
    invoice_number = "INV-HANDOFF-PRIVATE-ERROR"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)

    async def fail_delivery(**kwargs):
        raise RuntimeError("private provider token value")

    monkeypatch.setattr(
        iwa, "deliver_stock_invoice_owner_handoff", fail_delivery)

    receipt = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"})

    assert receipt["status"] == "pending"
    assert receipt["error"] == "notification_failed"
    stored = _read_stock_handoff_context(
        scratch, execution_id)[iwa._OWNER_HANDOFF_CONTEXT_KEY]
    assert stored["error"] == "notification_failed"
    assert "private provider token value" not in json.dumps(stored)


# ---------------------------------------------------------------------------
# Read-only operator projection
# ---------------------------------------------------------------------------


def _project_stock_handoff(
        execution_id, run_id, invoice_number, *, identity=None,
        required=True):
    return iwa.stock_invoice_owner_handoff_projection(
        execution_id=execution_id,
        run_id=run_id,
        invoice_number=invoice_number,
        identity=identity or {
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "user_id": USER_ID,
            "employee_id": USER_ID,
        },
        required=required,
    )


def test_stock_handoff_projection_requires_exact_scope_link_and_invoice(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-PROJECTION-SCOPE"
    execution_id = "exec-handoff-projection-scope"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(monkeypatch)

    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
    ) == {"status": "pending"}

    assert _project_stock_handoff(
        execution_id,
        attached["run_id"],
        invoice_number,
        identity={
            "tenant_id": "other-tenant",
            "workspace_id": WORKSPACE_ID,
            "user_id": USER_ID,
            "employee_id": USER_ID,
        },
    ) is None
    assert _project_stock_handoff(
        execution_id,
        attached["run_id"],
        invoice_number,
        identity={
            "tenant_id": TENANT_ID,
            "workspace_id": "other-workspace",
            "user_id": USER_ID,
            "employee_id": USER_ID,
        },
    ) is None
    assert _project_stock_handoff(
        execution_id, str(uuid.uuid4()), invoice_number) is None
    assert _project_stock_handoff(
        execution_id, attached["run_id"], "INV-WRONG") is None
    assert calls == []


def test_stock_handoff_projection_reports_no_owner_without_notification(
        scratch, monkeypatch):
    _seed_scope(scratch)
    invoice_number = "INV-HANDOFF-PROJECTION-NO-OWNER"
    execution_id = "exec-handoff-projection-no-owner"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(execution_id, invoice_number)
    calls = _install_notification_fake(monkeypatch)

    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
        required=True,
    ) == {"status": "owner_not_selected"}
    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
        required=False,
    ) == {"status": "not_required"}
    assert calls == []


def test_stock_handoff_projection_malformed_receipt_is_unavailable(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-PROJECTION-MALFORMED"
    execution_id = "exec-handoff-projection-malformed"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(monkeypatch)

    def store(receipt):
        with scratch() as db:
            row = db.get(WorkflowExecution, execution_id)
            context = _as_json(row.context)
            context[iwa._OWNER_HANDOFF_CONTEXT_KEY] = receipt
            row.context = json.dumps(context)
            db.commit()

    store("not-a-receipt")
    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
    ) == {"status": "unavailable"}

    store({
        "status": "delivered",
        "delivery_status": "delivered",
        "delivered": True,
        "success": True,
        "notification_id": iwa._owner_handoff_operation_id(
            execution_id, attached["run_id"]),
    })
    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
    ) == {"status": "unavailable"}

    store({
        "status": "delivered",
        "delivery_status": "delivered",
        "delivered": True,
        "success": True,
        "notification_id": "not-the-operation",
        "delivered_at": "2026-01-01T00:00:00+00:00",
    })
    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
    ) == {"status": "unavailable"}
    assert calls == []


def test_stock_handoff_projection_real_delivered_receipt(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-PROJECTION-DELIVERED"
    execution_id = "exec-handoff-projection-delivered"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    calls = _install_notification_fake(monkeypatch)

    receipt = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_commitment_no_commitment", "step_id": "commitment"})
    assert receipt["status"] == "delivered"

    projection = _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number)
    assert projection == {
        "status": "delivered",
        "notification_id": receipt["notification_id"],
        "delivered_at": receipt["delivered_at"],
    }
    assert set(projection) == {
        "status", "notification_id", "delivered_at"}
    assert len(calls) == 1

    # Projection is a read: a repeated status read must not deliver again.
    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number) == projection
    assert len(calls) == 1


def test_stock_handoff_projection_pending_receipt_and_unverifiable_link(
        scratch, monkeypatch):
    _seed_scope(scratch)
    _add_recipient(scratch)
    invoice_number = "INV-HANDOFF-PROJECTION-PENDING"
    execution_id = "exec-handoff-projection-pending"
    _add_execution(scratch, execution_id, invoice_number)
    attached = _attach(
        execution_id, invoice_number, account_owner_user_id=OWNER_ID)
    _install_notification_fake(
        monkeypatch, factory=lambda kwargs, attempt: _failure_outcome())

    receipt = _reconcile_stock_handoff_receipt(
        execution_id, attached["run_id"], invoice_number,
        {"event": "invoice_reply_expired", "step_id": "reply"})
    assert receipt["status"] == "pending"
    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
    ) == {"status": "pending"}

    # Removing the durable link makes the operator projection unverifiable.
    with scratch() as db:
        row = db.get(WorkflowExecution, execution_id)
        context = _as_json(row.context)
        for key in ("execution_id", "workflow_id", "goal_id", "run_id"):
            context.pop(key, None)
        row.context = json.dumps(context)
        db.commit()

    assert _project_stock_handoff(
        execution_id, attached["run_id"], invoice_number,
    ) is None
