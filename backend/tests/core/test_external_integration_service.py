"""
Tests for ExternalIntegrationService - external API integration management.

Target: 75%+ line coverage, 60%+ branch coverage
File: backend/core/external_integration_service.py (60 lines)
"""

import pytest
import sys
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime

# Mock the entire node_bridge_service module before importing
mock_bridge_service = MagicMock()
mock_bridge_instance = MagicMock()
mock_bridge_service.node_bridge = mock_bridge_instance
sys.modules['integrations.bridge.node_bridge_service'] = mock_bridge_service

from core.external_integration_service import ExternalIntegrationService, external_integration_service


class TestExternalIntegrationService:
    """Test suite for ExternalIntegrationService"""

    @pytest.fixture
    def mock_node_bridge(self):
        """Mock NodeBridgeService singleton"""
        # Create a fresh mock for each test
        bridge = MagicMock()
        bridge.get_catalog = AsyncMock(return_value=[
            {
                "name": "@activepieces/piece-slack",
                "displayName": "Slack",
                "actions": ["send_message", "upload_file"],
                "triggers": ["new_message"]
            },
            {
                "name": "@activepieces/piece-gmail",
                "displayName": "Gmail",
                "actions": ["send_email", "read_email"],
                "triggers": ["new_email"]
            }
        ])
        bridge.get_piece_details = AsyncMock(return_value={
            "name": "@activepieces/piece-slack",
            "displayName": "Slack",
            "version": "1.0.0",
            "actions": [
                {"name": "send_message", "displayName": "Send Message"}
            ]
        })
        # NodeBridgeService.execute_action returns result.get("output", {})
        # So we return just the output part
        bridge.execute_action = AsyncMock(return_value={
            "message_id": "msg123",
            "status": "sent"
        })
        return bridge

    @pytest.fixture
    def integration_service(self, mock_node_bridge):
        """Create ExternalIntegrationService with mocked dependencies"""
        # Patch the imported node_bridge singleton
        with patch('core.external_integration_service.node_bridge', mock_node_bridge):
            # Create a new instance with the patched dependency
            service = ExternalIntegrationService()
            yield service

    # Test 1: Singleton instance
    def test_singleton_instance(self):
        """Test that external_integration_service is a singleton"""
        assert isinstance(external_integration_service, ExternalIntegrationService)

    # Test 2: Initialization
    def test_initialization(self):
        """Test service initializes correctly"""
        with patch('core.external_integration_service.node_bridge'):
            service = ExternalIntegrationService()
            assert service is not None

    # Test 3: Get all integrations success
    @pytest.mark.asyncio
    async def test_get_all_integrations_success(self, integration_service, mock_node_bridge):
        """Test successfully retrieving all integrations"""
        result = await integration_service.get_all_integrations()

        assert len(result) == 2
        assert result[0]["name"] == "@activepieces/piece-slack"
        assert result[1]["name"] == "@activepieces/piece-gmail"
        mock_node_bridge.get_catalog.assert_called_once()

    # Test 4: Get all integrations empty list
    @pytest.mark.asyncio
    async def test_get_all_integrations_empty(self, integration_service, mock_node_bridge):
        """Test getting integrations when none exist"""
        mock_node_bridge.get_catalog.return_value = []

        result = await integration_service.get_all_integrations()

        assert result == []
        mock_node_bridge.get_catalog.assert_called_once()

    # Test 5: Get all integrations error handling
    @pytest.mark.asyncio
    async def test_get_all_integrations_error(self, integration_service, mock_node_bridge):
        """Test error handling when catalog fetch fails"""
        mock_node_bridge.get_catalog.side_effect = Exception("Connection failed")

        result = await integration_service.get_all_integrations()

        # Should return empty list on error
        assert result == []

    # Test 6: Get piece details success
    @pytest.mark.asyncio
    async def test_get_piece_details_success(self, integration_service, mock_node_bridge):
        """Test successfully retrieving piece details"""
        result = await integration_service.get_piece_details("@activepieces/piece-slack")

        assert result is not None
        assert result["name"] == "@activepieces/piece-slack"
        assert result["displayName"] == "Slack"
        mock_node_bridge.get_piece_details.assert_called_once_with("@activepieces/piece-slack")

    # Test 7: Get piece details not found (404)
    @pytest.mark.asyncio
    async def test_get_piece_details_not_found(self, integration_service, mock_node_bridge):
        """Test getting details for non-existent piece"""
        mock_node_bridge.get_piece_details.return_value = None

        result = await integration_service.get_piece_details("@activepieces/piece-nonexistent")

        assert result is None

    # Test 8: Get piece details error handling
    @pytest.mark.asyncio
    async def test_get_piece_details_error(self, integration_service, mock_node_bridge):
        """Test error handling when piece details fetch fails"""
        mock_node_bridge.get_piece_details.side_effect = Exception("Network error")

        result = await integration_service.get_piece_details("some-piece")

        assert result is None

    # Test 9: Execute integration action success
    @pytest.mark.asyncio
    async def test_execute_integration_action_success(self, integration_service, mock_node_bridge):
        """Test successfully executing an integration action"""
        result = await integration_service.execute_integration_action(
            integration_id="@activepieces/piece-slack",
            action_id="send_message",
            params={"channel": "#general", "text": "Hello"},
            credentials={"token": "xoxp-test-token"}
        )

        assert result is not None
        assert result["message_id"] == "msg123"
        assert result["status"] == "sent"

        # Verify node_bridge was called with correct parameters
        mock_node_bridge.execute_action.assert_called_once()
        call_kwargs = mock_node_bridge.execute_action.call_args[1]
        assert call_kwargs["piece_name"] == "@activepieces/piece-slack"
        assert call_kwargs["action_name"] == "send_message"
        assert call_kwargs["props"]["channel"] == "#general"
        assert call_kwargs["auth"]["token"] == "xoxp-test-token"

    # Test 10: Execute action without credentials
    @pytest.mark.asyncio
    async def test_execute_integration_action_no_credentials(self, integration_service, mock_node_bridge):
        """Test executing action without credentials"""
        result = await integration_service.execute_integration_action(
            integration_id="@activepieces/piece-gmail",
            action_id="send_email",
            params={"to": "test@example.com", "subject": "Test", "body": "Test body"}
        )

        assert result is not None

        # Verify auth was None
        call_kwargs = mock_node_bridge.execute_action.call_args[1]
        assert call_kwargs["auth"] is None

    # Test 11: Execute action error from node bridge
    @pytest.mark.asyncio
    async def test_execute_integration_action_node_error(self, integration_service, mock_node_bridge):
        """Test error handling when node bridge execution fails"""
        mock_node_bridge.execute_action.side_effect = Exception("Execution failed")

        with pytest.raises(Exception, match="Execution failed"):
            await integration_service.execute_integration_action(
                integration_id="test-piece",
                action_id="test_action",
                params={}
            )

    # Test 12: Execute action with empty params
    @pytest.mark.asyncio
    async def test_execute_integration_action_empty_params(self, integration_service, mock_node_bridge):
        """Test executing action with empty parameters"""
        mock_node_bridge.execute_action.return_value = {}

        result = await integration_service.execute_integration_action(
            integration_id="test-piece",
            action_id="test_action",
            params={}
        )

        call_kwargs = mock_node_bridge.execute_action.call_args[1]
        assert call_kwargs["props"] == {}
        assert result == {}

    # Test 13: Execute action with complex params
    @pytest.mark.asyncio
    async def test_execute_integration_action_complex_params(self, integration_service, mock_node_bridge):
        """Test executing action with complex nested parameters"""
        complex_params = {
            "message": {
                "text": "Hello",
                "attachments": [
                    {"type": "image", "url": "http://example.com/img.png"},
                    {"type": "file", "url": "http://example.com/doc.pdf"}
                ]
            },
            "options": {
                "thread_ts": "1234567890.123456",
                "reply_broadcast": True
            }
        }

        result = await integration_service.execute_integration_action(
            integration_id="test-piece",
            action_id="complex_action",
            params=complex_params
        )

        call_kwargs = mock_node_bridge.execute_action.call_args[1]
        assert call_kwargs["props"]["message"]["attachments"][0]["type"] == "image"

    # Test 14: Get piece details for various pieces
    @pytest.mark.asyncio
    async def test_get_piece_details_various_pieces(self, integration_service, mock_node_bridge):
        """Test getting details for multiple different pieces"""
        pieces = [
            "@activepieces/piece-slack",
            "@activepieces/piece-gmail",
            "@activepieces/piece-sheets",
            "@activepieces/piece-drive"
        ]

        for piece_name in pieces:
            mock_node_bridge.get_piece_details.return_value = {"name": piece_name}
            result = await integration_service.get_piece_details(piece_name)
            assert result["name"] == piece_name

        assert mock_node_bridge.get_piece_details.call_count == 4

    # Test 15: Execute action returns partial success
    @pytest.mark.asyncio
    async def test_execute_integration_action_partial_success(self, integration_service, mock_node_bridge):
        """Test handling partial success response from node bridge"""
        mock_node_bridge.execute_action.return_value = {
            "message": "Sent but not confirmed",
            "confirmed": False
        }

        result = await integration_service.execute_integration_action(
            integration_id="test-piece",
            action_id="test_action",
            params={}
        )

        assert result["message"] == "Sent but not confirmed"
        assert result["confirmed"] is False

    # Test 16: Execute action with unicode characters
    @pytest.mark.asyncio
    async def test_execute_integration_action_unicode(self, integration_service, mock_node_bridge):
        """Test executing action with unicode characters in parameters"""
        unicode_params = {
            "message": "Hello 世界 🌍",
            "emoji": "😀🎉"
        }

        result = await integration_service.execute_integration_action(
            integration_id="test-piece",
            action_id="unicode_action",
            params=unicode_params
        )

        call_kwargs = mock_node_bridge.execute_action.call_args[1]
        assert "世界" in call_kwargs["props"]["message"]

    # Test 17: Get integrations with large catalog
    @pytest.mark.asyncio
    async def test_get_all_integrations_large_catalog(self, integration_service, mock_node_bridge):
        """Test getting integrations with a large catalog"""
        large_catalog = [
            {"name": f"piece-{i}", "displayName": f"Piece {i}"}
            for i in range(100)
        ]
        mock_node_bridge.get_catalog.return_value = large_catalog

        result = await integration_service.get_all_integrations()

        assert len(result) == 100
        assert result[0]["name"] == "piece-0"
        assert result[99]["name"] == "piece-99"

    # Test 18: Execute action timeout handling
    @pytest.mark.asyncio
    async def test_execute_integration_action_timeout(self, integration_service, mock_node_bridge):
        """Test handling of timeout during action execution"""
        import asyncio
        mock_node_bridge.execute_action.side_effect = asyncio.TimeoutError("Request timed out")

        with pytest.raises(asyncio.TimeoutError):
            await integration_service.execute_integration_action(
                integration_id="test-piece",
                action_id="test_action",
                params={}
            )

    # Test 19: Get piece details with special characters in name
    @pytest.mark.asyncio
    async def test_get_piece_details_special_characters(self, integration_service, mock_node_bridge):
        """Test getting piece details with special characters in piece name"""
        special_names = [
            "@activepieces/piece-slack-pro",
            "@activepieces/piece-oauth2",
            "@custom/piece-with-dashes"
        ]

        for piece_name in special_names:
            mock_node_bridge.get_piece_details.return_value = {"name": piece_name}
            result = await integration_service.get_piece_details(piece_name)
            assert result["name"] == piece_name

    # Test 20: Multiple sequential execute actions
    @pytest.mark.asyncio
    async def test_execute_integration_action_sequential(self, integration_service, mock_node_bridge):
        """Test executing multiple actions sequentially"""
        actions = [
            ("send_message", {"channel": "#general"}),
            ("upload_file", {"file": "content"}),
            ("delete_message", {"message_id": "msg123"})
        ]

        for action_id, params in actions:
            await integration_service.execute_integration_action(
                integration_id="test-piece",
                action_id=action_id,
                params=params
            )

        assert mock_node_bridge.execute_action.call_count == 3


class TestExternalIntegrationServiceEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.fixture
    def integration_service(self):
        """Create service with mocked node_bridge"""
        mock_bridge = MagicMock()
        mock_bridge.get_catalog = AsyncMock(return_value=[])
        mock_bridge.get_piece_details = AsyncMock(return_value=None)
        # Return just the output part (what node_bridge.execute_action actually returns)
        mock_bridge.execute_action = AsyncMock(return_value={"message": "Success"})

        with patch('core.external_integration_service.node_bridge', mock_bridge):
            return ExternalIntegrationService()

    # Test 21: Get integrations with None return from node bridge
    @pytest.mark.asyncio
    async def test_get_all_integrations_none_return(self):
        """Test handling when node bridge returns None"""
        mock_bridge = MagicMock()
        mock_bridge.get_catalog = AsyncMock(return_value=None)

        with patch('core.external_integration_service.node_bridge', mock_bridge):
            service = ExternalIntegrationService()
            result = await service.get_all_integrations()

            # Should handle None gracefully
            assert result is None or result == []

    # Test 22: Execute action with very long params
    @pytest.mark.asyncio
    async def test_execute_integration_action_very_long_params(self):
        """Test executing action with very long parameter string"""
        mock_bridge = MagicMock()
        long_text = "a" * 10000  # 10KB of text
        mock_bridge.execute_action = AsyncMock(return_value={"success": True})

        with patch('core.external_integration_service.node_bridge', mock_bridge):
            service = ExternalIntegrationService()
            params = {"content": long_text}

            result = await service.execute_integration_action(
                integration_id="test-piece",
                action_id="test_action",
                params=params
            )

            assert result is not None

    # Test 23: Execute action with None credentials explicitly
    @pytest.mark.asyncio
    async def test_execute_integration_action_none_credentials(self):
        """Test executing action with explicitly None credentials"""
        mock_bridge = MagicMock()
        mock_bridge.execute_action = AsyncMock(return_value={"success": True})

        with patch('core.external_integration_service.node_bridge', mock_bridge):
            service = ExternalIntegrationService()
            result = await service.execute_integration_action(
                integration_id="test-piece",
                action_id="test_action",
                params={},
                credentials=None
            )

            assert result is not None

    # Test 24: Get piece details with empty string
    @pytest.mark.asyncio
    async def test_get_piece_details_empty_string(self, integration_service):
        """Test getting piece details with empty piece name"""
        result = await integration_service.get_piece_details("")

        # Should handle gracefully
        assert result is None

    # Test 25: Execute action with special JSON characters
    @pytest.mark.asyncio
    async def test_execute_integration_action_special_json_chars(self):
        """Test executing action with special JSON characters"""
        mock_bridge = MagicMock()
        mock_bridge.execute_action = AsyncMock(return_value={"success": True, "processed": True})

        with patch('core.external_integration_service.node_bridge', mock_bridge):
            service = ExternalIntegrationService()
            params = {
                "text": "Line 1\nLine 2\tTabbed",
                "nested": {"key": "value with \"quotes\" and \\backslashes\\"}
            }

            result = await service.execute_integration_action(
                integration_id="test-piece",
                action_id="test_action",
                params=params
            )

            assert result is not None
            assert result.get("success") is True
