"""Tests for the unified evolution pipeline facade.

Phase 3 of the harness evolution gap closure. Covers: governance gate
rejection, daily limit check, rollback snapshot creation, verify, and
rollback flow.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.auto_dev.evolution_pipeline import (
    MutationRequest,
    PipelineResult,
    UnifiedEvolutionPipeline,
)


@pytest.fixture
def pipeline():
    # NOTE: fixture upgraded for the daily-limit wiring fix (see
    # test_bughunt_autodev_comms.py) — the pipeline now calls
    # check_daily_limits(agent_id, capability, settings) with a mapped
    # capability, so the magic-mock db must behave like an empty store
    # (no workspace, no mutations) instead of exploding on the query chain.
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    return UnifiedEvolutionPipeline(db=db)


def _make_request(**kwargs):
    defaults = dict(
        agent_id="a1",
        tenant_id="t1",
        source="alpha_evolver",
        config_key="system_prompt",
        old_value="old prompt",
        new_value="new prompt",
    )
    defaults.update(kwargs)
    return MutationRequest(**defaults)


@pytest.mark.asyncio
async def test_valid_mutation_passes(pipeline):
    """A valid mutation with no danger patterns passes the pipeline."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    assert result.passed is True
    assert result.stage == "validated"


@pytest.mark.asyncio
async def test_governance_rejection_blocks(pipeline):
    """A mutation rejected by governance is blocked before deployment."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=False),
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    assert result.passed is False
    assert result.stage == "governance"


@pytest.mark.asyncio
async def test_daily_limit_exceeded_blocks(pipeline):
    """A mutation exceeding the daily limit is blocked."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=False,
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    assert result.passed is False
    assert result.stage == "daily_limit"


@pytest.mark.asyncio
async def test_rollback_snapshot_created(pipeline):
    """A passing mutation creates a rollback snapshot."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=True,
    ):
        result = await pipeline.submit_and_deploy(_make_request())
    assert result.passed is True
    assert result.rollback_mutation_id is not None


@pytest.mark.asyncio
async def test_rollback_restores_config(pipeline):
    """Rollback restores the old config value."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=True,
    ):
        result = await pipeline.submit_and_deploy(_make_request())
        config = {"system_prompt": "new prompt"}
        ok = await pipeline.rollback(result.rollback_mutation_id, config)
    assert ok is True
    assert config["system_prompt"] == "old prompt"


@pytest.mark.asyncio
async def test_verify_marks_mutation(pipeline):
    """Verify marks a mutation as passed regression validation."""
    with patch(
        "core.agent_governance_service.AgentGovernanceService.validate_evolution_directive",
        new=AsyncMock(return_value=True),
    ), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService.check_daily_limits",
        return_value=True,
    ):
        result = await pipeline.submit_and_deploy(_make_request())
        ok = await pipeline.verify(result.rollback_mutation_id)
    assert ok is True


def test_mutation_request_fields():
    req = _make_request(parent_code="old code", mutated_code="new code", test_inputs=[{"x": 1}])
    assert req.agent_id == "a1"
    assert req.parent_code == "old code"
    assert req.test_inputs == [{"x": 1}]


def test_pipeline_result_dataclass():
    r = PipelineResult(mutation_id="m1", passed=True, stage="validated")
    assert r.mutation_id == "m1"
    assert r.passed is True
    assert r.rollback_mutation_id is None
