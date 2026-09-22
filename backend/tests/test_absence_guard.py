"""Universal absence claims must be covered by the turn's evidence.

RCA 2026-09-17 answer-quality defects: a mailbox search for PRICE VIPUL
became "No file with that name exists in the system", and "None that we
sent" silently narrowed the scope to external recipients. Pins the
detector, the coverage check against the delivered evidence block, and
the corrective message's scope/direction rules.
"""
from core.absence_guard import (
    absence_correction_message,
    universal_absence_claims,
    uncovered_absence_claims,
)


def test_rca_file_absence_claim_detected():
    claims = universal_absence_claims(
        "I searched, but no file with that name exists in the system. "
        "Would you like me to look elsewhere?")
    assert len(claims) == 1
    assert "no file with that name exists" in claims[0]


def test_rca_sent_scope_claim_detected():
    claims = universal_absence_claims(
        "None that we sent — the attachment only appears on incoming mail.")
    assert claims
    assert "None that we sent" in claims[0]


def test_does_not_exist_detected():
    assert universal_absence_claims("That workbook does not exist.")


def test_hedged_or_scoped_phrasing_not_flagged():
    """Honest phrasing must never trip a regeneration."""
    assert not universal_absence_claims(
        "I did not find one in the CRM search above.")
    assert not universal_absence_claims(
        "I could not locate the scorecard in the folders I checked.")
    assert not universal_absence_claims(
        "Here is what I found in the mailbox search results.")


MAILBOX_BLOCK = (
    "LIVE TOOL RESULTS (ingested mailbox):\n"
    "outlook.search query='PRICE VIPUL price list attachment' -> 2 result(s)\n"
    "FULL MESSAGE BODIES are included above."
)


def test_rca_reply_uncovered_against_mailbox_block():
    """The shipped reply: absence about FILES asserted on a MAILBOX search
    — no executed lookup covers a filesystem claim."""
    reply = ("I searched the mailbox. No file with that name exists in the "
             "system.")
    uncovered = uncovered_absence_claims(reply, MAILBOX_BLOCK)
    assert uncovered
    assert "No file with that name" in uncovered[0]


def test_claim_covered_when_search_names_the_subject():
    reply = "No emails from VIPUL matched the vendor scorecard request."
    block = ("LIVE TOOL RESULTS:\n"
             "outlook.search query='vendor scorecard VIPUL' -> 0 result(s)")
    assert uncovered_absence_claims(reply, block) == []
    # non-vacuity: the sentence IS a claim, and without a block it is
    # uncovered — before 2026-09-21 'matched' matched no detector, so this
    # test passed with ANY block, even a failed search
    assert uncovered_absence_claims(reply, "") == [reply]


def test_empty_or_failed_block_covers_nothing():
    reply = "No matching records exist in the system."
    assert uncovered_absence_claims(reply, "")
    assert uncovered_absence_claims(
        reply, "NO LIVE LOOKUP EXECUTED: the planned lookup was declined.")


def test_no_tool_block_at_all_leaves_uncovered():
    reply = "There is no such workbook."
    assert uncovered_absence_claims(reply, None) == (
        universal_absence_claims(reply))


def test_correction_message_scope_direction_and_sources():
    msg = absence_correction_message(
        ["None that we sent."],
        "SOURCES LOCATED EARLIER IN THIS CONVERSATION: PRICE VIPUL (6).xlsx.")
    assert "internal forward is still SENT" in msg
    assert "scoped to what was actually checked" in msg
    assert "one match never proves no other match" in msg
    assert "PRICE VIPUL (6).xlsx" in msg


def test_claims_capped():
    reply = ". ".join(
        f"Claim number {i}: no matching records exist in the system."
        for i in range(6))
    assert len(universal_absence_claims(reply)) <= 3


# --- R2 coverage rules landed in cd0640d33, pinned afterwards (2026-09-17
# ZCode): the new coverage semantics shipped without pins here. ---

def test_failed_or_denied_lookup_never_covers():
    """A permission-denied 'file search' proves nothing about existence —
    review R2 repro 2, previously accepted via one shared token."""
    assert uncovered_absence_claims(
        "No file with that name exists in the system.",
        "LIVE TOOL RESULTS: file search failed with permission denied.")


def test_partial_page_or_cursor_never_covers():
    """A first page with a continuation cursor cannot establish that
    something exists nowhere — review R2 repro 1."""
    assert uncovered_absence_claims(
        "The vendor scorecard workbook does not exist.",
        "LIVE TOOL RESULTS: outlook.search query=vendor scorecard; "
        "first page only; 1 result; next_page_token=abc")


def test_positive_hit_never_covers_absence():
    """Evidence reporting a match on the claim's subject refutes the
    absence claim outright."""
    assert uncovered_absence_claims(
        "No emails from joel were found.",
        "LIVE TOOL RESULTS: outlook.search joel emails -> 3 messages "
        "matched")


def test_no_other_claim_is_recognised_as_absence():
    """'No other email carried it' was invisible to the detector before
    cd0640d33 — an unseen claim is indistinguishable from a covered one."""
    claims = universal_absence_claims("No other email carried that price list.")
    assert len(claims) == 1


# --- 2026-09-21 ZCode: verb-mediated absence shapes shipped unguarded —
# "PRICE VIPUL contains no scorecard sheet" and "No emails from VIPUL
# matched ..." matched NO detector, so those over-claims sailed through
# and the two "covered" tests above passed vacuously. ---

def test_absence_asserted_through_a_data_verb_is_detected():
    assert universal_absence_claims("PRICE VIPUL contains no scorecard sheet.")
    assert universal_absence_claims("The workbook holds none of the quoted figures.")
    assert universal_absence_claims("No emails from VIPUL matched the request.")
    assert universal_absence_claims("The attachment does not contain any price list.")
    assert universal_absence_claims("The index doesn't mention that clause.")


def test_search_behaviour_verbs_stay_exempt():
    """These report what the SEARCH did — the honest, scoped form. They
    must never trip a regeneration (find/match are deliberately absent
    from the do-support detector)."""
    assert not universal_absence_claims("I did not find one in the CRM search above.")
    assert not universal_absence_claims("The search did not match any rows.")
    assert not universal_absence_claims("I have no idea what happened to it.")


def test_verb_mediated_absence_follows_the_same_coverage_rule():
    claim = "PRICE VIPUL contains no scorecard sheet."
    covered = ("LIVE TOOL RESULTS (memory.search):\n"
               "- [document: ingested] PRICE VIPUL (6).xlsx | WORKBOOK INDEX")
    assert uncovered_absence_claims(claim, covered) == []
    assert uncovered_absence_claims(claim, "") == [claim]
    assert uncovered_absence_claims(
        claim, "LIVE TOOL RESULTS: file search failed with permission denied.")


def test_completed_empty_search_over_the_subject_covers():
    """The honest shape must keep passing: a finished search that names the
    subject and reports nothing, no failure, no cursor."""
    assert uncovered_absence_claims(
        "The mailbox scan found no messages about that RFQ.",
        "LIVE TOOL RESULTS: outlook.search 'RFQ foot shear' -> 0 results "
        "(scan complete)") == []


def test_sentence_final_subject_still_covered():
    """content_tokens glues the sentence-final period to the token
    ('RFQ.' != 'rfq') — an honest, covered answer must not be flagged
    purely on punctuation (strip fix, 2026-09-17)."""
    assert uncovered_absence_claims(
        "The ingested documents hold no such sheet for RFQ.",
        "LIVE TOOL RESULTS (memory.search): RFQ 7519 workbook index — "
        "0 matching sheets (search complete)") == []


# --- Deterministic last resort (strip), added 2026-09-17 (ZCode): the
# invariant must hold even when the corrective regeneration fails or
# over-claims again. ---

def test_strip_replaces_only_uncovered_sentences():
    from core.absence_guard import strip_uncovered_absence_claims

    reply = ("No file with that name exists in the system. "
             "Your draft was saved unchanged. "
             "None that we sent carried that price list.")
    block = "LIVE TOOL RESULTS: outlook.search failed with permission denied."
    out = strip_uncovered_absence_claims(reply, block)
    assert "does not exist" not in out
    assert "None that we sent" not in out
    assert "draft was saved unchanged" in out


def test_strip_passes_covered_reply_through_untouched():
    from core.absence_guard import strip_uncovered_absence_claims

    reply = "PRICE VIPUL contains no scorecard sheet."
    block = ("LIVE TOOL RESULTS (memory.search):\n"
             "- [document: ingested] PRICE VIPUL (6).xlsx | WORKBOOK INDEX")
    assert strip_uncovered_absence_claims(reply, block) == reply
    # non-vacuity: without coverage the same sentence IS rewritten — before
    # 2026-09-21 'contains no' matched no detector, so any reply passed
    # through untouched whatever the evidence said
    assert strip_uncovered_absence_claims(reply, "") != reply


def test_strip_limitation_is_itself_not_an_uncovered_claim():
    """The fallback sentence must not re-trip the guard (no loops, no
    second regeneration)."""
    from core.absence_guard import (
        _SCOPED_LIMITATION,
        strip_uncovered_absence_claims,
        uncovered_absence_claims,
    )

    out = strip_uncovered_absence_claims(
        "No file with that name exists in the system.",
        "LIVE TOOL RESULTS: file search failed with permission denied.")
    assert out == _SCOPED_LIMITATION
    assert uncovered_absence_claims(out, "") == []
