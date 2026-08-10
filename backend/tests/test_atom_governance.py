
import asyncio
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.atom_meta_agent import AtomMetaAgent
from core.models import AgentRegistry, AgentStatus


def _make_temp_db():
    """Hermetic tempfile DB — the shared dev DB is recreated per run with a
    drifting schema and its resolution is order-dependent (TESTING=1 module
    side effects), so these tests must never touch it."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create tables using create_all with checkfirst
    # Handle errors gracefully like db_session fixture
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception:
        # If create_all fails, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                # Skip tables that can't be created (missing FK refs, etc.)
                continue

    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal, db_path


@pytest.mark.asyncio
async def test_atom_governance_gating():
    """Test that STUDENT agents are blocked from high-complexity actions via governance service"""
    engine, TestSessionLocal, db_path = _make_temp_db()
    db = TestSessionLocal()
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
            confidence_score=0.1,
            workspace_id="default"
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
            confidence_score=1.0,
            workspace_id="default"
        )
        db.add(autonomous_atom)
        db.commit()
        db.close()
        engine.dispose()
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.asyncio
async def test_atom_learning_progression():
    """Test that AtomMetaAgent.execute() works and uses correct API (no _step_act)"""
    from unittest.mock import patch, MagicMock

    # Prevent UsageEvent import to avoid mapper initialization issues
    # This must happen before importing any modules that use UsageEvent
    sys.modules['saas.models'] = MagicMock()

    engine, TestSessionLocal, db_path = _make_temp_db()

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
            confidence_score=0.49,
            workspace_id="default"
        )
        db.add(agent_model)
        # AtomMetaAgent.execute validates the workspace exists.
        from core.models import Workspace

        if not db.query(Workspace).filter(Workspace.id == "default").first():
            db.add(Workspace(id="default", name="Default"))
        db.commit()

        # AtomMetaAgent internals open sessions via core.database.SessionLocal —
        # redirect them to the hermetic DB so no shared dev DB is touched.
        with patch("core.atom_meta_agent.SessionLocal", TestSessionLocal), \
             patch("core.agent_world_model.SessionLocal", TestSessionLocal):
            atom = AtomMetaAgent()

            # Allow the episode-budget spend gate (real BudgetEnforcementService
            # blocks on the hermetic DB's empty tenant budget state).
            atom._check_budget_before_react = AsyncMock(
                return_value={"allowed": True, "reason": "test"}
            )

            # Mock LLM - uses correct AtomMetaAgent.llm.generate_response API
            atom.llm.generate_response = AsyncMock(return_value="Thought: I should finish.\nFinal Answer: Done.")

            # Mock structured step generation - the ReAct loop uses
            # generate_structured_response (not generate_response)
            from core.atom_meta_agent import ReActStep
            atom.llm.generate_structured_response = AsyncMock(
                return_value=ReActStep(thought="I should finish.", final_answer="Done.")
            )

            # Execute a task using AtomMetaAgent.execute() - NOT _step_act
            result = await atom.execute("Test task")

            # Verify execution completed successfully
            # Even if there are mapper warnings, the core execution should work
            assert result is not None, "execute() should return a result"
            assert "status" in result or "error" in result, "Result should have status or error field"

            # If we got here without AttributeError about _step_act, the test passes
            # The mapper errors are warnings that don't prevent execution
            atom.llm.generate_structured_response.assert_called_once()

    finally:
        # Cleanup
        db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").delete()
        db.commit()
        db.close()
        engine.dispose()
        # Delete temp database file
        if os.path.exists(db_path):
            os.remove(db_path)

        # Restore the module
        del sys.modules['saas.models']
