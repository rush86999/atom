"""
Schema Validator

JSON Schema Draft 2020-12 validation for entity type definitions.
"""
from jsonschema import Draft202012Validator, validate, ValidationError as JSONSchemaValidationError
from typing import Dict, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validate JSON Schema definitions against Draft 2020-12 meta-schema.
    """

    MAX_DEPTH = 10
    MAX_PROPERTIES = 100

    def __init__(self):
        self.validator_cls = Draft202012Validator

    def validate_schema(self, schema: Dict) -> Tuple[bool, str]:
        """
        Validate schema against Draft 2020-12 meta-schema.
        """
        try:
            if "$schema" not in schema:
                schema = {**schema, "$schema": "https://json-schema.org/draft/2020-12/schema"}
            
            self.validator_cls.check_schema(schema)
            return True, ""
        except JSONSchemaValidationError as e:
            return False, f"Schema validation failed: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error validating schema: {e}")
            return False, f"Validation error: {str(e)}"

    def validate_instance(self, instance: Dict, schema: Dict) -> Tuple[bool, str]:
        """Validate instance data against schema."""
        try:
            validate(instance=instance, schema=schema)
            return True, ""
        except JSONSchemaValidationError as e:
            return False, f"Instance validation failed: {e.message}"
        except Exception as e:
            logger.error(f"Unexpected error validating instance: {e}")
            return False, f"Validation error: {str(e)}"


# Global validator instance
_schema_validator: SchemaValidator = None

def get_schema_validator() -> SchemaValidator:
    global _schema_validator
    if _schema_validator is None:
        _schema_validator = SchemaValidator()
    return _schema_validator
