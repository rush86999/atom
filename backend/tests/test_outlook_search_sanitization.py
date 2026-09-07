"""Live-incident regression (2026-09-02): the sales agent searched the
mailbox for "jschulz@blumetric.ca Jason response"; Graph rejected the email
term with a 400 ("Syntax error: character '@' is not valid at position 7 in
'jschulz@blumetric.ca'"), search_emails swallowed it to [], and the rarest,
most selective term silently dropped out of the merged search — so the agent
could not find an email that sat in the ingested mailbox all along.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from integrations.outlook_service import (
    OutlookService,
    sanitize_graph_kql,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        # The exact failing term from the incident: '@' → space, both
        # fragments still tokenize against the body "Email : jschulz@blumetric.ca".
        ("jschulz@blumetric.ca", "jschulz blumetric ca"),
        # Lead-form search from the earlier Kellam incident: ':' and ','
        # are KQL operators / noise, stripped; the words survive.
        ("Name : Mark, Kellam", "Name   Mark  Kellam"),
        # Already-legal queries must pass through untouched.
        ("Hydmech DM10 bandsaw", "Hydmech DM10 bandsaw"),
        ("blumetric ca", "blumetric ca"),
        ("O'Brien bandsaw", "O'Brien bandsaw"),
        ("", ""),
    ],
)
def test_sanitize_graph_kql(raw, expected):
    assert sanitize_graph_kql(raw) == expected


def test_sanitize_never_returns_none():
    assert sanitize_graph_kql("@@") == ""


def test_search_emails_retries_with_sanitized_kql_on_graph_400():
    """A 400 on the raw query must fall through to the sanitized retry, not
    return [] — the retry is what keeps 'jschulz@blumetric.ca' searchable."""

    svc = OutlookService()
    captured_endpoints = []

    async def fake_request(user_id, endpoint, method="GET", data=None, access_token=None):
        captured_endpoints.append(endpoint)
        if len(captured_endpoints) == 1:
            return None  # Graph 400 path: _handle_response → None
        return {
            "value": [
                {
                    "id": "msg-1",
                    "subject": "New Quote Request From New Lead",
                    "bodyPreview": "Email : jschulz@blumetric.ca",
                    "sender": {"emailAddress": {"address": "noreply@zohoforms.ca"}},
                }
            ]
        }

    svc._make_graph_request = AsyncMock(side_effect=fake_request)

    emails = asyncio.run(
        svc.search_emails("user-1", "jschulz@blumetric.ca", quote=False)
    )

    assert len(captured_endpoints) == 2, "sanitized retry must be attempted"
    first = captured_endpoints[0]
    second = captured_endpoints[1]
    assert "jschulz%40blumetric.ca" in first, "first attempt must use the raw query"
    assert "jschulz+blumetric+ca" in second, "retry must use the sanitized query"
    assert len(emails) == 1 and emails[0]["id"] == "msg-1"


def test_search_emails_no_extra_roundtrip_when_query_already_legal():
    """A legal query must not pay a second Graph call when it succeeds."""

    svc = OutlookService()
    svc._make_graph_request = AsyncMock(return_value={"value": []})

    emails = asyncio.run(svc.search_emails("user-1", "Hydmech DM10", quote=False))

    assert svc._make_graph_request.await_count == 1
    assert emails == []


def test_search_emails_returns_empty_when_both_attempts_fail():
    svc = OutlookService()
    svc._make_graph_request = AsyncMock(return_value=None)

    emails = asyncio.run(svc.search_emails("user-1", "jschulz@blumetric.ca"))

    assert svc._make_graph_request.await_count == 2
    assert emails == []
