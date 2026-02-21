"""
Test Runner Service - Execute tests and parse results.

Integrates with pytest for test execution, parses output and coverage reports,
analyzes stack traces to categorize failures, and stores results in AutonomousWorkflow.

Integration:
- Uses pytest for test execution
- Integrates with TestGeneratorService for running generated tests
- Stores results in AutonomousWorkflow.test_results
- Provides failure analysis to AutoFixerService

Performance targets:
- Test execution: Real-time via subprocess
- Result parsing: <1 second
- Stack trace analysis: <100ms
- Coverage measurement: <2 seconds
"""

import ast
import json
import logging
import re
import subprocess
import asyncio
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.models import AutonomousWorkflow, AgentLog

logger = logging.getLogger(__name__)


# ============================================================================
# Task 1: TestRunnerService for pytest execution
# ============================================================================

class TestRunnerService:
    """
    Execute tests and parse results.

    Runs pytest via subprocess, captures output, parses failures and coverage.
    Provides structured results for auto-fixer to analyze.

    Attributes:
        db: Database session for persistence
        project_root: Root directory for test execution
        tests_root: Test files directory

    Example:
        runner = TestRunnerService(db, project_root="backend")
        results = await runner.run_tests(coverage=True)
        print(f"Passed: {results['passed']}, Failed: {results['failed']}")
    """

    def __init__(
        self,
        db: Session,
        project_root: str = "backend"
    ):
        """
        Initialize test runner.

        Args:
            db: Database session
            project_root: Root directory (default: backend)
        """
        self.db = db
        self.project_root = Path(project_root)
        self.tests_root = self.project_root / "tests"
        self.coverage_file = self.project_root / "coverage.json"

    async def run_tests(
        self,
        test_files: Optional[List[str]] = None,
        coverage: bool = True,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run pytest and capture results.

        Args:
            test_files: List of test files (None = all tests)
            coverage: Run with coverage reporting
            verbose: Verbose output

        Returns:
            {
                "passed": int,
                "failed": int,
                "skipped": int,
                "total": int,
                "duration_seconds": float,
                "failures": [
                    {
                        "test_file": str,
                        "test_name": str,
                        "error_type": str,
                        "error_message": str,
                        "stack_trace": str,
                        "line_number": int
                    }
                ],
                "coverage": {
                    "percent": float,
                    "covered_lines": int,
                    "total_lines": int
                }
            }
        """
        start_time = datetime.now()

        # Build pytest command
        cmd = self._build_pytest_command(test_files, coverage, verbose)

        # Run pytest
        process = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=300  # 5 minute timeout
        )

        # Parse output
        results = self.parse_pytest_output(process.stdout + process.stderr)

        # Parse coverage if enabled
        if coverage and self.coverage_file.exists():
            try:
                coverage_data = self.parse_coverage_json(self.coverage_file)
                results["coverage"] = coverage_data
            except Exception as e:
                logger.warning(f"Failed to parse coverage: {e}")
                results["coverage"] = {"percent": 0.0, "covered_lines": 0, "total_lines": 0}

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        results["duration_seconds"] = duration

        # Log summary
        logger.info(
            f"Test run complete: {results['passed']} passed, "
            f"{results['failed']} failed, {results['skipped']} skipped "
            f"in {duration:.2f}s"
        )

        return results

    def _build_pytest_command(
        self,
        test_files: Optional[List[str]],
        coverage: bool,
        verbose: bool
    ) -> List[str]:
        """Build pytest command with appropriate flags."""
        cmd = ["python", "-m", "pytest"]

        # Add verbosity
        if verbose:
            cmd.append("-v")

        # Add coverage
        if coverage:
            cmd.extend(["--cov", ".", "--cov-report=json", "--cov-report=term"])

        # Add test files
        if test_files:
            cmd.extend(test_files)
        else:
            cmd.append(str(self.tests_root))

        return cmd

    def parse_pytest_output(
        self,
        output: str
    ) -> Dict[str, Any]:
        """
        Parse pytest terminal output for results.

        Extracts passed, failed, skipped counts.
        Parses FAILURE sections for error details.

        Args:
            output: Pytest stdout+stderr combined

        Returns:
            Structured test results
        """
        results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "failures": []
        }

        # Parse summary line (e.g., "5 passed, 2 failed, 1 skipped in 3.45s")
        summary_match = re.search(
            r'(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?',
            output
        )
        if summary_match:
            results["passed"] = int(summary_match.group(1))
            results["failed"] = int(summary_match.group(2) or 0)
            results["skipped"] = int(summary_match.group(3) or 0)
            results["total"] = (
                results["passed"] +
                results["failed"] +
                results["skipped"]
            )

        # Parse failure sections
        failures = self._parse_failures(output)
        results["failures"] = failures

        return results

    def _parse_failures(
        self,
        output: str
    ) -> List[Dict[str, Any]]:
        """Parse FAILURE sections from pytest output."""
        failures = []

        # Split by "FAILED" markers
        sections = re.split(r'^=+ FAILED ', output, flags=re.MULTILINE)

        for section in sections[1:]:  # Skip first (header)
            failure = self._parse_single_failure(section)
            if failure:
                failures.append(failure)

        return failures

    def _parse_single_failure(
        self,
        section: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single FAILURE section."""
        try:
            # Extract test name (first line)
            lines = section.strip().split('\n')
            test_name = lines[0].strip()

            # Find error type and message
            error_type = "Unknown"
            error_message = ""

            # Look for error pattern (e.g., "AssertionError: ...")
            error_match = re.search(
                r'(AssertionError|AttributeError|ImportError|TypeError|'
                r'ValueError|KeyError|NameError|RuntimeError): (.+)',
                section
            )
            if error_match:
                error_type = error_match.group(1)
                error_message = error_match.group(2).split('\n')[0].strip()

            # Extract stack trace (everything after "-*-" divider)
            stack_trace = ""
            if "-*-" in section:
                stack_trace = section.split("-*-")[1].strip()

            # Extract line number from stack trace
            line_number = self._extract_line_number(stack_trace)

            return {
                "test_name": test_name,
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "line_number": line_number
            }
        except Exception as e:
            logger.warning(f"Failed to parse failure section: {e}")
            return None

    def _extract_line_number(
        self,
        stack_trace: str
    ) -> int:
        """Extract line number from stack trace."""
        # Look for pattern like "file.py", line 42
        match = re.search(r'", line (\d+)', stack_trace)
        if match:
            return int(match.group(1))
        return 0

    def parse_coverage_json(
        self,
        coverage_path: str
    ) -> Dict[str, Any]:
        """
        Parse coverage.json file.

        Returns line coverage percentages by file.

        Args:
            coverage_path: Path to coverage.json

        Returns:
            {
                "percent": float,
                "covered_lines": int,
                "total_lines": int
            }
        """
        with open(coverage_path) as f:
            data = json.load(f)

        totals = data.get("totals", {})
        return {
            "percent": round(totals.get("percent_covered", 0.0), 2),
            "covered_lines": totals.get("covered_lines", 0),
            "total_lines": totals.get("num_statements", 0)
        }

    async def run_specific_test(
        self,
        test_file: str,
        test_name: str
    ) -> Dict[str, Any]:
        """
        Run a single test case.

        Useful for re-running after fixes.

        Args:
            test_file: Test file path
            test_name: Test function name

        Returns:
            Test results for single test
        """
        cmd = [
            "python", "-m", "pytest",
            f"{test_file}::{test_name}",
            "-v"
        ]

        process = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=30
        )

        return self.parse_pytest_output(process.stdout + process.stderr)

    def is_test_timeout(
        self,
        duration_seconds: float
    ) -> bool:
        """
        Check if test exceeded timeout.

        Target: <30s per test file, <5s per test.

        Args:
            duration_seconds: Test execution time

        Returns:
            True if timeout exceeded
        """
        return duration_seconds > 30.0


# ============================================================================
# Task 2: StackTraceAnalyzer for failure analysis
# ============================================================================

class ErrorCategory(str, Enum):
    """Error categorization for fix routing."""
    ASSERTION = "assertion"
    IMPORT = "import"
    DATABASE = "database"
    API = "api"
    LOGIC = "logic"
    TYPE_ERROR = "type_error"
    NONE_ERROR = "none_error"
    UNKNOWN = "unknown"


class StackTraceAnalyzer:
    """
    Analyze test failure stack traces.

    Categorizes errors, identifies root causes, suggests fixes.
    Routes failures to appropriate fix strategy.

    Attributes:
        error_patterns: Regex patterns for common errors

    Example:
        analyzer = StackTraceAnalyzer()
        analysis = analyzer.analyze_failure(failure)
        print(f"Category: {analysis['error_category']}")
        print(f"Fix strategy: {analysis['suggested_fix']}")
    """

    def __init__(self):
        """Initialize stack trace analyzer with error patterns."""
        self.error_patterns = {
            "AssertionError": r"AssertionError: (.+)",
            "AttributeError": r"AttributeError: '(.+?)' object has no attribute '(.+?)'",
            "ImportError": r"ImportError: (.+)",
            "ModuleNotFoundError": r"ModuleNotFoundError: (.+)",
            "TypeError": r"TypeError: (.+)",
            "ValueError": r"ValueError: (.+)",
            "KeyError": r"KeyError: '(.+?)'",
            "NameError": r"NameError: name '(.+?)' is not defined",
            "sqlalchemy.exc.IntegrityError": r"IntegrityError: (.+)",
            "sqlalchemy.orm.exc.*": r"(.+?)Error: (.+)",
        }

    def analyze_failure(
        self,
        failure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze test failure and identify root cause.

        Args:
            failure: Single failure from TestRunnerService

        Returns:
            {
                "error_type": str,
                "error_category": str,
                "root_cause": str,
                "suggested_fix": str,
                "file_to_fix": str,
                "line_number": int,
                "confidence": float
            }
        """
        error_type = failure.get("error_type", "Unknown")
        error_message = failure.get("error_message", "")
        stack_trace = failure.get("stack_trace", "")

        # Categorize error
        category = self.categorize_error(error_type, error_message)

        # Extract location
        location = self.extract_location_from_trace(stack_trace)
        file_to_fix = location.get("file", "")
        line_number = location.get("line", 0)

        # Identify root cause
        root_cause = self._identify_root_cause(
            error_type,
            error_message,
            category
        )

        # Identify fix strategy
        fix_strategy = self.identify_fix_strategy(category, root_cause)

        # Generate fix suggestion
        suggested_fix = self.generate_fix_suggestion({
            "error_type": error_type,
            "error_message": error_message,
            "category": category,
            "root_cause": root_cause,
            "strategy": fix_strategy,
            "file": file_to_fix,
            "line": line_number
        })

        # Calculate confidence
        confidence = self._calculate_confidence(category, error_type)

        return {
            "error_type": error_type,
            "error_category": category,
            "root_cause": root_cause,
            "suggested_fix": suggested_fix,
            "file_to_fix": file_to_fix,
            "line_number": line_number,
            "fix_strategy": fix_strategy,
            "confidence": confidence
        }

    def categorize_error(
        self,
        error_type: str,
        error_message: str
    ) -> ErrorCategory:
        """
        Categorize error by type.

        Categories: assertion, import, database, api, logic, type_error

        Args:
            error_type: Error type from exception
            error_message: Error message

        Returns:
            ErrorCategory enum
        """
        # Import errors
        if error_type in ["ImportError", "ModuleNotFoundError"]:
            return ErrorCategory.IMPORT

        # Assertion errors
        if error_type == "AssertionError":
            return ErrorCategory.ASSERTION

        # Database errors
        if "sqlalchemy" in error_type.lower() or "integrity" in error_type.lower():
            return ErrorCategory.DATABASE

        # None errors
        if error_type == "AttributeError" and "'NoneType'" in error_message:
            return ErrorCategory.NONE_ERROR

        # Type errors
        if error_type in ["TypeError", "ValueError"]:
            return ErrorCategory.TYPE_ERROR

        # Name errors (undefined variables)
        if error_type == "NameError":
            return ErrorCategory.IMPORT

        # Default to logic error
        return ErrorCategory.LOGIC

    def extract_location_from_trace(
        self,
        stack_trace: str
    ) -> Dict[str, Any]:
        """
        Extract file path and line number from stack trace.

        Returns {"file": str, "line": int}
        """
        # Look for pattern like "backend/core/service.py", line 42
        match = re.search(
            r'File "(.+?)", line (\d+)',
            stack_trace
        )

        if match:
            return {
                "file": match.group(1),
                "line": int(match.group(2))
            }

        return {"file": "", "line": 0}

    def _identify_root_cause(
        self,
        error_type: str,
        error_message: str,
        category: ErrorCategory
    ) -> str:
        """Identify root cause from error details."""
        # Import errors
        if category == ErrorCategory.IMPORT:
            if "No module named" in error_message:
                return f"Missing module: {error_message}"

        # Assertion errors
        if category == ErrorCategory.ASSERTION:
            if "assert None ==" in error_message:
                return "Value is None when it shouldn't be"
            if "assert" in error_message and "==" in error_message:
                return "Expected value doesn't match actual"

        # None errors
        if category == ErrorCategory.NONE_ERROR:
            return "Object is None, missing null check"

        # Database errors
        if category == ErrorCategory.DATABASE:
            if "foreign key" in error_message.lower():
                return "Foreign key constraint violation"
            if "unique" in error_message.lower():
                return "Unique constraint violation"
            if "not null" in error_message.lower():
                return "Required field is None"

        # Type errors
        if category == ErrorCategory.TYPE_ERROR:
            return f"Type mismatch: {error_message}"

        return f"Unknown root cause: {error_type}"

    def identify_fix_strategy(
        self,
        error_category: ErrorCategory,
        root_cause: str
    ) -> str:
        """
        Identify fix strategy based on error category.

        Strategies: add_import, fix_assertion, add_mock, fix_query,
        add_type_hint, add_none_check, add_db_commit
        """
        strategies = {
            ErrorCategory.IMPORT: "add_import",
            ErrorCategory.ASSERTION: "fix_assertion",
            ErrorCategory.DATABASE: "fix_query",
            ErrorCategory.API: "add_mock",
            ErrorCategory.NONE_ERROR: "add_none_check",
            ErrorCategory.TYPE_ERROR: "add_type_hint",
            ErrorCategory.LOGIC: "fix_logic",
        }

        return strategies.get(error_category, "manual_review")

    def generate_fix_suggestion(
        self,
        analysis: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable fix suggestion.

        Example: "Add db.commit() after creating OAuthSession"
        """
        strategy = analysis["strategy"]
        error_message = analysis["error_message"]

        suggestions = {
            "add_import": f"Add missing import for: {error_message}",
            "fix_assertion": f"Fix assertion logic - {error_message}",
            "fix_query": "Fix database query or add db.commit()",
            "add_mock": "Add mock for external API call",
            "add_none_check": "Add None check before accessing attribute",
            "add_type_hint": "Add type hint or fix type mismatch",
            "fix_logic": "Review and fix business logic",
            "manual_review": "Requires manual review and fix"
        }

        return suggestions.get(strategy, "Manual review required")

    def _calculate_confidence(
        self,
        category: ErrorCategory,
        error_type: str
    ) -> float:
        """Calculate confidence score for analysis (0-1)."""
        # High confidence for import/None errors
        if category in [ErrorCategory.IMPORT, ErrorCategory.NONE_ERROR]:
            return 0.95

        # Medium-high for assertion/type errors
        if category in [ErrorCategory.ASSERTION, ErrorCategory.TYPE_ERROR]:
            return 0.85

        # Medium for database errors
        if category == ErrorCategory.DATABASE:
            return 0.75

        # Lower for logic errors
        return 0.60


# ============================================================================
# Task 6: TestResultStorage for result persistence
# ============================================================================

class TestResultStorage:
    """
    Store and report test results.

    Saves results to AutonomousWorkflow, creates AgentLog entries,
    generates human-readable reports.

    Attributes:
        db: Database session

    Example:
        storage = TestResultStorage(db)
        storage.save_results_to_workflow(workflow_id, results)
        report = storage.generate_test_report(results)
    """

    def __init__(self, db: Session):
        """
        Initialize result storage.

        Args:
            db: Database session
        """
        self.db = db

    def save_results_to_workflow(
        self,
        workflow_id: str,
        results: Dict[str, Any]
    ) -> None:
        """
        Save test results to AutonomousWorkflow.

        Updates test_results JSON field.

        Args:
            workflow_id: Autonomous workflow ID
            results: Test results from TestRunnerService
        """
        workflow = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.test_results = results
            workflow.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Saved test results to workflow {workflow_id}")
        else:
            logger.warning(f"Workflow {workflow_id} not found")

    def create_agent_log(
        self,
        workflow_id: str,
        agent_id: str,
        phase: str,
        action: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str,
        error_message: Optional[str] = None
    ) -> AgentLog:
        """
        Create AgentLog entry for test execution.

        Tracks test run for audit trail.

        Args:
            workflow_id: Autonomous workflow ID
            agent_id: Agent ID that ran tests
            phase: Current phase (e.g., "test", "fix")
            action: Action performed (e.g., "run_tests")
            input_data: Input to action
            output_data: Output from action
            status: Status (success, failure, partial)
            error_message: Optional error message

        Returns:
            Created AgentLog instance
        """
        log = AgentLog(
            workflow_id=workflow_id,
            agent_id=agent_id,
            phase=phase,
            action=action,
            input_data=input_data,
            output_data=output_data,
            status=status,
            error_message=error_message,
            timestamp=datetime.utcnow()
        )

        self.db.add(log)
        self.db.commit()

        return log

    def generate_test_report(
        self,
        results: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable test report.

        Returns formatted report with:
        - Summary (passed/failed/total)
        - Failure details
        - Coverage summary
        - Recommendations

        Args:
            results: Test results from TestRunnerService

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("TEST EXECUTION REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        lines.append("Summary:")
        lines.append(f"  Passed:   {results['passed']}")
        lines.append(f"  Failed:   {results['failed']}")
        lines.append(f"  Skipped:  {results['skipped']}")
        lines.append(f"  Total:    {results['total']}")
        lines.append(f"  Duration: {results['duration_seconds']:.2f}s")
        lines.append("")

        # Coverage
        if "coverage" in results:
            cov = results["coverage"]
            lines.append("Coverage:")
            lines.append(f"  Percent: {cov['percent']}%")
            lines.append(f"  Lines:   {cov['covered_lines']} / {cov['total_lines']}")
            lines.append("")

        # Failures
        if results["failures"]:
            lines.append(f"Failures ({len(results['failures']):}):")
            lines.append("-" * 60)
            for i, failure in enumerate(results["failures"], 1):
                lines.append(f"\n{i}. {failure['test_name']}")
                lines.append(f"   Type:    {failure['error_type']}")
                lines.append(f"   Message: {failure['error_message'][:100]}")
                if failure['line_number']:
                    lines.append(f"   Line:    {failure['line_number']}")
            lines.append("")

        # Recommendations
        lines.append("Recommendations:")
        if results["failed"] == 0:
            lines.append("  ✓ All tests passing!")
        else:
            lines.append(f"  → Fix {results['failed']} failing test(s)")

        if "coverage" in results:
            cov_pct = results["coverage"]["percent"]
            if cov_pct < 80:
                lines.append(f"  → Improve coverage to 80%+ (current: {cov_pct}%)")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def calculate_coverage_delta(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate coverage improvement.

        Returns {"line_delta": float, "percent_delta": float}

        Args:
            before: Coverage data before fixes
            after: Coverage data after fixes

        Returns:
            Coverage deltas
        """
        before_pct = before.get("coverage", {}).get("percent", 0.0)
        after_pct = after.get("coverage", {}).get("percent", 0.0)

        before_lines = before.get("coverage", {}).get("covered_lines", 0)
        after_lines = after.get("coverage", {}).get("covered_lines", 0)

        return {
            "line_delta": after_lines - before_lines,
            "percent_delta": after_pct - before_pct
        }
