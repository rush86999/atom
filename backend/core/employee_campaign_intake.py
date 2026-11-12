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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

ENV_ENABLED = "ATOM_EMPLOYEE_BENCHMARK_EVIDENCE"
ENV_CAMPAIGN_ID = "ATOM_EMPLOYEE_BENCHMARK_CAMPAIGN_ID"
ENV_BENCHMARK_ID = "ATOM_EMPLOYEE_BENCHMARK_ID"
ENV_ARTIFACT_DIR = "ATOM_EMPLOYEE_BENCHMARK_ARTIFACT_DIR"

DEFAULT_CAMPAIGN_ID = "employee-heldout-two-domain"


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


def start_campaign_execution(
    *,
    db_path: Any,
    execution_id: str,
    assignment: Mapping[str, Any],
) -> Optional[str]:
    """Create the campaign's durable execution row (status ``running``)."""
    path = Path(str(db_path or ""))
    if not path.is_file():
        return None
    from core.models import AgentExecution

    engine, factory = _session_factory(path)
    try:
        AgentExecution.__table__.create(engine, checkfirst=True)
        with factory() as db:
            if db.get(AgentExecution, execution_id) is not None:
                return execution_id
            assignment = assignment if isinstance(assignment, Mapping) else {}
            db.add(AgentExecution(
                id=execution_id,
                agent_id=(
                    str(assignment.get("employee_id") or "")
                    or "employee-campaign"),
                tenant_id=str(assignment.get("tenant_id") or "") or None,
                workspace_id=str(assignment.get("workspace_id") or "") or None,
                status="running",
                input_summary=str(assignment.get("objective") or "")[:500],
                metadata_json={},
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
) -> bool:
    """Mark the campaign execution completed at the durable assignment time."""
    path = Path(str(db_path or ""))
    if not path.is_file():
        return False
    from core.models import AgentExecution

    engine, factory = _session_factory(path)
    try:
        AgentExecution.__table__.create(engine, checkfirst=True)
        with factory() as db:
            execution = db.get(AgentExecution, execution_id)
            if execution is None:
                assignment = assignment if isinstance(assignment, Mapping) else {}
                execution = AgentExecution(
                    id=execution_id,
                    agent_id=(
                        str(assignment.get("employee_id") or "")
                        or "employee-campaign"),
                    tenant_id=(
                        str(assignment.get("tenant_id") or "") or None),
                    workspace_id=(
                        str(assignment.get("workspace_id") or "") or None),
                    input_summary=str(
                        assignment.get("objective") or "")[:500],
                    metadata_json={},
                )
                db.add(execution)
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
            metadata.setdefault("campaign", {
                "id": campaign_id(),
                "run_id": str(assignment.get("run_id") or "") or None,
            })
            execution.metadata_json = metadata
            db.commit()
        return True
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
) -> Dict[str, Any]:
    """Seal the transport journal and invoke the production producer.

    The journal is opened here (the campaign's own journal), filled only from
    the transport's accepted identity records, and sealed with the durable
    assignment completion time. A campaign with no accepted call returns
    ``{"status": "skipped"}`` without writing anything. If any accepted call
    lacks an explicit provider ``response_identity`` the campaign is
    ``rejected`` as a whole — even when other accepted calls echoed one — and
    nothing is written.
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
    "route_decisions",
    "start_campaign_execution",
    "unique_served_identity",
]
