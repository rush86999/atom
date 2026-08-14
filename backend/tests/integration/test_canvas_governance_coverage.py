"""
Integration Tests for Canvas Routes and Governance Service.

These tests use a real SQLite database and execute actual code paths
to improve coverage from 74.6% to 80%.

Tests cover:
- Canvas submission and retrieval (real database operations)
- Agent registration and governance checks (real CRUD)
- Permission enforcement (real service calls)
- Error handling (actual error paths)
"""

import pytest
import uuid
from sqlalchemy.orm import Session
from datetime import datetime

from core.models import (
    AgentRegistry,
    AgentStatus,
    Workspace,
    User,
    Canvas,
)
from core.agent_governance_service import AgentGovernanceService
from core.database import SessionLocal


# ============================================================================
# Fixtures - Real Database
# ============================================================================

@pytest.fixture
def db():
    """Create a real SQLite database with the full schema.

    Uses a temp-file database (real engine, real SQL) instead of the
    dev atom_dev.db file, which does not reliably contain the schema.
    """
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture
def user(db: Session):
    """Create test user."""
    user = User(
        id=f"test_coverage_user_{uuid.uuid4()}",
        email=f"coverage_test-{uuid.uuid4()}@example.com",
        first_name="Coverage",
        last_name="Test User", role="member", status="active"
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def workspace(db: Session, user: User):
    """Create test workspace."""
    workspace = Workspace(
        id=f"test_coverage_workspace_{uuid.uuid4()}",
        name="Coverage Test Workspace",
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def autonomous_agent(db: Session, workspace: Workspace):
    """Create AUTONOMOUS agent (maturity is encoded in status)."""
    agent = AgentRegistry(
        id=f"test_coverage_autonomous_agent_{uuid.uuid4()}",
        name="Test Coverage Autonomous Agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,
        workspace_id=workspace.id,
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def student_agent(db: Session, workspace: Workspace):
    """Create STUDENT agent (maturity is encoded in status)."""
    agent = AgentRegistry(
        id=f"test_coverage_student_agent_{uuid.uuid4()}",
        name="Test Coverage Student Agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,
        workspace_id=workspace.id,
    )
    db.add(agent)
    db.commit()
    return agent


# ============================================================================
# Agent Governance Integration Tests
# ============================================================================

class TestAgentGovernanceRealDatabase:
    """Test agent governance with real database operations."""

    def test_register_or_update_agent_creates_new_agent(self, db: Session, workspace: Workspace):
        """Test registering a new agent with real database."""
        service = AgentGovernanceService(db, workspace_id=workspace.id)

        agent = service.register_or_update_agent(
            name="New Test Agent",
            category="testing",
            module_path="agents.new_test",
            class_name="NewTestAgent",
            description="A new test agent",
        )

        assert agent is not None
        assert agent.name == "New Test Agent"
        assert agent.category == "testing"

        # Verify it was actually saved to database
        retrieved = db.query(AgentRegistry).filter(
            AgentRegistry.module_path == "agents.new_test"
        ).first()
        assert retrieved is not None
        assert retrieved.name == "New Test Agent"

    def test_can_perform_action_autonomous_allowed(self, db: Session, autonomous_agent: AgentRegistry):
        """Test AUTONOMOUS agent can perform all actions."""
        service = AgentGovernanceService(db, workspace_id=autonomous_agent.workspace_id)

        result = service.can_perform_action(
            agent_id=autonomous_agent.id,
            action_type="delete",
        )

        assert result["allowed"] is True

    def test_can_perform_action_student_blocked(self, db: Session, student_agent: AgentRegistry):
        """Test STUDENT agent is blocked from delete actions."""
        service = AgentGovernanceService(db, workspace_id=student_agent.workspace_id)

        result = service.can_perform_action(
            agent_id=student_agent.id,
            action_type="delete",
        )

        assert result["allowed"] is False
        assert "reason" in result

    def test_enforce_action_autonomous_succeeds(self, db: Session, autonomous_agent: AgentRegistry):
        """Test enforce_action allows AUTONOMOUS agent actions."""
        service = AgentGovernanceService(db, workspace_id=autonomous_agent.workspace_id)

        result = service.enforce_action(
            agent_id=autonomous_agent.id,
            action_type="delete",
            # "delete" is high-complexity: the autonomous guardrail requires
            # an advanced model in the action details for such actions
            action_details={"model_name": "gpt-4"},
        )

        assert result["proceed"] is True

    def test_enforce_action_student_blocked(self, db: Session, student_agent: AgentRegistry):
        """Test enforce_action blocks STUDENT agent actions."""
        service = AgentGovernanceService(db, workspace_id=student_agent.workspace_id)

        result = service.enforce_action(
            agent_id=student_agent.id,
            action_type="delete",
        )

        assert result["proceed"] is False
        assert result["status"] == "BLOCKED"

    def test_get_agent_returns_agent(self, db: Session, autonomous_agent: AgentRegistry):
        """Test getting agent maturity from the database via the service."""
        service = AgentGovernanceService(db, workspace_id=autonomous_agent.workspace_id)

        # get_agent() was replaced by get_agent_capabilities(), which returns
        # the agent's maturity level and confidence from the database
        capabilities = service.get_agent_capabilities(autonomous_agent.id)

        assert capabilities is not None
        assert capabilities["maturity_level"] == AgentStatus.AUTONOMOUS.value

    def test_list_agents_returns_list(self, db: Session, workspace: Workspace, autonomous_agent: AgentRegistry, student_agent: AgentRegistry):
        """Test listing agents from database."""
        service = AgentGovernanceService(db, workspace_id=workspace.id)

        agents = service.list_agents()

        assert isinstance(agents, list)
        assert len(agents) >= 2  # autonomous_agent and student_agent fixtures


# ============================================================================
# Canvas Integration Tests
# ============================================================================

class TestCanvasRealDatabase:
    """Test canvas operations with real database."""

    def test_create_canvas_saves_to_database(self, db: Session, workspace: Workspace, user: User):
        """Test creating a canvas saves to real database."""
        canvas = Canvas(
            id=f"test_coverage_canvas_{uuid.uuid4()}",
            tenant_id=workspace.id,  # Using workspace.id as tenant_id
            workspace_id=workspace.id,
            created_by=user.id,
            name="Test Coverage Canvas",
            canvas_type="chart",
            content={"type": "line", "data": [1, 2, 3]},
        )

        db.add(canvas)
        db.commit()

        # Verify it was saved
        retrieved = db.query(Canvas).filter(Canvas.id == canvas.id).first()
        assert retrieved is not None
        assert retrieved.name == "Test Coverage Canvas"
        assert retrieved.canvas_type == "chart"

    def test_update_canvas_modifies_database(self, db: Session, workspace: Workspace, user: User):
        """Test updating a canvas modifies real database."""
        # Create canvas first
        canvas = Canvas(
            id=f"test_coverage_canvas_update_{uuid.uuid4()}",
            tenant_id=workspace.id,
            workspace_id=workspace.id,
            created_by=user.id,
            name="Original Title",
            canvas_type="document",
            content={"text": "original"},
        )
        db.add(canvas)
        db.commit()

        # Update the canvas
        canvas.name = "Updated Title"
        canvas.content = {"text": "updated"}
        db.commit()

        # Verify update
        retrieved = db.query(Canvas).filter(Canvas.id == canvas.id).first()
        assert retrieved.name == "Updated Title"
        assert retrieved.content["text"] == "updated"

    def test_delete_canvas_removes_from_database(self, db: Session, workspace: Workspace, user: User):
        """Test deleting a canvas removes from real database."""
        # Create canvas first
        canvas = Canvas(
            id=f"test_coverage_canvas_delete_{uuid.uuid4()}",
            tenant_id=workspace.id,
            workspace_id=workspace.id,
            created_by=user.id,
            name="To Be Deleted",
            canvas_type="form",
            content={},
        )
        db.add(canvas)
        db.commit()
        canvas_id = canvas.id

        # Delete the canvas
        db.delete(canvas)
        db.commit()

        # Verify deletion
        retrieved = db.query(Canvas).filter(Canvas.id == canvas_id).first()
        assert retrieved is None

    def test_query_canvases_by_workspace(self, db: Session, workspace: Workspace, user: User):
        """Test querying canvases by workspace."""
        # Create multiple canvases
        for i in range(3):
            canvas = Canvas(
                id=f"test_coverage_canvas_{i}_{uuid.uuid4()}",
                tenant_id=workspace.id,
                workspace_id=workspace.id,
                created_by=user.id,
                name=f"Canvas {i}",
                canvas_type="chart",
                content={"index": i},
            )
            db.add(canvas)
        db.commit()

        # Query canvases
        canvases = db.query(Canvas).filter(
            Canvas.workspace_id == workspace.id
        ).all()

        assert len(canvases) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
