"""Coverage push W84b — core/orchestration/* (8 modules to >=95%).

Modules:
  - reviewer_loop.py          (R54, P4c re-delegation loop)
  - workflow_patterns.py      (re-export facade)
  - workflow_state_machine.py (R26d validated transitions + rollback)
  - workflow_versioning.py    (snapshots/migrations)
  - conductor_agent.py        (R26d, 5+1 strategies, R54 consensus)
  - event_bus.py              (R26d pub/sub; R9/10 safe_eval conditions)
  - workflow_composer.py      (composition primitives)
  - workflow_templates.py     (template library)

Hermetic: in-memory objects only; no LLM, no network, no DB. Factory
singletons are reset between tests so the "first call constructs" branch is
exercised in isolation.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import core.orchestration.conductor_agent as conductor_mod
import core.orchestration.event_bus as event_bus_mod
import core.orchestration.reviewer_loop as reviewer_loop_mod
import core.orchestration.workflow_composer as composer_mod
import core.orchestration.workflow_state_machine as sm_mod
import core.orchestration.workflow_templates as templates_mod
import core.orchestration.workflow_versioning as versioning_mod
from core.orchestration.conductor_agent import (
    ConductorAgent,
    ConductorConfig,
    ExecutionStatus,
    ExecutionStrategy,
    OrchestrationResult,
    StepType,
    WorkflowExecutionContext,
    WorkflowStep,
    get_conductor_agent,
)
from core.orchestration.event_bus import (
    EventAck,
    EventBus,
    EventBusConfig,
    EventDelivery,
    EventSubscription,
    EventType,
    WorkflowEvent,
    get_event_bus,
)
from core.orchestration.reviewer_loop import (
    MAX_REVIEWER_REDELEGATIONS,
    attach_review_feedback,
    enter_review_waiting,
    get_review_feedback,
    get_review_loop_state_machine,
    install_state_machine_hooks,
    is_review_rejection,
    resume_after_review,
    reviewer_loop_enabled,
)
from core.orchestration.workflow_composer import (
    ComposedWorkflow,
    ComposerConfig,
    CompositionNode,
    CompositionPrimitive,
    CompositionStrategy,
    WorkflowComposer,
    get_workflow_composer,
)
from core.orchestration.workflow_state_machine import (
    RollbackPlan,
    StateMachineConfig,
    StateSnapshot,
    StateTransition,
    StateTransitionType,
    TransitionLog,
    TransitionResult,
    WorkflowState,
    WorkflowStateMachine,
    get_state_machine,
)
from core.orchestration.workflow_templates import (
    ParameterType,
    TemplateCategory,
    TemplateLibrary,
    TemplateParameter,
    WorkflowStepTemplate,
    WorkflowTemplate,
    get_template_library,
)
from core.orchestration.workflow_versioning import (
    CompatibilityStatus,
    MigrationPlan,
    MigrationStrategy,
    VersionIncrement,
    VersionSchema,
    VersionedWorkflow,
    VersioningConfig,
    WorkflowVersion,
    WorkflowVersioning,
    get_workflow_versioning,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def _reset_factories():
    """Reset module-level factory singletons + reviewer hook registry."""
    saved = (
        sm_mod._state_machine_instance,
        versioning_mod._versioning_instance,
        event_bus_mod._event_bus_instance,
        composer_mod._composer_instance,
        templates_mod._template_library_instance,
        conductor_mod._conductor_instance,
        set(reviewer_loop_mod._hooked_machines),
    )
    sm_mod._state_machine_instance = None
    versioning_mod._versioning_instance = None
    event_bus_mod._event_bus_instance = None
    composer_mod._composer_instance = None
    templates_mod._template_library_instance = None
    conductor_mod._conductor_instance = None
    reviewer_loop_mod._hooked_machines.clear()
    yield
    (
        sm_mod._state_machine_instance,
        versioning_mod._versioning_instance,
        event_bus_mod._event_bus_instance,
        composer_mod._composer_instance,
        templates_mod._template_library_instance,
        conductor_mod._conductor_instance,
    ) = saved[:6]
    reviewer_loop_mod._hooked_machines.clear()
    reviewer_loop_mod._hooked_machines.update(saved[6])


def _chain_steps(ids):
    """Build sequential WorkflowSteps linked via next_steps."""
    steps = []
    for i, sid in enumerate(ids):
        nxt = ids[i + 1] if i + 1 < len(ids) else None
        steps.append(
            WorkflowStep(step_id=sid, name=sid, next_steps=[nxt] if nxt else [])
        )
    return steps


def _make_context(steps, start, **kw):
    return WorkflowExecutionContext(
        workflow_id=kw.pop("workflow_id", "wf_x"),
        execution_id=kw.pop("execution_id", "exec_x"),
        steps=steps,
        start_step=start,
        **kw,
    )


def _review_rejection(feedback="missing edge case"):
    return SimpleNamespace(
        strategy=SimpleNamespace(value="review"),
        details={"accepted": False, "feedback": feedback},
        winner=None,
    )


def _review_acceptance(winner=None):
    return SimpleNamespace(
        strategy=SimpleNamespace(value="review"),
        details={"accepted": True},
        winner=winner or {"step_id": "s1", "output": "accepted"},
    )


# ===========================================================================
# reviewer_loop.py
# ===========================================================================


class TestIsReviewRejection:
    def test_no_strategy_attr_is_false(self):
        assert is_review_rejection(object()) is False

    def test_non_review_strategy_is_false(self):
        assert is_review_rejection(SimpleNamespace(strategy=SimpleNamespace(value="voting"))) is False

    def test_plain_string_strategy_is_false(self):
        assert is_review_rejection(SimpleNamespace(strategy="review")) is False

    def test_no_details_is_false(self):
        assert is_review_rejection(SimpleNamespace(strategy=SimpleNamespace(value="review"))) is False

    def test_accepted_true_is_false(self):
        assert is_review_rejection(
            SimpleNamespace(strategy=SimpleNamespace(value="review"), details={"accepted": True})
        ) is False

    def test_accepted_false_is_true(self):
        assert is_review_rejection(
            SimpleNamespace(strategy=SimpleNamespace(value="review"), details={"accepted": False})
        ) is True


class TestAttachAndGetReviewFeedback:
    def test_attach_creates_parameters_dict(self):
        step = SimpleNamespace()
        attach_review_feedback(step, "please fix")
        assert step.parameters["_review_feedback"] == "please fix"
        assert step.retry_count == 1

    def test_attach_uses_existing_parameters(self):
        step = SimpleNamespace(parameters={"k": "v"}, retry_count=3)
        attach_review_feedback(step, "again")
        assert step.parameters == {"k": "v", "_review_feedback": "again"}
        assert step.retry_count == 4

    def test_get_feedback_found(self):
        step = SimpleNamespace(parameters={"_review_feedback": "the note"})
        assert get_review_feedback(step) == "the note"

    def test_get_feedback_missing_key(self):
        step = SimpleNamespace(parameters={"other": 1})
        assert get_review_feedback(step) == ""

    def test_get_feedback_non_dict_params(self):
        step = SimpleNamespace(parameters="not-a-dict")
        assert get_review_feedback(step) == ""

    def test_get_feedback_no_params_attr(self):
        assert get_review_feedback(SimpleNamespace()) == ""


class TestReviewParkingTransitions:
    def test_enter_review_waiting_parks(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "exec")
        machine.transition("wf", "exec", WorkflowState.VALIDATED)
        machine.transition("wf", "exec", WorkflowState.QUEUED)
        machine.transition("wf", "exec", WorkflowState.RUNNING)
        result = enter_review_waiting(machine, "wf", "exec", "feedback here")
        assert result == TransitionResult.SUCCESS
        assert machine.get_state("wf") == WorkflowState.WAITING
        log = machine.get_transition_history("wf")[-1]
        assert log.reason == "reviewer re-delegation pending"
        assert log.from_state == WorkflowState.RUNNING

    def test_enter_review_waiting_generates_execution_id(self):
        machine = WorkflowStateMachine()
        assert enter_review_waiting(machine, "wf2", "", "f") == TransitionResult.FAILED

    def test_resume_after_review_returns_to_running(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "exec")
        machine.transition("wf", "exec", WorkflowState.VALIDATED)
        machine.transition("wf", "exec", WorkflowState.QUEUED)
        machine.transition("wf", "exec", WorkflowState.RUNNING)
        machine.transition("wf", "exec", WorkflowState.WAITING)
        result = resume_after_review(machine, "wf", "exec")
        assert result == TransitionResult.SUCCESS
        assert machine.get_state("wf") == WorkflowState.RUNNING
        log = machine.get_transition_history("wf")[-1]
        assert log.reason == "reviewer re-delegation resolved"

    def test_resume_after_review_generated_execution_id(self):
        machine = WorkflowStateMachine()
        assert resume_after_review(machine, "wf2", "") == TransitionResult.FAILED


class TestStateMachineHooks:
    def test_install_is_idempotent(self):
        machine = WorkflowStateMachine()
        install_state_machine_hooks(machine)
        install_state_machine_hooks(machine)
        assert len(reviewer_loop_mod._hooked_machines) == 1

    def test_hooks_fire_on_review_park(self, caplog):
        machine = WorkflowStateMachine()
        install_state_machine_hooks(machine)
        machine.initialize_state("wf", "exec")
        machine.transition("wf", "exec", WorkflowState.VALIDATED)
        machine.transition("wf", "exec", WorkflowState.QUEUED)
        machine.transition("wf", "exec", WorkflowState.RUNNING)
        result = machine.transition(
            "wf", "exec", WorkflowState.WAITING,
            context={"pending_review": True, "review_feedback": "fix it"},
        )
        assert result == TransitionResult.SUCCESS
        assert machine.get_state("wf") == WorkflowState.WAITING

    def test_hooks_allow_plain_wait(self):
        machine = WorkflowStateMachine()
        install_state_machine_hooks(machine)
        machine.initialize_state("wf", "exec")
        machine.transition("wf", "exec", WorkflowState.VALIDATED)
        machine.transition("wf", "exec", WorkflowState.QUEUED)
        machine.transition("wf", "exec", WorkflowState.RUNNING)
        assert machine.transition("wf", "exec", WorkflowState.WAITING) == TransitionResult.SUCCESS

    def test_get_review_loop_state_machine_installs_hooks(self):
        machine = get_review_loop_state_machine()
        assert (WorkflowState.RUNNING, WorkflowState.WAITING) in machine._guards
        assert (WorkflowState.RUNNING, WorkflowState.WAITING) in machine._pre_actions
        assert (WorkflowState.RUNNING, WorkflowState.WAITING) in machine._post_actions
        assert get_review_loop_state_machine() is machine


class TestReviewerLoopFlag:
    def test_enabled_true_when_env_set(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        assert reviewer_loop_enabled() is True

    def test_enabled_false_when_unset(self, monkeypatch):
        monkeypatch.delenv("ATOM_REVIEWER_LOOP_ENABLED", raising=False)
        assert reviewer_loop_enabled() is False

    def test_enabled_false_on_other_value(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "1")
        assert reviewer_loop_enabled() is False

    def test_max_redelegations_constant(self):
        assert MAX_REVIEWER_REDELEGATIONS == 2


# ===========================================================================
# workflow_patterns.py (re-export facade)
# ===========================================================================


class TestWorkflowPatternsFacade:
    def test_re_exports_match_underlying_modules(self):
        import core.orchestration.workflow_patterns as facade

        assert facade.WorkflowTemplate is templates_mod.WorkflowTemplate
        assert facade.TemplateCategory is templates_mod.TemplateCategory
        assert facade.TemplateParameter is templates_mod.TemplateParameter
        assert facade.get_template_library is templates_mod.get_template_library
        assert facade.WorkflowComposer is composer_mod.WorkflowComposer
        assert facade.CompositionPrimitive is composer_mod.CompositionPrimitive
        assert facade.CompositionStrategy is composer_mod.CompositionStrategy
        assert facade.ComposedWorkflow is composer_mod.ComposedWorkflow
        assert facade.get_workflow_composer is composer_mod.get_workflow_composer
        assert facade.WorkflowVersion is versioning_mod.WorkflowVersion
        assert facade.VersionSchema is versioning_mod.VersionSchema
        assert facade.MigrationStrategy is versioning_mod.MigrationStrategy
        assert facade.VersionedWorkflow is versioning_mod.VersionedWorkflow
        assert facade.get_workflow_versioning is versioning_mod.get_workflow_versioning
        for name in facade.__all__:
            assert hasattr(facade, name)


# ===========================================================================
# workflow_state_machine.py
# ===========================================================================


class TestStateMachineEnumsAndDataclasses:
    def test_state_values(self):
        assert WorkflowState.RUNNING.value == "running"
        assert WorkflowState.ROLLING_BACK.value == "rolling_back"
        assert WorkflowState.SUSPENDED.value == "suspended"

    def test_transition_type_values(self):
        assert StateTransitionType.CONDITION_BASED.value == "condition_based"
        assert StateTransitionType.TIMEOUT_DRIVEN.value == "timeout_driven"

    def test_transition_result_values(self):
        assert TransitionResult.SKIPPED.value == "skipped"
        assert TransitionResult.BLOCKED.value == "blocked"

    def test_config_defaults(self):
        cfg = StateMachineConfig()
        assert cfg.allow_invalid_transitions is False
        assert cfg.enable_auto_rollback is True
        assert cfg.max_rollback_attempts == 3
        assert cfg.enable_persistence is True
        assert cfg.enable_recovery is True

    def test_state_transition_can_execute(self):
        tr = StateTransition(guard_function=lambda ctx: ctx.get("ok") is True)
        assert tr.can_execute({"ok": True}) is True
        assert tr.can_execute({}) is False
        assert StateTransition().can_execute({}) is True

    def test_rollback_plan_is_expired(self):
        plan = RollbackPlan(expires_at=datetime.now() - timedelta(seconds=1))
        assert plan.is_expired() is True
        plan.expires_at = datetime.now() + timedelta(seconds=60)
        assert plan.is_expired() is False
        assert RollbackPlan().is_expired() is False

    def test_state_snapshot_to_dict(self):
        snap = StateSnapshot(
            snapshot_id="s1", workflow_id="wf", execution_id="ex",
            current_state=WorkflowState.RUNNING,
            step_states={"a": "done"}, context_data={"k": 1}, output_data={"o": 2},
        )
        d = snap.to_dict()
        assert d["snapshot_id"] == "s1"
        assert d["current_state"] == "running"
        assert d["step_states"] == {"a": "done"}
        assert d["created_at"] == snap.created_at.isoformat()


class TestStateMachineBasics:
    def test_initialize_and_get_state(self):
        machine = WorkflowStateMachine()
        assert machine.get_state("wf") is None
        machine.initialize_state("wf", "exec")
        assert machine.get_state("wf") == WorkflowState.CREATED
        history = machine.get_transition_history("wf")
        assert len(history) == 1
        assert history[0].from_state == WorkflowState.CREATED

    def test_can_transition_unknown_workflow(self):
        assert WorkflowStateMachine().can_transition("nope", WorkflowState.RUNNING) is False

    def test_can_transition_valid_and_invalid(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        assert machine.can_transition("wf", WorkflowState.VALIDATED) is True
        assert machine.can_transition("wf", WorkflowState.COMPLETED) is False

    def test_can_transition_allow_invalid(self):
        machine = WorkflowStateMachine(StateMachineConfig(allow_invalid_transitions=True))
        machine.initialize_state("wf", "e")
        assert machine.can_transition("wf", WorkflowState.COMPLETED) is True

    def test_transition_unknown_workflow_failed(self):
        machine = WorkflowStateMachine()
        assert machine.transition("x", "e", WorkflowState.RUNNING) == TransitionResult.FAILED

    def test_transition_invalid_returns_invalid(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        assert machine.transition("wf", "e", WorkflowState.COMPLETED) == TransitionResult.INVALID

    def test_transition_success_logs_and_snapshots(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        result = machine.transition(
            "wf", "e", WorkflowState.VALIDATED,
            transition_type=StateTransitionType.USER_INITIATED,
            triggered_by="tester", reason="test", context={"a": 1},
        )
        assert result == TransitionResult.SUCCESS
        assert machine.get_state("wf") == WorkflowState.VALIDATED
        history = machine.get_transition_history("wf")
        assert history[-1].to_state == WorkflowState.VALIDATED
        assert history[-1].triggered_by == "tester"
        assert history[-1].reason == "test"
        assert len(machine.get_snapshots("wf")) == 1

    def test_transition_skip_snapshot_when_persistence_off(self):
        machine = WorkflowStateMachine(StateMachineConfig(enable_persistence=False))
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        assert machine.get_snapshots("wf") == []

    def test_transition_second_check_workflow_gone(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        original = machine.get_state
        state = {"calls": 0}

        def weird(wid):
            state["calls"] += 1
            return original(wid) if state["calls"] == 1 else None

        machine.get_state = weird
        assert machine.transition("wf", "e", WorkflowState.VALIDATED) == TransitionResult.FAILED

    def test_guard_blocks_transition(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.add_guard(WorkflowState.CREATED, WorkflowState.VALIDATED, lambda ctx: False)
        assert machine.transition("wf", "e", WorkflowState.VALIDATED) == TransitionResult.BLOCKED
        assert machine.get_state("wf") == WorkflowState.CREATED

    def test_guard_allows_transition(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.add_guard(WorkflowState.CREATED, WorkflowState.VALIDATED, lambda ctx: True)
        assert machine.transition("wf", "e", WorkflowState.VALIDATED) == TransitionResult.SUCCESS

    def test_pre_action_failure_fails_transition(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.add_pre_action(
            WorkflowState.CREATED, WorkflowState.VALIDATED,
            lambda wf, ctx: (_ for _ in ()).throw(RuntimeError("pre boom")),
        )
        assert machine.transition("wf", "e", WorkflowState.VALIDATED) == TransitionResult.FAILED
        assert machine.get_state("wf") == WorkflowState.CREATED

    def test_pre_action_runs(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        seen = []
        machine.add_pre_action(WorkflowState.CREATED, WorkflowState.VALIDATED,
                               lambda wf, ctx: seen.append((wf, ctx)))
        machine.transition("wf", "e", WorkflowState.VALIDATED, context={"m": 1})
        assert seen == [("wf", {"m": 1})]

    def test_post_action_exception_still_succeeds(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.add_post_action(
            WorkflowState.CREATED, WorkflowState.VALIDATED,
            lambda wf, ctx: (_ for _ in ()).throw(RuntimeError("post boom")),
        )
        assert machine.transition("wf", "e", WorkflowState.VALIDATED) == TransitionResult.SUCCESS
        assert machine.get_state("wf") == WorkflowState.VALIDATED

    def test_post_action_runs(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        seen = []
        machine.add_post_action(WorkflowState.CREATED, WorkflowState.VALIDATED,
                                lambda wf, ctx: seen.append(ctx))
        machine.transition("wf", "e", WorkflowState.VALIDATED, context={"z": 2})
        assert seen == [{"z": 2}]


class TestRollback:
    async def test_create_rollback_plan_unknown_workflow(self):
        with pytest.raises(ValueError):
            WorkflowStateMachine().create_rollback_plan("nope", "e", ["a"])

    def test_create_rollback_plan_success(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        plan = machine.create_rollback_plan("wf", "e", ["comp_a", "comp_b"])
        assert plan.workflow_id == "wf"
        assert plan.current_state == WorkflowState.CREATED
        assert plan.rollback_states == [
            WorkflowState.RUNNING, WorkflowState.ROLLING_BACK, WorkflowState.ROLLED_BACK,
        ]
        assert plan.expires_at is not None
        assert machine._rollback_plans["wf"] is plan

    async def test_execute_rollback_no_plan(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        assert await machine.execute_rollback("wf", "e") == TransitionResult.FAILED

    async def test_execute_rollback_expired_plan(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        plan = machine.create_rollback_plan("wf", "e", [])
        plan.expires_at = datetime.now() - timedelta(seconds=1)
        assert await machine.execute_rollback("wf", "e") == TransitionResult.FAILED

    async def test_execute_rollback_success(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        machine.transition("wf", "e", WorkflowState.QUEUED)
        machine.transition("wf", "e", WorkflowState.RUNNING)
        plan = machine.create_rollback_plan("wf", "e", ["comp1", "comp2"])
        result = await machine.execute_rollback("wf", "e")
        assert result == TransitionResult.SUCCESS
        assert machine.get_state("wf") == WorkflowState.ROLLED_BACK
        assert plan.executed is True
        assert plan.result == "success"
        assert plan.attempts == 1

    async def test_execute_rollback_invalid_from_state(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        machine.transition("wf", "e", WorkflowState.QUEUED)
        machine.transition("wf", "e", WorkflowState.RUNNING)
        machine.transition("wf", "e", WorkflowState.COMPLETED)
        plan = machine.create_rollback_plan("wf", "e", [])
        result = await machine.execute_rollback("wf", "e")
        assert result == TransitionResult.INVALID
        assert plan.executed is False

    async def test_execute_rollback_compensation_exhausts_attempts(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=RuntimeError("comp failed")))
        machine = WorkflowStateMachine(StateMachineConfig(max_rollback_attempts=1))
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        machine.transition("wf", "e", WorkflowState.QUEUED)
        machine.transition("wf", "e", WorkflowState.RUNNING)
        plan = machine.create_rollback_plan("wf", "e", ["comp1"])
        plan.max_attempts = 1
        result = await machine.execute_rollback("wf", "e")
        assert result == TransitionResult.FAILED
        assert plan.attempts == 1

    async def test_execute_rollback_compensation_then_success(self, monkeypatch):
        sleep_mock = AsyncMock(side_effect=[None, RuntimeError("comp failed"), None])
        monkeypatch.setattr(asyncio, "sleep", sleep_mock)
        machine = WorkflowStateMachine(StateMachineConfig(max_rollback_attempts=3))
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        machine.transition("wf", "e", WorkflowState.QUEUED)
        machine.transition("wf", "e", WorkflowState.RUNNING)
        plan = machine.create_rollback_plan("wf", "e", ["comp1"])
        result = await machine.execute_rollback("wf", "e")
        assert result == TransitionResult.SUCCESS
        assert plan.result == "success"


class TestSnapshotsAndStats:
    def test_create_snapshot_unknown_workflow(self):
        machine = WorkflowStateMachine()
        assert machine._create_snapshot("nope", "e") is None

    def test_snapshot_limit_keeps_last_100(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        for i in range(105):
            machine._create_snapshot("wf", "e")
        snaps = machine._snapshots["wf"]
        assert len(snaps) == 100
        assert snaps[0].snapshot_id.startswith("snap_")

    def test_get_snapshots_limit(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        for i in range(5):
            machine._create_snapshot("wf", "e")
        assert len(machine.get_snapshots("wf", limit=2)) == 2
        assert machine.get_snapshots("other") == []

    def test_restore_from_snapshot(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        snap = StateSnapshot(current_state=WorkflowState.RUNNING)
        assert machine.restore_from_snapshot("wf", snap) is True
        assert machine.get_state("wf") == WorkflowState.RUNNING

    def test_restore_from_snapshot_exception(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")

        class Boom(dict):
            def __setitem__(self, key, value):
                raise RuntimeError("cannot set")

        machine._workflow_states = Boom()
        assert machine.restore_from_snapshot("wf", StateSnapshot()) is False

    def test_get_transition_history_limit(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf", "e")
        machine.transition("wf", "e", WorkflowState.VALIDATED)
        machine.transition("wf", "e", WorkflowState.QUEUED)
        machine.transition("wf", "e", WorkflowState.RUNNING)
        machine.transition("wf", "e", WorkflowState.PAUSED)
        machine.transition("wf", "e", WorkflowState.RUNNING)
        machine.transition("wf", "e", WorkflowState.PAUSED)
        assert len(machine.get_transition_history("wf")) == 7
        assert len(machine.get_transition_history("wf", limit=3)) == 3
        assert machine.get_transition_history("other") == []

    def test_get_statistics(self):
        machine = WorkflowStateMachine()
        machine.initialize_state("wf1", "e1")
        machine.initialize_state("wf2", "e2")
        machine.transition("wf1", "e1", WorkflowState.VALIDATED)
        machine.create_rollback_plan("wf1", "e1", [])
        stats = machine.get_statistics()
        assert stats["total_workflows"] == 2
        assert stats["total_transitions"] == 3
        assert stats["rollback_plans"] == 1
        assert stats["total_snapshots"] == 1
        assert stats["state_distribution"]["validated"] == 1


class TestStateMachineFactory:
    def test_factory_singleton(self):
        m1 = get_state_machine()
        m2 = get_state_machine()
        assert m1 is m2

    def test_factory_uses_config_on_first_call(self):
        cfg = StateMachineConfig(enable_persistence=False)
        m = get_state_machine(cfg)
        assert m.config is cfg


# ===========================================================================
# workflow_versioning.py
# ===========================================================================


class TestVersioningEnumsAndHelpers:
    def test_increment_values(self):
        assert VersionIncrement.MAJOR.value == "major"
        assert VersionIncrement.PATCH.value == "patch"

    def test_migration_strategy_values(self):
        assert MigrationStrategy.ROLLBACK.value == "rollback"

    def test_compatibility_values(self):
        assert CompatibilityStatus.UNKNOWN.value == "unknown"

    def test_semver_sort_key_valid(self):
        assert versioning_mod._semver_sort_key("2.1.0") == (2, 1, 0)

    def test_semver_sort_key_partial(self):
        assert versioning_mod._semver_sort_key("1.2") == (1, 2)

    def test_semver_sort_key_non_numeric(self):
        assert versioning_mod._semver_sort_key("abc") == (0, 0, 0)

    def test_semver_sort_key_empty(self):
        assert versioning_mod._semver_sort_key("") == (0, 0, 0)

    def test_config_defaults(self):
        cfg = VersioningConfig()
        assert cfg.auto_increment is True
        assert cfg.versioning_scheme == "semantic"
        assert cfg.max_versions_per_workflow == 10
        assert cfg.default_migration_strategy == MigrationStrategy.HYBRID


class TestWorkflowVersionCompat:
    def test_is_compatible_with_allowlist(self):
        v = WorkflowVersion(version="2.0.0", compatible_with=["1.5.0"])
        assert v.is_compatible_with("1.5.0") is True
        assert v.is_compatible_with("2.1.0") is True
        assert v.is_compatible_with("3.0.0") is False

    def test_is_compatible_with_denylist(self):
        v = WorkflowVersion(version="2.0.0", incompatible_with=["1.9.0"])
        assert v.is_compatible_with("1.9.0") is False

    def test_is_compatible_with_major_mismatch(self):
        v = WorkflowVersion(version="2.0.0")
        assert v.is_compatible_with("3.0.0") is False

    def test_is_compatible_with_bad_version(self):
        v = WorkflowVersion(version="x.0.0")
        assert v.is_compatible_with("3.0.0") is True

    def test_get_major_minor(self):
        assert WorkflowVersion(version="2.5.9").get_major_minor() == (2, 5)

    def test_get_major_minor_bad(self):
        assert WorkflowVersion(version="junk").get_major_minor() == (1, 0)
        assert WorkflowVersion(version="1").get_major_minor() == (1, 0)


class TestWorkflowVersioningManager:
    def _m(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "Workflow", "Desc")
        return m

    def test_create_workflow_creates_initial_version(self):
        m = WorkflowVersioning()
        wf = m.create_workflow("wf-1", "W", "D", version="2.0.0", creator="alice")
        assert wf.current_version == "2.0.0"
        assert m._version_history[0].version == "2.0.0"
        assert m._version_history[0].created_by == "alice"

    def test_add_version_unknown_workflow(self):
        with pytest.raises(ValueError):
            WorkflowVersioning().add_version("nope", "1.0.0", {}, {}, {})

    def test_add_version_duplicate(self):
        m = self._m()
        with pytest.raises(ValueError):
            m.add_version("wf-1", "1.0.0", {}, {}, {})

    def test_add_version_updates_latest_flags(self):
        m = self._m()
        v2 = m.add_version("wf-1", "1.1.0", {"a": {}}, {"b": {}}, {"s": {}},
                           increment_type=VersionIncrement.MINOR,
                           changelog=["x"], breaking_changes=["y"])
        assert v2.version_id == "wf-1_v_1_1_0"
        assert m.get_version("wf-1", "1.0.0").is_latest is False
        assert v2.is_latest is True
        assert m._workflows["wf-1"].schemas["1.1.0"].step_schemas == {"default": {"s": {}}}
        assert v2.changelog == ["x"]
        assert v2.breaking_changes == ["y"]

    def test_get_version_missing(self):
        m = self._m()
        assert m.get_version("nope", "1.0.0") is None
        assert m.get_version("wf-1", "9.9.9") is None
        assert m.get_version("wf-1", "1.0.0") is not None

    def test_get_latest_version(self):
        m = self._m()
        assert m.get_latest_version("nope") is None
        m.add_version("wf-1", "1.2.0", {}, {}, {})
        assert m.get_latest_version("wf-1").version == "1.2.0"

    def test_list_versions_sorted_desc(self):
        m = self._m()
        m.add_version("wf-1", "2.0.0", {}, {}, {})
        m.add_version("wf-1", "1.10.0", {}, {}, {})
        versions = m.list_versions("wf-1")
        assert [v.version for v in versions] == ["2.0.0", "1.10.0", "1.0.0"]
        assert m.list_versions("nope") == []

    def test_deprecate_version(self):
        m = self._m()
        assert m.deprecate_version("wf-1", "1.0.0") is True
        v = m.get_version("wf-1", "1.0.0")
        assert v.deprecated is True
        assert v.deprecated_at is not None
        assert m.deprecate_version("wf-1", "9.9.9") is False

    def test_statistics(self):
        m = self._m()
        m.add_version("wf-1", "1.1.0", {}, {}, {})
        m.create_migration_plan("wf-1", "1.0.0", "1.1.0")
        stats = m.get_statistics()
        assert stats["total_workflows"] == 1
        assert stats["total_versions"] == 2
        assert stats["migration_plans"] == 1
        assert stats["config"]["auto_increment"] is True


class TestMigrationPlans:
    def test_create_migration_plan_missing_versions(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        with pytest.raises(ValueError):
            m.create_migration_plan("wf-1", "1.0.0", "2.0.0")

    def test_create_migration_plan_steps(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "2.0.0",
                      {"properties": {"a": {}, "b": {}}},
                      {"properties": {"x": {}}},
                      {"step": 1},
                      breaking_changes=["output format changed"])
        plan = m.create_migration_plan("wf-1", "1.0.0", "2.0.0",
                                       strategy=MigrationStrategy.AUTOMATIC)
        assert plan.migration_id == "mig_wf-1_1.0.0_to_2.0.0"
        assert plan.strategy == MigrationStrategy.AUTOMATIC
        assert "Address breaking changes: output format changed" in plan.steps
        assert "Update input data to match new schema" in plan.steps
        assert "Update output data consumers for new schema" in plan.steps
        assert "Update step configurations" in plan.steps
        assert "Provide new parameters: b, a" in " ".join(plan.steps) or "Provide new parameters: a, b" in " ".join(plan.steps)
        assert plan.steps[-1] == "Validate migrated workflow"
        assert m._workflows["wf-1"].migration_plans[("1.0.0", "2.0.0")] is plan

    def test_create_migration_plan_autocreates_missing_workflow(self, monkeypatch):
        """Cover the auto-create branch (guard is dead in production — see report)."""
        m = WorkflowVersioning()
        fake_version = WorkflowVersion(version="1.0.0")
        monkeypatch.setattr(m, "get_version", lambda wf, ver: fake_version)
        plan = m.create_migration_plan("ghost", "1.0.0", "1.1.0")
        assert "ghost" in m._workflows
        assert m._workflows["ghost"].description == "Auto-created for migration"
        assert plan.steps == ["Validate migrated workflow"]

    def test_build_migration_steps_no_changes(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "1.0.1", {"properties": {"a": {}}}, {"properties": {"b": {}}}, {"s": {}})
        m.add_version("wf-1", "1.0.2", {"properties": {"a": {}}}, {"properties": {"b": {}}}, {"s": {}})
        plan = m.create_migration_plan("wf-1", "1.0.1", "1.0.2")
        assert plan.steps == ["Validate migrated workflow"]

    def test_build_migration_steps_none_schemas(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "1.0.1", None, None, None)
        m.add_version("wf-1", "1.0.2", None, None, None)
        plan = m.create_migration_plan("wf-1", "1.0.1", "1.0.2")
        assert plan.steps == ["Validate migrated workflow"]

    async def test_execute_migration_missing_workflow(self):
        assert await WorkflowVersioning().execute_migration("missing", "mig") is False

    async def test_execute_migration_missing_plan(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        assert await m.execute_migration("wf-1", "nope") is False

    async def test_execute_migration_success(self, monkeypatch):
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "2.0.0", {"p": 1}, {}, {})
        plan = m.create_migration_plan("wf-1", "1.0.0", "2.0.0")
        assert await m.execute_migration("wf-1", plan.migration_id) is True
        assert m._workflows["wf-1"].current_version == "2.0.0"
        assert plan.status == "completed"
        assert plan.completed_at is not None

    async def test_execute_migration_failure_rolls_back(self, monkeypatch):
        real_sleep = asyncio.sleep

        async def boom(*a, **kw):
            raise RuntimeError("migration exploded")

        monkeypatch.setattr(asyncio, "sleep", boom)
        try:
            m = WorkflowVersioning(VersioningConfig(rollback_on_validation_failure=True))
            m.create_workflow("wf-1", "n", "d")
            m.add_version("wf-1", "2.0.0", {}, {}, {})
            plan = m.create_migration_plan("wf-1", "1.0.0", "2.0.0")
            assert await m.execute_migration("wf-1", plan.migration_id) is True
            assert plan.status == "failed"
        finally:
            monkeypatch.setattr(asyncio, "sleep", real_sleep)

    async def test_execute_migration_failure_no_rollback(self, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("migration exploded")

        monkeypatch.setattr(asyncio, "sleep", boom)
        m = WorkflowVersioning(VersioningConfig(rollback_on_validation_failure=False))
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "2.0.0", {}, {}, {})
        plan = m.create_migration_plan("wf-1", "1.0.0", "2.0.0")
        assert await m.execute_migration("wf-1", plan.migration_id) is False
        assert plan.status == "failed"
        assert "exploded" in plan.error


class TestCompatibilityAndIncrement:
    def test_check_compatibility_unknown_versions(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        assert m.check_compatibility("wf-1", "1.0.0", "9.9.9") == CompatibilityStatus.UNKNOWN
        assert m.check_compatibility("nope", "1.0.0", "2.0.0") == CompatibilityStatus.UNKNOWN

    def test_check_compatibility_denylist(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        v2 = m.add_version("wf-1", "2.0.0", {}, {}, {})
        v2.incompatible_with = ["1.0.0"]
        assert m.check_compatibility("wf-1", "1.0.0", "2.0.0") == CompatibilityStatus.INCOMPATIBLE

    def test_check_compatibility_allowlist(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        v2 = m.add_version("wf-1", "2.0.0", {}, {}, {})
        v2.compatible_with = ["1.0.0"]
        assert m.check_compatibility("wf-1", "1.0.0", "2.0.0") == CompatibilityStatus.COMPATIBLE

    def test_check_compatibility_major_mismatch(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "3.0.0", {}, {}, {})
        m.add_version("wf-1", "1.5.0", {}, {}, {})
        assert m.check_compatibility("wf-1", "1.0.0", "3.0.0") == CompatibilityStatus.INCOMPATIBLE
        assert m.check_compatibility("wf-1", "1.0.0", "1.5.0") == CompatibilityStatus.COMPATIBLE

    def test_check_compatibility_bad_major(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m.add_version("wf-1", "abc", {}, {}, {})
        assert m.check_compatibility("wf-1", "1.0.0", "abc") == CompatibilityStatus.UNKNOWN

    def test_increment_version_missing_workflow(self):
        with pytest.raises(ValueError):
            WorkflowVersioning().increment_version("nope")

    def test_increment_major_minor_patch(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        assert m.increment_version("wf-1", VersionIncrement.MAJOR) == "2.0.0"
        assert m.increment_version("wf-1", VersionIncrement.MINOR) == "1.1.0"
        assert m.increment_version("wf-1", VersionIncrement.PATCH) == "1.0.1"
        assert m.increment_version("wf-1") == "1.0.1"

    def test_increment_version_short_current(self):
        m = WorkflowVersioning()
        m.create_workflow("wf-1", "n", "d")
        m._workflows["wf-1"].current_version = "1"
        assert m.increment_version("wf-1", VersionIncrement.PATCH) == "1.0.1"


class TestVersioningFactory:
    def test_factory_singleton(self):
        m1 = get_workflow_versioning()
        assert get_workflow_versioning() is m1


# ===========================================================================
# conductor_agent.py
# ===========================================================================


class TestConductorDataclasses:
    def test_step_can_execute(self):
        step = WorkflowStep(step_id="s1", depends_on=["a", "b"])
        assert step.can_execute({"a"}) is False
        assert step.can_execute({"a", "b"}) is True
        step.condition_met = False
        assert step.can_execute({"a", "b"}) is False

    def test_context_get_step_missing(self):
        ctx = _make_context([WorkflowStep(step_id="s1")], "s1")
        assert ctx.get_step("nope") is None

    def test_context_get_next_steps(self):
        ctx = _make_context(
            [WorkflowStep(step_id="s1", next_steps=["s2", "ghost"]), WorkflowStep(step_id="s2")],
            "s1",
        )
        assert [s.step_id for s in ctx.get_next_steps("s1")] == ["s2"]
        assert ctx.get_next_steps("missing") == []
        assert ctx.get_next_steps("s2") == []

    def test_context_get_ready_steps(self):
        ctx = _make_context(
            [
                WorkflowStep(step_id="s1", depends_on=["s0"]),
                WorkflowStep(step_id="s2"),
            ],
            "s2",
        )
        assert [s.step_id for s in ctx.get_ready_steps()] == ["s2"]
        ctx.steps[0].status = ExecutionStatus.RUNNING
        assert [s.step_id for s in ctx.get_ready_steps()] == ["s2"]

    def test_context_is_complete_terminal(self):
        ctx = _make_context([], "s1")
        ctx.status = ExecutionStatus.CANCELLED
        assert ctx.is_complete() is True
        ctx.status = ExecutionStatus.RUNNING
        ctx.steps = [
            WorkflowStep(step_id="a", status=ExecutionStatus.COMPLETED),
            WorkflowStep(step_id="b", status=ExecutionStatus.FAILED),
        ]
        assert ctx.is_complete() is True
        ctx.steps[1].status = ExecutionStatus.PENDING
        assert ctx.is_complete() is False

    def test_context_is_complete_compensation_targets(self):
        ctx = _make_context(
            [
                WorkflowStep(step_id="main", compensation_step_id="comp", status=ExecutionStatus.COMPLETED),
                WorkflowStep(step_id="comp", status=ExecutionStatus.PENDING),
            ],
            "main",
        )
        assert ctx.is_complete() is True

    def test_context_get_progress(self):
        ctx = _make_context([], "s1")
        assert ctx.get_progress() == 0.0
        ctx.steps = [
            WorkflowStep(step_id="a", status=ExecutionStatus.COMPLETED),
            WorkflowStep(step_id="b", status=ExecutionStatus.PENDING),
            WorkflowStep(step_id="c", status=ExecutionStatus.PENDING),
        ]
        assert ctx.get_progress() == pytest.approx(1 / 3)

    def test_orchestration_result_was_successful(self):
        ok = OrchestrationResult(status=ExecutionStatus.COMPLETED)
        assert ok.was_successful() is True
        assert OrchestrationResult(status=ExecutionStatus.FAILED).was_successful() is False
        assert OrchestrationResult(status=ExecutionStatus.COMPLETED, failed_steps=1).was_successful() is False
        assert OrchestrationResult(status=ExecutionStatus.COMPLETED, rolled_back=True).was_successful() is False

    def test_strategy_enum_values(self):
        assert ExecutionStrategy.PARALLEL_CONSENSUS.value == "parallel_consensus"
        assert ExecutionStatus.ROLLED_BACK.value == "rolled_back"
        assert StepType.COMPENSATION.value == "compensation"


class TestSequentialStrategy:
    async def test_sequential_success(self):
        agent = ConductorAgent()
        steps = _chain_steps(["s1", "s2", "s3"])
        result = await agent.execute_workflow(steps, "s1")
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 3
        assert agent._completed_workflows[result.execution_id] is result

    async def test_sequential_failed_status_dict(self):
        agent = ConductorAgent()
        step = WorkflowStep(step_id="s1", max_retries=0)
        agent.set_step_executor(lambda s, c: {"status": "failed", "error": "boom"})
        result = await agent.execute_workflow([step], "s1")
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1
        assert "boom" in result.errors[0]

    async def test_sequential_timeout(self):
        agent = ConductorAgent()

        async def slow(s, c):
            await asyncio.sleep(5)
            return {"step_id": s.step_id}

        agent.set_step_executor(slow)
        step = WorkflowStep(step_id="s1", timeout_seconds=1)
        result = await agent.execute_workflow([step], "s1")
        assert result.status == ExecutionStatus.FAILED
        assert step.status == ExecutionStatus.FAILED
        assert step.error == "Timeout"

    async def test_sequential_retry_then_success(self):
        agent = ConductorAgent()
        calls = {"n": 0}

        def flaky(s, c):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("first try fails")
            return {"step_id": s.step_id, "output": "ok"}

        agent.set_step_executor(flaky)
        step = WorkflowStep(step_id="s1", max_retries=2)
        result = await agent.execute_workflow([step], "s1")
        assert result.status == ExecutionStatus.COMPLETED
        assert step.retry_count == 1
        assert result.failed_steps == 0

    async def test_sequential_retries_exhausted(self):
        agent = ConductorAgent()
        agent.set_step_executor(lambda s, c: (_ for _ in ()).throw(RuntimeError("always")))
        step = WorkflowStep(step_id="s1", max_retries=1)
        result = await agent.execute_workflow([step], "s1")
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1
        assert step.retry_count == 1

    async def test_sequential_unknown_start_step(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1")]
        result = await agent.execute_workflow(steps, "ghost")
        assert result.status == ExecutionStatus.FAILED
        assert "no progress" in result.errors[0]

    async def test_sequential_blocked_start_step(self):
        agent = ConductorAgent()
        step = WorkflowStep(step_id="s1", condition_met=False)
        result = await agent.execute_workflow([step], "s1")
        assert result.status == ExecutionStatus.FAILED
        assert "no progress" in result.errors[0]

    async def test_context_reused(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1")]
        ctx = _make_context(steps, "s1")
        result = await agent.execute_workflow(steps, "s1", ctx)
        assert result.workflow_id == ctx.workflow_id
        assert result.execution_id == ctx.execution_id

    async def test_execution_exception_marks_failed(self):
        agent = ConductorAgent()
        agent._execute_sequential = AsyncMock(side_effect=RuntimeError("kaboom"))
        steps = [WorkflowStep(step_id="s1")]
        result = await agent.execute_workflow(steps, "s1")
        assert result.status == ExecutionStatus.FAILED
        assert "kaboom" in result.errors

    async def test_execution_exception_rolls_back_when_configured(self):
        config = ConductorConfig(enable_rollback=True, rollback_on_failure=True)
        agent = ConductorAgent(config)
        agent._execute_sequential = AsyncMock(side_effect=RuntimeError("kaboom"))
        steps = [WorkflowStep(step_id="s1", compensation_step_id="c1")]
        ctx = _make_context(steps, "s1", rollback_stack=["s1"])
        result = await agent.execute_workflow(steps, "s1", ctx)
        assert result.status == ExecutionStatus.FAILED
        assert result.rolled_back is True
        assert result.rollback_reason == "Workflow execution failed"


class TestParallelAndHybrid:
    async def test_parallel_runs_ready_steps(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1"), WorkflowStep(step_id="s2")]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 2

    async def test_parallel_failed_status_dict(self):
        agent = ConductorAgent()
        agent.set_step_executor(lambda s, c: {"status": "failed", "error": "nope"})
        steps = [WorkflowStep(step_id="s1")]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL)
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1

    async def test_parallel_dependency_gating(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", depends_on=["s0"]),
            WorkflowStep(step_id="s2", depends_on=["s1"]),
            WorkflowStep(step_id="s3"),
        ]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL)
        assert result.status == ExecutionStatus.FAILED
        assert result.completed_steps == 1

    async def test_hybrid_single_and_parallel_blocks(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1"),
            WorkflowStep(step_id="p1", parallel_group="g1", is_parallel_root=True),
            WorkflowStep(step_id="p2", parallel_group="g1"),
        ]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.HYBRID)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 3

    def test_identify_parallel_blocks(self):
        agent = ConductorAgent()
        ctx = _make_context(
            [
                WorkflowStep(step_id="s1"),
                WorkflowStep(step_id="p1", parallel_group="g1", is_parallel_root=True),
                WorkflowStep(step_id="p2", parallel_group="g1"),
                WorkflowStep(step_id="s2"),
            ],
            "s1",
        )
        blocks = agent._identify_parallel_blocks(ctx)
        assert [sorted(b.step_id for b in blk) for blk in blocks] == [
            ["s1"], ["p1", "p2"], ["s2"],
        ]

    async def test_execute_parallel_group(self):
        agent = ConductorAgent()
        ctx = _make_context(
            [
                WorkflowStep(step_id="p1", parallel_group="g1"),
                WorkflowStep(step_id="p2", parallel_group="g1"),
            ],
            "p1",
        )
        await agent._execute_parallel_group(ctx.steps[0], ctx, OrchestrationResult())
        assert ctx.steps[0].status == ExecutionStatus.COMPLETED
        assert ctx.steps[1].status == ExecutionStatus.COMPLETED

    def test_can_execute_parallel_group(self):
        agent = ConductorAgent()
        ctx = _make_context(
            [
                WorkflowStep(step_id="p1", parallel_group="g1", depends_on=["x"]),
                WorkflowStep(step_id="p2", parallel_group="g1"),
            ],
            "p1",
        )
        assert agent._can_execute_parallel_group(ctx.steps[0], ctx) is False
        ctx.steps[0].depends_on = []
        assert agent._can_execute_parallel_group(ctx.steps[0], ctx) is True


class TestAdaptiveStrategy:
    async def test_adaptive_skips_unmet_condition(self):
        agent = ConductorAgent()
        step = WorkflowStep(step_id="s1", condition="data['x'] > 10")
        ctx = _make_context([step], "s1")
        ctx.shared_context = {"data": {"x": 1}}
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.ADAPTIVE)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.skipped_steps == 1
        assert step.condition_met is False
        assert step.status == ExecutionStatus.COMPLETED

    async def test_adaptive_runs_met_condition(self):
        agent = ConductorAgent()
        step = WorkflowStep(step_id="s1", condition="data['x'] > 10")
        ctx = _make_context([step], "s1")
        ctx.shared_context = {"data": {"x": 20}}
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.ADAPTIVE)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 1

    async def test_adaptive_unknown_start_step(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1")]
        result = await agent.execute_workflow(steps, "ghost", strategy=ExecutionStrategy.ADAPTIVE)
        assert result.status == ExecutionStatus.FAILED
        assert "no progress" in result.errors[0]

    async def test_adaptive_skip_with_next_step(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", condition="data['x'] > 10", next_steps=["s2"]),
            WorkflowStep(step_id="s2"),
        ]
        ctx = _make_context(steps, "s1")
        ctx.shared_context = {"data": {"x": 1}}
        result = await agent.execute_workflow(steps, "s1", ctx, strategy=ExecutionStrategy.ADAPTIVE)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.skipped_steps == 1
        assert result.completed_steps == 1
        assert ctx.steps[1].status == ExecutionStatus.COMPLETED

    async def test_adaptive_met_condition_with_next_step(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", condition="data['x'] > 10", next_steps=["s2"]),
            WorkflowStep(step_id="s2"),
        ]
        ctx = _make_context(steps, "s1")
        ctx.shared_context = {"data": {"x": 20}}
        result = await agent.execute_workflow(steps, "s1", ctx, strategy=ExecutionStrategy.ADAPTIVE)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 2

    async def test_adaptive_parallel_group(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="p1", parallel_group="g1"),
            WorkflowStep(step_id="p2", parallel_group="g1"),
        ]
        result = await agent.execute_workflow(steps, "p1", strategy=ExecutionStrategy.ADAPTIVE)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 2

    def test_evaluate_condition_true(self):
        agent = ConductorAgent()
        ctx = _make_context([], "s1")
        ctx.shared_context = {"a": 1, "b": 2}
        assert agent._evaluate_condition("a + b == 3", ctx) is True
        assert agent._evaluate_condition("a + b == 99", ctx) is False

    def test_evaluate_condition_safe_eval_error(self):
        agent = ConductorAgent()
        ctx = _make_context([], "s1")
        ctx.shared_context = {}
        assert agent._evaluate_condition("data.get('x')", ctx) is False

    def test_evaluate_condition_generic_exception(self, monkeypatch):
        def boom(*a, **kw):
            raise RuntimeError("evaluator broken")

        monkeypatch.setattr("core.safe_evaluator.safe_eval", boom)
        agent = ConductorAgent()
        ctx = _make_context([], "s1")
        assert agent._evaluate_condition("1 + 1", ctx) is False


class TestRollbackSafe:
    async def test_rollback_safe_success(self):
        agent = ConductorAgent()
        steps = [
            WorkflowStep(step_id="s1", compensation_step_id="c1", next_steps=["s2"]),
            WorkflowStep(step_id="s2"),
        ]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.ROLLBACK_SAFE)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 2

    async def test_rollback_safe_triggers_rollback_on_failure(self):
        config = ConductorConfig(rollback_on_failure=True)
        agent = ConductorAgent(config)
        calls = []

        def executor(s, c):
            calls.append(s.step_id)
            if s.step_id == "s1":
                return {"status": "failed", "error": "bad"}
            return {"step_id": s.step_id}

        agent.set_step_executor(executor)
        steps = [
            WorkflowStep(step_id="s1", compensation_step_id="c1"),
            WorkflowStep(step_id="c1", step_type=StepType.COMPENSATION),
        ]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.ROLLBACK_SAFE)
        assert result.status == ExecutionStatus.FAILED
        assert result.rolled_back is True
        assert "c1" in calls, "compensation step ran"

    async def test_rollback_safe_blocked(self):
        agent = ConductorAgent()
        step = WorkflowStep(step_id="s1", depends_on=["ghost"])
        result = await agent.execute_workflow([step], "s1", strategy=ExecutionStrategy.ROLLBACK_SAFE)
        assert result.status == ExecutionStatus.FAILED
        assert "no progress" in result.errors[0]

    async def test_rollback_safe_unknown_start_step(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1")]
        result = await agent.execute_workflow(steps, "ghost", strategy=ExecutionStrategy.ROLLBACK_SAFE)
        assert result.status == ExecutionStatus.FAILED
        assert "no progress" in result.errors[0]

    async def test_rollback_workflow_missing_steps(self):
        agent = ConductorAgent()
        ctx = _make_context([WorkflowStep(step_id="s1", compensation_step_id="c1")], "s1")
        ctx.rollback_stack = ["s1", "ghost"]
        result = OrchestrationResult()
        await agent._rollback_workflow(ctx, result)
        assert result.rolled_back is True

    async def test_rollback_workflow_compensation_error(self):
        agent = ConductorAgent()
        agent._execute_step = AsyncMock(side_effect=RuntimeError("comp failed"))
        ctx = _make_context(
            [
                WorkflowStep(step_id="s1", compensation_step_id="c1"),
                WorkflowStep(step_id="c1", step_type=StepType.COMPENSATION),
            ],
            "s1",
        )
        ctx.rollback_stack = ["s1"]
        result = OrchestrationResult()
        await agent._rollback_workflow(ctx, result)
        assert result.rolled_back is True
        assert "comp failed" in result.errors[0]


class TestParallelConsensus:
    async def test_consensus_deterministic_skips_fanout(self):
        agent = ConductorAgent()
        agent._execute_step = AsyncMock(return_value={"step_id": "s1", "output": "once"})
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert agent._execute_step.call_count == 1
        assert result.status == ExecutionStatus.COMPLETED

    async def test_consensus_deterministic_failed_dict(self):
        agent = ConductorAgent()
        agent._execute_step = AsyncMock(return_value={"status": "failed", "error": "dead"})
        agent._is_stochastic_executor = Mock(return_value=False)
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1

    async def test_consensus_stochastic_uses_orchestrator(self):
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=SimpleNamespace(winner={"step_id": "s1", "output": "win"}))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(return_value=True)
        agent._execute_step = AsyncMock(return_value={"step_id": "s1", "output": "branch"})
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.COMPLETED
        assert verifier.verify.await_count == 1
        assert agent._execute_step.call_count == 3

    async def test_consensus_all_branches_fail(self):
        agent = ConductorAgent()
        agent._is_stochastic_executor = Mock(return_value=True)
        agent._execute_step = AsyncMock(side_effect=RuntimeError("dead"))
        steps = [WorkflowStep(step_id="s1", step_type=StepType.AGENT)]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1

    async def test_consensus_non_agent_steps(self):
        agent = ConductorAgent()
        steps = [WorkflowStep(step_id="s1", step_type=StepType.INTEGRATION)]
        result = await agent.execute_workflow(steps, "s1", strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.COMPLETED

    async def test_reviewer_loop_redelegates_stochastic(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        agent = ConductorAgent()
        calls = []

        async def fake_executor(step, ctx):
            calls.append(step.parameters.get("_review_feedback", ""))
            return {"step_id": step.step_id, "status": "completed", "output": f"draft {len(calls)}"}

        agent.set_step_executor(fake_executor)
        verifier = MagicMock()
        verifier.verify = AsyncMock(side_effect=[
            _review_rejection("missing edge case"),
            _review_acceptance({"step_id": "s1", "output": "fixed"}),
        ])
        agent.set_verification_orchestrator(verifier)
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.failed_steps == 0
        assert len(calls) == 6, "3 initial branches + 3 re-delegated"
        assert calls[3:] == ["missing edge case"] * 3
        assert step.retry_count == 1
        assert step.result == {"step_id": "s1", "output": "fixed"}

    async def test_reviewer_loop_deterministic_redelegation(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=_review_rejection("try again"))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(side_effect=[True, False])
        agent._execute_step = AsyncMock(return_value={"step_id": "s1", "status": "completed", "output": "single"})
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.COMPLETED
        assert agent._execute_step.call_count == 4, "3-branch fanout + 1 deterministic re-run"
        assert step.parameters.get("_review_feedback") == "try again"

    async def test_reviewer_loop_deterministic_redelegation_failed_rerun(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=_review_rejection("try again"))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(side_effect=[True, False])
        agent._execute_step = AsyncMock(side_effect=[
            {"step_id": "s1", "output": "ok"},
            {"step_id": "s1", "output": "ok"},
            {"step_id": "s1", "output": "ok"},
            {"status": "failed", "error": "rerun died"},
        ])
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1
        assert "rerun died" in result.errors[0]

    async def test_reviewer_loop_redelegation_branches_all_fail(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=_review_rejection("nope"))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(return_value=True)
        agent._execute_step = AsyncMock(side_effect=[
            {"step_id": "s1", "output": "ok"},
            {"step_id": "s1", "output": "ok"},
            {"step_id": "s1", "output": "ok"},
            RuntimeError("branch died"),
            RuntimeError("branch died"),
            RuntimeError("branch died"),
        ])
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1
        assert "All parallel branches failed" in result.errors[0]

    async def test_reviewer_loop_exhausts_rejections(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=_review_rejection("still wrong"))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(return_value=True)
        calls = []

        async def fake_executor(step, ctx):
            calls.append(1)
            return {"step_id": step.step_id, "output": "draft"}

        agent.set_step_executor(fake_executor)
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.FAILED
        assert len(calls) == 3 * (1 + MAX_REVIEWER_REDELEGATIONS)
        assert any("still wrong" in e for e in result.errors)

    async def test_reviewer_loop_flag_off_no_redelegation(self, monkeypatch):
        monkeypatch.delenv("ATOM_REVIEWER_LOOP_ENABLED", raising=False)
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=_review_rejection("nope"))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(return_value=True)
        calls = []

        async def fake_executor(step, ctx):
            calls.append(1)
            return {"step_id": step.step_id, "output": "draft"}

        agent.set_step_executor(fake_executor)
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.FAILED
        assert len(calls) == 3, "single pass — rejection is fatal when the loop is off"

    async def test_reviewer_loop_skips_parking_without_workflow_id(self, monkeypatch):
        monkeypatch.setenv("ATOM_REVIEWER_LOOP_ENABLED", "true")
        agent = ConductorAgent()
        verifier = MagicMock()
        verifier.verify = AsyncMock(return_value=_review_rejection("fix"))
        agent.set_verification_orchestrator(verifier)
        agent._is_stochastic_executor = Mock(side_effect=[True, False])
        agent._execute_step = AsyncMock(return_value={"step_id": "s1", "output": "ok"})
        step = WorkflowStep(step_id="s1", step_type=StepType.AGENT)
        ctx = _make_context([step], "s1", workflow_id="")
        result = await agent.execute_workflow([step], "s1", ctx, strategy=ExecutionStrategy.PARALLEL_CONSENSUS)
        assert result.status == ExecutionStatus.COMPLETED
        assert step.parameters.get("_review_feedback") == "fix"

    async def test_reconcile_branch_conflicts_delegates(self):
        agent = ConductorAgent()
        with patch("core.orchestration.verification.voting.VotingVerifier") as VV:
            vv = VV.return_value
            vv.reconcile_only = AsyncMock(return_value={"merged": True})
            out = await agent._reconcile_branch_conflicts("s1", [{"a": 1}, {"a": 2}])
        assert out == {"merged": True}
        vv.reconcile_only.assert_awaited_once_with("s1", [{"a": 1}, {"a": 2}])

    def test_verification_orchestrator_lazy_construction(self):
        agent = ConductorAgent()
        with patch("core.orchestration.verification.VerificationOrchestrator") as VO:
            inst = VO.return_value
            assert agent._get_or_create_verification_orchestrator() is inst
            assert agent._get_or_create_verification_orchestrator() is inst
        VO.assert_called_once()

    def test_set_verification_orchestrator(self):
        agent = ConductorAgent()
        orch = object()
        agent.set_verification_orchestrator(orch)
        assert agent._verification_orchestrator is orch


class TestStepExecutor:
    async def test_injected_executor_dict_result(self):
        agent = ConductorAgent()
        agent.set_step_executor(lambda s, c: {"step_id": s.step_id, "status": "completed"})
        out = await agent._execute_step(WorkflowStep(step_id="s1"), _make_context([], "s1"))
        assert out["status"] == "completed"

    async def test_injected_executor_coroutine_result(self):
        agent = ConductorAgent()

        async def exec_step(s, c):
            return {"step_id": s.step_id}

        agent.set_step_executor(exec_step)
        out = await agent._execute_step(WorkflowStep(step_id="s1"), _make_context([], "s1"))
        assert out["step_id"] == "s1"

    async def test_injected_executor_scalar_wrapped(self):
        agent = ConductorAgent()
        agent.set_step_executor(lambda s, c: "plain")
        out = await agent._execute_step(WorkflowStep(step_id="s1"), _make_context([], "s1"))
        assert out["status"] == "completed"
        assert out["output"] == "plain"

    async def test_injected_executor_exception_failed_dict(self):
        agent = ConductorAgent()

        def boom(s, c):
            raise RuntimeError("executor died")

        agent.set_step_executor(boom)
        out = await agent._execute_step(WorkflowStep(step_id="s1"), _make_context([], "s1"))
        assert out["status"] == "failed"
        assert "executor died" in out["error"]

    async def test_mock_fallback(self):
        agent = ConductorAgent()
        out = await agent._execute_step(WorkflowStep(step_id="s1", name="n"), _make_context([], "s1"))
        assert out["output"] == "Result from n"

    def test_is_stochastic_executor(self):
        agent = ConductorAgent()
        assert agent._is_stochastic_executor() is False
        agent.set_step_executor(lambda s, c: {})
        assert agent._is_stochastic_executor() is True

    async def test_execute_and_track_failed_dict(self):
        agent = ConductorAgent()
        agent.set_step_executor(lambda s, c: {"status": "failed", "error": "zap"})
        step = WorkflowStep(step_id="s1")
        result = OrchestrationResult()
        await agent._execute_and_track(step, _make_context([step], "s1"), result)
        assert step.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1

    async def test_execute_and_track_scalar_failed(self):
        agent = ConductorAgent()
        agent.set_step_executor(lambda s, c: "not a dict")
        step = WorkflowStep(step_id="s1")
        result = OrchestrationResult()
        await agent._execute_and_track(step, _make_context([step], "s1"), result)
        assert step.status == ExecutionStatus.COMPLETED
        assert result.completed_steps == 1

    async def test_execute_and_track_timeout(self):
        agent = ConductorAgent()

        async def slow(s, c):
            await asyncio.sleep(5)
            return {}

        agent.set_step_executor(slow)
        step = WorkflowStep(step_id="s1", timeout_seconds=1)
        result = OrchestrationResult()
        await agent._execute_and_track(step, _make_context([step], "s1"), result)
        assert step.status == ExecutionStatus.FAILED
        assert result.failed_steps == 1


class TestWorkflowLifecycleControl:
    def test_pause_and_resume(self):
        agent = ConductorAgent()
        ctx = _make_context([], "s1")
        agent._active_workflows["exec1"] = ctx
        assert agent.pause_workflow("nope") is False
        assert agent.pause_workflow("exec1") is True
        assert ctx.status == ExecutionStatus.PAUSED
        assert agent.resume_workflow("exec1") is True
        assert ctx.status == ExecutionStatus.RUNNING
        assert agent.resume_workflow("exec1") is False, "not paused anymore"
        assert agent.resume_workflow("nope") is False

    def test_cancel_workflow(self):
        agent = ConductorAgent()
        ctx = _make_context([], "s1")
        agent._active_workflows["exec1"] = ctx
        assert agent.cancel_workflow("exec1") is True
        assert ctx.status == ExecutionStatus.CANCELLED
        assert agent.cancel_workflow("nope") is False

    def test_get_workflow_status_active(self):
        agent = ConductorAgent()
        ctx = _make_context([WorkflowStep(step_id="s1")], "s1")
        agent._active_workflows["exec1"] = ctx
        status = agent.get_workflow_status("exec1")
        assert status["execution_id"] == "exec1"
        assert status["total_steps"] == 1

    def test_get_workflow_status_completed(self):
        agent = ConductorAgent()
        result = OrchestrationResult(
            workflow_id="wf", execution_id="exec1", status=ExecutionStatus.COMPLETED,
            completed_steps=2, failed_steps=0, duration_seconds=1.5,
        )
        agent._completed_workflows["exec1"] = result
        status = agent.get_workflow_status("exec1")
        assert status["status"] == "completed"
        assert status["duration_seconds"] == 1.5

    def test_get_workflow_status_missing(self):
        assert ConductorAgent().get_workflow_status("nope") is None

    def test_get_statistics(self):
        agent = ConductorAgent()
        agent._active_workflows["a"] = _make_context([], "s1")
        agent._completed_workflows["b"] = OrchestrationResult()
        agent._event_subscriptions["evt"].append(lambda e: None)
        stats = agent.get_statistics()
        assert stats["active_workflows"] == 1
        assert stats["completed_workflows"] == 1
        assert stats["event_subscriptions"] == 1

    def test_factory_singleton(self):
        agent = get_conductor_agent()
        assert get_conductor_agent() is agent


# ===========================================================================
# event_bus.py
# ===========================================================================


class TestEventBusDataclasses:
    def test_event_type_values(self):
        assert EventType.WORKFLOW_STARTED.value == "workflow.started"
        assert EventType.SYSTEM_SHUTDOWN.value == "system.shutdown"

    def test_delivery_values(self):
        assert EventDelivery.FIRE_AND_FORGET.value == "fire_and_forget"

    def test_config_defaults(self):
        cfg = EventBusConfig()
        assert cfg.default_delivery == EventDelivery.AT_LEAST_ONCE
        assert cfg.max_retry_attempts == 3
        assert cfg.enable_replay is True

    def test_event_to_dict(self):
        ev = WorkflowEvent(
            event_id="e1", event_type=EventType.STEP_STARTED, source="wf",
            data={"a": 1}, metadata={"m": 2}, published_at=datetime.now(),
            expires_at=None,
        )
        d = ev.to_dict()
        assert d["event_id"] == "e1"
        assert d["event_type"] == "step.started"
        assert d["published_at"] == ev.published_at.isoformat()
        assert d["expires_at"] is None

    def test_event_fingerprint(self):
        e1 = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="s", data={"a": 1})
        e2 = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="s", data={"a": 1})
        e3 = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="s", data={"a": 2})
        assert e1.get_fingerprint() == e2.get_fingerprint()
        assert e1.get_fingerprint() != e3.get_fingerprint()

    def test_subscription_matches(self):
        sub = EventSubscription(
            subscription_id="sub1", subscriber_id="svc",
            event_types=[EventType.WORKFLOW_STARTED],
            source_filter=r"wf-.*",
            data_filter={"tier": "gold"},
        )
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={"tier": "gold"})
        assert sub.matches(ev) is True
        assert sub.matches(WorkflowEvent(event_type=EventType.STEP_STARTED, source="wf-1", data={"tier": "gold"})) is False
        assert sub.matches(WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="other", data={"tier": "gold"})) is False
        assert sub.matches(WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={"tier": "silver"})) is False
        sub.active = False
        assert sub.matches(ev) is False

    def test_subscription_matches_no_filters(self):
        sub = EventSubscription(subscription_id="s", subscriber_id="svc")
        assert sub.matches(WorkflowEvent()) is True


class TestEventBusPubSub:
    def test_publish_stores_and_buffers(self):
        bus = EventBus()
        eid = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"k": "v"})
        assert eid in bus._events
        assert bus._events[eid].published_at is not None
        assert len(bus._event_buffer) == 1
        assert len(bus._event_fingerprints) == 1

    def test_publish_with_expiry_and_semantic(self):
        bus = EventBus()
        eid = bus.publish(
            EventType.STEP_STARTED, "wf-1", {}, source_type="external",
            delivery_semantic=EventDelivery.FIRE_AND_FORGET,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        ev = bus._events[eid]
        assert ev.delivery_semantic == EventDelivery.FIRE_AND_FORGET
        assert ev.expires_at is not None

    def test_publish_duplicate_returns_existing_id(self):
        bus = EventBus()
        eid1 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        eid2 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        assert eid2 == eid1
        assert len(bus._event_buffer) == 1

    def test_publish_duplicate_after_eviction_stores_fresh(self):
        bus = EventBus()
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf-1", data={"a": 1})
        bus._event_fingerprints.add(ev.get_fingerprint())
        eid = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {"a": 1})
        assert eid in bus._events, "evicted duplicate must be stored so the id resolves"
        assert len(bus._event_buffer) == 1

    def test_subscribe_and_unsubscribe(self):
        bus = EventBus()
        handler = Mock()
        sid = bus.subscribe("svc", [EventType.WORKFLOW_STARTED], handler)
        assert sid in bus._subscriptions
        assert sid in bus._type_index[EventType.WORKFLOW_STARTED]
        assert bus.unsubscribe(sid) is True
        assert sid not in bus._subscriptions
        assert sid not in bus._type_index[EventType.WORKFLOW_STARTED]
        assert bus.unsubscribe(sid) is False

    def test_unsubscribe_all(self):
        bus = EventBus()
        bus.subscribe("svc", [EventType.WORKFLOW_STARTED], Mock())
        bus.subscribe("svc", [EventType.STEP_STARTED], Mock())
        bus.subscribe("other", [EventType.WORKFLOW_STARTED], Mock())
        assert bus.unsubscribe_all("svc") == 2
        assert bus.unsubscribe_all("svc") == 0
        assert len(bus._subscriptions) == 1

    def test_get_events_filters(self):
        bus = EventBus()
        eid1 = bus.publish(EventType.WORKFLOW_STARTED, "wf-1", {})
        bus.publish(EventType.STEP_STARTED, "wf-1", {})
        bus.publish(EventType.WORKFLOW_STARTED, "wf-2", {})
        assert len(bus.get_events(source="wf-1")) == 2
        assert len(bus.get_events(event_type=EventType.WORKFLOW_STARTED)) == 2
        assert len(bus.get_events(source="wf-1", event_type=EventType.STEP_STARTED)) == 1
        assert len(bus.get_events(limit=1)) == 1
        assert len(bus.get_events(since=datetime.now() + timedelta(days=1))) == 0
        assert bus.get_events()[0].event_id == eid1

    def test_get_subscriptions_filter(self):
        bus = EventBus()
        bus.subscribe("svc1", [EventType.WORKFLOW_STARTED], Mock())
        bus.subscribe("svc2", [EventType.WORKFLOW_STARTED], Mock())
        assert len(bus.get_subscriptions()) == 2
        assert len(bus.get_subscriptions(subscriber_id="svc1")) == 1

    def test_start_stop(self):
        bus = EventBus()
        assert bus._running is False
        bus.start()
        assert bus._running is True
        bus.start()
        bus.stop()
        assert bus._running is False

    def test_stop_without_thread(self):
        bus = EventBus()
        bus.stop()
        assert bus._running is False


class TestEventDelivery:
    def _bus_with_sub(self, handler, delivery=EventDelivery.AT_LEAST_ONCE, max_retries=3):
        bus = EventBus()
        sub = EventSubscription(
            subscription_id="sub1", subscriber_id="svc",
            event_types=[EventType.WORKFLOW_STARTED],
            handler=handler, delivery_semantic=delivery, max_retries=max_retries,
        )
        bus._subscriptions["sub1"] = sub
        bus._type_index[EventType.WORKFLOW_STARTED].append("sub1")
        return bus

    def test_deliver_event_success(self):
        seen = []
        bus = self._bus_with_sub(lambda ev: seen.append(ev))
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._deliver_event(ev)
        assert seen == [ev]
        assert ev.delivered_to == ["svc"]
        sub = bus._subscriptions["sub1"]
        assert sub.events_processed == 1
        assert sub.last_event_at is not None

    def test_deliver_event_exactly_once_acks(self):
        bus = self._bus_with_sub(lambda ev: None, delivery=EventDelivery.EXACTLY_ONCE)
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._deliver_event(ev)
        assert f"{ev.event_id}:svc" in bus._ack_results
        ack = bus._ack_results[f"{ev.event_id}:svc"]
        assert ack.success is True
        assert ack.subscriber_id == "svc"

    def test_deliver_event_skips_unknown_subscription(self):
        bus = self._bus_with_sub(lambda ev: None)
        bus._type_index[EventType.WORKFLOW_STARTED].append("ghost")
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._deliver_event(ev)
        assert ev.delivered_to == ["svc"]

    def test_deliver_event_skips_non_matching(self):
        bus = self._bus_with_sub(lambda ev: None)
        sub = bus._subscriptions["sub1"]
        sub.source_filter = r"^wf-.*"
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="other", data={})
        bus._deliver_event(ev)
        assert ev.delivered_to == []
        assert sub.events_processed == 0

    def test_deliver_event_retry_and_requeue(self):
        calls = {"n": 0}

        def boom(ev):
            calls["n"] += 1
            raise RuntimeError("handler broke")

        bus = self._bus_with_sub(boom)
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._deliver_event(ev)
        assert ev.failed_deliveries["svc"] == 1
        assert getattr(ev, "_pending_retries", set()) == {"sub1"}
        queued = bus._delivery_queue.get_nowait()
        assert queued is ev
        bus._deliver_event(queued)
        assert ev.failed_deliveries["svc"] == 2
        assert bus._delivery_queue.get_nowait() is ev

    def test_deliver_event_retry_exhausted_no_requeue(self):
        def boom(ev):
            raise RuntimeError("handler broke")

        bus = self._bus_with_sub(boom, max_retries=1)
        bus.config.max_retry_attempts = 1
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._deliver_event(ev)
        assert bus._delivery_queue.empty(), "no requeue once attempts exhausted"

    def test_retry_skips_already_succeeded_subscribers(self):
        good = Mock()
        bad = Mock(side_effect=RuntimeError("boom"))
        bus = EventBus()
        bus._subscriptions["sub_good"] = EventSubscription(
            subscription_id="sub_good", subscriber_id="good_svc",
            event_types=[EventType.WORKFLOW_STARTED], handler=good,
        )
        bus._subscriptions["sub_bad"] = EventSubscription(
            subscription_id="sub_bad", subscriber_id="bad_svc",
            event_types=[EventType.WORKFLOW_STARTED], handler=bad,
        )
        bus._type_index[EventType.WORKFLOW_STARTED].extend(["sub_good", "sub_bad"])
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._deliver_event(ev)
        assert ev._pending_retries == {"sub_bad"}
        assert good.call_count == 1
        bus._deliver_event(ev)
        assert good.call_count == 1, "already-delivered subscriber skipped on retry"
        assert bad.call_count == 2

    def test_delivery_loop_expired_event_skipped(self):
        bus = EventBus()
        bus._running = True
        seen = []
        bus._deliver_event = Mock(side_effect=lambda ev: seen.append(ev))
        ev = WorkflowEvent(
            event_type=EventType.WORKFLOW_STARTED, source="wf", data={},
            expires_at=datetime.now() - timedelta(seconds=1),
        )
        bus._delivery_queue.put(ev)
        thread = threading.Thread(target=bus._delivery_loop, daemon=True)
        thread.start()
        deadline = time.time() + 5
        while not bus._delivery_queue.empty() and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
        bus._running = False
        thread.join(timeout=5)
        assert seen == [], "expired event must not be delivered"

    def test_delivery_loop_delivers_and_empty_continue(self):
        bus = EventBus()
        bus._running = True
        seen = []
        bus._deliver_event = Mock(side_effect=lambda ev: seen.append(ev))
        ev = WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf", data={})
        bus._delivery_queue.put(ev)
        thread = threading.Thread(target=bus._delivery_loop, daemon=True)
        thread.start()
        deadline = time.time() + 5
        while not bus._delivery_queue.empty() and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
        bus._running = False
        thread.join(timeout=5)
        assert seen == [ev]

    def test_delivery_loop_survives_errors(self):
        bus = EventBus()
        bus._running = True
        bus._deliver_event = Mock(side_effect=RuntimeError("loop boom"))
        bus._delivery_queue.put(WorkflowEvent(event_type=EventType.WORKFLOW_STARTED, source="wf"))
        thread = threading.Thread(target=bus._delivery_loop, daemon=True)
        thread.start()
        deadline = time.time() + 5
        while not bus._delivery_queue.empty() and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
        bus._running = False
        thread.join(timeout=5)
        assert not thread.is_alive()

    def test_get_statistics(self):
        bus = EventBus()
        bus.publish(EventType.WORKFLOW_STARTED, "wf", {})
        bus.subscribe("svc", [EventType.WORKFLOW_STARTED], Mock())
        stats = bus.get_statistics()
        assert stats["total_events"] == 1
        assert stats["buffer_size"] == 1
        assert stats["total_subscriptions"] == 1
        assert stats["active_subscriptions"] == 1
        assert stats["running"] is False


class TestWorkflowTriggers:
    def _bus(self):
        return EventBus()

    def test_trigger_no_condition_fires(self):
        bus = self._bus()
        triggered = []
        original = bus.publish

        def spy(event_type, source, data, **kw):
            triggered.append((event_type, source, data))
            return original(event_type, source, data, **kw)

        bus.publish = spy
        sub_id = bus.create_workflow_trigger("wf-1", EventType.WEBHOOK_TRIGGER)
        ev = WorkflowEvent(event_type=EventType.WEBHOOK_TRIGGER, source="src", data={})
        bus._deliver_event(ev)
        assert any(t[0] == EventType.WORKFLOW_STARTED for t in triggered)
        assert bus._subscriptions[sub_id].subscriber_id == "wf-1"

    def test_trigger_condition_met_fires(self):
        bus = self._bus()
        triggered = []
        original = bus.publish

        def spy(event_type, source, data, **kw):
            triggered.append(data)
            return original(event_type, source, data, **kw)

        bus.publish = spy
        bus.create_workflow_trigger("wf-1", EventType.WEBHOOK_TRIGGER, condition='data["amount"] > 100')
        ev = WorkflowEvent(event_type=EventType.WEBHOOK_TRIGGER, source="src", data={"amount": 500})
        bus._deliver_event(ev)
        assert len(triggered) == 1
        assert triggered[0]["triggered_by"] == "webhook.trigger"

    def test_trigger_condition_not_met_no_fire(self):
        bus = self._bus()
        bus.publish = Mock()
        bus.create_workflow_trigger("wf-1", EventType.WEBHOOK_TRIGGER, condition='data["amount"] > 100')
        ev = WorkflowEvent(event_type=EventType.WEBHOOK_TRIGGER, source="src", data={"amount": 50})
        bus._deliver_event(ev)
        bus.publish.assert_not_called()

    def test_trigger_delivery_safe_eval_error_no_fire(self):
        bus = self._bus()
        bus.publish = Mock()
        bus.create_workflow_trigger("wf-1", EventType.WEBHOOK_TRIGGER, condition="data['x'] > data['y']")
        ev = WorkflowEvent(
            event_type=EventType.WEBHOOK_TRIGGER, source="src",
            data={"x": {"a": 1}, "y": {"b": 2}},
        )
        bus._deliver_event(ev)
        bus.publish.assert_not_called()

    def test_trigger_delivery_generic_exception_no_fire(self, monkeypatch):
        def boom(*a, **kw):
            raise RuntimeError("evaluator down")

        monkeypatch.setattr("core.safe_evaluator.safe_eval", boom)
        bus = self._bus()
        bus.publish = Mock()
        bus.create_workflow_trigger("wf-1", EventType.WEBHOOK_TRIGGER, condition="data['x'] > 1")
        ev = WorkflowEvent(event_type=EventType.WEBHOOK_TRIGGER, source="src", data={"x": 5})
        bus._deliver_event(ev)
        bus.publish.assert_not_called()

    def test_trigger_registration_rejects_syntax_error(self):
        with pytest.raises(ValueError, match="Invalid trigger condition syntax"):
            self._bus().create_workflow_trigger("wf", EventType.WORKFLOW_STARTED, condition="data['x'] >")

    def test_trigger_registration_rejects_attribute_access(self):
        with pytest.raises(ValueError, match="attribute/method-call syntax"):
            self._bus().create_workflow_trigger("wf", EventType.WORKFLOW_STARTED, condition="event.status == 'done'")

    def test_trigger_registration_rejects_method_call(self):
        with pytest.raises(ValueError, match="attribute/method-call syntax"):
            self._bus().create_workflow_trigger("wf", EventType.WORKFLOW_STARTED, condition='data.get("status") == "done"')

    def test_trigger_registration_rejects_non_whitelisted_call(self):
        with pytest.raises(ValueError, match="does not allow"):
            self._bus().create_workflow_trigger("wf", EventType.WORKFLOW_STARTED, condition='print("x")')

    def test_trigger_registration_rejects_dry_run_failure(self):
        with pytest.raises(ValueError, match="rejected by safe evaluator"):
            self._bus().create_workflow_trigger("wf", EventType.WORKFLOW_STARTED, condition="missing_var == 1")

    def test_trigger_subscript_condition_registers(self):
        bus = self._bus()
        sub_id = bus.create_workflow_trigger("wf", EventType.WORKFLOW_STARTED, condition='data["status"] == "done"')
        assert bus._subscriptions[sub_id].subscriber_id == "wf"


class TestEventBusFactory:
    def test_factory_singleton_starts_bus(self):
        bus = get_event_bus()
        assert bus._running is True
        assert get_event_bus() is bus
        bus.stop()


# ===========================================================================
# workflow_composer.py
# ===========================================================================


class TestComposerDataclasses:
    def test_primitive_values(self):
        assert CompositionPrimitive.TRY_CATCH.value == "try_catch"
        assert CompositionStrategy.OPTIMAL.value == "optimal"

    def test_config_defaults(self):
        cfg = ComposerConfig()
        assert cfg.max_depth == 10
        assert cfg.validate_composition is True
        assert cfg.check_acyclic_deps is True

    def test_node_defaults(self):
        node = CompositionNode()
        assert node.primitive == CompositionPrimitive.SEQUENCE
        assert node.max_iterations == 100

    def test_composed_defaults(self):
        wf = ComposedWorkflow()
        assert wf.composer_type == CompositionStrategy.DEPENDENCY_AWARE
        assert wf.validated is False


class TestCompose:
    def test_compose_empty_primitives(self):
        with pytest.raises(ValueError, match="No primitives"):
            WorkflowComposer().compose([])

    def test_compose_single(self):
        wf = WorkflowComposer().compose([(CompositionPrimitive.SEQUENCE, {})], workflow_id="wf1", name="N")
        assert wf.workflow_id == "wf1"
        assert wf.name == "N"
        assert wf.root.primitive == CompositionPrimitive.SEQUENCE
        assert wf.node_count == 1
        assert wf.validated is True

    def test_compose_generates_workflow_id(self):
        wf = WorkflowComposer().compose([(CompositionPrimitive.SEQUENCE, {})])
        assert wf.workflow_id.startswith("comp_wf_")

    def test_compose_sequence_chain(self):
        wf = WorkflowComposer().compose(
            [(CompositionPrimitive.SEQUENCE, {})] + [(CompositionPrimitive.SEQUENCE, {})] * 3
        )
        assert wf.node_count == 4

    def test_compose_parallel_creates_parallel_root(self):
        wf = WorkflowComposer().compose(
            [(CompositionPrimitive.SEQUENCE, {}), (CompositionPrimitive.PARALLEL, {})]
        )
        assert wf.root.primitive == CompositionPrimitive.PARALLEL
        assert wf.node_count == 3

    def test_compose_choice_and_loop_appended(self):
        wf = WorkflowComposer().compose(
            [
                (CompositionPrimitive.SEQUENCE, {}),
                (CompositionPrimitive.CHOICE, {}),
                (CompositionPrimitive.LOOP, {}),
            ]
        )
        assert len(wf.root.children) == 2
        assert wf.root.children[0].primitive == CompositionPrimitive.CHOICE
        assert wf.root.children[1].primitive == CompositionPrimitive.LOOP

    def test_compose_validation_disabled(self):
        composer = WorkflowComposer(ComposerConfig(validate_composition=False))
        wf = composer.compose([(CompositionPrimitive.SEQUENCE, {})])
        assert wf.validated is False
        assert wf.validation_errors == []


class TestComposerMetrics:
    def test_count_nodes_nested(self):
        root = CompositionNode(
            node_id="r", primitive=CompositionPrimitive.PARALLEL,
            children=[
                CompositionNode(node_id="a"),
                CompositionNode(node_id="b", children=[CompositionNode(node_id="c")]),
            ],
        )
        assert WorkflowComposer()._count_nodes(root) == 4

    def test_estimate_duration_leaf(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="r")
        assert composer._estimate_duration(root) == 1000.0

    def test_estimate_duration_parallel_takes_max(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            node_id="r", primitive=CompositionPrimitive.PARALLEL,
            children=[
                CompositionNode(node_id="a", config={"duration_ms": 5000}),
                CompositionNode(node_id="b", config={"duration_ms": 2000}),
            ],
        )
        assert composer._estimate_duration(root) == 5000.0

    def test_estimate_duration_parallel_empty(self):
        root = CompositionNode(node_id="r", primitive=CompositionPrimitive.PARALLEL)
        assert WorkflowComposer()._estimate_duration(root) == 1000.0

    def test_estimate_duration_sequence_sums(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            node_id="r", primitive=CompositionPrimitive.SEQUENCE,
            children=[
                CompositionNode(node_id="a", config={"duration_ms": 1000}),
                CompositionNode(node_id="b", config={"duration_ms": 2000}),
            ],
        )
        assert composer._estimate_duration(root) == 3000.0

    def test_estimate_duration_sequence_leaf_falls_back(self):
        root = CompositionNode(node_id="r", primitive=CompositionPrimitive.SEQUENCE)
        assert WorkflowComposer()._estimate_duration(root) == 1000.0

    def test_estimate_duration_loop_multiplies(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            node_id="r", primitive=CompositionPrimitive.LOOP,
            config={"iterations": 4},
            children=[CompositionNode(node_id="a", config={"duration_ms": 1000})],
        )
        assert composer._estimate_duration(root) == 4000.0

    def test_estimate_duration_loop_default_iterations(self):
        root = CompositionNode(node_id="r", primitive=CompositionPrimitive.LOOP)
        assert WorkflowComposer()._estimate_duration(root) == 10000.0

    def test_estimate_duration_override_and_stored(self):
        composer = WorkflowComposer()
        child = CompositionNode(node_id="a", config={"duration_ms": 777.0})
        root = CompositionNode(node_id="r", primitive=CompositionPrimitive.SEQUENCE, children=[child])
        assert composer._estimate_duration(root) == 777.0
        assert child.estimated_duration_ms == 777.0
        assert root.estimated_duration_ms == 777.0


class TestComposerValidation:
    def _deep_tree(self, depth):
        root = CompositionNode(node_id="r", depth=0)
        node = root
        for i in range(1, depth + 1):
            child = CompositionNode(node_id=f"n{i}", depth=i)
            node.children.append(child)
            node = child
        return root

    def test_validate_depth_exceeded(self):
        composer = WorkflowComposer(ComposerConfig(max_depth=2))
        is_valid, errors = composer._validate_composition(self._deep_tree(5))
        assert is_valid is False
        assert any("exceeds maximum" in e for e in errors)

    def test_validate_valid_tree(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="r", children=[CompositionNode(node_id="a")])
        assert composer._validate_composition(root) == (True, [])

    def test_validate_cycle_detected(self):
        composer = WorkflowComposer()
        a = CompositionNode(node_id="a")
        b = CompositionNode(node_id="b")
        root = CompositionNode(node_id="r", children=[a])
        a.children.append(b)
        b.children.append(a)
        is_valid, errors = composer._validate_composition(root)
        assert is_valid is False
        assert any("Cyclic dependencies" in e for e in errors)

    def test_detect_cycles_duplicate_node_ids(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="")
        root.children = [CompositionNode(node_id=""), CompositionNode(node_id="")]
        cycles = composer._detect_cycles(root)
        assert cycles, "duplicate node ids are reported as cycles"
        assert all(" -> " in c for c in cycles)

    def test_detect_cycles_acyclic(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="r", children=[CompositionNode(node_id="a")])
        assert composer._detect_cycles(root) == []

    def test_detect_cycles_visited_skip_on_duplicate_node_id(self):
        composer = WorkflowComposer()
        a = CompositionNode(node_id="a", children=[CompositionNode(node_id="x")])
        b = CompositionNode(node_id="b", children=[CompositionNode(node_id="x")])
        root = CompositionNode(node_id="r", children=[a, b])
        assert composer._detect_cycles(root) == [], "shared node_id across branches is not a cycle"

    def test_validate_primitives_parallel_requires_two(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="p", primitive=CompositionPrimitive.PARALLEL, children=[CompositionNode(node_id="a")])
        errors = []
        composer._validate_primitives(root, errors)
        assert any("requires at least 2 children" in e for e in errors)

    def test_validate_primitives_loop_requires_condition(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="l", primitive=CompositionPrimitive.LOOP)
        errors = []
        composer._validate_primitives(root, errors)
        assert any("requires condition" in e for e in errors)

    def test_validate_primitives_cycle_safe(self):
        composer = WorkflowComposer()
        a = CompositionNode(node_id="a")
        root = CompositionNode(node_id="r", children=[a])
        a.children.append(root)
        errors = []
        composer._validate_primitives(root, errors)
        assert errors == []

    def test_get_max_depth(self):
        composer = WorkflowComposer()
        assert composer._get_max_depth(self._deep_tree(3)) == 3

    def test_get_max_depth_cycle_safe(self):
        composer = WorkflowComposer()
        a = CompositionNode(node_id="a", depth=1)
        root = CompositionNode(node_id="r", children=[a])
        a.children.append(root)
        assert composer._get_max_depth(root) == 1

    def test_validate_composition_skips_cycle_check_when_disabled(self):
        composer = WorkflowComposer(ComposerConfig(check_acyclic_deps=False, validate_primitives=False))
        root = CompositionNode(node_id="r")
        assert composer._validate_composition(root) == (True, [])


class TestComposerMisc:
    def test_decompose_empty(self):
        assert WorkflowComposer().decompose(ComposedWorkflow()) == []

    def test_decompose_tree(self):
        root = CompositionNode(
            node_id="r", primitive=CompositionPrimitive.PARALLEL,
            config={"a": 1},
            children=[CompositionNode(node_id="c1", config={"b": 2})],
        )
        wf = ComposedWorkflow(root=root)
        prims = WorkflowComposer().decompose(wf)
        assert [(p.value, c) for p, c in prims] == [("parallel", {"a": 1}), ("sequence", {"b": 2})]

    def test_get_statistics(self):
        stats = WorkflowComposer().get_statistics()
        assert stats["config"]["max_depth"] == 10
        assert stats["validation_enabled"] is True

    def test_factory_singleton(self):
        composer = get_workflow_composer()
        assert get_workflow_composer() is composer


# ===========================================================================
# workflow_templates.py
# ===========================================================================


class TestTemplateEnumsAndParams:
    def test_category_values(self):
        assert TemplateCategory.DATA_PIPELINE.value == "data_pipeline"
        assert TemplateCategory.MONITORING.value == "monitoring"

    def test_parameter_type_values(self):
        assert ParameterType.DATETIME.value == "datetime"
        assert ParameterType.ENUM.value == "enum"

    def test_parameter_validate_none(self):
        required = TemplateParameter(name="r", required=True)
        assert required.validate(None) is False
        optional = TemplateParameter(name="o", required=False)
        assert optional.validate(None) is True

    def test_parameter_validate_string(self):
        p = TemplateParameter(type=ParameterType.STRING)
        assert p.validate("x") is True
        assert p.validate(5) is False
        p.pattern = r"^[a-z]+$"
        assert p.validate("abc") is True
        assert p.validate("ABC") is False

    def test_parameter_validate_integer(self):
        p = TemplateParameter(type=ParameterType.INTEGER, min_value=1, max_value=5)
        assert p.validate(3) is True
        assert p.validate("3") is False
        assert p.validate(0) is False
        assert p.validate(6) is False

    def test_parameter_validate_float(self):
        p = TemplateParameter(type=ParameterType.FLOAT, min_value=0.5, max_value=2.5)
        assert p.validate(1) is True
        assert p.validate("1") is False
        assert p.validate(0.1) is False
        assert p.validate(9.0) is False

    def test_parameter_validate_boolean(self):
        p = TemplateParameter(type=ParameterType.BOOLEAN)
        assert p.validate(True) is True
        assert p.validate(1) is False

    def test_parameter_validate_array(self):
        p = TemplateParameter(type=ParameterType.ARRAY)
        assert p.validate([1, 2]) is True
        assert p.validate("nope") is False

    def test_parameter_validate_enum(self):
        p = TemplateParameter(type=ParameterType.ENUM, allowed_values=["a", "b"])
        assert p.validate("a") is True
        assert p.validate("c") is False
        p.allowed_values = None
        assert p.validate("anything") is True

    def test_parameter_validate_object_date_datetime(self):
        for ptype in (ParameterType.OBJECT, ParameterType.DATE, ParameterType.DATETIME):
            p = TemplateParameter(type=ptype)
            assert p.validate("anything") is True

    def test_step_template_defaults(self):
        step = WorkflowStepTemplate()
        assert step.step_type == "agent"
        assert step.timeout_seconds == 300
        assert step.retry_count == 3


class TestWorkflowTemplateValidation:
    def _template(self, **kw):
        return WorkflowTemplate(
            template_id="t1",
            parameters=[
                TemplateParameter(name="req", type=ParameterType.STRING, required=True),
                TemplateParameter(name="opt", type=ParameterType.INTEGER, required=False),
            ],
            **kw,
        )

    def test_validate_parameters_missing_required(self):
        t = self._template()
        valid, errors = t.validate_parameters({})
        assert valid is False
        assert any("'req' is missing" in e for e in errors)

    def test_validate_parameters_invalid_value(self):
        t = self._template()
        valid, errors = t.validate_parameters({"req": "ok", "opt": "not-int"})
        assert valid is False
        assert any("'opt' validation failed" in e for e in errors)

    def test_validate_parameters_schema_failure(self):
        t = self._template(
            input_schema={
                "type": "object",
                "properties": {"req": {"type": "string"}},
                "required": ["req"],
            }
        )
        valid, errors = t.validate_parameters({"req": "ok"})
        assert valid is True
        bad = self._template(input_schema={"type": "object", "properties": {"req": {"type": "integer"}}})
        valid, errors = bad.validate_parameters({"req": "ok"})
        assert valid is False
        assert any("Schema validation failed" in e for e in errors)

    def test_instantiate_invalid_parameters_raises(self):
        with pytest.raises(ValueError, match="Invalid parameters"):
            self._template().instantiate({})

    def test_instantiate_structure(self):
        t = self._template()
        t.steps = [
            WorkflowStepTemplate(
                step_id="s1", name="Step", step_type="agent", agent_type="spec",
                capability="cap", parameters={"prompt": "${req}"},
                depends_on=["d"], next_steps=["n"], condition="c",
                parallel_group="g", timeout_seconds=42,
            )
        ]
        wf = t.instantiate({"req": "hello"})
        assert wf["template_id"] == "t1"
        assert wf["start_step"] == ""
        step = wf["steps"][0]
        assert step["step_id"] == "s1"
        assert step["timeout_seconds"] == 42
        assert step["parameters"]["prompt"] == "hello"

    def test_instantiate_whole_value_keeps_type(self):
        t = self._template()
        t.steps = [WorkflowStepTemplate(step_id="s1", parameters={"n": "${opt}"})]
        wf = t.instantiate({"req": "r", "opt": 42})
        assert wf["steps"][0]["parameters"]["n"] == 42

    def test_instantiate_embedded_placeholder(self):
        t = self._template()
        t.steps = [WorkflowStepTemplate(step_id="s1", parameters={"prompt": "summarize ${req}"})]
        wf = t.instantiate({"req": "Q1"})
        assert wf["steps"][0]["parameters"]["prompt"] == "summarize Q1"

    def test_instantiate_unresolved_placeholder_stays(self):
        t = self._template()
        t.steps = [WorkflowStepTemplate(step_id="s1", parameters={"prompt": "${missing}"})]
        wf = t.instantiate({"req": "r"})
        assert wf["steps"][0]["parameters"]["prompt"] == "${missing}"

    def test_instantiate_non_string_value_untouched(self):
        t = self._template()
        t.steps = [WorkflowStepTemplate(step_id="s1", parameters={"n": 5, "b": True})]
        wf = t.instantiate({"req": "r"})
        assert wf["steps"][0]["parameters"]["n"] == 5
        assert wf["steps"][0]["parameters"]["b"] is True

    def test_instantiate_copies_lists(self):
        t = self._template()
        depends = ["a", "b"]
        t.steps = [WorkflowStepTemplate(step_id="s1", depends_on=depends)]
        wf = t.instantiate({"req": "r"})
        assert wf["steps"][0]["depends_on"] == ["a", "b"]
        depends.append("c")
        assert wf["steps"][0]["depends_on"] == ["a", "b"], "copies must not alias"


class TestTemplateLibrary:
    def _library(self):
        lib = TemplateLibrary()
        lib.register_template(
            WorkflowTemplate(
                template_id="custom", name="Custom Flow",
                description="a custom description", category=TemplateCategory.ANALYSIS,
                tags=["alpha", "beta"],
            )
        )
        return lib

    def test_registered_templates_loaded(self):
        lib = TemplateLibrary()
        for tid in ("data_sync_automation", "report_generation", "approval_workflow", "monitoring_alert"):
            assert lib.get_template(tid) is not None
        assert len(lib.list_templates()) == 4

    def test_get_template_missing(self):
        assert TemplateLibrary().get_template("nope") is None

    def test_get_templates_by_category(self):
        lib = self._library()
        analysis = lib.get_templates_by_category(TemplateCategory.ANALYSIS)
        assert [t.template_id for t in analysis] == ["custom"]
        assert lib.get_templates_by_category(TemplateCategory.AUTOMATION) != []
        assert lib.get_templates_by_category(TemplateCategory.APPROVAL) != []
        assert lib.get_templates_by_category(TemplateCategory.REPORTING) != []
        assert lib.get_templates_by_category(TemplateCategory.MONITORING) != []

    def test_search_templates(self):
        lib = self._library()
        assert any(t.template_id == "custom" for t in lib.search_templates("custom flow"))
        assert any(t.template_id == "custom" for t in lib.search_templates("a custom description"))
        assert any(t.template_id == "custom" for t in lib.search_templates("alpha"))
        assert lib.search_templates("zzz-no-match") == []

    def test_search_templates_standard(self):
        lib = TemplateLibrary()
        assert any(t.template_id == "data_sync_automation" for t in lib.search_templates("data sync"))
        assert any(t.template_id == "approval_workflow" for t in lib.search_templates("approval"))
        assert any(t.template_id == "report_generation" for t in lib.search_templates("report"))
        assert any(t.template_id == "monitoring_alert" for t in lib.search_templates("alerting"))

    def test_get_statistics(self):
        stats = self._library().get_statistics()
        assert stats["total_templates"] == 5
        assert stats["category_distribution"]["analysis"] == 1
        assert stats["parameter_counts"]["custom"] == 0
        assert stats["parameter_counts"]["data_sync_automation"] == 3

    def test_factory_singleton(self):
        lib = get_template_library()
        assert get_template_library() is lib
