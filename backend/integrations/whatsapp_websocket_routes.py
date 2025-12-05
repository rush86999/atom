"""
WhatsApp WebSocket Routes Extension
Add WebSocket endpoints to existing WhatsApp FastAPI routes
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

# Import existing WhatsApp components
try:
    from .whatsapp_fastapi_routes import router as whatsapp_router
    from .whatsapp_websocket_handler import websocket_manager, notify_message_status_change
except ImportError as e:
    logger.warning(f"WhatsApp WebSocket dependencies not available: {e}")
    websocket_manager = None

# Create WebSocket router
websocket_router = APIRouter(prefix="/ws", tags=["WhatsApp WebSocket"])

@websocket_router.websocket("/whatsapp")
async def whatsapp_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time WhatsApp updates"""
    if not websocket_manager:
        await websocket.close(code=1003, reason="WebSocket manager not available")
        return

    connection_id = f"ws_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(websocket_manager.active_connections)}"
    
    try:
        await websocket_manager.connect(websocket, connection_id)
        
        # Handle WebSocket messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get('type') == 'ping':
                    await websocket_manager.send_to_connection(connection_id, {
                        'type': 'pong',
                        'timestamp': datetime.now().isoformat()
                    })
                elif message.get('type') == 'subscribe':
                    # Handle subscription to events
                    await websocket_manager.send_to_connection(connection_id, {
                        'type': 'subscription_confirmed',
                        'subscriptions': message.get('subscriptions', []),
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    logger.warning(f"Unknown WebSocket message type: {message.get('type')}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket message handling: {str(e)}")
                await websocket_manager.send_to_connection(connection_id, {
                    'type': 'error',
                    'message': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        if websocket_manager:
            websocket_manager.disconnect(connection_id)

@websocket_router.get("/whatsapp/status")
async def get_websocket_status():
    """Get WebSocket connection status"""
    if not websocket_manager:
        return {
            'status': 'unavailable',
            'message': 'WebSocket manager not available',
            'active_connections': 0
        }
    
    return {
        'status': 'available',
        'active_connections': len(websocket_manager.active_connections),
        'connection_metadata': websocket_manager.connection_metadata,
        'timestamp': datetime.now().isoformat()
    }

@websocket_router.post("/whatsapp/notify")
async def trigger_websocket_notification(notification: Dict[str, Any]):
    """Manual trigger for WebSocket notifications (for testing)"""
    if not websocket_manager:
        return {
            'success': False,
            'error': 'WebSocket manager not available'
        }
    
    try:
        notification_type = notification.get('type', 'unknown')
        
        if notification_type == 'message_status':
            await websocket_manager.update_message_status(
                notification.get('message_id', ''),
                notification.get('status', 'unknown'),
                notification.get('metadata', {})
            )
        elif notification_type == 'new_message':
            await websocket_manager.new_message_received(notification)
        elif notification_type == 'conversation_status':
            await websocket_manager.update_conversation_status(
                notification.get('conversation_id', ''),
                notification.get('status', 'unknown')
            )
        
        return {
            'success': True,
            'message': f'WebSocket notification sent: {notification_type}',
            'active_connections': len(websocket_manager.active_connections),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending WebSocket notification: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# Extend existing WhatsApp router with WebSocket endpoints
def extend_whatsapp_routes_with_websocket():
    """Add WebSocket endpoints to existing WhatsApp router"""
    if whatsapp_router:
        # Add WebSocket status endpoint to main API
        @whatsapp_router.get("/websocket/status", tags=["WhatsApp WebSocket"])
        async def websocket_status():
            """Get WebSocket status (accessible via main API)"""
            if not websocket_manager:
                return {
                    'status': 'unavailable',
                    'message': 'WebSocket manager not available',
                    'active_connections': 0,
                    'service': 'WhatsApp WebSocket'
                }
            
            return {
                'status': 'available',
                'service': 'WhatsApp WebSocket',
                'active_connections': len(websocket_manager.active_connections),
                'connection_metadata': websocket_manager.connection_metadata,
                'websocket_url': 'ws://localhost:5058/ws/whatsapp',
                'timestamp': datetime.now().isoformat()
            }
        
        # Add WebSocket notification endpoint to main API
        @whatsapp_router.post("/websocket/notify", tags=["WhatsApp WebSocket"])
        async def websocket_notification_endpoint(notification: Dict[str, Any]):
            """Send WebSocket notification via main API"""
            if not websocket_manager:
                return {
                    'success': False,
                    'error': 'WebSocket manager not available',
                    'service': 'WhatsApp WebSocket'
                }
            
            try:
                notification_type = notification.get('type', 'unknown')
                
                if notification_type == 'message_status':
                    await websocket_manager.update_message_status(
                        notification.get('message_id', ''),
                        notification.get('status', 'unknown'),
                        notification.get('metadata', {})
                    )
                elif notification_type == 'new_message':
                    await websocket_manager.new_message_received(notification)
                elif notification_type == 'conversation_status':
                    await websocket_manager.update_conversation_status(
                        notification.get('conversation_id', ''),
                        notification.get('status', 'unknown')
                    )
                
                return {
                    'success': True,
                    'service': 'WhatsApp WebSocket',
                    'message': f'Notification sent: {notification_type}',
                    'active_connections': len(websocket_manager.active_connections),
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error sending WebSocket notification: {str(e)}")
                return {
                    'success': False,
                    'service': 'WhatsApp WebSocket',
                    'error': str(e)
                }
        
        logger.info("WebSocket endpoints added to WhatsApp router")
        return True
    
    return False

# Initialize WebSocket extensions
def initialize_websocket_extensions():
    """Initialize WebSocket extensions for WhatsApp integration"""
    try:
        # Extend main WhatsApp router with WebSocket endpoints
        extended = extend_whatsapp_routes_with_websocket()
        
        if extended:
            logger.info("WhatsApp WebSocket extensions initialized successfully")
        else:
            logger.warning("Failed to extend WhatsApp router with WebSocket endpoints")
        
        return extended
        
    except Exception as e:
        logger.error(f"Error initializing WebSocket extensions: {str(e)}")
        return False

# Export for registration
__all__ = [
    'websocket_router',
    'extend_whatsapp_routes_with_websocket',
    'initialize_websocket_extensions'
]