"""Release-level live-email restriction.

The assignment successor is draft-and-approval only.  The restriction is a
trusted server-side environment gate, evaluated before any provider transport.
It is intentionally independent of assignment approval payloads, model output
and client-supplied transport fields.
"""
from __future__ import annotations

import os
from typing import Any, Dict

DISABLE_ENV = "ATOM_EMAIL_SEND_DISABLED"


def live_email_send_disabled() -> bool:
    return str(os.getenv(DISABLE_ENV, "0")).strip().lower() in (
        "1", "true", "yes", "on")


def disabled_result() -> Dict[str, Any]:
    return {
        "success": False,
        "status": "blocked",
        "provider_state": "not_sent",
        "error": (
            "Live email sending is disabled for this release. "
            "Drafts and approval preparation remain available."),
        "policy": "draft_and_approval_only",
        "transport_attempted": False,
    }
