"""
TDD tests for OpenIESchemaDiscovery BYOK migration.

Verifies that entity extraction routes through LLMService (cost-tracked,
governance-aware, provider-fallback-capable) rather than instantiating a
direct OpenAI(api_key=...) client.

RED phase: these tests assert the post-migration contract. They fail against
the pre-migration code (which uses self._get_llm_client() + OpenAI client).
GREEN phase: they pass once the service calls self.llm_service.generate().
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.openie_schema_discovery import OpenIESchemaDiscovery


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_llm_service():
    """A MagicMock standing in for LLMService.

    generate() is async and returns the raw model text (a JSON string).
    is_available() is sync and returns True.
    """
    svc = MagicMock()
    svc.is_available.return_value = True
    svc.generate = AsyncMock(return_value=json.dumps({
        "entities": [
            {"name": "Person", "type": "Person", "description": "Alice Johnson"},
            {"name": "Organization", "type": "Organization", "description": "Acme Corp"},
        ],
        "relationships": [
            {"from": "Person", "to": "Organization", "type": "works_at", "description": ""}
        ],
        "discovery_reasoning": "Two entities extracted from sample text.",
    }))
    return svc


@pytest.fixture
def discovery(fake_llm_service):
    """OpenIESchemaDiscovery wired to the fake LLMService."""
    with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
        inst = OpenIESchemaDiscovery(tenant_id="test-tenant", workspace_id="test-ws")
    # Replace again in case the patch above didn't intercept the constructor
    inst.llm_service = fake_llm_service
    return inst


# ---------------------------------------------------------------------------
# Unavailable LLM path — error shape preserved
# ---------------------------------------------------------------------------


class TestLLMUnavailable:
    """When LLMService.is_available() is False, the extraction must return the
    exact legacy error payload (key order / values preserved)."""

    def test_unavailable_returns_canonical_error_shape(self):
        with patch("core.openie_schema_discovery.LLMService") as MockSvc:
            unavailable = MagicMock()
            unavailable.is_available.return_value = False
            MockSvc.return_value = unavailable

            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("some text", source="x")

        assert result == {
            "entities": [],
            "relationships": [],
            "core_entity_count": 0,
            "custom_entity_count": 0,
            "error": "LLM client not available",
        }
        # generate() must NOT be called when unavailable
        unavailable.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path — routes through LLMService.generate
# ---------------------------------------------------------------------------


class TestExtractionRoutesThroughLLMService:
    """The core assertion of the BYOK migration: generate() is the entry point,
    not a direct OpenAI client.chat.completions.create()."""

    def test_extraction_calls_llm_service_generate(self, discovery, fake_llm_service):
        discovery.extract_entities_with_core_hardcoding(
            "Alice works at Acme Corp.", source="test"
        )

        fake_llm_service.generate.assert_called_once()
        # Verify the prompt is forwarded
        args, kwargs = fake_llm_service.generate.call_args
        prompt = kwargs.get("prompt") or (args[0] if args else "")
        assert "Alice works at Acme Corp" in prompt or "Alice" in prompt

    def test_extraction_forwards_model_and_temperature(self, discovery, fake_llm_service):
        discovery.extract_entities_with_core_hardcoding("sample", source="x")

        _, kwargs = fake_llm_service.generate.call_args
        # Model must be pinned to gpt-4o-mini to preserve prior behavior
        assert kwargs.get("model") == "gpt-4o-mini"
        # Temperature must be pinned to 0.1 to preserve prior behavior
        assert kwargs.get("temperature") == pytest.approx(0.1)

    def test_extraction_sets_knowledge_graph_system_instruction(self, discovery, fake_llm_service):
        discovery.extract_entities_with_core_hardcoding("sample", source="x")

        _, kwargs = fake_llm_service.generate.call_args
        sys_instr = kwargs.get("system_instruction", "")
        assert "knowledge graph extractor" in sys_instr.lower()
        assert "json" in sys_instr.lower()

    def test_extraction_returns_entities_and_counts(self, discovery):
        result = discovery.extract_entities_with_core_hardcoding(
            "Alice works at Acme Corp.", source="test"
        )

        assert "entities" in result
        assert "relationships" in result
        assert result["core_entity_count"] >= 1
        assert result["custom_entity_count"] >= 0
        assert result.get("discovery_reasoning")

    def test_core_entity_classification_preserved(self, discovery):
        """Entity named 'Person' → canonical_type 'user' (core hardcoding)."""
        result = discovery.extract_entities_with_core_hardcoding(
            "Alice works at Acme.", source="test"
        )

        person = next(e for e in result["entities"] if e["name"] == "Person")
        assert person["properties"]["is_core"] is True
        assert person["properties"]["canonical_type"] == "user"
        assert person["properties"]["source"] == "test"
        assert person["properties"]["llm_extracted"] is True

    def test_relationships_passed_through(self, discovery):
        result = discovery.extract_entities_with_core_hardcoding(
            "Alice works at Acme.", source="test"
        )

        assert len(result["relationships"]) == 1
        rel = result["relationships"][0]
        assert rel["from"] == "Person"
        assert rel["to"] == "Organization"
        assert rel["type"] == "works_at"


# ---------------------------------------------------------------------------
# Failure path — LLMService.generate raises
# ---------------------------------------------------------------------------


class TestExtractionFailureHandling:
    """When generate() raises, the method must return the legacy error shape:
    entities=[], relationships=[], counts=0, error=str(e)."""

    def test_generate_exception_returns_error_payload(self, fake_llm_service):
        fake_llm_service.generate = AsyncMock(side_effect=RuntimeError("provider 503"))

        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        assert result["entities"] == []
        assert result["relationships"] == []
        assert result["core_entity_count"] == 0
        assert result["custom_entity_count"] == 0
        assert "provider 503" in result["error"]

    def test_malformed_json_returns_error_payload(self, fake_llm_service):
        """generate() returns text that isn't valid JSON → json.loads raises → caught."""
        fake_llm_service.generate = AsyncMock(return_value="not json {{{")

        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        assert result["entities"] == []
        assert "error" in result

    def test_markdown_wrapped_json_is_extracted(self, fake_llm_service):
        """REG-1: Without response_format, the LLM may wrap JSON in markdown
        fences. The extractor must defensively strip the fence before parsing,
        otherwise every markdown-wrapped response becomes an error payload."""
        wrapped = '```json\n{"entities": [], "relationships": [], "discovery_reasoning": ""}\n```'
        fake_llm_service.generate = AsyncMock(return_value=wrapped)

        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        # Must NOT surface an error — the fence must be stripped and JSON parsed
        assert "error" not in result, f"Expected JSON extraction, got error: {result.get('error')}"
        assert result["entities"] == []
        assert result["discovery_reasoning"] == ""


# ---------------------------------------------------------------------------
# Edge cases — empty payloads, missing keys, defaults
# ---------------------------------------------------------------------------


class TestExtractionEdgeCases:
    """Robustness coverage for the LLM-payload processing loop."""

    def test_empty_entities_and_relationships(self, fake_llm_service):
        """LLM returns well-formed but empty payload — counts stay 0, no error."""
        fake_llm_service.generate = AsyncMock(
            return_value=json.dumps({"entities": [], "relationships": []})
        )
        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        assert result["entities"] == []
        assert result["relationships"] == []
        assert result["core_entity_count"] == 0
        assert result["custom_entity_count"] == 0

    def test_missing_discovery_reasoning_defaults_to_empty(self, fake_llm_service):
        """data.get('discovery_reasoning', '') must default to empty string."""
        fake_llm_service.generate = AsyncMock(
            return_value=json.dumps({"entities": [], "relationships": []})
        )
        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        assert result.get("discovery_reasoning") == ""

    def test_entity_missing_name_key_caught_gracefully(self, fake_llm_service):
        """GAP-3: Entity dict missing 'name' → KeyError caught by except Exception,
        whole batch returns error payload. Documents the current behavior."""
        fake_llm_service.generate = AsyncMock(
            return_value=json.dumps({
                "entities": [{"type": "person", "description": "no name field"}],
                "relationships": [],
            })
        )
        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        # The broad except Exception catches the KeyError and returns the
        # canonical error shape. This documents the pre-existing behavior
        # (one malformed entity discards the whole batch).
        assert "error" in result
        assert result["entities"] == []

    def test_relationship_missing_required_keys_caught_gracefully(self, fake_llm_service):
        """GAP-4: Relationship dict missing 'from'/'to'/'type' → KeyError caught."""
        fake_llm_service.generate = AsyncMock(
            return_value=json.dumps({
                "entities": [],
                "relationships": [{"description": "missing from/to/type"}],
            })
        )
        with patch("core.openie_schema_discovery.LLMService", return_value=fake_llm_service):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")

        result = inst.extract_entities_with_core_hardcoding("sample", source="x")

        assert "error" in result
        assert result["relationships"] == []


# ---------------------------------------------------------------------------
# _run_sync thread-pool branch (caller is itself async)
# ---------------------------------------------------------------------------


class TestRunSyncAsyncBranch:
    """GAP-6: The thread-pool branch of _run_sync executes when the caller is
    already running inside an event loop. This is the production reality for
    any FastAPI route handler that calls the sync extract_* method."""

    def test_extraction_works_from_async_context(self, fake_llm_service):
        """Call extract_* from inside an async coroutine — forces the
        ThreadPoolExecutor branch of _run_sync."""
        import asyncio

        async def driver():
            # We're now inside a running loop. _run_sync must detect this and
            # offload via ThreadPoolExecutor rather than calling asyncio.run().
            with patch(
                "core.openie_schema_discovery.LLMService",
                return_value=fake_llm_service,
            ):
                inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")
            return inst.extract_entities_with_core_hardcoding("Alice", source="t")

        result = asyncio.run(driver())

        fake_llm_service.generate.assert_called_once()
        assert "error" not in result
        assert len(result["entities"]) >= 1


# ---------------------------------------------------------------------------
# Constructor wiring — LLMService instantiated with tenant/workspace context
# ---------------------------------------------------------------------------


class TestConstructorWiring:
    def test_llm_service_instantiated_with_context(self):
        with patch("core.openie_schema_discovery.LLMService") as MockSvc:
            mock_inst = MagicMock()
            MockSvc.return_value = mock_inst

            OpenIESchemaDiscovery(tenant_id="tenant-123", workspace_id="ws-456")

        MockSvc.assert_called_once()
        _, kwargs = MockSvc.call_args
        assert kwargs.get("tenant_id") == "tenant-123"
        assert kwargs.get("workspace_id") == "ws-456"

    def test_no_direct_openai_client_import(self):
        """The module must not import OpenAI at module top-level (BYOK compliance)."""
        import core.openie_schema_discovery as mod

        # _get_llm_client should no longer exist on the class
        assert not hasattr(OpenIESchemaDiscovery, "_get_llm_client"), (
            "_get_llm_client() must be removed; it bypassed LLMService."
        )

        # Source must not import openai directly
        src = open(mod.__file__).read()
        assert "from openai import" not in src, (
            "Direct OpenAI client import forbidden; route through LLMService."
        )
        assert "OpenAI(" not in src, (
            "Direct OpenAI() instantiation forbidden; route through LLMService."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
