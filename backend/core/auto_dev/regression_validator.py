"""Behavioral regression validator for self-evolving agent mutations.

Runs BOTH the parent (pre-mutation) and child (post-mutation) code on the
same test inputs in the sandbox and compares their outputs. A mutation passes
only if:
  (a) it doesn't crash, AND
  (b) its output matches the parent on all test inputs (exact-match by default,
      or fuzzy-match with configurable tolerance)

This closes the "fitness = didn't crash" gap from the SOTA analysis. Previously
a mutation that ran without error was promoted regardless of whether it changed
behavior. Now behavioral regression is detected and rejected.

Evidence: RepoFixer (arXiv 2411.10213) resolves 51% of issues because they
validate against regression tests. Tricentis/Autonoma show SOTA self-improving
agents select, run, and maintain regression tests as part of the mutation
validation gate.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TestMismatch:
    """A single test case where parent and child outputs differ."""

    test_input: Dict[str, Any]
    parent_output: str
    child_output: str


@dataclass
class RegressionResult:
    """Result of a behavioral regression validation pass."""

    passed: bool
    mismatches: List[TestMismatch] = field(default_factory=list)
    parent_results: List[Dict[str, Any]] = field(default_factory=list)
    child_results: List[Dict[str, Any]] = field(default_factory=list)
    total_tests: int = 0
    passed_tests: int = 0

    @property
    def regression_detected(self) -> bool:
        return len(self.mismatches) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "mismatch_count": len(self.mismatches),
            "mismatches": [
                {
                    "test_input": m.test_input,
                    "parent_output": m.parent_output[:200],
                    "child_output": m.child_output[:200],
                }
                for m in self.mismatches
            ],
        }


class RegressionValidator:
    """Compares parent vs. child code output on test inputs.

    Usage:
        validator = RegressionValidator()
        result = await validator.validate_regression(
            parent_code=old_function_source,
            mutated_code=new_function_source,
            test_inputs=[{"x": 1}, {"x": 2}, {"x": 3}],
            sandbox=sandbox_instance,
            tenant_id="t1",
        )
        if not result.passed:
            # mutation changed behavior — reject or flag for review
    """

    def __init__(self, fuzzy_match: bool = False, fuzzy_tolerance: float = 0.95) -> None:
        """Initialize the validator.

        Args:
            fuzzy_match: If True, outputs are compared with a similarity ratio
                instead of exact match. Useful for LLM-generated code where
                formatting may differ but semantics are preserved.
            fuzzy_tolerance: When fuzzy_match is True, outputs with a similarity
                ratio ≥ this threshold are considered matching (0.0–1.0).
        """
        self._fuzzy_match = fuzzy_match
        self._fuzzy_tolerance = fuzzy_tolerance

    async def validate_regression(
        self,
        parent_code: str,
        mutated_code: str,
        test_inputs: List[Dict[str, Any]],
        sandbox: Any,
        tenant_id: str,
    ) -> RegressionResult:
        """Run parent and child code on the same inputs and compare outputs.

        Args:
            parent_code: The pre-mutation Python source code.
            mutated_code: The post-mutation Python source code.
            test_inputs: A list of input dicts to test with. Each dict is
                passed as ``input_params`` to the sandbox. If empty, returns
                a passed result with 0 tests (no regression possible to detect).
            sandbox: An object implementing ``execute_raw_python`` (SandboxProtocol).
            tenant_id: Tenant ID for sandbox execution.

        Returns:
            RegressionResult indicating whether the mutation is behaviorally safe.
        """
        if not test_inputs:
            # No test inputs → can't detect regression. Don't block the mutation
            # (backward compat), but log that validation was skipped.
            logger.debug("[RegressionValidator] no test inputs provided; skipping")
            return RegressionResult(passed=True, total_tests=0, passed_tests=0)

        result = RegressionResult(passed=True, total_tests=len(test_inputs))

        for test_input in test_inputs:
            # Run parent code
            parent_result = await self._run_in_sandbox(
                sandbox, tenant_id, parent_code, test_input
            )
            result.parent_results.append(parent_result)

            # Run child code
            child_result = await self._run_in_sandbox(
                sandbox, tenant_id, mutated_code, test_input
            )
            result.child_results.append(child_result)

            # If child crashed, that's a regression (the mutation broke it)
            if not child_result.get("_success", False):
                result.mismatches.append(TestMismatch(
                    test_input=test_input,
                    parent_output=parent_result.get("output", ""),
                    child_output=f"[CRASH] {child_result.get('output', '')}",
                ))
                continue

            # If parent crashed but child didn't, that's an improvement — not a regression
            if not parent_result.get("_success", False):
                result.passed_tests += 1
                continue

            # Both succeeded — compare outputs
            parent_output = parent_result.get("output", "")
            child_output = child_result.get("output", "")

            if self._outputs_match(parent_output, child_output):
                result.passed_tests += 1
            else:
                result.mismatches.append(TestMismatch(
                    test_input=test_input,
                    parent_output=parent_output,
                    child_output=child_output,
                ))

        result.passed = len(result.mismatches) == 0

        if result.regression_detected:
            logger.warning(
                f"[RegressionValidator] regression detected: "
                f"{len(result.mismatches)}/{result.total_tests} tests mismatched"
            )
        else:
            logger.info(
                f"[RegressionValidator] passed: {result.passed_tests}/"
                f"{result.total_tests} tests matched"
            )

        return result

    async def _run_in_sandbox(
        self,
        sandbox: Any,
        tenant_id: str,
        code: str,
        input_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run code in the sandbox, returning a result dict with _success flag."""
        try:
            raw = await sandbox.execute_raw_python(
                tenant_id=tenant_id,
                code=code,
                input_params=input_params,
            )
            raw["_success"] = raw.get("status") == "success"
            return raw
        except Exception as e:
            logger.debug(f"[RegressionValidator] sandbox error: {e}")
            return {"_success": False, "output": str(e), "status": "failed"}

    def _outputs_match(self, parent: str, child: str) -> bool:
        """Compare two outputs. Exact match by default; fuzzy if enabled."""
        if not self._fuzzy_match:
            return parent.strip() == child.strip()

        # Fuzzy match: use difflib ratio
        from difflib import SequenceMatcher

        ratio = SequenceMatcher(None, parent.strip(), child.strip()).ratio()
        return ratio >= self._fuzzy_tolerance
