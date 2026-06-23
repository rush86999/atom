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
    for network in _BLOCKED_NETWORKS:
        if ip in network:
            return True
    return False


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

    # Check if hostname is already an IP literal
    try:
        ipaddress.ip_address(hostname)
        if _is_blocked_ip(hostname):
            raise SSRFError(f"URL points to blocked IP address: {hostname}")
    except ValueError:
        pass  # Not an IP literal — it's a hostname, resolve below

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
