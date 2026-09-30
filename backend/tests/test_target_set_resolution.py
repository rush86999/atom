# -*- coding: utf-8 -*-
"""Target-set resolution + comparison planning (2026-09-30).

Owner directive after the 'check the other machinery' incident: the app
mistook "related to the previous task" for "repeat the previous task."
The regression must assert WHICH items were investigated and WHAT
comparison occurred — not merely that the turn entered the research
lane. Fixtures are synthetic and domain-independent (house style): the
incident's eight-machine quote shape is rebuilt with abstract labels.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

T8 = ["M-1", "M-2", "M-3", "M-4", "M-5", "M-6", "M-7", "M-8"]
INCIDENT = ("check the other machinery from price list and verify if "
            "any pricing needs to be updated from latest pricing data")


class TestContrastiveDetection:
    def test_incident_shape_is_detected(self):
        from core.target_set_resolution import detect_contrastive_reference

        got = detect_contrastive_reference(INCIDENT)
        assert got is not None and got["marker"] == "other"

    def test_generic_contrastive_family(self):
        from core.target_set_resolution import detect_contrastive_reference

        for text in ("update the rest of the machines",
                     "check the remaining parts",
                     "everything except the M-1",
                     "all rows besides M-2 and M-3"):
            assert detect_contrastive_reference(text) is not None, text

    def test_non_contrastive_shapes_stay_out(self):
        from core.target_set_resolution import detect_contrastive_reference

        for text in ("check those results again",
                     "find M-1 in the workbook",
                     "show me the alpha sheet",
                     "research quantum physics"):
            assert detect_contrastive_reference(text) is None, text


class TestTargetSetResolution:
    def test_incident_with_draft_resolves_to_the_OTHERS(self):
        """The exact incident: draft holds 8 items, the conversation just
        served M-1. 'The other machinery' must investigate the OTHER
        SEVEN — never inherit M-1."""
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            INCIDENT, canvas_items=T8, prior_items=["M-1"],
            last_served_items=["M-1"])
        assert got["kind"] == "resolved", got
        assert got["items"] == T8[1:], got["items"]
        assert got["excluded"] == ["M-1"]

    def test_incident_without_any_list_clarifies(self):
        """A NEW conversation whose only prior item is the one being
        moved past: no 'others' exist to check — ask, never read the
        inherited item."""
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            INCIDENT, prior_items=["M-1"], last_served_items=["M-1"])
        assert got["kind"] == "clarify", got
        assert "Which items" in got["question"]

    def test_conflicting_candidate_bases_clarify(self):
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            "check the other machinery",
            canvas_items=["A-1", "A-2", "A-3"],
            prior_items=["B-1", "B-2", "B-9"])
        assert got["kind"] == "clarify", got
        assert set(got["candidate_sets"]) == {"draft", "prior_objective"}

    def test_superset_base_wins_without_asking(self):
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            "check the other machinery",
            canvas_items=T8, prior_items=T8[:2],
            last_served_items=["M-1"])
        assert got["kind"] == "resolved"
        assert got["origin"] == "canvas"
        assert "M-1" not in got["items"]

    def test_explicit_exclusion_is_honored(self):
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            "check everything in the quote except the M-1",
            canvas_items=T8)
        assert got["kind"] == "resolved"
        assert got["items"] == T8[1:]

    def test_one_item_set_has_no_others_so_clarify(self):
        from core.target_set_resolution import resolve_target_set

        got = resolve_target_set(
            "check the other machinery", canvas_items=["M-1", "M-2"],
            last_served_items=["M-1", "M-2"])
        assert got["kind"] == "clarify", got

    def test_repeated_reference_still_repeats(self):
        """Non-contrastive follow-ups keep the inheritance path — 'check
        those again' is a repeat, and must stay one."""
        from core.target_set_resolution import resolve_target_set

        assert resolve_target_set(
            "check those again", prior_items=T8)["kind"] == "none"


class TestComparisonPlanning:
    def _record(self, m1_value, m2_value=1777):
        def target(item, value, col, basis):
            return {
                "item": item, "aliases": [],
                "identity": {"status": "single", "candidates": [{
                    "ref": f"S!R1", "identity": {},
                    "values": [{"col": col, "basis": basis,
                                "kind": "number", "value": value,
                                "display": f"{value:,}"}]}]},
                "field": {},
            }
        return {
            "requested_items": ["M-1", "M-2"],
            "targets": [target("M-1", m1_value, "E1", "PRICE"),
                        target("M-2", m2_value, "C2", "List Price")],
        }

    def test_comparison_reports_changed_and_unchanged_per_item(self):
        from core.answer_presentation import compare_item_values

        got = compare_item_values(
            self._record(3254), self._record(3400))
        by_item = {i["item"]: i for i in got["items"]}
        assert by_item["M-1"]["outcome"] == "changed"
        assert by_item["M-1"]["baseline"] == "3,254 (PRICE)"
        assert by_item["M-1"]["current"] == "3,400 (PRICE)"
        assert by_item["M-2"]["outcome"] == "unchanged"

    def test_identical_records_are_all_unchanged(self):
        from core.answer_presentation import compare_item_values

        got = compare_item_values(
            self._record(3254), self._record(3254))
        assert all(i["outcome"] == "unchanged" for i in got["items"])

    def test_items_missing_on_a_side_are_stated_not_dropped(self):
        from core.answer_presentation import compare_item_values

        import copy

        base = self._record(3254)
        cur = self._record(3400)
        cur["requested_items"] = ["M-1"]
        cur["targets"] = [copy.deepcopy(base["targets"][0])]
        cur["targets"][0]["identity"]["candidates"][0]["values"][0][
            "value"] = 3400
        cur["targets"][0]["identity"]["candidates"][0]["values"][0][
            "display"] = "3,400"
        got = compare_item_values(base, cur)
        by_item = {i["item"]: i for i in got["items"]}
        assert by_item["M-1"]["outcome"] == "changed"
        assert by_item["M-2"]["outcome"] == "only_in_baseline"


class TestOrchestratorWiring:
    """The ask lane consults the resolver before the read (typed fields
    on the task; unresolved turns clarify instead of reading)."""

    def test_revised_targets_flow_to_the_read_task(self):
        """resolve_target_set's output is consumed as revised_targets —
        the seam the ask lane stamps — verified against the source the
        orchestrator executes."""
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "resolve_target_set" in src
        assert '"revised_targets"] = list(' in src
        # UNRESOLVED TARGET SETS MUST NOT FALL THROUGH TO A READ
        assert "clarifying, NO read ran" in src

    def test_refresh_failure_reframes_as_unable_to_verify(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert '"refresh_failed"' in src
        assert "verify against the latest" in src
        assert "possible. What the saved copy shows follows" in src

    def test_refresh_success_carries_per_item_comparison(self):
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "compare_item_values" in src
        assert "Compared with the earlier saved copy" in src
