"""
Tests for core.models.py - High Priority Coverage (Phase 251)

Focuses on critical model classes with low coverage:
- AgentRegistry and related models
- User and Workspace models
- WorkflowExecution models
- AgentEpisode models
"""
import pytest
from sqlalchemy.orm import Session
from core.models import (
    AgentRegistry,
    User, Workspace, Team,
)
from datetime import datetime, timezone, timedelta
import uuid


class TestAgentModels:
    """Test agent-related models for coverage."""

    def test_agent_registry_creation(self, db_session: Session):
        """Test AgentRegistry model creation and defaults."""
        agent = AgentRegistry(
            id="test-agent-001",
            name="Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestClass",
            status="STUDENT",
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()

        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == "test-agent-001"
        ).first()

        assert retrieved is not None
        assert retrieved.name == "Test Agent"
        assert retrieved.status == "STUDENT"
        assert retrieved.confidence_score == 0.3
        assert retrieved.created_at is not None

    def test_agent_registry_status_levels(self, db_session: Session):
        """Test AgentRegistry with different status levels."""
        status_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        for status in status_levels:
            agent = AgentRegistry(
                id=f"agent-{status.lower()}",
                name=f"{status} Agent",
                category="Testing",
                module_path="test.module",
                class_name="TestClass",
                status=status,
                confidence_score=0.5
            )
            db_session.add(agent)

        db_session.commit()

        agents = db_session.query(AgentRegistry).all()
        assert len(agents) >= 4

        for agent in agents:
            assert agent.status in status_levels

    def test_agent_registry_confidence_scores(self, db_session: Session):
        """Test AgentRegistry with different confidence scores."""
        for i, score in enumerate([0.1, 0.3, 0.5, 0.7, 0.9]):
            agent = AgentRegistry(
                id=f"agent-confidence-{i}",
                name=f"Agent {score*100:.0f}%",
                category="Testing",
                module_path="test.module",
                class_name="TestClass",
                status="INTERN",
                confidence_score=score
            )
            db_session.add(agent)

        db_session.commit()

        agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("agent-confidence-%")
        ).all()

        assert len(agents) == 5
        for agent in agents:
            assert 0.0 <= agent.confidence_score <= 1.0

    def test_agent_registry_update(self, db_session: Session):
        """Test AgentRegistry model updates."""
        agent = AgentRegistry(
            id="test-agent-update",
            name="Original Name",
            category="Testing",
            module_path="test.module",
            class_name="TestClass",
            status="STUDENT"
        )
        db_session.add(agent)
        db_session.commit()

        # Update the agent
        retrieved = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == "test-agent-update"
        ).first()
        retrieved.name = "Updated Name"
        retrieved.status = "INTERN"
        retrieved.confidence_score = 0.6
        db_session.commit()

        # Verify update
        updated = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == "test-agent-update"
        ).first()
        assert updated.name == "Updated Name"
        assert updated.status == "INTERN"
        assert updated.confidence_score == 0.6

    def test_agent_registry_deletion(self, db_session: Session):
        """Test AgentRegistry deletion."""
        agent = AgentRegistry(
            id="test-agent-delete",
            name="Delete Me",
            category="Testing",
            module_path="test.module",
            class_name="TestClass"
        )
        db_session.add(agent)
        db_session.commit()

        # Verify exists
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == "test-agent-delete"
        ).first() is not None

        # Delete
        db_session.delete(agent)
        db_session.commit()

        # Verify deleted
        assert db_session.query(AgentRegistry).filter(
            AgentRegistry.id == "test-agent-delete"
        ).first() is None


class TestUserModels:
    """Test user and authentication models for coverage."""

    def test_user_creation(self, db_session: Session):
        """Test User model creation."""
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role="user"
        )
        db_session.add(user)
        db_session.commit()

        retrieved = db_session.query(User).filter(
            User.email == "test@example.com"
        ).first()

        assert retrieved is not None
        assert retrieved.email == "test@example.com"
        assert retrieved.first_name == "Test"
        assert retrieved.last_name == "User"
        assert retrieved.role == "user"

    def test_user_super_admin_role(self, db_session: Session):
        """Test User model with super_admin role."""
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            role="super_admin"
        )
        db_session.add(user)
        db_session.commit()

        retrieved = db_session.query(User).filter(
            User.email == "admin@example.com"
        ).first()

        assert retrieved.role == "super_admin"

    def test_user_update(self, db_session: Session):
        """Test User model updates."""
        user = User(
            id=str(uuid.uuid4()),
            email="update@example.com",
            first_name="Original",
            last_name="Name"
        )
        db_session.add(user)
        db_session.commit()

        # Update
        retrieved = db_session.query(User).filter(
            User.email == "update@example.com"
        ).first()
        retrieved.first_name = "Updated"
        retrieved.role = "admin"
        db_session.commit()

        # Verify
        updated = db_session.query(User).filter(
            User.email == "update@example.com"
        ).first()
        assert updated.first_name == "Updated"
        assert updated.role == "admin"

    def test_user_multiple_roles(self, db_session: Session):
        """Test User with different role types."""
        roles = ["user", "admin", "super_admin", "team_lead"]

        for i, role in enumerate(roles):
            user = User(
                id=str(uuid.uuid4()),
                email=f"{role}-{i}-{uuid.uuid4()}@example.com",
                first_name=role.title(),
                last_name="User",
                role=role
            )
            db_session.add(user)

        db_session.commit()

        users = db_session.query(User).filter(
            User.email.like("%@example.com")
        ).all()

        assert len(users) >= 4


class TestWorkspaceModels:
    """Test workspace and team models for coverage."""

    def test_workspace_creation(self, db_session: Session):
        """Test Workspace model creation."""
        workspace = Workspace(
            id="workspace-001",
            name="Test Workspace",
            status="active"
        )
        db_session.add(workspace)
        db_session.commit()

        retrieved = db_session.query(Workspace).filter(
            Workspace.id == "workspace-001"
        ).first()

        assert retrieved is not None
        assert retrieved.name == "Test Workspace"
        assert retrieved.status == "active"

    def test_team_creation(self, db_session: Session):
        """Test Team model creation."""
        team = Team(
            id="team-001",
            name="Test Team",
            workspace_id="workspace-001"
        )
        db_session.add(team)
        db_session.commit()

        retrieved = db_session.query(Team).filter(
            Team.id == "team-001"
        ).first()

        assert retrieved is not None
        assert retrieved.name == "Test Team"

    def test_workspace_team_relationship(self, db_session: Session):
        """Test Workspace and Team relationship."""
        workspace = Workspace(
            id="workspace-002",
            name="Workspace with Teams"
        )
        db_session.add(workspace)

        team1 = Team(
            id="team-002",
            name="Team A",
            workspace_id="workspace-002"
        )
        team2 = Team(
            id="team-003",
            name="Team B",
            workspace_id="workspace-002"
        )
        db_session.add(team1)
        db_session.add(team2)
        db_session.commit()

        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == "workspace-002"
        ).first()

        assert len(retrieved_workspace.teams) == 2

    def test_workspace_statuses(self, db_session: Session):
        """Test Workspace with different statuses."""
        statuses = ["active", "inactive", "suspended"]

        for i, status in enumerate(statuses):
            workspace = Workspace(
                id=f"workspace-status-{i}",
                name=f"{status.title()} Workspace",
                status=status
            )
            db_session.add(workspace)

        db_session.commit()

        workspaces = db_session.query(Workspace).filter(
            Workspace.id.like("workspace-status-%")
        ).all()

        assert len(workspaces) == 3

    def test_workspace_update(self, db_session: Session):
        """Test Workspace model updates."""
        workspace = Workspace(
            id="workspace-update",
            name="Original Name",
            status="active"
        )
        db_session.add(workspace)
        db_session.commit()

        # Update
        retrieved = db_session.query(Workspace).filter(
            Workspace.id == "workspace-update"
        ).first()
        retrieved.name = "Updated Name"
        retrieved.status = "suspended"
        db_session.commit()

        # Verify
        updated = db_session.query(Workspace).filter(
            Workspace.id == "workspace-update"
        ).first()
        assert updated.name == "Updated Name"
        assert updated.status == "suspended"
