"""
RegressionTestGenerator - Convert BugReport objects to pytest test files.

This module provides automated regression test generation from discovered bugs,
closing the feedback loop by preventing bug recurrence.

Example:
    >>> from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod
    >>> from tests.bug_discovery.feedback_loops.regression_test_generator import RegressionTestGenerator
    >>>
    >>> bug = BugReport(
    ...     discovery_method=DiscoveryMethod.FUZZING,
    ...     test_name="test_agent_api_fuzzing",
    ...     error_message="SQL injection in agent_id parameter",
    ...     error_signature="abc123def4567890",
    ...     severity="critical"
    ... )
    >>>
    >>> generator = RegressionTestGenerator()
    >>> test_path = generator.generate_test_from_bug(bug)
    >>> print(f"Generated: {test_path}")
"""

from pathlib import Path
from typing import List, Dict, Any
from jinja2 import Template
import sys

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod


class RegressionTestGenerator:
    """
    Generate regression tests from BugReport objects.

    Converts bug findings into permanent pytest test files with:
    - Reproducible test cases (minimal reproduction from bug metadata)
    - Test fixtures (db_session, authenticated_page, browser)
    - Markers (@pytest.mark.regression, @pytest.mark.slow)
    - Docstrings (bug description, reproduction steps, expected behavior)

    Example:
        generator = RegressionTestGenerator()
        test_path = generator.generate_test_from_bug(
            bug=bug_report,
            output_dir="tests/bug_discovery/storage/regression_tests/"
        )
        print(f"Generated regression test: {test_path}")
    """

    def __init__(self, templates_dir: str = None):
        """
        Initialize RegressionTestGenerator.

        Args:
            templates_dir: Path to Jinja2 templates directory.
                          Defaults to bug_discovery/templates/.

        Note:
            Creates templates_dir if it doesn't exist.
        """
        if templates_dir is None:
            # Default to bug_discovery/templates/
            templates_dir = Path(__file__).parent.parent / "templates"
        else:
            templates_dir = Path(templates_dir)

        # Create templates directory if it doesn't exist
        templates_dir.mkdir(parents=True, exist_ok=True)

        self.templates_dir = templates_dir

    def generate_test_from_bug(
        self,
        bug: BugReport,
        output_dir: str = None,
        bug_id: str = None
    ) -> str:
        """
        Generate pytest test file from BugReport.

        Args:
            bug: BugReport object with bug metadata
            output_dir: Directory for generated test file.
                        Defaults to storage/regression_tests/.
            bug_id: Unique bug identifier. Defaults to error_signature[:8].

        Returns:
            Full path to generated test file.

        Example:
            >>> bug = BugReport(
            ...     discovery_method=DiscoveryMethod.FUZZING,
            ...     test_name="test_agent_api",
            ...     error_message="SQL injection",
            ...     error_signature="abc123def4567890"
            ... )
            >>> generator = RegressionTestGenerator()
            >>> path = generator.generate_test_from_bug(bug)
            >>> assert path.endswith(".py")
        """
        # Generate test filename: test_regression_{discovery_method}_{bug_id}.py
        if bug_id is None:
            # Use first 8 chars of error signature SHA256
            bug_id = bug.error_signature[:8]

        # Handle discovery_method (enum or string)
        if isinstance(bug.discovery_method, str):
            method = bug.discovery_method
        else:
            method = bug.discovery_method.value

        filename = f"test_regression_{method}_{bug_id}.py"

        # Set output directory
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "storage" / "regression_tests"
        else:
            output_dir = Path(output_dir)

        # Create output directory if needed
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get template for discovery method
        template = self._get_template_for_method(bug.discovery_method)

        # Render template with bug metadata
        reproduction_steps = self._infer_reproduction_steps(bug)
        expected_behavior = self._infer_expected_behavior(bug)

        test_content = template.render(
            bug=bug,
            bug_id=bug_id,
            discovery_method=method,
            reproduction_steps=reproduction_steps,
            expected_behavior=expected_behavior
        )

        # Write test file
        test_path = output_dir / filename
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        return str(test_path)

    def generate_tests_from_bug_list(
        self,
        bugs: List[BugReport],
        output_dir: str = None
    ) -> List[str]:
        """
        Generate regression tests from list of BugReports.

        Args:
            bugs: List of BugReport objects
            output_dir: Directory for generated test files.

        Returns:
            List of generated test file paths.

        Example:
            >>> bugs = [bug1, bug2, bug3]
            >>> generator = RegressionTestGenerator()
            >>> paths = generator.generate_tests_from_bug_list(bugs)
            >>> assert len(paths) == 3
        """
        generated_paths = []

        for bug in bugs:
            try:
                test_path = self.generate_test_from_bug(bug, output_dir=output_dir)
                generated_paths.append(test_path)
            except Exception as e:
                # Handle exceptions gracefully - continue with next bug
                print(f"Warning: Failed to generate test for bug {bug.error_signature[:8]}: {e}")
                continue

        return generated_paths

    def _get_template_for_method(self, discovery_method: DiscoveryMethod) -> Template:
        """
        Get Jinja2 template for discovery method.

        Args:
            discovery_method: DiscoveryMethod enum or string (FUZZING, CHAOS, PROPERTY, BROWSER)

        Returns:
            Jinja2 Template object

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        # Handle enum or string
        if isinstance(discovery_method, str):
            method = discovery_method
        else:
            method = discovery_method.value

        # Map discovery method to template file
        template_map = {
            "fuzzing": "fuzzing_regression_template.py.j2",
            "chaos": "chaos_regression_template.py.j2",
            "property": "property_regression_template.py.j2",
            "browser": "browser_regression_template.py.j2",
        }

        template_filename = template_map.get(method, "pytest_regression_template.py.j2")
        template_path = self.templates_dir / template_filename

        # Read and parse template
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        return Template(template_content)

    def _infer_reproduction_steps(self, bug: BugReport) -> str:
        """
        Infer reproduction steps from bug metadata.

        Args:
            bug: BugReport object

        Returns:
            Multi-line string with reproduction steps
        """
        steps = []

        # Add test run command if test_name exists
        if bug.test_name:
            steps.append(f"1. Run test: pytest {bug.test_name}")

        # Add discovery method specific context
        method = bug.discovery_method.value if isinstance(bug.discovery_method, DiscoveryMethod) else bug.discovery_method

        if method == "fuzzing":
            endpoint = bug.metadata.get("target_endpoint", "unknown")
            crash_file = bug.metadata.get("crash_file", "")
            if crash_file:
                steps.append(f"2. Fuzz endpoint {endpoint} with input from {crash_file}")
            else:
                steps.append(f"2. Fuzz endpoint {endpoint}")

        elif method == "chaos":
            experiment = bug.metadata.get("experiment_name", "unknown chaos experiment")
            steps.append(f"2. Inject failure: {experiment}")

        elif method == "property":
            steps.append("2. Run property test with Hypothesis")
            if bug.test_name:
                steps.append(f"3. Test: {bug.test_name}")

        elif method == "browser":
            url = bug.metadata.get("url", "unknown")
            steps.append(f"2. Navigate to: {url}")
            steps.append("3. Check for console errors and accessibility violations")

        return "\n".join(steps) if steps else "See bug metadata for reproduction details"

    def _infer_expected_behavior(self, bug: BugReport) -> str:
        """
        Infer expected behavior from bug metadata.

        Args:
            bug: BugReport object

        Returns:
            Description of expected behavior
        """
        method = bug.discovery_method.value if isinstance(bug.discovery_method, DiscoveryMethod) else bug.discovery_method

        if method == "fuzzing":
            return "Endpoint should handle malformed/malicious input gracefully (400/422 response, no crash)"

        elif method == "chaos":
            return "System should degrade gracefully under failure and recover after failure injection stops"

        elif method == "property":
            invariant = bug.metadata.get("invariant", "Property invariant")
            return f"Invariant must hold: {invariant}"

        elif method == "browser":
            return "Page should load without console errors or accessibility violations"

        return "Bug should not reproduce - system handles edge case correctly"

    def archive_test(self, test_path: str, reason: str = "verified") -> str:
        """
        Archive test for verified fixes (move to archived/ subdirectory).

        Args:
            test_path: Path to test file to archive
            reason: Reason for archival (default: "verified")

        Returns:
            New archived path

        Example:
            >>> generator = RegressionTestGenerator()
            >>> archived_path = generator.archive_test("test_regression_fuzzing_abc123.py")
            >>> assert "archived" in archived_path
        """
        test_path = Path(test_path)
        filename = test_path.name

        # Create archived/ subdirectory
        archived_dir = test_path.parent / "archived"
        archived_dir.mkdir(parents=True, exist_ok=True)

        # Move test to archived/
        archived_path = archived_dir / filename
        test_path.rename(archived_path)

        return str(archived_path)
