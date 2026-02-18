
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.atom_meta_agent import AtomMetaAgent
from core.database import SessionLocal
from core.models import AgentRegistry, AgentStatus


@pytest.mark.asyncio
async def test_atom_governance_gating():
    """Test that STUDENT agents are blocked from high-complexity actions via governance service"""
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

        # 2. Test governance service directly
        gov = AgentGovernanceService(db)

        # Check that "delete" action (complexity 4) is blocked for STUDENT
        auth_check = gov.can_perform_action("atom_main", "delete_file")

        assert not auth_check["allowed"], "STUDENT agent should not be allowed to delete files"
        assert "maturity" in auth_check["reason"].lower(), "Block reason should mention maturity level"

        # Check that read action (complexity 1) is allowed for STUDENT
        read_check = gov.can_perform_action("atom_main", "read_file")

        assert read_check["allowed"], "STUDENT agent should be allowed to read files"

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
    """Test that AtomMetaAgent.execute() works and uses correct API (no _step_act)"""
    from unittest.mock import patch
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    # Use in-memory DB to avoid atom_dev.db state issues and mapper initialization problems
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    db = TestSessionLocal()
    try:
        # Setup agent
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

        # Mock LLM - uses correct AtomMetaAgent.llm.generate_response API
        atom.llm.generate_response = AsyncMock(return_value="Thought: I should finish.\nFinal Answer: Done.")

        # Patch AgentGovernanceService.record_outcome to avoid UsageEvent mapper
        # This is more effective than patching _record_execution because it prevents
        # the mapper initialization issue at the source
        with patch('core.agent_governance_service.AgentGovernanceService.record_outcome', new_callable=AsyncMock):
            # Execute a task using AtomMetaAgent.execute() - NOT _step_act
            result = await atom.execute("Test task")

            # Verify execution completed successfully
            assert result is not None, "execute() should return a result"
            assert "status" in result, "Result should have status field"
            assert result["status"] == "success", f"Execution should succeed, got status: {result.get('status')}"
            atom.llm.generate_response.assert_called_once()

    finally:
        # Cleanup
        db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").delete()
        db.commit()
        db.close()
        engine.dispose()
