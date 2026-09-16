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
        # Currency/locale generality: ISO code before or after, EU decimal
        # convention, space-grouped thousands, Indian lakh/crore grouping.
        ("the invoice was CAD 7,200.50 all in", ["7,200.50"]),
        ("il a payé 5.350,00 EUR pour la machine", ["5.350,00"]),
        ("10 000 CAD for the pallet", ["10 000"]),
        ("quote ₹1,00,000 for the line", ["1,00,000"]),
        ("total 1,00,00,000 INR approved", ["1,00,00,000"]),
        ("£2,500 deposit received", ["2,500"]),
        ("1,234,567 annual revenue", ["1,234,567"]),
        # Identifier shapes across industries: underscored, slashed codes.
        ("find SAE_5216 washer stock", ["SAE_5216"]),
        ("part 1/2NPT fitting leak", ["1/2NPT"]),
        ("case CV-2026-1234 status", ["CV-2026-1234"]),
        # Small bare numbers are not distinctive evidence.
        ("$100 or best offer", []),
        ("", []),
        (None, []),
        # ─── False-positive screens (2026-09-13 review) ───────────────────
        # Phone numbers in every grouping style must NOT become figure
        # tokens — a 13-char phone phrase used to outrank genuine term hits
        # (boost=len(phrase)) and zero out the ALL-tokens store scan.
        ("call +1 555 123 4567 today", []),
        ("phone 555.123.4567 after lunch", []),
        ("dial 1,555,123,4567 please", []),
        ("fax (555) 123-4567 ok", []),
        # Space-grouped runs WITHOUT a currency signal: quantities, plain
        # grouped numbers, dates.
        ("10 000 units shipped", []),
        ("12 345", []),
        ("meeting 10 06 2026 confirmed", []),
        ("date 2026.09.13 review", []),
        ("September 13, 2026 minutes", []),
        # Document-structure contexts: version/section numbers are labels,
        # not amounts.
        ("version 1.234 deployed", []),
        ("section 3.456 amended", []),
        ("see rev 2.345 notes", []),
        ("per clause 4.567 of the agreement", []),
        # The SAME shapes WITH a currency signal stay figure tokens.
        ("total 5.350,00 EUR payable", ["5.350,00"]),
    ],
)
def test_distinctive_figure_phrases(text, expected):
    assert _distinctive_figure_phrases(text) == expected


def test_figure_phrase_limit_is_one_constant():
    """P1-2: ONE figure-phrase limit across every consumer (the collect /
    resolve ladder capped at 2 while the store scan capped at 3)."""
    assert planner._FIGURE_PHRASE_LIMIT == 3
    text = "5,350.00 plus 7,200.50 plus 9,100.25 plus F-5216"
    assert _distinctive_figure_phrases(text) == ["5,350.00", "7,200.50", "9,100.25"]


def test_phrase_boost_is_capped():
    """P1-2: rank boost capped — a long junk capture must not outrank
    genuine term hits via boost=len(phrase)."""
    assert planner._PHRASE_BOOST_CAP <= 12
    import inspect

    src = inspect.getsource(planner)
    assert "boost=min(len(phrase), _PHRASE_BOOST_CAP)" in src


def test_distinctive_figure_phrases_respects_limit():
    text = "F-5216 at 5,350.00 and WG350DSAV too"
    assert _distinctive_figure_phrases(text, limit=2) == ["5,350.00", "F-5216"]


# --- canonical row matching -------------------------------------------------


def _row(sender, subject, content, ts, html=None, row_id="msg-1"):
    meta = {"html_body": html} if html else None
    return {
        "id": row_id,
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


def test_match_rows_cross_locale_amount_forms():
    """EU-form query must match a US-form row (and vice versa): the
    canonical form strips every separator, so '5.350,00' (de-DE),
    '5,350.00' (en-CA) and '$ 5 350,00' all land on '535000'."""
    eu_row = _row(
        "vendor@eu-supplier.example",
        "Angebot Maschine",
        "Unser Preis: 5.350,00 EUR netto",
        "2026-08-26 10:00:00",
    )
    assert _match_rows_by_figure_tokens([eu_row], ["5,350.00"])
    assert _match_rows_by_figure_tokens([FW_ROW], ["5.350,00"])
    assert _match_rows_by_figure_tokens([eu_row], ["5 350,00"])


def test_match_rows_indian_grouping():
    in_row = _row(
        "sales@india-supplier.example",
        "Quotation",
        "Total amount Rs. 1,00,000 inclusive of GST",
        "2026-08-26 10:00:00",
    )
    assert _match_rows_by_figure_tokens([in_row], ["1,00,000"])


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

    def fake_tokens(user_id, tokens, limit=4, date_window=None):
        fig_calls.append(tokens)
        return ["- [ingested mailbox] From: joelseguin@seguinmach.com | FW: RFQ - Foot shear"]

    def fake_address(user_id, address, limit=4, query=""):
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
    def boom_tokens(user_id, tokens, limit=4, date_window=None):
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

    def slow_tokens(user_id, tokens, limit=4, date_window=None):
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


def test_mailbox_figure_lines_window_comes_from_current_message(monkeypatch):
    """The stated-date window must flow from the CURRENT message — the
    planner query rewrite keeps the code but drops the date, and session
    history lags the turn (it is written only after the response), so the
    context message key is what carries it."""
    seen = {}

    def fake_tokens(user_id, tokens, limit=4, date_window=None):
        seen["tokens"] = tokens
        seen["window"] = date_window
        return []

    monkeypatch.setattr(planner, "_search_ingested_by_tokens", fake_tokens)
    msg = "find the email thread for f-5216. it was sent to me on 9/11 friday"
    asyncio.run(planner._mailbox_figure_lines(
        "u1", "F-5216 quote", {"message": msg, "history": []}))
    assert seen["tokens"], "figure leg ran"
    assert seen["window"] == planner._stated_date_window(msg)
    assert seen["window"] is not None


def test_ingested_mailbox_lines_threads_stated_date_window(monkeypatch):
    """Same tier handle on the mailbox-shaped search lane: the figure-token
    calls carry the window, not just the memory lane."""
    seen = {}

    def fake_tokens(user_id, tokens, limit=4, date_window=None):
        seen["window"] = date_window
        return [f"- [ingested mailbox] F-5216 hit {i}" for i in range(6)]

    def fake_address(user_id, address, limit=4, query=""):
        raise AssertionError("figure lines filled the cap — no table walk")

    monkeypatch.setattr(planner, "_search_ingested_by_tokens", fake_tokens)
    monkeypatch.setattr(planner, "_search_ingested_by_address", fake_address)
    msg = "find the email thread for f-5216. it was sent to me on 9/11 friday"
    lines = asyncio.run(_ingested_mailbox_lines(
        "u1", "F-5216 quote", {"message": msg, "history": []}))
    assert len(lines) == 6, "cap filled by figure lines alone"
    assert seen["window"] == planner._stated_date_window(msg)
    assert seen["window"] is not None


# --- P2-8: ONE comms-table load per turn (shared, TTL-cached, invalidable) ---


def test_comms_store_loaded_once_and_invalidated_on_write(monkeypatch):
    """A single outlook search used to full-table-load atom_communications
    3-5 times per turn (~4s each at 3.5k rows). The shared loader must
    serve repeat loads from cache within the TTL and reload after the
    planner writes (invalidate_comms_store_cache)."""
    import lancedb as _ldb
    import pandas as pd

    connects = []

    class _FakeArrow:
        def __init__(self, rows):
            self._rows = rows

        def to_pandas(self):
            return pd.DataFrame(self._rows)

    class _FakeTable:
        def __init__(self, rows):
            self._rows = rows

        def to_arrow(self):
            return _FakeArrow(self._rows)

    class _FakeDB:
        def open_table(self, name):
            assert name == "atom_communications"
            return _FakeTable(_ROWS)

    _ROWS = [{
        "sender": "a@b.c", "recipient": "d@e.f", "subject": "s",
        "content": "body 5,350.00", "timestamp": "2026-08-26",
        "metadata": None,
    }]

    def fake_connect(path):
        connects.append(path)
        return _FakeDB()

    monkeypatch.setattr(_ldb, "connect", fake_connect)
    planner.invalidate_comms_store_cache()

    first = planner._comms_store_records()
    second = planner._comms_store_records()
    assert first is second
    assert len(connects) == 1, "repeat loads within the TTL must not re-walk the store"

    # The store path is resolved through the ONE resolver (P3-14), not a
    # hand-rolled Path(__file__) guess.
    import core.lancedb_handler as _lh

    assert planner._comms_store_db_path() == str(
        _lh._resolve_local_db_path("./data/atom_memory") + "/default"
    ) or planner._comms_store_db_path().endswith("atom_memory/default")

    planner.invalidate_comms_store_cache()
    planner._comms_store_records()
    assert len(connects) == 2, "invalidation (post-ingest re-read) must reload"
    planner.invalidate_comms_store_cache()


# --- canonical matching stays SEPARATOR-INSENSITIVE -------------------------
#
# `_canon_find` anchors digit edges so '$53,500.00' (canonical '5350000')
# cannot pass for the '$5,350.00' token ('535000') — the July Seguin 10'
# shear quote took a full-body slot that way. The first cut of that guard
# searched the RAW token ('5,350.00') in the canonical haystack, which
# silently re-broke the separator-insensitivity this whole leg exists for:
# a comma-grouped token can never match a body that renders '5 350.00' /
# '5.350,00' / an ungrouped '5350.00'. These pin both halves.


def test_grouped_token_matches_space_grouped_body():
    """en-CA token form must still match the fr-CA space-grouped render."""
    row = _row(
        "joelseguin@seguinmach.com",
        "FW: RFQ - Foot shear",
        "$ 5 350.00 – 10 %  in stock",
        "2026-08-26 14:06:28",
    )
    assert [h["subject"] for h in _match_rows_by_figure_tokens([row], ["5,350.00"])] == [
        "FW: RFQ - Foot shear"
    ]


def test_grouped_token_matches_ungrouped_body():
    """A body that drops the grouping entirely ('5350.00') still matches."""
    row = _row("vendor@x.example", "Quote", "net 5350.00 CAD", "2026-08-26 10:00:00")
    assert [h["subject"] for h in _match_rows_by_figure_tokens([row], ["5,350.00"])] == [
        "Quote"
    ]


def test_longer_amount_is_not_the_token():
    """$53,500.00 canonicalizes to '5350000'. The '5,350.00' token is a
    prefix of it, so containment alone re-admits the wrong machine."""
    bigger = _row(
        "joelseguin@seguinmach.com",
        "RE: RFQ - Shear",
        "The only one we have is a new 10' x 1/4'' on 600 V & 53,500.00 made in China",
        "2026-07-22 13:36:00",
    )
    assert _match_rows_by_figure_tokens([bigger], ["5,350.00"]) == []


def test_field_boundary_does_not_create_a_digit_run():
    """Subject and body are separate fields. A subject ending in a digit
    must not fuse with a body starting in one and hide a real match from
    the digit-boundary guard."""
    row = _row("vendor@x.example", "Quote 52", "5350.00 net", "2026-08-26 10:00:00")
    assert _match_rows_by_figure_tokens([row], ["5,350.00"])


def test_own_text_tier_outranks_newer_quoting_reply():
    """The incident shape: a newer reply that merely QUOTES the amount (it
    sits deep under signature/tracking-URL goo) must not displace the
    original message whose body states the amount up front."""
    original = _row(
        "joelseguin@seguinmach.com",
        "FW: RFQ - Foot shear",
        "$ 5,350.00 – 10 %  in stock",
        "2026-08-26 14:06:28",
    )
    quoting_reply = _row(
        "chandrakant@brennan.ca",
        "Re: RFQ - Foot shear",
        "thanks, checking" + (" see our site " * 80) + " quoted was 5,350.00",
        "2026-08-26 14:58:34",
    )
    hits = _match_rows_by_figure_tokens([quoting_reply, original], ["5,350.00"], limit=1)
    assert [h["subject"] for h in hits] == ["FW: RFQ - Foot shear"]


# --- matched figure must be VISIBLE in the rendered line --------------------


def test_truncated_line_shows_the_matched_figure():
    """A 260-char excerpt of a forward can cut before the quoted amount, so
    the model reads a 'match' that never shows the figure — the agent then
    reports the number 'isn't visible in what came back'."""
    row = _row(
        "chandrant@brennan.ca",
        "Fw: RFQ - Foot shear",
        "Please see the note below regarding the shear." + (" filler" * 60)
        + " Original message: $ 5,350.00 – 10 %  in stock",
        "2026-09-11 20:07:53",
    )
    line = planner._ingested_line_from_row(row, with_body=False, anchors=["5,350.00"])
    assert "5,350.00" in line, line


def test_full_body_line_shows_the_matched_figure():
    """Same guarantee for FULL BODY lines: the head/tail elision can drop
    the exact region the canonical scan matched."""
    row = _row(
        "chandrant@brennan.ca",
        "Fw: RFQ - Foot shear",
        "intro " + ("x" * 200) + " $ 5,350.00 – 10 %  in stock " + ("y" * 20000),
        "2026-09-11 20:07:53",
    )
    line = planner._ingested_line_from_row(row, with_body=True, anchors=["5,350.00"])
    assert "5,350.00" in line, line[:400]


def test_anchor_window_prefers_the_plain_copy_when_html_lacks_it():
    """The styled html_body can omit quoted text the plain content column
    carries — the window falls back to the content column."""
    row = _row(
        "joelseguin@seguinmach.com",
        "FW: RFQ - Foot shear",
        "Proceed as follows:" + (" z" * 400) + " price $ 5,350.00 net",
        "2026-08-26 14:06:28",
        html="<div>Proceed as follows: " + ("z " * 400) + "</div>",
    )
    line = planner._ingested_line_from_row(row, with_body=True, anchors=["5,350.00"])
    assert "5,350.00" in line, line[:400]


# --- memory.search lane needs the SAME deterministic figure leg -------------
#
# The 2026-09-13 live incident: the planner routed 'search for this one:
# $ 5,350.00 – 10 % in stock' to memory.search (not outlook), where the
# only mailbox legs were the hybrid hit list (whose 8-line cap it shares
# with unrelated document hits) and an address scan — no figure-token leg
# at all — so the block came back empty and the agent said the email was
# never ingested. It was in the store the whole time.


def test_memory_block_surfaces_figure_from_the_query(monkeypatch):
    monkeypatch.setattr(
        planner, "_search_ingested_by_exact_token", lambda *a, **k: []
    )
    monkeypatch.setattr(planner, "_datasets_evidence", _no_datasets)
    monkeypatch.setattr(
        planner, "_search_ingested_by_tokens", _fake_fig_lines
    )

    block = asyncio.run(
        planner._memory_search_block(
            "u1",
            "search for this one: $ 5,350.00 – 10 %  in stock",
            {"history": []},
        )
    )
    assert block, "the mailbox figure leg must be consulted on the memory lane"
    assert "5,350.00" in block


def test_memory_block_inherits_figure_from_last_user_turn(monkeypatch):
    """'try the search again' carries no amount of its own — the leg must
    inherit it from the most recent USER turn (assistant echoes name stale
    amounts like the $7,519 selling price)."""
    monkeypatch.setattr(
        planner, "_search_ingested_by_exact_token", lambda *a, **k: []
    )
    monkeypatch.setattr(planner, "_datasets_evidence", _no_datasets)
    monkeypatch.setattr(planner, "_search_ingested_by_tokens", _fake_fig_lines)

    block = asyncio.run(
        planner._memory_search_block(
            "u1",
            "try the search again",
            {"history": [
                {"role": "user", "content": "$ 5,350.00 – 10 % in stock"},
                {"role": "assistant", "content": "the quote was $7,519.00"},
            ]},
        )
    )
    assert block and "5,350.00" in block


def test_memory_block_figure_lines_are_not_crowded_out(monkeypatch):
    """Figure evidence ranks FIRST — the hybrid leg shares the 8-line cap
    and unrelated document hits must not push the amount out."""
    _patch_hybrid_search(monkeypatch, results=[])
    monkeypatch.setattr(
        planner, "_search_ingested_by_exact_token", lambda *a, **k: []
    )
    monkeypatch.setattr(planner, "_datasets_evidence", _no_datasets)
    monkeypatch.setattr(planner, "_search_ingested_by_tokens", _fake_fig_lines)

    block = asyncio.run(
        planner._memory_search_block("u1", "search: $ 5,350.00", {"history": []})
    )
    assert block, "the memory lane must return the figure evidence"
    lines = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert lines and "5,350.00" in lines[0], lines


def test_memory_hybrid_figure_leg_beats_hybrid_document_hits(monkeypatch):
    """The real incident had the block RETURNING, but full of unrelated
    document hits (CPO 350 specs) with the amount nowhere in it. Figure
    lines are prepended, so the cap can never cut them."""
    _patch_hybrid_search(
        monkeypatch,
        results=[{
            "id": "doc-1",
            "title": "CPO 350 AutoLoader.pdf",
            "source": "documents",
            "preview": "unrelated spec text",
        }],
    )
    monkeypatch.setattr(
        planner, "_search_ingested_by_exact_token", lambda *a, **k: []
    )
    monkeypatch.setattr(planner, "_datasets_evidence", _no_datasets)
    monkeypatch.setattr(planner, "_search_ingested_by_tokens", _fake_fig_lines)

    block = asyncio.run(
        planner._memory_search_block("u1", "search: $ 5,350.00", {"history": []})
    )
    assert block
    lines = [ln for ln in block.splitlines() if ln.startswith("- ")]
    assert lines, "the figure leg must contribute a line"
    # THE CONTRACT IS PLACEMENT, NOT COUNT. This asserted `len(lines) >= 2`,
    # which only held when the environment's ingested data happened to add
    # another line (the hybrid/attachment legs) — so it passed against a
    # populated store and failed on a fresh clone, where the figure line is the
    # only one. The property under test is that the figure line is PREPENDED and
    # therefore cannot be cut by the cap, no matter how many other lines exist.
    assert "5,350.00" in lines[0], lines
    # When the hybrid leg contributes a line, the figure line must precede it.
    # Conditional because a bare install (fresh clone, no documents table) has no
    # hybrid hits at all — asserting their presence would test the environment,
    # which is exactly what the old `len(lines) >= 2` did.
    if "unrelated spec text" in block:
        assert block.index("5,350.00") < block.index("unrelated spec text"), (
            "the figure line must come BEFORE unrelated document hits"
        )


def _patch_hybrid_search(monkeypatch, results):
    """Pin the vector/lexical hybrid leg (network + embeddings free) so the
    test exercises the figure leg's placement, not the embedder."""
    import core.hybrid_search.documents_hybrid as _dh

    class _Fake:
        async def search(self, *a, **k):
            return {"results": results}

    monkeypatch.setattr(_dh, "DocumentsHybridSearch", _Fake)


async def _no_datasets(*_a, **_k):
    return None


def _fake_fig_lines(user_id, tokens, limit=4, date_window=None):
    assert tokens, "the figure leg must receive the extracted amount"
    return ["- [ingested mailbox] From: joelseguin@seguinmach.com | FW: RFQ - Foot shear"
            " | received: 2026-08-26 14:06:28 | $ 5,350.00 – 10 % in stock"]


# ─── remaining coverage: helper units and pass-through wiring ─────────────


def test_latest_user_figure_phrases_shapes():
    """Direct unit pins for the history-referent helper: assistant echoes
    are skipped, session-shaped entries harvest only the user side, and
    figure-less histories yield nothing."""
    # Assistant echo carries the stale amount; the USER turn is older but
    # is the only side that counts.
    assert planner._latest_user_figure_phrases({"history": [
        {"role": "user", "content": "search for this one: $ 5,350.00 – 10 %  in stock"},
        {"role": "assistant", "content": "our own quote was $7,519.00"},
        {"role": "user", "content": "try the search again"},
    ]}) == ["5,350.00"]
    # Session shape {message, response}: the response is the assistant echo —
    # its figures must never be harvested, only the message side's.
    assert planner._latest_user_figure_phrases({"history": [
        {"message": "and the invoice?", "response": "nothing matching $9,100.25 found"},
        {"message": "try again", "response": "still nothing"},
    ]}) == []
    assert planner._latest_user_figure_phrases({}) == []
    assert planner._latest_user_figure_phrases({"history": [
        {"role": "user", "content": "no figures here"}]}) == []


def test_match_rows_recency_keeps_deciding_within_tier():
    """Tiering only lifts own-text matches; same-tier rows stay newest-first
    (recency still orders unrelated same-amount threads)."""
    a = _row("a@x.example", "Quote A", "$ 5,350.00 net", "2026-08-01 10:00:00")
    b = _row("b@x.example", "Quote B", "$ 5,350.00 net", "2026-08-02 10:00:00")
    assert [h["subject"] for h in _match_rows_by_figure_tokens(
        [a, b], ["5,350.00"])] == ["Quote B", "Quote A"]


def test_search_ingested_by_tokens_passes_anchors(monkeypatch):
    """The figure scan must hand its tokens to the line builder as anchors
    (the visibility guarantee), with full bodies for the top rows."""
    captured = {}

    def fake_line(row, with_body, anchors=None, body_cap=None):
        captured["anchors"] = anchors
        captured["with_body"] = with_body
        captured["body_cap"] = body_cap
        return "- [ingested mailbox] x"

    monkeypatch.setattr(planner, "_comms_store_records", lambda: [FW_ROW])
    monkeypatch.setattr(planner, "_ingested_line_from_row", fake_line)
    planner.invalidate_comms_store_cache()
    out = planner._search_ingested_by_tokens("u1", ["5,350.00"])
    assert out == ["- [ingested mailbox] x"]
    assert captured["anchors"] == ["5,350.00"]
    assert captured["with_body"] is True
    assert captured["body_cap"] == planner._INGESTED_BODY_CAP_FULL


def test_mailbox_lines_query_figure_wins_over_history(monkeypatch):
    """The current query's figure is the target; history never overrides
    it."""
    calls = []

    def fake_tokens(user_id, tokens, limit=4, date_window=None):
        calls.append(tokens)
        return []

    monkeypatch.setattr(planner, "_search_ingested_by_tokens", fake_tokens)
    asyncio.run(_ingested_mailbox_lines(
        "u1",
        "now search for the $9,100.25 invoice",
        {"history": [
            {"role": "user", "content": "earlier we looked at $ 5,350.00"},
        ]},
    ))
    assert calls == [["9,100.25"]]


def test_full_body_line_carries_attachments_footer():
    """The attachments footer lives only in the plain content column; the
    full-body line prefers the styled html_body, which drops it — losing the
    exact evidence that ties a quote to the machine (the '$ 5,350.00' email
    carries the Fintek F5216 spec-sheet .doc; the agent could name the price
    but 'couldn't confirm a spec sheet was attached')."""
    content = (
        "$ 5,350.00 – 10 %  in stock\n\nDo you prefer a used shear ?\n"
        + "quoted thread " * 300
        + "\n--- Attachments ---\n"
        "- 18896-99_Fintek F5216 Foot Shear (1).doc (application/msword / 1656740 bytes)"
    )
    row = _row(
        "joelseguin@seguinmach.com",
        "FW: RFQ - Foot shear",
        content,
        "2026-08-26 14:06:28",
        html="<div>$ 5,350.00 – 10 %  in stock Do you prefer a used shear ?</div>",
    )
    line = planner._ingested_line_from_row(row, with_body=True, anchors=["5,350.00"])
    assert "18896-99_Fintek F5216" in line
    assert "--- Attachments ---" in line
    # ...and the footer must survive the body elision (it rides the tail).
    assert "elided" in line or len(line) < planner._INGESTED_BODY_CAP + 600


# --- long threads are VISIBLE in the evidence, not just citable -------------
#
# Live 2026-09-13: 3,395 of 7,009 stored messages are longer than the 2,500-char
# excerpt cap (longest 79,017). A head+tail clip of a quoted thread hides the
# middle the user is asking about, so the top-ranked matched row now renders
# its WHOLE body up to _INGESTED_BODY_CAP_FULL while deeper rows stay small.


def test_top_ranked_mailbox_hit_renders_the_whole_thread():
    body = "intro\n" + ("quoted history\n" * 500) + "price $ 5,350.00 net"
    row = _row("joelseguin@seguinmach.com", "FW: RFQ - Foot shear", body,
               "2026-08-26 14:06:28")

    line = planner._ingested_line_from_row(
        row, with_body=True, anchors=["5,350.00"],
        body_cap=planner._INGESTED_BODY_CAP_FULL,
    )

    assert "middle of this quoted thread elided" not in line
    assert "net" in line, "the tail must survive when the body fits the cap"
    assert "5,350.00" in line


def test_mega_thread_keeps_the_figure_visible_and_the_path_citable():
    """Adversarial: 75k chars with the amount buried mid-quote. The cap elides
    the middle, but the anchor window and the VFS citation must both survive —
    the agent must never be able to say 'the figure isn't visible'."""
    body = ("quoted history line\n" * 3000) + "$ 5,350.00 – 10 % in stock\n" + (
        "tail line\n" * 1500
    )
    row = _row("joelseguin@seguinmach.com", "FW: RFQ - Foot shear", body,
               "2026-08-26 14:06:28")

    line = planner._ingested_line_from_row(
        row, with_body=True, anchors=["5,350.00"],
        body_cap=planner._INGESTED_BODY_CAP_FULL,
    )

    assert len(line) < len(body), "the cap still bounds the evidence budget"
    assert "5,350.00" in line, "the anchor window must survive the elision"
    assert "full: knowledge/conversations/" in line, "the rest stays reachable"


def test_deeper_rows_stay_small():
    """Only the top row(s) get the big budget — a wall of 32k threads would
    blow the turn's context."""
    assert planner._INGESTED_FULL_LINES >= 1
    assert planner._INGESTED_BODY_CAP_FULL > planner._INGESTED_BODY_CAP


def test_figure_search_gives_the_top_row_the_full_budget(monkeypatch):
    """The wiring, not just the renderer: _search_ingested_by_tokens must pass
    the larger cap for the first _INGESTED_FULL_LINES rows."""
    seen_caps = []
    long_body = "x" * 20000

    def fake_match(rows, tokens, limit=4, date_window=None):
        return [
            {"id": "m1", "sender": "joel@x.example", "recipient": "r@y.z",
             "subject": "FW: quote", "timestamp": "2026-08-26", "content": long_body,
             "metadata": None},
            {"id": "m2", "sender": "joel@x.example", "recipient": "r@y.z",
             "subject": "FW: quote 2", "timestamp": "2026-08-25", "content": long_body,
             "metadata": None},
        ]

    real = planner._ingested_line_from_row

    def spy(row, with_body, anchors=None, body_cap=None):
        seen_caps.append(body_cap)
        return real(row, with_body, anchors=anchors, body_cap=body_cap)

    monkeypatch.setattr(planner, "_match_rows_by_figure_tokens", fake_match)
    monkeypatch.setattr(planner, "_ingested_line_from_row", spy)

    planner._search_ingested_by_tokens("u1", ["5,350.00"], 2)

    assert seen_caps[0] == planner._INGESTED_BODY_CAP_FULL
    assert seen_caps[1] is None, "deeper rows keep the small default cap"


# --- PROVENANCE: where the quoted token lives, resolved BEFORE planning -----
#
# Live 2026-09-14: the user pasted a line out of a vendor email and the planner
# routed it to zoho_inventory ("in stock"). Nothing in the planner's inputs said
# the text was a MESSAGE the workspace already held. These pin the generalized
# fix: the ingested stores are checked for the quoted token first, and the
# result is rendered into the planner's prompt as evidence.


def test_canvas_block_tells_the_planner_what_is_open():
    from core.chat_tool_planner import _planner_canvas_block

    block = _planner_canvas_block({
        "canvas_type": "email",
        "title": "Quote for 52 Inch 16 Gauge Foot Shear",
        "content": {
            "to": "Wayne <wayne.knott@belden.com>",
            "subject": "Quote for 52 Inch 16 Gauge Foot Shear",
            "body": "<p>Hello Wayne,</p>" + ("x" * 5000),
        },
    })

    assert "type: email" in block
    assert "Quote for 52 Inch 16 Gauge Foot Shear" in block
    assert "wayne.knott@belden.com" in block
    # identity yes, the whole body no — the planner must not answer from the
    # prompt instead of from the tools. The block rides on EVERY planning call.
    assert len(block) < 1400, len(block)


def test_canvas_block_is_bounded_regardless_of_body_size():
    """A 30 KB canvas body must not bloat the cheap planning prompt — and the
    cap must hold for the string-content shape too."""
    from core.chat_tool_planner import _PLANNER_CANVAS_CHARS, _planner_canvas_block

    small = _planner_canvas_block(
        {"canvas_type": "email", "content": {"body": "y" * 2000}}
    )
    huge = _planner_canvas_block(
        {"canvas_type": "email", "content": {"body": "y" * 30000}}
    )
    as_str = _planner_canvas_block({"canvas_type": "doc", "content": "z" * 30000})

    for block in (small, huge, as_str):
        body_part = block.split("head: ", 1)[-1]
        assert len(body_part) <= _PLANNER_CANVAS_CHARS, len(body_part)
    # 30k of body must not cost more than the cap + the fixed header
    assert len(huge) < _PLANNER_CANVAS_CHARS + 400
    assert len(as_str) < _PLANNER_CANVAS_CHARS + 400


def test_canvas_block_empty_for_no_canvas():
    from core.chat_tool_planner import _planner_canvas_block

    assert _planner_canvas_block(None) == ""
    assert _planner_canvas_block({}) == ""


def test_token_probe_keys_avoid_the_digit_run_flood():
    """'350' matched 462 live messages of noise; the canonical key plus the
    decorated spellings must be used instead."""
    from core.chat_tool_planner import _token_probe_keys

    keys = _token_probe_keys(["5,350.00"])
    assert "535000" in keys
    assert "5,350.00" in keys
    assert not any(k == "350" for k in keys), keys


def test_mail_contains_tokens_rejects_a_longer_amount(monkeypatch):
    """'535000' is a substring of '$53,500.00' — the verify stage must apply
    the same digit-edge guard as the evidence path, or provenance would claim
    the wrong machine."""
    import core.chat_tool_planner as ctp

    wrong = _row(
        "joelseguin@seguinmach.com", "RE: RFQ - Shear",
        "The only one we have is a 10' shear & 53,500.00 made in China",
        "2026-07-22 13:36:00", row_id="m-wrong",
    )
    right = _row(
        "joelseguin@seguinmach.com", "FW: RFQ - Foot shear",
        "$ 5,350.00 – 10 %  in stock", "2026-08-26 14:06:28", row_id="m-right",
    )
    monkeypatch.setattr(ctp, "_comms_store_records", lambda: [wrong, right])
    ctp.invalidate_comms_store_cache()

    hits = ctp._mail_contains_tokens(["5,350.00"])

    assert [h["id"] for h in hits] == ["m-right"], [h["id"] for h in hits]


def test_provenance_menu_names_the_ingested_mail(monkeypatch):
    import core.chat_tool_planner as ctp

    row = _row(
        "joelseguin@seguinmach.com", "FW: RFQ - Foot shear",
        "$ 5,350.00 – 10 %  in stock", "2026-08-26 14:06:28", row_id="m1",
    )
    monkeypatch.setattr(ctp, "_comms_store_records", lambda: [row])
    monkeypatch.setattr(ctp, "_comms_store_cache", {"x": (0, [row])})
    # no dataset leg in this test
    import core.sheet_dataset_service as sds

    monkeypatch.setattr(sds, "sheet_datasets_enabled", lambda: False)

    menu = asyncio.run(ctp._provenance_menu(
        "search for this one: $ 5,350.00 - 10 % in stock", {"history": []}
    ))

    assert "PROVENANCE" in menu
    assert "INGESTED MAIL contains your quoted text" in menu
    assert "joelseguin@seguinmach.com" in menu
    assert "MESSAGE" in menu


def test_provenance_menu_silent_without_a_distinctive_token(monkeypatch):
    import core.chat_tool_planner as ctp

    def boom(*a, **k):
        raise AssertionError("must not touch the stores for a figure-less message")

    monkeypatch.setattr(ctp, "_mail_contains_tokens", boom)
    assert asyncio.run(ctp._provenance_menu("what did Sarah say about the deadline")) == ""


def test_provenance_menu_is_fault_isolated(monkeypatch):
    import core.chat_tool_planner as ctp

    def boom(*a, **k):
        raise RuntimeError("lance exploded")

    monkeypatch.setattr(ctp, "_mail_contains_tokens", boom)
    assert asyncio.run(ctp._provenance_menu("$ 5,350.00")) == ""


def test_planner_prompt_carries_a_provenance_rule():
    from core.chat_tool_planner import _PLANNER_SYSTEM

    low = _PLANNER_SYSTEM.lower()
    assert "provenance beats wording" in low
    assert "plan \"memory\"" in low or 'plan "memory"' in low


# --- the missing retrieval legs: codes and NAMED participants ---------------
#
# Live 2026-09-14, two searches that could not reach the right thread:
#   * "check the email thread chandrakant forwarded to me about how list price
#     was calculated for the foot shear" — the user's conceptual wording ("list
#     price", "calculated") shares almost no terms with the thread's text
#     ("cost", "$8,880", "52T", "81020") or its subject ("Re: Brake, Shear and
#     Lock Former."), and the thread is filed under chandrakant@brennan.ca
#     while the conversational history carried a DIFFERENT address.
#   * "find the email that said: put 25 percent only" — an exact phrase living
#     in the elided middle of a long quoted thread.
# These pin the two legs that close that gap: an exact CODE scan, and NAME →
# address resolution from the store's own identity map.


def test_code_scan_reaches_a_thread_filed_under_catalogue_numbers(monkeypatch):
    import core.chat_tool_planner as ctp

    row = _row(
        "chandrakant@brennan.ca", "Re: Brake, Shear and Lock Former.",
        "the 52T shear: cost 8,880 less the usual", "2026-09-14 15:38:16",
        row_id="m-brake",
    )
    monkeypatch.setattr(ctp, "_comms_store_records", lambda: [row])

    lines = asyncio.run(ctp._mailbox_code_lines("u1", "how was the list price calculated", {
        "history": [{"message": "what is the 52T list price?"}],
    }))

    assert lines, "a code from the conversation must reach the thread"
    assert "Brake, Shear and Lock Former" in lines[0]


def test_code_boundary_does_not_match_inside_a_longer_code(monkeypatch):
    import core.chat_tool_planner as ctp

    wrong = _row("v@x.example", "Quote", "part 810200 shipped", "2026-09-14",
                 row_id="m-wrong")
    right = _row("v@x.example", "Quote", "part 81020 shipped", "2026-09-13",
                 row_id="m-right")
    hits = ctp._code_boundary_hits([wrong, right], ["81020"])

    assert [h["id"] for h in hits] == ["m-right"]


def test_named_person_resolves_through_the_stores_own_addresses(monkeypatch):
    """'chandrakant forwarded to me' → his address, from the store's senders —
    no hardcoded roster (per-install identity is data)."""
    import core.chat_tool_planner as ctp

    row = _row("chandrakant@brennan.ca", "Re: Brake, Shear and Lock Former.",
               "body", "2026-09-14 15:38:16", row_id="m1")
    monkeypatch.setattr(ctp, "_comms_store_records", lambda: [row])
    ctp._PEOPLE_INDEX.clear()

    addrs = ctp._resolve_named_addresses(
        "check the email thread chandrakant forwarded to me"
    )

    assert addrs == ["chandrakant@brennan.ca"]


def test_generic_mailbox_words_are_not_people(monkeypatch):
    """'email@…' exists in the store; the word "email" in an ordinary sentence
    must not resolve into a mailbox scan."""
    import core.chat_tool_planner as ctp

    rows = [
        _row("email@email.shopify.com", "Newsletter", "sale", "2026-09-14",
             row_id="m1"),
        _row("chandrakant@brennan.ca", "Re: Shear", "body", "2026-09-14",
             row_id="m2"),
    ]
    monkeypatch.setattr(ctp, "_comms_store_records", lambda: rows)
    ctp._PEOPLE_INDEX.clear()

    assert ctp._extract_named_people("find the email about the foot shear") == []


def test_address_ranking_prefers_subject_overlap_over_recency(monkeypatch):
    """A named participant's address holds hundreds of unrelated messages:
    'newest N' returned the six latest while the described thread sat below
    the cap. A term the user used that the SUBJECT also uses wins."""
    import core.chat_tool_planner as ctp

    newer_other = _row("chandrakant@brennan.ca", "Re: Quote for GHS5430",
                       "unrelated", "2026-09-14 17:38", row_id="m-other")
    described = _row("chandrakant@brennan.ca", "Re: 52 Inch 16 Gauge Foot Shear",
                     "how the list price was built", "2026-09-14 12:51",
                     row_id="m-target")
    ranked = ctp._rank_address_hits(
        [newer_other, described], "chandrakant@brennan.ca", limit=1,
        query="the foot shear list price calculation",
    )

    assert [r["id"] for r in ranked] == ["m-target"]


# --- recipient provenance: a line must say WHO it was addressed to ----------
#
# Live 2026-09-14: the agent read "From: chandrakant@brennan.ca | Hey, I did
# not find the attachment" and told the user "Chandrakant sent YOU this",
# building a theory that "the calculation file never reached the mailbox".
# The message was `To: edwin@schulermachinery.com`, subject "Re: Enquiry about
# Lathe machine" — a note to a supplier about a missing lathe brochure. The
# listing line carried only the sender, so every stored message looked
# addressed to the user.


def test_mailbox_line_shows_the_recipient():
    row = _row(
        "chandrakant@brennan.ca", "Re: Enquiry about Lathe machine",
        "Hey, I did not find the attachment", "2026-09-11 12:50:09",
        row_id="m-edwin",
    )
    row["recipient"] = "edwin@schulermachinery.com"

    line = planner._ingested_line_from_row(row, with_body=False)

    assert "To: edwin@schulermachinery.com" in line, line
    assert "Re: Enquiry about Lathe machine" in line


def test_mailbox_line_marks_outbound_direction():
    row = _row("chandrakant@brennan.ca", "RE: RFQ - Foot shear", "body",
               "2026-09-11 19:21:04", row_id="m-out")
    row["recipient"] = "kurt@neimanmachinery.com"
    row["direction"] = "outbound"

    line = planner._ingested_line_from_row(row, with_body=False)

    assert "To: kurt@neimanmachinery.com" in line
    assert "direction: outbound" in line


def test_mailbox_line_without_recipient_still_renders():
    """Legacy rows predate the recipient column — the line must not break."""
    row = _row("v@x.example", "Quote", "body", "2026-09-11", row_id="m-norec")
    row.pop("recipient", None)

    line = planner._ingested_line_from_row(row, with_body=False)

    assert line.startswith("- [ingested mailbox] From: v@x.example")
    assert "To:" not in line


# --- attachments on the evidence line ---------------------------------------

def test_mailbox_line_lists_attachments_with_openable_paths(monkeypatch):
    """The email is often only the envelope: the number being asked about
    lives in the attached workbook (F-5216 thread → PRICE VIPUL (6).xlsx,
    row 235 → $7,519). Without the attachment on the line, an agent reads the
    email and still cannot say a file came with it."""
    import core.chat_tool_planner as ctp

    row = _row("chandrakant@brennan.ca", "Fw: RFQ - Foot shear",
               "please check row 235", "2026-09-11 20:07:31", row_id="m-fw")
    row["recipient"] = "rish@brennan.ca"
    monkeypatch.setattr(
        ctp, "_mail_attachments_for",
        lambda mid, limit=4: [("PRICE VIPUL (6).xlsx", "ext_c1f74")] if mid == "m-fw" else [],
    )

    line = ctp._ingested_line_from_row(row, with_body=False)

    assert "attachments: PRICE VIPUL (6).xlsx" in line
    assert "open: knowledge/documents/ext_c1f74/content.lines" in line


def test_mailbox_line_omits_attachments_when_there_are_none(monkeypatch):
    import core.chat_tool_planner as ctp

    monkeypatch.setattr(ctp, "_mail_attachments_for", lambda mid, limit=4: [])
    row = _row("v@x.example", "Quote", "body", "2026-09-11", row_id="m-none")

    assert "attachments:" not in ctp._ingested_line_from_row(row, with_body=False)
