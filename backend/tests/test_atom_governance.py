
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.atom_meta_agent import AtomMetaAgent
from core.database import SessionLocal
from core.models import AgentRegistry, AgentStatus


@pytest.mark.asyncio
async def test_atom_governance_gating():
    db = SessionLocal()
    try:
        # 1. Ensure "atom_main" is in registry as a "Student" for testing gating
        db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").delete()
        agent_model = AgentRegistry(
            id="atom_main",
            name="Atom",
            status=AgentStatus.STUDENT.value,
            category="Meta",
            module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent",
            confidence_score=0.1
        )
        db.add(agent_model)
        db.commit()
        
        atom = AtomMetaAgent()
        
        # "delete_file" (complexity 4) should be blocked for level 0 Student
        result = await atom._step_act("delete_file", {"path": "/tmp/test"}, {})
        
        assert "Governance Error" in result
        assert "maturity" in result.lower()
        
    finally:
        # Restore atom_main to autonomous for other tests
        db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").delete()
        autonomous_atom = AgentRegistry(
            id="atom_main",
            name="Atom",
            status=AgentStatus.AUTONOMOUS.value,
            category="Meta",
            module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent",
            confidence_score=1.0
        )
        db.add(autonomous_atom)
        db.commit()
        db.close()

@pytest.mark.asyncio
async def test_atom_learning_progression():
    db = SessionLocal()
    try:
        # 1. Setup Atom as a Student with specific confidence
        db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").delete()
        agent_model = AgentRegistry(
            id="atom_main",
            name="Atom",
            status=AgentStatus.STUDENT.value,
            category="Meta",
            module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent",
            confidence_score=0.49
        )
        db.add(agent_model)
        db.commit()
        
        atom = AtomMetaAgent()
        # Mock LLM
        atom.llm.generate_response = AsyncMock(return_value="Thought: I should finish.\nFinal Answer: Done.")
        
        # 2. Execute a task
        await atom.execute("Test task")
        
        # 3. Verify confidence increased and status evolved (0.49 + 0.01 = 0.5 -> INTERN)
        db.refresh(agent_model)
        assert agent_model.confidence_score >= 0.5
        assert agent_model.status == AgentStatus.INTERN.value
        
    finally:
        db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").delete()
        autonomous_atom = AgentRegistry(
            id="atom_main",
            name="Atom",
            status=AgentStatus.AUTONOMOUS.value,
            category="Meta",
            module_path="core.atom_meta_agent",
            class_name="AtomMetaAgent",
            confidence_score=1.0
        )
        db.add(autonomous_atom)
        db.commit()
        db.close()
