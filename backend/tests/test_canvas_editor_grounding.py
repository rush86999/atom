"""Canvas editor fresh-data evidence + external-facts grounding — regressions.

Live 2026-09-03 ("consolidated price list"): the canvas EDITOR received only
a history transcript — no tool evidence — so an edit asking for "the price
from the consolidated price list" typed a fabricated $14,500.00 straight
into the email draft (the workbook said $14,145.00), and the chat path then
"confirmed" the corrected value just as baselessly. The chat path already
carries a grounding rule on its tool blocks; these tests pin the editor-side
closure: the orchestrator fetches live evidence via the SAME read-only tool
planner the chat path uses (fetch_fresh_data_section) and hands it to
plan_canvas_edit as a FRESH DATA section, and the editor prompt carries the
EXTERNAL FACTS rule so unfilled values are placeholder-marked, never
invented.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_canvas_editor import (
    _ACTION_SYSTEM,
    _EDITOR_SYSTEM,
    _FRESH_DATA_TIMEOUT_SECONDS,
    CanvasActionPlan,
    CanvasEditPlan,
    fetch_fresh_data_section,
    plan_canvas_action,
    plan_canvas_edit,
)
from core.chat_tool_planner import ToolPlan


def _canvas():
    return {
        "canvas_id": "c-1",
        "canvas_type": "email",
        "content": "<p>Quote draft for Jacob.</p>",
        "title": "Quote — WG-350DSAV",
    }


def _editor_llm(plan: CanvasEditPlan):
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=plan)
    llm._get_handler = MagicMock(return_value=MagicMock(clients={}))
    return llm


def _edit_plan():
    return CanvasEditPlan(
        wants_edit=True,
        edit_mode="replace",
        updated_content_json='{"body": "<p>draft with price</p>"}',
        reply="Added the price row.",
    )


PRICE_BLOCK = (
    "LIVE TOOL RESULTS (memory.search, query='consolidated price list') "
    "— WG350DSAV Bandsaw $14,145.00\n\nGROUNDING RULE: specific facts ..."
)


# ── system prompt contract ──────────────────────────────────────────────


def test_editor_system_carries_external_facts_rule():
    assert "EXTERNAL FACTS" in _EDITOR_SYSTEM
    assert "FRESH DATA" in _EDITOR_SYSTEM


# ── evidence fetching (orchestrator-side helper) ────────────────────────


@pytest.mark.asyncio
async def test_fetch_returns_section_when_planner_fires():
    with patch("core.chat_tool_planner.plan_tool_use",
               AsyncMock(return_value=ToolPlan(
                   use_tool=True, service="memory", intent="search",
                   query="consolidated price list", reason="file value"))) as planner, \
         patch("core.chat_tool_planner.execute_tool_plan",
               AsyncMock(return_value=PRICE_BLOCK)) as execute:
        section = await fetch_fresh_data_section(
            "add the price from the consolidated price list", [],
            MagicMock(), "user-1",
        )
    assert section.startswith("FRESH DATA for this edit")
    assert "$14,145.00" in section
    assert "GROUNDING RULE" in section
    # planner ran with the caller's user id (connected services + memory
    # scoping are per user)
    planner.assert_awaited_once()
    assert planner.await_args.args[2] == "user-1"
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_empty_when_planner_declines():
    with patch("core.chat_tool_planner.plan_tool_use",
               AsyncMock(return_value=ToolPlan(use_tool=False, reason="style edit"))), \
         patch("core.chat_tool_planner.execute_tool_plan", AsyncMock()) as execute:
        section = await fetch_fresh_data_section(
            "make the heading bold", [], MagicMock(), "user-1")
    assert section == ""
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_failure_does_not_raise():
    with patch("core.chat_tool_planner.plan_tool_use",
               AsyncMock(side_effect=RuntimeError("planner down"))):
        assert await fetch_fresh_data_section(
            "add the price from the price list", [], MagicMock(), "user-1",
        ) == ""


@pytest.mark.asyncio
async def test_fetch_bounded_by_timeout(monkeypatch):
    """Evidence gathering must never cost the edit its own turn."""
    monkeypatch.setattr(
        "core.chat_canvas_editor._FRESH_DATA_TIMEOUT_SECONDS", 0.05)

    async def slow_planner(*a, **k):
        await asyncio.sleep(2)
        return ToolPlan(use_tool=True, service="memory", query="x")

    with patch("core.chat_tool_planner.plan_tool_use", slow_planner):
        section = await fetch_fresh_data_section(
            "add the price", [], MagicMock(), "user-1")
    assert section == ""


# ── editor prompt rendering ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fresh_data_rendered_into_edit_prompt():
    llm = _editor_llm(_edit_plan())
    plan = await plan_canvas_edit(
        "add the price from the consolidated price list",
        [], _canvas(), llm,
        fresh_data="FRESH DATA for this edit (live tool results, fetched just "
                   f"now):\n{PRICE_BLOCK}\n\n",
    )
    assert plan is not None and plan.wants_edit
    prompt = llm.generate_structured_response.await_args.kwargs["prompt"]
    assert "FRESH DATA for this edit" in prompt
    assert "$14,145.00" in prompt
    assert "GROUNDING RULE" in prompt


@pytest.mark.asyncio
async def test_no_fresh_section_by_default():
    llm = _editor_llm(_edit_plan())
    plan = await plan_canvas_edit(
        "make the heading bold", [], _canvas(), llm,
    )
    assert plan is not None and plan.wants_edit
    prompt = llm.generate_structured_response.await_args.kwargs["prompt"]
    # The EXTERNAL FACTS rule in _EDITOR_SYSTEM mentions the section by
    # name; the absence check is for the fetched section itself.
    assert "FRESH DATA for this edit" not in prompt


def test_timeout_constant_keeps_edit_turn_responsive():
    # The orchestrator gives planning 30s; evidence gathering must stay
    # well under it (planner + tool execution live inside this bound).
    assert _FRESH_DATA_TIMEOUT_SECONDS <= 15


# ── action planner (send path) — same grounding, all canvases ───────────


def test_action_system_carries_external_facts_rule():
    assert "EXTERNAL FACTS" in _ACTION_SYSTEM or "EXTERNAL FACTS travel" in _ACTION_SYSTEM
    assert "FRESH DATA" in _ACTION_SYSTEM


@pytest.mark.asyncio
async def test_action_plan_renders_fresh_data_into_prompt():
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=CanvasActionPlan(
        wants_action=True, action="send_email", to="jacob@example.com",
        reply="Sending with the price.",
    ))
    llm._get_handler = MagicMock(return_value=MagicMock(clients={}))
    plan = await plan_canvas_action(
        "send it with the current price", [], _canvas(), llm,
        fresh_data=f"FRESH DATA for this edit (live tool results, fetched just "
                   f"now):\n{PRICE_BLOCK}\n\n",
    )
    assert plan is not None and plan.wants_action
    prompt = llm.generate_structured_response.await_args.kwargs["prompt"]
    assert "FRESH DATA for this edit" in prompt
    assert "$14,145.00" in prompt
    assert "GROUNDING RULE" in prompt


@pytest.mark.asyncio
async def test_action_plan_has_no_fresh_section_by_default():
    llm = MagicMock()
    llm.generate_structured_response = AsyncMock(return_value=CanvasActionPlan(
        wants_action=True, action="send_email", reply="Sending.",
    ))
    llm._get_handler = MagicMock(return_value=MagicMock(clients={}))
    plan = await plan_canvas_action("send it", [], _canvas(), llm)
    assert plan is not None and plan.wants_action
    prompt = llm.generate_structured_response.await_args.kwargs["prompt"]
    # The EXTERNAL FACTS rule names the section; absence check targets the
    # fetched section itself.
    assert "FRESH DATA for this edit" not in prompt
