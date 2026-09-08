"""Styled-draft base: comm tool blocks surface the real styled HTML body.

Owner request 2026-09-07 — "agent can get styled email or other messages
and create it as base for drafting new emails or messages". Ingestion
preserves every comm app's original markup under metadata.html_body (store
choke point), and live Graph hits carry body.content — but the tool blocks
only ever showed 200/220-char TEXT previews, so the model could read ABOUT
a styled message yet could not base a new draft on its actual markup.

Pins: the outlook leg attaches the styled base (ingested store first, top
Graph HTML hit as fallback), the universal comm path attaches it on both
the live-miss and success-with-ingested-leads branches, and plain-text-only
results attach nothing."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import asyncio
import json
from unittest.mock import MagicMock, patch

import core.chat_tool_planner as planner
from core.chat_tool_planner import ToolPlan, execute_tool_plan

STYLED = (
    '<div style="font-family:Calibri"><b>Rish M.</b>'
    '<span style="color:rgb(0,0,0)">Brennan Machinery Inc.</span></div>'
)


def _plan(service, query):
    return ToolPlan(use_tool=True, service=service, intent="search",
                    query=query, reason="test")


def _fake_outlook_module(emails):
    svc = MagicMock()

    async def search_emails(user_id=None, query=None, max_results=10,
                            quote=False, token=None):
        return emails

    svc.search_emails = search_emails
    mod = MagicMock()
    mod.outlook_service = svc
    mod.sanitize_graph_kql = lambda q: q
    sys.modules["integrations.outlook_service"] = mod
    return mod


def _fake_universal_module(data):
    class _FakeSvc:
        def __init__(self, *a, **kw):
            pass

        async def search(self, service, query, context=None):
            return {"status": "success", "data": data}

        async def execute(self, service, action, params=None, context=None):
            return {"status": "success", "data": data}

    mod = MagicMock()
    mod.UniversalIntegrationService = _FakeSvc
    mod.SEARCHABLE_SERVICES = frozenset({"gmail", "slack", "notion"})
    sys.modules["integrations.universal_integration_service"] = mod
    return mod


def _graph_hit(html=None, sender="jacob@blumetric.ca"):
    body = (
        {"contentType": "HTML", "content": f"<html><body>{html or STYLED}</body></html>"}
        if html is not False else
        {"contentType": "text", "content": "plain body"}
    )
    return [{
        "id": "m1", "subject": "Quote follow-up", "body": body,
        "body_preview": "short preview only",
        "from_field": {"emailAddress": {"address": sender}},
        "received_date_time": "2026-09-06T10:00:00Z",
    }]


def test_outlook_block_carries_ingested_styled_base():
    _fake_outlook_module(_graph_hit(html=False))

    def fake_styled(*a, **kw):
        return {"sender": "jacob@blumetric.ca", "subject": "Quote", "html": STYLED}

    with patch.object(planner, "_latest_styled_ingested", side_effect=fake_styled):
        block = asyncio.run(execute_tool_plan(
            _plan("outlook", "quote from jacob@blumetric.ca"), "u1", "default",
            context={}))

    assert "STYLED HTML BODY" in block
    assert STYLED in block
    assert "base of a new draft" in block or "base a NEW draft" in block


def test_outlook_falls_back_to_graph_html_body():
    _fake_outlook_module(_graph_hit())

    def no_styled(*a, **kw):
        return None

    with patch.object(planner, "_latest_styled_ingested", side_effect=no_styled):
        block = asyncio.run(execute_tool_plan(
            _plan("outlook", "quote follow-up"), "u1", "default", context={}))

    assert "STYLED HTML BODY" in block
    assert STYLED in block


def test_plain_text_only_attaches_no_styled_section():
    _fake_outlook_module(_graph_hit(html=False))

    def no_styled(*a, **kw):
        return None

    with patch.object(planner, "_latest_styled_ingested", side_effect=no_styled):
        block = asyncio.run(execute_tool_plan(
            _plan("outlook", "quote follow-up"), "u1", "default", context={}))

    assert "STYLED HTML BODY" not in block


def test_gmail_success_with_ingested_leads_carries_styled_base():
    _fake_universal_module(
        data={"results": [{"snippet": "provider relevance hit"}]})

    async def fake_mail_lines(user_id, query, context=None, cap=6, hybrid_min=4):
        return ["- [ingested mailbox] From: a@b.com | hit | body | ts"]

    def fake_styled(*a, **kw):
        return {"sender": "a@b.com", "subject": "Thread", "html": STYLED}

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=fake_mail_lines), \
         patch.object(planner, "_latest_styled_ingested", side_effect=fake_styled), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("gmail", "a@b.com"), "u1", "default", context={}))

    assert "INGESTED MAILBOX matches first" in block
    assert "STYLED HTML BODY" in block
    assert STYLED in block


def test_latest_styled_ingested_prefers_newest_address_match():
    """The lookup must take the NEWEST matching record that carries styled
    markup, skipping address non-matches and plain rows."""
    import pandas as pd

    rows = [
        {"sender": "jacob@blumetric.ca", "recipient": "rish@brennan.ca",
         "subject": "old styled", "timestamp": "2026-09-01T10:00:00Z",
         "metadata": json.dumps({"html_body": "<div>old</div>"})},
        {"sender": "noreply@zoho.com", "recipient": "rish@brennan.ca",
         "subject": "not a match", "timestamp": "2026-09-05T10:00:00Z",
         "metadata": json.dumps({"html_body": "<div>lead form</div>"})},
        {"sender": "jacob@blumetric.ca", "recipient": "rish@brennan.ca",
         "subject": "plain", "timestamp": "2026-09-06T10:00:00Z",
         "metadata": json.dumps({})},
        {"sender": "jacob@blumetric.ca", "recipient": "rish@brennan.ca",
         "subject": "newest styled", "timestamp": "2026-09-06T18:00:00Z",
         "metadata": json.dumps({"html_body": STYLED})},
    ]
    df = pd.DataFrame(rows)

    table = MagicMock()
    table.to_arrow.return_value.to_pandas.return_value = df
    db = MagicMock()
    db.open_table.return_value = table
    lancedb_mod = MagicMock()
    lancedb_mod.connect.return_value = db
    sys.modules["lancedb"] = lancedb_mod

    got = planner._latest_styled_ingested(
        "u1", ["jacob@blumetric.ca"])
    assert got is not None
    assert got["subject"] == "newest styled"
    assert got["html"] == STYLED
    sys.modules.pop("lancedb", None)
