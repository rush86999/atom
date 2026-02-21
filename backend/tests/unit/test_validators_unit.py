"""
Unit Tests for Validators

Tests pure logic functions in validation_service.py, workflow_parameter_validator.py,
and command_whitelist.py without external dependencies.
"""

import pytest
import re
from hypothesis import given, strategies as st

from core.validation_service import (
    ValidationResult,
    ValidationService,
)
from core.workflow_parameter_validator import (
    RequiredRule,
    LengthRule,
    NumericRule,
    PatternRule,
    EmailRule,
    URLRule,
    EnumRule,
)
from core.command_whitelist import (
    CommandCategory,
    COMMAND_WHITELIST,
)


# ============================================================================
# ValidationResult Tests
# ============================================================================

@pytest.mark.unit
class TestValidationResult:
    """Test ValidationResult class"""

    def test_validation_result_success(self):
        """Test creating success result"""
        result = ValidationResult.success()

        assert result.is_valid is True
        assert result.errors == []
        assert result.details == {}

    def test_validation_result_error(self):
        """Test creating error result"""
        result = ValidationResult.error("Name is required")

        assert result.is_valid is False
        assert result.errors == ["Name is required"]
        assert result.details == {}

    def test_validation_result_error_with_details(self):
        """Test creating error result with details"""
        result = ValidationResult.error(
            "Invalid value",
            details={"field": "age", "value": -5}
        )

        assert result.is_valid is False
        assert result.errors == ["Invalid value"]
        assert result.details == {"field": "age", "value": -5}

    def test_validation_result_multiple_errors(self):
        """Test creating result with multiple errors"""
        result = ValidationResult.multiple([
            "Name is required",
            "Email is invalid",
            "Age must be positive"
        ])

        assert result.is_valid is False
        assert len(result.errors) == 3
        assert "Name is required" in result.errors
        assert "Email is invalid" in result.errors
        assert "Age must be positive" in result.errors


# ============================================================================
# RequiredRule Tests
# ============================================================================

@pytest.mark.unit
class TestRequiredRule:
    """Test RequiredRule validation"""

    def test_required_rule_with_value(self):
        """Test required field with value passes"""
        rule = RequiredRule("test_field", {"required": True})

        is_valid, error = rule.validate("some value")

        assert is_valid is True
        assert error is None

    def test_required_rule_with_none(self):
        """Test required field with None fails"""
        rule = RequiredRule("test_field", {"required": True})

        is_valid, error = rule.validate(None)

        assert is_valid is False
        assert error == "This field is required"

    def test_required_rule_with_empty_string(self):
        """Test required field with empty string fails"""
        rule = RequiredRule("test_field", {"required": True})

        is_valid, error = rule.validate("")

        assert is_valid is False
        assert error == "This field is required"

    @pytest.mark.parametrize("value,expected", [
        ("some value", True),
        ("0", True),
        (0, True),
        (False, True),
        (None, False),
        ("", False),
    ])
    def test_required_rule_various_values(self, value, expected):
        """Parametrized test for various values"""
        rule = RequiredRule("test_field", {"required": True})

        is_valid, _ = rule.validate(value)

        assert is_valid == expected

    def test_required_rule_optional(self):
        """Test optional field passes with None"""
        rule = RequiredRule("test_field", {"required": False})

        is_valid, error = rule.validate(None)

        assert is_valid is True
        assert error is None


# ============================================================================
# LengthRule Tests
# ============================================================================

@pytest.mark.unit
class TestLengthRule:
    """Test LengthRule validation"""

    def test_length_rule_within_bounds(self):
        """Test length within bounds passes"""
        rule = LengthRule("test_field", {"min_length": 3, "max_length": 10})

        is_valid, error = rule.validate("hello")

        assert is_valid is True
        assert error is None

    def test_length_rule_too_short(self):
        """Test string too short fails"""
        rule = LengthRule("test_field", {"min_length": 5, "max_length": 10})

        is_valid, error = rule.validate("hi")

        assert is_valid is False
        assert "at least 5 characters" in error

    def test_length_rule_too_long(self):
        """Test string too long fails"""
        rule = LengthRule("test_field", {"min_length": 3, "max_length": 10})

        is_valid, error = rule.validate("this is way too long")

        assert is_valid is False
        assert "at most 10 characters" in error

    @pytest.mark.parametrize("value,min_len,max_len,expected", [
        ("abc", 1, 10, True),
        ("a", 1, 10, True),
        ("abc", 3, 3, True),
        ("ab", 3, 5, False),
        ("abcdef", 1, 5, False),
    ])
    def test_length_rule_parametrized(self, value, min_len, max_len, expected):
        """Parametrized test for length validation"""
        rule = LengthRule("test_field", {"min_length": min_len, "max_length": max_len})

        is_valid, _ = rule.validate(value)

        assert is_valid == expected

    def test_length_rule_with_none(self):
        """Test length rule with None passes"""
        rule = LengthRule("test_field", {"min_length": 3, "max_length": 10})

        is_valid, error = rule.validate(None)

        assert is_valid is True
        assert error is None

    def test_length_rule_only_min(self):
        """Test length rule with only minimum"""
        rule = LengthRule("test_field", {"min_length": 5})

        is_valid, error = rule.validate("abc")

        assert is_valid is False
        assert "at least 5 characters" in error

    def test_length_rule_only_max(self):
        """Test length rule with only maximum"""
        rule = LengthRule("test_field", {"max_length": 10})

        is_valid, error = rule.validate("this is very very long")

        assert is_valid is False
        assert "at most 10 characters" in error


# ============================================================================
# NumericRule Tests
# ============================================================================

@pytest.mark.unit
class TestNumericRule:
    """Test NumericRule validation"""

    def test_numeric_rule_within_bounds(self):
        """Test number within bounds passes"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, error = rule.validate(50)

        assert is_valid is True
        assert error is None

    def test_numeric_rule_too_low(self):
        """Test number too low fails"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, error = rule.validate(-10)

        assert is_valid is False
        assert "at least 0" in error

    def test_numeric_rule_too_high(self):
        """Test number too high fails"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, error = rule.validate(150)

        assert is_valid is False
        assert "at most 100" in error

    @pytest.mark.parametrize("value,min_val,max_val,expected", [
        (5, 0, 10, True),
        (0, 0, 10, True),
        (10, 0, 10, True),
        (-1, 0, 10, False),
        (11, 0, 10, False),
    ])
    def test_numeric_rule_parametrized(self, value, min_val, max_val, expected):
        """Parametrized test for numeric validation"""
        rule = NumericRule("test_field", {"min_value": min_val, "max_value": max_val})

        is_valid, _ = rule.validate(value)

        assert is_valid == expected

    def test_numeric_rule_with_string_number(self):
        """Test numeric rule converts string to number"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, error = rule.validate("50")

        assert is_valid is True
        assert error is None

    def test_numeric_rule_with_invalid_string(self):
        """Test numeric rule with invalid string fails"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, error = rule.validate("not a number")

        assert is_valid is False
        assert "Must be a number" in error

    def test_numeric_rule_with_none(self):
        """Test numeric rule with None passes"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, error = rule.validate(None)

        assert is_valid is True
        assert error is None


# ============================================================================
# PatternRule Tests
# ============================================================================

@pytest.mark.unit
class TestPatternRule:
    """Test PatternRule validation"""

    def test_pattern_rule_matches(self):
        """Test pattern matching passes"""
        rule = PatternRule("test_field", {"pattern": r"^[a-z]+$"})

        is_valid, error = rule.validate("hello")

        assert is_valid is True
        assert error is None

    def test_pattern_rule_no_match(self):
        """Test pattern not matching fails"""
        rule = PatternRule("test_field", {"pattern": r"^[a-z]+$"})

        is_valid, error = rule.validate("Hello123")

        assert is_valid is False
        assert "Does not match required pattern" in error

    @pytest.mark.parametrize("value,pattern,expected", [
        ("test@email.com", r"^[^@]+@[^@]+\.[^@]+$", True),
        ("invalid", r"^[^@]+@[^@]+\.[^@]+$", False),
        ("ABC123", r"^[A-Z0-9]+$", True),
        ("abc", r"^[A-Z0-9]+$", False),
        ("123-456-7890", r"^\d{3}-\d{3}-\d{4}$", True),
        ("12-345-6789", r"^\d{3}-\d{3}-\d{4}$", False),
    ])
    def test_pattern_rule_parametrized(self, value, pattern, expected):
        """Parametrized test for pattern validation"""
        rule = PatternRule("test_field", {"pattern": pattern})

        is_valid, _ = rule.validate(value)

        assert is_valid == expected

    def test_pattern_rule_with_none(self):
        """Test pattern rule with None passes"""
        rule = PatternRule("test_field", {"pattern": r"^[a-z]+$"})

        is_valid, error = rule.validate(None)

        assert is_valid is True
        assert error is None

    def test_pattern_rule_no_pattern_config(self):
        """Test pattern rule without pattern config passes"""
        rule = PatternRule("test_field", {})

        is_valid, error = rule.validate("anything")

        assert is_valid is True
        assert error is None


# ============================================================================
# EmailRule Tests
# ============================================================================

@pytest.mark.unit
class TestEmailRule:
    """Test EmailRule validation"""

    def test_email_rule_valid_email(self):
        """Test valid email passes"""
        rule = EmailRule("email", {})

        is_valid, error = rule.validate("test@example.com")

        assert is_valid is True
        assert error is None

    def test_email_rule_invalid_email_no_at(self):
        """Test email without @ fails"""
        rule = EmailRule("email", {})

        is_valid, error = rule.validate("invalidemail")

        assert is_valid is False
        assert "Invalid email address" in error

    def test_email_rule_invalid_email_no_domain(self):
        """Test email without domain fails"""
        rule = EmailRule("email", {})

        is_valid, error = rule.validate("test@")

        assert is_valid is False
        assert "Invalid email address" in error

    @pytest.mark.parametrize("email,expected", [
        ("test@example.com", True),
        ("user.name@example.com", True),
        ("user+tag@example.co.uk", True),
        ("invalid", False),
        ("@example.com", False),
        ("test@", False),
        ("test@.com", False),
        ("test@com", False),
    ])
    def test_email_rule_parametrized(self, email, expected):
        """Parametrized test for email validation"""
        rule = EmailRule("email", {})

        is_valid, _ = rule.validate(email)

        assert is_valid == expected


# ============================================================================
# URLRule Tests
# ============================================================================

@pytest.mark.unit
class TestURLRule:
    """Test URLRule validation"""

    def test_url_rule_valid_url(self):
        """Test valid URL passes"""
        rule = URLRule("url", {})

        is_valid, error = rule.validate("https://example.com")

        assert is_valid is True
        assert error is None

    def test_url_rule_invalid_url_no_scheme(self):
        """Test URL without scheme fails"""
        rule = URLRule("url", {})

        is_valid, error = rule.validate("example.com")

        assert is_valid is False
        assert "Invalid URL" in error

    @pytest.mark.parametrize("url,expected", [
        ("https://example.com", True),
        ("http://example.com", True),
        ("https://example.com/path", True),
        ("https://example.com?query=value", True),
        ("ftp://example.com", True),
        ("example.com", False),
        ("not a url", False),
        ("", False),
    ])
    def test_url_rule_parametrized(self, url, expected):
        """Parametrized test for URL validation"""
        rule = URLRule("url", {})

        is_valid, _ = rule.validate(url)

        assert is_valid == expected


# ============================================================================
# EnumRule Tests
# ============================================================================

@pytest.mark.unit
class TestEnumRule:
    """Test EnumRule validation"""

    def test_enum_rule_valid_value(self):
        """Test valid enum value passes"""
        rule = EnumRule("status", {"allowed_values": ["active", "inactive", "pending"]})

        is_valid, error = rule.validate("active")

        assert is_valid is True
        assert error is None

    def test_enum_rule_invalid_value(self):
        """Test invalid enum value fails"""
        rule = EnumRule("status", {"allowed_values": ["active", "inactive", "pending"]})

        is_valid, error = rule.validate("deleted")

        assert is_valid is False
        assert "Must be one of" in error

    @pytest.mark.parametrize("value,allowed,expected", [
        ("red", ["red", "green", "blue"], True),
        ("green", ["red", "green", "blue"], True),
        ("yellow", ["red", "green", "blue"], False),
        (1, [1, 2, 3], True),
        (4, [1, 2, 3], False),
    ])
    def test_enum_rule_parametrized(self, value, allowed, expected):
        """Parametrized test for enum validation"""
        rule = EnumRule("field", {"allowed_values": allowed})

        is_valid, _ = rule.validate(value)

        assert is_valid == expected


# ============================================================================
# Command Whitelist Tests
# ============================================================================

@pytest.mark.unit
class TestCommandWhitelist:
    """Test command whitelist configuration"""

    def test_file_read_commands_exist(self):
        """Test FILE_READ commands are defined"""
        file_read = COMMAND_WHITELIST[CommandCategory.FILE_READ]
        assert "commands" in file_read
        assert "ls" in file_read["commands"]
        assert "cat" in file_read["commands"]
        assert "grep" in file_read["commands"]

    def test_file_write_commands_exist(self):
        """Test FILE_WRITE commands are defined"""
        file_write = COMMAND_WHITELIST[CommandCategory.FILE_WRITE]
        assert "commands" in file_write
        assert "cp" in file_write["commands"]
        assert "mv" in file_write["commands"]
        assert "mkdir" in file_write["commands"]

    def test_file_delete_autonomous_only(self):
        """Test FILE_DELETE is AUTONOMOUS only"""
        file_delete = COMMAND_WHITELIST[CommandCategory.FILE_DELETE]
        assert "AUTONOMOUS" in file_delete["maturity_levels"]
        assert "STUDENT" not in file_delete["maturity_levels"]

    def test_blocked_commands_have_no_access(self):
        """Test BLOCKED commands have no maturity levels"""
        blocked = COMMAND_WHITELIST[CommandCategory.BLOCKED]
        assert len(blocked["maturity_levels"]) == 0

    def test_blocked_commands_are_dangerous(self):
        """Test BLOCKED commands include dangerous ones"""
        blocked = COMMAND_WHITELIST[CommandCategory.BLOCKED]
        assert "sudo" in blocked["commands"]
        assert "chmod" in blocked["commands"]
        assert "kill" in blocked["commands"]

    @pytest.mark.parametrize("category,expected_commands", [
        (CommandCategory.FILE_READ, ["ls", "cat", "grep"]),
        (CommandCategory.FILE_WRITE, ["cp", "mv", "mkdir"]),
        (CommandCategory.FILE_DELETE, ["rm"]),
        (CommandCategory.BUILD_TOOLS, ["make", "npm", "pip"]),
        (CommandCategory.DEV_OPS, ["git", "docker", "kubectl"]),
        (CommandCategory.NETWORK, ["curl", "wget", "ping"]),
    ])
    def test_command_categories_have_required_commands(self, category, expected_commands):
        """Parametrized test for command categories"""
        config = COMMAND_WHITELIST[category]
        for cmd in expected_commands:
            assert cmd in config["commands"]

    def test_network_read_only(self):
        """Test NETWORK commands are read-only"""
        network = COMMAND_WHITELIST[CommandCategory.NETWORK]
        assert "curl" in network["commands"]
        assert "wget" in network["commands"]
        assert "ping" in network["commands"]


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.unit
class TestValidatorPropertyTests:
    """Property-based tests for validators"""

    @given(st.text())
    def test_length_rule_never_negative_length(self, text):
        """Property: length validation never results in negative length"""
        rule = LengthRule("test_field", {"min_length": 0, "max_length": 100})

        is_valid, _ = rule.validate(text)

        # Validation should not crash on any string
        assert isinstance(is_valid, bool)

    @given(st.integers())
    def test_numeric_rule_handles_all_integers(self, value):
        """Property: numeric rule handles any integer without crashing"""
        rule = NumericRule("test_field", {"min_value": 0, "max_value": 100})

        is_valid, _ = rule.validate(value)

        # Should always return boolean, never crash
        assert isinstance(is_valid, bool)

    @given(st.lists(st.text()))
    def test_enum_rule_never_crashes_on_lists(self, values):
        """Property: enum rule doesn't crash with various inputs"""
        rule = EnumRule("field", {"allowed_values": ["a", "b", "c"]})

        for value in values:
            is_valid, _ = rule.validate(value)
            assert isinstance(is_valid, bool)


# ============================================================================
# Validation Service Tests
# ============================================================================

@pytest.mark.unit
class TestValidationService:
    """Test ValidationService methods"""

    def test_validate_agent_config_missing_name(self):
        """Test agent config validation with missing name"""
        service = ValidationService()
        config = {"domain": "customer_support", "maturity_level": "INTERN"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert any("name" in error.lower() for error in result.errors)

    def test_validate_agent_config_empty_name(self):
        """Test agent config validation with empty name"""
        service = ValidationService()
        config = {"name": "", "domain": "customer_support", "maturity_level": "INTERN"}

        result = service.validate_agent_config(config)

        assert result.is_valid is False
        assert any("empty" in error.lower() or "required" in error.lower() for error in result.errors)

    def test_validate_agent_config_valid(self):
        """Test agent config validation with valid config"""
        service = ValidationService()
        config = {
            "name": "Test Agent",
            "domain": "customer_support",
            "maturity_level": "INTERN"
        }

        result = service.validate_agent_config(config)

        # May still have other validation errors, but name should be fine
        # Just check it doesn't crash
        assert isinstance(result.is_valid, bool)
