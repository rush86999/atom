# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/blueprint_healer (never-wave-tested).

Covers reactive self-healing for agent architectures:
- heal_blueprint: fenced (```json) and plain JSON LLM output -> healed copy
  (nodes replaced, status/notes set, original untouched); empty output ->
  original returned; invalid JSON / LLM exception -> original returned.
- summarize_healing_as_directive: content passthrough; empty -> default
  directive; LLM exception -> fallback directive.
- queen property: lazy ServiceFactory.get_queen_agent passthrough.

LLM service fully mocked (no network, zero LLM spend).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.blueprint_healer as bh
from core.blueprint_healer import BlueprintHealer

_BLUEPRINT = {
    "name": "ResearchArchitecture",
    "nodes": [
        {"id": "n1", "type": "tool", "name": "search"},
        {"id": "n2", "type": "tool", "name": "extract"},
    ],
}


def _healer(llm_return=None, llm_exc=None):
    llm = MagicMock()
    if llm_exc is not None:
        llm.generate_response = AsyncMock(side_effect=llm_exc)
    else:
        llm.generate_response = AsyncMock(return_value=llm_return)
    return BlueprintHealer(db=MagicMock(), llm_service=llm), llm


class TestHealBlueprint:
    def test_fenced_json_output_heals_copy(self):
        healer, llm = _healer(llm_return='''```json
[{"id": "n1", "type": "prerequisite", "name": "search-docs"}, {"id": "n2", "type": "tool", "name": "extract"}]
```''')
        original = dict(_BLUEPRINT)
        healed = asyncio.run(healer.heal_blueprint(_BLUEPRINT, "n1", "tool schema unknown"))
        assert healed["nodes"] == [
            {"id": "n1", "type": "prerequisite", "name": "search-docs"},
            {"id": "n2", "type": "tool", "name": "extract"},
        ]
        assert healed["status"] == "healed"
        assert "n1" in healed["healing_notes"]
        assert healed["name"] == "ResearchArchitecture"
        assert original["nodes"] == _BLUEPRINT["nodes"]  # original untouched
        # prompt embeds blueprint + failed node + error
        user_msg = llm.generate_response.await_args.kwargs["messages"][1]["content"]
        assert "ResearchArchitecture" in user_msg
        assert "n1" in user_msg
        assert "tool schema unknown" in user_msg
        assert llm.generate_response.await_args.kwargs["tenant_id"] == "default"

    def test_plain_json_output(self):
        healer, _ = _healer(llm_return='[{"id": "n9", "type": "tool", "name": "retry"}]')
        healed = asyncio.run(healer.heal_blueprint(_BLUEPRINT, "n2", "timeout"))
        assert healed["nodes"] == [{"id": "n9", "type": "tool", "name": "retry"}]
        assert healed["status"] == "healed"

    def test_custom_tenant_passed(self):
        healer, llm = _healer(llm_return='[{"id": "x"}]')
        asyncio.run(healer.heal_blueprint(_BLUEPRINT, "n1", "err", tenant_id="t-42"))
        assert llm.generate_response.await_args.kwargs["tenant_id"] == "t-42"

    def test_empty_content_returns_original(self):
        healer, _ = _healer(llm_return=None)
        healed = asyncio.run(healer.heal_blueprint(_BLUEPRINT, "n1", "err"))
        assert healed is _BLUEPRINT

    def test_invalid_json_returns_original(self):
        healer, _ = _healer(llm_return="[not json at all")
        healed = asyncio.run(healer.heal_blueprint(_BLUEPRINT, "n1", "err"))
        assert healed is _BLUEPRINT

    def test_llm_exception_returns_original(self):
        healer, _ = _healer(llm_exc=RuntimeError("llm down"))
        healed = asyncio.run(healer.heal_blueprint(_BLUEPRINT, "n1", "err"))
        assert healed is _BLUEPRINT


class TestSummarizeHealingAsDirective:
    def test_returns_llm_content(self):
        healer, llm = _healer(llm_return="Always add a search node first.")
        directive = asyncio.run(healer.summarize_healing_as_directive(
            {"name": "extract", "type": "tool"}, [{"id": "n1"}], "schema unknown"
        ))
        assert directive == "Always add a search node first."
        user_msg = llm.generate_response.await_args.kwargs["messages"][1]["content"]
        assert "extract" in user_msg
        assert "schema unknown" in user_msg

    def test_empty_content_returns_default(self):
        healer, _ = _healer(llm_return="")
        directive = asyncio.run(healer.summarize_healing_as_directive(
            {"name": "x", "type": "t"}, [], "err"
        ))
        assert directive == "Improve architectural robustness for the failing node type."

    def test_llm_exception_returns_fallback(self):
        healer, _ = _healer(llm_exc=RuntimeError("llm down"))
        directive = asyncio.run(healer.summarize_healing_as_directive(
            {"name": "x", "type": "t"}, [], "err"
        ))
        assert directive == "Refine dependencies for failed node types."


class TestQueenProperty:
    def test_lazy_service_factory_passthrough(self):
        queen = MagicMock()
        with patch("core.service_factory.ServiceFactory.get_queen_agent",
                   return_value=queen) as get_queen:
            healer = BlueprintHealer(db="db-obj", llm_service=MagicMock())
            assert healer.queen is queen
            get_queen.assert_called_once_with("db-obj")
