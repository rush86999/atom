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
