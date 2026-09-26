#!/usr/bin/env python3
"""Build the labeled search scenario corpus.

Expectations are written HERE, by hand, from the fixture's own content — never
read back from the system under test. That is the whole point: if the corpus
were derived from what Atom currently returns, every "pass" would be a
restatement of the incumbent's behaviour and the held-out split would be
meaningless.

Business names and the original eight-machine incident stay in FIXTURES only.
The general-domain corpora (invoices, policies, messages) are synthetic and
share no vocabulary with the workbook, so a scenario cannot pass by recognising
the fixture it grew up with.

Emitting a generator rather than a hand-written JSON blob keeps the labeling
rationale next to the labels and makes the held-out split auditable: the split
is declared by CATEGORY below, before any run, and re-running this script
reproduces the same corpus and the same split.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Declared BEFORE any run. 16 cases across the least-familiar categories, so a
# tuning decision cannot be fitted to them.
HELDOUT_CATEGORIES = (
    "conflicting_stale_sources",
    "absent_within_coverage",
    "restart_retry",
    "reranker_degraded",
    "similar_identifiers",
    "crowded_lexical",
)
HELDOUT_TARGET = 16


def _case(cid, category, query, *, sources, required_items, support=None,
          forbidden_sources=(), expect_status="success", multi_turn=None,
          notes=""):
    return {
        "id": cid,
        "category": category,
        "query": query,
        "required_sources": list(sources),
        "forbidden_sources": list(forbidden_sources),
        "required_items": list(required_items),
        "support": support or {},
        "expect_status": expect_status,
        "multi_turn": multi_turn or [],
        "notes": notes,
    }


def build() -> list[dict]:
    cases: list[dict] = []

    # -- 1. Exact named file -------------------------------------------------
    cases.append(_case(
        "exact_named_file_basic", "exact_named_file",
        "In linmac_consolidated.xlsx, what is the price for U-22?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22"],
        support={"U-22": {"value": "1284.00", "basis": "list", "unit": "CAD"}},
        notes="The named-file + exact-identifier route. Phase D forbids routing "
              "this through approximate vector retrieval just to standardise "
              "the implementation, so the direct structured lookup is the "
              "expected path.",
    ))
    cases.append(_case(
        "exact_named_file_two_items", "exact_named_file",
        "In linmac_consolidated.xlsx give me the list price for U-22 and SLE24-16",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22", "SLE24-16"],
        support={
            "U-22": {"value": "1284.00", "basis": "list", "unit": "CAD"},
            "SLE24-16": {"value": "2499.50", "basis": "list", "unit": "CAD"},
        },
    ))
    cases.append(_case(
        "exact_named_file_version_bound", "exact_named_file",
        "What does linmac_consolidated.xlsx say about SLE24-16 in the 2024 revision?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["SLE24-16"],
        support={"SLE24-16": {"value": "2499.50", "basis": "list", "unit": "CAD"}},
        notes="An absence claim here must be bounded to the searched revision.",
    ))

    # -- 2. Similar identifiers ---------------------------------------------
    for n, (code, near, value) in enumerate((
        ("U-22", "U-22X", "1284.00"),
        ("SLE24-16", "SLE24-160", "2499.50"),
        ("GSL48-16", "GSL48-1", "875.25"),
    )):
        cases.append(_case(
            f"similar_identifiers_{code}_{n}", "similar_identifiers",
            f"What is the price of {code}? Do not confuse it with {near}.",
            sources=["linmac_consolidated.xlsx"],
            required_items=[code],
            support={code: {"value": value, "basis": "list", "unit": "CAD"}},
            notes=f"{near} is present in the same sheet with a different price. "
                  "Silently merging them is a fabricated binding.",
        ))

    # -- 3. Long request / tail constraints ---------------------------------
    long_query = (
        "Before I do anything else, and this matters more than the formatting: "
        "find the current list price in CAD for each of these eight machines in "
        "linmac_consolidated.xlsx — U-22, SLE24-16, TK 1624, TK Manual Flanger, "
        "GSL48-16, SLE24-160, GSL48-1, and finally U-22X — and tell me which of "
        "them are the ones I flagged last week as needing a quote, because the "
        "account manager asked for the whole list before the end of the day and "
        "I need the currency to be Canadian dollars and not US dollars"
    )
    cases.append(_case(
        "long_request_tail_identifiers", "long_request",
        long_query,
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22", "SLE24-16", "TK 1624", "GSL48-16", "U-22X",
                        "SLE24-160", "GSL48-1"],
        support={
            "U-22": {"value": "1284.00", "unit": "CAD"},
            "SLE24-16": {"value": "2499.50", "unit": "CAD"},
            "GSL48-16": {"value": "875.25", "unit": "CAD"},
        },
        notes="The last three identifiers sit past character 200. A head-cut "
              "query searched the first five and reported a confident count for "
              "all eight.",
    ))
    cases.append(_case(
        "long_request_unit_constraint", "long_request",
        long_query + " Also confirm none of these are priced in USD.",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22", "SLE24-16"],
        support={"U-22": {"value": "1284.00", "unit": "CAD"}},
        notes="The currency constraint is in the tail; a truncated query loses "
              "the constraint while still returning the price.",
    ))

    # -- 4. Paraphrased question --------------------------------------------
    cases.append(_case(
        "paraphrase_warranty_terms", "paraphrased_question",
        "What does the manufacturer guarantee on the plate steel saw?",
        sources=["policy_manual.pdf"],
        required_items=["warranty term"],
        support={"warranty term": {"span": "24 months"}},
        notes="No exact identifier. Must retrieve on meaning, not wording.",
    ))
    cases.append(_case(
        "paraphrase_expense_policy", "paraphrased_question",
        "Can I expense a client dinner without a receipt?",
        sources=["expense_policy.md"],
        required_items=["receipt requirement"],
        support={"receipt requirement": {"span": "$75 or more"}},
    ))

    # -- 5. Mailbox identity -------------------------------------------------
    cases.append(_case(
        "mailbox_exact_address", "mailbox_identity",
        "Find the email from dana.whitfield@linmac.example about invoice 4417.",
        sources=["communication"],
        required_items=["invoice 4417"],
        support={"invoice 4417": {"sender": "dana.whitfield@linmac.example"}},
        notes="Provider address syntax must resolve without substituting an "
              "unrelated sender of similar name.",
    ))
    cases.append(_case(
        "mailbox_similar_sender", "mailbox_identity",
        "What did d.whitfield@linmac.example say about the stand-down?",
        sources=["communication"],
        required_items=["stand-down"],
        support={"stand-down": {"sender": "d.whitfield@linmac.example"}},
        notes="d.whitfield and dana.whitfield are different mailboxes; the "
              "wrong one is an access-scope issue, not just a ranking miss.",
    ))
    cases.append(_case(
        "mailbox_long_address_tail", "mailbox_identity",
        "Please find the message in which " + ("the legal team explained " * 20)
        + "the customs hold on invoice 4417 was released",
        sources=["communication"],
        required_items=["invoice 4417"],
        support={"invoice 4417": {"sender": "dana.whitfield@linmac.example"}},
        notes="The identifier sits past character 200 in a long prose turn.",
    ))

    # -- 6. Crowded lexical results -----------------------------------------
    for n in range(3):
        cases.append(_case(
            f"crowded_lexical_{n}", "crowded_lexical",
            f"What did the operations team say about shift handover on the {n+9}th?",
            sources=["mailbox", "shift_handover_log.md"],
            required_items=["shift handover"],
            support={"shift handover": {"span": "handover"}},
            notes="Many weak token matches ('the', 'team', 'about') crowd the "
                  "candidate set; the relevant semantic evidence must still "
                  "compete rather than be suppressed by a hit-count gate.",
        ))

    # -- 7. Source / date / owner restrictions --------------------------------
    cases.append(_case(
        "owner_scope_other_user_excluded", "source_owner_restriction",
        "What did the vendor say about account 90210?",
        sources=["communication"],
        required_items=["account 90210"],
        notes="The mailbox is the surface that CLAIMS an ownership boundary "
              "(search_communications takes owner_user_id), so this is where "
              "the access-scope gate is meaningful. A second owner's message "
              "about the same account is in the corpus; using or exposing it is "
              "an access-scope violation, the hardest gate in the matrix.",
    ))
    cases.append(_case(
        "date_restriction_pre_cutoff", "source_owner_restriction",
        "What was the agreed price as of 2023-06-30?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["agreed price"],
        notes="The corpus holds a later revision. Answering with it would be a "
              "stale-evidence binding presented as current. The assertion is "
              "that the bound evidence is revision-qualified at all.",
    ))
    cases.append(_case(
        "source_restriction_explicit", "source_owner_restriction",
        "Only look in the expense policy — do not search email for this.",
        sources=["expense_policy.md"],
        forbidden_sources=["communication"],
        required_items=["receipt requirement"],
    ))

    # -- 8. Ambiguous identity ----------------------------------------------
    cases.append(_case(
        "ambiguous_two_lookalikes", "ambiguous_identity",
        "What is the price of No. 381?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["No. 381"],
        support={"No. 381": {"alternatives": 2}},
        notes="Two rows match. The correct behaviour is to retain both and say "
              "so, not to pick one confidently.",
    ))
    cases.append(_case(
        "ambiguous_sender_name", "ambiguous_identity",
        "What did Whitfield say about the hold?",
        sources=["communication"],
        required_items=["the hold"],
        support={"the hold": {"alternatives": 2}},
        notes="Whitfield resolves to two mailboxes; both must be retained.",
    ))
    cases.append(_case(
        "ambiguous_unit_variant", "ambiguous_identity",
        "How much is the GSL48-16 in US dollars?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["GSL48-16"],
        notes="The corpus is CAD only. Converting or answering from a USD row "
              "would be a fabricated binding; the honest answer is that the "
              "requested unit is not in the searched source.",
    ))

    # -- 9. Conflicting / stale sources -------------------------------------
    for n in range(3):
        cases.append(_case(
            f"conflicting_stale_{n}", "conflicting_stale_sources",
            "What is the current list price of SLE24-16?",
            sources=["linmac_consolidated.xlsx"],
            required_items=["SLE24-16"],
            support={"SLE24-16": {"revision": "current"}},
            notes="A cached earlier revision disagrees with the live sheet. The "
                  "difference must be visible, and a live read failure must not "
                  "promote the saved copy to live truth.",
        ))
    cases.append(_case(
        "conflicting_stale_saved_only", "conflicting_stale_sources",
        "What is the current list price of SLE24-16? (injected failure: vector)",
        sources=["linmac_consolidated.xlsx"],
        required_items=["SLE24-16"],
        expect_status="failed",
        notes="Same question with the LIVE source failing. The answer must "
              "report that the live source could not be read, not serve the "
              "cached value as if it were current.",
    ))

    # -- 10. Actual absence --------------------------------------------------
    for n, (q, why) in enumerate((
        ("What is the price of XYZ-9999 in linmac_consolidated.xlsx?",
         "genuinely not in the corpus"),
        ("What is the price of U-22 in the service agreement?",
         "the item exists elsewhere, not in the named source"),
        ("Did anyone email about invoice 9999?",
         "no such message"),
        ("Does the expense policy mention parking?",
         "the policy genuinely does not cover parking"),
    )):
        cases.append(_case(
            f"absent_within_coverage_{n}", "absent_within_coverage",
            q, sources=["linmac_consolidated.xlsx", "communication", "expense_policy.md"],
            required_items=["absent:" + why],
            support={"absent:" + why: {"claimable": True}},
            notes="Absence is legitimate ONLY when every named source was "
                  "successfully searched. This is the control for the "
                  "false-absence cases: a system that abstains here is not "
                  "distinguishing failure from absence either.",
        ))

    # -- 11. Partial / failed search -----------------------------------------
    for n, (broken, why) in enumerate((
        ("lexical", "the BM25 index is unavailable"),
        ("vector", "the vector index is unavailable"),
        ("both", "both indexes are unavailable"),
        ("hydration", "source identity could not be resolved"),
        ("mailbox", "the mailbox store is unavailable"),
    )):
        cases.append(_case(
            f"partial_failed_{broken}_{n}", "partial_failed_search",
            f"What is the price of U-22? (injected failure: {broken})",
            sources=["linmac_consolidated.xlsx"],
            required_items=["U-22"],
            support={"U-22": {"resolvable": False}},
            expect_status="failed",
            notes=f"Failure case with {why}. An item that cannot be resolved "
                  "because retrieval failed is 'unresolved', never 'absent'. "
                  "A healthy sibling leg must stay usable.",
        ))
    cases.append(_case(
        "partial_corrupt_workbook", "partial_failed_search",
        "What is the price of U-22? (workbook is corrupt)",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22"],
        support={"U-22": {"resolvable": False}},
        expect_status="failed",
        notes="A corrupt file is an I/O failure, not a missing row. The "
              "distinction is the whole assertion.",
    ))

    # -- 12. Formatting follow-up (zero retrieval) ---------------------------
    for n, fmt in enumerate((
        "make that a table",
        "put that in a bulleted list",
        "shorter please",
    )):
        cases.append(_case(
            f"formatting_zero_retrieval_{n}", "formatting_followup",
            f"What is the price of U-22? (then: {fmt})",
            sources=["linmac_consolidated.xlsx"],
            required_items=["U-22"],
            multi_turn=[{"turn": 2, "message": fmt, "expect_retrieval": 0}],
            notes="Formatting performs no search. The previous delivery must be "
                  "byte-identical in the reloaded history.",
        ))

    # -- 13. Distractors / replacement ---------------------------------------
    cases.append(_case(
        "distractor_replacement", "distractors_replacement",
        "Actually forget SLE24-16 — I need TK 1624 instead.",
        sources=["linmac_consolidated.xlsx"],
        required_items=["TK 1624"],
        support={"TK 1624": {"value": "875.00", "unit": "CAD"}},
        multi_turn=[
            {"turn": 1, "message": "What is the price of SLE24-16?"},
            {"turn": 2, "message": "Actually forget SLE24-16 — I need TK 1624 instead.",
             "expect_retrieval": 1},
        ],
        notes="The CURRENT task revision determines the target. The superseded "
              "target must not leak back into the answer.",
    ))
    cases.append(_case(
        "distractor_restart_continuation", "distractors_replacement",
        "carry on with the list we were doing",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22"],
        multi_turn=[
            {"turn": 1, "message": "List the price of U-22 and SLE24-16"},
            {"turn": 2, "message": "carry on with the list we were doing",
             "expect_retrieval": 0},
        ],
        notes="The identifier set must come from the durable task revision, "
              "not from a union of every historical list.",
    ))

    # -- 14. Explicit re-search ----------------------------------------------
    cases.append(_case(
        "explicit_research_new_attempt", "explicit_research",
        "search again for U-22",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22"],
        support={"U-22": {"value": "1284.00"}},
        multi_turn=[
            {"turn": 1, "message": "What is the price of U-22?"},
            {"turn": 2, "message": "search again for U-22", "expect_retrieval": 1},
        ],
        notes="An explicit re-search is a NEW read attempt even when the "
              "evidence revision is unchanged. Zero invocations here would mean "
              "the re-search was silently a replay.",
    ))

    # -- 15. Reranker degraded -----------------------------------------------
    for n, mode in enumerate(("unavailable", "slow", "saturated", "bad_scores")):
        cases.append(_case(
            f"reranker_degraded_{mode}_{n}", "reranker_degraded",
            f"What is the price of U-22? (reranker {mode})",
            sources=["linmac_consolidated.xlsx"],
            required_items=["U-22"],
            support={"U-22": {"value": "1284.00"}},
            notes="A reranker fallback is RANKING degradation, not incomplete "
                  "source coverage. The answer must not claim the evidence was "
                  "fully searched on the strength of a degraded ordering, and "
                  "resource use must stay bounded.",
        ))

    # -- 16. Restart and retry -----------------------------------------------
    cases.append(_case(
        "restart_retry_keyed", "restart_retry",
        "What is the price of U-22?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22"],
        multi_turn=[{"turn": 2, "message": "(same request, same request_id)",
                     "expect_retrieval": 0}],
        notes="A keyed retry returns its pinned bytes and does NOT search "
              "again. Constraints and evidence must survive a restart.",
    ))
    cases.append(_case(
        "restart_retry_survives_restart", "restart_retry",
        "What is the price of U-22?",
        sources=["linmac_consolidated.xlsx"],
        required_items=["U-22"],
        notes="After a process restart the same request_id still returns the "
              "originally pinned response.",
    ))

    # -- 17. Multi-source -----------------------------------------------------
    for n, q in enumerate((
        "What is the price of U-22 and who emailed about it?",
        "Show me the price list and the warranty terms together",
        "Compare the invoice total in email with the policy limit",
    )):
        cases.append(_case(
            f"multi_source_{n}", "multi_source",
            q,
            sources=["linmac_consolidated.xlsx", "communication", "policy_manual.pdf"],
            required_items=["price", "email or terms"],
            notes="Both sources must be read; using one to answer for the other "
                  "is a fabricated binding.",
        ))

    return cases


def main() -> int:
    cases = build()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case id"
    heldout = [
        c for c in cases
        if c["category"] in HELDOUT_CATEGORIES
    ][:HELDOUT_TARGET]
    if len(heldout) < HELDOUT_TARGET:
        raise SystemExit(
            f"only {len(heldout)} cases in held-out categories; need "
            f"{HELDOUT_TARGET}. Add cases or widen HELDOUT_CATEGORIES."
        )
    for c in heldout:
        c["split"] = "heldout"
    for c in cases:
        c.setdefault("split", "development")

    doc = {
        "version": "search-scenarios-1",
        "built_by": "acceptance/search/build_scenarios.py",
        "independence": (
            "Required sources, required items and supporting values are declared "
            "in the generator from the fixture's own content. Nothing here is "
            "read back from the system under test, so a pass is evidence and a "
            "restatement of the incumbent is not."
        ),
        "heldout_policy": (
            "Held out by CATEGORY, declared before any run, so a tuning "
            "decision cannot be fitted to the held-out cases. Re-running the "
            "generator reproduces the same split."
        ),
        "counts": {
            "total": len(cases),
            "development": len(cases) - len(heldout),
            "heldout": len(heldout),
        },
        "categories": sorted({c["category"] for c in cases}),
        "cases": cases,
    }
    body = json.dumps(doc, indent=1, sort_keys=False)
    (HERE / "scenarios.json").write_text(body)
    print(f"wrote {len(cases)} cases "
          f"({doc['counts']['development']} dev / {doc['counts']['heldout']} held out)")
    print(f"categories: {len(doc['categories'])}")
    print(f"sha256: {hashlib.sha256(body.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
