"""Coverage wave 73b — core/agents/{autoresearch,king,queen,skill_creation}_agent.py.

Each module must hit >=95% statement coverage standalone (this file only).
Style: mocked deps, zero LLM spend, no network, no real DB.
"""
import json
import os
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.agents.autoresearch_agent import AutoresearchAgent
from core.agents.king_agent import KingAgent
from core.agents.queen_agent import QueenAgent
from core.agents.skill_creation_agent import SkillCreationAgent


# ---------------------------------------------------------------------------
# AutoresearchAgent — core/agents/autoresearch_agent.py
# ---------------------------------------------------------------------------

class TestAutoresearchAgent:
    def test_init(self):
        agent = AutoresearchAgent(db=Mock(), llm_service=Mock())
        assert agent.db is not None
        assert agent.llm is not None

    async def _run_loop(self, tmp_path, llm_content, metrics, iterations=2):
        program = tmp_path / "program.md"
        script = tmp_path / "train.py"
        program.write_text("instructions for the experiment")
        script.write_text("print('base code')")
        agent = AutoresearchAgent(db=Mock(), llm_service=Mock())
        agent.llm.generate = AsyncMock(return_value=llm_content)
        with patch.object(agent, "_evaluate_script", new=AsyncMock(side_effect=metrics)):
            result = await agent.run_experiment_loop(
                str(program), str(script), iterations=iterations
            )
        return agent, result, script

    async def test_run_loop_accept_and_reject(self, tmp_path):
        agent, result, script = await self._run_loop(
            tmp_path, "new_code_v1", [0.5, 2.0]
        )
        assert result["status"] == "success"
        assert result["best_metric"] == 0.5
        assert result["history"][0]["kept"] is True
        assert result["history"][1]["kept"] is False
        assert "new_code_v1" in script.read_text()

    async def test_run_loop_all_accepted(self, tmp_path):
        _, result, script = await self._run_loop(
            tmp_path, "code_2", [0.9, 0.4]
        )
        assert result["best_metric"] == 0.4
        assert all(h["kept"] for h in result["history"])
        assert script.read_text() == "code_2"

    async def test_run_loop_metric_none_rejected(self, tmp_path):
        _, result, script = await self._run_loop(
            tmp_path, "code_3", [None, 0.2]
        )
        assert result["best_metric"] == 0.2
        assert result["history"][0]["kept"] is False
        assert result["history"][0]["metric"] is None

    async def test_run_loop_best_metric_stays_none(self, tmp_path):
        _, result, script = await self._run_loop(
            tmp_path, "code_4", [None, None]
        )
        assert result["best_metric"] is None
        assert not os.path.exists(str(tmp_path / "train.py.tmp"))

    async def test_run_loop_strips_fenced_code(self, tmp_path):
        agent, result, _ = await self._run_loop(
            tmp_path, "```python\nfenced_code\n```", [0.1, 0.1]
        )
        assert result["history"][0]["kept"] is True
        script = tmp_path / "train.py"
        assert script.read_text() == "fenced_code"

    async def test_run_loop_read_instructions_failure(self, tmp_path):
        agent = AutoresearchAgent(db=Mock(), llm_service=Mock())
        result = await agent.run_experiment_loop(
            str(tmp_path / "missing.md"), str(tmp_path / "train.py")
        )
        assert result == {"status": "error", "message": "Failed to read instructions"}

    async def test_run_loop_read_script_failure(self, tmp_path):
        program = tmp_path / "program.md"
        program.write_text("instructions")
        agent = AutoresearchAgent(db=Mock(), llm_service=Mock())
        result = await agent.run_experiment_loop(
            str(program), str(tmp_path / "missing.py")
        )
        assert result == {"status": "error", "message": "Failed to read target script"}

    async def test_run_loop_llm_failure_continues(self, tmp_path):
        program = tmp_path / "program.md"
        script = tmp_path / "train.py"
        program.write_text("instructions")
        script.write_text("print('x')")
        agent = AutoresearchAgent(db=Mock(), llm_service=Mock())
        agent.llm.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        result = await agent.run_experiment_loop(
            str(program), str(script), iterations=2
        )
        assert result["status"] == "success"
        assert result["history"] == []
        assert result["best_metric"] is None

    async def _evaluator(self, returncode=0, stdout=b"", stderr=b"", raise_exec=False):
        agent = AutoresearchAgent(db=Mock(), llm_service=Mock())
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(stdout, stderr))
        if raise_exec:
            return agent, AsyncMock(side_effect=RuntimeError("no python"))
        return agent, AsyncMock(return_value=proc)

    async def test_evaluate_script_parses_metric(self):
        agent, exec_mock = await self._evaluator(
            stdout=b"epoch done\nFINAL_METRIC: 0.42\n"
        )
        with patch("core.agents.autoresearch_agent.asyncio.create_subprocess_exec", exec_mock):
            metric = await agent._evaluate_script("/tmp/x.py")
        assert metric == 0.42

    async def test_evaluate_script_nonzero_returncode(self):
        agent, exec_mock = await self._evaluator(
            returncode=1, stderr=b"crash"
        )
        with patch("core.agents.autoresearch_agent.asyncio.create_subprocess_exec", exec_mock):
            metric = await agent._evaluate_script("/tmp/x.py")
        assert metric is None

    async def test_evaluate_script_unparseable_metric(self):
        agent, exec_mock = await self._evaluator(
            stdout=b"FINAL_METRIC: not_a_number\n"
        )
        with patch("core.agents.autoresearch_agent.asyncio.create_subprocess_exec", exec_mock):
            metric = await agent._evaluate_script("/tmp/x.py")
        assert metric is None

    async def test_evaluate_script_metric_not_found(self):
        agent, exec_mock = await self._evaluator(stdout=b"no metric here\n")
        with patch("core.agents.autoresearch_agent.asyncio.create_subprocess_exec", exec_mock):
            metric = await agent._evaluate_script("/tmp/x.py")
        assert metric is None

    async def test_evaluate_script_subprocess_error(self):
        agent, exec_mock = await self._evaluator(raise_exec=True)
        with patch("core.agents.autoresearch_agent.asyncio.create_subprocess_exec", exec_mock):
            metric = await agent._evaluate_script("/tmp/x.py")
        assert metric is None


# ---------------------------------------------------------------------------
# KingAgent — core/agents/king_agent.py
# ---------------------------------------------------------------------------

class TestKingAgent:
    def _king(self, node_result=None):
        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king.workspace_id = "default"
        king.tenant_id = "default"
        if node_result is not None:
            king._execute_node = AsyncMock(return_value=node_result)
        return king

    @staticmethod
    def _node(node_id, name="N", node_type="agent", capability="c", deps=()):
        return {
            "id": node_id, "name": name, "type": node_type,
            "capability_required": capability, "dependencies": list(deps),
        }

    def test_init(self):
        llm = MagicMock()
        with patch("core.atom_meta_agent.WorldModelService"), patch(
            "core.atom_meta_agent.AdvancedWorkflowOrchestrator"
        ), patch("core.atom_meta_agent.SessionLocal") as sl, patch(
            "core.service_factory.ServiceFactory.get_llm_service", return_value=llm
        ), patch("core.atom_meta_agent.get_canvas_provider"), patch(
            "core.atom_meta_agent.mcp_service"
        ), patch("core.agents.king_agent.BlueprintHealer") as bh:
            db = Mock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            king = KingAgent(workspace_id="ws1", tenant_id="t1")
        assert king.workspace_id == "ws1"
        assert king.tenant_id == "t1"
        bh.assert_called_once()

    async def test_execute_simple_success(self):
        king = self._king(node_result={"ok": True})
        res = await king.execute_blueprint({
            "architecture_name": "Simple",
            "blueprint_id": "bp-1",
            "nodes": [self._node("n1")],
        })
        assert res["status"] == "success"
        assert res["execution_results"][0]["status"] == "completed"
        assert res["blueprint_id"] == "bp-1"

    async def test_execute_success_with_canvas(self):
        king = self._king(node_result={"ok": True})
        uc = AsyncMock(return_value={"success": True})
        pm = AsyncMock(return_value={"success": True, "canvas_id": "c1"})
        with patch("core.agents.king_agent.update_canvas", new=uc), patch(
            "core.agents.king_agent.present_markdown", new=pm
        ):
            res = await king.execute_blueprint(
                {
                    "architecture_name": "Canvas Flow",
                    "nodes": [self._node("n1"), self._node("n2", deps=("n1",))],
                },
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert res["status"] == "success"
        pm.assert_awaited_once()
        # in_progress + completed updates
        assert uc.await_count == 4

    async def test_execute_stalled_circular_dependency(self):
        king = self._king(node_result={"ok": True})
        res = await king.execute_blueprint({
            "architecture_name": "Stall",
            "nodes": [self._node("a", deps=("missing-dep",))],
        })
        assert res["status"] == "success"
        assert res["execution_results"] == []

    async def test_node_error_heal_failed(self):
        king = self._king(node_result={"error": "node exploded"})
        king.healer.heal_blueprint = AsyncMock(return_value={"status": "failed"})
        res = await king.execute_blueprint({
            "architecture_name": "X",
            "nodes": [self._node("n1")],
        })
        assert res["status"] == "failed"
        assert res["error"] == "node exploded"
        king.healer.heal_blueprint.assert_awaited_once()

    async def test_node_exception_heal_success_records_trace(self):
        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king._execute_node = AsyncMock(side_effect=[{"error": "boom"}, {"ok": True}])
        king.healer.heal_blueprint = AsyncMock(return_value={
            "status": "healed",
            "nodes": [self._node("n2")],
        })
        king.healer.summarize_healing_as_directive = AsyncMock(return_value="directive")
        with patch("core.agents.king_agent.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await king.execute_blueprint({
                "architecture_name": "X",
                "blueprint_id": "bp-1",
                "nodes": [self._node("n1")],
            })
        assert res["status"] == "success"
        assert res["final_summary"].endswith("with 1 heal events.")
        db.add.assert_called()
        db.commit.assert_called_once()

    async def test_heal_success_trace_failure(self):
        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king._execute_node = AsyncMock(side_effect=[{"error": "boom"}, {"ok": True}])
        king.healer.heal_blueprint = AsyncMock(return_value={
            "status": "healed",
            "nodes": [self._node("n2")],
        })
        king.healer.summarize_healing_as_directive = AsyncMock(
            side_effect=RuntimeError("trace boom")
        )
        with patch("core.agents.king_agent.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await king.execute_blueprint({
                "architecture_name": "X",
                "nodes": [self._node("n1")],
            })
        assert res["status"] == "success"

    async def test_heal_restart_with_canvas_title(self):
        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king._execute_node = AsyncMock(side_effect=[{"error": "boom"}, {"ok": True}])
        king.healer.heal_blueprint = AsyncMock(return_value={
            "status": "healed",
            "architecture_name": "Healed Arch",
            "nodes": [self._node("n2")],
        })
        king.healer.summarize_healing_as_directive = AsyncMock(return_value="d")
        uc = AsyncMock(return_value={"success": True})
        pm = AsyncMock(return_value={"success": True, "canvas_id": "c1"})
        with patch("core.agents.king_agent.update_canvas", new=uc), patch(
            "core.agents.king_agent.present_markdown", new=pm
        ), patch("core.agents.king_agent.SessionLocal") as sl:
            db = Mock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await king.execute_blueprint(
                {
                    "architecture_name": "X",
                    "nodes": [self._node("n1")],
                },
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert res["status"] == "success"
        assert res["final_summary"].startswith("Blueprint 'Healed Arch'")
        title_calls = [c.kwargs.get("updates", {}).get("title") for c in uc.await_args_list]
        assert any(t and "Healed Plan (1)" in t for t in title_calls)

    async def test_execute_node_agent_type(self):
        king = self._king()
        king._execute_delegation = AsyncMock(return_value={"ok": True})
        res = await king._execute_node(
            self._node("a", node_type="agent", capability="lead_scoring"), {}, None
        )
        assert res["ok"] is True
        king._execute_delegation.assert_awaited_once()
        args = king._execute_delegation.await_args
        assert args.kwargs["agent_name"] == "sales"

    async def test_execute_node_skill_type(self):
        king = self._king()
        king._execute_tool_with_governance = AsyncMock(return_value={"ok": True})
        res = await king._execute_node(
            self._node("s", node_type="skill", capability="search"), {}, None
        )
        assert res["ok"] is True
        king._execute_tool_with_governance.assert_awaited_once()

    async def test_execute_node_unknown_type(self):
        king = self._king()
        res = await king._execute_node(
            self._node("u", node_type="alien"), {}, None
        )
        assert res["status"] == "skipped"

    def test_map_capability_to_agent(self):
        king = self._king()
        mapping = {
            "reconciliation": "accounting",
            "lead_scoring": "sales",
            "inventory_check": "logistics",
            "campaign_analysis": "marketing",
            "b2b_extract_po": "purchasing",
        }
        for capability, expected in mapping.items():
            assert king._map_capability_to_agent(capability) == expected
        assert king._map_capability_to_agent("unknown_thing") == "general"
        assert king._map_capability_to_agent(None) == "general"


# ---------------------------------------------------------------------------
# QueenAgent — core/agents/queen_agent.py
# ---------------------------------------------------------------------------

class TestQueenAgent:
    @pytest.fixture
    def queen(self):
        with patch("core.agents.queen_agent.SkillCreationAgent"):
            return QueenAgent(db=Mock(), llm=Mock())

    @staticmethod
    def _blueprint(nodes=None):
        return {
            "architecture_name": "Test Arch",
            "description": "desc",
            "nodes": nodes or [
                {"id": "n1", "type": "agent", "name": "Agent 1",
                 "capability_required": "x", "dependencies": []},
            ],
            "required_integrations": [],
            "missing_capabilities": [],
        }

    async def test_generate_blueprint_one_off(self, queen):
        queen.llm.generate = AsyncMock(return_value=json.dumps(self._blueprint()))
        result = await queen.generate_blueprint("do something")
        assert result["architecture_name"] == "Test Arch"
        assert result["blueprint_id"]
        prompt = queen.llm.generate.await_args.kwargs["prompt"]
        assert "ONE-OFF TASK" in prompt
        queen.llm.generate.await_args.kwargs["user_id"] is None

    async def test_generate_blueprint_recurring(self, queen):
        captured = {}

        async def generate(**kwargs):
            captured["prompt"] = kwargs["prompt"]
            return json.dumps(self._blueprint())

        queen.llm.generate = generate
        result = await queen.generate_blueprint(
            "daily report", execution_mode="recurring_automation"
        )
        assert "RECURRING AUTOMATION" in captured["prompt"]
        assert result["blueprint_id"]

    async def test_generate_blueprint_fenced_json(self, queen):
        queen.llm.generate = AsyncMock(
            return_value="```json\n" + json.dumps(self._blueprint()) + "\n```"
        )
        result = await queen.generate_blueprint("x", user_id="u1")
        assert result["architecture_name"] == "Test Arch"

    async def test_generate_blueprint_missing_capabilities(self, queen):
        bp = self._blueprint()
        bp["missing_capabilities"] = [{"name": "c1", "description": "d"}]
        queen.llm.generate = AsyncMock(return_value=json.dumps(bp))
        result = await queen.generate_blueprint("x", tenant_id="t1")
        assert result["missing_capabilities"][0]["name"] == "c1"

    async def test_generate_blueprint_llm_failure_fallback(self, queen):
        queen.llm.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        result = await queen.generate_blueprint("anything")
        assert result["status"] == "fallback"
        assert result["nodes"][0]["id"] == "step_1"

    async def test_generate_blueprint_invalid_json_fallback(self, queen):
        queen.llm.generate = AsyncMock(return_value="not json at all")
        result = await queen.generate_blueprint("anything")
        assert result["status"] == "fallback"

    def test_generate_mermaid_basic(self, queen):
        bp = self._blueprint(nodes=[
            {"id": "n1", "type": "agent", "name": "Agent 1", "dependencies": []},
            {"id": "n2", "type": "trigger", "name": "Trigger", "dependencies": ["n1"]},
        ])
        mermaid = queen.generate_mermaid(bp, {"n1": "completed", "n2": "failed"})
        assert mermaid.startswith("graph TD")
        assert "classDef completed" in mermaid
        assert "classDef in_progress" in mermaid
        assert "classDef failed" in mermaid
        assert "classDef pending" in mermaid
        assert "class n1 completed" in mermaid
        assert "class n2 failed" in mermaid
        assert "n1 --> n2" in mermaid
        assert "(AGENT)" in mermaid and "(TRIGGER)" in mermaid

    def test_generate_mermaid_skips_missing_id_or_name(self, queen):
        bp = self._blueprint(nodes=[
            {"type": "agent", "name": "NoId", "dependencies": []},
            {"id": "n2", "dependencies": []},
            {"id": "n3", "type": "agent", "name": "Ok", "dependencies": []},
        ])
        mermaid = queen.generate_mermaid(bp)
        assert "NoId" not in mermaid
        assert "n2" not in mermaid
        assert "n3" in mermaid

    def test_generate_mermaid_default_pending_and_type(self, queen):
        mermaid = queen.generate_mermaid(self._blueprint())
        assert "class n1 pending" in mermaid
        assert "(AGENT)" in mermaid

    def test_fallback_blueprint_shape(self, queen):
        fb = queen._generate_fallback_blueprint("goal here")
        assert fb["description"] == "Fallback architecture for: goal here"
        assert fb["status"] == "fallback"
        assert fb["blueprint_id"]
        assert fb["nodes"][0]["capability_required"] == "general_reasoning"

    @staticmethod
    def _orchestrator_stack(orchestrator, wf_steps, captured, with_step_types=True):
        stack = ExitStack()

        def fake_step(**kwargs):
            wf_steps.append(kwargs)
            return SimpleNamespace(**kwargs)

        def fake_def(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(**kwargs)

        stack.enter_context(patch(
            "advanced_workflow_orchestrator.get_orchestrator",
            return_value=orchestrator))
        stack.enter_context(patch(
            "advanced_workflow_orchestrator.WorkflowStep", fake_step))
        stack.enter_context(patch(
            "advanced_workflow_orchestrator.WorkflowDefinition", fake_def))
        if with_step_types:
            stack.enter_context(patch(
                "advanced_workflow_orchestrator.WorkflowStepType",
                SimpleNamespace(
                    NLU_ANALYSIS="nlu",
                    BUSINESS_AGENT_EXECUTION="agent",
                    KNOWLEDGE_UPDATE="knowledge",
                    UNIVERSAL_INTEGRATION="universal",
                ),
            ))
        return stack

    async def test_realize_blueprint_orchestrator_unavailable(self, queen):
        with patch("builtins.__import__", side_effect=ImportError("no module")):
            result = await queen.realize_blueprint(self._blueprint())
        assert result == "orchestrator_not_available"

    async def test_realize_blueprint_full_mapping(self, queen):
        orchestrator = Mock()
        wf_steps = []
        captured = {}
        bp = self._blueprint(nodes=[
            {"id": "t1", "type": "trigger", "name": "Event",
             "metadata": {"trigger_event": "new_order"}, "dependencies": []},
            {"id": "a1", "type": "agent", "name": "Process",
             "dependencies": ["t1"]},
            {"id": "e1", "type": "entity", "name": "Order",
             "dependencies": ["a1"]},
            {"id": "u1", "type": "other", "name": "Integrate",
             "dependencies": ["e1"]},
        ])
        with self._orchestrator_stack(orchestrator, wf_steps, captured):
            result = await queen.realize_blueprint(bp, tenant_id="t1")
        assert result.startswith("ai_wf_")
        assert len(wf_steps) == 4
        assert captured["start_step"] == "t1"
        assert captured["triggers"] == ["new_order"]
        assert captured["name"] == "Test Arch"
        orchestrator.register_workflow.assert_called_once()
        types = [s["step_type"] for s in wf_steps]
        assert types == ["nlu", "agent", "knowledge", "universal"]

    async def test_realize_blueprint_ghost_dependency_and_no_ids(self, queen):
        orchestrator = Mock()
        wf_steps = []
        captured = {}
        bp = self._blueprint(nodes=[
            {"type": "agent", "name": "NoId", "dependencies": []},
            {"id": "a1", "type": "agent", "name": "A",
             "dependencies": ["ghost-dep"]},
            {"id": "a2", "type": "agent", "name": "B",
             "dependencies": ["a1"]},
        ])
        with self._orchestrator_stack(orchestrator, wf_steps, captured):
            result = await queen.realize_blueprint(bp)
        assert result.startswith("ai_wf_")
        assert len(wf_steps) == 2
        assert captured["start_step"] in ("a1", "a2")

    async def test_realize_blueprint_start_falls_back_to_first_step(self, queen):
        orchestrator = Mock()
        captured = {}
        bp = self._blueprint(nodes=[
            {"id": "a1", "type": "agent", "name": "A", "dependencies": ["a2"]},
            {"id": "a2", "type": "agent", "name": "B", "dependencies": ["a1"]},
        ])
        with self._orchestrator_stack(orchestrator, [], captured):
            await queen.realize_blueprint(bp)
        assert captured["start_step"] == "a1"

    async def test_realize_blueprint_first_no_dep_node_wins(self, queen):
        orchestrator = Mock()
        captured = {}
        bp = self._blueprint(nodes=[
            {"id": "a1", "type": "agent", "name": "A", "dependencies": []},
            {"id": "a2", "type": "agent", "name": "B", "dependencies": ["a1"]},
        ])
        with self._orchestrator_stack(orchestrator, [], captured):
            await queen.realize_blueprint(bp)
        assert captured["start_step"] == "a1"
        assert captured["triggers"] == []


# ---------------------------------------------------------------------------
# SkillCreationAgent — core/agents/skill_creation_agent.py
# ---------------------------------------------------------------------------

class TestSkillCreationAgent:
    @pytest.fixture
    def agent(self):
        with patch("core.agents.skill_creation_agent.httpx.AsyncClient"):
            a = SkillCreationAgent(db=Mock(), llm_service=Mock())
        a.client = MagicMock()
        return a

    def test_init(self):
        with patch("core.agents.skill_creation_agent.httpx.AsyncClient") as client:
            a = SkillCreationAgent(db=Mock(), llm_service=Mock())
        assert a.client is client.return_value
        assert a.openclaw_parser is not None

    # -- create_skill_from_api_documentation ---------------------------------

    async def test_create_skill_success(self, agent):
        agent._fetch_api_docs = AsyncMock(return_value={"openapi": "3.0.0"})
        analysis = {
            "suggested_name": "acme-fetcher",
            "description": "Fetch data from Acme API",
            "long_description": "full description",
            "base_url": "https://api.acme.com",
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object"},
            "auth_headers": {"Authorization": "Bearer {{API_KEY}}"},
            "config": {"example_path": "/things"},
            "category": "productivity",
            "tags": ["api"],
        }
        agent._analyze_api_spec = AsyncMock(return_value=analysis)
        agent._generate_skill_code = AsyncMock(return_value="async def execute(): ...")
        skill = Mock()
        skill.id = "skill-1"
        skill.name = "acme-fetcher"
        skill.description = "Fetch data from Acme API"
        skill.type = "api"
        with patch("core.agents.skill_creation_agent.Skill", return_value=skill), \
             patch("core.agents.skill_creation_agent.SkillVersion") as sv:
            result = await agent.create_skill_from_api_documentation(
                tenant_id="t1", agent_id="a1", user_id="u1",
                api_docs_url="https://api.acme.com/openapi.json",
                api_description="acme rest json",
                category="crm",
            )
        assert result is skill
        skill.name = "acme-fetcher"
        agent.db.add.assert_called()
        agent.db.commit.assert_called_once()
        sv.assert_called_once()

    async def test_create_skill_default_name_and_category(self, agent):
        agent._fetch_api_docs = AsyncMock(return_value={})
        analysis = {
            "suggested_name": "fallback-fetcher",
            "description": "d", "long_description": "l", "base_url": "",
            "input_schema": {}, "output_schema": {},
            "auth_headers": {}, "config": {}, "category": None, "tags": [],
        }
        agent._analyze_api_spec = AsyncMock(return_value=analysis)
        agent._generate_skill_code = AsyncMock(return_value="code")
        with patch("core.agents.skill_creation_agent.Skill") as skill_cls, \
             patch("core.agents.skill_creation_agent.SkillVersion"):
            skill = Mock()
            skill.id = "s2"
            skill.name = "fallback-fetcher"
            skill_cls.return_value = skill
            result = await agent.create_skill_from_api_documentation(
                tenant_id="t1", agent_id="a1", user_id="u1",
                api_docs_url="https://x.example/spec.json",
                api_description="plain",
            )
        assert result.name == "fallback-fetcher"
        config = skill_cls.call_args.kwargs["config"]
        assert config["url"] == ""

    async def test_create_skill_failure_rolls_back(self, agent):
        agent._fetch_api_docs = AsyncMock(side_effect=ValueError("bad url"))
        with pytest.raises(ValueError):
            await agent.create_skill_from_api_documentation(
                tenant_id="t1", agent_id="a1", user_id="u1",
                api_docs_url="http://localhost/x",
                api_description="d",
            )
        agent.db.rollback.assert_called_once()

    # -- create_canvas_component_for_skill -----------------------------------

    async def test_create_component_success(self, agent):
        skill = Mock()
        skill.id = "skill-1"
        skill.version = "1.0.0"
        skill.name = "acme-fetcher"
        skill.description = "desc"
        skill.tags = ["api"]
        agent.db.query.return_value.filter.return_value.first.return_value = skill
        agent._analyze_skill_for_component = AsyncMock(return_value={
            "category": "table",
            "config_schema": {"type": "object", "properties": {}},
        })
        agent._generate_component_code = AsyncMock(return_value="export const X = ...")
        component = Mock()
        component.id = "comp-1"
        with patch("core.agents.skill_creation_agent.CanvasComponent",
                   return_value=component) as cc:
            result = await agent.create_canvas_component_for_skill(
                tenant_id="t1", agent_id="a1", user_id="u1", skill_id="skill-1"
            )
        assert result is component
        agent.db.commit.assert_called_once()
        assert cc.call_args.kwargs["config_schema"]["required_skill_id"] == "skill-1"
        assert cc.call_args.kwargs["config_schema"]["required_skill_version"] == "1.0.0"

    async def test_create_component_skill_not_found(self, agent):
        agent.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await agent.create_canvas_component_for_skill(
                tenant_id="t1", agent_id="a1", user_id="u1", skill_id="nope"
            )

    async def test_create_component_failure_rolls_back(self, agent):
        skill = Mock()
        skill.id = "skill-1"
        skill.version = "1.0.0"
        skill.name = "n"
        skill.description = "d"
        skill.tags = []
        agent.db.query.return_value.filter.return_value.first.return_value = skill
        agent._analyze_skill_for_component = AsyncMock(
            side_effect=RuntimeError("analyze failed")
        )
        with pytest.raises(RuntimeError):
            await agent.create_canvas_component_for_skill(
                tenant_id="t1", agent_id="a1", user_id="u1", skill_id="skill-1"
            )
        agent.db.rollback.assert_called_once()

    # -- _fetch_api_docs / _validate_url --------------------------------------

    async def test_fetch_api_docs_success(self, agent):
        agent.client.get = AsyncMock(return_value=Mock(json=Mock(return_value={"ok": 1})))
        result = await agent._fetch_api_docs("https://api.example.com/openapi.json")
        assert result == {"ok": 1}

    async def test_fetch_api_docs_ssrf_blocked(self, agent):
        with pytest.raises(ValueError, match="Invalid URL"):
            await agent._fetch_api_docs("http://localhost/openapi.json")

    async def test_fetch_api_docs_request_failure(self, agent):
        agent.client.get = AsyncMock(side_effect=RuntimeError("network down"))
        with pytest.raises(ValueError, match="Failed to fetch API documentation"):
            await agent._fetch_api_docs("https://api.example.com/openapi.json")

    def test_validate_url_http_ok(self, agent):
        assert agent._validate_url("http://api.example.com/spec.json") is True
        assert agent._validate_url("https://api.example.com/spec.json") is True

    def test_validate_url_loopback_variants(self, agent):
        for host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "::"):
            assert agent._validate_url(f"http://{host}/x") is False

    def test_validate_url_private_ipv4(self, agent):
        for host in ("10.0.0.1", "172.16.0.1", "172.31.0.1", "192.168.1.1", "169.254.1.1"):
            assert agent._validate_url(f"https://{host}/x") is False
        assert agent._validate_url("https://172.32.0.1/x") is True
        assert agent._validate_url("https://11.0.0.1/x") is True

    def test_validate_url_private_ipv6(self, agent):
        assert agent._validate_url("https://[fd00::1]/x") is False
        assert agent._validate_url("https://[fe80::1]/x") is False

    def test_validate_url_invalid_ipv6(self, agent):
        assert agent._validate_url("https://[not-an-ip]/x") is False

    def test_validate_url_ipv6_ipaddress_value_error(self, agent):
        fake = SimpleNamespace(
            hostname="bad:host", netloc="[bad:host]", scheme="https"
        )
        with patch("urllib.parse.urlparse", return_value=fake):
            assert agent._validate_url("https://[bad:host]/x") is False

    def test_validate_url_bad_scheme(self, agent):
        assert agent._validate_url("ftp://api.example.com/x") is False
        assert agent._validate_url("javascript:alert(1)") is False

    def test_validate_url_parse_error(self, agent):
        assert agent._validate_url("https://[::1") is False

    def test_validate_url_no_hostname(self, agent):
        assert agent._validate_url("") is False

    # -- _analyze_api_spec -----------------------------------------------------

    async def test_analyze_api_spec_full(self, agent):
        docs = {
            "info": {"title": "Acme REST API", "version": "2.0"},
            "servers": [{"url": "https://api.acme.com/v2"}],
            "components": {"securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-Api-Key"},
                "HttpAuth": {"type": "http", "scheme": "bearer"},
            }},
            "paths": {
                "/things": {
                    "get": {
                        "parameters": [
                            {"name": "limit", "in": "query", "required": True,
                             "schema": {"type": "integer"},
                             "description": "page size"},
                        ],
                        "responses": {
                            "200": {"content": {
                                "application/json": {"schema": {"type": "array"}}
                            }},
                        },
                    }
                }
            },
        }
        result = await agent._analyze_api_spec(docs, "shopify ecommerce product orders")
        assert result["suggested_name"] == "acme-rest--fetcher"
        assert result["base_url"] == "https://api.acme.com/v2"
        assert result["auth_headers"] == {
            "X-Api-Key": "{{API_KEY}}",
            "Authorization": "Bearer {{API_KEY}}",
        }
        assert result["input_schema"]["required"] == ["limit"]
        assert result["output_schema"] == {"type": "array"}
        assert result["category"] == "ecommerce"
        assert result["endpoints"] == ["/things"]
        assert result["config"]["example_path"] == "/things"

    async def test_analyze_api_spec_minimal(self, agent):
        result = await agent._analyze_api_spec({"info": {}}, "nothing here")
        assert result["suggested_name"] == "-fetcher"
        assert result["base_url"] == ""
        assert result["auth_headers"] == {}
        assert result["input_schema"] == {}
        assert result["output_schema"] == {}
        assert result["category"] == "productivity"
        assert result["tags"] == []

    # -- _infer_category / _extract_tags ---------------------------------------

    async def test_infer_category_all(self, agent):
        cases = [
            ("salesforce crm leads contacts", "crm"),
            ("slack teams communication", "communication"),
            ("finance accounting invoice", "finance"),
            ("marketing campaign email", "marketing"),
            ("something totally different", "productivity"),
        ]
        for desc, expected in cases:
            assert agent._infer_category({}, desc) == expected

    async def test_extract_tags_combinations(self, agent):
        tags = agent._extract_tags({"title": "API"}, "rest json description")
        assert tags == ["api", "rest", "json"]
        assert agent._extract_tags({}, "") == []

    # -- _generate_skill_code ----------------------------------------------------

    async def test_generate_skill_code_success(self, agent):
        agent.llm.generate = AsyncMock(return_value="```python\nreal code\n```")
        code = await agent._generate_skill_code({"base_url": "u", "description": "d",
                                                 "input_schema": {}, "output_schema": {},
                                                 "auth_headers": {}})
        assert code == "real code"

    async def test_generate_skill_code_plain(self, agent):
        agent.llm.generate = AsyncMock(return_value="plain code")
        code = await agent._generate_skill_code({"base_url": "u", "description": "d",
                                                 "input_schema": {}, "output_schema": {},
                                                 "auth_headers": {}})
        assert code == "plain code"

    async def test_generate_skill_code_failure_fallback_bearer(self, agent):
        agent.llm.generate = AsyncMock(side_effect=RuntimeError("down"))
        code = await agent._generate_skill_code({
            "base_url": "https://api.acme.com",
            "description": "Acme API",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "auth_headers": {"Authorization": "Bearer {{API_KEY}}"},
        })
        assert "Bearer" in code
        assert "https://api.acme.com" in code

    # -- _generate_fallback_code --------------------------------------------------

    async def test_fallback_code_api_key_header(self, agent):
        code = agent._generate_fallback_code({
            "base_url": "https://api.acme.com",
            "description": "Acme API",
            "auth_headers": {"X-Api-Key": "{{API_KEY}}"},
        })
        assert "API Key" in code
        assert "X-Api-Key" in code

    async def test_fallback_code_api_key_value(self, agent):
        code = agent._generate_fallback_code({
            "base_url": "https://api.acme.com",
            "description": "Acme API",
            "auth_headers": {"custom": "API_KEY placeholder"},
        })
        assert "API Key" in code
        assert "custom" in code

    async def test_fallback_code_public(self, agent):
        code = agent._generate_fallback_code({
            "base_url": "https://api.acme.com",
            "description": "Public API",
            "auth_headers": {},
        })
        assert "Public API" in code
        assert "Authentication: None" in code

    # -- _analyze_skill_for_component ---------------------------------------------

    async def test_component_categories(self, agent):
        skill = Mock()
        for ctype, expected in (("table", "table"), ("chart", "chart"),
                                ("form", "form"), ("widget", "widget")):
            config = await agent._analyze_skill_for_component(skill, ctype)
            assert config["category"] == expected
            assert "skillId" in config["config_schema"]["properties"]
            assert config["dependencies"] == ["recharts", "lucide-react"]

    # -- _generate_component_code ---------------------------------------------------

    async def test_generate_component_code_typescript_fence(self, agent):
        skill = Mock(name="x", output_schema={}, description="d")
        agent.llm.generate = AsyncMock(return_value="```typescript\nconst a = 1;\n```")
        code = await agent._generate_component_code(skill, {"category": "widget"})
        assert code == "const a = 1;"

    async def test_generate_component_code_tsx_fence(self, agent):
        skill = Mock(name="x", output_schema={}, description="d")
        agent.llm.generate = AsyncMock(return_value="```tsx\nexport const B = 2;\n```")
        code = await agent._generate_component_code(skill, {"category": "widget"})
        assert code == "export const B = 2;"

    async def test_generate_component_code_failure_template(self, agent):
        skill = Mock()
        skill.name = "my-skill"
        skill.output_schema = {}
        skill.description = "d"
        agent.llm.generate = AsyncMock(side_effect=RuntimeError("down"))
        code = await agent._generate_component_code(skill, {"category": "widget"})
        assert "myskillComponent" in code
        assert "my-skill" in code

    # -- generate_skill_metadata -----------------------------------------------------

    def test_generate_skill_metadata_with_deps(self, agent):
        agent.openclaw_parser.extract_npm_dependencies = Mock(return_value=["recharts"])
        md = agent.generate_skill_metadata(
            {
                "code": "import recharts",
                "name": "comp",
                "description": "A component",
                "version": "2.0.0",
                "category": "widget",
                "component_type": "React",
                "python_dependencies": ["httpx"],
                "config_schema": {"type": "object", "properties": {}},
                "dependencies": ["recharts", "lucide-react"],
            },
            "skill-1", "t1",
        )
        assert "name: comp" in md
        assert "      - id: recharts" in md
        assert "kind: npm" in md
        assert "lucide-react" in md
        assert "**httpx**" in md
        assert "No configuration required." in md

    def test_generate_skill_metadata_no_deps(self, agent):
        md = agent.generate_skill_metadata({"name": "comp2"}, "skill-2", "t1")
        assert "      []" in md
        assert "## Python Packages\n\nNone\n" in md
        assert "### NPM Packages\n\nNone\n" in md
        assert "No configuration required." in md

    # -- formatters -------------------------------------------------------------------

    def test_format_npm_dependencies(self, agent):
        assert agent._format_npm_dependencies([]) == "None"
        assert agent._format_npm_dependencies(["a", "b"]) == "- **a**\n- **b**"

    def test_format_python_dependencies(self, agent):
        assert agent._format_python_dependencies([]) == "None"
        assert agent._format_python_dependencies(["requests"]) == "- **requests**"

    def test_format_config_schema(self, agent):
        assert agent._format_config_schema({}) == "No configuration required."
        assert agent._format_config_schema({"properties": None}) == \
            "No configuration required."
        out = agent._format_config_schema({
            "properties": {
                "title": {"type": "string", "description": "The title"},
                "count": {"type": "number", "description": "How many"},
            },
            "required": ["title"],
        })
        assert "**title** (string) *(required)*: The title" in out
        assert "**count** (number): How many" in out
