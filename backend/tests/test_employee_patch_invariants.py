"""Invariants for authoritative plan-patch identity and affected closure."""
from __future__ import annotations

import copy
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.assignment_plan import step_by_id
from core.employee_patch import PlanPatchError, apply_plan_patch
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import TaskLifecycle
from tests.test_assignment_executor import env, _patch_ready_assignment


def _patch(env, run_id, *, patch_id="inv-1", **overrides):
    record = env["lifecycle"].get_task(run_id)
    payload = {
        "patch_id": patch_id,
        "base_task_version": int(record["task_version"]),
        "base_plan_revision": record["assignment"]["plan_revision"],
        "reason": "new authoritative observation",
        "observations": [{"kind": "event", "id": "e1"}],
        "invalidate_steps": ["read-a"],
    }
    payload.update(overrides)
    return payload


def _fresh_lifecycle(env):
    return TaskLifecycle(
        GoalRunService(
            workspace_id="ws_assign", tenant_id="tenant_assign",
            session_factory=env["factory"]),
        GoalService(
            workspace_id="ws_assign", tenant_id="tenant_assign",
            session_factory=env["factory"]))


def test_transitive_uncertain_descendant_refuses_upstream_invalidation(env):
    run_id = _patch_ready_assignment(env)

    def mark_uncertain(record, assignment):
        updated = copy.deepcopy(assignment)
        step_by_id(updated, "use-a")["status"] = "uncertain"
        return updated, {}

    env["lifecycle"].mutate_assignment(
        run_id, mark_uncertain, rationale="effect outcome unknown")
    before = env["lifecycle"].get_assignment(run_id)
    with pytest.raises(PlanPatchError, match="uncertain|running|reconcil"):
        apply_plan_patch(
            env["lifecycle"], run_id,
            _patch(env, run_id, invalidate_steps=["read-a"]))
    after = env["lifecycle"].get_assignment(run_id)
    assert after["plan_revision"] == before["plan_revision"]
    assert step_by_id(after, "use-a") == step_by_id(before, "use-a")
    assert step_by_id(after, "read-a") == step_by_id(before, "read-a")
    assert after["authorized_actions"] == before["authorized_actions"]
    assert after["budget"] == before["budget"]
    assert env["lifecycle"].get_task(run_id)["operations"] == []


@pytest.mark.parametrize("mutation", ["facts", "teaching"])
def test_task_state_advance_without_plan_revision_refuses_old_patch(
        env, mutation):
    run_id = _patch_ready_assignment(env)
    stale = _patch(env, run_id, patch_id=f"inv-stale-{mutation}")
    before = env["lifecycle"].get_task(run_id)

    def change(record, assignment):
        updated = copy.deepcopy(assignment)
        if mutation == "facts":
            updated["facts"] = [{
                "fact_id": "eligibility", "value": False,
                "evidence_state": "established",
                "source_refs": [{"resource_id": "agreement-1",
                                 "version": "v9"}],
            }]
        else:
            snapshot = dict(updated.get("teaching_snapshot") or {})
            snapshot["revision"] = "teach-r9"
            updated["teaching_snapshot"] = snapshot
        return updated, {}

    env["lifecycle"].mutate_assignment(
        run_id, change, rationale=f"{mutation} changed")
    after = env["lifecycle"].get_task(run_id)
    assert after["task_version"] > before["task_version"]
    assert after["assignment"]["plan_revision"] == (
        before["assignment"]["plan_revision"])

    with pytest.raises(PlanPatchError, match="stale|version"):
        apply_plan_patch(env["lifecycle"], run_id, stale)

    fresh_patch = _patch(
        env, run_id, patch_id=f"inv-fresh-{mutation}",
        reason="proposal refreshed against newer state")
    applied = apply_plan_patch(_fresh_lifecycle(env), run_id, fresh_patch)
    assert applied["status"] == "applied"
    assert step_by_id(
        applied["assignment"], "read-a")["status"] == "pending"


def test_duplicate_patch_content_conflict_and_concurrent_adoption(env):
    run_id = _patch_ready_assignment(env)
    patch = _patch(env, run_id, patch_id="inv-duplicate")

    def adopt(_):
        return apply_plan_patch(env["lifecycle"], run_id, patch)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(adopt, range(2)))
    assert sorted(item["status"] for item in results) == [
        "already_applied", "applied"]
    assignment = env["lifecycle"].get_assignment(run_id)
    assert assignment["plan_revision"] == 2

    replay = apply_plan_patch(env["lifecycle"], run_id, patch)
    assert replay["status"] == "already_applied"
    assert replay["assignment"]["plan_revision"] == 2

    changed = {
        **patch,
        "invalidate_steps": ["read-b"],
        "reason": "the same identity now requests different work",
    }
    with pytest.raises(PlanPatchError, match="conflict|different|digest"):
        apply_plan_patch(env["lifecycle"], run_id, changed)

    restart_replay = apply_plan_patch(_fresh_lifecycle(env), run_id, patch)
    assert restart_replay["status"] == "already_applied"
    assert restart_replay["assignment"]["plan_revision"] == 2


def test_requirements_cannot_be_weakened_and_facts_need_provenance(env):
    run_id = _patch_ready_assignment(env)

    def add_requirement(record, assignment):
        updated = copy.deepcopy(assignment)
        step = step_by_id(updated, "use-a")
        step["status"] = "pending"
        step["requires"] = [{
            "kind": "fact", "fact_id": "eligibility", "equals": True}]
        return updated, {}

    env["lifecycle"].mutate_assignment(
        run_id, add_requirement, rationale="qualification requirement")
    weakening = _patch(
        env, run_id, patch_id="inv-weaken",
        invalidate_steps=["use-a"], set_requires={"use-a": []})
    with pytest.raises(PlanPatchError, match="erase|weaken"):
        apply_plan_patch(env["lifecycle"], run_id, weakening)

    unproven = _patch(
        env, run_id, patch_id="inv-fact",
        invalidate_steps=[],
        add_facts=[{
            "fact_id": "invented", "value": True,
            "evidence_state": "established",
        }])
    with pytest.raises(PlanPatchError, match="evidence|provenance|accepted"):
        apply_plan_patch(env["lifecycle"], run_id, unproven)

    arbitrary = _patch(
        env, run_id, patch_id="inv-fact-arbitrary",
        invalidate_steps=[],
        add_facts=[{
            "fact_id": "arbitrary", "value": True,
            "evidence_state": "established",
            "source_refs": [{"note": "someone observed it"}],
        }])
    with pytest.raises(PlanPatchError, match="evidence|provenance|accepted"):
        apply_plan_patch(env["lifecycle"], run_id, arbitrary)
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id), "use-a")[
            "requires"][0]["fact_id"] == "eligibility"


def test_registered_mutation_cannot_be_relabelled_read_only(env):
    from core.action_registry import action_registry

    run_id = _patch_ready_assignment(env)
    name = f"test.inv.create.{uuid.uuid4().hex[:8]}"

    async def create(args, context):
        return {"status": "applied"}

    action_registry.register(
        name, create, effects=[{"effect": "create", "object": "bill"}])
    added = _patch(
        env, run_id, patch_id="inv-relabel",
        invalidate_steps=[],
        add_steps=[{
            "step_id": "relabelled-create",
            "title": "Create a bill",
            "operation_type": "outbound",
            "adapter": "action.registry",
            "effect": "read_only",
            "inputs": {"action": name, "arguments": {}},
        }])
    with pytest.raises(
            PlanPatchError, match="effect|external|authority|outbound"):
        apply_plan_patch(env["lifecycle"], run_id, added)
    assert step_by_id(
        env["lifecycle"].get_assignment(run_id),
        "relabelled-create") is None


def test_forced_cas_retry_keeps_the_callback_pure(env, monkeypatch):
    from core.assignment_executor import default_adapter_registry

    run_id = _patch_ready_assignment(env)
    effects = []

    async def side_effect(inputs, context):
        effects.append("called")
        return {"status": "applied"}

    default_adapter_registry.register("test.inv.pure", side_effect)
    attempts = []
    original = env["lifecycle"]._cas_write

    def flaky_cas(run_id, expected, lifecycle, decision):
        attempts.append(int(expected))
        if len(attempts) == 1:
            return False
        return original(run_id, expected, lifecycle, decision)

    monkeypatch.setattr(env["lifecycle"], "_cas_write", flaky_cas)
    result = apply_plan_patch(
        env["lifecycle"], run_id,
        _patch(env, run_id, patch_id="inv-cas-retry"))
    assert result["status"] == "applied"
    assert len(attempts) == 2
    assert effects == []
    assert env["lifecycle"].get_assignment(
        run_id)["plan_revision"] == 2
