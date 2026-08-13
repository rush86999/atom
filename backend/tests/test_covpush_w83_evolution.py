# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/evolution_pipeline.py to >=95% (all safety gates
mocked; zero LLM spend, zero network, no real DB).

Covers:
- MutationRequest / PipelineResult dataclasses.
- submit_and_deploy: governance gate (pass / reject / raise), daily limit gate
  (pass / reject / raise), regression (skipped for config-only, pass, fail,
  raise), rollback snapshot (success / best-effort failure), success path.
- rollback(): success / exception.
- verify(): success / exception.
- _get_workspace_settings: found with metadata, found without, missing,
  exception.
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.evolution_pipeline import (
    MutationRequest,
    PipelineResult,
    UnifiedEvolutionPipeline,
)


class _FakeDb:
    """Minimal query/filter chain for Workspace lookups."""

    def __init__(self, workspace=None, raise_on_query=False):
        self.workspace = workspace
        self.raise_on_query = raise_on_query

    def query(self, model):
        workspace = self.workspace
        raise_on_query = self.raise_on_query

        class _Q:
            def filter(self, *a, **k):
                return self

            def first(self):
                if raise_on_query:
                    raise RuntimeError("db exploded")
                return workspace

        return _Q()


def _request(**over):
    defaults = dict(
        agent_id="agent-1",
        tenant_id="tenant-1",
        source="alpha_evolver",
        config_key="system_prompt",
        old_value="old",
        new_value="new",
    )
    defaults.update(over)
    return MutationRequest(**defaults)


def _pipeline(db=None, sandbox=None):
    return UnifiedEvolutionPipeline(db or _FakeDb(), sandbox=sandbox)


# ============================================================================
# Governance gate
# ============================================================================

def test_submit_and_deploy_governance_rejects():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=False)
        result = __import__("asyncio").run(pipe.submit_and_deploy(_request()))
    assert result.passed is False
    assert result.stage == "governance"
    assert "rejected" in result.reason


def test_submit_and_deploy_dict_new_value_updates_check_config():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=False)
        gate_cls.return_value.check_daily_limits.return_value = True
        req = _request(config_key="configuration", new_value={"temperature": 0.5})
        __import__("asyncio").run(pipe.submit_and_deploy(req))
    check_config = svc_cls.return_value.validate_evolution_directive.await_args.args[0]
    assert check_config["configuration"] == {"temperature": 0.5}
    assert check_config["temperature"] == 0.5


def test_submit_and_deploy_governance_raises_is_fail_closed():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(
            side_effect=RuntimeError("gov down")
        )
        result = __import__("asyncio").run(pipe.submit_and_deploy(_request()))
    assert result.passed is False
    assert result.stage == "governance"
    assert "Governance check error" in result.reason


# ============================================================================
# Daily limit gate
# ============================================================================

def test_submit_and_deploy_daily_limit_exceeded():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = False
        result = __import__("asyncio").run(pipe.submit_and_deploy(_request(source="memento")))
    assert result.passed is False
    assert result.stage == "daily_limit"
    assert "memento" in result.reason
    # source -> capability mapping: memento must map to the memento capability
    assert gate_cls.return_value.check_daily_limits.call_args[0][1] == "auto_dev.memento_skills"


def test_submit_and_deploy_daily_limit_unknown_source_defaults():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = False
        __import__("asyncio").run(pipe.submit_and_deploy(_request(source="mystery")))
    assert gate_cls.return_value.check_daily_limits.call_args[0][1] == "auto_dev.alpha_evolver"


def test_submit_and_deploy_daily_limit_raises_is_fail_closed():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.side_effect = ValueError("gate broke")
        result = __import__("asyncio").run(pipe.submit_and_deploy(_request()))
    assert result.passed is False
    assert result.stage == "daily_limit"
    assert "Daily limit check error" in result.reason


# ============================================================================
# Regression stage
# ============================================================================

def test_submit_and_deploy_regression_skipped_for_config_only_mutation():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls, \
         patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = True
        reg.return_value.snapshot.return_value = "rb-1"
        result = __import__("asyncio").run(pipe.submit_and_deploy(_request()))
    assert result.passed is True
    assert result.stage == "validated"
    assert result.rollback_mutation_id == "rb-1"
    assert result.mutation_id.startswith("pipe_")


def test_submit_and_deploy_regression_passes_with_injected_sandbox():
    sandbox = MagicMock()
    pipe = _pipeline(sandbox=sandbox)
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls, \
         patch("core.auto_dev.regression_validator.RegressionValidator") as reg_cls, \
         patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = True
        verdict = MagicMock()
        verdict.passed = True
        verdict.mismatches = []
        reg_cls.return_value.validate_regression = AsyncMock(return_value=verdict)
        reg.return_value.snapshot.return_value = "rb-2"
        req = _request(
            parent_code="def f(): return 1",
            mutated_code="def f(): return 2",
            test_inputs=[{"in": 1}],
        )
        result = __import__("asyncio").run(pipe.submit_and_deploy(req))
    assert result.passed is True
    assert reg_cls.return_value.validate_regression.await_args.kwargs["sandbox"] is sandbox


def test_submit_and_deploy_regression_fails():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls, \
         patch("core.auto_dev.regression_validator.RegressionValidator") as reg_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = True
        verdict = MagicMock()
        verdict.passed = False
        verdict.mismatches = [1, 2]
        reg_cls.return_value.validate_regression = AsyncMock(return_value=verdict)
        req = _request(
            parent_code="code", mutated_code="code2",
            test_inputs=[{"in": 1}, {"in": 2}],
        )
        result = __import__("asyncio").run(pipe.submit_and_deploy(req))
    assert result.passed is False
    assert result.stage == "regression"
    assert "2/2 test inputs" in result.reason


def test_submit_and_deploy_regression_raises_is_fail_closed():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls, \
         patch("core.auto_dev.regression_validator.RegressionValidator") as reg_cls:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = True
        reg_cls.return_value.validate_regression = AsyncMock(side_effect=RuntimeError("sandbox dead"))
        req = _request(parent_code="a", mutated_code="b", test_inputs=[{"in": 1}])
        result = __import__("asyncio").run(pipe.submit_and_deploy(req))
    assert result.passed is False
    assert result.stage == "regression"
    assert "Regression validation error" in result.reason


def test_submit_and_deploy_regression_creates_sandbox_when_none():
    pipe = _pipeline(sandbox=None)
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls, \
         patch("core.auto_dev.regression_validator.RegressionValidator") as reg_cls, \
         patch("core.auto_dev.container_sandbox.ContainerSandbox") as sandbox_cls, \
         patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = True
        verdict = MagicMock()
        verdict.passed = True
        reg_cls.return_value.validate_regression = AsyncMock(return_value=verdict)
        reg.return_value.snapshot.return_value = "rb-3"
        req = _request(parent_code="a", mutated_code="b", test_inputs=[{"in": 1}])
        result = __import__("asyncio").run(pipe.submit_and_deploy(req))
    assert result.passed is True
    sandbox_cls.assert_called_once()


# ============================================================================
# Rollback snapshot best-effort
# ============================================================================

def test_submit_and_deploy_snapshot_failure_is_best_effort():
    pipe = _pipeline()
    with patch("core.agent_governance_service.AgentGovernanceService") as svc_cls, \
         patch("core.auto_dev.capability_gate.AutoDevCapabilityService") as gate_cls, \
         patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        svc_cls.return_value.validate_evolution_directive = AsyncMock(return_value=True)
        gate_cls.return_value.check_daily_limits.return_value = True
        reg.return_value.snapshot.side_effect = RuntimeError("registry down")
        result = __import__("asyncio").run(pipe.submit_and_deploy(_request()))
    assert result.passed is True
    assert result.rollback_mutation_id is None


# ============================================================================
# rollback() / verify()
# ============================================================================

def test_rollback_success():
    pipe = _pipeline()
    with patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        reg.return_value.rollback.return_value = True
        assert __import__("asyncio").run(pipe.rollback("m1", {"cfg": 1})) is True
        reg.return_value.rollback.assert_called_once_with("m1", {"cfg": 1})


def test_rollback_exception_returns_false():
    pipe = _pipeline()
    with patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        reg.return_value.rollback.side_effect = RuntimeError("nope")
        assert __import__("asyncio").run(pipe.rollback("m1")) is False


def test_verify_success():
    pipe = _pipeline()
    with patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        reg.return_value.verify.return_value = True
        assert __import__("asyncio").run(pipe.verify("m1")) is True


def test_verify_exception_returns_false():
    pipe = _pipeline()
    with patch("core.auto_dev.mutation_rollback.get_rollback_registry") as reg:
        reg.return_value.verify.side_effect = RuntimeError("nope")
        assert __import__("asyncio").run(pipe.verify("m1")) is False


# ============================================================================
# _get_workspace_settings
# ============================================================================

def test_workspace_settings_returned_when_metadata_present():
    ws = MagicMock()
    ws.metadata_json = {"daily_limits": {"max": 3}}
    pipe = _pipeline(_FakeDb(workspace=ws))
    assert pipe._get_workspace_settings("tenant-1") == {"daily_limits": {"max": 3}}


def test_workspace_settings_empty_when_no_metadata():
    ws = MagicMock()
    ws.metadata_json = None
    pipe = _pipeline(_FakeDb(workspace=ws))
    assert pipe._get_workspace_settings("tenant-1") == {}


def test_workspace_settings_empty_when_missing():
    pipe = _pipeline(_FakeDb(workspace=None))
    assert pipe._get_workspace_settings("tenant-1") == {}


def test_workspace_settings_empty_on_db_error():
    pipe = _pipeline(_FakeDb(raise_on_query=True))
    assert pipe._get_workspace_settings("tenant-1") == {}


def test_pipeline_result_constructor():
    r = PipelineResult(mutation_id="m", passed=False, stage="governance", reason="x")
    assert r.stage == "governance" and r.rollback_mutation_id is None
