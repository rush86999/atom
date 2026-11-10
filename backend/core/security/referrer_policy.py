"""Referrer-Policy normalization shared by the security-header middleware.

W3C Referrer Policy allows a response to select its own policy:

    https://w3c.github.io/webappsec-referrer-policy/

A generic security-header middleware applies an application-wide default. When
an individual response has already chosen an explicitly *stricter* policy (for
example the OIDC sensitive callback/exchange endpoints emit ``no-referrer`` so
the authorization code cannot leak through the ``Referer`` header), the
middleware must not overwrite that choice with a weaker default.

Only policies that are unambiguously stricter than the application default are
preserved. Unsafe, weak, unknown or absent values are replaced with the
default so this helper can never *weaken* a response.
"""
from __future__ import annotations

from typing import MutableMapping, Optional

DEFAULT_REFERRER_POLICY = "strict-origin-when-cross-origin"

#: Policies that are strictly stronger than :data:`DEFAULT_REFERRER_POLICY`.
#: ``no-referrer`` sends nothing; ``same-origin`` and ``strict-origin`` never
#: leak the path/query cross-origin.
STRICTER_REFERRER_POLICIES = frozenset({
    "no-referrer",
    "same-origin",
    "strict-origin",
})

#: Every policy token defined by W3C Referrer Policy (used only to find the
#: effective member of a comma-separated header; not all are preserved).
KNOWN_REFERRER_POLICIES = frozenset({
    "no-referrer",
    "no-referrer-when-downgrade",
    "same-origin",
    "origin",
    "strict-origin",
    "origin-when-cross-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
})

_HEADER = "Referrer-Policy"


def _effective_policy(value: str) -> Optional[str]:
    """Return the policy a user agent would apply for a header value.

    Per the delivery rules in W3C Referrer Policy, a comma-separated list is
    resolved to its last *valid* member. Invalid members are ignored by user
    agents, so they are ignored here too.
    """
    policies = [part.strip().lower() for part in value.split(",")]
    valid = [policy for policy in policies if policy in KNOWN_REFERRER_POLICIES]
    return valid[-1] if valid else None


def normalize_referrer_policy(value: Optional[str]) -> str:
    """Return ``value`` when explicitly stricter, else the default policy."""
    if not value:
        return DEFAULT_REFERRER_POLICY
    effective = _effective_policy(value)
    if effective in STRICTER_REFERRER_POLICIES:
        return effective
    return DEFAULT_REFERRER_POLICY


def apply_referrer_policy(headers: MutableMapping[str, str]) -> None:
    """Apply the security default without weakening an explicit stricter policy.

    ``headers`` is a mutable response-header mapping (Starlette's
    ``MutableHeaders`` is case-insensitive; a plain dict is tolerated too).
    """
    existing = headers.get(_HEADER)
    if existing is None:
        existing = headers.get(_HEADER.lower())
    headers[_HEADER] = normalize_referrer_policy(existing)
