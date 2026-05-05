"""
Schema Discovery Service Tests

Tests for automatic schema discovery from LLM-extracted entities.

Phase 323-02: Schema Discovery & Entity Linking
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from core.schema_discovery_service import SchemaDiscoveryService
from core.models import DiscoveredEntity, EntityTypeDefinition


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def discovery_service(db_session):
    """SchemaDiscoveryService instance."""
    from core.schema_discovery_service import SchemaDiscoveryService
    return SchemaDiscoveryService(db_session)


@pytest.fixture
def sample_purchase_order_entities():
    """Sample PurchaseOrder entities for testing."""
    return [
        DiscoveredEntity(
            id="entity-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={
                "po_number": "PO-12345",
                "vendor": "Acme Corp",
                "amount": 5000.00,
                "currency": "USD",
                "approval_status": "pending"
            },
            confidence_score=0.95,
            source_record_id="email-001",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="entity-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={
                "po_number": "PO-67890",
                "vendor": "Global Supplies Inc",
                "amount": 7500.50,
                "currency": "USD",
                "approval_status": "approved"
            },
            confidence_score=0.88,
            source_record_id="email-002",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="entity-003",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={
                "po_number": "PO-11111",
                "vendor": "Tech Solutions LLC",
                "amount": 3200.00,
                "currency": "USD",
                "approval_status": "pending"
            },
            confidence_score=0.92,
            source_record_id="email-003",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="entity-004",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={
                "po_number": "PO-22222",
                "vendor": "Office Depot",
                "amount": 1200.75,
                "currency": "USD"
            },
            confidence_score=0.85,
            source_record_id="email-004",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="entity-005",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={
                "po_number": "PO-33333",
                "vendor": "Staples",
                "amount": 890.00,
                "currency": "USD"
            },
            confidence_score=0.90,
            source_record_id="email-005",
            source_record_type="email"
        )
    ]


@pytest.fixture
def sample_security_event_entities():
    """Sample SecurityEvent entities for testing."""
    return [
        DiscoveredEntity(
            id="entity-101",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SecurityEvent",
            properties={
                "event_type": "unusual_login",
                "severity": "high",
                "user": "john@example.com",
                "location": "Unknown IP",
                "detected_at": "2026-05-05T10:30:00Z"
            },
            confidence_score=0.92,
            source_record_id="email-101",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="entity-102",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SecurityEvent",
            properties={
                "event_type": "malware_detected",
                "severity": "critical",
                "user": "jane@example.com",
                "location": "Downloaded suspicious file",
                "detected_at": "2026-05-05T11:45:00Z"
            },
            confidence_score=0.88,
            source_record_id="email-102",
            source_record_type="email"
        )
    ]


# ============================================================================
# Test Class 1: Schema Discovery from Entities
# ============================================================================

class TestSchemaDiscovery:
    """Tests for schema discovery from entity samples."""

    @pytest.mark.asyncio
    async def test_discover_schema_from_purchase_orders(self, discovery_service, sample_purchase_order_entities):
        """Test discovering schema from PurchaseOrder entities."""
        # Arrange
        for entity in sample_purchase_order_entities:
            discovery_service.db.add(entity)
        discovery_service.db.commit()

        # Act
        entity_types = await discovery_service.discover_schemas_from_entities(
            "tenant-001",
            "workspace-001",
            min_sample_count=5
        )

        # Assert
        assert len(entity_types) == 1
        purchase_order_type = entity_types[0]
        assert purchase_order_type.slug == "purchase_order"
        assert purchase_order_type.display_name == "PurchaseOrder"
        assert "properties" in purchase_order_type.json_schema

        # Check inferred schema
        schema = purchase_order_type.json_schema
        assert "po_number" in schema["properties"]
        assert schema["properties"]["po_number"]["type"] == "string"
        assert "amount" in schema["properties"]
        assert schema["properties"]["amount"]["type"] == "number"

    @pytest.mark.asyncio
    async def test_discover_schema_from_security_events(self, discovery_service, sample_security_event_entities):
        """Test discovering schema from SecurityEvent entities."""
        # Arrange
        for entity in sample_security_event_entities:
            discovery_service.db.add(entity)
        discovery_service.db.commit()

        # Act
        entity_types = await discovery_service.discover_schemas_from_entities(
            "tenant-001",
            "workspace-001",
            min_sample_count=2  # Lower threshold for test
        )

        # Assert
        assert len(entity_types) == 1
        security_event_type = entity_types[0]
        assert security_event_type.slug == "security_event"
        assert security_event_type.display_name == "SecurityEvent"
        assert "event_type" in security_event_type.json_schema["properties"]

    @pytest.mark.asyncio
    async def test_skip_types_with_insufficient_samples(self, discovery_service):
        """Test that types with <5 samples are skipped."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-201",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Invoice",
            properties={"invoice_number": "INV-001"},
            confidence_score=0.8,
            source_record_id="email-201",
            source_record_type="email"
        )
        discovery_service.db.add(entity)
        discovery_service.db.commit()

        # Act
        entity_types = await discovery_service.discover_schemas_from_entities(
            "tenant-001",
            "workspace-001",
            min_sample_count=5
        )

        # Assert
        assert len(entity_types) == 0  # Invoice skipped (only 1 sample)

    @pytest.mark.asyncio
    async def test_discover_multiple_types_simultaneously(self, discovery_service):
        """Test discovering schemas for multiple entity types at once."""
        # Arrange
        entities = sample_purchase_order_entities[:3] + sample_security_event_entities[:2]
        for entity in entities:
            discovery_service.db.add(entity)
        discovery_service.db.commit()

        # Act
        entity_types = await discovery_service.discover_schemas_from_entities(
            "tenant-001",
            "workspace-001",
            min_sample_count=2
        )

        # Assert
        assert len(entity_types) == 2
        slugs = {et.slug for et in entity_types}
        assert "purchase_order" in slugs
        assert "security_event" in slugs


# ============================================================================
# Test Class 2: JSON Schema Inference
# ============================================================================

class TestSchemaInference:
    """Tests for JSON schema inference from entity properties."""

    def test_infer_string_properties(self, discovery_service):
        """Test inferring string property types."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-301",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="TestEntity",
            properties={
                "name": "Test",
                "description": "A test entity",
                "notes": "Some notes"
            },
            confidence_score=0.8,
            source_record_id="email-301",
            source_record_type="email"
        )

        # Act
        schema = discovery_service._infer_json_schema([entity])

        # Assert
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"
        assert "name" in schema["required"]  # Non-null values are required

    def test_infer_number_properties(self, discovery_service):
        """Test inferring number property types."""
        # Arrange
        entities = [
            DiscoveredEntity(
                id=f"entity-{i}",
                tenant_id="tenant-001",
                workspace_id="workspace-001",
                _discovered_type="TestEntity",
                properties={"amount": 100.0 + i * 50},
                confidence_score=0.8,
                source_record_id=f"email-{i}",
                source_record_type="email"
            )
            for i in range(3)
        ]

        # Act
        schema = discovery_service._infer_json_schema(entities)

        # Assert
        assert "amount" in schema["properties"]
        assert schema["properties"]["amount"]["type"] == "number"
        assert "minimum" in schema["properties"]["amount"]
        assert schema["properties"]["amount"]["minimum"] == 100.0

    def test_infer_boolean_properties(self, discovery_service):
        """Test inferring boolean property types."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-302",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="TestEntity",
            properties={
                "is_active": True,
                "is_deleted": False,
                "is_approved": True
            },
            confidence_score=0.8,
            source_record_id="email-302",
            source_record_type="email"
        )

        # Act
        schema = discovery_service._infer_json_schema([entity])

        # Assert
        assert "is_active" in schema["properties"]
        assert schema["properties"]["is_active"]["type"] == "boolean"

    def test_infer_array_properties(self, discovery_service):
        """Test inferring array property types."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-303",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="TestEntity",
            properties={
                "tags": ["important", "urgent", "finance"],
                "attachments": ["file1.pdf", "file2.pdf"]
            },
            confidence_score=0.8,
            source_record_id="email-303",
            source_record_type="email"
        )

        # Act
        schema = discovery_service._infer_json_schema([entity])

        # Assert
        assert "tags" in schema["properties"]
        assert schema["properties"]["tags"]["type"] == "array"
        assert "items" in schema["properties"]["tags"]
        assert schema["properties"]["tags"]["items"]["type"] == "string"


# ============================================================================
# Test Class 3: Type Inference Helpers
# ============================================================================

class TestTypeInference:
    """Tests for type inference helper methods."""

    def test_infer_type_from_string(self, discovery_service):
        """Test inferring type from string values."""
        assert discovery_service._infer_type_from_value("hello") == "string"
        assert discovery_service._infer_type_from_value("") == "string"

    def test_infer_type_from_number(self, discovery_service):
        """Test inferring type from numeric values."""
        assert discovery_service._infer_type_from_value(42) == "integer"
        assert discovery_service._infer_type_from_value(3.14) == "number"

    def test_infer_type_from_boolean(self, discovery_service):
        """Test inferring type from boolean values."""
        assert discovery_service._infer_type_from_value(True) == "boolean"
        assert discovery_service._infer_type_from_value(False) == "boolean"

    def test_infer_type_from_null(self, discovery_service):
        """Test inferring type from None values."""
        assert discovery_service._infer_type_from_value(None) == "null"

    def test_infer_type_from_list(self, discovery_service):
        """Test inferring type from list values."""
        assert discovery_service._infer_type_from_value([]) == "array"
        assert discovery_service._infer_type_from_value([1, 2, 3]) == "array"
        assert discovery_service._infer_type_from_value([{"a": 1}]) == "array"

    def test_infer_type_from_dict(self, discovery_service):
        """Test inferring type from dict values."""
        assert discovery_service._infer_type_from_value({}) == "object"
        assert discovery_service._infer_type_from_value({"key": "value"}) == "object"


# ============================================================================
# Test Class 4: PascalCase to Slug Conversion
# ============================================================================

class TestPascalCaseSlugConversion:
    """Tests for PascalCase to slug_case conversion."""

    def test_simple_pascal_case_conversion(self, discovery_service):
        """Test converting simple PascalCase to slug."""
        assert discovery_service._pascal_to_slug("PurchaseOrder") == "purchase_order"
        assert discovery_service._pascal_to_slug("SecurityEvent") == "security_event"

    def test_multi_word_pascal_case_conversion(self, discovery_service):
        """Test converting multi-word PascalCase to slug."""
        assert discovery_service._pascal_to_slug("PurchaseOrderLineItem") == "purchase_order_line_item"
        assert discovery_service._pascal_to_slug("SecurityEventDetector") == "security_event_detector"

    def test_single_word_pascal_case_conversion(self, discovery_service):
        """Test converting single-word PascalCase to slug."""
        assert discovery_service._pascal_to_slug("Invoice") == "invoice"
        assert discovery_service._pascal_to_slug("Ticket") == "ticket"


# ============================================================================
# Test Class 5: Schema Quality
# ============================================================================

class TestSchemaQuality:
    """Tests for schema quality and correctness."""

    def test_schema_has_required_fields(self, discovery_service):
        """Test that required fields are correctly identified."""
        # Arrange
        entities = [
            DiscoveredEntity(
                id=f"entity-{i}",
                tenant_id="tenant-001",
                workspace_id="workspace-001",
                _discovered_type="TestEntity",
                properties={
                    "required_field": f"value-{i}",  # Always present
                    "optional_field": None  # Always missing
                },
                confidence_score=0.8,
                source_record_id=f"email-{i}",
                source_record_type="email"
            )
            for i in range(10)
        ]

        # Act
        schema = discovery_service._infer_json_schema(entities)

        # Assert
        assert "required_field" in schema["required"]
        assert "optional_field" not in schema["required"]

    def test_schema_includes_metadata(self, discovery_service, sample_purchase_order_entities):
        """Test that created schemas include metadata."""
        # Arrange
        for entity in sample_purchase_order_entities:
            discovery_service.db.add(entity)
        discovery_service.db.commit()

        # Act
        import asyncio
        entity_types = asyncio.run(discovery_service.discover_schemas_from_entities(
            "tenant-001",
            "workspace-001",
            min_sample_count=5
        ))

        # Assert
        assert len(entity_types) == 1
        entity_type = entity_types[0]
        assert "metadata_json" in entity_type.__table_args__
        assert "discovered_type" in entity_type.metadata_json
        assert entity_type.metadata_json["sample_count"] == 5
        assert entity_type.metadata_json["auto_created"] is True
