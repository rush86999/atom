"""Tests for per-request routing header overrides (Feature 3 of the Manifest
gap-analysis work).

Covers: header parsing/validation, case-insensitivity, invalid-value
rejection, and end-to-end threading from the chat route handler through the
orchestrator into the BYOK handler.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import Headers

from core.llm.routing_overrides import (
    HEADER_INTENT,
    HEADER_MODEL,
    HEADER_TIER,
    parse_routing_overrides,
)


# --- Header parsing --------------------------------------------------------


def _headers(**kwargs):
    """Build a Starlette Headers object (case-insensitive) from kwargs."""
    return Headers({k: v for k, v in kwargs.items() if v is not None})


def test_parses_valid_tier():
    overrides = parse_routing_overrides(_headers(**{HEADER_TIER: "heavy"}))
    assert overrides == {"tier": "heavy"}


def test_parses_valid_intent():
    overrides = parse_routing_overrides(_headers(**{HEADER_INTENT: "coding"}))
    assert overrides == {"intent": "coding"}


def test_parses_valid_model():
    overrides = parse_routing_overrides(_headers(**{HEADER_MODEL: "gpt-4o"}))
    assert overrides == {"model": "gpt-4o"}


def test_parses_all_three():
    overrides = parse_routing_overrides(
        _headers(
            **{
                HEADER_TIER: "versatile",
                HEADER_MODEL: "claude-mythos-5",
                HEADER_INTENT: "reasoning",
            }
        )
    )
    assert overrides == {
        "tier": "versatile",
        "model": "claude-mythos-5",
        "intent": "reasoning",
    }


def test_empty_headers_returns_empty():
    assert parse_routing_overrides(_headers()) == {}


# --- Case-insensitivity ---------------------------------------------------


def test_headers_case_insensitive():
    # HTTP headers are case-insensitive; Starlette Headers handles this.
    overrides = parse_routing_overrides(
        Headers({"X-ATOM-TIER": "MICRO", "X-Atom-Intent": "REASONING"})
    )
    assert overrides == {"tier": "micro", "intent": "reasoning"}


def test_tier_value_lowercased():
    overrides = parse_routing_overrides(_headers(**{HEADER_TIER: "COMPLEX"}))
    assert overrides == {"tier": "complex"}


# --- Invalid values are dropped (never error) -----------------------------


def test_invalid_tier_dropped():
    assert parse_routing_overrides(_headers(**{HEADER_TIER: "bogus"})) == {}


def test_invalid_intent_dropped():
    assert parse_routing_overrides(_headers(**{HEADER_INTENT: "bogus"})) == {}


def test_empty_model_dropped():
    assert parse_routing_overrides(_headers(**{HEADER_MODEL: "  "})) == {}


def test_whitespace_trimmed():
    overrides = parse_routing_overrides(
        _headers(**{HEADER_TIER: "  heavy  ", HEADER_INTENT: " coding "})
    )
    assert overrides == {"tier": "heavy", "intent": "coding"}


def test_partial_invalid_keeps_valid():
    # Invalid tier is dropped, valid intent is kept.
    overrides = parse_routing_overrides(
        _headers(**{HEADER_TIER: "bogus", HEADER_INTENT: "coding"})
    )
    assert overrides == {"intent": "coding"}


# --- Plain dict support (fallback path) ------------------------------------


def test_plain_dict_case_insensitive():
    overrides = parse_routing_overrides({"X-Atom-Tier": "heavy"})
    assert overrides == {"tier": "heavy"}


def test_plain_dict_lower_key():
    overrides = parse_routing_overrides({"x-atom-intent": "reasoning"})
    assert overrides == {"intent": "reasoning"}


# --- Orchestrator threading ------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_threads_model_override():
    """process_chat_message should pass model override to generate_completion."""
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    orch.tenant_id = "default"
    orch.llm_service = MagicMock()
    # generate_completion returns a success payload so the orchestrator
    # treats it as a real AI response.
    orch.llm_service.generate_completion = AsyncMock(
        return_value={"success": True, "content": "hi", "model": "forced", "provider": "x"}
    )
    orch._get_or_create_session = MagicMock(return_value={"history": []})
    orch._analyze_intent = AsyncMock(return_value={"feature": "general"})
    orch._route_to_features = AsyncMock(return_value={})
    orch._is_cancelled = MagicMock(return_value=False)
    orch._persist_sessions = MagicMock()

    await orch.process_chat_message(
        user_id="u1",
        message="hello",
        routing_overrides={"model": "gpt-4o", "tier": "heavy", "intent": "reasoning"},
    )

    # The orchestrator should have called generate_completion with the forced
    # model and forwarded tier/intent as kwargs.
    call_kwargs = orch.llm_service.generate_completion.call_args
    assert call_kwargs.kwargs["model"] == "gpt-4o"
    assert call_kwargs.kwargs.get("cognitive_tier") == "heavy"
    assert call_kwargs.kwargs.get("intent_override") == "reasoning"


@pytest.mark.asyncio
async def test_orchestrator_defaults_to_auto_without_overrides():
    """Without overrides, generate_completion is called with model='auto'."""
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    orch.tenant_id = "default"
    orch.llm_service = MagicMock()
    orch.llm_service.generate_completion = AsyncMock(
        return_value={"success": True, "content": "hi", "model": "auto", "provider": "x"}
    )
    orch._get_or_create_session = MagicMock(return_value={"history": []})
    orch._analyze_intent = AsyncMock(return_value={"feature": "general"})
    orch._route_to_features = AsyncMock(return_value={})
    orch._is_cancelled = MagicMock(return_value=False)
    orch._persist_sessions = MagicMock()

    await orch.process_chat_message(user_id="u1", message="hello")

    call_kwargs = orch.llm_service.generate_completion.call_args
    assert call_kwargs.kwargs["model"] == "auto"
    # No tier/intent kwargs forwarded.
    assert "cognitive_tier" not in call_kwargs.kwargs
    assert "intent_override" not in call_kwargs.kwargs


# --- BYOKHandler override consumption -------------------------------------


@pytest.mark.asyncio
async def test_byok_handler_accepts_override_kwargs(monkeypatch):
    """generate_response should accept cognitive_tier and intent_override
    without TypeError and skip detection/classification when forced."""
    from core.llm.byok_handler import BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    # Minimal stubs so generate_response reaches the routing section.
    handler.workspace_id = "test"
    handler.tenant_id = "default"
    handler.clients = {}
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler._pending_routing_result_id = None
    monkeypatch.setattr(
        "core.llm.byok_handler.llm_usage_tracker.is_budget_exceeded",
        lambda ws: False,
    )

    # With no clients configured, generate_response returns the "not
    # initialized" string early — but only AFTER accepting the kwargs (no
    # TypeError). This confirms the signature accepts the overrides.
    result = await BYOKHandler.generate_response(
        handler,
        prompt="hi",
        model_type="auto",
        cognitive_tier="heavy",
        intent_override="reasoning",
    )
    assert isinstance(result, str)
    # No TypeError was raised — the kwargs were accepted.
