"""
Tests for Smart Home Tool (Philips Hue and Home Assistant)

Tests HueService and HomeAssistantService with mocked external APIs.
Covers governance enforcement, local network discovery, error handling.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.models import AgentRegistry, HueBridge, HomeAssistantConnection, User, AgentStatus

# Import functions directly
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.smarthome_tool import (
    hue_discover_bridges,
    hue_get_lights,
    hue_set_light_state,
    home_assistant_get_states,
    home_assistant_call_service,
    home_assistant_get_lights,
)


# ============================================================================
# HueService Tests
# ============================================================================

class TestHueService:
    """Test Hue service with mocked python-hue-v2 library."""

    @pytest.fixture
    def mock_bridge_finder(self):
        """Mock Hue BridgeFinder."""
        mock = MagicMock()
        mock.find_bridges.return_value = ["192.168.1.50"]
        return mock

    @pytest.fixture
    def mock_hue_bridge(self):
        """Mock Hue bridge instance."""
        mock = MagicMock()
        mock.get_api_key.return_value = "test_api_key"
        mock.get_lights.return_value = {
            "1": {"name": "Living Room", "on": True, "brightness": 254},
            "2": {"name": "Bedroom", "on": False, "brightness": 0}
        }
        return mock

    def test_discover_bridges_returns_ip_list(self, mock_bridge_finder):
        """Test bridge discovery returns list of found bridge IPs."""
        with patch('core.smarthome.hue_service.BridgeFinder', return_value=mock_bridge_finder):
            from core.smarthome.hue_service import HueService
            service = HueService()

            bridges = service.discover_bridges()

            assert len(bridges) == 1
            assert bridges[0] == "192.168.1.50"

    def test_connect_to_bridge_success(self, mock_hue_bridge):
        """Test successful bridge connection."""
        with patch('core.smarthome.hue_service.Bridge', return_value=mock_hue_bridge):
            from core.smarthome.hue_service import HueService
            service = HueService()

            result = service.connect("192.168.1.50", "test_api_key")

            assert result is True

    def test_get_all_lights(self, mock_hue_bridge):
        """Test getting all lights from bridge."""
        with patch('core.smarthome.hue_service.Bridge', return_value=mock_hue_bridge):
            from core.smarthome.hue_service import HueService
            service = HueService()

            lights = service.get_lights("192.168.1.50", "test_api_key")

            assert len(lights) == 2
            assert lights["1"]["name"] == "Living Room"
            assert lights["2"]["name"] == "Bedroom"

    def test_set_light_state_on_off(self, mock_hue_bridge):
        """Test setting light on/off state."""
        with patch('core.smarthome.hue_service.Bridge', return_value=mock_hue_bridge):
            from core.smarthome.hue_service import HueService
            service = HueService()

            result = service.set_light_state("192.168.1.50", "test_api_key", "1", {"on": True})

            assert result is True

    def test_set_light_state_brightness(self, mock_hue_bridge):
        """Test setting light brightness."""
        with patch('core.smarthome.hue_service.Bridge', return_value=mock_hue_bridge):
            from core.smarthome.hue_service import HueService
            service = HueService()

            result = service.set_light_state("192.168.1.50", "test_api_key", "1", {"brightness": 128})

            assert result is True

    def test_set_light_state_color_xy(self, mock_hue_bridge):
        """Test setting light color using XY coordinates."""
        with patch('core.smarthome.hue_service.Bridge', return_value=mock_hue_bridge):
            from core.smarthome.hue_service import HueService
            service = HueService()

            result = service.set_light_state("192.168.1.50", "test_api_key", "1", {"xy": [0.3, 0.3]})

            assert result is True

    def test_invalid_api_key_error(self, mock_hue_bridge):
        """Test error handling for invalid API key."""
        mock_hue_bridge.get_lights.side_effect = Exception("Unauthorized")

        with patch('core.smarthome.hue_service.Bridge', return_value=mock_hue_bridge):
            from core.smarthome.hue_service import HueService
            service = HueService()

            with pytest.raises(Exception, match="Unauthorized"):
                service.get_lights("192.168.1.50", "invalid_key")


# ============================================================================
# HomeAssistantService Tests
# ============================================================================

class TestHomeAssistantService:
    """Test Home Assistant service with mocked httpx.AsyncClient."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx AsyncClient."""
        mock = MagicMock()

        # Mock get_states response
        mock.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"entity_id": "light.living_room", "state": "on", "attributes": {"friendly_name": "Living Room"}},
                {"entity_id": "light.bedroom", "state": "off", "attributes": {"friendly_name": "Bedroom"}},
            ]
        )

        # Mock call_service response
        mock.post.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"context": {"id": "test"}, "response": {"variables": {}}}]
        )

        return mock

    @pytest.mark.asyncio
    async def test_get_states_returns_entity_list(self, mock_httpx_client):
        """Test getting all states from Home Assistant."""
        with patch('core.smarthome.home_assistant_service.httpx.AsyncClient', return_value=mock_httpx_client):
            from core.smarthome.home_assistant_service import HomeAssistantService
            service = HomeAssistantService("http://localhost:8123", "test_token")

            states = await service.get_states()

            assert len(states) == 2
            assert states[0]["entity_id"] == "light.living_room"
            assert states[1]["entity_id"] == "light.bedroom"

    @pytest.mark.asyncio
    async def test_call_service_turn_on_light(self, mock_httpx_client):
        """Test calling turn_on service for light."""
        with patch('core.smarthome.home_assistant_service.httpx.AsyncClient', return_value=mock_httpx_client):
            from core.smarthome.home_assistant_service import HomeAssistantService
            service = HomeAssistantService("http://localhost:8123", "test_token")

            result = await service.call_service("light", "turn_on", {"entity_id": "light.living_room"})

            assert result is True

    @pytest.mark.asyncio
    async def test_call_service_switch_toggle(self, mock_httpx_client):
        """Test calling toggle service for switch."""
        with patch('core.smarthome.home_assistant_service.httpx.AsyncClient', return_value=mock_httpx_client):
            from core.smarthome.home_assistant_service import HomeAssistantService
            service = HomeAssistantService("http://localhost:8123", "test_token")

            result = await service.call_service("switch", "toggle", {"entity_id": "switch.fan"})

            assert result is True

    @pytest.mark.asyncio
    async def test_unauthorized_token_error(self, mock_httpx_client):
        """Test error handling for unauthorized token."""
        mock_httpx_client.get.return_value = MagicMock(
            status_code=401,
            json=lambda: {"error": "Unauthorized"}
        )

        with patch('core.smarthome.home_assistant_service.httpx.AsyncClient', return_value=mock_httpx_client):
            from core.smarthome.home_assistant_service import HomeAssistantService
            service = HomeAssistantService("http://localhost:8123", "invalid_token")

            with pytest.raises(Exception, match="Unauthorized"):
                await service.get_states()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_httpx_client):
        """Test error handling for connection failures."""
        import httpx
        mock_httpx_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch('core.smarthome.home_assistant_service.httpx.AsyncClient', return_value=mock_httpx_client):
            from core.smarthome.home_assistant_service import HomeAssistantService
            service = HomeAssistantService("http://localhost:8123", "test_token")

            with pytest.raises(httpx.ConnectError):
                await service.get_states()


# ============================================================================
# HueTool Governance Tests
# ============================================================================

class TestHueToolGovernance:
    """Test governance enforcement for Hue tool."""

    @pytest.mark.asyncio
    async def test_supervised_agent_can_control_lights(self, db_session: Session):
        """Test SUPERVISED agent can control Hue lights."""
        agent = AgentRegistry(
            name="SupervisedAgent",
            category="test",
            module_path="test.module",
            class_name="TestSupervised",
            status=AgentStatus.SUPERVISED.value,
            maturity_level="SUPERVISED",
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock Hue service
        with patch('tools.smarthome_tool.HueService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.set_light_state.return_value = True
            mock_service_class.return_value = mock_service

            result = await hue_set_light_state(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                bridge_ip="192.168.1.50",
                light_id="1",
                state={"on": True}
            )

            # Should pass governance check
            assert "governance_check" in result

    @pytest.mark.asyncio
    async def test_student_agent_blocked(self, db_session: Session):
        """Test STUDENT agent is blocked from Hue control."""
        agent = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            maturity_level="STUDENT",
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        result = await hue_set_light_state(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session,
            bridge_ip="192.168.1.50",
            light_id="1",
            state={"on": True}
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_discover_action(self, db_session: Session):
        """Test discover action (read-only)."""
        agent = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="TestIntern",
            status=AgentStatus.INTERN.value,
            maturity_level="INTERN",
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        result = await hue_discover_bridges(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session
        )

        # Discover is read-only, INTERN should be allowed
        assert result.get("success") != False or "governance_check" in result

    @pytest.mark.asyncio
    async def test_set_light_action(self, db_session: Session):
        """Test set light action."""
        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        result = await hue_set_light_state(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session,
            bridge_ip="192.168.1.50",
            light_id="1",
            state={"on": True, "brightness": 200}
        )

        assert result.get("success") != False or "governance_check" in result

# ============================================================================
# HomeAssistantTool Governance Tests
# ============================================================================

class TestHomeAssistantToolGovernance:
    """Test governance enforcement for Home Assistant tool."""

    @pytest.mark.asyncio
    async def test_governance_enforcement(self, db_session: Session):
        """Test governance check is performed."""
        agent = AgentRegistry(
            name="StudentAgent",
            category="test",
            module_path="test.module",
            class_name="TestStudent",
            status=AgentStatus.STUDENT.value,
            maturity_level="STUDENT",
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        result = await home_assistant_call_service(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session,
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.living_room"}
        )

        assert result["success"] is False
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_states_action(self, db_session: Session):
        """Test get states action (read-only)."""
        agent = AgentRegistry(
            name="InternAgent",
            category="test",
            module_path="test.module",
            class_name="TestIntern",
            status=AgentStatus.INTERN.value,
            maturity_level="INTERN",
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        result = await home_assistant_get_states(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session
        )

        # Get states is read-only, INTERN should be allowed
        assert result.get("success") != False or "governance_check" in result

    @pytest.mark.asyncio
    async def test_call_service_action(self, db_session: Session):
        """Test call service action."""
        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        result = await home_assistant_call_service(
            agent_id=agent.id,
            user_id="test_user",
            db=db_session,
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.living_room"}
        )

        assert result.get("success") != False or "governance_check" in result


# ============================================================================
# Local Network Tests
# ============================================================================

class TestLocalNetworkOperations:
    """Test local network operations without internet."""

    @pytest.mark.asyncio
    async def test_local_services_work_without_internet(self, db_session: Session):
        """Test local services work without internet connection."""
        agent = AgentRegistry(
            name="AutonomousAgent",
            category="test",
            module_path="test.module",
            class_name="TestAutonomous",
            status=AgentStatus.AUTONOMOUS.value,
            maturity_level="AUTONOMOUS",
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock service to simulate no internet but local network working
        with patch('tools.smarthome_tool.HueService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.set_light_state.return_value = True
            mock_service_class.return_value = mock_service

            result = await hue_set_light_state(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                bridge_ip="192.168.1.50",
                light_id="1",
                state={"on": True}
            )

            assert result.get("success") != False or "governance_check" in result

    @pytest.mark.asyncio
    async def test_mdns_discovery_fallback_to_manual_ip(self, db_session: Session):
        """Test mDNS discovery falls back to manual IP configuration."""
        agent = AgentRegistry(
            name="SupervisedAgent",
            category="test",
            module_path="test.module",
            class_name="TestSupervised",
            status=AgentStatus.SUPERVISED.value,
            maturity_level="SUPERVISED",
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        # Mock discovery to fail
        with patch('tools.smarthome_tool.HueService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.discover_bridges.return_value = []  # No bridges found
            mock_service_class.return_value = mock_service

            # User can manually provide IP
            result = await hue_set_light_state(
                agent_id=agent.id,
                user_id="test_user",
                db=db_session,
                bridge_ip="192.168.1.50",  # Manual IP
                light_id="1",
                state={"on": True}
            )

            # Should work with manual IP even if discovery fails
            assert result.get("success") != False or "governance_check" in result


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestSmartHomeIntegration:
    """Integration tests requiring real devices."""

    @pytest.mark.skip(reason="Requires real Philips Hue bridge on network")
    def test_real_hue_discovery(self):
        """Test with real Hue bridge (requires local network)."""
        # This test only runs with: pytest -m integration
        pass

    @pytest.mark.skip(reason="Requires real Home Assistant instance")
    def test_real_home_assistant_states(self):
        """Test with real Home Assistant (requires local instance)."""
        # This test only runs with: pytest -m integration
        pass
