"""Focused tests for stock-invoice assignment persistence.

The tests use the real assignment module and real ORM models.  Each test gets
its own scratch SQLite database so nothing can reach a configured live DB.
"""

from __future__ import annotations

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
