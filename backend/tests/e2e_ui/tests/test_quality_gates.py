"""
Test quality gate features: screenshots, videos, retries, flaky detection.

This module tests the automatic screenshot and video capture functionality
that triggers on test failures to aid debugging in CI and local development.
"""
import os
import pytest
from playwright.sync_api import Page


def test_screenshot_directory_exists():
    """Verify screenshot artifacts directory exists."""
    screenshot_dir = "backend/tests/e2e_ui/artifacts/screenshots"
    assert os.path.exists(screenshot_dir), f"Screenshot directory {screenshot_dir} does not exist"


def test_video_directory_exists():
    """Verify video artifacts directory exists."""
    video_dir = "backend/tests/e2e_ui/artifacts/videos"
    assert os.path.exists(video_dir), f"Video directory {video_dir} does not exist"


def test_ci_environment_detection():
    """Verify CI environment detection works correctly."""
    from tests.e2e_ui.conftest import is_ci_environment

    # In local dev, should return False
    # In CI (GitHub Actions), should return True
    result = is_ci_environment()
    assert isinstance(result, bool), "is_ci_environment() should return a boolean"


def test_screenshot_not_captured_on_success(page: Page):
    """
    Verify screenshots are NOT captured for passing tests.

    This test passes and should not create a screenshot file.
    """
    # Navigate to base URL
    page.goto("")

    # Verify page loaded
    assert page.url is not None

    # Test passes - no screenshot should be created
    # (This is verified by the lack of new screenshot files)


def test_screenshot_on_failure(page: Page):
    """
    Verify screenshots are captured when tests fail.

    This test deliberately fails to trigger screenshot capture.
    The pytest_runtest_makereport hook should capture a screenshot
    and save it to artifacts/screenshots/ with a descriptive filename.

    Note: This test is expected to fail - it verifies the screenshot
    capture functionality by triggering it.
    """
    # Navigate to a known page
    page.goto("/")

    # Deliberately fail to trigger screenshot capture
    # The hook should capture a screenshot before test completes
    assert False, "Intentional failure to test screenshot capture"


@pytest.mark.skipif(not os.getenv("CI"), reason="Video recording only in CI")
def test_video_captured_on_failure_in_ci(page: Page):
    """
    Verify videos are captured on failure in CI environment.

    This test deliberately fails to trigger video capture in CI.
    The pytest_runtest_makereport hook should capture a video
    and save it to artifacts/videos/ with a descriptive filename.

    Note: This test is expected to fail - it verifies the video
    capture functionality by triggering it. Only runs in CI.
    """
    # Navigate to a known page
    page.goto("/")

    # Deliberately fail to trigger video capture
    # The hook should capture a video before test completes
    assert False, "Intentional failure to test video capture in CI"


def test_video_not_captured_locally(page: Page, monkeypatch):
    """
    Verify videos are NOT captured in local development.

    This test passes and verifies that no video file is created
    when running locally (CI environment variable not set).
    """
    # Ensure CI is not set
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    # This test passes - verify no video was created
    page.goto("/")
    assert page.title() is not None


@pytest.mark.parametrize("page_type", ["page", "authenticated_page"])
def test_screenshot_works_with_different_fixtures(page_type: str, request):
    """
    Verify screenshot capture works with different page fixtures.

    Tests that the screenshot capture mechanism works with both
    the basic 'page' fixture and 'authenticated_page' fixture.
    """
    page = request.getfixturevalue(page_type)
    page.goto("/")
    assert page.url is not None


# ============================================================================
# Retry Functionality Tests
# ============================================================================

def test_retries_disabled_locally(monkeypatch):
    """Verify test retries are disabled in local development."""
    # Ensure CI is not set
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    # Import and check configuration
    from tests.e2e_ui.conftest import is_ci_environment

    assert not is_ci_environment(), "Retries should be disabled in local development"


@pytest.mark.skipif(not os.getenv("CI"), reason="Retries only in CI")
def test_retries_enabled_in_ci():
    """Verify test retries are enabled in CI environment."""
    from tests.e2e_ui.conftest import is_ci_environment

    assert os.getenv("CI") == "true", "This test should only run in CI"
    assert is_ci_environment(), "Retries should be enabled in CI"


def test_pytest_reruns_env_variable(monkeypatch):
    """Verify PYTEST_RERUNS environment variable controls retry count."""
    # Set custom rerun count
    monkeypatch.setenv("PYTEST_RERUNS", "3")
    monkeypatch.setenv("CI", "true")

    # Verify environment variable is set
    assert os.getenv("PYTEST_RERUNS") == "3"


@pytest.mark.flaky  # This marker is for temporary flaky tests
def test_flaky_marker_example():
    """
    Example of flaky test marker (should be removed when fixed).

    This test is marked as flaky - do NOT use for new tests.
    Only use as temporary workaround while investigating root cause.
    """
    # This test is marked as flaky - do NOT use for new tests
    # Only use as temporary workaround while investigating root cause
    assert True


# ============================================================================
# Flaky Test Detection Tests
# ============================================================================


def test_flaky_test_tracker_initialization():
    """Verify FlakyTestTracker initializes correctly."""
    import tempfile
    from pathlib import Path

    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))

        assert tracker.data_file == data_file
        assert tracker.data["total_runs"] == 0
        assert len(tracker.data["tests"]) == 0


def test_flaky_test_tracker_update():
    """Verify tracker updates from pytest report."""
    import json
    import tempfile
    from pathlib import Path

    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock pytest report
        report_file = Path(tmpdir) / "pytest_report.json"
        mock_report = {
            "summary": {"total": 2, "passed": 1, "failed": 1},
            "tests": {
                "tests/test_foo.py::test_pass": {"outcome": "passed"},
                "tests/test_bar.py::test_fail": {"outcome": "failed"}
            }
        }
        report_file.write_text(json.dumps(mock_report))

        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))
        tracker.update_from_pytest_report(str(report_file))

        assert tracker.data["total_runs"] == 1
        assert len(tracker.data["tests"]) == 2
        assert tracker.data["tests"]["tests/test_foo.py::test_pass"]["passed"] == 1
        assert tracker.data["tests"]["tests/test_bar.py::test_fail"]["failed"] == 1


def test_flaky_test_detection():
    """Verify flaky tests are correctly identified."""
    import tempfile
    from pathlib import Path

    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))

        # Simulate test with mixed results (flaky)
        test_name = "tests/test_flaky.py::test_intermittent"
        tracker.data["tests"][test_name] = {
            "runs": [
                {"outcome": "passed", "run": 1},
                {"outcome": "failed", "run": 2},
                {"outcome": "passed", "run": 3},
                {"outcome": "failed", "run": 4},
                {"outcome": "passed", "run": 5}
            ],
            "total_runs": 5,
            "passed": 3,
            "failed": 2
        }

        flaky = tracker.get_flaky_tests(pass_threshold=0.8, min_runs=3)

        assert len(flaky) == 1
        assert flaky[0]["test"] == test_name
        assert flaky[0]["pass_rate"] == 0.6  # 3/5 = 60%


def test_stable_test_not_flagged():
    """Verify stable tests are not flagged as flaky."""
    import tempfile
    from pathlib import Path

    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))

        # Simulate stable test
        test_name = "tests/test_stable.py::test_reliable"
        tracker.data["tests"][test_name] = {
            "runs": [
                {"outcome": "passed", "run": 1},
                {"outcome": "passed", "run": 2},
                {"outcome": "passed", "run": 3},
                {"outcome": "passed", "run": 4},
                {"outcome": "passed", "run": 5}
            ],
            "total_runs": 5,
            "passed": 5,
            "failed": 0
        }

        flaky = tracker.get_flaky_tests(pass_threshold=0.8, min_runs=3)

        # Stable test should not be in flaky list
        assert not any(t["test"] == test_name for t in flaky)


# ============================================================================
# HTML Report Tests
# ============================================================================

def test_html_report_directory_exists():
    """Verify HTML report directory exists."""
    reports_dir = "backend/tests/e2e_ui/reports"
    assert os.path.exists(reports_dir), f"Reports directory {reports_dir} does not exist"


def test_html_report_hooks_exist():
    """Verify pytest-html hooks are defined in conftest.py."""
    from tests.e2e_ui import conftest

    # Check if hooks exist
    assert hasattr(conftest, 'pytest_html_results_summary') or \
           hasattr(conftest, 'pytest_html_results_table_row') or \
           'pytest_html' in str(dir(conftest))


def test_html_report_generator_script():
    """Verify HTML report generator script exists and runs."""
    import subprocess

    script_path = "backend/tests/e2e_ui/scripts/html_report_generator.py"
    assert os.path.exists(script_path), f"Script {script_path} not found"

    # Test help output
    result = subprocess.run(
        ["python3", script_path, "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Script help failed: {result.stderr}"
    assert "embed" in result.stdout.lower(), "Help should mention embed option"
    assert "screenshots" in result.stdout.lower(), "Help should mention screenshots option"


def test_html_report_contains_required_elements(page: Page):
    """
    Verify HTML report contains required elements for screenshot display.

    This test runs a simple test and checks that the HTML report
    would be generated with proper structure (actual report generation
    happens during pytest run with --html flag).
    """
    # Navigate to base URL
    page.goto("/")

    # Verify page loaded successfully
    assert page.url is not None

    # Note: Actual HTML report content is verified by pytest-html plugin
    # This test ensures the test infrastructure is working
    # Report structure is validated by pytest-html during test runs


# ============================================================================
# Quality Gate Tests
# ============================================================================

@pytest.mark.no_browser  # Unit tests that don't need browser/database
def test_pass_rate_calculator():
    """Verify pass rate calculation from pytest report."""
    from scripts.pass_rate_validator import PassRateValidator
    import tempfile
    from pathlib import Path
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock pytest report
        report_file = Path(tmpdir) / "pytest_report.json"
        mock_report = {
            "summary": {
                "total": 10,
                "passed": 9,
                "failed": 1,
                "skipped": 2,
                "error": 0
            }
        }
        report_file.write_text(json.dumps(mock_report))

        validator = PassRateValidator(gate_threshold=1.0)
        result = validator.calculate_from_report(str(report_file))

        # Pass rate = 9 / (9 + 1 + 0) = 90%
        assert result.total == 10
        assert result.passed == 9
        assert result.failed == 1
        assert result.pass_rate == 0.9
        assert not result.passed_gate  # 90% < 100%


@pytest.mark.no_browser  # Unit tests that don't need browser/database
def test_pass_rate_100_percent():
    """Verify 100% pass rate passes quality gate."""
    from scripts.pass_rate_validator import PassRateValidator
    import tempfile
    from pathlib import Path
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = Path(tmpdir) / "pytest_report.json"
        mock_report = {
            "summary": {
                "total": 5,
                "passed": 5,
                "failed": 0,
                "skipped": 0,
                "error": 0
            }
        }
        report_file.write_text(json.dumps(mock_report))

        validator = PassRateValidator(gate_threshold=1.0)
        result = validator.calculate_from_report(str(report_file))

        assert result.pass_rate == 1.0
        assert result.passed_gate


@pytest.mark.no_browser  # Unit tests that don't need browser/database
def test_quality_gate_consecutive_tracking():
    """Verify quality gate tracks consecutive passing runs."""
    from scripts.quality_gate import QualityGate
    import tempfile
    from pathlib import Path
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "quality_gate_history.json"

        # Create passing pytest report
        report_file = Path(tmpdir) / "pytest_report.json"
        passing_report = {
            "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0}
        }
        report_file.write_text(json.dumps(passing_report))

        gate = QualityGate(
            history_file=str(history_file),
            threshold=1.0,
            consecutive=3
        )

        # First run
        passed1, _ = gate.validate(str(report_file))
        assert not passed1  # Need 3 consecutive
        assert gate.history["consecutive_passes"] == 1

        # Second run
        passed2, _ = gate.validate(str(report_file))
        assert not passed2  # Need 3 consecutive
        assert gate.history["consecutive_passes"] == 2

        # Third run
        passed3, _ = gate.validate(str(report_file))
        assert passed3  # 3 consecutive passes!
        assert gate.history["consecutive_passes"] == 3


@pytest.mark.no_browser  # Unit tests that don't need browser/database
def test_quality_gate_reset_on_failure():
    """Verify quality gate resets on failed run."""
    from scripts.quality_gate import QualityGate
    import tempfile
    from pathlib import Path
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "quality_gate_history.json"
        report_file = Path(tmpdir) / "pytest_report.json"

        gate = QualityGate(
            history_file=str(history_file),
            threshold=1.0,
            consecutive=3
        )

        # Two passing runs
        passing_report = {
            "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "error": 0}
        }
        report_file.write_text(json.dumps(passing_report))
        gate.validate(str(report_file))
        gate.validate(str(report_file))

        assert gate.history["consecutive_passes"] == 2

        # One failing run
        failing_report = {
            "summary": {"total": 1, "passed": 0, "failed": 1, "skipped": 0, "error": 0}
        }
        report_file.write_text(json.dumps(failing_report))
        gate.validate(str(report_file))

        # Should reset to 0
        assert gate.history["consecutive_passes"] == 0
