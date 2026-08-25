"""Agent Radio feature flags and tuning knobs (env-driven, fail-safe defaults).

All switches follow the repo convention ``os.getenv("X", default)``. The
master switch ``ATOM_RADIO_ENABLED`` defaults to ON (additive capability);
setting it to ``false`` restores pre-radio behavior everywhere (kill-switch
parity is covered by tests).
"""

import os
from typing import Optional

from core.runtime_settings import get_bool_setting, get_float_setting, get_int_setting

# Canonical env-var name for the master switch (exposed for flag-sanity checks
# and docs cross-reference; the live value is read via radio_enabled()).
ATOM_RADIO_ENABLED = "ATOM_RADIO_ENABLED"


def _env_bool(name: str, default: bool) -> bool:
    # Raw env parse FIRST (legacy contract incl. uncataloged keys), then
    # runtime_settings DB row (UI admin), then default.
    import os

    raw = os.getenv(name)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return get_bool_setting(name, default)


def radio_enabled() -> bool:
    """Master kill switch for the lateral messaging layer."""
    return _env_bool("ATOM_RADIO_ENABLED", True)


def inbox_cap() -> int:
    """Max pending mentions surfaced to an agent per drain (attention cap)."""
    return get_int_setting("ATOM_RADIO_INBOX_CAP", 10)


def backlog_ttl_minutes() -> int:
    """Messages older than this are considered stale (not surfaced)."""
    return get_int_setting("ATOM_RADIO_BACKLOG_TTL_MIN", 30)


def team_budget_usd() -> float:
    """Per-thread cumulative message-budget ceiling (cost governance)."""
    return get_float_setting("ATOM_RADIO_TEAM_BUDGET_USD", 0.20)


def wait_timeout_seconds() -> int:
    """Bounded agent-initiated block in ``wait_for_mention`` (hard max)."""
    return get_int_setting("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", 30)


def breakpoint_gate_enabled() -> bool:
    """Auto-attach threads to fleet runs only for responsibility-breakpoint tasks."""
    return _env_bool("ATOM_RADIO_BREAKPOINT_GATE", True)


def _env_str(name: str) -> Optional[str]:
    # Raw env read FIRST (legacy contract incl. uncataloged keys), then
    # runtime_settings DB row (UI admin), then None.
    value = os.getenv(name)
    if value is None:
        from core.runtime_settings import get_setting

        value = get_setting(name, "")
        if not isinstance(value, str) or not value:
            return None
    return value.strip()


def thread_override_chain_id(thread_id: str) -> Optional[str]:
    """Reserved for per-thread overrides (metadata_json). Unused today."""
    del thread_id
    return None
