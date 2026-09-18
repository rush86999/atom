"""Relevance gate between a planned lookup and the CURRENT request.

RCA 2026-09-17 finding 2: the final scorecard turn executed the previous
turn's ``outlook.search "PRICE VIPUL price list attachment"`` and its
result was accepted as this turn's evidence. These tests pin the
acceptance gate (core.plan_relevance.relevance_verdict), including the
exact failure shape and the near-miss shapes that must stay relevant.
"""
from core.plan_relevance import (
    content_tokens,
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
