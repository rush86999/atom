"""LLMService.generate_structured_response must forward a caller task_type.

`LLMService.generate_structured_response(..., **kwargs)` forwards to the BYOK
handler as ``handler.generate_structured_response(..., task_type=model, **kwargs)``
where ``model`` defaults to the literal ``"quality"``. That means ANY caller
that passes its own ``task_type`` — which is how small structured workloads
declare themselves for cost-priority routing — hit::

    TypeError: generate_structured_response() got multiple values for
    keyword argument 'task_type'

Caught live 2026-09-10: after the pin removals, tagging the tool planner and
canvas editor with ``task_type="planning"`` made BOTH legs fail instantly
("canvas edit planning unavailable ... 0.2s") because the call never reached a
provider. The explicit caller value must win over the legacy positional
default, and the default must survive when no caller value is given.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("TESTING", "1")


def _service(handler):
    """LLMService with its handler stubbed (no DB / no real routing)."""
    from core.llm_service import LLMService

    svc = LLMService.__new__(LLMService)
    svc._get_handler = MagicMock(return_value=handler)
    svc.continuous_learning = None
    return svc


@pytest.mark.asyncio
async def test_caller_task_type_is_forwarded_not_duplicated():
    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(return_value="PLAN")

    svc = _service(handler)
    out = await svc.generate_structured_response(
        prompt="p",
        response_model=object,
        system_instruction="json",
        task_type="planning",
    )

    assert out == "PLAN"
    kwargs = handler.generate_structured_response.await_args.kwargs
    assert kwargs["task_type"] == "planning", (
        "the caller's task_type must reach the handler — it selects "
        "cost-priority routing for small structured workloads"
    )


@pytest.mark.asyncio
async def test_default_task_type_preserved_when_caller_omits_it():
    """Existing behaviour (task_type == the `model` selector) must not regress."""
    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(return_value="PLAN")

    svc = _service(handler)
    await svc.generate_structured_response(prompt="p", response_model=object)

    kwargs = handler.generate_structured_response.await_args.kwargs
    assert kwargs["task_type"] == "quality"
