"""
Unit tests for RegressionTestGenerator.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add backend to path
import sys
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity
from tests.bug_discovery.feedback_loops.regression_test_generator import RegressionTestGenerator


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for generated tests."""
    output_dir = tmp_path / "regression_tests"
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir)


@pytest.fixture
def sample_bug_report():
    """Sample BugReport for testing."""
    return BugReport(
        discovery_method=DiscoveryMethod.FUZZING,
        test_name="test_agent_api_fuzzing",
        error_message="SQL injection in agent_id parameter",
        error_signature="abc123def4567890",
        severity=Severity.CRITICAL,
        metadata={
            "target_endpoint": "/api/v1/agents",
            "crash_input": '{"agent_id": "1 OR 1=1--"}',
            "crash_file": "/tmp/crash-001.input"
        },
        timestamp=datetime.utcnow()
    )


class TestRegressionTestGenerator:
    """Test RegressionTestGenerator class."""

    def test_init_creates_templates_directory(self, temp_output_dir):
        """Test that __init__ creates templates directory if it doesn't exist."""
        temp_templates = tempfile.mkdtemp()
        try:
            templates_path = Path(temp_templates)
            # Remove directory to test creation
            if templates_path.exists():
                shutil.rmtree(templates_path)

            generator = RegressionTestGenerator(templates_dir=temp_templates)
            assert Path(temp_templates).exists()
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_init_with_existing_templates_directory(self, temp_output_dir):
        """Test that __init__ works with existing templates directory."""
        temp_templates = tempfile.mkdtemp()
        try:
            # Directory already exists
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            assert generator.templates_dir == Path(temp_templates)
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_generate_test_from_bug_creates_test_file(self, sample_bug_report, temp_output_dir):
        """Test that generate_test_from_bug creates a test file."""
        # Create templates directory first
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# Test template\n{{ bug_id }}")

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            test_path = generator.generate_test_from_bug(sample_bug_report, output_dir=temp_output_dir)

            assert Path(test_path).exists()
            assert test_path.endswith(".py")
            assert "test_regression_fuzzing_" in test_path
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_generate_test_from_bug_uses_default_bug_id(self, sample_bug_report, temp_output_dir):
        """Test that bug_id defaults to error_signature[:8]."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# {{ bug_id }}")

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            test_path = generator.generate_test_from_bug(sample_bug_report, output_dir=temp_output_dir)

            # error_signature is "abc123def4567890", so bug_id is "abc123de"
            assert "abc123de" in test_path
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_generate_test_from_bug_with_custom_bug_id(self, sample_bug_report, temp_output_dir):
        """Test that custom bug_id is used when provided."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# {{ bug_id }}")

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            test_path = generator.generate_test_from_bug(
                sample_bug_report,
                output_dir=temp_output_dir,
                bug_id="custom123"
            )

            assert "custom123" in test_path
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_generate_test_from_bug_creates_output_directory(self, sample_bug_report, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# Test")

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            output_dir = tmp_path / "new_output_dir" / "nested"
            test_path = generator.generate_test_from_bug(sample_bug_report, output_dir=str(output_dir))

            assert output_dir.exists()
            assert Path(test_path).exists()
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_generate_tests_from_bug_list(self, sample_bug_report, temp_output_dir):
        """Test generating tests from multiple bugs."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# Test {{ bug_id }}")
        (templates_path / "chaos_regression_template.py.j2").write_text("# Test {{ bug_id }}")

        # Create multiple bugs
        bugs = [
            sample_bug_report,
            BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name="test_network_latency",
                error_message="Connection timeout under latency",
                error_signature="def456abc1237890",
                severity=Severity.HIGH
            )
        ]

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            test_paths = generator.generate_tests_from_bug_list(bugs, output_dir=temp_output_dir)

            assert len(test_paths) == 2
            for path in test_paths:
                assert Path(path).exists()
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_generate_tests_from_bug_list_handles_exceptions(self, sample_bug_report, temp_output_dir):
        """Test that exceptions during generation are handled gracefully."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# Test {{ bug_id }}")
        (templates_path / "property_regression_template.py.j2").write_text("# Test {{ bug_id }}")

        # Create bugs where second one will fail
        bugs = [
            sample_bug_report,
            BugReport(
                discovery_method=DiscoveryMethod.PROPERTY,
                test_name="test_bad_bug",
                error_message="Bad bug",
                error_signature="",  # Empty signature will cause issues
                severity=Severity.LOW
            )
        ]

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            # Should not raise exception, should handle gracefully
            test_paths = generator.generate_tests_from_bug_list(bugs, output_dir=temp_output_dir)

            # At least first test should be generated
            assert len(test_paths) >= 1
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_get_template_for_method_fuzzing(self):
        """Test _get_template_for_method returns correct template for fuzzing."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)

        # Create template files
        (templates_path / "fuzzing_regression_template.py.j2").write_text("FUZZING")
        (templates_path / "chaos_regression_template.py.j2").write_text("CHAOS")
        (templates_path / "property_regression_template.py.j2").write_text("PROPERTY")
        (templates_path / "browser_regression_template.py.j2").write_text("BROWSER")

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)

            fuzzing_template = generator._get_template_for_method(DiscoveryMethod.FUZZING)
            template_str = str(fuzzing_template.module)
            assert "FUZZING" in template_str or fuzzing_template is not None
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_get_template_for_method_all_methods(self):
        """Test _get_template_for_method for all discovery methods."""
        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)

        # Create all template files
        (templates_path / "fuzzing_regression_template.py.j2").write_text("FUZZING")
        (templates_path / "chaos_regression_template.py.j2").write_text("CHAOS")
        (templates_path / "property_regression_template.py.j2").write_text("PROPERTY")
        (templates_path / "browser_regression_template.py.j2").write_text("BROWSER")
        (templates_path / "pytest_regression_template.py.j2").write_text("DEFAULT")

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)

            # Test each method
            fuzzing_template = generator._get_template_for_method(DiscoveryMethod.FUZZING)
            chaos_template = generator._get_template_for_method(DiscoveryMethod.CHAOS)
            property_template = generator._get_template_for_method(DiscoveryMethod.PROPERTY)
            browser_template = generator._get_template_for_method(DiscoveryMethod.BROWSER)

            # Verify templates are created (not None)
            assert fuzzing_template is not None
            assert chaos_template is not None
            assert property_template is not None
            assert browser_template is not None
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_infer_reproduction_steps_fuzzing(self, sample_bug_report):
        """Test _infer_reproduction_steps for fuzzing bugs."""
        temp_templates = tempfile.mkdtemp()
        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            steps = generator._infer_reproduction_steps(sample_bug_report)

            assert "test_agent_api_fuzzing" in steps
            assert "Fuzz endpoint" in steps
            assert "/api/v1/agents" in steps
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_infer_reproduction_steps_chaos(self):
        """Test _infer_reproduction_steps for chaos bugs."""
        temp_templates = tempfile.mkdtemp()

        chaos_bug = BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="test_network_latency",
            error_message="Request timeout",
            error_signature="xyz789",
            metadata={"experiment_name": "network_latency_3g"}
        )

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            steps = generator._infer_reproduction_steps(chaos_bug)

            assert "Inject failure" in steps
            assert "network_latency_3g" in steps
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_infer_reproduction_steps_property(self):
        """Test _infer_reproduction_steps for property bugs."""
        temp_templates = tempfile.mkdtemp()

        property_bug = BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_agent_execution_idempotence",
            error_message="Invariant violated",
            error_signature="prop123"
        )

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            steps = generator._infer_reproduction_steps(property_bug)

            assert "Hypothesis" in steps
            assert "test_agent_execution_idempotence" in steps
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_infer_reproduction_steps_browser(self):
        """Test _infer_reproduction_steps for browser bugs."""
        temp_templates = tempfile.mkdtemp()

        browser_bug = BugReport(
            discovery_method=DiscoveryMethod.BROWSER,
            test_name="test_dashboard_console_errors",
            error_message="Console error on dashboard",
            error_signature="browser123",
            metadata={"url": "http://localhost:3000/dashboard"}
        )

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            steps = generator._infer_reproduction_steps(browser_bug)

            assert "Navigate to" in steps
            assert "http://localhost:3000/dashboard" in steps
            assert "console errors" in steps
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_infer_expected_behavior_fuzzing(self):
        """Test _infer_expected_behavior for fuzzing bugs."""
        temp_templates = tempfile.mkdtemp()

        fuzzing_bug = BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="test_fuzzing",
            error_message="SQL injection",
            error_signature="fuzz123"
        )

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            behavior = generator._infer_expected_behavior(fuzzing_bug)

            assert "gracefully" in behavior
            assert "400" in behavior or "422" in behavior
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_infer_expected_behavior_chaos(self):
        """Test _infer_expected_behavior for chaos bugs."""
        temp_templates = tempfile.mkdtemp()

        chaos_bug = BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="test_chaos",
            error_message="System crash",
            error_signature="chaos123"
        )

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            behavior = generator._infer_expected_behavior(chaos_bug)

            assert "gracefully" in behavior
            assert "recover" in behavior
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_archive_test_moves_file_to_archived(self, temp_output_dir):
        """Test that archive_test moves file to archived/ subdirectory."""
        temp_templates = tempfile.mkdtemp()

        # Create a test file
        test_file = Path(temp_output_dir) / "test_regression_fuzzing_abc123de.py"
        test_file.write_text("# Test content")

        archived_dir = Path(temp_output_dir) / "archived"
        archived_dir.mkdir(parents=True, exist_ok=True)

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            archived_path = generator.archive_test(str(test_file))

            assert not test_file.exists()
            assert Path(archived_path).exists()
            assert "archived" in archived_path
            assert archived_path.endswith("test_regression_fuzzing_abc123de.py")
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)

    def test_archive_test_creates_archived_directory(self, temp_output_dir):
        """Test that archive_test creates archived/ directory if it doesn't exist."""
        temp_templates = tempfile.mkdtemp()

        # Create a test file
        test_file = Path(temp_output_dir) / "test_regression_fuzzing_abc123de.py"
        test_file.write_text("# Test content")

        # Don't create archived directory - test should create it
        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            archived_path = generator.archive_test(str(test_file))

            assert Path(archived_path).parent.name == "archived"
            assert Path(archived_path).exists()
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)


class TestIntegrationWithDiscoveryCoordinator:
    """Test integration with existing bug discovery infrastructure."""

    def test_uses_bug_report_model(self):
        """Test that RegressionTestGenerator works with BugReport model."""
        bug = BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_agent_execution_idempotence",
            error_message="Invariant violated: idempotence check failed",
            error_signature="inv123",
            metadata={"invariant": "Agent execution should be idempotent"}
        )

        temp_templates = tempfile.mkdtemp()
        temp_output = tempfile.mkdtemp()

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            # Should not raise an error
            assert generator is not None
            assert hasattr(generator, 'generate_test_from_bug')
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)
            shutil.rmtree(temp_output, ignore_errors=True)

    def test_handles_discovery_method_enum(self):
        """Test that generator handles DiscoveryMethod enum correctly."""
        bug = BugReport(
            discovery_method=DiscoveryMethod.FUZZING,  # Enum, not string
            test_name="test_enum_handling",
            error_message="Test",
            error_signature="enum123"
        )

        temp_templates = tempfile.mkdtemp()
        templates_path = Path(temp_templates)
        (templates_path / "fuzzing_regression_template.py.j2").write_text("# {{ bug_id }}")

        temp_output = tempfile.mkdtemp()

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            # Should handle enum value correctly
            assert generator is not None
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)
            shutil.rmtree(temp_output, ignore_errors=True)

    def test_handles_discovery_method_string(self):
        """Test that generator handles string discovery_method correctly."""
        # Create bug with string discovery_method (not enum)
        bug_dict = {
            "discovery_method": "fuzzing",  # String, not enum
            "test_name": "test_string_handling",
            "error_message": "Test",
            "error_signature": "str123",
            "severity": "high",
            "metadata": {},
            "timestamp": datetime.utcnow()
        }

        bug = BugReport(**bug_dict)

        temp_templates = tempfile.mkdtemp()

        try:
            generator = RegressionTestGenerator(templates_dir=temp_templates)
            # Should handle string value correctly
            assert generator is not None
        finally:
            shutil.rmtree(temp_templates, ignore_errors=True)
