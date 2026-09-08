"""Generalized tool-routing fixes: KQL token quoting, query-anchored
excerpts, file matching, planner context reading.

Live regressions these pin (2026-09-03):
  - outlook.search("WG350DSAV …") 400'd: Graph KQL rejects bare mixed
    letter+digit tokens.
  - storage search returned only metadata — nothing could OPEN a file.

(The pattern-matching router tests — named-service beats file nouns,
explicit-open regex — were removed 2026-09-08: commit 2523258fd made
routing LLM-owned and deleted _service_named_in_message/_EXPLICIT_OPEN,
so those tests pinned machinery that no longer exists.)
"""

import pytest

from core.chat_tool_planner import (
    _current_message_text,
)


def test_current_message_text_reads_last_user_entry():
    ctx = {"history": [
        {"role": "assistant", "content": "earlier answer"},
        {"role": "user", "content": "find the row please"},
    ]}
    assert "find the row" in _current_message_text(ctx)
    assert _current_message_text({}) == ""


def test_sanitize_graph_kql_quotes_mixed_alnum_tokens():
    from integrations.outlook_service import sanitize_graph_kql

    out = sanitize_graph_kql("WG350DSAV Linmac Bandsaw price consolidated price list")
    assert '"WG350DSAV"' in out
    assert "Linmac" in out and '"' + "Linmac" + '"' not in out  # letters-only untouched
    # letters+digits model with punctuation stripped then quoted
    out2 = sanitize_graph_kql("DM-10 bandsaw")
    assert "DM 10" in out2 and '"' not in out2  # hyphen stripped; letters-only / digits-only tokens stay bare
    # already-quoted tokens survive intact
    out3 = sanitize_graph_kql('"WG350DSAV" bandsaw')
    assert out3.count('"WG350DSAV"') == 1
    # emails still sanitize as before
    out4 = sanitize_graph_kql("jschulz@blumetric.ca")
    assert "@" not in out4


def test_query_anchored_excerpt_centers_on_token_region():
    from integrations.universal_integration_service import _query_anchored_excerpt

    head = "Cover page boilerplate " * 200
    target = "SHEET 7\nWG350DSAV DOUBLE MITER BAND SAW price 14145.00\n"
    tail = "tail padding " * 200
    text = head + target + tail
    excerpt = _query_anchored_excerpt(text, "WG350DSAV price", excerpt_chars=400)
    assert "WG350DSAV" in excerpt, "excerpt must center on the queried region"
    assert excerpt.index("WG350DSAV") < len(excerpt) // 2 + 100
    # no-match falls back to the head
    fallback = _query_anchored_excerpt(text, "nonexistent-token", excerpt_chars=200)
    assert fallback.startswith(text[:50])


def test_best_file_match_prefers_name_tokens():
    from integrations.universal_integration_service import UniversalIntegrationService

    hits = [
        {"id": "1", "name": "AR Running Balance.xlsx"},
        {"id": "2", "name": "Consolidated Price List 2019.xlsx"},
        {"id": "3", "name": "Cash Receipts - 2024.xlsx"},
    ]
    file_id, name = UniversalIntegrationService._best_file_match(
        hits, "Consolidated Price List 2019"
    )
    assert file_id == "2" and "Consolidated" in name
