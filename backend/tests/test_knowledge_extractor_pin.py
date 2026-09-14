"""Knowledge-extraction routing: bulk background extraction must not ride
BPC's value ranking onto frontier models.

Observed 2026-09-05: with zero user conversations, the communication
ingestion pipeline ran ~1,470 extraction calls in 6h, all routed by BPC to
openrouter/qwen3-max and xiaomi/mimo-v2.5-pro (~26-30x flash per-token
pricing) for ~400-char supplier emails. The fix pins the extractor to a
flash-class model via the planner's provider_model convention (see
test_chat_canvas_editor.py::test_plan_builds_prompt_with_canvas_content_and_pins_model)
with one unpinned retry, mirroring chat_tool_planner._structured_with_fallback.
"""
import os
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.knowledge_extractor import (
    ExtractionResult,
    KnowledgeExtractor,
)


def _extractor_with_llm(clients: dict) -> KnowledgeExtractor:
    with patch("core.knowledge_extractor.LLMService", MagicMock()):
        extractor = KnowledgeExtractor(workspace_id="default")
    extractor.redactor = None
    extractor.llm_service = MagicMock()
    extractor.llm_service._get_handler.return_value.clients = clients
    return extractor


_RESULT = ExtractionResult(
    entities=[{"id": "brennan", "type": "Organization", "properties": {"name": "Brennan Machinery Inc."}}],
    relationships=[{"from": "m1", "to": "quote", "type": "INTENT", "properties": {"confidence": 0.9}}],
)


@pytest.mark.asyncio
async def test_extraction_routes_via_bpc_with_no_hardcoded_model(monkeypatch):
    """Cost control is the REQUEST's task_type, not a hardcoded model.

    ``task_type="extraction"`` makes BPC apply its cheap-model cap
    (max_quality 90 + o-series exclusion) — verified against the live pricing
    cache to keep candidates flash-class. A hardcoded (provider, model) pin
    would additionally collapse the candidate list to one tuple and remove
    every provider fallback.
    """
    monkeypatch.delenv("ATOM_KG_EXTRACTION_MODEL", raising=False)
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=_RESULT)

    out = await extractor.extract_knowledge("Brennan Machinery Inc. sent a quote", source="email")

    assert out["entities"][0]["properties"]["name"] == "Brennan Machinery Inc."
    kwargs = extractor.llm_service.generate_structured_response.call_args.kwargs
    assert "provider_model" not in kwargs, (
        "extraction must let BPC route; no model may be hardcoded"
    )
    assert kwargs.get("task_type") == "extraction", (
        "task_type='extraction' is what keeps this bulk workload cheap"
    )
    assert kwargs["response_model"] is ExtractionResult
    assert kwargs["disable_reasoning"] is True


@pytest.mark.asyncio
async def test_operator_env_override_still_honoured(monkeypatch):
    """An explicit ATOM_KG_EXTRACTION_MODEL pin is an operator decision."""
    monkeypatch.setenv("ATOM_KG_EXTRACTION_MODEL", "openrouter:qwen/qwen3.8-flash")
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=_RESULT)

    await extractor.extract_knowledge("text", source="email")

    kwargs = extractor.llm_service.generate_structured_response.call_args.kwargs
    assert kwargs["provider_model"] == ("openrouter", "qwen/qwen3.8-flash")


@pytest.mark.asyncio
async def test_no_openrouter_client_leaves_routing_unpinned(monkeypatch):
    monkeypatch.delenv("ATOM_KG_EXTRACTION_MODEL", raising=False)
    extractor = _extractor_with_llm({"ollama": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=_RESULT)

    await extractor.extract_knowledge("text", source="email")

    kwargs = extractor.llm_service.generate_structured_response.call_args.kwargs
    assert "provider_model" not in kwargs


@pytest.mark.asyncio
async def test_pinned_none_retries_unpinned_once(monkeypatch):
    """Operator-pin contract: a pin that can't be served returns None
    silently — retry unpinned so a BYOK workspace still routes within its own
    configured providers."""
    monkeypatch.setenv("ATOM_KG_EXTRACTION_MODEL", "openrouter:qwen/qwen3.8-flash")
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(
        side_effect=[None, _RESULT]
    )

    out = await extractor.extract_knowledge("text", source="email")

    assert out["entities"], "unpinned retry should land the extraction"
    assert extractor.llm_service.generate_structured_response.await_count == 2
    first, second = extractor.llm_service.generate_structured_response.await_args_list
    assert "provider_model" in first.kwargs
    assert "provider_model" not in second.kwargs


@pytest.mark.asyncio
async def test_both_calls_failing_keeps_empty_knowledge_contract(monkeypatch):
    monkeypatch.delenv("ATOM_KG_EXTRACTION_MODEL", raising=False)
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=None)

    out = await extractor.extract_knowledge("text", source="email")

    assert out == {"entities": [], "relationships": []}


@pytest.mark.asyncio
async def test_llm_exception_keeps_empty_knowledge_contract(monkeypatch):
    monkeypatch.delenv("ATOM_KG_EXTRACTION_MODEL", raising=False)
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(
        side_effect=RuntimeError("provider down")
    )

    out = await extractor.extract_knowledge("text", source="email")

    assert out == {"entities": [], "relationships": []}
