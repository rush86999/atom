import json
import logging
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.core.mock_mode import get_mock_mode_manager
from .hubspot_service import HubSpotService

# Create router
router = APIRouter(prefix="/api/hubspot", tags=["hubspot"])


# Pydantic Models
class HubSpotAuthRequest(BaseModel):
    client_id: str = Field(..., description="HubSpot OAuth client ID")
    client_secret: str = Field(..., description="HubSpot OAuth client secret")
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    code: str = Field(..., description="OAuth authorization code")


class HubSpotContact(BaseModel):
    id: str = Field(..., description="Contact ID")
    email: str = Field(..., description="Contact email")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    company: Optional[str] = Field(None, description="Company name")
    phone: Optional[str] = Field(None, description="Phone number")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")
    lifecycle_stage: Optional[str] = Field(None, description="Lifecycle stage")
    lead_status: Optional[str] = Field(None, description="Lead status")


class HubSpotCompany(BaseModel):
    id: str = Field(..., description="Company ID")
    name: str = Field(..., description="Company name")
    domain: Optional[str] = Field(None, description="Company domain")
    industry: Optional[str] = Field(None, description="Industry")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State")
    country: Optional[str] = Field(None, description="Country")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")


class HubSpotDeal(BaseModel):
    id: str = Field(..., description="Deal ID")
    deal_name: str = Field(..., description="Deal name")
    amount: Optional[float] = Field(None, description="Deal amount")
    stage: str = Field(..., description="Deal stage")
    pipeline: str = Field(..., description="Pipeline name")
    close_date: Optional[datetime] = Field(None, description="Close date")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")
    owner_id: Optional[str] = Field(None, description="Owner ID")


class HubSpotCampaign(BaseModel):
    id: str = Field(..., description="Campaign ID")
    name: str = Field(..., description="Campaign name")
    type: str = Field(..., description="Campaign type")
    status: str = Field(..., description="Campaign status")
    created_at: datetime = Field(..., description="Creation date")
    last_modified: datetime = Field(..., description="Last modified date")
    num_included: int = Field(..., description="Number of contacts included")
    num_responded: int = Field(..., description="Number of contacts responded")


class HubSpotList(BaseModel):
    id: str = Field(..., description="List ID")
    name: str = Field(..., description="List name")
    list_type: str = Field(..., description="List type")
    created_at: datetime = Field(..., description="Creation date")
    last_processing_finished_at: Optional[datetime] = Field(
        None, description="Last processing time"
    )
    member_count: int = Field(..., description="Number of members")


class HubSpotSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    object_type: str = Field(
        "contact", description="Object type to search (contact, company, deal)"
    )


class HubSpotSearchResponse(BaseModel):
    results: List[dict] = Field(..., description="Search results")
    total: int = Field(..., description="Total results found")


class HubSpotStats(BaseModel):
    total_contacts: int = Field(..., description="Total contacts")
    total_companies: int = Field(..., description="Total companies")
    total_deals: int = Field(..., description="Total deals")
    total_campaigns: int = Field(..., description="Total campaigns")
    active_deals: int = Field(..., description="Active deals count")
    won_deals: int = Field(..., description="Won deals count")
    lost_deals: int = Field(..., description="Lost deals count")
    total_revenue: float = Field(..., description="Total revenue")


class HubSpotContactCreate(BaseModel):
    email: str = Field(..., description="Contact email")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    company: Optional[str] = Field(None, description="Company name")
    phone: Optional[str] = Field(None, description="Phone number")


class HubSpotDealCreate(BaseModel):
    deal_name: str = Field(..., description="Deal name")
    amount: Optional[float] = Field(None, description="Deal amount")
    stage: str = Field(..., description="Deal stage")
    pipeline: str = Field(..., description="Pipeline name")
    close_date: Optional[datetime] = Field(None, description="Close date")


# API Routes
@router.post("/callback")
async def hubspot_auth(auth_request: HubSpotAuthRequest):
    """Authenticate with HubSpot OAuth"""
    service = HubSpotService()
    return await service.authenticate(
        client_id=auth_request.client_id,
        client_secret=auth_request.client_secret,
        redirect_uri=auth_request.redirect_uri,
        code=auth_request.code
    )


@router.get("/contacts")
async def get_contacts(limit: int = 100, offset: int = 0):
    """Get HubSpot contacts"""
    service = HubSpotService()
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("hubspot", bool(service.access_token)):
        return mock_manager.get_mock_data("hubspot", "contacts", limit)
    return await service.get_contacts(limit, offset)


@router.get("/companies")
async def get_companies(limit: int = 100, offset: int = 0):
    """Get HubSpot companies"""
    service = HubSpotService()
    return await service.get_companies(limit, offset)


@router.get("/deals")
async def get_deals(limit: int = 100, offset: int = 0):
    """Get HubSpot deals"""
    service = HubSpotService()
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("hubspot", bool(service.access_token)):
        return mock_manager.get_mock_data("hubspot", "deals", limit)
    return await service.get_deals(limit, offset)


@router.get("/campaigns")
async def get_campaigns(limit: int = 100, offset: int = 0):
    """Get HubSpot campaigns"""
    service = HubSpotService()
    return await service.get_campaigns(limit, offset)


@router.get("/lists")
async def get_lists(limit: int = 100, offset: int = 0):
    """Get HubSpot contact lists"""
    # Not implemented in new service yet, returning empty or mock
    return []


@router.post("/search")
async def search_content(search_request: HubSpotSearchRequest):
    """Search HubSpot content"""
    service = HubSpotService()
    return await service.search_content(search_request.query, search_request.object_type)


@router.post("/contacts/create")
async def create_contact(contact_data: HubSpotContactCreate):
    """Create a new HubSpot contact"""
    service = HubSpotService()
    return await service.create_contact(
        email=contact_data.email,
        first_name=contact_data.first_name,
        last_name=contact_data.last_name,
        company=contact_data.company,
        phone=contact_data.phone
    )


@router.post("/deals/create")
async def create_deal(deal_data: HubSpotDealCreate):
    """Create a new HubSpot deal"""
    # Not implemented in new service yet
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/stats")
async def get_stats():
    """Get HubSpot platform statistics"""
    # Mock stats
    return {
        "total_contacts": 1500,
        "total_companies": 250,
        "total_deals": 75,
        "total_campaigns": 12,
        "active_deals": 45,
        "won_deals": 20,
        "lost_deals": 10,
        "total_revenue": 1250000.0,
    }


@router.get("/health")
async def health_check():
    """Health check for HubSpot service"""
    service = HubSpotService()
    mock_manager = get_mock_mode_manager()
    if mock_manager.is_mock_mode("hubspot", bool(service.access_token)):
         return {
            "ok": True,
            "status": "healthy",
            "service": "hubspot",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "is_mock": True
        }
    return await service.health_check()


@router.get("/")
async def hubspot_root():
    """HubSpot integration root endpoint"""
    return {
        "service": "hubspot",
        "status": "active",
        "version": "1.0.0",
        "description": "HubSpot CRM and Marketing Automation Integration",
        "endpoints": [
            "/auth - OAuth authentication",
            "/contacts - Get contacts",
            "/companies - Get companies",
            "/deals - Get deals",
            "/campaigns - Get campaigns",
            "/lists - Get contact lists",
            "/search - Search content",
            "/contacts/create - Create contact",
            "/deals/create - Create deal",
            "/stats - Get platform statistics",
            "/health - Health check",
        ],
    }
