"""Capability planner for durable assignments.

The existing GoalRun router decides ADVANCE/WAIT/REPLAN for a process; it is
not a typed assignment-plan generator and it cannot grant permissions. This
module turns an accepted objective plus explicit source/deliverable
descriptors into steps over the REGISTERED assignment adapters, then validates
the result before any work starts.

No business vocabulary is required: sources, deliverables, calculations and
outbound payloads are caller-supplied opaque descriptors. Unknown kinds or
unregistered adapters become validation errors or durable gaps, never invented
steps.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from core.assignment_executor import default_adapter_registry
from core.assignment_resources import resource_binding
from core.assignment_plan import (
    ASSIGNMENT_SCHEMA_VERSION,
    new_assignment,
    new_deliverable,
    new_step,
    new_teaching_snapshot,
    validate_assignment,
)
from core.task_lifecycle import TaskLifecycleError

_DELIVERABLE_ADAPTERS = {
    "document": "artifact.document",
    "spreadsheet": "artifact.spreadsheet",
    "presentation": "artifact.presentation",
    "email_draft": "email.draft",
}
_DELIVERABLE_CRITERIA = {
    "document": "artifact_verified",
    "spreadsheet": "artifact_verified",
    "presentation": "artifact_verified",
    "email_draft": "draft_saved",
}
_SOURCE_ADAPTERS = {
    "workbook": "workbook.read",
    "document": "document.read",
}


class AssignmentPlanError(TaskLifecycleError):
    """The proposed assignment plan is not executable as declared."""


def _bounded(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def _source_step(
    source: Dict[str, Any],
    index: int,
    *,
    aggregate: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    kind = str(source.get("kind") or "").strip().lower()
    representation = str(source.get("representation") or "").strip().lower()
    if representation == "parquet_frame":
        adapter = "dataset.aggregate" if aggregate else "dataset.read"
    elif representation in ("xlsx", "file"):
        adapter = "workbook.read" if kind == "workbook" else "document.read"
    else:
        adapter = _SOURCE_ADAPTERS.get(kind)
    if not adapter:
        raise AssignmentPlanError(
            f"unsupported source kind '{kind}'; supported: "
            f"{sorted(_SOURCE_ADAPTERS)}")
    binding = resource_binding(source)
    if not binding.get("resource_id") and not binding.get("dataset_name"):
        raise AssignmentPlanError(
            f"source {kind!r} requires a server-resolved resource binding")
    inputs: Dict[str, Any] = {"resource_binding": binding}
    if source.get("internal_fixture") and source.get("path"):
        inputs["path"] = str(source["path"])
    if kind == "workbook":
        for key in ("sheet", "columns", "filters", "header_row", "max_rows"):
            if source.get(key) is not None:
                inputs[key] = source[key]
    elif representation == "parquet_frame":
        for key in ("columns", "filters", "max_rows"):
            if source.get(key) is not None:
                inputs[key] = source[key]
    if aggregate:
        inputs["operation"] = str(
            aggregate.get("operation") or "sum").strip().lower()
        if aggregate.get("value_column"):
            inputs["value_column"] = str(aggregate["value_column"])
        if aggregate.get("filters") is not None:
            inputs["filters"] = aggregate["filters"]
        return new_step(
            step_id=f"source-{index}",
            title=f"Aggregate {kind} source",
            operation_type="calculate",
            adapter=adapter,
            inputs=inputs,
            effect="local",
        )
    return new_step(
        step_id=f"source-{index}",
        title=f"Read {kind} source",
        operation_type="retrieve",
        adapter=adapter,
        inputs=inputs,
        effect="read_only",
    )


def _deliverable_step(
    deliverable: Dict[str, Any],
    *,
    index: int,
    depends_on: Sequence[str],
    teaching: Dict[str, Any],
    objective: str,
    calculation_step: Optional[str],
    source_step: Optional[str],
    transport_adapter: Optional[str],
) -> List[Dict[str, Any]]:
    kind = str(deliverable.get("kind") or "").strip().lower()
    if kind not in _DELIVERABLE_ADAPTERS:
        raise AssignmentPlanError(
            f"unsupported deliverable kind '{kind}'; supported: "
            f"{sorted(_DELIVERABLE_ADAPTERS)}")
    step_id = str(deliverable.get("step_id") or f"deliverable-{index}")
    if kind == "email_draft":
        draft_id = step_id
        body = str(deliverable.get("body") or "").strip()
        compose = False
        if not body and calculation_step:
            compose = True
        if not body and not compose:
            raise AssignmentPlanError(
                "an email draft requires explicit body content or a "
                "validated result to compose from")
        draft = new_step(
            step_id=draft_id,
            title=f"Prepare {deliverable.get('description') or 'email draft'}",
            operation_type="outbound",
            adapter="email.draft",
            depends_on=list(depends_on),
            inputs={
                "to": deliverable.get("to") or [],
                "cc": deliverable.get("cc") or [],
                "subject": deliverable.get("subject")
                or _bounded(objective, 200),
                "body": body,
                "compose_from_results": compose,
                "deliverable_id": str(
                    deliverable.get("deliverable_id")
                    or f"del-{step_id}"),
            },
            effect="local",
        )
        return [draft]

    adapter = _DELIVERABLE_ADAPTERS[kind]
    inputs: Dict[str, Any] = {
        "path": deliverable.get("path"),
        "title": deliverable.get("title") or _bounded(objective, 200),
        "format_spec": (teaching.get("output_requirements") or {}),
        "deliverable_id": str(
            deliverable.get("deliverable_id") or f"del-{step_id}"),
    }
    if kind == "spreadsheet":
        rows = deliverable.get("rows")
        if isinstance(rows, list) and rows:
            inputs["rows"] = rows
        elif source_step:
            inputs["rows"] = f"${{{source_step}.rows}}"
            inputs["compose_from_results"] = True
        else:
            raise AssignmentPlanError(
                "a spreadsheet deliverable requires explicit rows or a "
                "validated source read")
    else:
        content = str(deliverable.get("content") or "").strip()
        if content:
            inputs["content"] = content
        elif calculation_step:
            inputs["content"] = ""
            inputs["compose_from_results"] = True
        else:
            raise AssignmentPlanError(
                "a grounded deliverable requires explicit content or a "
                "validated calculation; generic prose is not a deliverable")
    if not inputs.get("path"):
        raise AssignmentPlanError(
            f"deliverable {kind!r} requires an output path")
    step = new_step(
        step_id=step_id,
        title=f"Render {deliverable.get('description') or kind}",
        operation_type="present",
        adapter=adapter,
        depends_on=list(depends_on),
        inputs=inputs,
        effect="local",
    )
    return [step]


def _send_step(
    outbound: Dict[str, Any],
    *,
    step_id: str,
    depends_on: Sequence[str],
    draft_step: Optional[str],
    transport_adapter: Optional[str],
) -> Dict[str, Any]:
    adapter = transport_adapter or "email.send_outlook"
    if adapter == "email.send_outlook" and os.getenv(
            "ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", "0") != "1":
        raise AssignmentPlanError(
            "production email sending is not authorized in this release; "
            "use a draft-and-approval deliverable or the isolated controlled "
            "outbox adapter")
    if adapter == "email.send_outlook" and not outbound.get("canvas_id"):
        raise AssignmentPlanError(
            "the Outlook send adapter requires an existing prepared canvas_id; "
            "without one, use a draft-only step")
    attachment_ids = [
        str(item).strip() for item in (outbound.get("attachment_ids") or [])
        if str(item).strip()
    ]
    attachment_hashes = {
        str(key).strip(): str(value).strip()
        for key, value in (outbound.get("attachment_hashes") or {}).items()
        if str(key).strip()
    }
    if attachment_ids and not attachment_hashes:
        raise AssignmentPlanError(
            "outbound attachments require an exact sha256 binding; "
            "attachment ids alone can resolve to changed bytes")
    if attachment_hashes and not attachment_ids:
        raise AssignmentPlanError(
            "attachment sha256 bindings require matching attachment ids")
    if set(attachment_hashes) != set(attachment_ids):
        raise AssignmentPlanError(
            "attachment sha256 bindings must name exactly the sent attachments")
    inputs: Dict[str, Any] = {
        "to": outbound.get("to") or [],
        "cc": outbound.get("cc") or [],
        "subject": outbound.get("subject") or "",
        "body": str(outbound.get("body") or ""),
        "attachment_ids": attachment_ids,
        "attachment_hashes": attachment_hashes,
        "deliverable_id": str(
            outbound.get("deliverable_id") or "del-send"),
    }
    if not inputs["body"].strip():
        if outbound.get("compose_from_results"):
            inputs["compose_from_results"] = True
        else:
            raise AssignmentPlanError(
                "an outbound effect requires explicit body content or a "
                "validated result to compose from")
    if draft_step:
        inputs["canvas_id"] = outbound.get("canvas_id") or ""
        inputs["draft_revision"] = {
            "$ref": f"{draft_step}.artifact.revision"}
    inputs["deliverable_id"] = str(
        outbound.get("deliverable_id") or "del-send")
    return new_step(
        step_id=step_id,
        title="Send the approved response",
        operation_type="outbound",
        adapter=adapter,
        depends_on=list(depends_on),
        inputs=inputs,
        effect="external",
        approval_required=True,
        approval_purpose="Send the prepared response",
    )


def plan_assignment(
    *,
    objective: str,
    sources: Optional[Sequence[Dict[str, Any]]] = None,
    deliverables: Optional[Sequence[Dict[str, Any]]] = None,
    calculation: Optional[Dict[str, Any]] = None,
    outbound: Optional[Dict[str, Any]] = None,
    wait: Optional[Dict[str, Any]] = None,
    teaching_snapshot: Optional[Dict[str, Any]] = None,
    authorized_actions: Optional[Sequence[str]] = None,
    employee_id: str = "",
    workspace_id: str = "",
    tenant_id: str = "",
    agent_id: Optional[str] = None,
    transport_adapter: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    proposed_steps: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build and validate an assignment plan from opaque descriptors."""
    teaching = teaching_snapshot or new_teaching_snapshot(
        revision="untrained")
    aggregate: Optional[Dict[str, Any]] = None
    if calculation and isinstance(calculation.get("aggregate"), dict):
        aggregate = dict(calculation["aggregate"])
        if calculation.get("expression"):
            raise AssignmentPlanError(
                "a calculation cannot be both an expression and a connected "
                "aggregate")
    aggregate_index = 0
    if aggregate is not None:
        aggregate_index = max(0, int(calculation.get("source_index") or 0))
        if aggregate_index >= len(sources or []):
            raise AssignmentPlanError(
                "the aggregate names a source that is not in the accepted "
                "source scope")
        if str((sources or [])[aggregate_index].get("representation")
               or "") != "parquet_frame":
            raise AssignmentPlanError(
                "a connected aggregate requires a materialized Parquet "
                "dataset; an authorized workbook is read as rows")
    source_steps = [
        _source_step(
            dict(source), index + 1,
            aggregate=aggregate if index == aggregate_index else None,
        )
        for index, source in enumerate(sources or [])
    ]
    source_ids = [step["step_id"] for step in source_steps]
    wait_step: Optional[str] = None
    wait_steps: List[Dict[str, Any]] = []
    if wait:
        correlation = str(wait.get("correlation_id") or "").strip()
        if not correlation:
            raise AssignmentPlanError(
                "a wait step requires a correlation_id")
        wait_step = "wait"
        wait_steps = [new_step(
            step_id=wait_step,
            title="Wait for the missing external fact",
            operation_type="retrieve",
            adapter=str(wait.get("adapter") or "assignment.controlled_wait"),
            depends_on=source_ids,
            inputs={
                "correlation_id": correlation,
                "party": wait.get("party") or "",
                "detail": wait.get("detail") or "",
            },
            effect="read_only",
        )]
    calc_step: Optional[str] = None
    calc_steps: List[Dict[str, Any]] = []
    if aggregate is not None:
        calc_step = source_ids[aggregate_index]
    elif calculation and calculation.get("expression"):
        calc_step = "calculate"
        calc_steps = [new_step(
            step_id=calc_step,
            title="Calculate the requested result",
            operation_type="calculate",
            adapter="formula.calculate",
            depends_on=source_ids + ([wait_step] if wait_step else []),
            inputs={
                "expression": calculation["expression"],
                "bindings": calculation.get("bindings") or {},
                "units": calculation.get("units") or {},
                "output_unit": calculation.get("output_unit") or "",
                "origin": calculation.get("origin") or {},
            },
            effect="local",
        )]
    if calculation and not calculation.get("expression") and aggregate is None:
        raise AssignmentPlanError(
            "a calculation requires an explicit expression or a validated "
            "aggregate; a method gap cannot be invented")

    deliverable_steps: List[Dict[str, Any]] = []
    deliverable_records: List[Dict[str, Any]] = []
    base_deps = source_ids + ([wait_step] if wait_step else []) + (
        [calc_step] if calc_step else [])
    for index, raw in enumerate(deliverables or []):
        deliverable = dict(raw)
        kind = str(deliverable.get("kind") or "").strip().lower()
        steps = _deliverable_step(
            deliverable,
            index=index + 1,
            depends_on=base_deps,
            teaching=teaching,
            objective=objective,
            calculation_step=calc_step,
            source_step=source_ids[0] if source_ids else None,
            transport_adapter=transport_adapter,
        )
        deliverable_steps.extend(steps)
        deliverable_records.append(new_deliverable(
            deliverable_id=str(
                deliverable.get("deliverable_id")
                or f"del-{steps[0]['step_id']}"),
            kind=kind,
            description=str(deliverable.get("description") or kind),
            required=bool(deliverable.get("required", True)),
            step_id=steps[0]["step_id"],
        ))

    send_steps: List[Dict[str, Any]] = []
    if outbound:
        outbound_payload = dict(outbound)
        if not str(outbound_payload.get("body") or "").strip() and calc_step:
            outbound_payload["compose_from_results"] = True
        send_steps = [_send_step(
            outbound_payload, step_id="send",
            depends_on=list(base_deps) + [
                step["step_id"] for step in deliverable_steps],
            draft_step=next((
                step["step_id"] for step in deliverable_steps
                if step["adapter"] == "email.draft"), None),
            transport_adapter=transport_adapter,
        )]
        deliverable_records.append(new_deliverable(
            deliverable_id=str(
                outbound.get("deliverable_id") or "del-send"),
            kind="email",
            description="Provider-accepted response",
            required=True,
            step_id="send",
        ))

    if proposed_steps is not None:
        steps = [dict(step) for step in proposed_steps]
        # A proposed plan must not rename or expand the accepted objective's
        # scope; validate below against the registered catalog.
        source_steps = []
        wait_steps = []
        calc_steps = []
        deliverable_steps = []
        send_steps = []
    else:
        steps = source_steps + wait_steps + calc_steps + deliverable_steps + send_steps

    criteria: List[Dict[str, Any]] = []
    for record in deliverable_records:
        criterion = _DELIVERABLE_CRITERIA.get(record["kind"])
        if criterion:
            criteria.append({"kind": criterion,
                             "deliverable_id": record["deliverable_id"]})
    if send_steps:
        criteria.append({"kind": "provider_accepted",
                         "deliverable_id": "del-send"})
    criteria.append({"kind": "required_work_complete"})

    actions = sorted(set(str(item) for item in (authorized_actions or [])
                          if str(item).strip()))

    assignment = new_assignment(
        objective=objective,
        employee_id=employee_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        teaching_snapshot=teaching,
        steps=steps,
        deliverables=deliverable_records,
        sources=[
            {
                "kind": source.get("kind"),
                "binding": resource_binding(source),
            }
            for source in (sources or [])
        ],
        authorized_actions=actions,
        completion_criteria=criteria,
        budget={"max_steps": max(4, min(len(steps) + 8, 40)),
                "max_attempts_per_step": 3,
                "max_wall_seconds": 900},
        provenance={
            **dict(provenance or {}),
            "agent_id": agent_id,
            "planner": "capability_registry",
            "source_kinds": [s.get("kind") for s in (sources or [])],
        },
    )
    validate_proposed_plan(assignment)
    return assignment


def validate_proposed_plan(
    assignment: Dict[str, Any],
    *,
    registry=None,
) -> None:
    """Validate every executable step before the assignment is created."""
    validate_assignment(assignment)
    registry = registry or default_adapter_registry
    if not assignment.get("workspace_id"):
        raise AssignmentPlanError(
            "the assignment must carry an explicit workspace scope")
    if not assignment.get("sources"):
        raise AssignmentPlanError(
            "the assignment must identify at least one authorized source")
    if len(assignment.get("steps") or []) > int(
            (assignment.get("budget") or {}).get("max_steps") or 40):
        raise AssignmentPlanError("the plan exceeds its step budget")
    known_steps = {step["step_id"] for step in assignment["steps"]}
    accepted_actions = set(assignment.get("authorized_actions") or [])
    for step in assignment["steps"]:
        adapter = registry.get(step.get("adapter") or "")
        if adapter is None:
            raise AssignmentPlanError(
                f"step {step['step_id']} names unregistered adapter "
                f"'{step.get('adapter')}'")
        metadata = dict(adapter.metadata or {})
        expected_effect = metadata.get("effect")
        if expected_effect and expected_effect != "declared" and str(
                step.get("effect") or "") != str(expected_effect):
            raise AssignmentPlanError(
                f"step {step['step_id']} declares effect "
                f"'{step.get('effect')}' but adapter "
                f"'{step.get('adapter')}' is '{expected_effect}'")
        required_actions = set(metadata.get("required_actions") or [])
        if required_actions and not required_actions <= accepted_actions:
            raise AssignmentPlanError(
                f"step {step['step_id']} requires actions "
                f"{sorted(required_actions)} outside the accepted authority "
                f"{sorted(accepted_actions)}")
        if step.get("standing_authorization") and not metadata.get(
                "allow_standing_authorization"):
            raise AssignmentPlanError(
                f"step {step['step_id']} invents standing authorization; "
                f"the adapter does not accept it")
        for dependency in step.get("depends_on") or []:
            if dependency not in known_steps:
                raise AssignmentPlanError(
                    f"step {step['step_id']} depends on missing step "
                    f"{dependency}")
        if step.get("adapter") == "action.registry":
            from core.action_registry import action_registry

            action_name = str((step.get("inputs") or {}).get("action") or "")
            action = action_registry.get_action(action_name)
            if action is None:
                raise AssignmentPlanError(
                    f"step {step['step_id']} names unregistered action "
                    f"'{action_name}'")
            effects = [str(item.get("effect") or "")
                       for item in (action.effects or [])
                       if isinstance(item, dict)]
            mutating = {"write", "create", "update", "delete", "send",
                        "execute", "graph_updated", "record_created"}
            action_effect = "external" if any(
                effect.lower() in mutating for effect in effects
            ) else ("read_only" if effects else "external")
            if str(step.get("effect") or "") != action_effect:
                raise AssignmentPlanError(
                    f"step {step['step_id']} declares "
                    f"'{step.get('effect')}' but registered action "
                    f"'{action_name}' is '{action_effect}'")
            required_action = (
                "retrieve" if action_effect == "read_only" else "outbound")
            if required_action not in accepted_actions:
                raise AssignmentPlanError(
                    f"step {step['step_id']} invokes registered action "
                    f"'{action_name}' which requires accepted action "
                    f"'{required_action}' outside the accepted authority "
                    f"{sorted(accepted_actions)}")
        if step.get("effect") == "external" and not (
                (step.get("approval") or {}).get("required")):
            raise AssignmentPlanError(
                f"external step {step['step_id']} requires approval")
        if step.get("operation_type") == "outbound" and step.get(
                "effect") == "external" and not (
                (step.get("inputs") or {}).get("to")):
            raise AssignmentPlanError(
                f"outbound step {step['step_id']} requires a recipient")
        outbound_inputs = step.get("inputs") or {}
        proposed_attachment_ids = [
            str(item).strip() for item in (
                outbound_inputs.get("attachment_ids") or [])
            if str(item).strip()
        ]
        proposed_attachment_hashes = {
            str(key).strip() for key in (
                outbound_inputs.get("attachment_hashes") or {})
            if str(key).strip()
        }
        if proposed_attachment_ids or proposed_attachment_hashes:
            if set(proposed_attachment_ids) != proposed_attachment_hashes:
                raise AssignmentPlanError(
                    f"outbound step {step['step_id']} must bind every "
                    "attachment id to exactly one sha256")
    seen_deliverable_ids = set()
    seen_deliverable_steps = set()
    for item in assignment.get("deliverables") or []:
        deliverable_id = str(item.get("deliverable_id") or "")
        if not deliverable_id or deliverable_id in seen_deliverable_ids:
            raise AssignmentPlanError(
                "deliverable identities must be present and unique")
        seen_deliverable_ids.add(deliverable_id)
        step_id = str(item.get("step_id") or "")
        if step_id not in known_steps:
            raise AssignmentPlanError(
                f"deliverable {deliverable_id} references missing step "
                f"{step_id}")
        if step_id in seen_deliverable_steps:
            raise AssignmentPlanError(
                f"more than one deliverable claims step {step_id}")
        seen_deliverable_steps.add(step_id)
        step = next(s for s in assignment["steps"] if s["step_id"] == step_id)
        output_kind = {
            "artifact.document": "document",
            "artifact.spreadsheet": "spreadsheet",
            "artifact.presentation": "presentation",
            "email.draft": "email_draft",
            "email.send_outlook": "email",
            "assignment.controlled_outbox": "email",
        }.get(str(step.get("adapter") or ""))
        if output_kind != str(item.get("kind") or ""):
            raise AssignmentPlanError(
                f"deliverable {deliverable_id} is '{item.get('kind')}' but "
                f"step {step_id} produces '{output_kind or 'nothing'}'")
    if not assignment.get("completion_criteria"):
        raise AssignmentPlanError(
            "the assignment must declare acceptance criteria")
