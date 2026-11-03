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
    canonical_sha256,
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


class StepUpdate(BaseModel):
    """Bounded rewiring of pending/failed (or invalidated) work.

    The objective, adapter, effect, authority and required flag are not
    mutable here: a plan change may reroute data/dependencies, not weaken
    the job's obligations or convert work into a different effect class.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=80)
    depends_on: Optional[List[str]] = None
    inputs: Optional[Dict[str, Any]] = None
    requires: Optional[List[Dict[str, Any]]] = None


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
    update_steps: List[StepUpdate] = Field(default_factory=list)
    add_facts: List[Dict[str, Any]] = Field(default_factory=list)
    set_requires: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict)


def _task_version(record: Mapping[str, Any]) -> Optional[int]:
    """The authoritative lifecycle CAS state version (not objective revision)."""
    value = record.get("task_version")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _material_patch_digest(patch: Mapping[str, Any]) -> str:
    """Canonical identity of the MATERIAL patch content."""
    material = {
        "base_task_version": int(patch.get("base_task_version") or 0),
        "base_plan_revision": int(patch.get("base_plan_revision") or 0),
        "invalidate_steps": sorted({
            str(item) for item in patch.get("invalidate_steps") or []}),
        "remove_steps": sorted({
            str(item) for item in patch.get("remove_steps") or []}),
        "add_steps": sorted(
            [dict(item) for item in patch.get("add_steps") or []],
            key=lambda item: str(item.get("step_id") or "")),
        "update_steps": sorted(
            [dict(item) for item in patch.get("update_steps") or []],
            key=lambda item: str(item.get("step_id") or "")),
        "add_facts": sorted(
            [dict(item) for item in patch.get("add_facts") or []],
            key=lambda item: str(item.get("fact_id") or "")),
        "set_requires": {
            str(key): value for key, value in sorted(
                (patch.get("set_requires") or {}).items())
        },
    }
    return canonical_sha256(material)


def _operation_is_active(operation: Any) -> bool:
    if not isinstance(operation, Mapping):
        return False
    status = str(operation.get("status") or "").lower()
    if status in ("running", "uncertain", "dispatching", "claimed"):
        return True
    execution = operation.get("execution")
    if isinstance(execution, Mapping):
        if execution.get("outcome_unknown") is True:
            return True
        if str(execution.get("status") or "").lower() in (
                "dispatching", "claimed", "running", "uncertain"):
            return True
    return False


def _requirements_weakened(
    old: Sequence[Mapping[str, Any]],
    new: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Return old predicates erased by the proposed replacement list."""
    new_hashes = {canonical_sha256(dict(item)) for item in new}
    return [
        str(item) for item in old
        if canonical_sha256(dict(item)) not in new_hashes
    ]


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
    if current_version is None:
        errors.append(
            "task state version is missing or ambiguous; refresh the "
            "proposal against the durable task record")
    elif normalized.base_task_version != current_version:
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
        elif bool(step.get("required", True)):
            errors.append(
                f"required step {step_id} cannot be removed by a model "
                f"patch; an authorized objective revision is required")
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
            from core.assignment_executor import default_adapter_registry
            adapter = default_adapter_registry.get(raw.adapter)
            if adapter is None:
                errors.append(
                    f"added step {step_id} names unregistered adapter "
                    f"{raw.adapter!r}")
            else:
                metadata = dict(adapter.metadata or {})
                expected_effect = metadata.get("effect")
                if (expected_effect and expected_effect != "declared"
                        and str(raw.effect) != str(expected_effect)):
                    errors.append(
                        f"added step {step_id} declares effect {raw.effect!r} "
                        f"but adapter {raw.adapter!r} is {expected_effect!r}")
                required_actions = set(metadata.get("required_actions") or [])
                if required_actions and not required_actions <= set(
                        assignment.get("authorized_actions") or []):
                    errors.append(
                        f"added step {step_id} requires actions "
                        f"{sorted(required_actions)} outside the accepted "
                        f"authority")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"added step {step_id} adapter contract: {exc}")
        if raw.adapter == "action.registry":
            try:
                from core.action_registry import action_registry
                from core.assignment_planner import _registered_action_effect
                action_name = str(
                    (raw.inputs or {}).get("action") or "").strip()
                action = action_registry.get_action(action_name)
                if action is None:
                    errors.append(
                        f"added step {step_id} names unregistered action "
                        f"{action_name!r}")
                else:
                    actual = _registered_action_effect(action)
                    if str(raw.effect) != actual:
                        errors.append(
                            f"added step {step_id} declares {raw.effect!r} "
                            f"but action {action_name!r} is {actual!r}")
                    required = (
                        "outbound" if actual == "external" else "retrieve")
                    if required not in set(
                            assignment.get("authorized_actions") or []):
                        errors.append(
                            f"added step {step_id} requires action "
                            f"{required!r} outside the accepted authority")
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    f"added step {step_id} action contract: {exc}")
    invalidated = {str(item) for item in normalized.invalidate_steps}
    updated_seen = set()
    for raw in normalized.update_steps:
        step_id = raw.step_id
        if step_id in updated_seen:
            errors.append(f"step {step_id} is updated more than once")
            continue
        updated_seen.add(step_id)
        step = by_id.get(step_id)
        if step is None:
            errors.append(f"update names unknown step {step_id!r}")
            continue
        if step.get("status") in _IMMUTABLE_STATUSES:
            errors.append(
                f"step {step_id} is {step.get('status')}; a running or "
                f"uncertain effect cannot be rewired by replanning")
            continue
        if step.get("status") not in ("pending", "failed") and (
                step_id not in invalidated):
            errors.append(
                f"step {step_id} is {step.get('status')}; only pending, "
                f"failed or invalidated work may be updated")
            continue
        if (raw.depends_on is None and raw.inputs is None
                and raw.requires is None):
            errors.append(f"update for {step_id} has no changes")
            continue
        depends = (raw.depends_on if raw.depends_on is not None
                   else list(step.get("depends_on") or []))
        for dependency in depends:
            if dependency == step_id:
                errors.append(f"step {step_id} cannot depend on itself")
            elif dependency not in seen:
                errors.append(
                    f"updated step {step_id} depends on unknown step "
                    f"{dependency!r}")
        merged_inputs = (raw.inputs if raw.inputs is not None
                         else step.get("inputs") or {})
        merged_requires = (raw.requires if raw.requires is not None
                           else step.get("requires") or [])
        try:
            new_step(
                step_id=step_id, title=step.get("title") or step_id,
                operation_type=step.get("operation_type") or "retrieve",
                adapter=step.get("adapter") or "",
                depends_on=depends, inputs=merged_inputs,
                effect=step.get("effect") or "local",
                requires=merged_requires)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"updated step {step_id}: {exc}")
    # The FULL affected closure, not only explicitly named roots. Validate
    # every member against both plan status and durable operation truth.
    operations = {
        str(op.get("operation_id")): op
        for op in record.get("operations") or []
        if isinstance(op, dict) and op.get("operation_id")
    }
    roots = list(normalized.invalidate_steps)
    roots.extend(raw.step_id for raw in normalized.update_steps)
    roots.extend(normalized.set_requires)
    fact_ids = {
        str(item.get("fact_id")) for item in normalized.add_facts
        if isinstance(item, dict) and item.get("fact_id")
    }
    for step in steps:
        for requirement in step.get("requires") or []:
            if (requirement.get("kind") == "fact"
                    and str(requirement.get("fact_id") or "") in fact_ids):
                roots.append(str(step.get("step_id") or ""))
    roots = [item for item in dict.fromkeys(roots) if item]
    affected_closure = downstream_step_ids(assignment, roots) if roots else []
    for step_id in affected_closure:
        step = by_id.get(step_id)
        if step is None:
            errors.append(f"affected closure names unknown step {step_id!r}")
            continue
        if step.get("status") in _IMMUTABLE_STATUSES:
            errors.append(
                f"affected step {step_id} is {step.get('status')}; a running "
                f"or uncertain effect cannot be changed by replanning")
        operation = operations.get(str(step.get("operation_id") or ""))
        if _operation_is_active(operation):
            errors.append(
                f"affected step {step_id} has an active/uncertain durable "
                f"operation; reconcile it before replanning")
    for step_id in normalized.remove_steps:
        step = by_id.get(step_id)
        if step is not None and _operation_is_active(
                operations.get(str(step.get("operation_id") or ""))):
            errors.append(
                f"remove step {step_id} has an active/uncertain durable "
                f"operation")
    try:
        normalized_facts = normalize_facts(normalized.add_facts)
    except ValueError as exc:
        normalized_facts = []
        errors.append(f"facts: {exc}")
    for fact in normalized_facts:
        if str(fact.get("evidence_state") or "") != "established":
            continue
        bound_refs = [
            ref for ref in (fact.get("source_refs") or [])
            if isinstance(ref, dict) and any(
                ref.get(key) for key in
                ("resource_id", "source_id", "id", "uri", "sha256"))
        ]
        if not bound_refs and not fact.get("authority_ref"):
            errors.append(
                f"fact {fact.get('fact_id')} is marked established without "
                f"accepted evidence identity or authored confirmation")
    for step_id, requirements in normalized.set_requires.items():
        if step_id not in seen:
            errors.append(f"set_requires names unknown step {step_id!r}")
            continue
        step = by_id.get(step_id)
        if step is None:
            errors.append(f"set_requires names unknown step {step_id!r}")
            continue
        if step.get("status") in _IMMUTABLE_STATUSES:
            errors.append(
                f"set_requires cannot change {step_id} while it is "
                f"{step.get('status')}")
            continue
        if step.get("status") not in ("pending", "failed") and (
                step_id not in invalidated):
            errors.append(
                f"set_requires cannot change {step_id} while it is "
                f"{step.get('status')}")
            continue
        try:
            candidate = normalize_requirements(requirements)
        except ValueError as exc:
            errors.append(f"{step_id} requirements: {exc}")
            continue
        erased = _requirements_weakened(
            step.get("requires") or [], candidate)
        if erased:
            errors.append(
                f"set_requires would erase an existing requirement on "
                f"{step_id}; a model patch cannot weaken the objective")
    for raw in normalized.update_steps:
        step = by_id.get(raw.step_id)
        if step is not None and raw.requires is not None:
            try:
                candidate = normalize_requirements(raw.requires)
            except ValueError as exc:
                errors.append(f"{raw.step_id} requirements: {exc}")
                continue
            erased = _requirements_weakened(
                step.get("requires") or [], candidate)
            if erased:
                errors.append(
                    f"update_steps would erase an existing requirement on "
                    f"{raw.step_id}; a model patch cannot weaken the objective")
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
    digest = _material_patch_digest(normalized.model_dump())
    registry = (record.get("assignment") or {}).get("patch_registry") or {}
    existing = registry.get(normalized.patch_id) if isinstance(
        registry, Mapping) else None
    if existing is None:
        legacy = next((
            item for item in (
                (record.get("assignment") or {}).get("patch_history") or [])
            if item.get("patch_id") == normalized.patch_id), None)
        if legacy is not None:
            raise PlanPatchError(
                "patch history lacks a material digest; refresh the "
                "proposal against current state")
    if existing is not None:
        stored_digest = str(existing.get("material_digest") or "")
        if stored_digest and stored_digest != digest:
            raise PlanPatchError(
                "patch_id conflict: the same identity carries different "
                "material content")
        if stored_digest == digest:
            stored_result = existing.get("result")
            return {
                **(copy.deepcopy(stored_result)
                   if isinstance(stored_result, dict) else {}),
                "status": "already_applied",
                "patch_id": normalized.patch_id,
                "assignment": record.get("assignment"),
            }
        raise PlanPatchError(
            "patch identity has no material digest; refresh the proposal")
    checked = validate_plan_patch(normalized.model_dump(), record)
    if not checked["valid"]:
        raise PlanPatchError("; ".join(checked["errors"]))
    normalized = checked["patch"]

    def compute(record, assignment):
        # Duplicate identity is resolved BEFORE the version guard: a
        # concurrent winner has already advanced task_version, but replaying
        # the exact same material must return the first result, not look like
        # a stale proposal.
        registry = assignment.get("patch_registry") or {}
        duplicate = registry.get(normalized["patch_id"]) if isinstance(
            registry, Mapping) else None
        if duplicate is not None:
            stored_digest = str(duplicate.get("material_digest") or "")
            if stored_digest and stored_digest != digest:
                raise PlanPatchError(
                    "patch_id conflict: the same identity carries different "
                    "material content")
            if stored_digest == digest:
                stored_result = duplicate.get("result")
                return copy.deepcopy(assignment), {
                    **(copy.deepcopy(stored_result)
                       if isinstance(stored_result, dict) else {}),
                    "status": "already_applied",
                    "patch_id": normalized["patch_id"],
                }
            raise PlanPatchError(
                "patch identity has no material digest; refresh the proposal")
        # Re-check inside the CAS callback: another writer may have changed
        # the plan after the pre-check. task_version is the lifecycle CAS
        # state version; task_revision.revision is the objective revision and
        # is deliberately NOT used here.
        current_task_version = _task_version(record)
        if (current_task_version is None
                or current_task_version != normalized["base_task_version"]):
            raise PlanPatchError(
                "stale task version: the durable task state changed after "
                "the proposal")
        if int(assignment.get("plan_revision") or 1) != int(
                normalized["base_plan_revision"]):
            raise PlanPatchError(
                "stale plan revision: the plan changed after proposal")
        history = list(assignment.get("patch_history") or [])
        steps = list(assignment.get("steps") or [])
        by_id = {str(step.get("step_id") or ""): step for step in steps}
        operations = {
            str(op.get("operation_id")): op
            for op in record.get("operations") or []
            if isinstance(op, dict) and op.get("operation_id")
        }
        roots: List[str] = []
        for step_id in normalized["invalidate_steps"]:
            step = by_id.get(str(step_id))
            if step is None:
                raise PlanPatchError(f"unknown step {step_id!r}")
            roots.append(str(step_id))
        roots.extend(
            raw["step_id"] for raw in normalized["update_steps"])
        roots.extend(normalized["set_requires"])
        fact_ids = {
            str(item.get("fact_id")) for item in normalized["add_facts"]
            if isinstance(item, dict) and item.get("fact_id")
        }
        for step in steps:
            for requirement in step.get("requires") or []:
                if (requirement.get("kind") == "fact"
                        and str(requirement.get("fact_id") or "")
                        in fact_ids):
                    roots.append(str(step.get("step_id") or ""))
        roots = [item for item in dict.fromkeys(roots) if item]
        affected = downstream_step_ids(assignment, roots) if roots else []
        for step_id in affected:
            step = by_id.get(step_id)
            if step is None:
                raise PlanPatchError(
                    f"affected closure names unknown step {step_id!r}")
            if step.get("status") in _IMMUTABLE_STATUSES:
                raise PlanPatchError(
                    f"affected step {step_id} is {step.get('status')}; a "
                    f"running or uncertain effect cannot be changed by "
                    f"replanning")
            if _operation_is_active(
                    operations.get(str(step.get("operation_id") or ""))):
                raise PlanPatchError(
                    f"affected step {step_id} has an active or uncertain "
                    f"durable operation; reconcile it before replanning")
        removed = set(normalized["remove_steps"])
        for step_id in removed:
            step = by_id.get(step_id)
            if step is None:
                raise PlanPatchError(f"unknown step {step_id!r}")
            if step.get("status") != "pending":
                raise PlanPatchError(
                    f"step {step_id} is {step.get('status')}; only pending "
                    f"work may be removed")
            if bool(step.get("required", True)):
                raise PlanPatchError(
                    f"required step {step_id} cannot be removed by a model "
                    f"patch; an authorized objective revision is required")
            if _operation_is_active(
                    operations.get(str(step.get("operation_id") or ""))):
                raise PlanPatchError(
                    f"step {step_id} has an active or uncertain durable "
                    f"operation")
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
        updated_steps: List[str] = []
        for raw in normalized["update_steps"]:
            target = step_by_id(new_plan, raw["step_id"])
            if target is None:
                raise PlanPatchError(
                    f"update names unknown step {raw['step_id']!r}")
            if raw.get("depends_on") is not None:
                target["depends_on"] = list(raw["depends_on"])
            if raw.get("inputs") is not None:
                target["inputs"] = copy.deepcopy(raw["inputs"])
            if raw.get("requires") is not None:
                target["requires"] = normalize_requirements(
                    raw["requires"])
            target["updated_at"] = _utc_now_iso()
            updated_steps.append(raw["step_id"])
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
        result_summary = {
            "status": "applied",
            "patch_id": normalized["patch_id"],
            "material_digest": digest,
            "affected_steps": affected,
            "updated_steps": updated_steps,
            "retained_steps": retained,
            "plan_revision": new_plan["plan_revision"],
        }
        new_plan["last_transition"] = {
            "kind": "plan_patch",
            "patch_id": normalized["patch_id"],
            "material_digest": digest,
            "reason": normalized["reason"][:500],
            "affected_steps": affected,
            "updated_steps": updated_steps,
            "retained_steps": retained,
            "at": _utc_now_iso(),
        }
        history.append({
            "patch_id": normalized["patch_id"],
            "base_task_version": normalized["base_task_version"],
            "base_plan_revision": normalized["base_plan_revision"],
            "material_digest": digest,
            "reason": normalized["reason"][:500],
            "observations": copy.deepcopy(normalized["observations"]),
            "affected_steps": affected,
            "updated_steps": updated_steps,
            "retained_steps": retained,
            "at": _utc_now_iso(),
        })
        new_plan["patch_history"] = history[-MAX_PATCH_HISTORY:]
        # Durable replay identity is separate from the bounded display
        # history: pruning a display entry must not re-enable an old effect.
        patch_registry = dict(assignment.get("patch_registry") or {})
        patch_registry[normalized["patch_id"]] = {
            "material_digest": digest,
            "base_task_version": normalized["base_task_version"],
            "base_plan_revision": normalized["base_plan_revision"],
            "result": copy.deepcopy(result_summary),
            "at": _utc_now_iso(),
        }
        new_plan["patch_registry"] = patch_registry
        new_plan["updated_at"] = _utc_now_iso()
        try:
            validate_assignment(new_plan)
        except Exception as exc:  # noqa: BLE001
            raise PlanPatchError(f"patched plan is invalid: {exc}") from exc
        return new_plan, result_summary

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
