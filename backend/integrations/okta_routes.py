from fastapi import APIRouter, HTTPException, Query

from integrations.okta_service import okta_service

router = APIRouter(prefix="/api/okta", tags=["Okta"])

@router.get("/users")
async def list_okta_users(limit: int = Query(50, ge=1, le=200)):
    """List Okta users"""
    return await okta_service.list_users(limit)

@router.get("/health")
async def okta_health():
    """Get Okta integration health"""
    return await okta_service.check_health()
