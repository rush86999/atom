"""Parallel sandbox writer contracts for tool-mutation review.

The review decision is durable. A sandbox result may only advance the exact
material snapshot it executed; a stale caller session must not dispatch code
after a review already committed, and a review arriving while the worker runs
wins the result CAS.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
from core.auto_dev.models import ToolMutation
from tests.test_evolution_review_tool_mutations import env  # noqa: F401


def _snapshot(env, mutation_id):
    db = env.Session()
    try:
        row = db.query(ToolMutation).filter(
            ToolMutation.id == mutation_id).one()
        return {
            "status": row.sandbox_status,
            "parent": row.parent_tool_id,
            "error": row.execution_error,
            "code": row.mutated_code,
        }
    finally:
        db.close()


def _engine(env, callback):
    db = env.Session()
    return db, AlphaEvolverEngine(
        db=db, sandbox=SimpleNamespace(execute_raw_python=callback))


def _run(engine, mutation_id="m-pending", tenant_id="tenant-1"):
    return asyncio.run(engine.sandbox_execute_mutation(
        mutation_id, tenant_id, {}))


def test_pending_twin_executes_once_and_passes(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "ok", "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine)
    finally:
        db.close()
    assert len(calls) == 1
    assert result["status"] == "passed" and not result["skipped"]
    state = _snapshot(env, "m-pending")
    assert state["status"] == "passed"
    assert state["parent"] is None
    assert state["error"] is None


def test_failed_twin_executes_once_and_passes(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "ok", "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine, "m-failed")
    finally:
        db.close()
    assert len(calls) == 1
    assert result["status"] == "passed" and not result["skipped"]
    state = _snapshot(env, "m-failed")
    assert state["status"] == "passed"
    assert state["error"] is None


def test_changed_lineage_during_worker_is_skipped(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        with env.Session() as peer:
            peer.execute(update(ToolMutation).where(
                ToolMutation.id == "m-pending").values(
                    parent_tool_id="new-parent-generation"))
            peer.commit()
        return {"status": "success", "output": "controlled",
                "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine)
    finally:
        db.close()
    assert len(calls) == 1
    assert result["skipped"] is True
    assert result["reason"] == "stale_mutation"
    state = _snapshot(env, "m-pending")
    assert state["parent"] == "new-parent-generation"
    assert state["status"] == "pending"


def test_unchanged_null_lineage_twin_passes(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "ok", "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine)
    finally:
        db.close()
    assert len(calls) == 1
    assert result["status"] == "passed"
    state = _snapshot(env, "m-pending")
    assert state["parent"] is None and state["status"] == "passed"


def test_changed_code_during_worker_is_skipped(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        with env.Session() as peer:
            peer.execute(update(ToolMutation).where(
                ToolMutation.id == "m-pending").values(
                    mutated_code="def run():\n    return 'peer'\n"))
            peer.commit()
        return {"status": "success", "output": "controlled",
                "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine)
    finally:
        db.close()
    assert len(calls) == 1
    assert result["skipped"] is True
    state = _snapshot(env, "m-pending")
    assert "peer" in state["code"]
    assert state["status"] == "pending"


def test_changed_prior_error_during_worker_is_skipped(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        with env.Session() as peer:
            peer.execute(update(ToolMutation).where(
                ToolMutation.id == "m-failed").values(
                    execution_error="peer-error"))
            peer.commit()
        return {"status": "success", "output": "controlled",
                "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine, "m-failed")
    finally:
        db.close()
    assert len(calls) == 1
    assert result["skipped"] is True
    state = _snapshot(env, "m-failed")
    assert state["error"] == "peer-error"
    assert state["status"] == "failed"


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_stale_session_reloads_review_before_dispatch(env, decision):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "controlled",
                "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        held = db.query(ToolMutation).filter_by(id="m-pending").one()
        assert held.sandbox_status == "pending"
        with env.Session() as peer:
            peer.execute(update(ToolMutation).where(
                ToolMutation.id == "m-pending").values(
                    sandbox_status=decision))
            peer.commit()
        result = _run(engine)
    finally:
        db.close()
    assert calls == []
    assert result["skipped"] is True
    assert result["reason"] == "review_decision_present"
    assert _snapshot(env, "m-pending")["status"] == decision


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_reviewer_during_worker_wins_result_cas(env, decision):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        with env.Session() as peer:
            peer.execute(update(ToolMutation).where(
                ToolMutation.id == "m-pending").values(
                    sandbox_status=decision))
            peer.commit()
        return {"status": "success", "output": "controlled",
                "execution_time": 0.01}

    db, engine = _engine(env, run)
    try:
        result = _run(engine)
    finally:
        db.close()
    assert len(calls) == 1
    assert result["skipped"] is True
    assert result["reason"] == "review_decision_present"
    state = _snapshot(env, "m-pending")
    assert state["status"] == decision
    assert state["parent"] is None
    assert state["error"] is None


def test_missing_or_foreign_target_does_not_dispatch(env):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "output": "controlled"}

    db, engine = _engine(env, run)
    try:
        missing = _run(engine, "missing")
        foreign = _run(engine, "m-foreign", "tenant-1")
    finally:
        db.close()
    assert calls == []
    assert "error" in missing
    assert "error" in foreign
