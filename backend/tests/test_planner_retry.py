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


async def test_planner_routes_via_bpc_not_a_hardcoded_model(monkeypatch):
    """The planner must not name a model — routing is BPC's job.

    It used to pin ``("openrouter", PLANNER_MODEL)``. A ``provider_model`` pin
    collapses the handler's candidate list to that single tuple, so the leg had
    NO provider fallback at all: the same single point of failure that took the
    canvas editor down on a transient 429 (2026-09-10). The pin's original
    justification — unpinned routing preferring an unreachable local Ollama
    client — is now handled by BPC itself, which excludes connection-dead
    providers via `_filter_by_health` + the provider circuit breaker.
    """
    monkeypatch.setattr("core.chat_tool_planner.get_connected_services",
                        lambda user_id: ["outlook"])
    monkeypatch.setattr("core.chat_tool_planner._available_platform_services",
                        lambda: ["memory"])

    calls = []

    async def _gen(**kwargs):
        calls.append(kwargs)
        return ToolPlan(use_tool=True, service="outlook", intent="search",
                        query="jschultz blumetric")

    llm = SimpleNamespace(
        _get_handler=lambda *a, **k: SimpleNamespace(
            clients={"openrouter": object(), "openai": object()}),
        generate_structured_response=_gen,
    )
    plan = await plan_tool_use("find the blumetric email", HISTORY, "user-1", llm)

    assert plan is not None and plan.service == "outlook"
    assert len(calls) == 1, "no pin means there is nothing to retry"
    assert "provider_model" not in calls[0], (
        "the planner must let BPC rank models; a pin removes every fallback"
    )
    assert calls[0].get("disable_reasoning") is True, (
        "the pin's real purpose — a cheap non-reasoning plan — is kept on the "
        "request shape"
    )


async def test_planner_model_constant_is_gone():
    """A module-level model constant is what made the pin look configurable."""
    import core.chat_tool_planner as planner

    assert not hasattr(planner, "PLANNER_MODEL"), (
        "PLANNER_MODEL reintroduces a hardcoded planner model; BPC must choose"
    )


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
