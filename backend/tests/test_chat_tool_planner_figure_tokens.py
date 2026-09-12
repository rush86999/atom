"""Figure-token recall for mailbox search (live 2026-09-12, Seguin
vendor-cost incident): the user asked for the email quoting
'$ 5,350.00 – 10 %  in stock'. Every search leg shredded the amount into
noise or 400'd, while the email sat in BOTH the mailbox and the ingested
communications store. These tests pin the three new recall mechanisms:

1. _distinctive_figure_phrases — exact-form amounts/codes out of raw query
   text ('$ 5,350.00' → '5,350.00');
2. _match_rows_by_figure_tokens — separator-insensitive canonical match
   over ingested comms rows (subject/content/html body);
3. the figure leg LEADS _ingested_mailbox_lines and cannot be crowded out
   of the cap by address lines.
"""

import asyncio
import json

import pytest

import core.chat_tool_planner as planner
from core.chat_tool_planner import (
    _distinctive_figure_phrases,
    _ingested_mailbox_lines,
    _match_rows_by_figure_tokens,
)


# --- phrase extraction ------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        # The exact incident query: amount only, $ dropped for matching both
        # '$5,350.00' and '5,350.00' bodies.
        ("search for this one: $ 5,350.00 – 10 %  in stock", ["5,350.00"]),
        ("find the email for F-5216 original cost", ["F-5216"]),
        ('joelseguin@seguinmach.com "$5,350.00"', ["5,350.00"]),
        # Space-separated thousands (French-Canadian style) count too.
        ("he quoted 10 000 for the machine", ["10 000"]),
        # Small bare numbers are not distinctive evidence.
        ("$100 or best offer", []),
        ("", []),
        (None, []),
    ],
)
def test_distinctive_figure_phrases(text, expected):
    assert _distinctive_figure_phrases(text) == expected


def test_distinctive_figure_phrases_respects_limit():
    text = "F-5216 at 5,350.00 and WG350DSAV too"
    assert _distinctive_figure_phrases(text, limit=2) == ["5,350.00", "F-5216"]


# --- canonical row matching -------------------------------------------------


def _row(sender, subject, content, ts, html=None):
    meta = {"html_body": html} if html else None
    return {
        "sender": sender,
        "recipient": "someone@brennan.ca",
        "subject": subject,
        "content": content,
        "timestamp": ts,
        "metadata": json.dumps(meta) if meta is not None else None,
    }


FW_ROW = _row(
    "joelseguin@seguinmach.com",
    "FW: RFQ - Foot shear",
    "$ 5,350.00 – 10 %  in stock Do you prefer a used shear ?",
    "2026-08-26 14:06:28",
)
RE_ROW = _row(
    "joelseguin@seguinmach.com",
    "RE: RFQ - Foot shear",
    "NEW in Canadian dollars",
    "2026-08-26 14:42:04",
    html="<div>quoted $5,350.00 net</div>",
)
OLD_ROW = _row(
    "chandrakant@brennan.ca",
    "RFQ - Shear",
    "older thread, no figure",
    "2026-07-22 13:36:00",
)


def test_match_rows_separator_insensitive():
    hits = _match_rows_by_figure_tokens(
        [OLD_ROW, FW_ROW], ["5,350.00"]
    )
    assert [h["subject"] for h in hits] == ["FW: RFQ - Foot shear"]


def test_match_rows_html_body_counts():
    # The figure only lives in metadata.html_body (styled original).
    hits = _match_rows_by_figure_tokens([RE_ROW, OLD_ROW], ["5,350.00"])
    assert [h["subject"] for h in hits] == ["RE: RFQ - Foot shear"]


def test_match_rows_requires_every_token():
    both = _row(
        "joelseguin@seguinmach.com",
        "RE: both",
        "F-5216 for 5,350.00",
        "2026-08-26 15:17:27",
    )
    assert _match_rows_by_figure_tokens([FW_ROW], ["5,350.00", "F-5216"]) == []
    assert [h["subject"] for h in _match_rows_by_figure_tokens(
        [FW_ROW, both], ["5,350.00", "F-5216"]
    )] == ["RE: both"]


def test_match_rows_newest_first_and_limit():
    rows = [RE_ROW, OLD_ROW, FW_ROW]
    assert [h["timestamp"] for h in _match_rows_by_figure_tokens(rows, ["5,350.00"])] == [
        "2026-08-26 14:42:04",
        "2026-08-26 14:06:28",
    ]
    assert len(_match_rows_by_figure_tokens(rows, ["5,350.00"], limit=1)) == 1


def test_match_rows_tiny_tokens_rejected():
    assert _match_rows_by_figure_tokens([FW_ROW], ["10", "%"]) == []


def test_match_rows_tolerates_broken_metadata():
    row = dict(FW_ROW, metadata="{not json")
    assert _match_rows_by_figure_tokens([row], ["5,350.00"])


# --- mailbox-lines wiring: the figure leg LEADS -----------------------------


def test_figure_lines_lead_and_survive_address_flood(monkeypatch):
    """The incident shape: an address in the query floods the address scan
    with old thread lines; the amount match must still lead the listing."""
    fig_calls, addr_calls = [], []

    def fake_tokens(user_id, tokens, limit=4):
        fig_calls.append(tokens)
        return ["- [ingested mailbox] From: joelseguin@seguinmach.com | FW: RFQ - Foot shear"]

    def fake_address(user_id, address, limit=4):
        addr_calls.append(address)
        return ["- [ingested mailbox] old thread line"] * 6

    monkeypatch.setattr(planner, "_search_ingested_by_tokens", fake_tokens)
    monkeypatch.setattr(planner, "_search_ingested_by_address", fake_address)

    lines = asyncio.run(
        _ingested_mailbox_lines(
            "u1", 'joelseguin@seguinmach.com "$ 5,350.00"', {"history": []}
        )
    )

    assert fig_calls == [["5,350.00"]]
    assert lines[0].endswith("FW: RFQ - Foot shear"), lines
    assert lines[1:] == ["- [ingested mailbox] old thread line"]
    assert addr_calls, "address leg still runs for thread context"


def test_figure_leg_skipped_without_distinctive_tokens(monkeypatch):
    def boom_tokens(user_id, tokens, limit=4):
        raise AssertionError("token scan must not run for non-figure queries")

    monkeypatch.setattr(planner, "_search_ingested_by_tokens", boom_tokens)

    lines = asyncio.run(
        _ingested_mailbox_lines("u1", "foot shear quote", {"history": []})
    )
    assert isinstance(lines, list)


def test_figure_scan_runs_off_loop(monkeypatch):
    """Same rule as the address scan: a ~4s table walk must not stall the
    event loop."""
    import time

    def slow_tokens(user_id, tokens, limit=4):
        time.sleep(0.3)
        return ["- [ingested mailbox] figure hit"]

    monkeypatch.setattr(planner, "_search_ingested_by_tokens", slow_tokens)

    async def harness():
        ticks = []
        stop = False

        async def tick():
            nonlocal stop
            while not stop:
                ticks.append(time.monotonic())
                await asyncio.sleep(0.02)

        ticker = asyncio.create_task(tick())
        lines = await _ingested_mailbox_lines("u1", "$ 5,350.00", {"history": []})
        stop = True
        await ticker
        return lines, ticks

    lines, ticks = asyncio.run(harness())
    assert lines
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert max(gaps) < 0.4, f"event loop stalled {max(gaps):.2f}s during figure scan"
