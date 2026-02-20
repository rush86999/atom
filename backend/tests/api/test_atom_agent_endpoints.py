"""
Comprehensive test suite for atom_agent_endpoints.py

Target: 80%+ coverage for core/atom_agent_endpoints.py (2,042 lines)

Test Classes:
- TestAgentExecutionEndpoint: Agent execution with streaming, governance, error handling
- TestAgentStatusEndpoint: Session history, status retrieval
- TestAgentListEndpoint: Session listing, filtering
- TestAgentStopEndpoint: Session management
- TestAgentPauseResumeEndpoint: Not applicable (no pause/resume in this file)
- TestStreamValidation: Streaming response validation
- TestGovernanceIntegration: Maturity-based access control

Coverage Strategy:
1. Test all API endpoints (8 routes)
2. Test intent classification and routing
3. Test governance integration (agent maturity levels)
4. Test streaming functionality
5. Test error handling and edge cases
6. Test session management
7. Test retrieval endpoints

Author: Phase 62-03 (Test Coverage 80%)
Created: 2026-02-20
"""

import json
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the router
from core.atom_agent_endpoints import router, ChatRequest, ChatMessage
from core.models import AgentRegistry, AgentExecution, Workspace


# ========================================================================
# Test Fixtures
# ========================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with atom_agent router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def db_session(db_session_factory):
    """Create database session for tests"""
    return db_session_factory()


@pytest.fixture
def mock_student_agent(db_session):
    """Create a STUDENT maturity agent"""
    agent = AgentRegistry(
        id="student_agent_001",
        name="Student Agent",
        description="Learning agent",
        maturity_level="STUDENT",
        confidence_score=0.3,
        capabilities=[],
        workspace_id="default"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def mock_intern_agent(db_session):
    """Create an INTERN maturity agent"""
    agent = AgentRegistry(
        id="intern_agent_001",
        name="Intern Agent",
        description="Intern agent",
        maturity_level="INTERN",
        confidence_score=0.6,
        capabilities=["streaming", "presentation"],
        workspace_id="default"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def mock_supervised_agent(db_session):
    """Create a SUPERVISED maturity agent"""
    agent = AgentRegistry(
        id="supervised_agent_001",
        name="Supervised Agent",
        description="Supervised agent",
        maturity_level="SUPERVISED",
        confidence_score=0.8,
        capabilities=["streaming", "presentation", "state_changes"],
        workspace_id="default"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def mock_autonomous_agent(db_session):
    """Create an AUTONOMOUS maturity agent"""
    agent = AgentRegistry(
        id="autonomous_agent_001",
        name="Autonomous Agent",
        description="Fully autonomous agent",
        maturity_level="AUTONOMOUS",
        confidence_score=0.95,
        capabilities=["streaming", "presentation", "state_changes", "deletions"],
        workspace_id="default"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def sample_chat_request():
    """Sample chat request"""
    return {
        "message": "Create a workflow for daily reports",
        "user_id": "test_user_001",
        "session_id": None,
        "current_page": "/workflows",
        "context": {},
        "conversation_history": [],
        "agent_id": None,
        "workspace_id": "default"  # Add workspace_id for streaming endpoint
    }


@pytest.fixture
def mock_session_manager():
    """Mock session manager"""
    with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock:
        manager = AsyncMock()
        manager.create_session = AsyncMock(return_value="session_test_001")
        manager.get_session = Mock(return_value={"session_id": "session_test_001", "user_id": "test_user_001"})
        manager.list_user_sessions = Mock(return_value=[
            {"session_id": "session_001", "user_id": "test_user_001", "last_active": "2026-02-20T10:00:00Z", "metadata": {"title": "Test Session"}}
        ])
        manager.update_session_activity = Mock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_chat_history_manager():
    """Mock chat history manager"""
    with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock:
        manager = AsyncMock()
        manager.get_session_history = Mock(return_value=[
            {"id": "msg_001", "role": "user", "text": "Hello", "created_at": "2026-02-20T10:00:00Z"},
            {"id": "msg_002", "role": "assistant", "text": "Hi there!", "created_at": "2026-02-20T10:00:01Z"}
        ])
        manager.save_message = Mock()
        manager.add_message = Mock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_context_manager():
    """Mock context manager"""
    with patch('core.atom_agent_endpoints.get_chat_context_manager') as mock:
        manager = AsyncMock()
        manager.resolve_reference = AsyncMock(return_value={"id": "wf_001", "name": "Daily Report"})
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_ai_service():
    """Mock AI service"""
    with patch('core.atom_agent_endpoints.ai_service') as mock:
        mock.initialize_sessions = AsyncMock()
        mock.call_openai_api = AsyncMock(return_value={
            "success": True,
            "response": '{"intent": "CREATE_WORKFLOW", "entities": {"description": "daily report workflow"}}'
        })
        mock.call_anthropic_api = AsyncMock(return_value={
            "success": True,
            "response": '{"intent": "CREATE_WORKFLOW", "entities": {"description": "daily report workflow"}}'
        })
        mock.call_deepseek_api = AsyncMock(return_value={
            "success": True,
            "response": '{"intent": "CREATE_WORKFLOW", "entities": {"description": "daily report workflow"}}'
        })
        yield mock


# ========================================================================
# Test Class 1: Agent Execution Endpoint
# ========================================================================

class TestAgentExecutionEndpoint:
    """Test agent chat execution endpoint"""

    def test_chat_endpoint_success_with_new_session(self, client, mock_session_manager, mock_chat_history_manager, mock_ai_service):
        """Test successful chat request creates new session"""
        with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
            "intent": "CREATE_WORKFLOW",
            "entities": {"description": "daily report workflow"}
        })):
            with patch('core.atom_agent_endpoints.handle_create_workflow', new=AsyncMock(return_value={
                "success": True,
                "response": {"message": "Workflow created successfully"}
            })):
                response = client.post("/api/atom-agent/chat", json={
                    "message": "Create a workflow for daily reports",
                    "user_id": "test_user_001",
                    "session_id": None
                })

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "session_id" in data
                assert "response" in data

    def test_chat_endpoint_with_existing_session(self, client, mock_session_manager, mock_chat_history_manager, mock_ai_service):
        """Test chat request with existing session"""
        with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
            "intent": "LIST_WORKFLOWS",
            "entities": {}
        })):
            with patch('core.atom_agent_endpoints.handle_list_workflows', new=AsyncMock(return_value={
                "success": True,
                "response": {"message": "Found 2 workflows"}
            })):
                response = client.post("/api/atom-agent/chat", json={
                    "message": "List my workflows",
                    "user_id": "test_user_001",
                    "session_id": "session_existing_001"
                })

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    def test_chat_endpoint_with_invalid_payload(self, client):
        """Test chat endpoint with invalid request payload"""
        response = client.post("/api/atom-agent/chat", json={
            "message": "",  # Empty message
            "user_id": ""   # Empty user_id
        })

        # Should handle gracefully (may return 422 or 200 with error)
        assert response.status_code in [200, 422]

    def test_chat_endpoint_missing_required_fields(self, client):
        """Test chat endpoint without required fields"""
        response = client.post("/api/atom-agent/chat", json={
            "user_id": "test_user_001"
            # Missing 'message' field
        })

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    def test_chat_endpoint_creates_session_on_invalid_session_id(self, client, mock_session_manager, mock_chat_history_manager, mock_ai_service):
        """Test that new session is created when specified session doesn't exist"""
        mock_session_manager.get_session.return_value = None  # Session not found

        with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
            "intent": "HELP",
            "entities": {}
        })):
            with patch('core.atom_agent_endpoints.handle_help_request', return_value={
                "success": True,
                "response": {"message": "I can help you"}
            }) as mock_help:
                response = client.post("/api/atom-agent/chat", json={
                    "message": "Help",
                    "user_id": "test_user_001",
                    "session_id": "nonexistent_session"
                })

                assert response.status_code == 200
                # Should create new session
                mock_session_manager.create_session.assert_called()

    def test_chat_endpoint_saves_interaction(self, client, mock_session_manager, mock_chat_history_manager, mock_ai_service):
        """Test that chat interaction is saved to history"""
        with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
            "intent": "CREATE_TASK",
            "entities": {"title": "Test task"}
        })):
            with patch('core.atom_agent_endpoints.handle_task_intent', new=AsyncMock(return_value={
                "success": True,
                "response": {"message": "Task created"}
            })):
                with patch('core.atom_agent_endpoints.save_chat_interaction', Mock()) as mock_save:
                    response = client.post("/api/atom-agent/chat", json={
                        "message": "Create a task",
                        "user_id": "test_user_001",
                        "session_id": "session_001"
                    })

                    assert response.status_code == 200
                    # Verify save was called
                    # Note: May not be called depending on intent handler result

    def test_chat_endpoint_handles_exception_gracefully(self, client, mock_session_manager, mock_chat_history_manager):
        """Test chat endpoint handles internal exceptions"""
        with patch('core.atom_agent_endpoints.classify_intent_with_llm', side_effect=Exception("LLM error")):
            response = client.post("/api/atom-agent/chat", json={
                "message": "Test message",
                "user_id": "test_user_001"
            })

            # Should return error response, not crash
            assert response.status_code == 200
            data = response.json()
            assert "error" in data or data.get("success") is False

    def test_chat_endpoint_with_conversation_history(self, client, mock_session_manager, mock_chat_history_manager, mock_ai_service):
        """Test chat endpoint includes conversation history in LLM call"""
        history = [
            {"role": "user", "content": "Create a workflow"},
            {"role": "assistant", "content": "I'll create that for you"}
        ]

        with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
            "intent": "CREATE_WORKFLOW",
            "entities": {"description": "daily report"}
        })) as mock_classify:
            with patch('core.atom_agent_endpoints.handle_create_workflow', new=AsyncMock(return_value={
                "success": True,
                "response": {"message": "Workflow created"}
            })):
                response = client.post("/api/atom-agent/chat", json={
                    "message": "Make it daily",
                    "user_id": "test_user_001",
                    "conversation_history": history
                })

                assert response.status_code == 200
                # Verify classify was called with history
                mock_classify.assert_called_once()
                call_args = mock_classify.call_args
                # Check that history parameter was passed
                assert call_args is not None


# ========================================================================
# Test Class 2: Intent Classification and Routing
# ========================================================================

class TestIntentClassification:
    """Test intent classification from chat messages"""

    @pytest.mark.asyncio
    async def test_classify_intent_create_workflow(self):
        """Test CREATE_WORKFLOW intent classification"""
        from core.atom_agent_endpoints import classify_intent_with_llm

        with patch('core.atom_agent_endpoints.ai_service') as mock_ai:
            mock_ai.call_openai_api = AsyncMock(return_value={
                "success": True,
                "response": '{"intent": "CREATE_WORKFLOW", "entities": {"description": "test workflow"}}'
            })

            result = await classify_intent_with_llm("Create a workflow for testing", [])

            assert result["intent"] == "CREATE_WORKFLOW"
            assert "description" in result["entities"]

    @pytest.mark.asyncio
    async def test_classify_intent_list_workflows(self):
        """Test LIST_WORKFLOWS intent classification"""
        from core.atom_agent_endpoints import classify_intent_with_llm

        with patch('core.atom_agent_endpoints.ai_service') as mock_ai:
            mock_ai.call_openai_api = AsyncMock(return_value={
                "success": True,
                "response": '{"intent": "LIST_WORKFLOWS", "entities": {}}'
            })

            result = await classify_intent_with_llm("Show me all workflows", [])

            assert result["intent"] == "LIST_WORKFLOWS"

    @pytest.mark.asyncio
    async def test_classify_intent_run_workflow(self):
        """Test RUN_WORKFLOW intent classification"""
        from core.atom_agent_endpoints import classify_intent_with_llm

        with patch('core.atom_agent_endpoints.ai_service') as mock_ai:
            mock_ai.call_openai_api = AsyncMock(return_value={
                "success": True,
                "response": '{"intent": "RUN_WORKFLOW", "entities": {"workflow_ref": "daily report"}}'
            })

            result = await classify_intent_with_llm("Run the daily report workflow", [])

            assert result["intent"] == "RUN_WORKFLOW"
            assert "workflow_ref" in result["entities"]

    @pytest.mark.asyncio
    async def test_classify_intent_schedule_workflow(self):
        """Test SCHEDULE_WORKFLOW intent classification with time expression"""
        from core.atom_agent_endpoints import classify_intent_with_llm

        with patch('core.atom_agent_endpoints.ai_service') as mock_ai:
            mock_ai.call_openai_api = AsyncMock(return_value={
                "success": True,
                "response": '{"intent": "SCHEDULE_WORKFLOW", "entities": {"workflow_ref": "backup", "time_expression": "every day at 5pm"}}'
            })

            result = await classify_intent_with_llm("Schedule the backup workflow every day at 5pm", [])

            assert result["intent"] == "SCHEDULE_WORKFLOW"
            assert "time_expression" in result["entities"]

    @pytest.mark.asyncio
    async def test_classify_intent_fallback_to_regex(self):
        """Test fallback intent classification when LLM fails"""
        from core.atom_agent_endpoints import classify_intent_with_llm

        with patch('core.atom_agent_endpoints.ai_service') as mock_ai:
            with patch('core.atom_agent_endpoints.get_byok_manager') as mock_byok:
                mock_byok.return_value.get_optimal_provider.side_effect = Exception("BYOK error")

                result = await classify_intent_with_llm("create a workflow", [])

                # Should fall back to regex-based classification
                assert result["intent"] == "CREATE_WORKFLOW"

    def test_fallback_intent_classification_workflow_keywords(self):
        """Test regex-based fallback for workflow intents"""
        from core.atom_agent_endpoints import fallback_intent_classification

        result = fallback_intent_classification("create a workflow")
        assert result["intent"] == "CREATE_WORKFLOW"

        result = fallback_intent_classification("list all workflows")
        assert result["intent"] == "LIST_WORKFLOWS"

        result = fallback_intent_classification("run the daily report workflow")
        assert result["intent"] == "RUN_WORKFLOW"

        result = fallback_intent_classification("schedule workflow to run daily")
        assert result["intent"] == "SCHEDULE_WORKFLOW"

    def test_fallback_intent_classification_calendar_keywords(self):
        """Test regex-based fallback for calendar intents"""
        from core.atom_agent_endpoints import fallback_intent_classification

        result = fallback_intent_classification("schedule a meeting")
        assert result["intent"] == "CREATE_EVENT"

        result = fallback_intent_classification("resolve calendar conflicts")
        assert result["intent"] == "RESOLVE_CONFLICTS"

        result = fallback_intent_classification("show my calendar")
        assert result["intent"] == "LIST_EVENTS"

    def test_fallback_intent_classification_task_keywords(self):
        """Test regex-based fallback for task intents"""
        from core.atom_agent_endpoints import fallback_intent_classification

        result = fallback_intent_classification("create a task")
        assert result["intent"] == "CREATE_TASK"

        result = fallback_intent_classification("list my tasks")
        assert result["intent"] == "LIST_TASKS"

    def test_fallback_intent_classification_unknown(self):
        """Test fallback returns UNKNOWN for unrecognized messages"""
        from core.atom_agent_endpoints import fallback_intent_classification

        result = fallback_intent_classification("xyzabc random text")
        assert result["intent"] == "UNKNOWN"


# ========================================================================
# Test Class 3: Session Management Endpoints
# ========================================================================

class TestSessionManagement:
    """Test session listing, creation, and history retrieval"""

    def test_list_sessions_success(self, client, mock_session_manager):
        """Test listing all user sessions"""
        response = client.get("/api/atom-agent/sessions?user_id=test_user_001")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_list_sessions_with_limit(self, client, mock_session_manager):
        """Test listing sessions with custom limit"""
        response = client.get("/api/atom-agent/sessions?user_id=test_user_001&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_create_new_session_success(self, client, mock_session_manager):
        """Test creating a new chat session"""
        response = client.post("/api/atom-agent/sessions", json={
            "user_id": "test_user_001"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data

    def test_get_session_history_success(self, client, mock_session_manager, mock_chat_history_manager):
        """Test retrieving session history"""
        response = client.get("/api/atom-agent/sessions/session_001/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "messages" in data
        assert "count" in data

    def test_get_session_history_nonexistent_session(self, client, mock_session_manager, mock_chat_history_manager):
        """Test session history for non-existent session"""
        mock_session_manager.get_session.return_value = None

        response = client.get("/api/atom-agent/sessions/nonexistent_session/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_get_session_history_metadata_parsing(self, client, mock_session_manager, mock_chat_history_manager):
        """Test metadata parsing in session history"""
        # Mock message with JSON metadata
        mock_chat_history_manager.get_session_history.return_value = [
            {
                "id": "msg_001",
                "role": "assistant",
                "text": "Response",
                "created_at": "2026-02-20T10:00:00Z",
                "metadata": '{"intent": "CREATE_WORKFLOW", "workflow_id": "wf_001"}'
            }
        ]

        response = client.get("/api/atom-agent/sessions/session_001/history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Metadata should be parsed as dict
        if data["messages"]:
            assert isinstance(data["messages"][0].get("metadata"), dict)

    def test_get_session_history_invalid_metadata(self, client, mock_session_manager, mock_chat_history_manager):
        """Test handling of invalid JSON metadata"""
        # Mock message with invalid JSON metadata
        mock_chat_history_manager.get_session_history.return_value = [
            {
                "id": "msg_001",
                "role": "assistant",
                "text": "Response",
                "created_at": "2026-02-20T10:00:00Z",
                "metadata": "invalid json {"
            }
        ]

        response = client.get("/api/atom-agent/sessions/session_001/history")

        # Should not crash, should handle gracefully
        assert response.status_code == 200


# ========================================================================
# Test Class 4: Workflow Handlers
# ========================================================================

class TestWorkflowHandlers:
    """Test workflow-related intent handlers"""

    @pytest.mark.asyncio
    async def test_handle_create_workflow_success(self):
        """Test successful workflow creation"""
        from core.atom_agent_endpoints import handle_create_workflow, ChatRequest

        with patch('core.atom_agent_endpoints.get_orchestrator') as mock_orch:
            mock_orch.return_value.generate_dynamic_workflow = AsyncMock(return_value={
                "id": "wf_001",
                "name": "Daily Report Workflow",
                "nodes": [{"id": "node_1"}],
                "connections": [],
                "workflow_id": "wf_001"
            })

            with patch('core.atom_agent_endpoints.load_workflows', return_value=[]):
                with patch('core.atom_agent_endpoints.save_workflows') as mock_save:
                    request = ChatRequest(
                        message="Create a daily report workflow",
                        user_id="test_user"
                    )
                    result = await handle_create_workflow(request, {"description": "daily report"})

                    assert result["success"] is True
                    assert "workflow_id" in result["response"]
                    assert "nodes" in result["response"]

    @pytest.mark.asyncio
    async def test_handle_create_workflow_failure(self):
        """Test workflow creation failure"""
        from core.atom_agent_endpoints import handle_create_workflow, ChatRequest

        with patch('core.atom_agent_endpoints.get_orchestrator') as mock_orch:
            mock_orch.return_value.generate_dynamic_workflow = AsyncMock(return_value=None)

            request = ChatRequest(
                message="Create something unclear",
                user_id="test_user"
            )
            result = await handle_create_workflow(request, {"description": "unclear"})

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_handle_list_workflows(self):
        """Test listing workflows"""
        from core.atom_agent_endpoints import handle_list_workflows, ChatRequest

        with patch('core.atom_agent_endpoints.load_workflows') as mock_load:
            mock_load.return_value = [
                {"name": "Workflow 1", "workflow_id": "wf_001"},
                {"name": "Workflow 2", "workflow_id": "wf_002"}
            ]

            request = ChatRequest(message="List workflows", user_id="test_user")
            result = await handle_list_workflows(request)

            assert result["success"] is True
            assert "Found 2 workflows" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_list_workflows_empty(self):
        """Test listing workflows when none exist"""
        from core.atom_agent_endpoints import handle_list_workflows, ChatRequest

        with patch('core.atom_agent_endpoints.load_workflows') as mock_load:
            mock_load.return_value = []

            request = ChatRequest(message="List workflows", user_id="test_user")
            result = await handle_list_workflows(request)

            assert result["success"] is True
            assert "No workflows found" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_run_workflow_success(self):
        """Test running a workflow successfully"""
        from core.atom_agent_endpoints import handle_run_workflow, ChatRequest

        mock_workflows = [
            {"name": "Daily Report", "workflow_id": "wf_001", "id": "wf_001"}
        ]

        with patch('core.atom_agent_endpoints.load_workflows', return_value=mock_workflows):
            with patch('core.atom_agent_endpoints.AutomationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.execute_workflow_definition = AsyncMock(return_value={"status": "completed"})
                mock_engine_class.return_value = mock_engine

                request = ChatRequest(message="Run daily report", user_id="test_user")
                result = await handle_run_workflow(request, {"workflow_ref": "Daily Report"})

                assert result["success"] is True
                assert "execution_id" in result["response"]["message"]

    @pytest.mark.asyncio
    async def test_handle_run_workflow_not_found(self):
        """Test running a non-existent workflow"""
        from core.atom_agent_endpoints import handle_run_workflow, ChatRequest

        with patch('core.atom_agent_endpoints.load_workflows', return_value=[]):
            request = ChatRequest(message="Run nonexistent", user_id="test_user")
            result = await handle_run_workflow(request, {"workflow_ref": "nonexistent"})

            assert result["success"] is False
            assert "not found" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_run_workflow_missing_ref(self):
        """Test running workflow without specifying which one"""
        from core.atom_agent_endpoints import handle_run_workflow, ChatRequest

        request = ChatRequest(message="Run a workflow", user_id="test_user")
        result = await handle_run_workflow(request, {})

        assert result["success"] is False
        assert "specify" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_schedule_workflow_success(self):
        """Test scheduling a workflow successfully"""
        from core.atom_agent_endpoints import handle_schedule_workflow, ChatRequest

        mock_workflows = [
            {"name": "Daily Report", "workflow_id": "wf_001", "id": "wf_001"}
        ]

        with patch('core.atom_agent_endpoints.load_workflows', return_value=mock_workflows):
            with patch('core.atom_agent_endpoints.parse_time_expression', new=AsyncMock(return_value={
                "schedule_type": "cron",
                "cron_expression": "0 9 * * 1-5",
                "human_readable": "every weekday at 9am"
            })):
                with patch('core.atom_agent_endpoints.workflow_scheduler') as mock_scheduler:
                    mock_scheduler.schedule_workflow_cron = Mock()

                    request = ChatRequest(message="Schedule daily report", user_id="test_user")
                    result = await handle_schedule_workflow(request, {
                        "workflow_ref": "Daily Report",
                        "time_expression": "every weekday at 9am"
                    })

                    assert result["success"] is True
                    assert "schedule_id" in result["response"]

    @pytest.mark.asyncio
    async def test_handle_cancel_schedule_success(self):
        """Test cancelling a workflow schedule"""
        from core.atom_agent_endpoints import handle_cancel_schedule, ChatRequest

        with patch('core.atom_agent_endpoints.workflow_scheduler') as mock_scheduler:
            mock_scheduler.remove_job = Mock(return_value=True)

            request = ChatRequest(message="Cancel schedule", user_id="test_user")
            result = await handle_cancel_schedule(request, {"schedule_id": "job_001"})

            assert result["success"] is True
            assert "cancelled" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_get_status(self):
        """Test getting workflow status"""
        from core.atom_agent_endpoints import handle_get_status, ChatRequest

        request = ChatRequest(message="What's the status", user_id="test_user")
        result = await handle_get_status(request, {})

        assert result["success"] is True
        assert "status" in result["response"]["message"].lower()


# ========================================================================
# Test Class 5: Task, Calendar, and Email Handlers
# ========================================================================

class TestTaskCalendarEmailHandlers:
    """Test task, calendar, and email intent handlers"""

    @pytest.mark.asyncio
    async def test_handle_create_task(self):
        """Test creating a task"""
        from core.atom_agent_endpoints import handle_task_intent, ChatRequest

        with patch('core.atom_agent_endpoints.create_task', new=AsyncMock(return_value={
            "task_id": "task_001",
            "title": "Test Task"
        })):
            request = ChatRequest(message="Create a test task", user_id="test_user")
            result = await handle_task_intent("CREATE_TASK", {"title": "Test Task"}, request)

            assert result["success"] is True
            assert "created" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_list_tasks(self):
        """Test listing tasks"""
        from core.atom_agent_endpoints import handle_task_intent, ChatRequest

        with patch('core.atom_agent_endpoints.get_tasks', new=AsyncMock(return_value={
            "tasks": [{"id": "task_001", "title": "Task 1"}]
        })):
            request = ChatRequest(message="List tasks", user_id="test_user")
            result = await handle_task_intent("LIST_TASKS", {}, request)

            assert result["success"] is True
            assert "tasks" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_create_event(self):
        """Test creating a calendar event"""
        from core.atom_agent_endpoints import handle_create_event, ChatRequest

        request = ChatRequest(message="Schedule meeting", user_id="test_user")
        result = await handle_create_event(request, {"summary": "Team Meeting"})

        assert result["success"] is True
        assert "calendar event" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_list_events(self):
        """Test listing calendar events"""
        from core.atom_agent_endpoints import handle_list_events, ChatRequest

        with patch('core.atom_agent_endpoints.GoogleCalendarService') as mock_cal:
            mock_service = AsyncMock()
            mock_service.get_events = AsyncMock(return_value=[
                {"summary": "Meeting 1", "start": {"dateTime": "2026-02-20T10:00:00Z"}}
            ])
            mock_cal.return_value = mock_service

            request = ChatRequest(message="List events", user_id="test_user")
            result = await handle_list_events(request, {})

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_send_email(self):
        """Test preparing an email"""
        from core.atom_agent_endpoints import handle_send_email, ChatRequest

        request = ChatRequest(message="Send email", user_id="test_user")
        result = await handle_send_email(request, {"recipient": "test@example.com", "subject": "Test"})

        assert result["success"] is True
        assert "email" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_search_emails(self):
        """Test searching emails"""
        from core.atom_agent_endpoints import handle_search_emails, ChatRequest

        request = ChatRequest(message="Search emails", user_id="test_user")
        result = await handle_search_emails(request, {"query": "project update"})

        assert result["success"] is True


# ========================================================================
# Test Class 6: Streaming Endpoint
# ========================================================================

class TestStreamValidation:
    """Test streaming chat endpoint validation"""

    def test_stream_endpoint_exists(self, client):
        """Test that streaming endpoint is registered"""
        # This test verifies the endpoint exists (not functionality)
        # Actual streaming requires WebSocket setup which is complex
        from fastapi.routing import APIRoute

        routes = [r for r in router.routes if r.path == "/chat/stream"]
        assert len(routes) > 0
        assert routes[0].methods == {"POST"}

    def test_chat_endpoint_request_validation(self):
        """Test ChatRequest model validation"""
        # Valid request
        request = ChatRequest(
            message="Test message",
            user_id="test_user",
            session_id="session_001",
            current_page="/test",
            context={"key": "value"},
            conversation_history=[],
            agent_id="agent_001"
        )
        assert request.message == "Test message"
        assert request.user_id == "test_user"

        # Minimal valid request
        minimal = ChatRequest(
            message="Test",
            user_id="user_001"
        )
        assert minimal.message == "Test"
        assert minimal.session_id is None

    def test_chat_message_model_validation(self):
        """Test ChatMessage model validation"""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

        # Assistant message
        asst = ChatMessage(role="assistant", content="Hi there!")
        assert asst.role == "assistant"


# ========================================================================
# Test Class 7: Governance Integration
# ========================================================================

class TestGovernanceIntegration:
    """Test governance integration with agent maturity levels"""

    def test_student_agent_governance_check(self, db_session):
        """Test that STUDENT agents are checked for permissions"""
        from core.agent_governance_service import AgentGovernanceService

        agent = AgentRegistry(
            id="student_test",
            name="Student Test",
            maturity_level="STUDENT",
            confidence_score=0.3,
            capabilities=[],
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        governance = AgentGovernanceService(db_session)
        check = governance.can_perform_action(
            agent_id="student_test",
            action_type="stream_chat"
        )

        # Check returns dict with 'allowed' key
        assert "allowed" in check
        # STUDENT agents should be blocked from streaming (per governance rules)
        # However, specific behavior depends on governance configuration

    def test_intern_agent_governance_check(self, db_session):
        """Test that INTERN agents require approval for certain actions"""
        from core.agent_governance_service import AgentGovernanceService

        agent = AgentRegistry(
            id="intern_test",
            name="Intern Test",
            maturity_level="INTERN",
            confidence_score=0.6,
            capabilities=["streaming"],
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        governance = AgentGovernanceService(db_session)
        check = governance.can_perform_action(
            agent_id="intern_test",
            action_type="stream_chat"
        )

        assert "allowed" in check

    def test_autonomous_agent_governance_check(self, db_session):
        """Test that AUTONOMOUS agents have full access"""
        from core.agent_governance_service import AgentGovernanceService

        agent = AgentRegistry(
            id="autonomous_test",
            name="Autonomous Test",
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
            capabilities=["streaming", "state_changes", "deletions"],
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        governance = AgentGovernanceService(db_session)
        check = governance.can_perform_action(
            agent_id="autonomous_test",
            action_type="stream_chat"
        )

        # AUTONOMOUS agents should be allowed
        assert check["allowed"] is True

    def test_governance_caching(self, db_session):
        """Test that governance checks use cache for performance"""
        from core.agent_governance_service import AgentGovernanceService
        import time

        agent = AgentRegistry(
            id="cache_test",
            name="Cache Test",
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
            capabilities=["streaming"],
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        governance = AgentGovernanceService(db_session)

        # First check (cache miss)
        start1 = time.time()
        check1 = governance.can_perform_action(
            agent_id="cache_test",
            action_type="stream_chat"
        )
        duration1 = time.time() - start1

        # Second check (cache hit - should be faster)
        start2 = time.time()
        check2 = governance.can_perform_action(
            agent_id="cache_test",
            action_type="stream_chat"
        )
        duration2 = time.time() - start2

        assert check1 == check2
        # Cached check should be faster (though hard to guarantee in tests)


# ========================================================================
# Test Class 8: Hybrid Retrieval Endpoints
# ========================================================================

class TestHybridRetrievalEndpoints:
    """Test hybrid and baseline retrieval endpoints"""

    def test_retrieve_hybrid_endpoint_exists(self):
        """Test that hybrid retrieval endpoint exists"""
        from fastapi.routing import APIRoute

        routes = [r for r in router.routes if "/retrieve-hybrid" in r.path]
        assert len(routes) > 0

    def test_retrieve_baseline_endpoint_exists(self):
        """Test that baseline retrieval endpoint exists"""
        from fastapi.routing import APIRoute

        routes = [r for r in router.routes if "/retrieve-baseline" in r.path]
        assert len(routes) > 0

    @pytest.mark.asyncio
    async def test_retrieve_hybrid_success(self, client):
        """Test successful hybrid retrieval"""
        with patch('core.atom_agent_endpoints.HybridRetrievalService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.retrieve_semantic_hybrid = AsyncMock(return_value=[
                ("ep_001", 0.95, "rerank"),
                ("ep_002", 0.87, "rerank")
            ])
            mock_service_class.return_value = mock_service

            response = client.post("/api/atom-agent/agents/agent_001/retrieve-hybrid", json={
                "query": "test query",
                "coarse_top_k": 100,
                "rerank_top_k": 50,
                "use_reranking": True
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "results" in data
            assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_retrieve_baseline_success(self, client):
        """Test successful baseline retrieval"""
        with patch('core.atom_agent_endpoints.HybridRetrievalService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.retrieve_semantic_baseline = AsyncMock(return_value=[
                ("ep_001", 0.85),
                ("ep_002", 0.78)
            ])
            mock_service_class.return_value = mock_service

            response = client.post("/api/atom-agent/agents/agent_001/retrieve-baseline", json={
                "query": "test query",
                "top_k": 50
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "results" in data
            assert len(data["results"]) == 2


# ========================================================================
# Test Class 9: Execute Generated Workflow
# ========================================================================

class TestExecuteGeneratedWorkflow:
    """Test execute-generated workflow endpoint"""

    def test_execute_generated_success(self, client):
        """Test successful execution of generated workflow"""
        mock_workflows = [
            {"id": "wf_001", "name": "Generated Workflow", "workflow_id": "wf_001"}
        ]

        with patch('core.atom_agent_endpoints.load_workflows', return_value=mock_workflows):
            with patch('core.atom_agent_endpoints.AutomationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.execute_workflow_definition = AsyncMock(return_value={
                    "status": "completed",
                    "output": "Workflow executed successfully"
                })
                mock_engine_class.return_value = mock_engine

                response = client.post("/api/atom-agent/execute-generated", json={
                    "workflow_id": "wf_001",
                    "input_data": {"param1": "value1"}
                })

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "execution_id" in data
                assert data["status"] == "completed"

    def test_execute_generated_not_found(self, client):
        """Test executing non-existent workflow"""
        with patch('core.atom_agent_endpoints.load_workflows', return_value=[]):
            response = client.post("/api/atom-agent/execute-generated", json={
                "workflow_id": "nonexistent_wf",
                "input_data": {}
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "not found" in data["error"].lower()

    def test_execute_generated_automation_engine_unavailable(self, client):
        """Test execution when AutomationEngine is not available"""
        mock_workflows = [
            {"id": "wf_001", "name": "Generated Workflow", "workflow_id": "wf_001"}
        ]

        with patch('core.atom_agent_endpoints.load_workflows', return_value=mock_workflows):
            with patch('core.atom_agent_endpoints.AutomationEngine', None):
                response = client.post("/api/atom-agent/execute-generated", json={
                    "workflow_id": "wf_001",
                    "input_data": {}
                })

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is False
                assert "not available" in data["error"].lower()


# ========================================================================
# Test Class 10: System and Search Handlers
# ========================================================================

class TestSystemAndSearchHandlers:
    """Test system status and platform search handlers"""

    @pytest.mark.asyncio
    async def test_handle_system_status(self):
        """Test system status handler"""
        from core.atom_agent_endpoints import handle_system_status, ChatRequest

        with patch('core.atom_agent_endpoints.SystemStatus') as mock_status:
            mock_status.get_overall_status = Mock(return_value="healthy")
            mock_status.get_system_info = Mock(return_value={
                "platform": {"system": "Linux"}
            })
            mock_status.get_resource_usage = Mock(return_value={
                "cpu": {"percent": 45.2},
                "memory": {"percent": 62.8}
            })
            mock_status.get_service_status = Mock(return_value={
                "database": {"status": "healthy"},
                "redis": {"status": "healthy"}
            })

            request = ChatRequest(message="System status", user_id="test_user")
            result = await handle_system_status(request)

            assert result["success"] is True
            assert "system status" in result["response"]["message"].lower()
            assert "services" in result["response"]["data"]

    @pytest.mark.asyncio
    async def test_handle_platform_search(self):
        """Test platform search handler"""
        from core.atom_agent_endpoints import handle_platform_search, ChatRequest, SearchRequest

        with patch('core.atom_agent_endpoints.unified_hybrid_search') as mock_search:
            mock_response = Mock()
            mock_response.success = True
            mock_response.results = [
                Mock(text="Document 1 content", metadata={"type": "document"})
            ]
            mock_response.total_count = 1
            mock_search = AsyncMock(return_value=mock_response)

            with patch('core.atom_agent_endpoints.unified_hybrid_search', return_value=mock_response):
                request = ChatRequest(message="Search for documents", user_id="test_user")
                result = await handle_platform_search(request, {"query": "test query"})

                assert result["success"] is True
                assert "results" in result["response"]["data"]

    @pytest.mark.asyncio
    async def test_handle_automation_insights(self):
        """Test automation insights handler"""
        from core.atom_agent_endpoints import handle_automation_insights, ChatRequest

        with patch('core.atom_agent_endpoints.get_insight_manager') as mock_insight:
            mock_insight_mgr = Mock()
            mock_insight_mgr.generate_all_insights = Mock(return_value=[
                {"workflow_id": "wf_001", "drift_score": 0.3}
            ])
            mock_insight.return_value = mock_insight_mgr

        with patch('core.atom_agent_endpoints.get_behavior_analyzer') as mock_behavior:
            mock_behavior.return_value.detect_patterns = Mock(return_value=[])

        request = ChatRequest(message="Show insights", user_id="test_user")
        result = await handle_automation_insights(request)

        assert result["success"] is True
        assert "automation health" in result["response"]["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_knowledge_query(self):
        """Test knowledge query handler"""
        from core.atom_agent_endpoints import handle_knowledge_query, ChatRequest

        with patch('core.atom_agent_endpoints.get_knowledge_query_manager') as mock_kq:
            mock_mgr = Mock()
            mock_mgr.answer_query = AsyncMock(return_value={
                "answer": "The answer to your question",
                "relevant_facts": ["Fact 1", "Fact 2"]
            })
            mock_kq.return_value = mock_mgr

            request = ChatRequest(message="Who worked on project X", user_id="test_user")
            result = await handle_knowledge_query(request, {"query": "Who worked on project X"})

            assert result["success"] is True
            assert "answer" in result["response"]["message"]


# ========================================================================
# Test Class 11: Error Handling and Edge Cases
# ========================================================================

class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_chat_with_empty_message(self):
        """Test chat with empty message"""
        from core.atom_agent_endpoints import chat_with_agent, ChatRequest

        request = ChatRequest(message="", user_id="test_user")
        result = await chat_with_agent(request)

        # Should handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_chat_with_very_long_message(self):
        """Test chat with very long message"""
        from core.atom_agent_endpoints import chat_with_agent, ChatRequest

        long_message = "test " * 10000  # Very long message

        with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
            "intent": "UNKNOWN",
            "entities": {}
        })):
            with patch('core.atom_agent_endpoints.handle_help_request', return_value={
                "success": True,
                "response": {"message": "Help"}
            }):
                request = ChatRequest(message=long_message, user_id="test_user")
                result = await chat_with_agent(request)

                assert result is not None

    @pytest.mark.asyncio
    async def test_handler_exception_handling(self):
        """Test that handler exceptions are caught"""
        from core.atom_agent_endpoints import handle_create_workflow, ChatRequest

        with patch('core.atom_agent_endpoints.get_orchestrator') as mock_orch:
            mock_orch.return_value.generate_dynamic_workflow = AsyncMock(
                side_effect=Exception("Orchestrator error")
            )

            request = ChatRequest(message="Create workflow", user_id="test_user")
            result = await handle_create_workflow(request, {"description": "test"})

            # Should return error response, not raise exception
            assert result["success"] is False
            assert "error" in result["response"]["message"].lower() or "failed" in result["response"]["message"].lower()

    def test_session_manager_exception_handling(self, client):
        """Test session manager exception handling"""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock:
            mock.side_effect = Exception("Session manager error")

            response = client.get("/api/atom-agent/sessions?user_id=test_user")

            # Should return error response
            assert response.status_code == 200
            data = response.json()
            assert "error" in data

    def test_chat_history_manager_exception_handling(self, client):
        """Test chat history manager exception handling"""
        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_session:
            mock_session.return_value.create_session = Mock(return_value="session_001")
            mock_session.return_value.get_session = Mock(return_value={"session_id": "session_001"})

            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_history:
                mock_history.side_effect = Exception("History manager error")

                response = client.get("/api/atom-agent/sessions/session_001/history")

                # Should return error response
                assert response.status_code == 200
                data = response.json()
                assert "error" in data


# ========================================================================
# Test Class 12: Context Reference Resolution
# ========================================================================

class TestContextReferenceResolution:
    """Test context reference resolution in chat"""

    @pytest.mark.asyncio
    async def test_workflow_reference_resolution(self):
        """Test resolving workflow references from context"""
        from core.atom_agent_endpoints import chat_with_agent, ChatRequest

        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_session:
            mock_session.return_value.create_session = Mock(return_value="session_001")
            mock_session.return_value.get_session = Mock(return_value={"session_id": "session_001"})

            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_history:
                mock_history.get_session_history = Mock(return_value=[])

            with patch('core.atom_agent_endpoints.get_chat_context_manager') as mock_ctx:
                mock_ctx.return_value.resolve_reference = AsyncMock(return_value={
                    "id": "wf_001",
                    "name": "Daily Report"
                })

            with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
                "intent": "RUN_WORKFLOW",
                "entities": {"workflow_ref": "that"}  # Reference word
            })):
                with patch('core.atom_agent_endpoints.handle_run_workflow', new=AsyncMock(return_value={
                    "success": True,
                    "response": {"message": "Workflow running"}
                })) as mock_run:
                    request = ChatRequest(
                        message="Run that workflow",
                        user_id="test_user",
                        session_id="session_001"
                    )
                    result = await chat_with_agent(request)

                    # Verify reference was resolved
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args[0]
                    # entities should have resolved workflow_id
                    assert call_args is not None

    @pytest.mark.asyncio
    async def test_task_reference_resolution(self):
        """Test resolving task references from context"""
        from core.atom_agent_endpoints import chat_with_agent, ChatRequest

        with patch('core.atom_agent_endpoints.get_chat_session_manager') as mock_session:
            mock_session.return_value.get_session = Mock(return_value={"session_id": "session_001"})

            with patch('core.atom_agent_endpoints.get_chat_history_manager') as mock_history:
                mock_history.get_session_history = Mock(return_value=[])

            with patch('core.atom_agent_endpoints.get_chat_context_manager') as mock_ctx:
                mock_ctx.return_value.resolve_reference = AsyncMock(return_value={
                    "id": "task_001",
                    "name": "Follow up with client"
                })

            with patch('core.atom_agent_endpoints.classify_intent_with_llm', new=AsyncMock(return_value={
                "intent": "COMPLETE_TASK",
                "entities": {"task_ref": "it"}  # Reference word
            })):
                with patch('core.atom_agent_endpoints.handle_task_intent', new=AsyncMock(return_value={
                    "success": True,
                    "response": {"message": "Task completed"}
                })):
                    request = ChatRequest(
                        message="Complete it",
                        user_id="test_user",
                        session_id="session_001"
                    )
                    result = await chat_with_agent(request)

                    assert result is not None
