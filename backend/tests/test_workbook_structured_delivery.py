# -*- coding: utf-8 -*-
"""Structured workbook delivery — slice-2 wiring acceptance.

Covers the live-integration gate with domain-independent fixtures (no
real product names drive the logic; the incident's eight-machine shape is
rebuilt synthetically):
1. Requested-item authority: raw probe tokens resolve to the ordered ask.
2. Artifact-native targets: same-row citations group, distinct rows stay.
3. Presentation signal: generic formatting language re-renders; re-run wins.
4. Producer helper builds a versioned record with a fresh attempt identity.
5. Delivery branches: formatting re-render (no retrieval), transport retry
   (pinned verbatim), explicit re-search (new attempt recorded).
6. Durability: the structured record + pin survive session persistence
   and reload; deterministic lanes never touch narration or streaming.
"""
from __future__ import annotations

import hashlib
import json
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

import integrations.chat_orchestrator as chat
from core import answer_presentation as ap
from core.pending_file_task import is_retrieval_refresh_request


def _decision(message):
    orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
    return orch._continuation_decision(message)


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


def _orch():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(
        side_effect=AssertionError("must not narrate"))
    llm.stream_completion = AsyncMock(
        side_effect=AssertionError("must not stream"))
    orch.llm_service = llm
    return orch


def _ev(sheet, row, cell, values, alias=None):
    return {"sheet": sheet, "row": row, "cell": cell, "value": "hit",
            "column": "Model", "matched_alias": alias, "values": values,
            "prices": values}


def _v(cell, raw, basis):
    return {"cell": cell, "value": raw, "column": basis, "field": basis,
            "price_basis": basis}


SYNTHETIC_OUTCOMES = {
    # Same row, three matching cells -> one candidate (row-grouped).
    "M-1": {"target": "M-1", "status": "found", "evidence": [
        _ev("SheetA", 88, "A88", [_v("E88", "", "PRICE"),
                                  _v("M88", "10", "LIST"),
                                  _v("P88", "0", "COST")]),
        _ev("SheetA", 88, "B88", [_v("E88", "", "PRICE"),
                                  _v("M88", "10", "LIST"),
                                  _v("P88", "0", "COST")]),
    ]},
    # Distinct rows -> distinct candidates.
    "M-2": {"target": "M-2", "status": "ambiguous", "evidence": [
        _ev("SheetA", 101, "A101", [_v("D101", "8040", "Price"),
                                    _v("H101", "3950", "Factory Price")]),
        _ev("SheetB", 105, "A105", [_v("D105", "9000", "Price")]),
    ]},
}


def _record(**over):
    targets = ap.build_targets_from_scan(
        ["M-1", "M-2"], SYNTHETIC_OUTCOMES, {})
    rec = ap.build_structured_record(
        source_identity={"file_name": "w.xlsx",
                         "ingested_at": "2026-09-07"},
        evidence_revision="rev-1",
        attempt_id=ap.new_attempt_id(),
        evidence_action="new_read",
        requested_items=["M-1", "M-2"],
        requested_fields=["price"],
        targets=targets,
        coverage={"indexed_sheets": 2},
    )
    rec.update(over)
    return rec


# 1. Requested-item authority -------------------------------------------------

class TestResolveRequestedItems:
    def test_alias_tokens_consolidate(self):
        raw = ["381", "U-22", "622", "1624", "TK 1624",
               "Manual Flanger", "TK Manual Flanger"]
        assert ap.resolve_requested_items(raw) == [
            "381", "U-22", "622", "TK 1624", "TK Manual Flanger"]

    def test_distinct_models_never_merge(self):
        assert ap.resolve_requested_items(["381", "622"]) == ["381", "622"]
        assert ap.resolve_requested_items(["381", "381mm"]) == ["381", "381mm"]
        assert ap.resolve_requested_items(
            ["GSL48-16", "SLE24-16"]) == ["GSL48-16", "SLE24-16"]

    def test_long_product_names_survive(self):
        # No length cap: a realistic six-word model name is one item.
        long_name = "Acme Industrial Heavy Duty Gang Slitter"
        raw = [long_name, "U-22",
               "find the prices of these machines in w.xlsx"]
        assert long_name in ap.resolve_requested_items(raw)

    def test_exact_original_eight_in_requested_order(self):
        # The incident ask: literal names, requested order, no substitutes.
        from core.chat_tool_planner import _named_file_targets

        ask = ("find the prices of these 8 machines in Consolidated Price "
               "List 2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, "
               "SLE24-16, TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
        toks = _named_file_targets(ask, {}, None)
        assert ap.resolve_requested_items(toks, order_hint=ask) == [
            "No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
            "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]

    def test_honorific_matches_bare_cells(self):
        from core.workbook_read_artifact import _matches_target

        assert _matches_target("No. 381", "381")
        assert _matches_target("No. 622", "No. 622")
        assert not _matches_target("No. 381", "381mm")
        assert not _matches_target("381", "381mm")

    def test_cross_turn_glue_never_forms(self):
        # Live 2026-09-26: a re-search turn mined "U-38 give me a cleaner
        # response" from the joined history. Phrases never span turns.
        from core.chat_tool_planner import _named_file_targets

        ask = ("find the prices of these 8 machines in w.xlsx: 381, U-22, "
               "622 and U-38")
        ctx = {"history": [
            {"message": ask},
            {"message": "give me a cleaner response",
             "response": {"message": "..."}},
        ]}
        toks = _named_file_targets(
            "try the search again and give me a clean response", ctx, None)
        assert toks == ["381", "U-22", "622", "U-38"], toks
        assert not any("cleaner" in t for t in toks)

    def test_active_objective_inherited_without_union(self):
        # Follow-ups inherit the active objective; historical mentions
        # (e.g. a prior distractor list) never union in.
        from core.chat_tool_planner import _resolve_active_items

        active = ["No. 381", "U-22", "TK 1624"]
        ctx = {"requested_targets": active,
               "history": [
                   {"message": "find prices in w.xlsx: GSL24-16, SLE16-8"},
                   {"message": "and what about U-38",
                    "response": {"message": "..."}},
               ]}
        assert _resolve_active_items(
            "try the search again", ctx, None) == active

    def test_a_revised_objective_outranks_the_ask_text_it_supersedes(self):
        # Live 2026-09-27, the first divergent boundary of the replacement
        # gate. "Replace U-22 with U-38" does not restate the ask — the ask
        # still says "...: No. 381, U-22, ..." — so re-deriving the item set
        # from that text returned the OUTGOING item and the turn answered the
        # question it was correcting. The revision was passed in as
        # `requested_targets` and silently discarded. A revised objective is
        # declared separately and wins outright.
        from core.chat_tool_planner import _resolve_active_items

        ask = ("find the prices of these 8 machines in w.xlsx: No. 381, "
               "U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, "
               "TK Multi Wheel Gang Slitter and GSL48-16")
        edited = ["No. 381", "U-38", "No. 622", "TK Manual Flanger",
                  "SLE24-16", "TK 1624", "TK Multi Wheel Gang Slitter",
                  "GSL48-16"]
        ctx = {"requested_targets": edited, "revised_targets": edited,
               "history": []}
        assert _resolve_active_items(ask, ctx, None) == edited

    def test_the_revision_key_does_not_leak_into_own_text_derivation(self):
        # The revision must be consumed as the authority, not also offered to
        # the turn's-own-text path, where it would be mined a second time and
        # could re-tokenise the labels.
        from core.chat_tool_planner import _resolve_active_items

        edited = ["No. 381", "U-38"]
        ctx = {"revised_targets": edited, "requested_targets": edited,
               "history": [{"message": "and also check Z-99"}]}
        assert _resolve_active_items("and also check Z-99", ctx, None) == edited

    def test_an_unrevised_objective_keeps_the_old_precedence(self):
        # Negative control: the ordinary precedence (turn's own text beats
        # inheritance) is untouched for every turn that did not revise.
        from core.chat_tool_planner import _resolve_active_items

        active = ["No. 381", "U-22"]
        ctx = {"requested_targets": active, "history": []}
        assert _resolve_active_items("now check Z-99 too", ctx, None) == ["Z-99"]

    def test_latest_explicit_list_replaces(self):
        from core.chat_tool_planner import _resolve_active_items

        active = ["No. 381", "U-22"]
        ctx = {"requested_targets": active, "history": []}
        assert _resolve_active_items("now check Z-99 too", ctx, None) == ["Z-99"]

    def test_fresh_vague_ask_mines_history(self):
        # No own items and no active objective: history mining still
        # applies (the vaguer-ask resuming an identifier-rich ask).
        from core.chat_tool_planner import _resolve_active_items

        ctx = {"history": [
            {"message": "find prices in w.xlsx: 381, U-22"}]}
        got = _resolve_active_items("find all these prices", ctx, None)
        assert "381" in got and "U-22" in got

    def test_explicit_followup_does_not_union(self):
        # Latest explicit list replaces; older mentions stay out.
        from core.chat_tool_planner import _resolve_active_items

        ctx = {"history": [
            {"message": "find prices in w.xlsx: 381, U-22"}]}
        assert _resolve_active_items(
            "and also check 622", ctx, None) == ["622"]


# 2. Artifact-native targets --------------------------------------------------

class TestBuildTargetsFromScan:
    def test_row_grouping_and_bases(self):
        targets = ap.build_targets_from_scan(
            ["M-1", "M-2"], SYNTHETIC_OUTCOMES, {})
        single = next(t for t in targets if t["item"] == "M-1")
        assert single["identity"]["status"] == "single"
        assert [c["ref"] for c in single["identity"]["candidates"]] == [
            "SheetA!R88"]
        # Values stay associated with their candidate row.
        assert {v["basis"] for v in
                single["identity"]["candidates"][0]["values"]} == {
            "PRICE", "LIST", "COST"}
        bases = {v["basis"] for v in single["field"]["values"]}
        assert bases == {"PRICE", "LIST", "COST"}
        kinds = {v["display"]: v["kind"]
                 for v in single["field"]["values"]}
        assert kinds["blank"] == "blank"
        assert kinds["0"] == "zero"
        multi = next(t for t in targets if t["item"] == "M-2")
        assert multi["identity"]["status"] == "multiple"
        assert len(multi["identity"]["candidates"]) == 2


# 3. Continuation decision (routing layer — fail-closed) -----------------------
#
# Two independent fields (retrieval operation + presentation preference)
# resolved by the NLU routing layer. None means NOT a continuation:
# normal flow. New work, questions, outbound actions, halt words, and
# approvals never resolve here.

class TestContinuationDecision:
    @pytest.mark.parametrize("msg,expected", [
        ("make it cleaner", ("none", "compact", None)),
        ("give me a cleaner response", ("none", "compact", None)),
        ("make it a table", ("none", "table", None)),
        ("use factory price", ("none", "default", "factory price")),
        ("try the search again and give me a clean response",
         ("rerun", "compact", None)),
        ("search again", ("rerun", "default", None)),
    ])
    def test_continuations_resolve(self, msg, expected):
        decision = _decision(msg)
        assert decision is not None, msg
        assert decision["retrieval"] == expected[0], msg
        assert decision["presentation"]["style"] == expected[1], msg
        assert decision["presentation"]["field"] == expected[2], msg

    @pytest.mark.parametrize("msg", [
        "thanks,",
        "stop",
        "that is wrong",
        "explain the difference",
        "order more cutting fluid for the shop",
        "go",
        "yes",
        "U-22",
        "find the prices in w.xlsx",
        "what was the price?",
        "email the price list to accounts",
        "thanks for the quick delivery",
        "correct the typo in the draft",
    ])
    def test_non_continuations_fall_through(self, msg):
        assert _decision(msg) is None, msg


# 4. Producer helper ------------------------------------------------------------

class TestProducerHelper:
    def test_versioned_record(self):
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["1624", "TK 1624", "381"],
            artifact_outcomes={
                "1624": {"target": "1624", "status": "found",
                         "evidence": [_ev("S", 1, "A1",
                                           [_v("B1", "5", "PRICE")])]},
                "TK 1624": {"target": "TK 1624", "status": "found",
                            "evidence": [_ev("S", 1, "A1",
                                              [_v("B1", "5", "PRICE")])]},
                "381": {"target": "381", "status": "absent", "evidence": []},
            },
            per_item={},
            field_requests=["price"],
            file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read",
            attempt_id="attempt-test-1",
        )
        # v2 adds per-candidate IDENTITY evidence (the exact cell the
        # identity matched in), which v1 dropped when it grouped by row.
        from core.answer_presentation import STRUCTURED_RESULT_SCHEMA

        assert rec["schema_version"] == STRUCTURED_RESULT_SCHEMA
        assert rec["schema_version"] == "structured-result-2"
        assert rec["requested_items"] == ["TK 1624", "381"]
        assert rec["evidence_action"] == "new_read"
        assert rec["evidence_revision"] == "abc:2026-09-07"
        rec2 = planner._build_workbook_structured_record(
            item_tokens=["381"], artifact_outcomes={}, per_item={},
            field_requests=[], file_name="w.xlsx", prov={},
            coverage_limits={}, evidence_action="new_read",
            attempt_id="attempt-test-2")
        assert rec2["attempt_id"] != rec["attempt_id"]

    def test_unobserved_scan_stamps_read_failed(self):
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["381"], artifact_outcomes={}, per_item={},
            field_requests=[], file_name="w.xlsx", prov={},
            coverage_limits={}, evidence_action="read_failed",
            attempt_id="attempt-test-3")
        assert rec["evidence_action"] == "read_failed"
        out = ap.present_from_record(rec)
        assert "did not complete" in out["answer"]

    def test_stash_round_trip(self):
        import types

        import core.chat_tool_planner as planner

        plan = types.SimpleNamespace()
        rec = _record()
        planner._set_structured_result(plan, rec)
        stored = plan._result_meta["storage_read"]["structured_result"]
        assert stored["attempt_id"] == rec["attempt_id"]


# 5. Delivery branches ----------------------------------------------------------

ASK = ("find the prices of M-1 and M-2 in w.xlsx")


def _direct_result(rec):
    return {"ok": True, "block": "", "rendered_answer": "legacy",
            "structured_result": rec,
            "identity": {"file_name": "w.xlsx"},
            "identity_verified": True, "coverage_complete": True,
            "retrieval_complete": True, "freshness": {}}


@pytest.mark.asyncio
async def test_ask_lane_renders_structured_and_pins():
    orch = _orch()
    rec = _record()
    session = {"id": "s-ask", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read",
                     new=AsyncMock(return_value=_direct_result(rec))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", ASK, session_id="s-ask", context={})
    assert response["success"] is True
    assert "- **M-1**" in response["message"]
    assert "- **M-2**" in response["message"]
    row = session["_pending_file_result"]
    assert row["structured_result"]["attempt_id"] == rec["attempt_id"]
    assert row["evidence_action"] == "new_read"
    assert row["rendered_core"] == response["message"][:24000]
    assert row["presentation_action"]["action"] == "render"
    assert row["presentation_action"][
        "references_attempt_id"] == rec["attempt_id"]
    assert response["data"]["presentation_action"][
        "references_attempt_id"] == rec["attempt_id"]
    pin = row["delivery_pin"]
    assert pin["delivered_text"] == response["message"][:24000]
    assert pin["delivered_answer_sha256"] == hashlib.sha256(
        response["message"][:24000].encode()).hexdigest()


@pytest.mark.asyncio
async def test_formatting_followup_is_new_compact_delivery():
    """A formatting follow-up is a NEW turn and delivery: compact render
    from saved evidence, zero retrieval, new pin; the previous message
    and pin stay unchanged wherever history already persisted them."""
    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]
    previous = dict(ap.mark_delivered({
        "status": "delivered", "target_extraction_version": 3,
        "rendered": core, "rendered_core": core,
        "identity": {}, "structured_result": rec,
        "attempt_id": rec["attempt_id"],
        "evidence_revision": rec["evidence_revision"],
        "evidence_action": "new_read",
    }, core))
    history_copy = json.loads(json.dumps(previous))
    session = {"id": "s-fmt", "history": [],
               "_pending_file_result": dict(previous)}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", "make it cleaner", session_id="s-fmt", context={})
    assert response["success"] is True
    expected = ap.present_from_record(
        rec, presentation_action={
            "intent": {"action": "re-render", "style": "compact"}})["answer"]
    assert response["message"] == expected
    assert response["message"] != core  # compact visibly differs
    row = session["_pending_file_result"]
    assert row["attempt_id"] == rec["attempt_id"]  # evidence untouched
    assert row["evidence_action"] == "new_read"
    assert row["delivery_pin"]["delivered_text"] == expected  # new pin
    assert history_copy["delivery_pin"]["delivered_text"] == core  # old kept
    action = row["presentation_action"]
    assert action["action"] == "re-render"
    assert action["intent"]["style"] == "compact"
    assert response["data"]["presentation_action"][
        "references_attempt_id"] == rec["attempt_id"]


@pytest.mark.asyncio
async def test_table_preference_renders_table():
    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]
    session = {"id": "s-table", "history": [],
               "_pending_file_result": dict(ap.mark_delivered({
                   "status": "delivered", "target_extraction_version": 3,
                   "rendered": core, "rendered_core": core,
                   "identity": {}, "structured_result": rec,
                   "attempt_id": rec["attempt_id"],
                   "evidence_revision": rec["evidence_revision"],
                   "evidence_action": "new_read",
               }, core))}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", "make it a table", session_id="s-table", context={})
    assert response["success"] is True
    assert "| M-1 |" in response["message"]
    assert session["_pending_file_result"]["presentation_action"][
        "intent"]["style"] == "table"


@pytest.mark.asyncio
async def test_field_selection_prefers_basis():
    orch = _orch()
    targets = [{
        "item": "M-1", "aliases": [],
        "identity": {"status": "single", "candidates": [{
            "ref": "S!R1",
            "values": [
                {"col": "B1", "basis": "PRICE", "kind": "number",
                 "display": "5", "value": 5.0},
                {"col": "H1", "basis": "Factory Price", "kind": "number",
                 "display": "3", "value": 3.0},
            ]}]},
        "field": {"status": "competing", "values": [
            {"col": "B1", "basis": "PRICE", "kind": "number",
             "display": "5", "value": 5.0},
            {"col": "H1", "basis": "Factory Price", "kind": "number",
             "display": "3", "value": 3.0},
        ]},
    }]
    rec = ap.build_structured_record(
        source_identity={"file_name": "w.xlsx"},
        evidence_revision="rev-f", attempt_id=ap.new_attempt_id(),
        evidence_action="new_read", requested_items=["M-1"],
        requested_fields=["price"], targets=targets, coverage="c")
    core = ap.present_from_record(rec)["answer"]
    session = {"id": "s-field", "history": [],
               "_pending_file_result": dict(ap.mark_delivered({
                   "status": "delivered", "target_extraction_version": 3,
                   "rendered": core, "rendered_core": core,
                   "identity": {}, "structured_result": rec,
                   "attempt_id": rec["attempt_id"],
                   "evidence_revision": rec["evidence_revision"],
                   "evidence_action": "new_read",
               }, core))}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", "use factory price", session_id="s-field", context={})
    assert response["success"] is True
    assert "Factory Price" in response["message"]
    assert "PRICE" not in response["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("msg", [
    "order more cutting fluid for the shop",
    "that is wrong",
    "stop",
    "what was U-22's price?",
    "email the price list to accounts",
])
async def test_unrelated_turns_never_present_saved_result(msg):
    """Corrections, cancellation, questions, outbound actions, and new
    subjects must not trigger saved-result presentation."""
    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]
    pinned = ap.mark_delivered({
        "status": "delivered", "target_extraction_version": 3,
        "rendered": core, "rendered_core": core,
        "identity": {}, "structured_result": rec,
        "attempt_id": rec["attempt_id"],
        "evidence_revision": rec["evidence_revision"],
        "evidence_action": "new_read",
    }, core)
    session = {"id": "s-neg", "history": [],
               "_pending_file_result": dict(pinned)}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner ran instead of presenting"))),
    ):
        try:
            response = await orch.process_chat_message(
                "u1", msg, session_id="s-neg", context={})
        except AssertionError as exc:
            assert "planner ran" in str(exc), msg
            return
    assert response.get("message") != core, msg
    assert "presentation_action" not in session["_pending_file_result"], msg


@pytest.mark.asyncio
async def test_transport_retry_serves_pin_verbatim():
    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]
    pinned_row = ap.mark_delivered({
        "status": "delivered", "target_extraction_version": 3,
        "rendered": core, "rendered_core": core,
        "identity": {}, "structured_result": rec,
        "attempt_id": rec["attempt_id"],
        "evidence_revision": rec["evidence_revision"],
        "evidence_action": "new_read",
    }, core)
    session = {"id": "s-tr", "history": [],
               "_pending_file_result": dict(pinned_row)}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", "go", session_id="s-tr", context={})
    assert response["success"] is True
    assert response["message"] == core
    # Transport path renders nothing and records no action.
    assert "presentation_action" not in session["_pending_file_result"]
    assert response["data"]["presentation_action"] is None


@pytest.mark.asyncio
async def test_formatting_supersedes_stale_pin():
    """Formatting is a new delivery: an old pin plus a deliberately
    different fresh render yields the NEW finalized render, while the
    previously persisted message stays unchanged."""
    orch = _orch()
    rec = _record()
    stale_pin_text = "STALE PINNED BYTES"
    row = ap.mark_delivered({
        "status": "delivered", "target_extraction_version": 3,
        "rendered": stale_pin_text, "rendered_core": "something else",
        "identity": {}, "structured_result": rec,
        "attempt_id": rec["attempt_id"],
        "evidence_revision": rec["evidence_revision"],
        "evidence_action": "new_read",
    }, stale_pin_text)
    persisted_copy = json.loads(json.dumps(row))
    session = {"id": "s-drift", "history": [],
               "_pending_file_result": dict(row)}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            side_effect=AssertionError("must not re-read"))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", "make it cleaner", session_id="s-drift", context={})
    assert response["success"] is True
    expected = ap.present_from_record(
        rec, presentation_action={
            "intent": {"action": "re-render", "style": "compact"}})["answer"]
    assert response["message"] == expected
    assert response["message"] != stale_pin_text
    assert session["_pending_file_result"]["delivery_pin"][
        "delivered_text"] == expected
    # The previously persisted message/pin are untouched.
    assert persisted_copy["delivery_pin"]["delivered_text"] == stale_pin_text
    assert persisted_copy["rendered"] == stale_pin_text


@pytest.mark.asyncio
async def test_version_gate_single_difference_ab():
    """A/B on exactly one difference: a delivered row WITHOUT the current
    target-extraction version must NOT be served from persistence (it falls
    through to retrieval/planning); the identical row WITH the version
    serves the pin. (Live 2026-09-26: direct-lane rows lacked the stamp,
    so 'go' after a direct delivery fell through to narration.)"""
    from integrations.chat_orchestrator import _TARGET_EXTRACTION_VERSION_NOW

    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]

    def _row(version):
        row = {"status": "delivered",
               "rendered": core, "rendered_core": core,
               "identity": {}, "structured_result": rec,
               "attempt_id": rec["attempt_id"],
               "evidence_revision": rec["evidence_revision"],
               "evidence_action": "new_read"}
        if version is not None:
            row["target_extraction_version"] = version
        return ap.mark_delivered(row, core)

    async def _send(row):
        session = {"id": "s-ab", "history": [],
                   "_pending_file_result": dict(row)}
        fell_through = []
        with (
            patch.object(orch, "_get_or_create_session",
                         return_value=session),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
                side_effect=AssertionError("fell through to re-read"))),
            patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
                side_effect=AssertionError("fell through to planner"))),
        ):
            try:
                response = await orch.process_chat_message(
                    "u1", "go", session_id="s-ab", context={})
            except AssertionError as exc:
                fell_through.append(str(exc))
                return None, fell_through
            return response, fell_through

    # WITHOUT the version: persistence gate skips; the turn falls through
    # to other legs (here a template reply) instead of serving the pin.
    response, fell = await _send(_row(None))
    assert response is not None and response.get("message") != core, (
        "versionless row must not be served from persistence")
    # WITH the version, all else identical: pin served, no retrieval.
    response, fell = await _send(_row(_TARGET_EXTRACTION_VERSION_NOW))
    assert not fell and response["message"] == core


@pytest.mark.asyncio
async def test_explicit_research_mints_new_attempt():
    from core.pending_file_task import build_pending_task

    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]
    task = build_pending_task(ASK, "w.xlsx")
    session = {"id": "s-rs", "history": [],
               "_pending_file_task": task,
               "_pending_file_result": {
                   "status": "delivered", "target_extraction_version": 3,
                   "rendered": core, "identity": {},
                   "structured_result": rec,
                   "attempt_id": rec["attempt_id"],
                   "evidence_revision": rec["evidence_revision"],
                   "evidence_action": "new_read"}}
    rec2 = _record()
    assert rec2["attempt_id"] != rec["attempt_id"]
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read",
                     new=AsyncMock(return_value=_direct_result(rec2))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", "try the search again and give me a clean response",
            session_id="s-rs", context={})
    assert response["success"] is True
    row = session["_pending_file_result"]
    assert row["attempt_id"] == rec2["attempt_id"]
    assert row["attempt_id"] != rec["attempt_id"]
    # Same saved copy is a valid outcome; the new attempt proves the read.
    assert row["evidence_revision"] == "rev-1"
    assert "- **M-1**" in response["message"]


# 6. Durability -----------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.usefixtures("durable_metadata_db")
async def test_structured_record_survives_persistence_and_reload():
    orch = _orch()
    rec = _record()
    core = ap.present_from_record(rec)["answer"]
    row = ap.mark_delivered({
        "status": "delivered", "target_extraction_version": 3,
        "rendered": core, "identity": {"file_name": "w.xlsx"},
        "structured_result": rec, "attempt_id": rec["attempt_id"],
        "evidence_revision": rec["evidence_revision"],
        "evidence_action": "new_read",
    }, core)
    session = {"id": "s-durable", "history": [],
               "_pending_file_result": dict(row)}
    orch._update_session(
        session, "make it cleaner",
        {"success": True, "message": core,
         "execution_id": "exec-1", "model": "deterministic",
         "provider": "structured"},
        {"primary_intent": "search", "confidence": 0.9},
    )
    reloaded = orch._load_pending_file_result("s-durable")
    assert reloaded is not None
    assert reloaded["structured_result"]["attempt_id"] == rec["attempt_id"]
    assert reloaded["structured_result"]["evidence_revision"] == "rev-1"
    assert reloaded["delivery_pin"]["delivered_text"] == core
    assert reloaded["delivery_pin"]["delivered_answer_sha256"] == (
        hashlib.sha256(core.encode()).hexdigest())


# 7. Invocation instrumentation -------------------------------------------------
#
# Retrieval/render invocations are counted from durable boundary rows keyed
# by execution/attempt — never inferred from persisted artifacts.

@pytest.mark.asyncio
@pytest.mark.usefixtures("durable_metadata_db")
async def test_scan_entry_exit_bound_real_scan():
    import types

    import core.chat_tool_planner as planner

    import tempfile as _tf

    import pandas as _pd

    from core.models import InvocationEvent
    from core.database import get_db_session

    tmp = _tf.mkdtemp(prefix="wb-events-")
    frame = _pd.DataFrame({
        "__sheet_row": [26],
        "Model": ["U-22"], "List Price": [1777],
    })
    path = os.path.join(tmp, "s.parquet")
    frame.to_parquet(path)
    catalog = [{
        "source": "zoho_workdrive", "external_id": "e1",
        "dataset_name": "wb_ev", "file_name": "Consolidated Price List 2019.xlsx",
        "entity_name": "LINMAC", "parquet_path": path, "row_count": 1,
        "coverage": {"known": True, "truncated": False},
        "content_hash": "h1", "ingested_at": "2026-09-07",
    }]
    plan = types.SimpleNamespace()
    ask = ("find the price of U-22 in Consolidated Price List 2019.xlsx: "
           "U-22")
    with (
        patch("core.sheet_dataset_service.sheet_datasets_enabled",
              return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync",
              return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync",
              return_value=list(catalog)),
    ):
        block = await planner._datasets_named_file_block(
            "u1", ask,
            {"message": ask, "history": [],
             "execution_id": "exec-scan-1", "session_id": "s-scan"},
            plan=plan)
    assert block
    stored = plan._result_meta["storage_read"]["structured_result"]
    assert stored["evidence_action"] == "new_read"
    assert stored["requested_items"] == ["U-22"]
    with get_db_session() as db:
        rows = db.query(InvocationEvent).filter(
            InvocationEvent.execution_id == "exec-scan-1").all()
    kinds = sorted(r.kind for r in rows)
    assert kinds == ["scan_end", "scan_start"], kinds
    starts = [r for r in rows if r.kind == "scan_start"]
    ends = [r for r in rows if r.kind == "scan_end"]
    assert len(starts) == 1 and len(ends) == 1
    assert starts[0].attempt_id == ends[0].attempt_id == stored["attempt_id"]
    assert ends[0].outcome == "new_read"
    assert ends[0].evidence_revision == stored["evidence_revision"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("durable_metadata_db")
async def test_render_event_bound_to_execution_and_attempt():
    from core.database import get_db_session
    from core.models import InvocationEvent

    orch = _orch()
    rec = _record()
    session = {"id": "s-render-ev", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read",
                     new=AsyncMock(return_value=_direct_result(rec))),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("must not plan"))),
    ):
        response = await orch.process_chat_message(
            "u1", ASK, session_id="s-render-ev", context={})
    exec_id = response.get("execution_id")
    assert exec_id
    with get_db_session() as db:
        rows = db.query(InvocationEvent).filter(
            InvocationEvent.execution_id == exec_id).all()
    renders = [r for r in rows if r.kind == "render"]
    assert len(renders) == 1
    assert renders[0].attempt_id == rec["attempt_id"]
    assert renders[0].outcome == "ok"


class TestIdentityEvidence:
    """Contract v2: identity is a SEPARATE binding from value, carrying
    the exact cell the identity matched in.

    The candidate ``ref`` stays a row locator ("S!R1"), which is fine for
    display and proves nothing: a row holds several prices, and a row ref
    does not say which cell matched. These tests pin that the exact
    coordinate survives, and that nothing is invented when it is absent.
    """

    def _record(self, outcomes):
        import core.chat_tool_planner as planner

        return planner._build_workbook_structured_record(
            item_tokens=["381"], artifact_outcomes=outcomes, per_item={},
            field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-identity")

    def test_identity_binding_carries_the_exact_matched_cell(self):
        rec = self._record({
            "381": {"target": "381", "status": "found",
                    "evidence": [_ev("LINMAC", 26, "C26",
                                     [_v("C26", "1777", "List Price")])]}})
        cand = rec["targets"][0]["identity"]["candidates"][0]
        assert cand["identity"]["status"] == "bound"
        ref = cand["identity"]["references"][0]
        assert ref["cell"] == "C26"
        assert ref["sheet"] == "LINMAC"
        assert ref["role"] == "matched_target"
        # The row locator is unchanged for display.
        assert cand["ref"] == "LINMAC!R26"

    def test_identity_may_live_outside_column_a(self):
        """Identity is NOT assumed to be column A: models, descriptions,
        aliases and merged labels all sit elsewhere."""
        rec = self._record({
            "381": {"target": "381", "status": "found",
                    "evidence": [_ev("Sheet1", 7, "D7",
                                     [_v("E7", "9", "PRICE")])]}})
        ref = rec["targets"][0]["identity"]["candidates"][0][
            "identity"]["references"][0]
        assert ref["cell"] == "D7"

    def test_a101_does_not_match_aa101(self):
        """Exact coordinates only. 'A101' must never be read as 'AA101'."""
        rec_a = self._record({
            "381": {"target": "381", "status": "found",
                    "evidence": [_ev("S", 101, "A101",
                                     [_v("C101", "1", "PRICE")])]}})
        rec_aa = self._record({
            "381": {"target": "381", "status": "found",
                     "evidence": [_ev("S", 101, "AA101",
                                      [_v("AC101", "2", "PRICE")])]}})
        cell_a = rec_a["targets"][0]["identity"]["candidates"][0][
            "identity"]["references"][0]["cell"]
        cell_aa = rec_aa["targets"][0]["identity"]["candidates"][0][
            "identity"]["references"][0]["cell"]
        assert cell_a == "A101"
        assert cell_aa == "AA101"
        assert cell_a != cell_aa

    def test_row_display_notation_is_not_mistaken_for_a_cell(self):
        """'R26' is a row locator. It must never be recorded as an
        identity CELL reference."""
        rec = self._record({
            "381": {"target": "381", "status": "found",
                    "evidence": [{"sheet": "S", "row": 26, "value": "x",
                                  "values": [_v("C26", "5", "PRICE")]}]}})
        cand = rec["targets"][0]["identity"]["candidates"][0]
        # No matched coordinate on the record -> explicitly unverified.
        assert cand["identity"]["status"] == "unverified"
        assert cand["identity"]["references"] == []
        assert cand["ref"] == "S!R26"

    def test_multiple_matching_cells_in_one_row_keep_each_reference(self):
        """A88/B88/L88 are one row but three identity observations."""
        rec = self._record({
            "381": {"target": "381", "status": "found",
                    "evidence": [
                        _ev("S", 88, "A88", [_v("C88", "1", "PRICE")]),
                        _ev("S", 88, "B88", [_v("D88", "2", "PRICE")]),
                    ]}})
        cand = rec["targets"][0]["identity"]["candidates"][0]
        # Still ONE candidate: same row.
        assert cand["ref"] == "S!R88"
        cells = [r["cell"] for r in cand["identity"]["references"]]
        assert cells == ["A88", "B88"]

    def test_identity_never_substitutes_for_value_evidence(self):
        rec = self._record({
            "381": {"target": "381", "status": "found",
                    "evidence": [_ev("S", 26, "A26",
                                     [_v("C26", "1777", "List Price")])]}})
        cand = rec["targets"][0]["identity"]["candidates"][0]
        assert cand["identity"]["references"][0]["cell"] == "A26"
        # The price is proven by the VALUE cell, separately.
        assert [v["col"] for v in cand["values"]] == ["C26"]
        assert cand["values"][0]["basis"] == "List Price"

    def test_legacy_record_without_coordinates_stays_limited(self):
        """A row record with no matched coordinate must be reported
        unverified, never reconstructed into a column-A reference."""
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["381"], artifact_outcomes={},
            per_item={"381": {
                "entity_name": "S", "columns": ["Model", "Price"],
                "column_letters": {"Model": "A", "Price": "C"},
                "rows": [{"Model": "No. 381", "Price": "1777",
                          "__sheet_row": 26}]}},
            field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-legacy")
        cand = rec["targets"][0]["identity"]["candidates"][0]
        assert cand["identity"]["status"] == "unverified"
        assert cand["identity"]["references"] == []
        # The value binding is still exact and usable.
        assert [v["col"] for v in cand["values"]] == ["C26"]

    def test_absent_target_reports_no_identity_rather_than_a_guess(self):
        rec = self._record({"381": {"target": "381", "status": "absent",
                                     "evidence": []}})
        assert rec["targets"][0]["identity"]["status"] == "none"

    def test_schema_version_is_explicit_and_previous_is_declared(self):
        from core.answer_presentation import (
            STRUCTURED_RESULT_SCHEMA,
            STRUCTURED_RESULT_SCHEMA_PREVIOUS,
        )

        assert STRUCTURED_RESULT_SCHEMA == "structured-result-2"
        assert "structured-result-1" in STRUCTURED_RESULT_SCHEMA_PREVIOUS


class TestProbeMatchedCells:
    """The content probe knows WHICH cells matched; that coordinate must
    survive into identity evidence instead of a bare row locator."""

    def test_matched_cells_in_row_is_an_exact_value_comparison(self):
        from core.sheet_dataset_service import _matched_cells_in_row

        letters = {"Model": "A", "Price": "C", "Note": "D"}
        row = {"Model": "U-22", "Price": "1777", "Note": "n/a",
               "__sheet_row": 26}
        hits = _matched_cells_in_row(row, "U-22", letters, 26)
        assert [h["cell"] for h in hits] == ["A26"]
        assert hits[0]["value"] == "U-22"
        assert hits[0]["column"] == "Model"

    def test_identity_outside_column_a_is_still_found(self):
        from core.sheet_dataset_service import _matched_cells_in_row

        letters = {"Description": "D", "Price": "C"}
        row = {"Description": "Linmac Bead Roller U-22", "Price": "1777"}
        hits = _matched_cells_in_row(row, "U-22", letters, 26)
        assert [h["cell"] for h in hits] == ["D26"]

    def test_several_matching_cells_yield_several_references(self):
        from core.sheet_dataset_service import _matched_cells_in_row

        letters = {"A": "A", "B": "B"}
        row = {"A": "381", "B": "No. 381"}
        hits = _matched_cells_in_row(row, "381", letters, 88)
        assert sorted(h["cell"] for h in hits) == ["A88", "B88"]

    def test_no_match_yields_no_reference(self):
        from core.sheet_dataset_service import _matched_cells_in_row

        letters = {"Model": "A", "Price": "C"}
        assert _matched_cells_in_row({"Model": "U-22", "Price": "1"},
                                     "GSL48-16", letters, 5) == []

    def test_digit_boundary_is_respected(self):
        """'5216' must not match inside '15.5216250' — the whole-number
        rule the probe itself applies."""
        from core.sheet_dataset_service import _matched_cells_in_row

        letters = {"V": "A"}
        assert _matched_cells_in_row({"V": "15.521625000000002"},
                                     "5216", letters, 1) == []
        assert _matched_cells_in_row({"V": "TK 5216"}, "5216",
                                     letters, 1) != []

    def test_probe_record_identity_binds_end_to_end(self):
        """A probe record carrying matched_cells produces BOUND identity
        evidence on the candidate."""
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["U-22"], artifact_outcomes={},
            per_item={"U-22": {
                "entity_name": "LINMAC",
                "columns": ["Model", "Price"],
                "column_letters": {"Model": "A", "Price": "C"},
                "matched_cells": [{"cell": "A26", "column": "Model",
                                   "value": "U-22"}],
                "rows": [{"Model": "U-22", "Price": "1777",
                          "__sheet_row": 26}]}},
            field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-probe")
        cand = rec["targets"][0]["identity"]["candidates"][0]
        assert cand["identity"]["status"] == "bound"
        ref = cand["identity"]["references"][0]
        assert ref["cell"] == "A26"
        assert ref["sheet"] == "LINMAC"
        assert ref["value"] == "U-22"
        # Identity and value remain separate bindings.
        assert [v["col"] for v in cand["values"]] == ["C26"]

    def test_probe_record_without_matched_cells_stays_unverified(self):
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["U-22"], artifact_outcomes={},
            per_item={"U-22": {
                "entity_name": "LINMAC", "columns": ["Model", "Price"],
                "column_letters": {"Model": "A", "Price": "C"},
                "rows": [{"Model": "U-22", "Price": "1777",
                          "__sheet_row": 26}]}},
            field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-probe2")
        cand = rec["targets"][0]["identity"]["candidates"][0]
        assert cand["identity"]["status"] == "unverified"
        assert cand["identity"]["references"] == []


class TestIdentitySurvivesAliasMerge:
    """The alias merge consolidates duplicate spellings of one requested
    item ("1624" / "TK 1624") into a single target. That rebuild used to
    copy only ref+values, so the matched identity cell was dropped AFTER
    the per-target build had bound it correctly — with no error anywhere.
    These tests fail on that exact loss.
    """

    def _outcomes(self):
        return {
            "1624": {"target": "1624", "status": "found",
                     "evidence": [_ev("TINKNOCKER", 101, "A101",
                                      [_v("D101", "8040", "Price")])]},
            "TK 1624": {"target": "TK 1624", "status": "found",
                        "evidence": [_ev("TINKNOCKER", 101, "A101",
                                         [_v("D101", "8040", "Price")])]},
        }

    def _record(self):
        import core.chat_tool_planner as planner

        return planner._build_workbook_structured_record(
            item_tokens=["1624", "TK 1624"],
            artifact_outcomes=self._outcomes(), per_item={},
            field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-merge")

    def test_identity_binding_survives_the_alias_merge(self):
        rec = self._record()
        entry = next(t for t in rec["targets"] if t["item"] == "TK 1624")
        cand = entry["identity"]["candidates"][0]
        assert cand["identity"]["status"] == "bound", (
            "the alias merge dropped the identity binding")
        assert cand["identity"]["references"][0]["cell"] == "A101"

    def test_alias_merge_does_not_duplicate_the_same_cell(self):
        rec = self._record()
        entry = next(t for t in rec["targets"] if t["item"] == "TK 1624")
        cand = entry["identity"]["candidates"][0]
        cells = [r["cell"] for r in cand["identity"]["references"]]
        assert cells == ["A101"], f"duplicate identity references: {cells}"

    def test_value_binding_still_consolidates_across_aliases(self):
        rec = self._record()
        entry = next(t for t in rec["targets"] if t["item"] == "TK 1624")
        cand = entry["identity"]["candidates"][0]
        cols = [v["col"] for v in cand["values"]]
        assert cols.count("D101") == 1, f"duplicate value references: {cols}"

    def test_merged_candidates_keep_one_candidate_per_row(self):
        rec = self._record()
        entry = next(t for t in rec["targets"] if t["item"] == "TK 1624")
        # Same row from two alias spellings is still ONE candidate.
        assert len(entry["identity"]["candidates"]) == 1

    def test_unverified_identity_is_not_upgraded_by_the_merge(self):
        """A record with no matched cell must stay unverified; the merge
        must not invent a binding."""
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["1624", "TK 1624"],
            artifact_outcomes={
                "1624": {"target": "1624", "status": "found",
                         "evidence": [{"sheet": "S", "row": 5, "value": "x",
                                       "values": [_v("D5", "1", "P")]}]},
                "TK 1624": {"target": "TK 1624", "status": "found",
                            "evidence": [{"sheet": "S", "row": 5, "value": "x",
                                          "values": [_v("D5", "1", "P")]}]}},
            per_item={}, field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-merge2")
        entry = next(t for t in rec["targets"] if t["item"] == "TK 1624")
        cand = entry["identity"]["candidates"][0]
        assert cand["identity"]["status"] == "unverified"
        assert cand["identity"]["references"] == []


class TestMergedCellsAndVariants:
    """Merged identity cells and multiple variants on one row.

    A merged cell's value lives in its top-left anchor; every other member
    reads empty, so citing a member cell points at nothing. And two
    variants sharing a row must stay distinguishable when the source
    supports them — the row locator alone cannot tell them apart.
    """

    def _anchor(self):
        from core.workbook_read_artifact import merged_anchor_for_cell

        return merged_anchor_for_cell

    def test_member_cell_resolves_to_its_anchor(self):
        f = self._anchor()
        out = f(["A88:D88"], "B88")
        assert out["anchor"] == "A88"
        assert out["range"] == "A88:D88"
        assert out["is_anchor"] is False

    def test_anchor_cell_is_recognised_as_the_anchor(self):
        f = self._anchor()
        out = f(["A88:D88"], "A88")
        assert out["anchor"] == "A88"
        assert out["is_anchor"] is True

    def test_anchor_is_not_assumed_to_be_column_a(self):
        f = self._anchor()
        out = f(["C5:F5"], "E5")
        assert out["anchor"] == "C5"
        assert out["is_anchor"] is False

    def test_multi_row_merge_resolves_to_the_top_row(self):
        f = self._anchor()
        assert f(["B10:C12"], "C11")["anchor"] == "B10"

    def test_unmerged_cell_has_no_anchor(self):
        assert self._anchor()(["A88:D88"], "Z99") is None
        assert self._anchor()([], "A1") is None

    def test_absent_merge_metadata_yields_no_anchor(self):
        """A materialized dataset carries no merge metadata. That must
        produce None (and therefore an unverified binding), never a guess."""
        assert self._anchor()(None, "B88") is None
        assert self._anchor()(["not-a-range"], "B88") is None

    def test_malformed_cell_reference_is_rejected(self):
        assert self._anchor()(["A88:D88"], "R88") is None
        assert self._anchor()(["A88:D88"], "") is None

    def test_two_variants_on_one_row_stay_distinguishable(self):
        """Same row, two products: the row locator is shared, so identity
        must come from the cell to keep them apart."""
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["GSL48-16", "SLE24-16"],
            artifact_outcomes={
                "GSL48-16": {"target": "GSL48-16", "status": "found",
                             "evidence": [_ev("S", 106, "A106",
                                              [_v("E106", "14166", "PRICE")])]},
                "SLE24-16": {"target": "SLE24-16", "status": "found",
                             "evidence": [_ev("S", 101, "A101",
                                              [_v("E101", "8880", "PRICE")])]}},
            per_item={}, field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-variants")
        by_item = {t["item"]: t for t in rec["targets"]}
        a = by_item["GSL48-16"]["identity"]["candidates"][0]
        b = by_item["SLE24-16"]["identity"]["candidates"][0]
        # Distinct identity cells, so the two are separable even though a
        # row locator alone could not tell a same-row pair apart.
        assert a["identity"]["references"][0]["cell"] == "A106"
        assert b["identity"]["references"][0]["cell"] == "A101"
        assert [v["col"] for v in a["values"]] == ["E106"]
        assert [v["col"] for v in b["values"]] == ["E101"]

    def test_two_variants_sharing_one_row_keep_both_cells(self):
        import core.chat_tool_planner as planner

        rec = planner._build_workbook_structured_record(
            item_tokens=["381"],
            artifact_outcomes={
                "381": {"target": "381", "status": "found",
                        "evidence": [
                            _ev("S", 88, "A88", [_v("C88", "670", "PRICE")]),
                            _ev("S", 88, "B88", [_v("D88", "2421", "PRICE")]),
                        ]}},
            per_item={}, field_requests=["price"], file_name="w.xlsx",
            prov={"content_hash": "abc", "ingested_at": "2026-09-07"},
            coverage_limits={"indexed_sheets": 1},
            evidence_action="new_read", attempt_id="attempt-samerow")
        cand = rec["targets"][0]["identity"]["candidates"][0]
        cells = [r["cell"] for r in cand["identity"]["references"]]
        assert cells == ["A88", "B88"]
        # One row, so one candidate, but both observations are retained.
        assert len(rec["targets"][0]["identity"]["candidates"]) == 1
        cols = sorted(v["col"] for v in cand["values"])
        assert cols == ["C88", "D88"]


class TestValueBearingCandidatePrecedence:
    """A candidate that can ANSWER the request must not be truncated away.

    Live 2026-09-29 (session replay-retry2-20260923): the same "try again"
    read of the same workbook rendered two different answers minutes apart —
    22:04 showed the priced row (Tennsmith!R338, PRICE 3,254), 23:34 showed
    only three RoperWhitney rows whose price cells are blank/0 and buried the
    priced row entirely. The candidate list is built in SCAN order and dataset
    entries are ordered by entity_name ASC, so which rows survive the
    presenter's `candidates[:3]` window is decided by alphabetical SHEET NAME
    rather than by whether a row carries the requested value. Fixtures are
    domain-independent: "Atlas"/"Borealis" stand in for the two brands.
    """

    @staticmethod
    def _outcomes():
        blank_row = [
            _ev("Atlas", 88, "A88", [_v("E88", "", "PRICE"),
                                     _v("M88", "", "LIST")]),
            _ev("Atlas", 89, "A89", [_v("E89", "", "PRICE")]),
            _ev("Atlas", 90, "A90", [_v("E90", "", "PRICE")]),
            _ev("Atlas", 91, "A91", [_v("E91", "", "PRICE")]),
        ]
        priced_row = [
            _ev("Borealis", 40, "A40", [_v("E40", "3254", "PRICE"),
                                        _v("M40", "1845", "LIST")]),
        ]
        return {"381": {"target": "381", "status": "ambiguous",
                        "evidence": blank_row + priced_row}}

    def test_value_bearing_candidate_precedes_valueless_ones(self):
        targets = ap.build_targets_from_scan(["381"], self._outcomes(), {})
        cands = targets[0]["identity"]["candidates"]
        assert cands[0]["ref"] == "Borealis!R40", (
            "the only candidate carrying the requested value must lead; got "
            f"{[c['ref'] for c in cands]}")

    def test_value_bearing_candidate_survives_the_render_window(self):
        targets = ap.build_targets_from_scan(["381"], self._outcomes(), {})
        cands = targets[0]["identity"]["candidates"]
        window = cands[:ap.AMBIGUOUS_CANDIDATE_WINDOW]
        assert "Borealis!R40" in [c["ref"] for c in window], (
            "a priced row must never be truncated out of view by valueless "
            "rows that happen to sort first")

    def test_no_candidate_is_dropped(self):
        """Precedence REORDERS; it never eliminates a candidate."""
        targets = ap.build_targets_from_scan(["381"], self._outcomes(), {})
        refs = {c["ref"] for c in targets[0]["identity"]["candidates"]}
        assert refs == {"Atlas!R88", "Atlas!R89", "Atlas!R90", "Atlas!R91",
                        "Borealis!R40"}

    def test_all_valueless_candidates_keep_scan_order(self):
        """With no value-bearing candidate the order is untouched."""
        outcomes = {"381": {"target": "381", "status": "ambiguous", "evidence": [
            _ev("Atlas", 88, "A88", [_v("E88", "", "PRICE")]),
            _ev("Borealis", 40, "A40", [_v("E40", "", "PRICE")]),
            _ev("Atlas", 91, "A91", [_v("E91", "", "PRICE")]),
        ]}}
        targets = ap.build_targets_from_scan(["381"], outcomes, {})
        refs = [c["ref"] for c in targets[0]["identity"]["candidates"]]
        assert refs == ["Atlas!R88", "Borealis!R40", "Atlas!R91"]

    def test_zero_is_not_a_value(self):
        """A 0/blank price column cannot answer; it must not outrank a real
        figure (the live RoperWhitney rows carried PRICE blank, COST 0)."""
        outcomes = {"381": {"target": "381", "status": "ambiguous", "evidence": [
            _ev("Atlas", 88, "A88", [_v("E88", "0", "PRICE")]),
            _ev("Borealis", 40, "A40", [_v("E40", "3254", "PRICE")]),
        ]}}
        targets = ap.build_targets_from_scan(["381"], outcomes, {})
        refs = [c["ref"] for c in targets[0]["identity"]["candidates"]]
        assert refs[0] == "Borealis!R40"


# ---------------------------------------------------------------------------
# SHEET SCOPE (2026-09-30) — the reader naming a sheet is part of the request.
#
# Incident: "show me the tennsmith sheet searches" was answered with a
# byte-identical copy of the previous turn's sentence. Two independent causes,
# pinned separately below:
#   (a) ROUTING — the follow-up named a sheet of the conversation's own
#       spreadsheet but carried no preposition, so no file identity resolved
#       and the turn fell to narration, which re-served the prior answer.
#   (b) PRESENTATION — even with a correct re-read, the visible window was a
#       positional prefix of an alphabetically-ordered candidate list, so the
#       alphabetically-first sheet consumed every slot and the named sheet's
#       rows were unreachable.
#
# Fixtures are domain-free, per this module's rule: sheet names carry no real
# product identity and the logic keys on position and reference shape only.
# ---------------------------------------------------------------------------

_TWO_SHEET_OUTCOMES = None


def _two_sheet_outcomes():
    """5 rows on 'AlphaWorks' (alphabetically first) and 5 on 'BetaParts'."""
    global _TWO_SHEET_OUTCOMES
    if _TWO_SHEET_OUTCOMES is None:
        evidence = []
        for sheet, base in (("AlphaWorks", 200), ("BetaParts", 300)):
            for offset in range(5):
                row = base + offset
                evidence.append(_ev(
                    sheet, row, f"A{row}",
                    [_v(f"E{row}", str(100 + row), "PRICE")]))
        _TWO_SHEET_OUTCOMES = {
            "M-1": {"target": "M-1", "status": "ambiguous",
                    "evidence": evidence}}
    return _TWO_SHEET_OUTCOMES


_SHEETS = ["AlphaWorks", "BetaParts"]


class TestResolveRequestedSheets:
    """The scope is RESOLVED against real sheets, never extracted as a name."""

    def test_names_a_sheet_the_request_references(self):
        assert ap.resolve_requested_sheets(
            "show me the betaparts sheet", _SHEETS) == ["BetaParts"]

    def test_resolves_a_shortened_name(self):
        # Readers abbreviate; the workbook concatenates. Containment both
        # ways is what makes either habit resolve.
        assert ap.resolve_requested_sheets(
            "check the northwind sheet", ["AlphaWorks", "NorthwindParts"]
        ) == ["NorthwindParts"]

    def test_a_qualifier_below_the_floor_resolves_to_nothing(self):
        # The floor (mirroring the sheet-anchoring rule already used to match
        # a query token to a sheet name) is applied to the SHORTER side, so a
        # four-letter fragment cannot scope the turn by matching one common
        # letter of some other sheet's name.
        assert ap._SHEET_SCOPE_MIN_CHARS == 5
        assert ap.resolve_requested_sheets(
            "check the beta sheet", _SHEETS) == []

    def test_resolves_a_loosely_spelled_name(self):
        assert ap.resolve_requested_sheets(
            "check the beta parts sheet", _SHEETS) == ["BetaParts"]

    def test_resolves_a_prepositional_reference(self):
        assert ap.resolve_requested_sheets(
            "show me what's on the AlphaWorks tab", _SHEETS) == ["AlphaWorks"]

    def test_a_name_matching_no_sheet_resolves_to_nothing(self):
        # The load-bearing negative: a wrong scope can hide a match, so a
        # phrase that names no real sheet must scope nothing at all.
        assert ap.resolve_requested_sheets(
            "show me the GammaParts sheet", _SHEETS) == []

    def test_an_unqualified_reference_resolves_to_nothing(self):
        # "the sheet" names no sheet; it must not sweep in every sheet.
        for phrase in ("show me the sheet", "list each sheet",
                       "use the same sheet", "check the other sheet"):
            assert ap.resolve_requested_sheets(phrase, _SHEETS) == [], phrase

    def test_a_workbook_level_ask_resolves_to_no_sheet(self):
        assert ap.resolve_requested_sheets(
            "price for M-1 in the workbook", _SHEETS) == []
        assert ap.resolve_requested_sheets(
            "price for M-1 in the spreadsheet", _SHEETS) == []

    def test_a_short_qualifier_does_not_match(self):
        # Below the floor, containment would match on a single common letter
        # and scope the turn to whatever happened to contain it.
        assert ap.resolve_requested_sheets(
            "the a sheet", ["Zebra"]) == []

    def test_no_known_sheets_resolves_to_nothing(self):
        assert ap.resolve_requested_sheets(
            "show me the BetaParts sheet", []) == []

    def test_two_referenced_sheets_are_both_kept_in_request_order(self):
        # Request order, not sheet order: the reader listed the second sheet
        # first, so that is the order the scope is recorded in.
        assert ap.resolve_requested_sheets(
            "compare the BetaParts sheet and the AlphaWorks sheet", _SHEETS
        ) == ["BetaParts", "AlphaWorks"]


class TestSheetScopeReordersTheVisibleWindow:
    """(b) the named sheet's rows must REACH the window — by reordering."""

    def _refs(self, **kw):
        targets = ap.build_targets_from_scan(
            ["M-1"], _two_sheet_outcomes(), {}, **kw)
        return [c["ref"] for c in targets[0]["identity"]["candidates"]]

    def test_without_a_scope_the_window_is_the_scan_order_prefix(self):
        # Pins the pre-existing behavior so the scope's effect is attributable
        # to the scope alone and not to a silent change of baseline.
        refs = self._refs()
        assert refs[:3] == ["AlphaWorks!R200", "AlphaWorks!R201",
                            "AlphaWorks!R202"]

    def test_the_requested_sheet_leads_the_window(self):
        refs = self._refs(requested_sheets=["BetaParts"])
        assert refs[0] == "BetaParts!R300", refs
        window = refs[:ap.AMBIGUOUS_CANDIDATE_WINDOW]
        assert window == ["BetaParts!R300", "BetaParts!R301",
                          "BetaParts!R302"], window

    def test_the_requested_sheet_reaches_the_window_not_just_the_list(self):
        # The list order alone is not the fix; the point is that the row is
        # inside the window the renderer actually prints.
        targets = ap.build_targets_from_scan(
            ["M-1"], _two_sheet_outcomes(), {},
            requested_sheets=["BetaParts"])
        refs = [c["ref"] for c in targets[0]["identity"]["candidates"]]
        assert "BetaParts!R300" in refs[:ap.AMBIGUOUS_CANDIDATE_WINDOW]

    def test_scope_reorders_and_never_eliminates(self):
        scoped = set(self._refs(requested_sheets=["BetaParts"]))
        unscoped = set(self._refs())
        assert scoped == unscoped, "scope must reorder, never drop a candidate"

    def test_ambiguity_survives_the_scope(self):
        # A sheet the reader named proves nothing about which row is theirs,
        # so the confirmation ask must remain.
        targets = ap.build_targets_from_scan(
            ["M-1"], _two_sheet_outcomes(), {},
            requested_sheets=["BetaParts"])
        assert targets[0]["identity"]["status"] == "multiple"

    def test_answerability_outranks_the_scope(self):
        # Axis order is deliberate: a row that can REPLY beats a row the
        # reader merely asked to see. Here the scoped sheet's row is
        # valueless and the other sheet's row carries the figure, so the
        # figure must lead even though the scope asked for the other.
        priced = {"M-1": {"target": "M-1", "status": "ambiguous",
                          "evidence": [
                              _ev("AlphaWorks", 201, "A201",
                                  [_v("E201", "3254", "PRICE")]),
                              _ev("BetaParts", 300, "A300",
                                  [_v("E300", "", "PRICE")]),
                          ]}}
        refs = [c["ref"] for c in ap.build_targets_from_scan(
            ["M-1"], priced, {},
            requested_sheets=["BetaParts"])[0]["identity"]["candidates"]]
        assert refs[0] == "AlphaWorks!R201", refs

    def test_an_unresolvable_scope_changes_nothing(self):
        assert (self._refs(requested_sheets=["NoSuchSheet"])
                == self._refs())


class TestSurplusIsReportedPerSheet:
    """The tail must say WHERE the hidden rows are, and how many."""

    def _answer(self, **kw):
        targets = ap.build_targets_from_scan(
            ["M-1"], _two_sheet_outcomes(), {}, **kw)
        return ap.present(
            requested_items=["M-1"], requested_fields=["price"],
            source={"file_name": "wb.xlsx", "coverage": {
                "indexed_sheets": 2, "scanned_entries": 2}},
            targets=targets)["answer"]

    def test_surplus_carries_a_count_per_sheet(self):
        answer = self._answer()
        assert "+7 more match(es) (AlphaWorks 2, BetaParts 5)" in answer, answer

    def test_the_named_sheets_rows_are_printed_with_their_values(self):
        answer = self._answer(requested_sheets=["BetaParts"])
        assert "BetaParts sheet, row 300" in answer
        assert "E300 'PRICE' 400" in answer, answer

    def test_counts_sum_to_the_reported_surplus(self):
        # A breakdown the reader cannot add up is worse than no breakdown.
        import re as _re
        answer = self._answer()
        m = _re.search(r"\+(\d+) more match\(es\) \(([^)]*)\)", answer)
        assert m, answer
        total = int(m.group(1))
        parts = [int(entry.rsplit(" ", 1)[1])
                 for entry in m.group(2).split(", ")]
        assert sum(parts) == total, answer

    def test_no_surplus_renders_no_tail(self):
        outcomes = {"M-1": {"target": "M-1", "status": "found",
                            "evidence": [_ev("AlphaWorks", 200, "A200",
                                             [_v("E200", "7", "PRICE")])]}}
        targets = ap.build_targets_from_scan(["M-1"], outcomes, {})
        answer = ap.present(
            requested_items=["M-1"], requested_fields=["price"],
            source={"file_name": "wb.xlsx"}, targets=targets)["answer"]
        assert "more match" not in answer


class TestEmptyScopeIsNeverSilentlyBroadened:
    """A named sheet with no matching row must be STATED, not passed over.

    The scope reorders and never filters, which is what keeps an "include
    the Tennsmith sheet" ask from hiding the RoperWhitney rows the same
    reader also wants. But reordering alone is not enough: if the sheet that
    was asked for happens to hold nothing, the answer would otherwise lead
    with rows from other sheets and never acknowledge the sheet — a silent
    substitution the reader cannot distinguish from an answer.
    """

    def _answer(self, outcomes, sheets, **kw):
        targets = ap.build_targets_from_scan(
            ["M-1"], outcomes, {}, requested_sheets=sheets, **kw)
        return ap.present(
            requested_items=["M-1"], requested_fields=["price"],
            source={"file_name": "wb.xlsx"},
            targets=targets, requested_sheets=sheets)["answer"]

    def test_an_empty_scope_is_named(self):
        answer = self._answer(_two_sheet_outcomes(), ["GammaParts"])
        assert "nothing on the 'GammaParts' sheet" in answer, answer

    def test_the_clause_says_the_rows_shown_are_from_elsewhere(self):
        answer = self._answer(_two_sheet_outcomes(), ["GammaParts"])
        assert "the 10 rows shown are on other sheets" in answer, answer

    def test_no_clause_when_the_named_sheet_does_hold_a_row(self):
        answer = self._answer(_two_sheet_outcomes(), ["BetaParts"])
        assert "no matching row on" not in answer, answer

    def test_no_clause_without_a_scope(self):
        answer = self._answer(_two_sheet_outcomes(), [])
        assert "no matching row on" not in answer, answer

    def test_an_empty_scope_with_no_candidates_at_all(self):
        empty = {"M-1": {"target": "M-1", "status": "none", "evidence": []}}
        answer = self._answer(empty, ["BetaParts"])
        assert "no match in this copy" in answer
        assert "nothing on the 'BetaParts' sheet" in answer, answer

    def test_a_single_match_elsewhere_still_states_the_missed_sheet(self):
        # One candidate on the wrong sheet is as much a substitution as ten.
        outcomes = {"M-1": {"target": "M-1", "status": "found", "evidence": [
            _ev("AlphaWorks", 200, "A200", [_v("E200", "7", "PRICE")])]}}
        answer = self._answer(outcomes, ["BetaParts"])
        assert "nothing on the 'BetaParts' sheet" in answer, answer
        assert "the row shown is on another sheet" in answer, answer

    def test_the_clause_never_appears_after_a_read_failure(self):
        # A source that could not be read supports no claim about any sheet,
        # including the absence of a row on one.
        outcomes = {"M-1": {"target": "M-1", "status": "unavailable",
                            "error_category": "source_corrupt",
                            "evidence": []}}
        targets = ap.build_targets_from_scan(
            ["M-1"], outcomes, {}, requested_sheets=["BetaParts"])
        answer = ap.present(
            requested_items=["M-1"], requested_fields=["price"],
            source={"file_name": "wb.xlsx"}, targets=targets,
            requested_sheets=["BetaParts"])["answer"]
        assert "couldn't read the source" in answer, answer
        assert "nothing on the" not in answer, answer

    def test_the_clause_survives_a_rerender_from_the_record(self):
        # The record is the durable artifact; a retry or reload must
        # reproduce the same words, not drop the scope.
        record = ap.build_structured_record(
            source_identity={"file_name": "wb.xlsx", "ingested_at": "t"},
            evidence_revision="h:t", attempt_id="a1",
            evidence_action="new_read", requested_items=["M-1"],
            requested_fields=["price"],
            targets=ap.build_targets_from_scan(
                ["M-1"], _two_sheet_outcomes(), {},
                requested_sheets=["GammaParts"]),
            coverage={}, requested_sheets=["GammaParts"])
        rendered = ap.present_from_record(record)["answer"]
        assert "nothing on the 'GammaParts' sheet" in rendered, rendered

    def test_an_older_record_without_the_key_renders_as_before(self):
        record = ap.build_structured_record(
            source_identity={"file_name": "wb.xlsx", "ingested_at": "t"},
            evidence_revision="h:t", attempt_id="a1",
            evidence_action="new_read", requested_items=["M-1"],
            requested_fields=["price"],
            targets=ap.build_targets_from_scan(
                ["M-1"], _two_sheet_outcomes(), {}),
            coverage={})
        record.pop("requested_sheets", None)
        assert "no matching row on" not in ap.present_from_record(record)["answer"]


class TestRequestedSheetsAreRecorded:
    """The record explains the order it holds, rather than leaving it
    inferable."""

    def test_record_carries_the_scope(self):
        record = ap.build_structured_record(
            source_identity={"file_name": "wb.xlsx"},
            evidence_revision="h:i", attempt_id="a1",
            evidence_action="new_read", requested_items=["M-1"],
            requested_fields=["price"], targets=[], coverage={},
            requested_sheets=["BetaParts"])
        assert record["requested_sheets"] == ["BetaParts"]

    def test_record_defaults_to_no_scope(self):
        record = ap.build_structured_record(
            source_identity={"file_name": "wb.xlsx"},
            evidence_revision="h:i", attempt_id="a1",
            evidence_action="new_read", requested_items=["M-1"],
            requested_fields=["price"], targets=[], coverage={})
        assert record["requested_sheets"] == []


class TestMentionsSheetReference:
    """The routing-side half: is this turn sheet-shaped? (never: which sheet?)"""

    def test_a_named_sheet_reference_is_detected(self):
        for text in ("show me the BetaParts sheet searches",
                     "price on the AlphaWorks tab",
                     "what's on the beta parts worksheet"):
            assert ap.mentions_sheet_reference(text), text

    def test_a_generic_sheet_reference_is_not(self):
        for text in ("show me the sheet", "price for M-1 in the workbook",
                     "list each sheet", "summarize the document"):
            assert not ap.mentions_sheet_reference(text), text


# Sheet-scope browse record contract (2026-09-30) -----------------------------
#
# Owner evidence for the defect this locks down: message 65b9f7bd stored the
# raw workbook-read ARTIFACT as ``structured_result``; the ask lane rendered
# it with ``present_from_record`` — a record-schema consumer — and produced
# 'Results from the saved copy of the workbook: … Coverage: partial.' with
# zero rows. The browse must stamp a RECORD (source_identity /
# requested_items / targets), flagged as a listing so the presenter shows
# rows instead of candidate-disambiguation language.

class TestSheetBrowseRecord:
    """_build_sheet_browse_record emits the presenter's schema, and the
    presenter renders a listing — file identity, rows, stated cap."""

    @staticmethod
    def _rows(sheet_rows):
        return {
            sheet: [{"row": rn,
                     "cells": [("MODEL", f"M-{rn}"), ("PRICE", 100 * rn)]}
                    for rn in sheet_rows]
            for sheet, sheet_rows in sheet_rows.items()
        }

    def _build(self, **over):
        import core.chat_tool_planner as planner

        kwargs = dict(
            scope_sheets=["Alpha"],
            rows_by_sheet=self._rows({"Alpha": [2, 3, 4]}),
            sheet_total_rows={"Alpha": 3},
            file_name="Price List.xlsx",
            prov={"source": "src", "resource_id": "res-1",
                  "content_hash": "hash-1",
                  "ingested_at": "2026-09-07T23:06:19"},
            catalog_truncated=False,
            indexed_sheets=5,
            scanned_sheets=5,
            attempt_id="browse-test-1",
        )
        kwargs.update(over)
        return planner._build_sheet_browse_record(**kwargs)

    def test_record_carries_record_schema_not_artifact_schema(self):
        rec = self._build()
        assert rec["schema_version"].startswith("structured-result")
        # The exact keys whose absence rendered 'the workbook / partial'.
        assert rec["source_identity"]["file_name"] == "Price List.xlsx"
        assert rec["requested_items"] == ["Alpha"]
        assert rec["requested_sheets"] == ["Alpha"]
        assert rec["evidence_action"] == "new_read"

    def test_target_is_a_listing(self):
        rec = self._build()
        t = rec["targets"][0]
        assert t["presentation"] == "listing"
        assert t["item"] == "Alpha"
        assert [c["ref"] for c in t["identity"]["candidates"]] == [
            "Alpha!R2", "Alpha!R3", "Alpha!R4"]

    def test_render_shows_rows_and_file_identity(self):
        out = ap.present_from_record(self._build())["answer"]
        assert "Price List.xlsx" in out
        assert "Alpha!R2" in out and "Alpha!R4" in out
        # The degraded footer the artifact stamp produced.
        assert "the workbook" not in out
        assert "Coverage: partial" not in out
        # A listing is not an ambiguity: no confirmation ask.
        assert "which one is yours" not in out

    def test_render_states_the_cap_against_the_real_row_count(self):
        rec = self._build(
            rows_by_sheet=self._rows({"Alpha": list(range(2, 14))}),
            sheet_total_rows={"Alpha": 366})
        out = ap.present_from_record(rec)["answer"]
        assert "first 12 of 366 rows" in out

    def test_empty_sheet_states_no_rows_without_claiming_absence(self):
        rec = self._build(rows_by_sheet={"Alpha": []},
                          sheet_total_rows={"Alpha": 0})
        out = ap.present_from_record(rec)["answer"]
        assert "no rows in the indexed content searched" in out

    def test_coverage_footer_keeps_the_workbook_numbers(self):
        out = ap.present_from_record(self._build())["answer"]
        assert "searched all 5 sheets of this copy" in out


# Conversational rendering contract (2026-09-30) — research-grounded UX:
# answer-first with layered detail; user vocabulary in the bubble; the
# scope receipt, binding receipt, and retry delta state their provenance.

class TestConversationalRendering:
    def _found_record(self, **over):
        outcomes = {"M-1": {"target": "M-1", "status": "found",
                            "evidence": [_ev("LINMAC", 26, "A26",
                                             [_v("C26", "1777",
                                                 "List Price")])]}}
        targets = ap.build_targets_from_scan(["M-1"], outcomes, {})
        rec = ap.build_structured_record(
            source_identity={"file_name": "w.xlsx",
                             "ingested_at": "2026-09-07T23:06:19"},
            evidence_revision="r-1", attempt_id="a-1",
            evidence_action="new_read", requested_items=["M-1"],
            requested_fields=["price"], targets=targets,
            coverage={"indexed_sheets": 2, "scanned_entries": 2})
        rec.update(over)
        return rec

    def test_answer_is_written_for_the_reader(self):
        out = ap.present_from_record(self._found_record())["answer"]
        # value first, human locator, human date
        assert "M-1** — 1,777 'List Price' (LINMAC sheet, row 26, cell C26, matched at A26" in out
        assert "(saved 2026-09-07)" in out
        # audit vocabulary is gone from the bubble
        assert "indexed content searched" not in out
        assert "identity A26" not in out
        assert "absence claim" not in out

    def test_ambiguous_item_asks_like_a_person(self):
        outcomes = {"M-1": {"target": "M-1", "status": "ambiguous",
                            "evidence": [
                                _ev("Tennsmith", 338, "A338",
                                    [_v("E338", "3254", "PRICE")]),
                                _ev("Tennsmith", 340, "D340",
                                    [_v("E340", "906", "PRICE")])]}}
        targets = ap.build_targets_from_scan(["M-1"], outcomes, {})
        out = ap.present(requested_items=["M-1"],
                         requested_fields=["price"],
                         source={"file_name": "w.xlsx"},
                         targets=targets)["answer"]
        assert "2 possible rows" in out
        assert "Tennsmith sheet, row 338" in out
        assert "which one do you mean?" in out
        assert "which one is yours" not in out

    def test_standing_scope_receipt_names_the_preference(self):
        rec = self._found_record(
            requested_sheets=["Tennsmith"],
            requested_sheets_sources={"Tennsmith": "standing"})
        out = ap.present_from_record(rec)["answer"]
        assert ("Looking in: Tennsmith — per your standing preference."
                in out), out

    def test_message_scope_receipt_has_no_preference_note(self):
        rec = self._found_record(
            requested_sheets=["Tennsmith"],
            requested_sheets_sources={"Tennsmith": "message"})
        out = ap.present_from_record(rec)["answer"]
        assert "Looking in: Tennsmith." in out
        assert "standing preference" not in out

    def test_user_bound_row_says_so_instead_of_re_asking(self):
        outcomes = {"M-1": {"target": "M-1", "status": "found",
                            "bound_by": "user_assertion",
                            "evidence": [_ev("Tennsmith", 338, "A338",
                                             [_v("E338", "3254",
                                                 "PRICE")])]}}
        targets = ap.build_targets_from_scan(["M-1"], outcomes, {})
        out = ap.present(requested_items=["M-1"],
                         requested_fields=["price"],
                         source={"file_name": "w.xlsx"},
                         targets=targets)["answer"]
        assert "the row you confirmed" in out, out
        assert "which one do you mean" not in out

    def test_absence_is_plain_and_bounded_to_the_copy(self):
        outcomes = {"M-1": {"target": "M-1", "status": "absent",
                            "evidence": []}}
        targets = ap.build_targets_from_scan(["M-1"], outcomes, {})
        out = ap.present(requested_items=["M-1"],
                         requested_fields=["price"],
                         source={"file_name": "w.xlsx",
                                 "coverage": {"indexed_sheets": 2}},
                         targets=targets)["answer"]
        assert "M-1** — no match in this copy" in out
        assert "about this copy, not the live file" in out


class TestClosurePhrasing:
    """Background-edit outcomes close the loop in user terms."""

    def test_outcome_leads_reference_the_users_update(self):
        from core.async_turn_continuation import _readable_outcome_text

        assert _readable_outcome_text("applied", "") == \
            "Done — your update is applied."
        assert "saved as a proposal" in _readable_outcome_text(
            "awaiting_approval", "")
        assert "changed while I was editing" in _readable_outcome_text(
            "conflict", "")
        assert _readable_outcome_text("failed", "") == \
            "I couldn't apply your update."


# Domain independence (2026-09-30 generalization): the conversation seams
# must behave identically for a non-pricing domain. A preference may
# RANK, never ERASE — the default pricing-shaped request vocabulary must
# not blank a recipes/stock/lead-time workbook. Fixtures follow the house
# style: synthetic, domain-independent (no real product vocabulary).

class TestDomainIndependence:
    @staticmethod
    def _recipes_outcomes():
        return {"sourdough": {"target": "sourdough", "status": "found",
                              "evidence": [
                                  _ev("Breads", 14, "A14",
                                      [_v("D14", "78%", "HYDRATION"),
                                       _v("E14", "2 lb", "LOAF WEIGHT")])]}}

    def test_pricing_default_does_not_blank_a_non_pricing_domain(self):
        """requested_fields defaults to ['price']; a hydration row must
        still answer with its own values, not 'no price column'."""
        targets = ap.build_targets_from_scan(
            ["sourdough"], self._recipes_outcomes(), {})
        out = ap.present(requested_items=["sourdough"],
                         requested_fields=["price"],
                         source={"file_name": "recipe log.xlsx"},
                         targets=targets)["answer"]
        assert "78% 'HYDRATION'" in out, out
        assert "no column matching" not in out

    def test_absent_values_still_say_which_fields_were_sought(self):
        outcomes = {"sourdough": {"target": "sourdough", "status": "found",
                                  "evidence": [_ev("Breads", 14, "A14", [])]}}
        targets = ap.build_targets_from_scan(
            ["sourdough"], outcomes, {})
        out = ap.present(requested_items=["sourdough"],
                         requested_fields=["price"],
                         source={"file_name": "recipe log.xlsx"},
                         targets=targets)["answer"]
        assert "no column matching price" in out, out

    def test_probe_record_path_surfaces_non_pricing_columns(self):
        """The content-probe record path (per_item) picks value columns by
        a pricing-family preference; when the family matches none, the
        row's own leading columns flow (stock counts, hydration)."""
        per_item = {
            "sourdough": {
                "entity_name": "Breads",
                "columns": ["ITEM", "HYDRATION", "STOCK"],
                "column_letters": {"ITEM": "A", "HYDRATION": "D",
                                   "STOCK": "F"},
                "rows": [{"__sheet_row": 14, "ITEM": "sourdough",
                          "HYDRATION": "78%", "STOCK": 12}],
                "matched_cells": [{"cell": "A14", "value": "sourdough"}],
            },
        }
        targets = ap.build_targets_from_scan(["sourdough"], {}, per_item)
        out = ap.present(requested_items=["sourdough"],
                         requested_fields=["price"],
                         source={"file_name": "recipe log.xlsx"},
                         targets=targets)["answer"]
        assert "78% 'HYDRATION'" in out, out
        assert "12" in out  # STOCK flows too

    def test_field_request_extraction_spans_domains(self):
        from core.workbook_read_artifact import extract_field_requests

        got = extract_field_requests(
            ["how many do we have in stock for the sourdough?"])
        assert "quantity" in got, got
        got2 = extract_field_requests(
            ["what is the list price for the No. 381"])
        assert "price" in got2, got2

    def test_binding_receipt_works_in_non_pricing_domain(self, tmp_path):
        """The 'row you confirmed' receipt is structural: any domain's
        user-asserted, read-verified binding collapses the ambiguity."""
        import pandas as pd

        from core.workbook_read_artifact import inspect_dataset_entries

        path = tmp_path / "recipes.parquet"
        pd.DataFrame({
            "__sheet_row": [3, 14, 40],
            "ITEM": ["rye", "sourdough", "focaccia"],
            "HYDRATION": ["70%", "78%", "65%"],
        }).to_parquet(path)
        entry = {"entity_name": "Breads", "parquet_path": str(path),
                 "row_count": 3, "coverage": {"known": True,
                                              "truncated": False}}
        binding = {"item": "sourdough", "sheet": "Breads", "row": 14,
                   "content_hash": "rev-r", "confirmation": "user_supplied"}
        art = inspect_dataset_entries(
            [entry], "recipe log.xlsx",
            query="hydration for the sourdough loaf", context_texts=[],
            targets=["sourdough"],
            disambiguation={"resolved_bindings": [binding]},
            content_hash="rev-r")
        outcome = art["coverage"]["outcomes"][0]
        assert outcome["status"] == "found"
        assert outcome["bound_by"] == "user_assertion", outcome
        targets = ap.build_targets_from_scan(
            ["sourdough"], {outcome["target"]: outcome}, {})
        out = ap.present(requested_items=["sourdough"],
                         requested_fields=["price"],
                         source={"file_name": "recipe log.xlsx"},
                         targets=targets)["answer"]
        assert "78% 'HYDRATION'" in out
        assert "the row you confirmed" in out, out

    def test_sheet_scope_receipt_is_name_agnostic(self):
        """The standing-scope receipt renders for ANY sheet name — the
        mechanism resolves against whatever the workbook indexes."""
        rec = ap.build_structured_record(
            source_identity={"file_name": "recipe log.xlsx"},
            evidence_revision="r", attempt_id="a",
            evidence_action="new_read",
            requested_items=["sourdough"], requested_fields=["price"],
            targets=ap.build_targets_from_scan(
                ["sourdough"], self._recipes_outcomes(), {}),
            coverage={"indexed_sheets": 1},
            requested_sheets=["Breads"],
            requested_sheets_sources={"Breads": "standing"})
        out = ap.present_from_record(rec)["answer"]
        assert "Looking in: Breads — per your standing preference." in out


# Objective-anaphora recognition (2026-09-30): floor-first (retrieval-noun
# regex) with a cheap-NLU residue behind the same interface as every other
# refinement verdict — fail-closed to the plain reading. Research-grounded:
# conversation→standalone condensation (InfoCQR/CONQRR/ConvSearch-R1) + the
# repo's measured readout gate (JevK5-9B 4/4, Qwen3.5-4B 4/4 on the
# anaphoric kind — RESEARCH_ollaya_jev.md).

class TestObjectiveAnaphoraRecognition:
    def test_floor_regex_catches_the_noun_family(self):
        import core.chat_tool_planner as planner

        # positives: the noun family, plus the DEMONSTRATIVE-OBJECT
        # shapes observed in this workspace's real follow-up turns
        # (corpus-measured 2026-09-30: "please research this" was the
        # residual genuine-reference family after the nouns).
        for yes in ("show me the tennsmith sheet searches",
                    "check those results again on the roper sheet",
                    "re-run the lookup for my parts",
                    "the matches you found on the alpha sheet",
                    "please research this",
                    "check it again",
                    "pull those up"):
            assert planner._RETRIEVAL_REFERENCE_RE.search(yes), yes
        # negatives: fresh asks and relative-pronoun shapes — a false
        # positive turns a listing into a re-run (the inverted defect).
        for no in ("show me the tennsmith sheet",
                   "list the roper sheet",
                   "what is on the alpha tab",
                   "research quantum physics",
                   "find the row that was mentioned",
                   "find reports",
                   "is our $7,519 shear in stock right now?"):
            assert not planner._RETRIEVAL_REFERENCE_RE.search(no), no

    @pytest.mark.asyncio
    async def test_residue_verdict_is_binary_and_fail_closed(self):
        import core.llm.cheap_nlu as cheap

        # switch off (TESTING) -> None without any LLM demand
        assert await cheap.refers_to_prior_retrieval(
            "pull up what you found before") is None

        for verdict in (True, False, None):
            async def fake_binary(kind, question, subject,
                                  llm_service=None, _v=verdict):
                assert kind == "anaphoric_prior_retrieval"
                # the question carries the message and stays
                # domain/person-neutral
                assert "pull up what you found" in question
                return _v
            with patch.object(cheap, "binary", fake_binary):
                got = await cheap.refers_to_prior_retrieval(
                    "pull up what you found before")
            assert got is verdict

    def test_inherited_targets_flag_rides_the_task(self):
        """The orchestrator marks inherited targets so the reader's gate
        can tell 're-run what I asked before' from a listing; the flag
        is informational (the gate decides on recognized reference, not
        on carrier shape)."""
        import pathlib

        src = pathlib.Path(
            __import__("integrations.chat_orchestrator", fromlist=["x"])
            .__file__).read_text()
        assert '"inherited_targets": bool(' in src
