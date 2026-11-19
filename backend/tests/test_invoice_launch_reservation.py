"""Focused tests for the deterministic invoice-launch reservation."""

import asyncio
import hashlib

import pytest

pytest.importorskip("aiosqlite")
pytest_asyncio = pytest.importorskip("pytest_asyncio")

from sqlalchemy import Column, DateTime, Integer, String, Text, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

import core.execution_state_manager as manager_module
from core.execution_state_manager import (
    EXECUTION_SCOPE_KEY,
    INVOICE_INTENT_KEY,
    INVOICE_LAUNCH_WORKFLOW_ID,
    ExecutionStateManager,
    InvoiceLaunchConflict,
)

Base = declarative_base()


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    execution_id = Column(String(36), primary_key=True)
    workflow_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    input_data = Column(Text)
    steps = Column(Text)
    outputs = Column(Text)
    context = Column(Text)
    version = Column(Integer, nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    error = Column(Text)
    user_id = Column(String)
    owner_id = Column(String)
    tenant_id = Column(String)


IDENTITY = {"tenant_id": "tenant-1", "workspace_id": "workspace-1", "user_id": "user-1"}
OTHER_IDENTITY = {
    "tenant_id": "tenant-1",
    "workspace_id": "workspace-1",
    "user_id": "user-2",
}


def _session_factory(path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}", connect_args={"timeout": 30}
    )
    return engine, async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def store(tmp_path, monkeypatch):
    path = tmp_path / "state.db"
    engine, sessions = _session_factory(path)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(manager_module, "WorkflowExecution", WorkflowExecution)
    monkeypatch.setattr(manager_module, "get_async_db_session", sessions)
    yield ExecutionStateManager(), path, engine
    await engine.dispose()


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_concurrent_identical_reservations_create_one(store):
    manager, _, _ = store
    results = await asyncio.gather(
        *[
            manager.reserve_invoice_launch(
                "INV-001", identity=IDENTITY, idempotency_key="launch-key"
            )
            for _ in range(6)
        ]
    )

    assert len({execution_id for execution_id, _ in results}) == 1
    assert sum(created for _, created in results) == 1


@pytest.mark.asyncio
async def test_replay_and_conflict(store):
    manager, _, _ = store
    first = await manager.reserve_invoice_launch(
        " INV-001 ", identity=IDENTITY, idempotency_key="launch-key"
    )
    replay = await manager.reserve_invoice_launch(
        " INV-001 ", identity=IDENTITY, idempotency_key="launch-key"
    )

    assert replay == (first[0], False)

    with pytest.raises(InvoiceLaunchConflict):
        await manager.reserve_invoice_launch(
            "INV-002", identity=IDENTITY, idempotency_key="launch-key"
        )

    other_scope = await manager.reserve_invoice_launch(
        "INV-001", identity=OTHER_IDENTITY, idempotency_key="launch-key"
    )
    assert other_scope[0] != first[0]
    assert other_scope[1] is True

    state = await manager.get_execution_state(first[0])
    assert state["workflow_id"] == INVOICE_LAUNCH_WORKFLOW_ID
    assert state["input_data"]["invoice_number"] == " INV-001 "
    assert state["input_data"][INVOICE_INTENT_KEY] == _digest(" INV-001 ")


@pytest.mark.asyncio
async def test_replay_after_restart(store, monkeypatch):
    manager, path, old_engine = store
    execution_id, created = await manager.reserve_invoice_launch(
        "INV-001", identity=IDENTITY, idempotency_key="launch-key"
    )
    assert created is True

    await old_engine.dispose()
    new_engine, sessions = _session_factory(path)
    monkeypatch.setattr(manager_module, "get_async_db_session", sessions)

    replayed = await ExecutionStateManager().reserve_invoice_launch(
        "INV-001", identity=IDENTITY, idempotency_key="launch-key"
    )
    assert replayed == (execution_id, False)
    await new_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("column", ["owner_id", "user_id", "tenant_id"])
async def test_replay_rejects_inconsistent_owner_columns(store, column):
    manager, _, engine = store
    execution_id, created = await manager.reserve_invoice_launch(
        "INV-001", identity=IDENTITY, idempotency_key="launch-key"
    )
    assert created is True

    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"UPDATE workflow_executions SET {column} = :value "
                "WHERE execution_id = :execution_id"
            ),
            {"value": "inconsistent", "execution_id": execution_id},
        )

    with pytest.raises(InvoiceLaunchConflict):
        await manager.reserve_invoice_launch(
            "INV-001", identity=IDENTITY, idempotency_key="launch-key"
        )

    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT COUNT(*) FROM workflow_executions")
        )
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_resume_preserves_only_reservation_scope_and_digest(store):
    manager, _, _ = store
    execution_id, _ = await manager.reserve_invoice_launch(
        "INV-001", identity=IDENTITY, idempotency_key="launch-key"
    )

    await manager.update_execution_inputs(
        execution_id,
        {
            EXECUTION_SCOPE_KEY: {"tenant_id": "evil", "user_id": "evil"},
            INVOICE_INTENT_KEY: "forged",
            "note": "ordinary update",
        },
    )
    state = await manager.get_execution_state(execution_id)
    assert state["input_data"][EXECUTION_SCOPE_KEY] == IDENTITY
    assert state["input_data"][INVOICE_INTENT_KEY] == _digest("INV-001")
    assert state["input_data"]["note"] == "ordinary update"

    ordinary_id = await manager.create_execution("other_workflow", {"note": "old"})
    await manager.update_execution_inputs(
        ordinary_id, {INVOICE_INTENT_KEY: "ordinary marker", "note": "new"}
    )
    ordinary = await manager.get_execution_state(ordinary_id)
    assert ordinary["input_data"][INVOICE_INTENT_KEY] == "ordinary marker"
    assert ordinary["input_data"]["note"] == "new"


@pytest.mark.asyncio
async def test_create_execution_strips_reservation_marker(store):
    manager, _, _ = store
    execution_id = await manager.create_execution(
        "other_workflow",
        {INVOICE_INTENT_KEY: "forged", "note": "kept"},
        identity=IDENTITY,
    )
    state = await manager.get_execution_state(execution_id)
    assert INVOICE_INTENT_KEY not in state["input_data"]
    assert state["input_data"]["note"] == "kept"
    assert state["input_data"][EXECUTION_SCOPE_KEY] == IDENTITY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invoice_number,idempotency_key,identity",
    [
        (None, "key", IDENTITY),
        ("   ", "key", IDENTITY),
        ("INV-001", "", IDENTITY),
        ("INV-001", "x" * 256, IDENTITY),
        ("INV-001", "key", {"tenant_id": "t", "workspace_id": "w"}),
    ],
)
async def test_invalid_reservations_are_rejected(
    store, invoice_number, idempotency_key, identity
):
    manager, _, _ = store
    with pytest.raises(ValueError):
        await manager.reserve_invoice_launch(
            invoice_number, identity=identity, idempotency_key=idempotency_key
        )


class _PostgresError(Exception):
    def __init__(self, message, *, sqlstate="23505", constraint_name=None):
        super().__init__(message)
        self.sqlstate = sqlstate
        if constraint_name is not None:
            self.constraint_name = constraint_name


class _AsyncpgError(_PostgresError):
    pass


def _wrapped_postgres_error(cause):
    wrapper = Exception(str(cause))
    wrapper.__cause__ = cause
    return wrapper


def test_primary_key_diagnostic_classification(monkeypatch):
    monkeypatch.setattr(manager_module, "WorkflowExecution", WorkflowExecution)
    sqlite = IntegrityError(
        "insert", {},
        Exception("UNIQUE constraint failed: workflow_executions.execution_id"),
    )
    postgres = IntegrityError(
        "insert", {},
        _PostgresError(
            'duplicate key value violates unique constraint "workflow_executions_pkey"',
            constraint_name="workflow_executions_pkey",
        ),
    )
    asyncpg = IntegrityError(
        "insert", {},
        _wrapped_postgres_error(
            _AsyncpgError(
                'duplicate key value violates unique constraint "workflow_executions_pkey"',
                constraint_name="workflow_executions_pkey",
            )
        ),
    )
    wrong_sqlstate = IntegrityError(
        "insert", {},
        _PostgresError(
            'duplicate key value violates unique constraint "workflow_executions_pkey"',
            sqlstate="23503",
            constraint_name="workflow_executions_pkey",
        ),
    )
    not_null = IntegrityError(
        "insert", {},
        Exception("NOT NULL constraint failed: workflow_executions.execution_id"),
    )

    assert manager_module._is_execution_id_primary_key_violation(sqlite)
    assert manager_module._is_execution_id_primary_key_violation(postgres)
    assert manager_module._is_execution_id_primary_key_violation(asyncpg)
    assert not manager_module._is_execution_id_primary_key_violation(wrong_sqlstate)
    assert not manager_module._is_execution_id_primary_key_violation(not_null)


def test_unrelated_unique_diagnostic_is_not_a_primary_key_conflict(monkeypatch):
    monkeypatch.setattr(manager_module, "WorkflowExecution", WorkflowExecution)
    sqlite_other = IntegrityError(
        "insert", {},
        Exception("UNIQUE constraint failed: workflow_executions.workflow_id"),
    )
    postgres_other = IntegrityError(
        "insert", {},
        _PostgresError(
            'duplicate key value violates unique constraint '
            '"workflow_executions_workflow_id_key"',
            constraint_name="workflow_executions_workflow_id_key",
        ),
    )
    asyncpg_other = IntegrityError(
        "insert", {},
        _wrapped_postgres_error(
            _AsyncpgError(
                'duplicate key value violates unique constraint '
                '"workflow_executions_workflow_id_key"',
                constraint_name="workflow_executions_workflow_id_key",
            )
        ),
    )
    noisy_params = IntegrityError(
        "INSERT INTO workflow_executions (execution_id) VALUES (?)",
        {"execution_id": "slot"},
        _PostgresError(
            'duplicate key value violates unique constraint '
            '"workflow_executions_workflow_id_key"',
            constraint_name="workflow_executions_workflow_id_key",
        ),
    )

    assert not manager_module._is_execution_id_primary_key_violation(sqlite_other)
    assert not manager_module._is_execution_id_primary_key_violation(postgres_other)
    assert not manager_module._is_execution_id_primary_key_violation(asyncpg_other)
    assert not manager_module._is_execution_id_primary_key_violation(noisy_params)
