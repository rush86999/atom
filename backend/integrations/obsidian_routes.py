"""
Obsidian Integration Routes
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional, Dict, Any
from .obsidian_service import ObsidianService
from core.auth import get_current_user
from core.models import User
from core.ssrf_guard import validate_url, SSRFError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/obsidian", tags=["integrations"])

@router.get("/status")
async def get_obsidian_status(
    api_token: str = Header(...),
    plugin_url: str = Header("http://localhost:27123")
):
    """Check Obsidian connection status"""
    try:
        validate_url(plugin_url)
    except SSRFError as e:
        raise HTTPException(status_code=400, detail="Invalid plugin configuration")
    try:
        service = ObsidianService(api_token=api_token, plugin_url=plugin_url)
        return service.test_connection()
    except Exception:
        # Status probe must degrade gracefully when the plugin host is
        # unreachable (round 80c journey fix — was an unhandled 500).
        logger.warning("Obsidian status probe failed (plugin unreachable)")
        return {"ok": False, "status": "unreachable", "service": "obsidian"}

@router.get("/notes")
async def list_obsidian_notes(
    api_token: str = Header(...),
    plugin_url: str = Header("http://localhost:27123"),
    current_user: User = Depends(get_current_user)
):
    """List Obsidian notes"""
    service = ObsidianService(api_token=api_token, plugin_url=plugin_url)
    return {"notes": service.list_notes()}

@router.post("/notes")
async def create_obsidian_note(
    path: str,
    content: str,
    api_token: str = Header(...),
    plugin_url: str = Header("http://localhost:27123"),
    current_user: User = Depends(get_current_user)
):
    """Create a new Obsidian note"""
    service = ObsidianService(api_token=api_token, plugin_url=plugin_url)
    success = service.create_note(path, content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create note")
    return {"status": "success"}
