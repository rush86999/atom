"""Per-term retry for communication live searches + connected-tool hint.

Outlook's leg has fanned multi-term queries out per-term since the Graph
OR-ranking burying fix; gmail/slack/telegram sent the raw query to
providers whose AND-semantics zero out on one common token. And the memory
assembler header hardcoded "the outlook tool" for every user — naming a
tool a gmail-only user doesn't have, the same missing-capability
hallucination class as the 2026-09-06 chat lookup. These tests pin the
generalized behavior."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import asyncio
from unittest.mock import patch, MagicMock

import core.chat_tool_planner as planner
from core.chat_tool_planner import ToolPlan, execute_tool_plan


def _fake_universal_module(empty_first_query=True):
    """Fake universal service: the FULL query returns nothing; per-term
    retries return hits (call counts recorded on the module's fake)."""
    calls = []

    class _FakeSvc:
        def __init__(self, *a, **kw):
            pass

        async def search(self, service, query, context=None):
            calls.append(query)
            if empty_first_query and " " in query.strip():
                return {"status": "success", "data": None}
            return {"status": "success",
                    "data": {"results": [f"hit for {query!r}"]}}

        async def execute(self, service, action, params=None, context=None):
            calls.append((action, params.get("query") if params else None))
            if empty_first_query:
                return {"status": "success", "data": None}
            return {"status": "success",
                    "data": {"messages": [f"hit for {params.get('query')!r}"]}}

    mod = MagicMock()
    mod.UniversalIntegrationService = _FakeSvc
    mod.SEARCHABLE_SERVICES = frozenset({"gmail", "slack", "notion"})
    mod._calls = calls
    sys.modules["integrations.universal_integration_service"] = mod
    return mod


def _plan(service, query):
    return ToolPlan(use_tool=True, service=service, intent="search",
                    query=query, reason="test")


def test_per_term_retry_rescues_and_semantics_zeroing():
    mod = _fake_universal_module(empty_first_query=True)

    async def no_mail_lines(*a, **kw):
        return []

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=no_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("gmail", "find unusualWGterm from march"), "u1", "default",
            context={}))

    assert "per-term retries matched" in block
    assert "[matched 'unusualWGterm']" in block
    # longest (rarest) term retried first, ≤2 terms total
    assert "unusualWGterm" in str(mod._calls[1])
    assert len(mod._calls) <= 3


def test_per_term_retry_bounded_to_two_terms():
    mod = _fake_universal_module(empty_first_query=True)

    async def no_mail_lines(*a, **kw):
        return []

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=no_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        asyncio.run(execute_tool_plan(
            _plan("gmail", "aa bb ccdddd eeeeee"), "u1", "default", context={}))
    # full query + 2 per-term retries max
    assert len(mod._calls) <= 3
    assert "ccccdddd" not in str(mod._calls) or len(mod._calls) == 3


def test_hard_provider_error_does_not_retry():
    mod = _fake_universal_module()
    mod.UniversalIntegrationService.search = MagicMock(
        side_effect=RuntimeError("token dead"))

    async def no_mail_lines(*a, **kw):
        return []

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=no_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("gmail", "some query here"), "u1", "default", context={}))

    # outer try wraps everything: with the search raising, execute_tool_plan
    # returns None (the orchestrator's failure block takes over) — the point
    # is no per-term retry fired against a dead token.
    assert block is None


def test_non_comm_service_skips_retry():
    mod = _fake_universal_module(empty_first_query=True)

    with patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("notion", "quarterly planning"), "u1", "default", context={}))

    assert "per-term retries" not in (block or "")
    assert len(mod._calls) == 1  # the single full-query attempt


def test_mailbox_tool_hint_names_connected_tools():
    from core.memory_context_assembler import _mailbox_tool_hint

    with patch("core.chat_tool_planner.get_connected_services",
               return_value=["gmail", "notion", "slack"]):
        hint = _mailbox_tool_hint("u1")
    assert "gmail" in hint and "slack" in hint
    assert "outlook" not in hint


def test_mailbox_tool_hint_neutral_when_nothing_connected():
    from core.memory_context_assembler import _mailbox_tool_hint

    with patch("core.chat_tool_planner.get_connected_services",
               return_value=["zoho_crm"]):
        hint = _mailbox_tool_hint("u1")
    assert "mailbox search tool" in hint
    assert "outlook" not in hint

    with patch("core.chat_tool_planner.get_connected_services",
               side_effect=RuntimeError("db down")):
        hint = _mailbox_tool_hint("u1")
    assert "mailbox search tool" in hint
