"""One semantic validator for goal-run plans and REPLAN decisions.

Router acceptance, corrective feedback and executor consumption all use this
module. JSON shape alone is not enough: a plan is executable only when its
steps are supported, uniquely identified, ordered, referentially complete and
free of authority-expanding declarations.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional

SUPPORTED_STEP_KINDS = (
    "canvas_work",
    "computer_use_work",
    "integration_action",
    "human_checkpoint",
    "wait_for",
)
# Non-executable representations of assignment work in the shared GoalRun
# plan column. The native executor refuses these; only AssignmentExecutor
# reads them.
NON_EXECUTABLE_PROJECTION_KINDS = ("operation",)
FORBIDDEN_STEP_KEYS = {
    "authorized_actions",
    "standing_authority",
    "permissions",
    "permission_scope",
    "role_override",
}
_MAX_STEPS = 200
_LEGACY_CANVAS_KIND = "canvas_work"


def normalize_step_kind(step: Any) -> str:
    """One normalization shared by validation and executor dispatch.

    Legacy plans may omit ``kind`` (or carry an empty/whitespace value); those
    are canvas work. Everything else is trimmed and lower-cased so a model's
    ``Canvas_Work`` cannot validate here and then miss the executor branch.
    """
    if isinstance(step, Mapping):
        raw = step.get("kind")
    else:
        raw = step
    text = str(raw or "").strip().lower()
    return text or _LEGACY_CANVAS_KIND


def is_executable_step_kind(kind: Any) -> bool:
    return normalize_step_kind(kind) in SUPPORTED_STEP_KINDS


def validate_goal_plan(
    plan: Any,
    *,
    target_step: Optional[str] = None,
    require_non_empty: bool = True,
    action_registry: Any = None,
    allowed_extra_kinds: Iterable[str] = (),
) -> List[str]:
    """Return concise validation errors; an empty list means executable shape.

    ``allowed_extra_kinds`` is for non-executable plan PROJECTIONS that share
    the GoalRun row (e.g. the assignment executor's ``operation`` steps). The
    router/REPLAN call sites leave it empty, so a model cannot propose a
    projection kind as an executable goal plan.
    """
    errors: List[str] = []
    if not isinstance(plan, list):
        return ["new_plan must be a list of step objects"]
    if require_non_empty and not plan:
        return ["new_plan must contain at least one step"]
    if len(plan) > _MAX_STEPS:
        errors.append(f"new_plan exceeds {_MAX_STEPS} steps")
    supported_kinds = set(SUPPORTED_STEP_KINDS) | {
        normalize_step_kind(kind) for kind in allowed_extra_kinds if kind}
    seen: Dict[str, int] = {}
    all_ids: Dict[str, int] = {}
    for index, item in enumerate(plan):
        if isinstance(item, dict):
            item_id = str(item.get("id") or "").strip()
            if item_id and item_id not in all_ids:
                all_ids[item_id] = index
    for index, step in enumerate(plan):
        where = f"step[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{where} must be an object")
            continue
        step_id = str(step.get("id") or "").strip()
        if not step_id:
            errors.append(f"{where} requires a non-empty id")
        elif step_id in seen:
            errors.append(f"duplicate step id {step_id!r}")
        else:
            seen[step_id] = index
        forbidden = sorted(FORBIDDEN_STEP_KEYS & set(step))
        if forbidden:
            errors.append(
                f"{where} declares forbidden authority fields: "
                + ", ".join(forbidden))
        kind = normalize_step_kind(step)
        if kind not in supported_kinds:
            errors.append(f"{where} has unsupported kind {kind!r}")
            continue
        if kind == "canvas_work":
            if not str(step.get("title") or "").strip():
                errors.append(f"{where} canvas_work requires a title")
            if step.get("canvas_type") is not None and not isinstance(
                    step.get("canvas_type"), str):
                errors.append(f"{where} canvas_type must be a string")
        elif kind == "computer_use_work":
            if not str(
                    step.get("directive") or step.get("title") or "").strip():
                errors.append(
                    f"{where} computer_use_work requires a directive/title")
        elif kind == "integration_action":
            action = str(
                step.get("action") or step.get("title") or "").strip()
            if not action:
                errors.append(
                    f"{where} integration_action requires an action")
            elif action_registry is not None and action_registry.get_action(
                    action) is None:
                errors.append(
                    f"{where} names unregistered action {action!r}")
            arguments = step.get("arguments")
            if arguments is not None and not isinstance(arguments, dict):
                errors.append(f"{where} arguments must be an object")
        elif kind == "human_checkpoint":
            if not str(step.get("title") or "").strip():
                errors.append(f"{where} human_checkpoint requires a title")
        elif kind == "wait_for":
            spec = step.get("wait_spec")
            if not isinstance(spec, dict):
                errors.append(f"{where} wait_for requires a wait_spec object")
            elif not str(
                    spec.get("event") or spec.get("timer_seconds") or ""):
                errors.append(
                    f"{where} wait_spec requires an event or timer_seconds")
        depends = step.get("depends_on")
        if depends is not None:
            if not isinstance(depends, list):
                errors.append(f"{where} depends_on must be a list")
            else:
                for dependency in depends:
                    dep = str(dependency or "").strip()
                    if not dep:
                        errors.append(f"{where} has an empty dependency")
                    elif dep == step_id:
                        errors.append(f"{where} cannot depend on itself")
                    elif dep not in all_ids:
                        errors.append(
                            f"{where} depends on unknown step {dep!r}")
                    elif all_ids[dep] >= index:
                        errors.append(
                            f"{where} dependency {dep!r} must precede it")
    if target_step:
        target = str(target_step).strip()
        if target and target not in seen:
            errors.append(f"target_step {target!r} is not in the plan")
    return errors


def validate_replan_decision(
    decision: Dict[str, Any],
    *,
    action_registry: Any = None,
) -> List[str]:
    """Semantic errors for one proposed REPLAN decision."""
    if not isinstance(decision, dict):
        return ["decision must be an object"]
    if str(decision.get("decision") or "").strip().upper() != "REPLAN":
        return ["decision is not REPLAN"]
    return validate_goal_plan(
        decision.get("new_plan"),
        target_step=decision.get("target_step"),
        action_registry=action_registry,
    )


def validate_assignment_projection(
    plan: Any,
    *,
    require_non_empty: bool = True,
) -> List[str]:
    """Validate the assignment-owned read model stored in ``GoalRun.plan``.

    The canonical projection is operation-only, uses the assignment step's
    stable id, and keeps dependency order. This is deliberately separate from
    executable goal-plan validation: agreement between this validator and the
    executor representation is tested through actual consumption, not just an
    empty error list.
    """
    errors: List[str] = []
    if not isinstance(plan, list):
        return ["assignment projection must be a list of step objects"]
    if require_non_empty and not plan:
        return ["assignment projection must contain at least one step"]
    if len(plan) > _MAX_STEPS:
        errors.append(f"assignment projection exceeds {_MAX_STEPS} steps")
    all_ids: Dict[str, int] = {}
    for index, item in enumerate(plan):
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("id") or "").strip()
        if item_id and item_id not in all_ids:
            all_ids[item_id] = index
    seen: Dict[str, int] = {}
    for index, step in enumerate(plan):
        where = f"projection[{index}]"
        if not isinstance(step, Mapping):
            errors.append(f"{where} must be an object")
            continue
        step_id = str(step.get("id") or "").strip()
        if not step_id:
            errors.append(f"{where} requires a stable non-empty id")
        elif step_id in seen:
            errors.append(f"duplicate projection id {step_id!r}")
        else:
            seen[step_id] = index
        kind = normalize_step_kind(step)
        if kind not in NON_EXECUTABLE_PROJECTION_KINDS:
            errors.append(
                f"{where} has {kind!r}; an assignment projection may only "
                f"contain {list(NON_EXECUTABLE_PROJECTION_KINDS)}")
        if not str(step.get("title") or "").strip():
            errors.append(f"{where} operation projection requires a title")
        operation_type = step.get("operation_type")
        if operation_type is not None and not isinstance(operation_type, str):
            errors.append(f"{where} operation_type must be a string")
        status = step.get("status")
        if status is not None and not isinstance(status, str):
            errors.append(f"{where} status must be a string")
        depends = step.get("depends_on")
        if depends is not None:
            if not isinstance(depends, list):
                errors.append(f"{where} depends_on must be a list")
            else:
                for dependency in depends:
                    dep = str(dependency or "").strip()
                    if not dep:
                        errors.append(f"{where} has an empty dependency")
                    elif dep == step_id:
                        errors.append(
                            f"{where} cannot depend on itself")
                    elif dep not in all_ids:
                        errors.append(
                            f"{where} depends on unknown step {dep!r}")
    return errors


def confidence_is_valid(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and 0.0 <= number <= 1.0
