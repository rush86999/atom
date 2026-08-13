# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/entity_schema_suggestion_service
(never-wave-tested).

Covers AI schema suggestion:
- suggest_schema: plain JSON, ```json-fenced and ```-fenced responses parsed;
  markdown fence with `quality` model routing; invalid JSON / empty content /
  LLM exception -> fallback default schema.
- get_entity_schema_suggestion_service: singleton creation (double-checked
  lock) + existing-instance reuse.

LLM fully mocked (no network, zero LLM spend).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.entity_schema_suggestion_service as ess
from core.entity_schema_suggestion_service import (
    EntitySchemaSuggestionService,
    get_entity_schema_suggestion_service,
)

_FALLBACK = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
    "required": ["name"],
}


def _service(content=None, exc=None):
    llm = MagicMock()
    if exc is not None:
        llm.generate_completion = AsyncMock(side_effect=exc)
    else:
        llm.generate_completion = AsyncMock(return_value={"content": content})
    return EntitySchemaSuggestionService(llm_service=llm), llm


class TestSuggestSchema:
    def test_plain_json_response(self):
        svc, llm = _service(content='{"type": "object", "properties": {"title": {"type": "string"}}}')
        schema = asyncio.run(svc.suggest_schema("Task", "A work item"))
        assert schema == {"type": "object", "properties": {"title": {"type": "string"}}}
        prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
        assert "Task" in prompt
        assert "A work item" in prompt
        assert llm.generate_completion.await_args.kwargs["model"] == "quality"

    def test_fenced_json_response(self):
        svc, _ = _service(content='```json\n{"type": "object", "properties": {}}\n```')
        schema = asyncio.run(svc.suggest_schema("Task", "desc"))
        assert schema == {"type": "object", "properties": {}}

    def test_generic_fence_response(self):
        svc, _ = _service(content='```\n{"type": "object", "required": ["id"]}\n```')
        schema = asyncio.run(svc.suggest_schema("Task", "desc"))
        assert schema == {"type": "object", "required": ["id"]}

    def test_fence_with_surrounding_text(self):
        svc, _ = _service(content='Here you go:\n```json\n{"type": "object"}\n```\nEnjoy')
        schema = asyncio.run(svc.suggest_schema("Task", "desc"))
        assert schema == {"type": "object"}

    def test_invalid_json_returns_fallback(self):
        svc, _ = _service(content="not json at all")
        schema = asyncio.run(svc.suggest_schema("Task", "desc"))
        assert schema == _FALLBACK

    def test_empty_content_returns_fallback(self):
        svc, _ = _service(content="")
        schema = asyncio.run(svc.suggest_schema("Task", "desc"))
        assert schema == _FALLBACK

    def test_llm_exception_returns_fallback(self):
        svc, _ = _service(exc=RuntimeError("llm down"))
        schema = asyncio.run(svc.suggest_schema("Task", "desc"))
        assert schema == _FALLBACK

    def test_default_constructor_builds_real_service(self):
        with patch.object(ess, "LLMService") as llm_cls:
            svc = EntitySchemaSuggestionService()
            assert svc.llm_service is llm_cls.return_value
            llm_cls.assert_called_once_with(tenant_id="default")


class TestGetEntitySchemaSuggestionService:
    def test_creates_singleton_when_none(self):
        with patch.object(ess, "_instance", None):
            svc = get_entity_schema_suggestion_service()
            assert isinstance(svc, EntitySchemaSuggestionService)
            with patch.object(ess, "LLMService"):
                assert get_entity_schema_suggestion_service() is svc

    def test_returns_existing_instance(self):
        existing = MagicMock(spec=EntitySchemaSuggestionService)
        with patch.object(ess, "_instance", existing):
            assert get_entity_schema_suggestion_service() is existing
