"""
Coverage-driven tests for canvas_routes.py (0% -> 75%+ target)

API Endpoints Tested:
- POST /api/canvas/submit - Form submission with governance
- GET /api/canvas/status - Canvas status retrieval

Coverage Target Areas:
- Lines 1-50: Route initialization, dependencies, models
- Lines 50-100: Form submission endpoint (governance, validation)
- Lines 100-150: Agent permission checks and execution tracking
- Lines 150-200: Canvas audit logging and WebSocket broadcast
- Lines 200-227: Canvas status endpoint
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import canvas routes router
from api.canvas_routes import router

# Import models
from core.models import (
    Base, User, AgentExecution, AgentRegistry, CanvasAudit, AgentStatus
)

# Import auth for password hashing
from core.auth import get_password_hash


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create only the tables we need for canvas routes testing
    from core.models import User, AgentExecution, AgentRegistry, CanvasAudit

    User.__table__.create(bind=engine, checkfirst=True)
    AgentExecution.__table__.create(bind=engine, checkfirst=True)
    AgentRegistry.__table__.create(bind=engine, checkfirst=True)
    CanvasAudit.__table__.create(bind=engine, checkfirst=True)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    yield db

    # Cleanup
    db.close()
    CanvasAudit.__table__.drop(bind=engine)
    AgentExecution.__table__.drop(bind=engine)
    AgentRegistry.__table__.drop(bind=engine)
    User.__table__.drop(bind=engine)


@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with canvas routes for testing."""
    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    from core.database import get_db

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app: FastAPI):
    """Create TestClient for testing."""
    return TestClient(test_app)


@pytest.fixture(scope="function")
def test_user(test_db: Session) -> User:
    """Create test user for authentication."""
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
        email_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def autonomous_agent(test_db: Session) -> AgentRegistry:
    """Create AUTONOMOUS agent for governance tests."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="autonomous_agent",
        description="Test autonomous agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )
    test_db.add(agent)
    test_db.commit()
    test_db.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def supervised_agent(test_db: Session) -> AgentRegistry:
    """Create SUPERVISED agent for governance tests."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="supervised_agent",
        description="Test supervised agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.75
    )
    test_db.add(agent)
    test_db.commit()
    test_db.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def intern_agent(test_db: Session) -> AgentRegistry:
    """Create INTERN agent for governance tests (should be blocked)."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="intern_agent",
        description="Test intern agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    test_db.add(agent)
    test_db.commit()
    test_db.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def agent_execution(test_db: Session, autonomous_agent: AgentRegistry) -> AgentExecution:
    """Create agent execution for context tracking."""
    execution = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id=autonomous_agent.id,
        workspace_id="default",
        status="running",
        input_summary="Test execution for form submission",
        triggered_by="test"
    )
    test_db.add(execution)
    test_db.commit()
    test_db.refresh(execution)
    return execution


# ============================================================================
# Helper Functions
# ============================================================================

def mock_auth(user: User):
    """Mock authentication dependency."""
    def override_get_current_user():
        return user
    return override_get_current_user


# ============================================================================
# Form Submission Tests - Lines 45-210
# ============================================================================

class TestFormSubmissionCoverage:
    """Test form submission endpoint with comprehensive coverage."""

    def test_submit_form_success_autonomous_agent(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover successful form submission with AUTONOMOUS agent (lines 68-128)."""
        # Override auth
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-1",
            "form_data": {
                "email": "user@example.com",
                "message": "Test message",
                "name": "Test User"
            },
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock) as mock_broadcast:
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert "submission_id" in result["data"]
            assert result["data"]["agent_id"] == autonomous_agent.id
            assert "agent_execution_id" in result["data"]

            # Verify audit record created
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-1"
            ).first()
            assert audit is not None
            assert audit.action_type == "submit"
            assert audit.user_id == test_user.id

            # Verify agent execution created
            execution = test_db.query(AgentExecution).filter(
                AgentExecution.agent_id == autonomous_agent.id,
                AgentExecution.triggered_by == "form_submission"
            ).first()
            assert execution is not None
            assert execution.status == "completed"

        client.app.dependency_overrides.clear()

    def test_submit_form_supervised_agent_allowed(self, client: TestClient, test_db: Session, test_user: User, supervised_agent: AgentRegistry):
        """Cover form submission with SUPERVISED agent (allowed action)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-2",
            "form_data": {"field1": "value1"},
            "agent_id": supervised_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True

        client.app.dependency_overrides.clear()

    def test_submit_form_intern_agent_blocked(self, client: TestClient, test_db: Session, test_user: User, intern_agent: AgentRegistry):
        """Cover governance blocking for INTERN agent (lines 96-115)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-3",
            "form_data": {"field1": "value1"},
            "agent_id": intern_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            # Should be blocked due to maturity level
            assert response.status_code == 403

        client.app.dependency_overrides.clear()

    def test_submit_form_with_execution_context(self, client: TestClient, test_db: Session, test_user: User, agent_execution: AgentExecution):
        """Cover form submission linked to originating execution (lines 79-88)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-4",
            "form_data": {"field1": "value1"},
            "agent_execution_id": agent_execution.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            # Should use agent from originating execution
            assert result["data"]["agent_id"] == agent_execution.agent_id

        client.app.dependency_overrides.clear()

    def test_submit_form_with_both_contexts(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry, agent_execution: AgentExecution):
        """Cover form submission with both agent_id and execution_id (lines 86-88)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-5",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id,
            "agent_execution_id": agent_execution.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            # Prefers explicit agent_id over execution's agent

        client.app.dependency_overrides.clear()

    def test_submit_form_without_agent(self, client: TestClient, test_db: Session, test_user: User):
        """Cover form submission without agent context (lines 135-159)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-6",
            "form_data": {"field1": "value1"}
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            # Should create audit without agent context
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-6"
            ).first()
            assert audit.agent_id is None

        client.app.dependency_overrides.clear()

    def test_submit_form_validation_missing_canvas_id(self, client: TestClient, test_db: Session, test_user: User):
        """Cover validation error for missing canvas_id."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "form_data": {"field1": "value1"}
        }

        response = client.post("/api/canvas/submit", json=submission_data)
        assert response.status_code == 422  # Validation error

        client.app.dependency_overrides.clear()

    def test_submit_form_validation_missing_form_data(self, client: TestClient, test_db: Session, test_user: User):
        """Cover validation error for missing form_data."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form"
        }

        response = client.post("/api/canvas/submit", json=submission_data)
        assert response.status_code == 422  # Validation error

        client.app.dependency_overrides.clear()

    def test_submit_form_with_complex_data(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with complex nested data."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-7",
            "form_data": {
                "user": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "preferences": {
                        "theme": "dark",
                        "notifications": True
                    }
                },
                "items": ["item1", "item2", "item3"],
                "metadata": {
                    "source": "web",
                    "timestamp": "2026-03-15T10:00:00Z"
                }
            },
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True

            # Verify audit captured the complex data
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-7"
            ).first()
            assert audit is not None
            details = audit.details_json
            assert details["field_count"] == 3  # user, items, metadata

        client.app.dependency_overrides.clear()

    def test_submit_form_websocket_broadcast(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover WebSocket broadcast on form submission (lines 162-172)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-8",
            "form_data": {"message": "Hello"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock) as mock_broadcast:
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            assert mock_broadcast.called

            # Verify broadcast message structure
            call_args = mock_broadcast.call_args
            if call_args:
                channel = call_args[0][0]
                message = call_args[0][1]

                assert channel == f"user:{test_user.id}"
                assert message["type"] == "canvas:form_submitted"
                assert message["canvas_id"] == "test-form-8"
                assert message["data"] == {"message": "Hello"}

        client.app.dependency_overrides.clear()

    def test_submit_form_execution_completion(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover execution completion tracking (lines 175-198)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-9",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

            # Verify execution was marked completed
            execution = test_db.query(AgentExecution).filter(
                AgentExecution.agent_id == autonomous_agent.id,
                AgentExecution.triggered_by == "form_submission"
            ).first()

            assert execution is not None
            assert execution.status == "completed"
            assert execution.completed_at is not None
            assert execution.duration_seconds is not None
            assert execution.result_summary is not None

        client.app.dependency_overrides.clear()


# ============================================================================
# Canvas Status Tests - Lines 211-227
# ============================================================================

class TestCanvasStatusCoverage:
    """Test canvas status endpoint with comprehensive coverage."""

    def test_get_canvas_status_success(self, client: TestClient, test_db: Session, test_user: User):
        """Cover successful canvas status retrieval (lines 211-227)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        response = client.get("/api/canvas/status")

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["data"]["status"] == "active"
        assert result["data"]["user_id"] == test_user.id
        assert "features" in result["data"]
        assert isinstance(result["data"]["features"], list)

        client.app.dependency_overrides.clear()

    def test_get_canvas_status_features_list(self, client: TestClient, test_db: Session, test_user: User):
        """Cover feature list in status response."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        response = client.get("/api/canvas/status")

        assert response.status_code == 200
        result = response.json()
        features = result["data"]["features"]

        expected_features = ["markdown", "status_panel", "form", "line_chart", "bar_chart", "pie_chart"]
        for feature in expected_features:
            assert feature in features

        client.app.dependency_overrides.clear()

    def test_get_canvas_status_unauthorized(self, client: TestClient, test_db: Session):
        """Cover unauthorized access to status endpoint."""
        # No auth override
        response = client.get("/api/canvas/status")

        # Should return 401 or 403 depending on auth setup
        assert response.status_code in [401, 403]


# ============================================================================
# Error Handling and Edge Cases
# ============================================================================

class TestCanvasRoutesErrorHandling:
    """Test error handling and edge cases in canvas routes."""

    def test_submit_form_nonexistent_agent(self, client: TestClient, test_db: Session, test_user: User):
        """Cover handling of nonexistent agent ID."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-error",
            "form_data": {"field1": "value1"},
            "agent_id": str(uuid.uuid4())  # Nonexistent agent
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Should succeed but without governance check (agent not found)
            response = client.post("/api/canvas/submit", json=submission_data)
            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_nonexistent_execution(self, client: TestClient, test_db: Session, test_user: User):
        """Cover handling of nonexistent execution ID."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-error-2",
            "form_data": {"field1": "value1"},
            "agent_execution_id": str(uuid.uuid4())  # Nonexistent execution
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Should succeed but without execution context
            response = client.post("/api/canvas/submit", json=submission_data)
            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_execution_completion_error(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover error handling during execution completion (lines 193-198)."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-error-3",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Mock governance service to raise error on record_outcome
            from core.service_factory import ServiceFactory
            original_get_governance = ServiceFactory.get_governance_service

            def mock_get_governance(db):
                gov_service = original_get_governance(db)
                # Override record_outcome to raise error
                original_record_outcome = gov_service.record_outcome

                async def failing_record_outcome(*args, **kwargs):
                    raise Exception("DB error")

                gov_service.record_outcome = failing_record_outcome
                return gov_service

            with patch.object(ServiceFactory, 'get_governance_service', side_effect=mock_get_governance):
                # Should still succeed despite completion error
                response = client.post("/api/canvas/submit", json=submission_data)
                assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_empty_form_data(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with empty form_data."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-empty",
            "form_data": {},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True

            # Verify audit shows 0 fields
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-empty"
            ).first()
            assert audit.details_json["field_count"] == 0

        client.app.dependency_overrides.clear()

    def test_submit_form_special_characters(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with special characters in data."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-special",
            "form_data": {
                "message": "Test with 'quotes' and \"double quotes\"",
                "emoji": "Hello! 🎉",
                "newlines": "Line 1\nLine 2\nLine 3",
                "unicode": "你好世界"
            },
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_large_data(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with large data payload."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        # Create large form data
        large_text = "x" * 10000
        submission_data = {
            "canvas_id": "test-form-large",
            "form_data": {
                "large_field": large_text,
                "count": 1000
            },
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_multiple_submissions_same_canvas(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover multiple form submissions for the same canvas."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-multi",
            "form_data": {"step": "1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # First submission
            response1 = client.post("/api/canvas/submit", json=submission_data)
            assert response1.status_code == 200

            # Second submission
            submission_data["form_data"] = {"step": "2"}
            response2 = client.post("/api/canvas/submit", json=submission_data)
            assert response2.status_code == 200

            # Verify both audit records exist
            audits = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-multi"
            ).all()

            assert len(audits) == 2

        client.app.dependency_overrides.clear()


# ============================================================================
# Governance Integration Tests
# ============================================================================

class TestCanvasRoutesGovernanceIntegration:
    """Test governance integration in canvas routes."""

    def test_governance_flag_disabled(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover behavior when governance flag is disabled."""
        from core.security_dependencies import get_current_user
        from core.feature_flags import FeatureFlags
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-no-gov",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            with patch.object(FeatureFlags, 'should_enforce_governance', return_value=False):
                response = client.post("/api/canvas/submit", json=submission_data)

                # Should succeed without governance check
                assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_governance_check_allowed(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover governance check that returns allowed."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-allowed",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["data"]["governance_check"]["allowed"] is True

        client.app.dependency_overrides.clear()

    def test_governance_audit_logging(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover audit logging with governance details."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-audit",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

            # Verify audit has governance details
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-audit"
            ).first()

            assert audit is not None
            assert "governance_check_passed" in audit.details_json
            assert audit.details_json["governance_check_passed"] is True

        client.app.dependency_overrides.clear()


# ============================================================================
# Parameterized Tests
# ============================================================================

class TestCanvasRoutesParameterized:
    """Parameterized tests for canvas routes."""

    @pytest.mark.parametrize("canvas_id,form_data", [
        ("canvas-1", {"email": "test@example.com"}),
        ("canvas-2", {"name": "Test", "age": "25"}),
        ("canvas-3", {"message": "Hello World"}),
        ("canvas-4", {"choice": "option_a"}),
        ("canvas-5", {"enabled": True}),
    ])
    def test_submit_various_forms(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry, canvas_id, form_data):
        """Cover form submission with various data structures."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": canvas_id,
            "form_data": form_data,
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    @pytest.mark.parametrize("agent_status,confidence_score,should_be_allowed", [
        (AgentStatus.AUTONOMOUS.value, 0.95, True),
        (AgentStatus.SUPERVISED.value, 0.75, True),
        (AgentStatus.INTERN.value, 0.6, False),
        (AgentStatus.STUDENT.value, 0.4, False),
    ])
    def test_submit_form_maturity_levels(self, client: TestClient, test_db: Session, test_user: User, agent_status, confidence_score, should_be_allowed):
        """Cover form submission for all maturity levels."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        # Create agent with specific maturity level
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name=f"{agent_status.lower()}_agent",
            description=f"Test {agent_status} agent",
            category="testing",
            module_path="agents.test_agent",
            class_name="TestAgent",
            status=agent_status,
            confidence_score=confidence_score
        )
        test_db.add(agent)
        test_db.commit()

        submission_data = {
            "canvas_id": f"test-{agent_status.lower()}",
            "form_data": {"field1": "value1"},
            "agent_id": agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            if should_be_allowed:
                assert response.status_code == 200
            else:
                assert response.status_code == 403

        client.app.dependency_overrides.clear()

    @pytest.mark.parametrize("invalid_agent_id", [
        "",  # Empty string
        "not-a-uuid",  # Invalid UUID format
        "00000000-0000-0000-0000-000000000000",  # Nil UUID
    ])
    def test_submit_form_invalid_agent_id(self, client: TestClient, test_db: Session, test_user: User, invalid_agent_id):
        """Cover form submission with invalid agent IDs."""
        from core.security_dependencies import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-invalid-agent",
            "form_data": {"field1": "value1"},
            "agent_id": invalid_agent_id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Should succeed or fail gracefully
            response = client.post("/api/canvas/submit", json=submission_data)
            assert response.status_code in [200, 404, 422]

        client.app.dependency_overrides.clear()
