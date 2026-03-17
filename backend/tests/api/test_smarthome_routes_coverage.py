"""
Smart Home Routes Coverage Tests

Comprehensive TestClient-based tests for smarthome API endpoints to achieve 60%+ coverage.

Coverage Target:
- api/smarthome_routes.py - 60%+ coverage (113+ lines)

Test Classes:
- TestSmarthomeRoutes (10 tests): Device discovery, connection, status
- TestDeviceCommands (12 tests): Light control, scenes, service calls
- TestSmarthomeIntegration (8 tests): Room grouping, automation, entity filtering
- TestSmarthomeErrors (5 tests): Invalid devices, offline devices, command failures

Baseline: 0% coverage (smarthome_routes.py not tested)
Target: 60%+ coverage (113+ lines)
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session


# Import smarthome routes router
from api.smarthome_routes import router as smarthome_router
from core.models import User


# Create minimal FastAPI app for testing smarthome routes
app = FastAPI()
app.include_router(smarthome_router, tags=["smarthome"])


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def smarthome_test_client(mock_user):
    """Create TestClient for smarthome routes testing."""
    def get_current_user_override():
        return mock_user

    app.dependency_overrides[get_current_user] = get_current_user_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def mock_user():
    """Create mock user for authentication."""
    user = User(
        id="test-user-123",
        email="test@example.com"
    )
    return user


@pytest.fixture(scope="function")
def mock_db():
    """Create mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture(scope="function")
def smarthome_test_client(mock_user):
    """Create TestClient for smarthome routes testing."""
    def get_current_user_override():
        return mock_user

    def get_db_override():
        return MagicMock(spec=Session)

    app.dependency_overrides[get_current_user] = get_current_user_override
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def mock_db():
    """Create mock database session."""
    return MagicMock(spec=Session)


# ============================================================================
# Test Class: TestSmarthomeRoutes
# ============================================================================

class TestSmarthomeRoutes:
    """Tests for smarthome discovery and connection endpoints."""

    @patch("api.smarthome_routes.hue_discover_bridges")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_hue_bridges_success(
        self, mock_get_user, mock_hue_discover, smarthome_test_client, mock_user
    ):
        """Test successful Hue bridge discovery."""
        mock_get_user.return_value = mock_user
        mock_hue_discover.return_value = {
            "success": True,
            "bridges": ["192.168.1.100", "192.168.1.101"]
        }

        response = smarthome_test_client.get("/api/smarthome/hue/bridges")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "bridges" in data

    @patch("api.smarthome_routes.hue_discover_bridges")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_hue_bridges_discovery_failed(
        self, mock_get_user, mock_hue_discover, smarthome_test_client, mock_user
    ):
        """Test Hue bridge discovery failure."""
        mock_get_user.return_value = mock_user
        mock_hue_discover.return_value = {
            "success": False,
            "error": "Network discovery failed"
        }

        response = smarthome_test_client.get("/api/smarthome/hue/bridges")

        assert response.status_code == 503

    @patch("api.smarthome_routes.hue_discover_bridges")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_hue_bridges_permission_denied(
        self, mock_get_user, mock_hue_discover, smarthome_test_client, mock_user
    ):
        """Test Hue bridge discovery blocked by permission."""
        mock_get_user.return_value = mock_user
        mock_hue_discover.side_effect = PermissionError("Insufficient maturity level")

        response = smarthome_test_client.get("/api/smarthome/hue/bridges")

        assert response.status_code == 403
        data = response.json()
        assert "Insufficient maturity level" in data["detail"]

    @patch("api.smarthome_routes.hue_get_lights")
    @patch("api.smarthome_routes.get_current_user")
    @patch("api.smarthome_routes.get_db")
    def test_connect_hue_bridge_success(
        self, mock_get_db, mock_get_user, mock_hue_get_lights, smarthome_test_client, mock_user, mock_db
    ):
        """Test successful Hue bridge connection."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_hue_get_lights.return_value = {
            "success": True,
            "lights": [{"id": "1", "name": "Living Room"}],
            "count": 1
        }

        response = smarthome_test_client.post(
            "/api/smarthome/hue/connect",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-api-key",
                "name": "Hue Bridge"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bridge_ip"] == "192.168.1.100"

    @patch("api.smarthome_routes.hue_get_lights")
    @patch("api.smarthome_routes.get_current_user")
    @patch("api.smarthome_routes.get_db")
    def test_connect_hue_bridge_invalid_credentials(
        self, mock_get_db, mock_get_user, mock_hue_get_lights, smarthome_test_client, mock_user, mock_db
    ):
        """Test Hue bridge connection with invalid credentials."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_hue_get_lights.return_value = {
            "success": False,
            "error": "Unauthorized"
        }

        response = smarthome_test_client.post(
            "/api/smarthome/hue/connect",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "invalid-key"
            }
        )

        assert response.status_code == 401

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    @patch("api.smarthome_routes.get_db")
    def test_connect_home_assistant_success(
        self, mock_get_db, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user, mock_db
    ):
        """Test successful Home Assistant connection."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [{"entity_id": "light.living_room"}],
            "count": 1
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/connect",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    @patch("api.smarthome_routes.get_db")
    def test_connect_home_assistant_invalid_credentials(
        self, mock_get_db, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user, mock_db
    ):
        """Test Home Assistant connection with invalid credentials."""
        mock_get_user.return_value = mock_user
        mock_get_db.return_value = mock_db
        mock_ha_get_states.return_value = {
            "success": False,
            "error": "Unauthorized"
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/connect",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "invalid-token"
            }
        )

        assert response.status_code == 401

    @patch("api.smarthome_routes.hue_get_lights")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_hue_lights_success(
        self, mock_get_user, mock_hue_get_lights, smarthome_test_client, mock_user
    ):
        """Test successful Hue lights retrieval."""
        mock_get_user.return_value = mock_user
        mock_hue_get_lights.return_value = {
            "success": True,
            "lights": [{"id": "1", "name": "Living Room"}]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/hue/lights",
            params={"bridge_ip": "192.168.1.100", "api_key": "test-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_home_assistant_states_success(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test successful Home Assistant states retrieval."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [{"entity_id": "light.living_room", "state": "on"}],
            "count": 10
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/states",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["states"]) == 10


# ============================================================================
# Test Class: TestDeviceCommands
# ============================================================================

class TestDeviceCommands:
    """Tests for device control commands."""

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_turn_on(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test turning on Hue light."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.return_value = {
            "success": True,
            "light_id": "1",
            "on": True
        }

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "on": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["on"] is True

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_turn_off(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test turning off Hue light."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.return_value = {
            "success": True,
            "light_id": "1",
            "on": False
        }

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "on": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["on"] is False

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_brightness(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test setting Hue light brightness."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.return_value = {
            "success": True,
            "light_id": "1",
            "brightness": 0.8
        }

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "brightness": 0.8
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["brightness"] == 0.8

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_color(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test setting Hue light color."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.return_value = {
            "success": True,
            "light_id": "1",
            "color_xy": [0.5, 0.5]
        }

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "color_xy": [0.5, 0.5]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["color_xy"] == [0.5, 0.5]

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_not_found(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test setting state of non-existent Hue light."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.return_value = {
            "success": False,
            "error": "Light 999 not found"
        }

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/999/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "on": True
            }
        )

        assert response.status_code == 404

    @patch("api.smarthome_routes.home_assistant_call_service")
    @patch("api.smarthome_routes.get_current_user")
    def test_call_ha_service_turn_on(
        self, mock_get_user, mock_ha_call_service, smarthome_test_client, mock_user
    ):
        """Test calling Home Assistant turn_on service."""
        mock_get_user.return_value = mock_user
        mock_ha_call_service.return_value = {
            "success": True,
            "service": "turn_on",
            "entity_id": "light.living_room"
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/services/light/turn_on",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token",
                "entity_id": "light.living_room"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("api.smarthome_routes.home_assistant_call_service")
    @patch("api.smarthome_routes.get_current_user")
    def test_call_ha_service_turn_off(
        self, mock_get_user, mock_ha_call_service, smarthome_test_client, mock_user
    ):
        """Test calling Home Assistant turn_off service."""
        mock_get_user.return_value = mock_user
        mock_ha_call_service.return_value = {
            "success": True,
            "service": "turn_off",
            "entity_id": "switch.kitchen"
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/services/switch/turn_off",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token",
                "entity_id": "switch.kitchen"
            }
        )

        assert response.status_code == 200

    @patch("api.smarthome_routes.home_assistant_call_service")
    @patch("api.smarthome_routes.get_current_user")
    def test_call_ha_service_with_data(
        self, mock_get_user, mock_ha_call_service, smarthome_test_client, mock_user
    ):
        """Test calling Home Assistant service with data parameters."""
        mock_get_user.return_value = mock_user
        mock_ha_call_service.return_value = {
            "success": True
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/services/light/turn_on",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token",
                "entity_id": "light.living_room",
                "data": {"brightness": 255, "color_name": "red"}
            }
        )

        assert response.status_code == 200

    @patch("api.smarthome_routes.home_assistant_call_service")
    @patch("api.smarthome_routes.get_current_user")
    def test_call_ha_service_entity_not_found(
        self, mock_get_user, mock_ha_call_service, smarthome_test_client, mock_user
    ):
        """Test calling HA service on non-existent entity."""
        mock_get_user.return_value = mock_user
        mock_ha_call_service.return_value = {
            "success": False,
            "error": "Entity light.nonexistent not found"
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/services/light/turn_on",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token",
                "entity_id": "light.nonexistent"
            }
        )

        assert response.status_code == 404

    @patch("api.smarthome_routes.home_assistant_call_service")
    @patch("api.smarthome_routes.get_current_user")
    def test_call_ha_service_invalid_data(
        self, mock_get_user, mock_ha_call_service, smarthome_test_client, mock_user
    ):
        """Test calling HA service with invalid data."""
        mock_get_user.return_value = mock_user
        mock_ha_call_service.return_value = {
            "success": False,
            "error": "Invalid brightness value"
        }

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/services/light/turn_on",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token",
                "data": {"brightness": "invalid"}
            }
        )

        assert response.status_code == 400

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_combined_parameters(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test setting Hue light with combined parameters."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.return_value = {
            "success": True,
            "light_id": "1",
            "on": True,
            "brightness": 0.9,
            "color_xy": [0.6, 0.4]
        }

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "on": True,
                "brightness": 0.9,
                "color_xy": [0.6, 0.4]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["on"] is True
        assert data["brightness"] == 0.9


# ============================================================================
# Test Class: TestSmarthomeIntegration
# ============================================================================

class TestSmarthomeIntegration:
    """Tests for smarthome integration features."""

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_single_entity_state(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting single Home Assistant entity state."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [
                {"entity_id": "light.living_room", "state": "on", "attributes": {"brightness": 255}},
                {"entity_id": "light.kitchen", "state": "off"}
            ]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/states/light.living_room",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["entity"]["entity_id"] == "light.living_room"

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_entity_not_found(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting non-existent HA entity."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [{"entity_id": "light.living_room"}]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/states/light.nonexistent",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 404

    @patch("api.smarthome_routes.home_assistant_get_lights")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_lights(
        self, mock_get_user, mock_ha_get_lights, smarthome_test_client, mock_user
    ):
        """Test getting Home Assistant lights."""
        mock_get_user.return_value = mock_user
        mock_ha_get_lights.return_value = {
            "success": True,
            "lights": [
                {"entity_id": "light.living_room", "state": "on"},
                {"entity_id": "light.kitchen", "state": "off"}
            ],
            "count": 2
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/lights",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_switches(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting Home Assistant switches."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [
                {"entity_id": "switch.kitchen", "state": "on"},
                {"entity_id": "switch.living_room", "state": "off"},
                {"entity_id": "light.living_room", "state": "on"}  # Not a switch
            ]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/switches",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2  # Only switches, not lights

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_groups(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting Home Assistant groups."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [
                {"entity_id": "group.all_lights", "state": "on"},
                {"entity_id": "group.kitchen Appliances", "state": "off"},
                {"entity_id": "light.living_room", "state": "on"}  # Not a group
            ]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/groups",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2  # Only groups

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_states_empty_list(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting HA states with empty list."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [],
            "count": 0
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/states",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_switches_no_switches(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting HA switches when no switches present."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [
                {"entity_id": "light.living_room"},
                {"entity_id": "sensor.temperature"}
            ]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/switches",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_get_ha_groups_no_groups(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test getting HA groups when no groups present."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.return_value = {
            "success": True,
            "states": [
                {"entity_id": "light.living_room"},
                {"entity_id": "switch.kitchen"}
            ]
        }

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/groups",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


# ============================================================================
# Test Class: TestSmarthomeErrors
# ============================================================================

class TestSmarthomeErrors:
    """Tests for smarthome error handling."""

    @patch("api.smarthome_routes.hue_discover_bridges")
    @patch("api.smarthome_routes.get_current_user")
    def test_hue_discovery_exception(
        self, mock_get_user, mock_hue_discover, smarthome_test_client, mock_user
    ):
        """Test Hue discovery exception handling."""
        mock_get_user.return_value = mock_user
        mock_hue_discover.side_effect = Exception("Network timeout")

        response = smarthome_test_client.get("/api/smarthome/hue/bridges")

        assert response.status_code == 503
        data = response.json()
        assert "Failed to discover Hue bridges" in data["detail"]

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_set_hue_light_exception(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test Hue light state change exception handling."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.side_effect = Exception("Bridge offline")

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "on": True
            }
        )

        assert response.status_code == 503
        data = response.json()
        assert "Failed to set light state" in data["detail"]

    @patch("api.smarthome_routes.home_assistant_call_service")
    @patch("api.smarthome_routes.get_current_user")
    def test_ha_service_call_exception(
        self, mock_get_user, mock_ha_call_service, smarthome_test_client, mock_user
    ):
        """Test Home Assistant service call exception handling."""
        mock_get_user.return_value = mock_user
        mock_ha_call_service.side_effect = Exception("Home Assistant unavailable")

        response = smarthome_test_client.post(
            "/api/smarthome/homeassistant/services/light/turn_on",
            json={
                "url": "http://homeassistant.local:8123",
                "token": "test-token"
            }
        )

        assert response.status_code == 503
        data = response.json()
        assert "Failed to call service" in data["detail"]

    @patch("api.smarthome_routes.home_assistant_get_states")
    @patch("api.smarthome_routes.get_current_user")
    def test_ha_get_states_permission_denied(
        self, mock_get_user, mock_ha_get_states, smarthome_test_client, mock_user
    ):
        """Test HA get states blocked by permission."""
        mock_get_user.return_value = mock_user
        mock_ha_get_states.side_effect = PermissionError("Insufficient maturity level")

        response = smarthome_test_client.get(
            "/api/smarthome/homeassistant/states",
            params={"url": "http://homeassistant.local:8123", "token": "test-token"}
        )

        assert response.status_code == 403

    @patch("api.smarthome_routes.hue_set_light_state")
    @patch("api.smarthome_routes.get_current_user")
    def test_hue_set_light_permission_denied(
        self, mock_get_user, mock_hue_set_state, smarthome_test_client, mock_user
    ):
        """Test Hue light state change blocked by permission."""
        mock_get_user.return_value = mock_user
        mock_hue_set_state.side_effect = PermissionError("AUTONOMOUS maturity required")

        response = smarthome_test_client.put(
            "/api/smarthome/hue/lights/1/state",
            json={
                "bridge_ip": "192.168.1.100",
                "api_key": "test-key",
                "on": True
            }
        )

        assert response.status_code == 403
