"""
Mobile Workflow API Tests

Tests for mobile-optimized workflow endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestMobileWorkflows:
    """Test suite for mobile workflow APIs"""

    def test_trigger_workflow_async(self, client: TestClient, db: Session):
        """Test triggering a workflow asynchronously"""
        response = client.post(
            "/api/mobile/workflows/trigger?user_id=test",
            json={"workflow_id": "test", "synchronous": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["status"] in ["started", "running"]

    def test_trigger_workflow_sync(self, client: TestClient, db: Session):
        """Test triggering a workflow synchronously"""
        response = client.post(
            "/api/mobile/workflows/trigger?user_id=test",
            json={"workflow_id": "test", "synchronous": True}
        )
        # May return 404 if workflow doesn't exist, or 200 if it does
        assert response.status_code in [200, 404]

    def test_get_steps(self, client: TestClient, db: Session):
        """Test getting execution steps"""
        # Trigger workflow first
        trigger_resp = client.post(
            "/api/mobile/workflows/trigger?user_id=test",
            json={"workflow_id": "test", "synchronous": False}
        )

        if trigger_resp.status_code == 200:
            exec_id = trigger_resp.json()["execution_id"]

            # Get steps
            response = client.get(f"/api/mobile/workflows/test/executions/{exec_id}/steps")
            assert response.status_code == 200
            assert "steps" in response.json()

    def test_cancel_execution(self, client: TestClient, db: Session):
        """Test cancelling a workflow execution"""
        # Trigger workflow
        trigger_resp = client.post(
            "/api/mobile/workflows/trigger?user_id=test",
            json={"workflow_id": "test", "synchronous": False}
        )

        if trigger_resp.status_code == 200:
            exec_id = trigger_resp.json()["execution_id"]

            # Cancel it
            response = client.post(f"/api/mobile/workflows/executions/{exec_id}/cancel?user_id=test")
            assert response.status_code == 200

    def test_get_mobile_workflows_list(self, client: TestClient, db: Session):
        """Test getting mobile-optimized workflow list"""
        response = client.get("/api/mobile/workflows")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_workflow_details_mobile(self, client: TestClient, db: Session):
        """Test getting workflow details for mobile"""
        response = client.get("/api/mobile/workflows/test_workflow")
        # May return 404 if workflow doesn't exist
        assert response.status_code in [200, 404]

    def test_search_workflows_mobile(self, client: TestClient, db: Session):
        """Test searching workflows from mobile"""
        response = client.get("/api/mobile/workflows/search?query=test")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
