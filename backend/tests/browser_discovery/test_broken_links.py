"""
Broken link detection tests for browser bug discovery.

This module tests for broken links (404 responses, redirect loops, dead links)
across main application pages. These tests use the broken_link_checker fixture
from conftest.py to automatically discover dead links.

Coverage: BROWSER-04 (Broken Link Detection)
"""

import pytest
from tests.browser_discovery.conftest import authenticated_page, broken_link_checker


pytestmark = pytest.mark.broken_links


class TestBrokenLinks:
    """Test suite for broken link detection across application pages."""

    def test_no_broken_links_on_dashboard(
        self, authenticated_page, broken_link_checker
    ):
        """Verify dashboard has no broken links.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            broken_link_checker: Fixture that checks all links on page

        Raises:
            AssertionError: If any broken links found (status >= 400)
        """
        authenticated_page.goto("http://localhost:3001/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        broken_links = broken_link_checker()

        assert (
            len(broken_links) == 0
        ), f"Dashboard has {len(broken_links)} broken links: {broken_links}"

    def test_no_broken_links_on_agents_list(
        self, authenticated_page, broken_link_checker
    ):
        """Verify agents list page has no broken links.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            broken_link_checker: Fixture that checks all links on page

        Raises:
            AssertionError: If any broken links found (status >= 400)
        """
        authenticated_page.goto("http://localhost:3001/agents")
        authenticated_page.wait_for_load_state("networkidle")

        broken_links = broken_link_checker()

        assert (
            len(broken_links) == 0
        ), f"Agents list has {len(broken_links)} broken links: {broken_links}"

    def test_no_broken_links_on_canvas_list(
        self, authenticated_page, broken_link_checker
    ):
        """Verify canvas list page has no broken links.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            broken_link_checker: Fixture that checks all links on page

        Raises:
            AssertionError: If any broken links found (status >= 400)
        """
        authenticated_page.goto("http://localhost:3001/canvas")
        authenticated_page.wait_for_load_state("networkidle")

        broken_links = broken_link_checker()

        assert (
            len(broken_links) == 0
        ), f"Canvas list has {len(broken_links)} broken links: {broken_links}"

    def test_no_broken_links_on_workflows_list(
        self, authenticated_page, broken_link_checker
    ):
        """Verify workflows list page has no broken links.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            broken_link_checker: Fixture that checks all links on page

        Raises:
            AssertionError: If any broken links found (status >= 400)
        """
        authenticated_page.goto("http://localhost:3001/workflows")
        authenticated_page.wait_for_load_state("networkidle")

        broken_links = broken_link_checker()

        assert (
            len(broken_links) == 0
        ), f"Workflows list has {len(broken_links)} broken links: {broken_links}"

    def test_broken_link_includes_metadata(
        self, authenticated_page, broken_link_checker
    ):
        """Verify broken link checker includes full metadata.

        This test validates that when broken links are found, they include:
        - URL (the broken link)
        - Text (link anchor text)
        - status_code (HTTP status code)
        - error (if network error occurred)

        Args:
            authenticated_page: Authenticated Playwright page fixture
            broken_link_checker: Fixture that checks all links on page

        Note:
            This test navigates to a page that may have broken links
            to verify metadata structure. Update URL if all links are valid.
        """
        authenticated_page.goto("http://localhost:3001/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        broken_links = broken_link_checker()

        # If broken links found, verify metadata structure
        if len(broken_links) > 0:
            for link in broken_links:
                # Verify required metadata fields
                assert "url" in link, "Broken link missing 'url' field"
                assert "text" in link, "Broken link missing 'text' field"

                # Either status_code or error should be present
                assert (
                    "status_code" in link or "error" in link
                ), "Broken link missing 'status_code' or 'error' field"

                # Verify field types
                assert isinstance(link["url"], str), "Link URL should be string"
                assert isinstance(link["text"], str), "Link text should be string"

                if "status_code" in link:
                    assert isinstance(
                        link["status_code"], int
                    ), "Status code should be integer"
                    assert (
                        link["status_code"] >= 400
                    ), "Broken link should have status >= 400"

                if "error" in link:
                    assert isinstance(link["error"], str), "Error should be string"

    def test_link_checker_skips_localhost(
        self, authenticated_page, broken_link_checker
    ):
        """Verify link checker skips localhost/127.0.0.1 links.

        In test environments, localhost links may not be accessible.
        The broken_link_checker fixture should skip these to avoid
        false positives.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            broken_link_checker: Fixture that checks all links on page

        Raises:
            AssertionError: If localhost links are checked (should be skipped)
        """
        authenticated_page.goto("http://localhost:3001/dashboard")
        authenticated_page.wait_for_load_state("networkidle")

        broken_links = broken_link_checker()

        # Verify no localhost links in broken links
        for link in broken_links:
            url = link.get("url", "")
            assert (
                "localhost" not in url and "127.0.0.1" not in url
            ), f"Link checker should skip localhost URLs, but checked: {url}"
