"""
Coverage-driven tests for IntegrationDataMapper (currently 0% -> target 80%+)

Focus areas from integration_data_mapper.py:
- IntegrationDataMapper.__init__ (initialization)
- _initialize_default_schemas() - schema initialization
- register_schema() - schema registration
- create_mapping() - mapping creation
- transform_data() - data transformation
- validate_data() - data validation
- DataTransformer - field transformations
- Type conversion and validation
"""

import pytest
from datetime import datetime, date
from typing import Dict, Any
from unittest.mock import MagicMock

from core.integration_data_mapper import (
    IntegrationDataMapper,
    DataTransformer,
    IntegrationSchema,
    BulkOperation,
    FieldMapping,
    FieldType,
    TransformationType,
    get_data_mapper
)


class TestDataTransformer:
    """Test DataTransformer class."""

    def test_init(self):
        """Cover DataTransformer initialization."""
        transformer = DataTransformer()

        assert transformer.transform_functions is not None
        assert TransformationType.DIRECT_COPY in transformer.transform_functions

    def test_transform_field_direct_copy(self):
        """Cover direct value copy transformation."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="name",
            target_field="fullName",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.DIRECT_COPY
        )

        result = transformer.transform_field("John Doe", mapping, {})

        assert result == "John Doe"

    def test_transform_field_value_mapping(self):
        """Cover value mapping transformation."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="status",
            target_field="status_code",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.VALUE_MAPPING,
            transformation_config={
                "value_map": {
                    "active": "1",
                    "inactive": "0"
                }
            }
        )

        result = transformer.transform_field("active", mapping, {})

        assert result == "1"

    def test_transform_field_format_conversion_lowercase(self):
        """Cover format conversion to lowercase."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="email",
            target_field="email_lower",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.FORMAT_CONVERSION,
            transformation_config={"format_type": "lowercase"}
        )

        result = transformer.transform_field("JOHN@EXAMPLE.COM", mapping, {})

        assert result == "john@example.com"

    def test_transform_field_format_conversion_uppercase(self):
        """Cover format conversion to uppercase."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="name",
            target_field="name_upper",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.FORMAT_CONVERSION,
            transformation_config={"format_type": "uppercase"}
        )

        result = transformer.transform_field("john", mapping, {})

        assert result == "JOHN"

    def test_transform_field_format_conversion_trim(self):
        """Cover format conversion trim."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="name",
            target_field="name_trimmed",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.FORMAT_CONVERSION,
            transformation_config={"format_type": "trim"}
        )

        result = transformer.transform_field("  john  ", mapping, {})

        assert result == "john"

    def test_transform_field_calculation_multiply(self):
        """Cover calculation transformation (multiply)."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="price",
            target_field="total",
            source_type=FieldType.FLOAT,
            target_type=FieldType.FLOAT,
            transformation=TransformationType.CALCULATION,
            transformation_config={
                "calculation_type": "multiply",
                "multiplier": 1.1
            }
        )

        result = transformer.transform_field(100.0, mapping, {})

        assert result == 110.0

    def test_transform_field_calculation_percentage(self):
        """Cover calculation transformation (percentage)."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="value",
            target_field="percent",
            source_type=FieldType.FLOAT,
            target_type=FieldType.FLOAT,
            transformation=TransformationType.CALCULATION,
            transformation_config={
                "calculation_type": "percentage",
                "percentage": 25
            }
        )

        result = transformer.transform_field(200.0, mapping, {})

        assert result == 50.0

    def test_transform_field_concatenation(self):
        """Cover concatenation transformation."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="first_name",
            target_field="full_name",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.CONCATENATION,
            transformation_config={
                "fields": ["self", "last_name"],
                "separator": " "
            }
        )

        source_data = {"first_name": "John", "last_name": "Doe"}
        result = transformer.transform_field("John", mapping, source_data)

        assert result == "John Doe"

    def test_transform_field_conditional(self):
        """Cover conditional transformation."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="age",
            target_field="category",
            source_type=FieldType.INTEGER,
            target_type=FieldType.STRING,
            transformation=TransformationType.CONDITIONAL,
            transformation_config={
                "conditions": [
                    {
                        "field": "self",
                        "operator": "greater_than",
                        "expected": 18,
                        "result": "adult"
                    }
                ],
                "default": "minor"
            }
        )

        result = transformer.transform_field(25, mapping, {})

        assert result == "adult"

    def test_transform_field_conditional_default(self):
        """Cover conditional transformation with default."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="age",
            target_field="category",
            source_type=FieldType.INTEGER,
            target_type=FieldType.STRING,
            transformation=TransformationType.CONDITIONAL,
            transformation_config={
                "conditions": [
                    {
                        "field": "self",
                        "operator": "greater_than",
                        "expected": 65,
                        "result": "senior"
                    }
                ],
                "default": "regular"
            }
        )

        result = transformer.transform_field(25, mapping, {})

        assert result == "regular"

    def test_transform_field_custom_function_generate_id(self):
        """Cover custom function transformation (generate_id)."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="name",
            target_field="id",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.FUNCTION,
            transformation_config={"function_name": "generate_id"}
        )

        result = transformer.transform_field("Test Name", mapping, {})

        assert len(result) == 12  # MD5 hash truncated to 12 chars
        assert isinstance(result, str)

    def test_transform_field_custom_function_slugify(self):
        """Cover custom function transformation (slugify)."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="title",
            target_field="slug",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.FUNCTION,
            transformation_config={"function_name": "slugify"}
        )

        result = transformer.transform_field("Hello World Test", mapping, {})

        assert result == "hello-world-test"

    def test_transform_field_none_with_default(self):
        """Cover None value handling with default."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="optional_field",
            target_field="field",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.DIRECT_COPY,
            default_value="default_value",
            required=False
        )

        result = transformer.transform_field(None, mapping, {})

        assert result == "default_value"

    def test_transform_field_none_required_raises(self):
        """Cover None value handling for required field."""
        transformer = DataTransformer()

        mapping = FieldMapping(
            source_field="required_field",
            target_field="field",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.DIRECT_COPY,
            required=True
        )

        with pytest.raises(ValueError, match="Required field"):
            transformer.transform_field(None, mapping, {})

    def test_convert_type_string(self):
        """Cover type conversion to string."""
        transformer = DataTransformer()

        result = transformer._convert_type(123, FieldType.STRING)

        assert result == "123"

    def test_convert_type_integer(self):
        """Cover type conversion to integer."""
        transformer = DataTransformer()

        result = transformer._convert_type("123", FieldType.INTEGER)

        assert result == 123
        assert isinstance(result, int)

    def test_convert_type_float(self):
        """Cover type conversion to float."""
        transformer = DataTransformer()

        result = transformer._convert_type("123.45", FieldType.FLOAT)

        assert result == 123.45

    def test_convert_type_boolean_true(self):
        """Cover type conversion to boolean (true)."""
        transformer = DataTransformer()

        assert transformer._convert_type("true", FieldType.BOOLEAN) is True
        assert transformer._convert_type("1", FieldType.BOOLEAN) is True
        assert transformer._convert_type("yes", FieldType.BOOLEAN) is True
        assert transformer._convert_type(True, FieldType.BOOLEAN) is True

    def test_convert_type_boolean_false(self):
        """Cover type conversion to boolean (false)."""
        transformer = DataTransformer()

        assert transformer._convert_type("false", FieldType.BOOLEAN) is False
        assert transformer._convert_type("0", FieldType.BOOLEAN) is False
        assert transformer._convert_type("no", FieldType.BOOLEAN) is False
        assert transformer._convert_type(False, FieldType.BOOLEAN) is False

    def test_convert_type_date(self):
        """Cover type conversion to date."""
        transformer = DataTransformer()

        result = transformer._convert_type("2026-03-14", FieldType.DATE)

        assert isinstance(result, str)
        assert "2026-03-14" in result

    def test_convert_type_datetime(self):
        """Cover type conversion to datetime."""
        transformer = DataTransformer()

        result = transformer._convert_type("2026-03-14T10:30:00Z", FieldType.DATETIME)

        assert isinstance(result, str)
        assert "2026-03-14" in result

    def test_convert_type_email(self):
        """Cover type conversion to email."""
        transformer = DataTransformer()

        result = transformer._convert_type("TEST@EXAMPLE.COM", FieldType.EMAIL)

        assert result == "test@example.com"

    def test_convert_type_email_invalid(self):
        """Cover invalid email conversion."""
        transformer = DataTransformer()

        with pytest.raises(ValueError, match="Invalid email"):
            transformer._convert_type("not-an-email", FieldType.EMAIL)

    def test_convert_type_url(self):
        """Cover type conversion to URL."""
        transformer = DataTransformer()

        result = transformer._convert_type("example.com", FieldType.URL)

        assert result == "https://example.com"

    def test_convert_type_url_already_https(self):
        """Cover URL conversion with existing https."""
        transformer = DataTransformer()

        result = transformer._convert_type("https://example.com", FieldType.URL)

        assert result == "https://example.com"

    def test_convert_type_json_string(self):
        """Cover JSON conversion from string."""
        transformer = DataTransformer()

        result = transformer._convert_type('{"key": "value"}', FieldType.JSON)

        assert result == {"key": "value"}

    def test_convert_type_array_string(self):
        """Cover array conversion from comma-separated string."""
        transformer = DataTransformer()

        result = transformer._convert_type("item1,item2,item3", FieldType.ARRAY)

        assert result == ["item1", "item2", "item3"]

    def test_convert_type_object_dict(self):
        """Cover object conversion from dict."""
        transformer = DataTransformer()

        result = transformer._convert_type({"key": "value"}, FieldType.OBJECT)

        assert result == {"key": "value"}

    def test_convert_type_none(self):
        """Cover None value in type conversion."""
        transformer = DataTransformer()

        result = transformer._convert_type(None, FieldType.STRING)

        assert result is None

    def test_evaluate_condition_equals(self):
        """Cover condition evaluation (equals)."""
        transformer = DataTransformer()

        result = transformer._evaluate_condition("test", "equals", "test")

        assert result is True

    def test_evaluate_condition_not_equals(self):
        """Cover condition evaluation (not_equals)."""
        transformer = DataTransformer()

        result = transformer._evaluate_condition("test", "not_equals", "other")

        assert result is True

    def test_evaluate_condition_contains(self):
        """Cover condition evaluation (contains)."""
        transformer = DataTransformer()

        result = transformer._evaluate_condition("hello world", "contains", "world")

        assert result is True

    def test_evaluate_condition_greater_than(self):
        """Cover condition evaluation (greater_than)."""
        transformer = DataTransformer()

        result = transformer._evaluate_condition(10, "greater_than", 5)

        assert result is True

    def test_evaluate_condition_less_than(self):
        """Cover condition evaluation (less_than)."""
        transformer = DataTransformer()

        result = transformer._evaluate_condition(5, "less_than", 10)

        assert result is True

    def test_evaluate_condition_is_empty(self):
        """Cover condition evaluation (is_empty)."""
        transformer = DataTransformer()

        assert transformer._evaluate_condition("", "is_empty", None) is True
        assert transformer._evaluate_condition([], "is_empty", None) is True
        assert transformer._evaluate_condition(None, "is_empty", None) is True


class TestIntegrationDataMapper:
    """Test IntegrationDataMapper class."""

    def test_init(self):
        """Cover IntegrationDataMapper initialization."""
        mapper = IntegrationDataMapper()

        assert mapper.transformer is not None
        assert isinstance(mapper.schemas, dict)
        assert isinstance(mapper.mappings, dict)

    def test_initialize_default_schemas(self):
        """Cover default schema initialization."""
        mapper = IntegrationDataMapper()

        # Should have default schemas
        assert "asana_task" in mapper.schemas
        assert "jira_issue" in mapper.schemas
        assert "salesforce_lead" in mapper.schemas

    def test_register_schema(self):
        """Cover registering a new schema."""
        mapper = IntegrationDataMapper()

        schema = IntegrationSchema(
            integration_id="custom_integration",
            integration_name="Custom",
            version="1.0",
            fields={"field1": {"type": "string"}},
            supported_operations=["create", "read"]
        )

        mapper.register_schema(schema)

        assert "custom_integration" in mapper.schemas

    def test_create_mapping_success(self):
        """Cover creating a mapping between schemas."""
        mapper = IntegrationDataMapper()

        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="fullName",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY
            )
        ]

        mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        assert "test_mapping" in mapper.mappings

    def test_create_mapping_source_not_found(self):
        """Cover creating mapping with missing source schema."""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Source schema.*not found"):
            mapper.create_mapping(
                mapping_id="test",
                source_schema="nonexistent",
                target_schema="asana_task",
                field_mappings=[]
            )

    def test_create_mapping_target_not_found(self):
        """Cover creating mapping with missing target schema."""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Target schema.*not found"):
            mapper.create_mapping(
                mapping_id="test",
                source_schema="asana_task",
                target_schema="nonexistent",
                field_mappings=[]
            )

    def test_transform_data_single_record(self):
        """Cover transforming single data record."""
        mapper = IntegrationDataMapper()

        # Create mapping
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="summary",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY
            )
        ]

        mapper.create_mapping(
            mapping_id="test_map",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        # Transform data
        source_data = {"name": "Test Task"}
        result = mapper.transform_data(source_data, "test_map")

        assert result["summary"] == "Test Task"

    def test_transform_data_batch(self):
        """Cover transforming batch data records."""
        mapper = IntegrationDataMapper()

        field_mappings = [
            FieldMapping(
                source_field="title",
                target_field="summary",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY
            )
        ]

        mapper.create_mapping(
            mapping_id="batch_map",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        source_data = [
            {"title": "Task 1"},
            {"title": "Task 2"}
        ]

        results = mapper.transform_data(source_data, "batch_map")

        assert len(results) == 2
        assert results[0]["summary"] == "Task 1"
        assert results[1]["summary"] == "Task 2"

    def test_transform_data_mapping_not_found(self):
        """Cover transforming with non-existent mapping."""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Mapping.*not found"):
            mapper.transform_data({"test": "data"}, "nonexistent_mapping")

    def test_transform_data_constant_value(self):
        """Cover transforming with constant value."""
        mapper = IntegrationDataMapper()

        field_mappings = [
            FieldMapping(
                source_field="constant",
                target_field="fixed_value",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                transformation_config={"constant_value": "FIXED"}
            )
        ]

        mapper.create_mapping(
            mapping_id="constant_map",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        result = mapper.transform_data({}, "constant_map")

        assert result["fixed_value"] == "FIXED"

    def test_transform_data_missing_field_not_required(self):
        """Cover transforming with missing optional field."""
        mapper = IntegrationDataMapper()

        field_mappings = [
            FieldMapping(
                source_field="optional_field",
                target_field="target",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=False
            )
        ]

        mapper.create_mapping(
            mapping_id="optional_map",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        result = mapper.transform_data({}, "optional_map")

        # Should not have target field if source is missing and not required
        assert "target" not in result or result.get("target") is None

    def test_transform_data_missing_field_required(self):
        """Cover transforming with missing required field."""
        mapper = IntegrationDataMapper()

        field_mappings = [
            FieldMapping(
                source_field="required_field",
                target_field="target",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=True
            )
        ]

        mapper.create_mapping(
            mapping_id="required_map",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        with pytest.raises(ValueError, match="Required field"):
            mapper.transform_data({}, "required_map")

    def test_validate_data_success(self):
        """Cover successful data validation."""
        mapper = IntegrationDataMapper()

        # Validate against Asana schema
        data = {
            "name": "Test Task",
            "description": "Test description"
        }

        result = mapper.validate_data(data, "asana_task")

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_data_missing_required(self):
        """Cover validation with missing required field."""
        mapper = IntegrationDataMapper()

        # Missing 'name' which is required
        data = {
            "description": "Test"
        }

        result = mapper.validate_data(data, "asana_task")

        assert result["valid"] is False
        assert any("name" in error.lower() for error in result["errors"])

    def test_validate_data_schema_not_found(self):
        """Cover validation with non-existent schema."""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Schema.*not found"):
            mapper.validate_data({}, "nonexistent_schema")

    def test_validate_data_batch(self):
        """Cover batch data validation."""
        mapper = IntegrationDataMapper()

        data = [
            {"name": "Task 1"},
            {"name": "Task 2"}
        ]

        result = mapper.validate_data(data, "asana_task")

        assert result["valid"] is True
        assert result["validated_count"] == 2

    def test_get_schema_info(self):
        """Cover getting schema information."""
        mapper = IntegrationDataMapper()

        schema = mapper.get_schema_info("asana_task")

        assert schema is not None
        assert schema.integration_id == "asana_task"
        assert schema.integration_name == "Asana Task"

    def test_get_schema_info_not_found(self):
        """Cover getting non-existent schema info."""
        mapper = IntegrationDataMapper()

        result = mapper.get_schema_info("nonexistent")

        assert result is None

    def test_list_schemas(self):
        """Cover listing all schemas."""
        mapper = IntegrationDataMapper()

        schemas = mapper.list_schemas()

        assert len(schemas) >= 3
        assert "asana_task" in schemas
        assert "jira_issue" in schemas

    def test_list_mappings(self):
        """Cover listing all mappings."""
        mapper = IntegrationDataMapper()

        # Create a mapping
        field_mappings = [
            FieldMapping(
                source_field="test",
                target_field="test",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY
            )
        ]

        mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        mappings = mapper.list_mappings()

        assert "test_mapping" in mappings

    def test_export_mapping(self):
        """Cover exporting mapping configuration."""
        mapper = IntegrationDataMapper()

        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="summary",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY
            )
        ]

        mapper.create_mapping(
            mapping_id="export_test",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        exported = mapper.export_mapping("export_test")

        assert exported["mapping_id"] == "export_test"
        assert "field_mappings" in exported
        assert "exported_at" in exported
        assert len(exported["field_mappings"]) == 1

    def test_export_mapping_not_found(self):
        """Cover exporting non-existent mapping."""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Mapping.*not found"):
            mapper.export_mapping("nonexistent")

    def test_import_mapping(self):
        """Cover importing mapping configuration."""
        mapper = IntegrationDataMapper()

        mapping_config = {
            "mapping_id": "import_test",
            "field_mappings": [
                {
                    "source_field": "name",
                    "target_field": "summary",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy"
                }
            ]
        }

        mapper.import_mapping(mapping_config)

        assert "import_test" in mapper.list_mappings()


class TestGlobalDataMapper:
    """Test global data mapper instance."""

    def test_get_data_mapper_singleton(self):
        """Cover get_data_mapper returns singleton."""
        mapper1 = get_data_mapper()
        mapper2 = get_data_mapper()

        # Should return same instance
        assert mapper1 is mapper2


class TestBulkOperations:
    """Test bulk operation configuration."""

    def test_bulk_operation_config(self):
        """Cover bulk operation configuration."""
        bulk_op = BulkOperation(
            operation_type="create",
            integration_id="asana",
            items=[{"name": "Task 1"}, {"name": "Task 2"}],
            batch_size=50,
            parallel_processing=False,
            stop_on_error=True
        )

        assert bulk_op.operation_type == "create"
        assert bulk_op.batch_size == 50
        assert bulk_op.parallel_processing is False
        assert bulk_op.stop_on_error is True
        assert len(bulk_op.items) == 2
