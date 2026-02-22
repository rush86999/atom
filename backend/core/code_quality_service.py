"""
Code Quality Service - Automated code quality checking and enforcement.

Provides automated quality gates for:
- mypy strict type checking
- Black code formatting
- isort import sorting
- flake8 linting
- Google-style docstring validation

Integration:
- Used by CoderAgent for quality enforcement
- Runs tools via subprocess for real validation
- Graceful degradation when tools unavailable

Performance targets:
- mypy check: <10 seconds for typical file
- black format: <5 seconds
- isort sort: <2 seconds
- flake8 lint: <5 seconds
"""

import ast
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.feature_flags import QUALITY_ENFORCEMENT_ENABLED, EMERGENCY_QUALITY_BYPASS

logger = logging.getLogger(__name__)


class QualityCheckResult:
    """Result of a quality check."""

    def __init__(
        self,
        check_name: str,
        passed: bool,
        tool_used: str = "",
        output: str = "",
        error: str = ""
    ):
        self.check_name = check_name
        self.passed = passed
        self.tool_used = tool_used
        self.output = output
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "tool_used": self.tool_used,
            "output": self.output,
            "error": self.error
        }


class CodeQualityService:
    """
    Automated code quality checking and enforcement.

    Runs mypy, black, isort, flake8 via subprocess to validate
    generated code meets Atom standards.

    Attributes:
        project_root: Root directory for tool config files
        mypy_config: Path to mypy.ini configuration

    Example:
        service = CodeQualityService(project_root="backend")
        result = await service.check_mypy(code, "core/service.py")
        if result["passed"]:
            print("Type checking passed!")
    """

    def __init__(self, project_root: str = "backend"):
        """
        Initialize code quality service.

        Args:
            project_root: Root directory containing tool configs
        """
        self.project_root = Path(project_root)
        self.mypy_config = self.project_root / "mypy.ini"
        self.pyproject_toml = self.project_root / "pyproject.toml"
        self.isort_cfg = self.project_root / ".isort.cfg"

    async def check_mypy(
        self, code: str, file_path: str
    ) -> Dict[str, Any]:
        """
        Run mypy type checking on code.

        Validates type hints using mypy strict mode.
        Returns errors and suggestions for fixing type issues.

        Args:
            code: Python source code to check
            file_path: Virtual file path for module resolution

        Returns:
            {
                "passed": bool,
                "errors": [str],  # Type errors found
                "suggestions": [str]  # Fix suggestions
            }
        """
        logger.info(f"Running mypy on {file_path}")

        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            # Build mypy command
            cmd = [
                "mypy",
                tmp_path,
                "--strict",
                "--show-error-codes",
                "--no-error-summary",
            ]

            # Add config if exists
            if self.mypy_config.exists():
                cmd.extend(["--config-file", str(self.mypy_config)])

            # Run mypy
            result = self._run_command(cmd)

            # Clean up temp file
            os.unlink(tmp_path)

            # Parse output
            errors = []
            suggestions = []

            if result["returncode"] != 0:
                # Parse mypy errors
                for line in result["stderr"].split("\n"):
                    if ":" in line and "error:" in line:
                        errors.append(line.strip())

                # Generate suggestions
                suggestions = self._generate_mypy_suggestions(errors)

            return {
                "passed": result["returncode"] == 0,
                "errors": errors,
                "suggestions": suggestions,
                "raw_output": result["stderr"],
            }

        except FileNotFoundError:
            return self._handle_tool_unavailable("mypy")
        except Exception as e:
            logger.error(f"mypy check failed: {e}")
            return {
                "passed": False,
                "errors": [str(e)],
                "suggestions": [],
                "raw_output": str(e),
            }

    async def format_with_black(self, code: str) -> Dict[str, Any]:
        """
        Format code with Black.

        Applies Black code formatting standards.
        Returns formatted code with diff if changes made.

        Args:
            code: Python source code to format

        Returns:
            {
                "formatted_code": str,
                "changed": bool,  # True if formatting made changes
                "diff": str  # Unified diff if changed
            }
        """
        logger.info("Running black formatter")

        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            # Build black command
            cmd = [
                "black",
                tmp_path,
                "--quiet",
                "--line-length", "100",
            ]

            # Add config if exists
            if self.pyproject_toml.exists():
                cmd.extend(["--config", str(self.pyproject_toml)])

            # Run black
            result = self._run_command(cmd)

            # Read formatted code
            with open(tmp_path, "r") as f:
                formatted_code = f.read()

            # Generate diff if changed
            diff = ""
            changed = code != formatted_code
            if changed:
                diff = self._generate_diff(code, formatted_code, tmp_path)

            # Clean up temp file
            os.unlink(tmp_path)

            return {
                "formatted_code": formatted_code,
                "changed": changed,
                "diff": diff,
            }

        except FileNotFoundError:
            if QUALITY_ENFORCEMENT_ENABLED and not EMERGENCY_QUALITY_BYPASS:
                logger.error("black not available and QUALITY_ENFORCEMENT_ENABLED=true")
                return {
                    "formatted_code": code,
                    "changed": False,
                    "diff": "",
                    "error": "black not available and QUALITY_ENFORCEMENT_ENABLED=true"
                }
            logger.warning("black not found - returning original code")
            return {
                "formatted_code": code,
                "changed": False,
                "diff": "",
            }
        except Exception as e:
            logger.error(f"black formatting failed: {e}")
            return {
                "formatted_code": code,
                "changed": False,
                "diff": "",
                "error": str(e),
            }

    async def sort_imports(self, code: str) -> Dict[str, Any]:
        """
        Sort imports with isort.

        Applies isort import ordering standards.
        Returns sorted code with diff if changes made.

        Args:
            code: Python source code with imports

        Returns:
            {
                "sorted_code": str,
                "changed": bool,
                "diff": str
            }
        """
        logger.info("Running isort")

        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            # Build isort command
            cmd = [
                "isort",
                tmp_path,
                "--quiet",
            ]

            # Add config if exists
            if self.isort_cfg.exists():
                cmd.extend(["--settings-path", str(self.isort_cfg)])

            # Run isort
            result = self._run_command(cmd)

            # Read sorted code
            with open(tmp_path, "r") as f:
                sorted_code = f.read()

            # Generate diff if changed
            diff = ""
            changed = code != sorted_code
            if changed:
                diff = self._generate_diff(code, sorted_code, tmp_path)

            # Clean up temp file
            os.unlink(tmp_path)

            return {
                "sorted_code": sorted_code,
                "changed": changed,
                "diff": diff,
            }

        except FileNotFoundError:
            if QUALITY_ENFORCEMENT_ENABLED and not EMERGENCY_QUALITY_BYPASS:
                logger.error("isort not available and QUALITY_ENFORCEMENT_ENABLED=true")
                return {
                    "sorted_code": code,
                    "changed": False,
                    "diff": "",
                    "error": "isort not available and QUALITY_ENFORCEMENT_ENABLED=true"
                }
            logger.warning("isort not found - returning original code")
            return {
                "sorted_code": code,
                "changed": False,
                "diff": "",
            }
        except Exception as e:
            logger.error(f"isort failed: {e}")
            return {
                "sorted_code": code,
                "changed": False,
                "diff": "",
                "error": str(e),
            }

    async def run_flake8(
        self, code: str, file_path: str
    ) -> Dict[str, Any]:
        """
        Run flake8 linting.

        Checks code style and syntax issues with flake8.

        Args:
            code: Python source code to lint
            file_path: Virtual file path for reporting

        Returns:
            {
                "passed": bool,
                "warnings": [str],
                "errors": [str]
            }
        """
        logger.info(f"Running flake8 on {file_path}")

        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            # Build flake8 command
            cmd = [
                "flake8",
                tmp_path,
                "--max-line-length=100",
                "--ignore=E501",  # Line too long (black handles this)
            ]

            # Run flake8
            result = self._run_command(cmd)

            # Clean up temp file
            os.unlink(tmp_path)

            # Parse output
            warnings = []
            errors = []

            for line in result["stdout"].split("\n"):
                if line.strip():
                    # Classify as warning or error
                    if any(code in line for code in ["E9", "F6", "F8"]):
                        errors.append(line.strip())
                    else:
                        warnings.append(line.strip())

            return {
                "passed": len(errors) == 0,
                "warnings": warnings,
                "errors": errors,
                "raw_output": result["stdout"],
            }

        except FileNotFoundError:
            return self._handle_tool_unavailable("flake8", return_format="flake8")
        except Exception as e:
            logger.error(f"flake8 failed: {e}")
            return {
                "passed": False,
                "warnings": [],
                "errors": [str(e)],
                "raw_output": str(e),
            }

    async def enforce_all_quality_gates(
        self, code: str, file_path: str
    ) -> Dict[str, Any]:
        """
        Run all quality checks and apply fixes.

        Runs: mypy -> black -> isort -> flake8
        Returns final code with all fixes applied.

        Args:
            code: Python source code to validate
            file_path: Virtual file path for module resolution

        Returns:
            {
                "code": str,  # Final code with fixes applied
                "passed": bool,
                "quality_report": {
                    "mypy_passed": bool,
                    "black_formatted": bool,
                    "isort_sorted": bool,
                    "flake8_passed": bool
                },
                "errors": [str],
                "warnings": [str]
            }
        """
        logger.info(f"Enforcing quality gates for {file_path}")

        current_code = code
        errors = []
        warnings = []

        # 1. Sort imports first (isort)
        isort_result = await self.sort_imports(current_code)
        current_code = isort_result["sorted_code"]
        logger.info(f"isort: {'changed' if isort_result['changed'] else 'no change'}")

        # 2. Format with black
        black_result = await self.format_with_black(current_code)
        current_code = black_result["formatted_code"]
        logger.info(f"black: {'changed' if black_result['changed'] else 'no change'}")

        # 3. Type check with mypy
        mypy_result = await self.check_mypy(current_code, file_path)
        errors.extend(mypy_result["errors"])
        logger.info(f"mypy: {'passed' if mypy_result['passed'] else 'failed'}")

        # 4. Lint with flake8
        flake8_result = await self.run_flake8(current_code, file_path)
        warnings.extend(flake8_result["warnings"])
        errors.extend(flake8_result["errors"])
        logger.info(f"flake8: {'passed' if flake8_result['passed'] else 'failed'}")

        # Build quality report
        quality_report = {
            "isort_sorted": True,  # Always applied
            "black_formatted": True,  # Always applied
            "mypy_passed": mypy_result["passed"],
            "flake8_passed": flake8_result["passed"],
        }

        # Overall pass requires all checks to pass
        passed = all(quality_report.values())

        return {
            "code": current_code,
            "passed": passed,
            "quality_report": quality_report,
            "errors": errors,
            "warnings": warnings,
        }

    def _handle_tool_unavailable(self, tool_name: str, check_name: str = None, return_format: str = "default") -> Dict[str, Any]:
        """
        Handle unavailable tools with configurable graceful degradation.

        Args:
            tool_name: Name of the unavailable tool (e.g., "mypy", "black")
            check_name: Name of the quality check (defaults to tool_name)
            return_format: Format for return value ("default", "flake8")

        Returns:
            Quality check result based on enforcement mode
        """
        if check_name is None:
            check_name = tool_name

        if EMERGENCY_QUALITY_BYPASS:
            # Emergency mode: allow degradation
            logger.warning(f"{tool_name} not available (EMERGENCY_QUALITY_BYPASS active)")
            if return_format == "flake8":
                return {
                    "passed": True,
                    "warnings": [],
                    "errors": [],
                    "raw_output": f"{tool_name} not available (EMERGENCY_BYPASS active)",
                }
            return {
                "passed": True,
                "errors": [],
                "suggestions": [],
                "raw_output": f"{tool_name} not available (EMERGENCY_BYPASS active)",
            }
        elif QUALITY_ENFORCEMENT_ENABLED:
            # Enforcement mode: fail when tools unavailable
            logger.error(f"{tool_name} not available and QUALITY_ENFORCEMENT_ENABLED=true")
            if return_format == "flake8":
                return {
                    "passed": False,
                    "warnings": [],
                    "errors": [f"{tool_name} not available and QUALITY_ENFORCEMENT_ENABLED=true"],
                    "raw_output": f"{tool_name} not available",
                }
            return {
                "passed": False,
                "errors": [f"{tool_name} not available and QUALITY_ENFORCEMENT_ENABLED=true"],
                "suggestions": [f"Install {tool_name} or set QUALITY_ENFORCEMENT_ENABLED=false"],
                "raw_output": f"{tool_name} not available",
            }
        else:
            # Advisory mode: allow degradation
            logger.warning(f"{tool_name} not available (enforcement disabled)")
            if return_format == "flake8":
                return {
                    "passed": True,
                    "warnings": [],
                    "errors": [],
                    "raw_output": f"{tool_name} not available (enforcement disabled)",
                }
            return {
                "passed": True,
                "errors": [],
                "suggestions": [],
                "raw_output": f"{tool_name} not available (enforcement disabled)",
            }

    def _run_command(
        self, command: List[str], input_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run subprocess command and capture output.

        Args:
            command: Command and arguments to run
            input_text: Optional stdin input

        Returns:
            {
                "returncode": int,
                "stdout": str,
                "stderr": str
            }
        """
        logger.debug(f"Running: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                input=input_text,
                timeout=30,
            )

            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Command timed out after 30 seconds",
            }
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _generate_mypy_suggestions(self, errors: List[str]) -> List[str]:
        """
        Generate fix suggestions for mypy errors.

        Args:
            errors: List of mypy error messages

        Returns:
            List of suggestion strings
        """
        suggestions = []

        for error in errors:
            # Common mypy error patterns
            if "has no attribute" in error:
                suggestions.append("Add type hints for the attribute or use getattr()")
            elif "incompatible return value type" in error:
                suggestions.append("Check return type annotation matches actual return value")
            elif "incompatible type" in error:
                suggestions.append("Add type annotations or use typing.cast()")
            elif "unused" in error or "ignore" in error:
                suggestions.append("Remove unused import or add # type: ignore comment")
            else:
                suggestions.append("Add appropriate type hints")

        return list(set(suggestions))  # Deduplicate

    def _generate_diff(self, original: str, formatted: str, file_path: str) -> str:
        """
        Generate unified diff between original and formatted code.

        Args:
            original: Original code
            formatted: Formatted code
            file_path: File path for diff header

        Returns:
            Unified diff string
        """
        try:
            import difflib

            original_lines = original.splitlines(keepends=True)
            formatted_lines = formatted.splitlines(keepends=True)

            diff = difflib.unified_diff(
                original_lines,
                formatted_lines,
                fromfile=f"{file_path} (original)",
                tofile=f"{file_path} (formatted)",
                lineterm="",
            )

            return "".join(diff)

        except Exception as e:
            logger.error(f"Failed to generate diff: {e}")
            return ""

    def validate_docstrings(self, code: str) -> Dict[str, Any]:
        """
        Check for Google-style docstrings.

        Parses AST to find functions/methods and validates
        they have Google-style docstrings.

        Args:
            code: Python source code to validate

        Returns:
            {
                "valid_count": int,
                "missing_count": int,
                "missing_functions": [str]  # Function names missing docstrings
            }
        """
        logger.info("Validating docstrings")

        try:
            tree = ast.parse(code)

            valid_count = 0
            missing_functions = []

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private methods
                    if node.name.startswith("_"):
                        continue

                    # Check for docstring
                    docstring = ast.get_docstring(node)

                    if docstring:
                        # Validate Google-style format
                        if self._is_google_style_docstring(docstring):
                            valid_count += 1
                        else:
                            missing_functions.append(node.name)
                    else:
                        missing_functions.append(node.name)

            return {
                "valid_count": valid_count,
                "missing_count": len(missing_functions),
                "missing_functions": missing_functions,
            }

        except SyntaxError as e:
            logger.error(f"Failed to parse code: {e}")
            return {
                "valid_count": 0,
                "missing_count": 0,
                "missing_functions": [],
                "error": str(e),
            }

    def _is_google_style_docstring(self, docstring: str) -> bool:
        """
        Check if docstring follows Google style.

        Google-style docstrings have:
        - Summary line
        - Args section (if has parameters)
        - Returns section (if returns value)
        - Raises section (if raises exceptions)

        Args:
            docstring: Docstring content

        Returns:
            True if Google-style format detected
        """
        # Check for common Google-style sections
        google_sections = ["Args:", "Returns:", "Raises:", "Yields:", "Attributes:"]

        # Has at least one Google section
        has_google_section = any(section in docstring for section in google_sections)

        # Or has Args/Returns pattern
        has_args_pattern = "Args:" in docstring or "Arguments:" in docstring
        has_returns_pattern = "Returns:" in docstring

        return has_google_section or has_args_pattern or has_returns_pattern

    def validate_type_hints(self, file_path: str) -> QualityCheckResult:
        """
        Validate that all functions have type hints using AST parsing.

        Args:
            file_path: Path to Python file to validate

        Returns:
            QualityCheckResult with functions missing type hints
        """
        try:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read(), filename=file_path)

            functions_missing_hints = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private methods and dunder methods
                    if node.name.startswith('_'):
                        continue

                    # Check return type annotation
                    if node.returns is None:
                        functions_missing_hints.append(f"{node.name} (line {node.lineno})")
                        continue

                    # Check parameter annotations
                    for arg in node.args.args:
                        if arg.arg == 'self':
                            continue
                        if arg.annotation is None:
                            functions_missing_hints.append(f"{node.name} (line {node.lineno})")
                            break

            if functions_missing_hints:
                return QualityCheckResult(
                    check_name="type_hints",
                    passed=False,
                    tool_used="ast",
                    output="",
                    error=f"Functions missing type hints: {', '.join(functions_missing_hints[:5])}"
                )

            return QualityCheckResult(
                check_name="type_hints",
                passed=True,
                tool_used="ast",
                output=f"All functions have type hints",
                error=""
            )

        except Exception as e:
            return QualityCheckResult(
                check_name="type_hints",
                passed=False,
                tool_used="ast",
                output="",
                error=f"Failed to parse type hints: {str(e)}"
            )

    async def validate_code_quality(
        self,
        file_path: str,
        language: str = "python"
    ) -> "QualityCheckResults":
        """
        Run all quality checks on a file.

        Args:
            file_path: Path to file to validate
            language: Programming language (default: python)

        Returns:
            QualityCheckResults with all check results
        """
        results = []

        # Type hints validation
        if language == "python":
            type_hint_result = self.validate_type_hints(file_path)
            results.append(type_hint_result)

        return QualityCheckResults(results)


class QualityCheckResults:
    """Container for multiple quality check results."""

    def __init__(self, results: List[QualityCheckResult]):
        self.results = results

    @property
    def all_passed(self) -> bool:
        """Check if all quality checks passed."""
        return all(r.passed for r in self.results)

    def get_summary(self) -> str:
        """Get summary of quality check results."""
        lines = ["Quality Check Results:"]
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            lines.append(f"  {status}: {result.check_name}")
            if result.error:
                lines.append(f"    Error: {result.error}")
        return "\n".join(lines)
