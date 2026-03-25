"""InvariantGenerator: AI-generated property test invariants from code analysis."""
import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import re

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.llm_service import LLMService
from tests.bug_discovery.ai_enhanced.models.invariant_suggestion import (
    InvariantSuggestion, Criticality
)


class InvariantGenerator:
    """
    Generate AI-suggested property test invariants from code analysis.

    Analyzes Python code to identify patterns that warrant property-based
    testing (e.g., functions with loops, dictionary access, state machines)
    and generates formal invariant suggestions following INVARIANTS.md format.

    Example:
        generator = InvariantGenerator()
        invariants = await generator.generate_invariants_for_file(
            file_path="backend/core/agent_governance_service.py"
        )
        for invariant in invariants:
            if invariant.is_testable:
                generator.write_property_test(invariant)
    """

    # Code patterns that suggest property testing
    PROPERTY_TEST_PATTERNS = {
        "idempotence": [
            r"for\s+\w+\s+in\s+",  # Loops
            r"\.get\(",  # Dictionary access
            r"def\s+\w+\s*\(.*\).*:",  # Functions
        ],
        "commutativity": [
            r"\.update\(",  # Dictionary updates
            r"\.add\(",  # Set additions
        ],
        "associativity": [
            r"\s+\+\s+",  # Addition/concatenation
            r"\s*\*\s*",  # Multiplication
        ],
        "monotonicity": [
            r"status\s*=",  # State changes
            r"\.append\(",  # List growth
            r"count\s*[+\=]",  # Counters
        ],
        "termination": [
            r"while\s+True:",  # Infinite loops
            r"for\s+\w+\s+in\s+.*:",
            r"recursiv",  # Recursion
        ],
        "rounding": [
            r"round\(",
            r"int\(",
            r"\.quantize\(",
        ],
    }

    # Hypothesis strategy mappings
    HYPOTHESIS_STRATEGIES = {
        "str": "st.text(min_size=0, max_size=100)",
        "int": "st.integers(min_value=-1000, max_value=1000)",
        "float": "st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False)",
        "bool": "st.booleans()",
        "list": "st.lists(st.text())",
        "dict": "st.dictionaries(st.text(), st.integers())",
        "uuid": "st.uuids()",
        "datetime": "st.datetimes()",
        "enum": "st.sampled_from([...",
    }

    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize InvariantGenerator."""
        self.llm_service = llm_service or LLMService(workspace_id="default")

    async def generate_invariants_for_file(
        self,
        file_path: str,
        max_invariants: int = 5
    ) -> List[InvariantSuggestion]:
        """
        Generate invariant suggestions for a Python file.

        Args:
            file_path: Path to Python file to analyze
            max_invariants: Maximum number of invariants to suggest

        Returns:
            List of InvariantSuggestion objects
        """
        # Read source code
        with open(file_path) as f:
            source_code = f.read()

        # Parse AST for structure analysis
        try:
            tree = ast.parse(source_code)
            functions = self._extract_functions(tree)
        except SyntaxError:
            functions = []

        # Generate invariants using LLM
        invariants = await self._generate_invariants_with_llm(
            file_path=file_path,
            source_code=source_code,
            functions=functions,
            max_invariants=max_invariants
        )

        # Validate each invariant
        for invariant in invariants:
            invariant.is_testable, invariant.validation_errors = self._validate_invariant(invariant)

        # Sort by testability and criticality
        invariants.sort(key=lambda x: (x.is_testable, self._criticality_score(x.criticality)), reverse=True)

        return invariants[:max_invariants]

    async def _generate_invariants_with_llm(
        self,
        file_path: str,
        source_code: str,
        functions: List[Dict[str, Any]],
        max_invariants: int
    ) -> List[InvariantSuggestion]:
        """Generate invariants using LLM code analysis."""
        # Truncate code if too long
        code_snippet = source_code[:5000]  # First 5000 chars

        # Build function list for context
        function_list = "\n".join([
            f"- {f['name']}({', '.join(f['args'])})"
            for f in functions[:10]
        ])

        # Build LLM prompt
        prompt = f"""Analyze this Python code and suggest property-based testing invariants.

File: {file_path}

Functions:
{function_list}

Code:
```python
{code_snippet}
```

Task: Identify functions/classes that would benefit from property-based testing.

Look for:
1. Functions with loops (suggest idempotence, termination invariants)
2. Dictionary/set operations (suggest commutativity, associativity)
3. State machines (suggest monotonicity, transition invariants)
4. Mathematical operations (suggest rounding, precision invariants)
5. Caching mechanisms (suggest cache consistency invariants)

For each invariant, provide:
- invariant_name: Short descriptive name (e.g., "Cache Lookup Idempotence")
- function_name: Target function to test
- hypothesis: Natural language invariant (e.g., "Cache lookups are idempotent")
- formal_specification: Mathematical/logical specification (e.g., "∀ key: cache.get(key) == cache.get(key)")
- rationale: Why this invariant matters
- hypothesis_strategy: Hypothesis strategy (e.g., "st.text()" for strings, "st.integers()" for ints)
- criticality: CRITICAL/HIGH/STANDARD/LOW
- test_skeleton: Complete test skeleton with imports, @given decorator, and assertions

Output JSON format:
{{
    "invariants": [
        {{
            "invariant_name": "Cache Lookup Idempotence",
            "function_name": "get_from_cache",
            "hypothesis": "For all cache keys, lookups are idempotent",
            "formal_specification": "∀ key, n: cache.get(key) == cache.get(key) (n times)",
            "rationale": "Cache lookups must not have side effects or state changes",
            "hypothesis_strategy": "st.text(min_size=1, max_size=50) for cache keys",
            "criticality": "HIGH",
            "test_skeleton": "@given(st.text(min_size=1, max_size=50))\\n@settings(max_examples=200)\\ndef test_cache_lookup_idempotent(key):\\n    # Test implementation..."
        }}
    ]
}}

Respond ONLY with valid JSON, no explanation."""

        try:
            # Call LLM
            response = await self.llm_service.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,  # Medium temperature for creativity
                max_tokens=2000
            )

            # Parse JSON response
            response_text = response.get("content", response.get("text", ""))
            result = json.loads(response_text.strip())
            invariants_data = result.get("invariants", [])

            # Convert to InvariantSuggestion objects
            invariants = []
            for inv_data in invariants_data:
                # Determine suggested_examples based on criticality
                criticality = Criticality(inv_data.get("criticality", "STANDARD"))
                suggested_examples = self._get_examples_for_criticality(criticality)

                invariant = InvariantSuggestion(
                    file_path=file_path,
                    suggested_examples=suggested_examples,
                    **inv_data
                )
                invariants.append(invariant)

            return invariants

        except (json.JSONDecodeError, Exception) as e:
            # Fallback: generate invariants from AST patterns
            return self._generate_fallback_invariants(file_path, functions)

    def _generate_fallback_invariants(
        self,
        file_path: str,
        functions: List[Dict[str, Any]]
    ) -> List[InvariantSuggestion]:
        """Generate basic invariants from AST patterns when LLM fails."""
        invariants = []

        for func in functions[:3]:  # Top 3 functions
            func_name = func["name"]
            args = func["args"]

            # Generate idempotence invariant for functions with return values
            if func.get("has_return", False):
                invariants.append(InvariantSuggestion(
                    file_path=file_path,
                    invariant_name=f"{func_name.title()} Idempotence",
                    function_name=func_name,
                    hypothesis=f"{func_name} is idempotent for same inputs",
                    formal_specification=f"∀ inputs: {func_name}(inputs) == {func_name}(inputs)",
                    rationale=f"Function should return same result for same inputs (LLM failed, using AST fallback)",
                    hypothesis_strategy=self._infer_strategy_from_args(args),
                    criticality=Criticality.STANDARD,
                    test_skeleton=self._generate_test_skeleton(func_name, args, "idempotent"),
                    suggested_examples=100,
                    is_testable=True,
                    validation_errors=[]
                ))

        return invariants

    def _extract_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract function definitions from AST."""
        functions = []

        class FunctionVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "lineno": node.lineno,
                    "has_return": any(isinstance(n, ast.Return) for n in ast.walk(node))
                })

            def visit_AsyncFunctionDef(self, node):
                args = [arg.arg for arg in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "lineno": node.lineno,
                    "has_return": any(isinstance(n, ast.Return) for n in ast.walk(node))
                })

        FunctionVisitor().visit(tree)
        return functions

    def _infer_strategy_from_args(self, args: List[str]) -> str:
        """Infer Hypothesis strategy from function arguments."""
        if not args:
            return "st.none()"

        strategies = []
        for arg in args:
            arg_lower = arg.lower()
            if "id" in arg_lower or "key" in arg_lower or "name" in arg_lower:
                strategies.append("st.text()")
            elif "count" in arg_lower or "num" in arg_lower or "amount" in arg_lower:
                strategies.append("st.integers(min_value=0, max_value=1000)")
            elif "value" in arg_lower or "rate" in arg_lower:
                strategies.append("st.floats()")
            elif "enabled" in arg_lower or "active" in arg_lower or "flag" in arg_lower:
                strategies.append("st.booleans()")
            else:
                strategies.append("st.text()")

        return ", ".join(strategies) if strategies else "st.text()"

    def _generate_test_skeleton(
        self,
        func_name: str,
        args: List[str],
        invariant_type: str
    ) -> str:
        """Generate property test skeleton."""
        args_str = ", ".join(args) if args else ""
        strategies_str = self._infer_strategy_from_args(args)

        skeleton = f'''"""Property test: {func_name.title()} {invariant_type.title()}"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# TODO: Import target function
# from your_module import {func_name}

@given({strategies_str})
@settings(max_examples=200)
def test_{func_name}_{invariant_type}({args_str}):
    """Test that {func_name} is {invariant_type}."""
    # TODO: Implement test
    result1 = {func_name}({args_str})
    result2 = {func_name}({args_str})
    assert result1 == result2, "{func_name} should be {invariant_type}"
'''
        return skeleton

    def _get_examples_for_criticality(self, criticality: Criticality) -> int:
        """Get suggested max_examples based on criticality."""
        return {
            Criticality.CRITICAL: 200,
            Criticality.HIGH: 150,
            Criticality.STANDARD: 100,
            Criticality.LOW: 50,
        }.get(criticality, 100)

    def _criticality_score(self, criticality: Criticality) -> int:
        """Get numeric score for sorting."""
        return {
            Criticality.CRITICAL: 4,
            Criticality.HIGH: 3,
            Criticality.STANDARD: 2,
            Criticality.LOW: 1,
        }.get(criticality, 0)

    def _validate_invariant(
        self,
        invariant: InvariantSuggestion
    ) -> tuple[bool, List[str]]:
        """
        Validate invariant is testable with Hypothesis.

        Returns:
            Tuple of (is_testable, list of validation errors)
        """
        errors = []

        # Check hypothesis_strategy is valid
        if not self._is_valid_hypothesis_strategy(invariant.hypothesis_strategy):
            errors.append(f"Invalid Hypothesis strategy: {invariant.hypothesis_strategy}")

        # Check test_skeleton contains required elements
        if "@given" not in invariant.test_skeleton:
            errors.append("Test skeleton missing @given decorator")

        if "def test_" not in invariant.test_skeleton:
            errors.append("Test skeleton missing test function")

        # Check criticality is valid
        try:
            Criticality(invariant.criticality)
        except ValueError:
            errors.append(f"Invalid criticality: {invariant.criticality}")

        # Check suggested_examples is reasonable
        if invariant.suggested_examples < 10 or invariant.suggested_examples > 1000:
            errors.append(f"suggested_examples out of range: {invariant.suggested_examples}")

        return len(errors) == 0, errors

    def _is_valid_hypothesis_strategy(self, strategy: str) -> bool:
        """Check if Hypothesis strategy is valid."""
        # Look for st. prefix or valid strategies
        valid_patterns = [
            r"st\.[a-z_]+\(.*\)",  # st.text(), st.integers(), etc.
            r"sampled_from",
            r"one_of",
            r"none\(\)",
        ]

        return any(re.search(pattern, strategy) for pattern in valid_patterns)

    def write_property_test(
        self,
        invariant: InvariantSuggestion,
        output_dir: Optional[Path] = None
    ) -> str:
        """
        Write property test file from invariant suggestion.

        Args:
            invariant: InvariantSuggestion from generate_invariants_for_file
            output_dir: Output directory for generated tests

        Returns:
            Path to generated test file
        """
        if output_dir is None:
            output_dir = backend_dir / "tests" / "property_tests" / "generated"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from invariant name
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", invariant.invariant_name.lower())
        filename = f"test_{safe_name}.py"
        output_path = output_dir / filename

        # Write test file
        with open(output_path, "w") as f:
            f.write(f'''"""
Property Test: {invariant.invariant_name}

Auto-generated by InvariantGenerator (Phase 244)
File: {invariant.file_path}
Function: {invariant.function_name}

Invariant: {invariant.hypothesis}
Formal: {invariant.formal_specification}
Rationale: {invariant.rationale}
Criticality: {invariant.criticality}
"""

{invariant.test_skeleton}
''')

        return str(output_path)

    async def save_invariants(
        self,
        invariants: List[InvariantSuggestion],
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Save generated invariants to Markdown files.

        Args:
            invariants: List of InvariantSuggestion objects
            output_dir: Output directory (default: backend/tests/bug_discovery/storage/invariants)

        Returns:
            List of saved file paths
        """
        if output_dir is None:
            output_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "invariants"

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        saved_paths = []
        for invariant in invariants:
            # Generate filename
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", invariant.invariant_name.lower())
            filename = f"invariant_{safe_name}.md"
            filepath = Path(output_dir) / filename

            # Write markdown
            with open(filepath, "w") as f:
                f.write(f"""# {invariant.invariant_name}

**File:** `{invariant.file_path}`
**Function:** `{invariant.function_name}`
**Criticality:** {invariant.criticality}

## Invariant

{invariant.hypothesis}

## Formal Specification

{invariant.formal_specification}

## Rationale

{invariant.rationale}

## Hypothesis Strategy

```python
{invariant.hypothesis_strategy}
```

## Test Skeleton

```python
{invariant.test_skeleton}
```

## Validation

- **Testable:** {invariant.is_testable}
- **Errors:** {", ".join(invariant.validation_errors) if invariant.validation_errors else "None"}

---

*Generated by InvariantGenerator (Phase 244)*
""")

            saved_paths.append(str(filepath))

        return saved_paths
