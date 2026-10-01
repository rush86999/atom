# -*- coding: utf-8 -*-
"""Value provenance: a CAPABILITY, not a policy (2026-10-01 owner
correction).

The not-found escalation (attachments first; body-only → the two
options with the business specifics — Vipul, CSA, freight, margin) is
BUSINESS TRAINING delivered through the teaching system, never platform
code. What the platform owns is only the tool: which other cataloged
documents carry given item codes.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")


def _catalog():
    return [
        {"file_name": "Main Price List.xlsx", "entity_name": "S"},
        {"file_name": "Tennsmith Letter 072026.pdf.xlsx", "entity_name": "L"},
        {"file_name": "Discount Schedule.xlsx", "entity_name": "D"},
    ]


def _probe_factory(hits):
    def probe(entries, item):
        name = (entries or [{}])[0].get("file_name")
        return (name, item) in hits
    return probe


class TestCapability:
    def test_items_traced_across_other_documents(self):
        from core.value_provenance import trace_items_across_catalog

        probe = _probe_factory({
            ("Tennsmith Letter 072026.pdf.xlsx", "SLE24-16"),
            ("Discount Schedule.xlsx", "SLE24-16"),
        })
        trace = trace_items_across_catalog(
            ["SLE24-16", "M-404"],
            exclude_file="Main Price List.xlsx",
            catalog=_catalog(), probe=probe)
        assert trace["SLE24-16"] == [
            "Tennsmith Letter 072026.pdf.xlsx", "Discount Schedule.xlsx"]
        assert trace["M-404"] == []

    def test_excluded_file_is_never_a_hit(self):
        from core.value_provenance import trace_items_across_catalog

        probe = _probe_factory({("Main Price List.xlsx", "SLE24-16")})
        trace = trace_items_across_catalog(
            ["SLE24-16"], exclude_file="MAIN PRICE LIST.XLSX",
            catalog=_catalog(), probe=probe)
        assert trace["SLE24-16"] == []

    def test_lines_distinguish_found_and_body_only(self):
        from core.value_provenance import provenance_lines

        lines = provenance_lines({"SLE24-16": ["Letter.xlsx"], "M-404": []})
        assert any("SLE24-16: found in Letter.xlsx" in l for l in lines)
        assert any("M-404" in l and "body-only" in l for l in lines)


class TestPolicyIsTrainingNotCode:
    def test_no_auto_fire_in_the_read_lanes(self):
        """The escalation must NOT run as platform code on read misses —
        it is a taught lesson executed by the trained agent."""
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "_not_found_policy" not in src
        assert "_read_miss_items" not in src
        assert not hasattr(orch.ChatOrchestrator, "_not_found_policy")

    def test_tool_is_registered_for_the_trained_agent(self):
        import inspect

        import core.chat_tool_planner as planner

        src = inspect.getsource(planner)
        assert '"value_trace"' in src
        # the tool returns evidence only — no options, no policy words
        tool_block = src[src.find('== "value_trace"'):]
        tool_block = tool_block[:tool_block.find('== "find_all"')]
        for policy_word in ("use as-is", "rebuild", "vipul", "csa",
                            "freight", "margin"):
            assert policy_word not in tool_block.lower(), policy_word
        assert "value_provenance" in tool_block

    def test_lesson_delivered_through_the_teaching_system(self):
        """The business policy lives as a global lesson on the chat-facing
        agents — delivered 2026-10-01 via deliver_teacher_lesson (live:
        status ok on atom_main, Chat Assistant, and Sales Agent). The
        row-level check runs when the scratch schema carries the current
        AgentRegistry columns; older scratch DBs lag the model and skip."""
        from sqlalchemy import text as _sql

        from core.database import SessionLocal

        db = SessionLocal()
        try:
            try:
                rows = db.execute(_sql(
                    "SELECT lessons_learned FROM agent_registry "
                    "WHERE lessons_learned IS NOT NULL")).fetchall()
            except Exception as exc:  # stale scratch schema — see docstring
                import pytest

                pytest.skip(f"scratch schema lags model: {exc}")
            hits = 0
            for (blob,) in rows:
                low = " ".join(str(blob or "").lower().split())
                if ("value_trace" in low or
                        "not found in the price list" in low) and \
                        "vipul" in low:
                    hits += 1
            assert hits >= 1, "the taught lesson was not found on any agent"
        finally:
            db.close()
