
"""
ReAct-loop tests for AtomMetaAgent (current architecture).

The loop now uses instructor-structured ReActStep outputs via
``ServiceFactory.get_llm_service`` (the module-level LLMService patch is
obsolete), and dispatches tool calls through ``_execute_tool_with_governance``
(governance + sandbox-gated MCP path). These tests pin the loop contract:
tool calls from a step are dispatched with their params, the run persists
reasoning steps, and a final-answer step terminates the loop.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.atom_meta_agent import AgentTriggerMode, AtomMetaAgent, ReActStep, ToolCall
from core.models import User


class _FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model

    def filter(self, *a, **k):
        return self

    def with_for_update(self):
        return self

    def first(self):
        from core.models import AgentExecution, AgentRegistry, Workspace
        if self._model is Workspace:
            return self._session._workspace
        if self._model is AgentRegistry:
            return self._session._agent
        if self._model is AgentExecution:
            return self._session._execution
        return None


class _FakeSession:
    """Minimal SessionLocal stand-in (workspace/agent/execution lookups)."""

    def __init__(self, workspace=None, agent=None, execution=None):
        self._workspace = workspace or SimpleNamespace(tenant_id="default")
        self._agent = agent or SimpleNamespace(
            id="atom_main", name="Atom", category="Meta",
            status="AUTONOMOUS", confidence_score=1.0,
        )
        self._execution = execution or SimpleNamespace(
            id="exec-1", status="running", result_summary="",
            error_message=None, duration_seconds=None, completed_at=None,
        )
        self.added = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def query(self, model):
        return _FakeQuery(self, model)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        pass

    def refresh(self, row):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def atom(monkeypatch):
    """Hermetic AtomMetaAgent wired for a full execute() run."""
    from core import atom_meta_agent as am

    monkeypatch.setattr(am, "SessionLocal", lambda: _FakeSession())

    agent = am.AtomMetaAgent.__new__(am.AtomMetaAgent)
    agent.workspace_id = "default"
    agent.tenant_id = "default"
    agent.user = None
    agent.world_model = SimpleNamespace(
        recall_experiences=AsyncMock(return_value={"experiences": []}),
        recall_episodes=AsyncMock(return_value=[]),
        record_experience=AsyncMock(),
    )
    agent.mcp = SimpleNamespace(
        get_all_tools=AsyncMock(return_value=[]),
        search_tools=AsyncMock(return_value=[]),
        call_tool=AsyncMock(return_value={"ok": True}),
    )
    agent.llm = MagicMock()
    agent.canvas_provider = SimpleNamespace()
    agent.session_tools = []
    agent.spawned_agents = {}
    agent.queen = SimpleNamespace(
        generate_blueprint=AsyncMock(return_value=None)
    )
    agent.orchestrator = SimpleNamespace(
        generate_dynamic_workflow=AsyncMock(return_value=None)
    )
    agent.graduation_service = SimpleNamespace(
        get_maturity=MagicMock(return_value="autonomous"),
        record_usage=MagicMock(),
    )
    agent._stage_group = None

    def _get_atom_registry():
        return SimpleNamespace(
            id="atom_main", name="Atom", category="Meta",
            status="AUTONOMOUS", confidence_score=1.0,
        )

    agent._get_atom_registry = _get_atom_registry
    agent._check_budget_before_react = AsyncMock(
        return_value={"allowed": True, "reason": None}
    )
    agent._record_execution = AsyncMock()
    agent._persist_reasoning_step = MagicMock(return_value="rs-1")
    agent._execute_tool_with_governance = AsyncMock(
        return_value='{"ok": true}'
    )

    async def _classify_route(self, request, tenant_id=None):
        from ai.nlp_engine import RouteCategory
        return SimpleNamespace(category=RouteCategory.ONE_OFF, reasoning="test")

    monkeypatch.setattr(am.NaturalLanguageEngine, "classify_route", _classify_route)
    monkeypatch.setattr(
        "core.field_guide_service.get_field_guide_service",
        lambda: SimpleNamespace(get_field_guide_context=lambda ws: ""),
    )
    return agent


def _tool_step(tool, params):
    return ReActStep(
        thought=f"Need to call {tool}",
        action=ToolCall(tool=tool, params=params),
        final_answer=None,
    )


def _final_step(answer):
    return ReActStep(thought="done", action=None, final_answer=answer)


@pytest.mark.asyncio
async def test_atom_react_spawn_flow(atom):
    """The loop dispatches a spawn_agent tool call, then terminates on the
    final-answer step, persisting both reasoning steps."""
    atom._react_step = AsyncMock(side_effect=[
        _tool_step("spawn_agent", {
            "template": "finance_analyst", "task": "Analyze Q3 expenses",
        }),
        _final_step("The Q3 expenses execution is complete. See report."),
    ])

    result = await atom.execute("Analyze my Q3 expenses")

    assert result["final_output"] == "The Q3 expenses execution is complete. See report."
    assert len(result["actions_executed"]) == 2
    assert result["status"] == "success"

    # The tool call reached the governed dispatch with its params.
    atom._execute_tool_with_governance.assert_awaited()
    call = atom._execute_tool_with_governance.await_args
    assert call.args[0] == "spawn_agent"
    assert call.args[1] == {
        "template": "finance_analyst", "task": "Analyze Q3 expenses",
    }

    # Action steps are persisted (learning loop); the final-answer step
    # breaks the loop before persistence.
    assert atom._persist_reasoning_step.call_count == 1


@pytest.mark.asyncio
async def test_atom_react_integration_flow(atom):
    """The loop dispatches a call_integration tool call with its params and
    terminates on the final answer."""
    atom._react_step = AsyncMock(side_effect=[
        _tool_step("call_integration", {
            "service": "web_search", "action": "search", "params": {"q": "Atom"},
        }),
        _final_step("Search complete."),
    ])

    result = await atom.execute("Search for Atom")

    assert result["final_output"] == "Search complete."
    assert len(result["actions_executed"]) == 2

    call = atom._execute_tool_with_governance.await_args
    assert call.args[0] == "call_integration"
    assert call.args[1] == {
        "service": "web_search", "action": "search", "params": {"q": "Atom"},
    }
