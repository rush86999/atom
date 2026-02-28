"""
Path Traversal Security Tests (SECU-03.3).

Comprehensive tests for path traversal attack prevention:
- ../ sequences (Unix)
- ..\ sequences (Windows)
- Double-encoded variants
- URL-encoded variants
- Unicode-encoded variants

OWASP Category: A01:2021 - Broken Access Control
CWE: CWE-22 (Path Traversal)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


# ============================================================================
# Path Traversal Payloads
# ============================================================================

# Unix-style path traversal payloads
UNIX_PATH_TRAVERSAL = [
    "../../../etc/passwd",
    "..//..//..//etc/passwd",
    "....//....//....//etc/passwd",
    "../../../../etc/passwd",
    "..../../etc/passwd",
    "../etc/passwd",
    "../../etc/passwd",
    "../../../etc/shadow",
    "../../../../etc/shadow",
    "../.ssh/id_rsa",
    "../../.ssh/id_rsa",
    "../../../.ssh/id_rsa",
    "../root/.ssh/id_rsa",
    "../../root/.ssh/id_rsa",
]

# Windows-style path traversal payloads
WINDOWS_PATH_TRAVERSAL = [
    r"..\..\..\..\windows\system32\config\sam",
    r"..\\..\\..\\windows\\system32\\config\\sam",
    r"....\\....\\....\\windows\\system32\\config\\sam",
    r"..\..\..\windows\system32\drivers\etc\hosts",
    r"..\..\..\..\windows\system32\config\sam",
    r"..\..\boot.ini",
    r"..\..\..\boot.ini",
    r"..\..\..\..\boot.ini",
    r"..\..\..\..\..\windows\win.ini",
    r"..\..\..\..\windows\system32\config\sam",
]

# URL-encoded path traversal payloads
URL_ENCODED_TRAVERSAL = [
    "%2e%2e%2fetc%2fpasswd",  # ../etc/passwd
    "%2e%2e%5cetc%2fpasswd",  # ..\etc/passwd
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # ../../../etc/passwd
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fshadow",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "..%252f..%252f..%252fetc%252fpasswd",  # Double-encoded
    "..%252f..%252f..%252fetc%252fshadow",  # Double-encoded
    "..%255c..%255c..%255cetc%255cshadow",  # Double-encoded backslash
    "%252e%252e%252f%252e%252e%252fetc%252fpasswd",  # Triple-encoded
]

# Unicode-encoded path traversal payloads
UNICODE_ENCODED_TRAVERSAL = [
    "..%c0%af..%c0%af..%c0%afetc/passwd",  # Unicode bypass
    "..%c0%af..%c0%af..%c0%afetc/shadow",
    "..%c0%af..%c0%afetc/passwd",
    "..%c0%afetc/passwd",
    "%c0%ae%c0%ae%c0%af%c0%ae%c0%ae%c0%afetc/passwd",  # Full Unicode encoding
]

# Mixed path traversal payloads
MIXED_TRAVERSAL = [
    "....//....//....//etc/passwd",
    "..\\..\\..\\..\\etc/passwd",  # Mixed separators
    "..%5c..%5c..%5cetc/passwd",  # URL-encoded backslash, forward slash
    "../..\\../etc/passwd",  # Alternating separators
    "..%2f..%2fetc%2fpasswd",
    "..\\..%5cetc%5cshadow",
]


class TestPathTraversalInFileUploads:
    """Test path traversal in file upload operations."""

    @pytest.mark.parametrize("payload", UNIX_PATH_TRAVERSAL[:5])
    def test_unix_path_traversal_in_filename(self, payload, client: TestClient, admin_token: str):
        """
        Test Unix-style path traversal in filename parameter.

        ATTACK: Attempt to access /etc/passwd using ../ sequences
        EXPECTED: Path validation rejects or sanitizes the input
        """
        # Try to upload a file with path traversal in filename
        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test content"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should reject or sanitize
        # Should NOT return file contents like /etc/passwd
        assert response.status_code in [400, 403, 404, 422, 200]
        assert "root:" not in response.text
        assert "[extensions]" not in response.text

    @pytest.mark.parametrize("payload", WINDOWS_PATH_TRAVERSAL[:5])
    def test_windows_path_traversal_in_filename(self, payload, client: TestClient, admin_token: str):
        """
        Test Windows-style path traversal in filename parameter.

        ATTACK: Attempt to access Windows system files using ..\ sequences
        EXPECTED: Path validation rejects or sanitizes the input
        """
        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test content"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422, 200]
        # Should not contain Windows file contents
        assert "[boot loader]" not in response.text.lower()


class TestPathTraversalInCanvasTemplates:
    """Test path traversal in canvas template selection."""

    @pytest.mark.parametrize("payload", UNIX_PATH_TRAVERSAL[:5])
    def test_path_traversal_in_template_path(self, payload, client: TestClient, admin_token: str):
        """
        Test path traversal in canvas template parameter.

        ATTACK: Attempt to access sensitive files using template parameter
        EXPECTED: Template validation rejects path traversal attempts
        """
        response = client.post(
            "/api/canvas",
            json={
                "title": "Test Canvas",
                "template": payload,
                "canvas_type": "generic"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422, 200]
        assert "root:" not in response.text

    @pytest.mark.parametrize("payload", ["../../../sensitive/config.json", r"..\..\..\sensitive\api_keys.txt"])
    def test_path_traversal_to_sensitive_files(self, payload, client: TestClient, admin_token: str):
        """
        Test path traversal to sensitive configuration files.

        ATTACK: Attempt to access config files, API keys, secrets
        EXPECTED: Access blocked, files not exposed
        """
        response = client.post(
            "/api/canvas",
            json={
                "title": "Test Canvas",
                "template": payload,
                "canvas_type": "generic"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422, 200]
        # Should not leak sensitive data
        assert "api_key" not in response.text.lower()
        assert "secret" not in response.text.lower()
        assert "password" not in response.text.lower()


class TestPathTraversalInBrowserAutomation:
    """Test path traversal in browser automation."""

    @pytest.mark.parametrize("payload", UNIX_PATH_TRAVERSAL[:3])
    def test_path_traversal_in_screenshot_url(self, payload, client: TestClient, admin_token: str):
        """
        Test path traversal in browser screenshot URL parameter.

        ATTACK: Attempt to read local files via screenshot URL
        EXPECTED: URL validation rejects file:// protocol or path traversal
        """
        response = client.post(
            "/api/tools/browser/screenshot",
            json={"url": f"file:///{payload}"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422, 401, 500]
        assert "root:" not in response.text

    @pytest.mark.parametrize("payload", ["file:///etc/passwd", "file:///etc/shadow", "file:///root/.ssh/id_rsa"])
    def test_file_protocol_blocked(self, payload, client: TestClient, admin_token: str):
        """
        Test file:// protocol is blocked.

        ATTACK: Attempt to use file:// protocol to read local files
        EXPECTED: Protocol validation rejects file:// URLs
        """
        response = client.post(
            "/api/tools/browser/screenshot",
            json={"url": payload},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422, 401, 500]
        assert "root:" not in response.text


class TestDoubleEncodedPathTraversal:
    """Test double-encoded path traversal attempts."""

    @pytest.mark.parametrize("payload", [
        "%252e%252e%252fetc%252fpasswd",  # Double-encoded ../
        "..%252f%252e%252e%252fetc%252fpasswd",
        "%252e%252e%255cetc%252fshadow",  # Double-encoded ..\
    ])
    def test_double_encoded_path_traversal(self, payload, client: TestClient, admin_token: str):
        """
        Test double-encoded path traversal payloads.

        ATTACK: Bypass input validation by double-encoding ../ sequences
        EXPECTED: URL decoding applied correctly, traversal detected
        """
        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text


class TestUnicodeEncodedPathTraversal:
    """Test Unicode-encoded path traversal attempts."""

    @pytest.mark.parametrize("payload", UNICODE_ENCODED_TRAVERSAL[:3])
    def test_unicode_encoded_path_traversal(self, payload, client: TestClient, admin_token: str):
        """
        Test Unicode-encoded path traversal payloads.

        ATTACK: Bypass input validation using Unicode encoding
        EXPECTED: Unicode normalization applied, traversal detected
        """
        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text


class TestMixedPathTraversal:
    """Test mixed path traversal attempts."""

    @pytest.mark.parametrize("payload", MIXED_TRAVERSAL[:3])
    def test_mixed_separator_traversal(self, payload, client: TestClient, admin_token: str):
        """
        Test mixed path separator traversal attempts.

        ATTACK: Mix Unix and Windows path separators to bypass validation
        EXPECTED: Normalization applied, traversal detected
        """
        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text


class TestPathTraversalInQueryParameters:
    """Test path traversal in query parameters."""

    @pytest.mark.parametrize("payload", UNIX_PATH_TRAVERSAL[:3])
    def test_path_traversal_in_query_param(self, payload, client: TestClient, admin_token: str):
        """
        Test path traversal in query string parameters.

        ATTACK: Inject path traversal via query parameters
        EXPECTED: Query parameter validation blocks traversal
        """
        from urllib.parse import quote
        encoded_payload = quote(payload, safe='')

        response = client.get(
            f"/api/canvas?template={encoded_payload}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 400, 403, 404, 422]
        if response.status_code == 200:
            # If successful, ensure no file contents leaked
            assert "root:" not in response.text


class TestPathTraversalInRequestBody:
    """Test path traversal in request body."""

    @pytest.mark.parametrize("payload", UNIX_PATH_TRAVERSAL[:3])
    def test_path_traversal_in_json_body(self, payload, client: TestClient, admin_token: str):
        """
        Test path traversal in JSON request body.

        ATTACK: Inject path traversal via JSON body fields
        EXPECTED: Request body validation blocks traversal
        """
        response = client.post(
            "/api/canvas",
            json={
                "title": "Test",
                "canvas_type": "generic",
                "custom_path": payload  # Malicious custom path
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 400, 403, 404, 422]
        if response.status_code == 200:
            assert "root:" not in response.text


class TestPathTraversalEdgeCases:
    """Test path traversal edge cases."""

    def test_null_byte_injection(self, client: TestClient, admin_token: str):
        """
        Test null byte injection in path traversal.

        ATTACK: Use null bytes to bypass string validation
        EXPECTED: Null byte stripping or rejection
        """
        payload = "../../../etc/passwd\x00.jpg"

        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text

    def test_absolute_path_bypass(self, client: TestClient, admin_token: str):
        """
        Test absolute path bypass attempts.

        ATTACK: Use absolute paths instead of relative traversal
        EXPECTED: Absolute path validation blocks system files
        """
        for payload in ["/etc/passwd", "/etc/shadow", "C:\\Windows\\System32\\config\\SAM"]:
            response = client.post(
                "/api/files/upload",
                json={"filename": payload, "content": "test"},
                headers={"Authorization": f"Bearer {admin_token}"}
            )

            assert response.status_code in [400, 403, 404, 422]
            assert "root:" not in response.text

    def test_path_traversal_with_valid_extension(self, client: TestClient, admin_token: str):
        """
        Test path traversal with valid file extension.

        ATTACK: Use path traversal with .jpg/.png extension to bypass extension check
        EXPECTED: Full path validation, not just extension check
        """
        payload = "../../../etc/passwd.jpg"

        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        # Even with .jpg extension, should not access /etc/passwd
        assert "root:" not in response.text


class TestPathTraversalPreventionMechanisms:
    """Test that path traversal prevention mechanisms work."""

    def test_path_normalization(self, client: TestClient, admin_token: str):
        """
        Test that path normalization is applied.

        CHECK: ../ sequences are resolved and validated
        EXPECTED: Normalized path is checked against allowed directories
        """
        payload = "subdir/../../etc/passwd"

        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text

    def test_canonical_path_check(self, client: TestClient, admin_token: str):
        """
        Test that canonical (real) paths are checked.

        CHECK: Symbolic links are resolved and checked
        EXPECTED: Real path is validated, not just the symlink path
        """
        # Even if symlinks are used, real path should be validated
        payload = "../../../var/log/syslog"

        response = client.post(
            "/api/files/upload",
            json={"filename": payload, "content": "test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        # Should not leak system log contents

    def test_chroot_jail_boundary(self, client: TestClient, admin_token: str):
        """
        Test that chroot jail boundaries are enforced.

        CHECK: File access is restricted to allowed directory
        EXPECTED: Cannot escape chroot directory using ../
        """
        for payload in ["../../../etc/passwd", "..../etc/passwd", "../../etc/passwd"]:
            response = client.post(
                "/api/files/upload",
                json={"filename": payload, "content": "test"},
                headers={"Authorization": f"Bearer {admin_token}"}
            )

            assert response.status_code in [400, 403, 404, 422]
            assert "root:" not in response.text


class TestPathTraversalInSpecificEndpoints:
    """Test path traversal in specific API endpoints."""

    def test_path_traversal_in_episode_retrieval(self, client: TestClient, admin_token: str):
        """Test path traversal in episode file retrieval."""
        payload = "../../../etc/passwd"

        response = client.get(
            f"/api/episodes/file/{payload}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text

    def test_path_traversal_in_canvas_component_load(self, client: TestClient, admin_token: str):
        """Test path traversal in canvas component loading."""
        payload = "../../../etc/passwd"

        response = client.get(
            f"/api/canvas/components/{payload}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text

    def test_path_traversal_in_template_rendering(self, client: TestClient, admin_token: str):
        """Test path traversal in template rendering."""
        payload = "../../../etc/passwd"

        response = client.post(
            "/api/canvas/render",
            json={"template": payload, "data": {}},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [400, 403, 404, 422]
        assert "root:" not in response.text
