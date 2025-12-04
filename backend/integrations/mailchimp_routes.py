
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel

from .mailchimp_service import MailchimpService

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/mailchimp", tags=["mailchimp"])

# Initialize service
mailchimp_service = MailchimpService()

# Pydantic models
class MailchimpAuthRequest(BaseModel):
    code: str
    redirect_uri: str

# API Routes

@router.post("/auth/callback")
async def mailchimp_auth_callback(auth_request: MailchimpAuthRequest):
    """Exchange authorization code for access token"""
    try:
        token_data = await mailchimp_service.exchange_token(auth_request.code, auth_request.redirect_uri)
        # Get metadata to find the server prefix (dc)
        metadata = await mailchimp_service.get_metadata(token_data["access_token"])
        
        return {
            "ok": True,
            "access_token": token_data["access_token"],
            "server_prefix": metadata["dc"],
            "service": "mailchimp"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/audiences")
async def get_audiences(
    access_token: str = Query(..., description="Access Token"),
    server_prefix: str = Query(..., description="Server Prefix (e.g. us1)"),
    limit: int = Query(10, ge=1, le=100),
):
    """Get Mailchimp audiences"""
    audiences = await mailchimp_service.get_audiences(access_token, server_prefix, limit)
    return {"ok": True, "data": audiences, "count": len(audiences)}

@router.get("/campaigns")
async def get_campaigns(
    access_token: str = Query(..., description="Access Token"),
    server_prefix: str = Query(..., description="Server Prefix (e.g. us1)"),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get Mailchimp campaigns"""
    campaigns = await mailchimp_service.get_campaigns(access_token, server_prefix, limit, status)
    return {"ok": True, "data": campaigns, "count": len(campaigns)}

@router.get("/account")
async def get_account_info(
    access_token: str = Query(..., description="Access Token"),
    server_prefix: str = Query(..., description="Server Prefix (e.g. us1)"),
):
    """Get Mailchimp account info"""
    info = await mailchimp_service.get_account_info(access_token, server_prefix)
    return {"ok": True, "data": info}

@router.get("/health")
async def mailchimp_health():
    """Health check for Mailchimp integration"""
    return {
        "status": "healthy",
        "service": "mailchimp",
        "version": "1.0.0",
        "mode": "real"
    }

@router.get("/")
async def mailchimp_root():
    """Mailchimp integration root endpoint"""
    return {
        "service": "mailchimp",
        "status": "active",
        "endpoints": [
            "/auth/callback",
            "/audiences",
            "/campaigns",
            "/account",
            "/health"
        ]
    }
