"""MCP / cross-caller replay controls for ``radio.create_thread``.

These exercise the normal MCP -> action registry -> producer path, which has no
Generic-only claim wrapper, plus cross-caller and concurrent replay boundaries.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import AgentThread
from tests.test_oracle_radio_create_thread import (
    _agent,
    _args,
    _call,
    _context,
    _one_thread,
    _set_creator_state,
    _threads,
    env,  # noqa: F401 - pytest fixture
)


def _mcp_call(args, context):
    from integrations.mcp_service import MCPService

    return asyncio.run(MCPService(tenant_id="tenant-1").call_tool(
        "radio.create_thread", args, context=context))


def _patch_threadsafe_sessions(monkeypatch, path):
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextlib.contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr("core.database.get_db_session", _session)
    return Session


# ---------------------------------------------------------------------------
# Operation identity
# ---------------------------------------------------------------------------


def test_mcp_missing_operation_gets_server_identity_and_persists(env):
    result = _mcp_call(_args(""), _context(""))

    assert result["success"] is True, result
    operation = str(result.get("operation_id") or "")
    assert operation, result
    assert result.get("operation_source") == "server_generated", result
    row = _one_thread(env)
    assert (row.metadata_json or {}).get("operation_id") == operation
    assert (row.metadata_json or {}).get("operation_source") == "server_generated"


def test_caller_arg_operation_cannot_override_context_identity(env):
    context_op = f"ctx-{uuid.uuid4().hex}"
    arg_op = f"arg-{uuid.uuid4().hex}"
    first = _mcp_call(_args(arg_op), _context(context_op))

    assert first["success"] is True, first
    assert first["operation_id"] == context_op, first
    row = _one_thread(env)
    assert (row.metadata_json or {}).get("operation_id") == context_op

    second = _mcp_call(_args(f"other-{uuid.uuid4().hex}"), _context(context_op))
    assert second["success"] is True, second
    assert second["remote_id"] == first["remote_id"], second
    assert len(_threads(env)) == 1


def test_distinct_operations_create_distinct_threads(env):
    op1 = f"op-{uuid.uuid4().hex}"
    op2 = f"op-{uuid.uuid4().hex}"
    first = _mcp_call(_args(op1), _context(op1))
    second = _mcp_call(_args(op2), _context(op2))

    assert first["success"] is True and second["success"] is True
    assert first["remote_id"] != second["remote_id"]
    assert len(_threads(env)) == 2


# ---------------------------------------------------------------------------
# Cross-caller replay
# ---------------------------------------------------------------------------


def test_generic_then_mcp_replays_exact_thread(env):
    operation = f"cross-gm-{uuid.uuid4().hex}"
    first = _call(_agent(), _args(operation), _context(operation))
    second = _mcp_call(_args(operation), _context(operation))

    assert first["success"] is True, first
    assert second["success"] is True, second
    assert second["remote_id"] == first["remote_id"], second
    assert len(_threads(env)) == 1


def test_mcp_then_generic_replays_exact_thread(env):
    operation = f"cross-mg-{uuid.uuid4().hex}"
    first = _mcp_call(_args(operation), _context(operation))
    second = _call(_agent(), _args(operation), _context(operation))

    assert first["success"] is True, first
    assert second["success"] is True, second
    assert second["remote_id"] == first["remote_id"], second
    assert len(_threads(env)) == 1


# ---------------------------------------------------------------------------
# Authority loss / ambiguous rows / readback uncertainty
# ---------------------------------------------------------------------------


def test_assignment_adapter_same_operation_replays_exact_thread(env):
    from core.assignment_executor import _action_registry_adapter

    operation = f"assignment-{uuid.uuid4().hex}"
    args = _args(operation)
    context = {
        "workspace_id": "ws-1",
        "tenant_id": "tenant-1",
        "agent_id": "agent-a",
        "employee_id": "user-radio",
        "operation_id": operation,
        "tier": "autonomous",
    }
    with env["Session"]() as db:
        context["db"] = db
        first = asyncio.run(_action_registry_adapter(
            {"action": "radio.create_thread", "arguments": args}, context))
        second = asyncio.run(_action_registry_adapter(
            {"action": "radio.create_thread", "arguments": args}, context))

    assert first["status"] == "applied", first
    assert second["status"] == "applied", second
    assert second["remote_id"] == first["remote_id"], second
    assert len(_threads(env)) == 1


def test_mcp_authority_loss_on_replay_refuses_with_original_identity(env):
    operation = f"auth-loss-{uuid.uuid4().hex}"
    first = _mcp_call(_args(operation), _context(operation))
    assert first["success"] is True, first

    _set_creator_state(env, "agent-b", enabled=False)
    replay = _mcp_call(_args(operation), _context(operation))

    assert replay["success"] is False, replay
    assert replay["action_result"] == "proven_not_applied", replay
    assert replay["effect_possible"] is False, replay
    assert replay["original_thread_id"] == first["remote_id"], replay
    assert replay["original_effect_state"] == "committed_unverified", replay
    assert len(_threads(env)) == 1


def test_mcp_ambiguous_historical_rows_fail_closed_without_new_write(env):
    operation = f"ambiguous-{uuid.uuid4().hex}"
    first = _mcp_call(_args(operation), _context(operation))
    assert first["success"] is True, first

    with env["Session"]() as db:
        original = db.query(AgentThread).filter(
            AgentThread.id == first["remote_id"]).one()
        db.add(AgentThread(
            id=f"duplicate-{uuid.uuid4().hex}",
            name=original.name,
            created_by_agent_id=original.created_by_agent_id,
            member_agent_ids=list(original.member_agent_ids or []),
            tenant_id=original.tenant_id,
            status="open",
            metadata_json=dict(original.metadata_json or {}),
        ))
        db.commit()

    replay = _mcp_call(_args(operation), _context(operation))
    assert replay["success"] is False, replay
    assert replay["action_result"] == "proven_not_applied", replay
    assert replay["effect_possible"] is False, replay
    assert replay["original_thread_count"] == 2, replay
    assert len(_threads(env)) == 2


def test_mcp_readback_row_absent_is_uncertain_then_reconciles(env, monkeypatch):
    import core.agent_radio.radio_thread_mutations as mutations

    operation = f"readback-absent-{uuid.uuid4().hex}"
    original_read = mutations.read_thread
    armed = [True]

    def absent_once(*args, **kwargs):
        if armed[0]:
            armed[0] = False
            return None
        return original_read(*args, **kwargs)

    monkeypatch.setattr(mutations, "read_thread", absent_once)
    first = _mcp_call(_args(operation), _context(operation))

    assert first["success"] is False, first
    assert first["action_result"] == "uncertain", first
    assert first["operation_id"] == operation, first
    assert first["remote_id"], first
    assert len(_threads(env)) == 1

    second = _mcp_call(_args(operation), _context(operation))
    assert second["success"] is True, second
    assert second["remote_id"] == first["remote_id"], second
    assert len(_threads(env)) == 1


# ---------------------------------------------------------------------------
# Concurrent same-key writers
# ---------------------------------------------------------------------------


def _run_concurrently(workers):
    barrier = threading.Barrier(len(workers))

    def _run(fn):
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        return list(pool.map(_run, workers))


def test_concurrent_same_operation_same_material_one_thread(env, monkeypatch):
    _patch_threadsafe_sessions(monkeypatch, env["path"])
    operation = f"concurrent-same-{uuid.uuid4().hex}"

    def worker():
        return _mcp_call(_args(operation), _context(operation))

    results = _run_concurrently([worker, worker])
    rows = _threads(env)
    assert len(rows) == 1, (results, rows)
    assert all(item["success"] is True for item in results), results
    assert {item["remote_id"] for item in results} == {rows[0].id}


def test_concurrent_same_operation_changed_material_one_winner(env, monkeypatch):
    _patch_threadsafe_sessions(monkeypatch, env["path"])
    operation = f"concurrent-changed-{uuid.uuid4().hex}"

    def worker(name):
        return lambda: _mcp_call(
            _args(operation, name=name), _context(operation))

    results = _run_concurrently([worker("alpha"), worker("beta")])
    rows = _threads(env)
    assert len(rows) == 1, (results, rows)
    winners = [item for item in results if item.get("success") is True]
    losers = [item for item in results if item.get("success") is False]
    assert len(winners) == 1 and len(losers) == 1, results
    assert winners[0]["remote_id"] == rows[0].id
    assert losers[0]["original_thread_id"] == rows[0].id
    assert rows[0].name in {"alpha", "beta"}
