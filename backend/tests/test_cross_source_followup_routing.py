# -*- coding: utf-8 -*-
"""Cross-source follow-up routing (2026-09-29 original-canvas incident).

Live incident (acceptance/original_workbook_email/root_cause_2026_09_29):
after the eight-machine price objective in "Consolidated Price List
2019.xlsx" was delivered, the user asked to CHECK CHANDRAKANT'S EMAIL and
the workbook DESCRIPTIONS to find the correct sheet/row. The turn matched
the loose file-retry shape ("check … workbook … sheet"), was classified a
re-run of the STORED task, and the orchestrator answered by re-running the
price extraction — the email request was swallowed.

Pinned behavior:
1. A follow-up that ADDS a source, changes the requested information, or
   asks to compare descriptions / resolve identities is NOT completed by
   re-running the stored read: it supersedes the stored objective (context
   preserved) and reaches normal planning with the CURRENT instruction.
2. The same holds generically (any person, connector, document) — nothing
   name- or integration-specific.
3. Requested verification wording ("find the correct row", "… for
   confirmation") is an INSTRUCTION, not an approval: confirmation words
   inside a seek-shaped request must not mark the turn lineage.
4. Positive controls stay green: explicit same-read retry, verbose retry,
   refresh, compound retry+presentation, formatting-only, bare approval,
   filename confirmation, and entity-set edits keep their existing lanes.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

import core.chat_tool_planner as planner
import integrations.chat_orchestrator as chat
from core.pending_file_task import (
    FILE_TASK_SESSION_KEY,
    _FILE_RETRY_RE,
    _introduces_new_work,
    build_pending_task,
    classify_file_operation,
    is_filename_confirmation,
    is_rerun_request,
    matching_pending_task,
    recover_pending_task_from_history,
    supersedes_pending_task,
)

# --- Frozen incident fixtures (evidence.json, session replay-retry2-20260923)
INCIDENT_MSG = (
    "check Chandrakant's email and or description in workbook to find "
    "correct sheet and row from workbook for confirmation")
STORED_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
    "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
STORED_MENTION = "consolidated price list 2019.xlsx"
INCIDENT_HISTORY = [
    {"message": STORED_ASK, "response": "the eight prices were delivered"}]
EIGHT_ITEMS = [
    "No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
    "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]


def _delivered_task() -> dict:
    task = build_pending_task(STORED_ASK, STORED_MENTION)
    task["status"] = "delivered"
    task["resolved_file"] = {
        "file_id": "wd-77", "resource_id": "wd-77",
        "file_name": "Consolidated Price List 2019.xlsx",
        "identity_verified": True,
    }
    task["confirmed_mention"] = STORED_MENTION
    task["requested_targets"] = list(EIGHT_ITEMS)
    return task


def _pending_task() -> dict:
    task = build_pending_task(STORED_ASK, STORED_MENTION)
    task["requested_targets"] = list(EIGHT_ITEMS)
    return task


def _orch():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m", "provider": "p",
    })
    orch.llm_service = llm
    return orch


# ---------------------------------------------------------------------------
# 1. The frozen incident: the stored price objective must not own this turn
# ---------------------------------------------------------------------------

class TestFrozenIncidentRouting:
    def test_loose_retry_shape_still_matches_but_is_not_authoritative(self):
        """The regex shape is retained (it is how retry turns are DETECTED);
        the routing decisions below are what stop the substitution."""
        assert _FILE_RETRY_RE.search(INCIDENT_MSG), (
            "fixture drifted — the frozen wording must still match the "
            "retry-shape regex this incident was diagnosed against")
        assert is_filename_confirmation(INCIDENT_MSG) is True
        assert is_rerun_request(INCIDENT_MSG) is True

    def test_delivered_price_task_is_not_resumed_by_the_incident_turn(self):
        assert matching_pending_task(
            _delivered_task(), INCIDENT_MSG, INCIDENT_HISTORY) is None, (
            "the cross-source request must not re-run the stored price "
            "read as the whole objective")

    def test_pending_price_task_is_not_resumed_either(self):
        assert matching_pending_task(
            _pending_task(), INCIDENT_MSG, INCIDENT_HISTORY) is None

    def test_incident_turn_supersedes_the_stored_objective(self):
        assert supersedes_pending_task(_delivered_task(), INCIDENT_MSG) is (
            True), (
            "the stored objective is replaced (context preserved by the "
            "caller), not silently resumed")

    def test_incident_turn_recovers_no_legacy_objective(self):
        assert recover_pending_task_from_history(
            INCIDENT_HISTORY, INCIDENT_MSG) is None, (
            "legacy-state recovery must not reconstruct the old price ask "
            "under the cross-source instruction")

    def test_structured_comparison_names_the_new_work(self):
        assert _introduces_new_work(INCIDENT_MSG, STORED_ASK) is True


# ---------------------------------------------------------------------------
# 2. The helper trap: requested verification is not affirmation
# ---------------------------------------------------------------------------

class TestRequestedVerificationIsNotApproval:
    @pytest.mark.parametrize("msg", [
        "find the correct row",
        "check the workbook rows again for confirmation",
        "verify the description to identify the correct one",
    ])
    def test_verification_wording_introduces_work(self, msg):
        assert _introduces_new_work(msg, STORED_ASK) is True, (
            "confirmation vocabulary inside a seek-shaped request names "
            "requested verification, not approval")

    @pytest.mark.parametrize("msg", [
        "yes",
        "correct.",
        "That filename is correct",
        "yes the September one",
        "yes, go ahead",
    ])
    def test_affirmations_stay_lineage(self, msg):
        assert _introduces_new_work(msg, STORED_ASK) is False, (
            "an approval — even naming one qualifier — is lineage")


# ---------------------------------------------------------------------------
# 3. Generality: no named-entity special cases
# ---------------------------------------------------------------------------

GENERIFIED = [
    # another person + another messaging surface
    "check Meera's chat message and or description in workbook to find "
    "correct sheet and row from workbook for confirmation",
    # retry wording + an extra source retained
    "Search again and check the supplier message to confirm which model",
    # requested information changes from price extraction to identity
    "Use the description in the workbook to identify the correct row",
]


class TestCrossSourceGenerality:
    @pytest.mark.parametrize("msg", GENERIFIED)
    def test_no_resume_for_equivalent_additional_source_requests(self, msg):
        assert matching_pending_task(
            _delivered_task(), msg, INCIDENT_HISTORY) is None, msg
        assert matching_pending_task(
            _pending_task(), msg, INCIDENT_HISTORY) is None, msg

    @pytest.mark.parametrize("msg", GENERIFIED)
    def test_supersession_for_equivalent_additional_source_requests(
            self, msg):
        assert supersedes_pending_task(_delivered_task(), msg) is True, msg


# ---------------------------------------------------------------------------
# 4. Positive controls: the existing distinct behaviors are untouched
# ---------------------------------------------------------------------------

class TestExistingBehaviorsPreserved:
    def test_same_read_retry_continues_the_task(self):
        for msg in ("Search again", "search the file again",
                    "search again more thoroughly"):
            assert matching_pending_task(
                _delivered_task(), msg, INCIDENT_HISTORY) is not None, msg
            assert classify_file_operation(msg) in ("re-run", "refresh"), msg

    def test_refresh_wording_continues_the_task(self):
        msg = "check the latest version of the workbook"
        assert matching_pending_task(
            _delivered_task(), msg, INCIDENT_HISTORY) is not None
        assert classify_file_operation(msg) == "refresh"

    def test_compound_retry_with_presentation_continues(self):
        msg = "Search again and give me a clean response"
        assert matching_pending_task(
            _delivered_task(), msg, INCIDENT_HISTORY) is not None, (
            "a retry plus a presentation preference is one re-run with "
            "style — not new work")

    def test_bare_approvals_and_filename_confirmations_resume_or_redeliver(
            self):
        for msg in ("yes", "go ahead", "That filename is correct"):
            assert matching_pending_task(
                _pending_task(), msg, INCIDENT_HISTORY) is not None, msg
        # terminal task: an approval never re-runs (delivery path owns it)
        assert matching_pending_task(
            _delivered_task(), "go ahead", INCIDENT_HISTORY) is None
        assert matching_pending_task(
            _delivered_task(), "That filename is correct",
            INCIDENT_HISTORY) is None

    def test_entity_set_edit_stays_a_revision_of_the_objective(self):
        msg = "Replace U-22 with U-38"
        assert supersedes_pending_task(_delivered_task(), msg) is False
        assert matching_pending_task(
            _delivered_task(), msg, INCIDENT_HISTORY) is not None

    def test_incident_turn_is_not_a_continuation(self):
        orch = _orch()
        session = {FILE_TASK_SESSION_KEY: _delivered_task()}
        assert orch._continuation_decision(INCIDENT_MSG, session) is None, (
            "the NLU continuation layer must not hand the cross-source "
            "request the rerun contract")

    def test_compound_and_formatting_continuations_survive(self):
        orch = _orch()
        session = {FILE_TASK_SESSION_KEY: _delivered_task()}
        decision = orch._continuation_decision(
            "Search again and give me a clean response", session)
        assert decision is not None
        assert decision["retrieval"] == "rerun"
        assert decision["presentation"]["style"] == "compact"

        fmt = orch._continuation_decision("Make it cleaner", session)
        assert fmt is not None
        assert fmt["retrieval"] == "none"
        assert fmt["presentation"]["style"] == "compact"

        retry = orch._continuation_decision("Search again", session)
        assert retry is not None
        assert retry["retrieval"] == "rerun"


# ---------------------------------------------------------------------------
# 5. Orchestrator: the early-return substitution is gone, context survives
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_incident_turn_routes_to_normal_planning_with_context():
    """The exact incident message on the delivered-task session: no workbook
    re-read, no cached price re-delivery — the CURRENT instruction reaches
    the reply/planning path, and the eight items + source pins survive as
    context."""
    orch = _orch()
    session = {
        "id": "s-incident",
        "history": list(INCIDENT_HISTORY),
        FILE_TASK_SESSION_KEY: _delivered_task(),
        "_pending_file_result": {
            "status": "delivered",
            "rendered": "CACHED PRICE RENDER | SLE24-16 | 8880 |",
            "target_extraction_version": chat._TARGET_EXTRACTION_VERSION_NOW,
            "identity": {"file_id": "wd-77"},
            "structured_result": {
                "attempt_id": "attempt-old",
                "requested_items": list(EIGHT_ITEMS),
            },
        },
    }
    qwen_response = {
        "success": True, "content": "cross-source disambiguation answer",
        "model": "m", "provider": "p",
    }
    no_tool_plan = planner.ToolPlan(use_tool=False)
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e-ix"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_canvas_edit", new=AsyncMock()),
        patch.object(orch, "_try_canvas_action", new=AsyncMock()),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features",
                     new=AsyncMock(return_value={})),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError(
                "the cross-source request must not re-run the workbook "
                "price read"))) as direct_mock,
        patch.object(planner, "plan_tool_use",
                     new=AsyncMock(return_value=no_tool_plan)),
        patch.object(planner, "_provenance_menu",
                     new=AsyncMock(return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence",
                     new=AsyncMock(return_value=[])),
        patch.object(orch, "_get_qwen_response", new=AsyncMock(
            return_value=qwen_response)) as qwen_mock,
    ):
        result = await orch.process_chat_message(
            "u1", INCIDENT_MSG, "s-incident", context={})

    # The stored price read was NOT re-run and the cached render was NOT
    # re-delivered as this turn's answer.
    direct_mock.assert_not_awaited()
    assert result["success"] is True
    assert "CACHED PRICE RENDER" not in str(result.get("message"))
    assert result.get("data", {}).get("deterministic_delivery") is not True

    # The CURRENT instruction reached the normal planning/reply path.
    qwen_mock.assert_awaited_once()
    args, kwargs = qwen_mock.await_args
    assert args[0] == INCIDENT_MSG, (
        "the planner must see the cross-source instruction, not the "
        "stored price ask")
    assert kwargs.get("pending_file_task") is None

    # The stored objective was superseded — not silently resumed — and its
    # context (source pins) stayed reachable for the new objective.
    assert FILE_TASK_SESSION_KEY not in session, (
        "the delivered price objective must not stay resumable over the "
        "newer cross-source instruction")
    stash = session.get("_superseded_file_task_context")
    assert isinstance(stash, dict)
    assert stash.get("resolved_file", {}).get("file_id") == "wd-77"
    assert stash.get("confirmed_mention") == STORED_MENTION
    assert stash.get("requested_targets") == EIGHT_ITEMS, (
        "the ordered target identities ride with the stashed context")

    # The ordered eight items survive as context for the new task.
    assert chat._stored_requested_items(session) == EIGHT_ITEMS


@pytest.mark.asyncio
async def test_plain_retry_still_re_runs_through_the_resume_lane():
    """Positive control at the orchestrator boundary: "search the file
    again" on the same session still re-runs the stored read (the fix must
    not push every retry into narration)."""
    orch = _orch()
    session = {
        "id": "s-retry",
        "history": list(INCIDENT_HISTORY),
        FILE_TASK_SESSION_KEY: _delivered_task(),
        "_pending_file_result": {
            "status": "delivered",
            "rendered": "CACHED PRICE RENDER",
            "target_extraction_version": chat._TARGET_EXTRACTION_VERSION_NOW,
            "identity": {"file_id": "wd-77"},
            "structured_result": {
                "attempt_id": "attempt-old",
                "requested_items": list(EIGHT_ITEMS),
            },
        },
    }
    rendered = "FRESH READ | SLE24-16 | FOUND |"
    direct = {
        "ok": True, "block": rendered, "rendered_answer": rendered,
        "identity": {
            "file_id": "wd-77", "resource_id": "wd-77",
            "file_name": "Consolidated Price List 2019.xlsx",
            "identity_verified": True, "coverage_complete": True,
        },
        "meta": {
            "completed": True, "identity_verified": True,
            "coverage_complete": True,
            "workbook_read": {"coverage": {"complete": True}},
        },
        "retrieval_complete": True,
    }
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e-rt"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle",
              new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch.object(orch, "_get_qwen_response", new=AsyncMock(
            side_effect=AssertionError(
                "an explicit retry is served by the resume lane"))) as qwen_mock,
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=direct)) as direct_mock,
    ):
        result = await orch.process_chat_message(
            "u1", "search the file again", "s-retry", context={})

    direct_task = direct_mock.await_args.args[0]
    assert direct_task["original_message"] == STORED_ASK
    assert result["data"]["deterministic_delivery"] is True
    qwen_mock.assert_not_awaited()
