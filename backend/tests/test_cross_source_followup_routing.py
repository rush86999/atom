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

import json
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
    request_extends_objective,
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


# DOMAIN INDEPENDENCE MATRIX (2026-09-29 review): the same decision must
# hold for ANY source/target pair — messaging surfaces, calendars, PDFs,
# CSVs, CRM records, drive docs, plain notes — not just the incident's
# email+workbook. Each row: (stored objective, mention, a cross-source
# follow-up in the incident's shape, an explicit same-read retry).
DOMAIN_MATRIX = [
    ("find the rescheduled dates for the vendor visits in "
     "catering_contracts.pdf",
     "catering_contracts.pdf",
     "check the calendar invites and or notes in the pdf to find correct "
     "page and row for confirmation",
     "read the pdf again"),
    ("find the invoice totals in the Q3 billing summary",
     "q3 billing summary",
     "check the CRM record and or description in billing to find correct "
     "entry and total from billing for confirmation",
     "check the totals again"),
    ("find the churn reasons in churn_export.csv",
     "churn_export.csv",
     "check Dana's slack thread and or description in the csv to find "
     "correct column and row for confirmation",
     "search the csv again"),
    ("find the approved budgets in the 2027 planning sheet",
     "2027 planning sheet",
     "check the shared drive memo and or description in the sheet to find "
     "correct tab and cell for confirmation",
     "open the sheet again"),
    ("find the onboarding steps in the handbook notes",
     "handbook notes",
     "check the wiki page and or summary in the notes to find correct "
     "section for confirmation",
     "search the notes again"),
    # NON-BUSINESS domains (2026-09-29 owner audit): the decision must
    # hold where no commerce exists at all — cooking, training logs,
    # academic reading. If any guard only works because the incident was
    # a price list, these rows fail.
    ("find the oven temperatures for these 4 breads in my recipe log.xlsx",
     "recipe log.xlsx",
     "check the chef's video notes and or description in the sheet to "
     "find correct row and temperature for confirmation",
     "search the sheet again"),
    ("find the pace targets for these 5 intervals in training_plan.csv",
     "training_plan.csv",
     "check the coach's message and or notes in the file to find correct "
     "row and pace for confirmation",
     "search the file again"),
    ("find the publication years for these 6 papers in the reading list",
     "reading list",
     "check the author's abstract and or summary in the list to find "
     "correct entry and year for confirmation",
     "search the list again"),
]


class TestDomainIndependence:
    @pytest.mark.parametrize("orig,mention,followup,retry", DOMAIN_MATRIX)
    def test_cross_source_followup_supersedes_in_every_domain(
            self, orig, mention, followup, retry):
        task = build_pending_task(orig, mention)
        task["status"] = "delivered"
        assert request_extends_objective(followup, task) is True, followup
        assert supersedes_pending_task(task, followup) is True, followup
        assert matching_pending_task(
            task, followup, [{"message": orig, "response": "x"}]) is None, (
            f"{followup!r} must not resume the stored read")
        # The same-read retry control stays lineage in the same domain.
        assert matching_pending_task(
            task, retry, [{"message": orig, "response": "x"}]) is not None, (
            f"{retry!r} must keep resuming the stored read")

    @pytest.mark.parametrize("orig,mention", [
        (o, m) for o, m, _f, _r in DOMAIN_MATRIX])
    def test_approvals_stay_lineage_in_every_domain(self, orig, mention):
        task = build_pending_task(orig, mention)
        for approval in ("yes", "go ahead", "correct."):
            assert request_extends_objective(approval, task) is False
            assert matching_pending_task(
                task, approval, [{"message": orig, "response": "x"}]) is not (
                None), (orig, approval)


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


# ---------------------------------------------------------------------------
# 6. Anaphoric file reference ("find this in the workbook") — the row-338
#    incident (2026-09-29): the user gave the exact Tennsmith row and value
#    and said "find this in the workbook". The message names no extension-
#    ful filename, so the deterministic file-ask lane never fired; the turn
#    fell to mail/integration planning that cannot match workbook cells.
#    When the conversation holds a RESOLVED spreadsheet identity (live task
#    or the supersession stash), the generic reference IS that file.
# ---------------------------------------------------------------------------

ROW338_MSG = (
    "roper whitney and tennsmith are 2 brands under 1 ownership and they "
    "sometimes mix the names. no. 381 is on Tennsmith sheet of the workbook "
    "under row 338. under roll bending machines --- here's the data: 381\t"
    "167072381\t\tRoll Bending Machine,\t $3,254.00 . find this in the "
    "workbook")
RESOLVED_IDENTITY = {
    "file_id": "wd-77", "resource_id": "wd-77",
    "file_name": "Consolidated Price List 2019.xlsx",
    "identity_verified": True,
}


def _session_with_stash() -> dict:
    import uuid as _uuid

    return {
        "id": f"s-anaphoric-{_uuid.uuid4().hex[:8]}",
        "history": list(INCIDENT_HISTORY),
        "_superseded_file_task_context": {
            "resolved_file": dict(RESOLVED_IDENTITY),
            "confirmed_mention": STORED_MENTION,
            "requested_targets": list(EIGHT_ITEMS),
        },
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


class TestAnaphoricFileReference:
    @pytest.mark.asyncio
    async def test_generic_workbook_reference_reads_the_resolved_file(self):
        orch = _orch()
        session = _session_with_stash()
        rendered = ("Workbook read: Consolidated Price List 2019.xlsx\n"
                    "| 381 | FOUND | Tennsmith!A338 R338 [PRICE=3254] |")
        direct = {
            "ok": True, "block": rendered, "rendered_answer": rendered,
            "identity": dict(RESOLVED_IDENTITY, coverage_complete=True),
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
            patch.object(orch, "_start_chat_execution", return_value="e-an"),
            patch.object(orch, "_record_chat_step", new=AsyncMock()),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_update_session"),
            patch("core.chat_mini_app_authoring.try_handle",
                  new=AsyncMock(return_value=None)),
            patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
            patch.object(orch, "_route_to_features",
                         new=AsyncMock(return_value={})),
            patch.object(orch, "_get_qwen_response", new=AsyncMock(
                side_effect=AssertionError(
                    "a targeted same-workbook ask must not fall to generic "
                    "mail/integration planning"))) as qwen_mock,
            patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
                return_value=direct)) as direct_mock,
        ):
            result = await orch.process_chat_message(
                "u1", ROW338_MSG, session["id"], context={})

        direct_mock.assert_awaited_once()
        task = direct_mock.await_args.args[0]
        assert task["mention"] == STORED_MENTION, (
            "the generic 'the workbook' reference resolves to the "
            "conversation's resolved file identity")
        assert task["original_message"] == ROW338_MSG
        assert task.get("resolved_file", {}).get("file_id") == "wd-77", (
            "the pinned resource rides with the read")
        assert result["data"]["deterministic_delivery"] is True
        qwen_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_resolved_identity_stays_with_normal_planning(self):
        orch = _orch()
        session = _session_with_stash()
        del session["_superseded_file_task_context"]["resolved_file"]
        with (
            patch.object(orch, "_get_or_create_session", return_value=session),
            patch.object(orch, "_resolve_canvas_ctx",
                         new=AsyncMock(return_value=None)),
            patch.object(orch, "_start_chat_execution", return_value="e-an2"),
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
                    "with nothing to resolve the reference to, the "
                    "deterministic lane must not fire"))) as direct_mock,
            patch.object(planner, "plan_tool_use", new=AsyncMock(
                return_value=planner.ToolPlan(use_tool=False))),
            patch.object(planner, "_provenance_menu",
                         new=AsyncMock(return_value="")),
            patch("core.memory_context_assembler.assembly_enabled",
                  return_value=False),
            patch.object(chat, "_verbatim_mail_evidence",
                         new=AsyncMock(return_value=[])),
            patch.object(orch, "_get_qwen_response", new=AsyncMock(
                return_value={"success": True, "content": "honest answer",
                              "model": "m", "provider": "p"})),
        ):
            await orch.process_chat_message(
                "u1", ROW338_MSG, session["id"], context={})
        direct_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_confirmation_and_question_forms_never_read(self):
        orch = _orch()
        for msg in ("that workbook is correct", "is the workbook correct",
                    "which sheet is it in the workbook?"):
            session = _session_with_stash()
            with (
                patch.object(orch, "_get_or_create_session",
                             return_value=session),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=None)),
                patch.object(orch, "_start_chat_execution", return_value="e"),
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
                patch.object(orch, "_direct_confirmed_file_read",
                             new=AsyncMock(side_effect=AssertionError(msg))),
                patch.object(planner, "plan_tool_use", new=AsyncMock(
                    return_value=planner.ToolPlan(use_tool=False))),
                patch.object(planner, "_provenance_menu",
                             new=AsyncMock(return_value="")),
                patch("core.memory_context_assembler.assembly_enabled",
                      return_value=False),
                patch.object(chat, "_verbatim_mail_evidence",
                             new=AsyncMock(return_value=[])),
                patch.object(orch, "_get_qwen_response", new=AsyncMock(
                    return_value={"success": True, "content": "ok",
                                  "model": "m", "provider": "p"})),
            ):
                await orch.process_chat_message("u1", msg, session["id"],
                                                context={})


class TestAnaphoricPinReachesTheReader:
    """The row-338 chain has TWO seams: the orchestrator must resolve
    "the workbook" (covered above), and the reader must accept the
    resolved pin when the ask text itself names no file."""

    @pytest.mark.asyncio
    async def test_named_file_block_resolves_through_the_pinned_mention(
            self):
        from core.chat_tool_planner import _datasets_named_file_block

        catalog_entries = [
            {"source": "catalog", "external_id": "wb-2019",
             "file_name": "Consolidated Price List 2019.xlsx"},
            {"source": "catalog", "external_id": "sept-2026",
             "file_name": "All Prices For All Parts INDUSTRIAL "
                          "Sept 2026.xlsx"},
        ]

        def fake_probe(entries, token, max_rows):
            if entries and entries[0].get("external_id") == "wb-2019":
                return {"file_name": entries[0]["file_name"],
                        "entity_name": "Tennsmith",
                        "columns": ["MODEL NO.", "PRICE"],
                        "rows": [{"__row__": 338, "MODEL NO.": "381",
                                  "PRICE": 3254}],
                        "row_count": 1}
            return None

        with (
            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                  return_value=True),
            patch("core.sheet_dataset_service.find_entries_sync",
                  return_value=list(catalog_entries)),
            patch("core.sheet_dataset_service._probe_cached",
                  side_effect=fake_probe),
            patch("core.sheet_dataset_service.candidate_probe_tokens",
                  return_value=["167072381", "381", "3254"]),
        ):
            # The ask text names NO file; the pin scopes the read.
            block = await _datasets_named_file_block(
                "u1", ROW338_MSG,
                {"workspace_id": "ws",
                 "named_file_mention": "consolidated price list 2019.xlsx"},
            )
        assert block, "the pinned mention must scope the read"
        assert "Consolidated Price List 2019.xlsx" in block
        assert "Sept 2026" not in block

    @pytest.mark.asyncio
    async def test_no_pin_and_no_name_stays_none(self):
        from core.chat_tool_planner import _datasets_named_file_block

        with (
            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                  return_value=True),
            patch("core.sheet_dataset_service.find_entries_sync",
                  return_value=[]),
        ):
            block = await _datasets_named_file_block(
                "u1", ROW338_MSG, {"workspace_id": "ws"})
        assert block is None, (
            "without a text name or a resolved pin there is nothing to "
            "scope the read to")

    @pytest.mark.asyncio
    async def test_direct_read_threads_the_resolved_pin(self):
        captured = {}

        async def fake_block(user_id, query, context, plan=None):
            captured.update(context or {})
            return "BLOCK"

        orch = _orch()
        task = {
            "mention": "consolidated price list 2019.xlsx",
            "original_message": ROW338_MSG,
            "resolved_file": dict(RESOLVED_IDENTITY),
        }
        with patch("core.chat_tool_planner._datasets_named_file_block",
                   side_effect=fake_block):
            result = await orch._direct_confirmed_file_read(
                task, [], "u1", "s1", "ws")
        assert result["ok"] is True
        assert captured.get("named_file_mention") == (
            "Consolidated Price List 2019.xlsx"), (
            "the resolved identity's name, not just the loose mention, "
            "scopes the reader")


# ---------------------------------------------------------------------------
# 7. Cheap-NLU refinement layers (2026-09-29 generalization pass): the
#    deterministic noun-list floors stay authoritative in tests (TESTING=1
#    disables every LLM call); the semantic RESIDUE is judged by
#    core/llm/cheap_nlu.py — fail-closed, so None/NO keeps floor behavior.
# ---------------------------------------------------------------------------

class TestCheapNluRefinements:
    def test_floor_resolves_generic_document_nouns_without_llm(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        async def _resolve(msg):
            return await chat_mod._resolve_anaphoric_file_mention(
                msg, _session_with_stash())

        for msg in ("find this in the workbook",
                    "locate that row in the document",
                    "find the price from the report",
                    "find the model in the sheet"):
            assert asyncio.run(_resolve(msg)) == STORED_MENTION, msg
        # Unknown generic noun: floor declines, no LLM under TESTING.
        assert asyncio.run(_resolve("find this in the tracker")) == ""

    def test_llm_yes_resolves_unknown_generic_noun(self, monkeypatch):
        import asyncio

        import core.llm.cheap_nlu as cheap
        import integrations.chat_orchestrator as chat_mod

        async def yes(message, file_name, llm_service=None):
            assert llm_service is None or True
            return True

        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setattr(cheap, "refers_to_resolved_file", yes)
        monkeypatch.setattr(chat_mod, "_GENERIC_FILE_REF_RE",
                            __import__("re").compile(r"(?!x)x"))
        resolved = asyncio.run(
            chat_mod._resolve_anaphoric_file_mention(
                "find this in the tracker", _session_with_stash()))
        assert resolved == STORED_MENTION

    def test_llm_no_keeps_normal_planning(self, monkeypatch):
        import asyncio

        import core.llm.cheap_nlu as cheap
        import integrations.chat_orchestrator as chat_mod

        async def no(message, file_name, llm_service=None):
            return False

        monkeypatch.delenv("TESTING", raising=False)
        monkeypatch.setattr(cheap, "refers_to_resolved_file", no)
        monkeypatch.setattr(chat_mod, "_GENERIC_FILE_REF_RE",
                            __import__("re").compile(r"(?!x)x"))
        resolved = asyncio.run(
            chat_mod._resolve_anaphoric_file_mention(
                "find this in the tracker", _session_with_stash()))
        assert resolved == ""


class TestPossessiveSourceRefinement:
    def test_candidates_exclude_floor_nouns_and_keep_the_tail(self):
        from core.workbook_read_artifact import possessive_source_candidates

        text = ("check Priya's email and Meera's Notion page and "
                "Brennan Machinery's quote totals")
        cands = {c["possessor"]: c["noun"]
                 for c in possessive_source_candidates([text])}
        assert "Priya" not in cands, "email is settled by the floor"
        assert cands.get("Meera") == "Notion", cands
        assert "Brennan Machinery" in cands, cands

    def test_source_reference_names_skip_the_org_constraint(self, tmp_path):
        import pandas as pd

        from core.workbook_read_artifact import (
            _disambiguation_criteria,
            inspect_dataset_entries,
        )

        history = "check Meera's Notion page and or description in workbook"
        with_ref = _disambiguation_criteria(
            "find 381 in the workbook", [history],
            None, source_reference_names=["Meera"])
        without = _disambiguation_criteria(
            "find 381 in the workbook", [history], None)
        assert any("meera" in str(v).lower() for vs in without.values()
                   for v in vs)
        assert not any("meera" in str(v).lower()
                       for vs in with_ref.values() for v in vs)

        # Attribute possessives are untouched by the refinement.
        kept = _disambiguation_criteria(
            "Brennan Machinery's quote totals", ["same"], None,
            source_reference_names=["Meera"])
        assert any("brennan" in str(v).lower()
                   for vs in kept.values() for v in vs), kept

    def test_floor_now_covers_generic_communication_nouns(self):
        from core.workbook_read_artifact import _disambiguation_criteria

        for tail in ("ticket comments", "memo", "notes", "letter",
                     "announcement"):
            criteria = _disambiguation_criteria(
                f"check Maya's {tail} in the workbook",
                [f"check Maya's {tail} in the workbook"], None)
            assert not any("maya" in str(v).lower()
                           for vs in criteria.values() for v in vs), tail


# ---------------------------------------------------------------------------
# 8. Intent-based retry of a FAILED background edit (2026-09-29 live):
#    "try again" after "Background update failed" must re-dispatch the
#    EDIT (the newest unresolved action), not fall back to the older
#    workbook read. Detection is durable: the failed fork's continuation
#    record carries canvas_id + outcome; the original instruction is the
#    user message that spawned it.
# ---------------------------------------------------------------------------

class TestFailedEditRetryIntent:
    def _fake_failed_row(self, monkeypatch, instruction, canvas_id="c-orig",
                         outcome="failed"):
        """Stub the durable scan: one terminal (failed OR conflict)
        continuation row + the user message that spawned it."""
        import integrations.chat_orchestrator as chat_mod

        def fake_target(session_id, message, history=None):
            from core.pending_file_task import (
                _RETRY_LINEAGE_VOCABULARY,
                _introduces_new_work,
                is_bare_action_retry,
                is_filename_confirmation,
                is_rerun_request,
            )

            t = (message or "").strip()
            if not (is_rerun_request(t) or is_filename_confirmation(t)
                    or is_bare_action_retry(t)):
                return None
            if _introduces_new_work(
                    t, instruction,
                    extra_anchor=_RETRY_LINEAGE_VOCABULARY):
                return None
            return {"instruction": instruction, "canvas_id": canvas_id,
                    "execution_id": "exec-1", "outcome": outcome}

        monkeypatch.setattr(chat_mod, "_failed_edit_retry_target",
                            fake_target)

    def test_conflict_outcome_is_retryable_too(self, monkeypatch):
        """Live 2026-09-29 23:34: a CONFLICT held the background edit back
        ("Re-ask and it will run against the current canvas") — and the
        user's bare "try again" fell to the older workbook read instead.
        A conflict is an un-landed edit: the retry must re-dispatch it."""
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        # Drive the REAL detector with a stubbed durable layer: one
        # conflict continuation row + the instruction that spawned it.
        from unittest.mock import patch

        class _FakeRow:
            created_at = None
            metadata_json = json.dumps({"continuation": str({
                "id": "cont-9", "outcome": "conflict",
                "canvas_id": "c-orig"})})
        import datetime as _dt
        _FakeRow.created_at = _dt.datetime.now()

        class _FakeQuery:
            def __init__(self, *a, **k): pass
            def filter(self, *a, **k): return self
            def order_by(self, *a, **k): return self
            def limit(self, *a, **k): return self
            def all(self): return [_FakeRow()]
            def first(self):
                return type("R", (), {"content": "original instruction",
                                      "created_at": _FakeRow.created_at})()

        import core.database as db_mod

        class _FakeSession:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def query(self, *a, **k): return _FakeQuery()

        with patch.object(db_mod, "get_db_session",
                          return_value=_FakeSession()):
            out = chat_mod._failed_edit_retry_target(
                "sess-1", "try again", [])
        assert out is not None, (
            "a conflict outcome must be re-dispatched by a bare retry")
        assert out["canvas_id"] == "c-orig"
        assert out["instruction"] == "original instruction"

    def test_bare_retry_targets_the_failed_edit(self, monkeypatch):
        import asyncio

        orch = _orch()
        self._fake_failed_row(
            monkeypatch,
            "as you found the latest price for the roper 381 roll bender, "
            "update the email price accordingly")
        for msg in ("try again", "try it", "go ahead, try again"):
            target = chat._failed_edit_retry_target("sess-1", msg, [])
            assert target is not None, msg
            assert "update the email price" in target["instruction"]
            assert target["canvas_id"] == "c-orig"

    def test_new_substantive_turn_does_not_resume_the_edit(self, monkeypatch):
        import asyncio

        orch = _orch()
        self._fake_failed_row(
            monkeypatch, "update the email price accordingly")
        for msg in ("find the prices of these 8 machines in Consolidated "
                    "Price List 2019.xlsx: No. 381, U-22",
                    "what did the supplier say about lead times?"):
            assert chat._failed_edit_retry_target("sess-1", msg, []) is None, (
                f"{msg!r} is new work, not a retry of the edit")

    @pytest.mark.asyncio
    async def test_retry_turn_reaches_the_edit_lane_with_the_original(
            self, monkeypatch):
        """Orchestrator-level: 'try again' on a failed-edit session plans
        the ORIGINAL instruction against the recorded canvas — the read
        lane must not own the turn."""
        orch = _orch()
        instruction = ("as you found the latest price for the roper 381 "
                       "roll bender, update the email price accordingly")
        canvas = {"canvas_id": "c-orig", "canvas_type": "document",
                  "content": {"content": "email body"}}
        session = {"id": "s-edit-retry", "history": [
            {"message": instruction, "response": {"message": "ok"}}]}
        edit_result = {"success": True, "message": "applied",
                       "data": {"canvas_edit": {"updated": True}}}
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_resolve_canvas_ctx",
                         new=AsyncMock(return_value=canvas)),
            patch.object(chat, "_failed_edit_retry_target",
                         return_value={"instruction": instruction,
                                       "canvas_id": "c-orig",
                                       "execution_id": "exec-1"}),
            patch.object(chat, "_begin_task_edit",
                         return_value={"status": "legacy"}),
            patch.object(chat, "_canvas_edit_shaped",
                         return_value=True),
            patch.object(orch, "_start_chat_execution",
                         return_value="e-er"),
            patch.object(orch, "_record_chat_step", new=AsyncMock()),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_update_session"),
            patch("core.chat_mini_app_authoring.try_handle",
                  new=AsyncMock(return_value=None)),
            patch.object(orch, "_try_canvas_edit", new=AsyncMock(
                return_value=edit_result)) as edit_mock,
            patch.object(orch, "_direct_confirmed_file_read",
                         new=AsyncMock(side_effect=AssertionError(
                             "the read lane must not own the retry"))),
        ):
            result = await orch.process_chat_message(
                "u1", "try again", "s-edit-retry", context={})
        assert result["success"] is True
        planned = edit_mock.await_args.args[0]
        assert planned == instruction, (
            "the edit lane must plan the ORIGINAL instruction, not the "
            "bare retry")

    def test_successful_outcomes_are_not_retry_targets(self, monkeypatch):
        """No duplicate mutations: once the edit APPLIED (or awaits the
        user's approval), a bare "try again" must NOT re-dispatch it —
        only un-landed outcomes (failed, conflict) are retryable."""
        import integrations.chat_orchestrator as chat_mod
        from unittest.mock import patch
        import datetime as _dt

        for outcome in ("applied", "already_applied", "awaiting_approval"):
            class _FakeRow:
                created_at = _dt.datetime.now()
                metadata_json = json.dumps({"continuation": str({
                    "id": "cont-ok", "outcome": outcome,
                    "canvas_id": "c-orig"})})

            class _FakeQuery:
                def __init__(self, *a, **k): pass
                def filter(self, *a, **k): return self
                def order_by(self, *a, **k): return self
                def limit(self, *a, **k): return self
                def all(self): return [_FakeRow()]
                def first(self):
                    return type("R", (), {
                        "content": "update the email price accordingly",
                        "created_at": _FakeRow.created_at})()

            class _FakeSession:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def query(self, *a, **k): return _FakeQuery()

            import core.database as db_mod

            with patch.object(db_mod, "get_db_session",
                              return_value=_FakeSession()):
                out = chat_mod._failed_edit_retry_target(
                    "sess-1", "try again", [])
            assert out is None, (outcome, out)


# ---------------------------------------------------------------------------
# 9. RERUN-INHERITANCE (2026-09-30 gap fix): "repeat the search and
#    learn to include tennsmith sheet for roper whitney searches" — the
#    sentence is rerun-shaped, EXTENDS the stored objective (supersession
#    pops the task), and names no spreadsheet file, so it fell to
#    narration. The research lane must inherit the superseded objective's
#    file identity: a rerun-shaped message naming file vocabulary, with
#    no file mention of its own and no communication-source object,
#    resolves to the stash's spreadsheet identity.
# ---------------------------------------------------------------------------

class TestRerunInheritance:
    def test_exact_gap_sentence_resolves_to_stashed_identity(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "repeat the search and learn to include tennsmith sheet for "
            "roper whitney searches", _session_with_stash()))
        assert resolved == STORED_MENTION, resolved

    def test_rerun_without_file_vocabulary_does_not_inherit(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        for msg in ("check the email thread again",
                    "try the inbox search once more"):
            resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
                msg, _session_with_stash()))
            assert resolved == "", msg

    def test_message_with_own_mention_not_overridden(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        # the anaphoric floor declines (no generic ref); own file
        # mentions are handled by the mention detector upstream, and the
        # inheritance must not fire when the message names a DIFFERENT
        # file outright
        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "repeat the search in vendor_catalog.xlsx", _session_with_stash()))
        assert resolved == "", (
            "an explicit different-file mention is the mention detector's "
            "call, not inheritance")

    def test_no_stash_no_inheritance(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "repeat the search in the workbook", {"history": []}))
        assert resolved == ""


# ---------------------------------------------------------------------------
# 10. NAMED-SHEET FOLLOW-UP (2026-09-30): the follow-up to the sentence in
#     section 9 — "show me the tennsmith sheet searches" — was answered
#     with a BYTE-IDENTICAL copy of the previous reply. That follow-up is
#     not rerun-shaped ("show me" is neither a retry verb nor "again"), and
#     it carries no preposition, so `_GENERIC_FILE_REF_RE` declined it and no
#     file identity resolved: the turn fell to narration, which re-served
#     the prior answer verbatim. A reader narrowing a search within the
#     workbook is still asking the workbook, so a NAMED-SHEET REFERENCE must
#     resolve to the conversation's own spreadsheet without requiring a
#     preposition.
#
#     Scope of the fix, deliberately narrow: this seam resolves the FILE
#     only. Which sheet is meant is settled in `core.chat_tool_planner` by
#     `resolve_requested_sheets`, against the sheets the file actually
#     indexes — a place where a wrong guess can be caught rather than acted
#     on. Every existing exclusion still runs first.
# ---------------------------------------------------------------------------

class TestNamedSheetFollowUpResolves:
    def test_the_exact_follow_up_sentence_resolves(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "show me the tennsmith sheet searches", _session_with_stash()))
        assert resolved == STORED_MENTION, resolved

    @pytest.mark.parametrize("message", [
        "show me the tennsmith sheet",
        "price on the Tennsmith tab",
        "what's on the tennsmith worksheet",
    ])
    def test_prepositionless_named_sheet_references_resolve(self, message):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            message, _session_with_stash()))
        assert resolved == STORED_MENTION, message

    def test_a_generic_sheet_reference_still_does_not_resolve(self):
        # "the sheet" names no sheet; resolving it would attach a workbook
        # read to any turn that happens to say the word.
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        for msg in ("show me the sheet", "list each sheet", "clean up the tab"):
            resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
                msg, _session_with_stash()))
            assert resolved == "", msg

    def test_a_question_is_never_resolved(self):
        # The "?" guard precedes this seam: a question about a sheet is the
        # asker's, not a read instruction.
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "is the tennsmith sheet the right one?", _session_with_stash()))
        assert resolved == ""

    def test_a_cross_source_turn_is_never_resolved(self):
        # The communication-source exclusion is GLOBAL and FIRST; naming a
        # sheet must not become a way around it.
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "check priya's email and the tennsmith sheet",
            _session_with_stash()))
        assert resolved == ""

    def test_naming_a_sheet_does_not_invent_a_file(self):
        # With no spreadsheet identity held, a sheet reference resolves to
        # nothing — the seam inherits an identity, it never mints one.
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "show me the tennsmith sheet", {"history": []}))
        assert resolved == ""

    def test_a_non_spreadsheet_identity_does_not_match(self):
        import asyncio

        import integrations.chat_orchestrator as chat_mod

        session = {"history": [], "_superseded_file_task_context": {
            "resolved_file": {"file_name": "vendor_notes.pdf"}}}
        resolved = asyncio.run(chat_mod._resolve_anaphoric_file_mention(
            "show me the tennsmith sheet", session))
        assert resolved == ""
