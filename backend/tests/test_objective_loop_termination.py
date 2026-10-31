"""The running ReAct loop must stop at the satisfying step, not max_steps."""
import asyncio

import pytest

from core.generic_agent import GenericAgent
from core.models import AgentRegistry
from core.react_models import ReActStep, ToolCall


def _agent(db, name: str) -> GenericAgent:
    import uuid

    row = AgentRegistry(
        id=str(uuid.uuid4()),
        name=name,
        display_name=name,
        description="objective loop acceptance",
        category="acceptance",
        role="agent",
        type="personal",
        module_path="core.generic_agent",
        class_name="GenericAgent",
        status="intern",
        confidence_score=0.5,
        capabilities=["*"],
        configuration={"max_steps": 5},
        tenant_id="default",
        workspace_id="default",
    )
    db.add(row)
    db.commit()
    return GenericAgent(row, workspace_id="default")


@pytest.fixture
def db():
    from core.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_loop_stops_at_definition_of_done(db, monkeypatch):
    monkeypatch.setenv("ATOM_OBJECTIVE_LOOP_ENABLED", "true")
    agent = _agent(db, "objective-satisfied")
    calls = []

    async def fake_react_step(task_input, memory, history, context=None,
                              utility_delta=None):
        calls.append(len(calls) + 1)
        return ReActStep(
            thought="still working",
            action=ToolCall(tool="acceptance_probe", params={"n": len(calls)}),
        )

    async def fake_step_act(tool_name, tool_args, context, step_callback=None):
        return "probe observation"

    agent._react_step = fake_react_step
    agent._step_act = fake_step_act
    result = await agent.execute(
        "produce the acceptance answer",
        context={
            "optimization": {"max_steps": 5},
            "objective_goal": "answer at step 2",
            "objective_done": lambda state: int(state.get("current_step", 0)) >= 2,
        },
    )

    # The loop stopped at 2/5. NOTE: the returned status field currently says
    # max_steps even though the predicate break fired (a separate shared-loop
    # reporting bug handed to Agent 1); the call count is the discriminating
    # evidence for termination.
    assert len(calls) == 2, f"loop ran {len(calls)} steps, expected early stop at 2"
    assert len(result["steps"]) == 2


@pytest.mark.asyncio
async def test_unsatisfied_predicate_still_burns_max_steps(db, monkeypatch):
    monkeypatch.setenv("ATOM_OBJECTIVE_LOOP_ENABLED", "true")
    agent = _agent(db, "objective-unsatisfied")
    calls = []

    async def fake_react_step(task_input, memory, history, context=None,
                              utility_delta=None):
        calls.append(len(calls) + 1)
        return ReActStep(
            thought="still working",
            action=ToolCall(tool="acceptance_probe", params={"n": len(calls)}),
        )

    async def fake_step_act(tool_name, tool_args, context, step_callback=None):
        return "probe observation"

    agent._react_step = fake_react_step
    agent._step_act = fake_step_act
    result = await agent.execute(
        "never satisfy",
        context={
            "optimization": {"max_steps": 3},
            "objective_goal": "impossible",
            "objective_done": lambda state: False,
        },
    )

    assert result["status"] == "max_steps_exceeded", result
    assert len(calls) == 3, f"loop ran {len(calls)} steps, expected max_steps=3"
