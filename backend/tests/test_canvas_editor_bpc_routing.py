"""The canvas editor must route via BPC — not a hardcoded model.

The editor long pinned `("openrouter", ATOM_CANVAS_EDITOR_MODEL)`
(default `qwen/qwen3.7-flash`). The pin was introduced as a shape fix: the
previous pin (`minimax-m3`) is a reasoning model that ignored
``disable_reasoning`` and burned 1,100–2,000 hidden tokens / 30–75s on a
60-line planning answer, blowing the canvas-edit stage's 30s budget.

But a hardcoded model is not a shape control — it is a single point of
failure that bypasses BPC's dynamic routing entirely. A ``provider_model`` pin
collapses the candidate list to one tuple, so when that model was briefly
rate-limited (OpenRouter 429, 2026-09-10) the whole edit leg died even though
the workspace had other healthy providers.

The correct division of labor:
  * BPC chooses the model (dynamic, cost/quality/health aware).
  * ``disable_reasoning=True`` + the reasoning-mandatory exclusion keep the
    fast-small-call SHAPE, which is what the pin was really for.

These tests pin that contract: no canvas-editor planning call may carry a
``provider_model``.
"""
import os
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.chat_canvas_editor import (
    CanvasActionPlan,
    CanvasEditPlan,
    plan_canvas_action,
    plan_canvas_edit,
)


def _canvas():
    return {
        "canvas_id": "c-123",
        "canvas_type": "email",
        "title": "Quote",
        "content": {"to": "a@b.com", "cc": "", "subject": "Q", "body": "Hello"},
    }


def _llm():
    llm = MagicMock()
    # The pin was conditional on an openrouter client existing; give it one so
    # a regression that reintroduces the pin is actually exercised.
    llm._get_handler.return_value.clients = {"openrouter": object(), "openai": object()}
    return llm


@pytest.mark.asyncio
async def test_edit_plan_does_not_pin_a_provider_model():
    llm = _llm()
    llm.generate_structured_response = AsyncMock(
        return_value=CanvasEditPlan(wants_edit=True, updated_content_json='"new"')
    )

    await plan_canvas_edit("add a line", [], _canvas(), llm)

    kwargs = llm.generate_structured_response.await_args.kwargs
    assert "provider_model" not in kwargs, (
        "canvas-edit planning must let BPC route; a provider_model pin "
        "collapses the candidate list to one model and removes every fallback"
    )


@pytest.mark.asyncio
async def test_edit_plan_never_retries_because_there_is_no_pin():
    """With no pin the shared helper has nothing to unpin — exactly one call."""
    llm = _llm()
    llm.generate_structured_response = AsyncMock(
        return_value=CanvasEditPlan(wants_edit=True, updated_content_json='"new"')
    )

    await plan_canvas_edit("add a line", [], _canvas(), llm)

    assert llm.generate_structured_response.await_count == 1


@pytest.mark.asyncio
async def test_edit_plan_still_requests_non_reasoning_shape():
    """The pin's real purpose: a cheap, non-thinking planning call."""
    llm = _llm()
    llm.generate_structured_response = AsyncMock(
        return_value=CanvasEditPlan(wants_edit=True, updated_content_json='"new"')
    )

    await plan_canvas_edit("add a line", [], _canvas(), llm)

    kwargs = llm.generate_structured_response.await_args.kwargs
    assert kwargs.get("disable_reasoning") is True
    assert kwargs.get("temperature") == 0.0


@pytest.mark.asyncio
async def test_edit_plan_propagates_provider_failure_as_unavailable():
    """BPC with no usable provider must still raise (not silently no-op)."""
    from core.chat_canvas_editor import CanvasPlanUnavailable

    llm = _llm()
    llm.generate_structured_response = AsyncMock(return_value=None)

    with pytest.raises(CanvasPlanUnavailable):
        await plan_canvas_edit("add a line", [], _canvas(), llm)

    assert llm.generate_structured_response.await_count == 1


@pytest.mark.asyncio
async def test_action_plan_does_not_pin_a_provider_model():
    llm = _llm()
    llm.generate_structured_response = AsyncMock(return_value=CanvasActionPlan())

    await plan_canvas_action("send it", [], _canvas(), llm)

    kwargs = llm.generate_structured_response.await_args.kwargs
    assert "provider_model" not in kwargs, (
        "canvas ACTION planning must also route through BPC"
    )


@pytest.mark.asyncio
async def test_no_edit_plan_is_a_single_call():
    """A healthy "this isn't an edit" is a real answer — it must not be
    retried, which would double the latency of every non-edit canvas turn."""
    llm = _llm()
    llm.generate_structured_response = AsyncMock(
        return_value=CanvasEditPlan(wants_edit=False)
    )

    plan = await plan_canvas_edit("what is this?", [], _canvas(), llm)

    assert plan is not None and not plan.wants_edit
    assert llm.generate_structured_response.await_count == 1


@pytest.mark.asyncio
async def test_action_plan_propagates_provider_failure():
    """plan_canvas_action returns None (falls through to conversation) when
    no provider can serve it — the raw-JSON rescue is then tried once."""
    llm = _llm()
    llm.generate_structured_response = AsyncMock(return_value=None)
    llm.generate_completion = AsyncMock(return_value={"success": False})

    plan = await plan_canvas_action("send it", [], _canvas(), llm)

    assert plan is None
    assert llm.generate_structured_response.await_count == 1


def test_canvas_editor_model_constant_is_gone():
    """A module-level model constant is what made the pin look configurable.

    ``ATOM_CANVAS_EDITOR_MODEL`` let an operator name a model, but the code
    still pinned it -- so the env var could only swap one single point of
    failure for another. Routing is BPC's job.
    """
    import core.chat_canvas_editor as editor

    assert not hasattr(editor, "CANVAS_EDITOR_MODEL"), (
        "CANVAS_EDITOR_MODEL reintroduces a hardcoded canvas-editor model; "
        "BPC must choose the model"
    )
