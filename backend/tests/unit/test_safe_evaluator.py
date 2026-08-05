"""
TDD tests for core/safe_evaluator.safe_eval (CWE-94 mitigation).

Safe expressions evaluate; injection attempts (attribute traversal, dunder
access, function calls, unknown globals) raise SafeEvalError.
"""

import sys

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from core.safe_evaluator import SafeEvalError, safe_eval


def test_arithmetic():
    assert safe_eval("1 + 2") == 3


def test_boolean_expression():
    assert safe_eval("True == true") is True


def test_context_variables():
    assert safe_eval("x + y", {"x": 1, "y": 2}) == 3


def test_dunder_import_blocked():
    with pytest.raises(SafeEvalError):
        safe_eval("__import__('os').system('id')", {})


def test_class_traversal_blocked():
    with pytest.raises(SafeEvalError):
        safe_eval("().__class__.__base__.__subclasses__()", {})


def test_function_call_blocked():
    with pytest.raises(SafeEvalError):
        safe_eval("open('/etc/passwd')", {})


def test_unknown_name_blocked():
    with pytest.raises(SafeEvalError):
        safe_eval("os.system('id')", {})
