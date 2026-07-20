import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main_api_app import app
from core.models import User

@pytest.fixture
def mock_current_user():
    return User(
        id="user_123",
        email="test@example.com",
        tenant_id="t1"
    )

def test_harness_evolution_endpoint_requires_auth():
    client = TestClient(app)
    response = client.get("/api/chat/harness-evolution")
    # Should require authorization/current_user dependency
    assert response.status_code == 401

def test_harness_evolution_endpoint_success(mock_current_user):
    # Override authentication dependency
    from core.security_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    client = TestClient(app)

    # Mock database queries and harness service
    mock_db = MagicMock()
    
    with patch("core.database.get_db") as mock_get_db:
        # Mock get_db generator
        mock_get_db.return_value = iter([mock_db])
        
        # Mock HarnessEvolutionService.mine_weaknesses returning mock patterns
        with patch("core.harness_evolution_service.HarnessEvolutionService.mine_weaknesses") as mock_mine:
            mock_mine.return_value = [
                {"step_type": "action", "tool": "shell", "failure_count": 2, "examples": []}
            ]
            
            # Mock AgentRegistry queries
            mock_db.query().filter().all.return_value = []
            
            response = client.get("/api/chat/harness-evolution")
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is True
            assert len(data["mined_weaknesses"]) == 1
            assert data["mined_weaknesses"][0]["tool"] == "shell"

    # Clean up overrides
    app.dependency_overrides.clear()
