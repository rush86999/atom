"""
Agent Action Audit — read API for the per-decision audit trail.

Serves the rows written by core/agent_action_audit.py (event types
``agent_action`` and ``llm_call`` in saas_audit_logs) so the person an agent
acted for — and supervisors in the same workspace — can review every decision
the agent made: which tools it invoked with which arguments, which LLM calls
it made with which recorded model label, and how each run ended.

Read scope (see core/audit_access.py — ONE general predicate for all four
endpoints):
- ordinary member: their OWN audited rows only; unbound legacy rows stay
  unassigned;
- supervisor (TEAM_LEAD+): every user's rows in the CURRENT workspace, never
  a global all-users query;
- a real workspace is exact; personal/null keeps the documented
  Personal-Edition default compatibility.

Endpoints (prefix /api/audit):
- GET /events                 — filterable event feed
- GET /executions             — list audited runs (from execution_start events)
- GET /executions/{id}        — full replayable timeline for one run
- GET /summary                — aggregate stats for dashboard headers

Evidence honesty: audit ``llm_call`` rows record the router-requested label,
not a verified served model. Responses expose that as a label with an explicit
``provenance`` marker, and only surface a served model when the existing
execution provenance / reasoning-step columns actually recorded one. Costs come
from recorded ``TokenUsage`` rows only (labelled estimate/known-free/unpriced),
never an invoice claim.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from core.audit_access import (
    AUDIT_EVENT_TYPES,
    CORRECTION_CHANNELS,
    CORRECTION_TARGET_ID_RE,
    AuditAccessDenied,
    audit_row_condition,
    authoritative_actor,
    correction_href,
    exact_execution_condition,
    execution_identifier_valid,
    execution_workspace_visible,
    parse_metadata,
    read_scope_payload,
    resolve_audit_scope,
    row_execution_id,
    scoped_event_query,
)
from core.auth import get_current_user
from core.database import get_db
from core.models import (
    AgentExecution,
    AgentReasoningStep,
    AuditLog,
    TokenUsage,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])

# Agent_action sub-actions that bracket a run.
EXECUTION_START = "execution_start"
EXECUTION_COMPLETE = "execution_complete"

# Explicit, user-visible bounds on the evidence payload.
MAX_VERIFICATION_EVIDENCE_ROWS = 20
MAX_EVIDENCE_TEXT_CHARS = 500


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _redact_strings(value: Any) -> Any:
    """Reuse the existing key-shaped-secret redactor on arbitrary JSON-ish data."""
    if isinstance(value, str):
        try:
            from core.experience_marketplace.sanitizer import redact_secrets

            return redact_secrets(value)
        except Exception:  # noqa: BLE001 — redaction must not break the read
            return value
    if isinstance(value, dict):
        return {key: _redact_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_strings(item) for item in value]
    return value


def _safe_metadata(raw: Any) -> Dict[str, Any]:
    """Parse event metadata and apply the repo's existing credential redaction.

    Read-side only: the stored row is never rewritten. Credential-shaped keys
    are dropped via ``blueprint_sanitizer.strip_credentials`` and key-shaped
    secrets embedded in free text are replaced by ``<secret>``.
    """
    meta = parse_metadata(raw)
    try:
        from core.blueprint_sanitizer import strip_credentials

        meta = strip_credentials(meta)
    except Exception:  # noqa: BLE001
        pass
    return _redact_strings(meta)


def _redact_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _redact_strings(value)


def _model_identity(event_type: str, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Honest model identity for one audit event.

    ``llm_call`` rows carry the router tier/alias the caller requested, not a
    provider-echoed served model. Never present the response text as proof of
    which model ran.
    """
    if event_type != "llm_call":
        return None
    label = meta.get("model")
    provider = meta.get("provider")
    return {
        "recorded_label": str(label) if label else None,
        "label_kind": "router_tier_or_alias" if label else "unknown",
        "served_model": None,
        "provider": str(provider) if provider else None,
        "provenance": "recorded_label_only" if label else "unknown",
        "note": (
            "Recorded router-requested label; the audit row does not prove "
            "which model actually served the call."
            if label
            else "No model label was recorded for this call."
        ),
    }


def _correction_targets(source: Any) -> List[Dict[str, Any]]:
    """Validated repair-channel targets already present in recorded metadata.

    No inference, no domain regex: a target exists only when the run itself
    recorded one of these allowlisted identifiers. Anything URL-shaped or
    containing a path separator is rejected, so a stored value can never be
    replayed as an arbitrary link.
    """
    if not isinstance(source, dict):
        return []
    candidates = (
        ("goal_run_id", "activity"),
        ("learning_thread_id", "learning"),
        ("assignment_agent_id", "assignment"),
        ("autodev_candidate_id", "autodev"),
    )
    targets: List[Dict[str, Any]] = []
    seen = set()
    for key, channel in candidates:
        value = source.get(key)
        if not isinstance(value, str) or not CORRECTION_TARGET_ID_RE.match(value):
            continue
        key_id = (channel, value)
        if key_id in seen:
            continue
        seen.add(key_id)
        targets.append({
            "channel": channel,
            "label": CORRECTION_CHANNELS.get(channel, channel),
            "target_id": value,
            "href": correction_href(channel, value),
        })
    return targets


def _correction_receipt(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inline receipt for an existing correction_requested row."""
    if not meta.get("correction_request"):
        return None
    return {
        "feedback_id": meta.get("feedback_id"),
        "status": meta.get("status") or "requested",
        "applied": False if meta.get("applied") is None else bool(meta.get("applied")),
        "verified": False if meta.get("verified") is None else bool(meta.get("verified")),
        "channel": meta.get("channel"),
        "target_id": meta.get("channel_target_id"),
        "reason": meta.get("reason"),
    }


# Decision-authority fields that writers already persist on HITL/audit rows.
# When present, show the recorded actor/time/role; never infer or invent one.
_AUTHORITY_KEYS = (
    "reviewed_by", "reviewed_at", "required_role", "user_feedback",
    "approval_status", "decision", "decision_reason", "reason",
)


def _recorded_authority(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    recorded = {
        key: meta.get(key)
        for key in _AUTHORITY_KEYS
        if meta.get(key) not in (None, "")
    }
    return recorded or None


def _serialize_event(row: AuditLog) -> Dict[str, Any]:
    meta = _safe_metadata(row.metadata_json)
    return {
        "id": row.id,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        "event_type": row.event_type,
        "action": row.action,
        "description": _redact_text(row.description),
        "agent_id": meta.get("agent_id") or row.resource,
        "agent_execution_id": meta.get("agent_execution_id"),
        "user_id": row.user_id,
        "workspace_id": row.workspace_id,
        "success": row.success,
        "error_message": _redact_text(row.error_message),
        "metadata": meta,
        "model_identity": _model_identity(row.event_type, meta),
        "authority": _recorded_authority(meta),
        "correction_targets": _correction_targets(meta),
        "correction": _correction_receipt(meta),
    }


def _exact_execution_rows(db: Session, scope: Dict[str, Any], execution_id: str) -> List[AuditLog]:
    """Rows for ONE execution, exact-matched and re-checked after the query."""
    if not execution_identifier_valid(execution_id):
        return []
    rows = (
        scoped_event_query(db, scope)
        .filter(exact_execution_condition(execution_id))
        .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
        .all()
    )
    return [row for row in rows if row_execution_id(row) == execution_id]


def _chunks(values: List[str], size: int = 50) -> Iterable[List[str]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _usage_for_executions(
    db: Session, execution_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """One grouped query per page — never a per-execution (N+1) lookup."""
    ids = [value for value in dict.fromkeys(execution_ids) if value]
    if not ids:
        return {}
    usage: Dict[str, Dict[str, Any]] = {}
    try:
        for chunk in _chunks(ids, 100):
            rows = (
                db.query(
                    TokenUsage.execution_id,
                    func.count(TokenUsage.id),
                    func.coalesce(func.sum(TokenUsage.cost_usd), 0.0),
                    func.sum(
                        case((TokenUsage.cost_usd.is_(None), 1), else_=0)
                    ),
                    func.coalesce(func.sum(TokenUsage.total_tokens), 0),
                )
                .filter(TokenUsage.execution_id.in_(chunk))
                .group_by(TokenUsage.execution_id)
                .all()
            )
            for execution_id, row_count, priced_sum, unpriced_count, total_tokens in rows:
                count = int(row_count or 0)
                unpriced = int(unpriced_count or 0)
                priced = max(count - unpriced, 0)
                amount = float(priced_sum or 0.0)
                if count == 0:
                    entry = _usage_entry(
                        "unavailable", None, "no_recorded_usage",
                        "No provider usage rows were recorded for this run.",
                        count, priced, unpriced, int(total_tokens or 0),
                    )
                elif unpriced and not priced:
                    entry = _usage_entry(
                        "unavailable", None, "recorded_usage_unpriced",
                        "Recorded usage exists but has no recorded price.",
                        count, priced, unpriced, int(total_tokens or 0),
                    )
                elif unpriced:
                    entry = _usage_entry(
                        "partial", round(amount, 6), "recorded_usage_estimate",
                        "Some recorded usage rows are unpriced; this subtotal is incomplete.",
                        count, priced, unpriced, int(total_tokens or 0),
                    )
                elif amount == 0.0:
                    entry = _usage_entry(
                        "known_free", 0.0, "recorded_zero_cost",
                        "Recorded usage priced at zero; this is not an invoice.",
                        count, priced, unpriced, int(total_tokens or 0),
                    )
                else:
                    entry = _usage_entry(
                        "recorded_estimate", round(amount, 6),
                        "recorded_usage_estimate",
                        "Recorded provider-usage estimate; not invoice price.",
                        count, priced, unpriced, int(total_tokens or 0),
                    )
                if execution_id:
                    usage[str(execution_id)] = entry
    except Exception as exc:  # noqa: BLE001 — audit read must not fail on usage
        logger.warning(
            "Audit usage lookup unavailable (error_class=%s)",
            type(exc).__name__,
        )
        return {
            execution_id: _usage_entry(
                "unavailable", None, "usage_lookup_unavailable",
                "Usage/cost could not be read; no cost is claimed.",
                0, 0, 0, 0,
            )
            for execution_id in ids
        }
    for execution_id in ids:
        usage.setdefault(
            execution_id,
            _usage_entry(
                "unavailable", None, "no_recorded_usage",
                "No provider usage rows were recorded for this run.",
                0, 0, 0, 0,
            ),
        )
    return usage


def _usage_entry(
    status: str,
    amount: Optional[float],
    basis: str,
    note: str,
    rows: int,
    priced_rows: int,
    unpriced_rows: int,
    total_tokens: int,
) -> Dict[str, Any]:
    return {
        "status": status,
        "cost_usd": amount,
        "currency": "USD",
        "basis": basis,
        "rows": rows,
        "priced_rows": priced_rows,
        "unpriced_rows": unpriced_rows,
        "total_tokens": total_tokens,
        "note": note,
    }


def _verification_summary(db: Session, execution_id: str) -> Dict[str, Any]:
    """Aggregate the existing tri-state oracle columns for one execution."""
    try:
        rows = (
            db.query(
                AgentReasoningStep.step_number,
                AgentReasoningStep.verified,
                AgentReasoningStep.verification_evidence,
            )
            .filter(AgentReasoningStep.execution_id == execution_id)
            .order_by(AgentReasoningStep.step_number.asc())
            .all()
        )
    except Exception as exc:  # noqa: BLE001 — unavailable is explicit
        logger.warning(
            "Audit verification lookup unavailable (error_class=%s)",
            type(exc).__name__,
        )
        return {
            "status": "unavailable",
            "basis": "recorded_reasoning_step_tri_state",
            "counts": {},
            "evidence": [],
            "note": "Reasoning-step verification could not be read.",
        }

    counts = {"verified": 0, "unverified": 0, "failed_verification": 0}
    evidence: List[Dict[str, Any]] = []
    for step_number, verified, verification_evidence in rows:
        state = str(verified or "unverified")
        if state not in counts:
            state = "unverified"
        counts[state] += 1
        if verification_evidence and len(evidence) < MAX_VERIFICATION_EVIDENCE_ROWS:
            evidence.append({
                "step_number": step_number,
                "status": state,
                "evidence": _redact_text(
                    str(verification_evidence)[:MAX_EVIDENCE_TEXT_CHARS]
                ),
            })

    if not rows:
        status = "not_recorded"
    elif counts["failed_verification"]:
        status = "failed_verification"
    elif counts["verified"] and counts["unverified"]:
        status = "partially_verified"
    elif counts["verified"]:
        status = "verified"
    else:
        status = "unverified"
    return {
        "status": status,
        "basis": "recorded_reasoning_step_tri_state",
        "counts": counts,
        "evidence": evidence,
        "note": (
            "Step-level oracle state as recorded. This is not a guarantee that "
            "the overall task outcome is correct."
        ),
    }


def _execution_model_identity(
    execution: Optional[AgentExecution],
    events: List[Dict[str, Any]],
    db: Session,
    execution_id: str,
) -> Dict[str, Any]:
    """Recorded label vs recorded server provenance, kept separate."""
    metadata = {}
    if execution is not None and isinstance(execution.metadata_json, dict):
        metadata = execution.metadata_json
    provenance = metadata.get("model_provenance")
    recorded_provenance = None
    if isinstance(provenance, dict):
        recorded_provenance = {
            key: provenance.get(key)
            for key in (
                "provider", "model", "requested_provider", "requested_model",
                "resolved_model", "source",
            )
            if provenance.get(key) not in (None, "")
        }

    requested_models: List[str] = []
    resolved_models: List[str] = []
    try:
        model_rows = (
            db.query(
                AgentReasoningStep.requested_model,
                AgentReasoningStep.resolved_model,
            )
            .filter(AgentReasoningStep.execution_id == execution_id)
            .all()
        )
        for requested, resolved in model_rows:
            if requested and str(requested) not in requested_models:
                requested_models.append(str(requested))
            if resolved and str(resolved) not in resolved_models:
                resolved_models.append(str(resolved))
    except Exception:  # noqa: BLE001 — observational only
        pass

    labels = [
        str(event["model_identity"]["recorded_label"])
        for event in events
        if (event.get("model_identity") or {}).get("recorded_label")
    ]
    return {
        "recorded_llm_call_labels": list(dict.fromkeys(labels)),
        "execution_provenance": _redact_strings(recorded_provenance),
        "requested_models": requested_models,
        "resolved_models": resolved_models,
        "note": (
            "LLM-call labels are router-requested labels. Requested/resolved "
            "models come from the execution's recorded provenance only when "
            "present; unknown stays unknown."
        ),
    }


def _execution_workspace_allowed(scope: Dict[str, Any], execution: Optional[AgentExecution]) -> bool:
    return execution is None or execution_workspace_visible(scope, execution)


def _read_scope_or_raise(db: Session, current_user: User) -> Dict[str, Any]:
    try:
        actor = authoritative_actor(db, current_user)
    except AuditAccessDenied as denial:
        raise _http_denial(denial) from denial
    return resolve_audit_scope(actor)


def _http_denial(denial: AuditAccessDenied) -> HTTPException:
    return HTTPException(
        status_code=denial.status_code,
        detail={"code": denial.code, "message": denial.message, **denial.details},
    )


def _execution_summary_payload(
    execution: AgentExecution,
) -> Dict[str, Any]:
    return {
        "id": execution.id,
        "agent_id": execution.agent_id,
        "status": execution.status,
        "input_summary": _redact_text(execution.input_summary),
        "output_summary": _redact_text(execution.output_summary),
        "error_message": _redact_text(execution.error_message),
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "triggered_by": execution.triggered_by,
    }


def _outcome(status: Optional[str], verification_status: str) -> Dict[str, Any]:
    return {
        "status": status,
        "basis": "recorded_execution_status",
        "verification": verification_status,
        "note": (
            "Recorded run status. Audit replay does not independently re-verify "
            "the business outcome."
        ),
    }


# --------------------------------------------------------------------------- #
# Event feed
# --------------------------------------------------------------------------- #
@router.get("/events")
def list_events(
    agent_id: Optional[str] = Query(None, description="Filter by agent id"),
    execution_id: Optional[str] = Query(None, description="Filter by execution id"),
    event_type: Optional[str] = Query(None, description="agent_action | llm_call"),
    success: Optional[bool] = Query(None, description="Filter by outcome"),
    start: Optional[datetime] = Query(None, description="ISO timestamp lower bound"),
    end: Optional[datetime] = Query(None, description="ISO timestamp upper bound"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scope = _read_scope_or_raise(db, current_user)
    query = scoped_event_query(db, scope)

    if agent_id:
        query = query.filter(AuditLog.resource == agent_id)
    if execution_id:
        if not execution_identifier_valid(execution_id):
            raise HTTPException(status_code=422, detail="Invalid execution id")
        query = query.filter(exact_execution_condition(execution_id))
    if event_type:
        if event_type not in AUDIT_EVENT_TYPES:
            raise HTTPException(status_code=422, detail="Unsupported event type")
        query = query.filter(AuditLog.event_type == event_type)
    if success is not None:
        query = query.filter(AuditLog.success == success)
    if start:
        query = query.filter(AuditLog.timestamp >= start)
    if end:
        query = query.filter(AuditLog.timestamp <= end)

    total = query.count()
    rows = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    if execution_id:
        rows = [row for row in rows if row_execution_id(row) == execution_id]
    return {
        "items": [_serialize_event(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "read_scope": read_scope_payload(scope),
    }


# --------------------------------------------------------------------------- #
# Execution list + timeline
# --------------------------------------------------------------------------- #
@router.get("/executions")
def list_executions(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audited runs, newest first.

    Runs are anchored on their ``execution_start`` event; status comes from
    the matching ``execution_complete`` event when present (RUNNING implies
    the run crashed or the audit close-out failed — itself a signal). The
    run-row lookup is batched for the whole page, not per execution.
    """
    scope = _read_scope_or_raise(db, current_user)
    query = (
        scoped_event_query(db, scope)
        .filter(AuditLog.event_type == "agent_action")
        .filter(AuditLog.action == EXECUTION_START)
    )
    if agent_id:
        query = query.filter(AuditLog.resource == agent_id)

    total = query.count()
    starts = (
        query.order_by(AuditLog.timestamp.desc(), AuditLog.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    start_events = [_serialize_event(row) for row in starts]
    page_ids = [
        event["agent_execution_id"]
        for event in start_events
        if isinstance(event.get("agent_execution_id"), str)
        and execution_identifier_valid(event["agent_execution_id"])
    ]
    grouped: Dict[str, List[AuditLog]] = {}
    if page_ids:
        for chunk in _chunks(list(dict.fromkeys(page_ids)), 50):
            rows = (
                scoped_event_query(db, scope)
                .filter(or_(*[exact_execution_condition(value) for value in chunk]))
                .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
                .all()
            )
            for row in rows:
                row_id = row_execution_id(row)
                if row_id in chunk:
                    grouped.setdefault(row_id, []).append(row)

    usage = _usage_for_executions(db, page_ids)
    items: List[Dict[str, Any]] = []
    for event in start_events:
        execution_id = event.get("agent_execution_id")
        item = {
            "execution_id": execution_id,
            "agent_id": event.get("agent_id"),
            "started_at": event.get("timestamp"),
            "status": "running",
            "completed_at": None,
            "task_input": (event.get("metadata") or {}).get("task_input"),
            "tool_calls": 0,
            "llm_calls": 0,
            "failed_events": 0,
            "correction_requests": 0,
            "usage": usage.get(execution_id) if execution_id else _usage_entry(
                "unavailable", None, "no_execution_identity",
                "No execution id was recorded for this run.",
                0, 0, 0, 0,
            ),
            "verification": "unknown",
        }
        if execution_id:
            for row in grouped.get(execution_id, []):
                action = row.action or ""
                if row.event_type == "llm_call":
                    item["llm_calls"] += 1
                elif action.startswith("tool:"):
                    item["tool_calls"] += 1
                if action == "correction_requested":
                    item["correction_requests"] += 1
                if row.success is False:
                    item["failed_events"] += 1
                if action == EXECUTION_COMPLETE:
                    meta = _safe_metadata(row.metadata_json)
                    item["status"] = meta.get("status") or (
                        "success" if row.success else "failed")
                    item["completed_at"] = (
                        row.timestamp.isoformat() if row.timestamp else None)
        item["outcome"] = _outcome(item["status"], "see_timeline")
        items.append(item)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "read_scope": read_scope_payload(scope),
    }


@router.get("/executions/{execution_id}")
def get_execution_timeline(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full replayable decision chain for one agent execution.

    404 for an unknown id, an id outside the caller's workspace, or (for a
    member) an execution not provably owned by the caller. A supervisor in
    the execution's workspace keeps the legacy no-events fallback; a member
    without ownership evidence never receives it.
    """
    scope = _read_scope_or_raise(db, current_user)
    if not execution_identifier_valid(execution_id):
        raise HTTPException(
            status_code=404,
            detail=f"No audit trail found for execution {execution_id}",
        )

    exec_row = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == execution_id)
        .first()
    )
    if not _execution_workspace_allowed(scope, exec_row):
        raise HTTPException(
            status_code=404,
            detail="Audit execution not found in your authorized scope",
        )

    rows = _exact_execution_rows(db, scope, execution_id)
    if not rows:
        # Fall back to the persisted execution record only when it is bound to
        # the caller's workspace and (for a non-supervisor) ownership could be
        # proven elsewhere. Members without owner evidence get 404.
        if exec_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No audit trail found for execution {execution_id}",
            )
        if not scope["supervisor"]:
            raise HTTPException(
                status_code=404,
                detail="Audit execution not found in your authorized scope",
            )
        return {
            "execution_id": execution_id,
            "found_events": False,
            "execution": {
                **_execution_summary_payload(exec_row),
                "outcome": _outcome(exec_row.status, "not_recorded"),
                "model_identity": _execution_model_identity(
                    exec_row, [], db, execution_id),
                "verification": {
                    "status": "not_recorded",
                    "basis": "recorded_reasoning_step_tri_state",
                    "counts": {},
                    "evidence": [],
                    "note": "No per-event audit trail exists for this run.",
                },
                "usage": _usage_for_executions(db, [execution_id]).get(
                    execution_id,
                    _usage_entry(
                        "unavailable", None, "no_recorded_usage",
                        "No provider usage rows were recorded for this run.",
                        0, 0, 0, 0,
                    ),
                ),
                "correction_targets": _correction_targets(
                    exec_row.metadata_json),
            },
            "events": [],
            "counts": {"tool_calls": 0, "llm_calls": 0, "failed_events": 0},
            "read_scope": read_scope_payload(scope),
        }

    events = [_serialize_event(row) for row in rows]
    counts = {
        "tool_calls": sum(1 for e in events if (e["action"] or "").startswith("tool:")),
        "llm_calls": sum(1 for e in events if e["event_type"] == "llm_call"),
        "failed_events": sum(1 for e in events if e["success"] is False),
    }
    start_event = next(
        (e for e in events if e["action"] == EXECUTION_START), None)
    complete_event = next(
        (e for e in events if e["action"] == EXECUTION_COMPLETE), None)

    execution_summary: Dict[str, Any] = {"id": execution_id}
    if exec_row is not None:
        execution_summary.update(_execution_summary_payload(exec_row))
    if start_event:
        execution_summary.setdefault("agent_id", start_event["agent_id"])
        execution_summary["task_input"] = (
            start_event.get("metadata") or {}).get("task_input")
    if complete_event:
        execution_summary["status"] = (
            complete_event.get("metadata") or {}).get(
                "status", execution_summary.get("status"))

    verification = _verification_summary(db, execution_id)
    usage = _usage_for_executions(db, [execution_id]).get(
        execution_id,
        _usage_entry(
            "unavailable", None, "no_recorded_usage",
            "No provider usage rows were recorded for this run.",
            0, 0, 0, 0,
        ),
    )
    execution_summary["outcome"] = _outcome(
        execution_summary.get("status"), verification["status"])
    execution_summary["correction_requests"] = sum(
        1 for event in events if event["action"] == "correction_requested")
    execution_summary["verification"] = verification
    execution_summary["usage"] = usage
    execution_summary["model_identity"] = _execution_model_identity(
        exec_row, events, db, execution_id)

    execution_targets = _correction_targets(
        exec_row.metadata_json if exec_row is not None else {})
    if not execution_targets:
        for event in events:
            for target in event.get("correction_targets") or []:
                if target not in execution_targets:
                    execution_targets.append(target)
    execution_summary["correction_targets"] = execution_targets

    return {
        "execution_id": execution_id,
        "found_events": True,
        "execution": execution_summary,
        "events": events,
        "counts": counts,
        "read_scope": read_scope_payload(scope),
        "evidence_limits": {
            "signed": False,
            "hash_chain": False,
            "note": (
                "Rows are returned as stored for this authorized read. No "
                "signature or hash chain exists, so this is not tamper-evident "
                "and is not a completeness certificate."
            ),
        },
    }


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #
@router.get("/summary")
def audit_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate stats over the recent window, for dashboard headers.

    The same single read scope applies: a member sees only their own stats and
    a supervisor sees the current workspace — never a global all-users rollup.
    """
    scope = _read_scope_or_raise(db, current_user)
    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    base = scoped_event_query(db, scope).filter(
        AuditLog.timestamp >= window_start)

    total = base.count()
    if total == 0:
        return {
            "days": days,
            "total_events": 0,
            "by_event_type": {},
            "by_action": {},
            "failures": 0,
            "success_rate": None,
            "distinct_agents": 0,
            "executions_tracked": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_scope": read_scope_payload(scope),
        }

    by_type: Dict[str, int] = {
        str(k): int(v)
        for k, v in db.query(AuditLog.event_type, func.count(AuditLog.id))
        .filter(audit_row_condition(scope))
        .filter(AuditLog.timestamp >= window_start)
        .group_by(AuditLog.event_type)
        .all()
    }
    by_action: Dict[str, int] = {
        str(k): int(v)
        for k, v in db.query(AuditLog.action, func.count(AuditLog.id))
        .filter(audit_row_condition(scope))
        .filter(AuditLog.timestamp >= window_start)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(20)
        .all()
    }
    failures = base.filter(AuditLog.success.is_(False)).count()
    distinct_agents = (
        db.query(func.count(func.distinct(AuditLog.resource)))
        .filter(audit_row_condition(scope))
        .filter(AuditLog.timestamp >= window_start)
        .scalar()
    ) or 0
    executions_tracked = (
        scoped_event_query(db, scope)
        .filter(AuditLog.action == EXECUTION_START)
        .filter(AuditLog.timestamp >= window_start)
        .count()
    )

    return {
        "days": days,
        "total_events": total,
        "by_event_type": by_type,
        "by_action": by_action,
        "failures": failures,
        "success_rate": round((total - failures) / total * 100, 1) if total else None,
        "distinct_agents": distinct_agents,
        "executions_tracked": executions_tracked,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_scope": read_scope_payload(scope),
    }
