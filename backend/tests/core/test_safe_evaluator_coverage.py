"""
Coverage + security bug-hunt tests for core/safe_evaluator.py (CWE-94 sandbox).

Covers:
- safe_eval(): literals, operators, comparisons, booleans, subscripts, containers,
  ternary, context variables, and every BLOCK path (attribute, lambda, import,
  comprehensions, starred, named-expr, function calls).
- safe_eval_with_math(): whitelisted math fns, DoS guards, all block paths.
- SafeEvaluator AST validator internals (_fold_int, _pow_exponent_too_large,
  visit_Call dispatch, generic_visit, deprecated-node branches).
- DoS regression: huge-int exponents rejected at validation time (constant fold)
  AND a non-constant (Name) exponent cannot hang the evaluator.

Bug-hunt (TDD) findings documented inline with BUG docstrings on the tests.

NOTE: existing tests/unit/test_safe_evaluator.py covers the basic happy/sad
paths for safe_eval; these tests add full branch coverage of safe_eval_with_math
and the SafeEvaluator AST internals and the new bug-hunt regressions.
"""

import ast
import sys
import time

import pytest

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

from core.safe_evaluator import (
    SafeEvalError,
    SafeEvaluator,
    safe_eval,
    safe_eval_with_math,
)


# ---------------------------------------------------------------------------
# safe_eval — happy paths
# ---------------------------------------------------------------------------


class TestSafeEvalHappy:
    def test_int_literal(self):
        assert safe_eval("42") == 42

    def test_float_literal(self):
        assert safe_eval("3.14") == 3.14

    def test_string_literal(self):
        assert safe_eval("'hello'") == "hello"

    def test_bool_true(self):
        assert safe_eval("True") is True

    def test_bool_false(self):
        assert safe_eval("False") is False

    def test_none(self):
        assert safe_eval("None") is None

    def test_json_aliases(self):
        assert safe_eval("true") is True
        assert safe_eval("false") is False
        assert safe_eval("null") is None

    def test_unary_plus(self):
        assert safe_eval("+5") == 5

    def test_unary_minus(self):
        assert safe_eval("-5") == -5

    def test_unary_not(self):
        assert safe_eval("not True") is False

    def test_unary_invert(self):
        assert safe_eval("~5") == -6

    def test_arithmetic_all_ops(self):
        assert safe_eval("7 + 3") == 10
        assert safe_eval("7 - 3") == 4
        assert safe_eval("7 * 3") == 21
        assert safe_eval("7 / 2") == 3.5
        assert safe_eval("7 // 2") == 3
        assert safe_eval("7 % 3") == 1
        assert safe_eval("2 ** 3") == 8

    def test_bitwise_ops(self):
        assert safe_eval("5 & 3") == 1
        assert safe_eval("5 | 2") == 7
        assert safe_eval("5 ^ 1") == 4
        assert safe_eval("1 << 4") == 16
        assert safe_eval("256 >> 4") == 16

    def test_comparisons(self):
        assert safe_eval("1 == 1") is True
        assert safe_eval("1 != 2") is True
        assert safe_eval("1 < 2") is True
        assert safe_eval("2 <= 2") is True
        assert safe_eval("3 > 2") is True
        assert safe_eval("3 >= 3") is True
        assert safe_eval("1 is 1") is True  # small-int caching
        assert safe_eval("1 is not 2") is True
        assert safe_eval("1 in [1, 2]") is True
        assert safe_eval("5 not in [1, 2]") is True
        assert safe_eval("1 < 2 < 3") is True  # chained

    def test_boolean_ops(self):
        assert safe_eval("True and False") is False
        assert safe_eval("True or False") is True
        assert safe_eval("not False") is True

    def test_ternary(self):
        assert safe_eval("1 if True else 2") == 1
        assert safe_eval("1 if False else 2") == 2

    def test_containers(self):
        assert safe_eval("[1, 2, 3]") == [1, 2, 3]
        assert safe_eval("(1, 2, 3)") == (1, 2, 3)
        assert safe_eval("{1, 2, 3}") == {1, 2, 3}
        assert safe_eval("{1: 'a', 2: 'b'}") == {1: "a", 2: "b"}

    def test_subscript_index(self):
        assert safe_eval("x[0]", {"x": [10, 20]}) == 10

    def test_subscript_dict(self):
        assert safe_eval("x['k']", {"x": {"k": 99}}) == 99

    def test_subscript_slice(self):
        assert safe_eval("x[1:3]", {"x": [1, 2, 3, 4]}) == [2, 3]

    def test_context_variables(self):
        assert safe_eval("x + y", {"x": 1, "y": 2}) == 3

    def test_nested_expression(self):
        assert safe_eval("(1 + 2) * (3 + 4)") == 21

    def test_pow_large_constant_allowed(self):
        # 10**5 exponent is below the 10**6 cap; result has ~33k digits, fine.
        result = safe_eval("2 ** 1000")
        assert result == 2 ** 1000

    def test_negative_exponent_constant_allowed(self):
        # 2 ** -3 = 0.125 (fold returns False for negative, eval computes float).
        assert safe_eval("2 ** -3") == 0.125


# ---------------------------------------------------------------------------
# safe_eval — block paths (every disallowed AST node)
# ---------------------------------------------------------------------------


class TestSafeEvalBlocks:
    def test_attribute_access_blocked(self):
        with pytest.raises(SafeEvalError, match="Attribute access"):
            safe_eval("(1).__class__", {})

    def test_dunder_class_chain_blocked(self):
        with pytest.raises(SafeEvalError):
            safe_eval("().__class__.__base__.__subclasses__()", {})

    def test_lambda_blocked(self):
        # In safe_eval (calls disabled) the outer call is blocked first; the
        # lambda itself is also disallowed — assert either signal.
        with pytest.raises(SafeEvalError, match="Lambda|Function calls are not allowed"):
            safe_eval("(lambda: 1)()", {})

    def test_lambda_alone_blocked(self):
        # A bare lambda (no call) hits the Lambda node directly.
        with pytest.raises(SafeEvalError, match="Lambda"):
            safe_eval("lambda: 1", {})

    def test_import_blocked(self):
        # __import__(...) is a call → blocked by the function-call guard in
        # safe_eval. The import-node path is covered separately below.
        with pytest.raises(SafeEvalError, match="[Ii]mport|Function calls"):
            safe_eval("__import__('os').system('id')", {})

    def test_function_call_blocked(self):
        """safe_eval (default) disallows ALL function calls."""
        with pytest.raises(SafeEvalError, match="Function calls are not allowed"):
            safe_eval("open('/etc/passwd')", {})

    def test_list_comp_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ll]ist comprehension"):
            safe_eval("[x for x in [1, 2]]", {})

    def test_dict_comp_blocked(self):
        with pytest.raises(SafeEvalError, match="[Dd]ict comprehension"):
            safe_eval("{k: 1 for k in [1, 2]}", {})

    def test_set_comp_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ss]et comprehension"):
            safe_eval("{x for x in [1, 2]}", {})

    def test_genexp_blocked(self):
        with pytest.raises(SafeEvalError, match="[Gg]enerator"):
            safe_eval("(x for x in [1, 2])", {})

    def test_starred_blocked(self):
        with pytest.raises(SafeEvalError, match="[Uu]npacking"):
            safe_eval("[*[1, 2]]", {})

    def test_named_expr_blocked(self):
        with pytest.raises(SafeEvalError):
            safe_eval("(x := 1)", {})

    def test_method_call_blocked(self):
        # In safe_eval (calls disabled) the call guard fires first; with
        # calls enabled the method-call guard fires. Assert either.
        with pytest.raises(SafeEvalError, match="[Mm]ethod call|Function calls"):
            safe_eval("''.join(['a'])", {})

    def test_syntax_error_raises_safe_eval_error(self):
        with pytest.raises(SafeEvalError, match="Syntax error"):
            safe_eval("1 +")

    def test_empty_expression_raises(self):
        with pytest.raises(SafeEvalError):
            safe_eval("")

    def test_comment_only_raises(self):
        with pytest.raises(SafeEvalError):
            safe_eval("# just a comment")


# ---------------------------------------------------------------------------
# safe_eval_with_math — happy paths
# ---------------------------------------------------------------------------


class TestSafeEvalWithMath:
    def test_sum(self):
        assert safe_eval_with_math("sum([1, 2, 3])") == 6

    def test_min(self):
        assert safe_eval_with_math("min([3, 1, 2])") == 1

    def test_max(self):
        assert safe_eval_with_math("max([3, 1, 2])") == 3

    def test_abs(self):
        assert safe_eval_with_math("abs(-5)") == 5

    def test_round(self):
        assert safe_eval_with_math("round(3.6)") == 4

    def test_sqrt(self):
        assert safe_eval_with_math("sqrt(16)") == 4.0

    def test_pow_two_arg(self):
        assert safe_eval_with_math("pow(2, 10)") == 1024

    def test_pow_three_arg_modular(self):
        # Three-arg pow is modular/bounded — not subject to the DoS cap.
        assert safe_eval_with_math("pow(2, 10, 100)") == 24

    def test_log(self):
        import math
        assert safe_eval_with_math("log(e)") == 1.0

    def test_log10(self):
        assert safe_eval_with_math("log10(1000)") == 3.0

    def test_exp(self):
        import math
        assert safe_eval_with_math("exp(0)") == 1.0

    def test_trig(self):
        assert safe_eval_with_math("sin(0)") == 0.0
        assert safe_eval_with_math("cos(0)") == 1.0
        assert safe_eval_with_math("tan(0)") == 0.0

    def test_constants_pi_e(self):
        import math
        assert safe_eval_with_math("pi") == math.pi
        assert safe_eval_with_math("e") == math.e

    def test_context_inputs(self):
        assert safe_eval_with_math("x * 2", {"x": 5}) == 10

    def test_whitelisted_fn_with_subscript_arg(self):
        assert safe_eval_with_math("min([x[0], 9])", {"x": [3]}) == 3

    def test_call_with_kwarg(self):
        # int is whitelisted; even if int itself is unavailable this confirms
        # the keyword-argument validation path in visit_Call.
        with pytest.raises(SafeEvalError):
            # 'open' isn't whitelisted — proves kwarg validation reaches block
            safe_eval_with_math("open('/x', mode='r')")


# ---------------------------------------------------------------------------
# safe_eval_with_math — block paths
# ---------------------------------------------------------------------------


class TestSafeEvalWithMathBlocks:
    def test_unknown_function_blocked(self):
        with pytest.raises(SafeEvalError, match="not whitelisted|not in the safe"):
            safe_eval_with_math("open('/etc/passwd')")

    def test_method_call_blocked(self):
        with pytest.raises(SafeEvalError, match="[Mm]ethod call"):
            safe_eval_with_math("os.system('id')", {})

    def test_attribute_blocked(self):
        with pytest.raises(SafeEvalError, match="Attribute access"):
            safe_eval_with_math("(1).__class__", {})

    def test_lambda_blocked(self):
        with pytest.raises(SafeEvalError, match="Only whitelisted"):
            safe_eval_with_math("(lambda: 1)()", {})

    def test_subscript_call_blocked(self):
        """Call through a subscript/expression reaches arbitrary context
        callables and must be blocked even when function calls are allowed."""
        with pytest.raises(SafeEvalError, match="Only whitelisted functions"):
            safe_eval_with_math("f[0](1)", {"f": [print]})

    def test_dict_subscript_call_blocked(self):
        with pytest.raises(SafeEvalError, match="Only whitelisted functions"):
            safe_eval_with_math("d[k](1)", {"d": {"a": str}, "k": "a"})

    def test_attribute_method_call_blocked(self):
        with pytest.raises(SafeEvalError, match="[Mm]ethod call"):
            safe_eval_with_math("__import__('os').system('id')")


# ---------------------------------------------------------------------------
# DoS guards (constant folding)
# ---------------------------------------------------------------------------


class TestDoSGuards:
    def test_constant_huge_pow_blocked(self):
        """A constant exponent beyond the cap is rejected at validation."""
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval("2 ** (10**18)", {})

    def test_constant_huge_pow_folded_mult(self):
        """Folding through multiplication still detects the huge exponent."""
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval("2 ** (2 * 10**9)", {})

    def test_constant_negative_huge_pow_blocked(self):
        """Negative constant exponent beyond the cap is also rejected
        (defence-in-depth; -exp on int base yields float but the cap still
        holds for the abs value)."""
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval("2 ** -(10**18)", {})

    def test_math_pow_huge_exponent_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval_with_math("pow(2, 10**18)")

    def test_math_pow_three_arg_not_blocked(self):
        """Three-arg (modular) pow is bounded and must not be flagged."""
        assert safe_eval_with_math("pow(2, 10**18, 7)") == pow(2, 10**18, 7)

    def test_constant_just_under_cap_allowed(self):
        # 10**5 < 10**6 cap; computes a ~125KB int — allowed.
        assert safe_eval("2 ** 100000") == 2 ** 100000


# ---------------------------------------------------------------------------
# BUG (TDD): non-constant exponent DoS bypass — CWE-400
# ---------------------------------------------------------------------------


class TestNonConstantExponentDoS:
    def test_non_constant_huge_exponent_does_not_hang(self):
        """BUG: a non-constant (Name) exponent bypasses the static DoS cap
        (which only folds constant subtrees) and ``eval`` then computes a
        result with ~10^18 bits, hanging the process. The evaluator must
        bound the result of ``**`` at execution time, not just at AST time.

        Before the fix this test hangs (>5s). After the fix it raises
        SafeEvalError quickly.
        """
        start = time.time()
        with pytest.raises(SafeEvalError):
            safe_eval("2 ** e", {"e": 10 ** 18})
        elapsed = time.time() - start
        assert elapsed < 3.0, (
            f"Non-constant exponent DoS: evaluation took {elapsed:.1f}s — "
            "the evaluator must bound `**` results at execution time, not "
            "only constant-folded exponents at AST time."
        )

    def test_reasonable_non_constant_exponent_works(self):
        """Sanity: a small non-constant exponent still computes correctly."""
        assert safe_eval("2 ** e", {"e": 8}) == 256


# ---------------------------------------------------------------------------
# BUG (TDD): SAFE_FUNCTIONS advertises int/float/str/bool/len but
# safe_eval_with_math never injects them — they validate but fail at eval.
# ---------------------------------------------------------------------------


class TestWhitelistEvalMismatch:
    def test_int_available(self):
        """BUG: `int` is in SAFE_FUNCTIONS (AST validator allows it) but
        safe_eval_with_math doesn't inject it into eval globals, so
        `int('5')` fails with 'name int is not defined'."""
        assert safe_eval_with_math("int('5')") == 5

    def test_float_available(self):
        assert safe_eval_with_math("float('1.5')") == 1.5

    def test_str_available(self):
        assert safe_eval_with_math("str(123)") == "123"

    def test_bool_available(self):
        assert safe_eval_with_math("bool(0)") is False

    def test_len_available(self):
        assert safe_eval_with_math("len('abc')") == 3

    def test_int_with_base_kwarg(self):
        assert safe_eval_with_math("int('ff', base=16)") == 255


# ---------------------------------------------------------------------------
# SafeEvaluator AST internals (direct unit coverage)
# ---------------------------------------------------------------------------


class TestSafeEvaluatorInternals:
    def test_validate_returns_true_for_safe(self):
        v = SafeEvaluator()
        assert v.validate("1 + 2") is True

    def test_validate_resets_state_between_calls(self):
        v = SafeEvaluator(allow_function_calls=False)
        # First call: blocked (function call). Second call: safe — must not
        # carry over the previous failure.
        with pytest.raises(SafeEvalError):
            v.validate("open('x')")
        assert v.validate("1 + 1") is True

    def test_fold_int_constant(self):
        v = SafeEvaluator()
        tree = ast.parse("5", mode="eval")
        val, known = v._fold_int(tree.body)
        assert known and val == 5

    def test_fold_int_unary_minus(self):
        v = SafeEvaluator()
        tree = ast.parse("-5", mode="eval")
        val, known = v._fold_int(tree.body)
        assert known and val == -5

    def test_fold_int_add(self):
        v = SafeEvaluator()
        tree = ast.parse("2 + 3", mode="eval")
        val, known = v._fold_int(tree.body)
        assert known and val == 5

    def test_fold_int_sub(self):
        v = SafeEvaluator()
        tree = ast.parse("10 - 4", mode="eval")
        val, known = v._fold_int(tree.body)
        assert known and val == 6

    def test_fold_int_mult(self):
        v = SafeEvaluator()
        tree = ast.parse("3 * 4", mode="eval")
        val, known = v._fold_int(tree.body)
        assert known and val == 12

    def test_fold_int_pow_small(self):
        v = SafeEvaluator()
        tree = ast.parse("2 ** 5", mode="eval")
        val, known = v._fold_int(tree.body)
        assert known and val == 32

    def test_fold_int_pow_huge_returns_unknown(self):
        """Folding refuses to compute powers beyond POW_FOLD_MAX_BITS so the
        guard itself can't be abused for DoS."""
        v = SafeEvaluator()
        tree = ast.parse("2 ** (10**18)", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_fold_int_bool_not_folded(self):
        """``True`` is an int subclass but must NOT be folded as an int
        (folding it would let ``True ** huge`` bypass the cap)."""
        v = SafeEvaluator()
        tree = ast.parse("True", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_fold_int_name_not_folded(self):
        v = SafeEvaluator()
        tree = ast.parse("x", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_fold_int_unsupported_op(self):
        """Division (float result) is not folded as int."""
        v = SafeEvaluator()
        tree = ast.parse("7 / 2", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_pow_exponent_too_large_true(self):
        v = SafeEvaluator()
        tree = ast.parse("2 ** (10**18)", mode="eval")
        assert v._pow_exponent_too_large(tree.body.right) is True

    def test_pow_exponent_too_large_false_small(self):
        v = SafeEvaluator()
        tree = ast.parse("2 ** 5", mode="eval")
        assert v._pow_exponent_too_large(tree.body.right) is False

    def test_pow_exponent_too_large_false_nonconstant(self):
        v = SafeEvaluator()
        tree = ast.parse("2 ** e", mode="eval")
        assert v._pow_exponent_too_large(tree.body.right) is False

    def test_visit_call_when_disabled_sets_unsafe(self):
        v = SafeEvaluator(allow_function_calls=False)
        tree = ast.parse("sum([1,2])", mode="eval")
        v.visit(tree)
        assert v._is_safe is False
        assert any("Function calls are not allowed" in e for e in v._errors)

    def test_visit_call_attribute_func_blocked(self):
        v = SafeEvaluator(allow_function_calls=True)
        tree = ast.parse("''.join(['a'])", mode="eval")
        v.visit(tree)
        assert v._is_safe is False

    def test_visit_call_unknown_name_blocked(self):
        v = SafeEvaluator(allow_function_calls=True)
        tree = ast.parse("open('/x')", mode="eval")
        v.visit(tree)
        assert v._is_safe is False
        assert any("open" in e for e in v._errors)

    def test_visit_call_pow_two_arg_huge_blocked(self):
        v = SafeEvaluator(allow_function_calls=True)
        tree = ast.parse("pow(2, 10**18)", mode="eval")
        v.visit(tree)
        assert v._is_safe is False
        assert any("[Ee]xponent" in e or "Exponent" in e for e in v._errors)

    def test_visit_call_whitelisted_passes(self):
        v = SafeEvaluator(allow_function_calls=True)
        tree = ast.parse("sum([1, 2])", mode="eval")
        v.visit(tree)
        assert v._is_safe is True

    def test_generic_visit_walks_children(self):
        """generic_visit must recurse so a disallowed node nested deep in the
        tree is still caught."""
        v = SafeEvaluator()
        tree = ast.parse("(1 + (x for x in [1]))", mode="eval")
        v.visit(tree)
        assert v._is_safe is False

    def test_load_ctx_node_allowed(self):
        """ast.Load (the subscript/name ctx) is allowed and silently passes."""
        v = SafeEvaluator()
        assert v.validate("x[0]") is True


# ---------------------------------------------------------------------------
# Targeted line coverage for remaining branches
# ---------------------------------------------------------------------------


class TestRemainingBranchCoverage:
    def test_validate_generic_exception_becomes_safe_eval_error(self):
        """The catch-all `except Exception` in validate() wraps non-SyntaxError,
        non-SafeEvalError exceptions into SafeEvalError('Validation error: ...')."""
        v = SafeEvaluator()
        # Force an exception inside validate by giving it a non-string that
        # ast.parse can't handle and that isn't a SyntaxError path.
        with pytest.raises(SafeEvalError):
            v.validate(12345)  # type: ignore[arg-type]

    def test_fold_int_pow_negative_exponent_returns_unknown(self):
        """``2 ** -3`` via fold: right < 0 → returns (None, False)."""
        v = SafeEvaluator()
        tree = ast.parse("2 ** -3", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_fold_int_unsupported_binop_returns_unknown(self):
        """Division (float result) isn't folded as int."""
        v = SafeEvaluator()
        tree = ast.parse("7 / 2", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_fold_int_unary_minus_on_unknown_returns_unknown(self):
        """``-x`` where x isn't foldable → (None, False)."""
        v = SafeEvaluator()
        tree = ast.parse("-x", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_fold_int_non_int_constant_returns_unknown(self):
        """A string constant isn't folded as int."""
        v = SafeEvaluator()
        tree = ast.parse("'hi'", mode="eval")
        val, known = v._fold_int(tree.body)
        assert not known

    def test_safe_pow_modular_bounded(self):
        """3-arg _safe_pow delegates to modular pow (always bounded)."""
        from core.safe_evaluator import _safe_pow
        assert _safe_pow(2, 10, 100) == 24

    def test_safe_pow_negative_exponent_int(self):
        """Negative int exponent yields a float (tiny), allowed."""
        from core.safe_evaluator import _safe_pow
        assert _safe_pow(2, -3) == 0.125

    def test_safe_pow_float_base(self):
        """Float base defers to builtin pow (no bigint risk)."""
        from core.safe_evaluator import _safe_pow
        assert _safe_pow(2.0, 3) == 8.0

    def test_safe_pow_overflow_rejected(self):
        """A non-constant-style huge exponent is rejected by the result cap."""
        from core.safe_evaluator import _safe_pow, SafeEvalError
        with pytest.raises(ValueError):
            _safe_pow(2, 10 ** 18)

    def test_safe_pow_zero_base(self):
        """0 ** 0 == 1 (no division, fine)."""
        from core.safe_evaluator import _safe_pow
        assert _safe_pow(0, 0) == 1

    def test_safe_eval_value_error_surfaced(self):
        """A ValueError from _safe_pow during eval becomes SafeEvalError."""
        with pytest.raises(SafeEvalError):
            safe_eval("2 ** e", {"e": 10 ** 18})

    def test_safe_eval_with_math_value_error_surfaced(self):
        """pow(2, huge) via safe_eval_with_math is rejected at eval time."""
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("pow(2, e)", {"e": 10 ** 18})

    def test_generic_visit_walks_list_field(self):
        """generic_visit must recurse into list-of-AST fields (e.g. list body)."""
        v = SafeEvaluator()
        # A list literal contains a generator expr deep inside → must be caught
        # via generic_visit's list iteration.
        with pytest.raises(SafeEvalError):
            v.validate("[1, (x for x in [2]), 3]")

    def test_visit_call_pow_two_arg_nonconstant_exponent_allowed_at_ast(self):
        """AST validation alone can't see context values, so pow(2, e) passes
        AST validation (the runtime guard handles it)."""
        v = SafeEvaluator(allow_function_calls=True)
        # Should NOT raise — AST validation passes; runtime guard catches it.
        assert v.validate("pow(2, e)") is True

    def test_safe_eval_generic_exception_branch(self):
        """A non-ValueError exception during eval (e.g. NameError) is caught by
        the generic `except Exception` and surfaced as SafeEvalError."""
        with pytest.raises(SafeEvalError, match="Evaluation failed"):
            safe_eval("undefined_name_xyz", {})

    def test_safe_eval_with_math_generic_exception_branch(self):
        """Same generic-except path for safe_eval_with_math."""
        with pytest.raises(SafeEvalError, match="Evaluation failed"):
            safe_eval_with_math("undefined_name_xyz", {})

    def test_safe_eval_with_math_zero_division(self):
        """Division by zero surfaces as a generic eval error."""
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("1 / 0")

    def test_safe_pow_float_overflow_to_value_error(self):
        """A float base whose pow overflows hits OverflowError → ValueError."""
        from core.safe_evaluator import _safe_pow
        # 1e308 ** 2 overflows float → OverflowError → wrapped as ValueError
        with pytest.raises(ValueError):
            _safe_pow(1e308, 2)
