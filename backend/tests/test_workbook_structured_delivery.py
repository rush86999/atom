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
