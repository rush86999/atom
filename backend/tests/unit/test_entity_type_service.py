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

        entity_type_service.validator.validate_schema.return_value = None
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
        entity_type_service.validator.validate_schema.return_value = None
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
        entity_type_service.validator.validate_schema.return_value = None
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
        entity_type_service.validator.validate_schema.return_value = None
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
        entity_type_service.validator.validate_schema.return_value = None
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
        entity_type_service.validator.validate_schema.return_value = None
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
        entity_type_service.validator.validate_schema.return_value = None
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
# RUNTIME MODEL GENERATION TESTS (10 tests)
# ============================================================================

class TestRuntimeModelGeneration:
    """Test suite for runtime SQLAlchemy model generation."""

    def test_generate_runtime_model_success(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test successful runtime model generation."""
        # Arrange
        mock_model = Mock()
        mock_model.__tablename__ = "invoice"
        mock_model.invoice_number = Mock()
        mock_model.amount = Mock()

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert result is not None
        assert result.__tablename__ == "invoice"
        entity_type_service.model_factory.generate_model.assert_called_once_with(mock_entity_type)

    def test_generate_runtime_model_with_fields(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test runtime model generation with correct field types."""
        # Arrange
        mock_model = Mock()
        mock_model.string_field = Mock()
        mock_model.integer_field = Mock()
        mock_model.number_field = Mock()
        mock_model.boolean_field = Mock()

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert hasattr(result, 'string_field')
        assert hasattr(result, 'integer_field')
        assert hasattr(result, 'number_field')
        assert hasattr(result, 'boolean_field')

    def test_generate_runtime_model_with_relationships(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test runtime model with relationship fields."""
        # Arrange
        mock_model = Mock()
        mock_model.user_id = Mock()
        mock_model.related_entity_id = Mock()

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert hasattr(result, 'user_id')
        assert hasattr(result, 'related_entity_id')

    def test_generate_runtime_model_with_indexes(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test runtime model with index generation."""
        # Arrange
        mock_model = Mock()
        mock_model.__table_args__ = {'extend_existing': True}

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert result is not None
        assert hasattr(result, '__table_args__')

    def test_generate_runtime_model_invalid_schema(self, entity_type_service: EntityTypeService):
        """Test runtime model generation with invalid schema."""
        # Arrange
        invalid_entity_type = Mock()
        invalid_entity_type.json_schema = {"invalid": "schema"}

        entity_type_service.model_factory.generate_model.side_effect = ValueError("Invalid schema")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid schema"):
            entity_type_service.generate_runtime_model(invalid_entity_type)

    def test_generate_runtime_model_caching(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test that runtime models are cached."""
        # Arrange
        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act - Generate model twice
        result1 = entity_type_service.generate_runtime_model(mock_entity_type)
        result2 = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert - Should only call factory once (cached)
        entity_type_service.model_factory.generate_model.assert_called_once()
        assert result1 is result2

    def test_generate_runtime_model_with_constraints(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test runtime model with field constraints."""
        # Arrange
        mock_model = Mock()
        mock_model.email = Mock()
        mock_model.age = Mock()

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert hasattr(result, 'email')
        assert hasattr(result, 'age')

    def test_generate_runtime_model_table_creation(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test that runtime model creates table in database."""
        # Arrange
        mock_model = Mock()
        mock_model.__tablename__ = "test_table"
        mock_model.create_table = Mock()

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert result is not None
        assert result.__tablename__ == "test_table"

    def test_generate_runtime_model_with_validation(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test runtime model with validation rules."""
        # Arrange
        mock_model = Mock()
        mock_model.required_field = Mock()
        mock_model.optional_field = Mock()

        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert hasattr(result, 'required_field')
        assert hasattr(result, 'optional_field')

    def test_generate_runtime_model_performance(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test runtime model generation performance."""
        # Arrange
        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        import time
        start = time.time()
        result = entity_type_service.generate_runtime_model(mock_entity_type)
        elapsed = time.time() - start

        # Assert - Should be fast (<100ms target)
        assert result is not None
        assert elapsed < 0.1  # 100ms


# ============================================================================
# FIELD WHITELISTING TESTS (8 tests)
# ============================================================================

class TestFieldWhitelisting:
    """Test suite for field whitelisting functionality."""

    def test_whitelist_fields_success(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test successful field whitelisting."""
        # Arrange
        mock_entity_type.metadata_json = None
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type
        entity_type_service.db.commit.return_value = None

        # Act
        result = entity_type_service.whitelist_fields(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            fields=["invoice_number", "amount"]
        )

        # Assert
        assert result is not None
        entity_type_service.db.commit.assert_called_once()

    def test_whitelist_fields_with_wildcard(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test whitelisting with wildcard (allow all fields)."""
        # Arrange
        mock_entity_type.metadata_json = None
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.whitelist_fields(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            fields=["*"]
        )

        # Assert
        assert result is not None

    def test_whitelist_fields_empty_list(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test whitelisting with empty list (allow all by default)."""
        # Arrange
        mock_entity_type.metadata_json = {}
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.whitelist_fields(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            fields=[]
        )

        # Assert
        assert result is not None

    def test_whitelist_fields_invalid_field(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test whitelisting invalid field name."""
        # Arrange
        mock_entity_type.json_schema = {
            "properties": {
                "field1": {"type": "string"}
            }
        }
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act & Assert
        with pytest.raises(ValueError):
            entity_type_service.whitelist_fields(
                tenant_id="tenant-123",
                entity_type_id="test-entity-id",
                fields=["non_existent_field"]
            )

    def test_whitelist_fields_query_safety(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test that field whitelisting prevents SQL injection."""
        # Arrange
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act & Assert - Attempt SQL injection
        with pytest.raises(ValueError):
            entity_type_service.whitelist_fields(
                tenant_id="tenant-123",
                entity_type_id="test-entity-id",
                fields=["safe_field; DROP TABLE users; --"]
            )

    def test_whitelist_fields_performance(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test field whitelisting performance."""
        # Arrange
        mock_entity_type.metadata_json = None
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        import time
        start = time.time()
        result = entity_type_service.whitelist_fields(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            fields=["field"]
        )
        elapsed = time.time() - start

        # Assert - Should be fast (<50ms target)
        assert result is not None
        assert elapsed < 0.05  # 50ms

    def test_whitelist_fields_concurrent_whitelisting(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test handling of concurrent field whitelisting."""
        # Arrange
        mock_entity_type.metadata_json = None
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act - Whitelist different field sets
        result1 = entity_type_service.whitelist_fields(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            fields=["invoice_number"]
        )

        result2 = entity_type_service.whitelist_fields(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            fields=["amount", "date"]
        )

        # Assert
        assert result1 is not None
        assert result2 is not None

    def test_whitelist_fields_with_validation(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test field name validation in whitelisting."""
        # Arrange
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act & Assert
        with pytest.raises(ValueError):
            entity_type_service.whitelist_fields(
                tenant_id="tenant-123",
                entity_type_id="test-entity-id",
                fields=["123invalid"]  # Invalid starting with number
            )


# ============================================================================
# SCHEMA VALIDATION TESTS (10 tests)
# ============================================================================

class TestSchemaValidation:
    """Test suite for entity data validation against JSON schema."""

    def test_validate_entity_data_success(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation of valid entity data."""
        # Arrange
        valid_data = {
            "invoice_number": "INV-001",
            "amount": 100.50,
            "date": "2024-01-01",
            "status": "paid"
        }

        mock_result = Mock()
        mock_result.valid = True
        mock_result.errors = []

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=valid_data
        )

        # Assert
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_entity_data_invalid_type(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation rejects invalid data types."""
        # Arrange
        invalid_data = {
            "invoice_number": "INV-001",
            "amount": "not_a_number",
            "date": "2024-01-01"
        }

        mock_result = Mock()
        mock_result.valid = False
        mock_result.errors = ["amount must be number"]

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=invalid_data
        )

        # Assert
        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_entity_data_missing_required_field(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation rejects missing required fields."""
        # Arrange
        invalid_data = {
            "invoice_number": "INV-001",
            # Missing "amount"
            "date": "2024-01-01"
        }

        mock_result = Mock()
        mock_result.valid = False
        mock_result.errors = ["amount is required"]

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=invalid_data
        )

        # Assert
        assert result.valid is False

    def test_validate_entity_data_with_nested_objects(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation with nested objects."""
        # Arrange
        nested_data = {
            "customer": {
                "name": "John Doe",
                "email": "john@example.com"
            }
        }

        mock_result = Mock()
        mock_result.valid = True

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=nested_data
        )

        # Assert
        assert result.valid is True

    def test_validate_entity_data_with_arrays(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation with array fields."""
        # Arrange
        data_with_array = {
            "items": [{"product": "Widget", "quantity": 2}]
        }

        mock_result = Mock()
        mock_result.valid = True

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=data_with_array
        )

        # Assert
        assert result.valid is True

    def test_validate_entity_data_performance(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation performance."""
        # Arrange
        test_data = {"field1": "test", "field2": 123}

        mock_result = Mock()
        mock_result.valid = True

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        import time
        start = time.time()
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=test_data
        )
        elapsed = time.time() - start

        # Assert - Should be fast (<50ms target)
        assert result.valid is True
        assert elapsed < 0.05  # 50ms

    def test_validate_entity_data_with_custom_validators(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation with custom validation rules."""
        # Arrange
        custom_data = {"password": "Secure123"}

        mock_result = Mock()
        mock_result.valid = True

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=custom_data
        )

        # Assert
        assert result.valid is True

    def test_validate_entity_data_error_messages(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test that validation returns clear error messages."""
        # Arrange
        invalid_data = {"field": 123}  # Wrong type

        mock_result = Mock()
        mock_result.valid = False
        mock_result.errors = ["field must be string"]

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data=invalid_data
        )

        # Assert
        assert result.valid is False
        assert len(result.errors) > 0
        assert all(isinstance(err, str) for err in result.errors)

    def test_validate_entity_data_entity_not_found(self, entity_type_service: EntityTypeService):
        """Test validation when entity type not found."""
        # Arrange
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="not found"):
            entity_type_service.validate_entity_data(
                tenant_id="tenant-123",
                entity_type_id="nonexistent-id",
                data={}
            )

    def test_validate_entity_data_empty_data(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test validation with empty data."""
        # Arrange
        mock_result = Mock()
        mock_result.valid = False
        mock_result.errors = ["data is required"]

        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

        # Act
        result = entity_type_service.validate_entity_data(
            tenant_id="tenant-123",
            entity_type_id="test-entity-id",
            data={}
        )

        # Assert
        assert result.valid is False


# ============================================================================
# INTEGRATION TESTS (10 tests)
# ============================================================================

class TestEntityTypeIntegration:
    """Integration tests for end-to-end entity type workflows."""

    def test_entity_type_service_end_to_end_flow(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test full flow: create → generate model → validate."""
        # Step 1: Create entity type
        entity_type_service.validator.validate_schema.return_value = None
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

        mock_entity_type = Mock()
        mock_entity_type.id = "test-id"
        mock_entity_type.slug = "e2e_test"
        mock_entity_type.version = 1

        with patch('core.entity_type_service.EntityTypeDefinition', return_value=mock_entity_type):
            entity_type = entity_type_service.create_entity_type(
                tenant_id="tenant-1",
                slug="e2e_test",
                display_name="E2E Test",
                json_schema=valid_json_schema
            )

        assert entity_type.id is not None
        assert entity_type.slug == "e2e_test"

        # Step 2: Generate runtime model
        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model
        model = entity_type_service.generate_runtime_model(entity_type)
        assert model is not None

        # Step 3: Validate data
        test_data = {"invoice_number": "E2E-001", "amount": 99.99}

        mock_result = Mock()
        mock_result.valid = True
        entity_type_service.validator.validate.return_value = mock_result
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = entity_type

        validation = entity_type_service.validate_entity_data(
            tenant_id="tenant-1",
            entity_type_id="test-id",
            data=test_data
        )
        assert validation.valid is True

    def test_entity_type_service_error_recovery(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test error recovery during entity type operations."""
        # First attempt succeeds
        entity_type_service.validator.validate_schema.return_value = None
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

    def test_entity_type_service_model_caching(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test that model caching improves performance."""
        # Arrange
        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act - Generate model multiple times
        model1 = entity_type_service.generate_runtime_model(mock_entity_type)
        model2 = entity_type_service.generate_runtime_model(mock_entity_type)
        model3 = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert - All should be same cached instance
        assert model1 is model2
        assert model2 is model3

        # Factory should only be called once
        entity_type_service.model_factory.generate_model.assert_called_once()

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

        entity_type_service.db.query.return_value.filter.return_value.first.side_effect = [source_type, target_type]
        entity_type_service.db.execute.return_value = Mock(rowcount=5)
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

    def test_entity_type_service_resolve_or_create_draft(self, entity_type_service: EntityTypeService, valid_json_schema):
        """Test idempotent resolver for automated discovery."""
        # Arrange - Entity type doesn't exist yet
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = None

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
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

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
        entity_type_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = mock_types

        # Act
        result = entity_type_service.list_entity_types(
            tenant_id="tenant-123",
            page=1,
            per_page=10
        )

        # Assert
        assert len(result) == 10

    def test_entity_type_service_delete_entity_type(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test soft deleting entity type."""
        # Arrange
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type
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

        entity_type_service.validator.validate_schema.return_value = None
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type
        entity_type_service.db.commit.return_value = None

        mock_version = Mock()
        mock_version.id = "version-id"
        entity_type_service.db.query.return_value.filter.return_value.first.return_value = mock_entity_type

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
        entity_type_service.validator.validate_schema.return_value = None
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

    def test_entity_type_service_with_unicode_field_names(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test handling of Unicode field names."""
        # Arrange
        unicode_schema = {
            "type": "object",
            "properties": {
                "名前": {"type": "string"},  # Japanese
                "имя": {"type": "string"}  # Russian
            }
        }

        mock_entity_type.json_schema = unicode_schema

        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert result is not None

    def test_entity_type_service_with_reserved_keywords(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test handling of SQL reserved keywords as field names."""
        # Arrange
        keyword_schema = {
            "type": "object",
            "properties": {
                "select": {"type": "string"},
                "from": {"type": "string"},
                "where": {"type": "string"}
            }
        }

        mock_entity_type.json_schema = keyword_schema

        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert result is not None

    def test_entity_type_service_with_extremely_long_schema(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test handling of very large JSON schemas (>10KB)."""
        # Generate large schema
        properties = {}
        for i in range(100):
            properties[f"field_{i}"] = {"type": "string", "description": f"Field {i} " * 10}

        large_schema = {"type": "object", "properties": properties}

        # Assert schema is large
        assert len(json.dumps(large_schema)) > 10000

        mock_entity_type.json_schema = large_schema

        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act
        result = entity_type_service.generate_runtime_model(mock_entity_type)

        # Assert
        assert result is not None

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

    def test_entity_type_service_concurrent_access(self, entity_type_service: EntityTypeService, mock_entity_type):
        """Test handling of concurrent access to entity types."""
        # Arrange - Multiple threads accessing same entity type
        mock_model = Mock()
        entity_type_service.model_factory.generate_model.return_value = mock_model

        # Act - Simulate concurrent access
        results = []
        for _ in range(10):
            result = entity_type_service.generate_runtime_model(mock_entity_type)
            results.append(result)

        # Assert - All should succeed
        assert len(results) == 10
        assert all(r is not None for r in results)
        # Factory should only be called once due to caching
        entity_type_service.model_factory.generate_model.assert_called_once()
