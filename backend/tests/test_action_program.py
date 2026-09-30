# -*- coding: utf-8 -*-
"""The typed action program: incident-property tests (2026-09-30).

``core.action_program`` exists to make the scoped-follow-up failure class
IMPOSSIBLE TO EXPRESS SILENTLY. Each test here pins one property from the
2026-09-30 Tennsmith incident chain:

- a named sheet resolves to a real identity or is reported unresolved
  (never guessed);
- filtering/ranking happens BEFORE the display window slices;
- an empty scoped result is stated, never silently broadened;
- evidence passes through immutable (identity cells + value basis);
- displaying a match creates no row binding and no edit authorization;
- "search again" (fresh read) vs "re-use what you showed me" is an
  explicit program mode;
- a compound request compiles to SEPARATE actions with SEPARATE outcomes;
- authorization is COMPUTED from policy facts — the language has no word
  for a self-granted permission, so a proposal carrying one is invalid.

The final class measures what the typed layer is FOR on the incident
corpus: omitted constraints and wrong actions — not JSON validity.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from core import action_program as ap  # noqa: E402
from core.answer_presentation import (  # noqa: E402
    _rank_candidates,
    build_targets_from_scan,
    present,
)
from core.turn_decision import build_turn_decision  # noqa: E402

CATALOG = ["RoperWhitney", "Tennsmith", "LINMAC"]

ASK = ("find the prices of these 8 machines in Consolidated Price List "
       "2019.xlsx")
SESSION = {
    "id": "s-aprog",
    "_superseded_file_task_context": {
        "original_message": ASK,
        "mention": "consolidated price list 2019.xlsx",
        "resolved_file": {
            "file_name": "Consolidated Price List 2019.xlsx",
            "file_id": "wd-77", "content_hash": "ff2597d2",
        },
    },
}


def _cand(sheet: str, row: int, value: float) -> dict:
    return {
        "ref": f"{sheet}!R{row}",
        "values": [{"col": f"B{row}", "basis": "PRICE", "kind": "number",
                    "value": value, "display": f"{value:,.0f}"}],
        "identity": {"references": [{"cell": f"A{row}", "sheet": sheet,
                                      "row": row}],
                     "status": "bound"},
    }


#: The incident shape: five RoperWhitney rows alphabetically ahead of the
#: two Tennsmith rows the reader asked for, window 3.
INCIDENT_CANDIDATES = (
    [_cand("RoperWhitney", r, 100 + r) for r in (100, 101, 102, 103, 104)]
    + [_cand("Tennsmith", 338, 3254), _cand("Tennsmith", 340, 906)]
)


def _filter(item: str = "381", mentions=(), catalog=CATALOG,
            candidates=None, fields=()):
    program = ap.ActionProgram(actions=[
        ap.FilterPreviousOp(
            action_id="f", item=item,
            sheets=[ap.SheetRef(mention=m) for m in mentions])])
    record = ap.execute_program(
        program, sheet_names=catalog,
        candidates={item: list(candidates if candidates is not None
                               else INCIDENT_CANDIDATES)},
        requested_fields=list(fields))
    return record.outcome_for("f"), record


# ---------------------------------------------------------------------------
# Property 1: resolution is real identity or explicit unresolved
# ---------------------------------------------------------------------------

def test_sheet_ref_resolves_real_identity_from_phrase():
    ref = ap.SheetRef(mention="the tennsmith sheet").resolve(CATALOG)
    assert (ref.status, ref.resolved_name) == ("resolved", "Tennsmith")


def test_sheet_ref_resolves_exact_name_without_sheet_word():
    # The render path arrives pre-resolved; an exact name IS the identity.
    ref = ap.SheetRef(mention="Tennsmith").resolve(CATALOG)
    assert (ref.status, ref.resolved_name) == ("resolved", "Tennsmith")


def test_unknown_sheet_is_explicitly_unresolved_never_guessed():
    outcome, _ = _filter(mentions=("the borealis sheet",))
    assert outcome["status"] == ap.STATUS_UNRESOLVED_SHEET
    assert outcome["unresolved_mentions"] == ["the borealis sheet"]
    assert outcome["resolved_sheets"] == []
    # No fabricated name anywhere in the receipt.
    assert "Borealis" not in str(outcome)


def test_short_mention_below_floor_does_not_resolve():
    # A 3-char mention cannot sweep sheets by containment — the same floor
    # the renderer applies.
    assert ap.SheetRef(mention="lin").resolve(CATALOG).status == "unresolved"


# ---------------------------------------------------------------------------
# Property 2: filtering happens BEFORE the display window
# ---------------------------------------------------------------------------

def test_scope_reorders_before_window_so_asked_sheet_leads():
    outcome, _ = _filter(mentions=("the tennsmith sheet",))
    assert outcome["status"] == ap.STATUS_OK
    # The window is sliced from the RANKED list: the two Tennsmith rows
    # lead even though scan order put five RoperWhitney rows first.
    assert outcome["window_refs"] == ["Tennsmith!R338", "Tennsmith!R340",
                                      "RoperWhitney!R100"]
    assert outcome["in_scope_count"] == 2
    assert outcome["candidates_total"] == 7


def test_receipt_counts_in_scope_rows_the_window_hides():
    many = ([_cand("RoperWhitney", r, 1) for r in (1, 2, 3)]
            + [_cand("Tennsmith", r, 2) for r in (10, 11, 12, 13, 14)])
    outcome, _ = _filter(mentions=("the tennsmith sheet",), candidates=many)
    # Five in-scope rows, window 3 → two hidden in-scope rows, named.
    assert outcome["in_scope_rows_hidden_by_window"] == 2
    assert outcome["hidden_in_scope_refs"] == ["Tennsmith!R13",
                                               "Tennsmith!R14"]


# ---------------------------------------------------------------------------
# Property 3: an empty scoped result never silently broadens
# ---------------------------------------------------------------------------

def test_empty_scope_is_stated_not_substituted():
    outcome, _ = _filter(mentions=("the linmac sheet",))
    assert outcome["status"] == ap.STATUS_EMPTY_IN_SCOPE
    # EVERY candidate is preserved — reordered only by answerability, the
    # scope did not become an unrestricted search in disguise.
    assert outcome["candidates_total"] == 7
    assert outcome["in_scope_count"] == 0
    assert "LINMAC" in outcome["scope_note"]
    assert "nothing on the" in outcome["scope_note"]


# ---------------------------------------------------------------------------
# Property 4: evidence is immutable; Property 5: display creates nothing
# ---------------------------------------------------------------------------

def test_execution_never_mutates_input_evidence():
    import copy

    before = copy.deepcopy(INCIDENT_CANDIDATES)
    outcome, record = _filter(mentions=("the tennsmith sheet",))
    assert INCIDENT_CANDIDATES == before
    ranked = record.ranked_by_action["f"]
    # Same rows, same identity cells, same value basis — order changed,
    # content did not.
    assert {c["ref"] for c in ranked} == {c["ref"] for c in before}
    for c in ranked:
        original = next(x for x in before if x["ref"] == c["ref"])
        assert c["identity"] == original["identity"]
        assert [v["basis"] for v in c["values"]] == \
            [v["basis"] for v in original["values"]]
    assert outcome["preserved"] == ["ref", "identity_cells", "value_basis"]


def test_displaying_a_match_creates_no_binding_and_no_edit_grant():
    outcome, _ = _filter(mentions=("the tennsmith sheet",))
    assert outcome["creates_binding"] is False
    assert outcome["authorizes_edit"] is False


# ---------------------------------------------------------------------------
# Property 6: fresh read vs re-serve is explicit; Property 7: compound
# requests are separate actions with separate outcomes
# ---------------------------------------------------------------------------

def test_search_again_compiles_to_fresh_read():
    d = build_turn_decision("try the search again", SESSION, [], {},
                            "s-aprog")
    program = ap.program_from_decision(d)
    read = program.actions[0]
    assert read.op == "workbook_read"
    assert read.mode == ap.MODE_FRESH_READ


def test_decision_reason_maps_to_serve_previous_for_read_verdict():
    decision = {"message": "as you found the latest price",
                "requested_actions": [
                    {"kind": "research", "reason": "continuation_read",
                     "target": {"kind": "task_objective"},
                     "constraints": []}]}
    program = ap.program_from_decision(decision)
    assert program.actions[0].mode == ap.MODE_SERVE_PREVIOUS


def test_compound_request_is_two_actions_two_outcomes():
    d = build_turn_decision(
        "repeat the search and learn to include tennsmith sheet for roper "
        "whitney searches", SESSION, [], {}, "s-aprog")
    program = ap.program_from_decision(d)
    ops = [a.op for a in program.actions]
    assert ops == ["workbook_read", "propose_lesson"]
    record = ap.execute_program(program)
    read_out = record.outcome_for(program.actions[0].action_id)
    lesson_out = record.outcome_for(program.actions[1].action_id)
    # Separate outcomes: the read is a granted proposal; the lesson needs
    # confirmation and NOTHING is saved by proposing it.
    assert read_out["status"] == ap.STATUS_PROPOSED
    assert read_out["authorization"] == ap.AUTH_GRANTED
    assert lesson_out["status"] == ap.STATUS_NEEDS_CONFIRMATION
    assert lesson_out["authorization"] == ap.AUTH_NEEDS_CONFIRMATION
    assert lesson_out["saved"] is False


# ---------------------------------------------------------------------------
# Property 8: authorization is computed, never proposed
# ---------------------------------------------------------------------------

def test_ops_have_no_authorization_field_and_reject_self_grants():
    with pytest.raises(ValidationError):
        ap.FilterPreviousOp(action_id="f", item="381",
                            authorization="granted")
    with pytest.raises(ValidationError):
        ap.parse_program({
            "actions": [{"op": "propose_patch", "action_id": "p1",
                         "target_canvas": "c1", "authorized": True}]})
    with pytest.raises((ValidationError, ValueError)):
        ap.parse_program({"actions": [{"op": "nonexistent_op",
                                       "action_id": "x"}]})


def test_patch_authorization_comes_from_policy_facts_only():
    program = ap.ActionProgram(actions=[
        ap.ProposePatchOp(action_id="p", target_canvas="c1",
                          user_grounded_instruction="rebuild the draft")])
    # The op CARRIES the user's instruction as evidence, but without the
    # policy fact the verdict is still needs_grant.
    without_fact = ap.compute_authorizations(program)
    assert without_fact["p"] == ap.AUTH_NEEDS_GRANT
    record = ap.execute_program(program)
    assert record.outcome_for("p")["status"] == ap.STATUS_NEEDS_GRANT
    # Trusted code supplies the fact → granted → still NOT executed here
    # (the canvas-edit lane owns commit; this layer records not_wired).
    with_fact = ap.compute_authorizations(
        program, {"user_grounded_edit_instruction":
                  "rebuild the draft"})
    assert with_fact["p"] == ap.AUTH_GRANTED
    record2 = ap.execute_program(
        program, candidates={})
    # execution still computes from no facts
    assert record2.outcome_for("p")["authorization"] == ap.AUTH_NEEDS_GRANT


def test_validate_program_flags_structure_and_fabricated_references():
    program = ap.ActionProgram(actions=[
        ap.RenderOp(action_id="r", depends_on=["missing"]),
        ap.FilterPreviousOp(action_id="r", item="381"),
    ])
    report = ap.validate_program(program)
    assert not report["valid"]
    assert any("duplicate action_id" in v for v in report["violations"])
    assert any("unknown dependency" in v for v in report["violations"])
    fabricated = ap.ActionProgram(actions=[
        ap.FilterPreviousOp(action_id="f", sheets=[
            ap.SheetRef(mention="X", resolved_name="NotARealSheet",
                        status="resolved")])])
    report2 = ap.validate_program(fabricated, sheet_catalog=CATALOG)
    assert any("not in catalog" in v for v in report2["violations"])


def test_receipts_stay_lean_ranked_lists_not_serialized():
    _, record = _filter(mentions=("the tennsmith sheet",))
    dumped = record.model_dump()
    assert "ranked_by_action" not in dumped
    assert record.ranked_by_action["f"]


# ---------------------------------------------------------------------------
# Integration: the decision carries the program; the render seam executes it
# ---------------------------------------------------------------------------

def test_decision_persists_typed_program_with_sheet_constraint():
    d = build_turn_decision(
        "show me the tennsmith sheet searches", SESSION, [], {}, "s-aprog")
    program = d["action_program"]
    assert program["schema_version"] == ap.SCHEMA
    read = program["actions"][0]
    assert read["op"] == "workbook_read"
    mentions = [r["mention"] for r in read["include_sheets"]]
    # The constraint the user stated is IN the durable decision row as a
    # typed, pending reference (resolved only against a real catalog).
    assert any("tennsmith" in m.lower() for m in mentions)
    assert all(r["status"] == "pending"
               for r in read["include_sheets"])
    # JSON-serializable: it persists into ChatMessage.metadata_json.
    import json

    json.dumps(program)


def test_render_seam_attaches_receipt_and_matches_direct_ranking():
    ev = []
    for r in (100, 101, 102, 103, 104):
        ev.append({"sheet": "RoperWhitney", "row": r, "values": [
            {"cell": f"B{r}", "price_basis": "PRICE", "value": 100 + r}]})
    for r in (338, 340):
        ev.append({"sheet": "Tennsmith", "row": r, "values": [
            {"cell": f"B{r}", "price_basis": "PRICE",
             "value": 3254 if r == 338 else 906}]})
    outcomes = {"381": {"status": "found", "evidence": ev}}

    targets = build_targets_from_scan(["381"], outcomes, None,
                                      requested_sheets=["Tennsmith"])
    receipt = targets[0]["scope_receipt"]
    assert receipt["status"] == ap.STATUS_OK
    assert receipt["window_refs"] == ["Tennsmith!R338", "Tennsmith!R340",
                                      "RoperWhitney!R100"]
    assert receipt["in_scope_count"] == 2
    # The order is IDENTICAL to the direct primitive — the program is the
    # same ranking, made inspectable, not a second opinion.
    direct = _rank_candidates([_cand("RoperWhitney", r, 1)
                               for r in (100, 101, 102, 103, 104)]
                              + [_cand("Tennsmith", 338, 3254),
                                 _cand("Tennsmith", 340, 906)],
                              None, ["Tennsmith"])
    assert ([c["ref"] for c in direct]
            == [c["ref"] for c in targets[0]["identity"]["candidates"]])
    # present() renders over receipt-carrying targets unchanged.
    answer = present(requested_items=["381"], requested_fields=[],
                     source={"file_name": "Consolidated Price List "
                                          "2019.xlsx"},
                     targets=targets,
                     requested_sheets=["Tennsmith"])
    assert "Tennsmith sheet, row 338" in answer["answer"]


def test_render_seam_scopeless_read_keeps_scan_order_with_no_scope_receipt():
    targets = build_targets_from_scan(
        ["381"], {"381": {"status": "found", "evidence": [
            {"sheet": "RoperWhitney", "row": 100, "values": [
                {"cell": "B100", "price_basis": "PRICE", "value": 1}]},
            {"sheet": "Tennsmith", "row": 338, "values": [
                {"cell": "B338", "price_basis": "PRICE", "value": 2}]}]}},
        None)
    assert targets[0]["scope_receipt"]["status"] == ap.STATUS_NO_SCOPE
    assert [c["ref"] for c in targets[0]["identity"]["candidates"]] == \
        ["RoperWhitney!R100", "Tennsmith!R338"]


def test_render_seam_does_not_mutate_the_scan_outcomes():
    import copy

    outcomes = {"381": {"status": "found", "evidence": [
        {"sheet": "Tennsmith", "row": 338, "values": [
            {"cell": "B338", "price_basis": "PRICE", "value": 3254}]}]}}
    before = copy.deepcopy(outcomes)
    build_targets_from_scan(["381"], outcomes, None,
                            requested_sheets=["Tennsmith"])
    assert outcomes == before


# ---------------------------------------------------------------------------
# Generalization: all data types and all integrations
# ---------------------------------------------------------------------------

def test_source_ask_compiles_to_source_read_not_workbook():
    # A source-target research action ("check the emails/thread") is a
    # SOURCE read — not a workbook read with an empty file name, which is
    # what the pre-generalization compile produced.
    d = build_turn_decision(
        "check chandrakant's emails and or description in the thread to "
        "find the correct sheet", None, [], {}, "s-aprog")
    program = ap.program_from_decision(d)
    ops = [a.op for a in program.actions]
    assert ops == ["source_read"]
    assert sorted(program.actions[0].source_kinds) == ["email", "thread"]


def test_compound_workbook_plus_email_is_two_read_nodes():
    d = build_turn_decision(
        "try again this task, consider chandrakant's email contents",
        SESSION, [], {}, "s-aprog")
    program = ap.program_from_decision(d)
    ops = [a.op for a in program.actions]
    assert ops == ["workbook_read", "source_read"]
    # Separate nodes, separate outcomes — the email half can never be
    # lost to the workbook half again.
    record = ap.execute_program(program)
    outs = {o["op"]: o for o in record.outcomes}
    assert outs["workbook_read"]["executor"] == "read-lane"
    assert outs["source_read"]["executor"] == "integration-lane"
    assert all(o["authorization"] == ap.AUTH_GRANTED
               for o in record.outcomes)


def test_service_ref_resolves_only_against_catalog():
    ok = ap.ServiceRef(mention="outlook").resolve(["gmail", "outlook"])
    assert (ok.status, ok.resolved_name) == ("resolved", "outlook")
    # An integration the user has not connected is reported unresolved —
    # the program can name it, but nothing downstream can claim it ran.
    missing = ap.ServiceRef(mention="notion").resolve(["gmail", "outlook"])
    assert missing.status == "unresolved"
    program = ap.ActionProgram(actions=[
        ap.SourceReadOp(action_id="r", mode="fresh_read",
                        source_kinds=["email"],
                        service=ap.ServiceRef(mention="notion"))])
    outcome = ap.execute_program(
        program, service_catalog=["gmail", "outlook"]).outcome_for("r")
    assert outcome["status"] == ap.STATUS_UNRESOLVED_SERVICE
    assert outcome["service"]["status"] == "unresolved"


def test_validate_flags_fabricated_service():
    program = ap.ActionProgram(actions=[
        ap.SourceReadOp(action_id="r", mode="fresh_read",
                        source_kinds=["email"],
                        service=ap.ServiceRef(
                            mention="x", resolved_name="GhostService",
                            status="resolved"))])
    report = ap.validate_program(program, service_catalog=["gmail"])
    assert not report["valid"]
    assert any("not in service catalog" in v
               for v in report["violations"])


EMAILS = [
    {"subject": "Re: quote", "metadata": {"sender": "chandrakant@x.com"},
     "n_attachments": 2},
    {"subject": "Price list", "metadata": {"sender": "roper@x.com"},
     "n_attachments": 0},
    {"subject": "Tennsmith prices",
     "metadata": {"sender": "chandrakant@x.com"}, "n_attachments": 1},
]


def _filter_evidence(field, operator, value, pool=None):
    program = ap.ActionProgram(actions=[
        ap.FilterEvidenceOp(
            action_id="f",
            source=ap.SourceRef(mention="previous_search", kind="email"),
            field=field, operator=operator, value=value)])
    record = ap.execute_program(
        program, evidence={"previous_search": pool if pool is not None
                           else EMAILS})
    return record.outcome_for("f"), record


def test_filter_evidence_deterministic_over_any_data_type():
    outcome, record = _filter_evidence(
        "metadata.sender", "contains", "chandrakant")
    assert outcome["status"] == ap.STATUS_OK
    assert outcome["matched_count"] == 2
    assert outcome["evidence_total"] == 3
    kept = record.ranked_by_action["f"]
    assert {r["subject"] for r in kept} == {"Re: quote",
                                            "Tennsmith prices"}
    # Numeric and membership predicates work over the same records.
    outcome_gt, rec_gt = _filter_evidence("n_attachments", "gte", 1)
    assert outcome_gt["matched_count"] == 2
    outcome_in, _ = _filter_evidence(
        "subject", "in", ["Price list", "Re: quote"])
    assert outcome_in["matched_count"] == 2


def test_filter_evidence_empty_is_explicit_never_widened():
    outcome, record = _filter_evidence(
        "metadata.sender", "eq", "nobody@x.com")
    assert outcome["status"] == ap.STATUS_EMPTY_RESULT
    assert outcome["matched_count"] == 0
    assert outcome["widened_on_empty"] is False
    # The ranked list stays EMPTY — it does not fall back to the pool.
    assert record.ranked_by_action["f"] == []


def test_filter_evidence_is_immutable_and_side_effect_free():
    import copy
    import json

    pool = copy.deepcopy(EMAILS)
    before = json.dumps(pool, sort_keys=True)
    _filter_evidence("metadata.sender", "contains", "chandrakant",
                     pool=pool)
    assert json.dumps(pool, sort_keys=True) == before


def test_filter_evidence_missing_pool_and_missing_field_are_no_match():
    # A pool the caller does not hold is skipped, honestly.
    outcome, _ = _filter_evidence("subject", "contains", "quote",
                                  pool=[])
    assert outcome["status"] == ap.STATUS_SKIPPED_NO_EVIDENCE
    # A field a record does not carry cannot satisfy the constraint.
    outcome2, record2 = _filter_evidence("priority", "eq", "high")
    assert outcome2["status"] == ap.STATUS_EMPTY_RESULT
    assert outcome2["matched_count"] == 0


def test_unknown_source_kind_rejected_at_parse():
    with pytest.raises((ValidationError, ValueError)):
        ap.SourceReadOp(action_id="x", mode="fresh_read",
                        source_kinds=["telepathy"])
    with pytest.raises((ValidationError, ValueError)):
        ap.SourceRef(mention="x", kind="telepathy")
    assert ap.normalize_source_kind("emails") == "email"
    assert ap.normalize_source_kind("dms") == "chat"
    assert ap.normalize_source_kind("vibes") == ""


def test_patch_target_kinds_expressible_canvas_only_wired():
    # Every artifact kind is EXPRESSIBLE uniformly; only the canvas lane
    # is wired. An email-draft patch records not_wired, never a silent
    # execution path.
    program = ap.ActionProgram(actions=[
        ap.ProposePatchOp(action_id="p1", target_kind="canvas",
                          target_canvas="c1"),
        ap.ProposePatchOp(action_id="p2", target_kind="email_draft")])
    record = ap.execute_program(
        program, policy_facts={"user_grounded_edit_instruction": "go"})
    canvas = record.outcome_for("p1")
    draft = record.outcome_for("p2")
    assert canvas["authorization"] == ap.AUTH_GRANTED
    assert canvas["status"] == ap.STATUS_NOT_WIRED
    assert canvas["executor"] == "canvas-edit-lane"
    assert draft["authorization"] == ap.AUTH_GRANTED
    assert draft["status"] == ap.STATUS_NOT_WIRED
    assert draft["executor"] == "integration-lane"


# ---------------------------------------------------------------------------
# The measurement the typed layer is FOR: omitted constraints and wrong
# actions on the incident corpus — not JSON validity.
# ---------------------------------------------------------------------------

class TestIncidentCorpusOmissionsAndWrongActions:
    """Every turn that states a sheet scope must carry it into the
    program; every turn that does not must not invent one; an edit-shaped
    turn must compile to a patch, not a read."""

    CORPUS_SHEET_SCOPE = [
        "show me the tennsmith sheet searches",
        "repeat the search and learn to include tennsmith sheet for roper "
        "whitney searches",
        "what is the price on the tennsmith tab",
    ]
    CORPUS_NO_SCOPE = [
        "try the search again",
        "find the prices of these 8 machines",
    ]

    def test_no_omitted_sheet_constraints(self):
        omitted = []
        for message in self.CORPUS_SHEET_SCOPE:
            d = build_turn_decision(message, SESSION, [], {}, "s-aprog")
            program = ap.program_from_decision(d)
            read = next((a for a in program.actions
                         if a.op == "workbook_read"), None)
            if read is None or not read.include_sheets:
                omitted.append(message)
        assert not omitted, f"omitted constraints: {omitted}"

    def test_no_invented_sheet_constraints(self):
        invented = []
        for message in self.CORPUS_NO_SCOPE:
            d = build_turn_decision(message, SESSION, [], {}, "s-aprog")
            program = ap.program_from_decision(d)
            for a in program.actions:
                if getattr(a, "include_sheets", None):
                    invented.append(message)
        assert not invented, f"invented constraints: {invented}"

    def test_edit_turn_compiles_to_patch_not_read(self):
        context = {"canvas_id": "c-1"}
        d = build_turn_decision(
            "rebuild the draft now with all eight machines",
            SESSION, [], context, "s-aprog")
        program = ap.program_from_decision(d)
        ops = [a.op for a in program.actions]
        assert "propose_patch" in ops
        assert "workbook_read" not in ops
        # The op CARRIES the user's instruction as evidence, but this
        # layer's verdicts read POLICY FACTS only: without the trusted
        # caller supplying the fact, a patch never reaches granted —
        # even one compiled from a decision whose own verdict was granted.
        record = ap.execute_program(program)
        patch = next(o for o in record.outcomes if o["op"] == "propose_patch")
        assert patch["authorization"] == ap.AUTH_NEEDS_GRANT
        assert patch["status"] == ap.STATUS_NEEDS_GRANT
        # Trusted caller supplies the fact → granted → STILL not executed
        # here (the canvas-edit lane owns commit; this layer records
        # not_wired).
        record2 = ap.execute_program(
            program, policy_facts={"user_grounded_edit_instruction":
                                   "rebuild the draft now"})
        patch2 = next(o for o in record2.outcomes
                      if o["op"] == "propose_patch")
        assert patch2["authorization"] == ap.AUTH_GRANTED
        assert patch2["status"] == ap.STATUS_NOT_WIRED
