"""Knowledge VFS feature flag (W1, P2c).

Mirrors agent_radio/radio_config.py. The master switch
``ATOM_KNOWLEDGE_VFS_ENABLED`` defaults to ON (additive read-only actions);
set ``false`` to restore the legacy ILIKE-only documents.search (kill-switch).
"""
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def knowledge_vfs_enabled() -> bool:
    """Master switch for the VFS documents.* actions. Default True (additive)."""
    return _env_bool("ATOM_KNOWLEDGE_VFS_ENABLED", True)
