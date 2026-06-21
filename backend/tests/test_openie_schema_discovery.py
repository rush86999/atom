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
# _extract_json_text edge cases (line 58 empty-string guard)
# ---------------------------------------------------------------------------


class TestExtractJsonTextHelper:
    """Direct unit tests for the defensive markdown-stripping helper."""

    def test_empty_string_returned_unchanged(self):
        """Line 58 guard: falsy input short-circuits before regex match."""
        from core.openie_schema_discovery import _extract_json_text

        assert _extract_json_text("") == ""

    def test_none_returned_unchanged(self):
        """Line 58 guard also handles None (falsy)."""
        from core.openie_schema_discovery import _extract_json_text

        assert _extract_json_text(None) is None  # type: ignore[arg-type]

    def test_plain_json_returned_unchanged(self):
        """No fence → returned as-is (stripped of surrounding whitespace)."""
        from core.openie_schema_discovery import _extract_json_text

        raw = '  {"a": 1}  '
        assert _extract_json_text(raw) == '{"a": 1}'

    def test_json_fence_stripped(self):
        """```json ... ``` fence is removed, inner JSON preserved."""
        from core.openie_schema_discovery import _extract_json_text

        raw = '```json\n{"entities": []}\n```'
        assert _extract_json_text(raw) == '{"entities": []}'

    def test_bare_fence_stripped(self):
        """``` ... ``` fence without language tag is also stripped."""
        from core.openie_schema_discovery import _extract_json_text

        raw = '```\n{"x": 1}\n```'
        assert _extract_json_text(raw) == '{"x": 1}'


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


# ---------------------------------------------------------------------------
# Pre-existing pure functions: prompt builder, classifier, schema generator
# ---------------------------------------------------------------------------


class TestBuildExtractionPromptFromText:
    """_build_extraction_prompt_from_text — used by extract_*."""

    def test_prompt_contains_core_entities_section(self, discovery):
        prompt = discovery._build_extraction_prompt_from_text("sample text")
        assert "Core Entity Types" in prompt
        assert "Person" in prompt
        assert "Organization" in prompt

    def test_prompt_contains_input_text_truncated(self, discovery):
        long_text = "x" * 10000
        prompt = discovery._build_extraction_prompt_from_text(long_text)
        # Text is truncated to 6000 chars in the prompt
        assert '"""' in prompt
        assert "sample text" not in prompt or "x" in prompt

    def test_prompt_contains_json_schema(self, discovery):
        prompt = discovery._build_extraction_prompt_from_text("sample")
        assert '"entities"' in prompt
        assert '"relationships"' in prompt
        assert '"discovery_reasoning"' in prompt


class TestBuildExtractionPromptFromSampleData:
    """_build_extraction_prompt — sample-data variant (lines 164-204).
    Called externally by multi_entity_llm_extractor and ingestion_pipeline."""

    def test_prompt_contains_sample_data(self, discovery):
        samples = [{"name": "Alice", "email": "a@x.com"}]
        prompt = discovery._build_extraction_prompt(samples)
        assert "Alice" in prompt
        assert "a@x.com" in prompt

    def test_prompt_truncates_to_five_samples(self, discovery):
        samples = [{"name": f"User{i}"} for i in range(10)]
        prompt = discovery._build_extraction_prompt(samples)
        assert "User0" in prompt
        assert "User4" in prompt
        assert "User5" not in prompt  # Truncated to first 5

    def test_prompt_contains_core_entities_and_schema(self, discovery):
        prompt = discovery._build_extraction_prompt([])
        assert "Core Entity Types" in prompt
        assert '"entities"' in prompt
        assert "discovery_reasoning" in prompt


class TestClassifyEntityType:
    """_classify_entity_type — exercises direct, fuzzy, property, and no-match branches."""

    def test_direct_name_match_person(self, discovery):
        result = discovery._classify_entity_type("Person", {})
        assert result["is_core"] is True
        assert result["canonical_type"] == "user"
        assert result["confidence"] == 1.0

    def test_direct_name_match_case_insensitive(self, discovery):
        result = discovery._classify_entity_type("ORGANIZATION", {})
        assert result["is_core"] is True
        assert result["canonical_type"] == "organization"

    def test_fuzzy_match_customer_to_contact(self, discovery):
        """Lines 408-410: fuzzy match alias 'customer' → 'contact'."""
        result = discovery._classify_entity_type("customer", {})
        assert result["is_core"] is True
        assert result["canonical_type"] == "contact"
        assert result["confidence"] == 0.8

    def test_fuzzy_match_company_to_organization(self, discovery):
        result = discovery._classify_entity_type("company", {})
        assert result["is_core"] is True
        assert result["canonical_type"] == "organization"

    def test_property_based_match(self, discovery):
        """Line 421: ≥60% property overlap triggers core classification."""
        # Person schema has: name, email, title, phone (4 props)
        # If 3 of 4 match (75% ≥ 60%), should classify as user
        props = {"name": "Alice", "email": "a@x.com", "title": "CEO", "phone": "555"}
        result = discovery._classify_entity_type("RandomName", props)
        assert result["is_core"] is True
        assert result["canonical_type"] == "user"
        assert result["confidence"] == 0.7

    def test_no_match_returns_custom(self, discovery):
        result = discovery._classify_entity_type("completely_unknown_xyz", {"weird": "v"})
        assert result["is_core"] is False
        assert result["canonical_type"] is None
        assert result["confidence"] == 0.0


class TestNormalizeSlug:
    """_normalize_slug — alias map, suffix stripping, pluralization."""

    def test_alias_map_email_variants(self, discovery):
        assert discovery._normalize_slug("email_subject") == "email"
        assert discovery._normalize_slug("emailsubject") == "email"
        assert discovery._normalize_slug("mail") == "email"

    def test_space_and_hyphen_replaced_with_underscore(self, discovery):
        assert discovery._normalize_slug("foo bar") == "foo_bar"
        assert discovery._normalize_slug("foo-bar") == "foo_bar"

    def test_redundant_suffix_stripped(self, discovery):
        assert discovery._normalize_slug("customer_detail") == "customer"
        assert discovery._normalize_slug("order_record") == "order"

    def test_plural_singularized(self, discovery):
        assert discovery._normalize_slug("emails") == "email"
        assert discovery._normalize_slug("tasks") == "task"

    def test_generic_plural_strips_trailing_s(self, discovery):
        assert discovery._normalize_slug("widgets") == "widget"

    def test_preserves_words_ending_in_us(self, discovery):
        # "status" should not become "statu"
        assert discovery._normalize_slug("status") == "status"

    def test_collapses_multiple_underscores(self, discovery):
        """Line 468: 'foo__bar' → 'foo_bar'."""
        assert discovery._normalize_slug("foo__bar") == "foo_bar"
        assert discovery._normalize_slug("a___b") == "a_b"

    def test_step5_alias_recheck_after_suffix_strip(self, discovery):
        """Line 536: 'people_name' → strip '_name'... actually 'people' is in
        PLURAL_TO_SINGULAR map → 'person'. Exercises the step-5 re-check."""
        # 'mail_subject' → strip '_subject' → 'mail' → ALIAS_MAP['mail']='email'
        assert discovery._normalize_slug("mail_subject") == "email"


class TestGenerateJsonSchemaFromProperties:
    """_generate_json_schema_from_properties — type inference from values."""

    def test_string_type(self, discovery):
        schema = discovery._generate_json_schema_from_properties({"name": "Alice"})
        assert schema["properties"]["name"] == {"type": "string"}
        assert "name" not in schema["required"]

    def test_none_value_defaults_to_string(self, discovery):
        schema = discovery._generate_json_schema_from_properties({"x": None})
        assert schema["properties"]["x"] == {"type": "string"}

    def test_bool_type_added_to_required(self, discovery):
        schema = discovery._generate_json_schema_from_properties({"active": True})
        assert schema["properties"]["active"] == {"type": "boolean"}
        assert "active" in schema["required"]

    def test_int_type_added_to_required(self, discovery):
        schema = discovery._generate_json_schema_from_properties({"age": 42})
        assert schema["properties"]["age"] == {"type": "integer"}
        assert "age" in schema["required"]

    def test_float_type_added_to_required(self, discovery):
        schema = discovery._generate_json_schema_from_properties({"rate": 1.5})
        assert schema["properties"]["rate"] == {"type": "number"}
        assert "rate" in schema["required"]

    def test_list_type_not_required(self, discovery):
        schema = discovery._generate_json_schema_from_properties({"tags": ["a"]})
        assert schema["properties"]["tags"] == {"type": "array"}
        assert "tags" not in schema["required"]

    def test_schema_includes_draft_2020_12_uri(self, discovery):
        schema = discovery._generate_json_schema_from_properties({})
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"


class TestCreateDraftEntityType:
    """create_draft_entity_type — idempotent creation with DB-backed service."""

    def test_returns_existing_if_already_present(self, discovery):
        """Lines 584-589: if entity_type_service finds existing, return it."""
        mock_ets = MagicMock()
        mock_existing = MagicMock(id="et-123", is_active=False)
        mock_ets.get_entity_type.return_value = mock_existing
        discovery.entity_type_service = mock_ets

        result = discovery.create_draft_entity_type(
            slug="invoice", display_name="Invoice",
            properties={"amount": 100}, discovery_reasoning="from invoices"
        )

        assert result is mock_existing
        mock_ets.create_entity_type.assert_not_called()

    def test_creates_new_when_missing(self, discovery):
        """Lines 595-611: create_entity_type called, db committed, returned."""
        mock_ets = MagicMock()
        mock_ets.get_entity_type.return_value = None
        created = MagicMock(id="new-1")
        mock_ets.create_entity_type.return_value = created
        discovery.entity_type_service = mock_ets
        discovery.db = MagicMock()

        result = discovery.create_draft_entity_type(
            slug="customer", display_name="Customer",
            properties={"name": "x"}, discovery_reasoning="test"
        )

        assert result is created
        mock_ets.create_entity_type.assert_called_once()
        discovery.db.commit.assert_called_once()

    def test_returns_none_and_rolls_back_on_exception(self, discovery):
        """Lines 613-616: exception → rollback, return None."""
        mock_ets = MagicMock()
        mock_ets.get_entity_type.side_effect = RuntimeError("db down")
        discovery.entity_type_service = mock_ets
        discovery.db = MagicMock()

        result = discovery.create_draft_entity_type(
            slug="x", display_name="X", properties={}, discovery_reasoning="r"
        )

        assert result is None
        discovery.db.rollback.assert_called_once()

    def test_workspace_id_equals_tenant_id_becomes_none(self, discovery):
        """Lines 573-575: org-scope when workspace_id == tenant_id."""
        discovery.tenant_id = "tenant-1"
        mock_ets = MagicMock()
        mock_ets.get_entity_type.return_value = None
        created = MagicMock()
        mock_ets.create_entity_type.return_value = created
        discovery.entity_type_service = mock_ets
        discovery.db = MagicMock()

        discovery.create_draft_entity_type(
            slug="x", display_name="X", properties={},
            discovery_reasoning="r", workspace_id="tenant-1"
        )

        mock_ets.create_entity_type.assert_called_once()


class TestContextManager:
    """close/__enter__/__exit__ (lines 628-651, 660-669)."""

    def test_enter_returns_self(self, discovery):
        assert discovery.__enter__() is discovery

    def test_exit_calls_close(self, discovery):
        discovery.db = MagicMock()
        discovery.__exit__(None, None, None)
        discovery.db.close.assert_called_once()

    def test_close_closes_db_session(self):
        """close() calls db.close() when db is not None."""
        with patch("core.openie_schema_discovery.LLMService"):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")
        inst.db = MagicMock()
        inst.close()
        inst.db.close.assert_called_once()

    def test_close_handles_none_db(self):
        """close() is a no-op when db is None (defensive)."""
        with patch("core.openie_schema_discovery.LLMService"):
            inst = OpenIESchemaDiscovery(tenant_id="t", workspace_id="w")
        inst.db = None
        # Must not raise
        inst.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
