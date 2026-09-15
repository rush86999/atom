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
