"""
SSRF Guard — validates URLs before outbound HTTP requests.

Blocks requests to private/internal IP ranges to prevent:
- Cloud metadata theft (169.254.169.254)
- Internal service enumeration (127.0.0.1, 10.x, 172.16-31.x, 192.168.x)
- DNS rebinding attacks (resolved IP check)

Usage:
    from core.ssrf_guard import validate_url, SSRFError

    try:
        validate_url(user_provided_url)
        response = requests.get(user_provided_url)
    except SSRFError as e:
        logger.warning(f"Blocked SSRF attempt: {e}")
        raise HTTPException(status_code=400, detail="URL not allowed")

Or as a requests/httpx transport adapter (future work).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSRFError(ValueError):
    """Raised when a URL points to a blocked private/internal destination."""


# IP ranges that must never receive outbound requests from the server.
# These cover loopback, private networks, link-local, cloud metadata, and more.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),        # "This network"
    ipaddress.ip_network("10.0.0.0/8"),        # Private Class A
    ipaddress.ip_network("100.64.0.0/10"),     # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local + cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),     # Private Class B
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),    # Private Class C
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

# Schemes that are allowed for outbound requests.
_ALLOWED_SCHEMES = {"http", "https"}


def _is_blocked_ip(ip_str: str) -> bool:
    """Check if an IP address falls within any blocked network."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # If it's not a valid IP, block it
    # An IPv4-mapped IPv6 address (::ffff:a.b.c.d) is NOT contained by any of
    # the IPv4 blocked networks, so we must also test its embedded IPv4 form.
    # Without this, http://[::ffff:169.254.169.254]/ bypasses the metadata
    # block and http://[::ffff:127.0.0.1]/ bypasses loopback.
    if getattr(ip, "ipv4_mapped", None) is not None:
        ip = ip.ipv4_mapped
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            return True
    return False


def _normalize_ip_literal(host: str) -> "str | None":
    """Normalize an IP literal that the OS/libc accepts but Python's
    ``ipaddress`` does not (decimal, hex, and octal encodings of IPv4, plus
    short-form dotted IPv4 like ``127.1`` → 127.0.0.1).

    Examples: 2130706433 -> 127.0.0.1, 0x7f000001 -> 127.0.0.1,
    127.1 -> 127.0.0.1, 0x7f.0.0.1 -> 127.0.0.1.
    Returns the dotted-quad form, or None if ``host`` is not such an encoding.
    """
    # Dotted forms first: canonical dotted-quads are handled by the caller's
    # ipaddress path (return None); short-form / hex / octal component
    # encodings are expanded here. Checking the dotted branch BEFORE the
    # single-hex branch is important — "0x7f.0.0.1" must not be parsed as a
    # bare hex integer.
    if "." in host:
        try:
            ipaddress.ip_address(host)
            return None  # canonical — handled by the caller's ipaddress path
        except ValueError:
            return _short_form_candidates(host)

    # Single-value numeric encodings (decimal / 0x-hex / leading-zero octal).
    if host.lower().startswith("0x"):
        try:
            values = [int(host.lstrip("0xX"), 16)]
        except ValueError:
            return None
    elif host.isdigit():
        values = [int(host, 10)]
        if host.startswith("0") and len(host) > 1:
            try:
                values.append(int(host, 8))
            except ValueError:
                pass
    else:
        return None

    for val in values:
        if val < 0 or val > 0xFFFFFFFF:
            continue
        try:
            return str(ipaddress.IPv4Address(val))
        except (ValueError, ipaddress.AddressValueError):
            continue
    return None


def _parse_component_values(part: str):
    """Possible integer readings of one dotted component: decimal, 0x-hex,
    and leading-zero octal (glibc inet_aton treats leading zeros as octal;
    modern macOS libc reads them decimal — return BOTH so the conservative
    reading can win downstream)."""
    if not part:
        return []
    if part.lower().startswith("0x"):
        try:
            val = int(part, 16)
        except ValueError:
            return []
        return [val] if 0 <= val <= 0xFFFFFFFF else []
    if part.isdigit():
        values = [int(part, 10)]
        if part.startswith("0") and len(part) > 1:
            try:
                values.append(int(part, 8))
            except ValueError:
                pass
        return values
    return []


def _short_form_candidates(host: str):
    """Expand libc short-form IPv4 notation into dotted-quad strings.

    inet_aton semantics: 2 parts a.b (b is 24-bit), 3 parts a.b.c (c is
    16-bit), 4 parts a.b.c.d (each 8-bit). When a blocked reading exists
    (e.g. octal vs decimal component), return the blocked one — fail closed
    so glibc-based resolvers cannot be tricked into loopback.
    """
    parts = host.split(".")
    if not 2 <= len(parts) <= 4:
        return None
    parsed = [_parse_component_values(p) for p in parts]
    if any(not comp for comp in parsed):
        return None

    import itertools

    weights = {2: (24, 0), 3: (24, 16, 0), 4: (24, 16, 8, 0)}
    maxes = {2: (0xFF, 0xFFFFFF), 3: (0xFF, 0xFF, 0xFFFF), 4: (0xFF, 0xFF, 0xFF, 0xFF)}

    candidates = []
    for combo in itertools.product(*parsed):
        if any(val > mx for val, mx in zip(combo, maxes[len(parts)])):
            continue
        addr = sum(val << shift for val, shift in zip(combo, weights[len(parts)]))
        candidates.append(str(ipaddress.IPv4Address(addr)))

    if not candidates:
        return None
    # Fail closed: prefer a blocked candidate over a public one.
    for candidate in candidates:
        if _is_blocked_ip(candidate):
            return candidate
    return candidates[0]


def validate_url(url: str, *, resolve_dns: bool = True) -> str:
    """Validate that a URL is safe for outbound requests.

    Args:
        url: The URL to validate.
        resolve_dns: If True, resolve the hostname and check the IP.
            Set to False for URLs that will be validated again at request time.

    Returns:
        The validated URL (unchanged if safe).

    Raises:
        SSRFError: If the URL scheme is not allowed, the hostname resolves
            to a private/internal IP, or the URL is malformed.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL is empty or not a string")

    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SSRFError(
            f"URL scheme '{parsed.scheme}' is not allowed. Only http/https permitted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL has no hostname")

    # Check if hostname is already an IP literal (dotted-quad, IPv6, or an
    # encoded form like decimal/hex that the OS resolver would accept).
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        # Not a canonical IP — but it may be a decimal/hex encoding of an
        # IPv4 address (e.g. http://2130706433/ = 127.0.0.1). Normalize and
        # re-check so resolve_dns=False callers are still protected against
        # encoded-IP bypasses that the OS resolver would honor.
        normalized = _normalize_ip_literal(hostname)
        if normalized is not None and _is_blocked_ip(normalized):
            raise SSRFError(
                f"URL points to blocked IP address: {hostname} ({normalized})"
            )
        # Otherwise it's a regular hostname — resolve below.
    else:
        if _is_blocked_ip(hostname):
            raise SSRFError(f"URL points to blocked IP address: {hostname}")

    # DNS resolution check
    if resolve_dns:
        try:
            # getaddrinfo returns all resolved IPs — check ALL of them
            infos = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in infos:
                ip = sockaddr[0]
                if _is_blocked_ip(ip):
                    raise SSRFError(
                        f"Hostname '{hostname}' resolves to blocked IP: {ip}"
                    )
        except socket.gaierror:
            # DNS resolution failed — allow the request to fail naturally
            # (the HTTP client will handle the error)
            logger.debug(f"DNS resolution failed for '{hostname}' — allowing request to fail naturally")
        except SSRFError:
            raise
        except Exception as e:
            logger.warning(f"SSRF DNS check error for '{hostname}': {e}")

    return url


def is_safe_url(url: str) -> bool:
    """Non-raising version of validate_url. Returns True/False."""
    try:
        validate_url(url)
        return True
    except SSRFError:
        return False
