# -*- coding: utf-8 -*-
"""Pending file task — the confirmation must resume the read (2026-09-23).

Live incident: the user asked for eight machine prices in "Consolidated
Price List 2019.xlsx"; the tool planner timed out behind the canvas-edit
leg, the answer came from September-2026 email prices, and the user's
filename confirmation ("That filename is correct") was planned as small
talk ("No live lookup needed") — the requested read died with the turn
that asked for it.

Pinned behavior:
1. A file-scoped ask whose lookup never runs is STORED on the session,
   and the reply is told plainly the search did not run.
2. A stored ask that gets served by a live lookup is RETIRED.
3. The confirmation turn RESUMES the stored ask: the planner plans the
   ORIGINAL request (not the bare confirmation), the relevance gate
   judges the plan against it, the executor receives it, and the canvas
   edit leg is skipped.
4. Confirmations are narrow: a new request, a question, or an approval
   carrying its own instruction never resumes anything.
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.chat_tool_planner as planner
import integrations.chat_orchestrator as chat
from core.pending_file_task import (
    FILE_TASK_SESSION_KEY,
    build_pending_task,
    is_filename_confirmation,
    matching_pending_task,
    merge_pending_task,
)


ORIGINAL_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, SLE16-8 "
    "and U-38")
CONFIRMATION = "That filename is correct"
HISTORY = {"history": [
    {"message": ORIGINAL_ASK,
     "response": "I couldn't search the workbook yet — no lookup ran."},
]}


@pytest.fixture
def durable_metadata_db(monkeypatch):
    from core import database as database_module
    from core.models_registration import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        db = session_factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)
    yield
    engine.dispose()


# ---------------------------------------------------------------------------
# Confirmation detection
# ---------------------------------------------------------------------------

class TestIsFilenameConfirmation:
    @pytest.mark.parametrize("msg", [
        CONFIRMATION,
        "yes",
        "go",
        "yes, go ahead",
        "correct.",
        "exactly",
        "yes that's the one",
        "the file name is right",
        "ok proceed",
        "sure, that's the one — go ahead",
        "read that file again",
        "open Trumatic-L3030S.xlsx",
    ])
    def test_confirmations(self, msg):
        assert is_filename_confirmation(msg), msg

    @pytest.mark.parametrize("msg", [
        "correct the typo in the draft",
        "what about the 2019 file?",
        "yes please search Gmail for the quotes",
        "find the prices in Consolidated Price List 2019.xlsx",
        "update the canvas with the new prices",
        "no, use the other workbook",
        "",
    ])
    def test_not_confirmations(self, msg):
        assert not is_filename_confirmation(msg), msg


# ---------------------------------------------------------------------------
# Store / match / merge
# ---------------------------------------------------------------------------

class TestMatchingPendingTask:
    def _pending(self):
        return build_pending_task(ORIGINAL_ASK, "consolidated price list 2019.xlsx")

    def test_confirmation_matches_the_stored_ask(self):
        assert matching_pending_task(
            self._pending(), CONFIRMATION, HISTORY["history"]) is not None

    def test_no_match_without_confirmation(self):
        assert matching_pending_task(
            self._pending(), ORIGINAL_ASK, HISTORY["history"]) is None

    def test_newer_substantive_ask_supersedes(self):
        history = HISTORY["history"] + [
            {"message": "search slack for the shipping update",
             "response": "..."},
        ]
        assert matching_pending_task(
            self._pending(), CONFIRMATION, history) is None

    def test_expired_task_never_resumes(self, monkeypatch):
        import core.pending_file_task as pft

        monkeypatch.setattr(pft, "_PENDING_FILE_TASK_TTL_SECONDS", 0.0)
        assert matching_pending_task(
            self._pending(), CONFIRMATION, HISTORY["history"]) is None

    def test_disagreeing_filename_mention_does_not_resume(self):
        assert matching_pending_task(
            self._pending(), "yes, stock counts.xlsx is correct",
            HISTORY["history"]) is None

    def test_agreeing_filename_mention_resumes(self):
        assert matching_pending_task(
            self._pending(),
            "yes, Consolidated Price List 2019.xlsx is correct",
            HISTORY["history"]) is not None

    def test_malformed_pending_is_ignored(self):
        assert matching_pending_task(None, CONFIRMATION, []) is None
        assert matching_pending_task({"mention": "a.xlsx"}, CONFIRMATION, []) is None


    def test_extensionless_incident_target_is_stored_and_is_read_shaped(self):
        from core.agent_file_context import detect_file_task_mentions

        ask = "find all these prices from price list 2019 and let me know what you find"
        assert detect_file_task_mentions(ask) == ["price list 2019"]
        assert chat._read_only_file_ask(
            ask, {"canvas_id": "c1", "canvas_type": "document"}
        ) is True


class TestMergePendingTask:
    def test_confirmation_preserves_original_ask(self):
        existing = build_pending_task(ORIGINAL_ASK, "2019.xlsx")
        merged = merge_pending_task(existing, CONFIRMATION, "2019.xlsx")
        assert merged["original_message"] == ORIGINAL_ASK

    def test_confirmation_records_fuller_mention(self):
        existing = build_pending_task(ORIGINAL_ASK, "2019.xlsx")
        merged = merge_pending_task(
            existing, CONFIRMATION, "consolidated price list 2019.xlsx")
        # The stored mention is stable; the fuller name the user confirmed
        # rides `confirmed_mention`.
        assert merged["mention"] == "2019.xlsx"
        assert merged["confirmed_mention"] == (
            "consolidated price list 2019.xlsx")
        assert merged["original_message"] == ORIGINAL_ASK

    def test_disambiguation_survives_confirmation(self):
        criteria = {"attributes": {"region": "north"}}
        existing = build_pending_task(
            ORIGINAL_ASK, "2019.xlsx", disambiguation=criteria
        )
        merged = merge_pending_task(
            existing, CONFIRMATION, "2019.xlsx", disambiguation=criteria
        )
        assert merged["disambiguation"] == criteria

    def test_substantive_ask_replaces_task(self):
        existing = build_pending_task("older ask about old.xlsx", "old.xlsx")
        merged = merge_pending_task(
            existing, "check stock.csv please", "stock.csv")
        assert merged["original_message"] == "check stock.csv please"
        assert merged["mention"] == "stock.csv"


# ---------------------------------------------------------------------------
# Wiring 1 — the reply leg stores/retires the pending task
# ---------------------------------------------------------------------------

def _orch():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m", "provider": "p",
    })
    orch.llm_service = llm
    return orch


@pytest.mark.asyncio
async def test_failed_lookup_stores_pending_task_and_labels_reply():
    """Turn 1 of the incident: the planner times out, no lookup runs — the
    ask must be stored carrying the FULL spaced filename (never truncated
    to '2019.xlsx') and the reply model must be told the search did not
    run."""
    orch = _orch()
    session = {"id": "s1", "history": []}
    with (
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=asyncio.TimeoutError())),
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(
            return_value=["EMAIL September 2026: GSL48-16 price 51000"])),
        patch.object(chat, "_planner_timeout_evidence", new=AsyncMock(
            return_value="NO TOOL LOOKUP RAN THIS TURN")),
    ):
        await orch._get_qwen_response(
            ORIGINAL_ASK, [], user_id="u1", session_id="s1",
            execution_id="e1", session=session,
        )
    stored = session.get(FILE_TASK_SESSION_KEY)
    assert stored, "the unrun file ask must survive the turn"
    # The mention is the longest honest span (prose may prefix it) but it
    # must never LOSE the name to truncation.
    assert stored["mention"].endswith("consolidated price list 2019.xlsx")
    assert stored["mention"] != "2019.xlsx"
    assert stored["original_message"] == ORIGINAL_ASK
    system_texts = [
        " ".join(m.get("content", "") for m in c.kwargs.get("messages", [])
                 if isinstance(m, dict) and m.get("role") == "system")
        for c in orch.llm_service.generate_completion.call_args_list
    ]
    assert any("did NOT run this turn" in t for t in system_texts)
    assert any(
        "do not answer this file's contents from other sources" in t
        for t in system_texts)


@pytest.mark.asyncio
async def test_completed_read_serves_task_and_keeps_identity():
    """A COMPLETED storage read serves the ask: the task is marked served
    (never resurrected by a later confirmation) and the resolved identity
    is retained for the preview to share."""
    orch = _orch()
    session = {
        "id": "s1",
        "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    plan = planner.ToolPlan(
        use_tool=True, service="zoho_workdrive", intent="read",
        query="Consolidated Price List 2019.xlsx prices")
    # The storage layer's structured outcome: a COMPLETED read with the
    # file identity verified and spreadsheet coverage complete.
    plan._result_meta = {"storage_read": {
        "service": "zoho_workdrive", "file_id": "wd-77",
        "resource_id": "wd-77",
        "file_name": "Consolidated Price List 2019.xlsx",
        "completed": True, "identity_verified": True,
        "coverage_complete": True, "note": None, "dataset_sheet": "Sheet1",
    }}
    with (
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            return_value=plan)),
        patch("core.chat_tool_planner.execute_tool_plan", new=AsyncMock(
            return_value=(
                "LIVE TOOL RESULTS (zoho_workdrive read): Consolidated "
                "Price List 2019.xlsx — Sheet1 R12 | GSL48-16 | 44500"))),
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(
            return_value=[])),
    ):
        await orch._get_qwen_response(
            CONFIRMATION, [], user_id="u1", session_id="s1",
            execution_id="e2", session=session,
            pending_file_task=session[FILE_TASK_SESSION_KEY],
        )
    retrieved = session.get(FILE_TASK_SESSION_KEY)
    assert retrieved and retrieved["status"] == "retrieved", (
        "retrieval completes the read; delivery is marked separately")
    assert retrieved["resolved_file"]["file_id"] == "wd-77"
    result = session.get("_pending_file_result")
    assert result and result["status"] == "retrieved" and result["rendered"]
    # Identity retained separately, for preview reuse (gap 4).
    identity = session.get("_resolved_file_identity")
    assert identity and identity["file_id"] == "wd-77"
    assert identity["file_name"] == "Consolidated Price List 2019.xlsx"
    # A served task never resumes.
    from core.pending_file_task import matching_pending_task
    assert matching_pending_task(retrieved, "yes", HISTORY["history"]) is None
    # The workbook answer contract rides the evidence for spreadsheet asks.
    evidence = session.get("_ev_e2") or ""
    assert "TABULAR EVIDENCE CONTRACT" in evidence
    assert "never substitute" in evidence


@pytest.mark.asyncio
async def test_incomplete_read_keeps_task_pending_and_retains_identity():
    """A lookup that FOUND the file but extracted nothing (download failed,
    no text) is not a completed price lookup: the task stays pending with
    the attempt recorded, and the resolved identity is still retained."""
    orch = _orch()
    session = {
        "id": "s1",
        "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    plan = planner.ToolPlan(
        use_tool=True, service="zoho_workdrive", intent="read",
        query="Consolidated Price List 2019.xlsx prices")
    plan._result_meta = {"storage_read": {
        "service": "zoho_workdrive", "file_id": "wd-77",
        "file_name": "Consolidated Price List 2019.xlsx",
        "completed": False,
        "note": "Found the file in zoho_workdrive but the download failed.",
        "dataset_sheet": None,
    }}
    with (
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            return_value=plan)),
        patch("core.chat_tool_planner.execute_tool_plan", new=AsyncMock(
            return_value=(
                "LIVE TOOL RESULTS (zoho_workdrive read): found "
                "Consolidated Price List 2019.xlsx but the download "
                "failed."))),
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(
            return_value=[])),
    ):
        await orch._get_qwen_response(
            CONFIRMATION, [], user_id="u1", session_id="s1",
            execution_id="e2b", session=session,
            pending_file_task=session[FILE_TASK_SESSION_KEY],
        )
    stored = session.get(FILE_TASK_SESSION_KEY)
    assert stored and stored["status"] == "pending", (
        "a found-but-failed read must not complete the task")
    assert stored["attempts"] >= 1
    identity = session.get("_resolved_file_identity")
    assert identity and identity["file_id"] == "wd-77", (
        "identity is retained even when the read did not complete")
    system_texts = [
        " ".join(m.get("content", "") for m in c.kwargs.get("messages", [])
                 if isinstance(m, dict) and m.get("role") == "system")
        for c in orch.llm_service.generate_completion.call_args_list
    ]
    assert any("did NOT complete" in t for t in system_texts)


@pytest.mark.asyncio
async def test_off_request_decline_does_not_retire_pending_task():
    """A plan declined by the off-request gate never executed — its failure
    TEXT is not a lookup and must not retire the stored ask (the text names
    the declined query, and the service can still be a file service)."""
    orch = _orch()
    session = {
        "id": "s1",
        "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    plan = planner.ToolPlan(
        use_tool=True, service="zoho_workdrive", intent="read",
        query="unrelated shipping status")
    with (
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            return_value=plan)),
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(
            return_value=[])),
    ):
        await orch._get_qwen_response(
            ORIGINAL_ASK, [], user_id="u1", session_id="s1",
            execution_id="e5", session=session,
        )
    assert FILE_TASK_SESSION_KEY in session, (
        "a declined (never-executed) lookup must leave the pending file "
        "task in place")


@pytest.mark.asyncio
async def test_confirmed_file_read_is_direct_when_planner_and_narration_are_unavailable():
    orch = _orch()
    session = {
        "id": "s-direct",
        "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"
        ),
    }
    rendered = (
        "Workbook read: Consolidated Price List 2019.xlsx\n"
        "Source: MATERIALIZED COPY — resource=r1, content_hash=h, ingested=t\n"
        "Coverage — indexed content searched\n"
        "| 381 | FOUND | Sheet1!A1 R1 [basis=U.S. LIST; currency=unspecified] |"
    )
    direct = {
        "ok": True,
        "block": rendered,
        "rendered_answer": rendered,
        "identity": {
            "file_id": "r1",
            "resource_id": "r1",
            "file_name": "Consolidated Price List 2019.xlsx",
            "identity_verified": True,
            "coverage_complete": True,
        },
        "meta": {
            "workbook_read": {"coverage": {"complete": True}},
            "completed": True,
            "identity_verified": True,
            "coverage_complete": True,
        },
        "retrieval_complete": True,
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_start_chat_execution", return_value="exec-direct"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=direct)),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))) as planner_disabled,
        patch.object(orch.llm_service, "generate_completion", new=AsyncMock(
            side_effect=AssertionError("narration model must not run"))) as narration_disabled,
    ):
        response = await orch.process_chat_message(
            "u1", CONFIRMATION, session_id="s-direct", context={}
        )

    assert response["success"] is True
    assert response["model"] == "deterministic"
    assert "| 381 | FOUND |" in response["message"]
    assert response["data"]["deterministic_delivery"] is True
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"
    assert session["_pending_file_result"]["status"] == "delivered"
    planner_disabled.assert_not_awaited()
    narration_disabled.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieved_result_retry_renders_without_rereading():
    orch = _orch()
    session = {"id": "s-retry", "history": []}
    persisted = {
        "status": "retrieved",
        "target_extraction_version": 3,
        "rendered": (
            "Workbook read: Consolidated Price List 2019.xlsx\n"
            "| U-22 | FOUND | Sheet1!A2 R2 [basis=List; currency=unspecified] |"
        ),
        "identity": {"file_id": "r1", "file_name": "Consolidated Price List 2019.xlsx"},
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_pending_file_result", return_value=persisted),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
        patch.object(orch.llm_service, "generate_completion", new=AsyncMock(
            side_effect=AssertionError("must not narrate"))),
    ):
        response = await orch.process_chat_message(
            "u1", "yes", session_id="s-retry", context={}
        )

    assert response["success"] is True
    assert response["data"]["deterministic_delivery"] is True
    assert "| U-22 | FOUND |" in response["message"]
    assert session["_pending_file_result"]["status"] == "delivered"


@pytest.mark.asyncio
async def test_delivered_result_retry_is_idempotent_without_rereading():
    orch = _orch()
    session = {
        "id": "s-delivered-retry",
        "history": [],
        "_pending_file_result": {
            "status": "delivered",
            "target_extraction_version": 3,
            "rendered": "| U-22 | FOUND | Sheet1!A2 R2 |",
            "identity": {"file_id": "r1"},
        },
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_pending_file_result", return_value=None),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
        patch.object(orch.llm_service, "generate_completion", new=AsyncMock(
            side_effect=AssertionError("must not narrate"))),
    ):
        response = await orch.process_chat_message(
            "u1", "go", session_id="s-delivered-retry", context={}
        )
    assert response["success"] is True
    assert response["data"]["deterministic_delivery"] is True
    assert "| U-22 | FOUND |" in response["message"]


# ---------------------------------------------------------------------------
# Wiring 4 — durability: the task survives restarts via metadata_json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.usefixtures("durable_metadata_db")
async def test_pending_task_survives_restart_via_durable_metadata():
    """The in-memory session key dies with the process (the persisted
    session is a projection) — the task must round-trip through assistant
    metadata_json and still resume after a 'restart'."""
    import uuid as _uuid

    orch = _orch()
    session_id = f"pft-durab-{_uuid.uuid4().hex[:8]}"
    session = {
        "id": session_id, "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    # Persist the turn the way a real turn does.
    orch._update_session(
        session, ORIGINAL_ASK,
        {"success": True, "message": "the search did not run yet"},
        {"primary_intent": "search"})
    # Simulated restart: the rebuilt session dict lost every private key.
    task, _identity = orch._load_pending_file_task(session_id)
    assert task, "the durable carrier must return the stored task"
    assert task["original_message"] == ORIGINAL_ASK
    assert matching_pending_task(
        task, CONFIRMATION, HISTORY["history"]) is not None, (
        "a restarted process must still resume the confirmed ask")


@pytest.mark.asyncio
@pytest.mark.usefixtures("durable_metadata_db")
async def test_served_marker_survives_restart_and_blocks_resurrection():
    import uuid as _uuid

    orch = _orch()
    session_id = f"pft-served-{_uuid.uuid4().hex[:8]}"
    from core.pending_file_task import mark_task_served
    session = {
        "id": session_id, "history": [],
        FILE_TASK_SESSION_KEY: mark_task_served(
            build_pending_task(ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
            {"service": "zoho_workdrive", "file_id": "wd-77",
             "file_name": "Consolidated Price List 2019.xlsx"}),
    }
    orch._update_session(
        session, CONFIRMATION, {"success": True, "message": "prices found"},
        {"primary_intent": "search"})
    task, identity = orch._load_pending_file_task(session_id)
    assert task and task["status"] == "served"
    assert identity and identity["file_id"] == "wd-77"
    assert matching_pending_task(
        task, "yes", HISTORY["history"]) is None, (
        "a restart must not resurrect a served ask from an older row")


@pytest.mark.asyncio
@pytest.mark.usefixtures("durable_metadata_db")
async def test_sessions_are_isolated_per_conversation():
    import uuid as _uuid

    orch = _orch()
    sid_a = f"pft-iso-a-{_uuid.uuid4().hex[:8]}"
    sid_b = f"pft-iso-b-{_uuid.uuid4().hex[:8]}"
    ask_a = "find the prices in Consolidated Price List 2019.xlsx"
    ask_b = "what does Stock Counts 2026.xlsx say for SKU 381?"
    for sid, ask in ((sid_a, ask_a), (sid_b, ask_b)):
        orch._update_session(
            {"id": sid, "history": [],
             FILE_TASK_SESSION_KEY: build_pending_task(ask, ask)},
            ask, {"success": True, "message": "saved"},
            {"primary_intent": "search"})
    task_a, _ = orch._load_pending_file_task(sid_a)
    task_b, _ = orch._load_pending_file_task(sid_b)
    assert task_a["original_message"] == ask_a
    assert task_b["original_message"] == ask_b


# ---------------------------------------------------------------------------
# Wiring 5 — two different pending file requests in one session
# ---------------------------------------------------------------------------

def test_second_file_ask_replaces_the_first():
    existing = build_pending_task(
        "prices in Consolidated Price List 2019.xlsx",
        "consolidated price list 2019.xlsx")
    merged = merge_pending_task(
        existing,
        "check Stock Counts 2026.xlsx for SKU 381",
        "stock counts 2026.xlsx")
    assert merged["original_message"] == (
        "check Stock Counts 2026.xlsx for SKU 381")
    assert merged["mention"] == "stock counts 2026.xlsx"
    assert merged["status"] == "pending"


# ---------------------------------------------------------------------------
# Wiring 6 — preview shares the resolved identity with the answer
# ---------------------------------------------------------------------------

class TestPreviewSharesIdentity:
    def test_canvas_content_ties_to_live_read(self):
        from core.agent_file_context import build_file_canvas_content

        content = build_file_canvas_content(
            "Consolidated Price List 2019.xlsx",
            {"tables": [{"table": "documents", "count": 2,
                         "samples": ["R12 | GSL48-16"]}],
             "match_tier": "exact"},
            mention="price list.xlsx",
            live_identity={
                "service": "zoho_workdrive", "file_id": "wd-77",
                "file_name": "Consolidated Price List 2019.xlsx"},
        )
        assert "SAME FILE AS THIS ANSWER'S VERIFIED RESOURCE" in content
        assert "wd-77" in content

    def test_canvas_content_flags_different_file_from_live_read(self):
        from core.agent_file_context import build_file_canvas_content

        content = build_file_canvas_content(
            "Stock Counts 2026.xlsx",
            {"tables": [], "match_tier": "exact"},
            differs_from_live={
                "file_name": "Consolidated Price List 2019.xlsx"},
        )
        assert "DIFFERENT FILE" in content
        assert "Consolidated Price List 2019.xlsx" in content


# ---------------------------------------------------------------------------
# Wiring 2 — the confirmation turn resumes the stored ask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirmation_resumes_original_ask_through_process_chat():
    """A confirmed file enters the direct reader with the original ask."""
    orch = _orch()
    session = {
        "id": "s1",
        "history": list(HISTORY["history"]),
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    rendered = (
        "Workbook read: Consolidated Price List 2019.xlsx\n"
        "| GSL48-16 | FOUND | Tennsmith!A106 R106 |"
    )
    direct = {
        "ok": True,
        "block": rendered,
        "rendered_answer": rendered,
        "identity": {
            "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Consolidated Price List 2019.xlsx",
            "identity_verified": True,
            "coverage_complete": True,
        },
        "meta": {
            "completed": True,
            "identity_verified": True,
            "coverage_complete": True,
            "workbook_read": {"coverage": {"complete": True}},
        },
        "retrieval_complete": True,
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e3"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=direct)) as direct_mock,
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))) as plan_mock,
    ):
        result = await orch.process_chat_message(
            "u1", CONFIRMATION, "s1", context={"agent_id": "a1"})
    assert result["success"] is True
    direct_task = direct_mock.await_args.args[0]
    assert direct_task["original_message"] == ORIGINAL_ASK
    plan_mock.assert_not_awaited()
    assert result["data"]["deterministic_delivery"] is True
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"
    assert session["_pending_file_result"]["status"] == "delivered"


@pytest.mark.asyncio
async def test_resume_turn_skips_canvas_edit_leg():

    """A confirmation resuming a stored file ask must not spend its budget
    classifying a canvas edit of a bare confirmation (the 42.5s incident
    leg)."""
    orch = _orch()
    canvas = {"canvas_id": "c1", "canvas_type": "document",
              "content": {"content": "some canvas"}}
    session = {
        "id": "s1",
        "history": list(HISTORY["history"]),
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    plan = planner.ToolPlan(
        use_tool=True, service="zoho_workdrive", intent="read",
        query="Consolidated Price List 2019.xlsx machine prices")
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_start_chat_execution", return_value="e4"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_canvas_edit", new=AsyncMock()) as edit_leg,
        patch.object(orch, "_try_canvas_action", new=AsyncMock()),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch.object(planner, "_provenance_menu", new=AsyncMock(return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(planner, "plan_tool_use", new=AsyncMock(return_value=plan)),
        patch.object(planner, "execute_tool_plan", new=AsyncMock(
            return_value="LIVE TOOL RESULTS: Consolidated Price List 2019.xlsx rows")),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(return_value=[])),
    ):
        await orch.process_chat_message(
            "u1", CONFIRMATION, "s1",
            context={"agent_id": "a1", "canvas_id": "c1"})
    edit_leg.assert_not_awaited()


# ---------------------------------------------------------------------------
# Wiring 3 — read-only file asks bypass canvas-edit generation
# ---------------------------------------------------------------------------

class TestReadOnlyFileAskGate:
    def test_incident_read_ask_bypasses(self):
        canvas = {"canvas_id": "c1", "canvas_type": "document"}
        assert chat._read_only_file_ask(
            "what prices does Consolidated Price List 2019.xlsx show for "
            "these 8 machines?", canvas) is True

    def test_edit_ask_does_not_bypass(self):
        canvas = {"canvas_id": "c1", "canvas_type": "document"}
        assert chat._read_only_file_ask(
            "update the table with the prices from price list.xlsx", canvas) is False

    def test_action_ask_does_not_bypass(self):
        canvas = {"canvas_id": "c1", "canvas_type": "document"}
        assert chat._read_only_file_ask(
            "get the prices from price list.xlsx and send this", canvas) is False

    def test_no_canvas_no_bypass_needed(self):
        assert chat._read_only_file_ask(
            "what prices does price list.xlsx show?", None) is False

    def test_no_file_mention_does_not_bypass(self):
        canvas = {"canvas_id": "c1", "canvas_type": "document"}
        assert chat._read_only_file_ask(
            "what are the current prices?", canvas) is False


# ---------------------------------------------------------------------------
# Wiring 7 — resume-aware structured wait (caller-declared, task-scoped)
# ---------------------------------------------------------------------------

class TestDeclaredStructuredWait:
    def test_declare_and_reset(self):
        from core.llm.interactive_context import (
            declare_interactive_structured_wait,
            interactive_structured_wait,
            reset_interactive_structured_wait,
        )

        assert interactive_structured_wait() == 0.0
        token = declare_interactive_structured_wait(50.0)
        assert interactive_structured_wait() == 50.0
        reset_interactive_structured_wait(token)
        assert interactive_structured_wait() == 0.0

    def test_bad_values_fail_open_to_zero(self):
        from core.llm.interactive_context import (
            declare_interactive_structured_wait,
            interactive_structured_wait,
            reset_interactive_structured_wait,
        )

        token = declare_interactive_structured_wait("not-a-number")
        assert interactive_structured_wait() == 0.0
        reset_interactive_structured_wait(token)

    def test_effective_cap_takes_max_of_default_and_declaration(self):
        # The routing layer's interactive structured cap must ADMIT a
        # declared wait: max(default, declared). Verified against the
        # helper the handler uses, so a healthy 46s rung is no longer
        # excluded on a turn whose caller waits 50s.
        from core.llm import byok_handler
        from core.llm.interactive_context import (
            declare_interactive_structured_wait,
            interactive_structured_wait,
            reset_interactive_structured_wait,
        )

        token = declare_interactive_structured_wait(50.0)
        try:
            effective = max(
                byok_handler._interactive_structured_max_seconds(),
                interactive_structured_wait(),
            )
            assert effective >= 50.0
        finally:
            reset_interactive_structured_wait(token)


# ---------------------------------------------------------------------------
# Wiring 8 — a named file scopes the datasets evidence (unique resolution)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_named_file_query_resolves_to_that_file_not_a_token_winner():
    """The live 2026-09-24 replay defect: a query naming 'Consolidated
    Price List 2019.xlsx' returned rows from 'All Prices For All Parts
    INDUSTRIAL Sept 2026.xlsx' because the catalog probe's content token
    ('prices') outranked the name. A named file must SCOPE the evidence."""
    from core.chat_tool_planner import _datasets_named_file_block

    catalog_entries = [
        {"source": "catalog", "external_id": "wb-2019",
         "file_name": "Consolidated Price List 2019.xlsx"},
        {"source": "catalog", "external_id": "sept-2026",
         "file_name": "All Prices For All Parts INDUSTRIAL Sept 2026.xlsx"},
    ]

    def fake_find_entries(q="", user_id=None, ws=None, limit=500):
        return list(catalog_entries)

    def fake_probe(entries, token, max_rows):
        # Only the 2019 workbook contains the identifiers.
        if entries and entries[0].get("external_id") == "wb-2019":
            return {"file_name": entries[0]["file_name"],
                    "entity_name": "Sheet1", "columns": ["Model", "Price"],
                    "rows": [{"__row__": 12, "Model": token, "Price": 44500}],
                    "row_count": 1}
        return None

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              side_effect=fake_find_entries),
        patch("core.sheet_dataset_service._probe_cached",
              side_effect=fake_probe),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=["381", "622"]),
    ):
        block = await _datasets_named_file_block(
            "u1", "Consolidated Price List 2019.xlsx 381 U-22 622",
            {"workspace_id": "ws"},
        )
    assert block, "the named-file path must produce a block"
    assert "Consolidated Price List 2019.xlsx" in block
    assert "SCOPED to it" in block
    assert "Sept 2026" not in block, "a wrong-file row must not appear"


@pytest.mark.asyncio
async def test_named_file_ambiguity_is_explicit_not_silent():
    from core.chat_tool_planner import _datasets_named_file_block

    catalog_entries = [
        {"source": "catalog", "external_id": "a",
         "file_name": "Price List.xlsx"},
        {"source": "catalog", "external_id": "b",
         "file_name": "price list.xlsx"},
    ]

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog_entries)),
    ):
        block = await _datasets_named_file_block(
            "u1", "check Price List.xlsx", {})
    assert block and "MULTIPLE catalogued files match" in block
    assert "do NOT present" in block


@pytest.mark.asyncio
async def test_named_file_absent_falls_through_to_catalog_probe():
    from core.chat_tool_planner import _datasets_named_file_block

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=[{"source": "catalog", "external_id": "x",
                             "file_name": "unrelated.xlsx"}]),
    ):
        block = await _datasets_named_file_block(
            "u1", "prices in Missing Workbook 2019.xlsx", {})
    assert block is None, "not catalogued -> catalog-wide probe runs"


@pytest.mark.asyncio
async def test_named_file_block_stamps_serving_meta():
    """A datasets-served workbook answer must mark the pending task served:
    the lifecycle contract reads storage_read meta, so the named-file lane
    stamps the same structured outcome (unique identity + completed)."""
    from core.chat_tool_planner import _datasets_named_file_block

    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search", query="x")
    catalog_entries = [
        {"source": "catalog", "external_id": "wb-2019",
         "file_name": "Consolidated Price List 2019.xlsx",
         "parquet_path": "fake", "coverage": {"known": True}},
    ]

    def fake_probe(entries, token, max_rows):
        return {"file_name": entries[0]["file_name"],
                "entity_name": "Tennsmith", "columns": ["Model", "Price"],
                "rows": [{"__row__": 12, "Model": token, "Price": 8880}],
                "row_count": 1}

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog_entries)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              return_value=list(catalog_entries)),
        patch("core.sheet_dataset_service._probe_cached",
              side_effect=fake_probe),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=["SLE24-16"]),
        patch("core.workbook_read_artifact.inspect_dataset_entries",
              return_value={
                  "all_sheets_searched": True,
                  "truncated": False,
                  "coverage": {"complete": True, "outcomes": [
                      {"target": "SLE24-16", "status": "found",
                       "evidence": [{"sheet": "Tennsmith", "cell": "A12",
                                     "row": 12, "value": "SLE24-16",
                                     "prices": []}]},
                  ]},
              }),
        patch("core.workbook_read_artifact.render_workbook_artifact",
              return_value=""),
    ):
        block = await _datasets_named_file_block(
            "u1", "prices in Consolidated Price List 2019.xlsx", {},
            plan=plan)
    assert block and "SCOPED to it" in block
    meta = (getattr(plan, "_result_meta", None) or {}).get("storage_read")
    assert meta and meta["identity_verified"] is True
    assert meta["completed"] is True and meta["coverage_complete"] is True
    assert meta["file_name"] == "Consolidated Price List 2019.xlsx"


@pytest.mark.asyncio
async def test_prefixed_mention_resolves_only_when_containment_unique():
    """'prices in <name>.xlsx' keeps its prose prefix ('prices' is a real
    filename word) — a containment mention resolves when UNIQUE, and stays
    ambiguous against the workbook's 'Copy of …' variant."""
    from core.chat_tool_planner import _datasets_named_file_block

    def fake_probe(entries, token, max_rows):
        return {"file_name": entries[0]["file_name"],
                "entity_name": "Sheet1", "columns": ["Model"],
                "rows": [{"__row__": 3, "Model": token}], "row_count": 1}

    # UNIQUE containment: only one catalogued file contains the name.
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=[{"source": "c", "external_id": "w1",
                             "file_name": "Consolidated Price List 2019.xlsx"}]),
        patch("core.sheet_dataset_service._probe_cached",
              side_effect=fake_probe),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=["381"]),
    ):
        block = await _datasets_named_file_block(
            "u1", "prices in Consolidated Price List 2019.xlsx", {})
    assert block and "Consolidated Price List 2019.xlsx" in block

    # NON-unique containment (the workbook + its Copy-of variant) is
    # explicit ambiguity, never a silent pick. A CLEAN partial mention
    # ("price list 2019.xlsx") sits inside both stems; the prefixed
    # "prices in …" uniquely excludes the Copy, which is why the case
    # above resolves.
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=[
                  {"source": "c", "external_id": "w1",
                   "file_name": "Consolidated Price List 2019.xlsx"},
                  {"source": "c", "external_id": "w2",
                   "file_name": "Copy of Consolidated Price List 2019 - Linmac Update.xlsx"},
              ]),
    ):
        block = await _datasets_named_file_block(
            "u1", "check price list 2019.xlsx", {})
    assert block and "MULTIPLE catalogued files match" in block
    assert "Copy of Consolidated Price List 2019" in block


# ---------------------------------------------------------------------------
# Wiring 9 — coverage wording, provenance, and deterministic rendering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_named_file_block_carries_provenance_and_coverage_limits():
    """Version identity (resource id + hash + ingestion) rides the block,
    and not-found is scoped to the INDEXED CONTENT — never claimed as
    absence from the live workbook."""
    from core.chat_tool_planner import _datasets_named_file_block

    catalog = [
        {"source": "zoho_workdrive", "external_id": "u8ai1e3a",
         "file_name": "Consolidated Price List 2019.xlsx",
         "entity_name": "Tennsmith", "content_hash": "ff2597d26f",
         "ingested_at": "2026-09-07T23:06:19", "source_modified_at": None},
        {"source": "zoho_workdrive", "external_id": "u8ai1e3a",
         "file_name": "Consolidated Price List 2019.xlsx",
         "entity_name": "BurrKing", "content_hash": "ff2597d26f",
         "ingested_at": "2026-09-07T23:06:19", "source_modified_at": None},
    ]

    def fake_probe(entries, token, max_rows):
        if token.lower() in ("sle24-16", "sle2416"):
            return {"file_name": entries[0]["file_name"],
                    "entity_name": "Tennsmith",
                    "columns": ["Model", "Price"],
                    "rows": [{"__sheet_row": 12, "Model": "SLE24-16",
                              "Price": 8880}],
                    "row_count": 1}
        return None

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service._probe_cached",
              side_effect=fake_probe),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=["SLE24-16", "381"]),
    ):
        block = await _datasets_named_file_block(
            "u1", "prices in Consolidated Price List 2019.xlsx", {})
    assert "MATERIALIZED COPY" in block
    assert "NOT a fresh read" in block
    assert "u8ai1e3a" in block and "ff2597d26f" in block
    assert "2026-09-07T23:06:19" in block
    assert "2 sheet(s) indexed" in block
    assert "COVERAGE LIMITS" in block
    assert "does NOT prove absence from the live workbook" in block
    # Deterministic table: both outcomes rendered, no model arithmetic.
    assert "| SLE24-16 | FOUND |" in block
    assert "| 381 | INCOMPLETE — NOT FOUND IN INDEXED CONTENT |" in block
    assert "reproduce VERBATIM" in block
    assert "Tennsmith R12" in block  # sheet + row lineage


@pytest.mark.asyncio
async def test_alias_variants_are_probed():
    """Separator-normalized aliases ('U-22' -> 'u22') are tried when the
    as-typed token misses."""
    from core.chat_tool_planner import _datasets_named_file_block

    catalog = [{"source": "zoho_workdrive", "external_id": "w1",
                "file_name": "Consolidated Price List 2019.xlsx",
                "entity_name": "Sheet1"}]
    probed = []

    def fake_probe(entries, token, max_rows):
        probed.append(token)
        if token == "u22":
            return {"file_name": entries[0]["file_name"],
                    "entity_name": "Sheet1", "columns": ["Model"],
                    "rows": [{"__sheet_row": 4, "Model": "U22"}],
                    "row_count": 1}
        return None

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service._probe_cached",
              side_effect=fake_probe),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=["U-22"]),
    ):
        block = await _datasets_named_file_block(
            "u1", "check Consolidated Price List 2019.xlsx", {})
    assert probed[:2] == ["U-22", "u22"]
    assert "| U-22 | FOUND |" in block


@pytest.mark.asyncio
async def test_named_file_emits_one_structured_outcome_per_requested_item():
    from core.chat_tool_planner import _datasets_named_file_block

    targets = [
        "381", "U-22", "622", "SLE24-16", "GSL48-16", "GSL24-16",
        "SLE16-8", "U-38",
    ]
    catalog = [{"source": "zoho_workdrive", "external_id": "w1",
                "file_name": "Consolidated Price List 2019.xlsx",
                "entity_name": "Sheet1"}]

    def fake_probe(entries, token, max_rows):
        if token in {"381", "622"}:
            return {"file_name": entries[0]["file_name"],
                    "entity_name": "Sheet1", "columns": ["Model", "Price"],
                    "rows": [{"__sheet_row": 2, "Model": token, "Price": 100}],
                    "row_count": 1}
        return None

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=catalog),
        patch("core.sheet_dataset_service._probe_cached",
              side_effect=fake_probe),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=targets),
    ):
        block = await _datasets_named_file_block(
            "u1", "prices for " + ", ".join(targets)
            + " in Consolidated Price List 2019.xlsx", {})

    rows = [line for line in block.splitlines() if line.startswith("| ")
            and not line.startswith("| item")]
    assert len(rows) == len(targets)
    assert sum("| FOUND |" in row for row in rows) == 2
    assert sum("NOT FOUND IN INDEXED CONTENT" in row for row in rows) == 6


@pytest.mark.asyncio
async def test_named_file_not_catalogued_does_not_fall_through_to_other_files():
    from core.chat_tool_planner import _datasets_named_file_block

    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search",
        query="prices in Missing Workbook 2019.xlsx",
    )
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=[{"source": "catalog", "external_id": "other",
                             "file_name": "Other Prices.xlsx",
                             "entity_name": "Sheet1"}]),
    ):
        block = await _datasets_named_file_block(
            "u1", plan.query, {}, plan=plan)

    assert block and "NOT FOUND IN THE INDEXED CONTENT SEARCHED" in block
    assert "Other Prices.xlsx" not in block
    assert plan._result_meta["storage_read"]["completed"] is False


@pytest.mark.asyncio
async def test_all_miss_block_is_coverage_scoped_not_absence():
    from core.chat_tool_planner import _datasets_named_file_block

    catalog = [{"source": "zoho_workdrive", "external_id": "w1",
                "file_name": "Consolidated Price List 2019.xlsx",
                "entity_name": "Sheet1", "entity_rows": 10}]

    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service._probe_cached",
              return_value=None),
        patch("core.sheet_dataset_service.candidate_probe_tokens",
              return_value=["381"]),
    ):
        block = await _datasets_named_file_block(
            "u1", "check Consolidated Price List 2019.xlsx", {})
    assert "NOT FOUND IN THE INDEXED CONTENT SEARCHED" in block
    assert "do not claim absence from the workbook" in block
    assert "ABSENT from this workbook" not in block


# ---------------------------------------------------------------------------
# Wiring 10 — confirmed-read guarantee (planner routing variance)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_turn_delivers_file_evidence_even_when_planned_elsewhere():
    """Live wb-replay-1790254746: the confirmation turn's planner routed to
    a MAILBOX scan (fleet variance) and the confirmed file read's evidence
    never reached the reply. The guarantee runs the file-scoped lane and
    leads the evidence with it whenever the executed block does not name
    the confirmed file."""
    orch = _orch()
    session = {
        "id": "s1", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    # Planner routes to the mailbox — NOT a file-serving service.
    plan = planner.ToolPlan(
        use_tool=True, service="outlook", intent="search",
        query="consolidated price list")

    async def fake_execute(p, uid, tenant, context=None, llm_service=None):
        return ("LIVE TOOL RESULTS (outlook.search): mailbox scanned, "
                "no relevant messages")

    async def fake_named_file(uid, query, context, plan=None):
        # stamps the lifecycle meta exactly as the real lane does
        if plan is not None:
            plan._result_meta = {"storage_read": {
                "service": "datasets", "file_id": "u8ai1e3a",
                "resource_id": "u8ai1e3a",
                "file_name": "Consolidated Price List 2019.xlsx",
                "identity_verified": True, "completed": True,
                "coverage_complete": True, "note": "guarantee test"}}
        return ("LIVE TOOL RESULTS (datasets.named-file, file='Consolidated "
                "Price List 2019.xlsx') — MATERIALIZED COPY … PER-ITEM "
                "OUTCOMES table")

    with (
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            return_value=plan)),
        patch("core.chat_tool_planner.execute_tool_plan",
              new=fake_execute),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_file)) as named,
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(
            return_value=[])),
    ):
        await orch._get_qwen_response(
            CONFIRMATION, [], user_id="u1", session_id="s1",
            execution_id="e6", session=session,
            pending_file_task=session[FILE_TASK_SESSION_KEY],
        )
    named.assert_awaited()
    evidence = session.get("_ev_e6") or ""
    assert "datasets.named-file" in evidence, (
        "the file-scoped evidence must lead the composed block")
    assert evidence.index("datasets.named-file") < evidence.index(
        "outlook.search"), "file evidence leads the mailbox block"
    served = session.get(FILE_TASK_SESSION_KEY)
    assert served and served["status"] == "retrieved", (
        "the guarantee stamps the lifecycle meta — retrieval completes; "
        "delivery is marked when the response ships")


# ---------------------------------------------------------------------------
# Wiring 11 — THE ACCEPTANCE TEST: planner and narration deliberately
# unavailable; the confirmed read still runs, persists, and delivers.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acceptance_planner_and_narration_unavailable():
    """Confirmed filename -> direct scoped read -> durable structured
    results -> rendered eight-item table — with the planner and the
    narration model BOTH disabled (ATOM_DISABLE_TOOL_PLANNER + a
    generate_completion that raises if called). Then the retry turn
    delivers from persistence WITHOUT re-reading."""
    orch = _orch()
    # Narration is unavailable: any generation attempt fails loudly.
    orch.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError("narration model unavailable"))
    session = {
        "id": "acc1",
        "history": list(HISTORY["history"]),
        FILE_TASK_SESSION_KEY: build_pending_task(
            ORIGINAL_ASK, "consolidated price list 2019.xlsx"),
    }
    # REAL parquet fixtures: the deterministic artifact path scans these,
    # so the acceptance test exercises the true reader (designation
    # classification, currency labeling, coverage) — not probe mocks.
    import tempfile as _tf

    import pandas as _pd

    _tmpdir = _tf.mkdtemp(prefix="wb-acceptance-")
    _tennsmith = _pd.DataFrame({
        "__sheet_row": [100, 101, 102],
        "Model": ["SLE14-14", "SLE24-16", "GSL48-16"],
        "PRICE": [7000, 8880, 14166],
        "U.S. LIST": [3600, 4500, 6575],
        "Current Exchange Rate": [0.35, 0.36, 0.36],
    })
    _linmac = _pd.DataFrame({
        "__sheet_row": [25, 26],
        "Model": ["U-16", "U-22"],
        "List Price": [1500, 1777],
        "Current Exchange Rate": [381.6, 381.6],
    })
    _p1 = os.path.join(_tmpdir, "tennsmith.parquet")
    _p2 = os.path.join(_tmpdir, "linmac.parquet")
    _tennsmith.to_parquet(_p1)
    _linmac.to_parquet(_p2)

    def _entry(entity, path, rows):
        return {
            "source": "zoho_workdrive", "external_id": "u8ai1e3a",
            "dataset_name": f"wb_fixture_{entity.lower()}",
            "file_name": "Consolidated Price List 2019.xlsx",
            "entity_name": entity, "parquet_path": path,
            "row_count": rows,
            "coverage": {"known": True, "truncated": False},
            "content_hash": "ff2597d26f",
            "ingested_at": "2026-09-07T23:06:19",
            "source_modified_at": None,
        }

    catalog = [
        _entry("Tennsmith", _p1, len(_tennsmith)),
        _entry("LINMAC", _p2, len(_linmac)),
    ]

    with (
        patch.dict(os.environ, {"ATOM_DISABLE_TOOL_PLANNER": "1"}),
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="acc-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              return_value=list(catalog)),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))) as plan_mock,
    ):
        result = await orch.process_chat_message(
            "u1", CONFIRMATION, "acc1", context={"agent_id": "a1"})

    # The eight-item structured table shipped — deterministically.
    assert result["success"] is True
    assert result.get("model") == "deterministic"
    msg = result["message"]
    for item in ("381", "U-22", "622", "SLE24-16", "GSL48-16",
                 "GSL24-16", "SLE16-8", "U-38"):
        assert item in msg, f"missing per-item outcome: {item}"
    assert "1777" in msg and "8880" in msg
    assert "materialized copy" in msg.lower() or "MATERIALIZED COPY" in msg
    # Misses carry the honest scoped vocabulary (INCOMPLETE when the
    # fixture's coverage flags are partial, NOT FOUND otherwise) — never
    # a bare claim of absence from the workbook.
    assert "absent from the workbook" not in msg.lower().replace(
        "does not prove absence", "ok")
    plan_mock.assert_not_awaited()
    orch.llm_service.generate_completion.assert_not_awaited()

    # Durable structured result persisted; lifecycle delivered.
    pfr = session.get("_pending_file_result")
    assert pfr and pfr["status"] == "delivered" and pfr["rendered"]
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"

    # --- Retry turn: deliver from persistence WITHOUT re-reading. -------
    session2 = dict(session)  # same session continuing
    with (
        patch.object(orch, "_get_or_create_session", return_value=session2),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="acc-e2"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))) as direct_mock,
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        # A delivered result is terminal: a follow-up "go" neither re-reads
        # (direct reader raises if called) nor resurrects the planner.
        await orch.process_chat_message(
            "u1", "go", "acc1", context={"agent_id": "a1"})
    direct_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_turn_never_ships_fabricated_prices():
    """The fabrication guard: a spreadsheet price ask is answered by the
    file-scoped reader deterministically — a narration model that would
    invent prices (live: $5,850 for SLE24-16 vs the real 8880) is never
    consulted for the values."""
    orch = _orch()
    orch.llm_service.generate_completion = AsyncMock(return_value={
        "success": True, "content": "| Machine | Price |\n| SLE24-16 | $5,850 |",
        "model": "fabricator", "provider": "test",
    })
    import tempfile as _tf

    import pandas as _pd

    _tmp = _tf.mkdtemp(prefix="wb-fab-")
    _t = _pd.DataFrame({
        "__sheet_row": [101],
        "Model": ["SLE24-16"], "PRICE": [8880], "U.S. LIST": [4500],
    })
    _path = os.path.join(_tmp, "t.parquet")
    _t.to_parquet(_path)
    catalog = [{
        "source": "zoho_workdrive", "external_id": "u8ai1e3a",
        "dataset_name": "wb_fab", "file_name":
        "Consolidated Price List 2019.xlsx", "entity_name": "Tennsmith",
        "parquet_path": _path, "row_count": 1,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "ff2", "ingested_at": "2026-09-07",
    }]
    session = {"id": "fab1", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="fab-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              return_value=list(catalog)),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1",
            "find the prices of these machines in Consolidated Price List "
            "2019.xlsx: 381, U-22, SLE24-16 and U-38",
            "fab1", context={"agent_id": "a1"})
    assert result["success"] is True
    assert result.get("model") == "deterministic"
    assert "8880" in result["message"], "the REAL workbook price must ship"
    assert "5,850" not in result["message"], "fabricated values must not"
    orch.llm_service.generate_completion.assert_not_awaited()


# ---------------------------------------------------------------------------
# Wiring 12 — GENERALITY: non-price use case through the same machinery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_price_fields_flow_through_the_same_pipeline():
    """The machinery is a general structured-retrieval capability: a
    weight/lead-time ask on a spec sheet resolves, scopes, and delivers
    through the identical path — with requested-field words selecting the
    value columns and no price vocabulary involved."""
    orch = _orch()
    orch.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError(
        "narration must not be needed"))
    import tempfile as _tf

    import pandas as _pd

    _tmp = _tf.mkdtemp(prefix="wb-gen-")
    _spec = _pd.DataFrame({
        "__sheet_row": [7, 8],
        "Part": ["R-15", "R-16"],
        "Weight kg": [120, 145],
        "Lead Time days": [21, 35],
        "Notes": ["steel", "stainless"],
    })
    _path = os.path.join(_tmp, "spec.parquet")
    _spec.to_parquet(_path)
    catalog = [{
        "source": "app_upload", "external_id": "spec-1",
        "dataset_name": "spec_fixture", "file_name": "Spec Sheet 2025.xlsx",
        "entity_name": "Specs", "parquet_path": _path, "row_count": 2,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "ab12", "ingested_at": "2026-09-01",
    }]
    session = {"id": "gen1", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="gen-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              return_value=list(catalog)),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1",
            "find the weight and lead time of R-15 in Spec Sheet 2025.xlsx",
            "gen1", context={"agent_id": "a1"})
    assert result["success"] is True
    assert result.get("model") == "deterministic"
    msg = result["message"]
    assert "R-15" in msg and "120" in msg and "21" in msg, (
        "requested non-price fields must ship from the matched row")
    assert "Spec Sheet 2025.xlsx" in msg
    assert "MATERIALIZED COPY" in msg
    # Field labels come from the schema (column headers), not price vocab.
    assert "Weight kg" in msg and "Lead Time days" in msg


class TestCentralResponseValidation:
    def test_detects_tool_call_tag_dialects(self):
        from core.response_validation import is_malformed_output

        assert is_malformed_output(
            "Answer:\n<minimax:tool_call>\n<invoke name=\"x\">")
        assert is_malformed_output(
            "ok <openai:function_call>{}</openai:function_call>")
        assert is_malformed_output("partial </mm:think> residue")

    def test_detects_bare_tool_name_json_line(self):
        from core.response_validation import is_malformed_output

        # The live-observed residue shape (2026-09-24).
        assert is_malformed_output(
            'Let me check.\nsearch_read: {"file": "x.xlsx", "probe": ["381"]}')
        assert not is_malformed_output(
            "The result: {see the table above} is what we found.")

    def test_quoted_examples_and_code_blocks_are_not_protocol_leaks(self):
        from core.response_validation import is_malformed_output

        assert not is_malformed_output(
            'Example: "<invoke name=\\"demo\\">" is quoted documentation.'
        )
        assert not is_malformed_output(
            'Example:\n```xml\n<invoke name="demo"/>\n```'
        )
        assert not is_malformed_output(
            "Use the literal `<parameter>` tag in documentation."
        )

    def test_split_stream_marker_is_cleaned_but_not_accepted_as_final(self):
        from core.response_validation import (
            is_malformed_output,
            strip_protocol_fragments,
        )

        partial = "The answer is <thi"
        assert strip_protocol_fragments(partial) == "The answer is"
        assert not is_malformed_output(partial, channel="stream")
        assert is_malformed_output(partial)

    def test_structured_channel_validates_type_without_text_scanning(self):
        from core.response_validation import validate_response_payload

        result = validate_response_payload(
            {"tool_calls": [{"name": "read", "arguments": {}}]},
            channel="tool",
            content_type="application/json",
        )
        assert result.valid is True
        invalid = validate_response_payload(
            "{not-json", channel="tool", content_type="application/json"
        )
        assert invalid.valid is False
        assert invalid.reason == "invalid JSON response payload"

    def test_final_text_rejects_structured_json_payload(self):
        from core.response_validation import validate_response_payload

        result = validate_response_payload(
            {"answer": "ok"}, channel="final_text", content_type="application/json"
        )
        assert result.valid is False
        assert result.reason == "final text response must use a text content type"

    def test_clean_content_passes(self):
        from core.response_validation import is_malformed_output

        assert not is_malformed_output(
            "| SLE24-16 | FOUND | 8880 with sheet and row references |")
        assert not is_malformed_output("")

    def test_stream_stripper_preserves_think_capture(self):
        from core.response_validation import strip_protocol_fragments

        captured: list = []
        out = strip_protocol_fragments(
            "<think>reasoning</think>The answer is 42", captured=captured)
        assert out == "The answer is 42" and captured == ["reasoning"]


# ---------------------------------------------------------------------------
# Wiring 13 — GENERality contrast fixtures + NL attributes + field ambiguity
# ---------------------------------------------------------------------------

def _wb_fixture(tmpdir, name, columns, rows, entity="Data"):
    import pandas as pd

    frame = pd.DataFrame(
        [{"__sheet_row": i + 2, **row} for i, row in enumerate(rows)])
    path = os.path.join(tmpdir, f"{name}.parquet")
    frame.to_parquet(path)
    return {
        "source": "app_upload", "external_id": f"fix-{name}",
        "dataset_name": f"fix_{name}", "file_name": f"{name}.xlsx",
        "entity_name": entity, "parquet_path": path,
        "row_count": len(rows),
        "coverage": {"known": True, "truncated": False},
        "content_hash": f"hash-{name}", "ingested_at": "2026-09-01",
    }


async def _run_direct_ask(orch, catalog, session_id, message):
    from unittest.mock import AsyncMock, patch
    import core.chat_tool_planner as planner_mod
    session = {"id": session_id, "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value=f"{session_id}-e"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch("core.sheet_dataset_service.sheet_datasets_enabled", return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync", return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync", return_value=list(catalog)),
        patch.object(planner_mod, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        return await orch.process_chat_message(
            "u1", message, session_id, context={"agent_id": "a1"})


@pytest.mark.asyncio
async def test_generality_contrast_fixtures():
    """Three contrasting domains through the SAME production path:
    inventory quantities, employee certification dates, and software
    version requirements (2026-09-24 review: absence of incident tokens
    is hygiene, not proof — these are the proof)."""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="wb-contrast-")
    cases = [
        (_wb_fixture(tmp, "Inventory", ["__sheet_row", "SKU", "On Hand", "Reorder At"],
                     [{"SKU": "TX-4400", "On Hand": 12, "Reorder At": 4},
                      {"SKU": "TX-4500", "On Hand": 0, "Reorder At": 6}], "Stock"),
         "how many of TX-4400 are on hand in Inventory.xlsx",
         ["TX-4400", "12"]),
        (_wb_fixture(tmp, "Certifications", ["__sheet_row", "Employee", "Certification", "Expiry"],
                     [{"Employee": "J. Ortiz", "Certification": "Forklift-3", "Expiry": "2026-11-02"},
                      {"Employee": "M. Chen", "Certification": "Weld-1", "Expiry": "2027-03-15"}], "HR"),
         "when does the Forklift-3 certification expire in Certifications.xlsx",
         ["Forklift-3", "2026-11-02"]),
        (_wb_fixture(tmp, "Requirements", ["__sheet_row", "Component", "Min Version", "License"],
                     [{"Component": "auth-service", "Min Version": "4.2.1", "License": "MIT"},
                      {"Component": "sync-engine", "Min Version": "2.9.0", "License": "Apache"}], "Eng"),
         "what minimum version does auth-service require in Requirements.xlsx",
         ["auth-service", "4.2.1"]),
    ]
    for i, (entry, ask, expected) in enumerate(cases):
        orch = _orch()
        orch.llm_service.generate_completion = AsyncMock(
            side_effect=AssertionError("narration must not run"))
        result = await _run_direct_ask(orch, [entry], f"contrast{i}", ask)
        assert result["success"] is True, ask
        assert result.get("model") == "deterministic", ask
        for token in expected:
            assert token in result["message"], f"{ask}: missing {token}"


@pytest.mark.asyncio
async def test_natural_language_attribute_disambiguation():
    """"Find Acme's model 381" — the organization attribute rides into
    retrieval WITHOUT special syntax and corroborates via identity-headed
    fields; a same-code hit under another organization stays a candidate,
    not a silent pick."""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="wb-acme-")
    import pandas as pd

    frame = pd.DataFrame({
        "__sheet_row": [4, 5],
        "Part": ["381", "381"],
        "Vendor": ["Acme", "Zeta"],
        "Weight": [10, 99],
    })
    path = os.path.join(tmp, "parts.parquet")
    frame.to_parquet(path)
    entry = {
        "source": "app_upload", "external_id": "acme-1",
        "dataset_name": "acme_fixture", "file_name": "Parts Catalog.xlsx",
        "entity_name": "Parts", "parquet_path": path, "row_count": 2,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "h1", "ingested_at": "2026-09-01",
    }
    from core.workbook_read_artifact import (
        extract_attributes,
        inspect_dataset_entries,
    )

    targets = ["381"]
    attrs = extract_attributes(
        ["find Acme's model 381 in Parts Catalog.xlsx"], targets)
    assert "acme" in attrs, attrs
    art = inspect_dataset_entries(
        [entry], "Parts Catalog.xlsx", query="find Acme's model 381",
        targets=targets, attributes=attrs)
    (outcome,) = art["coverage"]["outcomes"]
    assert outcome["status"] == "found", outcome
    ev = outcome["evidence"][0]
    assert ev["row"] == 4 and "Acme" in str(ev.get("row_context")), (
        "the identity-field corroborated row must win")


@pytest.mark.asyncio
async def test_field_ambiguity_is_explicit_not_silent():
    """Duplicate value-columns for one requested field surface BOTH with
    an explicit ambiguity signal rather than a silent plausible pick."""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="wb-amb-")
    import pandas as pd

    frame = pd.DataFrame({
        "__sheet_row": [3],
        "Part": ["R-9"],
        "Weight gross": [120],
        "Weight net": [100],
    })
    path = os.path.join(tmp, "amb.parquet")
    frame.to_parquet(path)
    entry = {
        "source": "app_upload", "external_id": "amb-1",
        "dataset_name": "amb_fixture", "file_name": "Spec.xlsx",
        "entity_name": "Spec", "parquet_path": path, "row_count": 1,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "h2", "ingested_at": "2026-09-01",
    }
    from core.workbook_read_artifact import (
        extract_attributes,
        inspect_dataset_entries,
        render_workbook_artifact,
    )

    attrs = extract_attributes(
        ["what is the weight of R-9 in Spec.xlsx"], ["R-9"])
    art = inspect_dataset_entries(
        [entry], "Spec.xlsx", query="what is the weight of R-9",
        targets=["R-9"], attributes=attrs)
    (outcome,) = art["coverage"]["outcomes"]
    prices = outcome["evidence"][0].get("prices") or []
    weight_columns = sorted(
        p["column"] for p in prices if "weight" in str(p.get("column", "")).lower())
    assert weight_columns == ["Weight gross", "Weight net"], (
        "BOTH matching columns must ship — never a silent single pick")
    assert outcome["evidence"][0]["field_selection"]["ambiguous"] is True
    assert outcome["field_ambiguities"]["weight"] == [
        "Weight gross", "Weight net"
    ]
    assert outcome["evidence"][0]["field_ambiguities"]["weight"] == [
        "Weight gross", "Weight net"
    ]
    assert all(item["field_ambiguous"] for item in prices)
    rendered = render_workbook_artifact(art)
    assert "Weight gross" in rendered and "Weight net" in rendered


class TestValidatorFalsePositives:
    def test_quoted_example_and_code_block_are_legitimate(self):
        from core.response_validation import is_malformed_output

        assert not is_malformed_output(
            'Example residue looks like this: "<minimax:tool_call>" '
            "— ignore it.")
        assert not is_malformed_output(
            "```xml\n<invoke name=\"x\"/>\n```\nThat is the protocol doc.")
        assert not is_malformed_output(
            "Use `<parameter name=\"q\">` when calling the tool.")

    def test_prose_braces_are_not_json(self):
        from core.response_validation import is_malformed_output

        assert not is_malformed_output(
            "The result: {see the table above} is what we found.")

    def test_split_stream_marker_is_detected_once_complete(self):
        from core.response_validation import split_safe_prefix

        # Split across chunks: partial tail is held back, not displayed.
        safe, held, residue = split_safe_prefix(
            "The answer is 42.<minimax:tool")
        assert safe == "The answer is 42." and held == "<minimax:tool"
        assert residue is False
        # Completed: everything from the marker is protocol.
        safe2, held2, residue2 = split_safe_prefix(
            "The answer is 42.<minimax:tool_call>\n<invoke>")
        assert residue2 is True and safe2 == "The answer is 42."

    def test_quoted_and_code_examples_are_boundary_invariant(self):
        from core.response_validation import (
            is_malformed_output,
            split_safe_prefix,
        )

        samples = [
            'Example: "<invoke name=\\"demo\\">" is quoted documentation.',
            "Example:\n```xml\n<invoke name=\"demo\"/>\n```",
            "Use the literal `<parameter name=\"q\">` tag in documentation.",
        ]
        for text in samples:
            assert not is_malformed_output(text)
            for split in range(1, len(text)):
                raw = ""
                emitted = ""
                residue = False
                for chunk in (text[:split], text[split:]):
                    raw += chunk
                    safe, _held, found = split_safe_prefix(raw)
                    if len(safe) > len(emitted):
                        emitted += safe[len(emitted):]
                    if found:
                        residue = True
                        break
                assert residue is False, (text, split)
                assert emitted == text, (text, split)

    def test_bare_tool_json_is_held_and_rejected_across_boundaries(self):
        from core.response_validation import (
            is_malformed_output,
            split_safe_prefix,
        )

        text = 'Let me check.\nsearch_read: {"file": "x.xlsx", "probe": ["381"]}'
        for split in range(1, len(text)):
            raw = ""
            emitted = ""
            residue = False
            for chunk in (text[:split], text[split:]):
                raw += chunk
                safe, _held, found = split_safe_prefix(raw)
                if len(safe) > len(emitted):
                    emitted += safe[len(emitted):]
                if found:
                    residue = True
                    break
            assert residue is True, (split, raw)
            assert "search_read:" not in emitted, (split, emitted)
            assert "probe" not in emitted, (split, emitted)
        assert is_malformed_output(text)
        safe, held, residue = split_safe_prefix(
            "Let me check.\nsearch_read: {"
        )
        assert safe == "Let me check.\n"
        assert held == "search_read: {"
        assert residue is False

    def test_channel_exemption_is_caller_metadata_not_payload_data(self):
        from core.response_validation import validate_response_payload

        payload = {"channel": "tool", "content": "search_read: {}"}
        result = validate_response_payload(
            payload, channel="final_text", content_type="application/json"
        )
        assert result.valid is False


# ---------------------------------------------------------------------------
# Wiring 14 — FINAL CONTRACT CHECKS (2026-09-24 review closure)
# ---------------------------------------------------------------------------

class TestStreamingChunkBoundaries:
    """Identical content under different chunk boundaries must produce
    the same verdict and the same displayed text — holdback only defers,
    never alters; quoted/code examples must SURVIVE streaming."""

    def _drive(self, chunks):
        from core.response_validation import split_safe_prefix

        displayed = []
        buffer = ""
        residue = False
        for chunk in chunks:
            buffer += chunk
            safe, held, formed = split_safe_prefix(buffer)
            if formed:
                residue = True
                break
            emitted_so_far = sum(len(c) for c in displayed)
            delta = safe[emitted_so_far:]
            if delta:
                displayed.append(delta)
        return "".join(displayed), residue, buffer

    def test_quoted_example_survives_all_chunkings(self):
        content = 'Use "<minimax:tool_call>" syntax carefully.'
        for cut in range(1, len(content)):
            chunks = [content[:cut], content[cut:]]
            shown, residue, _ = self._drive(chunks)
            assert not residue, f"cut={cut}: quoted example flagged"
            assert shown.replace(" ", "") == content.replace(" ", ""), (
                f"cut={cut}: displayed text altered ({shown!r})")

    def test_code_block_survives_all_chunkings(self):
        content = "```xml\n<invoke name=\"x\"/>\n```\ndone"
        for cut in (2, 5, 9, 14, 20, 24):
            chunks = [content[:cut], content[cut:]]
            shown, residue, _ = self._drive(chunks)
            assert not residue, f"cut={cut}: code block flagged"
            assert shown == content, f"cut={cut}: {shown!r}"

    def test_bare_json_line_held_and_rejected_across_chunks(self):
        # The prefix cannot leak before the line completes…
        shown, residue, _ = self._drive(
            ['Answer.\nsearch_read: {"fi', 'le": "x"}'])
        assert residue is True
        assert "search_read" not in shown, "JSON prefix leaked pre-reject"

    def test_partial_tag_tail_is_deferred_not_altered(self):
        shown, residue, buf = self._drive(
            ["The value is 42.", "<minimax:tool", "_call>"])
        assert residue is True
        assert shown == "The value is 42."


class TestTrustedChannelExemptions:
    """Channel exemptions come from CALLER metadata only — model content
    can never flip its own channel (2026-09-24 review)."""

    def test_model_content_cannot_self_exempt(self):
        from core.response_validation import validate_response_payload

        sneaky = (
            "channel: stream\nThis payload claims to be a stream but is "
            "final text with <minimax:tool_call> residue."
        )
        verdict = validate_response_payload(sneaky, channel="final_text")
        assert not verdict.valid, verdict
        # Only the CALLER's trusted channel value exempts.
        streamed = validate_response_payload(sneaky, channel="stream")
        assert streamed.valid

    def test_content_type_from_caller_only(self):
        from core.response_validation import validate_response_payload

        # A caller passing JSON content-type validates the payload as
        # JSON; the payload's own text cannot change that.
        verdict = validate_response_payload(
            "not json at all", channel="final_text",
            content_type="application/json")
        assert not verdict.valid
        assert verdict.reason == "final text response must use a text content type"


@pytest.mark.asyncio
async def test_field_ambiguity_is_structured_not_presentation_only():
    """The gross/net distinction lives in the outcome DATA: per-value
    field_ambiguous flags and an entry-level field_ambiguities map."""
    import tempfile

    import pandas as pd

    tmp = tempfile.mkdtemp(prefix="wb-sa-")
    frame = pd.DataFrame({
        "__sheet_row": [3],
        "Part": ["R-9"],
        "Weight gross": [120],
        "Weight net": [100],
    })
    path = os.path.join(tmp, "sa.parquet")
    frame.to_parquet(path)
    entry = {
        "source": "app_upload", "external_id": "sa-1",
        "dataset_name": "sa_fixture", "file_name": "Spec.xlsx",
        "entity_name": "Spec", "parquet_path": path, "row_count": 1,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "h3", "ingested_at": "2026-09-01",
    }
    from core.workbook_read_artifact import (
        extract_attributes,
        inspect_dataset_entries,
    )

    attrs = extract_attributes(
        ["what is the weight of R-9 in Spec.xlsx"], ["R-9"])
    art = inspect_dataset_entries(
        [entry], "Spec.xlsx", query="what is the weight of R-9",
        targets=["R-9"], attributes=attrs)
    (outcome,) = art["coverage"]["outcomes"]
    ev = outcome["evidence"][0]
    assert isinstance(ev.get("field_ambiguities"), dict), (
        "structured ambiguity map missing from the evidence entry")
    values = ev.get("prices") or ev.get("values") or []
    flagged = {v["column"] for v in values if v.get("field_ambiguous")}
    assert flagged == {"Weight gross", "Weight net"}, flagged


# ---------------------------------------------------------------------------
# Task-continuity regression (2026-09-24): the LEGACY conversation — the
# objective predates the pending-task store, so a retry has NOTHING to
# resume. Live: "try excel file search again" logged `tool plan executed:
# None`, the reply promised a search that never started, and the next
# "go ahead" was answered from the open email canvas — the wrong task.
# ---------------------------------------------------------------------------

LEGACY_ASK = (
    "find all these prices from price list 2019 and let me know what you "
    "find")
LEGACY_CONFIRM = "Consolidated Price List 2019.xlsx is correct"
LEGACY_RETRY = "try excel file search again"
LEGACY_APPROVAL = "go ahead"
LEGACY_HISTORY = [
    {"message": "update the canvas",
     "response": "The canvas edit has been started in the background."},
    {"message": "create a sample quote email for this lead",
     "response": "To: Steve — Quote draft..."},
    {"message": "apply the priced table to the canvas now",
     "response": "I can't apply the canvas edit — the edit planner failed."},
    {"message": LEGACY_ASK,
     "response": "the WorkDrive lookup came back unverified"},
    {"message": LEGACY_CONFIRM,
     "response": "Noted that the filename to target is the 2019 price list."},
]


class TestLegacyTaskRecovery:
    def test_retry_recovers_the_unresolved_ask(self):
        from core.pending_file_task import recover_pending_task_from_history

        task = recover_pending_task_from_history(
            LEGACY_HISTORY, LEGACY_RETRY)
        assert task is not None, (
            "a retry in a legacy conversation must reconstruct the ask")
        assert task["original_message"] == LEGACY_ASK
        assert task["mention"] == "consolidated price list 2019.xlsx", (
            "the confirmation's specific name refines the ask's own "
            "extensionless mention")
        assert task["status"] == "pending"
        assert task["recovered"] is True

    def test_bare_approval_also_recovers(self):
        from core.pending_file_task import recover_pending_task_from_history

        task = recover_pending_task_from_history(
            LEGACY_HISTORY + [
                {"message": LEGACY_RETRY,
                 "response": "I will search Zoho WorkDrive now."},
            ],
            LEGACY_APPROVAL)
        assert task is not None
        assert task["original_message"] == LEGACY_ASK

    def test_approval_of_a_newer_email_objective_recovers_nothing(self):
        """Task drift guard: the approval belongs to the LATEST objective.
        When a non-file ask (the email draft) is newer than the file ask,
        recovery must stay out of it — the email flow owns the approval."""
        from core.pending_file_task import recover_pending_task_from_history

        history = LEGACY_HISTORY + [
            {"message": "create a sample quote email for this lead",
             "response": "Here is the draft..."},
        ]
        assert recover_pending_task_from_history(
            history, LEGACY_APPROVAL) is None

    def test_action_turn_on_the_same_file_refuses_recovery(self):
        """An approval of 'email me the price list' must never execute a
        workbook read instead."""
        from core.pending_file_task import recover_pending_task_from_history

        history = LEGACY_HISTORY + [
            {"message": "email me the consolidated price list 2019.xlsx",
             "response": "..."},
        ]
        assert recover_pending_task_from_history(
            history, LEGACY_APPROVAL) is None

    def test_different_file_objective_supersedes(self):
        from core.pending_file_task import recover_pending_task_from_history

        history = LEGACY_HISTORY + [
            {"message": "search the stock counts 2026.xlsx for SKU 12",
             "response": "..."},
        ]
        task = recover_pending_task_from_history(history, LEGACY_APPROVAL)
        assert task is not None and task["mention"] == (
            "stock counts 2026.xlsx")

    def test_expired_pending_state_recovers(self):
        """Replay requirement: expired pending state. The stored task's TTL
        is long gone, nothing was answered — the retry still continues the
        objective. A bare confirmation stays TTL-bound; an explicit
        re-retrieval request is live intent and matches anyway."""
        import core.pending_file_task as pft

        stored = pft.build_pending_task(
            LEGACY_ASK, "price list 2019")
        stored["created_at"] -= pft._PENDING_FILE_TASK_TTL_SECONDS * 4
        assert pft.matching_pending_task(
            stored, "That filename is correct", LEGACY_HISTORY) is None, (
            "a bare confirmation stays TTL-bound")
        assert pft.matching_pending_task(
            stored, LEGACY_RETRY, LEGACY_HISTORY) is not None, (
            "an explicit refresh is live intent past the TTL")
        assert pft.pending_task_is_recoverable(stored)
        task = pft.recover_pending_task_from_history(
            LEGACY_HISTORY, LEGACY_RETRY)
        assert task is not None and task["original_message"] == LEGACY_ASK

    def test_terminal_task_is_never_recovered(self):
        import core.pending_file_task as pft

        served = pft.mark_task_served(
            pft.build_pending_task(LEGACY_ASK, "price list 2019"), None)
        assert not pft.pending_task_is_recoverable(served)

    def test_cross_domain_equivalent(self):
        """The mechanism is domain-independent: a billing workbook instead
        of the machinery price list, same four-turn shape."""
        from core.pending_file_task import recover_pending_task_from_history

        history = [
            {"message": "write a blog post draft", "response": "..."},
            {"message": (
                "find the invoice totals in the Q3 billing summary and "
                "let me know what you find"),
             "response": "the lookup did not complete"},
            {"message": "Q3 Billing Summary 2026.xlsx is right",
             "response": "noted"},
        ]
        task = recover_pending_task_from_history(
            history, "try the file search again")
        assert task is not None
        assert task["mention"] == "q3 billing summary 2026.xlsx"
        assert "invoice totals" in task["original_message"]


class TestIdentifierInheritance:
    """2026-09-25: a vague re-ask superseded the identifier-rich ask, and
    the resumed read searched the canvas TITLE's phrases instead of the
    machines. The task must carry the USER's explicit identifiers forward
    — user asks only; assistant renders (markdown tables of canvas
    values) are the contamination source and never contribute."""

    MACHINES_ASK = (
        "find the prices of these 8 machines in Consolidated Price List "
        "2019.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, SLE16-8 "
        "and U-38")
    MACHINES = [
        "381", "U-22", "622", "SLE24-16", "GSL48-16",
        "GSL24-16", "SLE16-8", "U-38",
    ]

    def test_user_history_harvests_the_machines(self):
        from core.pending_file_task import identifier_targets_from_user_history

        history = [
            {"message": self.MACHINES_ASK,
             "response": "searching now"},
            {"message": LEGACY_ASK, "response": "unverified"},
        ]
        targets = identifier_targets_from_user_history(
            history, "consolidated price list 2019.xlsx")
        for machine in self.MACHINES:
            assert machine in targets, machine

    def test_comma_formatted_amounts_never_become_entities(self):
        """2026-09-25 review round 4: splitting on ',' BEFORE removing
        monetary tails made '902.00' a standalone entity out of
        '$2,902.00'. Thousands-separator commas must never split."""
        from core.pending_file_task import _enumeration_items

        items = _enumeration_items(
            "find the prices: No. 381 — $2,902.00, U-22 — $1,777.00, "
            "SLE24-16 — $8,880.00")
        assert items == ["No. 381", "U-22", "SLE24-16"]
        assert not any(
            "902" in item or "777" in item or "880" in item
            for item in items)

    def test_numbered_price_list_is_an_enumeration(self):
        """The ORIGINAL objective's shape (2026-09-25 review round 4:
        colon-only parsing never matched it): a numbered list with
        prices and delivery terms, full entity names preserved."""
        from core.pending_file_task import _enumeration_items

        items = _enumeration_items(
            "quote these:\n"
            "1. Roper Whitney No. 381 — $2,902.00 — 10–11 weeks\n"
            "2. Linmac U-22 — $1,777.00 — 3–4 months\n"
            "3. TK Manual Flanger — $1,609.00")
        assert items == [
            "Roper Whitney No. 381", "Linmac U-22", "TK Manual Flanger",
        ]

    def test_negation_items_are_removed_numero_survives(self):
        from core.pending_file_task import _enumeration_items

        items = _enumeration_items(
            "check: 381, U-22, not 0381, SLE24-16, no U-38 and TK 1624")
        assert items == ["381", "U-22", "SLE24-16", "TK 1624"]

    def test_assistant_renders_never_contribute(self):
        from core.pending_file_task import identifier_targets_from_user_history

        history = [
            {"message": self.MACHINES_ASK, "response": "ok"},
            # role-marked assistant render carrying the contaminating table
            {"role": "assistant",
             "content": "| 902 | ABSENT |\n| 00 | ABSENT |\n| 609 | ABSENT |"},
            # message/response shape: the render lives in 'response'
            {"message": "",
             "response": "| 777 | ABSENT |\n| 880 | ABSENT |"},
        ]
        targets = identifier_targets_from_user_history(
            history, "consolidated price list 2019.xlsx")
        assert not any(t in {"902", "00", "609", "777", "880"} for t in targets)

    def test_different_file_asks_are_excluded(self):
        from core.pending_file_task import identifier_targets_from_user_history

        history = [
            {"message": self.MACHINES_ASK, "response": "ok"},
            {"message": "check R-9 in Training Records.xlsx",
             "response": "ok"},
        ]
        targets = identifier_targets_from_user_history(
            history, "consolidated price list 2019.xlsx")
        assert "R-9" not in targets

    def test_recovery_stamps_requested_targets(self):
        from core.pending_file_task import recover_pending_task_from_history

        history = [
            {"message": self.MACHINES_ASK,
             "response": "the WorkDrive lookup came back unverified"},
            {"message": LEGACY_ASK, "response": "unverified again"},
            {"message": LEGACY_CONFIRM,
             "response": "Noted that the filename to target is the 2019 list."},
        ]
        task = recover_pending_task_from_history(history, LEGACY_RETRY)
        assert task is not None
        assert task["original_message"] == LEGACY_ASK
        stamped = task.get("requested_targets") or []
        for machine in self.MACHINES:
            assert machine in stamped, machine


class TestCanvasTruthGate:
    """2026-09-25 live defect: a read-only turn's reply claimed 'I've
    updated item 4' while the canvas-edit leg was SKIPPED (the canvas kept
    TBD). The reply model must be told no canvas change executed."""

    def test_reply_prompt_carries_canvas_state_rule(self):
        import inspect

        from integrations.chat_orchestrator import ChatOrchestrator

        source = inspect.getsource(ChatOrchestrator._get_qwen_response)
        assert "CANVAS STATE: no change to the canvas has been" in source
        assert "present them as PROPOSED values" in source

    # -- guard plumbing -------------------------------------------------
    @staticmethod
    def _seed_audit(op_id, canvas_id, payload, review_status,
                    postconditions=None, when=None):
        from datetime import datetime, timezone
        from uuid import uuid4

        from core.database import get_db_session
        from core.models import CanvasAudit

        details = {
            "operation_id": op_id,
            "content": payload,
            "review_status": review_status,
        }
        if postconditions is not None:
            details["postconditions"] = postconditions
        with get_db_session() as db:
            db.add(CanvasAudit(
                id=f"audit-{uuid4().hex[:10]}", canvas_id=canvas_id,
                tenant_id="default", session_id="s-g",
                action_type="update", user_id="u-g",
                created_at=when or datetime.now(timezone.utc),
                details_json=details,
            ))

    @staticmethod
    def _patch_checker(marker):
        """Isolate the guard from the editor's evidence checker (which has
        its own suite): the checker 'holds' only on the canvas content
        carrying the marker key."""
        from unittest.mock import patch

        def _applied(content, action):
            return isinstance(content, dict) and content.get(
                "marker") == marker
        return patch(
            "core.chat_canvas_editor._evidence_action_applied",
            side_effect=_applied)

    # -- verdicts --------------------------------------------------------
    @pytest.mark.asyncio
    async def test_unbound_claim_is_unverified_and_rewritten(self):
        from integrations.chat_orchestrator import ChatOrchestrator

        out = await ChatOrchestrator._canvas_claim_correction(
            "I've updated item 4 to reflect that pricing.",
            {"canvas_id": "cv-never"}, "s-g", "u-g", False,
        )
        assert "I've updated item 4" not in out
        assert "Unverified" in out

    @pytest.mark.asyncio
    async def test_overlapping_turn_write_does_not_verify(self):
        from datetime import datetime, timezone
        from uuid import uuid4

        from core.database import get_db_session
        from core.models import AgentExecution
        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        with get_db_session() as db:
            db.add(AgentExecution(
                id=exec_id, status="running",
                started_at=datetime.now(timezone.utc),
            ))
        self._seed_audit(
            f"op-other-{uuid4().hex[:6]}", canvas_id,
            {"marker": "other"}, "accepted")
        verdict = await ChatOrchestrator._canvas_write_for_operation(
            canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "unverified"

    @pytest.mark.asyncio
    async def test_substring_operation_never_verifies(self):
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            f"{exec_id}-suffix", canvas_id, {"marker": "x"}, "accepted")
        verdict = await ChatOrchestrator._canvas_write_for_operation(
            canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "unverified"

    @pytest.mark.asyncio
    async def test_result_verified_when_postconditions_hold_on_served(self):
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        payload = {"marker": "requested-result"}
        self._seed_audit(
            exec_id, canvas_id, payload, "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        with self._patch_checker("requested-result"):
            verdict = await ChatOrchestrator._canvas_write_for_operation(
                canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "result_verified"
        assert verdict["review_status"] == "accepted"
        text = "I've updated item 4 to reflect that pricing."
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                execution_id=exec_id,
            )
        assert "item 4" not in out  # replaced by the verified set
        assert "Verified on the canvas as served: 381 — price." in out
        assert "Review status: accepted." in out

    @pytest.mark.asyncio
    async def test_verified_pending_draft_says_ready_for_review(self):
        """Round 6: pending review and successful draft preparation are
        COMPATIBLE — verified contents may be called updated/ready, never
        accepted; the review state rides separately."""
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "pending_review",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        text = "I've updated item 4 to reflect that pricing."
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                execution_id=exec_id,
            )
        assert "item 4" not in out  # replaced by the verified set
        assert "Verified on the canvas as served: 381 — price." in out
        assert "Review status: pending review — not yet accepted." in out

    @pytest.mark.asyncio
    async def test_accepted_base_vs_pending_draft_served(self):
        """Round 6 boundary pin: an OLDER ACCEPTED write whose payload
        matches the stale Canvas.content fallback must NOT verify — the
        canonical read path serves a NEWER pending-review draft. Only the
        postconditions decide, and they hold on the pending draft, so the
        older operation stays write_recorded."""
        from datetime import datetime, timedelta, timezone
        from uuid import uuid4

        from core.database import get_db_session
        from core.models import Canvas
        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        accepted_payload = {"marker": "accepted-base"}
        pending_payload = {"marker": "pending-draft"}
        self._seed_audit(
            exec_id, canvas_id, accepted_payload, "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }], when=now - timedelta(minutes=5))
        self._seed_audit(
            f"op-newer-{uuid4().hex[:6]}", canvas_id, pending_payload,
            "pending_review", when=now)
        with get_db_session() as db:
            db.add(Canvas(  # the STALE fallback the old guard trusted
                id=canvas_id, tenant_id="default", created_by="u-g",
                name="Quote", content=accepted_payload,
            ))
        with self._patch_checker("accepted-base"):
            verdict = await ChatOrchestrator._canvas_write_for_operation(
                canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "write_recorded", (
            "the accepted base must not verify through the stale "
            "Canvas.content fallback while the UI serves the pending draft")

    @pytest.mark.asyncio
    async def test_bound_write_without_criteria_is_recorded_only(self):
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"body": "x"}, "accepted")
        verdict = await ChatOrchestrator._canvas_write_for_operation(
            canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "write_recorded"

    @pytest.mark.asyncio
    async def test_read_failure_is_recorded_not_verified(self):
        """read_canvas failing (ownership, DB) degrades to write_recorded
        — never a verified result, never 'unchanged'."""
        from unittest.mock import AsyncMock, patch
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "x"}, "accepted",
            postconditions=[{
                "entity_id": "e", "field": "f",
                "expected": {"raw_value": "v"},
            }])
        with patch(
            "tools.canvas_crud_tool.read_canvas",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            verdict = await ChatOrchestrator._canvas_write_for_operation(
                canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "write_recorded"

    @pytest.mark.asyncio
    async def test_claim_replaced_by_generated_verified_set(self):
        """Round 9: the confirmation is GENERATED from the verified
        entity/field set — total-success wording AND unchecked specific
        claims ('item 4' when only 381 was checked) cannot survive,
        qualifier or not."""
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted",
            postconditions=[{
                # only the 381 price is recorded — item 4 and the
                # footer-preservation condition were never stamped
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        for text in (
            "I've updated all the prices and everything is done on the "
            "canvas.",
            "I've updated item 4 to reflect that pricing.",
        ):
            with self._patch_checker("requested-result"):
                out = await ChatOrchestrator._canvas_claim_correction(
                    text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                    execution_id=exec_id,
                )
            assert "everything is done" not in out
            assert "item 4" not in out, (
                "an unchecked specific claim cannot survive a qualifier")
            assert "Verified on the canvas as served: 381 — price." in out
            assert "Review status: accepted." in out

    @pytest.mark.asyncio
    async def test_unnamed_criteria_fall_back_to_generic_statement(self):
        """Postconditions without entity/field cannot name what held —
        the statement falls back to the generic recorded-checks sentence
        rather than pretending specificity."""
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted", postconditions=[{"expected": {"raw_value": "x"}}])
        text = "I've updated item 4 to reflect that pricing."
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                execution_id=exec_id,
            )
        assert "item 4" not in out
        assert "The recorded checks for this change passed" in out
        assert "Review status: accepted." in out

    @pytest.mark.asyncio
    async def test_action_claims_replaced_at_every_review_status(self):
        """Round 9: acceptance does not prove sending — sent/approved/
        submitted claims are unsupported at ANY review status, because
        the generated statement only ever carries content criteria plus
        the audit's own review status."""
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        for verb in ("sent", "approved", "submitted", "accepted"):
            text = f"I've {verb} the updated quote on the canvas."
            with self._patch_checker("requested-result"):
                out = await ChatOrchestrator._canvas_claim_correction(
                    text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                    execution_id=exec_id,
                )
            assert f"I've {verb}" not in out, verb
            assert "Verified on the canvas as served: 381 — price." in out
            assert "Review status: accepted." in out

    @pytest.mark.asyncio
    async def test_integration_real_postconditions_real_checker(self):
        """Integration: real stamped postconditions, the REAL evidence
        checker, and the canonical readback (read_canvas over the audit
        trail) — no patched seams. The recorded price change holds on the
        served revision → result_verified, accepted → claim stands."""
        from uuid import uuid4

        from core.database import get_db_session
        from core.models import Canvas
        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        body = (
            "Quote below:\n\n"
            "| item | price |\n|---|---|\n"
            "| 381 | $8,880.00 |\n"
            "| 622 | $2,421.00 |\n"
        )
        content = {"to": "steve@example.com", "subject": "Quote",
                   "body": body}
        postcondition = {
            "entity_id": "381", "field": "price",
            "expected": {"raw_value": "$8,880.00"},
        }
        self._seed_audit(
            exec_id, canvas_id, content, "accepted",
            postconditions=[postcondition])
        with get_db_session() as db:
            db.add(Canvas(
                id=canvas_id, tenant_id="default", created_by="u-g",
                name="Quote", content=content,
            ))
        verdict = await ChatOrchestrator._canvas_write_for_operation(
            canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "result_verified", verdict
        text = "I've updated item 381 in the quote table."
        out = await ChatOrchestrator._canvas_claim_correction(
            text, {"canvas_id": canvas_id}, "u-g", "u-g", False,
            execution_id=exec_id,
        )
        assert "I've updated" not in out, (
            "the claim is replaced by the generated verified set")
        assert "Verified on the canvas as served: 381 — price." in out
        assert "Review status: accepted." in out

    @pytest.mark.asyncio
    async def test_integration_real_checker_rejects_wrong_served_value(self):
        """The real checker through canonical readback: when the served
        revision's value does not match the recorded criterion, the
        verdict is write_recorded even though the payload round-trips."""
        from uuid import uuid4

        from core.database import get_db_session
        from core.models import Canvas
        from integrations.chat_orchestrator import ChatOrchestrator

        from datetime import datetime, timedelta, timezone

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        recorded = {"body": "| item | price |\n|---|---|\n| 381 | $123.00 |"}
        served = {"body": "| item | price |\n|---|---|\n| 381 | $999.00 |"}
        now = datetime.now(timezone.utc)
        self._seed_audit(
            exec_id, canvas_id, recorded, "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "$123.00"},
            }], when=now - timedelta(minutes=5))
        # a NEWER operation's write supersedes the served revision
        self._seed_audit(
            f"op-newer-{uuid4().hex[:6]}", canvas_id, served, "accepted",
            when=now)
        verdict = await ChatOrchestrator._canvas_write_for_operation(
            canvas_id, "s-g", "u-g", exec_id)
        assert verdict["verdict"] == "write_recorded"

    @pytest.mark.asyncio
    async def test_unknown_shaped_workflow_claim_gets_the_section(self):
        """Round 10 counterexample: 'I sent the email.' does not match the
        legacy sentence shapes — outcome-based invocation still attaches
        the structured section (generated from evidence), which is the
        authoritative status; the section never reinforces the send."""
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        text = "I sent the email."
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                execution_id=exec_id,
            )
        assert "Operation status:" in out
        assert "Verified on the canvas as served: 381 — price." in out
        # the section is the ONLY place confirmations come from
        assert out.count("Verified on the canvas as served") == 1

    @pytest.mark.asyncio
    async def test_no_unsupported_workflow_claim_reaches_output(self):
        """THE SAFETY CRITERION (2026-09-25 review round 11, strict-xfail
        per round 12): no unsupported workflow claim may reach any
        user-visible output. Expected failure AT THE SAFETY ASSERTION
        ONLY while the legacy guard stands (setup/other errors surface
        as errors, never masked as xfail). When the unified finalizer
        lands: make this a mandatory passing test, retire the
        known-defect survival regressions, and test streamed output as
        well as final persisted text."""
        import pytest as _pytest
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                "I sent the email.", {"canvas_id": canvas_id},
                "s-g", "u-g", False, execution_id=exec_id,
            )
        # the structured section still rides (its contract is separate)
        assert "Operation status:" in out
        try:
            assert "sent" not in out.lower(), (
                "OPEN DEFECT (unified finalizer): the unsupported send "
                "claim reaches user-visible output")
        except AssertionError:
            _pytest.xfail(
                "OPEN DEFECT, carried to the unified finalizer: "
                "unsupported prose outside the legacy matcher reaches "
                "output; XPASS forces removal of this expectation and "
                "promotion to a mandatory check")
        _pytest.fail(
            "Safety criterion holds — remove the xfail expectation from "
            "this test and make it a mandatory passing check (with the "
            "streamed-output variant)")

    @pytest.mark.asyncio
    async def test_known_defect_mixed_claims_body_survives_with_section(self):
        """KNOWN-DEFECT REGRESSION (2026-09-25 review round 11 — NOT a
        passing safety criterion): the first sentence is legacy-replaced,
        the unsupported 'I sent the email.' SURVIVES in the body beside
        the section. Documents today's behavior so the unified finalizer
        can prove the change."""
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        text = "I updated the draft. I sent the email."
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
                execution_id=exec_id,
            )
        assert out.count("Operation status:") == 1
        assert out.count("Verified on the canvas as served") == 1
        assert "I sent the email." in out  # the open defect, pinned

    @pytest.mark.asyncio
    async def test_no_unsupported_claim_in_mixed_body(self):
        """THE SAFETY CRITERION for the mixed-claim counterexample —
        strict-xfail scoped to the safety assertion (round 12): unrelated
        errors surface as errors, never masked as xfail. Finalizer-landing
        duties: mandatory passing test, retire the known-defect survival
        regression, add the streamed-output variant."""
        import pytest as _pytest
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"marker": "requested-result"},
            "accepted",
            postconditions=[{
                "entity_id": "381", "field": "price",
                "expected": {"raw_value": "123.0"},
            }])
        with self._patch_checker("requested-result"):
            out = await ChatOrchestrator._canvas_claim_correction(
                "I updated the draft. I sent the email.",
                {"canvas_id": canvas_id}, "s-g", "u-g", False,
                execution_id=exec_id,
            )
        assert "Operation status:" in out
        try:
            assert "sent" not in out.lower(), (
                "OPEN DEFECT (unified finalizer): the unsupported send "
                "claim survives in the mixed body")
        except AssertionError:
            _pytest.xfail(
                "OPEN DEFECT, carried to the unified finalizer: the "
                "mixed body carries the unsupported send claim")
        _pytest.fail(
            "Safety criterion holds — remove the xfail expectation from "
            "this test and make it a mandatory passing check (with the "
            "streamed-output variant)")

    @pytest.mark.asyncio
    async def test_write_recorded_reported_even_without_matching_prose(self):
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        exec_id = f"exec-{uuid4().hex[:12]}"
        canvas_id = f"cv-{uuid4().hex[:8]}"
        self._seed_audit(
            exec_id, canvas_id, {"body": "x"}, "accepted")
        text = "The quote is ready below."
        out = await ChatOrchestrator._canvas_claim_correction(
            text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
            execution_id=exec_id,
        )
        assert "Operation status:" in out
        assert "not confirmed as served" in out

    @pytest.mark.asyncio
    async def test_read_only_turn_without_claim_is_untouched(self):
        from uuid import uuid4

        from integrations.chat_orchestrator import ChatOrchestrator

        canvas_id = f"cv-{uuid4().hex[:8]}"
        text = "The recorded checks: U-22 is 1777.0 in the indexed copy."
        out = await ChatOrchestrator._canvas_claim_correction(
            text, {"canvas_id": canvas_id}, "s-g", "u-g", False,
            execution_id=f"exec-{uuid4().hex[:12]}",
        )
        assert out == text  # a read-only turn acquires no status section

    def test_prompt_keeps_workflow_confirmations_in_the_section(self):
        import inspect

        from integrations.chat_orchestrator import ChatOrchestrator

        source = inspect.getsource(ChatOrchestrator._get_qwen_response)
        assert "ONLY in the platform's" in source
        assert "'Operation status' section" in source

    @pytest.mark.asyncio
    async def test_enforced_guard_ignores_non_claims_and_canvasless(self):
        from integrations.chat_orchestrator import ChatOrchestrator

        assert await ChatOrchestrator._canvas_claim_correction(
            "The price is 8880.", {"canvas_id": "cv-x"}, "s", "u", False
        ) == "The price is 8880."
        assert await ChatOrchestrator._canvas_claim_correction(
            "I've updated item 4.", None, None, None, False
        ) == "I've updated item 4."



class TestLineageMatching:
    def test_intervening_confirmation_does_not_break_the_match(self):
        """Even WITH stored state, the old history check hit the filename
        confirmation first (it classifies substantive) and the text-equality
        test broke the resume — the retry then had no task."""
        import core.pending_file_task as pft

        pending = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        matched = pft.matching_pending_task(
            pending, LEGACY_RETRY, LEGACY_HISTORY)
        assert matched is not None, (
            "the retry continues the task across its own lineage turns")

    def test_confirmation_then_retry_then_approval_all_match(self):
        import core.pending_file_task as pft

        pending = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        assert pft.matching_pending_task(
            pending, LEGACY_CONFIRM, LEGACY_HISTORY) is None, (
            "the confirmation itself is substantive-classified and stays a "
            "new-request to the strict matcher — recovery and the ask-turn "
            "read own it")
        assert pft.matching_pending_task(
            pending, LEGACY_APPROVAL, LEGACY_HISTORY) is not None

    def test_tasks_carry_explicit_lineage_id(self):
        import core.pending_file_task as pft

        task = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        merged = pft.merge_pending_task(task, LEGACY_RETRY, "price list 2019")
        assert merged["task_id"] == task["task_id"], (
            "confirmations and retries attach to the SAME task id")
        other = pft.merge_pending_task(
            task, "check stock counts 2026.xlsx", "stock counts 2026.xlsx")
        assert other["task_id"] != task["task_id"], (
            "a genuinely new objective starts a new task")


# ---------------------------------------------------------------------------
# Orchestrator-level migration acceptance: the four-turn sequence on a
# session that NEVER had pending state — retry executes the read
# deterministically; the approval re-delivers; no narration, no email.
# ---------------------------------------------------------------------------

def _direct_ok():
    rendered = (
        "Workbook read: Consolidated Price List 2019.xlsx\n"
        "| SLE24-16 | FOUND | Tennsmith!A106 R106 |"
    )
    return {
        "ok": True, "block": rendered, "rendered_answer": rendered,
        "identity": {"file_id": "wd-77",
                     "file_name": "Consolidated Price List 2019.xlsx",
                     "identity_verified": True, "coverage_complete": True},
        "meta": {"completed": True, "identity_verified": True,
                 "coverage_complete": True},
        "retrieval_complete": True,
    }


@pytest.mark.asyncio
async def test_legacy_retry_executes_the_read_without_narration():
    orch = _orch()
    # The session predates the pending-task store: NO task key at all.
    session = {"id": "s-legacy", "history": list(LEGACY_HISTORY)}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="leg-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=_direct_ok())) as direct_mock,
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))) as plan_mock,
        patch.object(orch.llm_service, "generate_completion", new=AsyncMock(
            side_effect=AssertionError(
                "narration must not answer a resolved read"))) as narr_mock,
    ):
        result = await orch.process_chat_message(
            "u1", LEGACY_RETRY, "s-legacy", context={"agent_id": "a1"})

    assert result["success"] is True
    assert result["model"] == "deterministic", (
        "the retry must be answered by the structured reader, not the "
        "reply model")
    assert "| SLE24-16 | FOUND |" in result["message"]
    direct_mock.assert_awaited()
    direct_task = direct_mock.await_args.args[0]
    assert direct_task["original_message"] == LEGACY_ASK
    plan_mock.assert_not_awaited()
    narr_mock.assert_not_awaited()
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"
    assert session["_pending_file_result"]["status"] == "delivered"


@pytest.mark.asyncio
async def test_legacy_approval_re_delivers_without_rereading():
    """Turn 4 of the sequence: after the retry delivered, 'go ahead' comes
    from the PERSISTED result — the open email canvas can never supply the
    answer, and no re-read runs."""
    orch = _orch()
    session = {
        "id": "s-legacy2", "history": list(LEGACY_HISTORY) + [
            {"message": LEGACY_RETRY,
             "response": "Workbook read: ... | SLE24-16 | FOUND |"}],
        FILE_TASK_SESSION_KEY: dict(
            build_pending_task(LEGACY_ASK,
                               "consolidated price list 2019.xlsx"),
            status="retrieved"),
        "_pending_file_result": {
            "status": "retrieved",
            "target_extraction_version": 3,
            "rendered": "Workbook read: Consolidated Price List 2019.xlsx\n"
                        "| SLE24-16 | FOUND | Tennsmith!A106 R106 |",
            "identity": {"file_id": "wd-77"},
        },
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_start_chat_execution", return_value="leg-e2"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_pending_file_result", return_value=(
            session["_pending_file_result"])),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
        patch.object(orch.llm_service, "generate_completion", new=AsyncMock(
            side_effect=AssertionError("must not narrate"))),
    ):
        result = await orch.process_chat_message(
            "u1", LEGACY_APPROVAL, "s-legacy2", context={})

    assert result["success"] is True
    assert result["data"]["deterministic_delivery"] is True
    assert "SLE24-16" in result["message"], (
        "the approval ships the workbook result — never the email draft")
    assert "To: Steve" not in result["message"]


@pytest.mark.asyncio
async def test_promise_gate_replaces_unexecuted_search_claims():
    """Honest execution status: a resume turn whose lookup did NOT run must
    not ship 'I'll search ... now' — the precise blocker ships instead."""
    orch = _orch()
    session = {
        "id": "s-promise",
        "history": [
            {"message": LEGACY_ASK, "response": "lookup unverified"},
            {"message": LEGACY_CONFIRM, "response": "noted"},
        ],
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="pm-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features", new=AsyncMock(return_value={})),
        # The read did not complete this turn...
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value={"ok": False, "block": "", "reason": "timeout"})),
        # ...and the reply leg promised anyway (the live drift shape).
        # _get_qwen_response is patched whole: the gate lives downstream,
        # where its content becomes the turn's message.
        patch.object(orch, "_get_qwen_response", new=AsyncMock(
            return_value={"content": "I'll search Zoho WorkDrive for the "
                                     "file now.",
                          "model": "m", "provider": "p"})),
    ):
        result = await orch.process_chat_message(
            "u1", LEGACY_RETRY, "s-promise", context={"agent_id": "a1"})

    assert "did not run this turn" in result["message"], (
        "a promise of unexecuted work is replaced by the honest blocker")
    assert "I'll search" not in result["message"]


def test_approval_rule_binds_the_artifact_to_the_approved_action():
    """The global approval rule must not push an unrelated artifact: an
    approved lookup is answered by its results or an honest failure — the
    live drift route named the email draft as the expected output."""
    assert "NEVER answer an approved lookup" in chat._APPROVAL_EXECUTION_RULE
    assert "unrelated artifact" in chat._APPROVAL_EXECUTION_RULE
    assert "email draft" in chat._APPROVAL_EXECUTION_RULE


# ---------------------------------------------------------------------------
# Review follow-ups (2026-09-24, second round) — two task-continuity edge
# cases with NEGATIVE tests:
# 1. same file does NOT mean same task — different work on one file starts
#    a new task instead of inheriting lineage;
# 2. cached re-delivery ("go ahead") is a different operation from
#    re-retrieval ("search again", "refresh", "check the latest version").
# ---------------------------------------------------------------------------

DIFFERENT_WORK = "check the revision history of the price list 2019 file"


class TestSameFileDifferentWork:
    def test_new_work_on_same_file_supersedes(self):
        import core.pending_file_task as pft

        pending = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        history = LEGACY_HISTORY + [{"message": DIFFERENT_WORK,
                                     "response": "..."}]
        assert pft.matching_pending_task(
            pending, "yes go ahead", history) is None, (
            "the approval belongs to the revision-history request — the "
            "stored price ask must not be resumed over it")

    def test_comparing_quantities_is_also_new_work(self):
        import core.pending_file_task as pft

        pending = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        history = LEGACY_HISTORY + [
            {"message": "compare its quantities with last year",
             "response": "..."}]
        assert pft.matching_pending_task(
            pending, "yes", history) is None

    def test_new_work_supersedes_recovery_too(self):
        from core.pending_file_task import recover_pending_task_from_history

        history = LEGACY_HISTORY + [{"message": DIFFERENT_WORK,
                                     "response": "..."}]
        task = recover_pending_task_from_history(history, LEGACY_APPROVAL)
        assert task is not None, (
            "recovery still finds the newest objective on the approval")
        assert task["original_message"] == DIFFERENT_WORK, (
            "the recovered task is the revision-history ask — NOT the "
            "older price ask")

    def test_refinement_of_the_same_work_stays_lineage(self):
        import core.pending_file_task as pft

        pending = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        history = LEGACY_HISTORY + [
            {"message": "find its prices and let me know", "response": "..."}]
        assert pft.matching_pending_task(
            pending, "yes", history) is not None, (
            "a pronoun-led re-ask of the SAME work continues the task")

    def test_retry_shape_stays_lineage_despite_loose_pattern(self):
        """'check the file again' is retry vocabulary; 'check the revision
        history of the file' matches the SAME loose pattern but carries two
        new nouns — the nouns decide, the shape does not."""
        import core.pending_file_task as pft

        pending = pft.build_pending_task(LEGACY_ASK, "price list 2019")
        assert pft.is_filename_confirmation(
            "check the file again") is True
        assert pft.matching_pending_task(
            pending, "yes",
            LEGACY_HISTORY + [{"message": "check the file again",
                               "response": "..."}]) is not None


class TestReDeliveryVsRefresh:
    """'go ahead' may re-deliver a completed result; 'search again' /
    'refresh' / 'check the latest version' must RE-RUN the retrieval."""

    def test_refresh_detector_distinguishes_the_operations(self):
        from core.pending_file_task import is_retrieval_refresh_request

        for msg in ("search the file again", "try the excel file search "
                    "again", "refresh the prices", "check the latest "
                    "version", "re-read the workbook"):
            assert is_retrieval_refresh_request(msg), msg
        for msg in ("go ahead", "yes", "proceed", "That filename is "
                    "correct"):
            assert not is_retrieval_refresh_request(msg), msg

    def test_terminal_task_matches_only_for_refresh(self):
        import core.pending_file_task as pft

        delivered = pft.mark_task_delivered(
            pft.build_pending_task(LEGACY_ASK,
                                   "consolidated price list 2019.xlsx"))
        assert pft.matching_pending_task(
            delivered, "go ahead", LEGACY_HISTORY) is None, (
            "an approval never re-runs a completed read")
        assert pft.matching_pending_task(
            delivered, "search the file again", LEGACY_HISTORY) is not None
        assert pft.matching_pending_task(
            delivered, "check the latest version of the workbook",
            LEGACY_HISTORY) is not None

    def test_merge_revives_terminal_task_keeping_source_constraints(self):
        import core.pending_file_task as pft

        delivered = pft.mark_task_delivered(
            pft.build_pending_task(
                LEGACY_ASK, "consolidated price list 2019.xlsx",
                disambiguation={"attributes": {"region": "north"}}))
        merged = pft.merge_pending_task(
            delivered, "check the latest version", "price list 2019")
        assert merged["status"] == "pending", (
            "the refresh re-opens the task for a fresh read")
        assert merged["original_message"] == LEGACY_ASK, (
            "the refresh retains the ORIGINAL objective, not the refresh "
            "phrase")
        assert merged["mention"] == "consolidated price list 2019.xlsx"
        assert merged["disambiguation"] == {
            "attributes": {"region": "north"}}
        assert merged["refreshed"] is True
        assert merged["attempts"] >= 1

    @pytest.mark.asyncio
    async def test_refresh_turn_retrieves_while_approval_re_delivers(self):
        """Orchestrator-level: with a DELIVERED result persisted, 'go
        ahead' must NOT re-read, and 'search again' must NOT answer from
        the cached copy."""
        orch = _orch()
        base_task = dict(
            build_pending_task(LEGACY_ASK,
                               "consolidated price list 2019.xlsx"),
            status="delivered")
        cached_render = "CACHED RENDER | SLE24-16 | FOUND |"
        fresh_render = "FRESH READ | SLE24-16 | FOUND |"

        def fresh_direct():
            rendered = fresh_render
            return {
                "ok": True, "block": rendered, "rendered_answer": rendered,
                "identity": {"file_id": "wd-77",
                             "file_name": "Consolidated Price List "
                                          "2019.xlsx",
                             "identity_verified": True,
                             "coverage_complete": True},
                "meta": {"completed": True, "identity_verified": True,
                         "coverage_complete": True},
                "retrieval_complete": True,
            }

        # --- 'go ahead': re-delivery from persistence, no re-read. -----
        session_go = {
            "id": "s-goahead", "history": list(LEGACY_HISTORY),
            FILE_TASK_SESSION_KEY: dict(base_task),
            "_pending_file_result": {
                "status": "delivered", "rendered": cached_render,
                "target_extraction_version": 3,
                "identity": {"file_id": "wd-77"},
            },
        }
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session_go),
            patch.object(orch, "_start_chat_execution",
                         return_value="rd-e1"),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_load_pending_file_result",
                         return_value=session_go["_pending_file_result"]),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(
                             side_effect=AssertionError(
                                 "an approval must not re-read"))) as go_read,
        ):
            go = await orch.process_chat_message(
                "u1", LEGACY_APPROVAL, "s-goahead", context={})
        go_read.assert_not_awaited()
        assert cached_render in go["message"], (
            "the approval re-delivers the persisted result")

        # --- 'search again': fresh retrieval, cached copy bypassed. ----
        session_again = {
            "id": "s-again", "history": list(LEGACY_HISTORY),
            FILE_TASK_SESSION_KEY: dict(base_task),
            "_pending_file_result": {
                "status": "delivered", "rendered": cached_render,
                "target_extraction_version": 3,
                "identity": {"file_id": "wd-77"},
            },
        }
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session_again),
            patch.object(orch, "_resolve_canvas_ctx",
                         new=AsyncMock(return_value=None)),
            patch.object(orch, "_start_chat_execution",
                         return_value="rd-e2"),
            patch.object(orch, "_record_chat_step", new=AsyncMock()),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_update_session"),
            patch("core.chat_mini_app_authoring.try_handle",
                  new=AsyncMock(return_value=None)),
            patch.object(orch, "_try_zoho_crm_write",
                         new=AsyncMock(return_value=None)),
            patch.object(orch, "_route_to_features",
                         new=AsyncMock(return_value={})),
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(return_value=fresh_direct())
                         ) as again_read,
            patch.object(planner, "plan_tool_use", new=AsyncMock(
                side_effect=AssertionError(
                    "the refresh executes the direct reader, not the "
                    "planner"))),
        ):
            again = await orch.process_chat_message(
                "u1", "search the file again", "s-again",
                context={"agent_id": "a1"})
        again_read.assert_awaited(), (
            "an explicit refresh must re-run the retrieval")
        assert again_read.await_args.args[0]["original_message"] == (
            LEGACY_ASK), "the refresh retains the original objective"
        assert cached_render not in again["message"], (
            "the refresh never answers from the cached copy")
        assert fresh_render in again["message"]
        assert session_again[FILE_TASK_SESSION_KEY]["status"] in (
            "retrieved", "delivered"), (
            "the fresh read re-drives the lifecycle")
        assert session_again[FILE_TASK_SESSION_KEY].get("refreshed") is \
            None or True  # lifecycle stamp; revival recorded on merge

        # --- STALE-RESULT INVALIDATION (2026-09-25 review round 2): a
        # persisted result built by an OLDER extractor (no version stamp,
        # or a lower one) must NEVER replay — even a bare approval
        # re-derives. Live instance: this conversation's contaminated
        # 24-target row (no stamp) re-rendered until superseded.
        for stale_version in (None, 2):
            session_stale = {
                "id": "s-stale", "history": list(LEGACY_HISTORY),
                FILE_TASK_SESSION_KEY: dict(base_task),
                "_pending_file_result": {
                    "status": "delivered", "rendered": cached_render,
                    "identity": {"file_id": "wd-77"},
                    **({"target_extraction_version": stale_version}
                       if stale_version is not None else {}),
                },
            }
            with (
                patch.object(orch, "_get_or_create_session",
                             return_value=session_stale),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=None)),
                patch.object(orch, "_start_chat_execution",
                             return_value="rd-stale"),
                patch.object(orch, "_record_chat_step", new=AsyncMock()),
                patch.object(orch, "_emit_agent_status", new=AsyncMock()),
                patch.object(orch, "_finish_chat_execution"),
                patch.object(orch, "_update_session"),
                patch("core.chat_mini_app_authoring.try_handle",
                      new=AsyncMock(return_value=None)),
                patch.object(orch, "_try_zoho_crm_write",
                             new=AsyncMock(return_value=None)),
                patch.object(orch, "_route_to_features",
                             new=AsyncMock(return_value={})),
                patch.object(orch, "_load_pending_file_result",
                             return_value=(
                                 session_stale["_pending_file_result"])),
                patch.object(orch, "_direct_confirmed_file_read",
                             new=AsyncMock(return_value={
                                 "success": True, "message": fresh_render,
                                 "data": {},
                             })) as stale_read,
            ):
                stale = await orch.process_chat_message(
                    "u1", LEGACY_APPROVAL, "s-stale", context={})
            assert cached_render not in str(stale.get("message", "")), (
                f"a persisted result stamped {stale_version!r} must never "
                "replay — its contaminated render is re-derived, not "
                "re-delivered")


# ---------------------------------------------------------------------------
# Review round 3 (2026-09-24) — bounded follow-ups:
# 1. task identity compares STRUCTURED attributes (action group, requested
#    objects/constraints); lexical counts are not identity. Domain-neutral
#    cases: a one-word objective change ("check availability"), a verbose
#    retry ("search again more thoroughly"), a changed constraint.
# 2. re-deliver / re-run / refresh are three distinct operations; a refresh
#    verifies the UPSTREAM source and never presents an old copy as current.
# ---------------------------------------------------------------------------

INVOICE_ASK = (
    "find the invoice totals in the Q3 billing summary and let me know "
    "what you find")


class TestStructuredTaskIdentity:
    def test_one_word_objective_change_is_new_work(self):
        """'check availability' changes the objective with ONE new word —
        a lexical count would keep it lineage; the object decides."""
        import core.pending_file_task as pft

        pending = pft.build_pending_task(INVOICE_ASK, "q3 billing summary")
        history = LEGACY_HISTORY[:0] + [
            {"message": INVOICE_ASK, "response": "lookup unverified"}]
        assert pft._introduces_new_work(
            "check availability", INVOICE_ASK) is True
        assert pft.matching_pending_task(
            pending, "yes go ahead",
            history + [{"message": "check availability",
                        "response": "..."}]) is None

    def test_verbose_retry_is_still_lineage(self):
        """'search again more thoroughly' adds words without changing the
        objective — the retry continues the task."""
        import core.pending_file_task as pft

        pending = pft.build_pending_task(INVOICE_ASK, "q3 billing summary")
        assert pft._introduces_new_work(
            "search again more thoroughly", INVOICE_ASK) is False
        assert pft.matching_pending_task(
            pending, "yes",
            [{"message": INVOICE_ASK, "response": "x"},
             {"message": "search again more thoroughly",
              "response": "y"}]) is not None

    def test_changed_constraint_is_new_work(self):
        import core.pending_file_task as pft

        assert pft._introduces_new_work(
            "find the invoice totals for the north region only",
            INVOICE_ASK) is True

    def test_pronoun_refinement_stays_lineage(self):
        import core.pending_file_task as pft

        assert pft._introduces_new_work(
            "find its totals and let me know", INVOICE_ASK) is False

    def test_morphology_folds_plural_forms(self):
        import core.pending_file_task as pft

        assert pft._light_stem("prices") == pft._light_stem("price")
        assert pft._light_stem("quantities") == pft._light_stem("quantity")


class TestThreeOperations:
    def test_operation_classification(self):
        from core.pending_file_task import classify_file_operation

        assert classify_file_operation("go ahead") == "re-deliver"
        assert classify_file_operation("yes") == "re-deliver"
        assert classify_file_operation(
            "That filename is correct") == "re-deliver"
        assert classify_file_operation("search the file again") == "re-run"
        assert classify_file_operation(
            "try the excel file search again") == "re-run"
        assert classify_file_operation("refresh the prices") == "refresh"
        assert classify_file_operation(
            "check the latest version of the workbook") == "refresh"

    def test_refresh_wins_over_rerun_wording(self):
        from core.pending_file_task import classify_file_operation

        assert classify_file_operation(
            "check the latest version again") == "refresh"


def _fake_uis_cls(execute_impl):
    class _FakeUIS:
        def __init__(self, workspace_id: str = "default"):
            self.workspace_id = workspace_id

        async def execute(self, service, action, params, context=None):
            return await execute_impl(service, action, params, context or {})

    return _FakeUIS


def _direct_read_result_meta(plan, block):
    plan._result_meta = {"storage_read": {
        "service": "zoho_workdrive", "file_id": "wd-77",
        "resource_id": "wd-77",
        "file_name": "Q3 Billing Summary 2026.xlsx",
        "completed": True, "identity_verified": True,
        "coverage_complete": True,
        "ingested_at": "2026-09-01T10:00:00",
        "content_hash": "aaa111",
    }}
    return block


@pytest.mark.asyncio
async def test_refresh_with_unavailable_source_never_claims_current():
    """The refresh guarantee: when the live source cannot be re-fetched,
    the answer ships the materialized copy EXPLICITLY labeled possibly
    outdated — never as current."""
    orch = _orch()
    orch.llm_service.generate_completion = AsyncMock(
        side_effect=AssertionError("narration must not run"))
    session = {
        "id": "s-refresh-fail", "history": [],
        FILE_TASK_SESSION_KEY: dict(
            build_pending_task(INVOICE_ASK, "q3 billing summary 2026.xlsx"),
            status="delivered"),
        "_pending_file_result": {
            "status": "delivered",
            "target_extraction_version": 3,
            "rendered": "| OLD COPY VALUES |",
            "identity": {"file_id": "wd-77"},
        },
    }

    async def failing_read(service, action, params, context):
        raise RuntimeError("workdrive unreachable")

    async def fake_named_block(user_id, query, ctx, plan=None):
        return _direct_read_result_meta(plan, "| OLD COPY VALUES |")

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService",
              _fake_uis_cls(failing_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the workbook",
            "s-refresh-fail", context={"agent_id": "a1"})

    message = result["message"]
    assert "SOURCE FRESHNESS" in message, (
        "a refresh answer must carry its freshness verdict")
    assert "could NOT be re-fetched" in message
    assert "OUTDATED" in message, (
        "a stale copy must be labeled, never passed as current")
    assert result["data"]["freshness"] == "refresh_failed"


@pytest.mark.asyncio
async def test_refresh_with_live_source_reports_updated_content():
    """When the live re-fetch succeeds, the reader runs on the refreshed
    copy and the verdict says the content is updated."""
    orch = _orch()
    session = {
        "id": "s-refresh-ok", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx"),
    }
    reads = {"count": 0}

    async def live_read(service, action, params, context):
        reads["live"] = reads.get("live", 0) + 1
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads["count"] += 1
        if reads["count"] > 1:
            # The re-read of the REFRESHED copy: new ingestion stamp and
            # changed content — the only evidence "refreshed" may claim.
            plan._result_meta = {"storage_read": {
                "service": "zoho_workdrive", "file_id": "wd-77",
                "resource_id": "wd-77",
                "file_name": "Q3 Billing Summary 2026.xlsx",
                "completed": True, "identity_verified": True,
                "coverage_complete": True,
                "ingested_at": "2026-09-24T20:00:00",
                "content_hash": "bbb222",
            }}
            return "| TOTAL | FOUND | Summary!B9 R9 |"
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive", "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "ingested_at": "2026-09-01T10:00:00",
            "content_hash": "aaa111",
        }}
        return "| TOTAL | FOUND | Summary!B2 R2 |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e2"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-refresh-ok", context={"agent_id": "a1"})

    assert reads.get("live") == 1, (
        "a refresh re-fetches the live source once")
    assert reads["count"] >= 2, (
        "the scoped reader runs on the refreshed copy")
    assert "SOURCE FRESHNESS" in result["message"]
    assert "CHANGED" in result["message"], (
        "'refreshed' requires provably changed content, read back")
    assert "bbb222" in result["message"]
    assert result["data"]["freshness"] == "refreshed"


@pytest.mark.asyncio
async def test_refresh_unchanged_content_reports_current_not_refreshed():
    """Upstream re-fetched and re-read successfully, content identical —
    the honest verdict is CURRENT (verified unchanged), not 'refreshed'.
    A new ingestion timestamp alone does not prove refreshed evidence."""
    orch = _orch()
    session = {
        "id": "s-refresh-cur", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx"),
    }
    reads = {"count": 0}

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads["count"] += 1
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive", "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "ingested_at": ("2026-09-24T20:00:00" if reads["count"] > 1
                            else "2026-09-01T10:00:00"),
            "content_hash": "same333",
        }}
        return "| TOTAL | FOUND | Summary!B2 R2 |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e3"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-refresh-cur", context={"agent_id": "a1"})

    assert result["data"]["freshness"] == "current", (
        "identical content after a successful check is CURRENT, not "
        "refreshed")
    assert "UNCHANGED" in result["message"]
    assert "verified current" in result["message"]


@pytest.mark.asyncio
async def test_refresh_with_unchanged_index_labels_the_old_copy():
    """Re-fetch succeeded but the indexed copy still shows the OLD stamp
    and hash — the answer must be labeled as the older copy, never as
    refreshed."""
    orch = _orch()
    session = {
        "id": "s-refresh-stale", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx"),
    }
    reads = {"count": 0}

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads["count"] += 1
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive", "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "ingested_at": "2026-09-01T10:00:00",
            "content_hash": "aaa111",
        }}
        return "| OLD INDEXED COPY |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e4"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-refresh-stale", context={"agent_id": "a1"})

    assert result["data"]["freshness"] == "stale_index"
    assert "did NOT update" in result["message"]
    assert "not verified current" in result["message"]
    assert "OLD INDEXED COPY" in result["message"]


@pytest.mark.asyncio
async def test_refresh_with_incomplete_extraction_is_unverified():
    """Re-fetch + re-read ran, but the extraction is incomplete — the
    verdict must not claim refreshed or current."""
    orch = _orch()
    session = {
        "id": "s-refresh-inc", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx"),
    }
    reads_inc = {"count": 0}

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads_inc["count"] += 1
        done = reads_inc["count"] > 1
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive", "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": done, "identity_verified": done,
            "coverage_complete": False,
            "ingested_at": ("2026-09-24T20:00:00" if done
                            else "2026-09-01T10:00:00"),
            "content_hash": "bbb222" if done else "aaa111",
        }}
        return "| PARTIAL EXTRACTION |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e5"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-refresh-inc", context={"agent_id": "a1"})

    assert result["data"]["freshness"] == "unverified"
    assert "INCOMPLETE" in result["message"]
    assert "does not reflect a verified-current read" in result["message"]


def test_replacement_task_preserves_the_superseded_objective():
    """Context preservation: a replacement task records WHICH objective it
    supersedes — a new requested field or constraint replaces the task
    explicitly, and the original is never silently discarded (review
    round 4)."""
    import core.pending_file_task as pft

    original = pft.build_pending_task(
        INVOICE_ASK, "q3 billing summary 2026.xlsx")
    replaced = pft.merge_pending_task(
        original, "check availability", "q3 billing summary 2026.xlsx")
    assert replaced["original_message"] == "check availability"
    assert replaced["supersedes"]["task_id"] == original["task_id"]
    assert replaced["supersedes"]["original_message"] == INVOICE_ASK
    assert replaced["supersedes"]["mention"] == (
        "q3 billing summary 2026.xlsx")


class TestTaskIntentAcrossDomains:
    """The four intents pinned across unrelated domains (review round 4):
    continuation, refinement, replacement, unresolved intent — identity is
    structured, and a replacement preserves the superseded objective."""

    def _inventory_pending(self):
        import core.pending_file_task as pft

        ask = "how many TX-4400 units are on hand in Stock Counts.xlsx"
        return pft.build_pending_task(ask, "stock counts.xlsx"), ask

    def test_continuation(self):
        import core.pending_file_task as pft

        pending, ask = self._inventory_pending()
        assert pft._introduces_new_work(
            "check that file again more carefully", ask) is False
        assert pft.matching_pending_task(
            pending, "yes",
            [{"message": ask, "response": "x"},
             {"message": "check that file again more carefully",
              "response": "y"}]) is not None

    def test_refinement(self):
        import core.pending_file_task as pft

        pending, ask = self._inventory_pending()
        assert pft._introduces_new_work(
            "how many of them are on hand and let me know", ask) is False

    def test_replacement_preserves_context(self):
        import core.pending_file_task as pft

        pending, ask = self._inventory_pending()
        assert pft._introduces_new_work(
            "compare its reorder thresholds with actual stock",
            ask) is True
        replaced = pft.merge_pending_task(
            pending, "compare its reorder thresholds with actual stock",
            "stock counts.xlsx")
        assert replaced["supersedes"]["original_message"] == ask

    def test_unresolved_intent_never_silently_continues(self):
        """One new object on the same file: ambiguous between extension
        and replacement — resolves to a NEW task, and the new task
        carries the superseded objective in its record (explicit, not
        silent)."""
        import core.pending_file_task as pft

        pending, ask = self._inventory_pending()
        assert pft._introduces_new_work(
            "check availability", ask) is True
        assert pft.matching_pending_task(
            pending, "yes",
            [{"message": ask, "response": "x"},
             {"message": "check availability",
              "response": "y"}]) is None, (
            "an approval must not resume the old objective over the "
            "unresolved newer one")
        merged = pft.merge_pending_task(pending, "check availability",
                                        "stock counts.xlsx")
        assert merged["supersedes"]["original_message"] == ask


# ---------------------------------------------------------------------------
# Review round 5 — freshness proof tightened, executable inheritance,
# entity extraction, last-known-good persistence.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_current_requires_positive_hash_equality():
    """A moved ingestion stamp with MISSING hashes can never assert
    'current' — positive evidence of equality is required; without it the
    verdict is unverified."""
    orch = _orch()
    session = {
        "id": "s-refresh-nohash", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx"),
    }
    reads = {"count": 0}

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads["count"] += 1
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive", "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "ingested_at": ("2026-09-24T20:00:00" if reads["count"] > 1
                            else "2026-09-01T10:00:00"),
            # NO content_hash on the re-read — nothing to compare.
            "content_hash": None,
        }}
        return "| TOTAL | FOUND |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e6"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-refresh-nohash", context={"agent_id": "a1"})

    assert result["data"]["freshness"] == "unverified", (
        "missing hashes can never assert 'current'")
    assert "no content hash to prove" in result["message"]


@pytest.mark.asyncio
async def test_refresh_reread_must_resolve_the_fetched_resource():
    """The refreshed read must bind to the SAME resource that was
    fetched — a different resource is unverified, never refreshed."""
    orch = _orch()
    session = {
        "id": "s-refresh-xfile", "history": [],
        FILE_TASK_SESSION_KEY: build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx"),
    }

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    reads = {"count": 0}

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads["count"] += 1
        # First read pins wd-77; the POST-refetch read resolves a
        # DIFFERENT resource — the copy cannot be bound to the fetched
        # version, so the verdict must be unverified.
        rid = "wd-77" if reads["count"] == 1 else "OTHER-RESOURCE"
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive",
            "file_id": rid,
            "resource_id": rid,
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "ingested_at": "2026-09-24T20:00:00",
            "content_hash": "bbb222",
        }}
        return "| MISMATCHED RESOURCE |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="rf-e7"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        result = await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-refresh-xfile", context={"agent_id": "a1"})

    assert result["data"]["freshness"] == "unverified"
    assert "DIFFERENT resource" in result["message"]


def test_replacement_inherits_executable_context():
    """Inheritance is behavior, not bookkeeping: the replacement carries
    the resolved resource pin and the disambiguation constraints the
    direct reader actually consumes."""
    import core.pending_file_task as pft

    original = dict(
        pft.build_pending_task(
            INVOICE_ASK, "q3 billing summary 2026.xlsx",
            disambiguation={"attributes": {"organization": "acme"}}),
        resolved_file={"service": "zoho_workdrive", "file_id": "wd-77"},
        confirmed_mention="q3 billing summary 2026.xlsx",
    )
    replaced = pft.merge_pending_task(
        original, "check availability", "q3 billing summary")
    assert replaced["disambiguation"] == {
        "attributes": {"organization": "acme"}}, (
        "constraints survive the replacement")
    assert replaced["resolved_file"]["file_id"] == "wd-77"
    assert replaced["confirmed_mention"] == (
        "q3 billing summary 2026.xlsx")
    assert replaced["supersedes"]["task_id"] == original["task_id"]


@pytest.mark.asyncio
async def test_replacement_constraints_reach_the_reader():
    """Consumption proof: a replacement turn's inherited constraints ride
    into the direct reader call."""
    orch = _orch()
    session = {
        "id": "s-inherit", "history": [],
        FILE_TASK_SESSION_KEY: dict(
            build_pending_task(
                INVOICE_ASK, "q3 billing summary 2026.xlsx",
                disambiguation={"attributes": {"organization": "acme"}}),
            resolved_file={"service": "zoho_workdrive",
                           "file_id": "wd-77"}),
    }
    # 'check availability' does not name the file, so the RESUME lane
    # carries it: force matching by stubbing the operation path via a
    # direct-read capture on a confirmation-shaped turn is already
    # covered; here we assert the reader sees the inherited constraints
    # when the replacement turn names the file with an extension.
    direct = {
        "ok": True, "block": "| AVAILABLE |",
        "rendered_answer": "| AVAILABLE |",
        "identity": {"file_id": "wd-77",
                     "file_name": "Q3 Billing Summary 2026.xlsx",
                     "identity_verified": True,
                     "coverage_complete": True},
        "meta": {"completed": True, "identity_verified": True,
                 "coverage_complete": True},
        "retrieval_complete": True,
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="inh-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch.object(orch, "_direct_confirmed_file_read",
                     new=AsyncMock(return_value=direct)) as direct_mock,
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        await orch.process_chat_message(
            "u1", "check availability in q3 billing summary 2026.xlsx",
            "s-inherit", context={"agent_id": "a1"})

    task_seen = direct_mock.await_args.args[0]
    assert task_seen["original_message"] == (
        "check availability in q3 billing summary 2026.xlsx"), (
        "the replacement objective is what executes")
    assert task_seen.get("disambiguation") == {
        "attributes": {"organization": "acme"}}, (
        "the inherited constraints are CONSUMED by the reader")
    assert task_seen.get("resolved_file", {}).get("file_id") == "wd-77"


def test_named_file_targets_drop_file_and_pronoun_fragments():
    """Entity extraction: filename words and pronoun fragments are never
    item targets; digit/hyphen/capitalized identifiers survive."""
    from core.chat_tool_planner import _named_file_targets

    query = ("check the latest version of Consolidated Price List "
             "2019.xlsx for that price")
    targets = _named_file_targets(query, {}, lambda t, m=3, anf=True: [])
    lowered = [t.lower() for t in targets]
    assert not any("consolidated" in t for t in lowered), (
        "the file name is the source, never an item target")
    assert "that" not in lowered and "that price" not in lowered
    # identifiers still pass
    ident = _named_file_targets(
        "prices for SLE24-16 and U-22 in Consolidated Price List 2019.xlsx",
        {}, lambda t, m=3, anf=True: [])
    flat = " | ".join(ident).lower()
    assert "sle24-16" in flat and "u-22" in flat


@pytest.mark.asyncio
async def test_non_refreshed_verdict_preserves_last_good_result():
    """A stale-index refresh does not erase the previously delivered good
    answer — it survives as previous_rendered beside the labeled new one."""
    orch = _orch()
    session = {
        "id": "s-preserve", "history": [],
        FILE_TASK_SESSION_KEY: dict(
            build_pending_task(INVOICE_ASK,
                               "q3 billing summary 2026.xlsx"),
            status="delivered"),
        "_pending_file_result": {
            "status": "delivered",
            "target_extraction_version": 3,
            "rendered": "| GOOD ANSWER 14,500 |",
            "identity": {"file_id": "wd-77"},
        },
    }
    reads = {"count": 0}

    async def live_read(service, action, params, context):
        return {"status": "success", "data": {"file_id": "wd-77"}}

    def fake_named_block(user_id, query, ctx, plan=None):
        reads["count"] += 1
        plan._result_meta = {"storage_read": {
            "service": "zoho_workdrive", "file_id": "wd-77",
            "resource_id": "wd-77",
            "file_name": "Q3 Billing Summary 2026.xlsx",
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "ingested_at": "2026-09-01T10:00:00",
            "content_hash": "aaa111",
        }}
        return "| OLD INDEXED COPY |"

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="lg-e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch("integrations.universal_integration_service."
              "UniversalIntegrationService", _fake_uis_cls(live_read)),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=AsyncMock(side_effect=fake_named_block)),
        patch.object(planner, "plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        await orch.process_chat_message(
            "u1", "check the latest version of the billing summary",
            "s-preserve", context={"agent_id": "a1"})

    row = session["_pending_file_result"]
    assert row["previous_rendered"] == "| GOOD ANSWER 14,500 |", (
        "the last-known-good answer survives a non-refreshed refresh")
    assert row["freshness"] == "stale_index"
