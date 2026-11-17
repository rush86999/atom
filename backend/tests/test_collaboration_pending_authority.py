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
import os
import sys
import tempfile
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
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.chat_session_manager as csm  # noqa: E402
import core.turn_decision as td  # noqa: E402
import integrations.chat_orchestrator as co  # noqa: E402
from core.chat_session_manager import ChatSessionManager  # noqa: E402
from core.models import Base, ChatSession, TaskOperationRecord  # noqa: E402
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
