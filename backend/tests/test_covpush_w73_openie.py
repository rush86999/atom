# -*- coding: utf-8 -*-
"""Coverage wave 73 — core/openie_schema_discovery branch completion.

Completes the last uncovered branch of _normalize_slug (the "-ies" plural
reduction) and adds the previously-unexercised service paths: _run_sync in
both loop/no-loop modes, _extract_json_text fencing, extract_entities_
with_core_hardcoding (unavailable LLM / core+custom classification / fenced
JSON / parse-failure), both prompt builders (incl. text truncation),
_classify_entity_type (exact/fuzzy/property/no-match), create_draft_entity_type
(exists/created/exception+rollback), _generate_json_schema_from_properties
type inference, and the context-manager lifecycle. Fully mocked deps, zero
LLM spend, no network, no real DB.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.openie_schema_discovery import (
    CORE_ENTITY_SCHEMAS,
    OpenIESchemaDiscovery,
    _extract_json_text,
    _run_sync,
)


@pytest.fixture()
def service():
    db = MagicMock()
    with patch(
        "core.openie_schema_discovery.EntityTypeService", MagicMock()
    ) as ets_cls, patch(
        "core.openie_schema_discovery.LLMService", MagicMock()
    ) as llm_cls:
        svc = OpenIESchemaDiscovery(tenant_id="tenant-1", db=db, workspace_id="ws-1")
        yield svc, db, ets_cls, llm_cls


# ============================================================================
# _run_sync
# ============================================================================

class TestRunSync:
    def test_no_running_loop_uses_asyncio_run(self):
        async def coro():
            return 42

        assert _run_sync(coro()) == 42

    @pytest.mark.asyncio
    async def test_running_loop_offloads_to_thread(self):
        async def coro():
            await asyncio.sleep(0)
            return "from-thread"

        assert await asyncio.to_thread(_run_sync, coro()) == "from-thread"


# ============================================================================
# _extract_json_text
# ============================================================================

class TestExtractJsonText:
    def test_empty_input(self):
        assert _extract_json_text("") == ""
        assert _extract_json_text(None) is None

    def test_plain_json_unchanged(self):
        raw = '{"entities": []}'
        assert _extract_json_text(raw) == raw

    def test_json_fence_stripped(self):
        assert _extract_json_text('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_plain_fence_stripped(self):
        assert _extract_json_text('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_no_fence_passthrough(self):
        assert _extract_json_text('  {"a": 1}  ') == '{"a": 1}'


# ============================================================================
# LLM extraction
# ============================================================================

class TestExtractEntitiesWithCoreHardcoding:
    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_error_dict(self, service):
        svc, db, ets_cls, llm_cls = service
        llm_cls.return_value.is_available.return_value = False

        result = svc.extract_entities_with_core_hardcoding("some text")
        assert result["entities"] == []
        assert result["error"] == "LLM client not available"

    @pytest.mark.asyncio
    async def test_success_with_core_and_custom(self, service):
        svc, db, ets_cls, llm_cls = service
        llm_cls.return_value.is_available.return_value = True
        llm_cls.return_value.generate = AsyncMock(return_value=(
            '{"entities": ['
            '{"name": "John Doe", "type": "person", "description": "a person", '
            '"properties": {"name": "John", "email": "j@x.com", "title": "CEO"}},'
            '{"name": "InvoiceItem", "type": "custom", "description": "line", '
            '"properties": {"amount": 100}}'
            '], "relationships": [{"from": "a", "to": "b", "type": "linked", '
            '"description": "rel"}], "discovery_reasoning": "because"}'
        ))

        result = svc.extract_entities_with_core_hardcoding("data", source="hubspot")

        assert result["core_entity_count"] == 1
        assert result["custom_entity_count"] == 1
        assert result["discovery_reasoning"] == "because"
        entities = result["entities"]
        assert entities[0]["properties"]["is_core"] is True
        assert entities[0]["properties"]["canonical_type"] == "user"
        assert entities[0]["properties"]["source"] == "hubspot"
        assert entities[0]["properties"]["llm_extracted"] is True
        assert entities[1]["properties"]["is_custom"] is True
        assert result["relationships"][0]["from"] == "a"
        assert result["relationships"][0]["properties"] == {"llm_extracted": True}
        llm_cls.return_value.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fenced_json_output(self, service):
        svc, db, ets_cls, llm_cls = service
        llm_cls.return_value.is_available.return_value = True
        llm_cls.return_value.generate = AsyncMock(
            return_value='```json\n{"entities": [{"name": "Contact", "type": "contact", "properties": {}}]}\n```'
        )

        result = svc.extract_entities_with_core_hardcoding("text")
        assert result["core_entity_count"] == 1
        assert result["entities"][0]["name"] == "Contact"

    @pytest.mark.asyncio
    async def test_parse_failure_returns_error(self, service, caplog):
        svc, db, ets_cls, llm_cls = service
        llm_cls.return_value.is_available.return_value = True
        llm_cls.return_value.generate = AsyncMock(return_value="not json at all")

        import logging
        with caplog.at_level(logging.ERROR, logger="core.openie_schema_discovery"):
            result = svc.extract_entities_with_core_hardcoding("text")

        assert result["entities"] == []
        assert "Expecting value" in result["error"]
        assert any("LLM extraction failed" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_missing_relationship_keys_tolerated(self, service):
        svc, db, ets_cls, llm_cls = service
        llm_cls.return_value.is_available.return_value = True
        llm_cls.return_value.generate = AsyncMock(return_value=(
            '{"entities": [], "relationships": [{"from": "a", "to": "b", "type": "t"}]}'
        ))
        result = svc.extract_entities_with_core_hardcoding("x")
        assert result["relationships"][0]["description"] == ""


class TestPromptBuilders:
    def test_build_extraction_prompt_includes_schemas_and_samples(self, service):
        svc, *_ = service
        sample = [{"id": i, "name": f"n{i}"} for i in range(8)]
        prompt = svc._build_extraction_prompt(sample)
        assert "Core Entity Types" in prompt
        assert '"Person"' in prompt
        assert "Sample Integration Data" in prompt
        # Truncated to 5 records
        assert '"n4"' in prompt
        assert '"n5"' not in prompt
        assert "discovery_reasoning" in prompt

    def test_build_prompt_from_text_truncates_at_6000(self, service):
        svc, *_ = service
        short = svc._build_extraction_prompt_from_text("x" * 100)
        prompt = svc._build_extraction_prompt_from_text("x" * 8000)
        assert "Core Entity Types" in prompt
        assert "JSON Schema:" in prompt
        # 8000-char text is truncated to 6000 chars inside the prompt
        assert prompt.count("x") - short.count("x") == 5900


# ============================================================================
# _classify_entity_type
# ============================================================================

class TestClassifyEntityType:
    def test_exact_name_match(self, service):
        svc, *_ = service
        result = svc._classify_entity_type("Organization", {})
        assert result == {"is_core": True, "canonical_type": "organization", "confidence": 1.0}

    def test_fuzzy_match(self, service):
        svc, *_ = service
        result = svc._classify_entity_type("customer", {})
        assert result == {"is_core": True, "canonical_type": "contact", "confidence": 0.8}

    def test_property_based_match(self, service):
        svc, *_ = service
        result = svc._classify_entity_type("Vendor", {"name": "x", "email": "y", "title": "z"})
        assert result["is_core"] is True
        assert result["canonical_type"] == "user"
        assert result["confidence"] == 0.7

    def test_no_match_custom(self, service):
        svc, *_ = service
        result = svc._classify_entity_type("Warehouse", {"shelf": 1})
        assert result == {"is_core": False, "canonical_type": None, "confidence": 0.0}


# ============================================================================
# _normalize_slug
# ============================================================================

class TestNormalizeSlug:
    @pytest.mark.parametrize("raw,expected", [
        ("EmailSubject", "email"),
        ("email_subject", "email"),
        ("  Contact   Name ", "contact_name"),
        ("person-name", "person"),
        ("contact_info", "contact"),
        ("email_content", "email"),
        ("order_detail", "order"),
        ("stories", "story"),
        ("categories", "category"),
        ("countries", "country"),
        ("queries", "query"),
        ("status", "status"),
        ("series", "series"),
        ("analysis", "analysis"),
        ("addresses", "address"),
        ("documents", "document"),
        ("people", "person"),
        ("organizations", "organization"),
        ("task", "task"),
        ("a__b___c", "a_b_c"),
        ("bookings", "booking"),
        ("virus", "virus"),
        ("campus", "campus"),
        ("paralysis", "paralysis"),
        ("contact_emails", "email"),
        ("phone_number", "phone"),
        ("date_time", "datetime"),
        ("timestamp", "datetime"),
        ("url_link", "url"),
        ("company_name", "organization"),
    ])
    def test_normalizations(self, raw, expected, service):
        svc, *_ = service
        assert svc._normalize_slug(raw) == expected

    def test_empty_slug(self, service):
        svc, *_ = service
        assert svc._normalize_slug("") == ""


# ============================================================================
# create_draft_entity_type
# ============================================================================

class TestCreateDraftEntityType:
    def test_existing_returns_existing(self, service):
        svc, db, ets_cls, _ = service
        existing = MagicMock()
        existing.id = "ets-1"
        existing.is_active = True
        ets_cls.return_value.get_entity_type.return_value = existing

        result = svc.create_draft_entity_type(
            slug="EmailSubject", display_name="Email", properties={"a": 1},
            discovery_reasoning="found it", confidence=0.9,
        )
        assert result is existing
        ets_cls.return_value.create_entity_type.assert_not_called()

    def test_created_draft(self, service):
        svc, db, ets_cls, _ = service
        ets_cls.return_value.get_entity_type.return_value = None
        created = MagicMock()
        ets_cls.return_value.create_entity_type.return_value = created

        result = svc.create_draft_entity_type(
            slug="Warehouse", display_name="Warehouse",
            properties={"name": "A", "is_active": True, "count": 3, "price": 1.5,
                        "tags": ["a"], "note": None},
            discovery_reasoning="new entity discovered",
        )
        assert result is created
        call_kwargs = ets_cls.return_value.create_entity_type.call_args.kwargs
        assert call_kwargs["tenant_id"] == "tenant-1"
        assert call_kwargs["slug"] == "warehouse"
        assert call_kwargs["is_active"] is False
        assert "new entity discovered" in call_kwargs["description"]
        assert call_kwargs["json_schema"]["properties"]["count"] == {"type": "integer"}
        assert call_kwargs["json_schema"]["properties"]["price"] == {"type": "number"}
        assert call_kwargs["json_schema"]["properties"]["is_active"] == {"type": "boolean"}
        assert call_kwargs["json_schema"]["properties"]["tags"] == {"type": "array"}
        assert call_kwargs["json_schema"]["properties"]["note"] == {"type": "string"}
        assert "count" in call_kwargs["json_schema"]["required"]
        db.commit.assert_called_once()

    def test_workspace_id_equal_tenant_becomes_none(self, service):
        svc, db, ets_cls, _ = service
        ets_cls.return_value.get_entity_type.return_value = None
        svc.create_draft_entity_type(
            slug="X", display_name="X", properties={}, discovery_reasoning="r",
            workspace_id="tenant-1",
        )
        get_call = ets_cls.return_value.get_entity_type.call_args
        assert get_call.kwargs["tenant_id"] == "tenant-1"

    def test_exception_rolls_back_and_returns_none(self, service, caplog):
        svc, db, ets_cls, _ = service
        ets_cls.return_value.get_entity_type.side_effect = RuntimeError("db exploded")

        import logging
        with caplog.at_level(logging.ERROR, logger="core.openie_schema_discovery"):
            result = svc.create_draft_entity_type(
                slug="X", display_name="X", properties={}, discovery_reasoning="r"
            )
        assert result is None
        db.rollback.assert_called_once()
        assert any("Failed to create draft entity type" in r.message for r in caplog.records)

    def test_create_call_omits_workspace_id(self, service):
        """create_entity_type has no workspace_id parameter — the service must
        not pass one (tenant-scoped draft creation)."""
        svc, db, ets_cls, _ = service
        ets_cls.return_value.get_entity_type.return_value = None
        svc.create_draft_entity_type(slug="Y", display_name="Y", properties={}, discovery_reasoning="r")
        assert "workspace_id" not in ets_cls.return_value.create_entity_type.call_args.kwargs


# ============================================================================
# _generate_json_schema_from_properties + lifecycle
# ============================================================================

class TestGenerateJsonSchema:
    def test_all_value_types(self, service):
        svc, *_ = service
        schema = svc._generate_json_schema_from_properties({
            "a": None, "b": True, "c": 5, "d": 2.5, "e": [1], "f": "text",
        })
        assert schema["$schema"].startswith("https://json-schema.org/draft/2020-12")
        assert schema["properties"]["a"] == {"type": "string"}
        assert schema["properties"]["b"] == {"type": "boolean"}
        assert schema["properties"]["c"] == {"type": "integer"}
        assert schema["properties"]["d"] == {"type": "number"}
        assert schema["properties"]["e"] == {"type": "array"}
        assert schema["properties"]["f"] == {"type": "string"}
        assert "b" in schema["required"]
        assert "c" in schema["required"]
        assert "d" in schema["required"]
        assert "e" not in schema["required"]

    def test_empty_properties(self, service):
        svc, *_ = service
        schema = svc._generate_json_schema_from_properties({})
        assert schema["properties"] == {}
        assert schema["required"] == []


class TestLifecycle:
    def test_close_closes_db(self, service):
        svc, db, _, _ = service
        svc.close()
        db.close.assert_called_once()

    def test_context_manager(self, service):
        svc, db, _, _ = service
        with svc as entered:
            assert entered is svc
        db.close.assert_called_once()

    def test_db_defaults_to_sessionlocal(self):
        with patch("core.openie_schema_discovery.SessionLocal") as sl_cls, patch(
            "core.openie_schema_discovery.EntityTypeService", MagicMock()
        ), patch("core.openie_schema_discovery.LLMService", MagicMock()):
            svc = OpenIESchemaDiscovery()
            assert svc.db is sl_cls.return_value
            assert svc.tenant_id == "default"
            assert svc.workspace_id is None

    def test_core_schemas_shape(self):
        assert set(CORE_ENTITY_SCHEMAS.keys()) == {"Person", "Organization", "Contact", "Project", "Task"}
        assert CORE_ENTITY_SCHEMAS["Person"]["canonical_type"] == "user"
        assert len(CORE_ENTITY_SCHEMAS["Person"]["examples"]) == 2
