"""Validated, atomic plan-patch adoption for employee-owned assignments.

The reasoning layer may propose a bounded change (add supported work, reopen
affected work, add a fact, or tighten a requirement). This module validates
the proposal against the current durable record and adopts it through the
existing ``TaskLifecycle.mutate_assignment`` CAS. The callback is pure: it
performs no provider call, file write, model inference or notification.

The existing step/operation records remain the only execution truth. A patch
never resets budgets, grants authority, erases criteria or replaces a running
or uncertain effect's operation.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from core.assignment_plan import (
    downstream_step_ids,
    new_step,
    step_by_id,
    validate_assignment,
)
from core.assignment_readiness import normalize_facts, normalize_requirements

PATCH_SCHEMA = "atom-employee-plan-patch-1"
MAX_ADDED_STEPS = 8
MAX_PATCH_HISTORY = 20
_IMMUTABLE_STATUSES = frozenset({"running", "uncertain"})


class PlanPatchError(Exception):
    """A proposed patch is invalid for the current durable state."""


class StepPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    operation_type: str = Field(min_length=1, max_length=40)
    adapter: str = Field(min_length=1, max_length=80)
    depends_on: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    effect: str = Field(default="local", max_length=20)
    requires: List[Dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False
    approval_purpose: str = Field(default="", max_length=300)
    required: bool = True


class PlanPatchProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patch_id: str = Field(min_length=1, max_length=120)
    base_task_version: int = Field(ge=0)
    base_plan_revision: int = Field(ge=0)
    reason: str = Field(default="", max_length=800)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    invalidate_steps: List[str] = Field(default_factory=list)
    remove_steps: List[str] = Field(default_factory=list)
    add_steps: List[StepPatch] = Field(default_factory=list)
    add_facts: List[Dict[str, Any]] = Field(default_factory=list)
    set_requires: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict)


def _task_version(record: Mapping[str, Any]) -> int:
    try:
        return int((record.get("task_revision") or {}).get("revision") or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_patch(patch: Any) -> PlanPatchProposal:
    if isinstance(patch, BaseModel):
        patch = patch.model_dump()
    try:
        return PlanPatchProposal.model_validate(dict(patch or {}))
    except Exception as exc:  # noqa: BLE001
        raise PlanPatchError(f"invalid plan patch: {exc}") from exc


def validate_plan_patch(
    patch: Any,
    record: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return typed errors without mutating durable state."""
    try:
        normalized = _normalize_patch(patch)
    except PlanPatchError as exc:
        return {"valid": False, "errors": [str(exc)], "patch": None}
    errors: List[str] = []
    current_version = _task_version(record)
    assignment = record.get("assignment") or {}
    current_revision = int(assignment.get("plan_revision") or 1)
    if normalized.base_task_version != current_version:
        errors.append(
            f"stale task version: base {normalized.base_task_version} is "
            f"not current {current_version}")
    if normalized.base_plan_revision != current_revision:
        errors.append(
            f"stale plan revision: base {normalized.base_plan_revision} is "
            f"not current {current_revision}")
    if not normalized.reason.strip():
        errors.append("a plan patch requires a concise reason")
    if not normalized.observations:
        errors.append("a plan patch requires at least one observation reference")
    if len(normalized.add_steps) > MAX_ADDED_STEPS:
        errors.append(f"at most {MAX_ADDED_STEPS} steps may be added")
    steps = list(assignment.get("steps") or [])
    by_id = {str(step.get("step_id") or ""): step for step in steps}
    for step_id in normalized.invalidate_steps:
        step = by_id.get(str(step_id))
        if step is None:
            errors.append(f"invalidate names unknown step {step_id!r}")
        elif step.get("status") in _IMMUTABLE_STATUSES:
            errors.append(
                f"step {step_id} is {step.get('status')}; a running or "
                f"uncertain effect cannot be invalidated by replanning")
    for step_id in normalized.remove_steps:
        step = by_id.get(str(step_id))
        if step is None:
            errors.append(f"remove names unknown step {step_id!r}")
        elif step.get("status") != "pending":
            errors.append(
                f"step {step_id} is {step.get('status')}; only pending work "
                f"may be removed")
        elif any(str(step_id) in (item.get("depends_on") or [])
                 for item in steps
                 if item.get("step_id") != step_id):
            errors.append(
                f"step {step_id} has dependents; invalidate them instead of "
                f"removing the prerequisite")
    seen = set(by_id)
    for raw in normalized.add_steps:
        step_id = raw.step_id
        if step_id in seen:
            errors.append(f"added step id {step_id!r} already exists")
            continue
        seen.add(step_id)
        for dependency in raw.depends_on:
            if dependency not in seen:
                errors.append(
                    f"added step {step_id} depends on unknown step "
                    f"{dependency!r}")
        if str(raw.effect) not in ("read_only", "local", "external"):
            errors.append(f"added step {step_id} has invalid effect")
        if raw.effect == "external" and not raw.approval_required:
            errors.append(
                f"added step {step_id} is external and requires explicit "
                f"approval")
        try:
            new_step(
                step_id=raw.step_id, title=raw.title,
                operation_type=raw.operation_type, adapter=raw.adapter,
                depends_on=raw.depends_on, inputs=raw.inputs,
                effect=raw.effect,
                approval_required=raw.approval_required,
                approval_purpose=raw.approval_purpose,
                required=raw.required, requires=raw.requires)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"added step {step_id}: {exc}")
    try:
        normalize_facts(normalized.add_facts)
    except ValueError as exc:
        errors.append(f"facts: {exc}")
    for step_id, requirements in normalized.set_requires.items():
        if step_id not in seen:
            errors.append(f"set_requires names unknown step {step_id!r}")
            continue
        try:
            normalize_requirements(requirements)
        except ValueError as exc:
            errors.append(f"{step_id} requirements: {exc}")
    return {
        "valid": not errors,
        "errors": errors,
        "patch": normalized.model_dump() if not errors else None,
    }


def apply_plan_patch(
    lifecycle: Any,
    run_id: str,
    patch: Any,
    *,
    rationale: Optional[str] = None,
) -> Dict[str, Any]:
    """Adopt one patch atomically through the existing task lifecycle CAS."""
    record = lifecycle.get_task(run_id)
    if record is None:
        raise PlanPatchError(f"no task record on run {run_id}")
    normalized = _normalize_patch(patch)
    existing = next((
        item for item in (
            (record.get("assignment") or {}).get("patch_history") or [])
        if item.get("patch_id") == normalized.patch_id), None)
    if existing is not None:
        if (int(existing.get("base_task_version") or 0)
                == normalized.base_task_version
                and int(existing.get("base_plan_revision") or 0)
                == normalized.base_plan_revision):
            return {
                "status": "already_applied",
                "patch_id": normalized.patch_id,
                "assignment": record.get("assignment"),
            }
        raise PlanPatchError(
            "patch_id was reused for a different base revision")
    checked = validate_plan_patch(normalized.model_dump(), record)
    if not checked["valid"]:
        raise PlanPatchError("; ".join(checked["errors"]))
    normalized = checked["patch"]

    def compute(record, assignment):
        # Re-check inside the CAS callback: another writer may have changed
        # the plan after the pre-check.
        if _task_version(record) != normalized["base_task_version"]:
            raise PlanPatchError(
                "stale task version: the plan changed after proposal")
        if int(assignment.get("plan_revision") or 1) != int(
                normalized["base_plan_revision"]):
            raise PlanPatchError(
                "stale plan revision: the plan changed after proposal")
        history = list(assignment.get("patch_history") or [])
        duplicate = next((
            item for item in history
            if item.get("patch_id") == normalized["patch_id"]), None)
        if duplicate is not None:
            if (int(duplicate.get("base_task_version") or 0)
                    == normalized["base_task_version"]
                    and int(duplicate.get("base_plan_revision") or 0)
                    == normalized["base_plan_revision"]):
                return copy.deepcopy(assignment), {
                    "status": "already_applied",
                    "patch_id": normalized["patch_id"],
                }
            raise PlanPatchError(
                "patch_id was reused for a different base revision")
        steps = list(assignment.get("steps") or [])
        by_id = {str(step.get("step_id") or ""): step for step in steps}
        affected: List[str] = []
        for step_id in normalized["invalidate_steps"]:
            step = by_id.get(str(step_id))
            if step is None:
                raise PlanPatchError(f"unknown step {step_id!r}")
            if step.get("status") in _IMMUTABLE_STATUSES:
                raise PlanPatchError(
                    f"step {step_id} is {step.get('status')}; cannot "
                    f"invalidate it by replanning")
            affected.extend(downstream_step_ids(assignment, [step_id]))
        affected = list(dict.fromkeys(affected))
        removed = set(normalized["remove_steps"])
        for step_id in removed:
            step = by_id.get(step_id)
            if step is None:
                raise PlanPatchError(f"unknown step {step_id!r}")
            if step.get("status") != "pending":
                raise PlanPatchError(
                    f"step {step_id} is {step.get('status')}; only pending "
                    f"work may be removed")
        retained = [
            item.get("step_id") for item in steps
            if item.get("step_id") not in affected
            and item.get("step_id") not in removed
        ]
        new_plan = copy.deepcopy(assignment)
        new_plan["plan_revision"] = int(
            assignment.get("plan_revision") or 1) + 1
        kept_steps = []
        for item in new_plan.get("steps") or []:
            step_id = item.get("step_id")
            if step_id in removed:
                continue
            if step_id in affected:
                prior = list(item.get("prior_results") or [])
                if item.get("result") is not None or item.get(
                        "artifact_revision"):
                    prior.append({
                        "plan_revision": assignment.get("plan_revision"),
                        "status": item.get("status"),
                        "result": copy.deepcopy(item.get("result")),
                        "artifact_revision": item.get("artifact_revision"),
                        "reason": normalized["reason"][:300],
                    })
                item["prior_results"] = prior[-10:]
                item["status"] = "pending"
                item["operation_id"] = None
                item["result"] = None
                item["artifact_revision"] = None
                item["failure"] = None
                item["waiting"] = None
                item["approval_request"] = None
                item["standing_authority_receipt"] = None
                item["gap_ids"] = []
                item["updated_at"] = _utc_now_iso()
            kept_steps.append(item)
        for raw in normalized["add_steps"]:
            try:
                compiled = new_step(
                    step_id=raw["step_id"],
                    title=raw["title"],
                    operation_type=raw["operation_type"],
                    adapter=raw["adapter"],
                    depends_on=raw["depends_on"],
                    inputs=raw["inputs"],
                    effect=raw["effect"],
                    approval_required=raw["approval_required"],
                    approval_purpose=raw["approval_purpose"],
                    required=raw["required"],
                    requires=raw["requires"],
                )
            except Exception as exc:  # noqa: BLE001
                raise PlanPatchError(
                    f"added step {raw.get('step_id')}: {exc}") from exc
            kept_steps.append(compiled)
        new_plan["steps"] = kept_steps
        if normalized["add_facts"]:
            facts = {
                str(item.get("fact_id")): item
                for item in new_plan.get("facts") or []
            }
            for fact in normalize_facts(normalized["add_facts"]):
                facts[str(fact["fact_id"])] = fact
            new_plan["facts"] = list(facts.values())
        for step_id, requirements in normalized["set_requires"].items():
            target = step_by_id(new_plan, step_id)
            if target is None:
                raise PlanPatchError(
                    f"set_requires names unknown step {step_id!r}")
            target["requires"] = normalize_requirements(requirements)
            target["updated_at"] = _utc_now_iso()
        new_plan["status"] = "planned"
        new_plan["completed_at"] = None
        new_plan["last_transition"] = {
            "kind": "plan_patch",
            "patch_id": normalized["patch_id"],
            "reason": normalized["reason"][:500],
            "affected_steps": affected,
            "retained_steps": retained,
            "at": _utc_now_iso(),
        }
        history.append({
            "patch_id": normalized["patch_id"],
            "base_task_version": normalized["base_task_version"],
            "base_plan_revision": normalized["base_plan_revision"],
            "reason": normalized["reason"][:500],
            "observations": copy.deepcopy(normalized["observations"]),
            "affected_steps": affected,
            "retained_steps": retained,
            "at": _utc_now_iso(),
        })
        new_plan["patch_history"] = history[-MAX_PATCH_HISTORY:]
        new_plan["updated_at"] = _utc_now_iso()
        validate_assignment(new_plan)
        return new_plan, {
            "status": "applied",
            "patch_id": normalized["patch_id"],
            "affected_steps": affected,
            "retained_steps": retained,
            "plan_revision": new_plan["plan_revision"],
        }

    result = lifecycle.mutate_assignment(
        run_id, compute,
        rationale=rationale or (
            f"plan patch {normalized['patch_id']}: "
            f"{normalized['reason'][:300]}"))
    return {
        **(result if isinstance(result, dict) else {}),
        "assignment": lifecycle.get_assignment(run_id),
    }


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
