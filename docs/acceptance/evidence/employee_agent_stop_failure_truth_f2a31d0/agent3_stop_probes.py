"""Agent 3 independent probes for merged #695 agent stop/cancel.

Independent review of owner-merged #695 (code ``1faccf71c``, merge
``e93982eec``, executed source bound by the
``employee_agent_stop_1faccf71c`` bundle) at current main. Adds only the
cases the submitted 9 controls do not cover:

1. the ``enabled`` sibling of the exact-material claim: a peer flipping
   ``enabled`` between load and the guarded claim must refuse with
   STALE_TARGET and preserve the peer's values (the submitted suite
   covers a ``configuration`` change);
2. a competing stop with a DIFFERENT operation id after a successful stop
   finds no tasks and is a no-change without a second receipt or audit —
   zero losing receipts for the same effect;
3. the receipt-failure 503 (effect unknown) still truthfully reports the
   cancellation that DID happen: the response carries the cancelled task
   count.

Reuses the submitted suite's environment fixture unchanged.
"""
from __future__ import annotations

import pytest
from sqlalchemy import update

from core.models import AgentRegistry

from tests.test_agent_stop_scope_contract import env as _env

env = _env


def _audits(env, operation_id=None):
    from core.models import AuditLog

    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _stop(env, user_id, agent_id, operation_id=None):
    suffix = f"?operation_id={operation_id}" if operation_id else ""
    return env.client(env.actors[user_id]).post(
        f"/api/agents/{agent_id}/stop{suffix}")


def test_enabled_change_before_claim_refuses(env):
    """Peer flips enabled between load and the guarded claim."""
    import core.agent_decision_write_service as service

    original = service._load_agent
    changed = {"done": False}

    def load_then_change(db, agent_id):
        row = original(db, agent_id)
        if row is not None and agent_id == "a1" and not changed["done"]:
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(AgentRegistry).where(
                    AgentRegistry.id == "a1").values(enabled=False))
                peer.commit()
            finally:
                peer.close()
        return row

    env.monkeypatch.setattr(service, "_load_agent", load_then_change)
    response = _stop(env, "admin-1", "a1", "agent3-stale-enabled")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_TARGET"
    now = env.Session().query(AgentRegistry).filter(
        AgentRegistry.id == "a1").first()
    assert now.enabled is False
    assert env.fake.cancel_calls == []
    assert _audits(env) == []


def test_competing_new_operation_stop_after_success_is_no_change(env):
    """A different-operation stop after a successful stop finds no tasks:
    200 no-change, no second receipt/audit, no extra cancel call — zero
    losing receipts for the same effect."""
    first = _stop(env, "admin-1", "a1", "agent3-first-stop")
    assert first.status_code == 200, first.text
    assert first.json()["data"]["cancelled_tasks"] == 2
    assert first.json()["data"]["verification"]["status"] == "verified"

    second = _stop(env, "admin-1", "a1", "agent3-second-stop")
    assert second.status_code == 200, second.text
    assert second.json()["data"]["cancelled_tasks"] == 0
    assert second.json()["data"]["verification"]["status"] == "no_change"
    # The no-task gate short-circuits before the cancel call: the first
    # stop's cancel is the only registry invocation.
    assert env.fake.cancel_calls == ["a1"]
    assert len(_audits(env, "agent:stop:agent3-first-stop")) == 1
    assert _audits(env, "agent:stop:agent3-second-stop") == []


def test_receipt_failure_response_still_reports_cancelled_count(env):
    """When the receipt commit fails after cancellation, the 503
    effect-unknown response should truthfully report the cancellation that
    DID happen, including the cancelled task count.

    The service envelope attaches ``data.cancelled_tasks`` (the stop path
    sets it after cancellation), but the route's effect_unknown projection
    currently drops ``result["data"]`` from the HTTPException detail — so
    this assertion FAILS on the merged source. This is the executable
    counterexample for the bounded consumer gap: Agent 2's one-line repair
    is projecting ``result.get("data")`` in the
    committed_unverified/effect_unknown branch of
    ``_raise_agent_decision``. Ownership: Agent 2."""
    import core.agent_decision_write_service as service

    original = service._audit_row

    def broken_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    env.monkeypatch.setattr(service, "_audit_row", broken_audit)
    response = _stop(env, "admin-1", "a1", "agent3-unknown-count")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "AGENT_EFFECT_UNKNOWN"
    assert detail["verification"]["effect"] == "unknown"
    # Consumer projection under test (currently dropped by the route):
    assert detail.get("data", {}).get("cancelled_tasks") == 2
    assert detail.get("data", {}).get("agent_id") == "a1"
    assert env.fake.cancel_calls == ["a1"]
    assert _audits(env) == []
