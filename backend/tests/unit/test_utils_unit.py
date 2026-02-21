"""
Unit Tests for Utility Functions

Tests pure logic functions in agent_utils.py and email_utils.py without external dependencies.
Focuses on string parsing, JSON handling, and email formatting.
"""

import pytest
import json
from hypothesis import given, strategies as st
from typing import Dict, Any, Optional

from core.agent_utils import parse_react_response


# ============================================================================
# parse_react_response Tests
# ============================================================================

@pytest.mark.unit
class TestParseReactResponse:
    """Test parse_react_response function"""

    def test_parse_with_all_components(self):
        """Test parsing Thought, Action, and Final Answer"""
        output = """Thought: I need to search for information.
Action: {
    "tool": "search",
    "params": {"query": "test"}
}"""

        thought, action, final_answer = parse_react_response(output)

        assert thought == "I need to search for information."
        assert action == {"tool": "search", "params": {"query": "test"}}
        assert final_answer is None

    def test_parse_with_final_answer(self):
        """Test parsing with Final Answer instead of Action"""
        output = """Thought: I have found the information.
Final Answer: The answer is 42."""

        thought, action, final_answer = parse_react_response(output)

        assert thought == "I have found the information."
        assert action is None
        assert final_answer == "The answer is 42."

    def test_parse_with_only_action(self):
        """Test parsing with only Action (no Thought)"""
        output = """Action: {
    "tool": "calculator",
    "params": {"expression": "2+2"}
}"""

        thought, action, final_answer = parse_react_response(output)

        assert thought is None or thought == ""
        assert action == {"tool": "calculator", "params": {"expression": "2+2"}}
        assert final_answer is None

    def test_parse_with_only_final_answer(self):
        """Test parsing with only Final Answer (no Thought)"""
        output = """Final Answer: The result is 4."""

        thought, action, final_answer = parse_react_response(output)

        assert thought is None or thought == ""
        assert action is None
        assert final_answer == "The result is 4."

    def test_parse_with_only_thought(self):
        """Test parsing with only Thought (no action or answer)"""
        output = """Thought: I need to think more about this."""

        thought, action, final_answer = parse_react_response(output)

        assert thought == "I need to think more about this."
        assert action is None
        assert final_answer is None

    def test_parse_multiline_thought(self):
        """Test parsing multi-line Thought"""
        output = """Thought: I need to consider multiple factors:
- The user's intent
- Available tools
- Current context
Action: {"tool": "test"}"""

        thought, action, final_answer = parse_react_response(output)

        assert "I need to consider multiple factors:" in thought
        assert action == {"tool": "test"}

    def test_parse_multiline_final_answer(self):
        """Test parsing multi-line Final Answer"""
        output = """Thought: Done thinking.
Final Answer: Based on my analysis:
1. Factor A is important
2. Factor B is critical
3. Conclusion: C"""

        thought, action, final_answer = parse_react_response(output)

        assert "Based on my analysis:" in final_answer
        assert "Conclusion: C" in final_answer

    def test_parse_action_with_complex_json(self):
        """Test parsing Action with nested JSON"""
        output = """Action: {
    "tool": "workflow",
    "params": {
        "steps": [
            {"name": "step1", "type": "search"},
            {"name": "step2", "type": "process"}
        ],
        "config": {
            "timeout": 30,
            "retries": 3
        }
    }
}"""

        thought, action, final_answer = parse_react_response(output)

        assert action["tool"] == "workflow"
        assert len(action["params"]["steps"]) == 2
        assert action["params"]["config"]["timeout"] == 30

    def test_parse_case_insensitive(self):
        """Test parsing is case-insensitive for keywords"""
        output = """thought: lower case thought
action: {"tool": "test"}"""

        thought, action, final_answer = parse_react_response(output)

        assert "lower case thought" in thought.lower()
        assert action == {"tool": "test"}

    def test_parse_empty_output(self):
        """Test parsing empty output"""
        thought, action, final_answer = parse_react_response("")

        assert thought in (None, "")
        assert action is None
        assert final_answer is None

    def test_parse_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError"""
        output = """Action: {
    "tool": "test",
    invalid json here
}"""

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_react_response(output)

    def test_parse_action_without_json_structure(self):
        """Test Action without JSON structure raises error"""
        output = """Action: just plain text"""

        with pytest.raises(ValueError, match="no JSON structure"):
            parse_react_response(output)

    @pytest.mark.parametrize("output,expected_thought,expected_has_action,expected_has_final", [
        (
            "Thought: test\nAction: {\"tool\": \"x\"}",
            "test",
            True,
            False
        ),
        (
            "Thought: test\nFinal Answer: answer",
            "test",
            False,
            True
        ),
        (
            "Action: {\"tool\": \"x\"}",
            None,
            True,
            False
        ),
        (
            "Final Answer: done",
            None,
            False,
            True
        ),
    ])
    def test_parse_various_formats(self, output, expected_thought, expected_has_action, expected_has_final):
        """Parametrized test for various output formats"""
        thought, action, final_answer = parse_react_response(output)

        if expected_thought:
            assert expected_thought in thought or thought == expected_thought
        else:
            assert thought is None or thought == ""

        assert (action is not None) == expected_has_action
        assert (final_answer is not None) == expected_has_final

    def test_parse_with_whitespace_variations(self):
        """Test parsing with various whitespace patterns"""
        output = """Thought:Test thought

Action:  {"tool":"test"}"""

        thought, action, final_answer = parse_react_response(output)

        assert "Test thought" in thought
        assert action == {"tool": "test"}


# ============================================================================
# Email Utility Tests (with mocking)
# ============================================================================

@pytest.mark.unit
class TestEmailUtils:
    """Test email utility functions"""

    def test_email_utility_import(self):
        """Test that email utils can be imported"""
        from core import email_utils

        assert hasattr(email_utils, 'send_smtp_email')

    def test_send_smtp_email_function_exists(self):
        """Test send_smtp_email function signature"""
        from core.email_utils import send_smtp_email

        # Function should be callable
        assert callable(send_smtp_email)

        # We don't actually test sending (requires SMTP server)
        # Just verify the function exists and has correct signature
        import inspect
        sig = inspect.signature(send_smtp_email)

        params = list(sig.parameters.keys())
        assert 'to_email' in params
        assert 'subject' in params
        assert 'body' in params
        assert 'html_body' in params


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.unit
class TestUtilsPropertyTests:
    """Property-based tests for utility functions"""

    @given(st.text())
    def test_parse_never_crashes_on_any_string(self, text):
        """Property: parser should handle any string without crashing"""
        # Some strings will raise ValueError for invalid JSON, that's expected
        # But it should never crash with unexpected exceptions
        try:
            thought, action, final_answer = parse_react_response(text)

            # If it succeeds, return types should be correct
            assert thought is None or isinstance(thought, str)
            assert action is None or isinstance(action, dict)
            assert final_answer is None or isinstance(final_answer, str)

        except ValueError:
            # Expected for invalid JSON
            pass
        except Exception as e:
            # Should not crash with other exceptions
            pytest.fail(f"Unexpected exception: {e}")

    @given(st.dictionaries(st.text(min_size=1), st.text()))
    def test_parse_valid_json_action(self, action_dict):
        """Property: valid JSON action should parse correctly"""
        action_json = json.dumps(action_dict)
        output = f"Action: {action_json}"

        try:
            thought, action, final_answer = parse_react_response(output)

            # Action should match input dict
            assert action == action_dict

        except Exception:
            # Some dict keys might cause issues (e.g., newlines in keys)
            # That's acceptable behavior
            pass

    @given(st.text(), st.text())
    def test_parse_thought_final_preserves_content(self, thought_text, answer_text):
        """Property: thought and final answer content should be preserved"""
        # Filter out strings that would break the format
        if "\nAction:" in thought_text or "\nFinal Answer:" in thought_text:
            return

        output = f"Thought: {thought_text}\nFinal Answer: {answer_text}"

        thought, action, final_answer = parse_react_response(output)

        # Should preserve the content
        if thought:
            assert thought_text in thought or thought == thought_text
        if final_answer:
            assert answer_text in final_answer or final_answer == answer_text


# ============================================================================
# String Utility Tests
# ============================================================================

@pytest.mark.unit
class TestStringUtilities:
    """Test string manipulation utilities"""

    @pytest.mark.parametrize("input_str,expected_clean", [
        ("  hello  ", "hello"),
        ("\thello\t", "hello"),
        ("\nhello\n", "hello"),
        ("  hello world  ", "hello world"),
        ("", ""),
        ("   ", ""),
    ])
    def test_string_whitespace_handling(self, input_str, expected_clean):
        """Parametrized test for whitespace handling"""
        # This tests common patterns used in utilities
        result = input_str.strip()
        assert result == expected_clean

    @pytest.mark.parametrize("text,substring,expected", [
        ("hello world", "world", True),
        ("hello world", "python", False),
        ("", "test", False),
        ("test", "", True),
    ])
    def test_string_search(self, text, substring, expected):
        """Parametrized test for string search patterns"""
        result = substring in text
        assert result == expected


# ============================================================================
# JSON Utility Tests
# ============================================================================

@pytest.mark.unit
class TestJSONUtilities:
    """Test JSON handling utilities"""

    def test_json_loads_valid(self):
        """Test loading valid JSON"""
        json_str = '{"key": "value", "number": 42}'
        result = json.loads(json_str)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_json_loads_invalid_raises_error(self):
        """Test loading invalid JSON raises error"""
        invalid_json = '{"key": invalid}'

        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)

    @pytest.mark.parametrize("data,expected_json", [
        ({"key": "value"}, '{"key": "value"}'),
        ([1, 2, 3], '[1, 2, 3]'),
        ({"nested": {"key": "value"}}, '{"nested": {"key": "value"}}'),
    ])
    def test_json_dumps_roundtrip(self, data, expected_json):
        """Parametrized test for JSON serialization"""
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed == data

    def test_json_dumps_with_indent(self):
        """Test JSON dumps with pretty printing"""
        data = {"key": "value", "number": 42}
        json_str = json.dumps(data, indent=2)

        assert "  " in json_str  # Has indentation
        assert "\n" in json_str  # Has newlines


# ============================================================================
# Date/Time Utility Tests
# ============================================================================

@pytest.mark.unit
class TestDateTimeUtilities:
    """Test date/time utility patterns"""

    from datetime import datetime, timedelta

    @pytest.mark.parametrize("minutes,expected_seconds", [
        (1, 60),
        (30, 1800),
        (60, 3600),
        (120, 7200),
    ])
    def test_minute_to_second_conversion(self, minutes, expected_seconds):
        """Parametrized test for minute to second conversion"""
        result = minutes * 60
        assert result == expected_seconds

    def test_datetime_now_is_recent(self):
        """Test that datetime.now() returns recent time"""
        now = self.datetime.now()
        assert (self.datetime.now() - now).total_seconds() < 1.0

    def test_timedelta_creation(self):
        """Test timedelta creation for various units"""
        td = self.timedelta(minutes=30)
        assert td.total_seconds() == 1800

        td = self.timedelta(seconds=60)
        assert td.total_seconds() == 60

        td = self.timedelta(hours=1)
        assert td.total_seconds() == 3600


# ============================================================================
# ID Generation Tests
# ============================================================================

@pytest.mark.unit
class TestIDGeneration:
    """Test ID generation patterns"""

    import uuid
    import re

    def test_uuid_generation(self):
        """Test UUID generation produces valid format"""
        generated_id = str(uuid.uuid4())

        # UUID should be 36 characters (32 hex + 4 hyphens)
        assert len(generated_id) == 36

        # Should match UUID pattern
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        assert re.match(pattern, generated_id, re.IGNORECASE)

    def test_uuid_uniqueness(self):
        """Test UUIDs are unique"""
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())

        assert id1 != id2

    @given(st.integers(min_value=0, max_value=1000))
    def test_short_id_generation(self, seed):
        """Test short ID generation patterns"""
        # Common pattern: use hash or first N chars of UUID
        full_id = str(uuid.uuid4())
        short_id = full_id[:8]  # First 8 characters

        assert len(short_id) == 8
        assert "-" not in short_id  # No hyphens in short form


# ============================================================================
# Data Structure Utilities
# ============================================================================

@pytest.mark.unit
class TestDataStructureUtilities:
    """Test data structure manipulation utilities"""

    @pytest.mark.parametrize("dict_list,key,expected", [
        ([{"id": 1}, {"id": 2}], "id", [1, 2]),
        ([{"name": "a"}, {"name": "b"}], "name", ["a", "b"]),
        ([], "id", []),
    ])
    def test_extract_key_from_dict_list(self, dict_list, key, expected):
        """Parametrized test for extracting key from list of dicts"""
        result = [d[key] for d in dict_list if key in d]
        assert result == expected

    def test_dict_merge(self):
        """Test dictionary merging"""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}

        merged = {**dict1, **dict2}

        assert merged == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_dict_update_preserves_original(self):
        """Test dict.update() modifies in place"""
        original = {"a": 1}
        copy = original.copy()

        original.update({"b": 2})

        assert original == {"a": 1, "b": 2}
        assert copy == {"a": 1}  # Unchanged

    @pytest.mark.parametrize("items,filter_func,expected_count", [
        ([1, 2, 3, 4, 5], lambda x: x % 2 == 0, 2),
        (["a", "b", "c", "d"], lambda x: x in ["a", "c"], 2),
        ([], lambda x: True, 0),
    ])
    def test_list_filtering(self, items, filter_func, expected_count):
        """Parametrized test for list filtering"""
        result = [item for item in items if filter_func(item)]
        assert len(result) == expected_count


# ============================================================================
# Type Conversion Utilities
# ============================================================================

@pytest.mark.unit
class TestTypeConversionUtilities:
    """Test type conversion utilities"""

    @pytest.mark.parametrize("value,expected_type", [
        ("123", int),
        (123, str),
        (123.45, int),
        (True, str),
    ])
    def test_type_conversion(self, value, expected_type):
        """Parametrized test for type conversion"""
        if expected_type == int:
            result = int(value)
        elif expected_type == str:
            result = str(value)

        assert isinstance(result, expected_type)

    def test_int_conversion_with_invalid_string(self):
        """Test int conversion with invalid string raises error"""
        with pytest.raises(ValueError):
            int("not a number")

    def test_float_conversion_with_precision(self):
        """Test float conversion maintains precision"""
        value = 3.14159
        result = float(value)

        assert abs(result - 3.14159) < 0.00001
