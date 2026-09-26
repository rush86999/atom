"""False-positive guards for acceptance runner v4 (work order Step 1).

Each test proves a specific way the gate must fail: non-Boolean checks,
missing/duplicate cases, order-only notes, ambiguous bindings,
uncomparable finalization, historical (not new) actions, and unfiltered
streaming assembly.
"""
import sys, os, json
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.orchestration_acceptance.live_integration_acceptance import (
    REQUIRED_CASE_IDS, diff_attempt_ids, bind_exact, evaluate_all_pass,
    finalize_comparison, validate_checks, exact_ordered_entries, new_actions,
    action_keys)


def test_required_ids_cover_full_matrix():
    assert REQUIRED_CASE_IDS == frozenset({
        "1_initial_request", "1b_historical_distractors",
        "2_formatting_followup", "3_explicit_research", "4_transport_retry",
        "4b_same_text_new_request", "5a_finalized_binding",
        "5b_finalization_transform", "6_streaming_consistency",
        "7_restart_history", "8_overlapping_turns",
        "9_unknown_source_handling", "11_forced_retrieval_failure"})


def _step(sid, *, exercised=True, error=None, checks=None, blocked_on=None):
    return {"step": sid, "required": True, "exercised": exercised,
            "error": error, "checks": checks or {}, "blocked_on": blocked_on,
            "notes": [], "details": {}}


def _full_pass_steps():
    return [_step(sid, checks={"ok": True} if sid != "6_streaming_consistency"
                  else {"streaming_exercised": True})
            for sid in REQUIRED_CASE_IDS]


def test_gate_passes_only_when_complete():
    assert evaluate_all_pass(_full_pass_steps(),
                             boundary_verified=True)["all_pass"]


def test_missing_required_case_fails():
    steps = [s for s in _full_pass_steps() if s["step"] != "9_unknown_source_handling"]
    r = evaluate_all_pass(steps, boundary_verified=True)
    assert not r["all_pass"] and any("9_unknown_source_handling" in f and "missing" in f
                                     for f in r["failures"])


def test_duplicate_case_fails():
    steps = _full_pass_steps() + [_step("1_initial_request", checks={"ok": True})]
    r = evaluate_all_pass(steps, boundary_verified=True)
    assert not r["all_pass"] and any("duplicate" in f for f in r["failures"])


def test_non_boolean_checks_rejected():
    assert validate_checks({"ok": True, "x": False}) == []
    assert validate_checks({"ok": "BLOCKED: reason"}) == ["ok"]
    assert validate_checks({"ok": 1}) == ["ok"]
    steps = [_step(s, checks={"ok": True}) for s in REQUIRED_CASE_IDS
             if s != "1_initial_request"]
    steps.append(_step("1_initial_request",
                       checks={"presentation_action_or_blocked": "BLOCKED: x"}))
    r = evaluate_all_pass(steps, boundary_verified=True)
    assert not r["all_pass"] and any("non-Boolean" in f for f in r["failures"])


def test_blocked_required_step_fails_gate():
    steps = [s if s["step"] != "4_transport_retry" else
             _step("4_transport_retry", exercised=False,
                   blocked_on="work-order Step 3") for s in _full_pass_steps()]
    r = evaluate_all_pass(steps, boundary_verified=True)
    assert not r["all_pass"] and any("BLOCKED" in f for f in r["failures"])


def test_exact_order_asserts_identity_and_order():
    good = ("Results:\n\n- **No. 381** - x\n- **U-22** - y\n")
    order = ["No. 381", "U-22"]
    assert exact_ordered_entries(good, order) is True
    swapped = ("Results:\n\n- **U-22** - y\n- **No. 381** - x\n")
    assert exact_ordered_entries(swapped, order) is False
    arbitrary = ("Results:\n\n- **GSL24-16** - y\n- **SLE16-8** - x\n")
    assert exact_ordered_entries(arbitrary, order) is False
    short = ("Results:\n\n- **No. 381** - x\n")
    assert exact_ordered_entries(short, order) is False


def test_bind_exact_requires_unique_agreement():
    db = [("3", "text", json.dumps({"execution_id": "e1"}))]
    api = [("uuid-1", "text", {"execution_id": "e1"})]
    r = bind_exact(db, api, "e1")
    assert r["ok"] is True and r["content"] == "text"
    assert bind_exact([], api, "e1")["ok"] is False
    dup = db + [("4", "other", json.dumps({"execution_id": "e1"}))]
    assert bind_exact(dup, api, "e1")["ok"] is False
    disagree = [(i, "DIFFERENT", m) for i, _, m in [api[0]]]
    assert bind_exact(db, disagree, "e1")["ok"] is False


def test_finalize_comparison_needs_both_sides():
    assert finalize_comparison("a", "b") == {
        "comparable": True, "changed": True,
        "pre_sha256": finalize_comparison("a", "b")["pre_sha256"],
        "post_sha256": finalize_comparison("a", "b")["post_sha256"]}
    assert finalize_comparison("s", "s")["changed"] is False
    assert finalize_comparison(None, "post")["comparable"] is False
    assert finalize_comparison(None, None)["comparable"] is False


def test_new_actions_detects_only_fresh_ones():
    a1 = {"action": "render", "references_attempt_id": "a",
          "references_evidence_revision": "r", "created_at": 100.0}
    a2 = dict(a1, created_at=200.0)
    assert new_actions([a1], [a1, a2]) == [a2]
    assert new_actions([a1], [a1]) == []
    assert action_keys({}) == (None, None, None, None)


def test_diff_attempt_ids_is_id_based():
    assert diff_attempt_ids({"a", "b"}, {"b", "c"}) == {"c"}
    assert diff_attempt_ids({"a"}, {"a"}) == set()
