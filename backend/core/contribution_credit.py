"""Marginal-contribution credit (AGENT_ORG_POLITICS_PLAN.md Phase 4).

R10: bucket-brigade backward value flow — graduation credit for fleet
specialists reflects their marginal contribution along the delegation chain
rather than uniform presence. Fully deterministic (ChainLink status deltas,
verified-gated); no LLM judging.

Model (see tests/test_contribution_credit_p4.py docstring):
  v ∈ {1.0 completed, 0.5 pending/unknown, 0.0 failed}
  r_i = v_i * γ^(n-1-i)              γ = 0.7
  V_eff = max(v_last, DAMPENED_OUTCOME)   # late failure dampens, not zeros
  w_i = r_i / Σr * V_eff             → Σw == V_eff ("sum ≈ outcome delta")

Graduation mapping is a one-shot chain-level supplement — per-tool records
(oracle-verified at dispatch time) stay authoritative; zero-weight specialists
are skipped so failures are never double-counted.

Flag: ATOM_CONTRIBUTION_CREDIT_ENABLED (default OFF).
Wire-in: fleet_routing_stats.record_fleet_execution_outcome.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GAMMA = 0.7
DAMPENED_OUTCOME = 0.25
STRONG_CREDIT_THRESHOLD = 0.5

_STEP_VALUES = {"completed": 1.0, "failed": 0.0}


def contribution_credit_enabled() -> bool:
    return os.getenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "false").lower() == "true"


def _step_value(status: Optional[str]) -> float:
    return _STEP_VALUES.get((status or "").lower(), 0.5)


def compute_chain_credit(steps: List[Dict[str, Any]]) -> Dict[str, float]:
    """Backward bucket-brigade weights per specialist (Σw == realized outcome).

    ``steps`` are in link_order; each carries ``agent_id`` and ``status``.
    Failed steps earn exactly zero but never poison upstream contributors;
    a failed final step dampens the whole chain to DAMPENED_OUTCOME.
    """
    if not steps:
        return {}
    values = [_step_value(s.get("status")) for s in steps]
    n = len(values)
    raw: List[float] = []
    for i, s in enumerate(steps):
        r = values[i] * (GAMMA ** (n - 1 - i))
        raw.append(max(0.0, r))
    total_raw = sum(raw)
    if total_raw <= 0:
        # Every step failed (or unknown-zero): nobody gets credit.
        return {str(s.get("agent_id")): 0.0 for s in steps if s.get("agent_id")}
    v_eff = max(values[-1], DAMPENED_OUTCOME)
    credits: Dict[str, float] = {}
    for s, r in zip(steps, raw):
        aid = s.get("agent_id")
        if not aid:
            continue
        w = (r / total_raw) * v_eff
        credits[str(aid)] = round(
            credits.get(str(aid), 0.0) + w, 6
        )
    return credits


def apply_credit(db: Any, entries: List[Dict[str, Any]]) -> int:
    """Feed chain credits into CapabilityGraduationService. Returns applied count.

    Mapping: w ≥ 0.5 → verified success; 0 < w < 0.5 → unverified success;
    w == 0 → skipped (failures already recorded at tool time — no poison,
    no double-count). Never raises.
    """
    if not entries:
        return 0
    applied = 0
    try:
        from core.capability_graduation_service import CapabilityGraduationService

        svc = CapabilityGraduationService(db)
        for e in entries:
            try:
                weight = float(e.get("weight", 0.0))
                agent_id = str(e.get("agent_id") or "")
                domain = str(e.get("domain") or "general")
                if not agent_id or weight <= 0.0:
                    continue
                verified = (
                    "verified" if weight >= STRONG_CREDIT_THRESHOLD else "unverified"
                )
                svc.record_usage(agent_id, domain, success=True, verified=verified)
                applied += 1
            except Exception as ee:  # noqa: BLE001 — one bad entry ≠ abort all
                logger.debug(f"apply_credit entry skipped: {ee}")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"apply_credit failed: {e}")
    return applied


def record_chain_credit(execution_id: str, db: Optional[Any] = None) -> bool:
    """execution_id → audit row → chain links → credits → graduation.

    Flag OFF or any missing piece is a silent no-op. Returns True when
    credits were applied. Safe to call from both finalize points.
    """
    if not contribution_credit_enabled():
        return False
    owned = db is None
    try:
        if owned:
            from core.database import get_db_session

            with get_db_session() as session:
                return _record_chain_credit_with_session(session, execution_id)
        return _record_chain_credit_with_session(db, execution_id)
    except Exception as e:  # noqa: BLE001 — supplement must never break finalize
        logger.warning(f"record_chain_credit failed: {e}")
        return False


def _record_chain_credit_with_session(db: Any, execution_id: str) -> bool:
    from core.models import ChainLink, FleetRoutingAudit

    audit = (
        db.query(FleetRoutingAudit)
        .filter(FleetRoutingAudit.execution_id == str(execution_id))
        .first()
    )
    if audit is None or not audit.chain_id:
        return False
    links = (
        db.query(ChainLink)
        .filter(ChainLink.chain_id == audit.chain_id)
        .order_by(ChainLink.link_order.asc())
        .all()
    )
    steps: List[Dict[str, Any]] = []
    for link in links:
        status = (link.status or "").lower()
        if status in ("pending", "in_progress"):
            continue  # run not finalized for this link
        ctx = link.context_json or {}
        steps.append(
            {
                "agent_id": link.child_agent_id,
                "status": status,
                "domain": ctx.get("domain", "general"),
            }
        )
    if not steps:
        return False
    credits = compute_chain_credit(steps)
    domains = {str(s["agent_id"]): s.get("domain", "general") for s in steps}
    entries = [
        {
            "agent_id": aid,
            "weight": w,
            "domain": domains.get(aid, "general"),
        }
        for aid, w in credits.items()
    ]
    applied = apply_credit(db, entries)
    if applied:
        logger.info(
            "contribution_credit: %s specialists credited for exec %s",
            applied,
            execution_id,
        )
    return applied > 0
