"""
Console error detection tests for browser bug discovery.

This module tests for JavaScript console errors, unhandled exceptions,
and runtime errors that indicate UI bugs and broken functionality.

Tests use console_monitor and assert_no_console_errors fixtures from conftest.py.
"""

import pytest
from tests.browser_discovery.conftest import (
    authenticated_page,
    console_monitor,
    assert_no_console_errors,
)


pytestmark = pytest.mark.browser_discovery


class TestConsoleErrors:
    """Test suite for detecting JavaScript console errors on critical pages."""

    @pytest.mark.browser_discovery
    def test_no_console_errors_on_dashboard(
        self, authenticated_page, console_monitor, assert_no_console_errors
    ):
        """Verify dashboard page loads without JavaScript console errors.

        Navigates to /dashboard and checks for any console errors that
        indicate broken JavaScript, missing dependencies, or runtime issues.

        Args:
            authenticated_page: Authenticated page fixture (API-first auth)
            console_monitor: Console monitor fixture
            assert_no_console_errors: Assertion helper fixture
        """
        base_url = "http://localhost:3001"
        dashboard_url = base_url + "/dashboard"
        authenticated_page.goto(dashboard_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_no_console_errors()

    @pytest.mark.browser_discovery
    def test_no_console_errors_on_agents_list(
        self, authenticated_page, console_monitor, assert_no_console_errors
    ):
        """Verify agents list page loads without JavaScript console errors.

        Navigates to /agents and checks for console errors that indicate
        issues with agent listing, filtering, or rendering.

        Args:
            authenticated_page: Authenticated page fixture
            console_monitor: Console monitor fixture
            assert_no_console_errors: Assertion helper fixture
        """
        base_url = "http://localhost:3001"
        agents_url = base_url + "/agents"
        authenticated_page.goto(agents_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_no_console_errors()

    @pytest.mark.browser_discovery
    def test_no_console_errors_on_agent_creation(
        self, authenticated_page, console_monitor, assert_no_console_errors
    ):
        """Verify agent creation page loads without JavaScript console errors.

        Navigates to /agents/new and checks for console errors that indicate
        issues with agent creation form, validation, or component rendering.

        Args:
            authenticated_page: Authenticated page fixture
            console_monitor: Console monitor fixture
            assert_no_console_errors: Assertion helper fixture
        """
        base_url = "http://localhost:3001"
        agent_creation_url = base_url + "/agents/new"
        authenticated_page.goto(agent_creation_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_no_console_errors()

    @pytest.mark.browser_discovery
    def test_no_console_errors_on_canvas_list(
        self, authenticated_page, console_monitor, assert_no_console_errors
    ):
        """Verify canvas list page loads without JavaScript console errors.

        Navigates to /canvas and checks for console errors that indicate
        issues with canvas listing, rendering, or state management.

        Args:
            authenticated_page: Authenticated page fixture
            console_monitor: Console monitor fixture
            assert_no_console_errors: Assertion helper fixture
        """
        base_url = "http://localhost:3001"
        canvas_url = base_url + "/canvas"
        authenticated_page.goto(canvas_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_no_console_errors()

    @pytest.mark.browser_discovery
    def test_no_console_errors_on_workflows_list(
        self, authenticated_page, console_monitor, assert_no_console_errors
    ):
        """Verify workflows list page loads without JavaScript console errors.

        Navigates to /workflows and checks for console errors that indicate
        issues with workflow listing, DAG rendering, or component initialization.

        Args:
            authenticated_page: Authenticated page fixture
            console_monitor: Console monitor fixture
            assert_no_console_errors: Assertion helper fixture
        """
        base_url = "http://localhost:3001"
        workflows_url = base_url + "/workflows"
        authenticated_page.goto(workflows_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_no_console_errors()

    @pytest.mark.browser_discovery
    def test_console_error_captures_metadata(
        self, authenticated_page, console_monitor
    ):
        """Verify console errors include timestamp, URL, and location metadata.

        Checks that console_monitor captures detailed error context including
        timestamp, current URL, and source location (file, line, column)
        for effective bug triaging and debugging.

        Args:
            authenticated_page: Authenticated page fixture
            console_monitor: Console monitor fixture
        """
        base_url = "http://localhost:3001"
        dashboard_url = base_url + "/dashboard"
        authenticated_page.goto(dashboard_url)
        authenticated_page.wait_for_load_state("domcontentloaded")

        # Verify console_monitor structure
        assert isinstance(console_monitor, dict), "console_monitor should be a dict"
        assert "error" in console_monitor, "console_monitor should have 'error' key"
        assert "warning" in console_monitor, "console_monitor should have 'warning' key"
        assert "info" in console_monitor, "console_monitor should have 'info' key"
        assert "log" in console_monitor, "console_monitor should have 'log' key"
        assert "debug" in console_monitor, "console_monitor should have 'debug' key"

        # If errors exist, verify metadata structure
        errors = console_monitor.get("error", [])
        if errors:
            for error in errors:
                assert "timestamp" in error, "Error should have timestamp"
                assert "url" in error, "Error should have URL"
                assert isinstance(error["timestamp"], str), "Timestamp should be string"
                assert isinstance(error["url"], str), "URL should be string"

                # Location is optional but should be dict if present
                if "location" in error:
                    assert isinstance(error["location"], dict), "Location should be dict"
                    assert "url" in error["location"], "Location should have url"
                    assert "line_number" in error["location"], "Location should have line_number"

    @pytest.mark.browser_discovery
    def test_console_warnings_logged_but_not_failed(
        self, authenticated_page, console_monitor
    ):
        """Verify console warnings are captured but do not fail tests.

        Console warnings should be logged for visibility but should not
        cause test failures. Only errors should fail tests.

        Args:
            authenticated_page: Authenticated page fixture
            console_monitor: Console monitor fixture
        """
        base_url = "http://localhost:3001"
        dashboard_url = base_url + "/dashboard"
        authenticated_page.goto(dashboard_url)
        authenticated_page.wait_for_load_state("domcontentloaded")

        # Verify warnings are captured (even if empty list)
        assert "warning" in console_monitor, "console_monitor should capture warnings"

        # Verify warning structure if present
        warnings = console_monitor.get("warning", [])
        if warnings:
            for warning in warnings:
                assert "timestamp" in warning, "Warning should have timestamp"
                assert "url" in warning, "Warning should have URL"
                assert "text" in warning, "Warning should have text"

        # Warnings should NOT fail test (no assertion on warning count)
