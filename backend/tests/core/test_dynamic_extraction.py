import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from core.knowledge_extractor import KnowledgeExtractor
from core.models import EntityTypeDefinition

VALID_JSON = '{"entities": [], "relationships": []}'


def _mock_llm_service():
    """Patch core.knowledge_extractor.LLMService with an AsyncMock whose
    generate_completion returns parseable JSON content."""
    mock_llm = AsyncMock()
    mock_llm.generate_completion.return_value = {"content": VALID_JSON}
    return patch("core.knowledge_extractor.LLMService", return_value=mock_llm), mock_llm


def _capture_system_prompt(mock_llm):
    """Extract the system prompt from the last generate_completion call."""
    args, kwargs = mock_llm.generate_completion.call_args
    messages = kwargs.get("messages") or args[0]
    return next(m["content"] for m in messages if m["role"] == "system")


@pytest.mark.asyncio
async def test_extract_knowledge_dynamic_prompt():
    # Mock LLMService (the extractor builds its own; no constructor injection)
    llm_patch, mock_llm = _mock_llm_service()

    # Mock custom entity types in DB
    mock_ct = MagicMock(spec=EntityTypeDefinition)
    mock_ct.id = "123"
    mock_ct.slug = "competitor"
    mock_ct.display_name = "Competitor"
    mock_ct.description = "A business rival"
    mock_ct.json_schema = {"properties": {"name": {"type": "string"}, "market_share": {"type": "number"}}}
    mock_ct.tenant_id = "test_tenant"
    mock_ct.is_active = True
    mock_ct.is_system = False

    # The prompt is built from the ONTOLOGY schema (not direct DB reads of
    # EntityTypeDefinition any more) — patch the ontology service with a
    # schema containing the custom type plus a base type.
    fake_schema = {
        "entity_types": [
            {
                "slug": "competitor",
                "description": "A business rival",
                "json_schema": {
                    "properties": {"name": {"type": "string"}, "market_share": {"type": "number"}}
                },
                "abstract": False,
            },
            {
                "slug": "Person",
                "fields": "name, role, organization, is_stakeholder: bool",
                "abstract": False,
            },
        ],
        "relations": [
            {
                "name": "COMPETES_WITH",
                "domain": ["competitor"],
                "range": ["competitor"],
                "description": "rivalry between companies",
            }
        ],
    }

    with llm_patch, patch(
        "core.ontology.get_ontology_service",
        return_value=MagicMock(get_schema=lambda: fake_schema),
    ):
        extractor = KnowledgeExtractor(tenant_id="test_tenant")

        # Trigger extraction
        result = await extractor.extract_knowledge("Our main rival is ACME Corp.", tenant_id="test_tenant")

        # Verify system prompt contains the custom type
        assert mock_llm.generate_completion.called
        system_prompt = _capture_system_prompt(mock_llm)

        assert "competitor (A business rival)" in system_prompt
        assert "Fields: [name, market_share]" in system_prompt
        assert "Person (name, role, organization, is_stakeholder: bool)" in system_prompt
        assert result == {"entities": [], "relationships": []}


@pytest.mark.asyncio
async def test_extract_knowledge_no_tenant():
    llm_patch, mock_llm = _mock_llm_service()

    # Base-types-only ontology schema (no custom types).
    fake_schema = {
        "entity_types": [
            {
                "slug": "Person",
                "fields": "name, role, organization, is_stakeholder: bool",
                "abstract": False,
            },
        ],
        "relations": [
            {"name": "KNOWS", "domain": ["Person"], "range": ["Person"]},
        ],
    }

    with llm_patch, patch(
        "core.ontology.get_ontology_service",
        return_value=MagicMock(get_schema=lambda: fake_schema),
    ):
        extractor = KnowledgeExtractor()
        await extractor.extract_knowledge("Hello world")

        assert mock_llm.generate_completion.called
        system_prompt = _capture_system_prompt(mock_llm)

        # Should only have base entities
        assert "Person (name, role, organization, is_stakeholder: bool)" in system_prompt
        assert "Competitor" not in system_prompt
