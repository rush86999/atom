# -*- coding: utf-8 -*-
"""Which message carried the file — ranked by how informative the match is.

Acceptance case 2 ("which emails did we send that carried the PRICE VIPUL price
list as an attachment?") failed with "none of the ingested mailbox records show
a sent email carrying a PRICE VIPUL price list attachment" while the store held
exactly one carrier. Measured cause: `_messages_carrying_file` collected every
attachment name sharing >= 2 tokens with the query and took the first `limit`
in DICT ITERATION ORDER. The query's tokens are {price, vipul, list}; every
vendor price list in the store shares {price, list}, two of them came first, and
the real carrier — the only name sharing "vipul", the decisive token — was cut
before it was ever rendered.

The rule these tests pin: a shared token that appears in ONE attachment name
discriminates; one that appears in fifty does not, so overlap is weighted by
1/df and the most informative match wins.
"""
from typing import Dict, List

import pytest

import core.chat_tool_planner as planner


@pytest.fixture()
def store(monkeypatch):
    """A fake attachment ledger shaped like the live one."""
    carrier_msg = "msg-carrier"
    reverse: Dict[str, List[tuple]] = {
        "HARSLE press brake stock price list.xlsx": [("msg-harsle", "doc-h")],
        "Tennsmith Inc. Price List TNS-059.docx": [("msg-tenn", "doc-t")],
        "PRICE VIPUL (6).xlsx": [(carrier_msg, "doc-v")],
        "New Vendor Request Form_External.xlsx": [("msg-form", "doc-f")],
    }
    rows = [
        {"id": "msg-harsle", "sender": "sales06@harsle.com",
         "recipient": "rish@brennan.ca", "subject": "In-Stock Press Brakes"},
        {"id": "msg-tenn", "sender": "jchampion@brennan.ca",
         "recipient": "rish@brennan.ca", "subject": "Tennsmith price list"},
        {"id": carrier_msg, "sender": "chandrakant@brennan.ca",
         "recipient": "rish@brennan.ca", "subject": "Fw: RFQ - Foot shear"},
        {"id": "msg-form", "sender": "x@y.example",
         "recipient": "rish@brennan.ca", "subject": "form"},
    ]
    monkeypatch.setattr(planner, "_mail_attachment_reverse_index",
                        lambda: reverse)
    monkeypatch.setattr(planner, "_comms_store_records", lambda: rows)
    monkeypatch.setattr(planner, "_ingested_line_from_row",
                        lambda row, **kw: (
                            f"- [ingested mailbox] From: {row['sender']} | "
                            f"To: {row['recipient']} | {row['subject']}"))
    return carrier_msg


class TestCarrierRanking:
    def test_the_decisive_token_wins_over_generic_ones(self, store):
        out = planner._messages_carrying_file(
            "PRICE VIPUL price list",
            "which emails did we send that carried the PRICE VIPUL price list "
            "as an attachment?")
        assert out, "no carrier was returned at all"
        assert "chandrakant@brennan.ca" in out[0], (
            "the generic {price,list} matches outranked the carrier that also "
            f"shares 'vipul': {out}")

    def test_the_full_question_as_a_name_still_finds_the_carrier(self, store):
        out = planner._messages_carrying_file(
            "the PRICE VIPUL price list as an attachment", "")
        assert out and "chandrakant@brennan.ca" in out[0]

    def test_an_exact_name_still_wins(self, store):
        out = planner._messages_carrying_file("PRICE VIPUL (6).xlsx", "")
        assert out and "chandrakant@brennan.ca" in out[0]

    def test_a_generic_query_alone_is_not_a_match(self, store):
        """'price list' shares {price,list} with several names and no decisive
        token — it must not claim a specific carrier as THE answer."""
        out = planner._messages_carrying_file("price list", "")
        assert not out or "vipul" not in out[0].lower()

    def test_unrelated_queries_return_nothing(self, store):
        assert planner._messages_carrying_file(
            "quarterly compliance certificate", "") == []


class TestAttachmentAskDetector:
    """The carrier join is deterministic for asks that are ABOUT a carried
    file — it must not depend on the planner choosing a dataset lane."""

    @pytest.mark.parametrize("message,expected", [
        ("which emails did we send that carried the PRICE VIPUL price list "
         "as an attachment?", True),
        ("what was in the workbook you sent me?", True),
        ("open the attached price list", True),
        ("summarise the forwarded quote", True),
        ("what is the list price of the F-9999 press?", False),
        ("how was the 7519 price derived?", False),
        ("", False),
    ])
    def test_detector(self, message, expected):
        from integrations.chat_orchestrator import _mentions_attachment

        assert _mentions_attachment(message) is expected
