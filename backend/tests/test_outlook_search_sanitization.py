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
    decompose_graph_kql,
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
        # Mixed letter+digit tokens (model numbers/SKUs) are quoted — Graph
        # rejects them bare (live 2026-09-03 WG350DSAV); the old parametrize
        # expected them unquoted, which pinned the pre-heuristic behavior.
        ("Hydmech DM10 bandsaw", 'Hydmech "DM10" bandsaw'),
        ("blumetric ca", "blumetric ca"),
        ("O'Brien bandsaw", "O'Brien bandsaw"),
        ("", ""),
        # Quoted phrases survive VERBATIM (2026-09-12 incident: the quoted
        # amount was gutted to '" 5 350 00"', which 400'd like the raw form
        # — the sanitized retry rung never worked for phrase queries).
        ('"$5,350.00"', '"$5,350.00"'),
        ('"$ 5,350.00 – 10 %  in stock"', '"$ 5,350.00 – 10 %  in stock"'),
        # Mixed: address fragments tokenized, the quoted amount preserved.
        (
            'joelseguin@seguinmach.com "$5,350.00"',
            'joelseguin seguinmach com "$5,350.00"',
        ),
        # Embedded quotes inside a phrase are stripped; escaped/doubled
        # quotes degrade to per-word phrases, never crash.
        ('"say ""hi"" soon"', '"say" "hi" "soon"'),
        # Unbalanced quotes degrade to bare-token handling, never crash.
        ('oops "unbalanced', 'oops unbalanced'),
    ],
)
def test_sanitize_graph_kql(raw, expected):
    assert sanitize_graph_kql(raw) == expected


def test_sanitize_never_returns_none():
    assert sanitize_graph_kql("@@") == ""


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Amount punctuation collapses to tokens; digit-bearing tokens are
        # individually quoted (bare digit-leading terms 400, live 2026-09-12).
        ("$ 5,350.00 – 10 %  in stock", '"5" "350.00" "10" in stock'),
        ("$5,350.00", '"5" "350.00"'),
        # Words come through bare; digit tokens quoted.
        ("Hydmech DM10 bandsaw", 'Hydmech "DM10" bandsaw'),
        ("used shear in stock", "used shear in stock"),
        ("", ""),
        ("###", ""),
    ],
)
def test_decompose_graph_kql(raw, expected):
    assert decompose_graph_kql(raw) == expected


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

    # Raw → sanitized → decomposed: every rung tried before giving up.
    assert svc._make_graph_request.await_count == 3
    assert emails == []


def test_search_emails_ladder_climbs_to_decomposed_phrase_query():
    """The 2026-09-12 incident shape: an address plus a quoted amount 400s
    raw; the sanitized form PRESERVES the phrase and must be tried as-is
    (the old sanitizer gutted it to '" 5 350 00"', also a 400, and the
    decomposed rung did not exist)."""
    svc = OutlookService()
    forms = []

    async def fake_request(user_id, endpoint, method="GET", data=None, access_token=None):
        forms.append(endpoint)
        if len(forms) < 3:
            return None  # raw AND sanitized forms rejected by Graph
        return {"value": [{"id": "fw-rfq-foot-shear", "subject": "FW: RFQ - Foot shear"}]}

    svc._make_graph_request = AsyncMock(side_effect=fake_request)

    emails = asyncio.run(
        svc.search_emails(
            "user-1", 'joelseguin@seguinmach.com "$5,350.00"', quote=False
        )
    )

    assert len(emails) == 1
    assert len(forms) == 3, "decomposed rung must fire after two rejections"
    # sanitized middle rung kept the quoted amount intact ($ included)
    assert "%22%245%2C350.00%22" in forms[1], forms[1]


def test_search_emails_quote_true_never_double_wraps_embedded_phrases():
    """quote=True + a query that already contains quotes must not wrap the
    whole thing again — nested phrase syntax always 400s (the original
    2026-09-12 repro: '""$5,350.00" joelseguin seguinmach"' hard-failed)."""
    svc = OutlookService()
    forms = []

    async def fake_request(user_id, endpoint, method="GET", data=None, access_token=None):
        forms.append(endpoint)
        return {"value": []}

    svc._make_graph_request = AsyncMock(side_effect=fake_request)

    asyncio.run(svc.search_emails("user-1", '"$5,350.00" joelseguin seguinmach'))

    assert forms, "at least one attempt"
    for f in forms:
        assert "%22%22" not in f, f"nested quoting in {f}"


def test_search_emails_sender_scoping_prefixes_from_clause():
    """sender= builds a quoted from:-scoped KQL clause — the form that
    reliably returns a whole thread where relevance-ranked free-text buries
    it (live 2026-09-12 Seguin). The clause MUST be quoted: the bare form
    400s on the ':' (same live check)."""
    svc = OutlookService()
    forms = []

    async def fake_request(user_id, endpoint, method="GET", data=None, access_token=None):
        forms.append(endpoint)
        return {"value": []}

    svc._make_graph_request = AsyncMock(side_effect=fake_request)

    asyncio.run(
        svc.search_emails(
            "user-1",
            "5,350.00 in stock",
            quote=False,
            sender="joelseguin@seguinmach.com",
            max_results=25,
        )
    )

    assert len(forms) == 1
    assert "%22from%3Ajoelseguin%40seguinmach.com%22" in forms[0], forms[0]
    assert "%24top=25" in forms[0], forms[0]
