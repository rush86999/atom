"""
Baseline unit tests for IntegrationDataMapper class

Tests cover:
- Initialization and configuration
- Schema registration and management
- Field mapping creation
- Data transformation logic
- Field type transformations
- Validation logic
- Import/export functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timezone
from typing import Dict, Any
from dataclasses import asdict

from core.integration_data_mapper import (
    IntegrationDataMapper,
    DataTransformer,
    FieldMapping,
    IntegrationSchema,
    BulkOperation,
    FieldType,
    TransformationType,
    get_data_mapper,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def data_mapper():
    """Create IntegrationDataMapper instance"""
    return IntegrationDataMapper()


@pytest.fixture
def sample_field_mapping():
    """Sample field mapping for testing"""
    return FieldMapping(
        source_field="first_name",
        target_field="FirstName",
        source_type=FieldType.STRING,
        target_type=FieldType.STRING,
        transformation=TransformationType.DIRECT_COPY,
        required=True,
        default_value=None
    )


@pytest.fixture
def sample_asana_schema():
    """Sample Asana task schema"""
    return IntegrationSchema(
        integration_id="asana_task",
        integration_name="Asana Task",
        version="1.0",
        fields={
            "name": {"type": "string", "required": True},
            "description": {"type": "string", "required": False}
        },
        supported_operations=["create", "read", "update"],
        bulk_operations_supported=True,
        max_bulk_size=50
    )


# =============================================================================
# TEST CLASS: TestDataMapperInit
# Tests for initialization and configuration
# =============================================================================

class TestDataMapperInit:
    """Test IntegrationDataMapper initialization"""

    def test_initialization(self, data_mapper):
        """Test data mapper initialization"""
        assert data_mapper.transformer is not None
        assert isinstance(data_mapper.transformer, DataTransformer)
        assert isinstance(data_mapper.schemas, dict)
        assert isinstance(data_mapper.mappings, dict)

    def test_default_schemas_initialized(self, data_mapper):
        """Test that default schemas are initialized"""
        assert "asana_task" in data_mapper.schemas
        assert "jira_issue" in data_mapper.schemas
        assert "salesforce_lead" in data_mapper.schemas

    def test_asana_schema_structure(self, data_mapper):
        """Test Asana schema structure"""
        schema = data_mapper.schemas["asana_task"]

        assert schema.integration_id == "asana_task"
        assert schema.integration_name == "Asana Task"
        assert len(schema.fields) > 0
        assert "name" in schema.fields
        assert schema.bulk_operations_supported is True
        assert schema.max_bulk_size == 50

    def test_jira_schema_structure(self, data_mapper):
        """Test Jira schema structure"""
        schema = data_mapper.schemas["jira_issue"]

        assert schema.integration_id == "jira_issue"
        assert schema.integration_name == "Jira Issue"
        assert "summary" in schema.fields
        assert "issue_type" in schema.fields
        assert schema.max_bulk_size == 100

    def test_salesforce_schema_structure(self, data_mapper):
        """Test Salesforce schema structure"""
        schema = data_mapper.schemas["salesforce_lead"]

        assert schema.integration_id == "salesforce_lead"
        assert schema.integration_name == "Salesforce Lead"
        assert "FirstName" in schema.fields
        assert "Email" in schema.fields
        assert schema.max_bulk_size == 200


# =============================================================================
# TEST CLASS: TestSchemaManagement
# Tests for schema registration and management
# =============================================================================

class TestSchemaManagement:
    """Test schema registration and management"""

    def test_register_new_schema(self, data_mapper, sample_asana_schema):
        """Test registering a new schema"""
        custom_schema = IntegrationSchema(
            integration_id="custom_integration",
            integration_name="Custom",
            version="1.0",
            fields={"field1": {"type": "string", "required": True}},
            supported_operations=["create"],
            bulk_operations_supported=False
        )

        data_mapper.register_schema(custom_schema)

        assert "custom_integration" in data_mapper.schemas
        assert data_mapper.schemas["custom_integration"] == custom_schema

    def test_list_schemas(self, data_mapper):
        """Test listing all registered schemas"""
        schemas = data_mapper.list_schemas()

        assert isinstance(schemas, list)
        assert "asana_task" in schemas
        assert "jira_issue" in schemas
        assert "salesforce_lead" in schemas

    def test_get_schema_info_existing(self, data_mapper):
        """Test getting info for existing schema"""
        schema = data_mapper.get_schema_info("asana_task")

        assert schema is not None
        assert schema.integration_id == "asana_task"

    def test_get_schema_info_nonexistent(self, data_mapper):
        """Test getting info for nonexistent schema"""
        schema = data_mapper.get_schema_info("nonexistent")

        assert schema is None


# =============================================================================
# TEST CLASS: TestFieldMapping
# Tests for field mapping creation
# =============================================================================

class TestFieldMapping:
    """Test field mapping creation and validation"""

    def test_create_mapping_valid(self, data_mapper):
        """Test creating valid field mapping"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="summary",  # jira_issue has 'summary' not 'name'
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        data_mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        assert "test_mapping" in data_mapper.mappings

    def test_create_mapping_invalid_source_schema(self, data_mapper):
        """Test creating mapping with invalid source schema"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        with pytest.raises(ValueError, match="Source schema"):
            data_mapper.create_mapping(
                mapping_id="test_mapping",
                source_schema="invalid_schema",
                target_schema="asana_task",
                field_mappings=field_mappings
            )

    def test_create_mapping_invalid_target_schema(self, data_mapper):
        """Test creating mapping with invalid target schema"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        with pytest.raises(ValueError, match="Target schema"):
            data_mapper.create_mapping(
                mapping_id="test_mapping",
                source_schema="asana_task",
                target_schema="invalid_schema",
                field_mappings=field_mappings
            )

    def test_create_mapping_invalid_target_field(self, data_mapper):
        """Test creating mapping with invalid target field"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="invalid_field",  # Not in schema
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        with pytest.raises(ValueError, match="Target field"):
            data_mapper.create_mapping(
                mapping_id="test_mapping",
                source_schema="asana_task",
                target_schema="asana_task",
                field_mappings=field_mappings
            )

    def test_list_mappings(self, data_mapper):
        """Test listing all mappings"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        data_mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="asana_task",
            field_mappings=field_mappings
        )

        mappings = data_mapper.list_mappings()

        assert isinstance(mappings, list)
        assert "test_mapping" in mappings


# =============================================================================
# TEST CLASS: TestDataTransformation
# Tests for data transformation logic
# =============================================================================

class TestDataTransformation:
    """Test data transformation methods"""

    def test_transform_single_record(self, data_mapper):
        """Test transforming a single data record"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        data_mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="asana_task",
            field_mappings=field_mappings
        )

        source_data = {"name": "Test Task"}
        result = data_mapper.transform_data(source_data, "test_mapping")

        assert result["name"] == "Test Task"

    def test_transform_bulk_records(self, data_mapper):
        """Test transforming multiple records"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        data_mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="asana_task",
            field_mappings=field_mappings
        )

        source_data = [
            {"name": "Task 1"},
            {"name": "Task 2"},
            {"name": "Task 3"}
        ]
        result = data_mapper.transform_data(source_data, "test_mapping")

        assert len(result) == 3
        assert result[0]["name"] == "Task 1"
        assert result[1]["name"] == "Task 2"
        assert result[2]["name"] == "Task 3"

    def test_transform_nonexistent_mapping(self, data_mapper):
        """Test transforming with nonexistent mapping"""
        with pytest.raises(ValueError, match="Mapping .* not found"):
            data_mapper.transform_data({"name": "Test"}, "nonexistent_mapping")


# =============================================================================
# TEST CLASS: TestFieldTransformations
# Tests for field-level transformations
# =============================================================================

class TestFieldTransformations:
    """Test field transformation types"""

    def test_direct_copy_transformation(self, data_mapper):
        """Test direct copy transformation"""
        result = data_mapper.transformer.transform_field(
            value="test_value",
            mapping=FieldMapping(
                source_field="field1",
                target_field="field2",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            ),
            source_data={"field1": "test_value"}
        )

        assert result == "test_value"

    def test_value_mapping_transformation(self, data_mapper):
        """Test value mapping transformation"""
        result = data_mapper.transformer.transform_field(
            value="open",
            mapping=FieldMapping(
                source_field="status",
                target_field="status",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.VALUE_MAPPING,
                transformation_config={
                    "value_map": {
                        "open": "In Progress",
                        "closed": "Completed"
                    }
                },
                required=True
            ),
            source_data={"status": "open"}
        )

        assert result == "In Progress"

    def test_format_conversion_lowercase(self, data_mapper):
        """Test format conversion to lowercase"""
        result = data_mapper.transformer.transform_field(
            value="TEST VALUE",
            mapping=FieldMapping(
                source_field="text",
                target_field="text_lower",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.FORMAT_CONVERSION,
                transformation_config={"format_type": "lowercase"},
                required=True
            ),
            source_data={"text": "TEST VALUE"}
        )

        assert result == "test value"

    def test_format_conversion_uppercase(self, data_mapper):
        """Test format conversion to uppercase"""
        result = data_mapper.transformer.transform_field(
            value="test value",
            mapping=FieldMapping(
                source_field="text",
                target_field="text_upper",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.FORMAT_CONVERSION,
                transformation_config={"format_type": "uppercase"},
                required=True
            ),
            source_data={"text": "test value"}
        )

        assert result == "TEST VALUE"

    def test_calculation_multiply(self, data_mapper):
        """Test calculation transformation - multiply"""
        result = data_mapper.transformer.transform_field(
            value=100,
            mapping=FieldMapping(
                source_field="price",
                target_field="total",
                source_type=FieldType.FLOAT,
                target_type=FieldType.FLOAT,
                transformation=TransformationType.CALCULATION,
                transformation_config={
                    "calculation_type": "multiply",
                    "multiplier": 1.5
                },
                required=True
            ),
            source_data={"price": 100}
        )

        assert result == 150.0

    def test_calculation_percentage(self, data_mapper):
        """Test calculation transformation - percentage"""
        result = data_mapper.transformer.transform_field(
            value=200,
            mapping=FieldMapping(
                source_field="amount",
                target_field="discount",
                source_type=FieldType.FLOAT,
                target_type=FieldType.FLOAT,
                transformation=TransformationType.CALCULATION,
                transformation_config={
                    "calculation_type": "percentage",
                    "percentage": 20
                },
                required=True
            ),
            source_data={"amount": 200}
        )

        assert result == 40.0

    def test_concatenation_transformation(self, data_mapper):
        """Test concatenation transformation"""
        result = data_mapper.transformer.transform_field(
            value="John",
            mapping=FieldMapping(
                source_field="first_name",
                target_field="full_name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.CONCATENATION,
                transformation_config={
                    "fields": ["self", "last_name"],
                    "separator": " "
                },
                required=True
            ),
            source_data={"first_name": "John", "last_name": "Doe"}
        )

        assert result == "John Doe"

    def test_conditional_transformation(self, data_mapper):
        """Test conditional transformation"""
        result = data_mapper.transformer.transform_field(
            value="premium",
            mapping=FieldMapping(
                source_field="tier",
                target_field="discount",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.CONDITIONAL,
                transformation_config={
                    "conditions": [
                        {
                            "type": "equals",
                            "field": "self",
                            "operator": "equals",  # Added required operator
                            "expected": "premium",
                            "result": "20%"
                        },
                        {
                            "type": "equals",
                            "field": "self",
                            "operator": "equals",
                            "expected": "standard",
                            "result": "10%"
                        }
                    ],
                    "default": "0%"
                },
                required=True
            ),
            source_data={"tier": "premium"}
        )

        assert result == "20%"

    def test_custom_function_generate_id(self, data_mapper):
        """Test custom function - generate ID"""
        result = data_mapper.transformer.transform_field(
            value="test_value",
            mapping=FieldMapping(
                source_field="name",
                target_field="id",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.FUNCTION,
                transformation_config={"function_name": "generate_id"},
                required=True
            ),
            source_data={"name": "test_value"}
        )

        assert result is not None
        assert isinstance(result, str)
        assert len(result) == 12  # MD5 hash truncated

    def test_custom_function_slugify(self, data_mapper):
        """Test custom function - slugify"""
        result = data_mapper.transformer.transform_field(
            value="Test Product Name",
            mapping=FieldMapping(
                source_field="name",
                target_field="slug",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.FUNCTION,
                transformation_config={"function_name": "slugify"},
                required=True
            ),
            source_data={"name": "Test Product Name"}
        )

        assert result == "test-product-name"

    def test_type_conversion_string_to_integer(self, data_mapper):
        """Test type conversion from string to integer"""
        result = data_mapper.transformer.transform_field(
            value="123",
            mapping=FieldMapping(
                source_field="count",
                target_field="count_int",
                source_type=FieldType.STRING,
                target_type=FieldType.INTEGER,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            ),
            source_data={"count": "123"}
        )

        assert result == 123
        assert isinstance(result, int)

    def test_type_conversion_to_boolean(self, data_mapper):
        """Test type conversion to boolean"""
        # Test various truthy values
        for value in ["true", "1", "yes", "on"]:
            result = data_mapper.transformer.transform_field(
                value=value,
                mapping=FieldMapping(
                    source_field="flag",
                    target_field="flag_bool",
                    source_type=FieldType.STRING,
                    target_type=FieldType.BOOLEAN,
                    transformation=TransformationType.DIRECT_COPY,
                    required=True
                ),
                source_data={"flag": value}
            )
            assert result is True

    def test_field_with_default_value(self, data_mapper):
        """Test field with default value when source is None"""
        result = data_mapper.transformer.transform_field(
            value=None,
            mapping=FieldMapping(
                source_field="optional_field",
                target_field="target_field",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=False,
                default_value="default_value"
            ),
            source_data={}
        )

        assert result == "default_value"

    def test_required_field_missing_raises_error(self, data_mapper):
        """Test that missing required field raises error"""
        with pytest.raises(ValueError, match="Required field"):
            data_mapper.transformer.transform_field(
                value=None,
                mapping=FieldMapping(
                    source_field="required_field",
                    target_field="target_field",
                    source_type=FieldType.STRING,
                    target_type=FieldType.STRING,
                    transformation=TransformationType.DIRECT_COPY,
                    required=True
                ),
                source_data={}
            )


# =============================================================================
# TEST CLASS: TestValidation
# Tests for validation logic
# =============================================================================

class TestValidation:
    """Test data validation"""

    def test_validate_valid_data(self, data_mapper):
        """Test validation of valid data"""
        data = {"name": "Test Task", "description": "A test task"}
        result = data_mapper.validate_data(data, "asana_task")

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_missing_required_field(self, data_mapper):
        """Test validation fails when required field is missing"""
        data = {"description": "Task without name"}  # name is required
        result = data_mapper.validate_data(data, "asana_task")

        assert result["valid"] is False
        assert any("name" in error.lower() for error in result["errors"])

    def test_validate_bulk_data(self, data_mapper):
        """Test validation of bulk data"""
        data = [
            {"name": "Task 1"},
            {"name": "Task 2"}
        ]
        result = data_mapper.validate_data(data, "asana_task")

        assert result["valid"] is True
        assert result["validated_count"] == 2

    def test_validate_invalid_schema(self, data_mapper):
        """Test validation with invalid schema"""
        with pytest.raises(ValueError, match="Schema .* not found"):
            data_mapper.validate_data({"name": "Test"}, "invalid_schema")


# =============================================================================
# TEST CLASS: TestImportExport
# Tests for import/export functionality
# =============================================================================

class TestImportExport:
    """Test import and export of mappings"""

    def test_export_mapping(self, data_mapper):
        """Test exporting mapping configuration"""
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="name",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        data_mapper.create_mapping(
            mapping_id="test_export",
            source_schema="asana_task",
            target_schema="asana_task",
            field_mappings=field_mappings
        )

        exported = data_mapper.export_mapping("test_export")

        assert "mapping_id" in exported
        assert exported["mapping_id"] == "test_export"
        assert "field_mappings" in exported
        assert "exported_at" in exported

    def test_export_nonexistent_mapping(self, data_mapper):
        """Test exporting nonexistent mapping"""
        with pytest.raises(ValueError, match="Mapping .* not found"):
            data_mapper.export_mapping("nonexistent")

    def test_import_mapping(self, data_mapper):
        """Test importing mapping configuration"""
        import_config = {
            "mapping_id": "imported_mapping",
            "field_mappings": [
                {
                    "source_field": "name",
                    "target_field": "name",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": True,
                    "default_value": None,
                    "transformation_config": None
                }
            ]
        }

        data_mapper.import_mapping(import_config)

        assert "imported_mapping" in data_mapper.mappings
        assert len(data_mapper.mappings["imported_mapping"]) == 1


# =============================================================================
# TEST CLASS: TestGlobalInstance
# Tests for global data mapper instance
# =============================================================================

class TestGlobalInstance:
    """Test global data mapper instance"""

    def test_get_data_mapper_returns_singleton(self):
        """Test that get_data_mapper returns singleton instance"""
        mapper1 = get_data_mapper()
        mapper2 = get_data_mapper()

        assert mapper1 is mapper2

    def test_get_data_mapper_type(self):
        """Test that get_data_mapper returns correct type"""
        mapper = get_data_mapper()

        assert isinstance(mapper, IntegrationDataMapper)


# =============================================================================
# TEST CLASS: TestEnums
# Tests for enum values
# =============================================================================

class TestEnums:
    """Test enum definitions"""

    def test_field_type_enum(self):
        """Test FieldType enum values"""
        assert FieldType.STRING.value == "string"
        assert FieldType.INTEGER.value == "integer"
        assert FieldType.FLOAT.value == "float"
        assert FieldType.BOOLEAN.value == "boolean"
        assert FieldType.DATE.value == "date"
        assert FieldType.DATETIME.value == "datetime"
        assert FieldType.EMAIL.value == "email"
        assert FieldType.URL.value == "url"
        assert FieldType.JSON.value == "json"
        assert FieldType.ARRAY.value == "array"
        assert FieldType.OBJECT.value == "object"

    def test_transformation_type_enum(self):
        """Test TransformationType enum values"""
        assert TransformationType.DIRECT_COPY.value == "direct_copy"
        assert TransformationType.VALUE_MAPPING.value == "value_mapping"
        assert TransformationType.FORMAT_CONVERSION.value == "format_conversion"
        assert TransformationType.CALCULATION.value == "calculation"
        assert TransformationType.CONCATENATION.value == "concatenation"
        assert TransformationType.CONDITIONAL.value == "conditional"
        assert TransformationType.FUNCTION.value == "function"
