
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.database import SessionLocal
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentStatus


@pytest.mark.asyncio
async def test_agent_governance_gating():
    db = SessionLocal()
    try:
        # 1. Create a "Student" agent registry model in DB
        db.query(AgentRegistry).filter(AgentRegistry.id == "test-student-id").delete()
        agent_model = AgentRegistry(
            id="test-student-id",
            name="Test Student Agent",
            status=AgentStatus.STUDENT.value,
            category="General",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            confidence_score=0.1,
            configuration={"tools": "*"}
        )
        db.add(agent_model)
        db.commit()
        
        agent = GenericAgent(agent_model)
        
        # "delete_file" has complexity 4 (requires Autonomous)
        # Student (level 0) should be blocked.
        result = await agent._step_act("delete_file", {"path": "/etc/shadow"})
        
        assert "Governance Error" in result
        assert "lacks maturity" in result.lower()
    finally:
        db.query(AgentRegistry).filter(AgentRegistry.id == "test-student-id").delete()
        db.commit()
        db.close()

@pytest.mark.asyncio
async def test_agent_learning_progression():
    # Note: This test requires a real DB entry because GenericAgent.execute 
    # creates its own DB sessions to update registry via GovernanceService
    db = SessionLocal()
    try:
        # Cleanup if exists
        db.query(AgentRegistry).filter(AgentRegistry.id == "learning-agent-id").delete()
        
        agent_model = AgentRegistry(
            id="learning-agent-id",
            name="Learning Agent",
            status=AgentStatus.STUDENT.value,
            category="General",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            confidence_score=0.48, # Just below Intern (0.5)
            configuration={"max_steps": 1}
        )
        db.add(agent_model)
        db.commit()
        
        agent = GenericAgent(agent_model)
        
        # Mock LLM to return final answer immediately
        agent.llm.generate_response = AsyncMock(return_value="Thought: Done.\nFinal Answer: Task complete.")
        
        # Execute task
        await agent.execute("Simple task")
        
        # Verify confidence increased
        db.refresh(agent_model)
        assert agent_model.confidence_score > 0.48
        # Since impact is low (0.01), 0.48 + 0.01 = 0.49. Still Student.
        
        # Run again to cross hurdle
        await agent.execute("Another task")
        db.refresh(agent_model)
        assert agent_model.confidence_score >= 0.5
        assert agent_model.status == AgentStatus.INTERN.value
        
    finally:
        db.query(AgentRegistry).filter(AgentRegistry.id == "learning-agent-id").delete()
        db.commit()
        db.close()
