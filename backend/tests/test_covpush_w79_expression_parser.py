# -*- coding: utf-8 -*-
"""Coverage wave 79 — core/expression_parser.py to 100% (gaps left by
test_r79_gap_expression_parser.py) plus four REAL bugs found by adversarial
probing (TDD red→green):

BUG 79-2 (security): the dunder-attribute guard only inspected the raw
  bracket text, so a QUOTED index bypassed it — ``o['_secret']`` /
  ``o['__class__']`` returned the attribute (evaluate → truthy) instead of
  being rejected. Any private/dunder attribute was readable.

BUG 79-3 (semantics): the NUMBER token absorbed a leading minus, so
  ``-2 ** 2`` evaluated as ``(-2) ** 2 == 4`` instead of Python's
  ``-(2 ** 2) == -4`` — the precedence documented in ``_parse_power``.

BUG 79-4 (init): the class defined a SECOND ``__init__`` that shadowed the
  first and never set ``self.variables`` → AttributeError on direct parser
  use.

BUG 79-5 (feature): negative indexes ``data[-1]`` failed — the index part
  ``-1`` is not ``isdigit()`` so it fell through to ``getattr``.

Also covers: unary plus/minus chains, ``**`` right-associativity, ``2 ** -3``,
``1 and``-style premature end, `,`-primary rejection, False/None literals,
sanitized-name fallback (``user.name`` → ``user_name``), non-containable
``in`` operands, is-not, boolean/literal edges, singleton lock path.
"""
import pytest

from core.expression_parser import (
    ExpressionEvaluator,
    ExpressionParser,
    get_expression_evaluator,
)


@pytest.fixture()
def evaluator():
    return ExpressionEvaluator()


class _Sneaky:
    _secret = 42
    __private = 7

    def __init__(self):
        self.visible = 1


# ============================================================================
# BUG 79-2 — quoted-index dunder guard bypass (security)
# ============================================================================

class TestQuotedIndexDunderBlocked:
    def test_quoted_private_attr_blocked(self, evaluator):
        obj = _Sneaky()
        assert evaluator.evaluate("o['_secret'] == 42", {"o": obj}) is False

    def test_quoted_double_underscore_attr_blocked(self, evaluator):
        obj = _Sneaky()
        assert evaluator.evaluate("o['__class__'] == 42", {"o": obj}) is False
        assert evaluator.evaluate("o['__private']", {"o": obj}) is False

    def test_quoted_dunder_blocks_class_truthiness(self, evaluator):
        obj = _Sneaky()
        # Regression: before the fix this returned True (attribute resolved)
        assert evaluator.evaluate("o['__class__']", {"o": obj}) is False

    def test_plain_quoted_attr_still_works(self, evaluator):
        obj = _Sneaky()
        assert evaluator.evaluate("o['visible'] == 1", {"o": obj}) is True

    def test_double_quoted_private_attr_blocked(self, evaluator):
        obj = _Sneaky()
        assert evaluator.evaluate('o["_secret"] == 42', {"o": obj}) is False

    def test_quoted_dunder_dict_key_fails_closed(self, evaluator):
        # Fail-closed: a dunder-looking quoted part is rejected even for dict
        # key access (indistinguishable from attribute probing at parse time).
        data = {"_secret": 1}
        assert evaluator.evaluate("d['_secret'] == 1", {"d": data}) is False


# ============================================================================
# BUG 79-3 — unary minus vs exponentiation precedence
# ============================================================================

class TestUnaryMinusPrecedence:
    def test_neg_pow_is_minus_of_pow(self, evaluator):
        assert evaluator.evaluate("-2 ** 2 == -4", {}) is True

    def test_neg_pow_is_not_parenthesized_negation(self, evaluator):
        # Before the fix `-2 ** 2` evaluated as (-2)**2 == 4
        assert evaluator.evaluate("-2 ** 2 == 4", {}) is False
        assert evaluator.evaluate("(-2) ** 2 == 4", {}) is True

    def test_neg_pow_of_pow(self, evaluator):
        assert evaluator.evaluate("-2 ** 3 ** 2 == -512", {}) is True

    def test_negative_literal_still_works(self, evaluator):
        assert evaluator.evaluate("x == -5", {"x": -5}) is True
        assert evaluator.evaluate("x == -5", {"x": 5}) is False

    def test_negative_float_and_scientific(self, evaluator):
        assert evaluator.evaluate("x == -0.5", {"x": -0.5}) is True
        assert evaluator.evaluate("x == -1e3", {"x": -1000}) is True

    def test_subtraction_still_works(self, evaluator):
        assert evaluator.evaluate("10 - 3 == 7", {}) is True
        assert evaluator.evaluate("2 - -2 == 4", {}) is True
        assert evaluator.evaluate("1--2 == 3", {}) is True


# ============================================================================
# BUG 79-4 — shadowed __init__ leaves variables unset
# ============================================================================

class TestParserInit:
    def test_variables_attribute_exists(self):
        parser = ExpressionParser()
        assert parser.variables == {}

    def test_direct_parser_use_has_clean_state(self):
        parser = ExpressionParser()
        assert parser.tokens == []
        assert parser.pos == 0


# ============================================================================
# BUG 79-5 — negative index support
# ============================================================================

class TestNegativeIndex:
    def test_negative_list_index(self, evaluator):
        assert evaluator.evaluate("data[-1] == 30", {"data": [10, 20, 30]}) is True
        assert evaluator.evaluate("data[-1] == 10", {"data": [10, 20, 30]}) is False

    def test_negative_index_in_chain(self, evaluator):
        assert evaluator.evaluate("data[-2] + data[-1] == 50", {"data": [10, 20, 30]}) is True


# ============================================================================
# Remaining coverage: unary/power/primary/identifier edges
# ============================================================================

class TestUnaryAndPowerEdges:
    def test_unary_plus(self, evaluator):
        assert evaluator.evaluate("+5 == 5", {}) is True
        assert evaluator.evaluate("x > +3", {"x": 4}) is True

    def test_unary_minus_variable(self, evaluator):
        assert evaluator.evaluate("-x == -5", {"x": 5}) is True
        assert evaluator.evaluate("- -x == 5", {"x": 5}) is True

    def test_power_right_associativity(self, evaluator):
        assert evaluator.evaluate("2 ** 3 ** 2 == 512", {}) is True

    def test_negative_exponent(self, evaluator):
        assert evaluator.evaluate("2 ** -3 == 0.125", {}) is True

    def test_power_binds_tighter_than_multiplication(self, evaluator):
        assert evaluator.evaluate("2 * 3 ** 2 == 18", {}) is True

    def test_mixed_precedence_chain(self, evaluator):
        assert evaluator.evaluate("2 + 3 * 4 - 10 / 2 == 9", {}) is True

    def test_modulo_negative_operand(self, evaluator):
        assert evaluator.evaluate("10 % -3", {}) is True  # -2 truthy

    def test_nested_unary(self, evaluator):
        assert evaluator.evaluate("-(x + 1) == -6", {"x": 5}) is True


class TestPrimaryEdges:
    def test_premature_end_after_and(self, evaluator):
        assert evaluator.evaluate("1 and", {}) is False

    def test_premature_end_after_operator(self, evaluator):
        assert evaluator.evaluate("1 +", {}) is False
        assert evaluator.evaluate("x >", {"x": 1}) is False

    def test_lone_paren_is_false(self, evaluator):
        assert evaluator.evaluate("(", {}) is False

    def test_comma_primary_rejected(self, evaluator):
        assert evaluator.evaluate(",", {}) is False

    def test_false_literal(self, evaluator):
        assert evaluator.evaluate("flag", {"flag": False}) is False
        assert evaluator.evaluate("flag == False", {"flag": False}) is True

    def test_none_literal_comparison(self, evaluator):
        assert evaluator.evaluate("x is None", {"x": None}) is True
        assert evaluator.evaluate("x == None", {"x": None}) is True

    def test_true_literal(self, evaluator):
        assert evaluator.evaluate("True", {}) is True

    def test_string_literals_single_double(self, evaluator):
        assert evaluator.evaluate('name == "ada"', {"name": "ada"}) is True
        assert evaluator.evaluate("name == 'ada'", {"name": "ada"}) is True

    def test_string_contains_operator_guard(self, evaluator):
        # `in` on non-containable operands must not raise
        assert evaluator.evaluate("'x' in 5", {}) is False

    def test_is_operator_non_none(self, evaluator):
        # CPython caches small ints, so `x is 5` with x=5 is True; a large int
        # is not cached → identity is False
        assert evaluator.evaluate("x is 10**10", {"x": 10**10}) is False

    def test_is_not_none(self, evaluator):
        assert evaluator.evaluate("x is not None", {"x": 0}) is True
        assert evaluator.evaluate("x is not None", {"x": None}) is False

    def test_not_not(self, evaluator):
        assert evaluator.evaluate("not not x", {"x": True}) is True
        assert evaluator.evaluate("not not x", {"x": False}) is False

    def test_and_or_precedence(self, evaluator):
        assert evaluator.evaluate("True or False and False", {}) is True

    def test_division_by_zero_is_false(self, evaluator):
        assert evaluator.evaluate("1 / 0 == 1", {}) is False

    def test_undefined_variable_is_false(self, evaluator):
        assert evaluator.evaluate("nope == 1", {}) is False


class TestIdentifierEdges:
    def test_sanitized_name_fallback_dot_to_underscore(self, evaluator):
        # user.name -> sanitized user_name lookup path
        assert evaluator.evaluate("user.name == 'ada'", {"user_name": "ada"}) is True

    def test_dotted_identifier_not_in_variables_is_false(self, evaluator):
        assert evaluator.evaluate("user.name == 'ada'", {"user": None}) is False

    def test_index_missing_key_is_false(self, evaluator):
        assert evaluator.evaluate("d['nope'] == 1", {"d": {"k": 1}}) is False

    def test_index_out_of_range_is_false(self, evaluator):
        assert evaluator.evaluate("d[9] == 1", {"d": [1, 2]}) is False

    def test_mixed_dot_and_index(self, evaluator):
        class Row:
            pass
        row = Row()
        row.items = [{"name": "ada"}]
        # Single-level index after dot (the tokenizer allows one bracket group)
        assert evaluator.evaluate("r.items[0]", {"r": row}) is True
        assert evaluator.evaluate("r.items[0]['name'] == 'ada'", {"r": row}) is False

    def test_dunder_dot_blocked(self, evaluator):
        obj = _Sneaky()
        assert evaluator.evaluate("o._secret == 42", {"o": obj}) is False

    def test_keyword_like_identifiers_are_whole_words(self, evaluator):
        assert evaluator.evaluate("android > 1", {"android": 5}) is True
        assert evaluator.evaluate("island == 'x'", {"island": "x"}) is True
        assert evaluator.evaluate("Truely", {"Truely": True}) is True

    def test_membership_on_string(self, evaluator):
        assert evaluator.evaluate("'ll' in 'hello'", {}) is True
        assert evaluator.evaluate("'zz' in 'hello'", {}) is False

    def test_not_in_operator(self, evaluator):
        assert evaluator.evaluate("'x' not in items", {"items": ["a"]}) is True
        assert evaluator.evaluate("'a' not in items", {"items": ["a"]}) is False


class TestSingleton:
    def test_singleton_lock_path(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("core.expression_parser._expression_evaluator", None)
            first = get_expression_evaluator()
            assert get_expression_evaluator() is first
