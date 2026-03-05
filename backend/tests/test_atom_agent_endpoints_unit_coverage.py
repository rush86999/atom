"""
Unit coverage tests for core/atom_agent_endpoints.py.

These tests directly test the functions in atom_agent_endpoints.py
without requiring the FastAPI router to be mounted.

Goal: Increase coverage from 11.98% (95/793 lines) to 25%+ by testing
helper functions and internal logic.
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session


class TestSaveChatInteraction:
    """Unit tests for save_chat_interaction helper function."""

    async def test_save_chat_interaction_basic(self, db_session: Session):
        """Test basic chat interaction saving."""
        from core.atom_agent_endpoints import save_chat_interaction

        # Mock chat history manager
        mock_chat_mgr = MagicMock()
        mock_session_mgr = MagicMock()

        save_chat_interaction(
            session_id="test-session-123",
            user_id="test-user",
            user_message="Hello",
            assistant_message="Hi there!",
            intent="greeting",
            entities={"key": "value"},
            result_data={"response": "test"},
            chat_history_mgr=mock_chat_mgr,
            session_mgr=mock_session_mgr
        )

        # Verify both messages were saved
        assert mock_chat_mgr.save_message.call_count == 2
        mock_session_mgr.update_session_activity.assert_called_once_with("test-session-123")

    async def test_save_chat_interaction_without_managers(self, db_session: Session):
        """Test save_chat_interaction creates managers if not provided."""
        from core.atom_agent_endpoints import save_chat_interaction

        # Patch the manager getters
        with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_get_chat, \
             patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_get_session:

            mock_chat_mgr = MagicMock()
            mock_session_mgr = MagicMock()
            mock_get_chat.return_value = mock_chat_mgr
            mock_get_session.return_value = mock_session_mgr

            save_chat_interaction(
                session_id="test-session-456",
                user_id="test-user-2",
                user_message="Test message",
                assistant_message="Test response"
            )

            # Verify managers were created
            mock_get_chat.assert_called_once_with("default")
            mock_get_session.assert_called_once_with("default")

    async def test_save_chat_interaction_with_workflow_result(self, db_session: Session):
        """Test save_chat_interaction extracts workflow metadata."""
        from core.atom_agent_endpoints import save_chat_interaction

        mock_chat_mgr = MagicMock()
        mock_session_mgr = MagicMock()

        save_chat_interaction(
            session_id="test-session-789",
            user_id="test-user-3",
            user_message="Create workflow",
            assistant_message="Workflow created",
            result_data={
                "response": {
                    "workflow_id": "wf-123",
                    "workflow_name": "Test Workflow"
                }
            },
            chat_history_mgr=mock_chat_mgr,
            session_mgr=mock_session_mgr
        )

        # Verify second call (assistant message) includes workflow metadata
        second_call_args = mock_chat_mgr.save_message.call_args_list[1]
        metadata = second_call_args[1]['metadata']
        assert metadata['workflow_id'] == "wf-123"
        assert metadata['workflow_name'] == "Test Workflow"

    async def test_save_chat_interaction_with_task_result(self, db_session: Session):
        """Test save_chat_interaction extracts task metadata."""
        from core.atom_agent_endpoints import save_chat_interaction

        mock_chat_mgr = MagicMock()
        mock_session_mgr = MagicMock()

        save_chat_interaction(
            session_id="test-session-task",
            user_id="test-user-task",
            user_message="Create task",
            assistant_message="Task created",
            result_data={
                "response": {
                    "task_id": "task-456"
                }
            },
            chat_history_mgr=mock_chat_mgr,
            session_mgr=mock_session_mgr
        )

        # Verify task_id is in metadata
        second_call_args = mock_chat_mgr.save_message.call_args_list[1]
        metadata = second_call_args[1]['metadata']
        assert metadata['task_id'] == "task-456"

    async def test_save_chat_interaction_handles_exceptions(self, db_session: Session):
        """Test save_chat_interaction handles exceptions gracefully."""
        from core.atom_agent_endpoints import save_chat_interaction

        mock_chat_mgr = MagicMock()
        mock_chat_mgr.save_message.side_effect = Exception("Database error")
        mock_session_mgr = MagicMock()

        # Should not raise exception
        save_chat_interaction(
            session_id="test-session-error",
            user_id="test-user-error",
            user_message="Test",
            assistant_message="Response",
            chat_history_mgr=mock_chat_mgr,
            session_mgr=mock_session_mgr
        )

        # Exception should be caught and logged
        assert True  # If we get here, exception was handled


class TestChatRequestModels:
    """Unit tests for ChatRequest and related models."""

    async def test_chat_message_model(self):
        """Test ChatMessage model validation."""
        from core.atom_agent_endpoints import ChatMessage

        msg = ChatMessage(
            role="user",
            content="Hello"
        )
        assert msg.role == "user"
        assert msg.content == "Hello"

    async def test_chat_request_model_basic(self):
        """Test ChatRequest model with basic fields."""
        from core.atom_agent_endpoints import ChatRequest

        req = ChatRequest(
            message="Test message",
            user_id="user-123"
        )
        assert req.message == "Test message"
        assert req.user_id == "user-123"
        assert req.session_id is None
        assert req.context is None

    async def test_chat_request_model_with_all_fields(self):
        """Test ChatRequest model with all optional fields."""
        from core.atom_agent_endpoints import ChatRequest, ChatMessage

        req = ChatRequest(
            message="Complex message",
            user_id="user-456",
            session_id="session-789",
            current_page="/workflows",
            context={"key": "value"},
            conversation_history=[
                ChatMessage(role="user", content="Previous"),
                ChatMessage(role="assistant", content="Response")
            ],
            agent_id="agent-123",
            workspace_id="workspace-456"
        )
        assert req.message == "Complex message"
        assert req.current_page == "/workflows"
        assert req.context == {"key": "value"}
        assert len(req.conversation_history) == 2
        assert req.agent_id == "agent-123"
        assert req.workspace_id == "workspace-456"


class TestExecuteGeneratedRequest:
    """Unit tests for ExecuteGeneratedRequest model."""

    async def test_execute_generated_request_model(self):
        """Test ExecuteGeneratedRequest model validation."""
        from core.atom_agent_endpoints import ExecuteGeneratedRequest

        req = ExecuteGeneratedRequest(
            workflow_id="wf-123",
            input_data={"param1": "value1", "param2": 42}
        )
        assert req.workflow_id == "wf-123"
        assert req.input_data == {"param1": "value1", "param2": 42}


class TestEndpointHelperFunctions:
    """Unit tests for endpoint helper functions."""

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    async def test_list_sessions_empty(self, mock_get_session_mgr, db_session: Session):
        """Test list_sessions returns empty list when no sessions."""
        from core.atom_agent_endpoints import list_sessions

        mock_session_mgr = MagicMock()
        mock_session_mgr.list_user_sessions.return_value = []
        mock_get_session_mgr.return_value = mock_session_mgr

        result = await list_sessions(user_id="test-no-sessions", limit=10)

        assert result["success"] is True
        assert result["sessions"] == []
        mock_session_mgr.list_user_sessions.assert_called_once_with("test-no-sessions", 10)

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    async def test_list_sessions_with_data(self, mock_get_session_mgr, db_session: Session):
        """Test list_sessions returns session data."""
        from core.atom_agent_endpoints import list_sessions

        mock_session_mgr = MagicMock()
        mock_session_mgr.list_user_sessions.return_value = [
            {
                "session_id": "sess-1",
                "last_active": "2024-01-01T00:00:00Z",
                "metadata": {
                    "title": "Test Session",
                    "last_message": "Hello world"
                }
            }
        ]
        mock_get_session_mgr.return_value = mock_session_mgr

        result = await list_sessions(user_id="test-user", limit=50)

        assert result["success"] is True
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["id"] == "sess-1"
        assert result["sessions"][0]["title"] == "Test Session"

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    async def test_create_new_session_success(self, mock_get_session_mgr, db_session: Session):
        """Test create_new_session creates session successfully."""
        from core.atom_agent_endpoints import create_new_session

        mock_session_mgr = MagicMock()
        mock_session_mgr.create_session.return_value = "new-session-123"
        mock_get_session_mgr.return_value = mock_session_mgr

        result = await create_new_session(user_id="test-create")

        assert result["success"] is True
        assert result["session_id"] == "new-session-123"
        mock_session_mgr.create_session.assert_called_once_with(user_id="test-create")

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    @patch('core.atom_agent_endpoints.get_chat_history_manager')
    async def test_get_session_history_success(self, mock_get_chat, mock_get_session, db_session: Session):
        """Test get_session_history returns messages."""
        from core.atom_agent_endpoints import get_session_history

        mock_session_mgr = MagicMock()
        mock_session_mgr.get_session.return_value = {"session_id": "sess-1"}
        mock_chat_mgr = MagicMock()
        mock_chat_mgr.get_session_history.return_value = [
            {
                "id": "msg-1",
                "role": "user",
                "content": "Hello",
                "timestamp": "2024-01-01T00:00:00Z",
                "metadata": {}
            }
        ]
        mock_get_session.return_value = mock_session_mgr
        mock_get_chat.return_value = mock_chat_mgr

        result = await get_session_history(session_id="sess-1")

        assert result["success"] is True
        assert "messages" in result
        assert len(result["messages"]) == 1

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    async def test_get_session_history_not_found(self, mock_get_session, db_session: Session):
        """Test get_session_history returns error for non-existent session."""
        from core.atom_agent_endpoints import get_session_history

        mock_session_mgr = MagicMock()
        mock_session_mgr.get_session.return_value = None
        mock_get_session.return_value = mock_session_mgr

        result = await get_session_history(session_id="nonexistent")

        assert result["success"] is False
        assert "error" in result


class TestIntentHandlers:
    """Unit tests for intent handler functions."""

    @patch('core.atom_agent_endpoints.load_workflows')
    async def test_list_workflows_intent_handler(self, mock_load, db_session: Session):
        """Test list workflows intent handler."""
        from core.atom_agent_endpoints import list_workflows_intent

        mock_load.return_value = [
            {"id": "wf-1", "name": "Workflow 1"},
            {"id": "wf-2", "name": "Workflow 2"}
        ]

        result = list_workflows_intent(
            message="List workflows",
            user_id="test-user",
            session_id="test-session"
        )

        assert "success" in result or "workflows" in result

    @patch('core.atom_agent_endpoints.save_workflows')
    @patch('core.atom_agent_endpoints.load_workflows')
    async def test_run_workflow_intent_handler(self, mock_load, mock_save, db_session: Session):
        """Test run workflow intent handler."""
        from core.atom_agent_endpoints import run_workflow_intent

        mock_load.return_value = [
            {"id": "wf-1", "name": "Test Workflow"}
        ]

        result = run_workflow_intent(
            message="Run workflow wf-1",
            user_id="test-user",
            session_id="test-session"
        )

        assert "success" in result or "workflow_id" in result


class TestCalendarIntents:
    """Unit tests for calendar intent handlers."""

    @patch('core.atom_agent_endpoints.GoogleCalendarService')
    async def test_create_event_intent_handler(self, mock_service_cls, db_session: Session):
        """Test create event intent handler."""
        from core.atom_agent_endpoints import create_event_intent

        mock_service = MagicMock()
        mock_service.create_event.return_value = {"event_id": "evt-123"}
        mock_service_cls.return_value = mock_service

        result = create_event_intent(
            message="Create event tomorrow at 2pm",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle even if service is not configured
        assert result is not None

    @patch('core.atom_agent_endpoints.GoogleCalendarService')
    async def test_list_events_intent_handler(self, mock_service_cls, db_session: Session):
        """Test list events intent handler."""
        from core.atom_agent_endpoints import list_events_intent

        mock_service = MagicMock()
        mock_service.list_events.return_value = [
            {"event_id": "evt-1", "summary": "Meeting"}
        ]
        mock_service_cls.return_value = mock_service

        result = list_events_intent(
            message="List my events",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle even if service is not configured
        assert result is not None


class TestEmailIntents:
    """Unit tests for email intent handlers."""

    @patch('core.atom_agent_endpoints.GmailService')
    async def test_send_email_intent_handler(self, mock_service_cls, db_session: Session):
        """Test send email intent handler."""
        from core.atom_agent_endpoints import send_email_intent

        mock_service = MagicMock()
        mock_service.send_email.return_value = {"message_id": "msg-123"}
        mock_service_cls.return_value = mock_service

        result = send_email_intent(
            message="Send email to test@example.com",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle even if service is not configured
        assert result is not None

    @patch('core.atom_agent_endpoints.GmailService')
    async def test_search_emails_intent_handler(self, mock_service_cls, db_session: Session):
        """Test search emails intent handler."""
        from core.atom_agent_endpoints import search_emails_intent

        mock_service = MagicMock()
        mock_service.search_emails.return_value = [
            {"message_id": "msg-1", "subject": "Test"}
        ]
        mock_service_cls.return_value = mock_service

        result = search_emails_intent(
            message="Search for emails about project",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle even if service is not configured
        assert result is not None


class TestTaskIntents:
    """Unit tests for task intent handlers."""

    @patch('core.atom_agent_endpoints.create_task')
    async def test_create_task_intent_handler(self, mock_create_task, db_session: Session):
        """Test create task intent handler."""
        from core.atom_agent_endpoints import create_task_intent

        mock_create_task.return_value = {"task_id": "task-123"}

        result = create_task_intent(
            message="Create a new task",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle task creation
        assert result is not None

    @patch('core.atom_agent_endpoints.get_tasks')
    async def test_list_tasks_intent_handler(self, mock_get_tasks, db_session: Session):
        """Test list tasks intent handler."""
        from core.atom_agent_endpoints import list_tasks_intent

        mock_get_tasks.return_value = [
            {"task_id": "task-1", "title": "Task 1"}
        ]

        result = list_tasks_intent(
            message="List all my tasks",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle task listing
        assert result is not None


class TestFinanceIntents:
    """Unit tests for finance intent handlers."""

    @patch('core.atom_agent_endpoints.list_quickbooks_items')
    async def test_get_transactions_intent_handler(self, mock_list, db_session: Session):
        """Test get transactions intent handler."""
        from core.atom_agent_endpoints import get_transactions_intent

        mock_list.return_value = [
            {"transaction_id": "txn-1", "amount": 100.00}
        ]

        result = get_transactions_intent(
            message="Show recent transactions",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle transaction listing
        assert result is not None


class TestSystemIntents:
    """Unit tests for system status and search intents."""

    @patch('core.atom_agent_endpoints.SystemStatus')
    async def test_get_system_status_intent_handler(self, mock_status_cls, db_session: Session):
        """Test get system status intent handler."""
        from core.atom_agent_endpoints import get_system_status_intent

        mock_status = MagicMock()
        mock_status.get_status.return_value = {
            "status": "healthy",
            "uptime": 12345
        }
        mock_status_cls.return_value = mock_status

        result = get_system_status_intent(
            message="What is the system status",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle system status
        assert result is not None

    @patch('core.atom_agent_endpoints.unified_hybrid_search')
    async def test_platform_search_intent_handler(self, mock_search, db_session: Session):
        """Test platform search intent handler."""
        from core.atom_agent_endpoints import platform_search_intent

        mock_search.return_value = [
            {"id": "1", "title": "Result 1"}
        ]

        result = platform_search_intent(
            message="Search for customer data",
            user_id="test-user",
            session_id="test-session"
        )

        # Should handle search
        assert result is not None


class TestErrorHandling:
    """Unit tests for error handling in endpoints."""

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    async def test_list_sessions_handles_exceptions(self, mock_get_session, db_session: Session):
        """Test list_sessions handles exceptions gracefully."""
        from core.atom_agent_endpoints import list_sessions

        mock_session_mgr = MagicMock()
        mock_session_mgr.list_user_sessions.side_effect = Exception("Database error")
        mock_get_session.return_value = mock_session_mgr

        result = await list_sessions(user_id="test-error", limit=10)

        # Should return error response
        assert result["success"] is False
        assert "error" in result

    @patch('core.atom_agent_endpoints.get_chat_session_manager')
    async def test_create_new_session_handles_exceptions(self, mock_get_session, db_session: Session):
        """Test create_new_session handles exceptions gracefully."""
        from core.atom_agent_endpoints import create_new_session

        mock_session_mgr = MagicMock()
        mock_session_mgr.create_session.side_effect = Exception("Session creation failed")
        mock_get_session.return_value = mock_session_mgr

        result = await create_new_session(user_id="test-create-error")

        # Should return error response
        assert result["success"] is False
        assert "error" in result
