# -*- coding: utf-8 -*-
"""Durable authority for a pending specialist collaboration.

Contract under test (2026-11-17 root review):

* the DURABLE session-metadata record is authoritative; an in-memory cached
  pending may not override a durable clear/cancel/supersession;
* a read failure is reported as ``unavailable`` and is never treated as
  absence or as permission to resume the cached copy;
* a pending write is published to the cache only after the store confirms the
  commit; a missing manager/exception/False is reported honestly as
  not-saved, and never claims ``request_preserved``;
* resume is scoped to the current actor/workspace/tenant/session and the
  stored request material digest;
* concurrent/stale approvals transition one durable record at a time and a
  completed receipt prevents a duplicate dispatch even if the metadata clear
  failed.

The tests use real scratch ``ChatSession`` rows plus FRESH manager/orchestrator
instances to simulate a cold process.  Only external authorisation/execution
is doubled; the durable helper and its CAS are exercised for real.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager

# Isolation MUST precede core imports (owner rule). Absolute scratch paths,
# never the dev DB or a shared world. The previous values are restored right
# after our imports so a later test module that reads DATABASE_URL/ATOM_DATA_DIR
# does not inherit this file's scratch target.
os.environ["TESTING"] = "1"
_PREV_DATABASE_URL = os.environ.get("DATABASE_URL")
_PREV_ATOM_DATA_DIR = os.environ.get("ATOM_DATA_DIR")
_SCRATCH_ROOT = tempfile.mkdtemp(prefix="atom-collab-authority-")
os.environ["DATABASE_URL"] = (
    f"sqlite:///{os.path.join(_SCRATCH_ROOT, 'authority.db')}")
os.environ["ATOM_DATA_DIR"] = os.path.join(_SCRATCH_ROOT, "data")
os.makedirs(os.environ["ATOM_DATA_DIR"], exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.dialects import postgresql, sqlite  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.chat_session_manager as csm  # noqa: E402
import core.turn_decision as td  # noqa: E402
import integrations.chat_orchestrator as co  # noqa: E402
from core.agent_context_resolver import AgentContextResolver  # noqa: E402
from core.chat_session_manager import ChatSessionManager  # noqa: E402
from core.models import (  # noqa: E402
    AgentRegistry, Base, ChatSession, TaskOperationRecord,
)
from core.turn_decision import (  # noqa: E402
    apply_interpretation_actions,
    build_turn_decision,
)

if _PREV_DATABASE_URL is None:
    os.environ.pop("DATABASE_URL", None)
else:
    os.environ["DATABASE_URL"] = _PREV_DATABASE_URL
if _PREV_ATOM_DATA_DIR is None:
    os.environ.pop("ATOM_DATA_DIR", None)
else:
    os.environ["ATOM_DATA_DIR"] = _PREV_ATOM_DATA_DIR

# Re-anchor the module constants created while the scratch ATOM_DATA_DIR was
# active, so later test modules do not inherit this file's sessions path.
_RESTORED_SESSIONS_FILE = os.path.join(
    _PREV_ATOM_DATA_DIR
    or os.path.dirname(os.path.dirname(os.path.abspath(csm.__file__))),
    "chat_sessions.json")
csm.SESSIONS_FILE = _RESTORED_SESSIONS_FILE
try:
    csm.chat_session_manager.sessions_file = _RESTORED_SESSIONS_FILE
except Exception:  # noqa: BLE001 — best-effort test isolation
    pass

MESSAGE = (
    "Analyze these synthetic Q3 facts with finance and sales specialists: "
    "closed revenue USD100, remaining pipeline USD200, target USD250. "
    "Compare closed revenue with target, identify the gap, and explain that "
    "pipeline is not closed revenue."
)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_ID = "s-collab"
USER_ID = "u-collab"
TENANT_ID = "t-collab"
WORKSPACE_ID = "w-collab"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def scratch(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'authority.db'}",
        connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield engine, Session
    finally:
        engine.dispose()


@pytest.fixture()
def db_world(scratch):
    engine, Session = scratch
    with Session() as db:
        db.add(ChatSession(
            id=SESSION_ID,
            user_id=USER_ID,
            metadata_json={"keep_unrelated": "v1"},
        ))
        db.commit()
    return engine, Session


def _install_scratch_db(monkeypatch, Session):
    @contextmanager
    def _db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(csm, "DB_AVAILABLE", True)
    monkeypatch.setattr(csm, "SessionLocal", Session)
    monkeypatch.setattr(csm, "get_db_session", _db)
    monkeypatch.setattr("core.database.get_db_session", _db)
    monkeypatch.setattr("core.database.SessionLocal", Session)
    monkeypatch.delenv("ATOM_CHAT_STORAGE", raising=False)
    return _db


def _db_manager(monkeypatch, Session, tmp_path):
    _install_scratch_db(monkeypatch, Session)
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "HYBRID")
    manager = ChatSessionManager(
        sessions_file=str(tmp_path / "collab-sessions.json"))
    assert manager.use_db is True
    return manager


def _file_manager(monkeypatch, tmp_path, *, create=True):
    monkeypatch.setattr(csm, "DB_AVAILABLE", False)
    monkeypatch.setattr(csm, "SessionLocal", None)
    monkeypatch.setenv("ATOM_CHAT_STORAGE", "file")
    monkeypatch.setenv("CHAT_PERSISTENCE_MODE", "FILE")
    manager = ChatSessionManager(
        sessions_file=str(tmp_path / "collab-sessions.json"))
    assert manager.use_db is False
    if create:
        manager.create_session(user_id=USER_ID, session_id=SESSION_ID)
    return manager


def _dispatch_mock(calls=None):
    async def _dispatch(*args, **kwargs):
        if calls is not None:
            calls.append(args[0] if args else kwargs.get("message"))
        await asyncio.sleep(0)
        return {
            "success": True,
            "status": "success",
            "outcome": "success",
            "message": (
                "FINANCE CONTRIBUTION: gap USD150. "
                "SALES CONTRIBUTION: pipeline is not closed revenue."),
            "chain_id": "chain-collab",
            "specialists_count": 2,
            "execution_id": "exec-agent",
        }

    return AsyncMock(side_effect=_dispatch)


def _orch(manager, *, tenant_id=TENANT_ID, dispatch=None):
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    orch.tenant_id = tenant_id
    orch.session_manager = manager
    orch.conversation_sessions = {}
    orch._cancelled_sessions = set()
    orch._handle_agent_request = dispatch or _dispatch_mock()
    return orch


def _deadline(remaining=60.0):
    deadline = MagicMock()
    deadline.remaining.return_value = remaining
    return deadline


def _collaboration_decision(message=MESSAGE):
    interpretation = {
        "schema": td.INTERPRETATION_SCHEMA,
        "origin": "llm:synthetic",
        "scope_change": "replace",
        "message": message,
        "actions": [{
            "kind": "collaboration",
            "roles": ["finance", "sales"],
            "explicit": True,
            "generic": False,
        }],
        "subjects": [],
        "sources": [],
        "constraints": [],
    }
    return apply_interpretation_actions(
        build_turn_decision(message, {}), interpretation)


def _approval_decision():
    return build_turn_decision("go ahead", {})


def _flags(monkeypatch, *, master=False, enforce=False):
    import core.fleet_routing_config as frc
    import core.fleet_orchestration.fleet_router_automation as fra

    monkeypatch.setattr(frc, "fleet_routing_enabled", lambda: master)
    monkeypatch.setattr(fra, "resolved_fleet_enforce", lambda: enforce)


def _create_pending(
    orch,
    *,
    decision=None,
    session_id=SESSION_ID,
    user_id=USER_ID,
    workspace=WORKSPACE_ID,
    message=MESSAGE,
):
    return asyncio.run(orch._route_accepted_collaboration(
        decision=decision or _collaboration_decision(),
        message=message,
        session=orch.conversation_sessions.setdefault(
            session_id, {"id": session_id, "history": []}),
        session_id=session_id,
        user_id=user_id,
        context={"workspace_id": workspace},
        execution_id="exec-chat",
        deadline=_deadline(),
    ))


def _approve(
    orch,
    *,
    session_id=SESSION_ID,
    user_id=USER_ID,
    workspace=WORKSPACE_ID,
    message="go ahead",
):
    return asyncio.run(orch._route_accepted_collaboration(
        decision=_approval_decision(),
        message=message,
        session=orch.conversation_sessions.setdefault(
            session_id, {"id": session_id, "history": []}),
        session_id=session_id,
        user_id=user_id,
        context={"workspace_id": workspace},
        execution_id="exec-approve",
        deadline=_deadline(),
    ))


def _durable_metadata(Session, session_id=SESSION_ID):
    with Session() as db:
        row = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        assert row is not None
        return dict(row.metadata_json or {})


def _receipts(Session):
    with Session() as db:
        return db.query(TaskOperationRecord).all()


# ---------------------------------------------------------------------------
# 1. Durable authority + cold resume
# ---------------------------------------------------------------------------

def test_pending_is_visible_to_a_fresh_manager_and_orchestrator(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(manager)

    response = _create_pending(orch)

    assert response["outcome"] == "pending"
    assert response["data"]["collaboration"]["request_preserved"] is True
    assert response["data"]["collaboration"]["pending_saved"] is True
    durable = _durable_metadata(Session)
    assert durable["_pending_collaboration"]["request"] == MESSAGE
    assert durable["_pending_collaboration"]["user_id"] == USER_ID
    assert durable["_pending_collaboration"]["workspace_id"] == WORKSPACE_ID
    assert durable["_pending_collaboration"]["tenant_id"] == TENANT_ID
    assert durable["_pending_collaboration"]["session_id"] == SESSION_ID
    assert durable["_pending_collaboration"]["request_digest"]
    assert durable["_pending_collaboration_revision"] == (
        durable["_pending_collaboration"]["revision"])
    # Unrelated metadata survives the patch.
    assert durable["keep_unrelated"] == "v1"

    # A NEW process: new manager, new orchestrator, empty conversation cache.
    fresh_manager = ChatSessionManager(
        sessions_file=str(tmp_path / "fresh-sessions.json"))
    fresh_orch = _orch(fresh_manager)
    state = fresh_orch._load_pending_collaboration_state(SESSION_ID)
    assert state["status"] == "found"
    assert state["pending"]["request"] == MESSAGE
    assert state["pending"]["roles"] == ["finance", "sales"]
    assert state["revision"] == durable["_pending_collaboration_revision"]


def test_fresh_process_resumes_exact_request_then_clears_durable(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    _create_pending(_orch(manager))

    _flags(monkeypatch, master=True, enforce=True)
    calls = []
    fresh_manager = ChatSessionManager(
        sessions_file=str(tmp_path / "fresh-resume.json"))
    fresh_orch = _orch(fresh_manager, dispatch=_dispatch_mock(calls))

    response = _approve(fresh_orch)

    assert calls == [MESSAGE]
    fresh_orch._handle_agent_request.assert_awaited_once()
    assert fresh_orch._handle_agent_request.await_args.args[0] == MESSAGE
    assert response["outcome"] == "completed"
    assert response["data"]["collaboration"]["pending_cleared"] is True
    assert response["data"]["collaboration"]["receipt_status"] == "succeeded"

    durable = _durable_metadata(Session)
    assert durable["_pending_collaboration"] is None
    assert durable["keep_unrelated"] == "v1"
    receipts = _receipts(Session)
    assert len(receipts) == 1
    assert receipts[0].status == "succeeded"
    assert receipts[0].operation_type == "generic:agent:collaboration_resume"

    # A second approval cannot re-run it.
    again = _approve(fresh_orch)
    assert len(calls) == 1
    fresh_orch._handle_agent_request.assert_awaited_once()
    assert again is None or again.get("outcome") != "completed"


# ---------------------------------------------------------------------------
# 2. Durable clear/cancel/supersession beats the cache; unreadable != absent
# ---------------------------------------------------------------------------

def test_durable_clear_beats_stale_in_memory_pending(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(manager)
    _create_pending(orch)
    old = _durable_metadata(Session)
    assert orch.conversation_sessions[SESSION_ID][
        co._PENDING_COLLABORATION_KEY]["state"] == "pending"

    # Another worker durably clears the record; this process still has the
    # old snapshot in memory.
    assert manager.update_session_metadata(
        SESSION_ID,
        {
            co._PENDING_COLLABORATION_KEY: None,
            co._PENDING_COLLABORATION_REVISION_KEY: "external-clear",
        },
        expected={
            co._PENDING_COLLABORATION_REVISION_KEY:
                old["_pending_collaboration_revision"]},
    )

    _flags(monkeypatch, master=True, enforce=True)
    response = _approve(orch)

    orch._handle_agent_request.assert_not_awaited()
    assert response is None  # no pending left; normal turn may continue
    assert co._PENDING_COLLABORATION_KEY not in orch.conversation_sessions[
        SESSION_ID]
    assert _durable_metadata(Session)["_pending_collaboration"] is None


def test_cancelled_durable_state_beats_stale_cache_and_never_resumes(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(manager)
    _create_pending(orch)
    assert orch.conversation_sessions[SESSION_ID][
        co._PENDING_COLLABORATION_KEY]["state"] == "pending"

    # Another worker cancels the durable request (tombstone, not absence).
    with Session() as db:
        row = db.query(ChatSession).filter(
            ChatSession.id == SESSION_ID).first()
        meta = dict(row.metadata_json or {})
        record = dict(meta[co._PENDING_COLLABORATION_KEY])
        record["state"] = "cancelled"
        meta[co._PENDING_COLLABORATION_KEY] = record
        row.metadata_json = meta
        db.commit()

    _flags(monkeypatch, master=True, enforce=True)
    response = _approve(orch)

    orch._handle_agent_request.assert_not_awaited()
    assert response is not None
    assert response["outcome"] == "unavailable"
    assert response["data"]["collaboration"]["state"] == "cancelled"
    assert response["data"]["collaboration"]["request_preserved"] is False


def test_revision_mismatch_is_unavailable_and_never_dispatches(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    _create_pending(_orch(manager))

    with Session() as db:
        row = db.query(ChatSession).filter(
            ChatSession.id == SESSION_ID).first()
        meta = dict(row.metadata_json or {})
        meta[co._PENDING_COLLABORATION_REVISION_KEY] = (
            "different-top-level-revision")
        row.metadata_json = meta
        db.commit()

    _flags(monkeypatch, master=True, enforce=True)
    fresh = _orch(
        ChatSessionManager(sessions_file=str(tmp_path / "revision.json")))
    response = _approve(fresh)

    fresh._handle_agent_request.assert_not_awaited()
    assert response is not None
    assert response["outcome"] == "unavailable"
    assert response["data"]["collaboration"]["reason"] == (
        "pending_inconsistent")
    assert response["data"]["collaboration"]["request_preserved"] is False


@pytest.mark.parametrize("failure", ["snapshot", "exception"])
def test_read_failure_is_unavailable_and_never_uses_cache(
        db_world, monkeypatch, tmp_path, failure):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(manager)
    _create_pending(orch)
    assert co._PENDING_COLLABORATION_KEY in orch.conversation_sessions[
        SESSION_ID]

    if failure == "snapshot":
        monkeypatch.setattr(
            manager, "read_session_metadata",
            lambda _sid: {
                "readable": False, "found": False,
                "metadata": {}, "revision": "",
                "error": "synthetic read failure",
            })
    else:
        def _boom(_sid):
            raise RuntimeError("synthetic read exception")

        monkeypatch.setattr(manager, "read_session_metadata", _boom)

    _flags(monkeypatch, master=True, enforce=True)
    response = _approve(orch)

    orch._handle_agent_request.assert_not_awaited()
    assert response is not None
    assert response["outcome"] == "unavailable"
    assert response["data"]["collaboration"]["request_preserved"] is False
    assert response["data"]["collaboration"]["request_verified"] is False
    assert response["data"]["collaboration"]["request"] == MESSAGE
    # The unreadable store did not erase the local copy, and did not authorise
    # a resume from it either.
    assert co._PENDING_COLLABORATION_KEY in orch.conversation_sessions[
        SESSION_ID]
    assert _durable_metadata(Session)["_pending_collaboration"] is not None


# ---------------------------------------------------------------------------
# 3. Honest save failures: no false preservation, no cache advance, no dispatch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["false", "exception"])
def test_failed_pending_save_is_honest_and_preserves_request_truth(
        db_world, monkeypatch, tmp_path, mode):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    if mode == "false":
        monkeypatch.setattr(
            manager, "update_session_metadata",
            lambda *a, **k: False)
    else:
        def _raise(*_a, **_k):
            raise OSError("synthetic write failure")

        monkeypatch.setattr(manager, "update_session_metadata", _raise)
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(manager)

    response = _create_pending(orch)

    orch._handle_agent_request.assert_not_awaited()
    assert response["outcome"] == "unavailable"
    assert response["success"] is False
    assert response["objective_pending"] is True
    assert response["data"]["collaboration"]["state"] == "unavailable"
    assert response["data"]["collaboration"]["request_preserved"] is False
    assert response["data"]["collaboration"]["pending_saved"] is False
    assert response["data"]["collaboration"]["save_reason"] == (
        "write_rejected" if mode == "false" else "write_exception")
    # Original task truth is not lost or falsely completed.
    assert response["data"]["collaboration"]["request"] == MESSAGE
    assert response["data"]["collaboration"]["roles"] == ["finance", "sales"]
    assert response["_recorded_outcome"]["state"] == "partial"
    assert "could not durably record" in response["message"]
    # The cache did not advance and the durable row has no pending.
    assert co._PENDING_COLLABORATION_KEY not in orch.conversation_sessions[
        SESSION_ID]
    durable = _durable_metadata(Session)
    assert durable.get("_pending_collaboration") is None
    assert durable["keep_unrelated"] == "v1"


def test_resume_claim_save_failure_does_not_dispatch(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    _create_pending(_orch(manager))
    _flags(monkeypatch, master=True, enforce=True)

    monkeypatch.setattr(
        manager, "update_session_metadata", lambda *a, **k: False)
    fresh = _orch(manager)
    response = _approve(fresh)

    fresh._handle_agent_request.assert_not_awaited()
    assert response["outcome"] == "unavailable"
    assert response["data"]["collaboration"]["reason"] == (
        "pending_claim_not_saved")
    assert response["data"]["collaboration"]["request_preserved"] is False
    # The unclaimed record stays pending and is not falsely completed.
    durable = _durable_metadata(Session)
    assert durable["_pending_collaboration"]["state"] == "pending"


def test_missing_manager_is_truthful_not_preserved(monkeypatch):
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(None)

    response = _create_pending(orch)

    orch._handle_agent_request.assert_not_awaited()
    assert response["outcome"] == "unavailable"
    assert response["data"]["collaboration"]["request_preserved"] is False
    assert response["data"]["collaboration"]["save_reason"] == (
        "no_session_manager")
    assert co._PENDING_COLLABORATION_KEY not in orch.conversation_sessions[
        SESSION_ID]


def test_failed_durable_clear_does_not_falsely_resolve_the_question(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    orch = _orch(manager)
    response = _create_pending(orch)
    assert response["outcome"] == "pending"

    # Give the durable record a linked question so the negative control is
    # about the clear failure, not about a missing question id.
    with Session() as db:
        row = db.query(ChatSession).filter(
            ChatSession.id == SESSION_ID).first()
        meta = dict(row.metadata_json or {})
        record = dict(meta[co._PENDING_COLLABORATION_KEY])
        record["question_id"] = "q-1"
        meta[co._PENDING_COLLABORATION_KEY] = record
        row.metadata_json = meta
        db.commit()

    resolved = []

    class _Lifecycle:
        def get_task(self, run_id):
            return {"run_id": "run-1"}

        def find_active_task(self, session_id):
            return {"run_id": "run-1"}

    monkeypatch.setattr(
        co, "_task_lifecycle_for", lambda *_a, **_k: _Lifecycle())
    monkeypatch.setattr(
        "core.task_lifecycle.resolve_unresolved_questions",
        lambda *a, **k: resolved.append(k))
    monkeypatch.setattr(
        manager, "update_session_metadata", lambda *a, **k: False)

    session = orch.conversation_sessions[SESSION_ID]
    pending = dict(session[co._PENDING_COLLABORATION_KEY])
    pending["question_id"] = "q-1"
    result = orch._clear_pending_collaboration(
        session, SESSION_ID, WORKSPACE_ID,
        "the approved fleet pilot completed the collaboration")

    assert result["saved"] is False
    assert resolved == []  # not falsely completed
    assert pending["question_id"] == "q-1"


# ---------------------------------------------------------------------------
# 4. Scope and material binding
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", [
    "actor", "workspace", "tenant", "digest",
])
def test_out_of_scope_or_tampered_pending_never_dispatches(
        db_world, monkeypatch, tmp_path, case):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    _create_pending(_orch(manager))

    if case == "digest":
        with Session() as db:
            row = db.query(ChatSession).filter(
                ChatSession.id == SESSION_ID).first()
            meta = dict(row.metadata_json or {})
            record = dict(meta[co._PENDING_COLLABORATION_KEY])
            record["request"] = MESSAGE + " (tampered)"
            meta[co._PENDING_COLLABORATION_KEY] = record
            row.metadata_json = meta
            db.commit()

    _flags(monkeypatch, master=True, enforce=True)
    fresh = _orch(
        ChatSessionManager(
            sessions_file=str(tmp_path / f"scope-{case}.json")),
        tenant_id=("t-other" if case == "tenant" else TENANT_ID))
    if case == "actor":
        response = _approve(fresh, user_id="u-intruder")
    elif case == "workspace":
        response = _approve(fresh, workspace="w-other")
    elif case == "tenant":
        response = _approve(fresh)
    else:
        response = _approve(fresh)

    fresh._handle_agent_request.assert_not_awaited()
    assert response is not None
    assert response["outcome"] == "unavailable"
    assert response["data"]["collaboration"]["request_preserved"] is False


# ---------------------------------------------------------------------------
# 5. Concurrency / stale approval / newer pending / duplicate dispatch
# ---------------------------------------------------------------------------

def test_concurrent_stale_approvals_dispatch_once(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    _create_pending(_orch(manager))
    _flags(monkeypatch, master=True, enforce=True)

    # Both processes observed the SAME revision before either wrote it.
    observer = _orch(manager)
    stale_snapshot = observer._load_pending_collaboration_state(SESSION_ID)
    assert stale_snapshot["status"] == "found"
    assert stale_snapshot["revision"]

    calls = []
    shared_dispatch = _dispatch_mock(calls)
    first = _orch(
        ChatSessionManager(sessions_file=str(tmp_path / "conc-1.json")),
        dispatch=shared_dispatch)
    second = _orch(
        ChatSessionManager(sessions_file=str(tmp_path / "conc-2.json")),
        dispatch=shared_dispatch)

    def _stale_state(_sid):
        return dict(stale_snapshot)

    monkeypatch.setattr(first, "_load_pending_collaboration_state", _stale_state)
    monkeypatch.setattr(second, "_load_pending_collaboration_state", _stale_state)

    async def _run_both():
        return await asyncio.gather(
            first._route_accepted_collaboration(
                decision=_approval_decision(), message="go ahead",
                session={"id": SESSION_ID, "history": []},
                session_id=SESSION_ID, user_id=USER_ID,
                context={"workspace_id": WORKSPACE_ID},
                execution_id="exec-c1", deadline=_deadline()),
            second._route_accepted_collaboration(
                decision=_approval_decision(), message="go ahead",
                session={"id": SESSION_ID, "history": []},
                session_id=SESSION_ID, user_id=USER_ID,
                context={"workspace_id": WORKSPACE_ID},
                execution_id="exec-c2", deadline=_deadline()),
        )

    responses = asyncio.run(_run_both())
    assert calls == [MESSAGE], calls
    assert shared_dispatch.await_count == 1
    assert sum(1 for r in responses if r and r.get("outcome") == "completed") == 1
    assert _durable_metadata(Session)["_pending_collaboration"] is None


def test_completed_receipt_blocks_duplicate_when_clear_failed(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    _create_pending(_orch(manager))
    durable = _durable_metadata(Session)
    pending = dict(durable[co._PENDING_COLLABORATION_KEY])
    _flags(monkeypatch, master=True, enforce=True)

    first = _orch(
        ChatSessionManager(sessions_file=str(tmp_path / "receipt-1.json")))
    _approve(first)
    assert first._handle_agent_request.await_count == 1

    # Simulate a failed durable clear: the same pending_id is still durable.
    restored = dict(pending)
    restored["revision"] = "restored-rev"
    restored["state"] = "pending"
    assert manager.update_session_metadata(
        SESSION_ID,
        {
            co._PENDING_COLLABORATION_KEY: restored,
            co._PENDING_COLLABORATION_REVISION_KEY: "restored-rev",
        })

    second = _orch(
        ChatSessionManager(sessions_file=str(tmp_path / "receipt-2.json")))
    response = _approve(second)

    second._handle_agent_request.assert_not_awaited()
    assert response is not None
    assert response["data"]["collaboration"]["state"] == "completed"
    assert response["outcome"] == "completed"
    # A new intent would get a new pending_id; this one is terminal.
    assert len(_receipts(Session)) == 1


def test_stale_writer_cannot_overwrite_a_newer_pending(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    old_orch = _orch(manager)
    _create_pending(old_orch)
    old_meta = _durable_metadata(Session)
    old_record = dict(old_meta[co._PENDING_COLLABORATION_KEY])
    old_rev = old_meta[co._PENDING_COLLABORATION_REVISION_KEY]

    # A genuinely newer explicit request replaces the older pending.
    newer = "Analyze Q4 with finance and sales specialists."
    newer_orch = _orch(manager)
    assert _create_pending(newer_orch, message=newer,
                           decision=_collaboration_decision(newer))[
        "outcome"] == "pending"
    newer_meta = _durable_metadata(Session)
    assert newer_meta[co._PENDING_COLLABORATION_KEY]["request"] == newer
    assert newer_meta[co._PENDING_COLLABORATION_REVISION_KEY] != old_rev

    # A delayed stale writer with the old material cannot clobber it.
    stale_result = old_orch._persist_pending_collaboration(
        old_orch.conversation_sessions[SESSION_ID], SESSION_ID,
        old_record)
    assert stale_result["saved"] is False
    assert stale_result["reason"] == "superseded_by_newer_pending"
    assert _durable_metadata(Session)["_pending_collaboration"]["request"] == (
        newer)

    # Even a direct stale CAS with the old revision is rejected.
    stale_cas = old_orch._persist_pending_collaboration(
        old_orch.conversation_sessions[SESSION_ID], SESSION_ID,
        old_record, expected_revision=old_rev)
    assert stale_cas["saved"] is False
    assert stale_cas["reason"] == "write_rejected"
    assert _durable_metadata(Session)["_pending_collaboration"]["request"] == (
        newer)

    # Approval runs only the newer material.
    _flags(monkeypatch, master=True, enforce=True)
    calls = []
    resume = _orch(
        ChatSessionManager(sessions_file=str(tmp_path / "newer-resume.json")),
        dispatch=_dispatch_mock(calls))
    _approve(resume)
    assert calls == [newer]


# ---------------------------------------------------------------------------
# 6. File mode remains a first-class durable store
# ---------------------------------------------------------------------------

def test_file_mode_pending_survives_fresh_manager_and_resumes_once(
        monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    _flags(monkeypatch, master=False, enforce=False)
    first = _orch(manager)
    response = _create_pending(first)
    assert response["outcome"] == "pending"
    assert response["data"]["collaboration"]["pending_saved"] is True

    fresh = _orch(_file_manager(monkeypatch, tmp_path, create=False))
    state = fresh._load_pending_collaboration_state(SESSION_ID)
    assert state["status"] == "found"
    assert state["pending"]["request"] == MESSAGE

    _flags(monkeypatch, master=True, enforce=True)
    calls = []
    resume = _orch(
        ChatSessionManager(
            sessions_file=str(tmp_path / "collab-sessions.json")),
        dispatch=_dispatch_mock(calls))
    second = _approve(resume)
    assert calls == [MESSAGE]
    assert second["outcome"] == "completed"
    cleared = _orch(ChatSessionManager(
        sessions_file=str(tmp_path / "collab-sessions.json")))
    assert cleared._load_pending_collaboration_state(SESSION_ID)[
        "status"] == "absent"


# ---------------------------------------------------------------------------
# 7. General metadata API: truthful read + CAS, back-compatible
# ---------------------------------------------------------------------------

def test_metadata_read_distinguishes_unreadable_from_absent(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)

    present = manager.read_session_metadata(SESSION_ID)
    assert present["readable"] is True and present["found"] is True
    assert present["metadata"]["keep_unrelated"] == "v1"

    absent = manager.read_session_metadata("missing-session")
    assert absent["readable"] is True and absent["found"] is False

    @contextmanager
    def _broken():
        raise RuntimeError("synthetic db read failure")
        yield  # pragma: no cover

    monkeypatch.setattr(csm, "get_db_session", _broken)
    unreadable = manager.read_session_metadata(SESSION_ID)
    assert unreadable["readable"] is False
    assert unreadable["found"] is False
    assert unreadable["error"]


def test_metadata_cas_rejects_stale_and_preserves_unrelated_keys(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    manager = _db_manager(monkeypatch, Session, tmp_path)

    assert manager.update_session_metadata(
        SESSION_ID, {"_rev": "r1", "added": 1},
        expected={"_rev": None}) is True
    first = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert first["keep_unrelated"] == "v1"
    assert first["added"] == 1

    assert manager.update_session_metadata(
        SESSION_ID, {"_rev": "r2"}, expected={"_rev": "wr0ng"}) is False
    assert manager.read_session_metadata(SESSION_ID)["metadata"]["_rev"] == (
        "r1")

    assert manager.update_session_metadata(
        SESSION_ID, {"_rev": "r2"}, expected={"_rev": "r1"}) is True
    final = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert final["_rev"] == "r2"
    assert final["keep_unrelated"] == "v1"
    assert final["added"] == 1

    # A missing row is a truthful failed save, not a silent success.
    assert manager.update_session_metadata(
        "missing-session", {"x": 1}) is False


def test_file_metadata_cas_rejects_stale(monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    assert manager.update_session_metadata(
        SESSION_ID, {"_rev": "f1", "keep": 1},
        expected={"_rev": None}) is True
    assert manager.read_session_metadata(SESSION_ID)["metadata"]["keep"] == 1
    assert manager.update_session_metadata(
        SESSION_ID, {"_rev": "f2"}, expected={"_rev": "stale"}) is False
    assert manager.read_session_metadata(SESSION_ID)["metadata"]["_rev"] == (
        "f1")
    assert manager.update_session_metadata(
        SESSION_ID, {"_rev": "f2"}, expected={"_rev": "f1"}) is True
    assert manager.read_session_metadata(SESSION_ID)["metadata"]["_rev"] == (
        "f2")


# ---------------------------------------------------------------------------
# 8. General metadata CAS: no lost unrelated updates, typed preconditions
# ---------------------------------------------------------------------------

def _set_row_metadata(Session, metadata, session_id=SESSION_ID):
    with Session() as db:
        row = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        assert row is not None
        row.metadata_json = dict(metadata)
        db.commit()


def _row_metadata(Session, session_id=SESSION_ID):
    with Session() as db:
        row = db.query(ChatSession).filter(
            ChatSession.id == session_id).first()
        assert row is not None
        return dict(row.metadata_json or {})


def _interleave_cas(
    paused_manager,
    other_manager,
    paused_patch,
    other_patch,
    *,
    paused_expected=None,
    other_expected=None,
):
    """Pause one writer after its snapshot read, let the other commit.

    This is a real two-session SQLite interleaving: the paused writer holds no
    read transaction (the snapshot read session is closed), so the other
    writer can commit. The paused writer's first conditional UPDATE then sees
    the conflict and re-reads/re-merges.
    """
    paused = threading.Event()
    resume = threading.Event()
    snapshots = []
    raw_snapshots = []
    original = paused_manager._conditional_metadata_update

    def _paused_cas(session_id, current, raw_snapshot, merged):
        snapshots.append(dict(current))
        raw_snapshots.append(raw_snapshot)
        if len(snapshots) == 1:
            paused.set()
            if not resume.wait(10):
                raise AssertionError("interleaved writer was not released")
        return original(session_id, current, raw_snapshot, merged)

    paused_manager._conditional_metadata_update = _paused_cas
    results = {}

    def _run_paused():
        try:
            results["paused"] = paused_manager.update_session_metadata(
                SESSION_ID, paused_patch, expected=paused_expected)
        except Exception as exc:  # noqa: BLE001 — re-raised on the main thread
            results["paused_error"] = exc

    thread = threading.Thread(target=_run_paused)
    thread.start()
    try:
        assert paused.wait(10), "paused writer never reached its CAS"
        results["other"] = other_manager.update_session_metadata(
            SESSION_ID, other_patch, expected=other_expected)
    finally:
        resume.set()
        thread.join(10)
    assert not thread.is_alive(), "paused writer did not finish"
    if "paused_error" in results:
        raise results["paused_error"]
    return results, snapshots, raw_snapshots


def test_metadata_cas_preserves_unrelated_concurrent_legacy_patch(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    _set_row_metadata(Session, {"guard": "v0", "unrelated": 0})
    manager_a = _db_manager(monkeypatch, Session, tmp_path)
    manager_b = _db_manager(monkeypatch, Session, tmp_path)

    # The root counter: A reads {guard:v0, unrelated:0} and pauses BEFORE its
    # UPDATE; B's legacy 2-arg patch commits; A resumes with a stale snapshot.
    results, snapshots, raw_snapshots = _interleave_cas(
        manager_a, manager_b,
        {"guard": "v1"},
        {"unrelated": 1},
        paused_expected={"guard": "v0"},
    )

    assert results == {"paused": True, "other": True}
    assert len(snapshots) >= 2, "the CAS must have retried"
    assert snapshots[0]["unrelated"] == 0
    assert snapshots[1]["unrelated"] == 1
    final = _row_metadata(Session)
    assert final["guard"] == "v1"
    assert final["unrelated"] == 1
    assert final["_metadata_revision"]


def test_stale_pending_condition_loser_refuses_without_overwrite(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    _set_row_metadata(Session, {"guard": "v0", "unrelated": 0})
    manager_a = _db_manager(monkeypatch, Session, tmp_path)
    manager_b = _db_manager(monkeypatch, Session, tmp_path)

    results, snapshots, raw_snapshots = _interleave_cas(
        manager_a, manager_b,
        {"guard": "v1", "loser": "a"},
        {"guard": "v2"},
        paused_expected={"guard": "v0"},
    )

    assert results["paused"] is False
    assert results["other"] is True
    # The retry re-read guard=v2 and refused before a second conditional write.
    assert len(snapshots) == 1
    final = _row_metadata(Session)
    assert final["guard"] == "v2"
    assert "loser" not in final
    assert final["unrelated"] == 0


def test_reverse_order_legacy_writer_preserves_cas_new_field(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    _set_row_metadata(Session, {"guard": "v0", "unrelated": 0})
    manager_a = _db_manager(monkeypatch, Session, tmp_path)
    manager_b = _db_manager(monkeypatch, Session, tmp_path)

    # Reverse order: the legacy writer reads first and pauses; the CAS writer
    # commits a new field; the legacy writer must re-merge, not clobber it.
    results, snapshots, raw_snapshots = _interleave_cas(
        manager_b, manager_a,
        {"unrelated": 1},
        {"new_field": 1},
        other_expected={"guard": "v0"},
    )

    assert results == {"paused": True, "other": True}
    assert len(snapshots) >= 2
    assert "new_field" not in snapshots[0]
    assert snapshots[1]["new_field"] == 1
    final = _row_metadata(Session)
    assert final["new_field"] == 1
    assert final["unrelated"] == 1
    assert final["guard"] == "v0"


def test_typed_scalar_expected_semantics_real_sqlite(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    _set_row_metadata(Session, {
        "s": "1", "i": 1, "f": 1.5, "bt": True, "bf": False,
        "n": None, "e": "",
    })
    manager = _db_manager(monkeypatch, Session, tmp_path)

    cases = [
        ("s", "1", True),
        ("s", 1, False),
        ("i", 1, True),
        ("i", "1", False),
        ("i", True, False),
        ("f", 1.5, True),
        ("f", 1, False),
        ("f", 1.5, True),
        ("bt", True, True),
        ("bt", 1, False),
        ("bf", False, True),
        ("bf", 0, False),
        ("n", None, True),
        ("n", "", False),
        ("missing", None, True),
        ("missing", "", False),
        ("missing", 0, False),
        ("e", "", True),
        ("e", None, False),
    ]
    for index, (key, wanted, expected_result) in enumerate(cases):
        result = manager.update_session_metadata(
            SESSION_ID, {"probe": index}, expected={key: wanted})
        assert result is expected_result, (key, wanted, result, expected_result)
        # The metadata keys under test never change.
        metadata = manager.read_session_metadata(SESSION_ID)["metadata"]
        assert metadata["s"] == "1" and metadata["i"] == 1
        assert metadata["f"] == 1.5 and metadata["bt"] is True
        assert metadata["bf"] is False and metadata["n"] is None
        assert metadata["e"] == ""

    # Composite and non-finite expectations are refused, not coerced.
    assert manager.update_session_metadata(
        SESSION_ID, {"x": 1}, expected={"i": {"nested": 1}}) is False
    assert manager.update_session_metadata(
        SESSION_ID, {"x": 1}, expected={"f": float("nan")}) is False

    # Old 2-arg patch semantics: None is JSON null, not a JSON Merge Patch
    # deletion. The key remains present.
    assert manager.update_session_metadata(
        SESSION_ID, {"null_kept": None}) is True
    final = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert "null_kept" in final
    assert final["null_kept"] is None


def test_pg_and_sqlite_compiled_metadata_cas_statement():
    current = {"guard": "v0", "unrelated": 0}
    merged = {
        **current, "guard": "v1", "_metadata_revision": "tok",
    }
    raw_snapshot = '{"guard": "v0", "unrelated": 0}'
    statement = ChatSessionManager._metadata_update_statement(
        SESSION_ID, raw_snapshot, merged)
    pg_sql = str(statement.compile(dialect=postgresql.dialect()))
    sqlite_sql = str(statement.compile(dialect=sqlite.dialect()))

    for compiled in (pg_sql, sqlite_sql):
        assert "UPDATE chat_sessions" in compiled
        assert "WHERE" in compiled
        assert "metadata_json" in compiled
    assert "JSONB" in pg_sql
    # The whole exact stored snapshot, not a single expected key, is the CAS
    # arm; both the SET and the WHERE reference the column.
    assert pg_sql.count("metadata_json") >= 2
    assert sqlite_sql.count("metadata_json") >= 2
    assert "CAST" in sqlite_sql.upper() or "JSON_EXTRACT" in sqlite_sql.upper()

    # SQL NULL uses IS NULL; a JSON literal null is a distinct exact text arm.
    sql_null = ChatSessionManager._metadata_update_statement(
        SESSION_ID, None, merged)
    assert "IS NULL" in str(sql_null.compile(dialect=sqlite.dialect()))
    assert "IS NULL" in str(sql_null.compile(dialect=postgresql.dialect()))
    json_null = ChatSessionManager._metadata_update_statement(
        SESSION_ID, "null", merged)
    json_null_sql = str(json_null.compile(dialect=sqlite.dialect()))
    assert "IS NULL" not in json_null_sql
    assert "CAST" in json_null_sql.upper() or (
        "JSON_EXTRACT" in json_null_sql.upper())


def test_file_lock_failure_is_truthful(monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    before = manager.read_session_metadata(SESSION_ID)["metadata"]

    @contextmanager
    def _denied(_path, **_kwargs):
        yield False

    monkeypatch.setattr(csm, "_interprocess_file_lock", _denied)
    assert manager.update_session_metadata(
        SESSION_ID, {"blocked": 1}) is False
    after = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert after == before
    assert "blocked" not in after


def test_file_write_failure_is_truthful(monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    before = manager.read_session_metadata(SESSION_ID)["metadata"]

    def _boom(*_args, **_kwargs):
        raise OSError("synthetic temp write failure")

    monkeypatch.setattr(csm.tempfile, "mkstemp", _boom)
    assert manager.update_session_metadata(
        SESSION_ID, {"blocked": 1}) is False
    after = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert after == before
    assert "blocked" not in after


def test_malformed_file_is_unavailable_and_not_written(monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    with open(manager.sessions_file, "w") as f:
        f.write("{not json")
    read = manager.read_session_metadata(SESSION_ID)
    assert read["readable"] is False
    assert read["found"] is False
    assert manager.update_session_metadata(
        SESSION_ID, {"blocked": 1}) is False
    with open(manager.sessions_file) as f:
        assert f.read() == "{not json"


def test_file_metadata_cas_preserves_two_legit_patches(monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    assert manager.update_session_metadata(SESSION_ID, {"a": 1}) is True
    assert manager.update_session_metadata(SESSION_ID, {"b": 2}) is True
    final = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert final["a"] == 1 and final["b"] == 2
    assert final["_metadata_revision"]


# ---------------------------------------------------------------------------
# 9. Two INDEPENDENT file-mode processes: one winner, no lost keys
# ---------------------------------------------------------------------------

_FILE_CHILD_SCRIPT = r'''
import json, os, sys, time
from core.chat_session_manager import ChatSessionManager

sessions_file, barrier, spec_json = sys.argv[1:4]
spec = json.loads(spec_json)
while not os.path.exists(barrier):
    time.sleep(0.005)
manager = ChatSessionManager(sessions_file=sessions_file)
ok = manager.update_session_metadata(
    spec["session_id"], spec["patch"], expected=spec.get("expected"))
print("RESULT:" + json.dumps({"ok": bool(ok)}))
'''


def _run_file_process_pair(tmp_path, specs, seed_metadata):
    sessions_file = str(tmp_path / "proc-sessions.json")
    barrier = str(tmp_path / "proc-go")
    with open(sessions_file, "w") as f:
        json.dump([{
            "session_id": SESSION_ID,
            "user_id": USER_ID,
            "metadata": dict(seed_metadata),
        }], f)

    env = dict(os.environ)
    env.update({
        "TESTING": "1",
        "ATOM_CHAT_STORAGE": "file",
        "CHAT_PERSISTENCE_MODE": "FILE",
        "ATOM_DATA_DIR": str(tmp_path / "proc-data"),
        "DATABASE_URL": f"sqlite:///{tmp_path / 'proc-db.sqlite'}",
        "PYTHONPATH": BACKEND_DIR,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    })
    os.makedirs(env["ATOM_DATA_DIR"], exist_ok=True)

    processes = [
        subprocess.Popen(
            [
                sys.executable, "-c", _FILE_CHILD_SCRIPT,
                sessions_file, barrier,
                json.dumps({"session_id": SESSION_ID, **spec}),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=BACKEND_DIR,
        )
        for spec in specs
    ]
    # Let both children reach their barrier spin before releasing them.
    time.sleep(0.2)
    with open(barrier, "w") as f:
        f.write("go")

    results = []
    for process in processes:
        try:
            out, err = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            out, err = process.communicate()
            raise AssertionError(f"child file writer timed out: {err[-2000:]}")
        if process.returncode != 0:
            raise AssertionError(
                f"child file writer failed ({process.returncode}): "
                f"{err[-2000:]}")
        line = next(
            (ln for ln in out.splitlines() if ln.startswith("RESULT:")), "")
        assert line, f"no RESULT in stdout={out!r} stderr={err[-2000:]}"
        results.append(json.loads(line[len("RESULT:"):]))
    with open(sessions_file) as f:
        final = json.load(f)
    return results, final[0]["metadata"]


def test_two_processes_compete_one_saved_revision(tmp_path):
    results, final = _run_file_process_pair(
        tmp_path,
        [
            {
                "patch": {"guard": "v1a", "winner_a": 1},
                "expected": {"guard": "v0"},
            },
            {
                "patch": {"guard": "v1b", "winner_b": 1},
                "expected": {"guard": "v0"},
            },
        ],
        {"guard": "v0", "unrelated": 0},
    )

    assert sum(1 for result in results if result["ok"]) == 1, results
    assert final["unrelated"] == 0
    assert final["guard"] in ("v1a", "v1b")
    assert ("winner_a" in final) != ("winner_b" in final)
    if final["guard"] == "v1a":
        assert final.get("winner_a") == 1
    else:
        assert final.get("winner_b") == 1
    assert final["_metadata_revision"]


def test_two_processes_disjoint_patches_both_preserved(tmp_path):
    results, final = _run_file_process_pair(
        tmp_path,
        [
            {"patch": {"a": 1}},
            {"patch": {"b": 2}},
        ],
        {"unrelated": 0},
    )

    assert all(result["ok"] for result in results), results
    assert final["a"] == 1
    assert final["b"] == 2
    assert final["unrelated"] == 0
    assert final["_metadata_revision"]


# ---------------------------------------------------------------------------
# 10. Raw JSON snapshot semantics: literal null, SQL NULL, arbitrary text
# ---------------------------------------------------------------------------

def _raw_set_metadata(Session, raw_literal, session_id=SESSION_ID):
    """Set metadata_json with a RAW SQL literal, bypassing the JSON type.

    ``None`` is SQL NULL; the string "null" is a JSON literal null; any other
    string is stored exactly as supplied (compact/spaced/pretty/escaped/etc.).
    """
    with Session() as db:
        db.execute(
            text(
                "UPDATE chat_sessions SET metadata_json = :raw "
                "WHERE id = :sid"),
            {"raw": raw_literal, "sid": session_id},
        )
        db.commit()


@pytest.mark.parametrize("raw_literal, expected", [
    (None, {}),                                  # SQL NULL
    ("null", {}),                                # JSON literal null
    ('{"guard":"v0"}', {"guard": "v0"}),         # compact raw SQL
    ('{"guard": "v0"}', {"guard": "v0"}),        # spaced raw SQL
    ('{\n  "guard": "v0"\n}', {"guard": "v0"}),  # pretty raw SQL
    ('{"s":"\\u00e9"}', {"s": "é"}),             # escaped unicode
    ('{"n":1,"f":1.50}', {"n": 1, "f": 1.5}),    # numeric encoding
    ("{}", {}),                                  # empty object
])
def test_raw_json_snapshot_forms_update_safely(
        db_world, monkeypatch, tmp_path, raw_literal, expected):
    _engine, Session = db_world
    _raw_set_metadata(Session, raw_literal)
    manager = _db_manager(monkeypatch, Session, tmp_path)

    assert manager.update_session_metadata(
        SESSION_ID, {"patched": True}) is True

    final = _row_metadata(Session)
    assert final["patched"] is True
    for key, value in expected.items():
        assert final[key] == value
    # The committed value is a JSON object in every case.
    assert isinstance(final, dict)


def test_stale_null_to_object_transition_preserves_both_patches(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    _raw_set_metadata(Session, "null")
    manager_a = _db_manager(monkeypatch, Session, tmp_path)
    manager_b = _db_manager(monkeypatch, Session, tmp_path)

    results, snapshots, raw_snapshots = _interleave_cas(
        manager_a, manager_b, {"a": 1}, {"b": 2})

    assert results == {"paused": True, "other": True}
    assert len(snapshots) >= 2
    assert raw_snapshots[0] == "null"
    final = _row_metadata(Session)
    assert final["a"] == 1
    assert final["b"] == 2


def test_stale_object_to_null_transition_does_not_resurrect_cleared_keys(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    _set_row_metadata(Session, {"b": 1, "unrelated": 0})
    manager = _db_manager(monkeypatch, Session, tmp_path)

    paused = threading.Event()
    resume = threading.Event()
    raw_seen = []
    original = manager._conditional_metadata_update

    def _paused_cas(session_id, current, raw_snapshot, merged):
        raw_seen.append(raw_snapshot)
        if len(raw_seen) == 1:
            paused.set()
            if not resume.wait(10):
                raise AssertionError("writer was not released")
        return original(session_id, current, raw_snapshot, merged)

    manager._conditional_metadata_update = _paused_cas
    result = {}

    def _run():
        try:
            result["ok"] = manager.update_session_metadata(
                SESSION_ID, {"a": 1})
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_run)
    thread.start()
    try:
        assert paused.wait(10), "writer never reached its CAS"
        _raw_set_metadata(Session, "null")
    finally:
        resume.set()
        thread.join(10)
    assert not thread.is_alive()
    if "error" in result:
        raise result["error"]

    assert result["ok"] is True
    assert raw_seen[0] is not None
    assert raw_seen[1] == "null"
    final = _row_metadata(Session)
    assert final["a"] == 1
    # The stale object snapshot must not resurrect keys cleared by the null.
    assert "b" not in final
    assert "unrelated" not in final


# ---------------------------------------------------------------------------
# 11. Lock context manager: body errors, contention, unsupported OS
# ---------------------------------------------------------------------------

_LOCK_CHILD_SCRIPT = r'''
import json, sys
from core.chat_session_manager import _interprocess_file_lock

lock_path = sys.argv[1]
with _interprocess_file_lock(lock_path) as acquired:
    print("RESULT:" + json.dumps({"acquired": bool(acquired)}), flush=True)
'''

_LOCK_HOLDER_SCRIPT = r'''
import os, sys, time
from core.chat_session_manager import _interprocess_file_lock

lock_path, release_path = sys.argv[1:3]
with _interprocess_file_lock(lock_path) as acquired:
    print("HELD:" + ("1" if acquired else "0"), flush=True)
    while not os.path.exists(release_path):
        time.sleep(0.01)
'''


def _lock_child_env(tmp_path):
    env = dict(os.environ)
    env.update({
        "TESTING": "1",
        "ATOM_CHAT_STORAGE": "file",
        "CHAT_PERSISTENCE_MODE": "FILE",
        "ATOM_DATA_DIR": str(tmp_path / "lock-child-data"),
        "DATABASE_URL": f"sqlite:///{tmp_path / 'lock-child.sqlite'}",
        "PYTHONPATH": BACKEND_DIR,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    })
    os.makedirs(env["ATOM_DATA_DIR"], exist_ok=True)
    return env


def test_lock_body_exception_propagates_and_releases(tmp_path):
    lock_path = str(tmp_path / "body-error.lock")

    # The original body exception must propagate (not RuntimeError "generator
    # didn't stop after throw"), and the lock must be released by the finally.
    with pytest.raises(ValueError, match="synthetic-body-failure"):
        with csm._interprocess_file_lock(lock_path) as acquired:
            assert acquired is True
            raise ValueError("synthetic-body-failure")

    # Same-process re-acquisition.
    with csm._interprocess_file_lock(lock_path) as acquired:
        assert acquired is True

    # Independent-process re-acquisition.
    completed = subprocess.run(
        [sys.executable, "-c", _LOCK_CHILD_SCRIPT, lock_path],
        cwd=BACKEND_DIR,
        env=_lock_child_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    result_line = next(
        (ln for ln in completed.stdout.splitlines()
         if ln.startswith("RESULT:")), "")
    assert result_line, completed.stdout
    assert json.loads(result_line[len("RESULT:"):])["acquired"] is True


def test_lock_contention_times_out_false_then_releases(tmp_path):
    lock_path = str(tmp_path / "contention.lock")
    release_path = str(tmp_path / "contention.release")
    holder = subprocess.Popen(
        [sys.executable, "-c", _LOCK_HOLDER_SCRIPT, lock_path, release_path],
        cwd=BACKEND_DIR,
        env=_lock_child_env(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    held = []
    reader = threading.Thread(
        target=lambda: held.append(holder.stdout.readline()))
    reader.start()
    reader.join(10)
    try:
        assert held and held[0].strip() == "HELD:1", held

        # A second independent process cannot acquire while the holder owns it.
        with csm._interprocess_file_lock(lock_path, timeout=0.2) as acquired:
            assert acquired is False

        with open(release_path, "w") as f:
            f.write("go")
        holder.wait(timeout=30)

        # Once released, a later attempt succeeds.
        with csm._interprocess_file_lock(lock_path, timeout=2.0) as acquired:
            assert acquired is True
    finally:
        if holder.poll() is None:
            holder.kill()
        holder.communicate(timeout=10)


def test_no_os_lock_primitive_fails_closed(monkeypatch, tmp_path):
    manager = _file_manager(monkeypatch, tmp_path)
    before = manager.read_session_metadata(SESSION_ID)["metadata"]
    lock_path = str(tmp_path / "no-os.lock")

    monkeypatch.setattr(csm, "fcntl", None)
    monkeypatch.setattr(csm, "msvcrt", None)

    with csm._interprocess_file_lock(lock_path) as acquired:
        assert acquired is False
    assert manager.update_session_metadata(
        SESSION_ID, {"blocked": 1}) is False
    after = manager.read_session_metadata(SESSION_ID)["metadata"]
    assert after == before
    assert "blocked" not in after


# ---------------------------------------------------------------------------
# 12. Direct ORM metadata writer routed through the shared CAS
# ---------------------------------------------------------------------------

def _seed_agent(Session, agent_id):
    with Session() as db:
        db.add(AgentRegistry(
            id=agent_id,
            name="Session Agent",
            category="custom",
            module_path="test",
            class_name="SessionAgent",
            confidence_score=0.6,
            status="intern",
            enabled=True,
        ))
        db.commit()


def test_direct_agent_assignment_reverse_order_preserves_pending_revision(
        db_world, monkeypatch, tmp_path):
    _engine, Session = db_world
    agent_id = "agent-session-1"
    _seed_agent(Session, agent_id)
    pending = {
        "state": "pending",
        "revision": "r0",
        "request": MESSAGE,
        "session_id": SESSION_ID,
        "user_id": USER_ID,
        "workspace_id": WORKSPACE_ID,
        "tenant_id": TENANT_ID,
    }
    _set_row_metadata(Session, {
        co._PENDING_COLLABORATION_KEY: pending,
        co._PENDING_COLLABORATION_REVISION_KEY: "r0",
        "unrelated": 0,
    })
    manager = _db_manager(monkeypatch, Session, tmp_path)

    direct_paused = threading.Event()
    pending_done = threading.Event()
    original = ChatSessionManager.merge_in_session.__func__

    def _paused_merge(cls, db, session_id, metadata, **kwargs):
        # The resolver's existence checks opened a read transaction. Release
        # it so the independent pending writer can commit on SQLite; the
        # seeded data is already committed.
        db.rollback()
        direct_paused.set()
        if not pending_done.wait(10):
            raise AssertionError("pending writer was not released")
        return original(cls, db, session_id, metadata, **kwargs)

    monkeypatch.setattr(
        ChatSessionManager, "merge_in_session",
        classmethod(_paused_merge))

    result = {}

    def _run_resolver():
        try:
            with Session() as db:
                resolver = AgentContextResolver(db)
                result["agent"] = resolver.set_session_agent(
                    SESSION_ID, agent_id)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc

    thread = threading.Thread(target=_run_resolver)
    thread.start()
    try:
        assert direct_paused.wait(10), "direct caller never reached its patch"
        pending_writer = _db_manager(monkeypatch, Session, tmp_path)
        assert pending_writer.update_session_metadata(
            SESSION_ID,
            {
                co._PENDING_COLLABORATION_KEY: {
                    **pending, "revision": "r1"},
                co._PENDING_COLLABORATION_REVISION_KEY: "r1",
                "unrelated_pending": 1,
            },
            expected={co._PENDING_COLLABORATION_REVISION_KEY: "r0"},
        ) is True
    finally:
        pending_done.set()
        thread.join(10)
    assert not thread.is_alive(), "direct caller did not finish"
    if "error" in result:
        raise result["error"]

    assert result["agent"] is True
    final = _row_metadata(Session)
    assert final[co._PENDING_COLLABORATION_REVISION_KEY] == "r1"
    assert final[co._PENDING_COLLABORATION_KEY]["revision"] == "r1"
    assert final["unrelated_pending"] == 1
    assert final["unrelated"] == 0
    assert final["agent_id"] == agent_id
