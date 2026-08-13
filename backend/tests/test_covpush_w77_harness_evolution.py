"""Coverage wave 77 — core/harness_evolution_service.py (15% -> 100%).

Offline meta-runtime: mines execution traces for failure patterns, proposes
harness mutations, validates them in a rollback sandbox, deploys patches.
Fully mocked DB; only the real SandboxTransaction runs on tempdirs.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import core.harness_evolution_service as harness_mod
from core.harness_evolution_service import HarnessEvolutionService
from core.models import AgentReasoningStep, AgentRegistry, AgentStatus


def _step(**overrides):
    defaults = {
        "id": "rs-1",
        "tenant_id": "t1",
        "execution_id": "ex-1",
        "step_number": 1,
        "step_type": "action",
        "thought": "need data",
        "action": {"tool": "shell", "params": {"cmd": "ls"}},
        "observation": "listed",
        "verified": "failed_verification",
        "feedback_score": None,
        "verification_evidence": "mismatch",
        "timestamp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    defaults.update(overrides)
    return AgentReasoningStep(**defaults)


class TestMineWeaknesses:
    def _service(self, steps):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = steps
        return HarnessEvolutionService(db)

    @pytest.mark.asyncio
    async def test_no_failures(self):
        service = self._service([])
        assert await service.mine_weaknesses("t1") == []

    @pytest.mark.asyncio
    async def test_groups_and_counts_by_step_tool(self):
        service = self._service([
            _step(id="r1", action={"tool": "shell"}),
            _step(id="r2", action={"tool": "shell"}),
            _step(id="r3", action={"tool": "browser"}),
        ])
        patterns = await service.mine_weaknesses("t1")
        by_tool = {p["tool"]: p for p in patterns}
        assert by_tool["shell"]["failure_count"] == 2
        assert by_tool["browser"]["failure_count"] == 1

    @pytest.mark.asyncio
    async def test_dict_and_json_string_actions(self):
        service = self._service([
            _step(id="r1", action={"tool": "run_command"}),
            _step(id="r2", action=json.dumps({"tool": "http_request"})),
            _step(id="r3", action="not-json{"),
            _step(id="r4", action=None),
        ])
        patterns = await service.mine_weaknesses("t1")
        tools = {p["tool"] for p in patterns}
        assert tools == {"run_command", "http_request", "unknown"}

    @pytest.mark.asyncio
    async def test_feedback_negative_counts_as_failure(self):
        service = self._service([
            _step(id="r1", verified="verified", feedback_score=-1),
        ])
        patterns = await service.mine_weaknesses("t1")
        assert len(patterns) == 1
        assert patterns[0]["failure_count"] == 1

    @pytest.mark.asyncio
    async def test_examples_capped_at_three(self):
        steps = [_step(id=f"r{i}", action={"tool": "shell"}) for i in range(5)]
        service = self._service(steps)
        patterns = await service.mine_weaknesses("t1")
        assert len(patterns[0]["examples"]) == 3
        assert patterns[0]["examples"][0]["thought"] == "need data"
        assert patterns[0]["examples"][0]["observation"] == "listed"
        assert patterns[0]["examples"][0]["verification_evidence"] == "mismatch"

    @pytest.mark.asyncio
    async def test_bad_json_string_treated_unknown_tool(self):
        service = self._service([_step(id="r1", action="{{{broken")])
        patterns = await service.mine_weaknesses("t1")
        assert patterns[0]["tool"] == "unknown"


class TestProposeMutation:
    @pytest.mark.asyncio
    async def test_shell_tool_ast_tripwire(self):
        service = HarnessEvolutionService(MagicMock())
        patch = await service.propose_mutation({"step_type": "action", "tool": "shell"})
        assert patch["target_component"] == "ast_tripwire"
        assert "rm -rf /" in patch["mutation_payload"]["blocked_patterns"]

    @pytest.mark.asyncio
    async def test_run_command_tool_ast_tripwire(self):
        service = HarnessEvolutionService(MagicMock())
        patch = await service.propose_mutation({"step_type": "action", "tool": "run_command"})
        assert patch["target_component"] == "ast_tripwire"

    @pytest.mark.asyncio
    async def test_thought_step_system_prompt(self):
        service = HarnessEvolutionService(MagicMock())
        patch = await service.propose_mutation({"step_type": "thought", "tool": "browser"})
        assert patch["target_component"] == "system_prompt"
        assert "Always justify tool parameters" in patch["mutation_payload"]["instruction_append"]

    @pytest.mark.asyncio
    async def test_default_context_compaction(self):
        service = HarnessEvolutionService(MagicMock())
        patch = await service.propose_mutation({"step_type": "action", "tool": "browser"})
        assert patch["target_component"] == "context_compaction"
        assert patch["patch_id"] == "patch_action_browser"


class TestValidateMutationInSandbox:
    def _service(self):
        return HarnessEvolutionService(MagicMock())

    @pytest.mark.asyncio
    async def test_test_fn_success(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1", "target_component": "x"}, str(tmp_path),
            test_fn=lambda p: True)
        assert ok is True

    @pytest.mark.asyncio
    async def test_test_fn_failure_rolls_back(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1", "target_component": "x"}, str(tmp_path),
            test_fn=lambda p: False)
        assert ok is False
        # sandbox snapshot removed after rollback
        assert not (tmp_path / ".sandbox_snapshots").exists()

    @pytest.mark.asyncio
    async def test_default_validation_pass(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1", "target_component": "context_compaction",
             "mutation_payload": {"max_token_limit": 4096}}, str(tmp_path))
        assert ok is True

    @pytest.mark.asyncio
    async def test_default_validation_danger_pattern(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1", "target_component": "context_compaction",
             "mutation_payload": {"instruction": "disable sandbox now"}}, str(tmp_path))
        assert ok is False

    @pytest.mark.asyncio
    async def test_default_validation_missing_patch_id(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"target_component": "x"}, str(tmp_path))
        assert ok is False

    @pytest.mark.asyncio
    async def test_default_validation_missing_target(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1"}, str(tmp_path))
        assert ok is False

    @pytest.mark.asyncio
    async def test_default_validation_protected_key(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1", "target_component": "governance_config",
             "mutation_payload": {}}, str(tmp_path))
        assert ok is False

    @pytest.mark.asyncio
    async def test_harness_patches_key_allowed(self, tmp_path):
        service = self._service()
        ok = await service.validate_mutation_in_sandbox(
            {"patch_id": "p1", "target_component": "harness_patches",
             "mutation_payload": {}}, str(tmp_path))
        assert ok is True

    @pytest.mark.asyncio
    async def test_governance_unavailable_does_not_block(self, tmp_path):
        service = self._service()
        with patch.dict("sys.modules", {"core.agent_governance_service": None}):
            ok = await service.validate_mutation_in_sandbox(
                {"patch_id": "p1", "target_component": "context_compaction"}, str(tmp_path))
        assert ok is True

    @pytest.mark.asyncio
    async def test_sandbox_failure_returns_false(self):
        service = self._service()
        with patch.object(harness_mod, "SandboxTransaction") as MockTx:
            MockTx.return_value.__enter__.side_effect = RuntimeError("sandbox broken")
            ok = await service.validate_mutation_in_sandbox(
                {"patch_id": "p1", "target_component": "x"}, "/nonexistent/dir")
        assert ok is False


class TestDefaultPatchValidation:
    @pytest.mark.asyncio
    async def test_direct_validation(self):
        service = HarnessEvolutionService(MagicMock())
        assert service._default_patch_validation({"patch_id": "p", "target_component": "x"}) is True
        assert service._default_patch_validation({}) is False
        assert service._default_patch_validation({"patch_id": "p"}) is False
        assert service._default_patch_validation(
            {"patch_id": "p", "target_component": "elevated_privileges"}) is False
        assert service._default_patch_validation(
            {"patch_id": "p", "target_component": "x", "payload": "remove tripwire"}) is False


class TestDeployHarnessPatch:
    def _service(self, agent):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        return HarnessEvolutionService(db), db

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = HarnessEvolutionService(db)
        assert await service.deploy_harness_patch({"patch_id": "p1"}, "ghost") is False
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_deploy_new_patch(self):
        agent = AgentRegistry(id="a1", name="A", category="Ops", type="personal",
                              module_path="m", class_name="C", status=AgentStatus.AUTONOMOUS)
        agent.configuration = None
        service, db = self._service(agent)
        patch = {"patch_id": "p1", "target_component": "context_compaction"}
        assert await service.deploy_harness_patch(patch, "a1") is True
        assert agent.configuration["harness_patches"] == [patch]
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_replaces_same_patch_id(self):
        agent = AgentRegistry(id="a1", name="A", category="Ops", type="personal",
                              module_path="m", class_name="C", status=AgentStatus.AUTONOMOUS)
        agent.configuration = {"harness_patches": [
            {"patch_id": "p1", "target_component": "old"},
            {"patch_id": "p2", "target_component": "keep"},
        ]}
        service, db = self._service(agent)
        new_patch = {"patch_id": "p1", "target_component": "new"}
        assert await service.deploy_harness_patch(new_patch, "a1") is True
        ids = [p["patch_id"] for p in agent.configuration["harness_patches"]]
        assert ids == ["p2", "p1"]
        assert agent.configuration["harness_patches"][-1]["target_component"] == "new"

    @pytest.mark.asyncio
    async def test_rollback_snapshot_recorded(self):
        agent = AgentRegistry(id="a1", name="A", category="Ops", type="personal",
                              module_path="m", class_name="C", status=AgentStatus.AUTONOMOUS)
        agent.configuration = {}
        service, db = self._service(agent)
        snapshot = MagicMock()
        snapshot.snapshot.return_value = "mut-42"
        with patch("core.auto_dev.mutation_rollback.get_rollback_registry", return_value=snapshot):
            hp = {"patch_id": "p1", "target_component": "x"}
            assert await service.deploy_harness_patch(hp, "a1") is True
        snapshot.snapshot.assert_called_once()
        assert hp["_rollback_mutation_id"] == "mut-42"

    @pytest.mark.asyncio
    async def test_rollback_registry_failure_never_blocks(self):
        agent = AgentRegistry(id="a1", name="A", category="Ops", type="personal",
                              module_path="m", class_name="C", status=AgentStatus.AUTONOMOUS)
        agent.configuration = {}
        service, db = self._service(agent)
        with patch("core.auto_dev.mutation_rollback.get_rollback_registry",
                   side_effect=RuntimeError("registry down")):
            hp = {"patch_id": "p1", "target_component": "x"}
            assert await service.deploy_harness_patch(hp, "a1") is True
        assert "_rollback_mutation_id" not in hp
        db.commit.assert_called_once()
