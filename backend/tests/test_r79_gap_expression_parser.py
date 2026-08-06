# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/expression_parser.py (safe conditional-breakpoint
expression evaluator; zero test references before this file).

TDD targets (RED first):
- Documented "dot notation" variable access (e.g. ``user.age > 30``) evaluated
  to False instead of resolving — the identifier tokenizer lumps ``a.b`` into
  one token that was only looked up verbatim.
- Documented "indexing" access (e.g. ``data[0] > 10``) also evaluated to False.
- Baseline: arithmetic/comparison/logical/membership/identity + safety
  guarantees (no function calls, no import, undefined vars -> False).
"""
from __future__ import annotations

import pytest

from core.expression_parser import (
    ExpressionEvaluator,
    ExpressionParser,
    get_expression_evaluator,
)


@pytest.fixture()
def evaluator():
    return ExpressionEvaluator()


class TestBasics:
    def test_comparison_true(self, evaluator):
        assert evaluator.evaluate("x > 5", {"x": 10}) is True

    def test_comparison_false(self, evaluator):
        assert evaluator.evaluate("x > 5", {"x": 3}) is False

    def test_arithmetic_precedence(self, evaluator):
        assert evaluator.evaluate("2 + 3 * 4 == 14", {}) is True

    def test_modulo_and_power(self, evaluator):
        assert evaluator.evaluate("10 % 3 == 1", {}) is True
        assert evaluator.evaluate("2 ** 8 == 256", {}) is True

    def test_logical_and_or_not(self, evaluator):
        assert evaluator.evaluate("a and b", {"a": True, "b": True}) is True
        assert evaluator.evaluate("a and b", {"a": True, "b": False}) is False
        assert evaluator.evaluate("a or b", {"a": False, "b": True}) is True
        assert evaluator.evaluate("not a", {"a": False}) is True

    def test_membership(self, evaluator):
        assert evaluator.evaluate("'x' in items", {"items": ["x", "y"]}) is True
        assert evaluator.evaluate("'z' in items", {"items": ["x", "y"]}) is False

    def test_identity_is_none(self, evaluator):
        assert evaluator.evaluate("x is None", {"x": None}) is True
        assert evaluator.evaluate("x is not None", {"x": 1}) is True

    def test_parenthesized_grouping(self, evaluator):
        assert evaluator.evaluate("(1 + 2) * 3 == 9", {}) is True

    def test_string_and_boolean_literals(self, evaluator):
        assert evaluator.evaluate("name == 'ada'", {"name": "ada"}) is True
        assert evaluator.evaluate("flag", {"flag": True}) is True

    def test_scientific_notation_number(self, evaluator):
        assert evaluator.evaluate("1e3 == 1000", {}) is True

    def test_empty_expression_is_false(self, evaluator):
        assert evaluator.evaluate("   ", {}) is False

    def test_undefined_variable_is_false(self, evaluator):
        assert evaluator.evaluate("missing > 1", {}) is False

    def test_unbalanced_parens_is_false(self, evaluator):
        assert evaluator.evaluate("(1 + 2", {}) is False

    def test_invalid_character_is_false(self, evaluator):
        assert evaluator.evaluate("x @ y", {"x": 1, "y": 2}) is False

    def test_trailing_garbage_is_false(self, evaluator):
        assert evaluator.evaluate("1 + 1 2", {}) is False


class TestSecurity:
    def test_function_call_blocked(self, evaluator):
        # No function calls allowed — this must never invoke os.system.
        assert evaluator.evaluate("__import__('os').system('id')", {}) is False

    def test_dunder_attribute_access_blocked(self, evaluator):
        class Sneaky:
            _secret = 42
        obj = Sneaky()
        assert evaluator.evaluate("o._secret == 42", {"o": obj}) is False

    def test_division_by_zero_returns_false(self, evaluator):
        assert evaluator.evaluate("1 / 0 == 1", {}) is False


class TestDotAndIndexAccess:
    """Documented features: 'Variable access (dot notation, indexing)'."""

    def test_dot_notation_resolves_nested_attribute(self, evaluator):
        class User:
            def __init__(self):
                self.age = 42
        assert evaluator.evaluate("user.age > 30", {"user": User()}) is True

    def test_dot_notation_false_branch(self, evaluator):
        class User:
            def __init__(self):
                self.age = 12
        assert evaluator.evaluate("user.age > 30", {"user": User()}) is False

    def test_indexing_resolves_list_element(self, evaluator):
        assert evaluator.evaluate("data[0] > 10", {"data": [15, 5]}) is True
        assert evaluator.evaluate("data[1] > 10", {"data": [15, 5]}) is False

    def test_indexing_resolves_dict_key(self, evaluator):
        assert evaluator.evaluate("data['k'] == 7", {"data": {"k": 7}}) is True

    def test_missing_nested_attribute_is_false(self, evaluator):
        class User:
            pass
        assert evaluator.evaluate("user.age > 30", {"user": User()}) is False


class TestSingleton:
    def test_get_expression_evaluator_is_cached(self):
        assert get_expression_evaluator() is get_expression_evaluator()
        assert isinstance(get_expression_evaluator(), ExpressionEvaluator)

    def test_parser_direct_use(self):
        parser = ExpressionParser()
        assert parser.evaluate("a == b", {"a": 1, "b": 1}) is True
