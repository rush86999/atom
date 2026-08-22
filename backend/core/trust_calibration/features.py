"""V1 feature extraction for trust calibration (plan §3).

tool_vec = [complexity/4, is_destructive, platform_risk/2]
ctx_vec  = [agent_tier_idx/3]

Complexity resolution mirrors AgentGovernanceService.ACTION_COMPLEXITY
(exact key -> substring max -> default 2) via a lazy import so this module
stays cheap to import in isolation.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

_DESTRUCTIVE_KEYWORDS = (
    "delete", "drop", "purge", "destroy", "terminate",
    "payment", "transfer", "bulk_",
)

_PLATFORM_RISK = {
    "internal": 0, "canvas": 0, "docs": 0, "search": 0,
    "email": 1, "gmail": 1, "slack": 1, "whatsapp": 1, "meta": 1,
    "telegram": 1, "teams": 1, "discord": 1,
    "payment": 2, "stripe": 2, "shell": 2, "infra": 2, "deploy": 2,
}

_TIER_INDEX = {"student": 0.0, "intern": 1.0, "supervised": 2.0, "autonomous": 3.0}


def action_complexity(action_type: str) -> int:
    """Exact-key -> substring-max -> default-2, mirroring governance."""
    if not action_type:
        return 2
    try:
        from core.agent_governance_service import AgentGovernanceService

        table = AgentGovernanceService.ACTION_COMPLEXITY
        low = action_type.lower()
        if low in table:
            return int(table[low])
        matches = [lvl for act, lvl in table.items() if act in low]
        return int(max(matches)) if matches else 2
    except Exception:  # noqa: BLE001 — feature extraction never raises
        low = action_type.lower()
        if any(k in low for k in ("delete", "payment", "transfer")):
            return 4
        return 2


def _is_destructive(action_type: str) -> bool:
    low = (action_type or "").lower()
    return any(k in low for k in _DESTRUCTIVE_KEYWORDS)


def _platform_risk(platform: Optional[str]) -> float:
    if not platform:
        return 1.0
    return float(_PLATFORM_RISK.get(str(platform).lower(), 1.0))


def tool_vector(action_type: str) -> np.ndarray:
    c = min(max(action_complexity(action_type), 1), 4) / 4.0
    d = 1.0 if _is_destructive(action_type) else 0.0
    r = _platform_risk(None) / 2.0  # tool-intrinsic risk: assume mid until
    # a platform-specific call passes one; keeps tool_vec pure w.r.t. action.
    return np.array([c, d, r], dtype=float)


def context_vector(agent_status: Optional[str], platform: Optional[str]) -> np.ndarray:
    tier = _TIER_INDEX.get(
        (agent_status or "").strip().lower(), 0.0
    ) / 3.0
    risk = _platform_risk(platform) / 2.0
    return np.array([tier, risk], dtype=float)
