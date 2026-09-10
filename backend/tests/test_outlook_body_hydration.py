"""Outlook full-body hydration + read intent in the chat tool planner.

Regression context (live 2026-09-09, canvas 7f078cea): "get
ryershov@nettinc.com to find original reseller's contents". Graph $search
omits the message body entirely (bodyPreview = first 255 chars, Microsoft's
documented property subset) and the tool listing clipped that to 200 chars,
so Roman Yershov's machine listing — quoted BELOW the signature of the Sep 8
"Fw: Used Equipment sell" forward — was structurally invisible. The agent
answered from previews and had no tool to open the message in full.

Fix pinned here: the search leg hydrates FULL bodies for the top-ranked
hits (head+tail capped, so bottom-quoted content survives), and a `read`
intent returns full bodies for more hits — or fetches one message directly
when handed a bare Graph id."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import asyncio
from unittest.mock import patch

import core.chat_tool_planner as planner
from core.chat_tool_planner import (
    ToolPlan,
    execute_tool_plan,
    _graph_body_text,
    _ingested_line_from_row,
)


def _hit(eid, subject, preview, received, sender="chandrakant@brennan.ca"):
    return {
        "id": eid,
        "subject": subject,
        "body_preview": preview,
        "from_field": {"emailAddress": {"address": sender}},
        "received_date_time": received,
    }


FAKE_HITS = [
    _hit("A" * 80, "Fw: Used Equipment sell", "short preview, cut at the sig…",
         "2026-09-08T10:00:00", "rish@brennan.ca"),
    _hit("B" * 80, "RE: Used Equipment sell", "preview two",
         "2026-07-17T13:53:00", "chandrakant@brennan.ca"),
    _hit("C" * 80, "Zoho Forms lead notification", "preview three",
         "2026-07-17T13:41:00", "notifications@zohoforms.ca"),
]

# The original listing content sits BELOW the signature of the forward —
# deeper than any preview could reach.
FORWARD_TAIL = (
    "<div>Sent from my iPhone</div>"
    "<div>Original listing: Yanmar laser model YL-500, year 2019, "
    "asking price CAD 42,000, excellent condition, one owner.</div>"
)


def _fake_graph_message(eid, body_html):
    return {
        "id": eid,
        "subject": "Fw: Used Equipment sell",
        "body": {"contentType": "html", "content": body_html},
        "from_field": {"emailAddress": {"address": "rish@brennan.ca"}},
        "received_date_time": "2026-09-08T10:00:00",
    }


def _patch_outlook(hits=FAKE_HITS, bodies=None, store_lines=()):
    """Patch the outlook singleton's Graph calls and the ingested-store
    supplement, so execute_tool_plan's outlook leg runs without network."""
    from integrations import outlook_service as osvc_mod

    bodies = bodies or {}

    async def fake_search(user_id, query, max_results=50, token=None, quote=True):
        return [dict(h) for h in hits]

    async def fake_get(user_id, email_id, token=None):
        if email_id in bodies:
            return _fake_graph_message(email_id, bodies[email_id])
        return None

    return (
        patch.object(osvc_mod.outlook_service, "search_emails", side_effect=fake_search),
        patch.object(osvc_mod.outlook_service, "get_email_by_id", side_effect=fake_get),
        patch.object(planner, "_ingested_mailbox_lines", side_effect=lambda *a, **k: list(store_lines)),
        patch.object(planner, "_memory_search_block", side_effect=lambda *a, **k: None),
        patch.object(planner, "_latest_styled_ingested", side_effect=lambda *a, **k: None),
    )


class TestGraphBodyText:
    def test_html_converted_to_text(self):
        text = _graph_body_text(
            {"body": {"contentType": "html", "content": "<p>Hi Roman</p><p>quote below</p>"}},
            cap=3500,
        )
        assert "Hi Roman" in text and "quote below" in text
        assert "<p>" not in text

    def test_plain_text_passes_through(self):
        text = _graph_body_text(
            {"body": {"contentType": "text", "content": "plain body"}}, cap=3500
        )
        assert text == "plain body"

    def test_cap_keeps_tail_not_just_head(self):
        # Top-posted forwards put the quoted original BELOW the newest text:
        # a head-only clip would cut exactly the content we hydrate for.
        body = "newest text " + "filler " * 600 + FORWARD_TAIL
        text = _graph_body_text(
            {"body": {"contentType": "html", "content": body}}, cap=800
        )
        assert len(text) < 900
        assert "asking price CAD 42,000" in text, "tail (quoted original) must survive"
        assert "elided" in text


class TestSearchHydration:
    def test_search_block_carries_full_bodies_for_top_hits(self):
        patches = _patch_outlook(bodies={"A" * 80: FORWARD_TAIL, "B" * 80: "reply body two"})
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            block = asyncio.run(execute_tool_plan(
                ToolPlan(use_tool=True, service="outlook", intent="search",
                         query="ryershov@nettinc.com", reason="t"),
                "u1", "default", context={}))
        assert "outlook.search_emails" in block
        assert "FULL BODY:" in block
        assert "asking price CAD 42,000" in block
        assert "reply body two" in block
        # The un-hydrated third hit keeps its preview line + the read hint.
        assert "preview three" in block
        assert "intent=read" in block

    def test_hydration_failure_degrades_to_preview(self):
        patches = _patch_outlook(bodies={})  # get_email_by_id returns None
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            block = asyncio.run(execute_tool_plan(
                ToolPlan(use_tool=True, service="outlook", intent="search",
                         query="ryershov@nettinc.com", reason="t"),
                "u1", "default", context={}))
        assert "FULL BODY:" not in block
        assert "cut at the sig…" in block  # previews still listed


class TestIngestedLineBodies:
    """The ingested store is the DETERMINISTIC source (Graph's relevance
    ranking returned unrelated mail for ryershov@nettinc.com on the live
    re-check) — its listing lines must carry full bodies too, not just the
    260-char excerpt that cut mid-signature."""

    ROW = {
        "sender": "chandrakant@brennan.ca",
        "subject": "Fw: Used Equipment sell",
        "timestamp": "2026-09-08 19:56:31",
        "content": "Best, Chandrakant Sharma",
        "metadata": '{"html_body": "<div>Best,</div>'
                    '<div>Original listing: Yanmar laser YL-500, year 2019, '
                    'asking CAD 42,000.</div>"}',
    }

    def test_body_line_carries_quoted_original(self):
        line = _ingested_line_from_row(self.ROW, with_body=True)
        assert "FULL BODY:" in line
        assert "asking CAD 42,000" in line
        assert "<div>" not in line  # html converted to text
        assert "received: 2026-09-08 19:56:31" in line

    def test_excerpt_line_without_body_unchanged_shape(self):
        line = _ingested_line_from_row(self.ROW, with_body=False)
        assert "FULL BODY" not in line
        assert "Best, Chandrakant Sharma" in line

    def test_body_falls_back_to_content_column(self):
        row = dict(self.ROW)
        row["metadata"] = "not json"
        line = _ingested_line_from_row(row, with_body=True)
        assert "Best, Chandrakant Sharma" in line

    def test_body_cap_keeps_tail(self):
        row = dict(self.ROW)
        row["metadata"] = '{"html_body": "' + "filler " * 700 + "asking CAD 42,000" + '"}'
        line = _ingested_line_from_row(row, with_body=True)
        assert "asking CAD 42,000" in line
        assert "elided" in line


class TestReadIntent:
    def test_read_block_carries_more_full_bodies(self):
        bodies = {h["id"]: f"full body of {h['subject']}" for h in FAKE_HITS}
        patches = _patch_outlook(bodies=bodies)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            block = asyncio.run(execute_tool_plan(
                ToolPlan(use_tool=True, service="outlook", intent="read",
                         query="ryershov@nettinc.com", reason="t"),
                "u1", "default", context={}))
        assert "outlook.read_emails" in block
        assert "full body of Zoho Forms lead notification" in block
        assert "preview:" not in block.split("use these to answer", 1)[-1]

    def test_read_with_bare_graph_id_fetches_directly(self):
        patches = _patch_outlook(bodies={"Z" * 80: FORWARD_TAIL})
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            block = asyncio.run(execute_tool_plan(
                ToolPlan(use_tool=True, service="outlook", intent="read",
                         query="Z" * 80, reason="t"),
                "u1", "default", context={}))
        assert "asking price CAD 42,000" in block
        assert "outlook.read_emails" in block

    def test_read_with_unknown_id_reports_honestly(self):
        patches = _patch_outlook(bodies={})
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            block = asyncio.run(execute_tool_plan(
                ToolPlan(use_tool=True, service="outlook", intent="read",
                         query="Q" * 80, reason="t"),
                "u1", "default", context={}))
        assert "not retrievable" in block
