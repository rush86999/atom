"""Unit tests for the address-hit ranking in the chat tool planner and the
tool-failure prompt block in the chat orchestrator.

Regression context (live 2026-09-06, agent 9837ec71): "find the email thread
for jschulz@blumetric.ca" — the ingested comms table held the whole thread,
but the first-N address scan walked table (insertion) order and filled its
slots with lead forms and internal chatter; the reply then sat near the end
of the table, unseen. The retry turn's executor timed out, the TimeoutError
stringified to "" and the model — given no tool block at all — told the user
it had no Outlook search tool."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.chat_tool_planner import _rank_address_hits
from integrations.chat_orchestrator import _tool_failure_block


def _row(sender, recipient, subject, content, ts):
    return {
        "sender": sender, "recipient": recipient, "subject": subject,
        "content": content, "timestamp": ts,
    }


ADDR = "jschulz@blumetric.ca"


class TestRankAddressHits:
    def test_participant_rows_outrank_body_mentions_regardless_of_order(self):
        # Table order: junk first (address only inside quoted bodies), the
        # actual thread members last — ranking must invert this.
        rows = [
            _row("vipul@brennan.ca", "rish@brennan.ca", "internal",
                 "quoted: jschulz@blumetric.ca asked", "2026-09-02T17:33:17"),
            _row("notifications@zohoforms.ca", "rish@brennan.ca", "lead",
                 "Email : jschulz@blumetric.ca", "2026-08-31T16:38:34"),
            _row("jschulz@blumetric.ca", "rish@brennan.ca", "RE: Brennan",
                 "thanks, received", "2026-09-02T17:08:35"),
            _row("rish@brennan.ca", "jschulz@blumetric.ca", "Re: Equivalent",
                 "quote below", "2026-09-04T17:15:53"),
        ]
        ranked = _rank_address_hits(rows, ADDR, limit=4)
        assert ranked[0]["subject"] == "Re: Equivalent"      # newest participant
        assert ranked[1]["subject"] == "RE: Brennan"
        # body-only mentions fill remaining slots, newest first
        assert ranked[2]["sender"] == "vipul@brennan.ca"
        assert ranked[3]["sender"] == "notifications@zohoforms.ca"

    def test_limit_keeps_participants_over_mentions(self):
        rows = [
            _row("a@x.com", "b@x.com", f"m{i}", f"cc {ADDR}", f"2026-09-0{i}T10:00:00")
            for i in range(1, 6)
        ]
        rows.append(_row(ADDR, "rish@brennan.ca", "the reply", "body", "2026-09-02T09:00:00"))
        ranked = _rank_address_hits(rows, ADDR, limit=4)
        assert len(ranked) == 4
        assert ranked[0]["subject"] == "the reply"

    def test_duplicates_collapse(self):
        dup = _row("jschulz@blumetric.ca", "rish@brennan.ca", "RE", "b", "2026-09-02T17:08:35")
        rows = [dup, dict(dup), dict(dup)]
        ranked = _rank_address_hits(rows, ADDR, limit=4)
        assert len(ranked) == 1

    def test_reingested_copy_with_restamped_timestamp_collapses(self):
        # Same message re-ingested under a new timestamp must not burn two
        # cap slots (live 2026-09-06: the Sep 4 quote appeared twice).
        body = "Hi Jacob, the quote for the Linmac WG-350DSAV is below."
        rows = [
            _row("rish@brennan.ca", ADDR, "Re: Equivalent", body, "2026-09-04T17:15:53"),
            _row("rish@brennan.ca", ADDR, "Re: Equivalent", body, "2026-09-04T18:00:00"),
        ]
        assert len(_rank_address_hits(rows, ADDR, limit=4)) == 1

    def test_non_matching_rows_dropped(self):
        rows = [
            _row("x@y.com", "z@y.com", "unrelated", "nothing here", "2026-09-01T00:00:00"),
            _row(ADDR, "rish@brennan.ca", "hit", "b", "2026-09-02T09:00:00"),
        ]
        ranked = _rank_address_hits(rows, ADDR, limit=4)
        assert len(ranked) == 1 and ranked[0]["subject"] == "hit"

    def test_empty_and_missing_fields_tolerated(self):
        # sender-only row is a valid participant hit; rows without the
        # address anywhere are dropped; missing fields must not raise.
        rows = [{"sender": ADDR}, {"timestamp": "2026-09-02T09:00:00"}, {}]
        ranked = _rank_address_hits(rows, ADDR, limit=4)
        assert len(ranked) == 1 and ranked[0]["sender"] == ADDR


class TestToolFailureBlock:
    def test_names_the_planned_lookup(self):
        block = _tool_failure_block("outlook.search:jschulz@blumetric.ca")
        assert "outlook.search:jschulz@blumetric.ca" in block

    def test_forbids_the_two_hallucinations(self):
        block = _tool_failure_block("outlook.search:x")
        assert "lack tools" in block
        assert "does not exist" in block
        assert "FAILED" in block


# --- SYNC-OFF-LOOP: the scans must not block the event loop ----------------

def test_mailbox_lines_offload_keeps_loop_responsive(monkeypatch):
    """The comms-table scan is a ~4s full-table walk at real size. It must
    run in a worker thread: while it runs, the event loop keeps servicing
    other tasks (live 2026-09-06: on-loop scans froze every endpoint)."""
    import asyncio
    import time
    import core.chat_tool_planner as planner

    def slow_scan(user_id, address, limit=4):
        time.sleep(0.4)
        return ["- [ingested mailbox] hit"]

    monkeypatch.setattr(planner, "_search_ingested_by_address", slow_scan)

    async def harness():
        ticks = []
        stop = False

        async def tick():
            while not stop:
                ticks.append(time.monotonic())
                await asyncio.sleep(0.02)

        ticker = asyncio.create_task(tick())
        t0 = time.monotonic()
        lines = await planner._ingested_mailbox_lines(
            "u1", "jschulz@blumetric.ca", {"history": []})
        elapsed = time.monotonic() - t0
        stop = True
        await ticker
        return lines, elapsed, ticks

    lines, elapsed, ticks = asyncio.run(harness())
    assert lines  # scan results still surface
    # the loop ticked DURING the 0.4s scan: gaps between ticks stay small
    # (the mocked 0.4s scan stands in for the real ~4s full-table walk; an
    # on-loop scan would stall the loop for the whole duration). The single
    # ~0.3s tail gap is the hybrid-fallback leg scheduling at the end.
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert max(gaps) < 0.5, f"event loop stalled {max(gaps):.2f}s during scan"
    assert sum(1 for g in gaps if g < 0.05) >= 10, "loop did not tick during scan"
    assert elapsed >= 0.4
