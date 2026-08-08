# -*- coding: utf-8 -*-
"""
Bug-hunt tests for core.expression_parser.py (net-new bugs only).

Each test documents a genuine logic bug found in the module and was written
RED before the corresponding fix.
"""

import pytest

from core.expression_parser import ExpressionEvaluator


@pytest.fixture()
def evaluator():
    return ExpressionEvaluator()


class TestExponentPrecedence:
    """BUG: ``**`` (exponentiation) had the wrong precedence.

    The grammar folded ``**`` into the multiplicative level alongside ``*``,
    ``/`` and ``%`` and evaluated left-to-right, so ``2 * 3 ** 2`` parsed as
    ``(2 * 3) ** 2`` (= 36) instead of ``2 * (3 ** 2)`` (= 18). In standard
    math (and Python) exponentiation binds tighter than multiplication and is
    right-associative.
    """

    def test_power_binds_tighter_than_multiply(self, evaluator):
        """BUG: 2 * 3 ** 2 evaluated to 36 instead of 18."""
        assert evaluator.evaluate("2 * 3 ** 2 == 18", {}) is True

    def test_power_binds_tighter_than_division(self, evaluator):
        """BUG: 36 / 3 ** 2 evaluated to 144 instead of 4."""
        assert evaluator.evaluate("36 / 3 ** 2 == 4", {}) is True

    def test_power_is_right_associative(self, evaluator):
        """BUG: 2 ** 3 ** 2 evaluated to 64 (left) instead of 512 (right)."""
        assert evaluator.evaluate("2 ** 3 ** 2 == 512", {}) is True

    def test_negative_base_power_resolves_correctly(self, evaluator):
        """Regression guard for unary-minus / power interaction.

        This parser tokenizes a leading minus as part of a numeric literal
        (``-2`` is a single NUMBER token), so ``-2 ** 2`` evaluates the power
        first against the negative literal base, yielding ``(-2) ** 2 == 4``.
        This documents the parser's existing tokenization model and guards
        against the precedence fix accidentally changing it.
        """
        assert evaluator.evaluate("-2 ** 2 == 4", {}) is True

    def test_power_does_not_break_plain_multiplication(self, evaluator):
        """Regression guard: ordinary precedence still works."""
        assert evaluator.evaluate("2 + 3 * 4 == 14", {}) is True

    def test_power_does_not_break_simple_power(self, evaluator):
        """Regression guard: a lone power still evaluates correctly."""
        assert evaluator.evaluate("2 ** 8 == 256", {}) is True


class TestKeywordOperatorWordBoundary:
    """BUG: keyword operators matched as prefixes of identifiers.

    The operator token regex listed the bare words ``and``, ``or``, ``not``,
    ``in`` and ``is`` with no word boundary, and the master tokenizer tried the
    OPERATOR alternative before IDENTIFIER. Any variable whose name *starts
    with* one of these keywords (e.g. ``android``, ``order``, ``island``,
    ``inside``, ``noted``) was therefore tokenized as the keyword followed by a
    dangling suffix, breaking evaluation.
    """

    def test_identifier_starting_with_and(self, evaluator):
        """BUG: 'android' tokenized as 'and' + 'roid'."""
        assert evaluator.evaluate("android == 1", {"android": 1}) is True

    def test_identifier_starting_with_or(self, evaluator):
        """BUG: 'order' tokenized as 'or' + 'der'."""
        assert evaluator.evaluate("order == 1", {"order": 1}) is True

    def test_identifier_starting_with_is(self, evaluator):
        """BUG: 'island' tokenized as 'is' + 'land'."""
        assert evaluator.evaluate("island == 1", {"island": 1}) is True

    def test_identifier_starting_with_in(self, evaluator):
        """BUG: 'inside' tokenized as 'in' + 'side'."""
        assert evaluator.evaluate("inside == 1", {"inside": 1}) is True

    def test_identifier_starting_with_not(self, evaluator):
        """BUG: 'noted' tokenized as 'not' + 'ed'."""
        assert evaluator.evaluate("noted == 1", {"noted": 1}) is True

    def test_real_and_operator_still_works(self, evaluator):
        """Regression guard: the genuine 'and' keyword still evaluates."""
        assert evaluator.evaluate("a and b", {"a": True, "b": True}) is True

    def test_real_in_operator_still_works(self, evaluator):
        """Regression guard: the genuine 'in' keyword still evaluates."""
        assert evaluator.evaluate("'x' in items", {"items": ["x", "y"]}) is True

    def test_real_is_operator_still_works(self, evaluator):
        """Regression guard: the genuine 'is' keyword still evaluates."""
        assert evaluator.evaluate("x is None", {"x": None}) is True

    def test_real_not_operator_still_works(self, evaluator):
        """Regression guard: the genuine 'not' keyword still evaluates."""
        assert evaluator.evaluate("not a", {"a": False}) is True
