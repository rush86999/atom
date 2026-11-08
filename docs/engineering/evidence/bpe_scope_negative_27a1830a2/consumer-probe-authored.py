#!/usr/bin/env python3
"""AUTHOR-ONLY bounded probe for registered ``workspace.note`` — DO NOT RUN here.

Status: AUTHOR-ONLY-NOTRUN. No product code, pytest, server, model, or
provider was executed. The only local Python invocation was a `json.load`
parse-check of the private source-bindings file; no repo/product module was
imported. Root's first gated execution is the proof.

Failure-first intent
--------------------
On current main ``workspace.note`` is a declared local mutation with no
postcondition verifier. The real Generic consumer therefore rewrites a landed
note to ``status=uncertain``, marks the durable claim ``uncertain_effect``, and
the episode close-out *drops* the pending note. The desired controls below
encode the minimum invariant regardless of the repair root chooses:

* a note that really landed must not force the run to ``uncertain`` and must
  still reach Experience consolidation;
* an empty note must remain a proven pre-effect refusal, not ``uncertain``.

The remaining controls are valid twins / current-state evidence: registered
name and required argument, read-only twin, exact material transform, session
scope precedence, and the real durable store round-trip. Controls that assert
the *current defect itself* (absent verifier, uncertain claim, shared default
scope) are pre-fix diagnostics and are skipped unless
``ATOM_PROBE_PRE_FIX_EVIDENCE=1``; the default suite is the post-fix gate.

Scope / seams
-------------
* Real ``core.bpe.actions`` registration + real ``core.action_registry``.
* Real ``GenericAgent._step_act_unaudited`` with ``pre_approved=True``. This
  deliberately isolates the outcome consumer; governance/HITL is out of scope
  (same boundary as ``tests/test_generic_oracle_mutation_contract.py``).
* Real scratch SQLite ``task_operation_records`` claim store. The DB is created
  with the real ORM metadata in a pytest ``tmp_path``; one seeded Tenant and
  Workspace keep optional FK enforcement valid. No hardcoded port/DB/workspace.
* Real ``BPEWorkspace``, real consolidation and real ``BPEWorkspaceStore`` with
  a fresh ``tmp_path`` data root. Only the DB-session seam and the BPE
  data-directory root are rebound; durability and readback are not faked.
* No live model/server/browser/account/credential/provider/HTTP call.

Run (root only, NOT RUN by the author): see the workorder's exact command.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generic_agent as ga
from core.action_effects import declares_mutation
from core.action_registry import action_registry
from core.bpe import actions as bpe_actions  # noqa: F401 - registers workspace.*
from core.bpe import consolidation as bpe_consolidation
from core.bpe import persistence as bpe_persistence
from core.bpe import workspace as bpe_workspace
from core.bpe.persistence import BPEWorkspaceStore
from core.generic_agent import GenericAgent
from core.oracle import get_postcondition

NOTE = "workspace.note"
WS = "ws-note-readonly"
AGENT = "agent-note-readonly"
SESSION = "sess-note-readonly"
EXECUTION = "exec-note-readonly"
TENANT = "tenant-note-readonly"
ACTOR = "user-note-readonly"

# Pre-fix evidence controls assert the current defect itself (uncertain claim,
# absent verifier, shared default scope, accepted unseeded workspace). They are
# diagnostics, not post-fix gate assertions: run them explicitly with
# ATOM_PROBE_PRE_FIX_EVIDENCE=1. The default suite is the failure-first gate
# plus valid twins that must pass before and after the repair.
pre_fix_only = pytest.mark.skipif(
    os.getenv("ATOM_PROBE_PRE_FIX_EVIDENCE") != "1",
    reason="pre-fix evidence only; run with ATOM_PROBE_PRE_FIX_EVIDENCE=1")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_bpe_and_oracle_env(monkeypatch):
    monkeypatch.setenv("ATOM_BPE_WORKSPACE_ENABLED", "true")
    monkeypatch.setenv("ATOM_ORACLE_ENFORCE", "true")
    monkeypatch.setenv("ATOM_ORACLE_VERIFIER_ENABLED", "true")
    bpe_workspace.reset_registry()
    try:
        yield
    finally:
        bpe_workspace.reset_registry()


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """Fresh real SQLite system of record for the claim + Oracle seams."""
    from core.models import Tenant, Workspace
    from core.models_registration import Base
    import core.models  # noqa: F401 - registers every table on Base

    db_path = tmp_path / "note_system_of_record.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    # Bind the exact seam the Generic claim + Oracle readback use. The
    # underlying files are the real scratch DB, not a stubbed verdict.
    monkeypatch.setattr(ga, "get_db_session", _session)
    import core.database as core_database
    monkeypatch.setattr(core_database, "get_db_session", _session)

    # Seed a real tenant/workspace so optional FK enforcement cannot make the
    # fixture invalid. The BPE namespace itself is still a plain string key.
    with Session() as db:
        db.add(Tenant(
            id=TENANT,
            name="Note probe tenant",
            subdomain="note-probe-scratch",
            plan_type="free",
            edition="personal",
        ))
        db.commit()
    with Session() as db:
        db.add(Workspace(id=WS, name="Note probe workspace", tenant_id=TENANT))
        db.commit()

    return {"path": str(db_path), "engine": engine, "Session": Session}


@pytest.fixture
def bpe_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "bpe_workspaces"
    # DATA_DIR is read by BPEWorkspaceStore.__init__ at call time. Rebinding
    # the module root is isolation, not a fake persistence/readback verdict.
    monkeypatch.setattr(bpe_persistence, "DATA_DIR", data_dir)
    return data_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent():
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = AGENT
    agent.workspace_id = WS
    agent.tenant_id = TENANT
    agent._custom_actions = {}

    async def registry_leaf(tool_name, arguments, context=None):
        return await action_registry.execute_action(
            tool_name, arguments, context or {})

    agent.mcp = SimpleNamespace(call_tool=registry_leaf)
    return agent


def _context(operation_id=None, **overrides):
    ctx = {
        "operation_id": operation_id or f"op-note-{uuid.uuid4().hex}",
        "workspace_id": WS,
        "tenant_id": TENANT,
        "execution_id": EXECUTION,
        "session_id": SESSION,
        "user_id": ACTOR,
        "agent_id": AGENT,
    }
    ctx.update(overrides)
    return ctx


def _dispatch(content, context):
    return asyncio.run(_agent()._step_act_unaudited(
        NOTE, {"content": content}, context=context, pre_approved=True))


def _snapshot():
    return bpe_workspace.get_workspace_snapshot(WS, AGENT, SESSION)


def _claim_row(db_path, operation_id):
    with sqlite3.connect(db_path) as raw:
        return raw.execute(
            "select status from task_operation_records "
            "where operation_id = ?", (operation_id,)).fetchone()


# ---------------------------------------------------------------------------
# Failure-first controls (expected to FAIL on current main)
# ---------------------------------------------------------------------------

def test_landed_note_must_not_force_uncertain_or_drop_the_note(scratch):
    """Primary failure-first control.

    A note that really landed in the exact scope must remain a usable success
    and must reach Experience consolidation. Current main returns uncertain,
    the claim becomes uncertain_effect, and the close-out drains/drops it.
    """
    content = "checkout retry needs an idempotency key"
    context = _context(f"op-note-desired-{uuid.uuid4().hex}")
    result = _dispatch(content, context)

    snapshot = _snapshot()
    assert snapshot is not None, "the handler did not create the scoped workspace"
    assert snapshot["pending_notes"] == [content], (
        "the note did not land exactly once in the expected scope")

    assert result.get("success") is True, result
    assert result.get("requires_reconciliation") is not True, result
    assert str(result.get("status") or "success").lower() != "uncertain", result
    assert not context.get("_uncertain_operations"), context

    # Mirror the real episode close-out branch in generic_agent.py:934-941.
    run_status = str(result.get("status") or "success")
    success = run_status in {"success", "objective_satisfied"}
    ws = bpe_workspace.get_workspace(WS, AGENT, SESSION)
    if success:
        report = bpe_consolidation.consolidate_workspace_notes(ws)
    else:
        report = {"dropped_notes": len(ws.drain_pending_notes())}

    assert report.get("skills") == 1, report
    assert ws.experience.to_dict()["skills"][0]["content"] == content
    assert _snapshot()["pending_notes"] == []


def test_empty_note_is_a_pre_effect_refusal(scratch):
    """A handler refusal before any append must stay a proven no-effect."""
    context = _context(f"op-note-empty-{uuid.uuid4().hex}")
    result = _dispatch("   ", context)

    snapshot = _snapshot()
    assert snapshot is None or snapshot["pending_notes"] == []
    assert result.get("success") is False, result
    assert str(result.get("status") or "").lower() != "uncertain", result
    assert result.get("requires_reconciliation") is not True, result
    assert not context.get("_uncertain_operations"), context


# ---------------------------------------------------------------------------
# Current-state evidence and valid twins (expected to PASS on current main)
# ---------------------------------------------------------------------------

def test_registered_name_and_declaration_shape():
    action = action_registry.get_action(NOTE)
    assert action is not None, "core.bpe.actions did not register workspace.note"
    assert action.name == NOTE
    assert action.parameters_schema["required"] == ["content"]
    assert any(
        str(entry.get("scope") or "").lower() == "local"
        for entry in action.effects
    ), action.effects


@pre_fix_only
def test_current_declaration_has_no_postcondition_verifier():
    action = action_registry.get_action(NOTE)
    assert action is not None
    assert action.effects == [{"effect": "create", "scope": "local"}]
    assert declares_mutation(action) is True
    assert get_postcondition(NOTE) is None


@pre_fix_only
def test_current_consumer_lands_note_but_reports_uncertain(scratch):
    """Current-state evidence for the exact bug path (expected PASS now)."""
    content = "current main will drop this landed note"
    operation_id = f"op-note-current-{uuid.uuid4().hex}"
    context = _context(operation_id)
    result = _dispatch(content, context)

    assert _snapshot()["pending_notes"] == [content]
    assert result["success"] is False
    assert result["status"] == "uncertain"
    assert result["action_result"] == "uncertain"
    assert result["business_success"] is False
    assert result["requires_reconciliation"] is True
    assert result["retryable"] is False
    assert "no registered postcondition verifier" in result["oracle_evidence"]
    assert _claim_row(scratch["path"], operation_id)[0] == "uncertain_effect"
    assert any(
        entry.get("tool") == NOTE
        for entry in context.get("_uncertain_operations", []))


def test_read_twin_track_stays_usable(scratch):
    """An explicitly read-only sibling is not caught by the mutation gate."""
    # Use the production NullAdapter fallback so the read twin stays bounded
    # and does not touch GraphRAG/DB belief stores. This does not affect the
    # mutation gate under test.
    from core.bpe.adapter import NullAdapter

    bpe_workspace.get_workspace(WS, AGENT, SESSION).adapter = NullAdapter()
    operation_id = f"op-track-{uuid.uuid4().hex}"
    result = asyncio.run(_agent()._step_act_unaudited(
        "workspace.track", {"topic": "world"},
        context=_context(operation_id), pre_approved=True))

    assert result["success"] is True, result
    assert result.get("requires_reconciliation") is not True, result
    assert _claim_row(scratch["path"], operation_id) is None


def test_note_material_is_stripped_and_truncated_to_400():
    """The exact material transform any future verifier must reproduce."""
    content = "  " + ("a" * 450) + "  "
    result = asyncio.run(action_registry.execute_action(
        NOTE, {"content": content}, _context()))

    assert result["success"] is True, result
    assert result["buffered"] == 1, result
    assert _snapshot()["pending_notes"] == ["a" * 400]


def test_session_scope_wins_over_execution_scope():
    """The handler's scope precedence is exact: session first, then execution."""
    content = "session scoped insight"
    context = _context(
        session_id="sess-precedence", execution_id="exec-precedence")
    result = asyncio.run(action_registry.execute_action(
        NOTE, {"content": content}, context))

    assert result["success"] is True
    assert bpe_workspace.get_workspace_snapshot(
        WS, AGENT, "sess-precedence")["pending_notes"] == [content]
    assert bpe_workspace.get_workspace_snapshot(
        WS, AGENT, "exec-precedence") is None


@pre_fix_only
def test_duplicate_content_has_no_per_effect_identity():
    """Presence in the buffer cannot prove a *new* append.

    The producer returns only a buffer count. A presence-only verifier would
    pass on a pre-existing identical note; a replay appends a duplicate.
    """
    content = "same insight"
    first = asyncio.run(action_registry.execute_action(
        NOTE, {"content": content}, _context()))
    second = asyncio.run(action_registry.execute_action(
        NOTE, {"content": content}, _context()))

    assert first == {"success": True, "buffered": 1}
    assert second == {"success": True, "buffered": 2}
    assert _snapshot()["pending_notes"] == [content, content]
    for result in (first, second):
        assert not ({"note_id", "id", "remote_id", "payload_sha256"}
                    & set(result))


@pre_fix_only
def test_rpc_like_default_scope_is_shared_across_users(scratch):
    """The exact RPC context has no workspace/agent/session/tenant.

    ``rpc_routes.py:92-97`` passes only ``user``/``user_id``/``db`` and calls
    the registry directly. Every authenticated user therefore shares
    ``("default", "atom_main", "")``; no Workspace row or role check is used.
    """
    first = asyncio.run(action_registry.execute_action(
        NOTE, {"content": "note from user one"}, {"user_id": "user-one"}))
    second = asyncio.run(action_registry.execute_action(
        NOTE, {"content": "note from user two"}, {"user_id": "user-two"}))

    assert first["success"] is True
    assert second["success"] is True
    snapshot = bpe_workspace.get_workspace_snapshot("default", "atom_main", "")
    assert snapshot["pending_notes"] == [
        "note from user one", "note from user two"]

    from core.models import Workspace
    with scratch["Session"]() as db:
        assert db.query(Workspace).filter(
            Workspace.id == "default").first() is None


@pre_fix_only
def test_unseeded_workspace_and_foreign_tenant_are_accepted():
    """No FK/membership/tenant validation exists on the handler path."""
    context = {
        "workspace_id": "ws-no-such-row",
        "tenant_id": "tenant-foreign",
        "agent_id": AGENT,
        "session_id": "sess-unseeded",
    }
    result = asyncio.run(action_registry.execute_action(
        NOTE, {"content": "cross-scope insight"}, context))

    assert result == {"success": True, "buffered": 1}
    snapshot = bpe_workspace.get_workspace_snapshot(
        "ws-no-such-row", AGENT, "sess-unseeded")
    assert snapshot["pending_notes"] == ["cross-scope insight"]


def test_durable_store_round_trip_is_scope_keyed(bpe_data_dir):
    """The real durable readback primitive after a successful consolidation."""
    content = "durable note for readback"
    asyncio.run(action_registry.execute_action(
        NOTE, {"content": content}, _context()))

    ws = bpe_workspace.get_workspace(WS, AGENT, SESSION)
    report = bpe_consolidation.consolidate_workspace_notes(ws)
    assert report["skills"] == 1, report

    store = BPEWorkspaceStore()
    assert store.save(ws.to_dict()) is True

    path = bpe_data_dir / f"{WS}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = f"{AGENT}|{SESSION}"
    assert key in payload, sorted(payload)
    assert payload[key]["pending_notes"] == []
    assert payload[key]["experience"]["skills"][0]["content"] == content

    restored = store.load(WS, AGENT, SESSION)
    assert restored["experience"]["skills"][0]["content"] == content
