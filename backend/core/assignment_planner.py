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

from typing import Any, Dict, List, Optional, Sequence

from core.assignment_executor import default_adapter_registry
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


def _source_step(source: Dict[str, Any], index: int) -> Dict[str, Any]:
    kind = str(source.get("kind") or "").strip().lower()
    adapter = _SOURCE_ADAPTERS.get(kind)
    if not adapter:
        raise AssignmentPlanError(
            f"unsupported source kind '{kind}'; supported: "
            f"{sorted(_SOURCE_ADAPTERS)}")
    locator = str(
        source.get("path") or source.get("resource_id")
        or source.get("locator") or "").strip()
    if not locator:
        raise AssignmentPlanError(
            f"source {kind!r} requires an authorized path/resource locator")
    inputs: Dict[str, Any] = {"path": locator}
    if kind == "workbook":
        for key in ("sheet", "columns", "filters", "header_row", "max_rows"):
            if source.get(key) is not None:
                inputs[key] = source[key]
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
                "body": deliverable.get("body")
                or "Please see the prepared result.",
                "deliverable_id": str(
                    deliverable.get("deliverable_id")
                    or f"del-{step_id}"),
            },
            effect="local",
        )
        if not deliverable.get("send", False):
            return [draft]
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
        if not isinstance(rows, list) or not rows:
            raise AssignmentPlanError(
                "a spreadsheet deliverable requires explicit rows or a "
                "$ref to a prior read result")
        inputs["rows"] = rows
    else:
        content = deliverable.get("content")
        if not content and calculation_step:
            content = (
                "## Summary\n\n${" + calculation_step + ".value}\n\n"
                "## Sources\n\n- Authorized source")
        inputs["content"] = content or (
            f"## Summary\n\n{_bounded(objective, 1000)}\n\n"
            "## Sources\n\n- Authorized source")
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
    if adapter == "email.send_outlook" and not outbound.get("canvas_id"):
        raise AssignmentPlanError(
            "the Outlook send adapter requires an existing prepared canvas_id; "
            "without one, use a draft-only step")
    inputs: Dict[str, Any] = {
        "to": outbound.get("to") or [],
        "cc": outbound.get("cc") or [],
        "subject": outbound.get("subject") or "",
        "body": outbound.get("body") or "",
    }
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
    source_steps = [
        _source_step(dict(source), index + 1)
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
    if calculation and calculation.get("expression"):
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
    if calculation and not calculation.get("expression"):
        raise AssignmentPlanError(
            "a calculation requires an explicit expression; a method gap "
            "cannot be invented")

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
        send_steps = [_send_step(
            dict(outbound), step_id="send",
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

    actions = sorted({
        step.get("operation_type") for step in steps
        if step.get("operation_type")
    } | set(authorized_actions or []))

    assignment = new_assignment(
        objective=objective,
        employee_id=employee_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        teaching_snapshot=teaching,
        steps=steps,
        deliverables=deliverable_records,
        sources=[dict(source) for source in (sources or [])],
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
    deliverable_steps = {
        item.get("step_id") for item in assignment.get("deliverables") or []
    }
    for step in assignment["steps"]:
        if registry.get(step.get("adapter") or "") is None:
            raise AssignmentPlanError(
                f"step {step['step_id']} names unregistered adapter "
                f"'{step.get('adapter')}'")
        for dependency in step.get("depends_on") or []:
            if dependency not in known_steps:
                raise AssignmentPlanError(
                    f"step {step['step_id']} depends on missing step "
                    f"{dependency}")
        if step.get("effect") == "external" and not (
                (step.get("approval") or {}).get("required")
                or step.get("standing_authorization")):
            raise AssignmentPlanError(
                f"external step {step['step_id']} requires approval or "
                f"standing authorization")
        if step.get("operation_type") == "outbound" and step.get(
                "effect") == "external" and not (
                (step.get("inputs") or {}).get("to")):
            raise AssignmentPlanError(
                f"outbound step {step['step_id']} requires a recipient")
    for item in assignment.get("deliverables") or []:
        if item.get("required", True) and item.get("step_id") not in (
                deliverable_steps | known_steps):
            raise AssignmentPlanError(
                f"deliverable {item.get('deliverable_id')} references a "
                f"missing step")
    if not assignment.get("completion_criteria"):
        raise AssignmentPlanError(
            "the assignment must declare acceptance criteria")
