import asyncio
from contextlib import contextmanager
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from core.agent_governance_service import AgentGovernanceService
from core.generic_agent import GenericAgent
from core.models import AgentRegistry, AgentStatus


@pytest.fixture
def fresh_db():
    """Hermetic in-memory DB — the shared dev DB is recreated per run with a
    drifting schema (R71 documented the agent_registry column drift), so these
    tests must never touch it."""
    from core.database import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session
    engine.dispose()


@contextmanager
def _session_ctx(session_factory):
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@patch('core.generic_agent.LLMService')
@pytest.mark.asyncio
async def test_agent_governance_gating(mock_llm, fresh_db, monkeypatch):
    db = fresh_db()
    monkeypatch.setattr("core.generic_agent.get_db_session", lambda: _session_ctx(fresh_db))
    try:
        db.query(AgentRegistry).filter(AgentRegistry.id == "test-student-id").delete()
        agent_model = AgentRegistry(
            id="test-student-id",
            name="Test Student Agent",
            status=AgentStatus.STUDENT.value,
            category="General",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            confidence_score=0.1,
            workspace_id="default",
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


@patch('core.generic_agent.LLMService')
@pytest.mark.asyncio
async def test_agent_learning_progression(mock_llm, fresh_db, monkeypatch):
    # Note: GenericAgent.execute opens its own sessions via get_db_session —
    # the monkeypatch routes them to the hermetic in-memory DB. The memory/
    # recall chain (agent_world_model) opens sessions via its own
    # SessionLocal import — redirect those too so no shared dev DB (with
    # drifting schema) is ever touched.
    db = fresh_db()
    monkeypatch.setattr("core.generic_agent.get_db_session", lambda: _session_ctx(fresh_db))
    monkeypatch.setattr("core.agent_world_model.SessionLocal", fresh_db)
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
            confidence_score=0.48,  # Just below Intern (0.5)
            workspace_id="default",
            configuration={"max_steps": 1}
        )
        db.add(agent_model)
        db.commit()

        agent = GenericAgent(agent_model)

        # Allow the episode-budget spend gate (real BudgetEnforcementService
        # blocks on the hermetic DB's empty tenant budget state).
        agent._check_budget_before_react = AsyncMock(
            return_value={"allowed": True, "reason": "test"}
        )

        # Mock the LLM: structured path returns a real ReActStep ending the
        # loop; raw path returns a final answer.
        from core.react_models import ReActStep

        agent.llm = MagicMock()
        agent.llm.generate_structured = AsyncMock(
            return_value=ReActStep(thought="Done.", final_answer="Task complete.")
        )
        agent.llm.generate = AsyncMock(
            return_value="Thought: Done.\nFinal Answer: Task complete."
        )

        # Execute task
        await agent.execute("Simple task")

        # Verify confidence increased
        db.refresh(agent_model)
        assert agent_model.confidence_score > 0.48
        # Since impact is low (0.01), 0.48 + 0.01 = 0.49. Still Student.

        # Run again to cross the score hurdle — the R86b evidence gate now
        # holds the tier at STUDENT: score drips alone must not promote
        # (alignment fix; see _resolve_promotion). Evidence arrives via the
        # training-session/graduation paths, not outcome hooks.
        await agent.execute("Another task")
        db.refresh(agent_model)
        assert agent_model.confidence_score >= 0.5
        assert agent_model.status == AgentStatus.STUDENT.value

    finally:
        db.query(AgentRegistry).filter(AgentRegistry.id == "learning-agent-id").delete()
        db.commit()
        db.close()
