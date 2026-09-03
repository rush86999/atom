"""Planner retry continuity — 'try again' after a failed tool turn must
re-plan deterministically instead of dying (which made the model answer
from memory while CLAIMING it had rechecked the mailbox, 2026-09-02)."""

from core.chat_tool_planner import (
    _fallback_service_from_history,
    _retry_query_from_history,
)


HISTORY = [
    {"role": "assistant", "content": "I rechecked the Outlook integration for any email from jschulz@blumetric.ca."},
    {"role": "user", "content": "try again"},
]


def test_fallback_finds_mentioned_service():
    assert _fallback_service_from_history(HISTORY, ["outlook", "zoho"], "try again") == "outlook"


def test_fallback_scans_any_entry_shape():
    """Session history entries aren't guaranteed role/content dicts — every
    string value is scanned."""
    weird = [{"text": "the outlook mailbox had nothing", "other": 5}, {"role": "user"}]
    assert _fallback_service_from_history(weird, ["outlook"], "try again") == "outlook"


def test_bare_retry_defaults_to_connected_mailbox():
    empty = [{"role": "user", "content": "try again"}]
    assert _fallback_service_from_history(empty, ["outlook", "zoho"], "try again") == "outlook"
    assert _fallback_service_from_history(empty, ["zoho", "gmail"], "keep looking") == "gmail"
    # No retry imperative and no mention → no guess.
    assert _fallback_service_from_history(empty, ["outlook"], "what is 2+2") is None


def test_retry_query_recovers_last_substantive_user_message():
    history = HISTORY + [
        {"role": "user", "content": "find and show me Jason's response. Also Mark is a dealer and not an employee of Brennan"},
    ]
    q = _retry_query_from_history(history, "try again")
    assert "Jason" in q and "dealer" in q
    # With no prior substantive user message, the bare message is the
    # documented fallback (the search runs on weak terms; the ingested-
    # store supplement carries the result).
    assert _retry_query_from_history(HISTORY, "try again") == "try again"


def test_memory_service_always_available(monkeypatch):
    """The memory tool queries the workspace's OWN ingested data — it must
    never be gated on the Tavily web-search key (coupling made it vanish
    wherever web search wasn't configured)."""
    import os

    from core.chat_tool_planner import _available_platform_services

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert "memory" in _available_platform_services()
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    assert "memory" in _available_platform_services()
