"""
Twilio Integration Routes for ATOM Platform
Uses the real twilio_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .twilio_service import get_twilio_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


class SendSMSRequest(BaseModel):
    to: str
    body: str
    from_number: Optional[str] = None


class MakeCallRequest(BaseModel):
    to: str
    twiml_url: str
    from_number: Optional[str] = None


@router.get("/auth/url")
async def get_auth_url():
    """Get Twilio console URL"""
    return {
        "url": "https://www.twilio.com/console",
        "message": "Twilio uses API key authentication, not OAuth",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/sms/send")
async def send_sms(request: SendSMSRequest):
    """Send an SMS message"""
    try:
        service = get_twilio_service()
        result = await service.send_sms(request.to, request.body, request.from_number)
        return {"ok": True, "message": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages")
async def get_messages(
    to: Optional[str] = None,
    from_number: Optional[str] = None,
    page_size: int = Query(50, ge=1, le=100)
):
    """Get message history"""
    try:
        service = get_twilio_service()
        messages = await service.get_messages(to, from_number, page_size)
        return {"ok": True, "messages": messages, "count": len(messages), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calls/make")
async def make_call(request: MakeCallRequest):
    """Make a voice call"""
    try:
        service = get_twilio_service()
        result = await service.make_call(request.to, request.twiml_url, request.from_number)
        return {"ok": True, "call": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to make call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls")
async def get_calls(
    to: Optional[str] = None,
    from_number: Optional[str] = None,
    page_size: int = Query(50, ge=1, le=100)
):
    """Get call history"""
    try:
        service = get_twilio_service()
        calls = await service.get_calls(to, from_number, page_size)
        return {"ok": True, "calls": calls, "count": len(calls), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to get calls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account")
async def get_account_info():
    """Get Twilio account information"""
    try:
        service = get_twilio_service()
        account = await service.get_account_info()
        return {"ok": True, "account": account, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to get account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def twilio_status():
    """Status check for Twilio integration"""
    service = get_twilio_service()
    return {
        "ok": True,
        "service": "twilio",
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "capabilities": ["sms", "voice", "messaging"]
    }


@router.get("/health")
async def twilio_health():
    """Health check for Twilio integration"""
    try:
        service = get_twilio_service()
        health = await service.health_check()
        return health
    except Exception as e:
        return {"ok": False, "status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}
