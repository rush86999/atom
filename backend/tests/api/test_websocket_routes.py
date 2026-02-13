
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.websocket_routes import websocket_endpoint


@pytest.fixture
def mock_websocket():
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_notification_manager():
    manager = MagicMock()
    manager.connect = MagicMock()
    manager.disconnect = MagicMock()
    return manager


@pytest.mark.asyncio
async def test_websocket_connect(mock_websocket, mock_notification_manager):
    mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")
    with patch('api.websocket_routes.notification_manager', mock_notification_manager):
        try:
            await websocket_endpoint(mock_websocket, "test_workspace")
        except:
            pass
    mock_websocket.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_ping_pong(mock_websocket, mock_notification_manager):
    mock_websocket.receive_text.side_effect = ["ping", Exception("WebSocketDisconnect")]
    with patch('api.websocket_routes.notification_manager', mock_notification_manager):
        try:
            await websocket_endpoint(mock_websocket, "test_workspace")
        except:
            pass
    mock_websocket.send_text.assert_called_with("pong")


@pytest.mark.asyncio
async def test_websocket_disconnect(mock_websocket, mock_notification_manager):
    mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")
    with patch('api.websocket_routes.notification_manager', mock_notification_manager):
        try:
            await websocket_endpoint(mock_websocket, "test_workspace")
        except:
            pass
    mock_notification_manager.disconnect.assert_called()


@pytest.mark.asyncio
async def test_websocket_error_handling(mock_websocket, mock_notification_manager):
    mock_websocket.receive_text.side_effect = Exception("Connection error")
    with patch('api.websocket_routes.notification_manager', mock_notification_manager):
        try:
            await websocket_endpoint(mock_websocket, "test_workspace")
        except:
            pass
    mock_notification_manager.disconnect.assert_called()


@pytest.mark.asyncio
async def test_websocket_client_message(mock_websocket, mock_notification_manager):
    mock_websocket.receive_text.side_effect = ["client message", Exception("Done")]
    with patch('api.websocket_routes.notification_manager', mock_notification_manager):
        try:
            await websocket_endpoint(mock_websocket, "test_workspace")
        except:
            pass
    # Should not send pong for non-ping message
    mock_websocket.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_workspace_routing(mock_websocket, mock_notification_manager):
    workspace_id = "custom_workspace"
    mock_websocket.receive_text.side_effect = Exception("Done")
    with patch('api.websocket_routes.notification_manager', mock_notification_manager):
        try:
            await websocket_endpoint(mock_websocket, workspace_id)
        except:
            pass
    mock_notification_manager.connect.assert_called_with(mock_websocket, workspace_id)
