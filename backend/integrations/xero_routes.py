import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .xero_service import XeroService

logger = logging.getLogger(__name__)

# Auth Type: OAuth2
router = APIRouter(prefix="/api/xero", tags=["xero"])

@router.get("/auth/url")
async def get_auth_url():
    """Get Xero OAuth URL"""
    return {
        "url": "https://login.xero.com/identity/connect/authorize?response_type=code&client_id=INSERT_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fxero%2Fcallback&scope=openid profile email accounting.transactions",
        "timestamp": datetime.now().isoformat()
    }

# Initialize service
xero_service = XeroService()

class XeroAuthRequest(BaseModel):
    code: str
    redirect_uri: str

@router.post("/auth/callback")
async def xero_auth_callback(auth_request: XeroAuthRequest):
    """Exchange authorization code for access token"""
    try:
        token_data = await xero_service.exchange_token(auth_request.code, auth_request.redirect_uri)
        # Automatically fetch tenants to help the frontend
        tenants = await xero_service.get_tenants(token_data["access_token"])
        
        return {
            "ok": True,
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "tenants": tenants,
            "service": "xero"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/tenants")
async def get_tenants(access_token: str = Query(..., description="Access Token")):
    """Get connected Xero tenants"""
    tenants = await xero_service.get_tenants(access_token)
    return {"ok": True, "data": tenants}

@router.get("/invoices")
async def list_invoices(
    access_token: str = Query(..., description="Access Token"),
    tenant_id: str = Query(..., description="Xero Tenant ID"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Xero invoices"""
    invoices = await xero_service.get_invoices(access_token, tenant_id, limit)
    return {"ok": True, "data": invoices, "count": len(invoices)}

@router.get("/contacts")
async def list_contacts(
    access_token: str = Query(..., description="Access Token"),
    tenant_id: str = Query(..., description="Xero Tenant ID"),
    limit: int = Query(20, ge=1, le=100)
):
    """List Xero contacts"""
    contacts = await xero_service.get_contacts(access_token, tenant_id, limit)
    return {"ok": True, "data": contacts, "count": len(contacts)}

@router.get("/status")
async def xero_status():
    """Get Xero integration status"""
    return {
        "ok": True,
        "service": "xero",
        "status": "active",
        "version": "1.0.0",
        "mode": "real"
    }

@router.get("/")
async def xero_root():
    """Xero integration root endpoint"""
    return {
        "service": "xero",
        "status": "active",
        "endpoints": [
            "/auth/callback",
            "/tenants",
            "/invoices",
            "/contacts",
            "/status"
        ]
    }
