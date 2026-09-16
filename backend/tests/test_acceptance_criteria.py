# -*- coding: utf-8 -*-
"""Unit tests for the acceptance-replay criteria and scoring helpers.

These tests are the proof that the criteria DISCRIMINATE: every case gets at
least one synthetic reply that is merely wordy (the previous revision's keyword
technique) and must FAIL, and one substantively correct reply that must PASS.

The criteria under test live in ``backend/scripts/acceptance_replay_canvas.py``
(loaded by path — ``scripts/`` is not a package). All evidence here is
synthetic: nothing in this file touches the live stores or the network.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "acceptance_replay_canvas.py",
)
_spec = importlib.util.spec_from_file_location("acceptance_replay_canvas", _SCRIPT)
arc = importlib.util.module_from_spec(_spec)
# Registering BEFORE exec is required: the module uses
# ``from __future__ import annotations`` with dataclasses, and dataclasses
# resolves the defining module through sys.modules.
sys.modules[_spec.name] = arc
_spec.loader.exec_module(arc)


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

VENDOR_MSG_ID = ("AAMkADdlNTY5N2I1LTQwNTMtNDQ2OC04MzBlLTU5OGFmZGQ2MzRmYQBGAAAA"
                 "AADWztKWmJlHSYU0pqyNk-0MBwDEtbYrrPLwTae3iXb78LoOAAAAAAEM")
PRICE_LIST_MSG_ID = ("AAMkADdlNTY5N2I1LTQwNTMtNDQ2OC04MzBlLTU5OGFmZGQ2MzRmYQBGAAAA"
                     "AADWztKWmJlHSYU0pqyNk-0MBwDEtbYrrPLwTae3iXb78LoOAAHNwG-DAAA=")


def _vendor_message() -> "arc.StoredMessage":
    return arc.StoredMessage(
        message_id=VENDOR_MSG_ID,
        sender="joelseguin@seguinmach.com",
        recipients=["chandrakant@brennan.ca"],
        subject="FW: RFQ - Foot shear",
        timestamp="2026-08-26 14:06:28",
        text=("FW: RFQ - Foot shear\n$ 5,350.00 – 10 %  in stock\n"
              "Do you prefer a used shear ?\nJoel Seguin V.P. SEGUIN Machinery Ltd"),
        sender_name="Joel Seguin",
    )


def _price_list_carrier(direction: str = "internal") -> "arc.StoredMessage":
    """The PRICE VIPUL carrier as the live store has it: an INTERNAL forward
    from chandrakant@brennan.ca to rish@brennan.ca."""
    return arc.StoredMessage(
        message_id=PRICE_LIST_MSG_ID,
        sender="chandrakant@brennan.ca",
        recipients=["rish@brennan.ca"],
        subject="Fw: RFQ - Foot shear",
        timestamp="2026-09-11 20:07:31",
        text="Best, Chandrakant Sharma — forwarding the price list.",
        attachments=["PRICE VIPUL (6).xlsx"],
        doc_ids=["ext_c1f74b7fad81fa71596b5380"],
    )


def _inbound_price_list_carrier() -> "arc.StoredMessage":
    return arc.StoredMessage(
        message_id=PRICE_LIST_MSG_ID,
        sender="joelseguin@seguinmach.com",
        recipients=["chandrakant@brennan.ca"],
        subject="FW: RFQ - Foot shear",
        timestamp="2026-08-26 14:06:28",
        text="Attached our price list.",
        attachments=["PRICE VIPUL (6).xlsx"],
        doc_ids=["ext_c1f74b7fad81fa71596b5380"],
    )


def _quote_evidence() -> "arc.EvidenceBundle":
    msg = _vendor_message()
    return arc.EvidenceBundle(our_domains=["brennan.ca"],
                              messages={msg.message_id: msg})


def _directional_evidence(carrier: "arc.StoredMessage" = None) -> "arc.EvidenceBundle":
    msg = carrier or _price_list_carrier()
    ev = arc.EvidenceBundle(our_domains=["brennan.ca"],
                            messages={msg.message_id: msg})
    ev.carriers[arc.carrier_key("PRICE VIPUL (6).xlsx")] = [msg.message_id]
    return ev


def _workbook_facts() -> "arc.WorkbookFacts":
    """The live PRICE VIPUL (6).xlsx row 235 chain (verified 2026-09-16)."""
    cell_values = {
        "D235": 7519.0, "F235": 5350.0, "G235": 4815.0, "H235": 4815.0,
        "I235": 5515.0, "J235": 5515.0, "K235": 5625.3, "L235": 6465.862068965517,
        "M235": 7518.444266238974, "N235": 7519.0, "O235": 1.0, "P235": 7519.0,
        "R235": 1893.6999999999998,
    }
    formulas = {
        "D235": "=P235", "G235": "=F235*0.9", "H235": "=G235",
        "I235": "=H235+700", "J235": "=I235", "K235": "=J235*1.02",
        "L235": "=K235/0.87", "M235": "=L235/0.86", "N235": "=ROUNDUP(M235,0)",
        "P235": "=N235*O235", "R235": "=P235-K235", "S235": "=R235/P235",
    }
    steps = [
        arc.WorkbookStep("G235", "Factory Discount", "=F235*0.9", 4815.0, "factor", 0.9),
        arc.WorkbookStep("I235", "Freight", "=H235+700", 5515.0, "offset", 700.0),
        arc.WorkbookStep("K235", "Warehouse", "=J235*1.02", 5625.3, "factor", 1.02),
        arc.WorkbookStep("L235", "Brennan Margin", "=K235/0.87", 6465.86, "factor", 0.87),
        arc.WorkbookStep("M235", "Dealer margin", "=L235/0.86", 7518.44, "factor", 0.86),
        arc.WorkbookStep("N235", "Price", "=ROUNDUP(M235,0)", 7519.0, "round", None),
    ]
    allowed = [235.0, 5350.0, 4815.0, 5515.0, 5625.3, 6465.862068965517,
               7518.444266238974, 7519.0, 0.9, 1.02, 0.87, 0.86, 700.0, 1.0,
               1893.7, 7519.0, 0.0]
    return arc.WorkbookFacts(
        file_name="PRICE VIPUL (6).xlsx",
        dataset_name="outlook_price_vipul_6___sheet1",
        sheet_name="Sheet1",
        row_number=235,
        product="F-52”x16G",
        target_value=7519.0,
        sheet_count=1,
        values={k: v for k, v in cell_values.items()},
        formulas=formulas,
        steps=steps,
        allowed_numbers=allowed,
        unresolved_cells=[],
    )


def _derivation_evidence() -> "arc.EvidenceBundle":
    return arc.EvidenceBundle(our_domains=["brennan.ca"],
                              workbook=_workbook_facts())


def _run(case_key: str, reply: str, ev: "arc.EvidenceBundle"):
    case = next(c for c in arc.CASES if c["key"] == case_key)
    return arc.evaluate_case(case, reply, ev)


def _quality(criteria, delivery=None) -> str:
    delivery = delivery or {"outcome": "answered"}
    return arc.aggregate_quality(delivery, criteria)["outcome"]


def _by_id(criteria):
    return {c.criterion: c for c in criteria}


# ---------------------------------------------------------------------------
# quote
# ---------------------------------------------------------------------------

CORRECT_QUOTE_REPLY = (
    "Found it. The **$5,350.00 – 10% in stock** line comes from Joel Seguin "
    "(joelseguin@seguinmach.com), V.P. of Seguin Machinery Ltd, in his "
    "\"FW: RFQ - Foot shear\" email received **Aug 26, 2026 at 2:06 PM**, "
    "replying to Chandrakant's RFQ for a foot shear."
)

KEYWORD_ONLY_QUOTE_REPLY = (
    "The vendor Seguin has a quote in stock: $5,350.00 with 10% — that is the "
    "quotation you are looking for."
)


def test_quote_correct_reply_passes():
    criteria = _run("quote", CORRECT_QUOTE_REPLY, _quote_evidence())
    assert _quality(criteria) == "pass", _by_id(criteria)
    assert all(c.passed for c in criteria)


def test_quote_identified_by_display_name_and_date_passes():
    """The live answer names the sender by display name ("Joel Seguin") plus
    the date, never the raw address — that is a real identification, verified
    against the display name the store itself holds."""
    reply = ("Found it — this comes from the **RFQ – Foot shear** email thread "
             "with Joel Seguin (SEGUIN Machinery Ltd), received Aug 26, 2026. "
             "He quoted: \"$ 5,350.00 – 10% in stock\".")
    ev = _quote_evidence()
    assert ev.messages[VENDOR_MSG_ID].sender_name == "Joel Seguin"
    criteria = _run("quote", reply, ev)
    reasons = arc.message_match_reasons(reply, ev.messages[VENDOR_MSG_ID])
    assert "sender_name+date" in reasons
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_quote_name_without_matching_date_is_not_an_identification():
    """A vendor name alone (the old keyword technique) still must not pass."""
    ev = _quote_evidence()
    reply = ("Joel Seguin has a quotation for a foot shear with $5,350.00, "
             "10% off, in stock.")
    reasons = arc.message_match_reasons(reply, ev.messages[VENDOR_MSG_ID])
    assert "sender_name" in reasons          # the name is recognised…
    assert not (arc.STRONG_MATCH_REASONS & set(reasons))  # …but proves nothing
    assert _quality(_run("quote", reply, ev)) == "fail"


def test_quote_keyword_only_reply_fails():
    """Every keyword the old harness looked for is present — and it must FAIL:
    no stored message is identified, so nothing establishes the quote."""
    low = KEYWORD_ONLY_QUOTE_REPLY.lower()
    assert "seguin" in low and "5,350" in low  # the old any_of tokens
    criteria = _run("quote", KEYWORD_ONLY_QUOTE_REPLY, _quote_evidence())
    assert _quality(criteria) == "fail"
    assert not _by_id(criteria)["quote.identifies_stored_message"].passed


def test_quote_wrong_attribution_fails():
    reply = ("That price came from Fintek on 2026-01-04 — the vendor quoted "
             "$5,350.00, 10% off, in stock.")
    criteria = _run("quote", reply, _quote_evidence())
    assert _quality(criteria) == "fail"
    assert not _by_id(criteria)["quote.identifies_stored_message"].passed


def test_quote_reversed_framing_fails():
    reply = (CORRECT_QUOTE_REPLY +
             " We sent the $5,350.00 quote back to Seguin the same day.")
    criteria = _run("quote", reply, _quote_evidence())
    assert not _by_id(criteria)["quote.not_reversed"].passed
    assert _quality(criteria) == "fail"


# ---------------------------------------------------------------------------
# directional
# ---------------------------------------------------------------------------

CORRECT_DIRECTIONAL_REPLY = (
    "The only message in the mailbox that carried PRICE VIPUL (6).xlsx as an "
    "attachment is Chandrakant Sharma's internal forward to Rish Maniar "
    "(chandrakant@brennan.ca -> rish@brennan.ca) on 2026-09-11, subject "
    "\"Fw: RFQ - Foot shear\". No email to a counterparty carries that price "
    "list as an attachment."
)

KEYWORD_ONLY_DIRECTIONAL_REPLY = (
    "Yes — the PRICE VIPUL price list was carried as an email attachment, and "
    "those sent emails are in the mailbox."
)


def test_directional_correct_reply_passes():
    criteria = _run("directional", CORRECT_DIRECTIONAL_REPLY,
                    _directional_evidence())
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_directional_keyword_only_reply_fails():
    """Contains 'price vipul', 'attachment', 'email', 'sent' — the old keyword
    list — but links the attachment to no message, so it must FAIL."""
    low = KEYWORD_ONLY_DIRECTIONAL_REPLY.lower()
    for token in ("price vipul", "attachment", "email", "sent"):
        assert token in low
    criteria = _run("directional", KEYWORD_ONLY_DIRECTIONAL_REPLY,
                    _directional_evidence())
    assert _quality(criteria) == "fail"
    assert not _by_id(criteria)["directional.attachment_linked"].passed


def test_directional_reversed_direction_fails():
    """The store's only carrier is an INTERNAL forward; claiming it went out to
    a counterparty reverses the direction and must FAIL."""
    reply = ("We sent the PRICE VIPUL price list to Wayne Knott on 2026-09-11, "
             "with the workbook attached, so the customer has the pricing.")
    criteria = _run("directional", reply, _directional_evidence())
    by_id = _by_id(criteria)
    assert not by_id["directional.no_phantom_outbound"].passed
    assert _quality(criteria) == "fail"


def test_directional_reversed_direction_with_external_address_fails():
    reply = ("We emailed the PRICE VIPUL price list to "
             "wayne.knott@belden.com on 2026-09-11 as an attachment.")
    criteria = _run("directional", reply, _directional_evidence())
    by_id = _by_id(criteria)
    assert not by_id["directional.no_phantom_outbound"].passed


def test_directional_counterparty_named_in_prose_fails():
    """No address and no framing word — but the store knows Seguin as an
    external correspondent, so "sent it to Seguin" is an outbound claim."""
    ev = _directional_evidence()
    ev.counterparty_tokens = ["seguin", "seguinmach", "massilly"]
    reply = ("We sent the PRICE VIPUL price list to Seguin on 2026-09-11 so "
             "they could quote the customer.")
    criteria = _run("directional", reply, ev)
    assert not _by_id(criteria)["directional.no_phantom_outbound"].passed


def test_directional_live_reply_shape_passes():
    """The 2026-09-16 live answer: "we sent one email carrying PRICE VIPUL…"
    followed by the From/To list of the INTERNAL forward. It names the right
    message and does not claim a counterparty received it — it must PASS."""
    reply = (
        "Based on the ingested mailbox threads, we sent one email carrying the "
        "**PRICE VIPUL (6).xlsx** price list as an attachment:\n"
        "- **From:** Chandrakant Sharma (chandrakant@brennan.ca)\n"
        "- **To:** Rish Maniar (rish@brennan.ca)\n"
        "- **Subject:** Fw: RFQ - Foot shear\n"
        "- **Received:** 2026-09-11 20:07:31\n\n"
        "That email explicitly lists PRICE VIPUL (6).xlsx as an attachment. No "
        "other email in the current search results shows that specific file "
        "attached — if you need to confirm whether it was sent to any external "
        "customer on a different thread, I can run a broader grep."
    )
    criteria = _run("directional", reply, _directional_evidence())
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_directional_received_claim_on_our_own_send_fails():
    """Claiming we RECEIVED the price list from the vendor reverses direction
    when the store says this mailbox sent it."""
    reply = ("Joel Seguin sent us the PRICE VIPUL price list as an attachment "
             "on 2026-09-11 — we received it in the mailbox.")
    criteria = _run("directional", reply, _directional_evidence())
    by_id = _by_id(criteria)
    assert not by_id["directional.direction_verified"].passed
    assert _quality(criteria) == "fail"


def test_directional_correct_on_an_outbound_carrier_passes():
    """With an outbound carrier in the store, a sent-to-counterparty claim with
    the right message is correct (the criterion is not 'must be internal')."""
    carrier = arc.StoredMessage(
        message_id=PRICE_LIST_MSG_ID,
        sender="chandrakant@brennan.ca",
        recipients=["joelseguin@seguinmach.com"],
        subject="Fw: RFQ - Foot shear",
        timestamp="2026-09-11 20:07:31",
        text="Forwarding the price list.",
        attachments=["PRICE VIPUL (6).xlsx"],
    )
    reply = ("We sent PRICE VIPUL (6).xlsx to joelseguin@seguinmach.com on "
             "2026-09-11 (subject \"Fw: RFQ - Foot shear\").")
    criteria = _run("directional", reply, _directional_evidence(carrier))
    assert _quality(criteria) == "pass", _by_id(criteria)


# ---------------------------------------------------------------------------
# derivation
# ---------------------------------------------------------------------------

CORRECT_DERIVATION_REPLY = (
    "In PRICE VIPUL (6).xlsx (sheet Sheet1), row 235 holds F-52”x16G. The "
    "listed price 7,519 is derived in-row:\n"
    "- Factory Price 5,350 (F235)\n"
    "- G235 = F235*0.9 = 4,815 (10% factory discount)\n"
    "- I235 = H235+700 = 5,515 (freight)\n"
    "- K235 = J235*1.02 = 5,625.30 (warehouse)\n"
    "- L235 = K235/0.87 = 6,465.86 (Brennan margin)\n"
    "- M235 = L235/0.86 = 7,518.44 (dealer margin)\n"
    "- N235 = ROUNDUP(M235,0) = 7,519 (Price), and D235 (LIST Price) = P235 = "
    "N235*O235 = 7,519"
)

KEYWORD_ONLY_DERIVATION_REPLY = (
    "PRICE VIPUL row 235 has a formula that produces 7519 — the listed price "
    "comes from the workbook cells."
)

FABRICATED_DERIVATION_REPLY = (
    "In PRICE VIPUL row 235, the 7,519 list price is the factory price of "
    "5,350 multiplied by the 1.35 exchange rate and then by a 1.04 freight "
    "factor, rounded up to 7,519."
)


def test_derivation_correct_reply_passes():
    criteria = _run("derivation", CORRECT_DERIVATION_REPLY,
                    _derivation_evidence())
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_derivation_keyword_only_reply_fails():
    low = KEYWORD_ONLY_DERIVATION_REPLY.lower()
    assert "7519" in low and "235" in low and "formula" in low
    criteria = _run("derivation", KEYWORD_ONLY_DERIVATION_REPLY,
                    _derivation_evidence())
    assert _quality(criteria) == "fail"
    assert not _by_id(criteria)["derivation.formula_chain"].passed


def test_derivation_fabricated_chain_fails():
    """1.35 and 1.04 are not in row 235 (U235 is empty, the workbook never
    resolves an exchange rate for this row) — a fabricated chain fails."""
    criteria = _run("derivation", FABRICATED_DERIVATION_REPLY,
                    _derivation_evidence())
    by_id = _by_id(criteria)
    assert not by_id["derivation.no_fabricated_chain"].passed
    assert not by_id["derivation.formula_chain"].passed
    assert _quality(criteria) == "fail"


LIVE_DERIVATION_REPLY = (
    "I opened PRICE VIPUL (6).xlsx — Sheet1, row 235 (product F-52”x16G). The "
    "workbook shows LIST Price (D235 = 7519) was computed from the Factory "
    "Price (F235 = 5350) using these steps (formulas taken from that sheet):\n"
    "- F235 = 5350 (Factory Price)\n"
    "- G235 = F235 * 0.9 = 5350 * 0.9 = 4815.0\n"
    "- H235 = G235 = 4815.0\n"
    "- I235 = H235 + 700 = 4815.0 + 700 = 5515.0\n"
    "- K235 = J235 * 1.02 = 5515.0 * 1.02 = 5625.3\n"
    "- L235 = K235 / 0.87 = 5625.3 / 0.87 = 6465.862068965517\n"
    "- M235 = L235 / 0.86 = 6465.862068965517 / 0.86 = 7518.882\n"
    "- N235 = ROUNDUP(M235, 0) = 7519\n"
    "From the sheet values (P235 = 7519 and N235 = 7519) the multiplier O235 "
    "must be 1 for this row."
)


def test_derivation_input_cell_values_are_legitimate():
    """F235 (Factory Price 5350) has no formula — it is an INPUT, and stating
    it is not fabrication. The 2026-09-16 run flagged it because the allowed
    set was built only from formula cells."""
    ev = _derivation_evidence()
    assert 5350.0 in ev.workbook.allowed_numbers
    assert arc.unsupported_figures(
        "G235 = F235 * 0.9 = 5350 * 0.9 = 4815.0",
        ev.workbook.allowed_numbers) == []


def test_derivation_wrong_quotient_fails_exactness():
    """The live reply's one slip: M235 divided by 0.86 printed as 7518.882
    where the sheet computes 7518.444266. Every other step is right, so this
    must fail ONLY the exactness criterion."""
    criteria = _run("derivation", LIVE_DERIVATION_REPLY, _derivation_evidence())
    by_id = _by_id(criteria)
    assert by_id["derivation.correct_workbook"].passed
    assert by_id["derivation.correct_row"].passed
    assert by_id["derivation.formula_chain"].passed
    assert by_id["derivation.no_fabricated_chain"].passed
    assert not by_id["derivation.values_match_store"].passed
    assert "7518.882" in " ".join(
        by_id["derivation.values_match_store"].evidence)
    assert _quality(criteria) == "fail"


def test_derivation_unresolved_marker_excuses_a_missing_input():
    """A genuine unresolved input, explicitly flagged, is honest — it must not
    be scored as a fabricated chain, even though the chain is incomplete."""
    reply = (
        "In PRICE VIPUL (6).xlsx row 235 (F-52”x16G) the listed price 7,519 is "
        "built as: 5,350 factory price *0.9 = 4,815, +700 = 5,515, *1.02 = "
        "5,625.30, /0.87 = 6,465.86, then a dealer-margin divisor that is "
        "UNRESOLVED: M235's divisor is not in the workbook copy I can read, so "
        "the final ROUNDUP to 7,519 cannot be verified. The 1.35 exchange "
        "factor is also UNRESOLVED."
    )
    criteria = _run("derivation", reply, _derivation_evidence())
    by_id = _by_id(criteria)
    assert by_id["derivation.no_fabricated_chain"].passed
    assert by_id["derivation.unresolved_reported"].passed
    # chain is still incomplete (0.86 not stated) — this is a quality FAIL,
    # but a defensible one, not a fabrication verdict.
    assert not by_id["derivation.formula_chain"].passed


# ---------------------------------------------------------------------------
# control_unrelated_source
# ---------------------------------------------------------------------------

SCORECARD_SPEC = {"name": "vendor scorecard", "value": "0.87"}


def _source_evidence(trace_steps=None, datasets=None) -> "arc.EvidenceBundle":
    return arc.EvidenceBundle(
        our_domains=["brennan.ca"],
        datasets=datasets or [],
        trace_steps=trace_steps if trace_steps is not None else [
            {"step_type": "observation", "action": "datasets.search",
             "observation": "no dataset matched 'vendor scorecard'",
             "duration_ms": 120},
        ],
    )


def test_control_unrelated_source_keyword_repeat_fails():
    """Repeats 'workbook', 'scorecard' and 0.87 from the question, with no
    lookup evidence and no verified source — the old harness passed this."""
    reply = ("The reliability score 0.87 from the vendor scorecard workbook is "
             "0.87 — a strong reliability score in that workbook.")
    criteria = _run("control_unrelated_source", reply, _source_evidence(
        trace_steps=[]))
    assert _quality(criteria) == "fail"
    by_id = _by_id(criteria)
    assert not by_id["control_unrelated_source.lookup_evidence"].passed
    assert not by_id["control_unrelated_source.source_verified_or_disclaimed"].passed


def test_control_unrelated_source_explicit_not_found_passes():
    reply = ("I searched the dataset catalog: there is no vendor scorecard "
             "workbook in our records, so I cannot confirm the 0.87 "
             "reliability score from that source.")
    criteria = _run("control_unrelated_source", reply, _source_evidence())
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_control_unrelated_source_verified_dataset_passes():
    datasets = [{"file_name": "Vendor Scorecard 2026.xlsx",
                 "dataset_name": "vendor_scorecard_2026"}]
    reply = ("The vendor scorecard workbook exists: its sheet holds the 0.87 "
             "reliability score for that vendor.")
    criteria = _run("control_unrelated_source", reply,
                    _source_evidence(datasets=datasets))
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_control_unrelated_source_false_source_claim_fails():
    reply = ("The vendor scorecard workbook shows a reliability score of 0.87 "
             "for that supplier.")
    criteria = _run("control_unrelated_source", reply, _source_evidence())
    by_id = _by_id(criteria)
    assert not by_id["control_unrelated_source.no_false_source"].passed
    assert _quality(criteria) == "fail"


# ---------------------------------------------------------------------------
# control_missing_evidence
# ---------------------------------------------------------------------------

F9999_SPEC = {"code": "F-9999", "kind": "hydraulic press"}


def test_missing_evidence_correct_reply_passes():
    """Disclaims F-9999 and mentions another product's REAL price — the answer
    the previous keyword harness scored as a failure."""
    reply = ("There is no record of an F-9999 hydraulic press in our records, "
             "so I can't give you its list price. The closest product I can "
             "find is the F-52”x16G foot shear at $7,519.00.")
    criteria = _run("control_missing_evidence", reply, arc.EvidenceBundle())
    assert _quality(criteria) == "pass", _by_id(criteria)


def test_missing_evidence_invented_price_fails():
    reply = ("The F-9999 hydraulic press lists at $45,000.00 in our records, "
             "with delivery in 6 weeks.")
    criteria = _run("control_missing_evidence", reply, arc.EvidenceBundle())
    by_id = _by_id(criteria)
    assert not by_id["control_missing_evidence.no_price_attributed_to_target"].passed
    assert _quality(criteria) == "fail"


def test_missing_evidence_bare_number_attribution_fails():
    reply = "F-9999 has a list price of 45,000 in the price list."
    criteria = _run("control_missing_evidence", reply, arc.EvidenceBundle())
    assert not _by_id(criteria)[
        "control_missing_evidence.no_price_attributed_to_target"].passed


def test_missing_evidence_ignoring_the_question_fails():
    criteria = _run("control_missing_evidence",
                    "Happy to help with pricing questions any time.",
                    arc.EvidenceBundle())
    by_id = _by_id(criteria)
    assert not by_id["control_missing_evidence.target_addressed"].passed
    assert _quality(criteria) == "fail"


# ---------------------------------------------------------------------------
# delivery vs quality, stage attribution, helpers
# ---------------------------------------------------------------------------


def test_provider_failure_is_not_a_quality_failure():
    steps = [{"step_type": "thought", "action": "tool_planner",
              "observation": "Planned live lookup: datasets.search"},
             {"step_type": "observation", "action": "datasets.search",
              "observation": "dataset row 235 with formulas =N235*O235"}]
    delivery = arc.classify_delivery(
        200, {"message": "[Error: All LLM providers failed. Please check your "
                         "API key configuration and try again.]",
              "error_code": None},
        None, steps, "derivation")
    assert delivery["outcome"] == "provider_failure"
    assert delivery["stage_failed"] == "final_generation"
    # retrieval DID run — recorded, not erased by the generation failure
    assert delivery["stage_evidence"]["retrieval"]
    assert delivery["stage_evidence"]["derivation"]
    quality = arc.aggregate_quality(delivery, [])
    assert quality["outcome"] == "not_evaluated"
    assert "not evaluated" in quality["reason"]


def test_transport_failure_stage_and_not_evaluated():
    delivery = arc.classify_delivery(
        None, None, "ConnectError: All connection attempts failed", [],
        "quote")
    assert delivery["outcome"] == "transport_error"
    assert delivery["stage_failed"] == "transport"
    assert arc.aggregate_quality(delivery, [])["outcome"] == "not_evaluated"


def test_template_route_is_a_delivery_failure_not_a_pass():
    """A canned template string is not a model answer: delivery fails, quality
    is NOT EVALUATED, and it is never a quality pass."""
    delivery = arc.classify_delivery(
        200, {"message": "I found 0 results for your search.",
              "provider": "template", "model": "template"},
        None, [], "control_unrelated_source")
    assert delivery["outcome"] == "template_fallback"
    assert delivery["stage_failed"] == "final_generation"
    quality = arc.aggregate_quality(delivery, [])
    assert quality["outcome"] == "not_evaluated"


def test_provider_failure_with_no_steps_records_absence_of_evidence():
    delivery = arc.classify_delivery(
        200, {"message": "[Error: All LLM providers failed.]"}, None, [], "quote")
    assert delivery["stage_failed"] == "final_generation"
    assert set(delivery["stages_unevidenced"]) == {"planning", "retrieval",
                                                   "derivation"}


def test_answered_case_is_scored_on_criteria():
    criteria = _run("quote", CORRECT_QUOTE_REPLY, _quote_evidence())
    quality = arc.aggregate_quality({"outcome": "answered"}, criteria)
    assert quality["outcome"] == "pass"
    assert quality["failing_stage"] == []
    bad = arc.aggregate_quality({"outcome": "answered"},
                                _run("quote", KEYWORD_ONLY_QUOTE_REPLY,
                                     _quote_evidence()))
    assert bad["outcome"] == "fail"
    assert set(bad["failing_stage"]) == {"retrieval"}


def test_carrier_index_key_is_order_independent():
    assert arc.carrier_key("PRICE VIPUL (6).xlsx") == \
        arc.carrier_key("price-vipul(6).XLSX")
    assert "price" in arc.carrier_key("PRICE VIPUL (6).xlsx")


def test_message_match_reasons_requires_identity_not_a_name():
    msg = _vendor_message()
    assert arc.message_match_reasons("Seguin has a quote", msg) == []
    reasons = arc.message_match_reasons(
        "joelseguin@seguinmach.com wrote on Aug 26, 2026", msg)
    assert "sender+date" in reasons
    assert "sender_address" in reasons


def test_quote_candidates_require_a_currency_figure_in_context():
    """A bare '5350' digit run (a phone number) plus a stray '10' elsewhere must
    not make a message a candidate: the loose version matched 141 messages and
    turned "identifies the correct message" into "matched one of many"."""
    spec = {"figure": "5350", "phrases": ["in stock", "10"]}
    noise = arc.StoredMessage(
        message_id="A" * 40,
        sender="someone@example.com",
        recipients=["chandrakant@brennan.ca"],
        subject="Unrelated",
        timestamp="2026-07-01 09:00:00",
        text=("Call me on +1-519-802-5350. We shipped 10 units last week "
              "and the pallet is in stock at the warehouse."),
    )
    real = _vendor_message()
    ev = arc.EvidenceBundle(our_domains=["brennan.ca"],
                            messages={noise.message_id: noise,
                                      real.message_id: real})
    candidates = arc._quote_candidates(ev, spec)
    assert [m.message_id for m in candidates] == [real.message_id]


def test_direction_claims_marks_negation():
    claims = arc.direction_claims(
        "It was not sent to a counterparty. We forwarded it to "
        "rish@brennan.ca internally.")
    negated = [c for c in claims if c["sent_negated"]]
    assert negated, claims
    assert any("not sent" in c["clause"] for c in negated)


def test_own_domain_resolution_from_traffic():
    records = []
    for i in range(30):
        records.append({"sender": "chandrakant@brennan.ca",
                        "recipient": f"vendor{i}@example{i}.com"})
    for i in range(30):
        records.append({"sender": f"vendor{i}@example{i}.com",
                        "recipient": "chandrakant@brennan.ca"})
    records.append({"sender": "rish@brennan.ca", "recipient": "vipul@brennan.ca"})
    assert arc._resolve_our_domains(records)[0] == "brennan.ca"


def test_every_case_declares_only_implemented_criteria():
    for case in arc.CASES:
        assert case["criteria"], case["key"]
        for name in case["criteria"]:
            assert name in arc.FAILING_STAGE_BY_CRITERION, name
