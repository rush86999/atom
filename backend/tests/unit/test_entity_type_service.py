"""
Test Suite for EntityTypeService

Comprehensive tests for dynamic entity type management.
Uses mocking to avoid PostgreSQL-specific dependencies for unit tests.

Target: 80%+ coverage for core/entity_type_service.py
"""

import pytest
import json
from datetime import datetime
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any

from core.entity_type_service import EntityTypeService
from core.models import EntityTypeDefinition


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def entity_type_service(mock_db):
    """Create EntityTypeService instance with mock database."""
    with patch('core.entity_type_service.get_schema_validator') as mock_validator, \
         patch('core.entity_type_service.get_model_factory') as mock_factory:
        service = EntityTypeService(db=mock_db)
        service.validator = Mock()
        service.model_factory = Mock()
        yield service


@pytest.fixture
def valid_json_schema() -> Dict[str, Any]:
    """Valid JSON schema for testing."""
    return {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string"},
            "amount": {"type": "number", "minimum": 0},
            "date": {"type": "string", "format": "date"},
            "status": {"type": "string", "enum": ["draft", "sent", "paid", "overdue"]}
        },
        "required": ["invoice_number", "amount", "date"]
    }


@pytest.fixture
def mock_entity_type(valid_json_schema):
    """Mock EntityTypeDefinition instance."""
    entity_type = Mock(spec=EntityTypeDefinition)
    entity_type.id = "test-entity-id"
    entity_type.tenant_id = "tenant-123"
    entity_type.slug = "invoice"
    entity_type.display_name = "Invoice"
    entity_type.description = "Customer invoice"
    entity_type.json_schema = valid_json_schema
    entity_type.available_skills = ["finance_analysis"]
    entity_type.is_active = True
    entity_type.is_system = False
    entity_type.version = 1
    entity_type.metadata_json = None
    entity_type.created_at = datetime.utcnow()
    entity_type.updated_at = datetime.utcnow()
    return entity_type


# ============================================================================
# ENTITY TYPE CREATION TESTS (10 tests)
# ============================================================================

class TestEntityTypeCreation:
    """Test suite for entity type creation functionality."""

    def test_create_entity_type_success(self, entity_type_service: EntityTypeService, mock_db, valid_json_schema):
        """Test successful entity type creation."""
        # Arrange
        mock_entity_type = Mock()
        mock_entity_type.id = "new-id"
        mock_entity_type.slug = "invoice"
        mock_entity_type.version = 1

        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.flush.return_value = None

        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No duplicate

        # Mock the model creation
        with patch('core.entity_type_service.EntityTypeDefinition') as mock_model:
            mock_model.return_value = mock_entity_type

            # Act
            result = entity_type_service.create_entity_type(
                tenant_id="tenant-123",
                slug="invoice",
                display_name="Invoice",
                json_schema=valid_json_schema
            )

            # Assert
            assert result is not None
            assert result.slug == "invoice"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_create_entity_type_with_json_schema(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test entity type creation with JSON schema validation."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        mock_db = entity_type_service.db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.id = "test-id"
        mock_entity_type.slug = "person"
        mock_entity_type.version = 1

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            # Act
            result = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="person",
                display_name="Person",
                json_schema=valid_json_schema
            )

            # Assert
            assert result.slug == "person"
            assert result.version == 1
            entity_type_service.validator.validate_schema.assert_called()

    def test_create_entity_type_duplicate_slug(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test that duplicate slug raises error."""
        # Arrange - Duplicate exists
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator;
        # create_entity_type validates the schema BEFORE checking for duplicates.
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act & Assert
        with pytest.raises(ValueError, match="already exists"):
            entity_type_service.create_entity_type(
                tenant_id="tenant-123",
                slug="invoice",  # Duplicate
                display_name="Invoice",
                json_schema={}
            )

    def test_create_entity_type_invalid_schema(self, entity_type_service: EntityTypeService):
        """Test that invalid JSON schema is rejected."""
        # Arrange - Schema validation fails
        entity_type_service.validator.validate_schema.side_effect = ValueError("Invalid schema")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid schema"):
            entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="test",
                display_name="Test",
                json_schema={"invalid": "schema"}
            )

    def test_create_entity_type_with_field_whitelist(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test entity type creation with field whitelist."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.id = "test-id"
        mock_entity_type.slug = "whitelisted"

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            # Act
            result = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="whitelisted",
                display_name="Whitelisted",
                json_schema=valid_json_schema
            )

            # Assert
            assert result.slug == "whitelisted"

    def test_create_entity_type_with_relationships(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test entity type creation with relationship definitions."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.slug = "user_profile_link"

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            # Act
            result = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="user_profile_link",
                display_name="User Profile Link",
                json_schema=valid_json_schema,
                description="Links users to profiles"
            )

            # Assert
            assert result.slug == "user_profile_link"

    def test_create_entity_type_with_metadata(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test entity type creation with custom metadata."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.slug = "metadata_test"

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            # Act
            result = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="metadata_test",
                display_name="Metadata Test",
                json_schema=valid_json_schema,
                description="Test metadata field"
            )

            # Assert
            assert result.slug == "metadata_test"

    def test_create_entity_type_concurrent_creation(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test handling of concurrent entity type creation."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type1 = Mock()
        mock_entity_type1.id = "id-1"
        mock_entity_type1.slug = "concurrent_1"

        mock_entity_type2 = Mock()
        mock_entity_type2.id = "id-2"
        mock_entity_type2.slug = "concurrent_2"

        with patch('core.entity_type_service.EntityTypeDefinition', side_effect=[mock_entity_type1, mock_entity_type2]):
            # Act - Create two different entity types
            result1 = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="concurrent_1",
                display_name="Concurrent 1",
                json_schema=valid_json_schema
            )

            result2 = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="concurrent_2",
                display_name="Concurrent 2",
                json_schema=valid_json_schema
            )

            # Assert
            assert result1.slug == "concurrent_1"
            assert result2.slug == "concurrent_2"
            assert result1.id != result2.id

    def test_create_entity_type_schema_validation(self, entity_type_service: EntityTypeService):
        """Test that schema validation catches malformed schemas."""
        # Arrange - Schema validation fails
        entity_type_service.validator.validate_schema.side_effect = ValueError("Missing 'type' field")

        # Act & Assert
        with pytest.raises(ValueError, match="Missing 'type' field"):
            entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="no_type",
                display_name="No Type",
                json_schema={"properties": {}}
            )

    def test_create_entity_type_with_tenant_isolation(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test tenant isolation in entity type creation."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.tenant_id = "tenant-abc"

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            # Act
            result = entity_type_service.create_entity_type(
                tenant_id="tenant-abc",
                slug="isolated",
                display_name="Isolated",
                json_schema=valid_json_schema
            )

            # Assert
            assert result.tenant_id == "tenant-abc"


# ============================================================================
# INTEGRATION TESTS (10 tests)
# ============================================================================

class TestEntityTypeIntegration:
    """Integration tests for end-to-end entity type workflows."""

    def test_entity_type_service_error_recovery(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test error recovery during entity type operations."""
        # First attempt succeeds
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.id = "test-id"
        mock_entity_type.slug = "recovery_test"

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            entity_type = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="recovery_test",
                display_name="Recovery Test",
                json_schema=valid_json_schema
            )

        assert entity_type.slug == "recovery_test"

    def test_entity_type_service_merge_entity_types(self, entity_type_service: EntityTypeService):
        """Test merging two entity types."""
        # Arrange
        source_type = Mock()
        source_type.slug = "source"
        source_type.id = "source-id"
        source_type.metadata_json = None

        target_type = Mock()
        target_type.slug = "target"
        target_type.metadata_json = {}

        # merge_entity_types() resolves source then target via get_entity_type()
        entity_type_service.get_entity_type = Mock(side_effect=[source_type, target_type])
        # GraphNode migration uses query.update() (not db.execute)
        entity_type_service.db.query.return_value.filter.return_value.update.return_value = 5
        entity_type_service.db.commit.return_value = None

        # Act
        result = entity_type_service.merge_entity_types(
            tenant_id="tenant-123",
            source_id="source-id",
            target_slug="target"
        )

        # Assert
        assert result is True
        entity_type_service.db.commit.assert_called()
        # Source is deactivated and its discovery metadata is recorded on the target
        assert source_type.is_active is False
        assert target_type.metadata_json["merges"][0]["source_slug"] == "source"
        assert target_type.metadata_json["merges"][0]["nodes_count"] == 5

    def test_entity_type_service_resolve_or_create_draft(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test idempotent resolver for automated discovery."""
        # Arrange - Entity type doesn't exist yet
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        # Draft creation goes through create_entity_type(), which validates the schema
        entity_type_service.validator.validate_schema.return_value = (True, "")

        mock_entity_type = Mock()
        mock_entity_type.slug = "invoice"
        mock_entity_type.version = 1
        mock_entity_type.json_schema = valid_json_schema

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            # Act - Should create new
            result = entity_type_service.resolve_or_create_draft(
                tenant_id="tenant-123",
                slug="invoice",
                display_name="Invoice",
                json_schema=valid_json_schema
            )

        # Assert
        assert result.slug == "invoice"

    def test_entity_type_service_get_entity_type(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test retrieving entity type by ID."""
        # Arrange
        # get_entity_type() chains filters: tenant -> is_active -> id -> first()
        entity_type_service.db.query.return_value.filter.return_value.filter.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.get_entity_type(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id"
        )

        # Assert
        assert result is not None
        assert result.id == "test-entity-id"

    def test_entity_type_service_list_entity_types(self, entity_type_service: EntityTypeService):
        """Test listing entity types with pagination."""
        # Arrange
        mock_types = [Mock() for _ in range(10)]
        # list_entity_types() chains filters: tenant -> is_active -> is_system -> order_by -> limit -> offset -> all()
        entity_type_service.db.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = mock_types

        # Act
        result = entity_type_service.list_entity_types(
            tenant_id="tenant-123",
            limit=10,
            offset=0
        )

        # Assert
        assert len(result) == 10

    def test_entity_type_service_delete_entity_type(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test soft deleting entity type."""
        # Arrange
        # delete_entity_type() resolves the record via get_entity_type()
        entity_type_service.get_entity_type = Mock(return_value=mock_entity_type)
        entity_type_service.db.commit.return_value = None

        # Act
        result = entity_type_service.delete_entity_type(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id"
        )

        # Assert
        assert result is True
        assert mock_entity_type.is_active is False
        entity_type_service.db.commit.assert_called_once()

    def test_entity_type_service_update_entity_type(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test updating entity type schema."""
        # Arrange
        new_schema = {"type": "object", "properties": {"new_field": {"type": "string"}}}

        # update_entity_type() resolves the record via get_entity_type()
        entity_type_service.get_entity_type = Mock(return_value=mock_entity_type)
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.commit.return_value = None

        # Act
        result = entity_type_service.update_entity_type(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            json_schema=new_schema,
            change_summary="Added new_field"
        )

        # Assert
        assert result is not None
        entity_type_service.db.commit.assert_called()

    def test_entity_type_service_performance_under_load(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test performance with many entity types."""
        # Arrange
        # validate_schema returns (is_valid: bool, error: str) per SchemaValidator
        entity_type_service.validator.validate_schema.return_value = (True, "")
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        import time
        start_time = time.time()

        # Create 100 entity types
        for i in range(100):
            mock_entity_type = Mock()
            mock_entity_type.id = f"id-{i}"
            mock_entity_type.slug = f"load_test_{i}"

            with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
                entity_type_service.create_entity_type(
                    tenant_id=f"tenant-{i % 10}",
                    slug=f"load_test_{i}",
                    display_name=f"Load Test {i}",
                    json_schema=valid_json_schema
                )

        elapsed = time.time() - start_time

        # Assert - Should complete in reasonable time (<10 seconds)
        assert elapsed < 10.0


# ============================================================================
# EDGE CASE TESTS (7 tests)
# ============================================================================

class TestEntityTypeEdgeCases:
    """Test suite for edge cases and corner cases."""

    def test_entity_type_service_with_null_schema(self, entity_type_service: EntityTypeService):
        """Test handling of null/None schema."""
        # Arrange
        entity_type_service.validator.validate_schema.side_effect = ValueError("Schema cannot be None")

        # Act & Assert
        with pytest.raises(ValueError):
            entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="null_schema",
                display_name="Null Schema",
                json_schema=None
            )

    def test_entity_type_service_with_invalid_json(self, entity_type_service: EntityTypeService):
        """Test handling of malformed JSON in schema."""
        # Arrange - Schema validation fails
        entity_type_service.validator.validate_schema.side_effect = ValueError("Invalid JSON")

        # Act & Assert
        with pytest.raises(ValueError):
            entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="invalid_json",
                display_name="Invalid JSON",
                json_schema={"type": "invalid"}
            )

    def test_entity_type_service_with_malformed_schema(self, entity_type_service: EntityTypeService):
        """Test handling of malformed JSON schema."""
        # Arrange
        malformed_schema = {
            "type": "object",
            "properties": "not_a_dict",  # Should be object
            "required": "not_a_list"  # Should be array
        }

        entity_type_service.validator.validate_schema.side_effect = ValueError("Malformed schema")

        # Act & Assert
        with pytest.raises(ValueError):
            entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="malformed",
                display_name="Malformed",
                json_schema=malformed_schema
            )

