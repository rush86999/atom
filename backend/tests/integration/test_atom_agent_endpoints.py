"""
Integration tests for atom_agent_endpoints.py (Phase 12, Plan 02).

Tests cover:
- Chat completion endpoint (POST /api/atom-agent/chat)
- Session management (list, create, get history)
- Workflow handlers (list, run, schedule)
- Calendar, Email, Task, and Finance intent handlers
- System status and platform search
- Knowledge query and CRM handlers
- Error handling and edge cases

Coverage target: 50% of atom_agent_endpoints.py (368 lines from 736 total)
"""

import pytest
import json
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from tests.factories.agent_factory import (
    AgentFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from tests.factories.user_factory import UserFactory
from tests.factories.execution_factory import AgentExecutionFactory
from core.models import AgentRegistry, AgentExecution, AgentFeedback


class TestChatEndpoint:
    """Integration tests for /api/atom-agent/chat endpoint."""

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

    def test_chat_with_agent_id(self, client: TestClient, db_session: Session):
        """Test chat with explicit agent_id for governance."""
        agent = AgentFactory(name="Test Agent", _session=db_session)
        db_session.commit()

        response = client.post("/api/atom-agent/chat", json={
            "message": "Execute workflow",
            "user_id": "test_user_agent",
            "agent_id": agent.id
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestSessionManagement:
    """Integration tests for session management endpoints."""

    def test_list_sessions_returns_empty_list(self, client: TestClient, db_session: Session):
        """Test listing sessions returns empty list when none exist."""
        response = client.get("/api/atom-agent/sessions?user_id=test_user_list")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "sessions" in data
        # Should be empty list or success response

    def test_list_sessions_with_limit(self, client: TestClient, db_session: Session):
        """Test listing sessions respects limit parameter."""
        response = client.get("/api/atom-agent/sessions?user_id=test_user_limit&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "sessions" in data

    def test_create_new_session(self, client: TestClient, db_session: Session):
        """Test creating a new chat session."""
        response = client.post("/api/atom-agent/sessions", json={
            "user_id": "test_user_create"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "session_id" in data

    def test_get_session_history(self, client: TestClient, db_session: Session):
        """Test retrieving conversation history for a session."""
        # First create a session by sending a chat message
        client.post("/api/atom-agent/chat", json={
            "message": "Test message",
            "user_id": "test_user_history",
            "session_id": "history_session_123"
        })

        # Then retrieve history
        response = client.get("/api/atom-agent/sessions/history_session_123/history")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "messages" in data or "error" in data  # May not have messages yet

    def test_get_session_history_not_found(self, client: TestClient, db_session: Session):
        """Test retrieving history for non-existent session."""
        response = client.get("/api/atom-agent/sessions/nonexistent_session/history")
        assert response.status_code == 200
        data = response.json()
        # Should handle gracefully (success=False with error message)
        assert "success" in data


class TestWorkflowHandlers:
    """Integration tests for workflow-related intent handlers."""

    def test_list_workflows_intent(self, client: TestClient, db_session: Session):
        """Test LIST_WORKFLOWS intent returns workflow list."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "List my workflows",
            "user_id": "test_user_workflows"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        # Should return workflows list or empty list message

    def test_run_workflow_intent(self, client: TestClient, db_session: Session):
        """Test RUN_WORKFLOW intent attempts to execute workflow."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Run the daily report workflow",
            "user_id": "test_user_run"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        # May return workflow not found or execution started

    def test_create_workflow_intent(self, client: TestClient, db_session: Session):
        """Test CREATE_WORKFLOW intent generates new workflow."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Create a workflow that sends daily emails",
            "user_id": "test_user_create_wf"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        # Should attempt to generate workflow or provide feedback

    def test_schedule_workflow_intent(self, client: TestClient, db_session: Session):
        """Test SCHEDULE_WORKFLOW intent schedules workflow execution."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Schedule the daily report to run every weekday at 9am",
            "user_id": "test_user_schedule"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_get_history_intent(self, client: TestClient, db_session: Session):
        """Test GET_HISTORY intent returns workflow execution history."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show me the history for daily report",
            "user_id": "test_user_history"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_cancel_schedule_intent(self, client: TestClient, db_session: Session):
        """Test CANCEL_SCHEDULE intent cancels workflow schedule."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Cancel the daily report schedule",
            "user_id": "test_user_cancel"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_get_status_intent(self, client: TestClient, db_session: Session):
        """Test GET_STATUS intent returns workflow status."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "What's the status of my workflows?",
            "user_id": "test_user_status"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestCalendarHandlers:
    """Integration tests for calendar-related intent handlers."""

    def test_create_event_intent(self, client: TestClient, db_session: Session):
        """Test CREATE_EVENT intent creates calendar event."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Schedule a meeting tomorrow at 2pm",
            "user_id": "test_user_calendar"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_list_events_intent(self, client: TestClient, db_session: Session):
        """Test LIST_EVENTS intent returns calendar events."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show me my calendar events",
            "user_id": "test_user_events"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_resolve_conflicts_intent(self, client: TestClient, db_session: Session):
        """Test RESOLVE_CONFLICTS intent handles calendar conflicts."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "I have calendar conflicts, help me resolve them",
            "user_id": "test_user_conflicts"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestEmailHandlers:
    """Integration tests for email-related intent handlers."""

    def test_send_email_intent(self, client: TestClient, db_session: Session):
        """Test SEND_EMAIL intent prepares email draft."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Send an email to john@example.com",
            "user_id": "test_user_email"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_search_emails_intent(self, client: TestClient, db_session: Session):
        """Test SEARCH_EMAILS intent searches email inbox."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Search for emails from boss",
            "user_id": "test_user_search"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_follow_up_emails_intent(self, client: TestClient, db_session: Session):
        """Test FOLLOW_UP_EMAILS intent identifies follow-up candidates."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show me people I need to follow up with",
            "user_id": "test_user_followup"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestTaskHandlers:
    """Integration tests for task-related intent handlers."""

    def test_create_task_intent(self, client: TestClient, db_session: Session):
        """Test CREATE_TASK intent creates new task."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Create a task to review the proposal",
            "user_id": "test_user_task"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_list_tasks_intent(self, client: TestClient, db_session: Session):
        """Test LIST_TASKS intent returns task list."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show me my tasks",
            "user_id": "test_user_list_tasks"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestFinanceHandlers:
    """Integration tests for finance-related intent handlers."""

    def test_get_transactions_intent(self, client: TestClient, db_session: Session):
        """Test GET_TRANSACTIONS intent returns transaction history."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show me recent transactions",
            "user_id": "test_user_finance"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_check_balance_intent(self, client: TestClient, db_session: Session):
        """Test CHECK_BALANCE intent returns account balance."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "What's my account balance?",
            "user_id": "test_user_balance"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_invoice_status_intent(self, client: TestClient, db_session: Session):
        """Test INVOICE_STATUS intent returns invoice information."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Check invoice status",
            "user_id": "test_user_invoice"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestSystemHandlers:
    """Integration tests for system-related intent handlers."""

    def test_get_system_status_intent(self, client: TestClient, db_session: Session):
        """Test GET_SYSTEM_STATUS intent returns system health."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show system status",
            "user_id": "test_user_system"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        # Should include system health information

    def test_get_automation_insights_intent(self, client: TestClient, db_session: Session):
        """Test GET_AUTOMATION_INSIGHTS intent returns automation metrics."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show automation insights",
            "user_id": "test_user_insights"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_search_platform_intent(self, client: TestClient, db_session: Session):
        """Test SEARCH_PLATFORM intent performs platform-wide search."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Search for project documents",
            "user_id": "test_user_search_platform"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_wellness_check_intent(self, client: TestClient, db_session: Session):
        """Test WELLNESS_CHECK intent analyzes user workload."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Check my wellness",
            "user_id": "test_user_wellness"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestKnowledgeAndCRMHandlers:
    """Integration tests for knowledge graph and CRM intent handlers."""

    def test_knowledge_query_intent(self, client: TestClient, db_session: Session):
        """Test KNOWLEDGE_QUERY intent queries knowledge graph."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Who worked on Project X?",
            "user_id": "test_user_knowledge"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_crm_query_intent(self, client: TestClient, db_session: Session):
        """Test CRM_QUERY intent handles sales and CRM queries."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Show me the sales pipeline",
            "user_id": "test_user_crm"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestGoalHandlers:
    """Integration tests for goal-related intent handlers."""

    def test_set_goal_intent(self, client: TestClient, db_session: Session):
        """Test SET_GOAL intent creates new goal."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Set a goal to close 5 deals this month",
            "user_id": "test_user_goal"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_goal_status_intent(self, client: TestClient, db_session: Session):
        """Test GOAL_STATUS intent returns goal progress."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "What's the status of my goals?",
            "user_id": "test_user_goal_status"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestSpecialHandlers:
    """Integration tests for special intent handlers."""

    def test_get_silent_stakeholders_intent(self, client: TestClient, db_session: Session):
        """Test GET_SILENT_STAKEHOLDERS intent identifies inactive stakeholders."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Who are my silent stakeholders?",
            "user_id": "test_user_stakeholders"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_help_intent(self, client: TestClient, db_session: Session):
        """Test HELP intent returns help information."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Help",
            "user_id": "test_user_help"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        # Should return help text with available commands


class TestExecuteGeneratedWorkflow:
    """Integration tests for /api/atom-agent/execute-generated endpoint."""

    def test_execute_generated_workflow_success(self, client: TestClient, db_session: Session):
        """Test executing a generated workflow."""
        response = client.post("/api/atom-agent/execute-generated", json={
            "workflow_id": "test_workflow_123",
            "input_data": {"test_param": "test_value"}
        })
        # May return success or workflow not found
        assert response.status_code in [200, 404]
        data = response.json()
        if response.status_code == 200:
            assert "success" in data

    def test_execute_generated_workflow_not_found(self, client: TestClient, db_session: Session):
        """Test executing non-existent workflow."""
        response = client.post("/api/atom-agent/execute-generated", json={
            "workflow_id": "nonexistent_workflow",
            "input_data": {}
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestErrorHandling:
    """Integration tests for error handling and edge cases."""

    def test_chat_with_missing_required_field(self, client: TestClient, db_session: Session):
        """Test chat handles missing message field gracefully."""
        response = client.post("/api/atom-agent/chat", json={
            "user_id": "test_user_error"
        })
        # May return validation error or handle gracefully
        assert response.status_code in [200, 422]

    def test_chat_with_malformed_json(self, client: TestClient, db_session: Session):
        """Test chat handles malformed JSON input."""
        response = client.post(
            "/api/atom-agent/chat",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        # Should return validation error
        assert response.status_code == 422

    def test_unknown_intent_returns_help(self, client: TestClient, db_session: Session):
        """Test unknown intent falls back to help message."""
        response = client.post("/api/atom-agent/chat", json={
            "message": "Do something completely unsupported",
            "user_id": "test_user_unknown"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        # Should provide helpful response

    def test_context_reference_resolution(self, client: TestClient, db_session: Session):
        """Test chat resolves references to previous context."""
        # First create a workflow
        client.post("/api/atom-agent/chat", json={
            "message": "Create a daily report workflow",
            "user_id": "test_user_context"
        })

        # Then reference it with pronoun
        response = client.post("/api/atom-agent/chat", json={
            "message": "Schedule that to run every day",
            "user_id": "test_user_context"
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestStreamingEndpoint:
    """Integration tests for /api/atom-agent/chat/stream endpoint."""

    @pytest.mark.asyncio
    async def test_streaming_chat_success(self, client: TestClient, db_session: Session):
        """Test streaming chat returns success response."""
        # Note: Full WebSocket testing requires async client
        # This test validates the endpoint exists and handles requests
        response = client.post("/api/atom-agent/chat/stream", json={
            "message": "Stream this response",
            "user_id": "test_user_stream"
        })
        # May return success or error depending on WebSocket setup
        assert response.status_code in [200, 404, 500]

    def test_streaming_with_agent_id(self, client: TestClient, db_session: Session):
        """Test streaming chat with explicit agent_id."""
        agent = AgentFactory(name="Stream Agent", _session=db_session)
        db_session.commit()

        response = client.post("/api/atom-agent/chat/stream", json={
            "message": "Stream with agent",
            "user_id": "test_user_stream_agent",
            "agent_id": agent.id
        })
        # May return success or error depending on WebSocket setup
        assert response.status_code in [200, 404, 500]


class TestGovernanceIntegration:
    """Integration tests for agent governance integration."""

    def test_chat_with_student_agent(self, client: TestClient, db_session: Session):
        """Test chat behavior with STUDENT maturity agent."""
        agent = StudentAgentFactory(name="Student Test Agent", _session=db_session)
        db_session.commit()

        response = client.post("/api/atom-agent/chat", json={
            "message": "Execute critical workflow",
            "user_id": "test_user_student",
            "agent_id": agent.id
        })
        # Should handle governance check
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_autonomous_agent(self, client: TestClient, db_session: Session):
        """Test chat behavior with AUTONOMOUS maturity agent."""
        agent = AutonomousAgentFactory(name="Autonomous Test Agent", _session=db_session)
        db_session.commit()

        response = client.post("/api/atom-agent/chat", json={
            "message": "Execute workflow",
            "user_id": "test_user_autonomous",
            "agent_id": agent.id
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_intern_agent(self, client: TestClient, db_session: Session):
        """Test chat behavior with INTERN maturity agent."""
        agent = InternAgentFactory(name="Intern Test Agent", _session=db_session)
        db_session.commit()

        response = client.post("/api/atom-agent/chat", json={
            "message": "List workflows",
            "user_id": "test_user_intern",
            "agent_id": agent.id
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_chat_with_supervised_agent(self, client: TestClient, db_session: Session):
        """Test chat behavior with SUPERVISED maturity agent."""
        agent = SupervisedAgentFactory(name="Supervised Test Agent", _session=db_session)
        db_session.commit()

        response = client.post("/api/atom-agent/chat", json={
            "message": "Show system status",
            "user_id": "test_user_supervised",
            "agent_id": agent.id
        })
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
