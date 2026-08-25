"""Knowledge VFS feature flag (W1, P2c).

Mirrors agent_radio/radio_config.py. The master switch
``ATOM_KNOWLEDGE_VFS_ENABLED`` defaults to ON (additive read-only actions);
set ``false`` to restore the legacy ILIKE-only documents.search (kill-switch).
"""
from core.runtime_settings import get_bool_setting


def _env_bool(name: str, default: bool) -> bool:
    # Raw env parse FIRST (legacy contract incl. uncataloged keys), then
    # runtime_settings DB row (UI admin), then default.
    import os

    raw = os.getenv(name)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return get_bool_setting(name, default)


def knowledge_vfs_enabled() -> bool:
    """Master switch for the VFS documents.* actions. Default True (additive)."""
    return _env_bool("ATOM_KNOWLEDGE_VFS_ENABLED", True)
