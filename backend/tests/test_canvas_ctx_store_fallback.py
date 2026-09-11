"""Canvas context resolution must survive a client that omits `canvas_content`.

Live 2026-09-11: a chat turn on a canvas sent only `canvas_id` (no
`canvas_content`), so `_canvas_ctx` was None and the agent answered from the
origin conversation — it told the operator the draft had no alternative
machine, because the draft was never in its prompt. The real panel sends the
content, but the server must not be silently blinded when a client doesn't.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

CANVAS = "c-ctx-1"


def _orch():
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator()
    orch.ai_engines = {}
    orch.llm_service = MagicMock()
    return orch


@pytest.mark.asyncio
async def test_client_supplied_content_wins_and_no_store_read():
    orch = _orch()
    content = {"subject": "x", "body": "from the client"}
    with patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock()) as read:
        ctx = await orch._resolve_canvas_ctx(
            {"canvas_id": CANVAS, "canvas_type": "email",
             "canvas_content": content},
            "user-1",
        )
    assert ctx is not None
    assert ctx["content"] == content
    read.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_content_falls_back_to_the_store():
    orch = _orch()
    stored = {"subject": "x", "body": "F-52”x16G Foot Shear F-5216 $7,519.00"}
    with patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(
        return_value={"success": True, "canvas_type": "email",
                      "title": "Quote", "content": stored}
    )) as read:
        ctx = await orch._resolve_canvas_ctx(
            {"canvas_id": CANVAS, "canvas_type": "email"}, "user-1")
    read.assert_awaited_once()
    assert ctx is not None
    assert ctx["content"] == stored
    assert ctx["canvas_id"] == CANVAS


@pytest.mark.asyncio
async def test_store_lookup_failure_degrades_to_no_context():
    orch = _orch()
    with patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(
        side_effect=RuntimeError("db down"))):
        ctx = await orch._resolve_canvas_ctx(
            {"canvas_id": CANVAS, "canvas_type": "email"}, "user-1")
    assert ctx is None


@pytest.mark.asyncio
async def test_no_canvas_id_yields_no_context():
    orch = _orch()
    assert await orch._resolve_canvas_ctx({"current_page": "/chat"}, "user-1") is None
    assert await orch._resolve_canvas_ctx(None, "user-1") is None
