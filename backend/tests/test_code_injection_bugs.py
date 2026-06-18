"""
Test suite for Code Injection vulnerabilities.

RED PHASE: These tests expose code injection bugs.

The bugs:
1. workflow_engine.py:857 - eval() with user input can access object methods
2. skill_composition_engine.py:299 - eval() with user input can escape sandbox
3. formula_memory.py:274 - eval() with user input allows code injection
"""

import pytest
import inspect


class TestCodeInjectionVulnerabilities:
    """
    Test suite revealing code injection vulnerabilities via eval().

    The bug: User-controlled expressions passed to eval() can escape
    restricted environments by accessing object methods and attributes.
    """

    def test_workflow_engine_eval_uses_user_input(self):
        """
        Test that workflow engine evaluates user expressions with eval().

        BUG: Lines 845-857 - User expression passed to eval() with insufficient sandboxing.
        Even with __builtins__ restricted, attackers can access object methods.
        """
        from core.workflow_engine import WorkflowEngine

        source = inspect.getsource(WorkflowEngine._evaluate_condition)

        # Verify the bug - eval() is used with user input
        assert 'eval(' in source, \
            "Bug confirmed: eval() used for condition evaluation"
        assert '"__builtins__": {}' in source, \
            "Bug confirmed: __builtins__ restriction is used (but insufficient)"

    def test_workflow_engine_eval_allows_object_access(self):
        """
        Test that workflow engine eval allows accessing object attributes.

        BUG: With eval(), attackers can use object.__class__, __bases__, __subclasses__()
        to escape the sandbox and access dangerous classes.
        """
        from core.workflow_engine import WorkflowEngine

        source = inspect.getsource(WorkflowEngine._evaluate_condition)

        # Verify the bug - allowed_names contains objects that can be exploited
        assert 'allowed_names' in source, \
            "Bug confirmed: allowed_names dict provides objects for evaluation"

    def test_skill_composition_eval_uses_user_input(self):
        """
        Test that skill composition engine evaluates user conditions with eval().

        BUG: Lines 292-299 - User condition passed to eval() with insufficient sandboxing.
        """
        from core.skill_composition_engine import SkillCompositionEngine

        source = inspect.getsource(SkillCompositionEngine._evaluate_condition)

        # Verify the bug - eval() is used with user input
        assert 'eval(' in source, \
            "Bug confirmed: eval() used for condition evaluation"
        assert '"__builtins__": {}' in source, \
            "Bug confirmed: __builtins__ restriction is used (but insufficient)"

    def test_skill_composition_eval_allows_result_access(self):
        """
        Test that skill composition eval allows accessing result object methods.

        BUG: The context dict contains step results which could be arbitrary objects.
        Attackers can access object methods to escape sandbox.
        """
        from core.skill_composition_engine import SkillCompositionEngine

        source = inspect.getsource(SkillCompositionEngine._evaluate_condition)

        # Verify the bug - context contains step results
        assert 'context = {}' in source, \
            "Bug confirmed: context dict is populated with step results"
        assert 'for step_id, result in results.items():' in source, \
            "Bug confirmed: step results (arbitrary objects) added to context"

    def test_formula_memory_eval_uses_user_input(self):
        """
        Test that formula memory evaluates user expressions with eval().

        BUG: Lines 267-274 - User expression passed to eval() with insufficient sandboxing.
        """
        from core.formula_memory import FormulaMemoryManager

        source = inspect.getsource(FormulaMemoryManager.apply_formula)

        # Verify the bug - eval() is used with user input
        assert 'eval(' in source, \
            "Bug confirmed: eval() used for formula evaluation"
        assert '"__builtins__": {}' in source, \
            "Bug confirmed: __builtins__ restriction is used (but insufficient)"

    def test_formula_memory_eval_allows_inputs_access(self):
        """
        Test that formula memory eval allows accessing input object methods.

        BUG: The inputs dict could contain arbitrary objects with dangerous methods.
        """
        from core.formula_memory import FormulaMemoryManager

        source = inspect.getsource(FormulaMemoryManager.apply_formula)

        # Verify the bug - inputs dict passed to eval
        assert 'inputs' in source and 'eval(expression' in source, \
            "Bug confirmed: user inputs passed to eval() as locals"

    def test_eval_sandbox_escape_possible(self):
        """
        Test that eval() sandboxing can be escaped via object attribute access.

        BUG: Even with __builtins__ restricted, attackers can use:
        ().__class__.__base__.__subclasses__() to get to dangerous classes.
        """
        # This test demonstrates the sandbox escape technique
        # In a restricted eval environment, you can still access object model

        # Simulate the restricted environment used in the codebase
        restricted_globals = {"__builtins__": {}}
        allowed_names = {
            'True': True,
            'False': False,
            'None': None,
        }

        # Demonstrate sandbox escape: Access __class__ from None object
        result = eval("None.__class__", restricted_globals, allowed_names)
        assert result is type(None), \
            "Bug confirmed: Can access __class__ attribute from None object"

        # Demonstrate further escape: Access __base__ and __subclasses__
        result2 = eval("None.__class__.__base__", restricted_globals, allowed_names)
        assert result2 is object, \
            "Bug confirmed: Can access __base__ to get to object class"

        # This demonstrates that the sandbox is NOT secure
        result3 = eval("None.__class__.__base__.__subclasses__()", restricted_globals, allowed_names)
        assert isinstance(result3, list), \
            "Bug confirmed: Can access __subclasses__() to enumerate all classes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
