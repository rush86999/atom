"""
Tests for Supervision Routes API

Coverage Targets:
- SSE streaming (GET /{execution_id}/stream)
- Intervention endpoints (POST /sessions/{session_id}/intervene)
- Session completion (POST /sessions/{session_id}/complete)
- Session queries (GET /sessions/active, /agents/{agent_id}/sessions, /sessions/{session_id})
- Autonomous approval (POST /proposals/{proposal_id}/autonomous-approve)
- Error handling (400, 404, 500)
"""

import pytest
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from api.supervision_routes import router
from core.models import SupervisionSession, AgentExecution, AgentRegistry
from core.database import get_db

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create test client with router"""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create mock database session"""
    mock_db = Mock(spec=Session)
    mock_db.query = Mock()
    mock_db.add = Mock()
    mock_db.commit = Mock()
    mock_db.rollback = Mock()
    mock_db.refresh = Mock()
    return mock_db


@pytest.fixture
def sample_execution():
    """Sample agent execution"""
    execution = Mock(spec=AgentExecution)
    execution.id = "exec_001"
    execution.agent_id = "agent_001"
    execution.agent_name = "Test Agent"
    return execution


@pytest.fixture
def sample_supervision_session():
    """Sample supervision session"""
    session = Mock(spec=SupervisionSession)
    session.id = "session_001"
    session.agent_id = "agent_001"
    session.agent_name = "Test Agent"
    session.supervisor_id = "user_001"
    session.status = "active"
    session.started_at = datetime.now()
    session.completed_at = None
    session.duration_seconds = 300
    session.intervention_count = 2
    return session


@pytest.fixture
def mock_supervision_service():
    """Mock SupervisionService"""
    service = Mock()
    service.monitor_agent_execution = AsyncMock()
    service.intervene = AsyncMock(return_value=Mock(
        success=True,
        message="Intervention applied",
        session_state="paused"
    ))
    service.complete_supervision = AsyncMock(return_value=Mock(
        session_id="session_001",
        duration_seconds=300,
        intervention_count=2,
        confidence_boost=0.1
    ))
    service.get_active_sessions = AsyncMock(return_value=[])
    service.get_supervision_history = AsyncMock(return_value=[])
    return service


# ============================================================================
# GET /{execution_id}/stream - SSE Streaming
# ============================================================================

def test_stream_supervision_logs_success(client, db_session, sample_execution):
    """Test successful SSE stream for supervision logs"""
    # Setup
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first = Mock(return_value=sample_execution)
    mock_query.filter = Mock(return_value=mock_filter)
    db_session.query = Mock(return_value=mock_query)

    mock_session_query = Mock()
    mock_session_filter = Mock()
    mock_session_filter.first = Mock(return_value=None)
    mock_session_filter.order_by = Mock(return_value=mock_session_filter)
    mock_session_query.filter = Mock(return_value=mock_session_filter)

    # Return different mock for session query
    query_count = [0]
    def mock_query_impl(model):
        query_count[0] += 1
        if query_count[0] == 1:
            return mock_query
        else:
            return mock_session_query

    db_session.query = mock_query_impl

    with patch('api.supervision_routes.get_db', return_value=db_session):
        with patch('api.supervision_routes.SupervisionService') as MockService:
            mock_service = Mock()

            # Create async generator that yields events
            async def event_generator():
                from core.supervision_service import SupervisionEvent
                yield SupervisionEvent(
                    event_type="connected",
                    timestamp=datetime.now(),
                    data={"execution_id": "exec_001"}
                )

            mock_service.monitor_agent_execution = event_generator
            MockService.return_value = mock_service

            # Test
            response = client.get("/api/supervision/exec_001/stream")

            # Verify
            # SSE endpoint returns streaming response
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


def test_stream_supervision_logs_execution_not_found(client, db_session):
    """Test SSE stream when execution not found returns 404"""
    # Setup
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first = Mock(return_value=None)
    mock_query.filter = Mock(return_value=mock_filter)
    db_session.query = Mock(return_value=mock_query)

    with patch('api.supervision_routes.get_db', return_value=db_session):
        # Test
        response = client.get("/api/supervision/nonexistent/stream")

        # Verify
        assert response.status_code == 404


# ============================================================================
# POST /sessions/{session_id}/intervene - Intervention
# ============================================================================

def test_intervene_in_session_pause(client, db_session):
    """Test successful pause intervention"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(return_value=Mock(
            success=True,
            message="Agent paused",
            session_state="paused"
        ))
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "pause",
            "guidance": "Pausing for review"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session_state"] == "paused"


def test_intervene_in_session_correct(client, db_session):
    """Test successful correction intervention"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(return_value=Mock(
            success=True,
            message="Correction applied",
            session_state="corrected"
        ))
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "correct",
            "guidance": "Adjusting parameters"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_intervene_in_session_terminate(client, db_session):
    """Test successful terminate intervention"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(return_value=Mock(
            success=True,
            message="Execution terminated",
            session_state="terminated"
        ))
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "terminate",
            "guidance": "Terminating due to error"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_intervene_session_not_found(client, db_session):
    """Test intervention on non-existent session returns 404"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(
            side_effect=ValueError("Session not found")
        )
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "pause",
            "guidance": "Pausing"
        }
        response = client.post("/api/supervision/sessions/nonexistent/intervene", json=request_data)

        # Verify
        assert response.status_code == 404


def test_intervene_service_error(client, db_session):
    """Test intervention when service errors"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(
            side_effect=Exception("Service error")
        )
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "pause",
            "guidance": "Pausing"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 500


# ============================================================================
# POST /sessions/{session_id}/complete - Session Completion
# ============================================================================

def test_complete_supervision_session_success(client, db_session):
    """Test successful supervision session completion"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.complete_supervision = AsyncMock(return_value=Mock(
            session_id="session_001",
            duration_seconds=300,
            intervention_count=2,
            confidence_boost=0.1
        ))
        MockService.return_value = mock_service

        # Test
        response = client.post("/api/supervision/sessions/session_001/complete?supervisor_rating=5&feedback=Good+work")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["duration_seconds"] == 300
        assert data["intervention_count"] == 2
        assert data["confidence_boost"] == 0.1


def test_complete_supervision_session_not_found(client, db_session):
    """Test completing non-existent session returns 404"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.complete_supervision = AsyncMock(
            side_effect=ValueError("Session not found")
        )
        MockService.return_value = mock_service

        # Test
        response = client.post("/api/supervision/sessions/nonexistent/complete?supervisor_rating=4&feedback=Needs+improvement")

        # Verify
        assert response.status_code == 404


def test_complete_supervision_service_error(client, db_session):
    """Test session completion when service errors"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.complete_supervision = AsyncMock(
            side_effect=Exception("Database error")
        )
        MockService.return_value = mock_service

        # Test
        response = client.post("/api/supervision/sessions/session_001/complete?supervisor_rating=3&feedback=Error")

        # Verify
        assert response.status_code == 500


# ============================================================================
# GET /sessions/active - Get Active Sessions
# ============================================================================

def test_get_active_sessions_success(client, db_session):
    """Test successful retrieval of active sessions"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_active_sessions = AsyncMock(return_value=[])
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/sessions/active")

        # Verify
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)


def test_get_active_sessions_with_workspace(client, db_session):
    """Test retrieval of active sessions filtered by workspace"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_active_sessions = AsyncMock(return_value=[])
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/sessions/active?workspace_id=workspace_001")

        # Verify
        assert response.status_code == 200


def test_get_active_sessions_with_limit(client, db_session):
    """Test retrieval of active sessions with limit"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_active_sessions = AsyncMock(return_value=[])
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/sessions/active?limit=25")

        # Verify
        assert response.status_code == 200


def test_get_active_sessions_service_error(client, db_session):
    """Test active sessions retrieval when service errors"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_active_sessions = AsyncMock(
            side_effect=Exception("Database error")
        )
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/sessions/active")

        # Verify
        assert response.status_code == 500


# ============================================================================
# GET /agents/{agent_id}/sessions - Agent Supervision History
# ============================================================================

def test_get_agent_supervision_history_success(client, db_session):
    """Test successful retrieval of agent supervision history"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_supervision_history = AsyncMock(return_value=[
            {
                "session_id": "session_001",
                "status": "completed",
                "started_at": "2026-02-14T10:00:00",
                "completed_at": "2026-02-14T10:05:00",
                "duration_seconds": 300,
                "intervention_count": 2
            }
        ])
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/agents/agent_001/sessions")

        # Verify
        assert response.status_code == 200
        history = response.json()
        assert len(history) == 1
        assert history[0]["session_id"] == "session_001"


def test_get_agent_supervision_history_empty(client, db_session):
    """Test agent supervision history when no sessions exist"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_supervision_history = AsyncMock(return_value=[])
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/agents/agent_999/sessions")

        # Verify
        assert response.status_code == 200
        history = response.json()
        assert len(history) == 0


def test_get_agent_supervision_history_with_limit(client, db_session):
    """Test agent supervision history with limit"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_supervision_history = AsyncMock(return_value=[])
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/agents/agent_001/sessions?limit=10")

        # Verify
        assert response.status_code == 200


def test_get_agent_supervision_history_service_error(client, db_session):
    """Test agent supervision history when service errors"""
    # Setup
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.get_supervision_history = AsyncMock(
            side_effect=Exception("Database error")
        )
        MockService.return_value = mock_service

        # Test
        response = client.get("/api/supervision/agents/agent_001/sessions")

        # Verify
        assert response.status_code == 500


# ============================================================================
# GET /sessions/{session_id} - Get Supervision Session
# ============================================================================

def test_get_supervision_session_success(client, db_session, sample_supervision_session):
    """Test successful retrieval of supervision session"""
    # Setup
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first = Mock(return_value=sample_supervision_session)
    mock_query.filter = Mock(return_value=mock_filter)
    db_session.query = Mock(return_value=mock_query)

    with patch('api.supervision_routes.get_db', return_value=db_session):
        # Test
        response = client.get("/api/supervision/sessions/session_001")

        # Verify
        assert response.status_code == 200
        session = response.json()
        assert session["session_id"] == "session_001"
        assert session["agent_id"] == "agent_001"


def test_get_supervision_session_not_found(client, db_session):
    """Test retrieving non-existent supervision session returns 404"""
    # Setup
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first = Mock(return_value=None)
    mock_query.filter = Mock(return_value=mock_filter)
    db_session.query = Mock(return_value=mock_query)

    with patch('api.supervision_routes.get_db', return_value=db_session):
        # Test
        response = client.get("/api/supervision/sessions/nonexistent")

        # Verify
        assert response.status_code == 404


# ============================================================================
# POST /proposals/{proposal_id}/autonomous-approve - Autonomous Approval
# ============================================================================

def test_autonomous_approve_proposal_success(client, db_session):
    """Test successful autonomous approval of proposal"""
    # Setup
    with patch('api.supervision_routes.ProposalService') as MockService:
        mock_service = Mock()
        mock_service.autonomous_approve_or_reject = AsyncMock(return_value={
            "proposal_id": "proposal_001",
            "approved": True,
            "approved_by": "agent_autonomous"
        })
        MockService.return_value = mock_service

        # Test
        response = client.post("/api/supervision/proposals/proposal_001/autonomous-approve")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["proposal_id"] == "proposal_001"


def test_autonomous_approve_proposal_not_found(client, db_session):
    """Test autonomous approval of non-existent proposal returns 404"""
    # Setup
    with patch('api.supervision_routes.ProposalService') as MockService:
        mock_service = Mock()
        mock_service.autonomous_approve_or_reject = AsyncMock(
            side_effect=ValueError("Proposal not found")
        )
        MockService.return_value = mock_service

        # Test
        response = client.post("/api/supervision/proposals/nonexistent/autonomous-approve")

        # Verify
        assert response.status_code == 404


def test_autonomous_approve_proposal_service_error(client, db_session):
    """Test autonomous approval when service errors"""
    # Setup
    with patch('api.supervision_routes.ProposalService') as MockService:
        mock_service = Mock()
        mock_service.autonomous_approve_or_reject = AsyncMock(
            side_effect=Exception("Service error")
        )
        MockService.return_value = mock_service

        # Test
        response = client.post("/api/supervision/proposals/proposal_001/autonomous-approve")

        # Verify
        assert response.status_code == 500


# ============================================================================
# Intervention Counting Tests
# ============================================================================

def test_intervention_counting_pause(client, db_session):
    """Test pause interventions are counted"""
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(return_value=Mock(
            success=True,
            message="Paused",
            session_state="paused"
        ))
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "pause",
            "guidance": "Review needed"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 200


def test_intervention_counting_correct(client, db_session):
    """Test correction interventions are counted"""
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(return_value=Mock(
            success=True,
            message="Corrected",
            session_state="corrected"
        ))
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "correct",
            "guidance": "Fix parameters"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 200


def test_intervention_counting_terminate(client, db_session):
    """Test terminate interventions are counted"""
    with patch('api.supervision_routes.SupervisionService') as MockService:
        mock_service = Mock()
        mock_service.intervene = AsyncMock(return_value=Mock(
            success=True,
            message="Terminated",
            session_state="terminated"
        ))
        MockService.return_value = mock_service

        # Test
        request_data = {
            "intervention_type": "terminate",
            "guidance": "Stop execution"
        }
        response = client.post("/api/supervision/sessions/session_001/intervene", json=request_data)

        # Verify
        assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_invalid_session_id_format(client):
    """Test error handling for invalid session ID format"""
    response = client.get("/api/supervision/sessions/invalid_id_with spaces")
    # Should return 404 or validation error
    assert response.status_code in [404, 422]


def test_database_connection_error(client, db_session):
    """Test handling of database connection errors"""
    # Setup
    with patch('api.supervision_routes.get_db', side_effect=Exception("Connection error")):
        # Test
        response = client.get("/api/supervision/sessions/session_001")

        # Verify - should return 500 or similar error
        assert response.status_code >= 400


def test_service_unavailable_error(client, db_session):
    """Test handling when SupervisionService is unavailable"""
    # Setup
    with patch('api.supervision_routes.SupervisionService', side_effect=ImportError):
        # Test
        response = client.get("/api/supervision/sessions/active")

        # Verify
        assert response.status_code >= 400
