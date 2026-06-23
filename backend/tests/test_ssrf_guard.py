"""Tests for SSRF guard — verifies private IP blocking."""
from __future__ import annotations

import pytest
from core.ssrf_guard import validate_url, is_safe_url, SSRFError


class TestSchemeValidation:
    def test_https_allowed(self):
        assert validate_url("https://api.openai.com/v1/chat") == "https://api.openai.com/v1/chat"

    def test_http_allowed(self):
        assert validate_url("http://example.com/path") == "http://example.com/path"

    def test_file_scheme_blocked(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_url("file:///etc/passwd")

    def test_ftp_scheme_blocked(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_url("ftp://evil.com/file")

    def test_javascript_scheme_blocked(self):
        with pytest.raises(SSRFError, match="scheme"):
            validate_url("javascript:alert(1)")


class TestBlockedIPs:
    @pytest.mark.parametrize("ip", [
        "127.0.0.1", "127.0.1.1", "127.255.255.255",
        "10.0.0.1", "10.255.255.255",
        "172.16.0.1", "172.31.255.255",
        "192.168.1.1", "192.168.0.0",
        "169.254.169.254",  # AWS metadata endpoint
        "0.0.0.0",
    ])
    def test_blocked_ipv4_url(self, ip):
        with pytest.raises(SSRFError, match="blocked"):
            validate_url(f"http://{ip}/path")

    def test_blocked_ipv6_loopback(self):
        """IPv6 loopback ::1 must be blocked (bracketed in URLs)."""
        with pytest.raises(SSRFError, match="blocked"):
            validate_url("http://[::1]/path")

    @pytest.mark.parametrize("ip", [
        "8.8.8.8", "1.1.1.1", "104.16.132.229",  # Public IPs
    ])
    def test_public_ip_allowed(self, ip):
        # Don't resolve DNS for IP literals — just check the IP itself
        result = validate_url(f"https://{ip}/path", resolve_dns=False)
        assert result == f"https://{ip}/path"


class TestCloudMetadataProtection:
    def test_aws_metadata_blocked(self):
        """169.254.169.254 is the AWS/GCP/Azure metadata endpoint."""
        with pytest.raises(SSRFError):
            validate_url("http://169.254.169.254/latest/meta-data/iam/security-credentials/")

    def test_gcp_metadata_blocked(self):
        """metadata.google.internal resolves to 169.254.169.254 inside GCP.
        Outside GCP the DNS won't resolve — skip in that case."""
        import socket
        try:
            socket.getaddrinfo("metadata.google.internal", None)
        except socket.gaierror:
            pytest.skip("metadata.google.internal not resolvable outside GCP")
        with pytest.raises(SSRFError):
            validate_url("http://metadata.google.internal/computeMetadata/v1/")


class TestEdgeCases:
    def test_empty_url(self):
        with pytest.raises(SSRFError):
            validate_url("")

    def test_none_url(self):
        with pytest.raises(SSRFError):
            validate_url(None)  # type: ignore

    def test_no_hostname(self):
        with pytest.raises(SSRFError, match="hostname"):
            validate_url("https:///path")

    def test_is_safe_url_true(self):
        assert is_safe_url("https://api.openai.com") is True

    def test_is_safe_url_false(self):
        assert is_safe_url("http://127.0.0.1/admin") is False
