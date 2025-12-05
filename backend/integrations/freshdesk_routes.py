"""
Freshdesk Integration Routes for ATOM Platform
Uses the real freshdesk_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .freshdesk_service import get_freshdesk_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/freshdesk", tags=["freshdesk"])


class TicketCreateRequest(BaseModel):
    subject: str
    description: str
    email: str
    priority: int = 1
    status: int = 2


class TicketUpdateRequest(BaseModel):
    status: Optional[int] = None
    priority: Optional[int] = None


class SearchRequest(BaseModel):
    query: str


@router.get("/auth/url")
async def get_auth_url():
    """Get Freshdesk auth info (API key based)"""
    return {
        "message": "Freshdesk uses API key authentication",
        "docs_url": "https://support.freshdesk.com/support/solutions/articles/215517-how-to-find-your-api-key",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status")
async def freshdesk_status():
    """Get Freshdesk integration status"""
    service = get_freshdesk_service()
    return {
        "ok": True,
        "service": "freshdesk",
        "configured": service is not None,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def freshdesk_health():
    """Health check for Freshdesk integration"""
    try:
        service = get_freshdesk_service()
        if not service:
            return {"ok": False, "status": "not_configured", "timestamp": datetime.now().isoformat()}
        result = await service.health_check()
        return {"ok": result.get("status") == "healthy", **result}
    except Exception as e:
        return {"ok": False, "status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}


@router.get("/tickets")
async def get_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    status: Optional[int] = None
):
    """Get Freshdesk tickets"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        tickets = await service.get_tickets(page=page, per_page=per_page, status=str(status) if status else None)
        return {"ok": True, "tickets": tickets, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tickets")
async def create_ticket(request: TicketCreateRequest):
    """Create a Freshdesk ticket"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        ticket = await service.create_ticket({
            "subject": request.subject,
            "description": request.description,
            "email": request.email,
            "priority": request.priority,
            "status": request.status
        })
        return {"ok": True, "ticket": ticket, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """Get a specific ticket"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        ticket = await service.get_ticket(ticket_id)
        return {"ok": True, "ticket": ticket, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: int, request: TicketUpdateRequest):
    """Update a ticket"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        ticket = await service.update_ticket(ticket_id, update_data)
        return {"ok": True, "ticket": ticket, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contacts")
async def get_contacts(page: int = Query(1, ge=1), per_page: int = Query(30, ge=1, le=100)):
    """Get Freshdesk contacts"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        contacts = await service.get_contacts(page=page, per_page=per_page)
        return {"ok": True, "contacts": contacts, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def get_agents():
    """Get Freshdesk agents"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        agents = await service.get_agents()
        return {"ok": True, "agents": agents, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/tickets")
async def search_tickets(request: SearchRequest):
    """Search Freshdesk tickets"""
    try:
        service = get_freshdesk_service()
        if not service:
            raise HTTPException(status_code=503, detail="Freshdesk not configured")
        results = await service.search_tickets(request.query)
        return {"ok": True, "query": request.query, "results": results, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))
