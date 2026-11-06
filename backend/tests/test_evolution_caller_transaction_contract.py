"""Caller transaction ownership for the parallel sandbox writer.

The sandbox result CAS owns only its own session. A caller's unrelated pending
or already-flushed edit must survive a skipped/deferred result and must not be
committed before the caller chooses to commit.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy import update

from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
from core.auto_dev.models import ToolMutation
from core.models import User
from tests.test_evolution_review_tool_mutations import env  # noqa: F401


def _engine(env, callback):
    db = env.Session()
    return db, AlphaEvolverEngine(
        db=db, sandbox=SimpleNamespace(execute_raw_python=callback))


def _run(engine, mutation_id="m-pending", tenant_id="tenant-1"):
    return asyncio.run(engine.sandbox_execute_mutation(
        mutation_id, tenant_id, {}))


def _first_name(env):
    db = env.Session()
    try:
        return db.query(User).filter(User.id == "lead-1").one().first_name
    finally:
        db.close()


def _mutation_status(env, mutation_id="m-pending"):
    db = env.Session()
    try:
        row = db.query(ToolMutation).filter(
            ToolMutation.id == mutation_id).one()
        return row.sandbox_status
    finally:
        db.close()


def _reject_pending(env):
    db = env.Session()
    try:
        db.execute(update(ToolMutation).where(
            ToolMutation.id == "m-pending").values(
                sandbox_status="rejected"))
        db.commit()
    finally:
        db.close()


def test_dirty_caller_edit_survives_losing_result_cas(env):
    calls = []
    db, engine = _engine(env, _peer_reject_then_succeed(env, calls))
    try:
        caller = db.query(User).filter(User.id == "lead-1").one()
        caller.first_name = "CallerPendingEdit"
        assert caller in db.dirty
        result = _run(engine)
        assert result.get("skipped"), result
        assert len(calls) == 1
        assert _mutation_status(env) == "rejected"
        assert _first_name(env) == "Lead"
        db.commit()
    finally:
        db.close()
    assert _first_name(env) == "CallerPendingEdit"
    assert _mutation_status(env) == "rejected"


def test_flushed_caller_edit_survives_pre_dispatch_skip(env):
    calls = []
    _reject_pending(env)
    db, engine = _engine(env, _never_call(calls))
    try:
        caller = db.query(User).filter(User.id == "lead-1").one()
        caller.first_name = "CallerFlushedEdit"
        db.flush()
        assert not db.dirty and not db.new and not db.deleted
        result = _run(engine)
        assert result.get("skipped") and calls == []
        assert _first_name(env) == "Lead"
        db.commit()
    finally:
        db.close()
    assert _first_name(env) == "CallerFlushedEdit"
    assert _mutation_status(env) == "rejected"


def test_dirty_caller_edit_is_not_committed_before_caller_commit(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "ok", "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        caller = db.query(User).filter(User.id == "lead-1").one()
        caller.first_name = "CallerPendingEdit"
        result = _run(engine)
        assert result["status"] == "passed" and not result["skipped"]
        # The sandbox result is committed on its own session; the caller edit
        # is still uncommitted.
        assert _mutation_status(env) == "passed"
        assert _first_name(env) == "Lead"
        db.commit()
    finally:
        db.close()
    assert _first_name(env) == "CallerPendingEdit"


def test_new_caller_object_is_not_lost_on_skipped_result(env):
    _reject_pending(env)
    db, engine = _engine(env, _never_call([]))
    try:
        new_mutation = ToolMutation(
            id="caller-new", tenant_id="tenant-1", tool_name="new.tool",
            mutated_code="x = 1", sandbox_status="pending")
        db.add(new_mutation)
        result = _run(engine)
        assert result.get("skipped")
        assert new_mutation in db.new
        db.commit()
    finally:
        db.close()
    assert _mutation_status(env, "caller-new") == "pending"


def test_deleted_caller_object_is_not_lost_on_skipped_result(env):
    env.add_mutation("caller-delete")
    _reject_pending(env)
    db, engine = _engine(env, _never_call([]))
    try:
        doomed = db.query(ToolMutation).filter(
            ToolMutation.id == "caller-delete").one()
        db.delete(doomed)
        result = _run(engine)
        assert result.get("skipped")
        db.commit()
    finally:
        db.close()
    db = env.Session()
    try:
        assert db.query(ToolMutation).filter(
            ToolMutation.id == "caller-delete").first() is None
    finally:
        db.close()


def test_clean_caller_with_read_transaction_still_executes(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "ok", "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        held = db.query(ToolMutation).filter(
            ToolMutation.id == "m-pending").one()
        assert held.sandbox_status == "pending"
        result = _run(engine)
        assert len(calls) == 1
        assert result["status"] == "passed" and not result["skipped"]
    finally:
        db.close()
    assert _mutation_status(env) == "passed"


def test_flushed_caller_with_pending_mutation_is_deferred(env):
    calls = []
    db, engine = _engine(env, _never_call(calls))
    try:
        caller = db.query(User).filter(User.id == "lead-1").one()
        caller.first_name = "CallerFlushedEdit"
        db.flush()
        result = _run(engine)
        assert result.get("skipped"), result
        assert result["reason"] == "caller_transaction_pending"
        assert calls == []
        assert _mutation_status(env) == "pending"
        db.commit()
    finally:
        db.close()
    assert _first_name(env) == "CallerFlushedEdit"
    assert _mutation_status(env) == "pending"


def _never_call(calls):
    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "unexpected"}
    return run


def _peer_reject_then_succeed(env, calls):
    async def run(**kwargs):
        calls.append(kwargs)
        _reject_pending(env)
        return {"status": "success", "output": "controlled",
                "execution_time": 0.01}
    return run
