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

from sqlalchemy import exists, update
from sqlalchemy.orm import Session

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


def _merge_error(existing: Optional[str], message: str) -> str:
    existing = str(existing or "").strip()
    return f"{existing}; {message}" if existing else message


def _norm_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _scope_material_complete(row: Any) -> bool:
    """Explicit scope and outcome identity, not legacy/unknown data."""
    return (
        bool(getattr(row, "tenant_id", None))
        and bool(getattr(row, "workspace_id", None))
        and bool(getattr(row, "agent_id", None))
        and str(getattr(row, "decision_source", "") or "")
        != "scope_unverified"
    )


def _outcome_eligible(row: Any) -> bool:
    return _scope_material_complete(row) and getattr(row, "success", None) is not None


def _recruitment_eligible(row: Any) -> bool:
    return (
        _scope_material_complete(row)
        and getattr(row, "recruitment_succeeded", None) is not None
    )


def _outcome_matches(
    row: Any, *, success: bool, error_message: Optional[str],
    actual_model: Optional[str], actual_provider: Optional[str],
) -> bool:
    if bool(getattr(row, "success", None)) != bool(success):
        return False
    if error_message is not None and _norm_text(
            getattr(row, "error", None)) != _norm_text(error_message):
        return False
    if actual_model is not None and _norm_text(
            getattr(row, "actual_model", None)) != _norm_text(actual_model):
        return False
    if actual_provider is not None and _norm_text(
            getattr(row, "actual_provider", None)) != _norm_text(
                actual_provider):
        return False
    return True


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

    The authenticated ``AgentExecution`` row is the scope authority. Caller
    scope is never allowed to become default authority: when it conflicts with
    the execution row the execution scope is recorded and the conflict is made
    explicit; when the execution row is missing/incomplete the row is marked
    ``scope_unverified`` and is not outcome/calibration eligible.

    Returns the audit row id (for callers that need to reference it), or None
    on any failure — the hot path must never be blocked by telemetry.
    """
    try:
        import uuid as _uuid

        from core.database import get_db_session
        from core.models import AgentExecution, FleetRoutingAudit

        with get_db_session() as db:
            execution = None
            if execution_id:
                execution = (
                    db.query(AgentExecution)
                    .filter(AgentExecution.id == str(execution_id))
                    .first()
                )

            scope_conflict = False
            if execution is not None:
                auth_tenant = execution.tenant_id
                auth_workspace = execution.workspace_id
                auth_agent = execution.agent_id
                if tenant_id is not None and str(tenant_id) != str(
                        auth_tenant or ""):
                    scope_conflict = True
                if workspace_id is not None and str(workspace_id) != str(
                        auth_workspace or ""):
                    scope_conflict = True
                if (
                    agent_id is not None
                    and auth_agent is not None
                    and str(agent_id) != str(auth_agent)
                ):
                    scope_conflict = True
                tenant_id = auth_tenant
                workspace_id = auth_workspace
                agent_id = auth_agent
                if not auth_tenant or not auth_workspace or not auth_agent:
                    decision_source = "scope_unverified"
                    error = _merge_error(
                        error, "authenticated execution scope is incomplete")
                elif scope_conflict:
                    decision_source = "scope_conflict"
                    error = _merge_error(
                        error,
                        "caller scope conflicted with authenticated execution; "
                        "authoritative execution scope recorded",
                    )
            else:
                # No authenticated execution to bind to. Preserve explicit
                # caller scope for diagnostics, but never substitute a caller
                # agent or manufacture default authority.
                agent_id = None
                decision_source = "scope_unverified"
                error = _merge_error(
                    error, "authenticated execution scope unavailable")

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
    *,
    audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Join a finalized execution onto its exact fleet audit row.

    The authenticated ``AgentExecution`` row is the complete scope authority
    (tenant/workspace/agent). The join is a single guarded DML over the exact
    audit id, execution identity, complete scope, pending outcome and an
    ``EXISTS`` check of the authoritative execution row. A peer outcome or a
    moved execution matches zero rows; the actual winner is then compared by
    exact outcome material, never by the boolean alone. Never raises.
    """
    result: Dict[str, Any] = {
        "status": "not_found",
        "execution_id": str(execution_id or ""),
        "audit_id": audit_id,
        "applied": [],
        "already_applied": [],
        "conflicts": [],
    }
    try:
        from core.database import get_db_session
        from core.models import AgentExecution, FleetRoutingAudit

        with get_db_session() as db:
            execution = None
            if execution_id:
                execution = (
                    db.query(AgentExecution)
                    .filter(AgentExecution.id == str(execution_id))
                    .first()
                )
            if execution is None:
                result["status"] = "scope_unavailable"
                return result
            auth_tenant = _norm_text(execution.tenant_id)
            auth_workspace = _norm_text(execution.workspace_id)
            auth_agent = _norm_text(execution.agent_id)
            if not auth_tenant or not auth_workspace or not auth_agent:
                result["status"] = "scope_unavailable"
                return result
            if tenant_id is not None and str(tenant_id) != auth_tenant:
                result["status"] = "scope_conflict"
                return result
            if workspace_id is not None and str(workspace_id) != auth_workspace:
                result["status"] = "scope_conflict"
                return result
            if agent_id is not None and str(agent_id) != auth_agent:
                result["status"] = "scope_conflict"
                return result

            if not isinstance(db, Session):
                # Legacy unit-test/mock seam. Production uses the guarded DML
                # below; this path keeps the same exact-material semantics.
                query = db.query(FleetRoutingAudit)
                if audit_id:
                    rows = query.filter(
                        FleetRoutingAudit.id == str(audit_id)).all()
                else:
                    rows = query.filter(
                        FleetRoutingAudit.execution_id == str(
                            execution_id)).all()
                for row in rows:
                    if (
                        str(getattr(row, "execution_id", "") or "")
                        != str(execution_id)
                        or _norm_text(getattr(row, "tenant_id", None))
                        != auth_tenant
                        or _norm_text(getattr(row, "workspace_id", None))
                        != auth_workspace
                        or _norm_text(getattr(row, "agent_id", None))
                        != auth_agent
                    ):
                        result["conflicts"].append(row.id)
                        continue
                    if not _scope_material_complete(row):
                        result["conflicts"].append(row.id)
                        continue
                    if row.success is not None:
                        if _outcome_matches(
                            row, success=success,
                            error_message=error_message,
                            actual_model=actual_model,
                            actual_provider=actual_provider,
                        ):
                            result["already_applied"].append(row.id)
                        else:
                            result["conflicts"].append(row.id)
                        continue
                    row.success = bool(success)
                    if error_message is not None:
                        row.error = _norm_text(error_message)
                    if actual_latency_ms is not None:
                        row.actual_latency_ms = float(actual_latency_ms)
                    if actual_model is not None:
                        row.actual_model = _norm_text(actual_model)
                    if actual_provider is not None:
                        row.actual_provider = _norm_text(actual_provider)
                    result["applied"].append(row.id)
                db.commit()
            else:
                statement = (
                    update(FleetRoutingAudit)
                    .where(
                        FleetRoutingAudit.execution_id == str(execution_id),
                        FleetRoutingAudit.tenant_id == auth_tenant,
                        FleetRoutingAudit.workspace_id == auth_workspace,
                        FleetRoutingAudit.agent_id == auth_agent,
                        FleetRoutingAudit.success.is_(None),
                        FleetRoutingAudit.decision_source
                        != "scope_unverified",
                        exists().where(
                            AgentExecution.id == str(execution_id),
                            AgentExecution.tenant_id == auth_tenant,
                            AgentExecution.workspace_id == auth_workspace,
                            AgentExecution.agent_id == auth_agent,
                        ),
                    )
                )
                if audit_id:
                    statement = statement.where(
                        FleetRoutingAudit.id == str(audit_id))
                values: Dict[str, Any] = {"success": bool(success)}
                if error_message is not None:
                    values["error"] = _norm_text(error_message)
                if actual_latency_ms is not None:
                    values["actual_latency_ms"] = float(actual_latency_ms)
                if actual_model is not None:
                    values["actual_model"] = _norm_text(actual_model)
                if actual_provider is not None:
                    values["actual_provider"] = _norm_text(actual_provider)
                updated = db.execute(statement.where(
                    FleetRoutingAudit.success.is_(None)).values(**values))
                db.commit()
                if updated.rowcount == 1:
                    result["applied"].append(audit_id or str(execution_id))
                else:
                    db.rollback()
                    with get_db_session() as fresh:
                        now_execution = (
                            fresh.query(AgentExecution)
                            .filter(AgentExecution.id == str(execution_id))
                            .populate_existing()
                            .first()
                        )
                        now_tenant = _norm_text(
                            getattr(now_execution, "tenant_id", None))
                        now_workspace = _norm_text(
                            getattr(now_execution, "workspace_id", None))
                        now_agent = _norm_text(
                            getattr(now_execution, "agent_id", None))
                        if (
                            now_tenant != auth_tenant
                            or now_workspace != auth_workspace
                            or now_agent != auth_agent
                        ):
                            result["status"] = "scope_conflict"
                            return result
                        query = fresh.query(FleetRoutingAudit)
                        if audit_id:
                            now_row = query.filter(
                                FleetRoutingAudit.id == str(audit_id)
                            ).populate_existing().first()
                        else:
                            now_row = query.filter(
                                FleetRoutingAudit.execution_id == str(
                                    execution_id)
                            ).populate_existing().first()
                        if now_row is None:
                            result["status"] = "not_found"
                            return result
                        if now_row.success is not None and _outcome_matches(
                            now_row, success=success,
                            error_message=error_message,
                            actual_model=actual_model,
                            actual_provider=actual_provider,
                        ):
                            result["already_applied"].append(now_row.id)
                        else:
                            result["conflicts"].append(now_row.id)

            if result["applied"]:
                result["status"] = "applied"
            elif result["already_applied"] and not result["conflicts"]:
                result["status"] = "already_applied"
            elif result["conflicts"]:
                result["status"] = "conflict"
            else:
                result["status"] = "not_found"

        if result["status"] in ("applied", "already_applied"):
            try:
                from core.contribution_credit import record_chain_credit

                record_chain_credit(execution_id)
            except Exception as cc_err:
                logger.debug("contribution credit skipped: %s", cc_err)
        return result
    except Exception as e:
        logger.warning("Fleet routing outcome join failed: %s", e)
        result["status"] = "error"
        return result


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
        if not _outcome_eligible(row):
            continue
        wk = row.workload_key or "unknown"
        s = stats.setdefault(
            wk,
            {"n": 0, "successes": 0, "recruit_attempts": 0,
             "recruit_successes": 0, "enforced_n": 0, "shadow_n": 0},
        )
        s["n"] += 1
        if row.success:
            s["successes"] += 1
        if row.enforced:
            s["enforced_n"] += 1
        else:
            s["shadow_n"] += 1
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
            "enforced_n": s["enforced_n"],
            "shadow_n": s["shadow_n"],
        }
    return out


def _aggregate_recruitment_health(db) -> Dict[str, Any]:
    """Global recruitment-machinery health across ALL fleet audit rows."""
    from core.models import FleetRoutingAudit

    attempts = 0
    successes = 0
    for row in db.query(FleetRoutingAudit).all():
        if not _recruitment_eligible(row):
            continue
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
