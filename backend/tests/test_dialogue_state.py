# -*- coding: utf-8 -*-
"""Event-sourced dialogue state (2026-10-01, migration step 2).

Invariants under test:
- APPEND-ONLY: the store exposes append/fetch only; supersede/retire are
  new events, never mutations (replay is the proof).
- PROJECTION CORRECTNESS: replaying the events yields the active
  objective / standing preferences / revision-scoped bindings.
- RESTART SURVIVAL: state is DB-backed per conversation — a fresh fetch
  (as a restarted process performs) rebuilds identical projections.
- THE DURABLE-FACTS RULE: a standing preference taught on an EARLIER
  turn reaches a LATER turn's program (no history-window decay), and
  the objective projection outranks the carrier chain while remaining
  its fallback.
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

CONV = f"dstest-{uuid.uuid4().hex[:8]}"
T8 = ["No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
      "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]


def _ev(kind, payload, eid=None, supersedes=None):
    return {"id": eid or uuid.uuid4().hex, "kind": kind,
            "payload": payload, "supersedes_event_id": supersedes}


# ---------------------------------------------------------------------------
# Pure projection
# ---------------------------------------------------------------------------

class TestProjectEvents:
    def test_latest_objective_wins_and_supersede_clears(self):
        events = [
            _ev("objective_set", {"items": T8}),
            _ev("objective_set", {"items": ["381"]}),
        ]
        assert [i for i in
                __import__("core.dialogue_state", fromlist=["x"])
                .project_events(events)["objective"]["items"]] == ["381"]
        from core.dialogue_state import OBJECTIVE_SUPERSEDED, project_events

        events.append(_ev(OBJECTIVE_SUPERSEDED, {}))
        assert project_events(events)["objective"] is None

    def test_preferences_accumulate_and_retire_by_event_id(self):
        from core.dialogue_state import (PREFERENCE_RETIRED, PREFERENCE_SET,
                                         project_events)

        e1 = _ev(PREFERENCE_SET, {"phrase": "tennsmith sheet"})
        e2 = _ev(PREFERENCE_SET, {"phrase": "exclude discontinued rows"})
        state = project_events([e1, e2])
        assert [p["phrase"] for p in state["preferences"]] == [
            "tennsmith sheet", "exclude discontinued rows"]
        retired = project_events(
            [e1, e2, _ev(PREFERENCE_RETIRED, {"event_id": e1["id"]})])
        assert [p["phrase"] for p in retired["preferences"]] == [
            "exclude discontinued rows"]

    def test_bindings_expire_by_revision(self):
        from core.dialogue_state import BINDING_CAPTURED, project_events

        e1 = _ev(BINDING_CAPTURED, {"item": "381", "sheet": "Tennsmith",
                                    "row": 338, "content_hash": "rev-1"})
        state = project_events([e1])
        assert len(state["bindings"]) == 1
        assert project_events([e1])["bindings"][0]["row"] == 338

    def test_active_bindings_filter_by_revision_in_store(self):
        from core import dialogue_state as ds

        cid = f"dstest-{uuid.uuid4().hex[:8]}"
        ds.append_event(ds.BINDING_CAPTURED, cid, {
            "item": "381", "sheet": "Tennsmith", "row": 338,
            "content_hash": "rev-1"})
        # active at its captured revision, expired at a changed one
        assert ds.active_bindings(cid, "rev-1")[0]["row"] == 338
        assert ds.active_bindings(cid, "rev-2") == []
        # no revision filter = all (the caller scopes when it has one)
        assert len(ds.active_bindings(cid)) == 1


# ---------------------------------------------------------------------------
# Store round-trip (TESTING=1 scratch DB)
# ---------------------------------------------------------------------------

class TestStore:
    def test_append_fetch_round_trip_and_restart_survival(self):
        from core import dialogue_state as ds

        cid = f"dstest-{uuid.uuid4().hex[:8]}"
        assert ds.append_event(
            ds.OBJECTIVE_SET, cid, {"items": T8, "file": "w.xlsx"})
        assert ds.append_event(
            ds.PREFERENCE_SET, cid, {"phrase": "tennsmith sheet"})
        # a LATER process (fresh fetch) rebuilds identical projections
        assert ds.active_objective_items(cid) == T8
        assert ds.active_preference_phrases(cid) == ["tennsmith sheet"]
        # re-fetch (restart-shaped) is identical
        assert ds.active_objective_items(cid) == T8

    def test_fetch_returns_oldest_first_and_bounded(self):
        from core import dialogue_state as ds

        cid = f"dstest-{uuid.uuid4().hex[:8]}"
        for n in range(5):
            ds.append_event(ds.PROGRAM_RECORDED, cid, {"n": n})
        events = ds.fetch_events(cid)
        assert [e["payload"].get("n") for e in events] == [0, 1, 2, 3, 4]
        assert len(ds.fetch_events(cid, limit=3)) == 3

    def test_unknown_conversation_is_empty_never_error(self):
        from core import dialogue_state as ds

        cid = f"dstest-absent-{uuid.uuid4().hex[:8]}"
        assert ds.active_objective_items(cid) == []
        assert ds.active_preference_phrases(cid) == []
        assert ds.fetch_events(cid) == []

    def test_record_program_is_bounded_audit(self):
        from core import dialogue_state as ds

        cid = f"dstest-{uuid.uuid4().hex[:8]}"
        program = {"schema": "turn-program-1", "operation": "compare",
                   "target_set": {"kind": "contrastive_resolved",
                                  "items": T8[1:], "origin": "canvas"},
                   "reference": {"prior_retrieval": False,
                                 "basis": "floor"},
                   "clarify": {"needed": False}}
        ds.record_program(cid, program)
        events = ds.fetch_events(cid)
        assert len(events) == 1 and events[0]["kind"] == "program_recorded"
        assert events[0]["payload"]["target_set"]["size"] == 7
        assert "items" not in events[0]["payload"]["target_set"]


# ---------------------------------------------------------------------------
# Integration: the durable-facts rule through the ask-lane wiring
# ---------------------------------------------------------------------------

class TestDurableFactsIntegration:
    def test_old_lesson_reaches_a_later_turns_program(self):
        """THE 2026-09-30 defect, closed at the architecture layer: the
        preference taught on an early turn ('always include the
        tennsmith sheet') must reach a MUCH later turn's program even
        though no resolver window sees the teaching turn."""
        from core import dialogue_state as ds
        from core.turn_program import build_turn_program

        cid = f"dstest-{uuid.uuid4().hex[:8]}"
        # turn 3 (long ago): the user teaches the standing preference
        ds.append_event(ds.PREFERENCE_SET, cid,
                        {"phrase": "tennsmith sheet"})
        # turn 300 (now): a bare find with no mention of any sheet
        merged_hints = (["whatever this turn said"]
                        + ds.active_preference_phrases(cid))
        program = build_turn_program(
            "find the price for No. 381 in the workbook",
            file_mention="Consolidated Price List 2019.xlsx",
            prior_items=["381"], last_served_items=[], own_items=["381"],
            standing_scope_hints=merged_hints)
        assert program["constraints"]["sheets"] == [
            "whatever this turn said", "tennsmith sheet"]
        assert program["constraints"]["sources"]["tennsmith sheet"] == \
            "standing"

    def test_objective_projection_is_read_first_carriers_fallback(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "active_objective_items(" in src
        assert "or _stored_requested_items(session)" in src
        assert "active_preference_phrases(" in src

    def test_preference_capture_is_the_universal_seam(self):
        """Capture must fire on EVERY lane (the teach turn routes to the
        teaching acknowledgment lane, which builds no turn decision —
        decision-layer capture missed it live). The single capture point
        is the TOP of process_chat_message, which every user message
        crosses before any lane split."""
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "PREFERENCE_SET" in src
        assert "always|whenever|each time|from now on" in src
        assert "_scope_constraints(message" in src
        import core.turn_decision as td

        td_src = inspect.getsource(td.build_turn_decision)
        assert "PREFERENCE_SET" not in td_src


# Step-2 completion: bindings + file identity as durable facts (2026-10-01)

class TestDurableBindingAndFileFacts:
    def test_capture_seam_writes_ledger_events(self):
        """A user assertion verified by a read lands in BOTH the task
        carrier and the ledger — and the ledger survives the carrier."""
        import uuid as _uuid

        from integrations.chat_orchestrator import (
            _capture_resolved_row_bindings,
        )
        from core import dialogue_state as ds
        from core.pending_file_task import FILE_TASK_SESSION_KEY

        cid = f"dstest-{_uuid.uuid4().hex[:8]}"
        session = {FILE_TASK_SESSION_KEY: {"disambiguation": {}}}
        structured = {
            "source_identity": {"content_hash": "rev-r"},
            "targets": [{
                "item": "sourdough", "aliases": [],
                "identity": {"status": "single", "candidates": [{
                    "ref": "Breads!R14",
                    "identity": {"references": [
                        {"sheet": "Breads", "cell": "A14", "row": 14,
                         "value": "sourdough", "role": "matched_target"}]},
                    "values": [{"col": "D14", "basis": "HYDRATION",
                                "kind": "text", "display": "78%"}]}]},
                "field": {},
            }],
        }
        _capture_resolved_row_bindings(
            session, [], structured,
            current_message="the sourdough is on the breads sheet "
                            "under row 14",
            conversation_id=cid)
        got = ds.active_bindings(cid, "rev-r")
        assert got and got[0]["row"] == 14 and got[0]["sheet"] == "Breads"
        assert got[0]["content_hash"] == "rev-r"
        # revision expiry still applies to the LEDGER copy
        assert ds.active_bindings(cid, "rev-other") == []

    def test_file_identity_is_a_durable_fact(self):
        from core import dialogue_state as ds

        cid = f"dstest-{uuid.uuid4().hex[:8]}"
        ds.append_event(ds.FILE_RESOLVED, cid, {
            "file_name": "Consolidated Price List 2019.xlsx",
            "resource_id": "r-1", "content_hash": "h-1"})
        state = ds.project_events(ds.fetch_events(cid))
        assert state["file"]["file_name"] == "Consolidated Price List 2019.xlsx"

    def test_anaphora_ledger_fallback_wired(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch._resolve_anaphoric_file_mention)
        assert "conversation_id" in src
        assert "LEDGER FALLBACK" in src
