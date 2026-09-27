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


# ── Bullet-form reply parsing (acceptance run, 2026-09-26) ─────────────
# The presentation renderer answers in per-target bullets, not a pipe
# table. The evaluator only understood pipe tables, so a CORRECT reply
# scored `missing_row` on every target. These tests pin the adapter AND,
# more importantly, pin that it fails closed: it must never invent a
# price binding that the renderer's text does not contain.

import importlib.util as _ilu
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(
    _os.path.abspath(__file__))))
_spec = _ilu.spec_from_file_location(
    "acc_runner_guards_ri",
    _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))),
        "scripts", "orchestration_acceptance", "run_isolated.py"))
_ri = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_ri)


def _bullets(reply):
    return {r["target"]: r for r in _ri.parse_reply_table(reply)}


def test_bullet_labels_keep_hyphenated_identifiers_intact():
    rows = _bullets(
        "- **U-22** - 1,777 (LINMAC!R26, column C26 'List Price')\n"
        "- **SLE24-16** - 8,880 (Tennsmith!R101, column E101 'PRICE')\n"
        "- **GSL48-16** - 14,166 (Tennsmith!R106, column E106 'PRICE')")
    assert set(rows) == {"U-22", "SLE24-16", "GSL48-16"}


def test_bullet_label_suffix_does_not_eat_the_body():
    rows = _bullets(
        "- **TK Multi Wheel Gang Slitter** (matched via 'Gang Slitter') - "
        "14,166 (Tennsmith!R106, column E106 'PRICE')")
    row = rows["TK Multi Wheel Gang Slitter"]
    assert _ri.classify(row["status"]) == "found"
    assert "E106=14,166" in row["evidence"]


def test_bullet_lead_value_binds_to_the_first_cited_pair():
    rows = _bullets("- **U-22** - 1,777 (LINMAC!R26, column C26 'List Price')")
    assert "C26=1,777" in rows["U-22"]["evidence"]


def test_bullet_lead_value_never_overrides_a_stated_pair_value():
    """The stated price and the cited price must not be conflated."""
    rows = _bullets(
        "- **GSL48-16** - 14,166 (Tennsmith!R106, column E106 'PRICE' 14,166)")
    evidence = rows["GSL48-16"]["evidence"]
    assert evidence.count("14,166") >= 1
    assert "E106=99" not in evidence


def test_ambiguous_bullets_classify_ambiguous_not_found():
    rows = _bullets(
        "- **No. 381** - several rows match (RoperWhitney!R88 (PRICE blank)); "
        "which one is yours needs your confirmation")
    assert _ri.classify(rows["No. 381"]["status"]) == "ambiguous"


def test_absent_bullets_classify_absent():
    rows = _bullets(
        "- **SLE24-16** - NOT FOUND IN INDEXED CONTENT (all 46 sheets probed)")
    assert _ri.classify(rows["SLE24-16"]["status"]) == "absent_from_indexed"


def test_adapter_invents_no_binding_when_there_is_no_citation():
    """FAIL CLOSED: a bullet with prose and no Sheet!Cell citation must
    yield no evidence, so no price can verify against it."""
    rows = _bullets(
        "- **No. 381** - several rows match; which one is yours needs your "
        "confirmation")
    assert rows["No. 381"]["evidence"] == ""
    # No citation means no pairs, so no price can verify against it.
    assert all(not seg["pairs"] for seg in _ri.parse_segments(
        rows["No. 381"]["evidence"]))


def test_adapter_preserves_the_renderer_wording_verbatim():
    body = ("1,777 (LINMAC!R26, column C26 'List Price'; also M26 "
            "'List Price_2' 1,777)")
    rows = _bullets(f"- **U-22** - {body}")
    assert rows["U-22"]["evidence_raw"] == body


def test_pipe_tables_still_take_priority_and_are_unchanged():
    reply = ("| item | status | evidence |\n"
             "| --- | --- | --- |\n"
             "| U-22 | FOUND | LINMAC!R26 ; C26=1777 [basis=List Price] |")
    rows = _ri.parse_reply_table(reply)
    assert len(rows) == 1
    assert rows[0]["target"] == "U-22"
    assert _ri.classify(rows[0]["status"]) == "found"


def test_prose_lines_are_not_mistaken_for_target_rows():
    rows = _bullets(
        "Source: Consolidated Price List 2019.xlsx - saved copy.\n"
        "Coverage: indexed sheets=46; scanned entries=46.")
    assert rows == {}


# ── Evaluator v3: artifact-native identity/value bindings ────────────────
# The evaluator must validate IDENTITY and VALUE as separate bindings, and
# must fail closed on each. These are the negative controls the plan
# requires: wrong identity cell, wrong value cell, wrong basis/value, the
# same suffix in another column, and missing evidence.

def _artifact(targets):
    return {"schema_version": "structured-result-2", "targets": targets}


def _cand(ref, identity_status, refs, values):
    return {"item": "U-22",
            "identity": {"status": identity_status,
                         "references": refs,
                         "candidates": [{"ref": ref, "values": values,
                                         "identity": {"status": identity_status,
                                                      "references": refs}}]},
            "field": {"status": "single", "values": values}}


def _expect(**kw):
    base = {"coverage": "found", "price": 1777.0, "cell": "linmac!A26",
            "value_col": "C", "basis": "List Price"}
    base.update(kw)
    return base


def _eval(artifact, expected=None):
    return _ri.evaluate_artifact_bindings(
        artifact, expected or {"U-22": _expect()})


def test_identity_and_value_bind_independently_pass():
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "A26", "row": 26, "value": "U-22",
          "role": "matched_target"}],
        [{"col": "C26", "basis": "List Price", "value": 1777.0,
          "display": "1,777"}])])
    r = _eval(art)["U-22"]
    assert r["identity_ok"] is True
    assert r["value_ok"] is True


def test_wrong_identity_cell_fails_even_with_a_right_price():
    """The price can be perfect and the identity still unproven."""
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "B26", "row": 26, "value": "U-22",
          "role": "matched_target"}],
        [{"col": "C26", "basis": "List Price", "value": 1777.0}])])
    r = _eval(art)["U-22"]
    assert r["identity_ok"] is False
    assert r["value_ok"] is True


def test_row_locator_is_not_an_identity_cell():
    art = _artifact([_cand("LINMAC!R26", "unverified", [],
                           [{"col": "C26", "basis": "List Price",
                             "value": 1777.0}])])
    r = _eval(art)["U-22"]
    assert r["identity_ok"] is False
    assert "unverified" in r["identity_detail"]


def test_same_suffix_in_another_column_is_rejected():
    """AA26 must never satisfy an A26 identity expectation."""
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "AA26", "row": 26, "value": "U-22",
          "role": "matched_target"}],
        [{"col": "C26", "basis": "List Price", "value": 1777.0}])])
    r = _eval(art)["U-22"]
    assert r["identity_ok"] is False
    assert "suffix-only matches rejected" in r["identity_detail"]


def test_wrong_value_cell_fails():
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "A26", "row": 26, "role": "matched_target"}],
        [{"col": "M26", "basis": "List Price", "value": 1777.0}])])
    r = _eval(art)["U-22"]
    assert r["identity_ok"] is True
    assert r["value_ok"] is False


def test_wrong_value_fails():
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "A26", "row": 26, "role": "matched_target"}],
        [{"col": "C26", "basis": "List Price", "value": 999.0}])])
    assert _eval(art)["U-22"]["value_ok"] is False


def test_wrong_basis_fails():
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "A26", "row": 26, "role": "matched_target"}],
        [{"col": "C26", "basis": "Factory Price", "value": 1777.0}])])
    assert _eval(art)["U-22"]["value_ok"] is False


def test_missing_artifact_evidence_fails_closed():
    r = _eval(None)["U-22"]
    assert r["identity_ok"] is False
    assert r["value_ok"] is False
    assert "absent from artifact" in r["identity_detail"]


def test_requested_item_absent_from_artifact_fails_closed():
    art = _artifact([_cand("S!R1", "single",
                           [{"sheet": "S", "cell": "A1", "row": 1}],
                           [{"col": "C1", "basis": "P", "value": 1.0}])])
    r = _ri.evaluate_artifact_bindings(
        art, {"SOMETHING ELSE": _expect()})["SOMETHING ELSE"]
    assert r["identity_ok"] is False
    assert "absent from artifact" in r["identity_detail"]


def test_identity_never_substitutes_for_a_missing_price():
    """A bound identity with no value binding must not read as found."""
    art = _artifact([_cand(
        "LINMAC!R26", "single",
        [{"sheet": "LINMAC", "cell": "A26", "row": 26, "role": "matched_target"}],
        [])])
    r = _eval(art)["U-22"]
    assert r["identity_ok"] is True
    assert r["value_ok"] is False


def test_ambiguous_expectation_requires_multiple_identity_candidates():
    art = _artifact([_cand(
        "S!R88", "single",
        [{"sheet": "S", "cell": "A88", "row": 88, "role": "matched_target"}],
        [])])
    r = _ri.evaluate_artifact_bindings(
        art, {"U-22": _expect(coverage="ambiguous", price=None,
                              cell=None, value_col=None, basis=None)}
    )["U-22"]
    assert r["identity_ok"] is False, "single identity cannot satisfy ambiguous"


def test_frozen_expectations_are_not_rewritten_by_the_evaluator():
    """The evaluator reads the frozen expectation; it must never mutate it."""
    exp = {"U-22": _expect()}
    before = repr(exp)
    _ri.evaluate_artifact_bindings(
        _artifact([_cand("LINMAC!R26", "single", [], [])]), exp)
    assert repr(exp) == before


# ── Absence decided from structured coverage, never from wording ──────────

def _abs_artifact(targets, complete):
    return {"schema_version": "structured-result-2",
            "coverage": {"complete": complete},
            "coverage_limits": {"indexed_sheets": 46},
            "targets": targets}


def _abs_expect():
    return {"coverage": "absent_from_indexed"}


def _none_target(item):
    return {"item": item, "identity": {"status": "none", "candidates": []},
            "field": {"status": "absent", "values": []}}


def test_complete_search_zero_matches_supports_absent():
    art = _abs_artifact([_none_target("U-38")], True)
    r = _ri.evaluate_absence_from_artifact(art, {"U-38": _abs_expect()})["U-38"]
    assert r["verdict"] == "absent_from_indexed"


def test_incomplete_coverage_cannot_claim_absence():
    art = _abs_artifact([_none_target("U-38")], False)
    r = _ri.evaluate_absence_from_artifact(art, {"U-38": _abs_expect()})["U-38"]
    assert r["verdict"] == "unknown"
    assert "coverage incomplete" in r["reason"]


def test_missing_artifact_is_unknown_not_absent():
    r = _ri.evaluate_absence_from_artifact(None, {"U-38": _abs_expect()})["U-38"]
    assert r["verdict"] == "unknown"


def test_absent_target_missing_from_artifact_is_unknown():
    art = _abs_artifact([], True)
    r = _ri.evaluate_absence_from_artifact(art, {"U-38": _abs_expect()})["U-38"]
    assert r["verdict"] == "unknown"
    assert "cannot distinguish" in r["reason"]


def test_artifact_with_value_evidence_is_not_absent():
    entry = {"item": "U-38",
             "identity": {"status": "single",
                          "candidates": [{"ref": "S!R1",
                                          "values": [{"col": "C1",
                                                      "basis": "P",
                                                      "value": 1.0}]}]},
             "field": {"status": "single", "values": []}}
    art = _abs_artifact([entry], True)
    r = _ri.evaluate_absence_from_artifact(art, {"U-38": _abs_expect()})["U-38"]
    assert r["verdict"] == "not_absent"


def test_non_absent_expectations_are_not_evaluated_as_absence():
    art = _abs_artifact([_none_target("U-22")], True)
    assert _ri.evaluate_absence_from_artifact(
        art, {"U-22": {"coverage": "found"}}) == {}


# ── C13: per-subturn artifact binding, and no recency substitution ───────

def test_load_artifact_selects_by_exact_execution_not_recency(tmp_path):
    """Selecting the LATEST row in a session substitutes one turn's
    identity for another's — the exact sin an overlapping-reads case
    exists to detect. Two turns, two artifacts, selected by execution id.
    """
    import sqlite3 as _sq

    world = tmp_path / "world"
    (world / "runs" / "run-1" / "data").mkdir(parents=True)
    db = world / "runs" / "run-1" / "data" / "atom.db"
    con = _sq.connect(str(db))
    con.execute(
        "CREATE TABLE chat_messages (conversation_id TEXT, role TEXT, "
        "created_at TEXT, metadata_json TEXT)")
    con.execute(
        "INSERT INTO chat_messages VALUES (?,?,?,?)",
        ("s1", "assistant", "2026-01-01T00:00:00",
         '{"execution_id": "ex-A", "structured_result": '
         '{"schema_version": "structured-result-2", "targets": ['
         '{"item": "U-22", "identity": {"status": "single", "candidates": ['
         '{"ref": "S!R1", "values": [{"col": "C1", "basis": "P", '
         '"value": 1.0}], "identity": {"status": "bound", "references": '
         '[{"sheet": "S", "cell": "A1", "row": 1}]}}]}}]}}'))
    con.execute(
        "INSERT INTO chat_messages VALUES (?,?,?,?)",
        ("s1", "assistant", "2026-01-01T00:00:01",
         '{"execution_id": "ex-B", "structured_result": '
         '{"schema_version": "structured-result-2", "targets": ['
         '{"item": "SLE24-16", "identity": {"status": "single", '
         '"candidates": [{"ref": "S!R2", "values": [{"col": "C2", '
         '"basis": "P", "value": 2.0}], "identity": {"status": "bound", '
         '"references": [{"sheet": "S", "cell": "A2", "row": 2}]}}]}}]}}'))
    con.commit()
    con.close()

    a = _ri.load_structured_result(world, "s1", execution_id="ex-A")
    b = _ri.load_structured_result(world, "s1", execution_id="ex-B")
    assert [t["item"] for t in a["targets"]] == ["U-22"]
    assert [t["item"] for t in b["targets"]] == ["SLE24-16"]
    # Recency is NOT the selector when an execution is named.
    assert a is not b


def test_load_artifact_falls_back_to_latest_when_no_execution_given(tmp_path):
    import sqlite3 as _sq

    world = tmp_path / "world2"
    (world / "runs" / "run-1" / "data").mkdir(parents=True)
    db = world / "runs" / "run-1" / "data" / "atom.db"
    con = _sq.connect(str(db))
    con.execute(
        "CREATE TABLE chat_messages (conversation_id TEXT, role TEXT, "
        "created_at TEXT, metadata_json TEXT)")
    con.execute(
        "INSERT INTO chat_messages VALUES (?,?,?,?)",
        ("s2", "assistant", "2026-01-01T00:00:00",
         '{"execution_id": "ex-1", "structured_result": '
         '{"schema_version": "structured-result-2", "targets": []}}'))
    con.commit()
    con.close()
    got = _ri.load_structured_result(world, "s2")
    assert got["schema_version"] == "structured-result-2"


def test_one_subturn_with_incorrect_evidence_fails_that_subturn():
    """Distinct execution ids are not overlap correctness. If ONE subturn's
    artifact carries the wrong identity cell, that subturn must fail even
    though the other is perfect and the ids differ."""
    good = _artifact([_cand(
        "S!R1", "single",
        [{"sheet": "S", "cell": "A1", "row": 1, "role": "matched_target"}],
        [{"col": "C1", "basis": "P", "value": 1.0}])])
    bad = _artifact([_cand(
        "S!R1", "single",
        [{"sheet": "S", "cell": "Z9", "row": 9, "role": "matched_target"}],
        [{"col": "C1", "basis": "P", "value": 1.0}])])
    exp = {"U-22": {"coverage": "found", "price": 1.0, "cell": "s!A1",
                    "value_col": "C", "basis": "P"}}
    good_r = _ri.evaluate_artifact_bindings(good, exp)["U-22"]
    bad_r = _ri.evaluate_artifact_bindings(bad, exp)["U-22"]
    assert good_r["identity_ok"] is True and good_r["value_ok"] is True
    assert bad_r["identity_ok"] is False, (
        "a subturn with the wrong identity cell must fail even when the "
        "sibling subturn is correct and the execution ids differ")
    assert bad_r["value_ok"] is True
