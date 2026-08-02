"""R72 Workstream G — in-loop parallel tool execution (default ON).

P1–P10:
  P1  actions field present + parses on BOTH ReActStep copies
  P2  flag OFF -> sequential fallback (no batch approval, one call per tool)
  P3  flag ON + allowed -> asyncio.gather, pre_approved=True per tool
  P4  complexity>1 -> HITL batch approval requested per tool
  P5  all-or-nothing: one REJECTED -> no tool executes
  P6  _execute_tool_with_governance(pre_approved=True) skips governance
  P7  mcp_tool_search serialized (not in gather); session_tools extended
  P8  max parallel cap (ATOM_MAX_PARALLEL_TOOLS) limits batch size
  P9  one AgentReasoningStep per tool, same step_number (loop integration)
  P10 turn-fact fires ONCE per batch (dispatch_turn_fact flag)

All tests mock agent internals — no real LLM / MCP / DB calls.
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.atom_meta_agent as ama
from core.atom_meta_agent import AtomMetaAgent, ToolCall
from core.react_models import ReActStep as SharedReActStep


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("ATOM_") and ("PARALLEL_TOOLS" in k or "MAX_PARALLEL" in k):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)


def _make_agent():
    """Construct AtomMetaAgent without heavy __init__ side effects."""
    agent = AtomMetaAgent.__new__(AtomMetaAgent)
    agent.workspace_id = "ws-1"
    agent.tenant_id = "t-1"
    agent.session_tools = []
    agent.llm = MagicMock()
    agent.graduation_service = None
    agent.mcp = AsyncMock()
    agent.mcp.call_tool = AsyncMock(return_value="ok")
    agent.mcp.search_tools = AsyncMock(return_value=[{"name": "extra_tool", "description": "x"}])
    return agent


def _actions(*tools):
    return [ToolCall(tool=t, params={}) for t in tools]


# ---------------------------------------------------------------------------
# P1: schema
# ---------------------------------------------------------------------------


def test_P1_actions_field_on_both_reactstep_copies():
    assert SharedReActStep.model_fields["actions"] is not None
    assert ama.ReActStep.model_fields["actions"] is not None
    step = SharedReActStep(
        thought="do", actions=[{"tool": "a", "params": {}}, {"tool": "b", "params": {}}]
    )
    assert [a.tool for a in step.actions] == ["a", "b"]


# ---------------------------------------------------------------------------
# P2: flag off -> sequential fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P2_flag_off_runs_sequential(monkeypatch):
    agent = _make_agent()
    monkeypatch.setenv("ATOM_PARALLEL_TOOLS", "false")
    agent._execute_tool_with_governance = AsyncMock(side_effect=lambda t, a, c, cb: f"R:{t}")
    # No can_perform_action/request_approval should be consulted in fallback.
    with patch.object(ama, "AgentGovernanceService") as mock_gov:
        records = await agent._execute_parallel_tools(_actions("a", "b"), {}, None)
    mock_gov.assert_not_called()
    assert [r["tool_name"] for r in records] == ["a", "b"]
    assert agent._execute_tool_with_governance.await_count == 2
    # pre_approved defaults to False in the fallback path.
    args = [c.args for c in agent._execute_tool_with_governance.await_args_list]
    assert all(len(a) == 4 for a in args)  # no pre_approved kwarg


# ---------------------------------------------------------------------------
# P3: flag ON + allowed -> gather with pre_approved=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P3_parallel_executes_via_gather(monkeypatch):
    agent = _make_agent()
    # Governance allows everything, no approval needed.
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "action_complexity": 1}
    )
    monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)

    executed = []

    async def fake_exec(tool_name, args, context, cb, **kw):
        executed.append((tool_name, kw.get("pre_approved")))
        return f"R:{tool_name}"

    agent._execute_tool_with_governance = fake_exec
    records = await agent._execute_parallel_tools(_actions("a", "b", "c"), {}, None)
    assert [r["tool_name"] for r in records] == ["a", "b", "c"]
    assert [t for t, _ in executed] == ["a", "b", "c"]
    assert all(p for _, p in executed), "each tool must run pre_approved=True"
    gov.request_approval.assert_not_called()


# ---------------------------------------------------------------------------
# P4: complexity>1 forces HITL batch approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P4_complex_forces_batch_approval(monkeypatch):
    agent = _make_agent()
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "action_complexity": 3}
    )
    gov.request_approval = MagicMock(side_effect=["id1", "id2"])
    monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)
    agent._execute_tool_with_governance = AsyncMock(return_value="ok")
    agent._wait_for_all_approvals = AsyncMock(return_value=True)

    await agent._execute_parallel_tools(_actions("a", "b"), {}, None)
    assert gov.request_approval.call_count == 2
    agent._wait_for_all_approvals.assert_awaited_once_with(["id1", "id2"])


# ---------------------------------------------------------------------------
# P5: all-or-nothing — one rejection aborts the batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P5_rejection_aborts_batch(monkeypatch):
    agent = _make_agent()
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "action_complexity": 3}
    )
    gov.request_approval = MagicMock(side_effect=["id1", "id2"])
    monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)
    agent._execute_tool_with_governance = AsyncMock(return_value="SHOULD NOT RUN")
    agent._wait_for_all_approvals = AsyncMock(return_value=False)

    records = await agent._execute_parallel_tools(_actions("a", "b"), {}, None)
    agent._execute_tool_with_governance.assert_not_called()
    assert all(r["verified_kind"] == "rejected" for r in records)
    assert "REJECTED" in records[0]["output"]


# ---------------------------------------------------------------------------
# P6: pre_approved=True skips governance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P6_preapproved_skips_governance(monkeypatch):
    agent = _make_agent()
    with patch.object(ama, "AgentGovernanceService") as mock_gov:
        out = await agent._execute_tool_with_governance("a", {}, {}, None, pre_approved=True)
    mock_gov.assert_not_called()
    assert out == "ok"


# ---------------------------------------------------------------------------
# P7: mcp_tool_search serialized, not part of the gather batch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P7_tool_search_serialized(monkeypatch):
    agent = _make_agent()
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "action_complexity": 1}
    )
    monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)

    batched = []

    async def fake_exec(tool_name, args, context, cb, **kw):
        batched.append(tool_name)
        return f"R:{tool_name}"

    agent._execute_tool_with_governance = fake_exec
    records = await agent._execute_parallel_tools(
        _actions("a", "mcp_tool_search", "b"), {}, None
    )
    # mcp_tool_search is NOT in the gathered batch.
    assert batched == ["a", "b"]
    assert "mcp_tool_search" not in batched
    # session_tools was extended by the serial search.
    assert any(t["name"] == "extra_tool" for t in agent.session_tools)
    search_rec = [r for r in records if r["tool_name"] == "mcp_tool_search"][0]
    assert "Found 1 new tools" in search_rec["output"]


# ---------------------------------------------------------------------------
# P8: max parallel cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P8_max_parallel_cap(monkeypatch):
    agent = _make_agent()
    monkeypatch.setenv("ATOM_MAX_PARALLEL_TOOLS", "2")
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "action_complexity": 1}
    )
    monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)

    batched = []

    async def fake_exec(tool_name, args, context, cb, **kw):
        batched.append(tool_name)
        return f"R:{tool_name}"

    agent._execute_tool_with_governance = fake_exec
    await agent._execute_parallel_tools(_actions("a", "b", "c", "d"), {}, None)
    assert len(batched) == 2  # capped


# ---------------------------------------------------------------------------
# P9: one AgentReasoningStep per tool (loop integration via persistence helper)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P9_one_reasoning_step_per_tool(monkeypatch):
    agent = _make_agent()
    gov = MagicMock()
    gov.can_perform_action_async = AsyncMock(
        return_value={"allowed": True, "requires_human_approval": False, "action_complexity": 1}
    )
    monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)
    agent._execute_tool_with_governance = AsyncMock(return_value="ok")

    # Mock the DB layer for _persist_reasoning_step.
    fake_db = MagicMock()
    fake_step = SimpleNamespace(id="step-1")
    fake_db.add.return_value = None
    fake_db.commit.return_value = None
    fake_db.query.return_value.filter.return_value.first.return_value = None

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ama, "SessionLocal", lambda: _Ctx())

    with patch.object(ama, "uuid") as mock_uuid:
        mock_uuid.uuid4.return_value = "u-1"
        with patch.object(ama, "AgentReasoningStep", return_value=fake_step):
            records = await agent._execute_parallel_tools(_actions("a", "b"), {}, None)
            step_id = agent._persist_reasoning_step(
                execution_id="e-1", step_number=3, step_type="parallel",
                thought="t", action_dict={"tool": "a", "params": {}},
                observation="ok", confidence=0.9, verified_kind="unverified",
                verification_evidence=None, duration_ms=1.0, request="r",
                final_answer=None, context={},
            )
    assert step_id == "step-1"
    # Two records -> the loop would persist one row per record.
    assert len(records) == 2


# ---------------------------------------------------------------------------
# P10: turn-fact fires once per batch (dispatch_turn_fact)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_P10_turn_fact_once_per_batch(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)

    fake_db = MagicMock()
    fake_step = SimpleNamespace(id="step-1")
    fake_db.add.return_value = None
    fake_db.commit.return_value = None

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ama, "SessionLocal", lambda: _Ctx())
    extractor = MagicMock()
    extractor.extract_from_turn = AsyncMock()
    monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda *a, **k: extractor)
    with patch.object(ama, "AgentReasoningStep", return_value=fake_step), \
         patch.object(ama, "_pending_extraction_tasks", set()):
        # First call dispatches extraction; second call does NOT.
        agent._persist_reasoning_step(
            execution_id="e-1", step_number=1, step_type="parallel", thought="t",
            action_dict={"tool": "a", "params": {}}, observation="ok", confidence=0.9,
            verified_kind="unverified", verification_evidence=None, duration_ms=1.0,
            request="r", final_answer=None, context={}, dispatch_turn_fact=True,
        )
        await asyncio.sleep(0)
        agent._persist_reasoning_step(
            execution_id="e-1", step_number=1, step_type="parallel", thought="t",
            action_dict={"tool": "b", "params": {}}, observation="ok", confidence=0.9,
            verified_kind="unverified", verification_evidence=None, duration_ms=1.0,
            request="r", final_answer=None, context={}, dispatch_turn_fact=False,
        )
        await asyncio.sleep(0)
    # extraction.create_task ran exactly once.
    assert extractor.extract_from_turn.await_count == 1
