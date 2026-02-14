"""
Dashboard Data Routes Unit Tests

Tests for dashboard data APIs from api/dashboard_data_routes.py.

Coverage:
- GET /data - Comprehensive dashboard data
- GET /stats - Dashboard statistics
- GET /events - Calendar events
- GET /tasks - User tasks
- GET /messages - User messages
- GET /health - Health check
- User filtering
- Status filtering
- Error handling
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session

from api.dashboard_data_routes import router
from core.models import WorkflowExecution, ChatProcess, AuditLog, AgentJob, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def app_with_db(db):
    """Create FastAPI app with database dependency."""
    app = FastAPI()
    app.include_router(router)

    from core.database import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield app

    app.dependency_overrides.clear()


@pytest.fixture
def client(app_with_db: FastAPI):
    """Create TestClient with overridden dependencies."""
    return TestClient(app_with_db, raise_server_exceptions=False)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    return user


# ============================================================================
# GET /data - Comprehensive Dashboard Data
# ============================================================================

def test_get_dashboard_data_success(client: TestClient, db: MagicMock):
    """Test getting comprehensive dashboard data."""
    # Mock the helper functions
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
            with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
                with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
                    mock_events.return_value = [
                        {
                            "id": "evt-1",
                            "title": "Test Event",
                            "start": "2026-02-13T10:00:00Z",
                            "end": "2026-02-13T11:00:00Z",
                            "status": "confirmed"
                        }
                    ]
                    mock_tasks.return_value = [
                        {
                            "id": "task-1",
                            "title": "Test Task",
                            "status": "todo",
                            "priority": "medium"
                        }
                    ]
                    mock_messages.return_value = [
                        {
                            "id": "msg-1",
                            "platform": "system",
                            "subject": "Test",
                            "timestamp": "2026-02-13T10:00:00Z"
                        }
                    ]
                    mock_stats.return_value = {
                        "upcoming_events": 1,
                        "overdue_tasks": 0,
                        "unread_messages": 1,
                        "completed_tasks": 5,
                        "active_workflows": 2,
                        "total_agents": 10
                    }

                    response = client.get("/api/dashboard/data")

                    assert response.status_code == 200
                    data = response.json()
                    assert "success" in data
                    assert "data" in data
                    assert "stats" in data
                    assert "timestamp" in data
                    assert data["success"] is True


def test_get_dashboard_data_with_user_filter(client: TestClient, db: MagicMock):
    """Test getting dashboard data with user filter."""
    user_id = "test-user-123"

    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
            with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
                with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
                    mock_events.return_value = []
                    mock_tasks.return_value = []
                    mock_messages.return_value = []
                    mock_stats.return_value = {
                        "upcoming_events": 0,
                        "overdue_tasks": 0,
                        "unread_messages": 0,
                        "completed_tasks": 0,
                        "active_workflows": 0,
                        "total_agents": 0
                    }

                    response = client.get(f"/api/dashboard/data?user_id={user_id}")

                    assert response.status_code == 200
                    mock_events.assert_called_once()
                    mock_tasks.assert_called_once()


def test_get_dashboard_data_custom_limit(client: TestClient, db: MagicMock):
    """Test getting dashboard data with custom limit."""
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
            with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
                with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
                    mock_events.return_value = []
                    mock_tasks.return_value = []
                    mock_messages.return_value = []
                    mock_stats.return_value = {
                        "upcoming_events": 0,
                        "overdue_tasks": 0,
                        "unread_messages": 0,
                        "completed_tasks": 0,
                        "active_workflows": 0,
                        "total_agents": 0
                    }

                    response = client.get("/api/dashboard/data?limit=50")

                    assert response.status_code == 200


def test_get_dashboard_data_limit_validation(client: TestClient, db: MagicMock):
    """Test that limit parameter validates correctly."""
    # Test maximum limit
    with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
        mock_stats.return_value = {
            "upcoming_events": 0, "overdue_tasks": 0, "unread_messages": 0,
            "completed_tasks": 0, "active_workflows": 0, "total_agents": 0
        }

        response = client.get("/api/dashboard/data?limit=101")
        # Should fail validation (max is 100)
        assert response.status_code == 422


def test_get_dashboard_data_server_error(client: TestClient, db: MagicMock):
    """Test dashboard data endpoint with server error."""
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        mock_events.side_effect = Exception("Database error")

        response = client.get("/api/dashboard/data")
        assert response.status_code == 500


# ============================================================================
# GET /stats - Dashboard Statistics
# ============================================================================

def test_get_dashboard_stats_success(client: TestClient, db: MagicMock):
    """Test getting dashboard statistics."""
    with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
        mock_stats.return_value = {
            "upcoming_events": 5,
            "overdue_tasks": 2,
            "unread_messages": 10,
            "completed_tasks": 50,
            "active_workflows": 3,
            "total_agents": 12
        }

        response = client.get("/api/dashboard/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["upcoming_events"] == 5
        assert data["overdue_tasks"] == 2
        assert data["unread_messages"] == 10
        assert data["completed_tasks"] == 50
        assert data["active_workflows"] == 3
        assert data["total_agents"] == 12


def test_get_dashboard_stats_with_user_id(client: TestClient, db: MagicMock):
    """Test getting dashboard stats filtered by user."""
    user_id = "user-456"

    with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
        mock_stats.return_value = {
            "upcoming_events": 1,
            "overdue_tasks": 0,
            "unread_messages": 2,
            "completed_tasks": 5,
            "active_workflows": 1,
            "total_agents": 10
        }

        response = client.get(f"/api/dashboard/stats?user_id={user_id}")

        assert response.status_code == 200
        mock_stats.assert_called_once()


def test_get_dashboard_stats_error(client: TestClient, db: MagicMock):
    """Test dashboard stats with error."""
    with patch('api.dashboard_data_routes.calculate_dashboard_stats') as mock_stats:
        mock_stats.side_effect = Exception("Stats calculation failed")

        response = client.get("/api/dashboard/stats")
        assert response.status_code == 500


# ============================================================================
# GET /events - Calendar Events
# ============================================================================

def test_get_calendar_events_success(client: TestClient, db: MagicMock):
    """Test getting calendar events."""
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        mock_events.return_value = [
            {
                "id": "evt-1",
                "title": "Meeting",
                "start": "2026-02-13T10:00:00Z",
                "end": "2026-02-13T11:00:00Z",
                "description": "Team meeting",
                "location": "Room A",
                "status": "confirmed"
            },
            {
                "id": "evt-2",
                "title": "Call",
                "start": "2026-02-13T14:00:00Z",
                "end": "2026-02-13T14:30:00Z",
                "status": "tentative"
            }
        ]

        response = client.get("/api/dashboard/events")

        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)
        assert len(events) == 2
        assert events[0]["title"] == "Meeting"
        assert events[0]["status"] == "confirmed"


def test_get_calendar_events_with_user_filter(client: TestClient, db: MagicMock):
    """Test getting calendar events filtered by user."""
    user_id = "user-789"

    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        mock_events.return_value = []

        response = client.get(f"/api/dashboard/events?user_id={user_id}")

        assert response.status_code == 200
        mock_events.assert_called_once()


def test_get_calendar_events_custom_limit(client: TestClient, db: MagicMock):
    """Test getting calendar events with custom limit."""
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        mock_events.return_value = []

        response = client.get("/api/dashboard/events?limit=25")

        assert response.status_code == 200


def test_get_calendar_events_limit_validation(client: TestClient, db: MagicMock):
    """Test that events limit validates correctly."""
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        mock_events.return_value = []

        response = client.get("/api/dashboard/events?limit=51")
        # Should fail validation (max is 50)
        assert response.status_code == 422


def test_get_calendar_events_error(client: TestClient, db: MagicMock):
    """Test calendar events with error."""
    with patch('api.dashboard_data_routes.get_user_upcoming_events') as mock_events:
        mock_events.side_effect = Exception("Events fetch failed")

        response = client.get("/api/dashboard/events")
        assert response.status_code == 500


# ============================================================================
# GET /tasks - User Tasks
# ============================================================================

def test_get_tasks_success(client: TestClient, db: MagicMock):
    """Test getting user tasks."""
    with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
        mock_tasks.return_value = [
            {
                "id": "task-1",
                "title": "Review PR",
                "description": "Review feature branch",
                "due_date": "2026-02-14T10:00:00Z",
                "priority": "high",
                "status": "todo",
                "created_at": "2026-02-13T09:00:00Z",
                "updated_at": "2026-02-13T09:00:00Z"
            },
            {
                "id": "task-2",
                "title": "Update docs",
                "description": "Update API documentation",
                "due_date": "2026-02-15T10:00:00Z",
                "priority": "medium",
                "status": "in-progress",
                "created_at": "2026-02-13T08:00:00Z",
                "updated_at": "2026-02-13T08:00:00Z"
            }
        ]

        response = client.get("/api/dashboard/tasks")

        assert response.status_code == 200
        tasks = response.json()
        assert isinstance(tasks, list)
        assert len(tasks) == 2
        assert tasks[0]["title"] == "Review PR"
        assert tasks[0]["priority"] == "high"


def test_get_tasks_with_status_filter(client: TestClient, db: MagicMock):
    """Test getting tasks filtered by status."""
    with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
        mock_tasks.return_value = [
            {
                "id": "task-1",
                "title": "Task 1",
                "status": "todo",
                "priority": "medium",
                "created_at": "2026-02-13T09:00:00Z",
                "updated_at": "2026-02-13T09:00:00Z"
            },
            {
                "id": "task-2",
                "title": "Task 2",
                "status": "completed",
                "priority": "low",
                "created_at": "2026-02-13T08:00:00Z",
                "updated_at": "2026-02-13T08:00:00Z"
            }
        ]

        response = client.get("/api/dashboard/tasks?status=completed")

        assert response.status_code == 200
        tasks = response.json()
        # Should only return completed tasks
        assert all(t["status"] == "completed" for t in tasks)


def test_get_tasks_with_user_filter(client: TestClient, db: MagicMock):
    """Test getting tasks filtered by user."""
    user_id = "user-abc"

    with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
        mock_tasks.return_value = []

        response = client.get(f"/api/dashboard/tasks?user_id={user_id}")

        assert response.status_code == 200
        mock_tasks.assert_called_once()


def test_get_tasks_custom_limit(client: TestClient, db: MagicMock):
    """Test getting tasks with custom limit."""
    with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
        mock_tasks.return_value = []

        response = client.get("/api/dashboard/tasks?limit=50")

        assert response.status_code == 200


def test_get_tasks_error(client: TestClient, db: MagicMock):
    """Test tasks endpoint with error."""
    with patch('api.dashboard_data_routes.get_user_tasks') as mock_tasks:
        mock_tasks.side_effect = Exception("Tasks fetch failed")

        response = client.get("/api/dashboard/tasks")
        assert response.status_code == 500


# ============================================================================
# GET /messages - User Messages
# ============================================================================

def test_get_messages_success(client: TestClient, db: MagicMock):
    """Test getting user messages."""
    with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
        mock_messages.return_value = [
            {
                "id": "msg-1",
                "platform": "slack",
                "from_user": "user@example.com",
                "subject": "New notification",
                "preview": "You have a new message",
                "timestamp": "2026-02-13T10:00:00Z",
                "unread": True,
                "priority": "normal"
            },
            {
                "id": "msg-2",
                "platform": "system",
                "from_user": "system",
                "subject": "Alert",
                "preview": "System alert",
                "timestamp": "2026-02-13T09:00:00Z",
                "unread": False,
                "priority": "high"
            }
        ]

        response = client.get("/api/dashboard/messages")

        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["platform"] == "slack"
        assert messages[0]["unread"] is True


def test_get_messages_unread_only(client: TestClient, db: MagicMock):
    """Test getting only unread messages."""
    with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
        mock_messages.return_value = [
            {
                "id": "msg-1",
                "platform": "slack",
                "subject": "New",
                "preview": "New message",
                "timestamp": "2026-02-13T10:00:00Z",
                "unread": True,
                "priority": "normal"
            },
            {
                "id": "msg-2",
                "platform": "system",
                "subject": "Alert",
                "preview": "System alert",
                "timestamp": "2026-02-13T09:00:00Z",
                "unread": False,
                "priority": "high"
            }
        ]

        response = client.get("/api/dashboard/messages?unread_only=true")

        assert response.status_code == 200
        messages = response.json()
        # Should only return unread messages
        assert all(m["unread"] for m in messages)


def test_get_messages_with_user_filter(client: TestClient, db: MagicMock):
    """Test getting messages filtered by user."""
    user_id = "user-xyz"

    with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
        mock_messages.return_value = []

        response = client.get(f"/api/dashboard/messages?user_id={user_id}")

        assert response.status_code == 200
        mock_messages.assert_called_once()


def test_get_messages_custom_limit(client: TestClient, db: MagicMock):
    """Test getting messages with custom limit."""
    with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
        mock_messages.return_value = []

        response = client.get("/api/dashboard/messages?limit=50")

        assert response.status_code == 200


def test_get_messages_error(client: TestClient, db: MagicMock):
    """Test messages endpoint with error."""
    with patch('api.dashboard_data_routes.get_user_messages') as mock_messages:
        mock_messages.side_effect = Exception("Messages fetch failed")

        response = client.get("/api/dashboard/messages")
        assert response.status_code == 500


# ============================================================================
# GET /health - Health Check
# ============================================================================

def test_dashboard_health(client: TestClient):
    """Test dashboard health check endpoint."""
    response = client.get("/api/dashboard/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "timestamp" in data


# ============================================================================
# Helper Functions Tests
# ============================================================================

def test_get_user_upcoming_events_empty():
    """Test getting upcoming events with no results."""
    from api.dashboard_data_routes import get_user_upcoming_events

    mock_db = MagicMock(spec=Session)

    with patch('api.dashboard_data_routes.Session') as mock_session:
        mock_query_result = MagicMock()
        mock_query_result.order_by.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query_result

        events = get_user_upcoming_events(mock_db, None, 10)
        assert isinstance(events, list)


def test_get_user_tasks_empty():
    """Test getting tasks with no results."""
    from api.dashboard_data_routes import get_user_tasks

    mock_db = MagicMock(spec=Session)

    with patch('sqlalchemy.orm.Session.query') as mock_query:
        mock_query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        tasks = get_user_tasks(mock_db, None, 20)
        assert isinstance(tasks, list)


def test_get_user_messages_empty():
    """Test getting messages with no results."""
    from api.dashboard_data_routes import get_user_messages

    mock_db = MagicMock(spec=Session)

    with patch('sqlalchemy.orm.Session.query') as mock_query:
        mock_query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        messages = get_user_messages(mock_db, None, 20)
        assert isinstance(messages, list)


def test_calculate_dashboard_stats_empty():
    """Test calculating stats with empty database."""
    from api.dashboard_data_routes import calculate_dashboard_stats

    mock_db = MagicMock(spec=Session)

    with patch('sqlalchemy.orm.Session.query') as mock_query:
        mock_query.return_value.scalar.return_value = 0
        mock_query.return_value.filter.return_value.scalar.return_value = 0

        stats = calculate_dashboard_stats(mock_db, None)
        assert "upcoming_events" in stats
        assert "overdue_tasks" in stats
        assert "unread_messages" in stats
        assert "completed_tasks" in stats
        assert "active_workflows" in stats
        assert "total_agents" in stats
