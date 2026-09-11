"""Explicit web-research floor — the 2026-09-08 canvas wobble.

Live incident: "web research lead's bandsaw that was mentioned and compare
it o our bandsaw. give me a response but don't update the draft" — the LLM
planner returned use_tool=false, no tool ran, and the reply claimed "I can't
run live web research in this session — I don't have a web-search tool
available here" while Tavily was fully configured.

The fix is a hybrid per repo standards (LLM routing over intent regexes):
a regex DETECTOR only flags the explicit instruction; one corrective
structured pass still owns routing; a deterministic web_search rung fires
only when that pass also fails. A matching orchestrator guard keeps
inability claims honest when no tool block exists at all.
"""
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_tool_planner import (
    ToolPlan,
    _explicit_web_research_requested,
    plan_tool_use,
)


# ─────────────────────────── detector ───────────────────────────

def test_detector_fires_on_the_live_message():
    assert _explicit_web_research_requested(
        "web research lead's bandsaw that was mentioned and compare it o "
        "our bandsaw. give me a response but don't update the draft")
    assert _explicit_web_research_requested(
        "search the web for the Hydmech DM10 bandsaw specifications")


def test_detector_fires_on_common_phrasings():
    assert _explicit_web_research_requested("google it")
    assert _explicit_web_research_requested("check brennan.ca online for the model")
    assert _explicit_web_research_requested("look up the company online")
    assert _explicit_web_research_requested("research it over the web")


def test_detector_ignores_negated_instructions():
    assert not _explicit_web_research_requested(
        "don't web research, just use the file in WorkDrive")
    assert not _explicit_web_research_requested(
        "no web research needed, answer from memory")
    assert not _explicit_web_research_requested(
        "without web research, draft the reply from the catalog")


def test_detector_ignores_non_web_research_asks():
    assert not _explicit_web_research_requested(
        "research the file in WorkDrive for the price")
    assert not _explicit_web_research_requested(
        "compare the two bandsaws for me")
    assert not _explicit_web_research_requested("")
    assert not _explicit_web_research_requested(None)


# ─────────────────────── planner floor wiring ───────────────────────

def _declined(reason="conversation suffices"):
    return ToolPlan(use_tool=False, service=None, intent="search",
                    query=None, reason=reason)


@pytest.mark.asyncio
async def test_declined_plan_on_explicit_ask_gets_llm_repair():
    """Repair pass runs, sees the defect, and its plan wins."""
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_declined())
    repaired = ToolPlan(use_tool=True, service="web_fetch", intent="search",
                        query="hydmech.com DM-10", reason="explicit ask")
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock, return_value=repaired) as repair:
        result = await plan_tool_use(
            "web research the lead's bandsaw and compare", [], "u1", llm)
    assert result is repaired
    assert "EXPLICITLY asked for web research" in repair.call_args.args[1]


@pytest.mark.asyncio
async def test_double_decline_falls_to_deterministic_web_search():
    """Both LLM passes decline on an EXPLICIT instruction — the floor runs
    web_search with a query built from the conversation, not the raw
    sentence."""
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_declined())
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock, return_value=_declined("still no")):
        result = await plan_tool_use(
            "web research Acme Industrial and compare to our saw",
            [{"message": "Acme Industrial sent the DM10 inquiry"}],
            "u1", llm)
    assert result is not None and result.use_tool
    assert result.service == "web_search"
    assert "acme industrial" in (result.query or "").lower()


@pytest.mark.asyncio
async def test_repair_non_web_route_falls_to_floor():
    """Live 2026-09-08 second wobble: on an explicit WEB ask the repair LLM
    picked memory.search — the tool ran, and the reply STILL claimed no
    web-search tool exists. A non-web route does not satisfy an explicit
    web instruction; the deterministic web_search rung fires instead."""
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_declined())
    memory_route = ToolPlan(use_tool=True, service="memory", intent="search",
                            query="bandsaw", reason="")
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock, return_value=memory_route):
        result = await plan_tool_use(
            "web research the lead's bandsaw and compare to ours", [], "u1",
            llm)
    assert result is not None and result.service == "web_search"
    assert result.use_tool


@pytest.mark.asyncio
async def test_valid_off_web_plan_also_gets_the_floor():
    """Live 2026-09-08 third wobble: pass 1 returned a VALID memory.search
    plan (use_tool=true) on an explicit web ask — no decline, yet the reply
    still claimed no web-search tool exists. The floor must cover every
    non-web first-pass outcome, not just declines."""
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=ToolPlan(
        use_tool=True, service="memory", intent="search",
        query="bandsaw mentioned lead", reason=""))
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock, return_value=_declined("keep memory")):
        result = await plan_tool_use(
            "web research the lead's bandsaw and compare to ours", [], "u1",
            llm)
    assert result is not None and result.service == "web_search"


@pytest.mark.asyncio
async def test_negated_ask_keeps_the_decline():
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_declined())
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock) as repair:
        result = await plan_tool_use(
            "don't web research, use the WorkDrive sheet", [], "u1", llm)
    assert result is not None and not result.use_tool
    repair.assert_not_awaited()


@pytest.mark.asyncio
async def test_floor_skipped_when_search_unavailable(monkeypatch):
    """No Tavily key: the decline is honest — no repair, no forced search."""
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_declined())
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock) as repair:
        result = await plan_tool_use(
            "web research the lead's bandsaw", [], "u1", llm)
    assert result is not None and not result.use_tool
    repair.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_escalation_when_plan_already_uses_tool():
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=ToolPlan(
        use_tool=True, service="web_search", intent="search",
        query="hydmech dm10 specs", reason=""))
    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock) as repair:
        result = await plan_tool_use(
            "search the web for hydmech dm10 specs", [], "u1", llm)
    assert result.service == "web_search"
    repair.assert_not_awaited()


# ───────────── canvas-editor leg: canvas reaches the executor ─────────────

@pytest.mark.asyncio
async def test_fresh_data_leg_sends_canvas_to_the_executor():
    """Live 2026-09-08: the canvas-editor fresh-data leg executed the
    explicit-web-research floor's plan with context={"history"} only — the
    rewrite had no canvas, the query stayed generic ("lead's bandsaw…"),
    and Tavily returned buying guides instead of the models the open draft
    names. The leg must forward the canvas like the chat path does."""
    from core.chat_canvas_editor import fetch_fresh_data_section

    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=_declined())
    captured = {}

    async def fake_execute(plan, user_id, tenant_id="default", context=None,
                           llm_service=None):
        captured["context"] = context
        return "LIVE TOOL RESULTS (web_search): specs"

    with patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock, return_value=_declined()), \
         patch("core.chat_tool_planner.execute_tool_plan",
               new_callable=AsyncMock, side_effect=fake_execute):
        fresh = await fetch_fresh_data_section(
            "web research the lead's bandsaw and compare", [], llm, "u1",
            canvas_id="cv1",
            canvas={"canvas_id": "cv1", "canvas_type": "email",
                    "title": "Re: Equivalent to Hydmech DM10 Bandsaw",
                    "content": {"to": "jschulz@blumetric.ca",
                                "subject": "Hydmech DM10 vs Linmac WG-350DSAV",
                                "body": "details"}},
        )
    assert fresh.needed and fresh.ok
    canvas_ctx = captured["context"]["canvas"]
    assert "Hydmech DM10" in canvas_ctx.get("subject", "")
    assert canvas_ctx.get("title")


# ───────────── singleflight: one plan + one execution per turn ─────────────

@pytest.mark.asyncio
async def test_fresh_data_leg_joins_shared_plan_task():
    """Research: plan-and-execute (plan once, share across executors) +
    singleflight (duplicate executions collapse into one). The editor leg
    must JOIN the chat leg's in-flight plan task instead of paying for a
    second planner LLM call, and hand the executed block back so the chat
    leg never re-executes it."""
    import asyncio

    from core.chat_canvas_editor import fetch_fresh_data_section

    llm = MagicMock()
    web_plan = ToolPlan(use_tool=True, service="web_search", intent="search",
                        query="hydmech dm10 vs linmac wg-350dsav", reason="")

    async def _planned():
        return web_plan

    plan_task = asyncio.ensure_future(_planned())

    async def _planner_should_not_run(*a, **k):
        raise AssertionError("plan_tool_use called despite shared plan_task")

    async def fake_execute(plan, user_id, tenant_id="default", context=None,
                           llm_service=None):
        assert context["canvas"]["subject"].startswith("Hydmech DM10")
        return "LIVE TOOL RESULTS (web_search, query='x'): DM-10 specs"

    with patch("core.chat_tool_planner.plan_tool_use",
               side_effect=_planner_should_not_run), \
         patch("core.chat_tool_planner.execute_tool_plan",
               new_callable=AsyncMock, side_effect=fake_execute):
        fresh = await fetch_fresh_data_section(
            "web research the lead's bandsaw and compare", [], llm, "u1",
            canvas_id="cv1",
            canvas={"canvas_id": "cv1", "title": "Hydmech DM10 Bandsaw",
                    "content": {"subject": "Hydmech DM10 vs Linmac",
                                "body": "details"}},
            plan_task=plan_task,
        )
    assert fresh.needed and fresh.ok
    assert "DM-10 specs" in fresh.block
    assert "FRESH DATA for this edit" in fresh.section


@pytest.mark.asyncio
async def test_fresh_data_leg_survives_failed_shared_plan():
    """A failed shared plan degrades to 'no live lookup needed' — the edit
    path continues without evidence instead of raising."""
    import asyncio

    from core.chat_canvas_editor import fetch_fresh_data_section

    llm = MagicMock()

    async def _boom():
        raise RuntimeError("planner down")

    plan_task = asyncio.ensure_future(_boom())
    with patch("core.chat_tool_planner.plan_tool_use",
               new_callable=AsyncMock) as planner, \
         patch("core.chat_tool_planner.execute_tool_plan",
               new_callable=AsyncMock) as execute:
        fresh = await fetch_fresh_data_section(
            "web research the lead's bandsaw", [], llm, "u1",
            plan_task=plan_task,
        )
    assert not fresh.needed and fresh.ok and not fresh.block
    planner.assert_not_awaited()
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_fresh_data_timeout_leaves_shared_plan_task_alive(monkeypatch):
    """Live 2026-09-08: the fresh-data wait_for timeout CANCELLED the shared
    plan task (cancellation propagates through a plain `await task`), so a
    slow planner under rate limiting killed the whole turn. The shield must
    keep the shared task alive for the chat leg."""
    import asyncio

    import core.chat_canvas_editor as cce
    from core.chat_canvas_editor import fetch_fresh_data_section

    llm = MagicMock()

    async def _slow_plan():
        await asyncio.sleep(0.3)
        return ToolPlan(use_tool=False, reason="slow planner")

    plan_task = asyncio.ensure_future(_slow_plan())
    monkeypatch.setattr(cce, "_FRESH_DATA_PLAN_TIMEOUT_SECONDS", 0.05)
    fresh = await fetch_fresh_data_section(
        "web research the lead's bandsaw", [], llm, "u1", plan_task=plan_task,
    )
    # Timeout path: edit evidence declined honestly…
    assert fresh.needed and not fresh.ok and not fresh.block
    # …and the shared task survived for the chat leg.
    assert not plan_task.cancelled()
    plan = await plan_task
    assert plan is not None and not plan.use_tool


@pytest.mark.asyncio
async def test_floor_skips_llm_repair_when_provider_gave_no_plan():
    """Live 2026-09-08 (429 storm): the first pass returned None (provider
    failure, no decision) and the repair LLM call just multiplied latency
    into the same failing provider. No decision -> deterministic rung
    immediately."""
    llm = MagicMock()
    with patch("core.chat_tool_planner._structured_with_fallback",
               new_callable=AsyncMock, return_value=None), \
         patch("core.chat_tool_planner.get_connected_services",
               return_value=[]), \
         patch("core.chat_tool_planner._repair_plan_via_llm",
               new_callable=AsyncMock) as repair:
        result = await plan_tool_use(
            "web research the lead's bandsaw and compare to ours", [], "u1",
            llm)
    assert result is not None and result.service == "web_search"
    repair.assert_not_awaited()


# ───────────── orchestrator wiring (shape pins) ──────────────────────────

def test_turn_blackboard_wired_through_process_chat_message():
    """process_chat_message must create the shared carrier (plan task in,
    executed block out), pass it to the edit leg, and hand any prefetched
    block to the chat leg."""
    import inspect
    from integrations import chat_orchestrator as co
    src = inspect.getsource(co.ChatOrchestrator.process_chat_message)
    assert '"plan_task": _tool_plan_task' in src
    assert "shared_tool_state=_shared_tool" in src
    assert "prefetched_tool_block=_shared_tool.get(\"block\")" in src

    edit_src = inspect.getsource(co.ChatOrchestrator._try_canvas_edit)
    assert "plan_task=(shared_tool_state or {}).get(\"plan_task\")" in edit_src
    assert "shared_tool_state[\"block\"] = fresh.block or None" in edit_src


def test_chat_leg_reuses_prefetched_block_without_reexecution():
    """_get_qwen_response must skip planner+executor entirely when the turn
    blackboard carries an already-executed block."""
    import inspect
    from integrations import chat_orchestrator as co
    src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
    assert "if prefetched_tool_block:" in src
    assert "reused canvas-edit leg" in src


# ───────────── non-responsive reply guard (2026-09-08 wobble) ─────────────

def test_generic_non_answer_detected():
    from integrations.chat_orchestrator import _reply_is_generic_non_answer
    msg = ("web research lead's bandsaw that was mentioned and compare it o "
           "our bandsaw. give me a response but don't update the draft")
    assert _reply_is_generic_non_answer(
        "I've processed your request across all connected platforms.", msg)


def test_substantive_and_short_addressing_replies_not_flagged():
    from integrations.chat_orchestrator import _reply_is_generic_non_answer
    msg = "web research lead's bandsaw and compare it to our bandsaw"
    assert not _reply_is_generic_non_answer(
        "The Hydmech DM10 cuts 10-inch rounds; our Linmac WG-350DSAV cuts "
        "10.64-inch rounds with inverter variable speed — the comparison "
        "holds on capacity, miter range and speed control.", msg)
    # short but genuinely addressing the ask -> overlap -> not flagged
    assert not _reply_is_generic_non_answer(
        "Found the bandsaw comparison — see the table above.", msg)
    # long replies are out of scope for the guard
    assert not _reply_is_generic_non_answer(
        "x" * 300, msg)


def test_non_responsive_guard_wired_on_both_reply_paths():
    import inspect
    from integrations import chat_orchestrator as co
    src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
    # streaming: condition + clean-check; non-streaming: condition only
    # (matching its sibling guards, which overwrite without re-checking)
    assert src.count("_reply_is_generic_non_answer(") == 3
    assert src.count("generic non-answer") >= 2


def test_tool_choice_json_mode_fallback_pinned():
    """Thinking-mode models reject instructor Mode.TOOLS' tool_choice=
    'required' with a 400 (98 occurrences live 2026-09-08, breaking the
    structured fallback ladder). The handler must retry once in JSON mode
    and memoize the provider/model pair."""
    import inspect
    from core.llm import byok_handler
    src = inspect.getsource(byok_handler)
    assert "_TOOLCHOICE_UNSUPPORTED" in src
    assert "instructor.Mode.JSON" in src
    assert "tool_choice" in src and "thinking" in src


# ───────────────── orchestrator guard wiring (shape pins) ─────────────────

def test_capability_honesty_guard_wired_on_both_reply_paths():
    """The no-tool-block inability guard must sit on the streaming AND the
    non-streaming path of _get_qwen_response, like the grounding guard."""
    import inspect
    from integrations import chat_orchestrator as co
    src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
    assert src.count("capability-honest") == 2
    assert src.count("Your previous reply claimed you lack web research") == 2
    assert src.count("_explicit_web_research_requested(message)") == 2
