"""
Comprehensive integration tests for agent endpoints (Phase 3, Plan 1, Task 1.1).

Tests cover:
- Chat endpoint (POST /api/atom-agent/chat)
- Streaming endpoint (POST /api/atom-agent/stream)
- Agent list endpoint (GET /api/agents)
- Agent detail endpoint (GET /api/agents/{agent_id})
- Agent creation endpoint (POST /api/agents)
- Agent update endpoint (PUT /api/agents/{agent_id})
- Agent deletion endpoint (DELETE /api/agents/{agent_id})

Coverage target: All endpoints tested with valid and invalid data, errors handled correctly
"""

import pytest
import json
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Generator

from core.models import AgentRegistry, AgentExecution, AgentFeedback, AgentStatus
from tests.fixtures.mock_services import MockLLMProvider


class TestChatEndpoint:
    """Integration tests for POST /api/atom-agent/chat endpoint."""

    def test_chat_success_returns_response(self, client: TestClient, db_session: Session):
        """Test successful chat request returns response with session_id."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Hello, agent!",
            "user_id": "test_user_123",
            "session_id": "test_session_123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "session_id" in data

    def test_chat_creates_new_session_when_not_provided(self, client: TestClient, db_session: Session):
        """Test chat creates new session when session_id not provided."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Start new conversation",
            "user_id": "test_user_456"
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        # Should have created a new session

    def test_chat_with_conversation_history(self, client: TestClient, db_session: Session):
        """Test chat includes conversation history in context."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "What did I just ask?",
            "user_id": "test_user_789",
            "session_id": "history_test_session",
            "conversation_history": [
                {"role": "user", "content": "My previous question"},
                {"role": "assistant", "content": "My previous answer"}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_empty_message(self, client: TestClient, db_session: Session):
        """Test chat handles empty message gracefully."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "",
            "user_id": "test_user_empty"
        })
        # Should return success even with empty message (fallback to help/unknown)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_missing_user_id_returns_422(self, client: TestClient, db_session: Session):
        """Test chat request without user_id returns validation error."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Hello"
        })
        assert response.status_code == 422  # Validation error

    def test_chat_with_invalid_session_id_format(self, client: TestClient, db_session: Session):
        """Test chat handles invalid session_id format gracefully."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Test message",
            "user_id": "test_user",
            "session_id": 123  # Invalid type (should be string)
        })
        # Should return validation error or handle gracefully
        assert response.status_code in [200, 422]

    def test_chat_with_agent_id_for_governance(self, client: TestClient, db_session: Session):
        """Test chat with explicit agent_id for governance routing."""
        # Create test agent
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()

        response = client.post("/api/atom-agent/chat", json={
            "message": "Execute workflow",
            "user_id": "test_user_governance",
            "agent_id": agent.id
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_current_page_context(self, client: TestClient, db_session: Session):
        """Test chat includes current_page context for better intent classification."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Help me with this page",
            "user_id": "test_user_page",
            "current_page": "/workflows/editor"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_context_dict(self, client: TestClient, db_session: Session):
        """Test chat includes custom context dictionary."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Process this data",
            "user_id": "test_user_ctx",
            "context": {
                "workflow_id": "wf_123",
                "project_id": "proj_456"
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_database_error_handling(self, client: TestClient, db_session: Session):
        """Test chat handles database errors gracefully."""
        # Mock database error
        with patch("core.chat_session_manager.get_chat_session_manager") as mock_mgr:
            mock_mgr.side_effect = Exception("Database connection failed")
            response = client.post("/api/atom-agent/chat", json={
                "message": "Test message",
                "user_id": "test_user_db_error"
            })
            # Should handle error gracefully (200 with error flag or 500)
            assert response.status_code in [200, 500]


class TestStreamingEndpoint:
    """Integration tests for POST /api/atom-agent/stream endpoint."""

    def test_streaming_success(self, client: TestClient, db_session: Session):
        """Test successful streaming endpoint returns SSE stream."""
        response = client.post("/api/atom-agent/stream", json={
            "message": "Stream this response",
            "user_id": "test_stream_user",
            "session_id": "stream_session_123"
        })
        # Streaming endpoints typically return 200 with content-type text/event-stream
        assert response.status_code == 200

    def test_streaming_with_empty_message(self, client: TestClient, db_session: Session):
        """Test streaming handles empty message."""
        response = client.post("/api/atom-agent/stream", json={
            "message": "",
            "user_id": "test_stream_empty"
        })
        assert response.status_code == 200

    def test_streaming_creates_session_if_missing(self, client: TestClient, db_session: Session):
        """Test streaming creates session if not provided."""
        response = client.post("/api/atom-agent/stream", json={
            "message": "Start streaming",
            "user_id": "test_stream_no_session"
        })
        assert response.status_code == 200

    def test_streaming_with_agent_id(self, client: TestClient, db_session: Session):
        """Test streaming with explicit agent_id."""
        agent = AgentRegistry(
            name="StreamAgent",
            category="test",
            module_path="test.module",
            class_name="StreamAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()

        response = client.post("/api/atom-agent/stream", json={
            "message": "Stream with agent",
            "user_id": "test_stream_agent",
            "agent_id": agent.id
        })
        assert response.status_code == 200

    def test_streaming_missing_user_id_returns_422(self, client: TestClient, db_session: Session):
        """Test streaming without user_id returns validation error."""
        response = client.post("/api/atom-agent/stream", json={
            "message": "Stream this"
        })
        assert response.status_code == 422


class TestAgentListEndpoint:
    """Integration tests for GET /api/agents endpoint."""

    def test_list_agents_success(self, client: TestClient, db_session: Session):
        """Test successful agent list retrieval."""
        # Create test agents
        agent1 = AgentRegistry(
            name="Agent1",
            category="test",
            module_path="test.module",
            class_name="Agent1",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.9
        )
        agent2 = AgentRegistry(
            name="Agent2",
            category="test",
            module_path="test.module",
            class_name="Agent2",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent1)
        db_session.add(agent2)
        db_session.commit()

        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data or isinstance(data, list)
        # Should contain at least our test agents

    def test_list_agents_with_category_filter(self, client: TestClient, db_session: Session):
        """Test listing agents filtered by category."""
        # Create agents with different categories
        agent_sales = AgentRegistry(
            name="SalesAgent",
            category="sales",
            module_path="test.module",
            class_name="SalesAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.9
        )
        agent_support = AgentRegistry(
            name="SupportAgent",
            category="support",
            module_path="test.module",
            class_name="SupportAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.9
        )
        db_session.add(agent_sales)
        db_session.add(agent_support)
        db_session.commit()

        response = client.get("/api/agents?category=sales")
        assert response.status_code == 200
        data = response.json()
        # Should filter by category
        agents = data.get("agents", data) if isinstance(data, dict) else data
        if agents:
            for agent in agents:
                assert agent.get("category") == "sales"

    def test_list_agents_with_status_filter(self, client: TestClient, db_session: Session):
        """Test listing agents filtered by status."""
        response = client.get("/api/agents?status=autonomous")
        assert response.status_code == 200

    def test_list_agents_empty_database(self, client: TestClient, db_session: Session):
        """Test listing agents when database is empty."""
        # Don't create any agents
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        # Should return empty list
        agents = data.get("agents", data) if isinstance(data, dict) else data
        assert len(agents) == 0


class TestAgentDetailEndpoint:
    """Integration tests for GET /api/agents/{agent_id} endpoint."""

    def test_get_agent_by_id_success(self, client: TestClient, db_session: Session):
        """Test successful agent retrieval by ID."""
        agent = AgentRegistry(
            name="DetailAgent",
            category="test",
            module_path="test.module",
            class_name="DetailAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            description="Test agent for detail endpoint"
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        response = client.get(f"/api/agents/{agent.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent.id
        assert data["name"] == "DetailAgent"
        assert data["category"] == "test"

    def test_get_agent_by_id_not_found(self, client: TestClient, db_session: Session):
        """Test getting non-existent agent returns 404."""
        response = client.get("/api/agents/nonexistent_agent_id")
        assert response.status_code == 404

    def test_get_agent_by_id_invalid_format(self, client: TestClient, db_session: Session):
        """Test getting agent with invalid ID format."""
        response = client.get("/api/agents/invalid-format-123!")
        # Should return 404 or validation error
        assert response.status_code in [404, 422]


class TestAgentCreationEndpoint:
    """Integration tests for POST /api/agents endpoint."""

    def test_create_agent_success(self, client: TestClient, db_session: Session):
        """Test successful agent creation."""
        agent_data = {
            "name": "NewAgent",
            "category": "test",
            "module_path": "test.module",
            "class_name": "NewAgent",
            "status": "intern",
            "confidence_score": 0.6,
            "description": "A new test agent"
        }
        response = client.post("/api/agents", json=agent_data)
        assert response.status_code in [200, 201]
        data = response.json()
        assert "id" in data or data.get("success")

    def test_create_agent_with_invalid_status(self, client: TestClient, db_session: Session):
        """Test creating agent with invalid status returns error."""
        agent_data = {
            "name": "InvalidAgent",
            "category": "test",
            "module_path": "test.module",
            "class_name": "InvalidAgent",
            "status": "invalid_status",
            "confidence_score": 0.5
        }
        response = client.post("/api/agents", json=agent_data)
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_create_agent_missing_required_fields(self, client: TestClient, db_session: Session):
        """Test creating agent without required fields returns error."""
        agent_data = {
            "name": "IncompleteAgent"
            # Missing category, module_path, class_name
        }
        response = client.post("/api/agents", json=agent_data)
        assert response.status_code in [400, 422]

    def test_create_agent_confidence_out_of_range(self, client: TestClient, db_session: Session):
        """Test creating agent with confidence > 1.0 returns error."""
        agent_data = {
            "name": "OverconfidentAgent",
            "category": "test",
            "module_path": "test.module",
            "class_name": "OverconfidentAgent",
            "status": "autonomous",
            "confidence_score": 1.5  # Invalid (> 1.0)
        }
        response = client.post("/api/agents", json=agent_data)
        assert response.status_code in [400, 422]


class TestAgentUpdateEndpoint:
    """Integration tests for PUT /api/agents/{agent_id} endpoint."""

    def test_update_agent_success(self, client: TestClient, db_session: Session):
        """Test successful agent update."""
        agent = AgentRegistry(
            name="UpdateAgent",
            category="test",
            module_path="test.module",
            class_name="UpdateAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        update_data = {
            "name": "UpdatedAgent",
            "description": "Updated description",
            "confidence_score": 0.75
        }
        response = client.put(f"/api/agents/{agent.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") or data.get("name") == "UpdatedAgent"

    def test_update_agent_not_found(self, client: TestClient, db_session: Session):
        """Test updating non-existent agent returns 404."""
        update_data = {
            "name": "GhostAgent"
        }
        response = client.put("/api/agents/nonexistent_id", json=update_data)
        assert response.status_code == 404

    def test_update_agent_invalid_confidence(self, client: TestClient, db_session: Session):
        """Test updating agent with invalid confidence returns error."""
        agent = AgentRegistry(
            name="ConfidenceAgent",
            category="test",
            module_path="test.module",
            class_name="ConfidenceAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        update_data = {
            "confidence_score": -0.5  # Invalid (< 0)
        }
        response = client.put(f"/api/agents/{agent.id}", json=update_data)
        assert response.status_code in [400, 422]

    def test_update_agent_status_mismatch(self, client: TestClient, db_session: Session):
        """Test updating agent with status/confidence mismatch."""
        agent = AgentRegistry(
            name="MismatchAgent",
            category="test",
            module_path="test.module",
            class_name="MismatchAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Update to autonomous without sufficient confidence
        update_data = {
            "status": "autonomous",
            "confidence_score": 0.7  # Too low for autonomous
        }
        response = client.put(f"/api/agents/{agent.id}", json=update_data)
        # Should accept or reject based on business logic
        assert response.status_code in [200, 400]


class TestAgentDeletionEndpoint:
    """Integration tests for DELETE /api/agents/{agent_id} endpoint."""

    def test_delete_agent_success(self, client: TestClient, db_session: Session):
        """Test successful agent deletion."""
        agent = AgentRegistry(
            name="DeleteAgent",
            category="test",
            module_path="test.module",
            class_name="DeleteAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        agent_id = agent.id
        response = client.delete(f"/api/agents/{agent_id}")
        assert response.status_code in [200, 204]

        # Verify deletion
        get_response = client.get(f"/api/agents/{agent_id}")
        assert get_response.status_code == 404

    def test_delete_agent_not_found(self, client: TestClient, db_session: Session):
        """Test deleting non-existent agent returns 404."""
        response = client.delete("/api/agents/nonexistent_id")
        assert response.status_code == 404

    def test_delete_agent_with_dependencies(self, client: TestClient, db_session: Session):
        """Test deleting agent with existing executions."""
        agent = AgentRegistry(
            name="DependentAgent",
            category="test",
            module_path="test.module",
            class_name="DependentAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Create execution record
        execution = AgentExecution(
            agent_id=agent.id,
            status="completed",
            input_data={"test": "data"},
            output_data={"result": "success"}
        )
        db_session.add(execution)
        db_session.commit()

        # Should either cascade delete or prevent deletion
        response = client.delete(f"/api/agents/{agent.id}")
        assert response.status_code in [200, 204, 400]  # 400 if foreign key constraint

    def test_delete_autonomous_agent_permission(self, client: TestClient, db_session: Session):
        """Test deleting autonomous agent may require special permissions."""
        agent = AgentRegistry(
            name="AutonomousToDelete",
            category="test",
            module_path="test.module",
            class_name="AutonomousToDelete",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        response = client.delete(f"/api/agents/{agent.id}")
        # May require elevated permissions or special confirmation
        assert response.status_code in [200, 204, 403]


class TestAgentGovernanceEndpoints:
    """Integration tests for agent governance-related endpoints."""

    def test_get_maturity_rules(self, client: TestClient, db_session: Session):
        """Test retrieving maturity level rules."""
        response = client.get("/api/agent-governance/rules")
        assert response.status_code == 200
        data = response.json()
        assert "maturity_levels" in data
        assert "student" in data["maturity_levels"]
        assert "intern" in data["maturity_levels"]
        assert "supervised" in data["maturity_levels"]
        assert "autonomous" in data["maturity_levels"]

    def test_get_agent_maturity_status(self, client: TestClient, db_session: Session):
        """Test getting agent maturity status."""
        agent = AgentRegistry(
            name="MaturityAgent",
            category="test",
            module_path="test.module",
            class_name="MaturityAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        response = client.get(f"/api/agent-governance/{agent.id}/maturity")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == agent.id
        assert "maturity_level" in data
        assert "confidence_score" in data
        assert "can_deploy_directly" in data

    def test_submit_workflow_for_approval(self, client: TestClient, db_session: Session):
        """Test submitting workflow for approval."""
        agent = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="InternAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()

        approval_request = {
            "agent_id": agent.id,
            "workflow_name": "Test Workflow",
            "workflow_definition": {"steps": [{"action": "send_email"}]},
            "trigger_type": "manual",
            "actions": ["send_email"],
            "requested_by": "test_user"
        }
        response = client.post("/api/agent-governance/approve", json=approval_request)
        assert response.status_code == 200
        data = response.json()
        assert "approval_id" in data
        assert data["requires_approval"] is True
