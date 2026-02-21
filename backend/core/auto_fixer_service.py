"""
Auto-Fixer Service - Automatically fix test failures using LLM.

Analyzes test failures, generates fixes with LLM, applies fixes,
and iterates until tests pass or max retries reached.

Integration:
- Uses StackTraceAnalyzer for failure categorization
- Uses BYOK handler for LLM fix generation
- Applies CommonFixPatterns for quick fixes
- Validates fixes with FixValidator
- Iterates with TestRunnerService

Performance targets:
- Pattern-based fix: <100ms
- LLM fix generation: <10 seconds
- Fix validation: <500ms
- Iteration loop: <30 seconds total
"""

import ast
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.auto_fixer_patterns import CommonFixPatterns, FixValidator
from core.autonomous_coder_agent import CodeGeneratorOrchestrator
from core.llm.byok_handler import BYOKHandler
from core.test_runner_service import (
    ErrorCategory,
    StackTraceAnalyzer,
    TestRunnerService,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Task 3: AutoFixerService for automated fixing
# ============================================================================

class FixStrategy(str, Enum):
    """Fix strategy types."""
    ADD_IMPORT = "add_import"
    FIX_ASSERTION = "fix_assertion"
    ADD_MOCK = "add_mock"
    FIX_QUERY = "fix_query"
    ADD_TYPE_HINT = "add_type_hint"
    ADD_NONE_CHECK = "add_none_check"
    ADD_DB_COMMIT = "add_db_commit"
    ADD_AWAIT = "add_await"
    FIX_LOGIC = "fix_logic"
    LLM_GENERATED = "llm_generated"
    MANUAL_REVIEW = "manual_review"


class AutoFixerService:
    """
    Automatically fix test failures using LLM.

    Analyzes failures, generates fixes with LLM, validates safety,
    applies fixes, and iterates until tests pass.

    Attributes:
        db: Database session
        byok_handler: LLM handler for fix generation
        max_iterations: Maximum fix iterations (default: 5)
        fix_history: Audit trail of applied fixes

    Example:
        fixer = AutoFixerService(db, byok_handler)
        result = await fixer.fix_failures(failures, source_files)
        print(f"Applied {len(result['fixes_applied'])} fixes")
    """

    def __init__(
        self,
        db: Session,
        byok_handler: BYOKHandler,
        max_iterations: int = 5
    ):
        """
        Initialize auto-fixer service.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
            max_iterations: Maximum fix iterations (default: 5)
        """
        self.db = db
        self.byok_handler = byok_handler
        self.max_iterations = max_iterations
        self.fix_history = []

        # Initialize helpers
        self.analyzer = StackTraceAnalyzer()
        self.patterns = CommonFixPatterns()
        self.validator = FixValidator()

    async def fix_failures(
        self,
        failures: List[Dict[str, Any]],
        source_files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Fix multiple test failures.

        Args:
            failures: List of failures from TestRunnerService
            source_files: Current source code {path: content}

        Returns:
            {
                "fixes_applied": [
                    {"file": str, "original": str, "fixed": str}
                ],
                "remaining_failures": int,
                "iterations": int
            }
        """
        fixes_applied = []
        remaining_failures = len(failures)

        # Try pattern-based fixes first
        for failure in failures:
            pattern_fix = await self._try_pattern_fix(failure, source_files)
            if pattern_fix:
                fixes_applied.append(pattern_fix)
                remaining_failures -= 1

        # Try LLM fixes for remaining failures
        if remaining_failures > 0:
            llm_fixes = await self._fix_with_llm(failures, source_files)
            fixes_applied.extend(llm_fixes["fixes"])

        return {
            "fixes_applied": fixes_applied,
            "remaining_failures": remaining_failures,
            "iterations": 1
        }

    async def _try_pattern_fix(
        self,
        failure: Dict[str, Any],
        source_files: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Try pattern-based fix for single failure."""
        # Analyze failure
        analysis = self.analyzer.analyze_failure(failure)

        # Find pattern match
        pattern_match = self.patterns.find_pattern_match(
            failure.get("error_message", "")
        )

        if not pattern_match:
            return None

        # Get source file
        file_path = analysis.get("file_to_fix")
        if file_path not in source_files:
            return None

        source_code = source_files[file_path]

        # Apply pattern fix
        fixed_code = self.patterns.apply_pattern_fix(
            source_code,
            analysis.get("line_number", 0),
            pattern_match["pattern"],
            pattern_match["groups"]
        )

        if fixed_code:
            # Validate fix
            validation = self.validator.validate_fix(
                source_code,
                fixed_code,
                analysis.get("line_number", 0)
            )

            if validation["valid"]:
                return {
                    "file": file_path,
                    "original": source_code,
                    "fixed": fixed_code,
                    "strategy": "pattern"
                }

        return None

    async def _fix_with_llm(
        self,
        failures: List[Dict[str, Any]],
        source_files: Dict[str, str]
    ) -> Dict[str, Any]:
        """Fix failures with LLM generation."""
        fixes = []

        for failure in failures:
            analysis = self.analyzer.analyze_failure(failure)

            file_path = analysis.get("file_to_fix")
            if not file_path or file_path not in source_files:
                continue

            source_code = source_files[file_path]

            # Generate fix with LLM
            fixed_code = await self.generate_fix_with_llm(
                failure,
                source_code,
                analysis
            )

            if fixed_code:
                # Validate fix
                validation = self.validator.validate_fix(
                    source_code,
                    fixed_code,
                    analysis.get("line_number", 0)
                )

                if validation["valid"]:
                    fixes.append({
                        "file": file_path,
                        "original": source_code,
                        "fixed": fixed_code,
                        "strategy": "llm"
                    })

        return {"fixes": fixes}

    async def fix_single_failure(
        self,
        failure: Dict[str, Any],
        source_code: str
    ) -> Optional[str]:
        """
        Fix a single test failure.

        Analyzes failure, generates fix with LLM, applies fix.
        Returns fixed code or None if fix failed.

        Args:
            failure: Single failure from TestRunnerService
            source_code: Source code content

        Returns:
            Fixed code or None
        """
        # Analyze failure
        analysis = self.analyzer.analyze_failure(failure)

        # Try pattern fix first
        pattern_match = self.patterns.find_pattern_match(
            failure.get("error_message", "")
        )

        if pattern_match:
            fixed = self.patterns.apply_pattern_fix(
                source_code,
                analysis.get("line_number", 0),
                pattern_match["pattern"],
                pattern_match["groups"]
            )
            if fixed:
                return fixed

        # Fall back to LLM
        return await self.generate_fix_with_llm(
            failure,
            source_code,
            analysis
        )

    async def generate_fix_with_llm(
        self,
        failure: Dict[str, Any],
        source_code: str,
        analysis: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Use LLM to generate code fix.

        Prompt includes:
        - Error message and stack trace
        - Source code context (10 lines before/after error)
        - Error analysis from StackTraceAnalyzer
        - Request for minimal fix that makes test pass

        Returns fixed code snippet.

        Args:
            failure: Test failure details
            source_code: Source code to fix
            analysis: Optional pre-computed analysis

        Returns:
            Fixed code or None
        """
        if not analysis:
            analysis = self.analyzer.analyze_failure(failure)

        # Extract error context
        line_number = analysis.get("line_number", 0)
        error_context = self._extract_error_context(source_code, line_number)

        # Build prompt
        prompt = self._build_fix_prompt(failure, analysis, error_context)

        try:
            # Call LLM
            response = await self.byok_handler.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python debugger. Generate minimal fixes for failing tests."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Deterministic fixes
                max_tokens=1000
            )

            # Extract fix from response
            fixed_code = self._extract_code_from_response(response)

            return fixed_code

        except Exception as e:
            logger.error(f"LLM fix generation failed: {e}")
            return None

    def _extract_error_context(
        self,
        source_code: str,
        line_number: int
    ) -> Dict[str, Any]:
        """Extract source code context around error line."""
        lines = source_code.split("\n")

        # Get 10 lines before and after
        start = max(0, line_number - 10)
        end = min(len(lines), line_number + 10)

        context_lines = lines[start:end]

        return {
            "start_line": start + 1,
            "end_line": end,
            "context": "\n".join(context_lines),
            "error_line": lines[line_number - 1] if 0 < line_number <= len(lines) else ""
        }

    def _build_fix_prompt(
        self,
        failure: Dict[str, Any],
        analysis: Dict[str, Any],
        error_context: Dict[str, Any]
    ) -> str:
        """Build LLM prompt for fix generation."""
        prompt = f"""Fix this failing test:

## Error
Type: {failure.get('error_type')}
Message: {failure.get('error_message')}

## Analysis
Category: {analysis.get('error_category')}
Root Cause: {analysis.get('root_cause')}
Suggested Strategy: {analysis.get('fix_strategy')}

## Stack Trace
```
{failure.get('stack_trace', '')[:500]}
```

## Source Code Context
```python
{error_context['context']}
```

## Instructions
Generate a MINIMAL fix that:
1. Addresses the root cause: {analysis.get('root_cause')}
2. Changes as little code as possible
3. Follows Python best practices
4. Makes the test pass

Return ONLY the fixed function or code block (no explanations).
"""

        return prompt

    def _extract_code_from_response(
        self,
        response: str
    ) -> Optional[str]:
        """Extract code block from LLM response."""
        # Look for ```python code blocks
        match = re.search(r'```python\n(.+?)\n```', response, re.DOTALL)
        if match:
            return match.group(1)

        # Look for ``` code blocks
        match = re.search(r'```\n(.+?)\n```', response, re.DOTALL)
        if match:
            return match.group(1)

        # Return full response if no code blocks
        return response.strip() if response else None

    def apply_fix(
        self,
        source_code: str,
        fix: str,
        line_number: int
    ) -> str:
        """
        Apply fix to source code.

        Replaces lines around line_number with fix.
        Preserves indentation and surrounding code.

        Args:
            source_code: Original source code
            fix: Fix to apply
            line_number: Line number to apply fix at

        Returns:
            Fixed source code
        """
        lines = source_code.split("\n")

        # Simple replacement for now
        # TODO: Implement smart merging
        if 0 < line_number <= len(lines):
            lines[line_number - 1] = fix

        return "\n".join(lines)

    async def iterate_until_fixed(
        self,
        test_file: str,
        source_files: Dict[str, str],
        test_runner: TestRunnerService,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run test, fix failures, repeat until pass or max iterations.

        Loop:
        1. Run tests
        2. If all pass, return success
        3. Analyze failures
        4. Generate fixes
        5. Apply fixes
        6. Repeat from 1

        Returns final status and fixes applied.

        Args:
            test_file: Test file to run
            source_files: Source code files
            test_runner: TestRunnerService instance
            max_iterations: Override max iterations

        Returns:
            {
                "status": "success" | "max_iterations_reached",
                "fixes_applied": List[Dict],
                "iterations": int,
                "final_results": Dict
            }
        """
        max_iter = max_iterations or self.max_iterations
        iterations = 0
        all_fixes = []

        while iterations < max_iter:
            iterations += 1

            # Run tests
            logger.info(f"Iteration {iterations}: Running tests...")
            results = await test_runner.run_tests(
                test_files=[test_file],
                coverage=True
            )

            # Check if all passed
            if results["failed"] == 0:
                logger.info(f"All tests passed after {iterations} iteration(s)")
                return {
                    "status": "success",
                    "fixes_applied": all_fixes,
                    "iterations": iterations,
                    "final_results": results
                }

            # Analyze and fix failures
            failures = results.get("failures", [])
            logger.info(f"Fixing {len(failures)} failure(s)...")

            fix_result = await self.fix_failures(failures, source_files)

            # Apply fixes to source files
            for fix in fix_result["fixes_applied"]:
                file_path = fix["file"]
                source_files[file_path] = fix["fixed"]
                all_fixes.append(fix)

                # Write to disk
                Path(file_path).write_text(fix["fixed"])

            # Track in history
            self.fix_history.extend(all_fixes)

            # Check if any fixes were applied
            if not fix_result["fixes_applied"]:
                logger.warning("No fixes could be applied, stopping")
                break

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iter}) reached")
        return {
            "status": "max_iterations_reached",
            "fixes_applied": all_fixes,
            "iterations": iterations,
            "final_results": results
        }

    def validate_fix(
        self,
        original: str,
        fixed: str
    ) -> Dict[str, Any]:
        """
        Validate fix is safe and minimal.

        Checks:
        - Fix doesn't remove too much code
        - Fix doesn't break syntax
        - Fix is minimal (only changes what's needed)

        Returns {"valid": bool, "reason": str}

        Args:
            original: Original code
            fixed: Fixed code

        Returns:
            Validation result
        """
        return self.validator.validate_fix(original, fixed, 0)
