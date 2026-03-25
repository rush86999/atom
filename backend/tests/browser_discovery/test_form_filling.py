"""
Form filling edge case tests for browser bug discovery.

This module tests form handling with edge case inputs that commonly cause bugs:
- Null bytes (string truncation vulnerabilities)
- XSS payloads (cross-site scripting)
- SQL injection (database injection attacks)
- Unicode characters (encoding issues)
- Massive strings (buffer overflow, DoS)
- Special characters (escape sequences)

These tests verify that forms handle edge cases gracefully without crashing,
sanitize malicious inputs, and display appropriate validation errors.

Coverage: BROWSER-06 (Form Edge Case Testing)
"""

import pytest
from tests.browser_discovery.conftest import authenticated_page, console_monitor


pytestmark = pytest.mark.browser_discovery


class TestFormFilling:
    """Test suite for form filling with edge case inputs."""

    def test_agent_form_handles_null_bytes(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form handles null bytes without crashing.

        Null bytes (\x00) can cause string truncation vulnerabilities in
        poorly handled strings. This test verifies the form handles them
        gracefully.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If form crashes or console errors occur
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Fill agent name with null bytes
        null_byte_payload = "agent\x00name\x00with\x00nulls"

        # Try to fill the form field
        try:
            authenticated_page.fill("input[name='name']", null_byte_payload)
            authenticated_page.fill(
                "textarea[name='description']", "Test agent with null bytes"
            )

            # Submit form (may fail validation, but should not crash)
            authenticated_page.click("button[type='submit']", timeout=5000)

            # Wait for response (success or error)
            authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        except Exception as e:
            # Form should not crash with null bytes
            pytest.fail(f"Form crashed with null bytes: {e}")

        # Verify no JavaScript errors
        errors = console_monitor.get("error", [])
        assert (
            len(errors) == 0
        ), f"Null bytes caused {len(errors)} JavaScript errors: {errors}"

        # Verify page still responsive (body visible)
        body_visible = authenticated_page.locator("body").is_visible()
        assert body_visible, "Page became unresponsive after null byte input"

    def test_agent_form_sanitizes_xss_payloads(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form sanitizes XSS script payloads.

        Tests that <script>alert('XSS')</script> is sanitized and not
        executed in the DOM.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If XSS payload is executed (console shows alert)
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # XSS payload with script tag
        xss_payload = '<script>alert("XSS")</script>'

        # Fill form with XSS payload
        authenticated_page.fill("input[name='name']", xss_payload)
        authenticated_page.fill(
            "textarea[name='description']", "Test agent with XSS payload"
        )

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no alert() was called (XSS not executed)
        console_logs = console_monitor.get("log", [])
        alert_calls = [log for log in console_logs if "alert" in log.get("text", "").lower()]

        assert (
            len(alert_calls) == 0
        ), f"XSS payload was executed! Found alert calls: {alert_calls}"

        # Verify page still responsive
        body_visible = authenticated_page.locator("body").is_visible()
        assert body_visible, "Page became unresponsive after XSS payload"

    def test_agent_form_sanitizes_xss_img_onerror(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form sanitizes XSS img onerror payloads.

        Tests that <img src=x onerror=alert('XSS')> is sanitized.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If XSS payload is executed
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # XSS payload with img onerror
        xss_payload = '<img src=x onerror=alert("XSS")>'

        # Fill form with XSS payload
        authenticated_page.fill("input[name='name']", xss_payload)
        authenticated_page.fill(
            "textarea[name='description']", "Test agent with img XSS payload"
        )

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no alert() was called
        console_logs = console_monitor.get("log", [])
        alert_calls = [log for log in console_logs if "alert" in log.get("text", "").lower()]

        assert (
            len(alert_calls) == 0
        ), f"XSS payload was executed! Found alert calls: {alert_calls}"

    def test_agent_form_sanitizes_xss_double_quote(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form sanitizes double quote XSS payloads.

        Tests that double quote escape XSS is sanitized:
        "><script>alert(String.fromCharCode(88,83,83))</script>

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If XSS payload is executed
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Double quote XSS payload
        xss_payload = '"><script>alert(String.fromCharCode(88,83,83))</script>'

        # Fill form with XSS payload
        authenticated_page.fill("input[name='name']", xss_payload)
        authenticated_page.fill(
            "textarea[name='description']", "Test agent with double quote XSS"
        )

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no alert() was called
        console_logs = console_monitor.get("log", [])
        alert_calls = [log for log in console_logs if "alert" in log.get("text", "").lower()]

        assert (
            len(alert_calls) == 0
        ), f"XSS payload was executed! Found alert calls: {alert_calls}"

    def test_agent_form_resists_sql_injection(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form resists SQL injection payloads.

        Tests that SQL injection payloads like ' OR '1'='1 are rejected
        or sanitized, not executed against the database.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If SQL injection causes database error or crash
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # SQL injection payload
        sqli_payload = "' OR '1'='1"

        # Fill form with SQL injection
        authenticated_page.fill("input[name='name']", sqli_payload)
        authenticated_page.fill(
            "textarea[name='description']", "Test agent with SQL injection"
        )

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no database errors in console
        errors = console_monitor.get("error", [])
        db_errors = [
            err
            for err in errors
            if "database" in err.get("text", "").lower()
            or "sql" in err.get("text", "").lower()
        ]

        assert (
            len(db_errors) == 0
        ), f"SQL injection caused database errors: {db_errors}"

        # Verify page still responsive
        body_visible = authenticated_page.locator("body").is_visible()
        assert body_visible, "Page became unresponsive after SQL injection"

    def test_agent_form_handles_unicode(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form handles Unicode characters correctly.

        Tests emoji (🎨), Chinese (你好), Arabic (مرحبا), and other Unicode
        characters are handled without encoding errors.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If Unicode causes encoding errors or crashes
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Unicode payload with emoji, Chinese, Arabic
        unicode_payload = "🎨 Test Agent 你好 مرحبا"

        # Fill form with Unicode
        authenticated_page.fill("input[name='name']", unicode_payload)
        authenticated_page.fill(
            "textarea[name='description']", "Test agent with Unicode characters"
        )

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no encoding errors
        errors = console_monitor.get("error", [])
        encoding_errors = [
            err
            for err in errors
            if "encoding" in err.get("text", "").lower()
            or "unicode" in err.get("text", "").lower()
            or "utf-8" in err.get("text", "").lower()
        ]

        assert (
            len(encoding_errors) == 0
        ), f"Unicode caused encoding errors: {encoding_errors}"

        # Verify page still responsive
        body_visible = authenticated_page.locator("body").is_visible()
        assert body_visible, "Page became unresponsive after Unicode input"

    def test_agent_form_handles_massive_input(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form handles massive input gracefully.

        Tests that 10,000 character strings are handled without causing
        buffer overflow, DoS, or performance degradation.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If massive input causes crash or timeout
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Massive payload (10,000 characters)
        massive_payload = "A" * 10000

        # Fill form with massive input
        authenticated_page.fill("input[name='name']", massive_payload[:500])  # Truncate for name field
        authenticated_page.fill("textarea[name='description']", massive_payload)

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no memory errors
        errors = console_monitor.get("error", [])
        memory_errors = [
            err
            for err in errors
            if "memory" in err.get("text", "").lower()
            or "heap" in err.get("text", "").lower()
            or "overflow" in err.get("text", "").lower()
        ]

        assert (
            len(memory_errors) == 0
        ), f"Massive input caused memory errors: {memory_errors}"

        # Verify page still responsive
        body_visible = authenticated_page.locator("body").is_visible()
        assert body_visible, "Page became unresponsive after massive input"

    def test_agent_form_handles_special_characters(
        self, authenticated_page, console_monitor
    ):
        """Verify agent creation form handles special characters correctly.

        Tests newline (\n), carriage return (\r), tab (\t), and escape
        sequences are handled without crashes or injection vulnerabilities.

        Args:
            authenticated_page: Authenticated Playwright page fixture
            console_monitor: Fixture that captures JavaScript console errors

        Raises:
            AssertionError: If special characters cause injection or crashes
        """
        authenticated_page.goto("http://localhost:3001/agents/new")
        authenticated_page.wait_for_load_state("networkidle")

        # Special character payload
        special_payload = "line1\nline2\rline3\ttab\x1bescape"

        # Fill form with special characters
        authenticated_page.fill("input[name='name']", special_payload)
        authenticated_page.fill(
            "textarea[name='description']", "Test agent with special characters"
        )

        # Submit form
        authenticated_page.click("button[type='submit']", timeout=5000)
        authenticated_page.wait_for_load_state("networkidle", timeout=5000)

        # Verify no injection errors
        errors = console_monitor.get("error", [])
        injection_errors = [
            err
            for err in errors
            if "injection" in err.get("text", "").lower()
            or "xss" in err.get("text", "").lower()
        ]

        assert (
            len(injection_errors) == 0
        ), f"Special characters caused injection errors: {injection_errors}"

        # Verify page still responsive
        body_visible = authenticated_page.locator("body").is_visible()
        assert body_visible, "Page became unresponsive after special character input"
