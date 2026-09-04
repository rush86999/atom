"""Planner retry continuity — 'try again' after a failed tool turn must
re-plan instead of dying (which made the model answer from memory while
CLAIMING it had rechecked the mailbox, 2026-09-02).

Routing is LLM-owned end to end: the corrective pass is itself a structured
LLM call (it sees the catalog + conversation and re-decides service,
intent, query), replacing the old pattern repairs — service-name matching,
file-noun matching, recently-used fallback — which kept misrouting fluid
conversations because surface words don't reliably name the service.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.chat_tool_planner import ToolPlan, plan_tool_use


HISTORY = [
    {"role": "assistant", "content": "I rechecked the Outlook integration for any email from jschulz@blumetric.ca."},
    {"role": "user", "content": "try again"},
]


def _llm(*plans):
    llm = SimpleNamespace()
    llm.generate_structured_response = AsyncMock(side_effect=list(plans))
    return llm


async def test_retry_repaired_to_history_service_by_llm(monkeypatch):
    """'try again' after an outlook turn: the repair pass sees the history
    and re-plans outlook — a DECISION from context, not a regex hit."""
    monkeypatch.setattr("core.chat_tool_planner.get_connected_services",
                        lambda user_id: ["outlook", "zoho"])
    monkeypatch.setattr("core.chat_tool_planner._available_platform_services",
                        lambda: [])
    flaky = ToolPlan(use_tool=True, service=None, intent="search")
    repaired = ToolPlan(use_tool=True, service="outlook", intent="search",
                        query="jschulz blumetric")
    plan = await plan_tool_use("try again", HISTORY, "user-1",
                               _llm(flaky, repaired))
    assert plan.service == "outlook"
    assert "jschulz" in plan.query


async def test_retry_repair_query_recovers_substantive_terms(monkeypatch):
    """The repair pass authors the query from the conversation — the bare
    'try again' message itself carries nothing to search for."""
    monkeypatch.setattr("core.chat_tool_planner.get_connected_services",
                        lambda user_id: ["outlook"])
    monkeypatch.setattr("core.chat_tool_planner._available_platform_services",
                        lambda: [])
    flaky = ToolPlan(use_tool=True, service=None, intent="search")
    repaired = ToolPlan(use_tool=True, service="outlook", intent="search",
                        query="Jason dealer Blumetric")
    history = HISTORY + [
        {"role": "user",
         "content": "find and show me Jason's response. Also Mark is a dealer"},
    ]
    plan = await plan_tool_use("try again", history, "user-1",
                               _llm(flaky, repaired))
    assert "Jason" in plan.query


async def test_both_passes_fail_defaults_to_memory(monkeypatch):
    monkeypatch.setattr("core.chat_tool_planner.get_connected_services",
                        lambda user_id: ["outlook"])
    monkeypatch.setattr("core.chat_tool_planner._available_platform_services",
                        lambda: ["memory"])
    flaky = ToolPlan(use_tool=True, service=None, intent="search",
                     query="whatever")
    plan = await plan_tool_use("try again", HISTORY, "user-1",
                               _llm(flaky, flaky))
    assert plan.service == "memory"


async def test_pinned_planner_failure_retries_unpinned(monkeypatch):
    """BYOK gap: the pin collapses the handler's options to
    (openrouter, PLANNER_MODEL) — a single attempt on the workspace's BYOK
    OpenRouter key. A key that can't serve that model (out of credits,
    gated, revoked) returns None with NO provider fallback, which used to
    kill the whole routing leg. The planner must retry unpinned so the
    handler re-ranks across the tenant's OWN configured providers."""
    monkeypatch.setattr("core.chat_tool_planner.get_connected_services",
                        lambda user_id: ["outlook"])
    monkeypatch.setattr("core.chat_tool_planner._available_platform_services",
                        lambda: ["memory"])

    class _Handler:
        clients = {"openrouter": object()}

    calls = []

    async def _gen(**kwargs):
        calls.append(kwargs.get("provider_model"))
        if kwargs.get("provider_model"):
            return None  # pinned BYOK attempt fails
        return ToolPlan(use_tool=True, service="outlook", intent="search",
                        query="jschulz blumetric")

    llm = SimpleNamespace(
        _get_handler=lambda *a, **k: _Handler(),
        generate_structured_response=_gen,
    )
    plan = await plan_tool_use("try again", HISTORY, "user-1", llm)
    assert plan is not None and plan.service == "outlook"
    assert calls[0] == ("openrouter", "qwen/qwen3.7-flash")
    assert calls[1] is None  # unpinned retry


async def test_memory_service_always_available(monkeypatch):
    """The memory tool queries the workspace's OWN ingested data — it must
    never be gated on the Tavily web-search key (coupling made it vanish
    wherever web search wasn't configured)."""
    import os

    from core.chat_tool_planner import _available_platform_services

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert "memory" in _available_platform_services()
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    assert "memory" in _available_platform_services()
