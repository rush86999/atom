import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from core.knowledge_extractor import KnowledgeExtractor
from core.models import EntityTypeDefinition

@pytest.mark.asyncio
async def test_extract_knowledge_dynamic_prompt():
    # Mock AI Service with AsyncMock
    mock_ai = AsyncMock()
    mock_ai.analyze_text.return_value = {"success": True, "response": '{"entities": [], "relationships": []}'}
    
    extractor = KnowledgeExtractor(mock_ai)
    
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

    with patch("core.knowledge_extractor.get_db_session") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        
        # Correctly mock a single .filter() call with arguments
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_ct]
        
        # Trigger extraction
        await extractor.extract_knowledge("Our main rival is ACME Corp.", tenant_id="test_tenant")
        
        # Verify system prompt contains the custom type
        # analyze_text is called once
        assert mock_ai.analyze_text.called
        args, kwargs = mock_ai.analyze_text.call_args
        system_prompt = kwargs.get("system_prompt", "")
        
        assert "Competitor (A business rival)" in system_prompt
        assert "Fields: [name, market_share]" in system_prompt
        assert "Person (name, role, organization, is_stakeholder: bool)" in system_prompt

@pytest.mark.asyncio
async def test_extract_knowledge_no_tenant():
    mock_ai = AsyncMock()
    mock_ai.analyze_text.return_value = {"success": True, "response": '{"entities": [], "relationships": []}'}
    extractor = KnowledgeExtractor(mock_ai)
    
    await extractor.extract_knowledge("Hello world")
    
    assert mock_ai.analyze_text.called
    args, kwargs = mock_ai.analyze_text.call_args
    system_prompt = kwargs.get("system_prompt", "")
    
    # Should only have base entities
    assert "Person (name, role, organization, is_stakeholder: bool)" in system_prompt
    assert "Competitor" not in system_prompt
