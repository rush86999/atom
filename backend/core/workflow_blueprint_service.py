"""Durable, scoped storage for ORCH-01 workflow blueprints.

The Queen's validated blueprint is stored in the existing ``Workflow`` /
``WorkflowStep`` tables. Generation only designs and persists; it never executes
the workflow or activates a recurring trigger. The read path does not depend on
the in-memory orchestrator, so a fresh process/session can retrieve the exact
committed definition.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.models import Workflow, WorkflowStep

logger = logging.getLogger(__name__)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _public_view(
    workflow: Workflow, configuration: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "workflow_id": workflow.id,
        "blueprint_id": configuration.get("blueprint_id"),
        "name": workflow.name,
        "architecture_name": configuration.get(
            "architecture_name") or workflow.name,
        "description": workflow.description or "",
        "execution_mode": configuration.get("execution_mode") or "one_off",
        "status": workflow.status or "designed",
        "start_step": configuration.get("start_step"),
        "nodes": list(configuration.get("nodes") or []),
        "steps": list(configuration.get("steps") or []),
        "triggers": list(configuration.get("triggers") or []),
        "required_integrations": list(
            configuration.get("required_integrations") or []),
        "missing_capabilities": list(
            configuration.get("missing_capabilities") or []),
        "hitl_gates": list(configuration.get("hitl_gates") or []),
        "step_count": len(configuration.get("steps") or []),
        "definition_digest": configuration.get("definition_digest"),
        "blueprint": {
            "architecture_name": configuration.get(
                "architecture_name") or workflow.name,
            "description": workflow.description or "",
            "execution_mode": configuration.get("execution_mode") or "one_off",
            "nodes": list(configuration.get("nodes") or []),
            "start_step": configuration.get("start_step"),
            "triggers": list(configuration.get("triggers") or []),
            "required_integrations": list(
                configuration.get("required_integrations") or []),
            "missing_capabilities": list(
                configuration.get("missing_capabilities") or []),
        },
        "created_at": _iso(workflow.created_at),
        "updated_at": _iso(workflow.updated_at),
        "provenance": dict(configuration.get("generation") or {}),
    }


def persist_blueprint(
    db: Session,
    *,
    compiled: Dict[str, Any],
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    route_reasoning: str = "",
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Commit one compiled blueprint and return its public readback view."""
    workflow_id = str(compiled.get("workflow_id") or "")
    if not workflow_id:
        raise ValueError("compiled blueprint has no workflow_id")
    existing = db.query(Workflow).filter(
        Workflow.id == workflow_id).first()
    if existing is not None:
        raise ValueError(f"workflow {workflow_id} already exists")
    configuration = {
        "schema": compiled.get("schema") or "orch-workflow-blueprint-1",
        "workspace_id": str(workspace_id or "default"),
        "blueprint_id": compiled.get("blueprint_id"),
        "architecture_name": compiled.get("architecture_name"),
        "execution_mode": compiled.get("execution_mode"),
        "start_step": compiled.get("start_step"),
        "nodes": list(compiled.get("nodes") or []),
        "steps": list(compiled.get("steps") or []),
        "triggers": list(compiled.get("triggers") or []),
        "required_integrations": list(
            compiled.get("required_integrations") or []),
        "missing_capabilities": list(
            compiled.get("missing_capabilities") or []),
        "hitl_gates": list(compiled.get("hitl_gates") or []),
        "definition_digest": compiled.get("definition_digest"),
        "definition": dict(compiled.get("definition") or {}),
        "route_reasoning": str(route_reasoning or ""),
        "generation": {
            **(provenance or {}),
            "source": "model",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    workflow = Workflow(
        id=workflow_id,
        name=str(compiled.get("architecture_name") or "AI Generated Workflow"),
        description=str(compiled.get("description") or ""),
        tenant_id=str(tenant_id or "default"),
        user_id=str(user_id or "") or None,
        # A generated design is not an active trigger. Manual execution can
        # still resolve it through the orchestrator registration below.
        status="designed",
        configuration=configuration,
    )
    try:
        db.add(workflow)
        db.flush()
        for index, step in enumerate(configuration["steps"], start=1):
            parameters = dict(step.get("parameters") or {})
            parameters.update({
                "step_id": step.get("step_id"),
                "description": step.get("description"),
                "next_steps": list(step.get("next_steps") or []),
                "hitl": bool(step.get("hitl")
                             or step.get("step_type") == "approval_required"),
            })
            design_action = parameters.get("design_action") or {}
            db.add(WorkflowStep(
                workflow_id=workflow_id,
                step_number=index,
                type=str(step.get("step_type") or "business_agent_execution"),
                connector_id=(
                    str(design_action.get("service") or "") or None),
                operation_id=(
                    str(design_action.get("action") or "") or None),
                parameters=parameters,
                priority="MEDIUM",
            ))
        db.commit()
        db.refresh(workflow)
    except Exception:
        db.rollback()
        raise
    return _public_view(workflow, configuration)


def load_blueprint(
    db: Session,
    *,
    workflow_id: str,
    tenant_id: str,
    workspace_id: str,
) -> Optional[Dict[str, Any]]:
    """Load the exact committed design in the caller's workspace scope."""
    workflow = db.query(Workflow).filter(
        Workflow.id == str(workflow_id or ""),
        Workflow.tenant_id == str(tenant_id or "default"),
    ).first()
    if workflow is None:
        return None
    configuration = workflow.configuration
    if not isinstance(configuration, dict):
        return None
    if str(configuration.get("workspace_id") or "") != str(
            workspace_id or "default"):
        return None
    return _public_view(workflow, configuration)


def register_compiled_workflow(compiled: Dict[str, Any]) -> bool:
    """Register a manual-execution definition without activating triggers.

    The durable design stores the requested trigger metadata. The in-memory
    orchestrator entry intentionally carries no triggers, so generating a
    recurring blueprint cannot activate it.
    """
    try:
        from advanced_workflow_orchestrator import (
            WorkflowDefinition,
            WorkflowStep,
            WorkflowStepType,
            get_orchestrator,
        )

        steps = []
        for raw in compiled.get("steps") or []:
            try:
                step_type = WorkflowStepType(str(raw.get("step_type")))
            except ValueError:
                step_type = WorkflowStepType.BUSINESS_AGENT_EXECUTION
            steps.append(WorkflowStep(
                step_id=str(raw.get("step_id")),
                step_type=step_type,
                description=str(raw.get("description") or ""),
                parameters=dict(raw.get("parameters") or {}),
                next_steps=list(raw.get("next_steps") or []),
            ))
        definition = WorkflowDefinition(
            workflow_id=str(compiled.get("workflow_id")),
            name=str(compiled.get("architecture_name")
                     or "AI Generated Workflow"),
            description=str(compiled.get("description") or ""),
            steps=steps,
            start_step=str(compiled.get("start_step") or ""),
            # Never activate a recurring trigger at design time.
            triggers=[],
            allow_event_critical=False,
        )
        get_orchestrator().register_workflow(definition)
        return True
    except Exception as exc:  # noqa: BLE001 — durable readback is primary
        logger.warning(
            "workflow blueprint registered durably but not in the live "
            "orchestrator: %s", exc)
        return False
