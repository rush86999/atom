"""Round 79 — safe_evaluator whitelist-escape + DoS hardening tests.

TDD: the subscript-call escape tests and the huge-exponent DoS tests fail
against the pre-fix module:

- ``safe_eval_with_math("f[0]()", {"f": [lambda: ...]})`` silently called the
  context callable (whitelist bypass via ast.Call whose func is a Subscript /
  BinOp rather than a plain whitelisted Name).
- ``safe_eval("2 ** (10**18)")`` and ``safe_eval_with_math("pow(2, 10**18)")``
  hang the process indefinitely (CWE-400 resource exhaustion).

The DoS assertions run the expression in a bounded subprocess so a regression
fails fast as a timeout instead of hanging the suite.
"""
import os
import subprocess
import sys
import textwrap

import pytest

from core.safe_evaluator import SafeEvalError, safe_eval, safe_eval_with_math

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_subprocess(expression_stmt: str, timeout: float = 15.0) -> str:
    """Evaluate ``expression_stmt`` (a python statement) in a subprocess.

    The subprocess imports core.safe_evaluator and prints BLOCKED when a
    SafeEvalError is raised, EVALUATED otherwise. A hang surfaces as
    subprocess.TimeoutExpired (test failure), never as a hung suite.
    """
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {_BACKEND_DIR!r})
        from core.safe_evaluator import safe_eval, safe_eval_with_math, SafeEvalError
        try:
            {expression_stmt}
            print("EVALUATED")
        except SafeEvalError:
            print("BLOCKED")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-u", "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


class TestWhitelistCallEscape:
    """Only whitelisted plain-name functions may be called — never context
    callables reachable through subscripts or expressions."""

    def test_safe_eval_blocks_subscript_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval("f[0]()", {"f": [lambda: 1]})

    def test_safe_eval_blocks_or_form_subscript_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval("('a'*0 or f[0])()", {"f": [lambda: 1]})

    def test_safe_eval_with_math_blocks_subscript_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("f[0]()", {"f": [lambda: "PWNED"]})

    def test_safe_eval_with_math_blocks_dict_subscript_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("d['x']()", {"d": {"x": len}})

    def test_safe_eval_with_math_blocks_or_form_subscript_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("('a'*0 or f[0])()", {"f": [lambda: "PWNED"]})

    def test_safe_eval_with_math_blocks_expression_result_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("(f if True else f)[0]()", {"f": [lambda: "PWNED"]})

    def test_safe_eval_with_math_blocks_method_call(self):
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("f.append(1)", {"f": []})

    def test_safe_eval_with_math_still_allows_whitelisted_functions(self):
        assert safe_eval_with_math("pow(2, 10)", {}) == 1024
        assert safe_eval_with_math("sqrt(16)", {}) == 4.0
        assert safe_eval_with_math("sum([1, 2, 3])", {}) == 6


class TestHugeExponentDoS:
    """Provably-huge constant exponents must be rejected at validation time —
    ``2**(10**18)`` used to hang the process indefinitely."""

    def test_safe_eval_blocks_huge_pow_operator(self):
        out = _run_subprocess('safe_eval("2 ** (10**18)", {})')
        assert out == "BLOCKED"

    def test_safe_eval_blocks_left_assoc_huge_pow(self):
        out = _run_subprocess('safe_eval("2 ** 10 ** 18", {})')
        assert out == "BLOCKED"

    def test_safe_eval_blocks_tetration(self):
        out = _run_subprocess('safe_eval("9 ** 9 ** 9", {})')
        assert out == "BLOCKED"

    def test_safe_eval_with_math_blocks_huge_pow_call(self):
        out = _run_subprocess('safe_eval_with_math("pow(2, 10**18)", {})')
        assert out == "BLOCKED"

    def test_safe_eval_with_math_blocks_pow_with_nested_huge_exponent(self):
        out = _run_subprocess('safe_eval_with_math("pow(2, 2**200)", {})')
        assert out == "BLOCKED"

    def test_safe_eval_with_math_blocks_variable_base_huge_exponent(self):
        out = _run_subprocess(
            'safe_eval_with_math("x ** (10**18)", {"x": 2})'
        )
        assert out == "BLOCKED"

    def test_legit_bounded_exponents_still_work(self):
        assert safe_eval("2 ** 40", {}) == 1099511627776
        assert safe_eval("2 ** 100000", {}).bit_length() == 100001
        assert safe_eval_with_math("pow(2, 100)", {}) == 2 ** 100
        assert safe_eval_with_math("pow(x, n)", {"x": 3, "n": 4}) == 81
