"""
WhatsApp Routes Extension
Add fixed WebSocket routes to main API app
"""

from fastapi import APIRouter
from integrations.whatsapp_websocket_router_fix import websocket_router

def register_websocket_routes(app):
    """Register fixed WebSocket routes with main API app"""
    try:
        # Include WebSocket router
        app.include_router(websocket_router)
        
        # Add WebSocket status endpoint to main API
        @app.get("/api/whatsapp/websocket/status", tags=["WhatsApp WebSocket"])
        async def get_main_websocket_status():
            """Get WebSocket status via main API"""
            return {
                "status": "available",
                "service": "WhatsApp WebSocket",
                "websocket_url": "ws://localhost:5058/ws/whatsapp",
                "timestamp": datetime.now().isoformat(),
                "features": [
                    "Real-time message status updates",
                    "Connection management",
                    "Message subscriptions",
                    "Error handling and recovery"
                ]
            }
        
        print("✅ WebSocket routes registered successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error registering WebSocket routes: {str(e)}")
        return False

__all__ = ['register_websocket_routes']
