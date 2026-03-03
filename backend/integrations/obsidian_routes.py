"""
Obsidian Integration Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional, Dict, Any
from .obsidian_service import ObsidianService

router = APIRouter(prefix="/obsidian", tags=["integrations"])

@router.get("/status")
async def get_obsidian_status(
    api_token: str = Header(...),
    plugin_url: str = Header("http://localhost:27123")
):
    """Check Obsidian connection status"""
    service = ObsidianService(api_token=api_token, plugin_url=plugin_url)
    return service.test_connection()

@router.get("/notes")
async def list_obsidian_notes(
    api_token: str = Header(...),
    plugin_url: str = Header("http://localhost:27123")
):
    """List Obsidian notes"""
    service = ObsidianService(api_token=api_token, plugin_url=plugin_url)
    return {"notes": service.list_notes()}

@router.post("/notes")
async def create_obsidian_note(
    path: str,
    content: str,
    api_token: str = Header(...),
    plugin_url: str = Header("http://localhost:27123")
):
    """Create a new Obsidian note"""
    service = ObsidianService(api_token=api_token, plugin_url=plugin_url)
    success = service.create_note(path, content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create note")
    return {"status": "success"}
