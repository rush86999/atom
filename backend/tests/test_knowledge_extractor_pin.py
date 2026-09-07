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
    KG_EXTRACTION_MODEL,
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
async def test_extraction_pins_openrouter_flash_model():
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=_RESULT)

    out = await extractor.extract_knowledge("Brennan Machinery Inc. sent a quote", source="email")

    assert out["entities"][0]["properties"]["name"] == "Brennan Machinery Inc."
    kwargs = extractor.llm_service.generate_structured_response.call_args.kwargs
    assert kwargs["provider_model"] == ("openrouter", KG_EXTRACTION_MODEL)
    assert kwargs["response_model"] is ExtractionResult
    assert kwargs["disable_reasoning"] is True


@pytest.mark.asyncio
async def test_no_openrouter_client_leaves_routing_unpinned():
    extractor = _extractor_with_llm({"ollama": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=_RESULT)

    await extractor.extract_knowledge("text", source="email")

    kwargs = extractor.llm_service.generate_structured_response.call_args.kwargs
    assert "provider_model" not in kwargs


@pytest.mark.asyncio
async def test_pinned_none_retries_unpinned_once():
    """Planner contract: a pin that can't be served (revoked key, gated
    model) returns None silently — retry unpinned so a BYOK workspace still
    routes within its own configured providers."""
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
async def test_both_calls_failing_keeps_empty_knowledge_contract():
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(return_value=None)

    out = await extractor.extract_knowledge("text", source="email")

    assert out == {"entities": [], "relationships": []}


@pytest.mark.asyncio
async def test_llm_exception_keeps_empty_knowledge_contract():
    extractor = _extractor_with_llm({"openrouter": object()})
    extractor.llm_service.generate_structured_response = AsyncMock(
        side_effect=RuntimeError("provider down")
    )

    out = await extractor.extract_knowledge("text", source="email")

    assert out == {"entities": [], "relationships": []}
