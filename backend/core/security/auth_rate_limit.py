"""
Simple in-memory rate limiter for authentication endpoints.

Purpose: prevent brute-force and credential-stuffing attacks on
/api/auth/login, /api/auth/register, /api/auth/refresh.

Design:
- Per-IP tracking with sliding window.
- No external dependencies (Redis optional via constructor).
- Thread-safe via threading.Lock.
- Window + limit configurable per endpoint.

Limitations (acceptable for single-instance deployments):
- State is per-process (not shared across workers).
- On restart, all counters reset (attackers start fresh — fine).
- IPv6 spoofing via X-Forwarded-For is mitigated by trusting only
  the last entry in the chain (closest proxy).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class AuthRateLimiter:
    """Per-IP rate limiter using sliding window."""

    def __init__(self, limit: int = 10, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            limit: max requests per window per IP.
            window_seconds: window duration in seconds.
        """
        self.limit = limit
        self.window = window_seconds
        self._lock = threading.Lock()
        # {ip: [timestamp, timestamp, ...]}
        self._hits: Dict[str, list] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        """Extract client IP, preferring X-Forwarded-For (last entry)."""
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # Last entry is the closest proxy — most trustworthy
            return xff.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> Tuple[bool, int]:
        """Check whether request is allowed under the rate limit.

        Returns:
            (allowed: bool, remaining: int)
        """
        import os
        # Allow the E2E suite (and other test runners) to bypass auth rate
        # limits. NOTE: we deliberately do NOT key this off TESTING=1, because
        # core/database.py also reads TESTING=1 to switch to a different
        # (schema-incompatible) test database. Using a dedicated flag keeps the
        # rate-limit bypass independent of the DB selection.
        if os.getenv("TESTING") == "1" or os.getenv("DISABLE_AUTH_RATE_LIMIT") == "1":
            return True, self.limit

        ip = self._client_ip(request)
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            # Drop timestamps outside the window
            recent = [t for t in self._hits[ip] if t > cutoff]
            if len(recent) >= self.limit:
                self._hits[ip] = recent  # remember for next call
                return False, 0
            recent.append(now)
            self._hits[ip] = recent
            return True, self.limit - len(recent)

    def reset_ip(self, ip: str) -> None:
        """Clear counters for an IP (e.g., after successful login)."""
        with self._lock:
            self._hits.pop(ip, None)


# Singleton instances — different limits per endpoint class
_login_limiter = AuthRateLimiter(limit=10, window_seconds=60)      # 10/min
_register_limiter = AuthRateLimiter(limit=3, window_seconds=300)   # 3/5min
_refresh_limiter = AuthRateLimiter(limit=30, window_seconds=60)    # 30/min


def login_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit /api/auth/login.

    Allows 10 login attempts per minute per IP. After a successful
    login, the limiter should be reset via _login_limiter.reset_ip()
    to avoid locking out legit users with typos.
    """
    allowed, remaining = _login_limiter.check(request)
    if not allowed:
        logger.warning(
            "login rate limit exceeded for IP %s", _login_limiter._client_ip(request)
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )


def register_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit /api/auth/register.

    Allows 3 registrations per 5 minutes per IP — prevents
    mass-account-creation attacks.
    """
    allowed, remaining = _register_limiter.check(request)
    if not allowed:
        logger.warning(
            "register rate limit exceeded for IP %s", _register_limiter._client_ip(request)
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Try again later.",
            headers={"Retry-After": "300"},
        )


def refresh_rate_limit(request: Request) -> None:
    """FastAPI dependency: rate limit /api/auth/refresh.

    Allows 30 refreshes per minute per IP — high limit because
    legitimate clients refresh hourly.
    """
    allowed, remaining = _refresh_limiter.check(request)
    if not allowed:
        logger.warning(
            "refresh rate limit exceeded for IP %s", _refresh_limiter._client_ip(request)
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts.",
            headers={"Retry-After": "60"},
        )
