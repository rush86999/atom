"""Coverage push for auto_dev modules + communication adapters + lancedb_handler.

Targets >=95% line coverage per module. All external I/O (Docker, HTTP,
LLM, LanceDB, DB) is mocked — no real network or containers.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pandas as pd
import pytest

from core.auto_dev.event_hooks import (
    SkillExecutionEvent,
    TaskEvent,
    event_bus,
)
from core.auto_dev.evolution_pipeline import MutationRequest
from core.auto_dev.regression_validator import RegressionResult
from core.lancedb_handler import LanceDBHandler


@pytest.fixture(autouse=True)
def _clean_event_bus():
    event_bus.clear()
    yield
    event_bus.clear()


@pytest.fixture(autouse=True)
def _no_llm_service():
    with patch("core.lancedb_handler.LLMService", None):
        yield


# ===========================================================================
# base_engine
# ===========================================================================

class TestBaseEngineCoverage:
    def _engine(self, db=None, llm=None, sandbox=None):
        from core.auto_dev.base_engine import BaseLearningEngine

        class _Concrete(BaseLearningEngine):
            async def analyze_episode(self, episode_id, **kwargs):
                return {}

            async def propose_code_change(self, context, **kwargs):
                return "code"

            async def validate_change(self, code, test_inputs, tenant_id, **kwargs):
                return {"passed": True}

        return _Concrete(db=db or Mock(), llm_service=llm, sandbox=sandbox)

    def test_get_llm_service_injected(self):
        eng = self._engine(llm=Mock())
        assert eng._get_llm_service() is eng.llm

    def test_get_llm_service_fallback(self):
        eng = self._engine()
        fake = Mock()
        with patch("core.llm_service.get_llm_service", return_value=fake):
            assert eng._get_llm_service() is fake
        assert eng.llm is fake

    def test_get_llm_service_unavailable(self):
        eng = self._engine()
        with patch.dict(sys.modules, {"core.llm_service": None}):
            assert eng._get_llm_service() is None
        assert eng.llm is None

    def test_get_sandbox_injected(self):
        eng = self._engine(sandbox=Mock())
        assert eng._get_sandbox() is eng.sandbox

    def test_get_sandbox_fallback(self):
        eng = self._engine()
        fake = Mock()
        with patch("core.auto_dev.container_sandbox.ContainerSandbox", return_value=fake):
            assert eng._get_sandbox() is fake
        assert eng.sandbox is fake

    def test_get_sandbox_unavailable(self):
        eng = self._engine()
        with patch.dict(sys.modules, {"core.auto_dev.container_sandbox": None}):
            assert eng._get_sandbox() is None

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("```python\nprint(1)\n```", "print(1)"),
            ("```\nprint(1)\n```", "print(1)"),
            ("print(1)", "print(1)"),
            ("  ```python\nx = 1\n```  ", "x = 1"),
        ],
    )
    def test_strip_markdown_fences(self, raw, expected):
        assert self._engine()._strip_markdown_fences(raw) == expected

    def test_sandbox_protocol_runtime_check(self):
        from core.auto_dev.base_engine import SandboxProtocol

        class Impl:
            async def execute_raw_python(self, **kwargs):
                return {"status": "success"}

        assert isinstance(Impl(), SandboxProtocol)

        class NoImpl:
            pass

        assert not isinstance(NoImpl(), SandboxProtocol)


# ===========================================================================
# container_sandbox
# ===========================================================================

class TestContainerSandboxCoverage:
    def _sb(self, **kwargs):
        from core.auto_dev.container_sandbox import ContainerSandbox
        return ContainerSandbox(**kwargs)

    def test_docker_available_cache(self):
        sb = self._sb()
        with patch("subprocess.run", return_value=Mock(returncode=0)) as run:
            assert sb.docker_available is True
            assert sb.docker_available is True
            assert run.call_count == 1

    def test_docker_unavailable_errors(self):
        sb = self._sb()
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert sb.docker_available is False
        sb2 = self._sb()
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)):
            assert sb2.docker_available is False

    def test_docker_available_nonzero(self):
        sb = self._sb()
        with patch("subprocess.run", return_value=Mock(returncode=1)):
            assert sb.docker_available is False

    @pytest.mark.asyncio
    async def test_docker_success_path(self):
        sb = self._sb()
        sb._docker_available = True
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"hello world", b""))
        proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=proc), patch(
            "tempfile.NamedTemporaryFile"
        ) as tmp, patch("core.auto_dev.container_sandbox.Path.unlink"):
            tmp.return_value.__enter__.return_value.name = "/tmp/x.py"
            result = await sb.execute_raw_python("t1", "print(1)", {"a": 1}, timeout=10)
        assert result["status"] == "success"
        assert result["output"] == "hello world"
        assert result["environment"] == "docker"

    @pytest.mark.asyncio
    async def test_docker_failure_path(self):
        sb = self._sb()
        sb._docker_available = True
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b"boom"))
        proc.returncode = 1
        with patch("asyncio.create_subprocess_exec", return_value=proc), patch(
            "tempfile.NamedTemporaryFile"
        ) as tmp, patch("core.auto_dev.container_sandbox.Path.unlink"):
            tmp.return_value.__enter__.return_value.name = "/tmp/x.py"
            result = await sb.execute_raw_python("t1", "bad", {}, timeout=10)
        assert result["status"] == "failed"
        assert result["output"] == "boom"

    @pytest.mark.asyncio
    async def test_docker_network_enabled_flag(self):
        sb = self._sb(enable_network=True)
        sb._docker_available = True
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b""))
        proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=proc) as exec_, patch(
            "tempfile.NamedTemporaryFile"
        ) as tmp, patch("core.auto_dev.container_sandbox.Path.unlink"):
            tmp.return_value.__enter__.return_value.name = "/tmp/x.py"
            await sb.execute_raw_python("t1", "print(1)", {}, timeout=10)
        cmd = exec_.call_args.args
        assert "--network" not in cmd

    @pytest.mark.asyncio
    async def test_subprocess_success(self):
        sb = self._sb()
        sb._docker_available = False
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"out", b""))
        proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=proc) as exec_, patch(
            "tempfile.NamedTemporaryFile"
        ) as tmp, patch("core.auto_dev.container_sandbox.Path.unlink"):
            tmp.return_value.__enter__.return_value.name = "/tmp/x.py"
            result = await sb.execute_raw_python("t1", "print(1)", {}, timeout=10)
        assert result["status"] == "success"
        assert result["environment"] == "subprocess"
        assert exec_.call_args.kwargs.get("preexec_fn") is not None

    @pytest.mark.asyncio
    async def test_subprocess_failure(self):
        sb = self._sb()
        sb._docker_available = False
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b"traceback"))
        proc.returncode = 2
        with patch("asyncio.create_subprocess_exec", return_value=proc), patch(
            "tempfile.NamedTemporaryFile"
        ) as tmp, patch("core.auto_dev.container_sandbox.Path.unlink"):
            tmp.return_value.__enter__.return_value.name = "/tmp/x.py"
            result = await sb.execute_raw_python("t1", "bad", {}, timeout=10)
        assert result["status"] == "failed"
        assert result["output"] == "traceback"

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self):
        sb = self._sb(timeout=1)
        sb._docker_available = False
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        proc.kill = Mock()
        proc.wait = AsyncMock()
        with patch("asyncio.create_subprocess_exec", return_value=proc), patch(
            "tempfile.NamedTemporaryFile"
        ) as tmp, patch("core.auto_dev.container_sandbox.Path.unlink"):
            tmp.return_value.__enter__.return_value.name = "/tmp/x.py"
            result = await sb.execute_raw_python("t1", "loop", {}, timeout=1)
        assert result["status"] == "failed"
        assert "timed out" in result["output"]
        assert result["environment"] == "subprocess"
        proc.kill.assert_called_once()

    def test_execution_wrapper_uses_base64(self):
        sb = self._sb()
        wrapper = sb._build_execution_wrapper("print(1)", {"evil": "'''\n__import__('os').system('x')"})
        assert "base64" in wrapper
        assert "'''" not in wrapper.split("_INPUT_PARAMS")[0]
        import base64
        import json
        b64 = wrapper.split("b64decode('")[1].split("').decode")[0]
        assert json.loads(base64.b64decode(b64)) == {"evil": "'''\n__import__('os').system('x')"}

    def test_resource_limit_preexec_windows(self):
        sb = self._sb()
        with patch("sys.platform", "win32"):
            assert sb._resource_limit_preexec() is None
        fn = sb._resource_limit_preexec()
        assert callable(fn)
        fn()  # must not raise


# ===========================================================================
# event_hooks
# ===========================================================================

class TestEventHooksCoverage:
    @pytest.mark.asyncio
    async def test_decorator_registration_and_emission(self):
        calls = []

        @event_bus.on_task_fail
        async def fail_handler(event):
            calls.append(("fail", event.episode_id))

        @event_bus.on_task_success
        async def success_handler(event):
            calls.append(("success", event.episode_id))

        @event_bus.on_skill_execution
        async def skill_handler(event):
            calls.append(("skill", event.skill_id))

        await event_bus.emit_task_fail(TaskEvent(episode_id="e1", agent_id="a", tenant_id="t"))
        await event_bus.emit_task_success(TaskEvent(episode_id="e2", agent_id="a", tenant_id="t"))
        await event_bus.emit_skill_execution(
            SkillExecutionEvent(execution_id="x", agent_id="a", tenant_id="t", skill_id="s1")
        )
        assert calls == [("fail", "e1"), ("success", "e2"), ("skill", "s1")]

    @pytest.mark.asyncio
    async def test_handler_exception_swallowed(self):
        @event_bus.on_task_fail
        async def bad(event):
            raise RuntimeError("handler exploded")

        await event_bus.emit_task_fail(TaskEvent(episode_id="e1", agent_id="a", tenant_id="t"))

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self):
        await event_bus.emit_task_fail(TaskEvent(episode_id="e1", agent_id="a", tenant_id="t"))

    def test_clear(self):
        @event_bus.on_task_fail
        async def h(event):
            pass

        assert len(event_bus._fail_handlers) == 1
        event_bus.clear()
        assert event_bus._fail_handlers == []
        assert event_bus._success_handlers == []
        assert event_bus._skill_handlers == []


# ===========================================================================
# evolution_engine
# ===========================================================================

class TestEvolutionEngineCoverage:
    @pytest.mark.asyncio
    async def test_register(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        with patch.object(event_bus, "on_skill_execution") as register:
            EvolutionEngine(Mock()).register()
        register.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_execution_gate_denied(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        with patch.object(eng, "_should_optimize", return_value=False) as should:
            await eng.process_execution(
                SkillExecutionEvent(execution_id="x", agent_id="a", tenant_id="t", skill_id="s")
            )
        should.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_execution_no_trigger(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        event = SkillExecutionEvent(
            execution_id="x", agent_id="a", tenant_id="t", skill_id="s",
            execution_seconds=1.0, token_usage=10, success=True,
        )
        with patch.object(eng, "_should_optimize", return_value=True), patch.object(
            eng, "_trigger_alpha_evolver"
        ) as trigger:
            await eng.process_execution(event)
        trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_execution_triggers_on_latency(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        event = SkillExecutionEvent(
            execution_id="x", agent_id="a", tenant_id="t", skill_id="s",
            skill_name="my_skill", execution_seconds=9.0, token_usage=99999, success=False,
        )
        with patch.object(eng, "_should_optimize", return_value=True), patch.object(
            eng, "_trigger_alpha_evolver"
        ) as trigger:
            await eng.process_execution(event)
        trigger.assert_awaited_once()
        reason = trigger.await_args.args[1]
        assert "high_latency" in reason
        assert "high_token_usage" in reason
        assert "execution_failure" in reason

    @pytest.mark.asyncio
    async def test_trigger_alpha_evolver_success_path(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        engine = Mock()
        mutation = Mock()
        mutation.id = "mut_1"
        engine.generate_tool_mutation = AsyncMock(return_value=mutation)
        engine.sandbox_execute_mutation = AsyncMock(return_value={"success": True})
        session = Mock()
        with patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=engine
        ), patch("core.database.SessionLocal", return_value=session), patch.object(
            eng, "_get_skill_code", return_value="def f(): pass"
        ):
            await eng._trigger_alpha_evolver(
                SkillExecutionEvent(
                    execution_id="x", agent_id="a", tenant_id="t", skill_id="s", skill_name="s"
                ),
                "high_latency",
            )
        session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_alpha_evolver_failed_sandbox(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        engine = Mock()
        mutation = Mock()
        mutation.id = "mut_2"
        engine.generate_tool_mutation = AsyncMock(return_value=mutation)
        engine.sandbox_execute_mutation = AsyncMock(return_value={"success": False})
        session = Mock()
        with patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=engine
        ), patch("core.database.SessionLocal", return_value=session), patch.object(
            eng, "_get_skill_code", return_value="def f(): pass"
        ):
            await eng._trigger_alpha_evolver(
                SkillExecutionEvent(
                    execution_id="x", agent_id="a", tenant_id="t", skill_id="s"
                ),
                "execution_failure",
            )
        session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_alpha_evolver_no_skill_code(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        engine = Mock()
        session = Mock()
        with patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=engine
        ), patch("core.database.SessionLocal", return_value=session), patch.object(
            eng, "_get_skill_code", return_value=None
        ):
            await eng._trigger_alpha_evolver(
                SkillExecutionEvent(
                    execution_id="x", agent_id="a", tenant_id="t", skill_id="s"
                ),
                "high_latency",
            )
        engine.generate_tool_mutation.assert_not_called()
        session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_alpha_evolver_exception(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        with patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine",
            side_effect=RuntimeError("import failed"),
        ):
            await eng._trigger_alpha_evolver(
                SkillExecutionEvent(
                    execution_id="x", agent_id="a", tenant_id="t", skill_id="s"
                ),
                "high_latency",
            )

    def test_should_optimize_gate(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        gate = Mock()
        gate.can_use = Mock(return_value=True)
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ), patch.object(eng, "_get_workspace_settings", return_value={"auto_dev": {"enabled": True}}):
            assert eng._should_optimize("a1", "t1") is True
        gate.can_use.assert_called_once_with(
            agent_id="a1",
            capability="auto_dev.background_evolution",
            workspace_settings={"auto_dev": {"enabled": True}},
        )

    def test_should_optimize_exception_false(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        eng = EvolutionEngine(Mock())
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            side_effect=ImportError("no gate"),
        ):
            assert eng._should_optimize("a1", "t1") is False

    def test_get_skill_code_found(self, tmp_path):
        from core.auto_dev.evolution_engine import EvolutionEngine
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "main.py").write_text("print('hi')")
        builder = Mock()
        builder._get_tenant_skills_dir = Mock(return_value=tmp_path / "skills")
        with patch("core.skill_builder_service.SkillBuilderService", return_value=builder):
            code = EvolutionEngine(Mock())._get_skill_code("my-skill", "t1")
        assert code == "print('hi')"

    def test_get_skill_code_not_found(self, tmp_path):
        from core.auto_dev.evolution_engine import EvolutionEngine
        (tmp_path / "skills").mkdir(parents=True)
        builder = Mock()
        builder._get_tenant_skills_dir = Mock(return_value=tmp_path / "skills")
        with patch("core.skill_builder_service.SkillBuilderService", return_value=builder):
            assert EvolutionEngine(Mock())._get_skill_code("missing", "t1") is None

    def test_get_skill_code_exception(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        with patch("core.skill_builder_service.SkillBuilderService", side_effect=RuntimeError):
            assert EvolutionEngine(Mock())._get_skill_code("s", "t") is None

    def test_get_workspace_settings(self):
        from core.auto_dev.evolution_engine import EvolutionEngine
        db = Mock()
        ws = Mock()
        ws.metadata_json = {"auto_dev": {"enabled": True}}
        db.query.return_value.filter.return_value.first.return_value = ws
        assert EvolutionEngine(db)._get_workspace_settings("t1") == {"auto_dev": {"enabled": True}}

        db2 = Mock()
        ws2 = Mock()
        ws2.metadata_json = None
        db2.query.return_value.filter.return_value.first.return_value = ws2
        assert EvolutionEngine(db2)._get_workspace_settings("t1") == {}

        db3 = Mock()
        db3.query.side_effect = RuntimeError("db down")
        assert EvolutionEngine(db3)._get_workspace_settings("t1") == {}


# ===========================================================================
# evolution_pipeline
# ===========================================================================

class TestEvolutionPipelineCoverage:
    def _req(self, **overrides):
        kwargs = dict(
            agent_id="ag-1",
            tenant_id="t-1",
            source="gea",
            config_key="system_prompt",
            old_value="old",
            new_value="new",
        )
        kwargs.update(overrides)
        return MutationRequest(**kwargs)

    @pytest.mark.asyncio
    async def test_governance_rejects(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        gov = Mock()
        gov.validate_evolution_directive = AsyncMock(return_value=False)
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            result = await UnifiedEvolutionPipeline(Mock()).submit_and_deploy(self._req())
        assert result.passed is False
        assert result.stage == "governance"

    @pytest.mark.asyncio
    async def test_governance_exception_blocks(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        with patch(
            "core.agent_governance_service.AgentGovernanceService",
            side_effect=RuntimeError("gov down"),
        ):
            result = await UnifiedEvolutionPipeline(Mock()).submit_and_deploy(self._req())
        assert result.passed is False
        assert result.stage == "governance"

    @pytest.mark.asyncio
    async def test_daily_limit_exception_blocks(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        gov = Mock()
        gov.validate_evolution_directive = AsyncMock(return_value=True)
        gate = Mock()
        gate.check_daily_limits = Mock(side_effect=RuntimeError("count failed"))
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ):
            result = await UnifiedEvolutionPipeline(Mock()).submit_and_deploy(self._req())
        assert result.passed is False
        assert result.stage == "daily_limit"

    @pytest.mark.asyncio
    async def test_happy_path_no_code_snapshot(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        gov = Mock()
        gov.validate_evolution_directive = AsyncMock(return_value=True)
        gate = Mock()
        gate.check_daily_limits = Mock(return_value=True)
        registry = Mock()
        registry.snapshot = Mock(return_value="mut_abc")
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ), patch("core.auto_dev.mutation_rollback.get_rollback_registry", return_value=registry):
            result = await UnifiedEvolutionPipeline(Mock()).submit_and_deploy(self._req())
        assert result.passed is True
        assert result.stage == "validated"
        assert result.rollback_mutation_id == "mut_abc"
        registry.snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_snapshot_exception_best_effort(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        gov = Mock()
        gov.validate_evolution_directive = AsyncMock(return_value=True)
        gate = Mock()
        gate.check_daily_limits = Mock(return_value=True)
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ), patch(
            "core.auto_dev.mutation_rollback.get_rollback_registry",
            side_effect=RuntimeError("registry down"),
        ):
            result = await UnifiedEvolutionPipeline(Mock()).submit_and_deploy(self._req())
        assert result.passed is True
        assert result.rollback_mutation_id is None

    @pytest.mark.asyncio
    async def test_regression_exception_blocks(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        gov = Mock()
        gov.validate_evolution_directive = AsyncMock(return_value=True)
        gate = Mock()
        gate.check_daily_limits = Mock(return_value=True)
        validator = Mock()
        validator.validate_regression = AsyncMock(side_effect=RuntimeError("sandbox down"))
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ), patch(
            "core.auto_dev.regression_validator.RegressionValidator", return_value=validator
        ):
            req = self._req(
                parent_code="def f(x): return x",
                mutated_code="def f(x): return x",
                test_inputs=[{"x": 1}],
            )
            result = await UnifiedEvolutionPipeline(Mock()).submit_and_deploy(req)
        assert result.passed is False
        assert result.stage == "regression"

    @pytest.mark.asyncio
    async def test_regression_uses_injected_sandbox(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        gov = Mock()
        gov.validate_evolution_directive = AsyncMock(return_value=True)
        gate = Mock()
        gate.check_daily_limits = Mock(return_value=True)
        sandbox = Mock()
        validator = Mock()
        validator.validate_regression = AsyncMock(return_value=RegressionResult(passed=True))
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ), patch(
            "core.auto_dev.regression_validator.RegressionValidator", return_value=validator
        ):
            req = self._req(
                parent_code="def f(x): return x",
                mutated_code="def f(x): return x",
                test_inputs=[{"x": 1}],
            )
            result = await UnifiedEvolutionPipeline(Mock(), sandbox=sandbox).submit_and_deploy(req)
        assert result.passed is True
        validator.validate_regression.assert_awaited_once_with(
            parent_code="def f(x): return x",
            mutated_code="def f(x): return x",
            test_inputs=[{"x": 1}],
            sandbox=sandbox,
            tenant_id="t-1",
        )

    @pytest.mark.asyncio
    async def test_rollback_and_verify(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        registry = Mock()
        registry.rollback = Mock(return_value=True)
        registry.verify = Mock(return_value=True)
        pipeline = UnifiedEvolutionPipeline(Mock())
        with patch("core.auto_dev.mutation_rollback.get_rollback_registry", return_value=registry):
            assert await pipeline.rollback("m1") is True
            registry.rollback.assert_called_once_with("m1", None)
            assert await pipeline.verify("m1") is True

    @pytest.mark.asyncio
    async def test_rollback_and_verify_exception(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        pipeline = UnifiedEvolutionPipeline(Mock())
        with patch(
            "core.auto_dev.mutation_rollback.get_rollback_registry",
            side_effect=RuntimeError("down"),
        ):
            assert await pipeline.rollback("m1") is False
            assert await pipeline.verify("m1") is False

    def test_workspace_settings_helper(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        db = Mock()
        ws = Mock()
        ws.metadata_json = {"auto_dev": {"max_mutations_per_day": 3}}
        db.query.return_value.filter.return_value.first.return_value = ws
        assert UnifiedEvolutionPipeline(db)._get_workspace_settings("t1") == {
            "auto_dev": {"max_mutations_per_day": 3}
        }
        db2 = Mock()
        db2.query.side_effect = RuntimeError("db down")
        assert UnifiedEvolutionPipeline(db2)._get_workspace_settings("t1") == {}


# ===========================================================================
# mutation_rollback
# ===========================================================================

class TestMutationRollbackCoverage:
    def _registry(self, max_snapshots=10):
        from core.auto_dev.mutation_rollback import MutationRollbackRegistry
        return MutationRollbackRegistry(max_snapshots=max_snapshots)

    def test_snapshot_and_rollback(self):
        reg = self._registry()
        mid = reg.snapshot("ag-1", "system_prompt", "old", "new", source="gea")
        assert mid.startswith("mut_")
        assert reg.rollback(mid) is True
        cfg = {}
        assert reg.rollback(mid, cfg) is True
        assert cfg["system_prompt"] == "old"

    def test_rollback_unknown(self):
        reg = self._registry()
        assert reg.rollback("mut_nope") is False

    def test_rollback_agent(self):
        reg = self._registry()
        m1 = reg.snapshot("ag-1", "key1", "old1", "new1")
        m2 = reg.snapshot("ag-1", "key2", "old2", "new2")
        m3 = reg.snapshot("ag-2", "key3", "old3", "new3")
        reg.verify(m1)
        cfg = {}
        assert reg.rollback_agent("ag-1", cfg) == 1  # only m2 (m1 verified)
        assert cfg == {"key2": "old2"}
        assert reg.rollback_agent("ag-2") == 1
        assert reg.rollback_agent("ag-none") == 0

    def test_verify_unknown(self):
        reg = self._registry()
        assert reg.verify("mut_nope") is False

    def test_get_snapshot_and_agent_mutations(self):
        reg = self._registry()
        m1 = reg.snapshot("ag-1", "key1", "old1", "new1")
        snap = reg.get_snapshot(m1)
        assert snap.agent_id == "ag-1"
        assert snap.old_value == "old1"
        assert snap.new_value == "new1"
        assert snap.source == "unknown"
        assert len(reg.get_agent_mutations("ag-1")) == 1
        assert reg.get_agent_mutations("ag-x") == []
        assert reg.get_snapshot("nope") is None

    def test_lru_eviction(self):
        reg = self._registry(max_snapshots=2)
        m1 = reg.snapshot("ag-1", "k1", "o1", "n1")
        m2 = reg.snapshot("ag-1", "k2", "o2", "n2")
        m3 = reg.snapshot("ag-1", "k3", "o3", "n3")
        assert reg.get_snapshot(m1) is None
        assert reg.get_snapshot(m2) is not None
        assert reg.get_snapshot(m3) is not None

    def test_clear_and_singleton(self):
        from core.auto_dev.mutation_rollback import get_rollback_registry
        reg = self._registry()
        reg.snapshot("ag-1", "k1", "o1", "n1")
        reg.clear()
        assert reg.get_agent_mutations("ag-1") == []
        assert get_rollback_registry() is get_rollback_registry()


# ===========================================================================
# reflection_engine
# ===========================================================================

class TestReflectionEngineCoverage:
    @pytest.mark.asyncio
    async def test_register(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        with patch.object(event_bus, "on_task_fail") as register:
            ReflectionEngine(Mock()).register()
        register.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_failure_gate_denied(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        with patch.object(eng, "_should_process_agent", return_value=False):
            await eng.process_failure(
                TaskEvent(episode_id="e1", agent_id="a1", tenant_id="t1", task_description="parse json")
            )
        assert eng._failure_buffer["a1"] == []

    @pytest.mark.asyncio
    async def test_process_failure_below_threshold(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock(), failure_threshold=3)
        with patch.object(eng, "_should_process_agent", return_value=True), patch.object(
            eng, "_trigger_memento"
        ) as trigger:
            await eng.process_failure(
                TaskEvent(episode_id="e1", agent_id="a1", tenant_id="t1", task_description="parse json file")
            )
            await eng.process_failure(
                TaskEvent(episode_id="e2", agent_id="a1", tenant_id="t1", task_description="parse json file")
            )
        trigger.assert_not_called()
        assert len(eng._failure_buffer["a1"]) == 2

    @pytest.mark.asyncio
    async def test_process_failure_triggers_memento_and_clears(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock(), failure_threshold=2)
        with patch.object(eng, "_should_process_agent", return_value=True), patch.object(
            eng, "_trigger_memento"
        ) as trigger:
            await eng.process_failure(
                TaskEvent(episode_id="e1", agent_id="a1", tenant_id="t1", task_description="parse json file")
            )
            await eng.process_failure(
                TaskEvent(episode_id="e2", agent_id="a1", tenant_id="t1", task_description="parse json file")
            )
        trigger.assert_awaited_once()
        assert eng._failure_buffer["a1"] == []  # cleared after trigger

    @pytest.mark.asyncio
    async def test_trigger_memento_success(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        engine = Mock()
        candidate = Mock()
        candidate.skill_name = "json-parser"
        engine.generate_skill_candidate = AsyncMock(return_value=candidate)
        with patch("core.auto_dev.memento_engine.MementoEngine", return_value=engine):
            await eng._trigger_memento("a1", "t1", "e1", [{"episode_id": "e1"}])
        engine.generate_skill_candidate.assert_awaited_once_with(
            tenant_id="t1", agent_id="a1", episode_id="e1"
        )

    @pytest.mark.asyncio
    async def test_trigger_memento_error(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        engine = Mock()
        engine.generate_skill_candidate = AsyncMock(side_effect=RuntimeError("llm down"))
        with patch("core.auto_dev.memento_engine.MementoEngine", return_value=engine):
            await eng._trigger_memento("a1", "t1", "e1", [])

    def test_should_process_agent(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        gate = Mock()
        gate.can_use = Mock(return_value=True)
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
        ), patch.object(eng, "_get_workspace_settings", return_value={}):
            assert eng._should_process_agent("a1", "t1") is True
        gate.can_use.assert_called_once_with(
            agent_id="a1",
            capability="auto_dev.memento_skills",
            workspace_settings={},
        )

    def test_should_process_agent_exception(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            side_effect=ImportError("no gate"),
        ):
            assert eng._should_process_agent("a1", "t1") is False

    def test_get_workspace_settings(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        db = Mock()
        ws = Mock()
        ws.metadata_json = {"auto_dev": {"enabled": True}}
        db.query.return_value.filter.return_value.first.return_value = ws
        assert ReflectionEngine(db)._get_workspace_settings("t1") == {"auto_dev": {"enabled": True}}
        db2 = Mock()
        db2.query.side_effect = RuntimeError("db down")
        assert ReflectionEngine(db2)._get_workspace_settings("t1") == {}

    def test_find_similar_failures(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        eng._failure_buffer["a1"] = [
            {"episode_id": "e1", "task_description": "parse json file"},
            {"episode_id": "e2", "task_description": "parse xml file"},
            {"episode_id": "e3", "task_description": "send email report"},
        ]
        similar = eng._find_similar_failures("a1", "parse json file")
        assert {f["episode_id"] for f in similar} == {"e1", "e2"}
        assert eng._find_similar_failures("a1", "completely unrelated task here") == []
        assert eng._find_similar_failures("a1", "") == []
        assert eng._find_similar_failures("no-agent", "parse json file") == []

    def test_clear_pattern(self):
        from core.auto_dev.reflection_engine import ReflectionEngine
        eng = ReflectionEngine(Mock())
        eng._failure_buffer["a1"] = [
            {"episode_id": "e1", "task_description": "a"},
            {"episode_id": "e2", "task_description": "b"},
        ]
        eng._clear_pattern("a1", [{"episode_id": "e1"}])
        assert [f["episode_id"] for f in eng._failure_buffer["a1"]] == ["e2"]


# ===========================================================================
# regression_validator
# ===========================================================================

class TestRegressionValidatorCoverage:
    def _sandbox(self, outputs):
        sb = Mock()

        async def execute_raw_python(tenant_id, code, input_params, **kwargs):
            key = (code, tuple(sorted((input_params or {}).items())))
            return outputs[key]

        sb.execute_raw_python = Mock(side_effect=execute_raw_python)
        return sb

    @pytest.mark.asyncio
    async def test_no_test_inputs(self):
        from core.auto_dev.regression_validator import RegressionValidator
        result = await RegressionValidator().validate_regression("p", "c", [], Mock(), "t1")
        assert result.passed is True
        assert result.total_tests == 0

    @pytest.mark.asyncio
    async def test_matching_outputs(self):
        from core.auto_dev.regression_validator import RegressionValidator
        sb = self._sandbox({
            ("parent", (("x", 1),)): {"status": "success", "output": "2"},
            ("child", (("x", 1),)): {"status": "success", "output": "2"},
        })
        result = await RegressionValidator().validate_regression(
            "parent", "child", [{"x": 1}], sb, "t1"
        )
        assert result.passed is True
        assert result.passed_tests == 1
        assert not result.regression_detected

    @pytest.mark.asyncio
    async def test_mismatched_outputs(self):
        from core.auto_dev.regression_validator import RegressionValidator
        sb = self._sandbox({
            ("parent", (("x", 1),)): {"status": "success", "output": "2"},
            ("child", (("x", 1),)): {"status": "success", "output": "3"},
        })
        result = await RegressionValidator().validate_regression(
            "parent", "child", [{"x": 1}], sb, "t1"
        )
        assert result.passed is False
        assert result.regression_detected
        assert len(result.mismatches) == 1
        d = result.to_dict()
        assert d["mismatch_count"] == 1
        assert d["mismatches"][0]["parent_output"] == "2"

    @pytest.mark.asyncio
    async def test_child_crash(self):
        from core.auto_dev.regression_validator import RegressionValidator
        sb = self._sandbox({
            ("parent", (("x", 1),)): {"status": "success", "output": "2"},
            ("child", (("x", 1),)): {"status": "failed", "output": "SyntaxError"},
        })
        result = await RegressionValidator().validate_regression(
            "parent", "child", [{"x": 1}], sb, "t1"
        )
        assert result.passed is False
        assert "[CRASH]" in result.mismatches[0].child_output

    @pytest.mark.asyncio
    async def test_parent_crash_child_ok_is_improvement(self):
        from core.auto_dev.regression_validator import RegressionValidator
        sb = self._sandbox({
            ("parent", (("x", 1),)): {"status": "failed", "output": "boom"},
            ("child", (("x", 1),)): {"status": "success", "output": "2"},
        })
        result = await RegressionValidator().validate_regression(
            "parent", "child", [{"x": 1}], sb, "t1"
        )
        assert result.passed is True
        assert result.passed_tests == 1

    @pytest.mark.asyncio
    async def test_sandbox_exception(self):
        from core.auto_dev.regression_validator import RegressionValidator
        sb = Mock()
        sb.execute_raw_python = Mock(side_effect=RuntimeError("sandbox exploded"))
        result = await RegressionValidator().validate_regression(
            "p", "c", [{"x": 1}], sb, "t1"
        )
        assert result.passed is False
        assert result.mismatches[0].child_output.startswith("[CRASH]")

    @pytest.mark.asyncio
    async def test_fuzzy_match(self):
        from core.auto_dev.regression_validator import RegressionValidator
        sb = self._sandbox({
            ("parent", (("x", 1),)): {"status": "success", "output": "hello world"},
            ("child", (("x", 1),)): {"status": "success", "output": "hello world!"},
        })
        result = await RegressionValidator(fuzzy_match=True, fuzzy_tolerance=0.9).validate_regression(
            "parent", "child", [{"x": 1}], sb, "t1"
        )
        assert result.passed is True

        sb2 = self._sandbox({
            ("parent", (("x", 1),)): {"status": "success", "output": "aaaa"},
            ("child", (("x", 1),)): {"status": "success", "output": "bbbb"},
        })
        result2 = await RegressionValidator(fuzzy_match=True, fuzzy_tolerance=0.9).validate_regression(
            "parent", "child", [{"x": 1}], sb2, "t1"
        )
        assert result2.passed is False


# ===========================================================================
# lancedb_handler
# ===========================================================================

class TestLanceDBHandlerCoverage:
    def _handler(self, tmp_path, **kwargs):
        h = LanceDBHandler(db_path=str(tmp_path / "mem"), **kwargs)
        h.db = Mock()
        h._ensure_db = Mock()
        return h

    def _embedder(self):
        svc = Mock()
        svc.generate_embedding = AsyncMock(return_value=[0.1] * 384)
        return svc

    def _df(self, rows, columns=None):
        if columns is None:
            columns = list(rows[0].keys()) if rows else []
        df = pd.DataFrame(rows, columns=columns)
        df["_distance"] = [0.1] * len(df)
        return df

    # -- _initialize_db paths --

    def test_initialize_db_local_path(self, tmp_path):
        h = LanceDBHandler(db_path=str(tmp_path / "mem"))
        mock_db = Mock()
        with patch("lancedb.connect", return_value=mock_db) as connect:
            h._initialize_db()
        assert h.db is mock_db
        connect.assert_called_once()

    def test_initialize_db_connect_failure(self, tmp_path):
        h = LanceDBHandler(db_path=str(tmp_path / "mem"))
        with patch("lancedb.connect", side_effect=RuntimeError("connect refused")):
            h._initialize_db()
        assert h.db is None

    def test_initialize_db_s3_cloud_enabled_r2(self, tmp_path, monkeypatch):
        h = LanceDBHandler(db_path="s3://bucket/mem")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIA123")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "SECRET")
        monkeypatch.setenv("S3_ENDPOINT", "https://r2.example.com")
        mock_db = Mock()
        with patch("lancedb.connect", return_value=mock_db) as connect, patch(
            "core.lancedb_config.LANCEDB_CLOUD_ENABLED", True
        ):
            h._initialize_db()
        opts = connect.call_args.kwargs["storage_options"]
        assert opts["endpoint"] == "https://r2.example.com"
        assert opts["region"] == "auto"
        assert opts["aws_access_key_id"] == "AKIA123"

    def test_initialize_db_s3_no_endpoint(self, tmp_path, monkeypatch):
        h = LanceDBHandler(db_path="s3://bucket/mem")
        monkeypatch.delenv("S3_ENDPOINT", raising=False)
        monkeypatch.delenv("R2_ENDPOINT", raising=False)
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
        monkeypatch.delenv("AWS_S3_ENDPOINT", raising=False)
        monkeypatch.delenv("CLOUDFLARE_R2_ACCOUNT_ID", raising=False)
        monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
        mock_db = Mock()
        with patch("lancedb.connect", return_value=mock_db), patch(
            "core.lancedb_config.LANCEDB_CLOUD_ENABLED", True
        ):
            h._initialize_db()
        assert h.db is mock_db

    def test_initialize_db_r2_account_id_autoconstruct(self, tmp_path, monkeypatch):
        h = LanceDBHandler(db_path="s3://bucket/mem")
        monkeypatch.delenv("S3_ENDPOINT", raising=False)
        monkeypatch.delenv("R2_ENDPOINT", raising=False)
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
        monkeypatch.delenv("AWS_S3_ENDPOINT", raising=False)
        monkeypatch.setenv("CLOUDFLARE_R2_ACCOUNT_ID", "acct123")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "K")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "S")
        mock_db = Mock()
        with patch("lancedb.connect", return_value=mock_db) as connect, patch(
            "core.lancedb_config.LANCEDB_CLOUD_ENABLED", True
        ):
            h._initialize_db()
        assert connect.call_args.kwargs["storage_options"]["endpoint"] == (
            "https://acct123.r2.cloudflarestorage.com"
        )

    def test_initialize_db_s3_missing_creds(self, tmp_path, monkeypatch):
        h = LanceDBHandler(db_path="s3://bucket/mem")
        monkeypatch.setenv("S3_ENDPOINT", "https://r2.example.com")
        monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("R2_SECRET_ACCESS_KEY", raising=False)
        mock_db = Mock()
        with patch("lancedb.connect", return_value=mock_db) as connect, patch(
            "core.lancedb_config.LANCEDB_CLOUD_ENABLED", True
        ):
            h._initialize_db()
        assert "aws_access_key_id" not in (connect.call_args.kwargs.get("storage_options") or {})

    def test_initialize_db_s3_cloud_disabled_downgrade(self, tmp_path, monkeypatch):
        h = LanceDBHandler(db_path="s3://bucket/mem")
        mock_db = Mock()
        with patch("lancedb.connect", return_value=mock_db) as connect, patch(
            "core.lancedb_config.LANCEDB_CLOUD_ENABLED", False
        ):
            h._initialize_db()
        assert not h.db_path.startswith("s3://")

    # -- embed paths --

    def test_embed_text_no_service(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        assert h.embed_text("hi") is None

    def test_embed_text_no_loop(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        assert h.embed_text("hi") is not None

    def test_embed_text_async_same_thread(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()

        async def call():
            return h.embed_text("hi")

        result = asyncio.run(call())
        assert result is None

    def test_embed_text_exception(self, tmp_path):
        h = self._handler(tmp_path)
        svc = Mock()
        svc.generate_embedding = AsyncMock(side_effect=RuntimeError("no embedding"))
        h.embedding_service = svc
        assert h.embed_text("hi") is None

    def test_async_embed_text(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        result = asyncio.run(h.async_embed_text("hi"))
        assert result is not None

    def test_async_embed_text_no_service(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        assert asyncio.run(h.async_embed_text("hi")) is None

    def test_async_embed_text_exception(self, tmp_path):
        h = self._handler(tmp_path)
        svc = Mock()
        svc.generate_embedding = AsyncMock(side_effect=RuntimeError("boom"))
        h.embedding_service = svc
        assert asyncio.run(h.async_embed_text("hi")) is None

    # -- knowledge graph --

    def test_add_knowledge_edge_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.add_knowledge_edge("a", "b", "related") is False

    def test_add_knowledge_edge_success(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        assert h.add_knowledge_edge("a", "b", "related", "desc", {"k": "v"}) is True
        record = table.add.call_args.args[0][0]
        assert record["from_id"] == "a"
        assert record["type"] == "related"

    def test_add_knowledge_edge_create_table_fail(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(return_value=None)
        h.create_table = Mock(return_value=None)
        assert h.add_knowledge_edge("a", "b", "related") is False

    def test_add_knowledge_edge_embedding_fallback(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        table = Mock()
        h.get_table = Mock(return_value=table)
        assert h.add_knowledge_edge("a", "b", "related", "desc") is True
        record = table.add.call_args.args[0][0]
        assert len(record["vector"]) == 1536

    def test_add_knowledge_edge_exception(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.add_knowledge_edge("a", "b", "related") is False

    # -- add_document paths --

    def test_add_document_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.add_document("documents", "text") is False

    def test_add_document_empty_text(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        assert h.add_document("documents", "   ") is False

    def test_add_document_embedding_fail(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        assert h.add_document("documents", "some text") is False

    def test_add_document_creates_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(side_effect=[None, table])
        h.db.create_table = Mock(return_value=table)
        assert h.add_document(
            "documents",
            "hello world",
            source="chat",
            metadata={"title": "t"},
            doc_id="doc-1",
            extra_columns={"outcome": "success"},
        ) is True
        record = table.add.call_args.args[0][0]
        assert record["outcome"] == "success"
        assert record["id"] == "doc-1"

    def test_add_document_existing_table_and_redaction(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        redactor = Mock()
        res = Mock()
        res.has_secrets = True
        res.redacted_text = "REDACTED"
        res.redactions = [{"type": "api_key"}, {"type": "email"}]
        redactor.redact = Mock(return_value=res)
        with patch("core.secrets_redactor.get_secrets_redactor", return_value=redactor):
            assert h.add_document(
                "documents", "my api key is sk-1234 and email a@b.com", metadata={"x": 1}
            ) is True
        record = table.add.call_args.args[0][0]
        assert record["text"] == "REDACTED"
        assert record["metadata"].startswith('{"x": 1, "_redacted_types"')

    def test_add_document_redactor_unavailable(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        with patch(
            "core.secrets_redactor.get_secrets_redactor", side_effect=ImportError("no redactor")
        ):
            assert h.add_document("documents", "plain text") is True

    def test_add_document_redactor_error(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        with patch(
            "core.secrets_redactor.get_secrets_redactor", side_effect=RuntimeError("redactor broke")
        ):
            assert h.add_document("documents", "plain text") is True

    def test_add_document_add_fail(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        table.add = Mock(side_effect=RuntimeError("schema mismatch"))
        h.get_table = Mock(return_value=table)
        assert h.add_document("documents", "plain text") is False

    def test_add_document_outer_exception(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = Mock()
        h.embedding_service.generate_embedding = AsyncMock(side_effect=RuntimeError("boom"))
        assert h.add_document("documents", "plain text") is False

    def test_add_document_with_embedding(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        h.get_table = Mock(return_value=table)
        assert h._add_document_with_embedding(
            "documents", "text", [0.1] * 384, "src", {"m": 1}, "u1", "w1"
        ) is True
        assert h._add_document_with_embedding("documents", "text2", [0.1] * 384) is True

    def test_add_document_with_embedding_creates(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        h.get_table = Mock(return_value=None)
        h.db.create_table = Mock(return_value=table)
        assert h._add_document_with_embedding("documents", "text", [0.1] * 384) is True

    def test_add_document_with_embedding_fail(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h._add_document_with_embedding("documents", "text", [0.1] * 384) is False

    # -- batch paths --

    def test_add_documents_batch(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        n = h.add_documents_batch(
            "documents",
            [{"text": "a", "source": "s", "metadata": {}, "id": "d1", "user_id": "u"}],
        )
        assert n == 1
        assert table.add.call_args.args[0][0]["id"] == "d1"

    def test_add_documents_batch_skip_embed_fail(self, tmp_path):
        h = self._handler(tmp_path)
        svc = Mock()
        svc.generate_embedding = AsyncMock(side_effect=RuntimeError("embedding down"))
        h.embedding_service = svc
        assert h.add_documents_batch("documents", [{"text": "a"}]) == 0

    def test_add_documents_batch_no_records(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        assert h.add_documents_batch("documents", [{"text": "a"}]) == 0

    def test_add_documents_batch_creates_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=None)
        h.db.create_table = Mock(return_value=table)
        assert h.add_documents_batch("documents", [{"text": "a"}, {"text": "b"}]) == 2

    def test_add_documents_batch_create_fails(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        h.get_table = Mock(return_value=None)
        h.db.create_table = Mock(side_effect=RuntimeError("schema"))
        assert h.add_documents_batch("documents", [{"text": "a"}]) == 0

    def test_add_documents_batch_exception(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = Mock()
        h.embedding_service.generate_embedding = AsyncMock(side_effect=RuntimeError("boom"))
        assert h.add_documents_batch("documents", [{"text": "a"}]) == 0

    def test_add_documents_batch_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.add_documents_batch("documents", [{"text": "a"}]) == 0

    # -- search / doc retrieval --

    def test_search_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.search("documents", "q") == []

    def test_search_missing_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        h.get_table = Mock(return_value=None)
        assert h.search("documents", "q") == []

    def test_search_embed_fail(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        h.get_table = Mock(return_value=Mock())
        assert h.search("documents", "q") == []

    def test_search_with_filters(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        results = self._df([
            {"id": "1", "text": "hello", "source": "s", "metadata": "{}", "created_at": "t"},
        ])
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = h.search("documents", "hello", user_id="u'1", filter_str="source == 'x'")
        assert len(out) == 1
        assert out[0]["id"] == "1"
        where_calls = [
            c.args[0] for c in table.search.return_value.limit.return_value.where.call_args_list
        ]
        assert any("user_id == 'u''1'" in w for w in where_calls)
        assert any("workspace_id ==" in w for w in where_calls)

    def test_search_freshness_filter(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        from types import SimpleNamespace
        table = Mock()
        table.schema = [SimpleNamespace(name="freshness_status"), SimpleNamespace(name="id")]
        results = self._df([
            {"id": "1", "text": "hello", "source": "s", "metadata": {}, "created_at": "t"},
        ])
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        with patch("core.lancedb_handler.FRESHNESS_FILTER_ENABLED", True):
            h.search("documents", "hello")
        where_calls = [
            c.args[0] for c in table.search.return_value.limit.return_value.where.call_args_list
        ]
        assert any("freshness_status == 'fresh'" in w for w in where_calls)

    def test_search_result_parse_error(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        row = Mock()
        row.__getitem__ = Mock(side_effect=RuntimeError("column missing"))
        df = MagicMock()
        df.iterrows = Mock(return_value=iter([("idx", row)]))
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=df
        )
        h.get_table = Mock(return_value=table)
        out = h.search("documents", "hello")
        assert out == []

    def test_search_exception(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.search("documents", "hello") == []

    def test_get_document_by_id(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df([
            {"id": "d1", "text": "t", "source": "s", "metadata": '{"k": 1}', "created_at": "c"},
        ])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        doc = h.get_document_by_id("documents", "d1")
        assert doc["id"] == "d1"
        assert doc["metadata"] == {"k": 1}
        assert doc["vector"] == []

    def test_get_document_by_id_not_found(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        empty = MagicMock()
        empty.empty = True
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=empty
        )
        h.get_table = Mock(return_value=table)
        assert h.get_document_by_id("documents", "d1") is None

    def test_get_document_by_id_error(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.get_document_by_id("documents", "d1") is None

    def test_list_documents(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df([
            {"id": "1", "text": "t1", "source": "src", "metadata": "{}", "created_at": "c1"},
            {"id": "2", "text": "t2", "source": "src2", "metadata": "{}", "created_at": "c2"},
        ])
        table.search.return_value.limit.return_value.to_pandas = Mock(return_value=results)
        h.get_table = Mock(return_value=table)
        docs = h.list_documents("documents", limit=1, offset=1)
        assert len(docs) == 1

    def test_list_documents_empty(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        empty = MagicMock()
        empty.empty = True
        table.search.return_value.limit.return_value.to_pandas = Mock(return_value=empty)
        h.get_table = Mock(return_value=table)
        assert h.list_documents("documents") == []

    def test_list_documents_no_created_at(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df([{"id": "1", "text": "t1", "source": "src", "metadata": "{}"}])
        table.search.return_value.limit.return_value.to_pandas = Mock(return_value=results)
        h.get_table = Mock(return_value=table)
        docs = h.list_documents("documents")
        assert docs[0]["title"] == "src"

    def test_query_knowledge_graph_exclude(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        results = self._df([
            {"id": "e1", "text": "rel", "source": "s", "metadata": '{"doc_id": "doc-1"}', "created_at": "c"},
            {"id": "e2", "text": "rel2", "source": "s", "metadata": '{"doc_id": "doc-2"}', "created_at": "c"},
        ])
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = h.query_knowledge_graph("rel", exclude_source_doc_ids={"doc-1"})
        assert [r["id"] for r in out] == ["e2"]

    def test_seed_mock_data(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        assert h.seed_mock_data([{"text": "a"}, {"text": "b"}]) == 2

    # -- dual vector methods --

    def test_add_embedding_success(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        h.get_table = Mock(return_value=table)
        assert asyncio.run(
            h.add_embedding("episodes", "ep1", [0.1] * 1536, metadata={"text": "x"})
        ) is True
        record = table.add.call_args.args[0][0]
        assert record["id"] == "ep1"

    def test_add_embedding_creates_table(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        h.get_table = Mock(return_value=None)
        h.create_table = Mock(return_value=table)
        assert asyncio.run(h.add_embedding("episodes", "ep1", [0.1] * 1536)) is True
        h.create_table.assert_called_once_with("episodes", dual_vector=True)

    def test_add_embedding_create_fails(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(return_value=None)
        h.create_table = Mock(return_value=None)
        assert asyncio.run(h.add_embedding("episodes", "ep1", [0.1] * 1536)) is False

    def test_add_embedding_unknown_column(self, tmp_path):
        h = self._handler(tmp_path)
        with pytest.raises(ValueError):
            asyncio.run(h.add_embedding("episodes", "ep1", [0.1] * 10, vector_column="nope"))

    def test_add_embedding_dim_mismatch(self, tmp_path):
        h = self._handler(tmp_path)
        with pytest.raises(ValueError):
            asyncio.run(h.add_embedding("episodes", "ep1", [0.1] * 10))

    def test_add_embedding_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert asyncio.run(h.add_embedding("episodes", "ep1", [0.1] * 1536)) is False

    def test_similarity_search_success(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df([{"id": "ep1"}])
        table.search.return_value.limit.return_value.to_pandas = Mock(return_value=results)
        h.get_table = Mock(return_value=table)
        out = asyncio.run(h.similarity_search("episodes", [0.1] * 1536, top_k=5))
        assert out[0]["episode_id"] == "ep1"
        assert out[0]["vector_column"] == "vector"

    def test_similarity_search_missing_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(return_value=None)
        assert asyncio.run(h.similarity_search("episodes", [0.1] * 1536)) == []

    def test_similarity_search_unknown_column(self, tmp_path):
        h = self._handler(tmp_path)
        with pytest.raises(ValueError):
            asyncio.run(
                h.similarity_search("episodes", [0.1] * 10, vector_column="nope")
            )

    def test_similarity_search_dim_mismatch(self, tmp_path):
        h = self._handler(tmp_path)
        with pytest.raises(ValueError):
            asyncio.run(h.similarity_search("episodes", [0.1] * 10))

    def test_similarity_search_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert asyncio.run(h.similarity_search("episodes", [0.1] * 1536)) == []

    def test_get_embedding_success(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df([{"id": "ep1", "vector": [0.1, 0.2]}])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = asyncio.run(h.get_embedding("episodes", "ep1"))
        assert out == [0.1, 0.2]

    def test_get_embedding_not_found(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        empty = MagicMock()
        empty.empty = True
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=empty
        )
        h.get_table = Mock(return_value=table)
        assert asyncio.run(h.get_embedding("episodes", "ep1")) is None

    def test_get_embedding_missing_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(return_value=None)
        assert asyncio.run(h.get_embedding("episodes", "ep1")) is None

    def test_get_embedding_error(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert asyncio.run(h.get_embedding("episodes", "ep1")) is None

    # -- basic plumbing --

    def test_test_connection_not_available(self, tmp_path):
        with patch("core.lancedb_handler.LANCEDB_AVAILABLE", False):
            h = LanceDBHandler(db_path=str(tmp_path / "mem"))
            result = h.test_connection()
        assert result["connected"] is False

    def test_test_connection_db_none(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        result = h.test_connection()
        assert result["connected"] is False

    def test_test_connection_success(self, tmp_path):
        h = self._handler(tmp_path)
        h.db.table_names = Mock(return_value=["documents"])
        result = h.test_connection()
        assert result["connected"] is True
        assert result["tables"] == ["documents"]

    def test_create_table_db_none(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.create_table("documents") is None

    def test_create_table_exception(self, tmp_path):
        h = self._handler(tmp_path)
        h.db.create_table = Mock(side_effect=RuntimeError("schema err"))
        assert h.create_table("documents") is None

    def test_create_table_custom_schema(self, tmp_path):
        h = self._handler(tmp_path)
        schema = {"custom": "schema"}
        table = Mock()
        h.db.create_table = Mock(return_value=table)
        out = h.create_table("custom_table", schema=schema)
        assert out is table
        h.db.create_table.assert_called_once_with("custom_table", schema=schema, mode="overwrite")

    def test_get_table_variants(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.get_table("x") is None
        h2 = self._handler(tmp_path)
        h2.db.table_names = Mock(return_value=["x"])
        h2.db.open_table = Mock(return_value="T")
        assert h2.get_table("x") == "T"
        h3 = self._handler(tmp_path)
        h3.db.table_names = Mock(return_value=["x"])
        assert h3.get_table("y") is None
        h4 = self._handler(tmp_path)
        h4.db.table_names = Mock(side_effect=RuntimeError("boom"))
        assert h4.get_table("x") is None

    def test_has_column(self):
        from types import SimpleNamespace
        table = Mock()
        table.schema = [SimpleNamespace(name="id"), SimpleNamespace(name="text")]
        assert LanceDBHandler._has_column(table, "id") is True
        assert LanceDBHandler._has_column(table, "nope") is False
        bad = Mock()
        bad.schema = Mock(side_effect=RuntimeError("no schema"))
        assert LanceDBHandler._has_column(bad, "id") is False

    def test_drop_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.drop_table("x") is False
        h2 = self._handler(tmp_path)
        h2.db.table_names = Mock(return_value=["x"])
        assert h2.drop_table("x") is True
        h2.db.drop_table.assert_called_once_with("x")
        h3 = self._handler(tmp_path)
        h3.db.table_names = Mock(return_value=[])
        assert h3.drop_table("x") is True
        h4 = self._handler(tmp_path)
        h4.db.table_names = Mock(side_effect=RuntimeError("boom"))
        assert h4.drop_table("x") is False

    def test_ensure_db_lazy(self, tmp_path):
        h = LanceDBHandler(db_path=str(tmp_path / "mem"))
        with patch("core.lancedb_handler.LANCEDB_AVAILABLE", False):
            h._ensure_db()
        assert h.db is None
        with patch("core.lancedb_handler.LANCEDB_AVAILABLE", True):
            with patch.object(h, "_initialize_db") as init:
                h._ensure_db()
        init.assert_called_once()

    def test_ensure_embedder_deprecated(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedder = None
        with patch.object(h, "_initialize_embedder") as init:
            h._ensure_embedder()
        init.assert_called_once()
        h._initialize_embedder()
        h._init_local_embedder()

    # -- chat history manager --

    def _chat_manager(self, tmp_path, db_ok=True):
        h = self._handler(tmp_path)
        if not db_ok:
            h.db = None
        from core.lancedb_handler import ChatHistoryManager
        return h, ChatHistoryManager(h)

    def test_chat_manager_ensure_table(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.db.table_names = Mock(return_value=[])
        cm._ensure_table()
        h.db.create_table.assert_called_once()
        h.db.table_names = Mock(return_value=["chat_messages"])
        cm._ensure_table()
        h.db.table_names = Mock(side_effect=RuntimeError("boom"))
        cm._ensure_table()

    def test_chat_manager_save_message(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        assert cm.save_message("sess-1", "user-1", "user", "hello") is True
        record = table.add.call_args.args[0][0]
        assert "session_id" in record["metadata"]

    def test_chat_manager_save_message_no_db(self, tmp_path):
        h, cm = self._chat_manager(tmp_path, db_ok=False)
        assert cm.save_message("s", "u", "user", "hi") is False

    def test_chat_manager_save_message_error(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.embedding_service = None
        assert cm.save_message("s", "u", "user", "hi") is False

    def test_escape_like(self):
        from core.lancedb_handler import ChatHistoryManager
        assert ChatHistoryManager._escape_like("a'b%_c") == "a''b\\%\\_c"
        assert ChatHistoryManager._escape_like("back\\slash") == "back\\\\slash"

    def test_get_session_history(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        table = Mock()
        rows = self._df([
            {"id": "m1", "text": "hi", "source": "chat_user", "metadata": '{"session_id": "s1", "role": "user"}', "created_at": "c1"},
            {"id": "m2", "text": "yo", "source": "chat_user", "metadata": '{"session_id": "s2", "role": "user"}', "created_at": "c2"},
        ])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=rows
        )
        h.get_table = Mock(return_value=table)
        msgs = cm.get_session_history("s1", limit=1)
        assert [m["id"] for m in msgs] == ["m1"]

    def test_get_session_history_empty(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.get_table = Mock(return_value=None)
        assert cm.get_session_history("s1") == []
        h2, cm2 = self._chat_manager(tmp_path, db_ok=False)
        assert cm2.get_session_history("s1") == []

    def test_get_session_history_parse_error(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        table = Mock()
        rows = self._df([
            {"id": "m1", "text": "hi", "source": "s", "metadata": "not-json{{", "created_at": "c1"},
        ])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=rows
        )
        h.get_table = Mock(return_value=table)
        assert cm.get_session_history("s1") == []

    def test_search_relevant_context(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        results = self._df([
            {"id": "m1", "text": "hi", "source": "s", "metadata": '{"session_id": "s1"}', "created_at": "c1"},
        ])
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = cm.search_relevant_context("hello", session_id="s1")
        assert [r["id"] for r in out] == ["m1"]
        h2, cm2 = self._chat_manager(tmp_path, db_ok=False)
        assert cm2.search_relevant_context("hello") == []

    def test_search_relevant_context_post_filter(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        results = self._df([
            {"id": "m1", "text": "hi", "source": "s", "metadata": '{"session_id": "s-prefix"}', "created_at": "c1"},
        ])
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = cm.search_relevant_context("hello", session_id="s")
        assert out == []

    def test_get_entity_mentions(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        table = Mock()
        rows = self._df([
            {"id": "m1", "text": "hi", "source": "s", "metadata": '{"workflow_id": "wf-1", "session_id": "s1"}', "created_at": "c1"},
            {"id": "m2", "text": "yo", "source": "s", "metadata": '{"workflow_id": "wf-2", "session_id": "s1"}', "created_at": "c2"},
        ])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=rows
        )
        h.get_table = Mock(return_value=table)
        msgs = cm.get_entity_mentions("workflow_id", "wf-1")
        assert [m["id"] for m in msgs] == ["m1"]
        msgs2 = cm.get_entity_mentions("workflow_id", "wf-1", session_id="other")
        assert msgs2 == []
        h2, cm2 = self._chat_manager(tmp_path, db_ok=False)
        assert cm2.get_entity_mentions("workflow_id", "wf-1") == []

    def test_get_entity_mentions_no_table(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.get_table = Mock(return_value=None)
        assert cm.get_entity_mentions("workflow_id", "wf-1") == []

    def test_get_entity_mentions_parse_error(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        table = Mock()
        rows = self._df([
            {"id": "m1", "text": "hi", "source": "s", "metadata": "bad-json", "created_at": "c1"},
        ])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=rows
        )
        h.get_table = Mock(return_value=table)
        assert cm.get_entity_mentions("workflow_id", "wf-1") == []

    # -- module-level helpers --

    def test_get_lancedb_handler_caching(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        from core.lancedb_handler import get_lancedb_handler, _workspace_handlers
        _workspace_handlers.clear()
        h1 = get_lancedb_handler("ws-1")
        h2 = get_lancedb_handler("ws-1")
        assert h1 is h2
        assert h1.workspace_id == "ws-1"
        h3 = get_lancedb_handler(None, None, db=Mock())
        assert h3 not in [h1, h2]
        assert h3.workspace_id == "default_shared"
        _workspace_handlers.clear()

    def test_module_globals(self):
        from core.lancedb_handler import (
            chat_history_manager,
            get_chat_history_manager,
            lancedb_handler,
        )
        assert lancedb_handler is not None
        assert chat_history_manager is not None
        manager = get_chat_history_manager("ws-x")
        assert manager is not None

    def test_embed_documents_batch_unavailable(self):
        from core.lancedb_handler import embed_documents_batch
        with patch("core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE", False):
            assert embed_documents_batch(["a"]) is None

    def test_embed_documents_batch_error(self):
        from core.lancedb_handler import embed_documents_batch
        fake_st = Mock()
        fake_st.SentenceTransformer = Mock(side_effect=RuntimeError("model load failed"))
        with patch("core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE", True), patch(
            "core.lancedb_handler.NUMPY_AVAILABLE", True
        ), patch.dict(sys.modules, {"sentence_transformers": fake_st}):
            assert embed_documents_batch(["a"]) is None

    def test_create_memory_schema(self):
        from typing import List
        from core.lancedb_handler import create_memory_schema
        with patch.dict(sys.modules, {"lancedb.pydantic": None}):
            schema = create_memory_schema(512)
        assert schema["vector"] == List[float]

    def test_create_memory_schema_with_vector(self):
        from core.lancedb_handler import create_memory_schema
        fake_vector = Mock()
        with patch("lancedb.pydantic.Vector", return_value=fake_vector):
            schema = create_memory_schema(512)
        assert schema["vector"] is fake_vector

    def test_mock_embedder(self):
        from core.lancedb_handler import MockEmbedder
        emb = MockEmbedder(8)
        v1 = emb.encode("hello")
        v2 = emb.encode("hello")
        assert v1 == v2
        assert len(v1) == 8
        v3 = emb.encode("hello", convert_to_numpy=True)
        assert v3.shape == (8,)


    # -- remaining gap coverage --

    def test_embed_text_other_thread_loop(self, tmp_path):
        import threading
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        fake_loop = Mock()
        fake_loop._thread_id = threading.get_ident() + 1
        with patch("asyncio.get_running_loop", return_value=fake_loop):
            assert h.embed_text("hi") is not None

    def test_async_embed_text_no_numpy(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        with patch("core.lancedb_handler.NUMPY_AVAILABLE", False):
            out = asyncio.run(h.async_embed_text("hi"))
        assert out == [0.1] * 384

    def test_add_knowledge_edge_zero_vector_no_numpy(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = None
        table = Mock()
        h.get_table = Mock(return_value=table)
        with patch("core.lancedb_handler.NUMPY_AVAILABLE", False):
            assert h.add_knowledge_edge("a", "b", "rel", "d") is True
        record = table.add.call_args.args[0][0]
        assert record["vector"] == [0.0] * 1536

    def test_add_document_outer_exception(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        h.get_table = Mock(side_effect=RuntimeError("lancedb down"))
        assert h.add_document("documents", "text") is False

    def test_add_document_with_embedding_db_none(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h._add_document_with_embedding("documents", "t", [0.1] * 384) is False

    def test_add_documents_batch_get_table_raises(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.add_documents_batch("documents", [{"text": "a"}]) == 0

    def test_search_pandas_unavailable(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        h.get_table = Mock(return_value=table)
        with patch("core.lancedb_handler.PANDAS_AVAILABLE", False):
            assert h.search("documents", "q") == []

    def test_search_metadata_none(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        results = self._df(
            [{"id": "1", "text": "t", "source": "s", "metadata": None, "created_at": "c"}]
        )
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = h.search("documents", "q")
        assert out[0]["metadata"] == {}

    def test_get_document_by_id_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.get_document_by_id("documents", "d1") is None

    def test_get_document_by_id_no_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(return_value=None)
        assert h.get_document_by_id("documents", "d1") is None

    def test_list_documents_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert h.list_documents("documents") == []

    def test_list_documents_no_table(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(return_value=None)
        assert h.list_documents("documents") == []

    def test_list_documents_metadata_none(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df(
            [{"id": "1", "text": "t", "source": "src", "metadata": None, "created_at": "c"}]
        )
        table.search.return_value.limit.return_value.to_pandas = Mock(return_value=results)
        h.get_table = Mock(return_value=table)
        docs = h.list_documents("documents")
        assert docs[0]["title"] == "src"

    def test_list_documents_outer_error(self, tmp_path):
        h = self._handler(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert h.list_documents("documents") == []

    def test_query_knowledge_graph_no_exclude(self, tmp_path):
        h = self._handler(tmp_path)
        h.embedding_service = self._embedder()
        table = Mock()
        results = self._df(
            [{"id": "e1", "text": "r", "source": "s", "metadata": "{}", "created_at": "c"}]
        )
        table.search.return_value.limit.return_value.where.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        out = h.query_knowledge_graph("q")
        assert [r["id"] for r in out] == ["e1"]

    def test_add_embedding_add_raises(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        table.add = Mock(side_effect=RuntimeError("schema mismatch"))
        h.get_table = Mock(return_value=table)
        assert asyncio.run(h.add_embedding("episodes", "ep1", [0.1] * 1536)) is False

    def test_similarity_search_row_error(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        row = Mock()
        row.get = Mock(side_effect=RuntimeError("no col"))
        df = MagicMock()
        df.iterrows = Mock(return_value=iter([("i", row)]))
        table.search.return_value.limit.return_value.to_pandas = Mock(return_value=df)
        h.get_table = Mock(return_value=table)
        assert asyncio.run(h.similarity_search("episodes", [0.1] * 1536)) == []

    def test_similarity_search_outer_error(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        table.search.return_value.limit.return_value.to_pandas = Mock(
            side_effect=RuntimeError("boom")
        )
        h.get_table = Mock(return_value=table)
        assert asyncio.run(h.similarity_search("episodes", [0.1] * 1536)) == []

    def test_get_embedding_no_db(self, tmp_path):
        h = self._handler(tmp_path)
        h.db = None
        assert asyncio.run(h.get_embedding("episodes", "ep1")) is None

    def test_get_embedding_vector_none(self, tmp_path):
        h = self._handler(tmp_path)
        table = Mock()
        results = self._df([{"id": "ep1", "vector": None}])
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=results
        )
        h.get_table = Mock(return_value=table)
        assert asyncio.run(h.get_embedding("episodes", "ep1")) is None

    def test_chat_manager_save_message_add_document_raises(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.add_document = Mock(side_effect=RuntimeError("boom"))
        assert cm.save_message("s", "u", "user", "hi") is False

    def test_get_session_history_pandas_missing(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.get_table = Mock(return_value=Mock())
        with patch("core.lancedb_handler.PANDAS_AVAILABLE", False):
            assert cm.get_session_history("s1") == []

    def test_get_session_history_metadata_none(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        table = Mock()
        rows = self._df(
            [{"id": "m1", "text": "hi", "source": "s", "metadata": None, "created_at": "c1"}]
        )
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            return_value=rows
        )
        h.get_table = Mock(return_value=table)
        assert cm.get_session_history("s1") == []

    def test_get_session_history_outer_error(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.get_table = Mock(side_effect=RuntimeError("boom"))
        assert cm.get_session_history("s1") == []

    def test_search_relevant_context_outer_error(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.embedding_service = self._embedder()
        h.search = Mock(side_effect=RuntimeError("boom"))
        assert cm.search_relevant_context("q") == []

    def test_get_entity_mentions_pandas_missing(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        h.get_table = Mock(return_value=Mock())
        with patch("core.lancedb_handler.PANDAS_AVAILABLE", False):
            assert cm.get_entity_mentions("workflow_id", "wf-1") == []

    def test_get_entity_mentions_outer_error(self, tmp_path):
        h, cm = self._chat_manager(tmp_path)
        table = Mock()
        table.search.return_value.where.return_value.limit.return_value.to_pandas = Mock(
            side_effect=RuntimeError("boom")
        )
        h.get_table = Mock(return_value=table)
        assert cm.get_entity_mentions("workflow_id", "wf-1") == []

    def test_get_chat_context_manager(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))
        from core.lancedb_handler import get_chat_context_manager, _workspace_handlers
        _workspace_handlers.clear()
        manager = get_chat_context_manager("ws-ccm")
        assert manager is not None
        _workspace_handlers.clear()

    def test_mock_embedder_without_numpy(self):
        from core.lancedb_handler import MockEmbedder
        emb = MockEmbedder(8)
        with patch.dict(sys.modules, {"numpy": None}):
            v = emb.encode("hello")
        assert len(v) == 8
        assert v != emb.encode("different text")

# ===========================================================================
# communication adapters
# ===========================================================================

class TestCommunicationAdaptersCoverage:
    def _client(self, response=None, post_result=None):
        client = AsyncMock()
        client.__aenter__.return_value = client
        if post_result is not None:
            client.post = AsyncMock(return_value=post_result)
        return client

    def test_facebook_verify_and_normalize(self):
        from core.communication.adapters.facebook import FacebookAdapter
        adapter = FacebookAdapter()
        assert adapter.verify_request({}, "") is True
        payload = {
            "object": "page",
            "entry": [{"messaging": [{"sender": {"id": "U1"}, "message": {"text": "hi"}}]}],
        }
        out = adapter.normalize_payload(payload)
        assert out["sender_id"] == "U1"
        assert out["content"] == "hi"
        assert adapter.normalize_payload({"object": "not_page"}) is None
        assert adapter.normalize_payload({"object": "page", "entry": []}) is None
        assert adapter.normalize_payload({}) is None

    def test_facebook_send_message(self):
        from core.communication.adapters.facebook import FacebookAdapter
        adapter = FacebookAdapter()
        assert asyncio.run(adapter.send_message("U1", "hi")) is False
        adapter = FacebookAdapter(page_access_token="tok")
        response = Mock()
        response.raise_for_status = Mock()
        client = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.send_message("U1", "hi")) is True
        response.raise_for_status = Mock(side_effect=RuntimeError("fb error"))
        client2 = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client2):
            assert asyncio.run(adapter.send_message("U1", "hi")) is False

    def test_google_chat_verify_and_normalize(self):
        from core.communication.adapters.google_chat import GoogleChatAdapter
        adapter = GoogleChatAdapter()
        assert adapter.verify_request({}, "") is True
        payload = {
            "type": "MESSAGE",
            "space": {"name": "spaces/ABC", "type": "ROOM"},
            "message": {"sender": {"name": "users/1", "email": "u@x.com", "displayName": "U"}, "text": "hello"},
        }
        out = adapter.normalize_payload(payload)
        assert out["sender_id"] == "u@x.com"
        assert out["channel_id"] == "spaces/ABC"
        assert adapter.normalize_payload({"type": "ADDED_TO_SPACE"}) is None
        assert adapter.normalize_payload({"type": "MESSAGE", "message": {}}) is None

    def test_intercom_verify_signature(self):
        from core.communication.adapters.intercom import IntercomAdapter
        import hashlib
        import hmac as hmac_mod
        adapter = IntercomAdapter(access_token="tok")
        assert adapter.verify_request({}, "body") is True  # no client_secret
        adapter = IntercomAdapter(access_token="tok", client_secret="secret")
        assert adapter.verify_request({}, "body") is False  # missing header
        assert adapter.verify_request({"x-hub-signature": "garbage-no-sep"}, "body") is False
        body = "hello body"
        sig256 = "sha256=" + hmac_mod.new(b"secret", body.encode(), hashlib.sha256).hexdigest()
        assert adapter.verify_request({"x-hub-signature": sig256}, body) is True
        sig1 = "sha1=" + hmac_mod.new(b"secret", body.encode(), hashlib.sha1).hexdigest()
        assert adapter.verify_request({"x-hub-signature": sig1}, body) is True
        assert adapter.verify_request({"x-hub-signature": "md5=abc"}, body) is False
        bad = "sha256=" + "0" * 64
        assert adapter.verify_request({"x-hub-signature": bad}, body) is False

    def test_intercom_normalize(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok")
        payload = {
            "topic": "conversation.user.created",
            "data": {"item": {"id": "c1", "user": {"id": "u1", "email": "a@b.com", "name": "A"}, "conversation_message": {"body": "<p>Hello <b>there</b></p>"}}},
        }
        out = adapter.normalize_payload(payload)
        assert out["sender_id"] == "u1"
        assert out["content"] == "Hello there"
        assert adapter.normalize_payload({"topic": "other"}) is None
        assert adapter.normalize_payload({"topic": "conversation.user.created", "data": {}}) is None

    def test_intercom_send_message(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok")
        response = Mock()
        response.raise_for_status = Mock()
        client = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.send_message("c1", "hi")) is True
        err = Mock()
        err.raise_for_status = Mock(side_effect=RuntimeError("401"))
        err.response = Mock()
        err.response.text = "unauthorized"
        client2 = self._client(post_result=err)
        with patch("httpx.AsyncClient", return_value=client2):
            assert asyncio.run(adapter.send_message("c1", "hi")) is False
        err2 = Mock()
        err2.raise_for_status = Mock(side_effect=RuntimeError("500"))
        err2.response = None
        client3 = self._client(post_result=err2)
        with patch("httpx.AsyncClient", return_value=client3):
            assert asyncio.run(adapter.send_message("c1", "hi")) is False

    def test_line_verify_and_normalize(self):
        from core.communication.adapters.line import LineAdapter
        adapter = LineAdapter()
        assert adapter.verify_request({}, "") is True
        payload = {"events": [{"type": "message", "source": {"userId": "U1"}, "message": {"type": "text", "text": "hi"}}]}
        out = adapter.normalize_payload(payload)
        assert out["sender_id"] == "U1"
        assert adapter.normalize_payload({"events": []}) is None
        assert adapter.normalize_payload({"events": [{"type": "follow"}]}) is None
        assert adapter.normalize_payload({"events": [{"type": "message"}]}) is None
        assert adapter.normalize_payload({}) is None
        assert adapter.normalize_payload(None) is None

    def test_line_send_message(self):
        from core.communication.adapters.line import LineAdapter
        adapter = LineAdapter()
        assert asyncio.run(adapter.send_message("U1", "hi")) is False
        adapter = LineAdapter(channel_access_token="tok")
        response = Mock()
        response.raise_for_status = Mock()
        client = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.send_message("U1", "hi")) is True
        response.raise_for_status = Mock(side_effect=RuntimeError("line error"))
        client2 = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client2):
            assert asyncio.run(adapter.send_message("U1", "hi")) is False

    def test_matrix_verify_and_normalize(self):
        from core.communication.adapters.matrix import MatrixAdapter
        adapter = MatrixAdapter()
        assert adapter.verify_request({}, "") is True
        payload = {"type": "m.room.message", "sender": "@u:matrix.org", "content": {"msgtype": "m.text", "body": "hi"}, "room_id": "!r:matrix.org"}
        out = adapter.normalize_payload(payload)
        assert out["sender_id"] == "@u:matrix.org"
        assert out["channel_id"] == "!r:matrix.org"
        assert adapter.normalize_payload({"type": "m.room.membership"}) is None
        assert adapter.normalize_payload({"type": "m.room.message"}) is None

    def test_matrix_send_message(self):
        from core.communication.adapters.matrix import MatrixAdapter
        adapter = MatrixAdapter()
        assert asyncio.run(adapter.send_message("!r", "hi")) is False
        adapter = MatrixAdapter(homeserver_url="https://hs.org", access_token="tok")
        response = Mock()
        response.raise_for_status = Mock()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.put = AsyncMock(return_value=response)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.send_message("!r", "hi")) is True
        response.raise_for_status = Mock(side_effect=RuntimeError("matrix error"))
        client2 = AsyncMock()
        client2.__aenter__.return_value = client2
        client2.put = AsyncMock(return_value=response)
        with patch("httpx.AsyncClient", return_value=client2):
            assert asyncio.run(adapter.send_message("!r", "hi")) is False

    def test_signal_verify_and_normalize(self):
        from core.communication.adapters.signal import SignalAdapter
        adapter = SignalAdapter()
        assert adapter.verify_request({}, "") is True
        payload = {"source": "+1000", "message": "hi"}
        out = adapter.normalize_payload(payload)
        assert out["sender_id"] == "+1000"
        assert adapter.normalize_payload({"source": "+1000"}) is None
        assert adapter.normalize_payload({}) is None

    def test_signal_send_message_success(self):
        from core.communication.adapters.signal import SignalAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(SignalAdapter().send_message("+1", "hi")) is True

    def test_telegram_verify_request(self):
        from core.communication.adapters.telegram import TelegramAdapter
        adapter = TelegramAdapter(bot_token="tok")
        request = Mock()
        assert asyncio.run(adapter.verify_request(request, b"body")) is True
        adapter = TelegramAdapter(bot_token="tok", secret_token="secret")
        request.headers.get = Mock(return_value="secret")
        assert asyncio.run(adapter.verify_request(request, b"body")) is True
        request.headers.get = Mock(return_value="wrong")
        assert asyncio.run(adapter.verify_request(request, b"body")) is False

    def test_telegram_send_message(self):
        from core.communication.adapters.telegram import TelegramAdapter
        adapter = TelegramAdapter(bot_token=None)
        assert asyncio.run(adapter.send_message("123", "hi")) is False
        adapter = TelegramAdapter(bot_token="tok")
        response = Mock()
        response.raise_for_status = Mock()
        client = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.send_message("123", "hi")) is True
        response.raise_for_status = Mock(side_effect=RuntimeError("tg error"))
        client2 = self._client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client2):
            assert asyncio.run(adapter.send_message("123", "hi")) is False

    def test_telegram_get_media(self):
        from core.communication.adapters.telegram import TelegramAdapter
        adapter = TelegramAdapter(bot_token=None)
        assert asyncio.run(adapter.get_media("f1")) is None
        adapter = TelegramAdapter(bot_token="tok")
        client = AsyncMock()
        client.__aenter__.return_value = client
        res1 = Mock()
        res1.raise_for_status = Mock()
        res1.json = Mock(return_value={"result": {"file_path": "docs/file1"}})
        res2 = Mock()
        res2.raise_for_status = Mock()
        res2.content = b"audio-bytes"
        client.get = AsyncMock(side_effect=[res1, res2])
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.get_media("f1")) == b"audio-bytes"
        res3 = Mock()
        res3.raise_for_status = Mock()
        res3.json = Mock(return_value={"result": {}})
        client.get = AsyncMock(return_value=res3)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.get_media("f1")) is None
        client.get = AsyncMock(side_effect=RuntimeError("network down"))
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.get_media("f1")) is None

    def test_telegram_get_updates(self):
        from core.communication.adapters.telegram import TelegramAdapter
        adapter = TelegramAdapter(bot_token=None)
        assert asyncio.run(adapter.get_updates()) == []
        adapter = TelegramAdapter(bot_token="tok")
        client = AsyncMock()
        client.__aenter__.return_value = client
        res = Mock()
        res.raise_for_status = Mock()
        res.json = Mock(return_value={"result": [{"update_id": 1}]})
        client.get = AsyncMock(return_value=res)
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.get_updates(limit=200, offset=5, timeout=3)) == [{"update_id": 1}]
        client.get = AsyncMock(side_effect=RuntimeError("api down"))
        with patch("httpx.AsyncClient", return_value=client):
            assert asyncio.run(adapter.get_updates()) == []

    def test_base_adapter_defaults(self):
        from core.communication.adapters.base import GenericAdapter
        adapter = GenericAdapter()
        assert asyncio.run(adapter.verify_request(Mock(), b"")) is True
        out = adapter.normalize_payload({"sender_id": "s", "message": "hi", "channel_id": "c"})
        assert out["sender_id"] == "s"
        assert out["content"] == "hi"
        out2 = adapter.normalize_payload({"content": "hi2"})
        assert out2["sender_id"] == "unknown"
        assert asyncio.run(adapter.send_message("t", "m")) is True
        assert asyncio.run(adapter.get_media("m")) is None


def test_module_reimport_fallback_branches_last():
        import importlib

        real_find_spec = importlib.util.find_spec

        def fake_find_spec(name, *args, **kwargs):
            if name in ("numpy", "pandas", "lancedb", "sentence_transformers", "openai", "pyarrow"):
                return None
            return real_find_spec(name, *args, **kwargs)

        orig = sys.modules["core.lancedb_handler"]
        sys.modules.pop("core.lancedb_handler")
        try:
            with patch("importlib.util.find_spec", side_effect=fake_find_spec), patch.dict(
                sys.modules,
                {"core.byok_endpoints": None, "core.llm_service": None, "pyarrow": None},
            ):
                mod = importlib.import_module("core.lancedb_handler")
            assert mod.LANCEDB_AVAILABLE is False
            assert mod.NUMPY_AVAILABLE is False
            assert mod.PANDAS_AVAILABLE is False
            assert mod.SENTENCE_TRANSFORMERS_AVAILABLE is False
            assert mod.OPENAI_AVAILABLE is False
            assert mod.pa is None
            assert mod.get_byok_manager is None
            assert mod.LLMService is None
        finally:
            sys.modules["core.lancedb_handler"] = orig
