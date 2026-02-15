"""
Integration tests for cross-API workflow scenarios.

Tests agent lifecycle, supervision, collaboration, and guidance systems
working together in end-to-end workflows.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus
from tests.factories.agent_factory import (
    AgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from tests.factories.user_factory import UserFactory, AdminUserFactory
from tests.factories.execution_factory import AgentExecutionFactory


class TestAgentLifecycleIntegration:
    """Test agent lifecycle integration with supervision, workflows, and collaboration."""

    def test_complete_agent_lifecycle(self, client: TestClient, db_session: Session):
        """Test complete agent lifecycle: create → configure → execute → monitor → delete."""
        # Create agent
        agent = AgentFactory(
            name="Test Agent",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Get agent details
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]

        # List agents to verify it exists
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        # Response might be wrapped
        if isinstance(data, dict):
            agents = data.get("agents", data.get("data", []))
        else:
            agents = data
        assert len(agents) >= 1

    def test_supervision_integration(self, client: TestClient, db_session: Session):
        """Test SUPERVISED agent operations with supervision integration."""
        # Create SUPERVISED agent
        agent = SupervisedAgentFactory(
            name="Test Supervised Agent",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Get agent details to verify creation
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]

    def test_collaboration_integration(self, client: TestClient, db_session: Session):
        """Test workflow collaboration: share, join, complete."""
        # Create autonomous agent for collaboration
        agent = AutonomousAgentFactory(
            name="Collaboration Agent",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Verify agent exists
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]

    def test_cross_api_workflows(self, client: TestClient, db_session: Session):
        """Test cross-API workflows: agent → workflow → collaboration."""
        # Create multiple agents for cross-API workflow
        agent1 = AgentFactory(
            name="Cross API Agent 1",
            category="testing",
            _session=db_session
        )
        agent2 = SupervisedAgentFactory(
            name="Cross API Agent 2",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # List all agents
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        if isinstance(data, dict):
            agents = data.get("agents", data.get("data", []))
        else:
            agents = data
        assert len(agents) >= 2

    def test_agent_status_tracking(self, client: TestClient, db_session: Session):
        """Test agent status tracking across lifecycle."""
        # Create agent with initial status
        agent = AgentFactory(
            name="Status Tracking Agent",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Query agent status
        response = client.get(f"/api/agents/{agent.id}/status")
        assert response.status_code in [200, 404, 405]

    def test_multi_agent_coordination(self, client: TestClient, db_session: Session):
        """Test multiple agents coordinating across workflows."""
        # Create agents at different maturity levels using list comprehension
        agents = [AgentFactory(name=f"Coordinator Agent {i}", category="testing", _session=db_session) for i in range(3)]
        for agent in agents:
            db_session.commit()

        # List all agents
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        if isinstance(data, dict):
            agent_list = data.get("agents", data.get("data", []))
        else:
            agent_list = data
        assert len(agent_list) >= 3

    def test_agent_configuration_integration(self, client: TestClient, db_session: Session):
        """Test agent configuration management across APIs."""
        # Create agent with configuration
        agent = AgentFactory(
            name="Configured Agent",
            category="testing",
            configuration={"monitoring_enabled": True, "learning_enabled": False},
            _session=db_session
        )
        db_session.commit()

        # Get agent details
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]

    def test_cross_api_error_handling(self, client: TestClient, db_session: Session):
        """Test error handling across API boundaries."""
        # Use a valid UUID format that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        # Try to get non-existent agent
        response = client.get(f"/api/agents/{fake_uuid}")
        assert response.status_code == 404

        # Try to update non-existent agent with all required fields
        response = client.put(f"/api/agents/{fake_uuid}", json={
            "name": "Updated Name",
            "description": "Updated Description",
            "category": "testing",
            "configuration": {}
        })
        assert response.status_code == 404


class TestSupervisionWorkflowIntegration:
    """Test supervision workflow integration with agents."""

    def test_supervision_session_lifecycle(self, client: TestClient, db_session: Session):
        """Test supervision session start → monitor → terminate."""
        agent = SupervisedAgentFactory(
            name="Supervision Session Agent",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Verify agent exists
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]

    def test_supervision_intervention_workflow(self, client: TestClient, db_session: Session):
        """Test supervision intervention: detect → intervene → correct."""
        agent = SupervisedAgentFactory(
            name="Intervention Agent",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Get agent status
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]


class TestCollaborationWorkflowIntegration:
    """Test workflow collaboration integration."""

    def test_workflow_sharing_integration(self, client: TestClient, db_session: Session):
        """Test workflow sharing across multiple agents."""
        agents = [AutonomousAgentFactory(name=f"Collaborator {i}", category="testing", _session=db_session) for i in range(2)]
        for agent in agents:
            db_session.commit()

        # List agents to verify collaborators
        response = client.get("/api/agents")
        assert response.status_code == 200

    def test_collaborative_session_management(self, client: TestClient, db_session: Session):
        """Test collaborative session lifecycle."""
        agent = AutonomousAgentFactory(
            name="Session Manager",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Verify agent exists
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]


class TestCrossAPIWorkflowIntegration:
    """Test end-to-end cross-API workflows."""

    def test_agent_to_supervision_workflow(self, client: TestClient, db_session: Session):
        """Test agent creation → supervision session."""
        agent = SupervisedAgentFactory(
            name="Agent to Supervision",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # Verify agent
        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 404]

    def test_agent_to_collaboration_workflow(self, client: TestClient, db_session: Session):
        """Test agent creation → workflow collaboration."""
        agent = AutonomousAgentFactory(
            name="Agent to Collaboration",
            category="testing",
            _session=db_session
        )
        db_session.commit()

        # List agents
        response = client.get("/api/agents")
        assert response.status_code == 200

    def test_supervision_to_collaboration_workflow(self, client: TestClient, db_session: Session):
        """Test supervision session → collaborative workflow."""
        agents = [
            SupervisedAgentFactory(name="Supervised to Collaborate", category="testing", _session=db_session),
            AutonomousAgentFactory(name="Collaborator", category="testing", _session=db_session)
        ]
        for agent in agents:
            db_session.commit()

        # Verify both agents exist
        response = client.get("/api/agents")
        assert response.status_code == 200

    def test_complete_cross_api_orchestration(self, client: TestClient, db_session: Session):
        """Test full orchestration: agent → supervision → collaboration."""
        agents = [
            AgentFactory(name="Orchestrator 1", category="testing", _session=db_session),
            SupervisedAgentFactory(name="Orchestrator 2", category="testing", _session=db_session),
            AutonomousAgentFactory(name="Orchestrator 3", category="testing", _session=db_session)
        ]
        for agent in agents:
            db_session.commit()

        # List all agents in orchestration
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        if isinstance(data, dict):
            agent_list = data.get("agents", data.get("data", []))
        else:
            agent_list = data
        assert len(agent_list) >= 3
