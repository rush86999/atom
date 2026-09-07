"""Generalized ingested-mailbox supplement for communication services.

The jschulz@blumetric.ca failure (live 2026-09-06) was fixed for outlook
with a dedicated leg; every other mailbox/chat service (gmail, slack,
telegram, …) routes through the universal integration path, where a live
search that "succeeds" with provider-relevance junk — or returns nothing —
had no deterministic ingested-copy rescue. These tests pin the generalized
behavior: ranked ingested lines LEAD the block on success, carry the
dead-end when the live search returns nothing, and the outlook leg shares
the same helper."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import asyncio
from unittest.mock import patch, MagicMock

import core.chat_tool_planner as planner
from core.chat_tool_planner import ToolPlan, execute_tool_plan, _haystack_has_address


def _fake_universal_module(status="success", data=None):
    """Inject a fake integrations.universal_integration_service so the
    universal path runs without tokens or network."""
    class _FakeSvc:
        def __init__(self, *a, **kw):
            pass

        async def search(self, service, query, context=None):
            return {"status": status, "data": data}

        async def execute(self, service, action, params=None, context=None):
            return {"status": status, "data": data}

    mod = MagicMock()
    mod.UniversalIntegrationService = _FakeSvc
    mod.SEARCHABLE_SERVICES = frozenset({"gmail", "slack", "notion"})
    sys.modules["integrations.universal_integration_service"] = mod
    return mod


def _plan(service, query):
    return ToolPlan(use_tool=True, service=service, intent="search",
                    query=query, reason="test")


def _mailbox_lines(n=2):
    return [f"- [ingested mailbox] From: a@b.com | hit {i} | body | ts" for i in range(n)]


def test_haystack_address_detects_query_and_history():
    assert _haystack_has_address("jschulz@blumetric.ca quote", {}) is True
    assert _haystack_has_address("no address here", {"history": [
        {"message": "email Jacob at jacob@x.com please"}]}) is True
    assert _haystack_has_address("no address anywhere", {"history": [
        {"message": "plain words only"}]}) is False


def test_mailbox_lines_dedupes_addresses_across_query_and_history():
    calls = []

    with patch.object(planner, "_search_ingested_by_address",
                      side_effect=lambda uid, addr: calls.append(addr) or []):
        asyncio.run(planner._ingested_mailbox_lines(
            "u1", "jschulz@blumetric.ca quote",
            {"history": [{"message": "from jschulz@blumetric.ca"}]}))
    assert calls == ["jschulz@blumetric.ca"]  # scanned ONCE, not twice


def test_gmail_live_junk_with_ingested_hits_leads_with_mailbox():
    _fake_universal_module(
        status="success",
        data={"results": [{"snippet": "zoho lead form for someone else"}]},
    )
    async def fake_mail_lines(user_id, query, context=None, cap=6, hybrid_min=4):
        return _mailbox_lines(2)

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=fake_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("gmail", "jschulz@blumetric.ca"), "u1", "default", context={}))

    assert "INGESTED MAILBOX matches first" in block
    assert block.index("[ingested mailbox]") < block.index("Live gmail results")
    assert "supplemental" in block


def test_gmail_live_empty_uses_mailbox_lines_not_dead_end():
    _fake_universal_module(status="success", data=None)

    async def fake_mail_lines(user_id, query, context=None, cap=6, hybrid_min=4):
        return _mailbox_lines(1)

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=fake_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("gmail", "find the thread"), "u1", "default", context={}))

    assert "returned nothing usable" in block
    assert "[ingested mailbox]" in block


def test_gmail_empty_and_no_mailbox_still_honest_dead_end():
    _fake_universal_module(status="success", data=None)

    async def fake_mail_lines(user_id, query, context=None, cap=6, hybrid_min=4):
        return []

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=fake_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("gmail", "nothing anywhere"), "u1", "default", context={}))

    assert "returned nothing usable" in block
    assert "[ingested mailbox]" not in block


def test_slack_execute_path_gets_the_same_supplement():
    _fake_universal_module(status="success", data=None)

    async def fake_mail_lines(user_id, query, context=None, cap=6, hybrid_min=4):
        return _mailbox_lines(1)

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=fake_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("slack", "deploy discussion"), "u1", "default", context={}))

    # slack has NO search handler in the fake: status success with data=None
    # hits the dead-end branch, where the mailbox supplement now applies.
    assert "[ingested mailbox]" in block


def test_non_comm_service_without_address_is_untouched():
    _fake_universal_module(status="success", data={"results": ["real page hit"]})

    async def must_not_run(*a, **kw):
        raise AssertionError("supplement must not run for non-comm, no-address queries")

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=must_not_run), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("notion", "quarterly planning pages"), "u1", "default", context={}))

    assert "INGESTED MAILBOX" not in block
    assert "real page hit" in block


def test_address_in_history_triggers_supplement_for_crm_service():
    _fake_universal_module(status="success", data={"results": ["lead record"]})

    async def fake_mail_lines(user_id, query, context=None, cap=6, hybrid_min=4):
        return _mailbox_lines(1)

    with patch.object(planner, "_ingested_mailbox_lines", side_effect=fake_mail_lines), \
         patch.object(planner, "_memory_search_block", return_value=None):
        block = asyncio.run(execute_tool_plan(
            _plan("zoho_crm", "find this lead"),
            "u1", "default",
            context={"history": [{"message": "the lead is jschulz@blumetric.ca"}]}))

    assert "INGESTED MAILBOX matches first" in block
