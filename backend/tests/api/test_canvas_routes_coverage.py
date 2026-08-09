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
        status="active"
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
        confidence_score=0.95,
        workspace_id="default"
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
        confidence_score=0.75,
        workspace_id="default"
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
        confidence_score=0.6,
        workspace_id="default"
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


def patch_global_db(test_db: Session):
    """Patch core.database.get_db_session to yield the in-memory test DB.

    submit_canvas persists the audit row through the module-global
    get_db_session() (imported inside the handler), not the injected session —
    so audit assertions need this redirect (the real dev DB has schema drift
    and would pollute the test run).
    """
    from contextlib import contextmanager

    @contextmanager
    def _yield_test_db():
        yield test_db

    return patch('core.database.get_db_session', side_effect=_yield_test_db)


# ============================================================================
# Form Submission Tests - Lines 45-210
# ============================================================================

class TestFormSubmissionCoverage:
    """Test form submission endpoint with comprehensive coverage."""

    def test_submit_form_success_autonomous_agent(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover successful form submission with AUTONOMOUS agent."""
        # Override auth
        from core.auth import get_current_user
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

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            with patch_global_db(test_db):
                response = client.post("/api/canvas/submit", json=submission_data)

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        # Real contract: data carries canvas_id/submitted/timestamp only
        assert result["data"]["canvas_id"] == "test-form-1"
        assert result["data"]["submitted"] is True

        # Verify audit record created (via the patched global session)
        audit = test_db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "test-form-1"
        ).first()
        assert audit is not None
        assert audit.action_type == "submit"
        assert audit.user_id == test_user.id
        assert audit.agent_id == autonomous_agent.id

        client.app.dependency_overrides.clear()

    def test_submit_form_supervised_agent_allowed(self, client: TestClient, test_db: Session, test_user: User, supervised_agent: AgentRegistry):
        """Cover form submission with SUPERVISED agent (allowed action)."""
        from core.auth import get_current_user
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
        """Cover governance blocking for INTERN agent."""
        from core.auth import get_current_user
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
        """Cover form submission with an agent_execution_id."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-4",
            "form_data": {"field1": "value1"},
            "agent_execution_id": agent_execution.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            # The route accepts the field but doesn't resolve the execution
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True

        client.app.dependency_overrides.clear()

    def test_submit_form_with_both_contexts(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry, agent_execution: AgentExecution):
        """Cover form submission with both agent_id and execution_id."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-5",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id,
            "agent_execution_id": agent_execution.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            # Governance runs off the explicit agent_id
            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_without_agent(self, client: TestClient, test_db: Session, test_user: User):
        """Cover form submission without agent context."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-6",
            "form_data": {"field1": "value1"}
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            with patch_global_db(test_db):
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
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "form_data": {"field1": "value1"}
        }

        response = client.post("/api/canvas/submit", json=submission_data)
        assert response.status_code == 422  # Validation error

        client.app.dependency_overrides.clear()

    def test_submit_form_validation_missing_form_data(self, client: TestClient, test_db: Session, test_user: User):
        """Cover validation error for missing form_data."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form"
        }

        response = client.post("/api/canvas/submit", json=submission_data)
        assert response.status_code == 422  # Validation error

        client.app.dependency_overrides.clear()

    def test_submit_form_with_complex_data(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with complex nested data."""
        from core.auth import get_current_user
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
            with patch_global_db(test_db):
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
            assert details["form_data"]["user"]["preferences"]["theme"] == "dark"

        client.app.dependency_overrides.clear()

    def test_submit_form_websocket_broadcast(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission — the route does NOT broadcast."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-8",
            "form_data": {"message": "Hello"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock) as mock_broadcast:
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            # submit_canvas persists an audit row; WS broadcast is not part of
            # its contract (canvas:update broadcasts happen on state changes).
            mock_broadcast.assert_not_called()

        client.app.dependency_overrides.clear()

    def test_submit_form_execution_completion(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission — no execution lifecycle in this route."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-9",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

            # The route does not create/complete AgentExecution rows — no
            # "form_submission" executions exist after a submit.
            execution = test_db.query(AgentExecution).filter(
                AgentExecution.agent_id == autonomous_agent.id,
                AgentExecution.triggered_by == "form_submission"
            ).first()
            assert execution is None

        client.app.dependency_overrides.clear()


# ============================================================================
# Canvas Status Tests - Lines 211-227
# ============================================================================

class TestCanvasStatusCoverage:
    """Test the canvas read endpoint (GET /api/canvas/{canvas_id})."""

    def test_get_canvas_status_success(self, client: TestClient, test_db: Session, test_user: User):
        """Cover reading a canvas that exists in the audit trail."""
        from core.auth import get_current_user
        from core.models import Canvas
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        # Seed the Canvas row (IDOR ownership guard) + audit row so
        # read_canvas resolves the canvas for this user.
        Canvas.__table__.create(bind=test_db.get_bind(), checkfirst=True)
        canvas = Canvas(
            id="status-canvas-1", tenant_id="default", created_by=test_user.id,
            name="c", canvas_type="form", content={"blocks": []}, style={},
        )
        test_db.add(canvas)
        audit = CanvasAudit(
            canvas_id="status-canvas-1",
            tenant_id="default",
            canvas_type="form",
            action_type="create",
            user_id=test_user.id,
            details_json={"title": "t"},
        )
        test_db.add(audit)
        test_db.commit()
        with patch_global_db(test_db):
            response = client.get("/api/canvas/status-canvas-1")

        # read_canvas reads the audit trail (via the patched global session)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["canvas_id"] == "status-canvas-1"

        client.app.dependency_overrides.clear()

    def test_get_canvas_status_features_list(self, client: TestClient, test_db: Session, test_user: User):
        """Cover reading an unknown canvas → 404."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        with patch_global_db(test_db):
            response = client.get("/api/canvas/status")

        # "status" is not a route — it resolves to /{canvas_id}, and the
        # canvas doesn't exist in the audit trail → 404.
        assert response.status_code == 404

        client.app.dependency_overrides.clear()

    def test_get_canvas_status_unauthorized(self, client: TestClient, test_db: Session):
        """Cover unauthorized access to canvas read endpoint."""
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
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-error",
            "form_data": {"field1": "value1"},
            "agent_id": str(uuid.uuid4())  # Nonexistent agent
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Governance can't find the agent → fail-closed denial
            response = client.post("/api/canvas/submit", json=submission_data)
            assert response.status_code == 403

        client.app.dependency_overrides.clear()

    def test_submit_form_nonexistent_execution(self, client: TestClient, test_db: Session, test_user: User):
        """Cover handling of nonexistent execution ID."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-error-2",
            "form_data": {"field1": "value1"},
            "agent_execution_id": str(uuid.uuid4())  # Nonexistent execution
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # The route accepts the field without resolving it
            response = client.post("/api/canvas/submit", json=submission_data)
            assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_execution_completion_error(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover non-fatal audit persistence failure."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-error-3",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Audit persistence goes through the global get_db_session and is
            # non-fatal (logged + swallowed) — a failing session must not fail
            # the submission.
            from core.database import get_db_session
            with patch('core.database.get_db_session', side_effect=RuntimeError("DB down")):
                response = client.post("/api/canvas/submit", json=submission_data)
                assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_submit_form_empty_form_data(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with empty form_data."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-empty",
            "form_data": {},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            with patch_global_db(test_db):
                response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True

            # Verify audit shows empty form data
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-empty"
            ).first()
            assert audit.details_json["form_data"] == {}

        client.app.dependency_overrides.clear()

    def test_submit_form_special_characters(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover form submission with special characters in data."""
        from core.auth import get_current_user
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
        from core.auth import get_current_user
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
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-multi",
            "form_data": {"step": "1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            with patch_global_db(test_db):
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
        from core.auth import get_current_user
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

                # Autonomous agent passes the governance check regardless
                assert response.status_code == 200

        client.app.dependency_overrides.clear()

    def test_governance_check_allowed(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover governance check that returns allowed."""
        from core.auth import get_current_user
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
            assert result["success"] is True

        client.app.dependency_overrides.clear()

    def test_governance_audit_logging(self, client: TestClient, test_db: Session, test_user: User, autonomous_agent: AgentRegistry):
        """Cover audit logging on governance-allowed submission."""
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-form-audit",
            "form_data": {"field1": "value1"},
            "agent_id": autonomous_agent.id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            with patch_global_db(test_db):
                response = client.post("/api/canvas/submit", json=submission_data)

            assert response.status_code == 200

            # Verify audit row records the acting agent
            audit = test_db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == "test-form-audit"
            ).first()

            assert audit is not None
            assert audit.agent_id == autonomous_agent.id

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
        from core.auth import get_current_user
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
        from core.auth import get_current_user
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
            confidence_score=confidence_score,
            workspace_id="default"
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
        from core.auth import get_current_user
        client.app.dependency_overrides[get_current_user] = lambda: test_user

        submission_data = {
            "canvas_id": "test-invalid-agent",
            "form_data": {"field1": "value1"},
            "agent_id": invalid_agent_id
        }

        with patch('core.websockets.manager.broadcast', new_callable=AsyncMock):
            # Empty string is falsy → no governance path → accepted.
            # Unknown non-empty IDs → governance "Agent not found" → 403.
            response = client.post("/api/canvas/submit", json=submission_data)
            if invalid_agent_id == "":
                assert response.status_code == 200
            else:
                assert response.status_code == 403

        client.app.dependency_overrides.clear()
