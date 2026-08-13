# -*- coding: utf-8 -*-
"""Coverage wave 82 — core/ssrf_guard.

Pure validation module — socket.getaddrinfo is patched for DNS checks; no
network. Builds on the earlier wave fixes (IPv4-mapped IPv6, decimal/hex
single-integer encodings) and closes BUG W82-6: libc short-form IPv4
encodings (127.1, 0x7f.0.0.1, 0177.0.0.1) that the OS resolver honors but
ipaddress rejects bypassed the resolve_dns=False literal check.

Coverage targets:
- _is_blocked_ip: invalid string blocked, ipv4-mapped normalization, all
  blocked networks present in the allowlist, public IPs allowed.
- _normalize_ip_literal: decimal / hex / octal single-integer forms, public
  integer forms, canonical IP (None), hostname (None), out-of-range, short
  forms 127.1 / 127.0.1 / 0x7f.0.0.1 / 0177.0.0.1 (conservative octal
  interpretation preferred → blocked), non-numeric (None).
- validate_url: empty/non-str, bad scheme, no hostname, blocked literal v4,
  blocked literal v6, BUG W82-6 (short-form loopback blocked with
  resolve_dns=False), encoded loopback blocked, public IP allowed, DNS
  resolution (blocked IP → error; public → pass; gaierror → pass; generic
  error → pass), resolve_dns=False skips DNS lookup, is_safe_url both ways.
"""
import socket

import pytest
from unittest.mock import patch

from core.ssrf_guard import (
    SSRFError,
    _is_blocked_ip,
    _normalize_ip_literal,
    is_safe_url,
    validate_url,
)


class TestIsBlockedIp:
    def test_invalid_ip_blocked(self):
        assert _is_blocked_ip("not-an-ip") is True

    @pytest.mark.parametrize(
        "ip",
        [
            "0.0.0.0", "10.1.2.3", "100.64.0.1", "127.0.0.1", "169.254.169.254",
            "172.16.0.1", "172.31.255.255", "192.0.0.1", "192.0.2.1", "192.168.1.1",
            "198.18.0.1", "198.51.100.1", "203.0.113.1", "224.0.0.1", "240.0.0.1",
            "::1", "fc00::1", "fe80::1",
        ],
    )
    def test_blocked_networks(self, ip):
        assert _is_blocked_ip(ip) is True

    @pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
    def test_public_allowed(self, ip):
        assert _is_blocked_ip(ip) is False

    def test_ipv4_mapped_ipv6_blocked(self):
        assert _is_blocked_ip("::ffff:127.0.0.1") is True
        assert _is_blocked_ip("::ffff:169.254.169.254") is True
        assert _is_blocked_ip("::ffff:8.8.8.8") is False


class TestNormalizeIpLiteral:
    def test_decimal(self):
        assert _normalize_ip_literal("2130706433") == "127.0.0.1"

    def test_hex(self):
        assert _normalize_ip_literal("0x7f000001") == "127.0.0.1"

    def test_octal(self):
        assert _normalize_ip_literal("017700000001") == "127.0.0.1"

    def test_public_integer(self):
        assert _normalize_ip_literal("134744072") == "8.8.8.8"

    def test_canonical_ip_returns_none(self):
        assert _normalize_ip_literal("8.8.8.8") is None

    def test_hostname_returns_none(self):
        assert _normalize_ip_literal("example.com") is None

    def test_out_of_range(self):
        assert _normalize_ip_literal("4294967296") is None

    def test_negative(self):
        assert _normalize_ip_literal("-1") is None

    def test_short_form_two_parts(self):
        assert _normalize_ip_literal("127.1") == "127.0.0.1"

    def test_short_form_three_parts(self):
        assert _normalize_ip_literal("127.0.1") == "127.0.0.1"

    def test_short_form_hex_components(self):
        assert _normalize_ip_literal("0x7f.0.0.1") == "127.0.0.1"

    def test_short_form_octal_prefers_blocked(self):
        """0177.0.0.1: macOS libc reads 177.0.0.1 (public), glibc inet_aton
        reads 127.0.0.1 (loopback) — the conservative (blocked) reading must
        win so the Linux variant cannot bypass."""
        assert _normalize_ip_literal("0177.0.0.1") == "127.0.0.1"

    def test_short_form_public(self):
        # inet_aton 3-part form: a.b.c where c is a 16-bit value
        assert _normalize_ip_literal("8.8.8") == "8.8.0.8"

    def test_invalid_parts(self):
        assert _normalize_ip_literal("12x.3") is None
        assert _normalize_ip_literal("127..1") is None
        assert _normalize_ip_literal("127.1.2.3.4") is None

    def test_component_too_large(self):
        assert _normalize_ip_literal("256.1.1.1") is None

    def test_invalid_single_hex(self):
        assert _normalize_ip_literal("0xZZ") is None

    def test_invalid_octal_component(self):
        # "09" has a leading zero but is not octal → decimal reading wins
        assert _normalize_ip_literal("09") == "0.0.0.9"
        assert _normalize_ip_literal("08.0.0.1") == "8.0.0.1"

    def test_invalid_hex_component(self):
        assert _normalize_ip_literal("0xzz.1.2.3") is None


class TestValidateUrl:
    @pytest.mark.parametrize("url", [None, "", 123])
    def test_empty_or_non_string(self, url):
        with pytest.raises(SSRFError, match="empty or not a string"):
            validate_url(url)

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host/x",
                                     "javascript:alert(1)", "gopher://h/"])
    def test_bad_scheme(self, url):
        with pytest.raises(SSRFError, match="scheme"):
            validate_url(url)

    def test_no_hostname(self):
        with pytest.raises(SSRFError, match="no hostname"):
            validate_url("http://")

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/x", "http://10.0.0.1/", "http://169.254.169.254/",
        "http://192.168.0.1/", "http://172.16.0.1/", "http://[::1]/",
        "http://[fc00::1]/", "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:169.254.169.254]/",
    ])
    def test_blocked_literal(self, url):
        with pytest.raises(SSRFError, match="blocked IP"):
            validate_url(url, resolve_dns=False)

    def test_encoded_loopback_decimal(self):
        with pytest.raises(SSRFError, match="blocked IP"):
            validate_url("http://2130706433/", resolve_dns=False)

    def test_encoded_loopback_hex(self):
        with pytest.raises(SSRFError, match="blocked IP"):
            validate_url("http://0x7f000001/", resolve_dns=False)

    def test_public_ip_allowed(self):
        url = "http://8.8.8.8/path"
        assert validate_url(url, resolve_dns=False) == url

    def test_hostname_allowed_with_public_dns(self):
        with patch("core.ssrf_guard.socket.getaddrinfo",
                   return_value=[(socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))]):
            assert validate_url("http://example.com/") == "http://example.com/"

    def test_dns_blocked(self):
        with patch("core.ssrf_guard.socket.getaddrinfo",
                   return_value=[(socket.AF_INET, 0, 0, "", ("127.0.0.1", 0)),
                                 (socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))]):
            with pytest.raises(SSRFError, match="resolves to blocked IP"):
                validate_url("http://internal.example.com/")

    def test_dns_gaierror_allowed_to_fail(self):
        with patch("core.ssrf_guard.socket.getaddrinfo", side_effect=socket.gaierror("nxdomain")):
            assert validate_url("http://no-such-host.invalid/") == "http://no-such-host.invalid/"

    def test_dns_generic_error_allowed(self):
        with patch("core.ssrf_guard.socket.getaddrinfo", side_effect=RuntimeError("resolver down")):
            assert validate_url("http://example.com/") == "http://example.com/"

    def test_resolve_dns_false_skips_lookup(self):
        with patch("core.ssrf_guard.socket.getaddrinfo") as gi:
            assert validate_url("http://example.com/", resolve_dns=False) == "http://example.com/"
            gi.assert_not_called()

    @pytest.mark.parametrize("url", [
        "http://127.1/", "http://127.0.1/", "http://0x7f.0.0.1/",
        "http://0177.0.0.1/", "http://2130706433/", "http://0x7f000001/",
    ])
    def test_bug_w82_6_short_forms_blocked_without_dns(self, url):
        """BUG W82-6: libc short-form IPv4 encodings bypassed the literal
        check when resolve_dns=False (no DNS lookup happens for them — the
        OS resolver parses them as IP addresses directly)."""
        with patch("core.ssrf_guard.socket.getaddrinfo") as gi:
            with pytest.raises(SSRFError, match="blocked IP"):
                validate_url(url, resolve_dns=False)
            gi.assert_not_called()


class TestIsSafeUrl:
    def test_safe(self):
        with patch("core.ssrf_guard.socket.getaddrinfo",
                   return_value=[(socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))]):
            assert is_safe_url("http://example.com/") is True

    def test_unsafe(self):
        assert is_safe_url("http://127.0.0.1/") is False
        assert is_safe_url("") is False
