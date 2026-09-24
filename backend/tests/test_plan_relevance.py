"""Relevance gate between a planned lookup and the CURRENT request.

RCA 2026-09-17 finding 2: the final scorecard turn executed the previous
turn's ``outlook.search "PRICE VIPUL price list attachment"`` and its
result was accepted as this turn's evidence. These tests pin the
acceptance gate (core.plan_relevance.relevance_verdict), including the
exact failure shape and the near-miss shapes that must stay relevant.
"""
from core.plan_relevance import (
    content_tokens,
    relevance_basis,
    relevance_verdict,
    strong_tokens,
)


#: The RCA turn's request, reconstructed from the persisted reasoning step.
SCORECARD_ASK = (
    "Can you search for the vendor scorecard and check the reliability "
    "0.87 before updating the workbook?"
)


def test_rca_case_stale_query_is_irrelevant():
    """The exact RCA shape: the old ask's query names nothing in the new
    ask — it must be declined before execution."""
    assert relevance_verdict(
        "PRICE VIPUL price list attachment", SCORECARD_ASK) == "irrelevant"


def test_query_addressing_the_ask_is_relevant():
    assert relevance_verdict(
        "vendor scorecard reliability 0.87", SCORECARD_ASK) == "relevant"


def test_shared_generic_word_alone_is_irrelevant():
    """One shared generic word ('update') with a long ask must not pass."""
    assert relevance_verdict(
        "update the mailbox flags", SCORECARD_ASK) == "irrelevant"


def test_strong_number_in_query_is_relevant():
    assert relevance_verdict("scorecard 0.87 vendor", SCORECARD_ASK) == (
        "relevant")


def test_code_split_across_tokens_stays_relevant():
    """'WG-350DSAV' re-tokenized as 'wg 350dsav' in the query — the short
    single-overlap rule keeps this relevant (false declines cost real
    evidence)."""
    assert relevance_verdict(
        "wg 350dsav price", "what is the price of the WG-350DSAV?") == (
        "relevant")


def test_quoted_phrase_in_query_is_relevant():
    assert relevance_verdict(
        "price list quote", 'which emails carried "PRICE VIPUL price list"?'
    ) == "relevant"


def test_empty_or_missing_query_fails_open():
    """Intents like documents.read can carry their target in kwargs — no
    query means no verdict, never a decline."""
    assert relevance_verdict("", SCORECARD_ASK) == "unknown"
    assert relevance_verdict(None, SCORECARD_ASK) == "unknown"
    assert relevance_verdict("   ", SCORECARD_ASK) == "unknown"


def test_content_free_message_fails_open():
    assert relevance_verdict("anything at all", "hi") == "unknown"
    assert relevance_verdict("anything at all", "") == "unknown"


def test_short_ask_single_overlap_is_relevant():
    assert relevance_verdict(
        "alternatives price", "update the alternatives price") == "relevant"


def test_content_tokens_drops_function_words_only():
    toks = content_tokens("Find the vendor scorecard for me, please")
    assert toks == {"vendor", "scorecard"}


def test_strong_tokens_captures_numbers_codes_caps():
    s = strong_tokens("RFQ 7519 and 0.87 with wg-350dsav vendor")
    assert {"7519", "0.87", "wg-350dsav", "rfq"} <= s
    assert "vendor" not in s


# --- R4 rules landed in cd0640d33, pinned afterwards (2026-09-17 ZCode):
# the new semantics shipped without pins in this file; these hold them. ---

def test_referential_message_is_unknown_not_irrelevant():
    """Review R4 repro 1: 'open that attachment' names its target through
    the conversation, so a lexical mismatch cannot prove staleness."""
    assert relevance_verdict(
        "invoice INV-0042",
        "Open the attachment from that email you just found") == "unknown"


def test_shared_number_alone_is_not_a_confident_relevant():
    """Review R4 false-accept: 0.87 in both strings is not a shared
    subject — an identifier needs corroboration, so the verdict drops to
    unknown (inspect) instead of a confident accept."""
    assert relevance_verdict("PRICE VIPUL 0.87", SCORECARD_ASK) == "unknown"


def test_number_with_content_corroboration_is_relevant():
    """The corroboration rule must not swallow the legitimate shape: the
    query names the subject words AND the identifier."""
    assert relevance_verdict(
        "vendor scorecard reliability 0.87", SCORECARD_ASK) == "relevant"


def test_identifer_only_message_keeps_identifier_relevant():
    """A message that is nothing BUT the identifier ('show me row 235')
    keeps the identifier as its subject (cd0640d33 rule 2 carve-out)."""
    assert relevance_verdict("row 235 values", "show me row 235") == (
        "relevant")


def test_stale_rca_query_still_irrelevant_after_r4_rules():
    """The original RCA decline must survive the new fail-open rules."""
    assert relevance_verdict(
        "PRICE VIPUL price list attachment", SCORECARD_ASK) == "irrelevant"


def test_body_figure_subject_query_stays_irrelevant_lexically():
    """The recorded R4 leftover (cd0640d33): a quoted BODY's figure against
    the thread SUBJECT query shares neither words nor digit runs. It stays
    lexically irrelevant BY DESIGN — the fix is the planner's acceptance
    stamp (relevant / provenance-quote), which the downstream gates honor,
    not another lexical exception here."""
    assert relevance_verdict(
        "FW: RFQ - Foot shear",
        "search for this one: $ 5,350.00 - 10 % in stock") == "irrelevant"


# --- CANVAS-TARGET ACCEPTANCE (2026-09-23, canvas 0e4defa5) -----------------
# Live incident: the edit instruction names the artifact and the fields to
# fill; the planner's evidence query names the SOURCE (Chandrakant's quote
# emails, i.e. the products being priced). Zero lexical overlap BY
# CONSTRUCTION, the same shape as the provenance-quote exemption — and the
# bare-word verdict stamped the correct query "irrelevant", both
# consumption gates declined it, the edit never ran, and the retry
# continuation died on its budget with an empty error string.

UPDATE_ASK = (
    "update with actual prices in the email. if unable, say so and why. "
    "square brackets with reference labels will not work in an email sent "
    "to a lead"
)
EVIDENCE_QUERY = (
    "Chandrakant amacisaac alternatives roll bender bead roller flanger "
    "slitter TK 16"
)
QUOTE_CANVAS = {
    "title": "Quote – Roper Whitney Roll Bender, Linmac Bead Roller, "
             "Manual Flanger & Slitters",
    "content": {
        "body": "<table><tr><td>Roper Whitney 36\" Gauge Manual Roll "
                "Bender, No. 381</td><td>TBD</td></tr>"
                "<tr><td>Tennsmith Single Wheel Slitter SLE24-16</td>"
                "<td>TBD</td></tr></table>",
    },
}
SCORECARD_CANVAS = {
    "title": "Vendor Scorecard Q3",
    "content": {"content": "vendor reliability scorecard workbook"},
}


def test_update_prices_ask_accepts_source_query_via_canvas_target():
    """THE incident: 'update with actual prices in the email' + the correct
    mailbox query for the quoted products — relevant ONLY through the
    canvas target (basis names the rule)."""
    from core.plan_relevance import canvas_topic_text

    verdict, basis = relevance_basis(
        EVIDENCE_QUERY, UPDATE_ASK,
        extra_topic=canvas_topic_text(QUOTE_CANVAS))
    assert (verdict, basis) == ("relevant", "canvas-target")


def test_same_pair_without_canvas_stays_irrelevant():
    """Backward compatibility: callers that pass no extra_topic see the
    byte-identical pre-rule behaviour."""
    assert relevance_basis(EVIDENCE_QUERY, UPDATE_ASK) == (
        "irrelevant", "zero-overlap")


def test_stale_query_against_its_own_canvas_still_irrelevant():
    """The gate's original purpose survives: the previous ask's query
    shares nothing with the scorecard canvas either — still declined."""
    from core.plan_relevance import canvas_topic_text

    assert relevance_basis(
        "PRICE VIPUL price list attachment", SCORECARD_ASK,
        extra_topic=canvas_topic_text(SCORECARD_CANVAS)) == (
        "irrelevant", "zero-overlap")


def test_canvas_target_identifier_rule():
    """A single overlapping token that is a strong identifier of the
    canvas (the model code) is enough — 'sle24-16' names the draft's row."""
    from core.plan_relevance import canvas_topic_text

    verdict, basis = relevance_basis(
        "sle24-16 delivery weeks", UPDATE_ASK,
        extra_topic=canvas_topic_text(QUOTE_CANVAS))
    assert verdict == "relevant"
    assert basis == "canvas-target-identifier"


def test_canvas_topic_text_shapes():
    """The helper reads title + readable content text from both context
    shapes and tolerates junk."""
    from core.plan_relevance import canvas_topic_text

    assert "SLE24-16" in canvas_topic_text(QUOTE_CANVAS)
    assert "<td>" not in canvas_topic_text(QUOTE_CANVAS)
    assert canvas_topic_text(None) == ""
    assert canvas_topic_text({"content": {"body": "<p>Flanger</p>"}}) != ""


def test_canvas_target_is_opt_in_for_non_edit_requests():
    from core.plan_relevance import canvas_topic_text

    assert relevance_basis(
        "roll bender alternatives",
        "check the vendor reliability score",
        extra_topic=canvas_topic_text(QUOTE_CANVAS),
        allow_canvas_target=False,
    ) == ("irrelevant", "zero-overlap")


def test_canvas_target_matches_simple_plural_variants():
    from core.plan_relevance import canvas_topic_text

    verdict, basis = relevance_basis(
        "slitter alternatives",
        "update the actual prices in the email",
        extra_topic=canvas_topic_text({"title": "Slitters"}),
        allow_canvas_target=True,
    )
    assert (verdict, basis) == ("relevant", "canvas-target")


def test_canvas_target_ignores_year_and_boilerplate_overlap():
    from core.plan_relevance import canvas_topic_text

    verdict, basis = relevance_basis(
        "2026 vendor benefits",
        "update the actual prices in the email",
        extra_topic=canvas_topic_text({
            "title": "Prepared 2026",
            "content": {"body": "All quotes are valid for 15 days. CAD FOB TBD"},
        }),
        allow_canvas_target=True,
    )
    assert (verdict, basis) == ("irrelevant", "zero-overlap")
