"""
Workflow Parameter Validator
Advanced validation system for workflow inputs with dependencies and conditions
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class ValidationRule(ABC):
    """
    Base class for validation rules (Abstract).

    Concrete implementations must override the validate() method.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        """
        Validate a value against this rule.

        Subclasses must implement this method.

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

class RequiredRule(ValidationRule):
    """Required field validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        is_required = self.config.get("required", True)
        if is_required and (value is None or value == ""):
            return False, "This field is required"
        return True, None

class LengthRule(ValidationRule):
    """String length validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if value is None:
            return True, None

        str_value = str(value)
        min_length = self.config.get("min_length")
        max_length = self.config.get("max_length")

        if min_length and len(str_value) < min_length:
            return False, f"Must be at least {min_length} characters long"

        if max_length and len(str_value) > max_length:
            return False, f"Must be at most {max_length} characters long"

        return True, None

class NumericRule(ValidationRule):
    """Numeric range validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if value is None:
            return True, None

        try:
            num_value = float(value)
        except (ValueError, TypeError):
            return False, "Must be a number"

        min_value = self.config.get("min_value")
        max_value = self.config.get("max_value")

        if min_value is not None and num_value < min_value:
            return False, f"Must be at least {min_value}"

        if max_value is not None and num_value > max_value:
            return False, f"Must be at most {max_value}"

        return True, None

class PatternRule(ValidationRule):
    """Regex pattern validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if value is None:
            return True, None

        pattern = self.config.get("pattern")
        if not pattern:
            return True, None

        try:
            compiled_pattern = re.compile(pattern)
            if not compiled_pattern.match(str(value)):
                return False, self.config.get("message", "Invalid format")
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return False, "Validation error"

        return True, None

class EmailRule(ValidationRule):
    """Email format validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if value is None:
            return True, None

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, str(value)):
            return False, "Must be a valid email address"

        return True, None

class UrlRule(ValidationRule):
    """URL format validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if value is None:
            return True, None

        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, str(value)):
            return False, "Must be a valid URL"

        return True, None

class FileRule(ValidationRule):
    """File validation"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if value is None:
            return True, None

        # Check file type restrictions
        allowed_types = self.config.get("allowed_types", [])
        if allowed_types and hasattr(value, 'filename'):
            file_extension = value.filename.split('.')[-1].lower()
            if file_extension not in allowed_types:
                return False, f"File type not allowed. Allowed: {', '.join(allowed_types)}"

        # Check file size restrictions
        max_size = self.config.get("max_size_mb")
        if max_size and hasattr(value, 'size'):
            size_mb = value.size / (1024 * 1024)
            if size_mb > max_size:
                return False, f"File size too large. Maximum: {max_size}MB"

        return True, None

class ConditionalRule(ValidationRule):
    """Conditional validation based on other fields"""

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if not context:
            return True, None

        condition = self.config.get("condition")
        if not condition:
            return True, None

        # Simple condition format: {"field": "value", "operator": "equals"}
        field = condition.get("field")
        operator = condition.get("operator", "equals")
        expected = condition.get("value")

        if field not in context:
            return True, None  # Cannot validate condition, allow

        actual = context[field]
        condition_met = False

        if operator == "equals":
            condition_met = actual == expected
        elif operator == "not_equals":
            condition_met = actual != expected
        elif operator == "contains":
            condition_met = str(expected) in str(actual)
        elif operator == "greater_than":
            try:
                condition_met = float(actual) > float(expected)
            except (ValueError, TypeError):
                condition_met = False
        elif operator == "less_than":
            try:
                condition_met = float(actual) < float(expected)
            except (ValueError, TypeError):
                condition_met = False

        # If condition is met, validate the value
        if condition_met:
            validation_rules = self.config.get("validation_rules", [])
            for rule_config in validation_rules:
                rule = create_validation_rule("conditional", rule_config)
                is_valid, error = rule.validate(value, context)
                if not is_valid:
                    return False, error

        return True, None

class CustomRule(ValidationRule):
    """Custom validation using a function"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.validation_function = config.get("function")

    def validate(self, value: Any, context: Dict[str, Any] = None) -> tuple[bool, Optional[str]]:
        if not callable(self.validation_function):
            return True, None

        try:
            result = self.validation_function(value, context)
            if isinstance(result, tuple):
                return result
            return bool(result), None
        except Exception as e:
            logger.error(f"Custom validation function error: {e}")
            return False, "Validation error"

# Rule registry
RULE_REGISTRY = {
    "required": RequiredRule,
    "length": LengthRule,
    "numeric": NumericRule,
    "pattern": PatternRule,
    "email": EmailRule,
    "url": UrlRule,
    "file": FileRule,
    "conditional": ConditionalRule,
    "custom": CustomRule
}

def create_validation_rule(rule_name: str, config: Dict[str, Any]) -> ValidationRule:
    """Create a validation rule from configuration"""
    if rule_name not in RULE_REGISTRY:
        raise ValueError(f"Unknown validation rule: {rule_name}")

    rule_class = RULE_REGISTRY[rule_name]
    return rule_class(rule_name, config)

class WorkflowParameterValidator:
    """Main validator for workflow parameters"""

    def __init__(self):
        self.global_validators = {}
        self.field_validators = {}

    def register_global_validator(self, name: str, config: Dict[str, Any]):
        """Register a global validator that applies to all fields"""
        self.global_validators[name] = create_validation_rule(name, config)

    def register_field_validator(self, field_name: str, rule_name: str, config: Dict[str, Any]):
        """Register a validator for a specific field"""
        if field_name not in self.field_validators:
            self.field_validators[field_name] = {}
        self.field_validators[field_name][rule_name] = create_validation_rule(rule_name, config)

    def validate_parameters(
        self,
        parameters: Dict[str, Dict[str, Any]],
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate all parameters against inputs"""
        results = {
            "valid": True,
            "errors": {},
            "warnings": {},
            "validated_inputs": inputs.copy()
        }

        if context is None:
            context = inputs.copy()

        # Validate each parameter
        for param_name, param_config in parameters.items():
            param_result = self._validate_parameter(param_name, param_config, inputs.get(param_name), context)

            if not param_result["valid"]:
                results["valid"] = False

            if param_result.get("errors"):
                results["errors"][param_name] = param_result["errors"]

            if param_result.get("warnings"):
                results["warnings"][param_name] = param_result["warnings"]

            if param_result.get("transformed_value") is not None:
                results["validated_inputs"][param_name] = param_result["transformed_value"]

        return results

    def _validate_parameter(
        self,
        param_name: str,
        param_config: Dict[str, Any],
        value: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a single parameter"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "transformed_value": None
        }

        # Check if parameter should be validated based on conditions
        if not self._should_validate_parameter(param_config, context):
            return result

        # Apply global validators
        for rule_name, rule in self.global_validators.items():
            is_valid, error_msg = rule.validate(value, context)
            if not is_valid:
                result["valid"] = False
                result["errors"].append(error_msg)

        # Apply field-specific validators
        if param_name in self.field_validators:
            for rule_name, rule in self.field_validators[param_name].items():
                is_valid, error_msg = rule.validate(value, context)
                if not is_valid:
                    result["valid"] = False
                    result["errors"].append(error_msg)

        # Apply parameter-specific validation rules
        validation_rules = param_config.get("validation_rules", [])
        for rule_config in validation_rules:
            rule_name = rule_config.get("type")
            if not rule_name:
                continue

            try:
                rule = create_validation_rule(rule_name, rule_config)
                is_valid, error_msg = rule.validate(value, context)
                if not is_valid:
                    result["valid"] = False
                    result["errors"].append(error_msg)
            except Exception as e:
                logger.error(f"Error creating validation rule {rule_name}: {e}")
                result["errors"].append(f"Validation error for rule {rule_name}")

        # Apply data type transformation
        param_type = param_config.get("type", "string")
        transformed_value = self._transform_value(value, param_type)
        if transformed_value is not None:
            result["transformed_value"] = transformed_value

        return result

    def _should_validate_parameter(self, param_config: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check if parameter should be validated based on show_when conditions"""
        show_when = param_config.get("show_when")
        if not show_when:
            return True

        # Simple condition evaluation
        for field_name, condition in show_when.items():
            if field_name not in context:
                return False

            if isinstance(condition, dict):
                for operator, expected in condition.items():
                    actual = context[field_name]
                    if operator == "equals" and actual != expected:
                        return False
                    elif operator == "not_equals" and actual == expected:
                        return False
                    elif operator == "contains" and expected not in str(actual):
                        return False
            else:
                if context[field_name] != condition:
                    return False

        return True

    def _transform_value(self, value: Any, param_type: str) -> Any:
        """Transform value to the specified type"""
        try:
            if param_type == "string":
                return str(value)
            elif param_type == "number":
                return float(value)
            elif param_type == "boolean":
                if isinstance(value, str):
                    return value.lower() in ["true", "1", "yes", "on"]
                return bool(value)
            elif param_type == "array":
                if isinstance(value, str):
                    return json.loads(value)
                return list(value)
            elif param_type == "object":
                if isinstance(value, str):
                    return json.loads(value)
                return dict(value)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass

        return value

    def get_missing_required_parameters(
        self,
        parameters: Dict[str, Dict[str, Any]],
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get list of missing required parameters"""
        missing = []

        if context is None:
            context = inputs.copy()

        for param_name, param_config in parameters.items():
            # Check if parameter is required
            is_required = param_config.get("required", True)
            if not is_required:
                continue

            # Check if parameter should be shown
            if not self._should_validate_parameter(param_config, context):
                continue

            # Check if value is provided
            if param_name not in inputs or inputs[param_name] in [None, "", []]:
                missing.append({
                    "name": param_name,
                    "label": param_config.get("label", param_name),
                    "description": param_config.get("description", ""),
                    "type": param_config.get("type", "string"),
                    "default_value": param_config.get("default_value"),
                    "options": param_config.get("options", [])
                })

        return missing

# Predefined validation rule sets
def create_email_validation_rules() -> List[Dict[str, Any]]:
    """Create email validation rules"""
    return [
        {"type": "required"},
        {"type": "length", "max_length": 254},
        {"type": "email"}
    ]

def create_url_validation_rules() -> List[Dict[str, Any]]:
    """Create URL validation rules"""
    return [
        {"type": "required"},
        {"type": "url"},
        {"type": "length", "max_length": 2048}
    ]

def create_password_validation_rules() -> List[Dict[str, Any]]:
    """Create password validation rules"""
    return [
        {"type": "required"},
        {"type": "length", "min_length": 8, "max_length": 128},
        {"type": "pattern", "pattern": r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+",
         "message": "Password must contain at least one lowercase letter, one uppercase letter, and one digit"}
    ]

def create_phone_validation_rules() -> List[Dict[str, Any]]:
    """Create phone number validation rules"""
    return [
        {"type": "required"},
        {"type": "pattern",
         "pattern": r"^\+?[\d\s\-\(\)]{10,}$",
         "message": "Please enter a valid phone number"}
    ]

def create_number_validation_rules(min_value: float = None, max_value: float = None) -> List[Dict[str, Any]]:
    """Create numeric validation rules"""
    rules = [{"type": "numeric"}]
    if min_value is not None:
        rules.append({"type": "numeric", "min_value": min_value})
    if max_value is not None:
        rules.append({"type": "numeric", "max_value": max_value})
    return rules

def create_file_validation_rules(
    allowed_types: List[str] = None,
    max_size_mb: int = None
) -> List[Dict[str, Any]]:
    """Create file validation rules"""
    rules = [{"type": "file"}]
    if allowed_types:
        rules.append({"type": "file", "allowed_types": allowed_types})
    if max_size_mb:
        rules.append({"type": "file", "max_size_mb": max_size_mb})
    return rules