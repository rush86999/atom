"""
Comprehensive test coverage for Smart Home Routes API endpoints.

Tests Philips Hue and Home Assistant integration endpoints:
- Hue bridge discovery, connection, light control
- Home Assistant states, service calls, entity queries
- Error handling (401, 403, 404, 503)
- Authentication and governance checks

Target: 75%+ coverage (141+ lines of 188)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI

from api.smarthome_routes import router
from core.models import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    return user


@pytest.fixture
def client():
    """Create FastAPI TestClient for smart home routes."""
    app = FastAPI()
    app.include_router(router)

    # Mock get_current_user dependency
    async def get_current_user_override():
        return Mock(id="test-user-123", username="testuser")

    from core.security_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = get_current_user_override

    return TestClient(app)


@pytest.fixture
def smarthome_mocks():
    """Mock smart home tool functions."""
    mocks = {}

    # Hue mocks
    mocks["hue_discover_bridges"] = AsyncMock(return_value={
        "success": True,
        "bridges": ["192.168.1.100", "192.168.1.101"],
        "count": 2
    })

    mocks["hue_get_lights"] = AsyncMock(return_value={
        "success": True,
        "lights": [
            {"id": "1", "name": "Living Room", "state": {"on": True, "brightness": 254}},
            {"id": "2", "name": "Bedroom", "state": {"on": False, "brightness": 0}}
        ],
        "count": 2
    })

    mocks["hue_set_light_state"] = AsyncMock(return_value={
        "success": True,
        "light_id": "1",
        "state": {"on": True, "brightness": 128, "color_xy": [0.5, 0.5]}
    })

    # Home Assistant mocks
    mocks["home_assistant_get_states"] = AsyncMock(return_value={
        "success": True,
        "states": [
            {"entity_id": "light.living_room", "state": "on", "attributes": {"brightness": 255}},
            {"entity_id": "switch.kitchen", "state": "on"},
            {"entity_id": "group.all_lights", "state": "on"}
        ],
        "count": 3
    })

    mocks["home_assistant_call_service"] = AsyncMock(return_value={
        "success": True,
        "service": "turn_on",
        "entity_id": "light.living_room"
    })

    mocks["home_assistant_get_lights"] = AsyncMock(return_value={
        "success": True,
        "lights": [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "light.bedroom", "state": "off"}
        ],
        "count": 2
    })

    return mocks


# ============================================================================
# Hue Bridge Endpoints
# ============================================================================

class TestHueBridgeEndpoints:
    """Test Hue bridge discovery and connection endpoints."""

    def test_get_hue_bridges_success(self, client, smarthome_mocks):
        """Test discovering Hue bridges successfully."""
        with patch("api.smarthome_routes.hue_discover_bridges", smarthome_mocks["hue_discover_bridges"]):
            response = client.get("/api/smarthome/hue/bridges")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "bridges" in data
            assert data["count"] == 2

    def test_get_hue_bridges_discovery_failed(self, client, smarthome_mocks):
        """Test Hue bridge discovery failure."""
        smarthome_mocks["hue_discover_bridges"].return_value = {
            "success": False,
            "error": "Network discovery failed"
        }
        with patch("api.smarthome_routes.hue_discover_bridges", smarthome_mocks["hue_discover_bridges"]):
            response = client.get("/api/smarthome/hue/bridges")
            assert response.status_code == 503

    def test_get_hue_bridges_permission_blocked(self, client, smarthome_mocks):
        """Test Hue bridge discovery blocked by governance."""
        smarthome_mocks["hue_discover_bridges"].side_effect = PermissionError("Insufficient maturity level")
        with patch("api.smarthome_routes.hue_discover_bridges", smarthome_mocks["hue_discover_bridges"]):
            response = client.get("/api/smarthome/hue/bridges")
            assert response.status_code == 403

    def test_connect_hue_bridge_success(self, client, smarthome_mocks):
        """Test connecting to Hue bridge successfully."""
        request_data = {
            "bridge_ip": "192.168.1.100",
            "api_key": "test-api-key",
            "name": "Test Bridge"
        }
        with patch("api.smarthome_routes.hue_get_lights", smarthome_mocks["hue_get_lights"]):
            response = client.post("/api/smarthome/hue/connect", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["bridge_ip"] == "192.168.1.100"
            assert data["light_count"] == 2

    def test_connect_hue_bridge_invalid_credentials(self, client, smarthome_mocks):
        """Test connecting with invalid Hue credentials."""
        smarthome_mocks["hue_get_lights"].return_value = {
            "success": False,
            "error": "Unauthorized"
        }
        request_data = {
            "bridge_ip": "192.168.1.100",
            "api_key": "invalid-key"
        }
        with patch("api.smarthome_routes.hue_get_lights", smarthome_mocks["hue_get_lights"]):
            response = client.post("/api/smarthome/hue/connect", json=request_data)
            assert response.status_code == 401


# ============================================================================
# Hue Light Endpoints
# ============================================================================

class TestHueLightEndpoints:
    """Test Hue light control endpoints."""

    def test_get_hue_lights_success(self, client, smarthome_mocks):
        """Test getting all Hue lights successfully."""
        params = {
            "bridge_ip": "192.168.1.100",
            "api_key": "test-api-key"
        }
        with patch("api.smarthome_routes.hue_get_lights", smarthome_mocks["hue_get_lights"]):
            response = client.get("/api/smarthome/hue/lights", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["lights"]) == 2

    def test_get_hue_lights_permission_blocked(self, client, smarthome_mocks):
        """Test getting Hue lights blocked by governance."""
        smarthome_mocks["hue_get_lights"].side_effect = PermissionError("Blocked")
        params = {
            "bridge_ip": "192.168.1.100",
            "api_key": "test-api-key"
        }
        with patch("api.smarthome_routes.hue_get_lights", smarthome_mocks["hue_get_lights"]):
            response = client.get("/api/smarthome/hue/lights", params=params)
            assert response.status_code == 403

    def test_set_hue_light_state_success(self, client, smarthome_mocks):
        """Test setting Hue light state successfully."""
        request_data = {
            "bridge_ip": "192.168.1.100",
            "api_key": "test-api-key",
            "light_id": "1",
            "on": True,
            "brightness": 128
        }
        with patch("api.smarthome_routes.hue_set_light_state", smarthome_mocks["hue_set_light_state"]):
            response = client.put("/api/smarthome/hue/lights/1/state", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_set_hue_light_state_not_found(self, client, smarthome_mocks):
        """Test setting non-existent Hue light state."""
        smarthome_mocks["hue_set_light_state"].return_value = {
            "success": False,
            "error": "Light not found"
        }
        request_data = {
            "bridge_ip": "192.168.1.100",
            "api_key": "test-api-key",
            "light_id": "999"
        }
        with patch("api.smarthome_routes.hue_set_light_state", smarthome_mocks["hue_set_light_state"]):
            response = client.put("/api/smarthome/hue/lights/999/state", json=request_data)
            assert response.status_code == 404

    def test_set_hue_light_state_permission_blocked(self, client, smarthome_mocks):
        """Test setting Hue light state blocked by governance."""
        smarthome_mocks["hue_set_light_state"].side_effect = PermissionError("Blocked")
        request_data = {
            "bridge_ip": "192.168.1.100",
            "api_key": "test-api-key",
            "light_id": "1"
        }
        with patch("api.smarthome_routes.hue_set_light_state", smarthome_mocks["hue_set_light_state"]):
            response = client.put("/api/smarthome/hue/lights/1/state", json=request_data)
            assert response.status_code == 403


# ============================================================================
# Home Assistant Connection Endpoints
# ============================================================================

class TestHomeAssistantConnectionEndpoints:
    """Test Home Assistant connection endpoints."""

    def test_connect_home_assistant_success(self, client, smarthome_mocks):
        """Test connecting to Home Assistant successfully."""
        request_data = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token",
            "name": "Test HA"
        }
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            response = client.post("/api/smarthome/homeassistant/connect", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["url"] == "http://homeassistant.local:8123"

    def test_connect_home_assistant_invalid_credentials(self, client, smarthome_mocks):
        """Test connecting with invalid Home Assistant credentials."""
        smarthome_mocks["home_assistant_get_states"].return_value = {
            "success": False,
            "error": "Unauthorized"
        }
        request_data = {
            "url": "http://homeassistant.local:8123",
            "token": "invalid-token"
        }
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            response = client.post("/api/smarthome/homeassistant/connect", json=request_data)
            assert response.status_code == 401


# ============================================================================
# Home Assistant State Endpoints
# ============================================================================

class TestHomeAssistantStateEndpoints:
    """Test Home Assistant state query endpoints."""

    def test_get_home_assistant_states_success(self, client, smarthome_mocks):
        """Test getting all Home Assistant states successfully."""
        params = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token"
        }
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            response = client.get("/api/smarthome/homeassistant/states", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["states"]) == 3

    def test_get_home_assistant_states_permission_blocked(self, client, smarthome_mocks):
        """Test getting HA states blocked by governance."""
        smarthome_mocks["home_assistant_get_states"].side_effect = PermissionError("Blocked")
        params = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token"
        }
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            response = client.get("/api/smarthome/homeassistant/states", params=params)
            assert response.status_code == 403

    def test_get_home_assistant_state_success(self, client, smarthome_mocks):
        """Test getting single Home Assistant entity state."""
        params = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token"
        }
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            response = client.get("/api/smarthome/homeassistant/states/light.living_room", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["entity"]["entity_id"] == "light.living_room"

    def test_get_home_assistant_state_not_found(self, client, smarthome_mocks):
        """Test getting non-existent Home Assistant entity."""
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            params = {
                "url": "http://homeassistant.local:8123",
                "token": "test-token"
            }
            response = client.get("/api/smarthome/homeassistant/states/sensor.nonexistent", params=params)
            assert response.status_code == 404


# ============================================================================
# Home Assistant Service Endpoints
# ============================================================================

class TestHomeAssistantServiceEndpoints:
    """Test Home Assistant service call endpoints."""

    def test_call_home_assistant_service_success(self, client, smarthome_mocks):
        """Test calling Home Assistant service successfully."""
        request_data = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token",
            "domain": "light",
            "service": "turn_on",
            "entity_id": "light.living_room"
        }
        with patch("api.smarthome_routes.home_assistant_call_service", smarthome_mocks["home_assistant_call_service"]):
            response = client.post("/api/smarthome/homeassistant/services/light/turn_on", json=request_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_call_home_assistant_service_not_found(self, client, smarthome_mocks):
        """Test calling non-existent Home Assistant service."""
        smarthome_mocks["home_assistant_call_service"].return_value = {
            "success": False,
            "error": "Service not found"
        }
        request_data = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token",
            "domain": "light",
            "service": "nonexistent"
        }
        with patch("api.smarthome_routes.home_assistant_call_service", smarthome_mocks["home_assistant_call_service"]):
            response = client.post("/api/smarthome/homeassistant/services/light/nonexistent", json=request_data)
            assert response.status_code == 404

    def test_call_home_assistant_service_invalid_request(self, client, smarthome_mocks):
        """Test calling service with invalid request data."""
        smarthome_mocks["home_assistant_call_service"].return_value = {
            "success": False,
            "error": "Invalid service data"
        }
        request_data = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token",
            "domain": "light",
            "service": "turn_on",
            "data": {"invalid": "data"}
        }
        with patch("api.smarthome_routes.home_assistant_call_service", smarthome_mocks["home_assistant_call_service"]):
            response = client.post("/api/smarthome/homeassistant/services/light/turn_on", json=request_data)
            assert response.status_code == 400

    def test_call_home_assistant_service_permission_blocked(self, client, smarthome_mocks):
        """Test calling HA service blocked by governance."""
        smarthome_mocks["home_assistant_call_service"].side_effect = PermissionError("Blocked")
        request_data = {
            "url": "http://homeassistant.local:8123",
            "token": "test-token",
            "domain": "light",
            "service": "turn_on"
        }
        with patch("api.smarthome_routes.home_assistant_call_service", smarthome_mocks["home_assistant_call_service"]):
            response = client.post("/api/smarthome/homeassistant/services/light/turn_on", json=request_data)
            assert response.status_code == 403


# ============================================================================
# Home Assistant Entity Type Endpoints
# ============================================================================

class TestHomeAssistantEntityTypeEndpoints:
    """Test Home Assistant entity type filtering endpoints."""

    def test_get_home_assistant_lights_success(self, client, smarthome_mocks):
        """Test getting Home Assistant lights."""
        with patch("api.smarthome_routes.home_assistant_get_lights", smarthome_mocks["home_assistant_get_lights"]):
            params = {
                "url": "http://homeassistant.local:8123",
                "token": "test-token"
            }
            response = client.get("/api/smarthome/homeassistant/lights", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["lights"]) == 2

    def test_get_home_assistant_switches_success(self, client, smarthome_mocks):
        """Test getting Home Assistant switches."""
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            params = {
                "url": "http://homeassistant.local:8123",
                "token": "test-token"
            }
            response = client.get("/api/smarthome/homeassistant/switches", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["switches"]) == 1

    def test_get_home_assistant_groups_success(self, client, smarthome_mocks):
        """Test getting Home Assistant groups."""
        with patch("api.smarthome_routes.home_assistant_get_states", smarthome_mocks["home_assistant_get_states"]):
            params = {
                "url": "http://homeassistant.local:8123",
                "token": "test-token"
            }
            response = client.get("/api/smarthome/homeassistant/groups", params=params)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["groups"]) == 1
