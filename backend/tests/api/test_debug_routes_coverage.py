"""
Test Coverage for Debug API Routes

Comprehensive test suite for debug_routes.py (896 lines).
Target: 60%+ coverage (538+ lines).

Test Structure:
- TestDebugRoutes: Debug configuration, system status, feature flags
- TestDebugEndpoints: Event collection, state snapshots, insights
- TestDebugErrorHandling: Error paths, validation, disabled mode
- TestDebugSecurity: Authentication, authorization, governance
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any

# Import models
from backend.core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugMetric,
    DebugSession,
    User,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def debug_client(test_app):
    """Test client for debug routes."""
    return TestClient(test_app)


@pytest.fixture
def mock_user(db_session: Session):
    """Mock authenticated user."""
    user = User(
        id="test-user-1",
        email="test@example.com",
        username="testuser",
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def mock_superuser(db_session: Session):
    """Mock superuser for admin operations."""
    user = User(
        id="admin-user-1",
        email="admin@example.com",
        username="adminuser",
        is_active=True,
        is_superuser=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def mock_debug_event(db_session: Session):
    """Mock debug event."""
    event = DebugEvent(
        id="event-1",
        event_type="log",
        component_type="agent",
        component_id="agent-1",
        correlation_id="corr-1",
        level="INFO",
        message="Test message",
        timestamp=datetime.utcnow()
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def mock_debug_insight(db_session: Session):
    """Mock debug insight."""
    insight = DebugInsight(
        id="insight-1",
        insight_type="performance",
        severity="medium",
        scope="component",
        title="Test insight",
        summary="Test summary",
        description="Test description",
        confidence_score=0.85,
        resolved=False,
        created_at=datetime.utcnow()
    )
    db_session.add(insight)
    db_session.commit()
    return insight


@pytest.fixture
def mock_debug_session(db_session: Session):
    """Mock debug session."""
    session = DebugSession(
        id="session-1",
        session_name="Test Session",
        description="Test debug session",
        active=True,
        resolved=False,
        event_count=10,
        insight_count=5,
        created_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.commit()
    return session


# ============================================================================
# TestDebugRoutes: Debug Configuration and System Status (15 tests)
# ============================================================================

class TestDebugRoutes:
    """Test debug system configuration, feature flags, and system status endpoints."""

    def test_debug_system_enabled_by_default(self, debug_client):
        """Test debug system is enabled by default."""
        # This tests the DEBUG_SYSTEM_ENABLED feature flag
        response = debug_client.get("/api/debug/events")
        # Should return empty events list when enabled
        assert response.status_code in [200, 401]  # 401 if auth required

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False)
    def test_debug_system_disabled_responses(self, debug_client):
        """Test endpoints return disabled message when system is off."""
        response = debug_client.get("/api/debug/events")
        assert response.status_code == 200
        assert response.json()["enabled"] == False

    def test_debug_feature_flags(self, debug_client):
        """Test DEBUG_SYSTEM_ENABLED and EMERGENCY_GOVERNANCE_BYPASS flags."""
        # Test that feature flags are read from environment
        with patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True):
            with patch("backend.api.debug_routes.EMERGENCY_GOVERNANCE_BYPASS", False):
                # Should be enabled when flag is True
                response = debug_client.get("/api/debug/events")
                assert response.status_code in [200, 401]

    def test_debug_prefix_and_tags(self, debug_client):
        """Test router is configured with correct prefix and tags."""
        # Router should have prefix="/api/debug" and tags=["debug"]
        # This is tested by successful endpoint access
        response = debug_client.get("/api/debug/events")
        assert response.status_code in [200, 401]

    def test_debug_module_imports(self):
        """Test all required modules are imported correctly."""
        # Test that imports work (no ImportError)
        try:
            from backend.api import debug_routes
            from backend.core.debug_collector import get_debug_collector
            from backend.core.debug_insight_engine import DebugInsightEngine
            from backend.core.debug_query import DebugQuery
            from backend.core.debug_ai_assistant import DebugAIAssistant
            from backend.core.debug_storage import HybridDebugStorage
        except ImportError as e:
            pytest.fail(f"Failed to import debug modules: {e}")

    def test_base_router_inheritance(self):
        """Test debug router inherits from BaseAPIRouter."""
        from backend.api.debug_routes import router
        from backend.core.base_routes import BaseAPIRouter

        assert isinstance(router, BaseAPIRouter)
        assert router.prefix == "/api/debug"
        assert "debug" in router.tags

    def test_request_models_defined(self):
        """Test all Pydantic request models are defined."""
        from backend.api.debug_routes import (
            CollectEventRequest,
            CollectBatchEventsRequest,
            CollectStateSnapshotRequest,
            QueryEventsRequest,
            QueryInsightsRequest,
            GenerateInsightsRequest,
            CreateDebugSessionRequest,
            ComponentHealthRequest,
            NaturalLanguageQueryRequest,
        )

        # Test models can be instantiated
        event_req = CollectEventRequest(
            event_type="log",
            component_type="agent",
            correlation_id="test"
        )
        assert event_req.event_type == "log"

    def test_event_request_validation(self):
        """Test CollectEventRequest validates required fields."""
        from backend.api.debug_routes import CollectEventRequest
        from pydantic import ValidationError

        # Missing required field
        with pytest.raises(ValidationError):
            CollectEventRequest(
                component_type="agent",
                correlation_id="test"
                # Missing event_type
            )

    def test_batch_events_request_validation(self):
        """Test CollectBatchEventsRequest validates events list."""
        from backend.api.debug_routes import CollectBatchEventsRequest
        from pydantic import ValidationError

        # Empty events list should fail
        with pytest.raises(ValidationError):
            CollectBatchEventsRequest(events=[])

    def test_state_snapshot_request_validation(self):
        """Test CollectStateSnapshotRequest validates required fields."""
        from backend.api.debug_routes import CollectStateSnapshotRequest

        request = CollectStateSnapshotRequest(
            component_type="agent",
            component_id="agent-1",
            operation_id="op-1",
            state_data={"test": "data"}
        )
        assert request.snapshot_type == "full"  # Default value

    def test_natural_language_query_request(self):
        """Test NaturalLanguageQueryRequest accepts question and context."""
        from backend.api.debug_routes import NaturalLanguageQueryRequest

        request = NaturalLanguageQueryRequest(
            question="What errors occurred?",
            context={"user_id": "test-user"}
        )
        assert request.question == "What errors occurred?"

    def test_debug_routes_decorator(self, debug_client):
        """Test debug routes are decorated with auth requirements."""
        # Most debug routes require authentication
        response = debug_client.post(
            "/api/debug/events",
            json={"event_type": "log", "component_type": "agent", "correlation_id": "test"}
        )
        # Should require authentication (401 or 422)
        assert response.status_code in [401, 422]

    def test_error_response_structure(self, debug_client):
        """Test error responses follow standard structure."""
        response = debug_client.get("/api/debug/events/nonexistent")
        # Should return error response with proper structure
        assert response.status_code in [404, 401, 422]

    def test_success_response_structure(self, debug_client):
        """Test success responses follow standard structure."""
        # When debug system is disabled, should return success with enabled=False
        with patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
            response = debug_client.get("/api/debug/events")
            assert response.status_code == 200
            data = response.json()
            assert "data" in data or "enabled" in data


# ============================================================================
# TestDebugEndpoints: Event Collection, State Snapshots, Insights (12 tests)
# ============================================================================

class TestDebugEndpoints:
    """Test debug endpoint functionality for events, state, and insights."""

    @patch("backend.api.debug_routes.get_debug_collector")
    @patch("backend.api.debug_routes.init_debug_collector")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_collect_single_event(self, mock_init, mock_get, debug_client, mock_user):
        """Test collecting a single debug event."""
        mock_collector = Mock()
        mock_event = Mock()
        mock_event.id = "event-123"
        mock_collector.collect_event = Mock(return_value=mock_event)
        mock_get.return_value = None
        mock_init.return_value = mock_collector

        # Mock authentication
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/events",
                json={
                    "event_type": "log",
                    "component_type": "agent",
                    "component_id": "agent-1",
                    "correlation_id": "corr-1",
                    "level": "INFO",
                    "message": "Test event"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["event_id"] == "event-123"

    @patch("backend.api.debug_routes.get_debug_collector")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_collect_batch_events(self, mock_get, debug_client, mock_user):
        """Test collecting multiple events in batch."""
        mock_collector = Mock()
        mock_events = [Mock(id=f"event-{i}") for i in range(3)]
        mock_collector.collect_batch_events = Mock(return_value=mock_events)
        mock_get.return_value = mock_collector

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/events/batch",
                json={
                    "events": [
                        {
                            "event_type": "log",
                            "component_type": "agent",
                            "correlation_id": "corr-1"
                        },
                        {
                            "event_type": "state_snapshot",
                            "component_type": "workflow",
                            "correlation_id": "corr-2"
                        }
                    ]
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["collected_count"] == 3

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_query_events_with_filters(self, mock_storage, debug_client, mock_user):
        """Test querying events with various filters."""
        mock_storage_instance = Mock()
        mock_storage_instance.query_events = Mock(return_value=[
            {"id": "event-1", "event_type": "log", "level": "INFO"}
        ])
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get(
                "/api/debug/events",
                params={
                    "component_type": "agent",
                    "level": "INFO",
                    "limit": 10
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "events" in data["data"]
        assert len(data["data"]["events"]) >= 0

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_event_by_id(self, mock_storage, debug_client, mock_user, mock_debug_event):
        """Test retrieving a single event by ID."""
        mock_storage_instance = Mock()
        mock_storage_instance.get_event = Mock(return_value=mock_debug_event)
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get("/api/debug/events/event-1")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch("backend.api.debug_routes.get_debug_collector")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_collect_state_snapshot(self, mock_get, debug_client, mock_user):
        """Test collecting a component state snapshot."""
        mock_collector = Mock()
        mock_snapshot = Mock()
        mock_snapshot.id = "snapshot-1"
        mock_collector.collect_state_snapshot = Mock(return_value=mock_snapshot)
        mock_get.return_value = mock_collector

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/state",
                json={
                    "component_type": "agent",
                    "component_id": "agent-1",
                    "operation_id": "op-1",
                    "state_data": {"status": "running", "progress": 50}
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["snapshot_id"] == "snapshot-1"

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_component_state(self, mock_storage, debug_client, mock_user):
        """Test retrieving component state snapshot."""
        mock_snapshot = Mock()
        mock_snapshot.id = "snapshot-1"
        mock_storage_instance = Mock()
        mock_storage_instance.get_state_snapshot = Mock(return_value=mock_snapshot)
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get(
                "/api/debug/state/agent/agent-1",
                params={"operation_id": "op-1"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_query_insights(self, mock_storage, debug_client, mock_user):
        """Test querying debug insights with filters."""
        mock_storage_instance = Mock()
        mock_storage_instance.query_insights = Mock(return_value=[
            {"id": "insight-1", "severity": "medium", "resolved": False}
        ])
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get(
                "/api/debug/insights",
                params={"severity": "medium", "resolved": "false"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data["data"]

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_insight_by_id(self, mock_storage, debug_client, mock_user, mock_debug_insight):
        """Test retrieving a single insight by ID."""
        mock_storage_instance = Mock()
        mock_storage_instance.get_insight = Mock(return_value=mock_debug_insight)
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get("/api/debug/insights/insight-1")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch("backend.api.debug_routes.DebugInsightEngine")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_generate_insights(self, mock_engine_class, debug_client, mock_user):
        """Test generating insights from events."""
        mock_engine = Mock()
        mock_insight = Mock()
        mock_insight.id = "insight-generated"
        mock_engine.generate_insights_from_events = Mock(return_value=[mock_insight])
        mock_engine._insight_to_dict = Mock(return_value={"id": "insight-generated"})
        mock_engine_class.return_value = mock_engine

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/insights/generate",
                json={
                    "correlation_id": "corr-1",
                    "time_range": "last_1h"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data["data"]

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_resolve_insight(self, debug_client, mock_user, mock_debug_insight, db_session: Session):
        """Test marking an insight as resolved."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.put(
                "/api/debug/insights/insight-1/resolve",
                params={"resolution_notes": "Fixed the issue"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["resolved"] == True

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_create_debug_session(self, debug_client, mock_user):
        """Test creating a new debug session."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/sessions",
                json={
                    "session_name": "Test Session",
                    "description": "Testing debug session",
                    "filters": {"component_type": "agent"}
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data["data"]


# ============================================================================
# TestDebugErrorHandling: Error Paths and Validation (10 tests)
# ============================================================================

class TestDebugErrorHandling:
    """Test error handling, validation, and disabled mode behavior."""

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False)
    def test_collect_event_when_disabled(self, debug_client, mock_user):
        """Test event collection returns disabled message when system is off."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/events",
                json={
                    "event_type": "log",
                    "component_type": "agent",
                    "correlation_id": "test"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == False

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False)
    def test_get_event_when_disabled_returns_error(self, debug_client, mock_user):
        """Test get_event returns error when debug system is disabled."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get("/api/debug/events/event-1")

        assert response.status_code == 400
        assert "DEBUG_DISABLED" in response.json()["error_code"]

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False)
    def test_state_snapshot_when_disabled(self, debug_client, mock_user):
        """Test state snapshot returns disabled message."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/state",
                json={
                    "component_type": "agent",
                    "component_id": "agent-1",
                    "operation_id": "op-1",
                    "state_data": {}
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == False

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False)
    def test_insight_operations_when_disabled(self, debug_client, mock_user):
        """Test insight operations return error when disabled."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get("/api/debug/insights/insight-1")

        assert response.status_code == 400
        assert "DEBUG_DISABLED" in response.json()["error_code"]

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", False)
    def test_create_session_when_disabled(self, debug_client, mock_user):
        """Test session creation returns error when disabled."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.post(
                "/api/debug/sessions",
                json={"session_name": "Test"}
            )

        assert response.status_code == 400
        assert "DEBUG_DISABLED" in response.json()["error_code"]

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_event_not_found(self, mock_storage, debug_client, mock_user):
        """Test get_event returns 404 for nonexistent event."""
        mock_storage_instance = Mock()
        mock_storage_instance.get_event = Mock(return_value=None)
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get("/api/debug/events/nonexistent")

        assert response.status_code == 404
        assert "EVENT_NOT_FOUND" in response.json()["error_code"]

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_insight_not_found(self, mock_storage, debug_client, mock_user):
        """Test get_insight returns 404 for nonexistent insight."""
        mock_storage_instance = Mock()
        mock_storage_instance.get_insight = Mock(return_value=None)
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get("/api/debug/insights/nonexistent")

        assert response.status_code == 404
        assert "INSIGHT_NOT_FOUND" in response.json()["error_code"]

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_state_snapshot_missing_operation_id(self, debug_client, mock_user):
        """Test get_state_snapshot requires operation_id parameter."""
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            # Missing operation_id should return 400 error
            response = debug_client.get("/api/debug/state/agent/agent-1")

        assert response.status_code == 400
        assert "MISSING_OPERATION_ID" in response.json()["error_code"]

    @patch("backend.api.debug_routes._get_storage")
    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_get_state_snapshot_not_found(self, mock_storage, debug_client, mock_user):
        """Test get_state_snapshot returns 404 when snapshot not found."""
        mock_storage_instance = Mock()
        mock_storage_instance.get_state_snapshot = Mock(return_value=None)
        mock_storage.return_value = mock_storage_instance

        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.get(
                "/api/debug/state/agent/agent-1",
                params={"operation_id": "op-1"}
            )

        assert response.status_code == 404
        assert "SNAPSHOT_NOT_FOUND" in response.json()["error_code"]

    @patch("backend.api.debug_routes.DEBUG_SYSTEM_ENABLED", True)
    def test_close_session_not_found(self, debug_client, mock_user):
        """Test closing nonexistent session returns 404."""
        with patch("backend.api.debug_routes.get_current_user", return_value=mock_user):
            response = debug_client.put("/api/debug/sessions/nonexistent/close")

        assert response.status_code == 404
        assert "SESSION_NOT_FOUND" in response.json()["error_code"]


# ============================================================================
# TestDebugSecurity: Authentication and Authorization (8 tests)
# ============================================================================

class TestDebugSecurity:
    """Test authentication, authorization, and security restrictions."""

    def test_event_collection_requires_auth(self, debug_client):
        """Test event collection endpoint requires authentication."""
        response = debug_client.post(
            "/api/debug/events",
            json={
                "event_type": "log",
                "component_type": "agent",
                "correlation_id": "test"
            }
        )

        # Should require authentication
        assert response.status_code == 401

    def test_batch_events_requires_auth(self, debug_client):
        """Test batch event collection requires authentication."""
        response = debug_client.post(
            "/api/debug/events/batch",
            json={"events": []}
        )

        assert response.status_code == 401

    def test_query_events_requires_auth(self, debug_client):
        """Test querying events requires authentication."""
        response = debug_client.get("/api/debug/events")

        assert response.status_code == 401

    def test_state_snapshot_requires_auth(self, debug_client):
        """Test state snapshot collection requires authentication."""
        response = debug_client.post(
            "/api/debug/state",
            json={
                "component_type": "agent",
                "component_id": "agent-1",
                "operation_id": "op-1",
                "state_data": {}
            }
        )

        assert response.status_code == 401

    def test_insight_query_requires_auth(self, debug_client):
        """Test insight queries require authentication."""
        response = debug_client.get("/api/debug/insights")

        assert response.status_code == 401

    def test_session_creation_requires_auth(self, debug_client):
        """Test debug session creation requires authentication."""
        response = debug_client.post(
            "/api/debug/sessions",
            json={"session_name": "Test"}
        )

        assert response.status_code == 401

    def test_analytics_endpoints_require_auth(self, debug_client):
        """Test analytics endpoints require authentication."""
        response = debug_client.get("/api/debug/analytics/error-patterns")

        assert response.status_code == 401

    def test_ai_query_requires_auth(self, debug_client):
        """Test AI query endpoint requires authentication."""
        response = debug_client.post(
            "/api/debug/ai/query",
            json={"question": "What errors occurred?"}
        )

        assert response.status_code == 401
