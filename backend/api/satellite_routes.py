import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.auth import generate_satellite_key, get_current_user
from core.database import SessionLocal, get_db
from core.models import Workspace
from core.satellite_service import satellite_service
from core.security import verify_api_key_ws

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
        api_key = websocket.query_params.get("key")
        if not api_key:
            await websocket.close(code=1008, reason="Missing API Key")
            return

        # Use context manager for WebSocket endpoints (can't use Depends)
        with SessionLocal() as db:
            workspace = db.query(Workspace).filter(Workspace.satellite_api_key == api_key).first()
            if not workspace:
                # Fallback for sk- prefix if no keys generated yet (migration path)
                if api_key.startswith("sk-"):
                    tenant_id = "default"
                else:
                    await websocket.close(code=1008, reason="Invalid API Key")
                    return
            else:
                tenant_id = workspace.id

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
        except Exception as e:
            pass

@router.get("/api/satellite/key")
async def get_satellite_key(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve the current Satellite API key for the workspace."""
    # Single-tenant: just get the first workspace
    workspace = db.query(Workspace).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Auto-generate if missing
    if not workspace.satellite_api_key:
        workspace.satellite_api_key = generate_satellite_key()
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        
    return {"api_key": workspace.satellite_api_key}

@router.post("/api/satellite/rotate")
async def rotate_satellite_key(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Regenerate the Satellite API key."""
    workspace = db.query(Workspace).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workspace.satellite_api_key = generate_satellite_key()
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    return {"success": True, "api_key": workspace.satellite_api_key}
