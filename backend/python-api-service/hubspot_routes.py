"""
ATOM HubSpot Integration Routes
FastAPI routes for HubSpot marketing and CRM functionality
Following ATOM API patterns and conventions
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from loguru import logger
import asyncio

from hubspot_service import create_hubspot_service, HubSpotService
from db_oauth_hubspot import create_hubspot_db_handler, HubSpotOAuthToken
from auth_handler_hubspot import HubSpotAuthHandler

# Create router
router = APIRouter(prefix="/api/hubspot", tags=["hubspot"])

# Global instances
hubspot_service = create_hubspot_service()
db_handler = create_hubspot_db_handler()
auth_handler = HubSpotAuthHandler()

# Dependencies
async def get_access_token_and_hub_id(user_id: str) -> tuple[str, str]:
    """Get access token and hub ID for user"""
    tokens = await db_handler.get_tokens(user_id)
    if not tokens:
        raise HTTPException(status_code=401, detail="HubSpot not authenticated for this user")
    
    if not tokens.hub_id:
        raise HTTPException(status_code=400, detail="HubSpot hub ID not configured")
    
    # Check if token is expired and refresh if needed
    if await db_handler.is_token_expired(user_id):
        if tokens.refresh_token:
            try:
                new_tokens = await auth_handler.refresh_access_token(tokens.refresh_token)
                await db_handler.save_tokens(HubSpotOAuthToken(
                    user_id=user_id,
                    access_token=new_tokens["access_token"],
                    refresh_token=new_tokens["refresh_token"],
                    token_type=new_tokens["token_type"],
                    expires_in=new_tokens["expires_in"],
                    hub_id=tokens.hub_id,
                    scopes=new_tokens.get("scope", [])
                ))
                return new_tokens["access_token"], tokens.hub_id
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise HTTPException(status_code=401, detail="Token expired and refresh failed")
        else:
            raise HTTPException(status_code=401, detail="Token expired and no refresh token available")
    
    return tokens.access_token, tokens.hub_id

# Contact management endpoints
@router.get("/contacts")
async def get_contacts(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of contacts to return"),
    email: Optional[str] = Query(None, description="Contact email filter"),
    first_name: Optional[str] = Query(None, description="Contact first name filter"),
    last_name: Optional[str] = Query(None, description="Contact last name filter"),
    company: Optional[str] = Query(None, description="Contact company filter"),
    created_after: Optional[str] = Query(None, description="Create date filter (YYYY-MM-DD)"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get list of contacts with optional filtering"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse date if provided
        created_date = date.fromisoformat(created_after) if created_after else None
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_contacts(
            access_token=access_token,
            limit=limit,
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            created_after=created_date,
            properties=properties_list
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    user_id: str = Query(..., description="User ID"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get specific contact by ID"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_contact(contact_id, access_token, properties_list)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/contacts")
async def create_contact(
    contact_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new contact"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.create_contact(
            access_token=access_token,
            email=contact_data["email"],
            first_name=contact_data.get("first_name"),
            last_name=contact_data.get("last_name"),
            phone=contact_data.get("phone"),
            company=contact_data.get("company"),
            properties=contact_data.get("properties"),
            lifecycle_stage=contact_data.get("lifecycle_stage")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Contact created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create contact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/contacts/{contact_id}")
async def update_contact(
    contact_id: str,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing contact"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.update_contact(
            access_token=access_token,
            contact_id=contact_id,
            email=update_data.get("email"),
            first_name=update_data.get("first_name"),
            last_name=update_data.get("last_name"),
            phone=update_data.get("phone"),
            company=update_data.get("company"),
            properties=update_data.get("properties"),
            lifecycle_stage=update_data.get("lifecycle_stage")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Contact updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Delete contact"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.delete_contact(contact_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Contact deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete contact {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Company management endpoints
@router.get("/companies")
async def get_companies(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of companies to return"),
    domain: Optional[str] = Query(None, description="Company domain filter"),
    name: Optional[str] = Query(None, description="Company name filter"),
    industry: Optional[str] = Query(None, description="Company industry filter"),
    state: Optional[str] = Query(None, description="Company state filter"),
    created_after: Optional[str] = Query(None, description="Create date filter (YYYY-MM-DD)"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get list of companies with optional filtering"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse date if provided
        created_date = date.fromisoformat(created_after) if created_after else None
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_companies(
            access_token=access_token,
            limit=limit,
            domain=domain,
            name=name,
            industry=industry,
            state=state,
            created_after=created_date,
            properties=properties_list
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/companies/{company_id}")
async def get_company(
    company_id: str,
    user_id: str = Query(..., description="User ID"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get specific company by ID"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_company(company_id, access_token, properties_list)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/companies")
async def create_company(
    company_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new company"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.create_company(
            access_token=access_token,
            name=company_data["name"],
            domain=company_data.get("domain"),
            description=company_data.get("description"),
            industry=company_data.get("industry"),
            state=company_data.get("state"),
            country=company_data.get("country"),
            phone=company_data.get("phone"),
            website=company_data.get("website"),
            employee_count=company_data.get("employee_count"),
            annual_revenue=company_data.get("annual_revenue"),
            properties=company_data.get("properties")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Company created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create company: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/companies/{company_id}")
async def update_company(
    company_id: str,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing company"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.update_company(
            access_token=access_token,
            company_id=company_id,
            name=update_data.get("name"),
            domain=update_data.get("domain"),
            description=update_data.get("description"),
            industry=update_data.get("industry"),
            state=update_data.get("state"),
            country=update_data.get("country"),
            phone=update_data.get("phone"),
            website=update_data.get("website"),
            employee_count=update_data.get("employee_count"),
            annual_revenue=update_data.get("annual_revenue"),
            properties=update_data.get("properties")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Company updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Delete company"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.delete_company(company_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Company deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Deal management endpoints
@router.get("/deals")
async def get_deals(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of deals to return"),
    deal_name: Optional[str] = Query(None, description="Deal name filter"),
    deal_stage: Optional[str] = Query(None, description="Deal stage filter"),
    amount: Optional[float] = Query(None, description="Minimum amount filter"),
    closed_won: Optional[bool] = Query(None, description="Closed won filter"),
    created_after: Optional[str] = Query(None, description="Create date filter (YYYY-MM-DD)"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get list of deals with optional filtering"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse date if provided
        created_date = date.fromisoformat(created_after) if created_after else None
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_deals(
            access_token=access_token,
            limit=limit,
            deal_name=deal_name,
            deal_stage=deal_stage,
            amount=amount,
            closed_won=closed_won,
            created_after=created_date,
            properties=properties_list
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deals/{deal_id}")
async def get_deal(
    deal_id: str,
    user_id: str = Query(..., description="User ID"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get specific deal by ID"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_deal(deal_id, access_token, properties_list)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deals")
async def create_deal(
    deal_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new deal"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse date if provided
        close_date = date.fromisoformat(deal_data["close_date"]) if deal_data.get("close_date") else None
        
        result = await hubspot_service.create_deal(
            access_token=access_token,
            deal_name=deal_data["deal_name"],
            amount=deal_data.get("amount"),
            pipeline=deal_data.get("pipeline"),
            deal_stage=deal_data.get("deal_stage"),
            close_date=close_date,
            contact_id=deal_data.get("contact_id"),
            company_id=deal_data.get("company_id"),
            properties=deal_data.get("properties")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Deal created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create deal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/deals/{deal_id}")
async def update_deal(
    deal_id: str,
    update_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Update existing deal"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse date if provided
        close_date = date.fromisoformat(update_data["close_date"]) if update_data.get("close_date") else None
        
        result = await hubspot_service.update_deal(
            access_token=access_token,
            deal_id=deal_id,
            deal_name=update_data.get("deal_name"),
            amount=update_data.get("amount"),
            pipeline=update_data.get("pipeline"),
            deal_stage=update_data.get("deal_stage"),
            close_date=close_date,
            properties=update_data.get("properties")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Deal updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Delete deal"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.delete_deal(deal_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Deal deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Pipeline management endpoints
@router.get("/pipelines")
async def get_pipelines(user_id: str = Query(..., description="User ID")):
    """Get all sales pipelines"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.get_pipelines(access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pipelines/{pipeline_id}/stages")
async def get_pipeline_stages(
    pipeline_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get stages for a specific pipeline"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.get_pipeline_stages(access_token, pipeline_id)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline stages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Campaign management endpoints
@router.get("/campaigns")
async def get_campaigns(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of campaigns to return"),
    campaign_name: Optional[str] = Query(None, description="Campaign name filter"),
    status: Optional[str] = Query(None, description="Campaign status filter"),
    created_after: Optional[str] = Query(None, description="Create date filter (YYYY-MM-DD)")
):
    """Get list of marketing campaigns"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse date if provided
        created_date = date.fromisoformat(created_after) if created_after else None
        
        result = await hubspot_service.get_campaigns(
            access_token=access_token,
            limit=limit,
            campaign_name=campaign_name,
            status=status,
            created_after=created_date
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    user_id: str = Query(..., description="User ID")
):
    """Get specific campaign by ID"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.get_campaign(campaign_id, access_token)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/campaigns")
async def create_campaign(
    campaign_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new marketing campaign"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.create_campaign(
            access_token=access_token,
            campaign_name=campaign_data["campaign_name"],
            subject=campaign_data.get("subject"),
            content=campaign_data.get("content"),
            status=campaign_data.get("status", "DRAFT"),
            campaign_type=campaign_data.get("campaign_type", "EMAIL"),
            properties=campaign_data.get("properties")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Campaign created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Analytics endpoints
@router.get("/analytics/deals")
async def get_deal_analytics(
    user_id: str = Query(..., description="User ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get deal analytics and metrics"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_deal_analytics(
            access_token=access_token,
            date_from=start_date,
            date_to=end_date,
            properties=properties_list
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deal analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/contacts")
async def get_contact_analytics(
    user_id: str = Query(..., description="User ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    properties: Optional[str] = Query(None, description="Comma-separated properties to return")
):
    """Get contact analytics and metrics"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        # Parse properties if provided
        properties_list = properties.split(",") if properties else None
        
        result = await hubspot_service.get_contact_analytics(
            access_token=access_token,
            date_from=start_date,
            date_to=end_date,
            properties=properties_list
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get contact analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/campaigns/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: str,
    user_id: str = Query(..., description="User ID"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get campaign analytics and metrics"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse dates if provided
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
        
        result = await hubspot_service.get_campaign_analytics(
            access_token=access_token,
            campaign_id=campaign_id,
            date_from=start_date,
            date_to=end_date
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Lead management endpoints
@router.get("/lead-lists")
async def get_lead_lists(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of lead lists to return")
):
    """Get all lead lists"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.get_lead_lists(access_token, limit)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get lead lists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lead-lists")
async def create_lead_list(
    list_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Create a new lead list"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.create_lead_list(
            access_token=access_token,
            list_name=list_data["list_name"],
            description=list_data.get("description"),
            processing_type=list_data.get("processing_type", "MANUAL")
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Lead list created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create lead list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lead-lists/{list_id}/members")
async def add_contacts_to_list(
    list_id: str,
    membership_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Add contacts to a lead list"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        contact_ids = membership_data.get("contact_ids", [])
        
        result = await hubspot_service.add_contacts_to_list(access_token, list_id, contact_ids)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Added {len(contact_ids)} contacts to lead list"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add contacts to list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/lead-lists/{list_id}/members")
async def remove_contacts_from_list(
    list_id: str,
    membership_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Remove contacts from a lead list"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        contact_ids = membership_data.get("contact_ids", [])
        
        result = await hubspot_service.remove_contacts_from_list(access_token, list_id, contact_ids)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Removed {len(contact_ids)} contacts from lead list"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove contacts from list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Email marketing endpoints
@router.get("/email-templates")
async def get_email_templates(
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(30, ge=1, le=100, description="Number of templates to return")
):
    """Get all email templates"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        result = await hubspot_service.get_email_templates(access_token, limit)
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get email templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-email")
async def send_email_to_contacts(
    email_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Send email to specific contacts"""
    try:
        access_token, hub_id = await get_access_token_and_hub_id(user_id)
        
        # Parse send_at if provided
        send_at = datetime.fromisoformat(email_data["send_at"]) if email_data.get("send_at") else None
        
        result = await hubspot_service.send_email_to_contacts(
            access_token=access_token,
            template_id=email_data["template_id"],
            contact_ids=email_data["contact_ids"],
            send_at=send_at
        )
        
        return {
            "ok": True,
            "data": result,
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Email sent to {len(email_data['contact_ids'])} contacts"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoints
@router.post("/auth/save")
async def save_auth_data(
    auth_data: Dict[str, Any] = Body(...),
    user_id: str = Query(..., description="User ID")
):
    """Save authentication data"""
    try:
        # Save tokens
        tokens_data = auth_data.get("tokens", {})
        tokens = HubSpotOAuthToken(
            user_id=user_id,
            access_token=tokens_data.get("access_token"),
            refresh_token=tokens_data.get("refresh_token"),
            token_type=tokens_data.get("token_type", "Bearer"),
            expires_in=tokens_data.get("expires_in", 3600),
            hub_id=tokens_data.get("hub_id"),
            hub_domain=tokens_data.get("hub_domain"),
            app_id=tokens_data.get("app_id"),
            scopes=tokens_data.get("scope", [])
        )
        
        success = await db_handler.save_tokens(tokens)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save tokens")
        
        # Save user data
        from db_oauth_hubspot import HubSpotUserData
        account_data_dict = auth_data.get("account_info", {})
        user_data = HubSpotUserData(
            user_id=user_id,
            hub_id=tokens_data.get("hub_id"),
            user_email=account_data_dict.get("email"),
            user_name=account_data_dict.get("user_name"),
            first_name=account_data_dict.get("first_name"),
            last_name=account_data_dict.get("last_name"),
            portal_id=account_data_dict.get("portal_id"),
            account_type=account_data_dict.get("account_type"),
            is_super_admin=account_data_dict.get("is_super_admin"),
            is_primary_user=account_data_dict.get("is_primary_user"),
            role_id=account_data_dict.get("role_id"),
            role_name=account_data_dict.get("role_name"),
            permissions=account_data_dict.get("permissions", {}),
            metadata=account_data_dict.get("metadata", {})
        )
        
        await db_handler.save_user_data(user_data)
        
        # Save portal data
        portal_data_dict = auth_data.get("portal_info", {})
        from db_oauth_hubspot import HubSpotPortalData
        portal_data = HubSpotPortalData(
            user_id=user_id,
            portal_id=portal_data_dict.get("portal_id"),
            company_name=portal_data_dict.get("company_name"),
            domain=portal_data_dict.get("domain"),
            currency=portal_data_dict.get("currency"),
            time_zone=portal_data_dict.get("time_zone")
        )
        
        await db_handler.save_portal_data(portal_data)
        
        return {
            "ok": True,
            "message": "Authentication data saved successfully",
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save auth data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/status")
async def get_auth_status(user_id: str = Query(..., description="User ID")):
    """Get authentication status"""
    try:
        tokens = await db_handler.get_tokens(user_id)
        user_data = await db_handler.get_user_data(user_id)
        portal_data = await db_handler.get_portal_data(user_id)
        is_expired = await db_handler.is_token_expired(user_id)
        
        return {
            "ok": True,
            "data": {
                "authenticated": bool(tokens) and not is_expired,
                "user": user_data,
                "portal": portal_data,
                "tokens_exist": bool(tokens),
                "token_expired": is_expired,
                "hub_configured": bool(tokens and tokens.hub_id) if tokens else False
            },
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/auth")
async def revoke_auth(user_id: str = Query(..., description="User ID")):
    """Revoke authentication"""
    try:
        # Get tokens for revocation
        tokens = await db_handler.get_tokens(user_id)
        if tokens and tokens.access_token:
            await auth_handler.revoke_token(tokens.access_token)
        
        # Delete from database
        await db_handler.delete_tokens(user_id)
        
        return {
            "ok": True,
            "message": "Authentication revoked successfully",
            "service": "hubspot",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to revoke auth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health")
async def health_check():
    """HubSpot integration health check"""
    try:
        # Check service configuration
        config_status = bool(
            hubspot_service.config.client_id and
            hubspot_service.config.client_secret
        )
        
        return {
            "ok": True,
            "data": {
                "service": "hubspot",
                "status": "healthy" if config_status else "misconfigured",
                "configured": config_status,
                "database_connected": db_handler is not None,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"HubSpot health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export router
def register_hubspot_routes(app):
    """Register HubSpot API routes"""
    app.include_router(router)
    logger.info("HubSpot API routes registered")