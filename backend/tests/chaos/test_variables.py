
import re
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# --- Mock Context ---
@dataclass
class WorkflowContext:
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)

# --- The Code Under Test (extracted from AdvancedWorkflowOrchestrator) ---
class VariableResolver:
    def _resolve_variables(self, value: Any, context: WorkflowContext) -> Any:
        """Resolve variables in a value (string, dict, or list)"""
        if isinstance(value, str):
            # Replace {{variable}} with value from context.variables
            matches = re.findall(r'\{\{([^}]+)\}\}', value)
            for match in matches:
                # Support nested access like {{step_id.key}}
                if '.' in match:
                    parts = match.split('.')
                    step_id = parts[0]
                    key = parts[1]
                    if step_id in context.results:
                        val = context.results[step_id].get(key, "")
                        value = value.replace(f"{{{{{match}}}}}", str(val))
                elif match in context.variables:
                    value = value.replace(f"{{{{{match}}}}}", str(context.variables[match]))
            return value
        elif isinstance(value, dict):
            return {k: self._resolve_variables(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_variables(v, context) for v in value]
        return value

class TestVariableResolution(unittest.TestCase):
    def setUp(self):
        self.resolver = VariableResolver()
        self.context = WorkflowContext()
        self.context.variables = {
            "user": "Alice",
            "count": 10,
            "nested_ptr": "user"
        }
        self.context.results = {
            "step_1": {"output": "Success", "id": 123}
        }

    def test_basic_resolution(self):
        """Test simple variable replacement"""
        result = self.resolver._resolve_variables("Hello {{user}}", self.context)
        print(f"\n[Test Basic] 'Hello {{{{user}}}}' -> '{result}'")
        self.assertEqual(result, "Hello Alice")

    def test_step_output_resolution(self):
        """Test accessing step results"""
        result = self.resolver._resolve_variables("ID: {{step_1.id}}", self.context)
        print(f"[Test Step] 'ID: {{{{step_1.id}}}}' -> '{result}'")
        self.assertEqual(result, "ID: 123")

    def test_undefined_variable(self):
        """Test variable that doesn't exist"""
        input_str = "Value: {{missing_var}}"
        result = self.resolver._resolve_variables(input_str, self.context)
        print(f"[Test Undefined] '{input_str}' -> '{result}'")
        # CURRENT BEHAVIOR: It likely leaves it as-is because the `if match in context.variables` check fails.
        # This confirms "Silent Failure" or "Leakage"
        self.assertEqual(result, input_str)

    def test_nested_curly_braces(self):
        """Test nested braces which Regex struggles with"""
        # Intent: Resolve {{nested_ptr}} to "user", then resolve {{user}} to "Alice"
        # Actual Regex: likely matches "nested_ptr}} to output {{user" or similar weirdness
        input_str = "Double: {{ {{nested_ptr}} }}" 
        result = self.resolver._resolve_variables(input_str, self.context)
        print(f"[Test Nested] '{input_str}' -> '{result}'")
        # This will almost certainly fail or produce garbage
        self.assertNotEqual(result, "Double: Alice")

    def test_partial_match_ambiguity(self):
        """Test when regex greedy match might fail"""
        input_str = "{{user}} and {{count}}"
        result = self.resolver._resolve_variables(input_str, self.context)
        print(f"[Test Multi] '{input_str}' -> '{result}'")
        self.assertEqual(result, "Alice and 10")

if __name__ == '__main__':
    unittest.main()
