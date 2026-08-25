"""Fleet routing statistics — audit writes, outcome join, calibration status.

2026-08-21 (validation pipeline for the ON-shadow fleet routing rollout):

- ``record_fleet_decision`` — hot-path audit write from the
  ``AtomMetaAgent.execute()`` fleet branch (shadow or enforced). Never raises.
- ``record_fleet_execution_outcome`` — joins the meta-agent execution result
  onto audit rows by ``execution_id`` (called from both finalize points in
  execute()). Only rows with ``success`` populated are calibration-eligible.
- ``fleet_calibration_status`` — per-workload single-arm calibration readout:
  how many fleet-eligible decisions exist, how the *incumbent* (Queen->ReAct)
  performed on them, and whether recruitment machinery is healthy.

Honest asymmetry: in shadow mode the fleet is recruited but NOT auto-executed
(``route_with_governance`` returns a summary only), so audit rows measure the
baseline the fleet path would replace — there is no fleet-arm outcome until
force-enforce (pilot) is on. Certification therefore means "baseline healthy +
recruitment works -> safe to pilot", not "fleet beats incumbent". The
automation module enforces exactly that semantics.

Gap math (``min_turns_per_arm`` / ``min_detectable_gap``) is reused verbatim
from ``core.llm.stage_router`` — same two-proportion machinery as the stage
router's calibration, so the numbers read identically across subsystems.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")

# Minimum outcome-joined rows per workload before a calibration verdict is
# attempted (mirrors stage-router MIN_OUTCOME_ROWS_PER_ARM).
MIN_OUTCOME_ROWS = 30
# Recruitment health floor: below this, never recommend a pilot.
MIN_RECRUIT_SUCCESS_RATE = 0.8
MIN_RECRUIT_ATTEMPTS = 10
# Incumbent success floor for a healthy baseline (recommend-pilot threshold).
BASELINE_SUCCESS_FLOOR = 0.7
# Regressing-baseline trigger (auto-revoke threshold).
REVOKE_SUCCESS_CEILING = 0.5
REVOKE_MIN_ROWS = 20

GLOBAL_WORKLOAD_KEY = "__global__"


def workload_key_for(request: str) -> str:
    """Anonymized workload signature: sha1 of the normalized request, 16 hex."""
    if not request:
        return "unknown"
    normalized = _WS_RE.sub(" ", request.strip().lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def record_fleet_decision(
    *,
    execution_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    request: str = "",
    chain_id: Optional[str] = None,
    specialists_count: int = 0,
    roster: Optional[List[Dict[str, Any]]] = None,
    recruitment_succeeded: Optional[bool] = None,
    enforced: bool = False,
    decision_source: str = "fleet_eligible",
    error: Optional[str] = None,
) -> Optional[str]:
    """Persist one fleet-routing decision (shadow or enforced). Never raises.

    Returns the audit row id (for callers that need to reference it), or None
    on any failure — the hot path must never be blocked by telemetry.
    """
    try:
        import uuid as _uuid

        from core.database import get_db_session
        from core.models import FleetRoutingAudit

        with get_db_session() as db:
            row = FleetRoutingAudit(
                id=str(_uuid.uuid4()),
                execution_id=execution_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                workload_key=workload_key_for(request or ""),
                request_text=(request or "")[:200],
                chain_id=chain_id,
                specialists_count=int(specialists_count or 0),
                roster_json=roster or [],
                recruitment_succeeded=recruitment_succeeded,
                enforced=bool(enforced),
                decision_source=decision_source,
                error=(error or None),
            )
            db.add(row)
            db.commit()
            return row.id
    except Exception as e:
        logger.warning("Fleet routing audit write failed: %s", e)
        return None


def record_fleet_execution_outcome(
    execution_id: str,
    success: bool,
    error_message: Optional[str] = None,
    actual_latency_ms: Optional[float] = None,
    actual_model: Optional[str] = None,
    actual_provider: Optional[str] = None,
) -> None:
    """Join a finalized meta-agent execution onto its fleet audit rows.

    Called from both finalize points in ``AtomMetaAgent.execute()``. Updates
    every audit row with the given ``execution_id`` (in practice one). Rows
    missing (e.g. execution never reached the fleet branch) are a no-op.
    Never raises.
    """
    try:
        from core.database import get_db_session
        from core.models import FleetRoutingAudit

        with get_db_session() as db:
            rows = (
                db.query(FleetRoutingAudit)
                .filter(FleetRoutingAudit.execution_id == execution_id)
                .all()
            )
            for row in rows:
                row.success = bool(success)
                if error_message:
                    row.error = str(error_message)[:400]
                if actual_latency_ms is not None:
                    row.actual_latency_ms = float(actual_latency_ms)
                if actual_model:
                    row.actual_model = actual_model
                if actual_provider:
                    row.actual_provider = actual_provider
            db.commit()

        # P4 contribution credit (AGENT_ORG_POLITICS_PLAN.md): feed bucket-
        # brigade weights into graduation on fleet finalization. Flag-gated;
        # never raises; no-op when no chain/links exist.
        try:
            from core.contribution_credit import record_chain_credit

            record_chain_credit(execution_id)
        except Exception as cc_err:
            logger.debug("contribution credit skipped: %s", cc_err)
    except Exception as e:
        logger.warning("Fleet routing outcome join failed: %s", e)


def _workload_stats(db) -> Dict[str, Dict[str, Any]]:
    """Per-workload calibration stats from outcome-joined fleet audit rows."""
    from core.models import FleetRoutingAudit

    stats: Dict[str, Dict[str, Any]] = {}
    rows = (
        db.query(FleetRoutingAudit)
        .filter(FleetRoutingAudit.success.isnot(None))
        .all()
    )
    for row in rows:
        wk = row.workload_key or "unknown"
        s = stats.setdefault(
            wk,
            {"n": 0, "successes": 0, "recruit_attempts": 0, "recruit_successes": 0},
        )
        s["n"] += 1
        if row.success:
            s["successes"] += 1
        if row.recruitment_succeeded is not None:
            s["recruit_attempts"] += 1
            if row.recruitment_succeeded:
                s["recruit_successes"] += 1

    out: Dict[str, Dict[str, Any]] = {}
    for wk, s in stats.items():
        out[wk] = {
            "n": s["n"],
            "success_rate": round(s["successes"] / s["n"], 3),
            "recruit_attempts": s["recruit_attempts"],
            "recruit_success_rate": (
                round(s["recruit_successes"] / s["recruit_attempts"], 3)
                if s["recruit_attempts"]
                else None
            ),
        }
    return out


def _aggregate_recruitment_health(db) -> Dict[str, Any]:
    """Global recruitment-machinery health across ALL fleet audit rows."""
    from core.models import FleetRoutingAudit

    attempts = 0
    successes = 0
    for row in db.query(FleetRoutingAudit).all():
        if row.recruitment_succeeded is not None:
            attempts += 1
            if row.recruitment_succeeded:
                successes += 1
    return {
        "recruit_attempts": attempts,
        "recruit_success_rate": (round(successes / attempts, 3) if attempts else None),
    }


def fleet_calibration_status(db=None) -> Dict[str, Any]:
    """Operator-facing calibration readout for the fleet router.

    Phase semantics (single-arm, honest):
    - ``off``            — fleet routing disabled entirely (kill switch).
    - ``blocked``        — recruitment machinery unhealthy; never pilot.
    - ``collecting``     — not enough outcome-joined rows yet.
    - ``ready``          — enough rows + healthy baseline + healthy recruitment
                           -> automation may recommend a pilot (force-enforce).
    - ``enforced``       — force-enforce is currently on (env or automation
                           override); calibration then measures the fleet arm.
    """
    try:
        from core.database import get_db_session
        from core.fleet_routing_config import fleet_routing_enabled
        from core.llm.stage_router import min_detectable_gap, min_turns_per_arm

        with get_db_session() as db:
            workloads = _workload_stats(db)
            recruit = _aggregate_recruitment_health(db)

            counts = {"outcome_joined": sum(w["n"] for w in workloads.values())}
            total_rows = 0
            if db:
                from core.models import FleetRoutingAudit

                total_rows = db.query(FleetRoutingAudit).count()
            counts["total"] = total_rows

            sufficiency: Dict[str, Dict[str, Any]] = {}
            for wk, s in workloads.items():
                sufficiency[wk] = {
                    "n": s["n"],
                    "success_rate": s["success_rate"],
                    "min_detectable_gap": round(min_detectable_gap(s["n"]), 3),
                    "turns_needed_for_10pt_gap": min_turns_per_arm(),
                    "calibration_ready": s["n"] >= MIN_OUTCOME_ROWS
                    and s["success_rate"] >= BASELINE_SUCCESS_FLOOR,
                }

            from core.fleet_orchestration.fleet_router_automation import resolved_fleet_enforce

            enforced = resolved_fleet_enforce()

            phase = "off"
            why = "Fleet routing disabled (ATOM_FLEET_ROUTING_ENABLED=false)."
            next_action = "Leave off, or set ATOM_FLEET_ROUTING_ENABLED=true to shadow."
            if fleet_routing_enabled():
                if recruit["recruit_attempts"] >= MIN_RECRUIT_ATTEMPTS and (
                    recruit["recruit_success_rate"] is not None
                    and recruit["recruit_success_rate"] < MIN_RECRUIT_SUCCESS_RATE
                ):
                    phase = "blocked"
                    why = (
                        f"Recruitment machinery unhealthy "
                        f"({recruit['recruit_success_rate']} success over "
                        f"{recruit['recruit_attempts']} attempts) — fix before piloting."
                    )
                    next_action = "Investigate FleetAdmiral recruitment failures."
                elif enforced:
                    phase = "enforced"
                    why = "Force-enforce is on (env or automation override); measuring the fleet arm."
                    next_action = "Monitor fleet-arm success rate; automation revokes automatically on regression."
                elif counts["outcome_joined"] < MIN_OUTCOME_ROWS:
                    phase = "collecting"
                    gap = round(min_detectable_gap(max(counts["outcome_joined"], 1)), 3)
                    why = (
                        f"Collecting shadow data: {counts['outcome_joined']} outcome-joined "
                        f"rows of {MIN_OUTCOME_ROWS} needed (min detectable gap ~{gap})."
                    )
                    next_action = "Keep shadow mode on; calibration needs more fleet-eligible tasks."
                else:
                    ready_wk = [wk for wk, s in sufficiency.items() if s["calibration_ready"]]
                    phase = "ready"
                    why = (
                        f"{len(ready_wk)}/{len(sufficiency)} workload(s) pass the baseline "
                        "bar (healthy incumbent + healthy recruitment)."
                    )
                    next_action = "Approve the automation recommendation to pilot force-enforce."

            return {
                "phase": phase,
                "why": why,
                "next_action": next_action,
                "counts": counts,
                "recruitment": recruit,
                "workloads": sufficiency,
                "enforced": enforced,
                "min_rows_required": MIN_OUTCOME_ROWS,
            }
    except Exception as e:
        logger.warning("Fleet calibration status failed: %s", e)
        return {
            "phase": "error",
            "why": "Status unavailable",
            "next_action": "Check logs",
            "counts": {"outcome_joined": 0, "total": 0},
            "recruitment": {"recruit_attempts": 0, "recruit_success_rate": None},
            "workloads": {},
            "enforced": False,
        }
