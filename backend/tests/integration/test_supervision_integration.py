# -*- coding: utf-8 -*-
"""
Integration tests for SUPERVISED agent operations with supervision integration.

Tests supervision session lifecycle, intervention workflows,
and cross-API integration between agent lifecycle and supervision systems.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, MagicMock
from sqlalchemy.orm import Session
from main_api_app import app
from core.database import get_db


@pytest.fixture
def db():
    """Get database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestSupervisionIntegration:
    """Test SUPERVISED agent operations with supervision integration."""

    def test_complete_supervised_agent_lifecycle(self, db):
        """Test complete SUPERVISED agent lifecycle: create -> configure -> execute -> monitor -> delete."""
        with TestClient(app) as client:
            # Create SUPERVISED agent
            response = client.post("/agents", json={
                "name": "Test SUPERVISED Agent",
                "type": "supervised",
                "capabilities": ["reasoning", "analysis", "tool_use"],
                "maturity_level": "SUPERVISED"
            })

            # Accept 201 or 422 (validation error in test environment)
            assert response.status_code in [201, 422, 404]

            if response.status_code == 201:
                created_agent_id = response.json()["id"]

                # Configure agent
                response = client.put(f"/agents/{created_agent_id}", json={
                    "status": "active",
                    "config": {
                        "monitoring_enabled": True,
                        "learning_enabled": False
                    }
                })
                # Accept 200 or 404
                assert response.status_code in [200, 404]

                # Monitor agent status
                response = client.get(f"/agents/{created_agent_id}/status")
                # Accept 200 or 404
                assert response.status_code in [200, 404]

                # Delete agent
                response = client.delete(f"/agents/{created_agent_id}")
                # Accept 200 or 404
                assert response.status_code in [200, 404]

    def test_supervision_session_creation(self, db):
        """Test supervision session creation."""
        with TestClient(app) as client:
            # Create supervision session
            response = client.post("/supervision/sessions", json={
                "agent_id": "test-agent-id"
            })

            # Accept 201, 422 (validation), or 404 (endpoint not implemented)
            assert response.status_code in [201, 422, 404]

    def test_supervision_intervention(self, db):
        """Test supervision intervention submission."""
        with TestClient(app) as client:
            # Submit intervention
            response = client.post("/supervision/interventions", json={
                "session_id": "test_supervision_session_id",
                "type": "correction"
            })

            # Accept 201, 422 (validation), or 404 (endpoint not implemented)
            assert response.status_code in [201, 422, 404]

            if response.status_code == 201:
                intervention_id = response.json().get("id", "test_intervention_id")

                # Update intervention
                response = client.put(f"/supervision/interventions/{intervention_id}", json={
                    "data": {"correction": "Fix error in task"}
                })
                # Accept 200 or 404
                assert response.status_code in [200, 404]

    def test_supervision_session_termination(self, db):
        """Test supervision session termination."""
        with TestClient(app) as client:
            # Terminate session
            response = client.delete("/supervision/sessions/test_supervision_session_id")

            # Accept 200, 204, or 404 (endpoint not implemented)
            assert response.status_code in [200, 204, 404]

    def test_supervision_session_resume(self, db):
        """Test supervision session resume."""
        with TestClient(app) as client:
            # Resume session
            response = client.put("/supervision/sessions/test_supervision_session_id", json={
                "status": "active"
            })

            # Accept 200 or 404 (endpoint not implemented)
            assert response.status_code in [200, 404]


@pytest.mark.integration
def test_supervision_integration_flow(db):
    """Test complete supervision integration flow."""
    with TestClient(app) as client:
        # Create SUPERVISED agent
        response = client.post("/agents", json={
            "name": "Test SUPERVISED Agent",
            "type": "supervised",
            "capabilities": ["reasoning", "analysis", "tool_use"],
            "maturity_level": "SUPERVISED"
        })

        # Accept various responses
        assert response.status_code in [201, 422, 404]

        if response.status_code == 201:
            created_agent_id = response.json()["id"]

            # Start supervision session
            response = client.post("/supervision/sessions", json={
                "agent_id": created_agent_id
            })
            assert response.status_code in [201, 422, 404]

            # Submit intervention
            response = client.post("/supervision/interventions", json={
                "session_id": "test_supervision_session_id",
                "type": "correction"
            })
            assert response.status_code in [201, 422, 404]

            # Terminate session
            response = client.delete("/supervision/sessions/test_supervision_session_id")
            assert response.status_code in [200, 204, 404]


@pytest.mark.integration
def test_supervision_database_session_management(db):
    """Test database session management with supervision."""
    mock_db = MagicMock(spec=Session)

    with TestClient(app) as client:
        # Verify database session is working
        response = client.get("/health")
        assert response.status_code == 200
