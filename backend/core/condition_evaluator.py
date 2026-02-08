"""
Condition Evaluator - Phase 36
Evaluates conditional expressions for workflow branching.
"""

from dataclasses import dataclass
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class Operator(Enum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    IN = "in"

@dataclass
class Condition:
    """Single condition expression"""
    left: str  # Variable path, e.g., "step1_output.status"
    operator: Operator
    right: Any  # Value to compare against
    
    def __str__(self):
        return f"{self.left} {self.operator.value} {self.right}"

@dataclass
class ConditionGroup:
    """Group of conditions with logical operator"""
    conditions: List[Condition]
    logic: str = "AND"  # AND | OR

class ConditionEvaluator:
    """
    Evaluates conditional expressions against workflow context.
    """
    
    def evaluate(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition dict against context.
        
        Supports:
        - Simple: {"left": "status", "operator": "==", "right": "success"}
        - Nested: {"variable": "step1_output.count", "operator": ">", "value": 10}
        - Groups: {"conditions": [...], "logic": "AND"}
        """
        
        # Handle condition groups
        if "conditions" in condition:
            return self._evaluate_group(condition, context)
        
        # Handle simple condition
        left_path = condition.get("left") or condition.get("variable") or condition.get("field")
        operator_str = condition.get("operator", "==")
        right_value = condition.get("right") or condition.get("value")
        
        if not left_path:
            logger.warning("Condition missing left/variable/field")
            return False
        
        # Resolve left value from context
        left_value = self._resolve_path(left_path, context)
        
        # Get operator
        try:
            operator = self._parse_operator(operator_str)
        except ValueError:
            logger.warning(f"Unknown operator: {operator_str}")
            return False
        
        # Evaluate
        return self._compare(left_value, operator, right_value)
    
    def _evaluate_group(self, group: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a group of conditions with AND/OR logic"""
        conditions = group.get("conditions", [])
        logic = group.get("logic", "AND").upper()
        
        if not conditions:
            return True
        
        results = [self.evaluate(c, context) for c in conditions]
        
        if logic == "AND":
            return all(results)
        elif logic == "OR":
            return any(results)
        else:
            return all(results)
    
    def _resolve_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Resolve a dot-notation path to a value in context"""
        parts = path.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value
    
    def _parse_operator(self, op_str: str) -> Operator:
        """Parse operator string to Operator enum"""
        op_map = {
            "==": Operator.EQUALS,
            "=": Operator.EQUALS,
            "!=": Operator.NOT_EQUALS,
            "<>": Operator.NOT_EQUALS,
            ">": Operator.GREATER_THAN,
            "<": Operator.LESS_THAN,
            ">=": Operator.GREATER_EQUAL,
            "<=": Operator.LESS_EQUAL,
            "contains": Operator.CONTAINS,
            "not_contains": Operator.NOT_CONTAINS,
            "matches": Operator.MATCHES,
            "is_empty": Operator.IS_EMPTY,
            "is_not_empty": Operator.IS_NOT_EMPTY,
            "in": Operator.IN,
        }
        
        if op_str.lower() in op_map:
            return op_map[op_str.lower()]
        raise ValueError(f"Unknown operator: {op_str}")
    
    def _compare(self, left: Any, operator: Operator, right: Any) -> bool:
        """Compare two values with given operator"""
        try:
            if operator == Operator.EQUALS:
                return left == right
            elif operator == Operator.NOT_EQUALS:
                return left != right
            elif operator == Operator.GREATER_THAN:
                return float(left) > float(right)
            elif operator == Operator.LESS_THAN:
                return float(left) < float(right)
            elif operator == Operator.GREATER_EQUAL:
                return float(left) >= float(right)
            elif operator == Operator.LESS_EQUAL:
                return float(left) <= float(right)
            elif operator == Operator.CONTAINS:
                return str(right) in str(left)
            elif operator == Operator.NOT_CONTAINS:
                return str(right) not in str(left)
            elif operator == Operator.MATCHES:
                return bool(re.match(str(right), str(left)))
            elif operator == Operator.IS_EMPTY:
                return not left or (isinstance(left, (list, dict, str)) and len(left) == 0)
            elif operator == Operator.IS_NOT_EMPTY:
                return bool(left) and (not isinstance(left, (list, dict, str)) or len(left) > 0)
            elif operator == Operator.IN:
                return left in right if isinstance(right, (list, tuple, set)) else False
            else:
                return False
        except (ValueError, TypeError) as e:
            logger.warning(f"Comparison error: {e}")
            return False

# Global instance
condition_evaluator = ConditionEvaluator()
