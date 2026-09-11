"""Fresh-data evidence budget: the PLANNER wait vs the LOOKUP budget.

Regression context (live 2026-09-11, canvas a1a13834 — the Foot Shear quote):
the canvas co-editor charged the shared PLANNER's latency to the 25s EVIDENCE
budget, timed out, declined a data-INDEPENDENT header-style edit, and the
conversational fallback then shipped "Done — here's what I changed" for an
edit that never landed (execution 874668b5…, session r90e-verify: the shared
planner resolved ~37s after the 25s cap).

These tests pin the split introduced by the fix:
  * a planner that resolves to "no live data needed" AFTER the old budget
    must let the edit proceed (planner latency is the chat leg's cost, not
    evidence-fetch cost);
  * when even the (generous) planner cap is exceeded with no verdict in, the
    edit declines with needed/ok = True/False (the orchestrator then flags
    the turn no-edit);
  * the LOOKUP keeps its own budget — a plan that needs live data but whose
    retrieval overruns still declines, never fabricates.

Kept in its own module because test_chat_canvas_editor.py installs an autouse
fixture that mocks fetch_fresh_data_section for every test in that file.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.chat_canvas_editor as ed


@pytest.mark.asyncio
async def test_slow_planner_without_lookup_need_does_not_decline(monkeypatch):
    """Planner latency must NOT be charged to the evidence budget."""
    monkeypatch.setattr(ed, "_FRESH_DATA_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(ed, "_FRESH_DATA_PLAN_TIMEOUT_SECONDS", 1.0)

    async def slow_plan():
        await asyncio.sleep(0.2)  # 4x the old budget, under the planner cap
        return SimpleNamespace(use_tool=False)

    res = await ed.fetch_fresh_data_section(
        "fix the table header background color with text",
        [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(slow_plan()),
    )
    assert res.needed is False
    assert res.ok is True


@pytest.mark.asyncio
async def test_planner_over_its_cap_declines(monkeypatch):
    """Planner cap exceeded with no verdict in → decline (never fabricate)."""
    monkeypatch.setattr(ed, "_FRESH_DATA_PLAN_TIMEOUT_SECONDS", 0.05)

    async def hung_plan():
        await asyncio.sleep(5)
        return SimpleNamespace(use_tool=True)

    task = asyncio.create_task(hung_plan())
    try:
        res = await ed.fetch_fresh_data_section(
            "update the alternatives price", [], MagicMock(), "user-1",
            plan_task=task,
        )
    finally:
        task.cancel()
    assert res.needed is True
    assert res.ok is False


@pytest.mark.asyncio
async def test_lookup_over_its_budget_still_declines(monkeypatch):
    """The LOOKUP keeps its own budget: retrieval overrun still declines."""
    monkeypatch.setattr(ed, "_FRESH_DATA_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(ed, "_FRESH_DATA_PLAN_TIMEOUT_SECONDS", 1.0)

    async def fast_plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search", query="F-5216 price")

    async def slow_lookup(*args, **kwargs):
        await asyncio.sleep(0.5)
        return "never arrives"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan", slow_lookup)

    res = await ed.fetch_fresh_data_section(
        "update the alternatives price", [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(fast_plan()),
    )
    assert res.needed is True
    assert res.ok is False


@pytest.mark.asyncio
async def test_fast_planner_with_lookup_returns_evidence(monkeypatch):
    """Happy path: a plan that needs data + a fast lookup → evidence section."""
    monkeypatch.setattr(ed, "_FRESH_DATA_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(ed, "_FRESH_DATA_PLAN_TIMEOUT_SECONDS", 1.0)

    async def fast_plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search", query="F-5216 price")

    async def fast_lookup(*args, **kwargs):
        return "F-52”x16G Foot Shear | $7,519.00 | 2-3 Weeks"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan", fast_lookup)

    res = await ed.fetch_fresh_data_section(
        "update the alternatives price", [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(fast_plan()),
    )
    assert res.needed is True
    assert res.ok is True
    assert "$7,519.00" in res.section
