# -*- coding: utf-8 -*-
"""The mailbox evidence choke point grips more than figures.

Live 2026-09-14 (canvas a1a13834, third wave — same root-cause family,
different surface): "find the email that said: put 25 percent only" got
closest-match noise instead of the row that VERBATIM contains the phrase,
and "check the email thread chandrakant forwarded to me about how list
price was calculated for the foot shear" found nothing because the
planner's query dropped the only deterministic handle ("chandrakant")
and no lane grips a participant NAME: grep needs verbatim strings, the
address lane needs x@y.z, figure lanes need amounts.

`_verbatim_mail_evidence` (the orchestrator-level evidence that LEADS the
tool block regardless of what the planner chose) now resolves, in order:
distinctive figures → quoted phrases (verbatim containment) → participant
names (matched against the store's OWN sender/recipient strings — no
name-entity guessing). All mocked — zero network, zero live DB.
"""
import asyncio
from unittest.mock import patch

import pytest

import core.chat_tool_planner as ctp
import integrations.chat_orchestrator as co


def _rows(*specs):
    out = []
    for i, (sender, recipient, subject, content, ts) in enumerate(specs):
        out.append({
            "id": f"m{i}", "sender": sender, "recipient": recipient,
            "subject": subject, "content": content, "timestamp": ts,
            "metadata": "",
        })
    return out


STORE = _rows(
    # The turn-7 thread: participant-named, conceptually worded, code-filed.
    ("chandrakant@brennan.ca", "rish@brennan.ca",
     "Re: Brake, Shear and Lock Former",
     "52T 81020 Tennsmith list derived from cost $8,880 plus freight.",
     "2026-08-20T14:00:00"),
    # The turn-6 phrase row: verbatim "put 25 percent only" inside a thread.
    ("chandrakant@brennan.ca", "rish@brennan.ca",
     "Fw: RFQ - Foot shear",
     "Vipul wrote: put 25 percent only on the Seguin machine.",
     "2026-09-11T09:00:00"),
    # Same participant, unrelated traffic (must NOT outrank the foot-shear
    # rows for the turn-7 ask despite being newer).
    ("chandrakant@brennan.ca", "rish@brennan.ca",
     "Kitchen renovation photos",
     "check out these tiles",
     "2026-09-13T10:00:00"),
    # Different participant entirely.
    ("joelseguin@seguinmach.com", "rish@brennan.ca",
     "FW: RFQ - Foot shear",
     "$ 5,350.00 - 10 % in stock",
     "2026-08-26T14:06:00"),
)


@pytest.fixture(autouse=True)
def _fake_store(monkeypatch):
    import core.chat_tool_planner as ctp

    monkeypatch.setattr(ctp, "_comms_store_records", lambda: STORE)
    # The figure leg's renderer is irrelevant to these cases (no figures);
    # keep it from touching anything else.
    monkeypatch.setattr(ctp, "_distinctive_figure_phrases", lambda *a, **k: [])
    monkeypatch.setattr(ctp, "_latest_user_figure_phrases", lambda *a, **k: [])


class TestParticipantLeg:
    def test_participant_rows_ranked_by_topic_overlap_then_newest(self):
        rows = co._participant_mail_rows(
            "check the email thread chandrakant forwarded to me about how "
            "list price was calculated for the foot shear")
        assert rows, "expected the participant lane to fire"
        senders = {r["sender"] for r in rows}
        assert senders == {"chandrakant@brennan.ca"}
        # Both foot-shear-adjacent threads surface (the model reads both and
        # picks the list-price one); the NEWER UNRELATED thread does not.
        subjects = {r["subject"] for r in rows}
        assert "Re: Brake, Shear and Lock Former" in subjects
        assert "Fw: RFQ - Foot shear" in subjects
        assert "Kitchen renovation photos" not in subjects

    def test_role_addresses_never_become_participants(self):
        rows = co._participant_mail_rows(
            "show me what sales sent about the shear")
        assert rows == []

    def test_unknown_name_fires_nothing(self):
        assert co._participant_mail_rows(
            "check the thread bernhard forwarded about shears") == []


class TestVerbatimEvidenceLegs:
    @pytest.mark.asyncio
    async def test_quoted_phrase_leads_the_evidence(self):
        lines = await co._verbatim_mail_evidence(
            "find the email that said: put 25 percent only", "u1", None)
        assert any("Fw: RFQ - Foot shear" in l for l in lines), lines
        # The verbatim phrase row leads.
        assert "Fw: RFQ - Foot shear" in lines[0]

    @pytest.mark.asyncio
    async def test_participant_ask_surfaces_the_thread(self):
        lines = await co._verbatim_mail_evidence(
            "check the email thread chandrakant forwarded to me about how "
            "list price was calculated for the foot shear and reverse "
            "engineer the calculation and show it to me", "u1", None)
        assert lines, "expected participant evidence"
        assert any("Brake, Shear and Lock Former" in l for l in lines), lines

    @pytest.mark.asyncio
    async def test_no_handles_returns_empty(self):
        lines = await co._verbatim_mail_evidence(
            "what is the capital of France", "u1", None)
        assert lines == []

class TestComposerMailLed:
    def test_participant_referent_ask_is_mail_led(self):
        # "check the email thread chandrakant forwarded …" has no quoted
        # span, but it points at a MESSAGE. The composer must lead with the
        # mailbox bodies (live 2026-09-15: demoting them to caveat-wrapped
        # "HISTORICAL CORRESPONDENCE" produced "I found 0 results" from the
        # pinned fallback, which read only the empty live block).
        mail = ["- [ingested mailbox] From: chandrakant@brennan.ca | Re: "
                "Brake, Shear and Lock Former. | FULL BODY:\ncost $8,880 "
                "plus freight and margin = list"]
        live = "LIVE TOOL RESULTS (documents.search): returned nothing usable"
        out = co._compose_lookup_evidence(
            "check the email thread chandrakant forwarded to me about how "
            "list price was calculated for the foot shear and reverse "
            "engineer the calculation and show it to me",
            None, live, mail)
        assert out.startswith("LIVE TOOL RESULTS (ingested mailbox")
        assert "FULL MESSAGE BODIES" in out
        assert mail[0] in out
        # the live block is retained as the trailing note, not the lead
        assert out.index(mail[0]) < out.index(live)

    def test_quote_lookup_still_mail_led(self):
        mail = ["- [ingested mailbox] line"]
        out = co._compose_lookup_evidence(
            "search for this one: $ 5,350.00 - 10 % in stock",
            None, "LIVEBLOCK", mail)
        assert out.startswith("LIVE TOOL RESULTS (ingested mailbox")
        assert "LIVEBLOCK" in out

class TestStatedDateWindow:
    def test_slash_date_with_weekday_parses(self):
        import datetime
        today = datetime.date(2026, 9, 14)  # Monday
        assert ctp._stated_date_window(
            "find the email thread for f-5216. it was sent to me on 9/11 friday",
            today=today,
        ) == ("2026-09-11 00:00:00", "2026-09-12 00:00:00")

    def test_month_name_and_weekday_forms(self):
        import datetime
        today = datetime.date(2026, 9, 14)
        assert ctp._stated_date_window(
            "the email from september 11", today=today
        ) == ("2026-09-11 00:00:00", "2026-09-12 00:00:00")
        assert ctp._stated_date_window("sent friday", today=today) == (
            "2026-09-11 00:00:00", "2026-09-12 00:00:00")

    def test_dimension_fractions_are_not_dates(self):
        # '7/8-inch' without any day-word context must not become July 8.
        import datetime
        today = datetime.date(2026, 9, 14)
        assert ctp._stated_date_window(
            "check the 7/8-inch port spec", today=today) is None

    def test_date_window_tiers_matches(self):
        # Live shape: 'F-5216' matches 17 stored rows; the Sep 11 pair the
        # user pointed at lost the newest-3 cap to Sep 14 traffic. The
        # stated-date tier must lead with them.
        rows = [
            {"id": "m1", "sender": "a@x.ca", "recipient": "r@brennan.ca",
             "subject": "old thread", "content": "F-5216 mentioned",
             "timestamp": "2026-08-26 15:50:00", "metadata": ""},
            {"id": "m2", "sender": "chandrakant@brennan.ca",
             "recipient": "r@brennan.ca",
             "subject": "Re: 52 Inch 16 Gauge Foot Shear",
             "content": "F-5216 alternative, 2-3 weeks",
             "timestamp": "2026-09-11 19:21:00", "metadata": ""},
            {"id": "m3", "sender": "kurt@neimanmachinery.com",
             "recipient": "r@brennan.ca",
             "subject": "RE: 52 Inch 16 Gauge Foot Shear",
             "content": "F-5216 hydraulic?",
             "timestamp": "2026-09-11 20:36:00", "metadata": ""},
            {"id": "m4", "sender": "chandrakant@brennan.ca",
             "recipient": "r@brennan.ca",
             "subject": "Re: Brake, Shear and Lock Former.",
             "content": "F-5216 at 7519", "timestamp": "2026-09-14 15:38:00",
             "metadata": ""},
        ]
        out = ctp._match_rows_by_figure_tokens(
            rows, ["F-5216"], limit=3,
            date_window=("2026-09-11 00:00:00", "2026-09-12 00:00:00"))
        ids = [r["id"] for r in out]
        # In-window rows lead (newest first); the cap then keeps the newer
        # out-of-window thread — the Aug 26 row is correctly dropped.
        assert ids == ["m3", "m2", "m4"], ids
