"""canvas.present_chart / canvas.present_markdown action wiring (2026-09-09).

The present_* tools existed in tools/canvas_tool.py (registered in the OLD
tools/registry.py) but were never registered in the unified action registry
the agent loop renders tools from — and were absent from the meta-agent's
CORE_TOOLS_NAMES allowlist — so a chat ask to "show a chart" could only
ever degrade to a text description or a raw canvas content edit.
"""

import os
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest

from core.action_registry import action_registry
from core.atom_meta_agent import AtomMetaAgent


class TestRegistryWiring:
    def test_present_chart_action_registered(self):
        action = action_registry.get_action("canvas.present_chart")
        assert action is not None
        props = action.parameters_schema["properties"]
        assert "chart_type" in props and "data" in props
        assert action.parameters_schema["required"] == ["chart_type", "data"]

    def test_present_markdown_action_registered(self):
        action = action_registry.get_action("canvas.present_markdown")
        assert action is not None
        assert action.parameters_schema["required"] == ["content"]

    def test_actions_reach_the_agent_loop_allowlist(self):
        """Registration alone is not enough: the meta-agent filters
        get_all_tools() through CORE_TOOLS_NAMES."""
        names = set(AtomMetaAgent.CORE_TOOLS_NAMES)
        assert "canvas.present_chart" in names
        assert "canvas.present_markdown" in names


class TestPresentChartHandler:
    @pytest.mark.asyncio
    async def test_handler_threads_user_session_agent_into_tool(self):
        from core.action_registry import _canvas_present_chart

        with patch("tools.canvas_tool.present_chart", new_callable=AsyncMock) as tool:
            tool.return_value = {"success": True}
            result = await _canvas_present_chart(
                {"chart_type": "bar", "data": [{"x": "A", "y": 5}], "title": "Demo"},
                {"user_id": "u1", "session_id": "s1", "agent_id": "a1"},
            )
        assert result == {"success": True}
        tool.assert_awaited_once_with(
            user_id="u1",
            chart_type="bar",
            data=[{"x": "A", "y": 5}],
            title="Demo",
            agent_id="a1",
            session_id="s1",
        )

    @pytest.mark.asyncio
    async def test_handler_normalizes_nested_chart_shape(self):
        """Live 2026-09-09: glm-5.3-flash called the tool with
        {'chart': {'type': 'bar_chart', 'categories': [...], 'values':
        [...]}} — the loop's simplified tool schema hides the exact shape.
        The handler must normalize it, not bounce the call."""
        from core.action_registry import _canvas_present_chart

        with patch("tools.canvas_tool.present_chart", new_callable=AsyncMock) as tool:
            tool.return_value = {"success": True}
            result = await _canvas_present_chart(
                {"chart": {"type": "bar_chart", "title": "Demo",
                           "categories": ["Alpha", "Beta"], "values": [5, 3]}},
                {"user_id": "u1", "session_id": "s1"},
            )
        assert result == {"success": True}
        kwargs = tool.await_args.kwargs
        assert kwargs["chart_type"] == "bar_chart"
        assert kwargs["data"] == [{"x": "Alpha", "y": 5}, {"x": "Beta", "y": 3}]
        assert kwargs["title"] == "Demo"
        assert kwargs["session_id"] == "s1"

    @pytest.mark.asyncio
    async def test_handler_requires_authenticated_user(self):
        from core.action_registry import _canvas_present_chart

        result = await _canvas_present_chart(
            {"chart_type": "bar", "data": [1]}, {})
        assert result["success"] is False
        assert "user" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handler_requires_chart_args(self):
        from core.action_registry import _canvas_present_chart

        result = await _canvas_present_chart({"data": [1]}, {"user_id": "u1"})
        assert result["success"] is False


class TestPresentMarkdownHandler:
    @pytest.mark.asyncio
    async def test_handler_threads_context(self):
        from core.action_registry import _canvas_present_markdown

        with patch("tools.canvas_tool.present_markdown", new_callable=AsyncMock) as tool:
            tool.return_value = {"success": True}
            result = await _canvas_present_markdown(
                {"content": "# hi", "title": "t"},
                {"user_id": "u1", "session_id": "s1"},
            )
        assert result == {"success": True}
        tool.assert_awaited_once_with(
            user_id="u1", content="# hi", title="t", agent_id=None, session_id="s1",
        )

    @pytest.mark.asyncio
    async def test_handler_requires_content(self):
        from core.action_registry import _canvas_present_markdown

        result = await _canvas_present_markdown({}, {"user_id": "u1"})
        assert result["success"] is False
