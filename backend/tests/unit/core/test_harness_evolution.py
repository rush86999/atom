import pytest
from unittest.mock import MagicMock, patch
import json
import os
import tempfile

from core.harness_evolution_service import HarnessEvolutionService
from core.models import AgentRegistry, AgentReasoningStep

@pytest.mark.asyncio
async def test_weakness_mining_collects_failures():
    db = MagicMock()
    
    # Mock database query for AgentReasoningStep
    step_1 = AgentReasoningStep(
        id="step_1",
        tenant_id="t1",
        step_type="action",
        action={"tool": "shell", "cmd": "rm -rf /"},
        verified="failed_verification",
        feedback_score=-1
    )
    step_2 = AgentReasoningStep(
        id="step_2",
        tenant_id="t1",
        step_type="thought",
        action=None,
        verified="unverified",
        feedback_score=-1
    )
    db.query().filter().all.return_value = [step_1, step_2]

    service = HarnessEvolutionService(db=db)
    patterns = await service.mine_weaknesses(tenant_id="t1")

    assert len(patterns) == 2
    # Verify groupings by key
    grouped_tools = {p["tool"] for p in patterns}
    assert "shell" in grouped_tools
    assert "unknown" in grouped_tools


@pytest.mark.asyncio
async def test_mutation_proposal_selects_type():
    db = MagicMock()
    service = HarnessEvolutionService(db=db)

    # Test tool mutation selection
    pattern_shell = {"tool": "shell", "step_type": "action"}
    patch_shell = await service.propose_mutation(pattern_shell)
    assert patch_shell["target_component"] == "ast_tripwire"

    # Test thought mutation selection
    pattern_thought = {"tool": "unknown", "step_type": "thought"}
    patch_thought = await service.propose_mutation(pattern_thought)
    assert patch_thought["target_component"] == "system_prompt"


@pytest.mark.asyncio
async def test_sandbox_validation_respects_outcomes():
    db = MagicMock()
    service = HarnessEvolutionService(db=db)
    
    patch_data = {"patch_id": "p1", "target_component": "system_prompt"}
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test validation pass
        pass_test = lambda p: True
        success = await service.validate_mutation_in_sandbox(
            patch=patch_data,
            workspace_dir=tmp_dir,
            test_fn=pass_test
        )
        assert success is True

        # Test validation fail
        fail_test = lambda p: False
        failure = await service.validate_mutation_in_sandbox(
            patch=patch_data,
            workspace_dir=tmp_dir,
            test_fn=fail_test
        )
        assert failure is False


@pytest.mark.asyncio
async def test_patch_deployment_persists_to_agent_config():
    db = MagicMock()
    agent = AgentRegistry(
        id="agent1",
        name="Test Agent",
        configuration={}
    )
    db.query().filter().first.return_value = agent
    
    service = HarnessEvolutionService(db=db)
    patch_data = {
        "patch_id": "patch_thought_unknown",
        "target_component": "system_prompt",
        "mutation_payload": {"append": "Be concise"},
        "model_scope": "all"
    }

    with patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag:
        success = await service.deploy_harness_patch(patch_data, agent_id="agent1")
        
        assert success is True
        assert len(agent.configuration["harness_patches"]) == 1
        assert agent.configuration["harness_patches"][0]["patch_id"] == "patch_thought_unknown"
        mock_flag.assert_called_once_with(agent, "configuration")
        db.commit.assert_called_once()
