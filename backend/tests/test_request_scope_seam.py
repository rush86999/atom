"""Request-bound scope at the orchestration-to-executor seam.

Owner-required proofs (2026-10-08 Phase-2 directive), tested at the seam
— not helper-only:
- A fresh request and a changed subject reach executor inputs INTACT;
  old objectives cannot replace new explicit scope (the live case-4
  defect: asked 'No. 381', scanned 'sle24').
- Explicit subsets remain subsets; similarly named subjects stay
  distinct; continuations retain the intended scope.
- An unresolved interpretation leaves the legacy inheritance behavior
  untouched (the floor).
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("TESTING", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))

from core import chat_tool_planner as ctp


# ---------------------------------------------------------------------------
# Reader seam: _resolve_active_items consumes request_scope verbatim
# ---------------------------------------------------------------------------

class TestReaderConsumesRequestScope:
    def test_changed_subject_reaches_reader_verbatim(self):
        """The request names 381; the stored objective holds SLE24-16 and
        canvas rows — the reader must scan 381, not re-derive by mining
        or substring authority."""
        out = ctp._resolve_active_items(
            "Consolidated Price List 2019.xlsx",
            {
                "message": ASK_MESSAGE,
                "requested_targets": ["Tennsmith Single Wheel Slitter "
                                      "SLE24-16"],
                "request_scope": {
                    "subjects": ["No. 381"],
                    "scope_change": "replace",
                    "origin": "llm", "request_id": "r1"},
            },
            ["381", "sle24"])
        assert out == ["No. 381"], (
            "request-bound scope is consumed verbatim — the old "
            "objective cannot replace new explicit scope")

    def test_explicit_subset_stays_subset(self):
        out = ctp._resolve_active_items(
            "wb.xlsx",
            {"message": "Just these two for now: the Linmac U-22 and "
                        "the manual flanger",
             "requested_targets": ["381", "U-22", "Flanger", "622",
                                   "SLE24-16"],
             "request_scope": {"subjects": ["U-22", "Flanger"],
                               "scope_change": "subset"}},
            [])
        assert out == ["U-22", "Flanger"]

    def test_similarly_named_subjects_stay_distinct(self):
        """A shared substring is not evidence the old subject is
        intended — 'Manual Flanger' does not become 'Manual Flanger
        Deluxe'."""
        out = ctp._resolve_active_items(
            "wb.xlsx",
            {"message": "check the Manual Flanger price",
             "requested_targets": ["Manual Flanger Deluxe"],
             "request_scope": {"subjects": ["Manual Flanger"],
                               "scope_change": "replace"}},
            [])
        assert out == ["Manual Flanger"]

    def test_continuation_without_request_scope_retains_scope(self):
        """Legacy path unchanged: a vague follow-up with an active
        objective and NO interpretation inherits it."""
        out = ctp._resolve_active_items(
            "wb.xlsx",
            {"message": "and what about the rest?",
             "requested_targets": ["381", "U-22"]},
            [])
        assert out == ["381", "U-22"]

    def test_extend_retains_both_subjects_through_scan(self):
        """'also check the Linmac U-22' with a prior 'No. 381' objective:
        the scan must receive BOTH — the merged set, not the turn's own
        newly-mined subject alone (the own-first mining rule would
        otherwise drop the old subject)."""
        out = ctp._resolve_active_items(
            "Consolidated Price List 2019.xlsx",
            {
                "message": "also check the price for the Linmac U-22 "
                           "bead roller",
                "requested_targets": ["No. 381", "Linmac U-22"],
                "request_scope": {
                    "subjects": ["No. 381", "Linmac U-22"],
                    "scope_change": "extend"},
            },
            ["381", "u22"])
        assert out == ["No. 381", "Linmac U-22"], (
            "extend merges old + new and the merged set reaches the scan "
            "— the turn's own mining must not drop the old subject")

    def test_timeout_fallback_new_subject_beats_old_objective(self):
        """Interpretation UNAVAILABLE (timeout/unresolved) + a stored old
        objective + a NEW explicit subject in the request: the executor
        must scan the NEW subject — an unresolved label alone does not
        make inheriting the old objective safe."""
        out = ctp._resolve_active_items(
            "Consolidated Price List 2019.xlsx",
            {
                "message": "What is the current price for No. 381?",
                # stored objective from an earlier, different ask
                "requested_targets": [
                    "Tennsmith Single Wheel Slitter SLE24-16"],
            },
            ["381", "sle24"])
        joined = " | ".join(out).lower()
        assert "381" in joined and "sle24" not in joined, (
            "with interpretation unavailable, the turn's own explicit "
            "subject must still outrank the stored objective; got %r"
            % (out,))

    def test_unresolved_scope_falls_through_to_legacy(self):
        out = ctp._resolve_active_items(
            "wb.xlsx",
            {"message": "check it",
             "requested_targets": ["381"],
             "request_scope": {"subjects": [], "scope_change":
                               "unresolved"}},
            [])
        assert out == ["381"]


# ---------------------------------------------------------------------------
# Orchestrator seam: the task carries the accepted scope to the reader
# ---------------------------------------------------------------------------

ASK_MESSAGE = (
    "What is the current price for No. 381 in the "
    "Consolidated Price List 2019 workbook?")

INTERPRETATION = {
    "schema": "turn-interpretation-1",
    "request_id": "req-42",
    "origin": "llm:test-model",
    "actions": [{"kind": "research", "subjects": ["No. 381"],
                 "authorization": "granted"}],
    "subjects": ["No. 381"],
    "sources": ["Consolidated Price List 2019"],
    "requested_fields": ["price"],
    "constraints": [],
    "scope_change": "replace",
    "confidence": 0.9,
}


def _orch():
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m",
        "provider": "p"})
    orch.llm_service = llm
    return orch


def _session_with_active_objective() -> dict:
    return {
        "id": "s-scope-1",
        "_pending_file_result": None,
        "_stored_requested_items": ["Tennsmith Single Wheel Slitter "
                                    "SLE24-16"],
    }


@pytest.mark.asyncio
async def test_changed_subject_reaches_reader_inputs_intact():
    """The full ask lane: stored objective holds SLE24-16; the request
    names 381; the interpretation establishes replace-scope; the reader
    must receive 381 as its requested targets AND its request_scope."""
    from core.turn_decision import INTERPRETATION_SCHEMA

    orch = _orch()
    session = _session_with_active_objective()
    direct = {
        "ok": True, "block": "read done", "rendered_answer": "read done",
        "identity": {"file_name": "Consolidated Price List 2019.xlsx"},
        "meta": {"completed": True, "identity_verified": True,
                 "coverage_complete": True,
                 "structured_result": {
                     "requested_items": ["No. 381"],
                     "targets": []}},
        "retrieval_complete": True,
    }
    with (
        patch.object(orch, "_get_or_create_session",
                     return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e-s1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch.object(orch, "_get_qwen_response",
                     new=AsyncMock(return_value={
                         "success": True, "message": "qwen",
                         "session_id": "s-scope-1"})),
        patch("core.turn_decision.interpret_turn_request",
              new=AsyncMock(return_value=dict(INTERPRETATION))),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=direct)) as direct_mock,
    ):
        await orch.process_chat_message(
            "u1", ASK_MESSAGE, session["id"],
            context={"canvas_id": "fork-1"})

    direct_mock.assert_awaited_once()
    task = direct_mock.await_args.args[0]
    assert task.get("requested_targets") == ["No. 381"], (
        "the changed subject reaches the executor's task intact — the "
        "stored SLE24-16 objective must not replace it")
    rs = task.get("request_scope") or {}
    assert rs.get("subjects") == ["No. 381"]
    assert rs.get("scope_change") == "replace"
    assert rs.get("request_id") == "req-42"
    assert task.get("inherited_targets") is False
