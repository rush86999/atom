"""
Bug-hunt + coverage tests for core/advanced_workflow_system.py (round 2).

Each ``BUG:`` test is written first (TDD), verified to FAIL for the right
reason, then the source is fixed and the test passes.

Focus: conditional logic evaluation (AND/OR/precedence), trigger conditions,
validation rule applicability per parameter type, and shared-state issues.
"""
import pytest
from unittest.mock import MagicMock

from core.advanced_workflow_system import (
    AdvancedWorkflowDefinition,
    WorkflowStep,
    InputParameter,
    ParameterType,
    WorkflowState,
    ExecutionEngine,
    StateManager,
    AdvancedWorkflowSystem,
    ParameterValidator,
)


# =============================================================================
# BUG 1 (HIGH): validate_parameter applies min_length/max_length rules to
# non-string values. For a NUMBER parameter, ``len(str(value))`` is used, so a
# number like 42 fails ``min_length=3`` ("42" has 2 chars). Length rules must
# only apply to STRING/ARRAY/select types, not numbers/booleans.
# =============================================================================

def test_bug_validate_min_length_not_applied_to_number():
    """BUG: a NUMBER parameter with a min_length rule fails validation for
    short numeric values because the rule uses len(str(value))."""
    param = InputParameter(
        name="age",
        type=ParameterType.NUMBER,
        label="Age",
        description="d",
        required=True,
        validation_rules={"min_length": 3},  # nonsensical for numbers
    )
    # 42 is a perfectly valid number; min_length must not reject it.
    is_valid, error = ParameterValidator.validate_parameter(param, 42)
    assert is_valid is True, (
        "min_length rule must not apply to NUMBER parameters"
    )


def test_bug_validate_max_length_not_applied_to_number():
    """BUG: max_length rule should not be applied to NUMBER parameters."""
    param = InputParameter(
        name="big",
        type=ParameterType.NUMBER,
        label="Big",
        description="d",
        required=True,
        validation_rules={"max_length": 3},
    )
    is_valid, _ = ParameterValidator.validate_parameter(param, 123456)
    assert is_valid is True


# =============================================================================
# BUG 2 (HIGH): validate_parameter applies min_value/max_value rules to STRING
# values, which raises TypeError (str < int) in Python 3. The broad except
# swallows it into a generic "Validation failed". Range rules must only apply
# to NUMBER parameters.
# =============================================================================

def test_bug_validate_min_value_not_applied_to_string():
    """BUG: min_value/max_value rules must only apply to NUMBER parameters,
    not strings. Applying them to strings raises TypeError under the hood."""
    param = InputParameter(
        name="name",
        type=ParameterType.STRING,
        label="Name",
        description="d",
        required=True,
        validation_rules={"min_value": 5},  # nonsensical for strings
    )
    is_valid, error = ParameterValidator.validate_parameter(param, "hello")
    assert is_valid is True, (
        "min_value rule must not apply to STRING parameters"
    )


# =============================================================================
# BUG 3 (MEDIUM): ParameterValidator skips type-checking entirely when a
# required parameter has a default_value and the caller passes None. A
# NUMBER param with a STRING default passes validation. The default ought to
# be substituted and then type-validated.
# =============================================================================

def test_bug_validate_required_param_default_must_match_type():
    """BUG: a required NUMBER parameter with a STRING default value passes
    validation when no value is provided; the default is never type-checked."""
    param = InputParameter(
        name="count",
        type=ParameterType.NUMBER,
        label="Count",
        description="d",
        required=True,
        default_value="not-a-number",  # wrong type for a NUMBER param
    )
    is_valid, error = ParameterValidator.validate_parameter(param, None)
    assert is_valid is False, (
        "A NUMBER parameter whose default is a string must be invalid"
    )


# =============================================================================
# BUG 4 (MEDIUM): ExecutionEngine._create_execution_plan silently drops steps
# that participate in a cycle (or are unreachable) — it returns an empty plan
# with no error signal. When a cycle is detected at planning time the engine
# should surface it so callers don't silently get a no-op execution. We
# assert the plan at least flags the problem.
# =============================================================================

def test_bug_execution_plan_surfaces_cycle():
    """BUG: a workflow with a dependency cycle yields an EMPTY execution plan
    with no indication that steps were skipped."""
    engine = ExecutionEngine(StateManager())

    cyclic = AdvancedWorkflowDefinition(
        workflow_id="cyc",
        name="Cyclic",
        description="d",
        steps=[
            WorkflowStep(
                step_id="A", name="A", description="d",
                step_type="task", depends_on=["B"],
            ),
            WorkflowStep(
                step_id="B", name="B", description="d",
                step_type="task", depends_on=["A"],
            ),
        ],
    )
    plan = engine._create_execution_plan(cyclic)

    # Two real steps exist; an empty plan means they were silently dropped.
    # The engine must signal that steps could not be scheduled.
    total_steps = len(cyclic.steps)
    scheduled = len(plan.planned_steps)
    assert scheduled == total_steps or scheduled > 0 or plan.estimated_duration == -1, (
        "Cycle/unreachable steps must not be silently dropped without a signal"
    )


# =============================================================================
# Coverage: exercise the definition-level _should_show_parameter with a list
# condition and a scalar condition (engine version is tested elsewhere).
# =============================================================================

def test_coverage_should_show_parameter_list_condition():
    wf = AdvancedWorkflowDefinition(
        workflow_id="wf1",
        name="WF",
        description="d",
        input_schema=[
            InputParameter(
                name="mode", type=ParameterType.SELECT, label="Mode",
                description="d", options=["a", "b"],
            ),
            InputParameter(
                name="extra", type=ParameterType.STRING, label="Extra",
                description="d", required=True,
                show_when={"mode": ["a"]},
            ),
        ],
    )
    # 'extra' visible only when mode == 'a'
    assert wf._should_show_parameter(wf.input_schema[1], {"mode": "a"}) is True
    assert wf._should_show_parameter(wf.input_schema[1], {"mode": "b"}) is False
    assert wf._should_show_parameter(wf.input_schema[1], {}) is False


def test_coverage_should_show_parameter_scalar_condition():
    wf = AdvancedWorkflowDefinition(
        workflow_id="wf2", name="WF", description="d",
        input_schema=[
            InputParameter(
                name="x", type=ParameterType.STRING, label="X",
                description="d", required=True,
                show_when={"flag": "yes"},
            ),
        ],
    )
    assert wf._should_show_parameter(wf.input_schema[0], {"flag": "yes"}) is True
    assert wf._should_show_parameter(wf.input_schema[0], {"flag": "no"}) is False


# =============================================================================
# Coverage: ParameterValidator type-check branches (string/number/bool/array/
# select/multiselect) and validation rules (pattern, min/max for proper types).
# =============================================================================

class TestParameterValidatorCoverage:

    def test_string_type_mismatch(self):
        p = InputParameter(name="s", type=ParameterType.STRING, label="S", description="d")
        ok, _ = ParameterValidator.validate_parameter(p, 123)
        assert ok is False

    def test_number_rejects_bool(self):
        p = InputParameter(name="n", type=ParameterType.NUMBER, label="N", description="d")
        ok, _ = ParameterValidator.validate_parameter(p, True)
        assert ok is False

    def test_number_rejects_string(self):
        p = InputParameter(name="n", type=ParameterType.NUMBER, label="N", description="d")
        ok, _ = ParameterValidator.validate_parameter(p, "abc")
        assert ok is False

    def test_boolean_rejects_int(self):
        p = InputParameter(name="b", type=ParameterType.BOOLEAN, label="B", description="d")
        ok, _ = ParameterValidator.validate_parameter(p, 1)
        assert ok is False

    def test_array_rejects_non_list(self):
        p = InputParameter(name="a", type=ParameterType.ARRAY, label="A", description="d")
        ok, _ = ParameterValidator.validate_parameter(p, "not-a-list")
        assert ok is False

    def test_select_valid_and_invalid(self):
        p = InputParameter(
            name="sel", type=ParameterType.SELECT, label="Sel", description="d",
            options=["red", "green", "blue"],
        )
        ok, _ = ParameterValidator.validate_parameter(p, "red")
        assert ok is True
        ok2, _ = ParameterValidator.validate_parameter(p, "purple")
        assert ok2 is False

    def test_multiselect_valid_and_invalid(self):
        p = InputParameter(
            name="ms", type=ParameterType.MULTISELECT, label="MS", description="d",
            options=["a", "b", "c"],
        )
        ok, _ = ParameterValidator.validate_parameter(p, ["a", "c"])
        assert ok is True
        # not a list
        ok2, _ = ParameterValidator.validate_parameter(p, "a")
        assert ok2 is False
        # value not in options
        ok3, _ = ParameterValidator.validate_parameter(p, ["a", "z"])
        assert ok3 is False

    def test_min_max_length_on_string(self):
        p = InputParameter(
            name="s", type=ParameterType.STRING, label="S", description="d",
            validation_rules={"min_length": 3, "max_length": 5},
        )
        assert ParameterValidator.validate_parameter(p, "ab")[0] is False   # too short
        assert ParameterValidator.validate_parameter(p, "abc")[0] is True
        assert ParameterValidator.validate_parameter(p, "abcdef")[0] is False  # too long

    def test_min_max_value_on_number(self):
        p = InputParameter(
            name="n", type=ParameterType.NUMBER, label="N", description="d",
            validation_rules={"min_value": 10, "max_value": 100},
        )
        assert ParameterValidator.validate_parameter(p, 5)[0] is False
        assert ParameterValidator.validate_parameter(p, 50)[0] is True
        assert ParameterValidator.validate_parameter(p, 200)[0] is False

    def test_pattern_rule(self):
        p = InputParameter(
            name="s", type=ParameterType.STRING, label="S", description="d",
            validation_rules={"pattern": r"^\d+$"},
        )
        assert ParameterValidator.validate_parameter(p, "12345")[0] is True
        assert ParameterValidator.validate_parameter(p, "abc")[0] is False

    def test_pattern_too_complex(self):
        p = InputParameter(
            name="s", type=ParameterType.STRING, label="S", description="d",
            validation_rules={"pattern": "x" * 300},  # exceeds MAX_REGEX_LENGTH
        )
        ok, err = ParameterValidator.validate_parameter(p, "x")
        assert ok is False
        assert "too complex" in err

    def test_optional_none_valid(self):
        p = InputParameter(
            name="s", type=ParameterType.STRING, label="S", description="d",
            required=False,
        )
        assert ParameterValidator.validate_parameter(p, None)[0] is True

    def test_default_substituted_and_validated(self):
        # required, no value, default provided and matches type
        p = InputParameter(
            name="s", type=ParameterType.STRING, label="S", description="d",
            required=True, default_value="fallback",
        )
        ok, _ = ParameterValidator.validate_parameter(p, None)
        assert ok is True


# =============================================================================
# Coverage: StateManager persistence (file), list filtering, and
# AdvancedWorkflowSystem high-level builders (parallel/conditional/retry).
# =============================================================================

class TestStateManagerCoverage:

    def test_save_load_round_trip_to_file(self, tmp_path, monkeypatch):
        # Isolate file storage in a temp dir
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        state = {"name": "X", "steps": [{"id": 1}], "state": "draft"}
        assert sm.save_state("wf-file-1", state) is True

        # New manager (empty memory) loads from file
        sm2 = StateManager()
        loaded = sm2.load_state("wf-file-1")
        assert loaded is not None
        assert loaded["name"] == "X"
        assert "saved_at" in loaded

    def test_load_nonexistent_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        assert sm.load_state("does-not-exist") is None

    def test_delete_state_memory_and_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.save_state("wf-del", {"name": "X", "state": "draft"})
        assert sm.delete_state("wf-del") is True
        # deleting again -> file gone, memory gone -> False
        assert sm.delete_state("wf-del") is False

    def test_delete_invalid_id_returns_false(self):
        sm = StateManager()
        # workflow_id with only invalid chars sanitizes to empty -> False
        assert sm.delete_state("../../../etc/passwd") is False

    def test_list_workflows_filters_and_tags(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.save_state("wf-a", {
            "name": "Alpha", "state": "draft", "category": "marketing",
            "tags": ["email", "automation"],
            "updated_at": "2026-01-01T00:00:00",
            "created_at": "2026-01-01T00:00:00",
            "steps": [{"id": 1}],
        })
        sm.save_state("wf-b", {
            "name": "Beta", "state": "running", "category": "ops",
            "tags": ["automation"],
            "updated_at": "2026-02-01T00:00:00",
            "created_at": "2026-02-01T00:00:00",
            "steps": [{"id": 1}, {"id": 2}],
        })

        # filter by status
        running = sm.list_workflows(status="running")
        assert len(running) == 1
        assert running[0]["name"] == "Beta"

        # filter by category
        mkt = sm.list_workflows(category="marketing")
        assert len(mkt) == 1
        assert mkt[0]["name"] == "Alpha"

        # filter by tags (must have ALL)
        both_tags = sm.list_workflows(tags=["email", "automation"])
        assert len(both_tags) == 1
        assert both_tags[0]["name"] == "Alpha"

        # tags subset that matches both
        auto = sm.list_workflows(tags=["automation"])
        assert len(auto) == 2

    def test_list_workflows_sort_and_pagination(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        for i, name in enumerate(["Charlie", "Alpha", "Bravo"]):
            sm.save_state(f"wf-{i}", {
                "name": name, "state": "draft",
                "updated_at": f"2026-01-0{i+1}T00:00:00",
                "created_at": f"2026-01-0{i+1}T00:00:00",
                "steps": [],
            })

        asc = sm.list_workflows(sort_by="name", sort_order="asc")
        assert [w["name"] for w in asc] == ["Alpha", "Bravo", "Charlie"]

        desc = sm.list_workflows(sort_by="name", sort_order="desc")
        assert desc[0]["name"] == "Charlie"

        # invalid sort_by -> default sort by updated_at desc
        defaulted = sm.list_workflows(sort_by="bogus")
        assert len(defaulted) == 3

        # pagination
        page = sm.list_workflows(sort_by="name", sort_order="asc", offset=1, limit=1)
        assert len(page) == 1
        assert page[0]["name"] == "Bravo"


class TestAdvancedWorkflowSystemBuilders:

    def test_create_parallel(self):
        system = AdvancedWorkflowSystem()
        result = system.create_parallel({
            "name": "My Parallel",
            "parallel_branches": [
                {"steps": ["fetch", "transform"]},
                {"steps": ["notify"]},
            ],
        })
        assert result.workflow_id is not None
        assert result.execution_mode == "parallel"
        assert result.branches == 2

    def test_create_conditional(self):
        system = AdvancedWorkflowSystem()
        result = system.create_conditional({
            "name": "My Conditional",
            "conditions": [
                {"if": "x > 5", "then": "do_a"},
                {"if": "x <= 5", "then": "do_b"},
            ],
        })
        assert result.execution_mode == "conditional"
        assert result.conditions == 2

    def test_execute_with_retry(self):
        system = AdvancedWorkflowSystem()
        result = system.execute_with_retry("wf-1", {"max_retries": 3})
        assert result.workflow_id == "wf-1"
        assert result.retry_policy == {"max_retries": 3}
        assert result.status == "pending"


class TestExecutionEngineCoverage:

    def test_get_workflow_status_and_progress(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = AdvancedWorkflowDefinition(
            workflow_id="wf-status", name="S", description="d",
            steps=[
                WorkflowStep(step_id="a", name="a", description="d", step_type="task"),
                WorkflowStep(step_id="b", name="b", description="d", step_type="task"),
            ],
        )
        wf.step_results = {"a": {"output": 1}}
        sm.save_state("wf-status", wf.dict())

        status = engine.get_workflow_status("wf-status")
        assert status is not None
        assert status["state"] == "draft"
        # 1 of 2 steps -> 50%
        assert status["progress"] == 50.0

    def test_get_workflow_status_missing(self):
        engine = ExecutionEngine(StateManager())
        assert engine.get_workflow_status("nope") is None

    def test_cancel_workflow(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        engine = ExecutionEngine(sm)
        sm.save_state("wf-c", {"name": "X", "state": "running", "user_inputs": {}})
        assert engine.cancel_workflow("wf-c") is True
        assert sm.load_state("wf-c")["state"] == WorkflowState.CANCELLED

    def test_cancel_workflow_missing(self):
        engine = ExecutionEngine(StateManager())
        assert engine.cancel_workflow("nope") is False

    def test_validate_workflow_circular(self):
        engine = ExecutionEngine(StateManager())
        wf = AdvancedWorkflowDefinition(
            workflow_id="wf-v", name="V", description="d",
            steps=[
                WorkflowStep(step_id="a", name="a", description="d",
                             step_type="task", depends_on=["b"]),
                WorkflowStep(step_id="b", name="b", description="d",
                             step_type="task", depends_on=["a"]),
            ],
        )
        ok, msg = engine._validate_workflow(wf)
        assert ok is False
        assert "circular" in msg.lower()
