"""
TDD bug-hunt tests for core/advanced_workflow_system.py + core/workflow_security.py.

Bugs covered:
- BUG W-1: ParameterValidator.validate_parameter rejects optional params whose
  value is None (should be valid when not required and no default).
- BUG W-2: NUMBER parameters accept booleans (True/False validate as numbers).
- BUG W-3: MULTISELECT parameters accept non-list values (a string is iterated
  char-by-char against the options) and leak exception detail
  ("Validation failed: 'NoneType' object is not iterable").
- BUG W-4: ExecutionEngine.start_workflow never type-validates provided inputs;
  a NUMBER param given "abc" starts execution anyway.
- BUG W-5: ExecutionEngine._should_show_parameter diverges from
  AdvancedWorkflowDefinition._should_show_parameter: a required param whose
  show_when trigger field is missing is reported missing instead of hidden.
- BUG W-6: a failed step (status == "error") does not fail the workflow — the
  workflow is marked COMPLETED despite a step error.
- BUG W-7: resume_workflow re-executes already-completed steps (double side
  effects: e.g. api_call steps fire twice).
- BUG W-8: AdvancedWorkflowSystem.create_parallel / create_conditional never
  persist the definition — the returned workflow cannot be started.
- BUG W-9: start_workflow allows concurrent duplicate execution of the same
  workflow (double side effects); the second start returns "started".
- BUG W-10: workflow_security gates are case/whitespace-sensitive — mixed-case
  or trailing-space critical tool names ("Terminal_Command", "terminal_command ")
  bypass _has_critical_mcp_tool / require_critical_tool / has_critical_automation_nodes.
"""

import asyncio
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from core.advanced_workflow_system import (
    AdvancedWorkflowDefinition,
    AdvancedWorkflowSystem,
    ExecutionEngine,
    InputParameter,
    ParameterType,
    ParameterValidator,
    StateManager,
    WorkflowState,
)
from core.workflow_security import (
    _has_critical_mcp_tool,
    has_critical_automation_nodes,
    require_critical_tool,
)


class _User:
    def __init__(self, role="member"):
        self.id = "u-1"
        self.role = role


@pytest.fixture
def temp_state_dir():
    """Isolate StateManager file persistence in a temp cwd."""
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        yield tmpdir
        os.chdir(original_cwd)


def _number_param(name="count", required=True):
    return InputParameter(
        name=name,
        type=ParameterType.NUMBER,
        label="Count",
        description="A count",
        required=required,
    )


def _wait_for_idle(engine: ExecutionEngine, workflow_id: str, timeout: float = 3.0) -> None:
    async def _wait() -> None:
        elapsed = 0.0
        while engine.running_workflows.get(workflow_id) is not None and elapsed < timeout:
            await asyncio.sleep(0.02)
            elapsed += 0.02

    asyncio.run(_wait())


# ---------------------------------------------------------------------------
# BUG W-1: optional parameter with None value must be valid
# ---------------------------------------------------------------------------


def test_optional_parameter_none_value_is_valid():
    param = _number_param(required=False)
    is_valid, error = ParameterValidator.validate_parameter(param, None)
    assert is_valid is True
    assert error is None


def test_optional_boolean_none_value_is_valid():
    param = InputParameter(
        name="flag", type=ParameterType.BOOLEAN, label="Flag",
        description="d", required=False,
    )
    is_valid, error = ParameterValidator.validate_parameter(param, None)
    assert is_valid is True
    assert error is None


# ---------------------------------------------------------------------------
# BUG W-2: NUMBER must reject booleans
# ---------------------------------------------------------------------------


def test_number_rejects_boolean():
    is_valid, _ = ParameterValidator.validate_parameter(_number_param(), True)
    assert is_valid is False


# ---------------------------------------------------------------------------
# BUG W-3: MULTISELECT must reject non-list values without leaking str(e)
# ---------------------------------------------------------------------------


def test_multiselect_rejects_non_list_value():
    param = InputParameter(
        name="ms", type=ParameterType.MULTISELECT, label="MS",
        description="d", required=True, options=["a", "b"],
    )
    is_valid, error = ParameterValidator.validate_parameter(param, "a")
    assert is_valid is False
    assert "array" in error


def test_multiselect_optional_none_does_not_leak_exception():
    param = InputParameter(
        name="ms", type=ParameterType.MULTISELECT, label="MS",
        description="d", required=False, options=["a", "b"],
    )
    is_valid, error = ParameterValidator.validate_parameter(param, None)
    assert is_valid is True
    assert error is None


def test_multiselect_valid_list():
    param = InputParameter(
        name="ms", type=ParameterType.MULTISELECT, label="MS",
        description="d", required=True, options=["a", "b"],
    )
    is_valid, error = ParameterValidator.validate_parameter(param, ["a", "b"])
    assert is_valid is True
    assert error is None


# ---------------------------------------------------------------------------
# BUG W-4: start_workflow must type-validate provided inputs
# ---------------------------------------------------------------------------


def test_start_workflow_rejects_invalid_input_type(temp_state_dir):
    state_manager = StateManager()
    engine = ExecutionEngine(state_manager)

    asyncio.run(engine.create_workflow({
        "workflow_id": "wf_types",
        "name": "Types",
        "description": "d",
        "input_schema": [{
            "name": "count", "type": "number", "label": "Count",
            "description": "d", "required": True,
        }],
        "steps": [{
            "step_id": "s1", "name": "S1", "description": "D",
            "step_type": "task", "depends_on": [],
        }],
    }))

    result = asyncio.run(engine.start_workflow("wf_types", {"count": "not-a-number"}))
    assert result["status"] == "waiting_for_input"
    assert "count" in result["validation_errors"]
    loaded = state_manager.load_state("wf_types")
    assert loaded["state"] == WorkflowState.WAITING_FOR_INPUT


# ---------------------------------------------------------------------------
# BUG W-5: show_when trigger field missing hides the parameter
# ---------------------------------------------------------------------------


def test_engine_missing_inputs_respects_show_when(temp_state_dir):
    state_manager = StateManager()
    engine = ExecutionEngine(state_manager)

    asyncio.run(engine.create_workflow({
        "workflow_id": "wf_show",
        "name": "Show",
        "description": "d",
        "input_schema": [
            {
                "name": "kind", "type": "string", "label": "Kind",
                "description": "d", "required": True,
            },
            {
                "name": "secret", "type": "string", "label": "Secret",
                "description": "d", "required": True,
                "show_when": {"kind": "api"},
            },
        ],
        "steps": [],
    }))

    result = asyncio.run(engine.start_workflow("wf_show", {}))
    missing = [m.name for m in result["missing_parameters"]]
    assert "kind" in missing
    assert "secret" not in missing


def test_engine_show_when_list_condition(temp_state_dir):
    """Engine condition evaluation must support list conditions like the
    definition-level implementation: when the trigger is 'file', the list-gated
    required param must not be demanded."""
    state_manager = StateManager()
    engine = ExecutionEngine(state_manager)

    async def main() -> None:
        await engine.create_workflow({
            "workflow_id": "wf_show_list",
            "name": "Show List",
            "description": "d",
            "input_schema": [
                {
                    "name": "kind", "type": "string", "label": "Kind",
                    "description": "d", "required": True,
                },
                {
                    "name": "token", "type": "string", "label": "Token",
                    "description": "d", "required": True,
                    "show_when": {"kind": ["api", "webhook"]},
                },
            ],
            "steps": [],
        })
        result = await engine.start_workflow("wf_show_list", {"kind": "file"})
        assert result["status"] == "started"

    asyncio.run(main())


# ---------------------------------------------------------------------------
# BUG W-6: step failure must fail the workflow, not complete it
# ---------------------------------------------------------------------------


def test_step_failure_marks_workflow_failed(temp_state_dir):
    state_manager = StateManager()
    engine = ExecutionEngine(state_manager)

    asyncio.run(engine.create_workflow({
        "workflow_id": "wf_fail",
        "name": "Fail",
        "description": "d",
        "steps": [{
            "step_id": "s1", "name": "S1", "description": "D",
            "step_type": "api_call", "depends_on": [],
        }],
    }))

    async def failing_execute(step, inputs):
        raise ValueError("boom")

    engine._execute_api_call = failing_execute
    asyncio.run(engine.start_workflow("wf_fail", {}))
    _wait_for_idle(engine, "wf_fail")

    loaded = state_manager.load_state("wf_fail")
    assert loaded["state"] == WorkflowState.FAILED


# ---------------------------------------------------------------------------
# BUG W-7: resume must not re-execute completed steps
# ---------------------------------------------------------------------------


def test_resume_does_not_reexecute_completed_steps(temp_state_dir):
    state_manager = StateManager()
    engine = ExecutionEngine(state_manager)
    calls = []

    async def main() -> None:
        async def step_call(step, inputs):
            calls.append(step.step_id)
            await asyncio.sleep(0.15)
            return {"ok": True}

        engine._execute_api_call = step_call
        await engine.create_workflow({
            "workflow_id": "wf_resume",
            "name": "Resume",
            "description": "d",
            "steps": [
                {
                    "step_id": "a", "name": "A", "description": "D",
                    "step_type": "api_call", "depends_on": [],
                },
                {
                    "step_id": "b", "name": "B", "description": "D",
                    "step_type": "api_call", "depends_on": ["a"],
                },
            ],
        })
        await engine.start_workflow("wf_resume", {})
        await asyncio.sleep(0.2)
        assert engine.pause_workflow("wf_resume") is True
        await asyncio.sleep(0.05)
        engine.resume_workflow("wf_resume")
        await asyncio.sleep(0.6)

    asyncio.run(main())

    # 'a' completed before the pause and must NOT re-execute on resume; the
    # interrupted step 'b' runs once more (it never completed), so the total is
    # a single execution of every step plus the in-flight re-run.
    assert calls.count("a") == 1
    assert calls[0:2] == ["a", "b"]
    assert calls[-1] == "b"
    loaded = state_manager.load_state("wf_resume")
    assert loaded["state"] == WorkflowState.COMPLETED


# ---------------------------------------------------------------------------
# BUG W-8: create_parallel / create_conditional must persist the workflow
# ---------------------------------------------------------------------------


def test_create_parallel_workflow_can_be_started(temp_state_dir):
    aws = AdvancedWorkflowSystem()

    async def main() -> None:
        result = aws.create_parallel({
            "name": "p",
            "parallel_branches": [{"steps": ["x", "y"]}],
        })
        started = await aws.execution_engine.start_workflow(result.workflow_id, {})
        assert started["status"] == "started"
        for _ in range(100):
            if result.workflow_id not in aws.execution_engine.running_workflows:
                break
            await asyncio.sleep(0.02)

    asyncio.run(main())


def test_create_conditional_workflow_can_be_started(temp_state_dir):
    aws = AdvancedWorkflowSystem()

    async def main() -> None:
        result = aws.create_conditional({
            "name": "c",
            "conditions": [{"if": "a > b"}],
        })
        started = await aws.execution_engine.start_workflow(result.workflow_id, {})
        assert started["status"] == "started"
        for _ in range(100):
            if result.workflow_id not in aws.execution_engine.running_workflows:
                break
            await asyncio.sleep(0.02)

    asyncio.run(main())


# ---------------------------------------------------------------------------
# BUG W-9: duplicate concurrent start must be refused
# ---------------------------------------------------------------------------


def test_duplicate_start_workflow_refused(temp_state_dir):
    state_manager = StateManager()
    engine = ExecutionEngine(state_manager)

    async def main() -> None:
        async def slow_call(step, inputs):
            await asyncio.sleep(0.3)
            return {"ok": True}

        engine._execute_api_call = slow_call
        await engine.create_workflow({
            "workflow_id": "wf_dup",
            "name": "Dup",
            "description": "d",
            "steps": [{
                "step_id": "s1", "name": "S1", "description": "D",
                "step_type": "api_call", "depends_on": [],
            }],
        })
        first = await engine.start_workflow("wf_dup", {})
        assert first["status"] == "started"
        with pytest.raises(ValueError, match="already running"):
            await engine.start_workflow("wf_dup", {})
        await asyncio.sleep(0.4)

    asyncio.run(main())


# ---------------------------------------------------------------------------
# BUG W-10: workflow_security tool-name normalization
# ---------------------------------------------------------------------------


def test_mcp_tool_name_mixed_case_is_critical():
    step = {"service": "mcp", "action": "Terminal_Command", "parameters": {}}
    assert _has_critical_mcp_tool(step) is True


def test_mcp_tool_name_trailing_whitespace_is_critical():
    step = {"service": "mcp", "action": "terminal_command ", "parameters": {}}
    assert _has_critical_mcp_tool(step) is True


def test_mcp_tool_name_in_parameters_mixed_case_is_critical():
    step = {"step_type": "mcp", "parameters": {"tool_name": "Browser_Navigate"}}
    assert _has_critical_mcp_tool(step) is True


def test_require_critical_tool_mixed_case_blocked():
    with patch("core.workflow_security.RBACService.check_permission", return_value=False):
        with pytest.raises(HTTPException):
            asyncio.run(require_critical_tool(_User(), "Browser_Navigate"))


def test_require_critical_tool_trailing_whitespace_blocked():
    with patch("core.workflow_security.RBACService.check_permission", return_value=False):
        with pytest.raises(HTTPException):
            asyncio.run(require_critical_tool(_User(), "terminal_command "))


def test_require_critical_tool_benign_still_allowed():
    with patch("core.workflow_security.RBACService.check_permission", return_value=False):
        asyncio.run(require_critical_tool(_User(), "present_markdown"))


def test_automation_action_type_case_insensitive():
    assert has_critical_automation_nodes(
        {"nodes": [{"config": {"actionType": "Send_Email"}}]}
    ) is True


def test_automation_action_type_trailing_whitespace():
    assert has_critical_automation_nodes(
        {"nodes": [{"config": {"actionType": "send_email "}}]}
    ) is True


def test_automation_benign_action_type_still_benign():
    assert has_critical_automation_nodes(
        {"nodes": [{"config": {"actionType": "read_file"}}]}
    ) is False
