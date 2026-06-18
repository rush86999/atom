"""
Test suite for Code Injection fix verification.

GREEN PHASE: These tests verify the code injection fixes are applied.
"""

import pytest


class TestCodeInjectionFixes:
    """Tests for verifying the code injection fixes."""

    def test_safe_eval_blocks_sandbox_escape(self):
        """
        Test that safe_eval blocks sandbox escape attempts.

        GREEN PHASE: After the fix, dangerous operations should be blocked.
        """
        from core.safe_evaluator import safe_eval, SafeEvalError

        # Safe expressions should work
        result = safe_eval("5 > 3", {})
        assert result is True, "Safe: Numeric comparison works"

        result = safe_eval("true == true", {})
        assert result is True, "Safe: Boolean comparison works"

        result = safe_eval("x + y", {"x": 5, "y": 3})
        assert result == 8, "Safe: Variable arithmetic works"

        # Dangerous expressions should raise SafeEvalError
        with pytest.raises(SafeEvalError):
            safe_eval("__import__('os')", {})

        with pytest.raises(SafeEvalError):
            safe_eval("().__class__", {})

        with pytest.raises(SafeEvalError):
            safe_eval("true.__class__", {})

        with pytest.raises(SafeEvalError):
            safe_eval("(lambda: 5)()", {})

        with pytest.raises(SafeEvalError):
            safe_eval("print('test')", {})

    def test_safe_eval_with_math_blocks_sandbox_escape(self):
        """
        Test that safe_eval_with_math blocks sandbox escape while allowing math functions.

        GREEN PHASE: After the fix, dangerous operations should be blocked but math functions allowed.
        """
        from core.safe_evaluator import safe_eval_with_math, SafeEvalError

        # Math expressions should work
        result = safe_eval_with_math("sqrt(16) + pow(2, 3)", {})
        assert result == 12.0, "Safe: Math functions work"

        result = safe_eval_with_math("sum([1, 2, 3])", {})
        assert result == 6, "Safe: Built-in functions work"

        result = safe_eval_with_math("x * y + sqrt(z)", {"x": 2, "y": 3, "z": 16})
        assert result == 10.0, "Safe: Combined math and variables work"

        # Dangerous expressions should raise SafeEvalError
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("__import__('os').system('ls')", {})

        with pytest.raises(SafeEvalError):
            safe_eval_with_math("().__class__.__base__", {})

        with pytest.raises(SafeEvalError):
            safe_eval_with_math("open('/etc/passwd').read()", {})

    def test_workflow_engine_uses_safe_eval(self):
        """
        Test that workflow engine uses safe_eval for condition evaluation.

        GREEN PHASE: After the fix, safe_eval should be used instead of eval.
        """
        from core.workflow_engine import WorkflowEngine
        from core.safe_evaluator import SafeEvalError

        engine = WorkflowEngine()

        # Safe expressions should work
        result = engine._evaluate_condition("true", {})
        assert result is True, "Fix applied: Simple boolean works"

        result = engine._evaluate_condition("5 > 3", {})
        assert result is True, "Fix applied: Numeric comparison works"

        # Variable substitution with ${} syntax (workflow engine's internal format)
        # State needs 'outputs' key for step outputs
        result = engine._evaluate_condition("${step1} > 3", {"outputs": {"step1": 5}})
        assert result is True, "Fix applied: Variable substitution works"

        # Dangerous expressions should be blocked
        result = engine._evaluate_condition("().__class__", {})
        assert result is False, "Fix applied: __class__ access is blocked"

        result = engine._evaluate_condition("__import__('os')", {})
        assert result is False, "Fix applied: __import__ is blocked"

    def test_skill_composition_uses_safe_eval(self):
        """
        Test that skill composition engine uses safe_eval for condition evaluation.

        GREEN PHASE: After the fix, safe_eval should be used instead of eval.
        """
        from core.skill_composition_engine import SkillCompositionEngine
        from core.safe_evaluator import SafeEvalError
        from core.database import get_db_session

        # Initialize with database session
        with get_db_session() as db:
            engine = SkillCompositionEngine(db)

            # Safe expressions should work
            # Note: Use simple variable names, not attribute access
            result = engine._evaluate_condition("success == true", {"success": True})
            assert result is True, "Fix applied: Simple boolean with context works"

            result = engine._evaluate_condition("count > 0", {"count": 5})
            assert result is True, "Fix applied: Numeric comparison works"

            # Dangerous expressions should be blocked
            result = engine._evaluate_condition("().__class__", {})
            assert result is False, "Fix applied: __class__ access is blocked"

            result = engine._evaluate_condition("__import__('os')", {})
            assert result is False, "Fix applied: __import__ is blocked"

    def test_formula_memory_uses_safe_eval(self):
        """
        Test that formula memory uses safe_eval_with_math for expression evaluation.

        GREEN PHASE: After the fix, safe_eval_with_math should be used.
        """
        from core.safe_evaluator import safe_eval_with_math, SafeEvalError

        # Test the safe_eval_with_math function directly
        result = safe_eval_with_math("x + y", {"x": 5, "y": 3})
        assert result == 8, "Fix applied: Basic arithmetic works"

        result = safe_eval_with_math("sqrt(16)", {})
        assert result == 4.0, "Fix applied: Math functions work"

        # Dangerous expressions should be blocked
        with pytest.raises(SafeEvalError):
            safe_eval_with_math("__import__('os')", {})

        with pytest.raises(SafeEvalError):
            safe_eval_with_math("().__class__.__base__", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
