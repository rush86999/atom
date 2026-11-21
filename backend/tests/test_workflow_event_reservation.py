"""Durable event-receipt reservation tests.

These tests exercise ``ExecutionStateManager.reserve_event_execution`` against
real SQLite databases. A caller-supplied deterministic ``evt_...`` id is the
receipt identity, so racing two different subscription receipts that derive the
same id must produce exactly one row, and both callers must receive the original
winner's persisted state. Separate ids remain independent executions.

The persisted admission lives in ``context`` because that is the only channel
production recovery reads when claiming the run; event input stays separate.

No real application database is touched; every test uses a fresh temporary
SQLite file.
"""

import asyncio
from contextlib import asynccontextmanager
import json
import os
import sys
import uuid

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.append(os.getcwd())

import core.models  # noqa: F401  (registers WorkflowExecution)
import core.execution_state_manager as esm
from core.database import Base
from core.execution_state_manager import (
    EVENT_ADMISSION_KEY,
    EXECUTION_SCOPE_KEY,
    ExecutionStateManager,
)
from core.models import WorkflowExecution


IDENTITY = {
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
    "user_id": "user-a",
}


def _event_id(label):
    return f"evt_{label}_{uuid.uuid4().hex}"


def _admission(execution_id, subscription="sub-a", receipt="receipt-a"):
    return {
        "execution_id": execution_id,
        "subscription_id": subscription,
        "receipt_id": receipt,
    }


def _json_value(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


@pytest.fixture
def event_db(monkeypatch, tmp_path):
    """Fresh file-backed async SQLite database with the real ORM tables."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'workflow_event_reservations.db'}",
        connect_args={"timeout": 30},
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def _session():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(esm, "get_async_db_session", _session)

    async def _create_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    try:
        yield session_factory
    finally:
        asyncio.run(engine.dispose())


async def _fetch_row(session_factory, execution_id):
    async with session_factory() as session:
        result = await session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
        )
        return result.scalar_one_or_none()


async def _fetch_all(session_factory):
    async with session_factory() as session:
        result = await session.execute(select(WorkflowExecution))
        return result.scalars().all()


def test_reserve_persists_event_inputs_admission_context_scope_and_owner(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("single")
    admission = _admission(execution_id)
    input_data = {
        "event": {
            "type": "invoice.paid",
            "payload": {"amount": 42, "nested": [1, 2, {"ok": True}]},
        },
        "labels": ["finance", "paid"],
        EXECUTION_SCOPE_KEY: {
            "tenant_id": "forged-tenant",
            "workspace_id": "forged-workspace",
            "user_id": "forged-user",
        },
        EVENT_ADMISSION_KEY: {"execution_id": "evt_forged", "source": "caller"},
    }

    async def _scenario():
        state, created = await manager.reserve_event_execution(
            "wf_invoice_paid",
            input_data,
            execution_id=execution_id,
            identity=IDENTITY,
            admission=admission,
        )
        row = await _fetch_row(event_db, execution_id)
        return state, created, row

    state, created, row = asyncio.run(_scenario())

    assert created is True
    assert state["execution_id"] == execution_id
    assert state["workflow_id"] == "wf_invoice_paid"
    assert state["status"] == "PENDING"
    assert state["input_data"]["event"] == input_data["event"]
    assert state["input_data"]["labels"] == ["finance", "paid"]
    assert state["input_data"][EXECUTION_SCOPE_KEY] == IDENTITY
    assert EVENT_ADMISSION_KEY not in state["input_data"]
    assert state["context"] == {EVENT_ADMISSION_KEY: admission}
    assert state["context"][EVENT_ADMISSION_KEY]["execution_id"] == execution_id
    assert state["context"][EVENT_ADMISSION_KEY].get("source") != "caller"

    assert row is not None
    assert row.user_id == "user-a"
    assert row.owner_id == "user-a"
    assert row.tenant_id == "tenant-a"
    assert _json_value(row.input_data) == state["input_data"]
    assert _json_value(row.steps) == {}
    assert _json_value(row.outputs) == {}
    assert _json_value(row.context) == state["context"]
    assert _json_value(row.context)[EVENT_ADMISSION_KEY] == admission


def test_racing_same_row_id_returns_one_winner_and_original_receipt(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("racing")
    admission_a = _admission(execution_id, "sub-a", "receipt-a")
    admission_b = _admission(execution_id, "sub-b", "receipt-b")
    inputs_a = {"receipt": "A", "event": {"id": "event-a", "value": 1}}
    inputs_b = {"receipt": "B", "event": {"id": "event-b", "value": 2}}

    async def _race():
        return await asyncio.gather(
            manager.reserve_event_execution(
                "wf_events",
                inputs_a,
                execution_id=execution_id,
                identity=IDENTITY,
                admission=admission_a,
            ),
            manager.reserve_event_execution(
                "wf_events",
                inputs_b,
                execution_id=execution_id,
                identity=IDENTITY,
                admission=admission_b,
            ),
        )

    first, second = asyncio.run(_race())

    assert sorted([first[1], second[1]]) == [False, True]
    winner_state = first[0] if first[1] else second[0]
    loser_state = second[0] if first[1] else first[0]
    winner_admission = (
        admission_a if winner_state["input_data"]["receipt"] == "A" else admission_b
    )

    # The winner's event payload and subscription remain untouched, and both
    # callers receive that same stored reservation.
    assert winner_state["input_data"]["receipt"] in {"A", "B"}
    assert winner_state["input_data"]["event"] == (
        inputs_a["event"]
        if winner_state["input_data"]["receipt"] == "A"
        else inputs_b["event"]
    )
    assert winner_state["context"] == {EVENT_ADMISSION_KEY: winner_admission}
    assert loser_state["execution_id"] == execution_id
    assert loser_state["input_data"] == winner_state["input_data"]
    assert loser_state["context"] == winner_state["context"]
    assert loser_state["created_at"] == winner_state["created_at"]

    async def _stored():
        return await _fetch_all(event_db)

    rows = asyncio.run(_stored())
    assert len(rows) == 1
    assert rows[0].execution_id == execution_id
    assert _json_value(rows[0].input_data) == winner_state["input_data"]
    assert _json_value(rows[0].context) == winner_state["context"]


def test_different_row_ids_create_independent_executions(event_db):
    manager = ExecutionStateManager()
    first_id = _event_id("ordinary_a")
    second_id = _event_id("ordinary_b")
    first_admission = _admission(first_id, "sub-a", "receipt-a")
    second_admission = _admission(second_id, "sub-b", "receipt-b")

    async def _create_both():
        first = await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A", "event": {"id": "event-a"}},
            execution_id=first_id,
            identity=IDENTITY,
            admission=first_admission,
        )
        second = await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "B", "event": {"id": "event-b"}},
            execution_id=second_id,
            identity=IDENTITY,
            admission=second_admission,
        )
        rows = await _fetch_all(event_db)
        return first, second, rows

    first, second, rows = asyncio.run(_create_both())

    assert first[1] is True
    assert second[1] is True
    assert first[0]["execution_id"] == first_id
    assert second[0]["execution_id"] == second_id
    assert first[0]["input_data"]["receipt"] == "A"
    assert second[0]["input_data"]["receipt"] == "B"
    assert first[0]["context"] == {EVENT_ADMISSION_KEY: first_admission}
    assert second[0]["context"] == {EVENT_ADMISSION_KEY: second_admission}
    assert {row.execution_id for row in rows} == {first_id, second_id}


def test_admission_execution_id_must_match_reserved_row(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("mismatch")

    async def _attempt():
        return await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=_admission("evt_some_other_receipt"),
        )

    with pytest.raises(ValueError, match="admission.execution_id"):
        asyncio.run(_attempt())

    async def _stored():
        return await _fetch_row(event_db, execution_id)

    assert asyncio.run(_stored()) is None


def test_admission_must_be_a_strict_dict(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("not_dict")
    admission = type("Admission", (), {"execution_id": execution_id})()

    async def _attempt():
        return await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=admission,
        )

    with pytest.raises(ValueError, match="admission must be a dict"):
        asyncio.run(_attempt())

    async def _stored():
        return await _fetch_row(event_db, execution_id)

    assert asyncio.run(_stored()) is None


@pytest.mark.parametrize("execution_id", ["run_123", "evt_", "evt bad"])
def test_non_evt_row_id_is_rejected(event_db, execution_id):
    manager = ExecutionStateManager()

    async def _attempt():
        return await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=_admission(execution_id),
        )

    with pytest.raises(ValueError, match="evt_"):
        asyncio.run(_attempt())

    async def _stored():
        return await _fetch_row(event_db, execution_id)

    assert asyncio.run(_stored()) is None


@pytest.mark.parametrize("missing", ["tenant_id", "workspace_id", "user_id"])
def test_missing_scope_is_rejected(event_db, missing):
    manager = ExecutionStateManager()
    execution_id = _event_id(f"missing_{missing}")
    identity = dict(IDENTITY)
    identity.pop(missing)

    async def _attempt():
        return await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=identity,
            admission=_admission(execution_id),
        )

    with pytest.raises(ValueError, match="scope"):
        asyncio.run(_attempt())

    async def _stored():
        return await _fetch_row(event_db, execution_id)

    assert asyncio.run(_stored()) is None


def test_duplicate_with_different_workflow_is_rejected(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("workflow_collision")
    admission = _admission(execution_id)

    async def _scenario():
        first = await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=admission,
        )
        with pytest.raises(ValueError, match="workflow"):
            await manager.reserve_event_execution(
                "wf_other",
                {"receipt": "B"},
                execution_id=execution_id,
                identity=IDENTITY,
                admission=admission,
            )
        return first, await _fetch_all(event_db)

    first, rows = asyncio.run(_scenario())

    assert first[1] is True
    assert len(rows) == 1
    assert rows[0].workflow_id == "wf_events"
    assert _json_value(rows[0].input_data)["receipt"] == "A"


def test_duplicate_with_different_scope_is_rejected(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("scope_collision")
    admission = _admission(execution_id)
    other_identity = dict(IDENTITY, user_id="user-b")

    async def _scenario():
        first = await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=admission,
        )
        with pytest.raises(ValueError, match="scope"):
            await manager.reserve_event_execution(
                "wf_events",
                {"receipt": "B"},
                execution_id=execution_id,
                identity=other_identity,
                admission=admission,
            )
        return first, await _fetch_all(event_db)

    first, rows = asyncio.run(_scenario())

    assert first[1] is True
    assert len(rows) == 1
    assert _json_value(rows[0].input_data)["receipt"] == "A"
    assert _json_value(rows[0].input_data)[EXECUTION_SCOPE_KEY] == IDENTITY


def test_duplicate_with_different_stored_admission_id_is_rejected(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("admission_collision")
    admission = _admission(execution_id)

    async def _scenario():
        first = await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=admission,
        )
        async with event_db() as session:
            await session.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(
                    context=json.dumps(
                        {EVENT_ADMISSION_KEY: {"execution_id": "evt_other"}}
                    )
                )
            )
            await session.commit()

        with pytest.raises(ValueError, match="admission"):
            await manager.reserve_event_execution(
                "wf_events",
                {"receipt": "B"},
                execution_id=execution_id,
                identity=IDENTITY,
                admission=admission,
            )
        return first, await _fetch_all(event_db)

    first, rows = asyncio.run(_scenario())

    assert first[1] is True
    assert len(rows) == 1
    assert _json_value(rows[0].input_data)["receipt"] == "A"


def test_duplicate_with_different_stored_receipt_is_rejected(event_db):
    manager = ExecutionStateManager()
    execution_id = _event_id("receipt_collision")
    admission = _admission(execution_id)

    async def _scenario():
        first = await manager.reserve_event_execution(
            "wf_events",
            {"receipt": "A"},
            execution_id=execution_id,
            identity=IDENTITY,
            admission=admission,
        )
        async with event_db() as session:
            await session.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(tenant_id="tenant-other")
            )
            await session.commit()

        with pytest.raises(ValueError, match="receipt"):
            await manager.reserve_event_execution(
                "wf_events",
                {"receipt": "B"},
                execution_id=execution_id,
                identity=IDENTITY,
                admission=admission,
            )
        return first, await _fetch_all(event_db)

    first, rows = asyncio.run(_scenario())

    assert first[1] is True
    assert len(rows) == 1
    assert _json_value(rows[0].input_data)["receipt"] == "A"
