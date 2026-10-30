"""Presence-only preflight for Microsoft OAuth client configuration.

Never read back or log secret values. The runtime needs the same approved
client id/secret that issued the stored refresh token; a missing value is an
administrator configuration repair, not revoked user consent.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

MICROSOFT_CLIENT_KEYS = (
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
)
_PLACEHOLDER_MARKERS = (
    "your-",
    "change-me",
    "<redacted>",
    "stripped",
    "placeholder",
)


def microsoft_client_config_state() -> Dict[str, Any]:
    """Return presence/placeholder state without exposing values."""
    missing = []
    placeholders = []
    for key in MICROSOFT_CLIENT_KEYS:
        value = str(os.getenv(key, "") or "").strip()
        if not value:
            missing.append(key)
            continue
        lowered = value.lower()
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            placeholders.append(key)
    return {
        "configured": not missing and not placeholders,
        "missing": missing,
        "placeholders": placeholders,
        "checked_keys": list(MICROSOFT_CLIENT_KEYS),
        "source": "process_environment_after_dotenv",
    }


def run_oauth_config_preflight(logger: logging.Logger | None = None) -> Dict[str, Any]:
    """Log a sanitized startup warning when Microsoft OAuth is incomplete."""
    log = logger or logging.getLogger(__name__)
    state = microsoft_client_config_state()
    if state["configured"]:
        log.info("Microsoft OAuth client configuration present")
    else:
        incomplete = list(state["missing"]) + list(state["placeholders"])
        log.warning(
            "Microsoft OAuth client configuration incomplete (%s). "
            "Administrator configuration repair is required; this is not a "
            "revoked user grant.",
            ", ".join(incomplete),
        )
    return state
