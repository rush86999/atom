import os
import sys
import unittest

sys.path.append(os.getcwd())

from core.condition_evaluator import ConditionEvaluator, Operator


class TestPhase36ConditionalLogic(unittest.TestCase):

    def setUp(self):
        self.evaluator = ConditionEvaluator()
        self.context = {
            "step1_output": {
                "status": "success",
                "count": 42,
                "items": ["a", "b", "c"]
            },
            "user": {
                "name": "John",
                "role": "admin"
            },
            "empty_value": "",
            "null_value": None
        }

    def test_equals_operator(self):
        print("\n--- Phase 36: Equals Operator Test ---")
        
        result = self.evaluator.evaluate(
            {"left": "step1_output.status", "operator": "==", "right": "success"},
            self.context
        )
        self.assertTrue(result)
        
        result = self.evaluator.evaluate(
            {"left": "step1_output.status", "operator": "==", "right": "failed"},
            self.context
        )
        self.assertFalse(result)
        print("✅ Equals operator works")

    def test_comparison_operators(self):
        print("\n--- Phase 36: Comparison Operators Test ---")
        
        # Greater than
        self.assertTrue(self.evaluator.evaluate(
            {"variable": "step1_output.count", "operator": ">", "value": 40},
            self.context
        ))
        
        # Less than
        self.assertTrue(self.evaluator.evaluate(
            {"variable": "step1_output.count", "operator": "<", "value": 50},
            self.context
        ))
        
        print("✅ Comparison operators work")

    def test_contains_operator(self):
        print("\n--- Phase 36: Contains Operator Test ---")
        
        result = self.evaluator.evaluate(
            {"left": "user.name", "operator": "contains", "right": "oh"},
            self.context
        )
        self.assertTrue(result)
        print("✅ Contains operator works")

    def test_is_empty_operator(self):
        print("\n--- Phase 36: Is Empty Operator Test ---")
        
        self.assertTrue(self.evaluator.evaluate(
            {"left": "empty_value", "operator": "is_empty", "right": None},
            self.context
        ))
        
        self.assertFalse(self.evaluator.evaluate(
            {"left": "user.name", "operator": "is_empty", "right": None},
            self.context
        ))
        print("✅ Is empty operator works")

    def test_condition_group_and(self):
        print("\n--- Phase 36: Condition Group AND Test ---")
        
        result = self.evaluator.evaluate({
            "conditions": [
                {"left": "step1_output.status", "operator": "==", "right": "success"},
                {"left": "step1_output.count", "operator": ">", "right": 10}
            ],
            "logic": "AND"
        }, self.context)
        
        self.assertTrue(result)
        print("✅ AND logic works")

    def test_condition_group_or(self):
        print("\n--- Phase 36: Condition Group OR Test ---")
        
        result = self.evaluator.evaluate({
            "conditions": [
                {"left": "step1_output.status", "operator": "==", "right": "failed"},
                {"left": "user.role", "operator": "==", "right": "admin"}
            ],
            "logic": "OR"
        }, self.context)
        
        self.assertTrue(result)  # Second condition is true
        print("✅ OR logic works")

if __name__ == "__main__":
    unittest.main()
