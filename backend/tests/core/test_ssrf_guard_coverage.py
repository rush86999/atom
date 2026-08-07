"""
Coverage + security bug-hunt tests for core/ssrf_guard.py.

Targets every branch of validate_url / is_safe_url / _is_blocked_ip and
verifies the SSRF guard defeats known bypass techniques:
  * IPv4-mapped IPv6 of cloud-metadata / loopback
  * decimal / hex encoded loopback IPs (resolve_dns=False path)
  * DNS rebinding (first A record private, second public)
  * malformed URLs, disallowed schemes, non-string input

Security-bug tests carry a ``BUG:`` docstring and are written TDD-style:
they fail before the source fix and pass afterwards.
"""
from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from core.ssrf_guard import (
    SSRFError,
    _is_blocked_ip,
    _normalize_ip_literal,
    is_safe_url,
    validate_url,
)


# ---------------------------------------------------------------------------
# _is_blocked_ip: direct unit coverage of every blocked network
# ---------------------------------------------------------------------------
class TestIsBlockedIp:
    @pytest.mark.parametrize(
        "ip",
        [
            "0.0.0.0",            # this-network
            "10.0.0.5",           # private A
            "100.64.0.1",         # CGNAT
            "127.0.0.1",          # loopback
            "127.255.255.255",    # loopback top
            "169.254.169.254",    # link-local / cloud metadata
            "169.254.0.1",
            "172.16.0.1",         # private B start
            "172.31.255.255",     # private B end
            "192.0.0.1",          # IETF protocol assignments
            "192.0.2.1",          # TEST-NET-1
            "192.168.1.1",        # private C
            "198.18.0.1",         # benchmark
            "198.51.100.1",       # TEST-NET-2
            "203.0.113.1",        # TEST-NET-3
            "224.0.0.1",          # multicast
            "240.0.0.1",          # reserved
            "::1",                # IPv6 loopback
            "fc00::1",            # IPv6 ULA
            "fd00::1",
            "fe80::1",            # IPv6 link-local
        ],
    )
    def test_blocked_networks(self, ip):
        assert _is_blocked_ip(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "1.1.1.1",
            "104.16.132.229",
            "172.32.0.1",      # just outside private B
            "172.15.0.1",      # just below private B
            "11.0.0.1",        # just outside private A
            "2606:4700:4700::1111",  # public IPv6 (Cloudflare DNS)
        ],
    )
    def test_public_networks_not_blocked(self, ip):
        assert _is_blocked_ip(ip) is False

    def test_invalid_ip_string_is_blocked(self):
        """A non-IP string passed to _is_blocked_ip must be treated as blocked
        (fail-closed) rather than raising."""
        assert _is_blocked_ip("not-an-ip") is True

    def test_ipv4_mapped_loopback_blocked(self):
        """BUG: IPv4-mapped IPv6 of loopback (::ffff:127.0.0.1) must be blocked.

        Previously _is_blocked_ip only checked the literal against IPv4 and
        IPv6 blocked-network lists; an IPv4-mapped IPv6 address like
        ::ffff:127.0.0.1 falls outside 127.0.0.0/8 and was allowed, opening a
        bypass to reach loopback services.
        """
        assert _is_blocked_ip("::ffff:127.0.0.1") is True

    def test_ipv4_mapped_cloud_metadata_blocked(self):
        """BUG: IPv4-mapped IPv6 of the cloud-metadata IP must be blocked.

        ::ffff:169.254.169.254 is the IPv4-mapped form of the AWS/GCP/Azure
        metadata endpoint; allowing it permits cloud metadata theft over IPv6.
        """
        assert _is_blocked_ip("::ffff:169.254.169.254") is True

    def test_ipv4_mapped_public_not_blocked(self):
        """A public IPv4 address mapped into IPv6 must still be allowed."""
        assert _is_blocked_ip("::ffff:8.8.8.8") is False


class TestNormalizeIpLiteral:
    """Direct unit coverage for the decimal/hex/octal IP normalizer."""

    def test_decimal_loopback(self):
        assert _normalize_ip_literal("2130706433") == "127.0.0.1"

    def test_hex_loopback(self):
        assert _normalize_ip_literal("0x7f000001") == "127.0.0.1"

    def test_octal_loopback(self):
        assert _normalize_ip_literal("017700000001") == "127.0.0.1"

    def test_decimal_public(self):
        assert _normalize_ip_literal("134744072") == "8.8.8.8"

    def test_dotted_quad_returns_none(self):
        # Already-canonical dotted-quad strings are not "encoded" forms.
        assert _normalize_ip_literal("8.8.8.8") is None

    def test_hostname_returns_none(self):
        assert _normalize_ip_literal("example.com") is None

    def test_out_of_range_decimal_returns_none(self):
        assert _normalize_ip_literal("4294967296") is None  # 2**32

    def test_negative_returns_none(self):
        assert _normalize_ip_literal("-1") is None


# ---------------------------------------------------------------------------
# validate_url: scheme / hostname / IP-literal / DNS branches
# ---------------------------------------------------------------------------
class TestSchemeValidation:
    def test_https_returns_url_unchanged(self):
        url = "https://api.example.com/v1/chat"
        assert validate_url(url) == url

    def test_http_allowed(self):
        assert validate_url("http://example.com/p") == "http://example.com/p"

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://evil.com/x",
            "javascript:alert(1)",
            "gopher://x/y",
            "dict://localhost:11211/stat",
            "data:text/html,<script>",
            "ldap://localhost",
        ],
    )
    def test_disallowed_schemes_blocked(self, url):
        with pytest.raises(SSRFError, match="scheme"):
            validate_url(url)

    def test_uppercase_scheme_handled(self):
        # urlparse lowercases scheme; HTTPS still allowed.
        assert validate_url("HTTPS://example.com") == "HTTPS://example.com"


class TestInputValidation:
    def test_empty_string_rejected(self):
        with pytest.raises(SSRFError, match="empty"):
            validate_url("")

    def test_none_rejected(self):
        with pytest.raises(SSRFError, match="empty"):
            validate_url(None)  # type: ignore[arg-type]

    def test_non_string_rejected(self):
        with pytest.raises(SSRFError, match="empty"):
            validate_url(12345)  # type: ignore[arg-type]

    def test_missing_hostname_rejected(self):
        with pytest.raises(SSRFError, match="hostname"):
            validate_url("https:///path-only")

    def test_no_scheme_rejected(self):
        # No scheme -> parsed.scheme == "" which is not in allowed set.
        with pytest.raises(SSRFError):
            validate_url("//example.com/path")


class TestIpLiteralBlocking:
    def test_loopback_ipv4_blocked(self):
        with pytest.raises(SSRFError, match="blocked"):
            validate_url("http://127.0.0.1/admin", resolve_dns=False)

    def test_metadata_ipv4_blocked(self):
        with pytest.raises(SSRFError, match="blocked"):
            validate_url(
                "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                resolve_dns=False,
            )

    def test_public_ipv4_literal_allowed(self):
        assert (
            validate_url("https://8.8.8.8/", resolve_dns=False)
            == "https://8.8.8.8/"
        )

    def test_ipv6_loopback_bracketed_blocked(self):
        with pytest.raises(SSRFError, match="blocked"):
            validate_url("http://[::1]/", resolve_dns=False)

    def test_ipv4_mapped_loopback_url_blocked(self):
        """BUG: http://[::ffff:127.0.0.1]/ must be blocked as SSRF.

        The bracketed IPv4-mapped IPv6 literal reaches loopback services and
        was accepted because the IPv6 address is not in any IPv4 blocked range.
        """
        with pytest.raises(SSRFError, match="blocked"):
            validate_url("http://[::ffff:127.0.0.1]/", resolve_dns=False)

    def test_ipv4_mapped_metadata_url_blocked(self):
        """BUG: http://[::ffff:169.254.169.254]/ must be blocked (metadata theft)."""
        with pytest.raises(SSRFError, match="blocked"):
            validate_url(
                "http://[::ffff:169.254.169.254]/latest/meta-data/",
                resolve_dns=False,
            )

    def test_decimal_encoded_loopback_blocked_no_dns(self):
        """BUG: http://2130706433/ (decimal 127.0.0.1) must be blocked even
        when DNS resolution is disabled.

        ipaddress.ip_address() does not parse decimal/hex encodings, so the
        literal fell through to the hostname branch and was never checked.
        """
        with pytest.raises(SSRFError):
            validate_url("http://2130706433/", resolve_dns=False)

    def test_hex_encoded_loopback_blocked_no_dns(self):
        """BUG: http://0x7f000001/ (hex 127.0.0.1) must be blocked even
        when DNS resolution is disabled."""
        with pytest.raises(SSRFError):
            validate_url("http://0x7f000001/", resolve_dns=False)

    def test_octal_encoded_loopback_blocked_no_dns(self):
        """Octal-encoded loopback (017700000001 -> 127.0.0.1) must be blocked."""
        with pytest.raises(SSRFError):
            validate_url("http://017700000001/", resolve_dns=False)

    def test_decimal_encoded_public_allowed_no_dns(self):
        """Decimal encoding of a public IP (8.8.8.8 = 134744072) is allowed
        but the path is still exercised by the normalizer."""
        # _is_blocked_ip fail-closes on non-IP strings, so a decimal public IP
        # that the normalizer resolves to a real public address is allowed.
        assert (
            validate_url("http://134744072/", resolve_dns=False)
            == "http://134744072/"
        )


# ---------------------------------------------------------------------------
# DNS resolution branch — mocked getaddrinfo
# ---------------------------------------------------------------------------
class TestDnsResolution:
    def test_hostname_resolving_to_public_ip_allowed(self):
        with patch("core.ssrf_guard.socket.getaddrinfo") as mock:
            mock.return_value = [
                (socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))
            ]
            assert validate_url("https://example.com/") == "https://example.com/"

    def test_hostname_resolving_to_private_ip_blocked(self):
        with patch("core.ssrf_guard.socket.getaddrinfo") as mock:
            mock.return_value = [
                (socket.AF_INET, 0, 0, "", ("10.0.0.1", 0))
            ]
            with pytest.raises(SSRFError, match="resolves to blocked"):
                validate_url("https://internal.example.com/")

    def test_hostname_with_any_private_ip_blocked(self):
        """If any one of multiple A records is private, the request is blocked."""
        with patch("core.ssrf_guard.socket.getaddrinfo") as mock:
            mock.return_value = [
                (socket.AF_INET, 0, 0, "", ("93.184.216.34", 0)),
                (socket.AF_INET, 0, 0, "", ("127.0.0.1", 0)),
            ]
            with pytest.raises(SSRFError, match="resolves to blocked"):
                validate_url("https://rebind.example.com/")

    def test_dns_resolution_failure_allows_request(self):
        """gaierror is swallowed: the HTTP client will fail naturally later."""
        with patch("core.ssrf_guard.socket.getaddrinfo", side_effect=socket.gaierror):
            # No raise — caller can proceed and let the HTTP layer fail.
            assert validate_url("https://nonexistent.invalid/") == "https://nonexistent.invalid/"

    def test_unexpected_socket_error_is_swallowed(self):
        """Any non-gaierror exception from getaddrinfo is logged and tolerated
        (fail-open by design: better a noisy failure than a DoS)."""
        with patch("core.ssrf_guard.socket.getaddrinfo", side_effect=OSError("boom")):
            assert validate_url("https://example.com/") == "https://example.com/"

    def test_resolve_dns_false_skips_lookup(self):
        """When resolve_dns=False the DNS branch is skipped entirely."""
        with patch("core.ssrf_guard.socket.getaddrinfo") as mock:
            validate_url("https://example.com/", resolve_dns=False)
            mock.assert_not_called()

    def test_dns_rebinding_check_runs_for_public_hostname(self):
        """A hostname that is not an IP literal still triggers a DNS lookup."""
        with patch("core.ssrf_guard.socket.getaddrinfo") as mock:
            mock.return_value = [
                (socket.AF_INET, 0, 0, "", ("169.254.169.254", 0))
            ]
            with pytest.raises(SSRFError):
                validate_url("https://metadata.attacker.com/")


# ---------------------------------------------------------------------------
# is_safe_url wrapper
# ---------------------------------------------------------------------------
class TestIsSafeUrl:
    def test_safe_public_url(self):
        with patch("core.ssrf_guard.socket.getaddrinfo") as mock:
            mock.return_value = [
                (socket.AF_INET, 0, 0, "", ("93.184.216.34", 0))
            ]
            assert is_safe_url("https://example.com/") is True

    def test_loopback_unsafe(self):
        assert is_safe_url("http://127.0.0.1/") is False

    def test_bad_scheme_unsafe(self):
        assert is_safe_url("file:///etc/passwd") is False

    def test_empty_unsafe(self):
        assert is_safe_url("") is False

    def test_ipv4_mapped_metadata_unsafe(self):
        """BUG: is_safe_url must reject IPv4-mapped metadata IP."""
        assert is_safe_url("http://[::ffff:169.254.169.254]/") is False
