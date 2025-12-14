"""
Advanced Integration Data Mapping & Bulk Operations System
Provides sophisticated data transformation and bulk processing capabilities
for ATOM's integrations ecosystem
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)

class FieldType(Enum):
    """Supported field types for data mapping"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    URL = "url"
    JSON = "json"
    ARRAY = "array"
    OBJECT = "object"

class TransformationType(Enum):
    """Types of field transformations"""
    DIRECT_COPY = "direct_copy"
    VALUE_MAPPING = "value_mapping"
    FORMAT_CONVERSION = "format_conversion"
    CALCULATION = "calculation"
    CONCATENATION = "concatenation"
    CONDITIONAL = "conditional"
    FUNCTION = "function"

@dataclass
class FieldMapping:
    """Individual field mapping configuration"""
    source_field: str
    target_field: str
    source_type: FieldType
    target_type: FieldType
    transformation: TransformationType
    transformation_config: Optional[Dict[str, Any]] = None
    required: bool = True
    default_value: Optional[Any] = None

@dataclass
class IntegrationSchema:
    """Schema definition for an integration"""
    integration_id: str
    integration_name: str
    version: str
    fields: Dict[str, Dict[str, Any]]  # field_name -> {type, required, description, etc.}
    supported_operations: List[str]
    bulk_operations_supported: bool = False
    max_bulk_size: Optional[int] = None

@dataclass
class BulkOperation:
    """Bulk operation configuration"""
    operation_type: str  # create, update, delete, upsert
    integration_id: str
    items: List[Dict[str, Any]]
    batch_size: int = 100
    parallel_processing: bool = True
    stop_on_error: bool = False
    progress_callback: Optional[Callable] = None

class DataTransformer:
    """Handles field-level data transformations"""

    def __init__(self):
        self.transform_functions = {
            TransformationType.DIRECT_COPY: self._direct_copy,
            TransformationType.VALUE_MAPPING: self._value_mapping,
            TransformationType.FORMAT_CONVERSION: self._format_conversion,
            TransformationType.CALCULATION: self._calculation,
            TransformationType.CONCATENATION: self._concatenation,
            TransformationType.CONDITIONAL: self._conditional,
            TransformationType.FUNCTION: self._custom_function
        }

    def transform_field(
        self,
        value: Any,
        mapping: FieldMapping,
        source_data: Dict[str, Any]
    ) -> Any:
        """Transform a single field based on mapping configuration"""
        try:
            if value is None:
                if mapping.default_value is not None:
                    return mapping.default_value
                elif mapping.required:
                    raise ValueError(f"Required field {mapping.source_field} is missing")
                else:
                    return None

            # Apply transformation
            transform_func = self.transform_functions.get(mapping.transformation)
            if transform_func:
                transformed_value = transform_func(value, mapping, source_data)
            else:
                transformed_value = value

            # Type conversion
            return self._convert_type(transformed_value, mapping.target_type)

        except Exception as e:
            logger.error(f"Failed to transform field {mapping.source_field}: {e}")
            if mapping.required:
                raise
            return mapping.default_value

    def _direct_copy(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Direct value copy"""
        return value

    def _value_mapping(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Map values using configuration"""
        mapping_config = mapping.transformation_config or {}
        value_map = mapping_config.get("value_map", {})

        return value_map.get(str(value), value)

    def _format_conversion(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Convert data format"""
        mapping_config = mapping.transformation_config or {}
        format_type = mapping_config.get("format_type")

        if format_type == "date_to_iso":
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()
            elif isinstance(value, datetime):
                return value.isoformat()
        elif format_type == "date_format":
            date_format = mapping_config.get("format", "%Y-%m-%d")
            if isinstance(value, (datetime, str)):
                if isinstance(value, str):
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return value.strftime(date_format)
        elif format_type == "lowercase":
            return str(value).lower()
        elif format_type == "uppercase":
            return str(value).upper()
        elif format_type == "title_case":
            return str(value).title()
        elif format_type == "remove_spaces":
            return str(value).replace(" ", "")

        return value

    def _calculation(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Perform calculations"""
        mapping_config = mapping.transformation_config or {}
        calculation_type = mapping_config.get("calculation_type")

        if calculation_type == "sum_fields":
            fields = mapping_config.get("fields", [])
            total = sum(source_data.get(field, 0) for field in fields)
            return total
        elif calculation_type == "multiply":
            multiplier = mapping_config.get("multiplier", 1)
            return float(value) * multiplier
        elif calculation_type == "percentage":
            percentage = mapping_config.get("percentage", 100)
            return (float(value) * percentage) / 100
        elif calculation_type == "round":
            decimals = mapping_config.get("decimals", 2)
            return round(float(value), decimals)

        return value

    def _concatenation(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Concatenate multiple fields"""
        mapping_config = mapping.transformation_config or {}
        fields = mapping_config.get("fields", [])
        separator = mapping_config.get("separator", " ")

        parts = []
        for field in fields:
            if field == "self":
                parts.append(str(value))
            else:
                parts.append(str(source_data.get(field, "")))

        return separator.join(parts).strip()

    def _conditional(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Conditional transformation"""
        mapping_config = mapping.transformation_config or {}
        conditions = mapping_config.get("conditions", [])
        default_value = mapping_config.get("default", value)

        for condition in conditions:
            condition_type = condition.get("type")
            field = condition.get("field")
            operator = condition.get("operator")
            expected = condition.get("expected")
            result = condition.get("result")

            source_value = source_data.get(field, value) if field != "self" else value

            if self._evaluate_condition(source_value, operator, expected):
                return result

        return default_value

    def _custom_function(self, value: Any, mapping: FieldMapping, source_data: Dict) -> Any:
        """Custom function transformation"""
        mapping_config = mapping.transformation_config or {}
        function_name = mapping_config.get("function_name")

        # Built-in functions
        if function_name == "generate_id":
            return hashlib.md5(str(value).encode()).hexdigest()[:12]
        elif function_name == "slugify":
            return str(value).lower().replace(" ", "-").replace("_", "-")
        elif function_name == "extract_domain":
            if "://" in str(value):
                return str(value).split("://")[1].split("/")[0]
            return str(value).split("/")[0]
        elif function_name == "phone_format":
            # Basic phone number formatting
            digits = ''.join(filter(str.isdigit, str(value)))
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            return value

        return value

    def _evaluate_condition(self, value: Any, operator: str, expected: Any) -> bool:
        """Evaluate a single condition"""
        if operator == "equals":
            return value == expected
        elif operator == "not_equals":
            return value != expected
        elif operator == "contains":
            return expected in str(value)
        elif operator == "not_contains":
            return expected not in str(value)
        elif operator == "greater_than":
            return float(value) > float(expected)
        elif operator == "less_than":
            return float(value) < float(expected)
        elif operator == "is_empty":
            return not value
        elif operator == "is_not_empty":
            return bool(value)

        return False

    def _convert_type(self, value: Any, target_type: FieldType) -> Any:
        """Convert value to target type"""
        if value is None:
            return None

        try:
            if target_type == FieldType.STRING:
                return str(value)
            elif target_type == FieldType.INTEGER:
                return int(float(value))
            elif target_type == FieldType.FLOAT:
                return float(value)
            elif target_type == FieldType.BOOLEAN:
                if isinstance(value, str):
                    return value.lower() in ['true', '1', 'yes', 'on']
                return bool(value)
            elif target_type == FieldType.DATE:
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
                elif isinstance(value, datetime):
                    return value.date().isoformat()
                return value
            elif target_type == FieldType.DATETIME:
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()
                elif isinstance(value, datetime):
                    return value.isoformat()
                return value
            elif target_type == FieldType.EMAIL:
                # Basic email validation
                email_str = str(value).lower()
                if '@' in email_str and '.' in email_str.split('@')[1]:
                    return email_str
                raise ValueError("Invalid email format")
            elif target_type == FieldType.URL:
                url_str = str(value)
                if not url_str.startswith(('http://', 'https://')):
                    return f"https://{url_str}"
                return url_str
            elif target_type == FieldType.JSON:
                if isinstance(value, str):
                    return json.loads(value)
                elif isinstance(value, (dict, list)):
                    return value
                else:
                    return json.loads(str(value))
            elif target_type == FieldType.ARRAY:
                if isinstance(value, str):
                    return [v.strip() for v in value.split(',')]
                elif isinstance(value, list):
                    return value
                else:
                    return [value]
            elif target_type == FieldType.OBJECT:
                if isinstance(value, dict):
                    return value
                elif isinstance(value, str):
                    return json.loads(value)
                else:
                    return {"value": value}

            return value
        except Exception as e:
            logger.error(f"Type conversion failed for {value} to {target_type}: {e}")
            raise

class IntegrationDataMapper:
    """Main data mapping system for integrations"""

    def __init__(self):
        self.transformer = DataTransformer()
        self.schemas: Dict[str, IntegrationSchema] = {}
        self.mappings: Dict[str, List[FieldMapping]] = {}  # mapping_id -> mappings
        self._initialize_default_schemas()

    def _initialize_default_schemas(self):
        """Initialize schemas for common integrations"""
        # Asana Task Schema
        self.schemas["asana_task"] = IntegrationSchema(
            integration_id="asana_task",
            integration_name="Asana Task",
            version="1.0",
            fields={
                "name": {"type": "string", "required": True, "description": "Task name"},
                "description": {"type": "string", "required": False, "description": "Task description"},
                "due_on": {"type": "date", "required": False, "description": "Due date"},
                "assignee": {"type": "string", "required": False, "description": "Assignee ID"},
                "projects": {"type": "array", "required": False, "description": "Project IDs"},
                "completed": {"type": "boolean", "required": False, "description": "Completion status"},
                "priority": {"type": "string", "required": False, "description": "Priority level"}
            },
            supported_operations=["create", "read", "update", "delete"],
            bulk_operations_supported=True,
            max_bulk_size=50
        )

        # Jira Issue Schema
        self.schemas["jira_issue"] = IntegrationSchema(
            integration_id="jira_issue",
            integration_name="Jira Issue",
            version="1.0",
            fields={
                "summary": {"type": "string", "required": True, "description": "Issue summary"},
                "description": {"type": "string", "required": False, "description": "Issue description"},
                "issue_type": {"type": "string", "required": True, "description": "Issue type"},
                "priority": {"type": "string", "required": False, "description": "Priority"},
                "assignee": {"type": "string", "required": False, "description": "Assignee"},
                "reporter": {"type": "string", "required": False, "description": "Reporter"},
                "status": {"type": "string", "required": False, "description": "Status"},
                "labels": {"type": "array", "required": False, "description": "Labels"},
                "components": {"type": "array", "required": False, "description": "Components"}
            },
            supported_operations=["create", "read", "update", "delete", "transition"],
            bulk_operations_supported=True,
            max_bulk_size=100
        )

        # Salesforce Lead Schema
        self.schemas["salesforce_lead"] = IntegrationSchema(
            integration_id="salesforce_lead",
            integration_name="Salesforce Lead",
            version="1.0",
            fields={
                "FirstName": {"type": "string", "required": False, "description": "First name"},
                "LastName": {"type": "string", "required": True, "description": "Last name"},
                "Email": {"type": "email", "required": False, "description": "Email address"},
                "Phone": {"type": "string", "required": False, "description": "Phone number"},
                "Company": {"type": "string", "required": False, "description": "Company"},
                "Title": {"type": "string", "required": False, "description": "Job title"},
                "LeadSource": {"type": "string", "required": False, "description": "Lead source"},
                "Status": {"type": "string", "required": False, "description": "Lead status"},
                "AnnualRevenue": {"type": "float", "required": False, "description": "Annual revenue"},
                "Industry": {"type": "string", "required": False, "description": "Industry"}
            },
            supported_operations=["create", "read", "update", "delete", "convert"],
            bulk_operations_supported=True,
            max_bulk_size=200
        )

    def register_schema(self, schema: IntegrationSchema):
        """Register a new integration schema"""
        self.schemas[schema.integration_id] = schema
        logger.info(f"Registered schema: {schema.integration_id}")

    def create_mapping(
        self,
        mapping_id: str,
        source_schema: str,
        target_schema: str,
        field_mappings: List[FieldMapping]
    ):
        """Create a mapping between two schemas"""
        # Validate schemas exist
        if source_schema not in self.schemas:
            raise ValueError(f"Source schema {source_schema} not found")
        if target_schema not in self.schemas:
            raise ValueError(f"Target schema {target_schema} not found")

        # Validate field mappings
        source_fields = set(self.schemas[source_schema].fields.keys())
        target_fields = set(self.schemas[target_schema].fields.keys())

        for mapping in field_mappings:
            if mapping.source_field not in source_fields and mapping.source_field != "constant":
                logger.warning(f"Source field {mapping.source_field} not in schema {source_schema}")
            if mapping.target_field not in target_fields:
                raise ValueError(f"Target field {mapping.target_field} not in schema {target_schema}")

        self.mappings[mapping_id] = field_mappings
        logger.info(f"Created mapping {mapping_id}: {source_schema} -> {target_schema}")

    def transform_data(
        self,
        source_data: Union[Dict, List[Dict]],
        mapping_id: str
    ) -> Union[Dict, List[Dict]]:
        """Transform data using mapping configuration"""
        if mapping_id not in self.mappings:
            raise ValueError(f"Mapping {mapping_id} not found")

        field_mappings = self.mappings[mapping_id]
        is_bulk = isinstance(source_data, list)

        if is_bulk:
            return [self._transform_single(item, field_mappings) for item in source_data]
        else:
            return self._transform_single(source_data, field_mappings)

    def _transform_single(self, source_data: Dict, field_mappings: List[FieldMapping]) -> Dict:
        """Transform a single data record"""
        transformed_data = {}

        for mapping in field_mappings:
            try:
                # Handle constant values
                if mapping.source_field == "constant":
                    value = mapping.transformation_config.get("constant_value")
                else:
                    value = source_data.get(mapping.source_field)

                transformed_value = self.transformer.transform_field(
                    value, mapping, source_data
                )
                transformed_data[mapping.target_field] = transformed_value

            except Exception as e:
                logger.error(f"Failed to transform field {mapping.source_field}: {e}")
                if mapping.required:
                    raise
                # Use default value or skip
                if mapping.default_value is not None:
                    transformed_data[mapping.target_field] = mapping.default_value

        return transformed_data

    def validate_data(self, data: Union[Dict, List[Dict]], schema_id: str) -> Dict[str, Any]:
        """Validate data against schema"""
        if schema_id not in self.schemas:
            raise ValueError(f"Schema {schema_id} not found")

        schema = self.schemas[schema_id]
        is_bulk = isinstance(data, list)
        items = data if is_bulk else [data]

        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "validated_count": len(items)
        }

        for i, item in enumerate(items):
            item_errors = []
            item_warnings = []

            for field_name, field_config in schema.fields.items():
                is_required = field_config.get("required", False)
                field_value = item.get(field_name)

                if is_required and (field_value is None or field_value == ""):
                    item_errors.append(f"Required field '{field_name}' is missing")
                elif field_value is not None:
                    # Type validation would go here
                    field_type = field_config.get("type")
                    try:
                        FieldType(field_type)  # Validate enum
                    except ValueError:
                        item_warnings.append(f"Unknown field type '{field_type}' for '{field_name}'")

            if item_errors:
                validation_results["valid"] = False
                validation_results["errors"].extend([
                    f"Item {i + 1}: {error}" for error in item_errors
                ])

            validation_results["warnings"].extend([
                f"Item {i + 1}: {warning}" for warning in item_warnings
            ])

        return validation_results

    def get_schema_info(self, schema_id: str) -> Optional[IntegrationSchema]:
        """Get schema information"""
        return self.schemas.get(schema_id)

    def list_schemas(self) -> List[str]:
        """List all registered schemas"""
        return list(self.schemas.keys())

    def list_mappings(self) -> List[str]:
        """List all registered mappings"""
        return list(self.mappings.keys())

    def export_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """Export mapping configuration"""
        if mapping_id not in self.mappings:
            raise ValueError(f"Mapping {mapping_id} not found")

        return {
            "mapping_id": mapping_id,
            "field_mappings": [asdict(mapping) for mapping in self.mappings[mapping_id]],
            "exported_at": datetime.now(timezone.utc).isoformat()
        }

    def import_mapping(self, mapping_config: Dict[str, Any]):
        """Import mapping configuration"""
        mapping_id = mapping_config["mapping_id"]
        field_mappings = [
            FieldMapping(**mapping_data)
            for mapping_data in mapping_config["field_mappings"]
        ]

        # Store mapping
        self.mappings[mapping_id] = field_mappings
        logger.info(f"Imported mapping: {mapping_id}")

# Global data mapper instance
_data_mapper = None

def get_data_mapper() -> IntegrationDataMapper:
    """Get the global data mapper instance"""
    global _data_mapper
    if _data_mapper is None:
        _data_mapper = IntegrationDataMapper()
    return _data_mapper