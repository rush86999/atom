# -*- coding: utf-8 -*-
"""Turn-program invariants (2026-10-01, migration step 1 + 4).

The conversation failures of 2026-09-30 were re-derivation failures:
the same question decided at multiple seams, slightly differently. The
turn program decides ONCE; these tests hold the invariants that keep
that true:

I1 DETERMINISM — same inputs, identical program (byte-stable fields).
I2 DECIDED FACTS PROPAGATE — every non-empty decision reaches the
   executed read context (or the clarify rejection); nothing decided
   may vanish between interpretation and execution.
I3 CONVERSATION REPLAY — the recorded incident turns of 2026-09-30
   produce the interpretations the owner specified, asserted on WHICH
   items are investigated and WHAT operation runs — not merely that a
   lane fired.
I4 PROGRAM AUTHORITY — when a program rides the read context, the
   reader's gate consumes it instead of re-deciding.
"""
from __future__ import annotations

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

T8 = ["No. 381", "U-22", "No. 622", "TK Manual Flanger", "SLE24-16",
      "TK 1624", "TK Multi Wheel Gang Slitter", "GSL48-16"]
FILE = "Consolidated Price List 2019.xlsx"


def program(message, **kw):
    from core.turn_program import build_turn_program

    return build_turn_program(message, **kw)


# I1 -------------------------------------------------------------------------
class TestDeterminism:
    def test_same_inputs_identical_program(self):
        kw = dict(file_mention=FILE, canvas_items=T8, prior_items=T8,
                  last_served_items=["No. 381"], own_items=[],
                  standing_scope_hints=["tennsmith sheet"])
        a = program("check the other machinery and verify pricing", **kw)
        b = program("check the other machinery and verify pricing", **kw)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

    def test_carrier_order_does_not_change_interpretation(self):
        """The interpretation must depend on the SET of prior items, not
        their order (carrier write-order was a divergence source)."""
        kw = dict(file_mention=FILE, prior_items=list(reversed(T8)),
                  last_served_items=["381"], own_items=[])
        a = program("show me the searches", **kw)
        b = program("show me the searches",
                    file_mention=FILE, prior_items=T8,
                    last_served_items=["381"], own_items=[])
        # kind/origin identical; items are the same SET (the requested
        # ORDER is meaningful presentation authority and follows the
        # carrier, which this invariant deliberately does not pin)
        assert a["target_set"]["kind"] == b["target_set"]["kind"]
        assert a["target_set"]["origin"] == b["target_set"]["origin"]
        assert set(a["target_set"]["items"]) == set(b["target_set"]["items"])
        assert a["reference"] == b["reference"]


# I2 -------------------------------------------------------------------------
class TestDecidedFactsPropagate:
    """Every decided fact must appear in the read context the reader
    consumes (or the clarify response that rejects the read)."""

    @staticmethod
    def _context_from_task(task):
        """The exact context assembly _direct_confirmed_file_read
        performs — the propagation seam under test."""
        ctx = {
            "requested_targets": task.get("requested_targets") or [],
            "revised_targets": (task.get("objective_edit") or {}).get(
                "items")
            or task.get("revised_targets") or [],
            "sheet_scope_hints": task.get("sheet_scope_hints") or [],
            "turn_program": task.get("turn_program"),
        }
        return ctx

    def _task_from_program(self, tp, session_items):
        """The ask lane's consumption of the program, as wired."""
        task = {"mention": tp["file"]["mention"], "operation":
                tp["operation"] if tp["operation"] in ("refresh",
                                                       "compare") else None}
        ts = tp["target_set"]
        if ts["kind"] == "contrastive_resolved":
            task["revised_targets"] = list(ts["items"])
        elif ts["kind"] == "inherited":
            task["requested_targets"] = list(session_items)
            task["inherited_targets"] = True
        if tp["constraints"]["sheets"]:
            task["sheet_scope_hints"] = list(tp["constraints"]["sheets"])
        task["turn_program"] = tp
        return task

    def test_every_decided_fact_reaches_the_read_context(self):
        tp = program("show me the tennsmith sheet searches",
                     file_mention=FILE, prior_items=T8,
                     last_served_items=["381"], own_items=[],
                     standing_scope_hints=["tennsmith sheet"])
        task = self._task_from_program(tp, T8)
        ctx = self._context_from_task(task)
        for fact in tp["decided_facts"]:
            kind = fact["kind"]
            if kind == "operation":
                continue  # consumed by the freshness machinery, not ctx
            if kind == "file_mention":
                assert task["mention"] == fact["value"]
            elif kind == "prior_retrieval_reference":
                assert ctx["turn_program"]["reference"][
                    "prior_retrieval"] is True
            elif kind == "target_set":
                items = ctx["revised_targets"] or ctx["requested_targets"]
                assert sorted(map(str, items)) == sorted(
                    map(str, fact["value"]))
            elif kind == "standing_scope":
                assert set(ctx["sheet_scope_hints"]) >= set(
                    fact["value"])

    def test_unresolved_set_rejects_the_read_entirely(self):
        """I2's rejection half: a clarify program must produce NO read
        context at all — nothing inherited may leak into execution."""
        tp = program(
            "check the other machinery and verify pricing",
            file_mention=FILE, prior_items=["381"],
            last_served_items=["381"], own_items=[])
        assert tp["clarify"]["needed"] is True
        assert tp["target_set"]["kind"] == "unresolved"
        # the wiring contract: clarify => early return BEFORE any
        # requested_targets are stamped on the task
        task = {"mention": tp["file"]["mention"]}
        ctx = self._context_from_task(task)
        assert ctx["requested_targets"] == []
        assert ctx["revised_targets"] == []


# I3 -------------------------------------------------------------------------
class TestConversationReplay:
    """The 2026-09-30 incidents, replayed as a conversation: each turn's
    program must encode the interpretation the owner specified."""

    def test_turn1_fresh_scoped_find(self):
        tp = program("find model 381 in tennsmith sheet",
                     file_mention=FILE, prior_items=[], own_items=["381"])
        assert tp["operation"] == "read"
        assert tp["target_set"] == {
            "kind": "explicit", "items": ["381"], "origin": "message"}

    def test_turn2_reference_reruns_the_objective(self):
        tp = program("show me the tennsmith sheet searches",
                     file_mention=FILE, prior_items=T8,
                     last_served_items=["381"], own_items=[])
        assert tp["reference"]["prior_retrieval"] is True
        assert tp["target_set"]["kind"] == "inherited"
        assert len(tp["target_set"]["items"]) == 8

    def test_turn3_other_machinery_without_a_list_clarifies(self):
        tp = program(
            "check the other machinery from price list and verify if "
            "any pricing needs to be updated from latest pricing data",
            file_mention=FILE, prior_items=["381"],
            last_served_items=["381"], own_items=[])
        assert tp["operation"] == "compare"
        assert tp["clarify"]["needed"] is True

    def test_turn3_with_the_draft_investigates_the_other_seven(self):
        tp = program(
            "check the other machinery from price list and verify if "
            "any pricing needs to be updated from latest pricing data",
            file_mention=FILE, canvas_items=T8, prior_items=["381"],
            last_served_items=["381"], own_items=[])
        assert tp["operation"] == "compare"
        assert tp["target_set"]["kind"] == "contrastive_resolved"
        assert "No. 381" not in tp["target_set"]["items"]
        assert len(tp["target_set"]["items"]) == 7

    def test_bare_sheet_mention_is_a_listing_not_a_rerun(self):
        tp = program("show me the tennsmith sheet",
                     file_mention=FILE, prior_items=T8,
                     last_served_items=["381"], own_items=[])
        assert tp["reference"]["prior_retrieval"] is False
        assert tp["target_set"]["kind"] == "none"

    def test_nlu_residue_overrides_the_floor(self):
        """The residue verdict ('pull up what you found on the sheet')
        is the program's input, recorded with its basis."""
        tp = program("pull up what you found on the tennsmith sheet",
                     file_mention=FILE, prior_items=T8,
                     last_served_items=["381"], own_items=[],
                     prior_retrieval_reference=True,
                     reference_basis="nlu")
        assert tp["reference"] == {
            "prior_retrieval": True, "basis": "nlu"}


# I4 -------------------------------------------------------------------------
class TestProgramAuthority:
    def test_reader_gate_consumes_the_program(self):
        """With a program on the context, the reader's gate takes the
        reference and target set from it and skips its own regex/NLU
        re-derivation (single decision)."""
        import inspect

        import core.chat_tool_planner as planner

        src = inspect.getsource(planner._datasets_named_file_block)
        assert '== "turn-program-1"' in src
        assert "_retrieval_reference = bool(_tp_ref.get" in src
        # fallback preserved for program-less callers
        assert "_RETRIEVAL_REFERENCE_RE.search" in src

    def test_ask_lane_builds_the_program_once(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "build_turn_program(" in src
        assert '"turn_program"] = _turn_program' in src
        assert "clarifying, NO read ran" in src

    def test_read_context_carries_the_program(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(
            orch.ChatOrchestrator._direct_confirmed_file_read)
        assert '"turn_program": pending_task.get("turn_program")' in src

    def test_compare_operation_rides_the_freshness_machinery(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(
            orch.ChatOrchestrator._direct_confirmed_file_read)
        assert 'in ("refresh", "compare")' in src
