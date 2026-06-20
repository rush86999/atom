"""
Entity Linking Service Tests

Tests for linking discovered entities to graph nodes.

Phase 323-02: Schema Discovery & Entity Linking
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone

from core.entity_linking_service import EntityLinkingService
from core.schema_discovery_service import SchemaDiscoveryService
from core.models import DiscoveredEntity, GraphNode, EntityTypeDefinition


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def linking_service(db_session):
    """EntityLinkingService instance."""
    schema_discovery = SchemaDiscoveryService(db_session)
    return EntityLinkingService(db_session, schema_discovery)


@pytest.fixture
def sample_purchase_order_entities():
    """Sample PurchaseOrder entities for linking."""
    return [
        DiscoveredEntity(
            id="entity-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-12345", "amount": 5000.0},
            confidence_score=0.95,
            source_record_id="email-001",
            source_record_type="email"
        ),
        DiscoveredEntity(
            id="entity-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-67890", "amount": 7500.0},
            confidence_score=0.88,
            source_record_id="email-002",
            source_record_type="email"
        )
    ]


@pytest.fixture
def sample_entity_type(db_session):
    """Sample EntityTypeDefinition for testing."""
    entity_type = EntityTypeDefinition(
        id="type-001",
        tenant_id="tenant-001",
        slug="purchase_order",
        display_name="PurchaseOrder",
        json_schema={
            "type": "object",
            "properties": {
                "po_number": {"type": "string"},
                "amount": {"type": "number"}
            }
        },
        is_active=True,
        metadata_json={"source": "llm_discovery"}
    )
    db_session.add(entity_type)
    db_session.commit()
    return entity_type


# ============================================================================
# Test Class 1: Entity Linking
# ============================================================================

class TestEntityLinking:
    """Tests for linking discovered entities to graph nodes."""

    @pytest.mark.asyncio
    async def test_link_entities_to_existing_type(self, linking_service, sample_purchase_order_entities, sample_entity_type):
        """Test linking entities to existing entity type."""
        # Arrange
        for entity in sample_purchase_order_entities:
            linking_service.db.add(entity)
        linking_service.db.commit()

        # Act
        graph_nodes = await linking_service.link_entities_to_graph(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            auto_create_types=False
        )

        # Assert
        assert len(graph_nodes) == 2
        assert all(node.type == "purchase_order" for node in graph_nodes)

        # Verify entities are marked as linked
        linked_entities = linking_service.db.query(DiscoveredEntity).filter(
            DiscoveredEntity.status == "linked"
        ).all()
        assert len(linked_entities) == 2

    @pytest.mark.asyncio
    async def test_link_entities_creates_graph_nodes(self, linking_service, sample_purchase_order_entities, sample_entity_type):
        """Test that linking creates GraphNodes with correct properties."""
        # Arrange
        for entity in sample_purchase_order_entities:
            linking_service.db.add(entity)
        linking_service.db.commit()

        # Act
        graph_nodes = await linking_service.link_entities_to_graph(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            auto_create_types=False
        )

        # Assert
        assert len(graph_nodes) == 2

        # Check first GraphNode
        node1 = graph_nodes[0]
        assert node1.type == "purchase_order"
        assert node1.properties["po_number"] == "PO-12345"
        assert node1.properties["amount"] == 5000.0
        assert node1.tenant_id == "tenant-001"
        assert node1.workspace_id == "workspace-001"

    @pytest.mark.asyncio
    async def test_link_entities_with_confidence_filtering(self, linking_service, sample_purchase_order_entities):
        """Test linking only high-confidence entities."""
        # Arrange
        # Add a low-confidence entity
        low_confidence_entity = DiscoveredEntity(
            id="entity-003",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-LOW", "amount": 100.0},
            confidence_score=0.3,  # Below threshold
            source_record_id="email-003",
            source_record_type="email"
        )
        for entity in sample_purchase_order_entities + [low_confidence_entity]:
            linking_service.db.add(entity)
        linking_service.db.commit()

        # Act - only link entities with confidence >= 0.8
        graph_nodes = await linking_service.link_entities_to_graph(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            auto_create_types=False,
            min_confidence=0.8
        )

        # Assert - only 2 high-confidence entities linked
        assert len(graph_nodes) == 2
        assert all(n.properties.get("po_number") != "PO-LOW" for n in graph_nodes)


# ============================================================================
# Test Class 2: Novel Type Creation
# ============================================================================

class TestNovelTypeCreation:
    """Tests for auto-creating novel entity types."""

    @pytest.mark.asyncio
    async def test_create_novel_type_from_single_entity(self, linking_service):
        """Test creating novel entity type from single entity."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-novel-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Invoice",  # Novel type
            properties={"invoice_number": "INV-001", "amount": 1000.0},
            confidence_score=0.85,
            source_record_id="email-novel-001",
            source_record_type="email"
        )
        linking_service.db.add(entity)
        linking_service.db.commit()

        # Act
        graph_nodes = await linking_service.link_entities_to_graph(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            auto_create_types=True
        )

        # Assert
        assert len(graph_nodes) == 1
        node = graph_nodes[0]
        assert node.type == "invoice"

        # Check that EntityTypeDefinition was created
        entity_type = linking_service.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.slug == "invoice",
            EntityTypeDefinition.tenant_id == "tenant-001"
        ).first()
        assert entity_type is not None
        assert entity_type.display_name == "Invoice"

    @pytest.mark.asyncio
    async def test_skip_novel_type_creation_when_disabled(self, linking_service):
        """Test that novel types are not created when auto_create_types=False."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-novel-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Product",  # Novel type
            properties={"product_name": "Widget", "sku": "WGT-001"},
            confidence_score=0.90,
            source_record_id="email-novel-002",
            source_record_type="email"
        )
        linking_service.db.add(entity)
        linking_service.db.commit()

        # Act - auto_create_types=False
        graph_nodes = await linking_service.link_entities_to_graph(
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            auto_create_types=False
        )

        # Assert - no nodes created (type doesn't exist)
        assert len(graph_nodes) == 0


# ============================================================================
# Test Class 3: Type Matching
# ============================================================================

class TestTypeMatching:
    """Tests for _discovered_type to entity type slug matching."""

    def test_discovered_type_to_slug_conversion(self, linking_service):
        """Test PascalCase to slug_case conversion."""
        assert linking_service._discovered_type_to_slug("PurchaseOrder") == "purchase_order"
        assert linking_service._discovered_type_to_slug("SecurityEvent") == "security_event"
        assert linking_service._discovered_type_to_slug("Invoice") == "invoice"
        assert linking_service._discovered_type_to_slug("Ticket") == "ticket"

    def test_discovered_type_to_slug_handles_multi_word(self, linking_service):
        """Test multi-word PascalCase conversion."""
        assert linking_service._discovered_type_to_slug("PurchaseOrderLineItem") == "purchase_order_line_item"
        assert linking_service._discovered_type_to_slug("SecurityEventDetector") == "security_event_detector"


# ============================================================================
# Test Class 4: Schema Inference for Single Entities
# ============================================================================

class TestSingleEntitySchemaInference:
    """Tests for schema inference from single entity (for novel types)."""

    def test_infer_schema_from_single_entity(self, linking_service):
        """Test inferring schema from a single discovered entity."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-single-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="Product",
            properties={
                "product_name": "Widget",
                "sku": "WGT-001",
                "price": 29.99,
                "in_stock": True
            },
            confidence_score=0.75,
            source_record_id="email-single-001",
            source_record_type="email"
        )

        # Act
        schema = linking_service._infer_schema_from_single_entity(entity)

        # Assert
        assert schema["type"] == "object"
        assert "product_name" in schema["properties"]
        assert schema["properties"]["product_name"]["type"] == "string"
        assert "price" in schema["properties"]
        assert schema["properties"]["price"]["type"] == "number"
        assert "in_stock" in schema["properties"]
        assert schema["properties"]["in_stock"]["type"] == "boolean"

    def test_infer_schema_value_from_value(self, linking_service):
        """Test _infer_schema_from_value helper method."""
        # Test various value types
        assert linking_service._infer_schema_from_value("string") == {"type": "string"}
        assert linking_service._infer_schema_from_value(42) == {"type": "integer"}
        assert linking_service._infer_schema_from_value(3.14) == {"type": "number"}
        assert linking_service._infer_schema_from_value(True) == {"type": "boolean"}
        assert linking_service._infer_schema_from_value(None) == {"type": "null"}
        assert linking_service._infer_schema_from_value([1, 2, 3]) == {"type": "array", "items": {"type": "string"}}
        assert linking_service._infer_schema_from_value({"key": "val"}) == {"type": "object"}


# ============================================================================
# Test Class 5: Linking Single Entity
# ============================================================================

class TestSingleEntityLinking:
    """Tests for linking individual discovered entities."""

    @pytest.mark.asyncio
    async def test_link_single_entity_to_existing_type(self, linking_service, sample_entity_type):
        """Test linking a single entity to an existing type."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-single-001",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="PurchaseOrder",
            properties={"po_number": "PO-SINGLE", "amount": 2500.0},
            confidence_score=0.90,
            source_record_id="email-single-001",
            source_record_type="email"
        )
        linking_service.db.add(entity)
        linking_service.db.commit()

        # Act
        graph_node = await linking_service.link_single_entity(
            entity_id="entity-single-001",
            entity_type_slug="purchase_order",
            create_type_if_missing=False
        )

        # Assert
        assert graph_node is not None
        assert graph_node.type == "purchase_order"
        assert graph_node.properties["po_number"] == "PO-SINGLE"

    @pytest.mark.asyncio
    async def test_link_single_entity_creates_novel_type(self, linking_service):
        """Test linking single entity creates novel type if enabled."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-single-002",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type="SupportTicket",  # Novel type
            properties={"ticket_number": "TKT-001", "severity": "high"},
            confidence_score=0.82,
            source_record_id="email-single-002",
            source_record_type="email"
        )
        linking_service.db.add(entity)
        linking_service.db.commit()

        # Act
        graph_node = await linking_service.link_single_entity(
            entity_id="entity-single-002",
            entity_type_slug="support_ticket",
            create_type_if_missing=True
        )

        # Assert
        assert graph_node is not None
        assert graph_node.type == "support_ticket"

        # Verify EntityTypeDefinition was created
        entity_type = linking_service.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.slug == "support_ticket"
        ).first()
        assert entity_type is not None
        assert entity_type.metadata_json.get("auto_created") is True

    @pytest.mark.asyncio
    async def test_link_single_entity_skips_if_type_missing(self, linking_service):
        """Test that linking fails gracefully if type missing and auto_create=False."""
        # Arrange
        entity = DiscoveredEntity(
            id="entity-single-003",
            tenant_id="tenant-001",
            workspace_id="workspace-001",
            _discovered_type=" novel type ",  # Novel type
            properties={"data": "value"},
            confidence_score=0.75,
            source_record_id="email-single-003",
            source_record_type="email"
        )
        linking_service.db.add(entity)
        linking_service.db.commit()

        # Act - type doesn't exist, auto_create=False
        graph_node = await linking_service.link_single_entity(
            entity_id="entity-single-003",
            entity_type_slug="novel_type",
            create_type_if_missing=False
        )

        # Assert - no graph node created
        assert graph_node is None
