"""One semantic validator for goal-run plans and REPLAN decisions.

Router acceptance, corrective feedback and executor consumption all use this
module. JSON shape alone is not enough: a plan is executable only when its
steps are supported, uniquely identified, ordered, referentially complete and
free of authority-expanding declarations.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional

SUPPORTED_STEP_KINDS = (
    "canvas_work",
    "computer_use_work",
    "integration_action",
    "human_checkpoint",
    "wait_for",
)
FORBIDDEN_STEP_KEYS = {
    "authorized_actions",
    "standing_authority",
    "permissions",
    "permission_scope",
    "role_override",
}
_MAX_STEPS = 200


def validate_goal_plan(
    plan: Any,
    *,
    target_step: Optional[str] = None,
    require_non_empty: bool = True,
    action_registry: Any = None,
) -> List[str]:
    """Return concise validation errors; an empty list means executable shape."""
    errors: List[str] = []
    if not isinstance(plan, list):
        return ["new_plan must be a list of step objects"]
    if require_non_empty and not plan:
        return ["new_plan must contain at least one step"]
    if len(plan) > _MAX_STEPS:
        errors.append(f"new_plan exceeds {_MAX_STEPS} steps")
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
        kind = str(step.get("kind") or "canvas_work").strip().lower()
        if kind not in SUPPORTED_STEP_KINDS:
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


def confidence_is_valid(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and 0.0 <= number <= 1.0
