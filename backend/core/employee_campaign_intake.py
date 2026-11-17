"""Benchmark intake for the controlled employee campaign runners.

The campaign runner already owns the durable campaign (a ``GoalRun`` with its
``decision_log`` and a completed assignment). This module turns the accepted
provider calls the transport recorded on that run into the campaign-owned
sealed journal the benchmark producer requires, binds the result to a durable
``AgentExecution`` completion and invokes the producer.

It deliberately does **not** infer authority from the runner's report:

* accepted provider calls come from the durable route decisions written by the
  transport hook (``model_provenance.set_served_route`` ->
  ``api.assignment_routes._routing_history_entry``), never from a caller
  supplied pair — and only when the provider echoed a ``response_identity``:
  an accepted decision carrying just a served route is audit data, not a
  provider-echoed call, and produces no evidence. There is no fallback to the
  served route, and a campaign in which *any* accepted call lacks that echo is
  rejected outright rather than scored from the calls that happen to carry
  one;
* the completion time is read from the durable assignment, never from a
  wall-clock value chosen by the runner;
* the observation is built from durable assignment results by the runner, and
  the producer scores it against the frozen registry.

The feature is opt-in (``ATOM_EMPLOYEE_BENCHMARK_EVIDENCE=1`` or an explicit
CLI flag). When it is not configured these helpers return immediately and the
campaign behaves exactly as before.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from core.personal_scope import (
    PERSONAL_TENANT_ID,
    PERSONAL_WORKSPACE_ID,
)

logger = logging.getLogger(__name__)

ENV_ENABLED = "ATOM_EMPLOYEE_BENCHMARK_EVIDENCE"
ENV_CAMPAIGN_ID = "ATOM_EMPLOYEE_BENCHMARK_CAMPAIGN_ID"
ENV_BENCHMARK_ID = "ATOM_EMPLOYEE_BENCHMARK_ID"
ENV_ARTIFACT_DIR = "ATOM_EMPLOYEE_BENCHMARK_ARTIFACT_DIR"

DEFAULT_CAMPAIGN_ID = "employee-heldout-two-domain"

# Attribution refusal reasons. These are durable facts about the server plan
# and the registry, never a client-supplied claim: callers may log them, but a
# refusal is final for that execution id.
REASON_AGENT_MISSING = "campaign_agent_missing"
REASON_AGENT_REGISTRY_UNAVAILABLE = "campaign_agent_registry_unavailable"
REASON_AGENT_NOT_FOUND = "campaign_agent_not_found"
REASON_AGENT_TENANT_MISMATCH = "campaign_agent_tenant_mismatch"
REASON_AGENT_WORKSPACE_MISMATCH = "campaign_agent_workspace_mismatch"
REASON_EMPLOYEE_REGISTRY_UNAVAILABLE = "campaign_employee_registry_unavailable"
REASON_EMPLOYEE_NOT_FOUND = "campaign_employee_not_found"
REASON_EMPLOYEE_TENANT_MISMATCH = "campaign_employee_tenant_mismatch"
REASON_EMPLOYEE_WORKSPACE_MISMATCH = "campaign_employee_workspace_mismatch"
REASON_CAMPAIGN_RUN_MISSING = "campaign_run_identity_missing"
REASON_ROW_ATTRIBUTION_MISMATCH = "campaign_row_attribution_mismatch"
REASON_ROW_CAMPAIGN_MISMATCH = "campaign_row_identity_mismatch"
REASON_ROW_TERMINAL = "campaign_row_terminal"
REASON_COMPLETION_MISMATCH = "campaign_completion_mismatch"
REASON_ROW_AGENT_UNRESOLVED = "campaign_row_agent_unresolved"
REASON_ROW_AGENT_SCOPE_MISMATCH = "campaign_row_agent_scope_mismatch"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {
        "1", "true", "yes", "on", "enabled",
    }


def benchmark_intake_enabled(explicit: Optional[bool] = None) -> bool:
    """Campaign intake is opt-in; an explicit CLI flag wins over the env."""
    if explicit is not None:
        return bool(explicit)
    return _truthy(os.getenv(ENV_ENABLED))


def campaign_id(default: str = DEFAULT_CAMPAIGN_ID) -> str:
    return str(os.getenv(ENV_CAMPAIGN_ID) or default).strip() or default


def benchmark_id() -> Optional[str]:
    value = str(os.getenv(ENV_BENCHMARK_ID) or "").strip()
    return value or None


def artifact_dir() -> Optional[Path]:
    value = str(os.getenv(ENV_ARTIFACT_DIR) or "").strip()
    return Path(value) if value else None


# ---------------------------------------------------------------------------
# Durable campaign facts (SQLite scratch world used by the acceptance runner)
# ---------------------------------------------------------------------------


def _connect(db_path: Any) -> Optional[sqlite3.Connection]:
    text = str(db_path or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_file():
        return None
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _json_value(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError):
        return default


def _datetime_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def durable_assignment(db_path: Any, run_id: str) -> Dict[str, Any]:
    """The assignment body from the run's durable task lifecycle."""
    connection = _connect(db_path)
    if connection is None:
        return {}
    try:
        row = connection.execute(
            "select parameters from goal_runs where id = ?", (run_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return {}
    parameters = _json_value(row["parameters"], {})
    lifecycle = (
        parameters.get("task_lifecycle")
        if isinstance(parameters, Mapping) else None)
    lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
    assignment = lifecycle.get("assignment")
    return dict(assignment) if isinstance(assignment, Mapping) else {}


def route_decisions(db_path: Any, run_id: str) -> List[Dict[str, Any]]:
    """The durable route-decision log for one run."""
    connection = _connect(db_path)
    if connection is None:
        return []
    try:
        row = connection.execute(
            "select decision_log from goal_runs where id = ?", (run_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return []
    log = _json_value(row["decision_log"], [])
    return [dict(item) for item in log if isinstance(item, Mapping)]


def _explicit_response_identity(
    decision: Mapping[str, Any],
) -> Optional[Dict[str, str]]:
    """The provider echo on one route decision, only when it is complete.

    A served route is never a substitute: an accepted call without a complete
    ``response_identity`` has no identity, however it was routed.
    """
    identity = decision.get("response_identity")
    if not isinstance(identity, Mapping):
        return None
    provider = str(identity.get("provider") or "").strip()
    model = str(identity.get("model") or "").strip()
    if not provider or not model:
        return None
    return {"provider": provider, "model": model}


def _accepted_route_decisions(
    decisions: List[Mapping[str, Any]],
) -> List[tuple]:
    """``(index, decision)`` pairs for accepted employee route decisions."""
    accepted: List[tuple] = []
    for index, decision in enumerate(decisions or []):
        if not isinstance(decision, Mapping):
            continue
        if str(decision.get("kind") or "") != "employee_route":
            continue
        if decision.get("accepted") is not True:
            continue
        accepted.append((index, decision))
    return accepted


def accepted_transport_calls(
    decisions: List[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Accepted provider calls recorded by the transport on this run.

    Only entries the transport marked ``accepted is True`` **and** whose
    provider echoed a complete ``response_identity`` are returned; an accepted
    call with only a served route has no provider echo and is not returned.
    Requested/attempted routes are carried for audit, never as identity.

    Callers must also consult :func:`accepted_calls_missing_identity`: a
    campaign with any accepted call missing its echo is ineligible as a whole,
    even when the calls returned here carry one.
    """
    calls: List[Dict[str, Any]] = []
    for index, decision in _accepted_route_decisions(decisions):
        identity = _explicit_response_identity(decision)
        if identity is None:
            # The provider echo is the evidence. A served route alone —
            # however accepted — is audit data, not identity; falling back
            # to it would manufacture the echo the producer requires.
            continue
        call_id = str(
            decision.get("attempt_id")
            or f"route-{index + 1}")
        calls.append({
            "call_id": call_id,
            "requested_route": (
                dict(decision["requested_route"])
                if isinstance(decision.get("requested_route"), Mapping)
                else None),
            "served_route": (
                dict(decision["served_route"])
                if isinstance(decision.get("served_route"), Mapping)
                else None),
            "response_identity": identity,
        })
    return calls


def accepted_calls_missing_identity(
    decisions: List[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Accepted calls whose provider echo is absent or incomplete.

    A campaign is only eligible when *every* accepted call carries an explicit
    provider ``response_identity``. These entries are the gap: the campaign
    must be rejected as a whole rather than scored from its remaining echoes.
    """
    missing: List[Dict[str, Any]] = []
    for index, decision in _accepted_route_decisions(decisions):
        if _explicit_response_identity(decision) is not None:
            continue
        missing.append({
            "call_id": str(
                decision.get("attempt_id") or f"route-{index + 1}"),
            "stage": str(decision.get("stage") or "") or None,
        })
    return missing


def unique_served_identity(
    calls: List[Mapping[str, Any]],
) -> Optional[Dict[str, str]]:
    """The one provider-echoed pair in a campaign, or ``None`` when ambiguous.

    Every accepted call must carry its own explicit echo: one call without an
    identity makes the campaign ambiguous, so the remaining echo is never
    promoted to the run's identity (that would be the missing-echo fallback).
    """
    pairs: List[Dict[str, str]] = []
    for call in calls or []:
        if not isinstance(call, Mapping):
            return None
        identity = call.get("response_identity")
        if not isinstance(identity, Mapping):
            return None
        pair = {
            "provider": str(identity.get("provider") or "").strip(),
            "model": str(identity.get("model") or "").strip(),
        }
        if not pair["provider"] or not pair["model"]:
            return None
        if pair not in pairs:
            pairs.append(pair)
    return pairs[0] if len(pairs) == 1 else None


# ---------------------------------------------------------------------------
# Durable AgentExecution binding
# ---------------------------------------------------------------------------


def _session_factory(db_path: Path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Campaign agent attribution (durable, shared by both create paths)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignAttribution:
    """The resolved durable identity of one campaign execution.

    ``agent_id`` comes only from the server plan's validated
    ``provenance.agent_id``; ``employee_id`` stays the human/User assignment
    target. The two are deliberately NOT required to be equal: the established
    authorization helpers validate tenant/workspace scope, and shared/system
    agents legitimately have a NULL or different owner.
    """

    ok: bool
    agent_id: str = ""
    employee_id: str = ""
    tenant_id: str = ""
    workspace_id: str = ""
    campaign_id: str = ""
    run_id: str = ""
    reason: Optional[str] = None
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "agent_id": self.agent_id,
            "employee_id": self.employee_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "reason": self.reason,
            "detail": self.detail,
        }


class CampaignAttributionError(ValueError):
    """Explicit refusal: no campaign row may be created, completed or sealed."""

    def __init__(self, resolution: CampaignAttribution):
        self.reason = resolution.reason or REASON_ROW_ATTRIBUTION_MISMATCH
        self.detail = resolution.detail
        self.resolution = resolution
        message = f"campaign attribution refused: {self.reason}"
        if self.detail:
            message = f"{message}: {self.detail}"
        super().__init__(message)


def _canonical_scope(value: Any, default: str) -> str:
    """Personal-Edition NULL/``default`` equivalence, never a new scope."""
    text = str(value or "").strip()
    return text or default


def _table_exists(db: Any, table: str) -> bool:
    from sqlalchemy import inspect

    try:
        return bool(inspect(db.get_bind()).has_table(table))
    except Exception:  # noqa: BLE001 — an unreadable schema is unresolvable
        return False


def _refused(reason: str, detail: Optional[str] = None) -> CampaignAttribution:
    return CampaignAttribution(ok=False, reason=reason, detail=detail)


def _resolve_campaign_attribution(
    db: Any,
    assignment: Mapping[str, Any],
    *,
    campaign: Optional[str] = None,
    run_id: Optional[str] = None,
) -> CampaignAttribution:
    """Resolve the agent/employee/scope identity from durable server facts.

    The only agent claim read is ``assignment["provenance"]["agent_id"]`` —
    the field the trusted assignment planner stamps from the validated request
    agent. There is no fallback to ``employee_id``, the sole registry agent, a
    model name or any client metadata.
    """
    from core.models import AgentRegistry, User

    assignment = assignment if isinstance(assignment, Mapping) else {}
    provenance = assignment.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    claimed_agent = str(provenance.get("agent_id") or "").strip()
    if not claimed_agent:
        return _refused(
            REASON_AGENT_MISSING,
            "the server plan carries no provenance.agent_id")

    employee_id = str(assignment.get("employee_id") or "").strip()
    tenant_id = _canonical_scope(
        assignment.get("tenant_id"), PERSONAL_TENANT_ID)
    workspace_id = _canonical_scope(
        assignment.get("workspace_id"), PERSONAL_WORKSPACE_ID)
    run_key = str(run_id or assignment.get("run_id") or "").strip()
    if not run_key:
        return _refused(
            REASON_CAMPAIGN_RUN_MISSING,
            "a campaign execution requires a durable run identity")
    campaign_key = str(campaign or campaign_id()).strip() or DEFAULT_CAMPAIGN_ID

    if not _table_exists(db, AgentRegistry.__tablename__):
        return _refused(
            REASON_AGENT_REGISTRY_UNAVAILABLE,
            "the durable agent registry is not readable")
    agent = db.get(AgentRegistry, claimed_agent)
    if agent is None:
        return _refused(
            REASON_AGENT_NOT_FOUND,
            f"agent {claimed_agent!r} is not in the durable registry")
    agent_tenant = _canonical_scope(agent.tenant_id, PERSONAL_TENANT_ID)
    agent_workspace = _canonical_scope(
        agent.workspace_id, PERSONAL_WORKSPACE_ID)
    if agent_tenant != tenant_id:
        return _refused(
            REASON_AGENT_TENANT_MISMATCH,
            f"agent tenant {agent_tenant!r} != assignment tenant {tenant_id!r}")
    if agent_workspace != workspace_id:
        return _refused(
            REASON_AGENT_WORKSPACE_MISMATCH,
            f"agent workspace {agent_workspace!r} != assignment workspace "
            f"{workspace_id!r}")

    if employee_id:
        if not _table_exists(db, User.__tablename__):
            return _refused(
                REASON_EMPLOYEE_REGISTRY_UNAVAILABLE,
                "the durable employee registry is not readable")
        employee = db.get(User, employee_id)
        if employee is None:
            return _refused(
                REASON_EMPLOYEE_NOT_FOUND,
                f"employee {employee_id!r} is not in the durable registry")
        employee_tenant = _canonical_scope(
            employee.tenant_id, PERSONAL_TENANT_ID)
        employee_workspace = _canonical_scope(
            employee.workspace_id, PERSONAL_WORKSPACE_ID)
        if employee_tenant != tenant_id:
            return _refused(
                REASON_EMPLOYEE_TENANT_MISMATCH,
                f"employee tenant {employee_tenant!r} != assignment tenant "
                f"{tenant_id!r}")
        if employee_workspace != workspace_id:
            return _refused(
                REASON_EMPLOYEE_WORKSPACE_MISMATCH,
                f"employee workspace {employee_workspace!r} != assignment "
                f"workspace {workspace_id!r}")

    return CampaignAttribution(
        ok=True,
        agent_id=claimed_agent,
        employee_id=employee_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        campaign_id=campaign_key,
        run_id=run_key,
    )


def resolve_campaign_attribution(
    *,
    db_path: Any,
    assignment: Mapping[str, Any],
    campaign: Optional[str] = None,
    run_id: Optional[str] = None,
) -> CampaignAttribution:
    """Durable public resolver shared by both campaign create paths."""
    path = Path(str(db_path or ""))
    if not path.is_file():
        return _refused(
            REASON_ROW_ATTRIBUTION_MISMATCH, "the campaign database is absent")
    engine, factory = _session_factory(path)
    try:
        with factory() as db:
            return _resolve_campaign_attribution(
                db, assignment, campaign=campaign, run_id=run_id)
    finally:
        engine.dispose()


def _campaign_block(metadata: Any) -> Mapping[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    block = metadata.get("campaign")
    return block if isinstance(block, Mapping) else {}


def _require_existing_attribution(
    execution: Any,
    resolution: CampaignAttribution,
    *,
    completing: bool,
) -> Optional[CampaignAttribution]:
    """Exact idempotency: same agent, scope and campaign/run identity only."""
    row_agent = str(getattr(execution, "agent_id", None) or "").strip()
    row_tenant = _canonical_scope(
        getattr(execution, "tenant_id", None), PERSONAL_TENANT_ID)
    row_workspace = _canonical_scope(
        getattr(execution, "workspace_id", None), PERSONAL_WORKSPACE_ID)
    if (row_agent != resolution.agent_id
            or row_tenant != resolution.tenant_id
            or row_workspace != resolution.workspace_id):
        return _refused(
            REASON_ROW_ATTRIBUTION_MISMATCH,
            "the existing execution row is owned by a different agent or "
            "scope; it is never reused or re-attributed")
    status = str(getattr(execution, "status", None) or "").strip().casefold()
    allowed = {"running", "completed"} if completing else {"running"}
    if status not in allowed:
        return _refused(
            REASON_ROW_TERMINAL,
            f"the existing execution row is {status or 'unknown'}; start a "
            "new campaign run instead")
    block = _campaign_block(getattr(execution, "metadata_json", None))
    block_campaign = str(block.get("id") or "").strip()
    block_run = str(block.get("run_id") or "").strip()
    if (block_campaign != resolution.campaign_id
            or block_run != resolution.run_id):
        return _refused(
            REASON_ROW_CAMPAIGN_MISMATCH,
            "the existing execution row belongs to a different campaign run; "
            "it is never reused or re-attributed")
    return None


def start_campaign_execution(
    *,
    db_path: Any,
    execution_id: str,
    assignment: Mapping[str, Any],
    run_id: Optional[str] = None,
    campaign: Optional[str] = None,
) -> Optional[str]:
    """Create the campaign's durable execution row (status ``running``).

    The row is attributed to the durable server plan's validated
    ``provenance.agent_id`` — never to ``employee_id``. A missing, foreign or
    unresolvable agent raises :class:`CampaignAttributionError` before any row
    is written. An existing row is reused only for the exact same agent,
    tenant, workspace, campaign and run; anything else is refused.
    """
    path = Path(str(db_path or ""))
    if not path.is_file():
        return None
    from core.models import AgentExecution

    engine, factory = _session_factory(path)
    try:
        AgentExecution.__table__.create(engine, checkfirst=True)
        with factory() as db:
            resolution = _resolve_campaign_attribution(
                db, assignment, campaign=campaign, run_id=run_id)
            if not resolution.ok:
                raise CampaignAttributionError(resolution)
            existing = db.get(AgentExecution, execution_id)
            if existing is not None:
                problem = _require_existing_attribution(
                    existing, resolution, completing=False)
                if problem is not None:
                    raise CampaignAttributionError(problem)
                return execution_id
            assignment = assignment if isinstance(assignment, Mapping) else {}
            db.add(AgentExecution(
                id=execution_id,
                agent_id=resolution.agent_id,
                tenant_id=resolution.tenant_id,
                workspace_id=resolution.workspace_id,
                status="running",
                input_summary=str(assignment.get("objective") or "")[:500],
                metadata_json={"campaign": {
                    "id": resolution.campaign_id,
                    "run_id": resolution.run_id,
                }},
            ))
            db.commit()
        return execution_id
    finally:
        engine.dispose()


def complete_campaign_execution(
    *,
    db_path: Any,
    execution_id: str,
    assignment: Mapping[str, Any],
    completed_at: Any,
    served_identity: Optional[Mapping[str, Any]] = None,
    run_id: Optional[str] = None,
    campaign: Optional[str] = None,
) -> bool:
    """Mark the campaign execution completed at the durable assignment time.

    Completion never rewrites agent/tenant/workspace. A completed row is
    immutable: only an identical re-completion (same identity and completion
    time) returns ``True`` without writing. A foreign, colliding, misattributed
    or legacy row raises :class:`CampaignAttributionError`.
    """
    path = Path(str(db_path or ""))
    if not path.is_file():
        return False
    from core.models import AgentExecution

    engine, factory = _session_factory(path)
    try:
        AgentExecution.__table__.create(engine, checkfirst=True)
        with factory() as db:
            resolution = _resolve_campaign_attribution(
                db, assignment, campaign=campaign, run_id=run_id)
            if not resolution.ok:
                raise CampaignAttributionError(resolution)
            execution = db.get(AgentExecution, execution_id)
            if execution is None:
                assignment = (
                    assignment if isinstance(assignment, Mapping) else {})
                execution = AgentExecution(
                    id=execution_id,
                    agent_id=resolution.agent_id,
                    tenant_id=resolution.tenant_id,
                    workspace_id=resolution.workspace_id,
                    input_summary=str(
                        assignment.get("objective") or "")[:500],
                    metadata_json={"campaign": {
                        "id": resolution.campaign_id,
                        "run_id": resolution.run_id,
                    }},
                )
                db.add(execution)
            else:
                problem = _require_existing_attribution(
                    execution, resolution, completing=True)
                if problem is not None:
                    raise CampaignAttributionError(problem)
                if str(execution.status or "").strip().casefold() == "completed":
                    requested = _datetime_value(completed_at)
                    existing_completed = _datetime_value(
                        execution.completed_at)
                    if (requested is not None and existing_completed is not None
                            and requested != existing_completed):
                        raise CampaignAttributionError(_refused(
                            REASON_COMPLETION_MISMATCH,
                            "the completed execution has a different durable "
                            "completion time; sealed history is immutable"))
                    return True
            execution.status = "completed"
            execution.completed_at = _datetime_value(completed_at)
            execution.output_summary = str(
                assignment.get("status") or "completed")
            metadata = (
                dict(execution.metadata_json)
                if isinstance(execution.metadata_json, Mapping) else {})
            if isinstance(served_identity, Mapping):
                provider = str(served_identity.get("provider") or "").strip()
                model = str(served_identity.get("model") or "").strip()
                if provider and model:
                    metadata["model_provenance"] = {
                        "provider": provider,
                        "model": model,
                        "source": "route_attribution",
                        "serving_models": [{
                            "provider": provider, "model": model}],
                    }
            metadata["campaign"] = {
                "id": resolution.campaign_id,
                "run_id": resolution.run_id,
            }
            execution.metadata_json = metadata
            db.commit()
        return True
    finally:
        engine.dispose()


def _execution_assignment_refusal(
    path: Path,
    execution_id: str,
    assignment: Mapping[str, Any],
    *,
    campaign: Optional[str] = None,
) -> Optional[str]:
    """When the caller supplies the plan, the row must match it exactly."""
    if not path.is_file():
        return None
    from core.models import AgentExecution

    engine, factory = _session_factory(path)
    try:
        with factory() as db:
            resolution = _resolve_campaign_attribution(
                db, assignment, campaign=campaign,
                run_id=str(assignment.get("run_id") or "") or None)
            if not resolution.ok:
                return resolution.reason or REASON_ROW_ATTRIBUTION_MISMATCH
            if not _table_exists(db, AgentExecution.__tablename__):
                return REASON_ROW_ATTRIBUTION_MISMATCH
            execution = db.get(AgentExecution, execution_id)
            if execution is None:
                return REASON_ROW_ATTRIBUTION_MISMATCH
            problem = _require_existing_attribution(
                execution, resolution, completing=True)
            if problem is not None:
                return problem.reason or REASON_ROW_ATTRIBUTION_MISMATCH
            return None
    finally:
        engine.dispose()


def _execution_attribution_refusal(
    path: Path, execution_id: str,
) -> Optional[str]:
    """The durable row's agent must resolve inside the row's own scope.

    Returns a refusal reason, or ``None`` when the row is absent/unreadable (the
    producer reports those) or already correctly attributed. A completed
    legacy row attributed to a ``User.id`` (or the old ``employee-campaign``
    fallback) has no registry row and is refused here, so it can never be
    sealed after the fact.
    """
    if not path.is_file():
        return None
    from core.models import AgentExecution, AgentRegistry

    engine, factory = _session_factory(path)
    try:
        with factory() as db:
            if not _table_exists(db, AgentExecution.__tablename__):
                return None
            execution = db.get(AgentExecution, execution_id)
            if execution is None:
                return None
            row_agent = str(execution.agent_id or "").strip()
            row_tenant = _canonical_scope(
                execution.tenant_id, PERSONAL_TENANT_ID)
            row_workspace = _canonical_scope(
                execution.workspace_id, PERSONAL_WORKSPACE_ID)
            if not row_agent:
                return REASON_ROW_AGENT_UNRESOLVED
            if not _table_exists(db, AgentRegistry.__tablename__):
                return REASON_ROW_AGENT_UNRESOLVED
            agent = db.get(AgentRegistry, row_agent)
            if agent is None:
                return REASON_ROW_AGENT_UNRESOLVED
            if (_canonical_scope(agent.tenant_id, PERSONAL_TENANT_ID)
                    != row_tenant
                    or _canonical_scope(
                        agent.workspace_id, PERSONAL_WORKSPACE_ID)
                    != row_workspace):
                return REASON_ROW_AGENT_SCOPE_MISMATCH
            return None
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


def record_campaign_evidence(
    *,
    db_path: Any,
    execution_id: str,
    campaign: str,
    observation: Any,
    completed_at: Any,
    decisions: List[Mapping[str, Any]],
    registry: Optional[Mapping[str, Any]] = None,
    benchmark: Optional[str] = None,
    out_dir: Optional[Any] = None,
    assignment: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Seal the transport journal and invoke the production producer.

    The journal is opened here (the campaign's own journal), filled only from
    the transport's accepted identity records, and sealed with the durable
    assignment completion time. A campaign with no accepted call returns
    ``{"status": "skipped"}`` without writing anything. If any accepted call
    lacks an explicit provider ``response_identity`` the campaign is
    ``rejected`` as a whole — even when other accepted calls echoed one — and
    nothing is written.

    ``assignment`` is optional: when supplied (the runner always does), the
    durable row must match the server plan's exact agent/scope/campaign-run
    identity before sealing. Without it, the row's agent must still resolve to
    a real ``AgentRegistry`` row in the row's own scope, so a legacy
    user-attributed row can never be sealed.
    """
    from core.employee_benchmark_evidence import (
        REASON_IDENTITY_MISSING,
        open_campaign_transport_journal,
        produce_employee_benchmark_evidence,
    )

    missing = accepted_calls_missing_identity(decisions)
    if missing:
        # A partial journal would present the calls that happen to carry an
        # echo as the campaign's identity. The whole campaign is ineligible:
        # a served route is audit data, never a substitute for the echo.
        logger.warning(
            "employee campaign %s: accepted calls without a provider "
            "response identity: %s",
            campaign, [item.get("call_id") for item in missing])
        return {
            "status": "rejected",
            "reason": REASON_IDENTITY_MISSING,
            "reasons": [REASON_IDENTITY_MISSING],
            "campaign_id": campaign,
            "missing_identity_calls": missing,
        }
    calls = accepted_transport_calls(decisions)
    if not calls:
        return {
            "status": "skipped",
            "reason": "no_accepted_transport_calls",
            "campaign_id": campaign,
        }
    # Independent, durable gate: a row whose agent is not a real registry row
    # in the row's own scope is not agent-qualifying evidence. When the caller
    # supplies the server plan, the row must also match that plan's exact
    # agent/scope/campaign-run identity. This closes the legacy
    # user-attributed row and a foreign row reached without the create paths
    # (the producer itself stays row-authority).
    if isinstance(assignment, Mapping):
        attribution_refusal = _execution_assignment_refusal(
            Path(str(db_path)), execution_id, assignment, campaign=campaign)
    else:
        attribution_refusal = _execution_attribution_refusal(
            Path(str(db_path)), execution_id)
    if attribution_refusal is not None:
        logger.warning(
            "employee campaign %s: refusing to seal execution %s: %s",
            campaign, execution_id, attribution_refusal)
        return {
            "status": "rejected",
            "reason": attribution_refusal,
            "reasons": [attribution_refusal],
            "campaign_id": campaign,
        }
    journal = open_campaign_transport_journal(
        campaign_id=campaign, execution_id=execution_id)
    for call in calls:
        journal.record_call(
            accepted=True,
            requested_route=call.get("requested_route"),
            served_route=call.get("served_route"),
            response_identity=call.get("response_identity"),
            call_id=call.get("call_id"),
        )
    journal.seal(completed_at=completed_at)

    path = Path(str(db_path))
    engine, factory = _session_factory(path)
    try:
        result = produce_employee_benchmark_evidence(
            execution_id=execution_id,
            observation=observation,
            transport_journal=journal,
            benchmark_id=benchmark,
            registry=registry,
            session_factory=factory,
            artifact_dir=out_dir or artifact_dir(),
        )
    finally:
        engine.dispose()
    if result.get("status") not in ("recorded", "already_recorded"):
        logger.warning(
            "employee campaign %s: benchmark evidence not recorded: %s",
            campaign, result.get("reasons") or result.get("status"))
    elif result.get("status") == "recorded":
        logger.info(
            "employee campaign %s: benchmark evidence recorded for %s",
            campaign, result.get("evidence_id"))
    return result


__all__ = [
    "CampaignAttribution",
    "CampaignAttributionError",
    "DEFAULT_CAMPAIGN_ID",
    "ENV_ARTIFACT_DIR",
    "ENV_BENCHMARK_ID",
    "ENV_CAMPAIGN_ID",
    "ENV_ENABLED",
    "accepted_calls_missing_identity",
    "accepted_transport_calls",
    "artifact_dir",
    "benchmark_id",
    "benchmark_intake_enabled",
    "campaign_id",
    "complete_campaign_execution",
    "durable_assignment",
    "record_campaign_evidence",
    "resolve_campaign_attribution",
    "route_decisions",
    "start_campaign_execution",
    "unique_served_identity",
]
