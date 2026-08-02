"""
Round 72 — Hermes gap closure (Workstream A): in-loop verification + self-correction.

Covers:
  - atom_meta_agent: [CRITIQUE] appended to execution_history when a tool's
    verification hook rejects the result (failed_verification) or the
    observation is an error string; NOT appended on verified outcomes.
  - generic_agent: same critique hook on error observations.
  - ActionJudge consulted in _execute_tool_with_governance ONLY when
    ATOM_SANDBOX_JUDGE_ENABLED=true.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.atom_meta_agent import AtomMetaAgent
from core.generic_agent import GenericAgent
from core.react_models import ReActStep, ToolCall


@pytest.fixture(autouse=True)
def _disable_turn_fact(monkeypatch):
    import core.atom_meta_agent as ama
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)


def _patch_meta_agent(agent, steps, observation=None):
    """Wire _react_step to return steps in sequence, capturing history."""
    calls = []

    async def fake_react_step(**kwargs):
        calls.append(kwargs.get("execution_history", ""))
        return steps[min(len(calls) - 1, len(steps) - 1)]

    agent._react_step = fake_react_step
    if observation is not None:
        agent._execute_tool_with_governance = AsyncMock(return_value=observation)
    return calls


def _meta_db(mock_session):
    db = MagicMock()
    ws = MagicMock()
    ws.tenant_id = "tenant"
    db.query.return_value.filter.return_value.first.return_value = ws
    mock_session.return_value.__enter__.return_value = db
    mock_session.return_value.__exit__.return_value = None


class _FakeRoute:
    category = MagicMock(value="onetime")
    reasoning = "test routing"


@pytest.fixture(autouse=True)
def _mock_nlu(monkeypatch):
    import core.atom_meta_agent as ama
    fake_engine = MagicMock()
    fake_engine.classify_route = AsyncMock(return_value=_FakeRoute())
    monkeypatch.setattr(ama, "NaturalLanguageEngine", lambda: fake_engine)


@patch("core.atom_meta_agent.SessionLocal")
@pytest.mark.asyncio
async def test_meta_agent_critique_on_failed_verification(mock_session):
    """failed_verification observation → [CRITIQUE] fed into next ReAct step."""
    _meta_db(mock_session)
    agent = AtomMetaAgent()
    agent._record_execution = AsyncMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])

    histories = _patch_meta_agent(agent, [
        ReActStep(thought="first", action=ToolCall(tool="read_codebase", params={})),
        ReActStep(thought="re-plan", final_answer="done"),
    ])
    result = await agent.execute("test")
    assert result["status"] == "success"
    assert "[CRITIQUE]" in histories[-1]


@patch("core.atom_meta_agent.SessionLocal")
@pytest.mark.asyncio
async def test_meta_agent_no_critique_on_verified(mock_session):
    """verified outcome → no [CRITIQUE] directive."""
    _meta_db(mock_session)
    agent = AtomMetaAgent()
    agent._record_execution = AsyncMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent._execute_tool_with_governance = AsyncMock(
        return_value='{"success": true, "verified": true, "evidence": "stat confirmed"}'
    )

    histories = _patch_meta_agent(agent, [
        ReActStep(thought="first", action=ToolCall(tool="read_codebase", params={})),
        ReActStep(thought="done", final_answer="ok"),
    ])
    result = await agent.execute("test")
    assert result["status"] == "success"
    assert "[CRITIQUE]" not in histories[-1]


@patch("core.atom_meta_agent.SessionLocal")
@pytest.mark.asyncio
async def test_meta_agent_critique_on_error_observation(mock_session):
    """plain error string observation → [CRITIQUE] directive."""
    _meta_db(mock_session)
    agent = AtomMetaAgent()
    agent._record_execution = AsyncMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent._execute_tool_with_governance = AsyncMock(
        return_value="Tool error. Please try again."
    )

    histories = _patch_meta_agent(agent, [
        ReActStep(thought="first", action=ToolCall(tool="read_codebase", params={})),
        ReActStep(thought="done", final_answer="ok"),
    ])
    result = await agent.execute("test")
    assert result["status"] == "success"
    assert "[CRITIQUE]" in histories[-1]


@pytest.mark.asyncio
async def test_generic_agent_critique_on_error_observation():
    """generic_agent appends [CRITIQUE] when the observation is an error string."""
    agent_model = MagicMock()
    agent_model.id = "agent-1"
    agent_model.name = "Test"
    agent_model.configuration = {"max_steps": 3}
    agent_model.vision_enabled = False

    agent = GenericAgent(agent_model, workspace_id="ws")
    agent._step_act = AsyncMock(return_value="Tool Execution Failed: boom. You can try to correct parameters.")
    agent.world_model = MagicMock()
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.world_model.record_experience = AsyncMock()
    agent._record_execution = AsyncMock()
    agent.llm = MagicMock()
    agent.llm._get_handler.return_value.analyze_query_complexity = MagicMock(
        return_value=MagicMock(value="simple")
    )

    histories = []

    async def fake_react_step(task_input, memory_context, execution_history, context):
        histories.append(execution_history)
        if "Tool Execution Failed" in execution_history:
            return ReActStep(thought="done", final_answer="ok")
        return ReActStep(
            thought="act",
            action=ToolCall(tool="read_codebase", params={}),
        )

    agent._react_step = fake_react_step
    result = await agent.execute("task")
    assert result["status"] == "success"
    assert "[CRITIQUE]" in histories[-1]


@patch("core.atom_meta_agent.SessionLocal")
@pytest.mark.asyncio
async def test_action_judge_consulted_when_enabled(mock_session):
    """ATOM_SANDBOX_JUDGE_ENABLED=true → ActionJudge.evaluate is called."""
    _meta_db(mock_session)
    agent = AtomMetaAgent()
    agent.mcp.call_tool = AsyncMock(return_value={"success": True})
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent._record_execution = AsyncMock()

    class FakeVerdict:
        verdict = "block"
        rationale = "unsafe"

    fake_judge = MagicMock()
    fake_judge.evaluate = AsyncMock(return_value=FakeVerdict())
    from core import sandbox_config
    with patch.object(
        sandbox_config, "is_sandbox_judge_enabled", return_value=True
    ), patch("core.llm.action_judge.ActionJudge", return_value=fake_judge):
        out = await agent._execute_tool_with_governance(
            "read_codebase", {"file_path": "/tmp/x"}, {}, None
        )
        fake_judge.evaluate.assert_awaited()
        assert "blocked by the safety judge" in out


@patch("core.atom_meta_agent.SessionLocal")
@pytest.mark.asyncio
async def test_action_judge_not_consulted_when_disabled(mock_session):
    """default (judge off) → ActionJudge.evaluate is NOT called."""
    _meta_db(mock_session)
    agent = AtomMetaAgent()
    agent.mcp.call_tool = AsyncMock(return_value={"success": True})
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent._record_execution = AsyncMock()

    fake_judge = MagicMock()
    fake_judge.evaluate = AsyncMock(return_value=MagicMock(verdict="proceed"))
    from core import sandbox_config
    with patch.object(
        sandbox_config, "is_sandbox_judge_enabled", return_value=False
    ), patch("core.llm.action_judge.ActionJudge", return_value=fake_judge):
        out = await agent._execute_tool_with_governance(
            "read_codebase", {"file_path": "/tmp/x"}, {}, None
        )
        fake_judge.evaluate.assert_not_awaited()
        assert "blocked by the safety judge" not in out
