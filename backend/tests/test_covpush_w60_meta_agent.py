"""Coverage wave 60 — core/atom_meta_agent.py execute() edge branches + bug fixes (TDD).

Closes the last uncovered blocks: vector-recall prefetch failure, registry
hiccup tier fallback, canvas episodic-recall failure, tool-description
serialization fallback, fleet-routing config-import failure / governance
failure / shadow-mode recruitment callback, AgentRadio inbox drain (+
exception), parallel-batch failed-verification CRITIQUE + per-tool stream
callback, single-tool failed-verification CRITIQUE, parse-outcome exception
tolerance, session-end extraction dispatch failure, body-exception finalizer
commit/close failure, execution-record update rollback, stage-router model
override / handoff note / exception, ActionJudge consult error, fleet radio
thread propagation to chain links, parallel parse-outcome exception, plus
two REAL bug fixes:

1. spawn_agent(persist=True) without a db: ``with SessionLocal() as db:``
   (capability-reset block) shadowed the ``db`` parameter, making the
   ``if db is None:`` fresh-session branch unreachable — persistence ran
   against the already-closed reset-block session. Fixed by renaming the
   reset-block variable.
2. generate_mentorship_guidance DB failure: the except block returned
   ``("General", 1)`` while its own trailing comment + unreachable
   ``return ("General", 0)`` document the intent to assume NO supervisors
   (Meta-Agent steps in as interim supervisor). Fixed to return 0.

All deps mocked (WorldModelService / AdvancedWorkflowOrchestrator /
CapabilityGraduationService / SessionLocal / ServiceFactory /
get_canvas_provider), AsyncMock agents, zero LLM spend, no network, no DB.
"""
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ai.nlp_engine import RouteCategory, RouteClassification

import core.atom_meta_agent as ama
from core.atom_meta_agent import AtomMetaAgent, ReActStep, ToolCall


def make_exec_agent(**kw):
    with patch("core.atom_meta_agent.WorldModelService",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.AdvancedWorkflowOrchestrator",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.CapabilityGraduationService",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.SessionLocal",
               return_value=MagicMock()), \
         patch("core.service_factory.ServiceFactory.get_llm_service",
               return_value=MagicMock()), \
         patch("core.atom_meta_agent.get_canvas_provider",
               return_value=MagicMock()):
        agent = AtomMetaAgent(workspace_id="default")
    agent.llm = MagicMock()
    agent.world_model = MagicMock()
    agent.world_model.recall_experiences = AsyncMock(return_value={})
    agent.mcp = MagicMock()
    agent.mcp.get_all_tools = AsyncMock(return_value=[])
    agent.mcp.search_tools = AsyncMock(return_value=[])
    agent.canvas_provider = MagicMock()
    agent._persist_reasoning_step = MagicMock(return_value="step-1")
    agent._record_execution = AsyncMock()
    agent._check_budget_before_react = AsyncMock(
        return_value={"allowed": True, "reason": "ok"})
    for k, v in kw.items():
        setattr(agent, k, v)
    return agent


def _registry(status="autonomous", category="general"):
    return SimpleNamespace(id="ag-1", status=status, category=category,
                           confidence_score=0.8)


def _workspace_session(workspace=None):
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.add = MagicMock()
    db.commit = MagicMock()
    db.close = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        workspace or SimpleNamespace(tenant_id="t-1"))
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
        workspace or SimpleNamespace(tenant_id="t-1"))
    return db


def _db():
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.close = MagicMock()
    return db


def _nlu_patch(route_category=RouteCategory.UNKNOWN, reason="r"):
    """Patch the MODULE-LEVEL NaturalLanguageEngine (line-30 import) — the
    ai.nlp_engine attribute patch used by older waves never intercepts it."""
    nlu = MagicMock()
    nlu.classify_route = AsyncMock(return_value=RouteClassification(
        category=route_category, reasoning=reason, confidence=0.9))
    return patch.object(ama, "NaturalLanguageEngine", return_value=nlu), nlu


class TestExecuteEdgeBranches:
    async def test_vector_recall_prefetch_failure_tolerated(self):
        """435-436: prefetch exception is swallowed, run proceeds."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.atom_meta_agent._prefetch_relevant_facts",
                   side_effect=RuntimeError("lancedb down")), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             nlu_patch:
            result = await agent.execute("hello")
        assert result["status"] == "success"
        assert result["final_output"] == "ok"

    async def test_registry_hiccup_tier_falls_back_autonomous(self):
        """458-459: _get_atom_registry raising once → tier=autonomous, run
        continues (subsequent calls succeed)."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        state = {"n": 0}

        def hiccup_registry():
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("registry down")
            return _registry()

        with patch.object(agent, "_get_atom_registry",
                          new=hiccup_registry), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             nlu_patch:
            result = await agent.execute("hello")
        assert result["status"] == "success"
        assert state["n"] >= 2

    async def test_canvas_episodic_recall_failure_tolerated(self):
        """584-585: canvas-aware episodic recall failure is logged, run
        continues with the plain memory context."""
        agent = make_exec_agent()
        canvas_state = SimpleNamespace(
            canvas_id="cv-1", artifact_count=2, comments=[
                SimpleNamespace(content="user comment")])
        agent.canvas_provider.get_canvas_context = AsyncMock(
            return_value=canvas_state)
        agent.canvas_provider.format_for_agent = MagicMock(
            return_value="CANVAS TEXT")
        agent.world_model.recall_episodes = AsyncMock(
            side_effect=RuntimeError("episodes down"))
        nlu_patch, _ = _nlu_patch()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             nlu_patch:
            result = await agent.execute(
                "with canvas", canvas_context={"canvas_id": "cv-1"})
        assert result["status"] == "success"
        agent.world_model.recall_episodes.assert_called_once()

    async def test_tool_descriptions_serialization_fallback(self):
        """619-621: json.dumps TypeError on tool descriptions → fallback to
        empty-list JSON, run proceeds."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        state = {"n": 0}

        def flaky_dumps(*args, **kwargs):
            state["n"] += 1
            if state["n"] == 1:
                raise TypeError("not serializable")
            return "[]"

        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             patch("core.atom_meta_agent.json.dumps", new=flaky_dumps), \
             nlu_patch:
            result = await agent.execute("hello")
        assert result["status"] == "success"
        assert state["n"] == 2  # failing call + [] fallback

    async def test_fleet_routing_config_import_failure(self):
        """658-660: fleet_routing_config import failure → lambda fallbacks,
        fleet branch skipped entirely."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch(route_category=RouteCategory.ONE_OFF)
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             patch.dict(sys.modules, {"core.fleet_routing_config": None}), \
             nlu_patch:
            result = await agent.execute("x" * 60)
        assert result["status"] == "success"

    async def test_fleet_routing_governance_failure_falls_back(self):
        """698-700: route_with_governance raising → warning + fall through
        to Queen→ReAct (shadow flag off)."""
        agent = make_exec_agent()
        agent.route_with_governance = AsyncMock(
            side_effect=RuntimeError("fleet down"))
        nlu_patch, _ = _nlu_patch(route_category=RouteCategory.ONE_OFF)
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             patch("core.fleet_routing_config.fleet_routing_enabled",
                   return_value=True), \
             patch("core.fleet_routing_config.fleet_routing_force_enforce",
                   return_value=False), \
             nlu_patch:
            result = await agent.execute("x" * 60)
        assert result["status"] == "success"
        agent.route_with_governance.assert_awaited_once()

    async def test_fleet_recruitment_shadow_emits_callback_step(self):
        """707: shadow-mode fleet recruitment emits a synthetic
        fleet_recruitment step via step_callback, then falls through."""
        agent = make_exec_agent()
        agent.route_with_governance = AsyncMock(return_value={
            "status": "fleet_recruited", "specialists_count": 3,
            "chain_id": "ch-9"})
        nlu_patch, _ = _nlu_patch(route_category=RouteCategory.ONE_OFF)
        records = []

        async def cb(step_record):
            records.append(step_record)

        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             patch("core.fleet_routing_config.fleet_routing_enabled",
                   return_value=True), \
             patch("core.fleet_routing_config.fleet_routing_force_enforce",
                   return_value=False), \
             nlu_patch:
            result = await agent.execute("x" * 60, step_callback=cb)
        assert result["status"] == "success"
        assert any(r.get("step_type") == "fleet_recruitment"
                   for r in records)

    async def test_radio_inbox_drain_appends_history(self):
        """811-820: AgentRadio @mention inbox drained into execution_history."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        captured = {}

        async def react(request, memory_context, tool_descriptions,
                        execution_history, context, canvas_text="",
                        turn_index=0):
            captured.setdefault("histories", []).append(execution_history)
            return ReActStep(thought="t", final_answer="ok")

        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step", new=react), \
             patch("core.agent_radio.radio_service.inbox_drain_text",
                   return_value="[RADIO] team @mention about invoice\n"), \
             nlu_patch:
            result = await agent.execute(
                "hello", context={"radio_thread_id": "th-1"})
        assert result["status"] == "success"
        assert "[RADIO] team @mention" in captured["histories"][0]

    async def test_radio_inbox_drain_exception_tolerated(self):
        """821-822: a failing inbox drain must never break the agent loop."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             patch("core.agent_radio.radio_service.inbox_drain_text",
                   side_effect=RuntimeError("radio down")), \
             nlu_patch:
            result = await agent.execute(
                "hello", context={"radio_thread_id": "th-1"})
        assert result["status"] == "success"


class TestReActLoopCritiques:
    async def test_parallel_failed_verification_critique_and_callback(self):
        """931 + 943: parallel batch with failed_verification emits a
        [CRITIQUE] directive + streams each p_record via step_callback."""
        agent = make_exec_agent()
        agent._execute_parallel_tools = AsyncMock(return_value=[
            {"tool_name": "t1", "params": {}, "output": "out",
             "verified_kind": "failed_verification",
             "verified_evidence": "no evidence provided"},
        ])
        nlu_patch, _ = _nlu_patch()
        captured = {"histories": [], "records": []}

        async def react(request, memory_context, tool_descriptions,
                        execution_history, context, canvas_text="",
                        turn_index=0):
            captured["histories"].append(execution_history)
            if turn_index == 0:
                return ReActStep(thought="t1", actions=[
                    ToolCall(tool="t1", params={})])
            return ReActStep(thought="t2", final_answer="done")

        async def cb(step_record):
            captured["records"].append(step_record)

        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step", new=react), \
             patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             nlu_patch:
            result = await agent.execute("run both", step_callback=cb)
        assert result["status"] == "success"
        assert "The action t1 failed verification" in captured["histories"][1]
        assert any(r.get("step_type") == "parallel"
                   for r in captured["records"])

    async def test_single_tool_failed_verification_critique(self):
        """1025: single-action failed_verification appends a [CRITIQUE]."""
        agent = make_exec_agent()
        agent._execute_tool_with_governance = AsyncMock(return_value="out")
        nlu_patch, _ = _nlu_patch()
        captured = {}

        async def react(request, memory_context, tool_descriptions,
                        execution_history, context, canvas_text="",
                        turn_index=0):
            captured["histories"] = captured.get("histories", [])
            captured["histories"].append(execution_history)
            if turn_index == 0:
                return ReActStep(thought="t1", action=ToolCall(
                    tool="run_tool", params={}))
            return ReActStep(thought="t2", final_answer="done")

        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step", new=react), \
             patch("core.atom_meta_agent.parse_tool_outcome",
                   return_value=SimpleNamespace(
                       kind="failed_verification", success=False,
                       evidence="no evidence provided")), \
             nlu_patch:
            result = await agent.execute("do it")
        assert result["status"] == "success"
        assert "The action run_tool failed verification" in captured["histories"][1]

    async def test_parse_tool_outcome_exception_tolerated(self):
        """1035-1037: a raising parse_tool_outcome degrades to 'unverified'
        without breaking the step."""
        agent = make_exec_agent()
        agent._execute_tool_with_governance = AsyncMock(return_value="out")
        nlu_patch, _ = _nlu_patch()
        react_returns = [
            ReActStep(thought="t1", action=ToolCall(tool="run_tool",
                                                    params={})),
            ReActStep(thought="t2", final_answer="done"),
        ]
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=react_returns)), \
             patch("core.atom_meta_agent.parse_tool_outcome",
                   side_effect=RuntimeError("parse boom")), \
             nlu_patch:
            result = await agent.execute("do it")
        assert result["status"] == "success"
        persist_call = agent._persist_reasoning_step.call_args_list[0]
        assert persist_call.kwargs["verified_kind"] == "unverified"
        assert persist_call.kwargs["verification_evidence"] is None

    async def test_session_end_extraction_dispatch_failure(self):
        """1109-1110: on_session_end extraction dispatch failure is logged,
        run completes normally."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   return_value=_workspace_session()), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", True), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             patch("core.atom_meta_agent.get_turn_fact_extractor",
                   side_effect=RuntimeError("extractor down")), \
             nlu_patch:
            result = await agent.execute("hello")
        assert result["status"] == "success"


class TestExecuteFailureFinalizers:
    async def test_body_exception_finalize_commit_and_close_failure(self):
        """1138-1139 + 1143: finalizer commit failure logged + close failure
        swallowed; the original body exception still propagates."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        ws_db = _workspace_session()
        fin_db = MagicMock()
        fin_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
            SimpleNamespace())
        fin_db.commit = MagicMock(side_effect=RuntimeError("commit boom"))
        fin_db.close = MagicMock(side_effect=RuntimeError("close boom"))
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   side_effect=[ws_db, fin_db]), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(side_effect=RuntimeError("boom"))), \
             nlu_patch:
            with pytest.raises(RuntimeError, match="boom"):
                await agent.execute("run")
        fin_db.commit.assert_called_once()

    async def test_execution_record_update_failure_rolls_back(self):
        """1186-1188: post-run AgentExecution update failure → rollback +
        close; payload still returned."""
        agent = make_exec_agent()
        nlu_patch, _ = _nlu_patch()
        ws_db = _workspace_session()
        upd_db = MagicMock()
        upd_db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = (
            SimpleNamespace())
        upd_db.commit = MagicMock(side_effect=RuntimeError("update boom"))
        with patch.object(agent, "_get_atom_registry",
                          return_value=_registry()), \
             patch("core.atom_meta_agent.SessionLocal",
                   side_effect=[ws_db, upd_db]), \
             patch("core.atom_meta_agent._TURN_FACT_EXTRACTION_ENABLED", False), \
             patch("core.field_guide_service.get_field_guide_service",
                   return_value=MagicMock(get_field_guide_context=lambda w: "")), \
             patch.object(agent, "_react_step",
                          new=AsyncMock(return_value=ReActStep(
                              thought="t", final_answer="ok"))), \
             nlu_patch:
            result = await agent.execute("hello")
        assert result["status"] == "success"
        upd_db.rollback.assert_called_once()


class TestReactStepStageRouter:
    async def test_stage_router_override_model_and_handoff(self):
        """1374 + 1380: stage-router decision overrides the model type and
        appends the handoff note to the system prompt."""
        agent = make_exec_agent()
        agent.llm.generate_structured_response = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="ok"))
        router = MagicMock()
        router.enabled = True
        decision = SimpleNamespace(
            applied_group="efficient", handoff_note="NOTE: switching to efficient",
            id="sr-1")
        router.decide_for_history = AsyncMock(return_value=decision)
        policy = SimpleNamespace(enforce=True)
        with patch("core.llm.stage_router.get_stage_router",
                   return_value=router), \
             patch("core.llm.stage_router.resolve_agent_policy",
                   return_value=policy), \
             patch("core.llm.stage_router.map_decision_to_model_type",
                   return_value="fast"):
            result = await agent._react_step("request", {}, "tools", "", {})
        assert result.final_answer == "ok"
        kwargs = agent.llm.generate_structured_response.call_args.kwargs
        assert kwargs["model"] == "fast"
        assert "NOTE: switching to efficient" in kwargs["system_instruction"]
        assert kwargs["stage_decision_id"] == "sr-1"
        assert agent._stage_group == "efficient"

    async def test_stage_router_exception_keeps_model(self):
        """1376-1378: a failing stage router never breaks the step; the
        default model selection is kept."""
        agent = make_exec_agent()
        agent.llm.generate_structured_response = AsyncMock(
            return_value=ReActStep(thought="t", final_answer="ok"))
        with patch("core.llm.stage_router.get_stage_router",
                   side_effect=RuntimeError("router down")):
            result = await agent._react_step("request", {}, "tools", "", {})
        assert result.final_answer == "ok"
        kwargs = agent.llm.generate_structured_response.call_args.kwargs
        assert kwargs["model"] == "reasoning"
        assert kwargs["stage_decision_id"] is None


class TestActionJudgeError:
    async def test_action_judge_consult_exception_proceeds(self):
        """1703-1704: a raising ActionJudge consult is skipped and the tool
        executes normally."""
        agent = make_exec_agent()
        agent.mcp.call_tool = AsyncMock(
            return_value={"status": "success", "output": "ok"})
        judge = MagicMock()
        judge.evaluate = AsyncMock(side_effect=RuntimeError("judge down"))
        with patch("core.sandbox_config.is_sandbox_judge_enabled",
                   return_value=True), \
             patch("core.llm.action_judge.ActionJudge", return_value=judge):
            result = await agent._execute_tool_with_governance(
                "run_tool", {}, {}, None, pre_approved=True)
        assert "success" in result
        agent.mcp.call_tool.assert_called_once()


class TestRecruitFleetRadio:
    async def test_radio_thread_id_propagated_to_chain_links(self):
        """1820-1826: a non-None radio thread is written into context AND
        propagated onto every ChainLink's context_json."""
        agent = make_exec_agent()
        fleet = MagicMock()
        chain = SimpleNamespace(id="chain-1")
        fleet.initialize_fleet.return_value = chain
        fleet.recruit_member.return_value = SimpleNamespace(id="link-1")
        optimizer = MagicMock()
        optimizer.get_optimization_parameters.return_value = {
            "optimization_reason": "r", "params": {}}
        specialist = SimpleNamespace(id="spec-1", name="Sales")
        link = SimpleNamespace(context_json={"k": "v"})
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        db.query.return_value.filter.return_value.all.return_value = [link]
        context = {"execution_id": "ex-1"}
        with patch("core.business_agents.get_specialized_agent",
                   return_value=specialist), \
             patch("core.atom_meta_agent.AgentFleetService",
                   return_value=fleet), \
             patch("core.atom_meta_agent.FleetOptimizationService",
                   return_value=optimizer), \
             patch("core.atom_meta_agent.SessionLocal", return_value=db), \
             patch("core.agent_radio.radio_adapter.attach_thread_for_chain",
                   return_value=SimpleNamespace(id="th-1")):
            result = await agent._recruit_fleet(
                "big goal",
                [{"domain": "sales", "task": "analyze"}],
                context, None)
        assert "Fleet" in result
        assert context["radio_thread_id"] == "th-1"
        assert link.context_json == {"k": "v", "radio_thread_id": "th-1"}
        db.commit.assert_called_once()


class TestParallelOutcomeParse:
    async def test_parallel_batch_parse_outcome_exception(self):
        """2218-2220: parse_tool_outcome raising on a parallel result
        degrades to 'unverified' without failing the batch."""
        agent = make_exec_agent()
        agent._execute_tool_with_governance = AsyncMock(return_value="ok")
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": True, "action_complexity": 1,
                          "reason": "ok"})
        with patch("core.hallucination_config.is_parallel_tools_enabled",
                   return_value=True), \
             patch("core.hallucination_config.get_max_parallel_tools",
                   return_value=5), \
             patch("core.atom_meta_agent.SessionLocal", return_value=_db()), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   return_value=gov), \
             patch("core.atom_meta_agent.parse_tool_outcome",
                   side_effect=RuntimeError("parse boom")):
            records = await agent._execute_parallel_tools(
                [ToolCall(tool="tool_a", params={})], {}, None)
        assert records[0]["verified_kind"] == "unverified"
        assert records[0]["output"] == "ok"


class TestSpawnAgentFreshSession:
    async def test_persist_without_db_opens_fresh_session(self):
        """BUG FIX: `with SessionLocal() as db:` in the capability-reset
        block shadowed the ``db`` parameter, dead-coding the
        `if db is None:` fresh-session persist branch. The governance
        service must be built on a NEW session, never the reset block's
        (already closed) one."""
        agent = make_exec_agent()
        reset_sess = MagicMock()
        fresh_sess = MagicMock()
        gov = MagicMock()
        gov.register_or_update_agent.return_value = SimpleNamespace(id="reg-1")
        captured = {}

        def gov_factory(session, **kw):
            captured["session"] = session
            return gov

        with patch("core.atom_meta_agent.AgentRegistry",
                   lambda **kw: SimpleNamespace(**kw)), \
             patch("core.atom_meta_agent.SessionLocal",
                   side_effect=[reset_sess, fresh_sess]), \
             patch("core.atom_meta_agent.AgentGovernanceService",
                   new=gov_factory):
            result = await agent.spawn_agent("finance_analyst", persist=True)
        assert result.id == "reg-1"
        reset_entered = reset_sess.__enter__()
        fresh_entered = fresh_sess.__enter__()
        assert captured["session"] is fresh_entered
        assert captured["session"] is not reset_entered


class TestMentorshipDbFallback:
    async def test_db_failure_treats_as_no_supervisors(self):
        """BUG FIX: on DB failure _check_supervisors_sync must return 0
        (documented intent: 'Meta Agent steps in' as interim supervisor) —
        the old `return 1` made the mentorship NOTE unreachable and left an
        unreachable `return 0` behind."""
        agent = make_exec_agent()
        agent.llm.generate_response = AsyncMock(return_value="guidance text")
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with patch("core.atom_meta_agent.SessionLocal") as sl:
            sl.return_value.__enter__.return_value = db
            result = await agent.generate_mentorship_guidance(
                "student-1", "create_record", {"a": 1}, "needs approval")
        assert result == "guidance text"
        system_instruction = agent.llm.generate_response.call_args.kwargs[
            "system_instruction"]
        assert "Interim Supervisor" in system_instruction
        assert "NO higher maturity agents" in system_instruction
