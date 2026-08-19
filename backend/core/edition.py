"""
Edition seams (berd gap #6) — formal extension points for distributions.

The AGPL repo is the complete free edition. Paid/client-hosted editions are
a DISTRIBUTION, not a divergence: a distributor drops a `distribution.json`
(ATOM_DISTRIBUTION_FILE, or ./distribution.json) that overrides declared
seams without touching the public tree. Mirrors Berd's distribution-seam
pattern.

Seams:
  branding        — product name/title shown in clients
  provider_policy — restrict/expand allowed LLM providers (e.g. a client
                    that mandates one internal gateway)
  agent_catalog   — add private agents/templates beyond the public registry
  gateway_keys    — pre-provisioned atom_sk_* gateway keys (paid edition)
  feature_flags   — pinned experiment overrides (see core/experiments.py)

Nothing here changes behavior for the public edition — no file, no change.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULTS: Dict[str, Any] = {
    "edition": "community",   # community | client-hosted
    "branding": {"name": "Atom", "title": "ATOM Platform"},
    "provider_policy": {"allowed_providers": None},  # None = all
    "agent_catalog": [],
    "gateway_keys": [],
    "feature_flags": {},
}

_cache: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    path = os.getenv("ATOM_DISTRIBUTION_FILE") or "./distribution.json"
    merged = dict(DEFAULTS)
    try:
        with open(path) as f:
            overrides = json.load(f)
        for key, value in overrides.items():
            if key not in DEFAULTS:
                logger.warning(f"distribution.json: unknown seam '{key}' ignored")
                continue
            merged[key] = value
        logger.info(f"Edition seams loaded from {path} (edition={merged.get('edition')})")
    except FileNotFoundError:
        pass  # public edition — no distribution file
    except Exception as e:
        logger.error(f"distribution.json invalid ({e}); community defaults in effect")
    _cache = merged
    return merged


def seam(name: str) -> Any:
    """Read one seam's configured value (community default when unset)."""
    return _load().get(name, DEFAULTS.get(name))


def provider_allowed(provider_id: str) -> bool:
    allowed = (seam("provider_policy") or {}).get("allowed_providers")
    return True if not allowed else provider_id in allowed


def distribution_summary() -> Dict[str, Any]:
    """Ops introspection (hide secret material)."""
    d = dict(_load())
    d["gateway_keys"] = len(d.get("gateway_keys") or [])
    return d
