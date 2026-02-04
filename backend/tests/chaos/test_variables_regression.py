
import os
import sys
import unittest
from typing import Any, Dict


# Mock context
class WorkflowContext:
    def __init__(self, variables=None, results=None):
        self.variables = variables or {}
        self.results = results or {}

# Import the class (we need to be able to import the method or class)
# Since we modified the file, we can import it directly if dependencies allow.
# However, AdvancedWorkflowOrchestrator has many imports.
# It might be safer to copy the NEW implementation into the test file to test the Logic in isolation, 
# OR try to import. Importing is better for integration test, but might fail due to missing env.
# Let's try to import. If it fails, I'll Mock the class and inject the method.

try:
    from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
except ImportError:
    # If import fails (likely due to path), we append path
    sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
    try:
        from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
    except ImportError:
        # If deeply nested dependencies (like 'core.models') fail, we mock the class with new logic
        # This mirrors the logic we JUST injected.
        import re
        class AdvancedWorkflowOrchestrator:
            def _resolve_variables(self, value: Any, context: WorkflowContext) -> Any:
                """
                Resolve variables in a value (string, dict, or list) with support for nesting.
                Uses an iterative inside-out approach to handle {{ {{var}} }}.
                """
                # [PASTED LOGIC FOR TEST ISOLATION IF PREVIOUS IMPORT FAILS]
                # ... avoiding massive paste, relying on import first ...
                pass 

# Actually, to be 100% sure we test the FILE ON DISK, we must import it.
# I will use a simple wrapper to import.

class TestVariableRegression(unittest.TestCase):
    def setUp(self):
        # We need an instance. 
        # AdvancedWorkflowOrchestrator __init__ loads things. 
        # We should Mock the __init__ if possible or handle side effects.
        # But wait, I can just patch the class?
        pass

    def test_regression_suite(self):
        """
        Comprehensive regression test for variable resolution.
        """
        # 1. Instantiate 
        try:
            orch = AdvancedWorkflowOrchestrator()
        except:
            # If init fails, we might need to bypass it.
            # Let's create a dummy class that inherits or just use the function if it was static (it's not).
            orch = AdvancedWorkflowOrchestrator.__new__(AdvancedWorkflowOrchestrator)
        
        # 2. Setup Context
        ctx = WorkflowContext(
            variables={
                "name": "Atom",
                "version": 1.0,
                "is_live": True,
                "nested_key": "version"
            },
            results={
                "step1": {"output": "http://api.com", "code": 200},
                "step2": {"data": {"id": 999}}
            }
        )

        # 3. Test Cases
        cases = [
            ("Hello {{name}}", "Hello Atom"),                   # Simple
            ("v{{version}}", "v1.0"),                           # Number to String
            ("Status: {{is_live}}", "Status: True"),            # Bool to String
            ("No vars", "No vars"),                             # Identity
            ("{{missing}}", "{{missing}}"),                     # Undefined (Preserve)
            ("Link: {{step1.output}}", "Link: http://api.com"), # Step Output
            ("ID: {{step2.data.id}}", "ID: 999"),               # Nested Dict Access
            ("{{name}} - {{version}}", "Atom - 1.0"),           # Multiple vars
            
            # COMPLEX / NEW FEATURES
            ("{{ {{nested_key}} }}", "1.0"),                    # Nested: {{version}} -> 1.0
            ("{{step2.data.{{missing_key}}}}", "{{step2.data.{{missing_key}}}}"), # Broken nested
        ]

        print("\n--- Regression Test Running ---")
        for inp, expected in cases:
            res = orch._resolve_variables(inp, ctx)
            print(f"Input: '{inp}' -> Output: '{res}'")
            self.assertEqual(res, expected, f"Failed on input: {inp}")

        # 4. Dictionary Test
        input_dict = {"a": "{{name}}", "b": 123}
        res_dict = orch._resolve_variables(input_dict, ctx)
        self.assertEqual(res_dict["a"], "Atom")
        self.assertEqual(res_dict["b"], 123)
        print("Dictionary Test: OK")

        # 5. List Test
        input_list = ["{{name}}", "{{step1.code}}"]
        res_list = orch._resolve_variables(input_list, ctx)
        self.assertEqual(res_list[0], "Atom")
        self.assertEqual(res_list[1], "200")
        print("List Test: OK")

if __name__ == '__main__':
    unittest.main()
