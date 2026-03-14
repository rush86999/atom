"""
Coverage-driven tests for integration_data_mapper.py (0% -> 75%+ target)

This test suite focuses on achieving 75%+ coverage on IntegrationDataMapper (325 statements)
by testing data transformation, schema mapping, validation, error handling, and batch processing.

Target: 75%+ coverage (245+ of 325 statements)
Baseline: 74.6% coverage (existing tests from Phase 189)
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, date
from core.integration_data_mapper import (
    IntegrationDataMapper,
    DataTransformer,
    FieldMapping,
    IntegrationSchema,
    BulkOperation,
    FieldType,
    TransformationType
)


class TestIntegrationDataMapperCoverage:
    """Coverage-driven tests for integration_data_mapper.py (74.6% -> 85%+ target)"""

    # ========== Initialization Tests ==========

    def test_mapper_initialization(self):
        """Cover mapper initialization (lines 329-333)"""
        mapper = IntegrationDataMapper()
        assert mapper.transformer is not None
        assert isinstance(mapper.schemas, dict)
        assert isinstance(mapper.mappings, dict)
        assert len(mapper.schemas) >= 3  # asana_task, jira_issue, salesforce_lead

    def test_default_schemas_initialized(self):
        """Cover default schema initialization (lines 335-397)"""
        mapper = IntegrationDataMapper()
        assert "asana_task" in mapper.schemas
        assert "jira_issue" in mapper.schemas
        assert "salesforce_lead" in mapper.schemas

        # Check asana schema
        asana_schema = mapper.schemas["asana_task"]
        assert asana_schema.integration_id == "asana_task"
        assert asana_schema.bulk_operations_supported is True
        assert asana_schema.max_bulk_size == 50

    # ========== Schema Registration Tests ==========

    def test_register_schema(self):
        """Cover schema registration (lines 399-402)"""
        mapper = IntegrationDataMapper()
        new_schema = IntegrationSchema(
            integration_id="test_integration",
            integration_name="Test Integration",
            version="1.0",
            fields={"field1": {"type": "string", "required": True}},
            supported_operations=["create", "read"]
        )

        mapper.register_schema(new_schema)
        assert "test_integration" in mapper.schemas
        assert mapper.schemas["test_integration"].integration_name == "Test Integration"

    # ========== Mapping Creation Tests ==========

    def test_create_mapping_success(self):
        """Cover successful mapping creation (lines 404-429)"""
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
            mapping_id="asana_to_jira",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        assert "asana_to_jira" in mapper.mappings
        assert len(mapper.mappings["asana_to_jira"]) == 1

    def test_create_mapping_invalid_source_schema(self):
        """Cover mapping creation with invalid source schema (lines 413-414)"""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Source schema.*not found"):
            mapper.create_mapping(
                mapping_id="test_mapping",
                source_schema="nonexistent_schema",
                target_schema="jira_issue",
                field_mappings=[]
            )

    def test_create_mapping_invalid_target_schema(self):
        """Cover mapping creation with invalid target schema (lines 415-416)"""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Target schema.*not found"):
            mapper.create_mapping(
                mapping_id="test_mapping",
                source_schema="asana_task",
                target_schema="nonexistent_schema",
                field_mappings=[]
            )

    def test_create_mapping_invalid_target_field(self):
        """Cover mapping creation with invalid target field (lines 425-426)"""
        mapper = IntegrationDataMapper()
        field_mappings = [
            FieldMapping(
                source_field="name",
                target_field="nonexistent_field",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY
            )
        ]

        with pytest.raises(ValueError, match="Target field.*not in schema"):
            mapper.create_mapping(
                mapping_id="test_mapping",
                source_schema="asana_task",
                target_schema="jira_issue",
                field_mappings=field_mappings
            )

    # ========== Data Transformation Tests ==========

    def test_transform_data_single_record(self):
        """Cover single record transformation (lines 431-446)"""
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
            mapping_id="asana_to_jira",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        source_data = {"name": "Test Task"}
        result = mapper.transform_data(source_data, "asana_to_jira")

        assert result["summary"] == "Test Task"

    def test_transform_data_bulk(self):
        """Cover bulk data transformation (lines 443-444)"""
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
            mapping_id="asana_to_jira",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        source_data = [
            {"name": "Task 1"},
            {"name": "Task 2"},
            {"name": "Task 3"}
        ]
        result = mapper.transform_data(source_data, "asana_to_jira")

        assert len(result) == 3
        assert result[0]["summary"] == "Task 1"
        assert result[1]["summary"] == "Task 2"
        assert result[2]["summary"] == "Task 3"

    def test_transform_data_mapping_not_found(self):
        """Cover transformation with nonexistent mapping (lines 437-438)"""
        mapper = IntegrationDataMapper()

        with pytest.raises(ValueError, match="Mapping.*not found"):
            mapper.transform_data({"name": "Test"}, "nonexistent_mapping")

    def test_transform_single_with_constant_value(self):
        """Cover transformation with constant value (lines 455-456)"""
        mapper = IntegrationDataMapper()
        field_mappings = [
            FieldMapping(
                source_field="constant",
                target_field="priority",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.VALUE_MAPPING,
                transformation_config={"constant_value": "High"}
            )
        ]

        mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        result = mapper._transform_single({}, field_mappings)
        assert result["priority"] == "High"

    def test_transform_single_with_default_value(self):
        """Cover transformation with default value for missing field (lines 470-471)"""
        mapper = IntegrationDataMapper()
        field_mappings = [
            FieldMapping(
                source_field="nonexistent_field",
                target_field="summary",
                source_type=FieldType.STRING,
                target_type=FieldType.STRING,
                transformation=TransformationType.DIRECT_COPY,
                required=False,
                default_value="Default Summary"
            )
        ]

        mapper.create_mapping(
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        result = mapper._transform_single({}, field_mappings)
        assert result["summary"] == "Default Summary"

    # ========== DataTransformer Tests ==========

    def test_transform_field_direct_copy(self):
        """Cover direct copy transformation (lines 115-125)"""
        mapping = FieldMapping(
            source_field="source",
            target_field="target",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.DIRECT_COPY
        )

        transformer = DataTransformer()
        source_data = {"source": "test_value"}

        result = transformer.transform_field("test_value", mapping, source_data)
        assert result == "test_value"

    def test_transform_field_with_none_and_default(self):
        """Cover transformation with None value and default (lines 98-102)"""
        mapping = FieldMapping(
            source_field="field",
            target_field="target",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.DIRECT_COPY,
            default_value="default_value"
        )

        transformer = DataTransformer()
        source_data = {}

        result = transformer.transform_field(None, mapping, source_data)
        assert result == "default_value"

    def test_transform_field_value_mapping(self):
        """Cover value mapping transformation (lines 126-132)"""
        mapping = FieldMapping(
            source_field="status",
            target_field="status_label",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.VALUE_MAPPING,
            transformation_config={
                "value_map": {
                    "active": "Active",
                    "inactive": "Inactive"
                }
            }
        )

        transformer = DataTransformer()
        source_data = {"status": "active"}

        result = transformer.transform_field("active", mapping, source_data)
        assert result == "Active"

    def test_transform_field_concatenation(self):
        """Cover field concatenation (lines 181-195)"""
        mapping = FieldMapping(
            source_field="first_name",
            target_field="full_name",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.CONCATENATION,
            transformation_config={
                "fields": ["first_name", "last_name"],
                "separator": " "
            }
        )

        transformer = DataTransformer()
        source_data = {"first_name": "John", "last_name": "Doe"}

        result = transformer.transform_field("John", mapping, source_data)
        assert result == "John Doe"

    def test_transform_field_conditional(self):
        """Cover conditional transformation (lines 196-215)"""
        mapping = FieldMapping(
            source_field="score",
            target_field="grade",
            source_type=FieldType.INTEGER,
            target_type=FieldType.STRING,
            transformation=TransformationType.CONDITIONAL,
            transformation_config={
                "conditions": [
                    {"operator": ">=", "value": 90, "result": "A"},
                    {"operator": ">=", "value": 80, "result": "B"},
                    {"operator": ">=", "value": 70, "result": "C"}
                ]
            }
        )

        transformer = DataTransformer()
        source_data = {"score": 85}

        result = transformer.transform_field(85, mapping, source_data)
        assert result == "B"

    # ========== Data Validation Tests ==========

    def test_validate_data_success(self):
        """Cover successful data validation (lines 475-507)"""
        mapper = IntegrationDataMapper()
        data = {
            "name": "Test Task",
            "description": "Test Description"
        }

        result = mapper.validate_data(data, "asana_task")
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_data_missing_required_field(self):
        """Cover validation with missing required field (lines 489-497)"""
        mapper = IntegrationDataMapper()
        data = {
            "description": "Test Description"
            # Missing required 'name' field
        }

        result = mapper.validate_data(data, "asana_task")
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert any("name" in str(error).lower() for error in result["errors"])

    def test_validate_data_type_mismatch(self):
        """Cover validation with type mismatch (lines 499-507)"""
        mapper = IntegrationDataMapper()
        data = {
            "name": "Test Task",
            "completed": "not_a_boolean"  # Should be boolean
        }

        result = mapper.validate_data(data, "asana_task")
        assert result["valid"] is False

    def test_validate_data_bulk(self):
        """Cover bulk data validation (lines 509-519)"""
        mapper = IntegrationDataMapper()
        data = [
            {"name": "Task 1"},
            {"name": "Task 2"},
            {"name": "Task 3"}
        ]

        result = mapper.validate_data(data, "asana_task")
        assert result["valid"] is True
        assert result["total_records"] == 3

    def test_validate_data_schema_not_found(self):
        """Cover validation with nonexistent schema (lines 485-487)"""
        mapper = IntegrationDataMapper()
        data = {"name": "Test"}

        result = mapper.validate_data(data, "nonexistent_schema")
        assert result["valid"] is False

    # ========== Schema Info Tests ==========

    def test_get_schema_info(self):
        """Cover getting schema information (lines 521-523)"""
        mapper = IntegrationDataMapper()
        schema_info = mapper.get_schema_info("asana_task")

        assert schema_info is not None
        assert schema_info.integration_id == "asana_task"
        assert schema_info.integration_name == "Asana Task"

    def test_get_schema_info_not_found(self):
        """Cover getting schema info for nonexistent schema"""
        mapper = IntegrationDataMapper()
        schema_info = mapper.get_schema_info("nonexistent_schema")
        assert schema_info is None

    # ========== Listing Tests ==========

    def test_list_schemas(self):
        """Cover listing schemas (lines 525-527)"""
        mapper = IntegrationDataMapper()
        schemas = mapper.list_schemas()

        assert len(schemas) >= 3
        assert "asana_task" in schemas
        assert "jira_issue" in schemas
        assert "salesforce_lead" in schemas

    def test_list_mappings(self):
        """Cover listing mappings (lines 529-531)"""
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
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        mappings = mapper.list_mappings()
        assert "test_mapping" in mappings

    # ========== Mapping Export/Import Tests ==========

    def test_export_mapping(self):
        """Cover exporting mapping (lines 533-542)"""
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
            mapping_id="test_mapping",
            source_schema="asana_task",
            target_schema="jira_issue",
            field_mappings=field_mappings
        )

        exported = mapper.export_mapping("test_mapping")
        assert exported["mapping_id"] == "test_mapping"
        assert exported["source_schema"] == "asana_task"
        assert exported["target_schema"] == "jira_issue"
        assert len(exported["field_mappings"]) == 1

    def test_export_mapping_not_found(self):
        """Cover exporting nonexistent mapping"""
        mapper = IntegrationDataMapper()
        exported = mapper.export_mapping("nonexistent_mapping")
        assert exported["error"] is not None

    def test_import_mapping(self):
        """Cover importing mapping (lines 544-557)"""
        mapper = IntegrationDataMapper()
        mapping_config = {
            "mapping_id": "imported_mapping",
            "source_schema": "asana_task",
            "target_schema": "jira_issue",
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
        assert "imported_mapping" in mapper.mappings

    # ========== Type Conversion Tests ==========

    def test_convert_type_string_to_integer(self):
        """Cover string to integer conversion (lines 260-290)"""
        transformer = DataTransformer()
        result = transformer._convert_type("123", FieldType.INTEGER)
        assert result == 123
        assert isinstance(result, int)

    def test_convert_type_string_to_float(self):
        """Cover string to float conversion"""
        transformer = DataTransformer()
        result = transformer._convert_type("123.45", FieldType.FLOAT)
        assert result == 123.45
        assert isinstance(result, float)

    def test_convert_type_string_to_boolean(self):
        """Cover string to boolean conversion"""
        transformer = DataTransformer()
        assert transformer._convert_type("true", FieldType.BOOLEAN) is True
        assert transformer._convert_type("True", FieldType.BOOLEAN) is True
        assert transformer._convert_type("false", FieldType.BOOLEAN) is False
        assert transformer._convert_type("False", FieldType.BOOLEAN) is False

    def test_convert_type_string_to_datetime(self):
        """Cover string to datetime conversion (lines 305-315)"""
        transformer = DataTransformer()
        result = transformer._convert_type("2026-03-14", FieldType.DATETIME)
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 14

    def test_convert_type_string_to_date(self):
        """Cover string to date conversion (lines 317-320)"""
        transformer = DataTransformer()
        result = transformer._convert_type("2026-03-14", FieldType.DATE)
        assert isinstance(result, date)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 14

    def test_convert_type_unsupported(self):
        """Cover unsupported type conversion (lines 320-323)"""
        transformer = DataTransformer()
        with pytest.raises(ValueError, match="Unsupported target type"):
            transformer._convert_type("data", FieldType.JSON)

    # ========== Condition Evaluation Tests ==========

    def test_evaluate_condition_equal(self):
        """Cover equal condition evaluation (lines 239-258)"""
        transformer = DataTransformer()
        assert transformer._evaluate_condition("test", "==", "test") is True
        assert transformer._evaluate_condition("test", "==", "other") is False

    def test_evaluate_condition_greater_than(self):
        """Cover greater than condition evaluation"""
        transformer = DataTransformer()
        assert transformer._evaluate_condition(10, ">", 5) is True
        assert transformer._evaluate_condition(5, ">", 10) is False

    def test_evaluate_condition_less_than(self):
        """Cover less than condition evaluation"""
        transformer = DataTransformer()
        assert transformer._evaluate_condition(5, "<", 10) is True
        assert transformer._evaluate_condition(10, "<", 5) is False

    def test_evaluate_condition_in_list(self):
        """Cover 'in' condition evaluation (lines 252-258)"""
        transformer = DataTransformer()
        assert transformer._evaluate_condition("apple", "in", ["apple", "banana"]) is True
        assert transformer._evaluate_condition("orange", "in", ["apple", "banana"]) is False

    def test_evaluate_condition_invalid_operator(self):
        """Cover invalid condition operator (lines 256-258)"""
        transformer = DataTransformer()
        assert transformer._evaluate_condition("value", "invalid_operator", "test") is False

    # ========== Field Mapping Configuration Tests ==========

    def test_field_mapping_configuration(self):
        """Cover FieldMapping dataclass (lines 43-52)"""
        mapping = FieldMapping(
            source_field="source",
            target_field="target",
            source_type=FieldType.STRING,
            target_type=FieldType.STRING,
            transformation=TransformationType.DIRECT_COPY,
            required=True,
            default_value="default"
        )

        assert mapping.source_field == "source"
        assert mapping.target_field == "target"
        assert mapping.source_type == FieldType.STRING
        assert mapping.target_type == FieldType.STRING
        assert mapping.transformation == TransformationType.DIRECT_COPY
        assert mapping.required is True
        assert mapping.default_value == "default"

    # ========== IntegrationSchema Configuration Tests ==========

    def test_integration_schema_configuration(self):
        """Cover IntegrationSchema dataclass (lines 55-63)"""
        schema = IntegrationSchema(
            integration_id="test_integration",
            integration_name="Test Integration",
            version="1.0.0",
            fields={
                "field1": {"type": "string", "required": True},
                "field2": {"type": "integer", "required": False}
            },
            supported_operations=["create", "update"],
            bulk_operations_supported=True,
            max_bulk_size=1000
        )

        assert schema.integration_id == "test_integration"
        assert schema.integration_name == "Test Integration"
        assert schema.version == "1.0.0"
        assert len(schema.fields) == 2
        assert "create" in schema.supported_operations
        assert schema.bulk_operations_supported is True
        assert schema.max_bulk_size == 1000

    # ========== BulkOperation Configuration Tests ==========

    def test_bulk_operation_configuration(self):
        """Cover BulkOperation dataclass (lines 66-74)"""
        bulk_op = BulkOperation(
            operation_type="create",
            integration_id="test_integration",
            items=[{"id": 1}, {"id": 2}],
            batch_size=50,
            parallel_processing=True,
            stop_on_error=False
        )

        assert bulk_op.operation_type == "create"
        assert bulk_op.integration_id == "test_integration"
        assert len(bulk_op.items) == 2
        assert bulk_op.batch_size == 50
        assert bulk_op.parallel_processing is True
        assert bulk_op.stop_on_error is False

    # ========== FieldType Enum Tests ==========

    def test_field_type_enum(self):
        """Cover FieldType enum values (lines 18-30)"""
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

    # ========== TransformationType Enum Tests ==========

    def test_transformation_type_enum(self):
        """Cover TransformationType enum values (lines 32-40)"""
        assert TransformationType.DIRECT_COPY.value == "direct_copy"
        assert TransformationType.VALUE_MAPPING.value == "value_mapping"
        assert TransformationType.FORMAT_CONVERSION.value == "format_conversion"
        assert TransformationType.CALCULATION.value == "calculation"
        assert TransformationType.CONCATENATION.value == "concatenation"
        assert TransformationType.CONDITIONAL.value == "conditional"
        assert TransformationType.FUNCTION.value == "function"

    # ========== Global Instance Tests ==========

    def test_get_data_mapper_singleton(self):
        """Cover global data mapper instance (lines 559-563)"""
        from core.integration_data_mapper import get_data_mapper

        mapper1 = get_data_mapper()
        mapper2 = get_data_mapper()

        # Should return same instance
        assert mapper1 is mapper2
