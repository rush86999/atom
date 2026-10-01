# -*- coding: utf-8 -*-
"""Value-provenance tracing + the typed two-option decision (2026-10-01).

Owner policy: a value the workbook cannot derive is not 'unsourced'
until every OTHER cataloged document (attachments, worksheets) has been
checked; body-only values then get a typed choice — confirm as-is, or
rebuild from components. Domain-neutral: items are tokens, documents
are catalog entries, labels carry no business vocabulary.
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


class TestTrace:
    def test_items_traced_across_other_documents(self):
        from core.value_provenance import trace_items_across_catalog

        probe = _probe_factory({
            ("Tennsmith Letter 072026.pdf.xlsx", "SLE24-16"),
            ("Discount Schedule.xlsx", "SLE24-16"),
            ("Tennsmith Letter 072026.pdf.xlsx", "GSL48-16"),
        })
        trace = trace_items_across_catalog(
            ["SLE24-16", "GSL48-16", "M-404"],
            exclude_file="Main Price List.xlsx",
            catalog=_catalog(), probe=probe)
        assert trace["SLE24-16"] == [
            "Tennsmith Letter 072026.pdf.xlsx", "Discount Schedule.xlsx"]
        assert trace["GSL48-16"] == ["Tennsmith Letter 072026.pdf.xlsx"]
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

        lines = provenance_lines({
            "SLE24-16": ["Letter.xlsx"],
            "M-404": [],
        })
        assert any("SLE24-16: found in Letter.xlsx" in l for l in lines)
        assert any("M-404" in l and "body-only" in l for l in lines)


class TestDecisionOptions:
    def test_options_are_generic_and_clickable(self):
        from core.value_provenance import decision_options

        opts = decision_options()
        assert [o["type"] for o in opts] == ["confirm", "execute"]
        joined = " ".join(o["label"] for o in opts).lower()
        for business_word in ("vipul", "csa", "freight", "margin",
                              "price list", "machinery"):
            assert business_word not in joined, business_word
        assert "as-is" in joined and "rebuild" in joined

    def test_wired_into_both_compare_lanes(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        # the helper carries the policy once; both lanes call it
        helper = inspect.getsource(orch.ChatOrchestrator._not_found_policy)
        assert "value_provenance import" in helper
        assert src.count("await self._not_found_policy(") >= 2
        assert "(_ask_options or [])" in src
        assert "(_direct_options or [])" in src


# Miss-trigger (2026-10-01 owner clarification): the policy's original
# context is 'prices that weren't found in the price list' — plain READ
# misses fire it, not just comparison turns.

class TestMissTrigger:
    def test_read_miss_items_detected_from_targets(self):
        import integrations.chat_orchestrator as orch

        structured = {
            "requested_items": ["A-1", "B-2"],
            "targets": [
                {"item": "A-1", "identity": {"status": "single"}},
                {"item": "B-2", "identity": {"status": "none"}},
            ],
        }
        assert orch.ChatOrchestrator._read_miss_items(structured) == ["B-2"]
        assert orch.ChatOrchestrator._read_miss_items(None) == []

    def test_both_lanes_trigger_on_misses(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert src.count("_read_miss_items(") >= 2
        assert src.count("await self._not_found_policy(") >= 2
        # the helper carries the policy once, shared
        helper = inspect.getsource(orch.ChatOrchestrator._not_found_policy)
        assert "trace_items_across_catalog" in helper
        assert "decision_options" in helper

    def test_policy_helper_semantics_no_items_no_output(self):
        import asyncio

        import integrations.chat_orchestrator as orch

        o = object.__new__(orch.ChatOrchestrator)
        lines, opts = asyncio.run(
            o._not_found_policy({"requested_items": []}, None, None, None))
        assert lines == [] and opts is None
