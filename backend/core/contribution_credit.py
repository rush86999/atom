"""Marginal-contribution credit (AGENT_ORG_POLITICS_PLAN.md Phase 4).

R10: bucket-brigade backward value flow — graduation credit for fleet
specialists reflects their marginal contribution along the delegation chain
rather than uniform presence. This module keeps the deterministic chain math
(ChainLink status deltas) but no longer treats status, a contribution weight,
completion text, a roster domain, or a model-authored result as verification.

Authority chain for a verified fleet outcome:

``FleetRoutingAudit`` (exact id + execution + authenticated scope)
    -> exact ``DelegationChain``/``ChainLink``
    -> server-bound child ``AgentExecution`` (stored on the link by
       ``FleetAdmiral`` before dispatch)
    -> succeeded ``TaskOperationRecord`` claim whose durable ``result_json``
       was written by the real oracle after an independent postcondition read.

Contribution weights remain ranking/analytics signals. They can choose what to
show first; they cannot manufacture ``verified=True``. The capability name is
the exact namespaced operation identity (the claimed action), never the roster
domain, so a verified canvas write cannot graduate a broad "finance" label.

Consumption is idempotent through the existing ``TaskOperationRecord`` table:
one receipt row per source operation (or legacy link) and the graduation
counter update share the same transaction. Replays see the receipt and add no
new usage. If an outcome committed but the worker was lost before credit, the
missing receipt is still recoverable.

Model (see tests/test_contribution_credit_p4.py docstring):
  v ∈ {1.0 completed, 0.5 pending/unknown, 0.0 failed}
  r_i = v_i * γ^(n-1-i)              γ = 0.7
  V_eff = max(v_last, DAMPENED_OUTCOME)   # late failure dampens, not zeros
  w_i = r_i / Σr * V_eff             → Σw == V_eff ("sum ≈ outcome delta")

Flag: ATOM_CONTRIBUTION_CREDIT_ENABLED (default OFF).
Wire-in: fleet_routing_stats.record_fleet_execution_outcome.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

GAMMA = 0.7
DAMPENED_OUTCOME = 0.25
STRONG_CREDIT_THRESHOLD = 0.5

_STEP_VALUES = {"completed": 1.0, "failed": 0.0}

#: Namespace used by this consumer inside the existing operation table. It is
#: deliberately NOT ``generic:agent%`` so a credit receipt is never mistaken
#: for a tool dispatch claim (or vice versa).
CREDIT_RECEIPT_TYPE = "fleet:capability_credit:v1"
CREDIT_RECEIPT_VERSION = 1

_SCOPE_UNVERIFIED = {"", "scope_unverified", "scope_conflict"}


def contribution_credit_enabled() -> bool:
    # Env wins > runtime_settings DB row (UI admin) > default.
    from core.runtime_settings import get_bool_setting

    return get_bool_setting("ATOM_CONTRIBUTION_CREDIT_ENABLED", False)


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


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_dict(value: Any) -> Dict[str, Any]:
    """Read a nullable JSON/raw-JSON column without inventing authority."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _parse_time(value: Any) -> Optional[datetime]:
    """Normalize server timestamps; SQLite's naive DateTime values are UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        # A date alone cannot prove a post-epoch observation instant.
        if not text or ("T" not in text and " " not in text):
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    else:
        return None
    try:
        return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc))
    except (TypeError, ValueError):
        return None


def _caller_owns_session(db: Any) -> bool:
    """True when a borrowed session may already contain caller-owned work.

    Checking only ``new``/``dirty``/``deleted`` misses edits the caller has
    already FLUSHED: those are no longer pending objects, but they still live
    in the session's uncommitted transaction and must not be committed or
    rolled back by this supplement. Any active transaction is therefore
    caller-owned unless this function created it.
    """
    try:
        if (getattr(db, "new", None)
                or getattr(db, "dirty", None)
                or getattr(db, "deleted", None)):
            return True
        in_transaction = getattr(db, "in_transaction", None)
        if callable(in_transaction):
            return bool(in_transaction())
        get_transaction = getattr(db, "get_transaction", None)
        if callable(get_transaction):
            return get_transaction() is not None
        # Unknown session shape: assume the caller owns an open unit of work.
        return True
    except Exception:  # noqa: BLE001 - unknown shape -> treat as borrowed
        return True


def _independent_writer(db: Any):
    """Open an owned Session on the same engine when that is genuinely safe.

    A Session bound to a Connection, or an engine pool that hands the very same
    DBAPI connection to every checkout (StaticPool/SingletonThreadPool), cannot
    provide an independent transaction. In that case return ``None`` and the
    caller refuses explicitly instead of touching the caller's unit of work.
    """
    try:
        from sqlalchemy.engine import Engine
        from sqlalchemy.orm import sessionmaker

        bind = db.get_bind()
        if not isinstance(bind, Engine):
            return None
        if type(bind.pool).__name__ in (
                "StaticPool", "SingletonThreadPool"):
            return None
        return sessionmaker(bind=bind)()
    except Exception:  # noqa: BLE001 - no independent writer = explicit refusal
        return None


def _resolve_fleet_outcome(
    db: Any,
    execution_id: str,
    *,
    audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Resolve one exact, authenticated fleet outcome for credit.

    Caller-supplied scope is an assertion, never authority: it must equal the
    audit/execution scope. Missing, foreign, ambiguous, shadow, recruitment
    only, or unresolved rows are refused rather than guessed from ``.first()``.
    """
    from core.models import AgentExecution, DelegationChain, FleetRoutingAudit

    query = db.query(FleetRoutingAudit)
    if audit_id:
        rows = query.filter(
            FleetRoutingAudit.id == str(audit_id)).limit(2).all()
    else:
        rows = query.filter(
            FleetRoutingAudit.execution_id == str(execution_id)
        ).limit(2).all()
    if not rows:
        return None, "missing_audit"
    if len(rows) != 1:
        return None, "ambiguous_audit"
    audit = rows[0]

    exact_execution = _text(audit.execution_id)
    if not exact_execution or exact_execution != _text(execution_id):
        return None, "foreign_execution"

    auth_tenant = _text(audit.tenant_id)
    auth_workspace = _text(audit.workspace_id)
    auth_agent = _text(audit.agent_id)
    if not auth_tenant or not auth_workspace or not auth_agent:
        return None, "incomplete_scope"
    if _text(audit.decision_source) in _SCOPE_UNVERIFIED:
        return None, "unverified_scope"
    if audit.success is not True:
        return None, "unresolved_outcome"
    # A shadow decision measures the incumbent baseline, not fleet work.
    if not bool(audit.enforced):
        return None, "shadow_outcome"

    for supplied, authoritative, label in (
        (tenant_id, auth_tenant, "tenant"),
        (workspace_id, auth_workspace, "workspace"),
        (agent_id, auth_agent, "agent"),
    ):
        if supplied is not None and _text(supplied) != authoritative:
            return None, f"{label}_scope_conflict"

    execution_rows = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == exact_execution)
        .limit(2)
        .all()
    )
    if len(execution_rows) != 1:
        return None, "missing_execution"
    execution = execution_rows[0]
    if (
        _text(execution.tenant_id) != auth_tenant
        or _text(execution.workspace_id) != auth_workspace
        or _text(execution.agent_id) != auth_agent
    ):
        return None, "execution_scope_conflict"

    chain_id = _text(audit.chain_id)
    if not chain_id:
        return None, "missing_chain"
    chain_rows = (
        db.query(DelegationChain)
        .filter(DelegationChain.id == chain_id)
        .limit(2)
        .all()
    )
    if len(chain_rows) != 1:
        return None, "missing_chain"
    chain = chain_rows[0]
    if _text(chain.tenant_id) != auth_tenant:
        return None, "chain_scope_conflict"
    chain_workspace = _text(_as_dict(chain.metadata_json).get("workspace_id"))
    if chain_workspace and chain_workspace != auth_workspace:
        return None, "chain_scope_conflict"

    return {
        "audit": audit,
        "audit_id": _text(audit.id),
        "execution_id": exact_execution,
        "chain": chain,
        "chain_id": chain_id,
        "tenant_id": auth_tenant,
        "workspace_id": auth_workspace,
        "agent_id": auth_agent,
    }, "ok"


def _verified_operation(
    row: Any, outcome: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return exact verified capability material from a stored claim receipt.

    Only a succeeded generic-agent operation whose durable receipt was written
    after an independent oracle readback qualifies. A raw result envelope, a
    ``verified`` boolean on the link, or a roster domain is never consulted.
    """
    operation_type = _text(getattr(row, "operation_type", None))
    prefix = "generic:agent:"
    if not operation_type.startswith(prefix):
        return None
    action = operation_type[len(prefix):].strip()
    if not action or action == "fleet.child":
        return None

    receipt = _as_dict(getattr(row, "result_json", None))
    if not receipt:
        return None
    if receipt.get("oracle_verified") is not True:
        return None
    if receipt.get("success") is not True:
        return None
    if _text(receipt.get("status")).lower() != "success":
        return None
    if _text(receipt.get("operation_id")) != _text(row.operation_id):
        return None
    if _text(receipt.get("action")) != action:
        return None

    receipt_workspace = _text(receipt.get("workspace_id"))
    receipt_tenant = _text(receipt.get("tenant_id"))
    if receipt_workspace and receipt_workspace != outcome["workspace_id"]:
        return None
    if receipt_tenant and receipt_tenant != outcome["tenant_id"]:
        return None

    source_time = getattr(row, "created_at", None)
    clock_fields = ("verification_receipt_version", "dispatch_recorded_at",
                    "verification_recorded_at")
    if any(name in receipt for name in clock_fields):
        version = receipt.get("verification_receipt_version")
        if type(version) is not int or version != 1:
            return None
        dispatch_time = _parse_time(receipt.get("dispatch_recorded_at"))
        verification_time = _parse_time(receipt.get("verification_recorded_at"))
        if (dispatch_time is None or verification_time is None
                or verification_time < dispatch_time):
            return None
        source_time = dispatch_time

    return {
        "capability": action,
        "action": action,
        "source_record_id": _text(row.id),
        "source_created_at": source_time,
    }


def _child_execution_for_link(
    db: Any, link: Any, outcome: Dict[str, Any],
) -> Optional[Any]:
    """Resolve the exact server-bound child execution stored on a link."""
    from core.models import AgentExecution

    result = _as_dict(getattr(link, "result_json", None))
    result_status = _text(result.get("status")).lower()
    if result_status and result_status not in (
            "completed", "success", "succeeded"):
        return None
    child_execution_id = _text(
        result.get("execution_id") or result.get("child_execution_id"))
    if not child_execution_id:
        nested = _as_dict(result.get("result"))
        child_execution_id = _text(
            nested.get("execution_id") or nested.get("child_execution_id"))
    if not child_execution_id:
        return None

    bound_agent = _text(result.get("agent_id"))
    if bound_agent and bound_agent != _text(link.child_agent_id):
        return None

    rows = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == child_execution_id)
        .limit(2)
        .all()
    )
    if len(rows) != 1:
        return None
    child = rows[0]
    if (
        _text(child.agent_id) != _text(link.child_agent_id)
        or _text(child.tenant_id) != outcome["tenant_id"]
        or _text(child.workspace_id) != outcome["workspace_id"]
    ):
        return None
    return child


def _pre_revocation(
    db: Any, agent_id: str, capability: str, source_created_at: Any,
    *,
    expected_scope=None,
) -> Tuple[bool, bool, Any]:
    """Return ``(pre_revocation, found, raw_configuration)`` for one entry.

    True when this source outcome predates (or cannot prove post-revocation).
    A late credit for work performed before an active revocation must remain
    visible but cannot become one of the NEW successes that re-enters INTERN.
    Unknown source time is treated as pre-revocation, never as fresh proof.

    The same raw configuration blob is returned so the caller can bind its
    eligibility decision into the counter CAS. Reading the physical value (not
    an ORM entity) keeps SQL NULL vs JSON ``null`` distinct and avoids a stale
    identity-map view of a just-committed peer revocation.
    """
    from core.capability_graduation_service import CapabilityGraduationService

    found, raw = CapabilityGraduationService(db).observed_configuration(
        agent_id, expected_scope=expected_scope)
    if not found:
        return False, False, None
    config = _as_dict(raw)
    revocations = _as_dict(config.get("autonomy_revocations"))
    marker = _as_dict(revocations.get(capability))
    stats = _as_dict(_as_dict(config.get("capability_stats")).get(capability))
    has_epoch = (bool(marker) or "epoch_started_at" in stats
                 or "epoch_baseline_verified_success" in stats)
    if not has_epoch:
        return False, True, raw
    marker_at = _parse_time(marker.get("at")) if marker else None
    epoch_at = _parse_time(stats.get("epoch_started_at")) or (
        marker_at if "epoch_started_at" not in stats else None)
    source_at = _parse_time(source_created_at)
    if epoch_at is None or source_at is None or (marker and marker_at is None):
        return True, True, raw
    try:
        cutoff = max(epoch_at, marker_at) if marker_at else epoch_at
        return source_at < cutoff, True, raw
    except (TypeError, ValueError):
        return True, True, raw


def _collect_credit_entries(
    db: Any, outcome: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build credit entries only from exact scoped evidence."""
    from core.models import ChainLink, TaskOperationRecord

    chain_id = outcome["chain_id"]
    links = (
        db.query(ChainLink)
        .filter(ChainLink.chain_id == chain_id)
        .order_by(ChainLink.link_order.asc())
        .all()
    )

    steps: List[Dict[str, Any]] = []
    completed_links: List[Any] = []
    for link in links:
        status = _text(getattr(link, "status", None)).lower()
        if status in ("pending", "in_progress"):
            continue
        ctx = _as_dict(getattr(link, "context_json", None))
        agent_id = _text(link.child_agent_id)
        steps.append({
            "agent_id": agent_id,
            "status": status,
            "domain": _text(ctx.get("domain")) or "general",
        })
        if status == "completed" and agent_id:
            completed_links.append(link)

    if not steps:
        return []
    credits = compute_chain_credit(steps)
    per_agent_count: Dict[str, int] = {}
    for link in completed_links:
        aid = _text(link.child_agent_id)
        per_agent_count[aid] = per_agent_count.get(aid, 0) + 1

    entries: List[Dict[str, Any]] = []
    for link in completed_links:
        agent_id = _text(link.child_agent_id)
        weight = credits.get(agent_id, 0.0) / max(
            per_agent_count.get(agent_id, 1), 1)
        if not agent_id or weight <= 0.0:
            continue
        ctx = _as_dict(getattr(link, "context_json", None))
        domain = _text(ctx.get("domain")) or "general"

        child = _child_execution_for_link(db, link, outcome)
        if child is None:
            result = _as_dict(getattr(link, "result_json", None))
            if result:
                # A link that names an unreadable/foreign child is contradictory.
                # Never downgrade that into a generic domain success.
                logger.warning(
                    "contribution_credit: refusing contradictory child "
                    "binding for link %s", getattr(link, "id", "?"))
                continue
            # Legacy completed synthetic link: visible as unverified usage, but
            # it can never earn verified capability success.
            entries.append({
                "agent_id": agent_id,
                "capability": domain,
                "weight": weight,
                "verified": False,
                "link_id": _text(getattr(link, "id", "")),
                "child_execution_id": "",
                "task_digest": _text(
                    _as_dict(getattr(link, "metadata_json", None)).get(
                        "task_digest")),
            })
            continue

        child_execution_id = _text(getattr(child, "id", ""))
        operation_rows = (
            db.query(TaskOperationRecord)
            .filter(
                TaskOperationRecord.workspace_id == outcome["workspace_id"],
                TaskOperationRecord.run_id == child_execution_id,
            )
            .all()
        )
        generic_rows = [
            row for row in operation_rows
            if _text(getattr(row, "operation_type", None)).startswith(
                "generic:agent:")
        ]
        # A contradictory durable row cannot become a generic unverified win.
        if any(_text(getattr(row, "tenant_id", None)) != outcome["tenant_id"]
               for row in generic_rows):
            continue
        if not generic_rows:
            # No tool receipt at all: keep the completed work visible without
            # claiming that the roster domain was verified.
            entries.append({
                "agent_id": agent_id,
                "capability": domain,
                "weight": weight,
                "verified": False,
                "link_id": _text(getattr(link, "id", "")),
                "child_execution_id": child_execution_id,
                "task_digest": _text(
                    _as_dict(getattr(link, "metadata_json", None)).get(
                        "task_digest")),
            })
            continue

        candidate_entries: List[Dict[str, Any]] = []
        for row in generic_rows:
            if _text(getattr(row, "status", None)) != "succeeded":
                continue
            verified = _verified_operation(row, outcome)
            operation_type = _text(getattr(row, "operation_type", None))
            action = operation_type.split("generic:agent:", 1)[1].strip()
            if verified is not None:
                candidate_entries.append({
                    "agent_id": agent_id,
                    "capability": verified["capability"],
                    "weight": weight,
                    "verified": True,
                    "link_id": _text(getattr(link, "id", "")),
                    "child_execution_id": child_execution_id,
                    "task_digest": _text(
                        _as_dict(getattr(link, "metadata_json", None)).get(
                            "task_digest")),
                    "source_record_id": verified["source_record_id"],
                    "source_created_at": verified["source_created_at"],
                    "action": verified["action"],
                })
            elif action:
                candidate_entries.append({
                    "agent_id": agent_id,
                    # Exact operation identity still visible, but unverified.
                    "capability": action,
                    "weight": weight,
                    "verified": False,
                    "link_id": _text(getattr(link, "id", "")),
                    "child_execution_id": child_execution_id,
                    "task_digest": _text(
                        _as_dict(getattr(link, "metadata_json", None)).get(
                            "task_digest")),
                    "source_record_id": _text(getattr(row, "id", "")),
                    "source_created_at": getattr(row, "created_at", None),
                    "action": action,
                })
        if not candidate_entries:
            entries.append({
                "agent_id": agent_id,
                "capability": domain,
                "weight": weight,
                "verified": False,
                "link_id": _text(getattr(link, "id", "")),
                "child_execution_id": child_execution_id,
                "task_digest": _text(
                    _as_dict(getattr(link, "metadata_json", None)).get(
                        "task_digest")),
            })
            continue
        # Each exact operation contributes once; split the link weight so the
        # ranking signal is still bounded by the realized chain outcome.
        share = weight / len(candidate_entries)
        for entry in candidate_entries:
            entry["weight"] = share
            entries.append(entry)
    return entries


def _credit_receipt_identity(
    entry: Dict[str, Any], outcome: Dict[str, Any],
) -> Tuple[str, str, str]:
    """Return (run_id, idempotency_key, payload_sha256) for one receipt."""
    source = _text(entry.get("source_record_id"))
    link_id = _text(entry.get("link_id"))
    capability = _text(entry.get("capability"))
    source_identity = (
        f"operation:{source}" if source else f"link:{link_id}")
    run_id = (
        _text(entry.get("child_execution_id"))
        or _text(entry.get("link_id"))
        or outcome["execution_id"]
    )
    key = f"fleet-credit:v1:{source_identity}:{capability}"
    payload = {
        "version": CREDIT_RECEIPT_VERSION,
        "audit_id": outcome["audit_id"],
        "execution_id": outcome["execution_id"],
        "chain_id": outcome["chain_id"],
        "tenant_id": outcome["tenant_id"],
        "workspace_id": outcome["workspace_id"],
        "agent_id": _text(entry.get("agent_id")),
        "capability": capability,
        "action": _text(entry.get("action")) or capability,
        "link_id": link_id,
        "child_execution_id": _text(entry.get("child_execution_id")),
        "source_record_id": source,
        "task_digest": _text(entry.get("task_digest")),
        "verified": bool(entry.get("verified")),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return run_id, key, hashlib.sha256(raw.encode()).hexdigest()


def _existing_receipt(
    db: Any, workspace_id: str, run_id: str, key: str,
) -> Optional[Any]:
    from core.models import TaskOperationRecord

    return (
        db.query(TaskOperationRecord)
        .filter(
            TaskOperationRecord.workspace_id == workspace_id,
            TaskOperationRecord.run_id == run_id,
            TaskOperationRecord.idempotency_key == key,
        )
        .first()
    )


def _consume_entries(
    db: Any, entries: List[Dict[str, Any]], outcome: Dict[str, Any],
) -> int:
    """Apply each eligible outcome once, receipt + counter in one transaction."""
    if not entries:
        return 0

    from sqlalchemy.exc import IntegrityError

    from core.capability_graduation_service import CapabilityGraduationService
    from core.models import AgentRegistry, TaskOperationRecord

    svc = CapabilityGraduationService(db)
    applied = 0
    for entry in entries:
        agent_id = _text(entry.get("agent_id"))
        capability = _text(entry.get("capability"))
        if not agent_id or not capability:
            continue
        try:
            # Column query: do not preload a stale entity into the identity map
            # before record_usage takes its serialized read/modify/write.
            target = (
                db.query(AgentRegistry.id, AgentRegistry.tenant_id,
                         AgentRegistry.workspace_id)
                .filter(AgentRegistry.id == agent_id)
                .first()
            )
        except Exception:  # noqa: BLE001 - unreadable target is not a receipt
            continue
        if target is None:
            continue
        # Preserve Personal aliases at admission, but bind the exact raw values
        # in the counter DML: a concurrent scope move must match zero rows.
        expected_scope = {"tenant_id": target.tenant_id,
                          "workspace_id": target.workspace_id}
        def admitted_scope(raw, accepted):
            return _text(raw) == accepted or (
                accepted == "default" and _text(raw) in ("", "default"))
        if not all(admitted_scope(raw, outcome[name])
                   for name, raw in expected_scope.items()):
            continue

        run_id, key, payload_hash = _credit_receipt_identity(entry, outcome)
        parent = _existing_receipt(
            db, outcome["workspace_id"], run_id, key)
        if parent is not None:
            if (
                _text(getattr(parent, "payload_sha256", None)) != payload_hash
                or _text(getattr(parent, "status", None)) != "succeeded"
            ):
                logger.warning(
                    "contribution_credit: receipt conflict for %s/%s",
                    run_id, key)
            continue

        verified = bool(entry.get("verified"))
        pre_revoked, config_found, config_snapshot = _pre_revocation(
            db, agent_id, capability, entry.get("source_created_at"),
            expected_scope=expected_scope)
        if not config_found:
            # The target disappeared between admission and eligibility. No
            # counter and no receipt may be written for it.
            continue
        if verified and pre_revoked:
            # Visible legacy pre-revocation work may not become a NEW success.
            verified = False

        receipt = TaskOperationRecord(
            id=str(uuid.uuid4()),
            workspace_id=outcome["workspace_id"],
            tenant_id=outcome["tenant_id"],
            run_id=run_id,
            idempotency_key=key,
            payload_sha256=payload_hash,
            operation_id=f"fleet-credit:{uuid.uuid4()}",
            operation_type=CREDIT_RECEIPT_TYPE,
            status="claimed",
        )
        try:
            # The savepoint makes the receipt insert/conditional counter update
            # atomic per entry; the final commit publishes all of them. A peer
            # contender that wins the unique key makes this flush fail before
            # any counter is touched.
            with db.begin_nested():
                db.add(receipt)
                db.flush()
                applied_usage = svc.record_usage(
                    agent_id,
                    capability,
                    success=True,
                    verified=("verified" if verified else "unverified"),
                    commit=False,
                    expected_scope=expected_scope,
                    # Bind the exact raw configuration used for the
                    # pre-revocation eligibility decision. If a peer commits a
                    # revocation/regression after that read, the counter UPDATE
                    # matches zero rows and this entry's receipt rolls back; a
                    # later recovery pass re-reads and downgrades old work.
                    expected_configuration=config_snapshot,
                )
                if applied_usage is False:
                    # The counter CAS could not be published against the
                    # observed configuration (peer revocation/regression
                    # changed the eligibility snapshot). Roll this entry's
                    # savepoint back: no receipt may exist without its counter
                    # update, and the published receipt may never claim more
                    # verification than was actually credited. A later
                    # recovery pass can still apply the missing credit.
                    raise RuntimeError("capability counter CAS not applied")
                receipt.status = "succeeded"
                receipt.result_json = {
                    "version": CREDIT_RECEIPT_VERSION,
                    "audit_id": outcome["audit_id"],
                    "execution_id": outcome["execution_id"],
                    "chain_id": outcome["chain_id"],
                    "child_execution_id": _text(
                        entry.get("child_execution_id")),
                    "source_record_id": _text(
                        entry.get("source_record_id")),
                    "agent_id": agent_id,
                    "capability": capability,
                    "action": _text(entry.get("action")) or capability,
                    "weight": float(entry.get("weight") or 0.0),
                    "verified": verified,
                    "applied_at": datetime.utcnow().isoformat(),
                }
            applied += 1
        except IntegrityError:
            # The database uniqueness constraint is the arbiter. Re-read the
            # winner instead of crediting a second time.
            continue
        except Exception as exc:  # noqa: BLE001 - one bad entry != abort all
            logger.warning(
                "contribution_credit: entry skipped for %s/%s (%s)",
                agent_id, capability, type(exc).__name__)
            continue
    if applied:
        db.commit()
    return applied


def apply_credit(db: Any, entries: List[Dict[str, Any]]) -> int:
    """Directly feed explicit entries into CapabilityGraduationService.

    Kept for legacy unverified usage accounting. Caller-owned flags and receipt
    labels are not proof and never increment verified success here. Verified
    credit uses :func:`record_chain_credit`, which resolves the durable scoped
    operation, independent Oracle evidence, and unique consumption receipt.

    Returns applied count. Never raises for one bad entry.
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
                capability = str(
                    e.get("capability") or e.get("domain") or "general")
                if not agent_id or weight <= 0.0:
                    continue
                verified = "unverified"
                recorded = svc.record_usage(
                    agent_id, capability, success=True, verified=verified)
                if recorded is False:
                    continue
                applied += 1
            except Exception as ee:  # noqa: BLE001 — one bad entry ≠ abort all
                logger.debug(f"apply_credit entry skipped: {ee}")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"apply_credit failed: {e}")
    return applied


def record_chain_credit(
    execution_id: str,
    db: Optional[Any] = None,
    *,
    audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> bool:
    """Consume one exact fleet outcome into capability credit.

    ``execution_id`` plus (when supplied) the exact ``audit_id`` and
    authenticated scope identify the outcome. Flag OFF or any missing/invalid
    authority is a silent no-op. Returns True only when a new receipt was
    applied (a replay adds nothing).
    """
    if not contribution_credit_enabled():
        return False
    try:
        if db is None:
            from core.database import get_db_session

            with get_db_session() as session:
                return _record_chain_credit_with_session(
                    session, execution_id, audit_id=audit_id,
                    tenant_id=tenant_id, workspace_id=workspace_id,
                    agent_id=agent_id)
        if _caller_owns_session(db):
            # Never commit, roll back, expire, or flush caller-owned state
            # (including already-flushed edits). Write through an independent
            # owned session when the engine can provide one; otherwise refuse
            # explicitly and leave the caller's transaction exactly as it was.
            writer = _independent_writer(db)
            if writer is None:
                logger.warning(
                    "contribution_credit: refusing credit for exec %s because "
                    "the caller's active transaction cannot be supplemented "
                    "independently", execution_id)
                return False
            try:
                return _record_chain_credit_with_session(
                    writer, execution_id, audit_id=audit_id,
                    tenant_id=tenant_id, workspace_id=workspace_id,
                    agent_id=agent_id)
            finally:
                writer.close()
        return _record_chain_credit_with_session(
            db, execution_id, audit_id=audit_id,
            tenant_id=tenant_id, workspace_id=workspace_id,
            agent_id=agent_id)
    except Exception as e:  # noqa: BLE001 — supplement must never break finalize
        # Do not roll back a borrowed session: caller-owned edits are not ours
        # to discard. Owned/isolated writers roll back when their session closes.
        logger.warning(
            "record_chain_credit failed for exec %s (%s)",
            execution_id, type(e).__name__)
        return False


def _record_chain_credit_with_session(
    db: Any,
    execution_id: str,
    *,
    audit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> bool:
    outcome, reason = _resolve_fleet_outcome(
        db, execution_id, audit_id=audit_id, tenant_id=tenant_id,
        workspace_id=workspace_id, agent_id=agent_id)
    if outcome is None:
        logger.debug(
            "contribution_credit: outcome %s refused (%s)",
            execution_id, reason)
        return False

    entries = _collect_credit_entries(db, outcome)
    if not entries:
        return False
    applied = _consume_entries(db, entries, outcome)
    if applied:
        logger.info(
            "contribution_credit: %s specialist outcome(s) credited for "
            "exec %s (audit %s)",
            applied, execution_id, outcome.get("audit_id"))
    return applied > 0
