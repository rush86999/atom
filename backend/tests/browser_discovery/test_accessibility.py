"""
Accessibility violation detection tests for browser bug discovery.

This module tests for WCAG 2.1 AA compliance violations using axe-core.
Tests detect missing ARIA labels, color contrast issues, and other a11y bugs.

Tests use accessibility_checker and assert_accessibility fixtures from conftest.py.
"""

import pytest
from tests.browser_discovery.conftest import (
    authenticated_page,
    accessibility_checker,
    assert_accessibility,
)


pytestmark = pytest.mark.accessibility


class TestAccessibility:
    """Test suite for detecting WCAG 2.1 AA accessibility violations."""

    @pytest.mark.accessibility
    def test_dashboard_wcag_aa_compliance(
        self, authenticated_page, assert_accessibility
    ):
        """Verify dashboard page meets WCAG 2.1 AA accessibility standards.

        Navigates to /dashboard and checks for accessibility violations
        that would prevent users with disabilities from using the dashboard.

        Args:
            authenticated_page: Authenticated page fixture (API-first auth)
            assert_accessibility: Assertion helper fixture for WCAG compliance
        """
        base_url = "http://localhost:3001"
        dashboard_url = base_url + "/dashboard"
        authenticated_page.goto(dashboard_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_accessibility()

    @pytest.mark.accessibility
    def test_agents_list_wcag_aa_compliance(
        self, authenticated_page, assert_accessibility
    ):
        """Verify agents list page meets WCAG 2.1 AA accessibility standards.

        Navigates to /agents and checks for accessibility violations
        in agent listings, filters, and action buttons.

        Args:
            authenticated_page: Authenticated page fixture
            assert_accessibility: Assertion helper fixture for WCAG compliance
        """
        base_url = "http://localhost:3001"
        agents_url = base_url + "/agents"
        authenticated_page.goto(agents_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_accessibility()

    @pytest.mark.accessibility
    def test_agent_creation_form_wcag_aa(
        self, authenticated_page, assert_accessibility
    ):
        """Verify agent creation form meets WCAG 2.1 AA accessibility standards.

        Navigates to /agents/new and checks for form accessibility violations
        including missing labels, unclear error messages, and keyboard navigation issues.

        Args:
            authenticated_page: Authenticated page fixture
            assert_accessibility: Assertion helper fixture for WCAG compliance
        """
        base_url = "http://localhost:3001"
        agent_creation_url = base_url + "/agents/new"
        authenticated_page.goto(agent_creation_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_accessibility()

    @pytest.mark.accessibility
    def test_canvas_list_wcag_aa_compliance(
        self, authenticated_page, assert_accessibility
    ):
        """Verify canvas list page meets WCAG 2.1 AA accessibility standards.

        Navigates to /canvas and checks for accessibility violations
        in canvas listings, visual presentations, and interactive elements.

        Args:
            authenticated_page: Authenticated page fixture
            assert_accessibility: Assertion helper fixture for WCAG compliance
        """
        base_url = "http://localhost:3001"
        canvas_url = base_url + "/canvas"
        authenticated_page.goto(canvas_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_accessibility()

    @pytest.mark.accessibility
    def test_workflows_list_wcag_aa_compliance(
        self, authenticated_page, assert_accessibility
    ):
        """Verify workflows list page meets WCAG 2.1 AA accessibility standards.

        Navigates to /workflows and checks for accessibility violations
        in workflow DAG visualizations, node selectors, and action buttons.

        Args:
            authenticated_page: Authenticated page fixture
            assert_accessibility: Assertion helper fixture for WCAG compliance
        """
        base_url = "http://localhost:3001"
        workflows_url = base_url + "/workflows"
        authenticated_page.goto(workflows_url)
        authenticated_page.wait_for_load_state("domcontentloaded")
        assert_accessibility()

    @pytest.mark.accessibility
    def test_accessibility_violation_metadata(
        self, authenticated_page, accessibility_checker
    ):
        """Verify accessibility violations include id, impact, description, and help_url.

        Checks that accessibility_checker returns structured violation data
        with all necessary fields for bug triaging and remediation.

        Args:
            authenticated_page: Authenticated page fixture
            accessibility_checker: Accessibility checker fixture with axe-core
        """
        base_url = "http://localhost:3001"
        dashboard_url = base_url + "/dashboard"
        authenticated_page.goto(dashboard_url)
        authenticated_page.wait_for_load_state("domcontentloaded")

        # Run accessibility audit
        violations = accessibility_checker()

        # Verify violations is a list (even if empty)
        assert isinstance(violations, list), "Violations should be a list"

        # If violations exist, verify metadata structure
        if violations:
            for violation in violations:
                assert "id" in violation, "Violation should have id"
                assert "impact" in violation, "Violation should have impact"
                assert "description" in violation, "Violation should have description"
                assert "help" in violation, "Violation should have help"
                assert "help_url" in violation, "Violation should have help_url"
                assert "tags" in violation, "Violation should have tags"

                # Verify WCAG 2.1 AA tags are present
                tags = violation.get("tags", [])
                assert any(tag in tags for tag in ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]), \
                    "Violation should have WCAG 2.1 AA tags"

                # Verify impact is one of the expected values
                impact = violation.get("impact")
                assert impact in ["critical", "serious", "moderate", "minor"], \
                    "Impact should be critical/serious/moderate/minor, got " + str(impact)

    @pytest.mark.accessibility
    def test_accessibility_graceful_degradation(
        self, authenticated_page, accessibility_checker
    ):
        """Verify accessibility tests handle axe-core load failures gracefully.

        If axe-core fails to load due to network issues or CDN problems,
        the test should skip rather than fail with a cryptic error.

        Args:
            authenticated_page: Authenticated page fixture
            accessibility_checker: Accessibility checker fixture with axe-core
        """
        base_url = "http://localhost:3001"
        dashboard_url = base_url + "/dashboard"

        try:
            authenticated_page.goto(dashboard_url)
            authenticated_page.wait_for_load_state("domcontentloaded")

            # Run accessibility audit
            violations = accessibility_checker()

            # If we got here, axe-core loaded successfully
            # Verify violations is a list
            assert isinstance(violations, list), "Violations should be a list"

        except Exception as e:
            # Check if error is related to axe-core loading
            error_msg = str(e).lower()
            if "axe-core" in error_msg or "axe" in error_msg:
                # Skip test if axe-core failed to load (network issue, CDN down, etc.)
                pytest.skip("axe-core failed to load: " + str(e))
            else:
                # Re-raise if it's a different error
                raise
