"""
Experiment registry — one place for behavioral feature flags.

Berd-style semantics: each experiment declares a default, a dev default
(auto-on during development), and an env override. This replaces the
scattered `os.getenv(...).lower() in ("1","true",...)` patterns that had
no uniform dev/prod story (UI gap analysis #5 / berd gap #5).

Usage:
    from core.experiments import is_enabled
    if is_enabled("memory_context_assembly"): ...

Adding an experiment: register it below with its defaults. Env override is
always `{ENV_NAME}=true|false` where ENV_NAME is declared per experiment.
"""

import os
from typing import Dict

_EXPERIMENTS: Dict[str, Dict[str, object]] = {
    # ---- Memory unification (docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md) ----
    "memory_context_assembly": {
        "env": "MEMORY_CONTEXT_ASSEMBLY",
        "default": True,       # P0 shipped + live-verified
        "dev": True,
    },
    "memory_conversations_leg": {
        "env": "MEMORY_CONVERSATIONS_LEG",
        "default": True,       # P1.3 first slice shipped
        "dev": True,
    },
    "memory_rerank": {
        "env": "MEMORY_CONTEXT_RERANK",
        "default": True,       # budget-gated internally; no-op without torch
        "dev": True,
    },
    "memory_consolidation": {
        "env": "MEMORY_CONSOLIDATION_ENABLED",
        "default": True,       # P2.1 nightly worker
        "dev": True,
    },
    # ---- IM ----
    "telegram_polling": {
        "env": "TELEGRAM_POLLING_ENABLED",
        "default": False,      # requires TELEGRAM_BOT_TOKEN; opt-in
        "dev": True,
    },
    # ---- Knowledge ----
    "knowledge_vfs": {
        "env": "ATOM_KNOWLEDGE_VFS_ENABLED",
        "default": True,
        "dev": True,
    },
    # ---- Temporal evolution (P0) ----
    "temporal_normalization": {
        "env": "ATOM_TEMPORALITY_ENABLED",
        "default": True,       # P0 shipped — temporal anchors on ingested records
        "dev": True,
    },
}


def is_enabled(name: str) -> bool:
    """Resolve an experiment: explicit env override wins, else the mode
    default (dev vs prod per NODE_ENV/ENVIRONMENT). Unknown names are
    off-by-default with a logged hint to register them."""
    import logging

    exp = _EXPERIMENTS.get(name)
    if exp is None:
        logging.getLogger(__name__).debug(
            f"experiment '{name}' is not registered — returning False")
        return False

    raw = os.getenv(str(exp["env"]))
    if raw is not None and raw != "":
        return raw.strip().lower() in ("1", "true", "yes", "on")

    # Explicit production anywhere beats dev defaults; otherwise default dev.
    node_env = os.getenv("NODE_ENV", "")
    env_env = os.getenv("ENVIRONMENT", "")
    is_prod = "production" in (node_env + env_env)
    is_dev = (not is_prod) and (
        node_env == "development" or env_env in ("", "development")
    )
    return bool(exp["dev"] if is_dev else exp["default"])


def registry_summary() -> Dict[str, Dict[str, object]]:
    """Introspection for settings UI / ops: every experiment, its env var,
    and its CURRENT resolution."""
    return {
        name: {
            "env": exp["env"],
            "default": exp["default"],
            "dev": exp["dev"],
            "enabled": is_enabled(name),
        }
        for name, exp in _EXPERIMENTS.items()
    }
