"""Agent Radio feature flags and tuning knobs (env-driven, fail-safe defaults).

All switches follow the repo convention ``os.getenv("X", default)``. The
master switch ``ATOM_RADIO_ENABLED`` defaults to ON (additive capability);
setting it to ``false`` restores pre-radio behavior everywhere (kill-switch
parity is covered by tests).
"""

import os
from typing import Optional

# Canonical env-var name for the master switch (exposed for flag-sanity checks
# and docs cross-reference; the live value is read via radio_enabled()).
ATOM_RADIO_ENABLED = "ATOM_RADIO_ENABLED"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def radio_enabled() -> bool:
    """Master kill switch for the lateral messaging layer."""
    return _env_bool("ATOM_RADIO_ENABLED", True)


def inbox_cap() -> int:
    """Max pending mentions surfaced to an agent per drain (attention cap)."""
    return int(os.getenv("ATOM_RADIO_INBOX_CAP", "10"))


def backlog_ttl_minutes() -> int:
    """Messages older than this are considered stale (not surfaced)."""
    return int(os.getenv("ATOM_RADIO_BACKLOG_TTL_MIN", "30"))


def team_budget_usd() -> float:
    """Per-thread cumulative message-budget ceiling (cost governance)."""
    return float(os.getenv("ATOM_RADIO_TEAM_BUDGET_USD", "0.20"))


def wait_timeout_seconds() -> int:
    """Bounded agent-initiated block in ``wait_for_mention`` (hard max)."""
    return int(os.getenv("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", "30"))


def breakpoint_gate_enabled() -> bool:
    """Auto-attach threads to fleet runs only for responsibility-breakpoint tasks."""
    return _env_bool("ATOM_RADIO_BREAKPOINT_GATE", True)


def _env_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    return value.strip() if value is not None else None


def thread_override_chain_id(thread_id: str) -> Optional[str]:
    """Reserved for per-thread overrides (metadata_json). Unused today."""
    del thread_id
    return None
