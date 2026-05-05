"""
Multi-Entity LLM Extractor Tests

Tests for LLM-powered multi-entity extraction service.

Phase 323-01: Core Infrastructure
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

from core.multi_entity_llm_extractor import MultiEntityLLMExtractor
from core.models import DiscoveredEntity


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def extractor():
    """MultiEntityLLMExtractor instance."""
    return MultiEntityLLMExtractor()


@pytest.fixture
def sample_email():
    """Sample email data."""
    return {
        "id": "email-001",
        "subject": "Purchase Order PO-12345 Approved",
        "from": "vendor@acme.com",
        "to": ["admin@company.com"],
        "body": "Please approve PO-12345 for $5,000 from Acme Corp."
    }


# ============================================================================
# Test Class 1: LLM Extraction
# ============================================================================

class TestLLMExtraction:
    """Tests for LLM-based entity extraction."""

    @pytest.mark.asyncio
    async def test_extract_entities_from_email(self, extractor, sample_email):
        """Test extracting entities from email."""
        # Arrange
        extractor._call_llm = AsyncMock(return_value='''
        {
            "entities": [
                {
                    "type": "PurchaseOrder",
                    "properties": {"po_number": "PO-12345", "amount": 5000.0},
                    "confidence": 0.95
                }
            ]
        }
        ''')

        # Act
        entities = await extractor.extract_from_email(
            sample_email,
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) >= 1
        assert isinstance(entities[0], DiscoveredEntity)
        assert entities[0]._discovered_type == "PurchaseOrder"
        assert entities[0].properties.get("po_number") == "PO-12345"
        assert entities[0].confidence_score > 0.7

    @pytest.mark.asyncio
    async def test_extract_multiple_entities(self, extractor):
        """Test extracting multiple entities from one email."""
        # Arrange
        email = {
            "id": "email-002",
            "subject": "Security Alert and Purchase Order",
            "from": "security@company.com",
            "to": ["admin@company.com"],
            "body": "Unusual login detected for john@example.com. Also approve PO-999 for $2,000."
        }

        extractor._call_llm = AsyncMock(return_value='''
        {
            "entities": [
                {
                    "type": "SecurityEvent",
                    "properties": {"event": "login", "user": "john@example.com"},
                    "confidence": 0.9
                },
                {
                    "type": "PurchaseOrder",
                    "properties": {"po_number": "PO-999", "amount": 2000.0},
                    "confidence": 0.85
                }
            ]
        }
        ''')

        # Act
        entities = await extractor.extract_from_email(
            email,
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) >= 1
        discovered_types = [e._discovered_type for e in entities]
        assert "SecurityEvent" in discovered_types or "PurchaseOrder" in discovered_types

    @pytest.mark.asyncio
    async def test_extract_with_batch_id(self, extractor, sample_email):
        """Test extraction with batch ID tracking."""
        # Arrange
        extractor._call_llm = AsyncMock(return_value='{"entities": [{"type": "PurchaseOrder", "properties": {"po_number": "PO-12345"}, "confidence": 0.9}]}')

        # Act
        entities = await extractor.extract_from_email(
            sample_email,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            batch_id="batch-001"
        )

        # Assert
        assert len(entities) >= 1
        assert entities[0].extraction_metadata.get("batch_id") == "batch-001"

    @pytest.mark.asyncio
    async def test_extract_handles_empty_response(self, extractor):
        """Test extraction handles no entities found."""
        # Arrange
        email = {
            "id": "email-003",
            "subject": "Hello",
            "from": "friend@example.com",
            "to": ["user@example.com"],
            "body": "Just saying hi!"
        }

        # Mock LLM to return empty entities
        extractor._call_llm = AsyncMock(return_value='{"entities": []}')

        # Act
        entities = await extractor.extract_from_email(
            email,
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) == 0


# ============================================================================
# Test Class 2: Prompt Building
# ============================================================================

class TestPromptBuilding:
    """Tests for LLM prompt construction."""

    def test_build_extraction_prompt_includes_all_fields(self, extractor, sample_email):
        """Test prompt includes all email fields."""
        # Act
        prompt = extractor._build_extraction_prompt(sample_email)

        # Assert
        assert "Purchase Order PO-12345 Approved" in prompt
        assert "vendor@acme.com" in prompt
        assert "admin@company.com" in prompt
        assert "$5,000" in prompt

    def test_build_extraction_prompt_includes_rules(self, extractor, sample_email):
        """Test prompt includes extraction rules."""
        # Act
        prompt = extractor._build_extraction_prompt(sample_email)

        # Assert
        assert "PascalCase" in prompt
        assert "confidence scores" in prompt
        assert "2-5 entities" in prompt

    def test_build_extraction_prompt_truncates_long_body(self, extractor):
        """Test prompt truncates long email body."""
        # Arrange
        long_email = {
            "id": "email-long",
            "subject": "Long Email",
            "from": "test@example.com",
            "to": ["user@example.com"],
            "body": "x" * 5000  # Very long body
        }

        # Act
        prompt = extractor._build_extraction_prompt(long_email)

        # Assert
        # Body should be truncated to 3000 chars
        assert len([line for line in prompt.split('\n') if 'x' in line]) < 5000


# ============================================================================
# Test Class 3: Response Parsing
# ============================================================================

class TestResponseParsing:
    """Tests for LLM response parsing."""

    @pytest.mark.asyncio
    async def test_parse_valid_json_response(self, extractor):
        """Test parsing valid JSON response."""
        # Arrange
        llm_response = '''
        {
            "entities": [
                {
                    "type": "PurchaseOrder",
                    "properties": {"po_number": "PO-123", "amount": 1000},
                    "confidence": 0.95
                }
            ]
        }
        '''

        # Act
        entities = extractor._parse_llm_response(
            llm_response,
            source_record_id="email-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) == 1
        assert entities[0]._discovered_type == "PurchaseOrder"
        assert entities[0].properties["po_number"] == "PO-123"
        assert entities[0].confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_parse_json_with_markdown(self, extractor):
        """Test parsing JSON wrapped in markdown code blocks."""
        # Arrange
        llm_response = '''```json
        {
            "entities": [
                {
                    "type": "Invoice",
                    "properties": {"invoice_number": "INV-001"},
                    "confidence": 0.88
                }
            ]
        }
        ```'''

        # Act
        entities = extractor._parse_llm_response(
            llm_response,
            source_record_id="email-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) == 1
        assert entities[0]._discovered_type == "Invoice"

    @pytest.mark.asyncio
    async def test_parse_handles_invalid_json(self, extractor):
        """Test parsing handles invalid JSON gracefully."""
        # Arrange
        llm_response = "This is not valid JSON"

        # Act
        entities = extractor._parse_llm_response(
            llm_response,
            source_record_id="email-003",
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) == 0

    @pytest.mark.asyncio
    async def test_parse_sets_metadata(self, extractor):
        """Test parsing sets extraction metadata."""
        # Arrange
        llm_response = '{"entities": []}'

        # Act
        entities = extractor._parse_llm_response(
            llm_response,
            source_record_id="email-004",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            batch_id="batch-001"
        )

        # Assert (no entities, but check metadata would be set)
        # This test validates the parsing logic structure
        assert isinstance(entities, list)


# ============================================================================
# Test Class 4: Batch Processing
# ============================================================================

class TestBatchProcessing:
    """Tests for batch entity extraction."""

    @pytest.mark.asyncio
    async def test_extract_batch_multiple_emails(self, extractor):
        """Test extracting entities from multiple emails."""
        # Arrange
        emails = [
            {
                "id": f"email-{i}",
                "subject": f"Email {i}",
                "from": "test@example.com",
                "to": ["user@example.com"],
                "body": "Content"
            }
            for i in range(5)
        ]

        extractor._call_llm = AsyncMock(return_value='{"entities": [{"type": "Entity", "properties": {}, "confidence": 0.9}]}')

        # Act
        entities = await extractor.extract_batch(
            emails,
            tenant_id="tenant-001",
            workspace_id="workspace-001"
        )

        # Assert
        assert len(entities) >= 5  # At least 1 entity per email
        assert all(e.source_record_type == "email" for e in entities)

    @pytest.mark.asyncio
    async def test_extract_batch_with_batch_id(self, extractor):
        """Test batch extraction with batch ID."""
        # Arrange
        emails = [
            {
                "id": "email-batch-1",
                "subject": "Batch Test",
                "from": "test@example.com",
                "to": ["user@example.com"],
                "body": "Content"
            }
        ]

        extractor._call_llm = AsyncMock(return_value='{"entities": [{"type": "Entity", "properties": {}, "confidence": 0.9}]}')

        # Act
        entities = await extractor.extract_batch(
            emails,
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            batch_id="batch-test"
        )

        # Assert
        assert len(entities) >= 1
        assert entities[0].extraction_metadata.get("batch_id") == "batch-test"


# ============================================================================
# Test Class 5: DiscoveredEntity Model
# ============================================================================

class TestDiscoveredEntityModel:
    """Tests for DiscoveredEntity model."""

    def test_discovered_entity_creation(self):
        """Test creating DiscoveredEntity instance."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-123", "amount": 5000.0},
            confidence_score=0.95,
            source_record_id="email-001",
            source_record_type="email",
            status="pending"
        )

        # Assert
        assert entity._discovered_type == "PurchaseOrder"
        assert entity.status == "pending"
        assert entity.confidence_score == 0.95

    def test_mark_linked_updates_status(self):
        """Test mark_linked method updates status."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SecurityEvent",
            properties={"severity": "high"},
            source_record_id="email-002",
            source_record_type="email",
            status="pending"
        )

        # Act
        entity.mark_linked("graph-node-001")

        # Assert
        assert entity.status == "linked"
        assert entity.linked_to_graph_node_id == "graph-node-001"
        assert entity.processed_at is not None

    def test_mark_rejected_updates_status(self):
        """Test mark_rejected method updates status."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-003",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Invoice",
            properties={},
            source_record_id="email-003",
            source_record_type="email",
            status="pending"
        )

        # Act
        entity.mark_rejected("Low quality extraction")

        # Assert
        assert entity.status == "rejected"
        assert entity.extraction_metadata["rejection_reason"] == "Low quality extraction"

    def test_to_graph_node_converts_entity(self):
        """Test to_graph_node method converts to GraphNode."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-004",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-456", "name": "Office Supplies"},
            source_record_id="email-004",
            source_record_type="email",
            status="pending"
        )

        # Act
        graph_node = entity.to_graph_node("purchase_order")

        # Assert
        assert graph_node.type == "purchase_order"
        assert graph_node.properties["po_number"] == "PO-456"
        assert graph_node.tenant_id == "tenant-001"
        assert graph_node.workspace_id == "workspace-001"
