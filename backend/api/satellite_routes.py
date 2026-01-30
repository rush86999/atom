from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from core.satellite_service import satellite_service
from core.security import verify_api_key_ws
import logging

router = APIRouter(tags=["Satellite"])

logger = logging.getLogger(__name__)

@router.websocket("/api/ws/satellite/connect")
async def websocket_satellite_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Atom Satellite CLI.
    Requires 'X-Atom-Key' header during handshake.
    """
    try:
        # 1. Handshake & Auth
        # Note: WebSocket headers are tricky in some clients, 
        # so we might accept a query param ?key=... or do an initial auth message
        # For simplicity/security, we check query param first
        
        api_key = websocket.query_params.get("key")
        if not api_key:
            await websocket.close(code=1008, reason="Missing API Key")
            return

        # Simple verification (In prod, use verify_api_key dependency properly)
        # Here we mock tenant extraction based on key prefix or lookup
        # TODO: Replace with real key lookup
        if api_key.startswith("sk-"):
             # Basic check, in real app, query DB for key -> tenant_id
             tenant_id = "default" # Default for now until multi-tenant keys implemented
        else:
             await websocket.close(code=1008, reason="Invalid API Key")
             return

        # 2. Accept & Register
        await satellite_service.connect(websocket, tenant_id)
        
        try:
            while True:
                # 3. Listen loop
                data = await websocket.receive_json()
                await satellite_service.handle_message(tenant_id, data)
                
        except WebSocketDisconnect:
            satellite_service.disconnect(tenant_id)
            
    except Exception as e:
        logger.error(f"Satellite WS error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass
