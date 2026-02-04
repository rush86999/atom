import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from db_connection import get_db_connection
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.token_storage import token_storage
from integrations.hubspot_service import get_hubspot_service
from integrations.microsoft365_service import microsoft365_service
from integrations.salesforce_service import SalesforceService, create_client_with_token
from integrations.zoho_crm_service import ZohoCRMService

router = APIRouter(prefix="/api/atom/sales/live", tags=["sales-live"])
logger = logging.getLogger(__name__)

# --- Data Models ---

class UnifiedDeal(BaseModel):
    id: str
    deal_name: str
    value: float
    status: str
    stage: str
    platform: str  # 'salesforce', 'hubspot', 'zoho', 'dynamics'
    company: Optional[str] = None
    close_date: Optional[str] = None
    owner: Optional[str] = None
    probability: Optional[float] = None
    url: Optional[str] = None

class SalesStats(BaseModel):
    total_pipeline_value: float
    active_deal_count: int
    win_rate: float
    avg_deal_size: float

class LivePipelineResponse(BaseModel):
    ok: bool = True
    stats: SalesStats
    deals: List[UnifiedDeal]
    providers: Dict[str, bool]

# --- Helper Functions ---

def map_salesforce_opportunity(opp: Dict[str, Any], instance_url: str = "") -> UnifiedDeal:
    return UnifiedDeal(
        id=opp.get("Id"),
        deal_name=opp.get("Name"),
        value=float(opp.get("Amount") or 0.0),
        status=opp.get("StageName"),
        stage=opp.get("StageName"),
        platform="salesforce",
        company=None, # Account name usually needs a separate fetch or join
        close_date=opp.get("CloseDate"),
        probability=float(opp.get("Probability") or 0.0) if opp.get("Probability") is not None else None,
        url=f"{instance_url}/{opp.get('Id')}" if instance_url else None
    )

def map_hubspot_deal(deal: Dict[str, Any]) -> UnifiedDeal:
    properties = deal.get("properties", {})
    return UnifiedDeal(
        id=deal.get("id"),
        deal_name=properties.get("dealname") or "Unknown Deal",
        value=float(properties.get("amount") or 0.0),
        status=properties.get("dealstage"),
        stage=properties.get("dealstage"),
        platform="hubspot",
        close_date=properties.get("closedate"),
        owner=properties.get("hubspot_owner_id")
    )

def map_zoho_deal(deal: Dict[str, Any]) -> UnifiedDeal:
    return UnifiedDeal(
        id=deal.get("id"),
        deal_name=deal.get("Deal_Name") or "Untitled Zoho Deal",
        value=float(deal.get("Amount") or 0.0),
        status=deal.get("Stage"),
        stage=deal.get("Stage"),
        platform="zoho",
        company=deal.get("Account_Name", {}).get("name"),
        close_date=deal.get("Closing_Date"),
        owner=deal.get("Owner", {}).get("name")
    )

def map_dynamics_deal(deal: Dict[str, Any]) -> UnifiedDeal:
    # This is a placeholder mapping for Dynamics 365 via MS Graph trending/insights
    return UnifiedDeal(
        id=deal.get("id", "dynamics_deal"),
        deal_name=deal.get("resourceVisualization", {}).get("title") or "Dynamics Opportunity",
        value=0.0, # Value often requires separate lookup in Dynamics
        status="Open",
        stage="Qualification",
        platform="dynamics",
        url=deal.get("resourceReference", {}).get("webUrl")
    )

# --- Endpoints ---

@router.get("/pipeline", response_model=LivePipelineResponse)
async def get_live_pipeline(
    limit: int = 50,
    # In a real app, we would get user_id from auth dependency
    # user_id: str = Depends(get_current_user) 
):
    """
    Fetch live opportunities/deals from connected CRMs (Salesforce, HubSpot)
    and aggregate them into a unified pipeline view.
    """
    deals = []
    providers_status = {"salesforce": False, "hubspot": False, "zoho": False, "dynamics": False}
    
    # Placeholder for user ID until full auth middleware is in place for this route
    # For now we rely on environment variables or specific user context
    # This matches behavior in atom_communication_live_api.py
    
    # 2. Fetch HubSpot Deals
    try:
        hubspot = get_hubspot_service()
        # We try to use the environment token first if available (common for single-tenant/dev)
        if os.getenv("HUBSPOT_ACCESS_TOKEN"):
             raw_deals = await hubspot.get_deals(limit=limit)
             deals.extend([map_hubspot_deal(d) for d in raw_deals])
             providers_status["hubspot"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live HubSpot deals: {e}")

    # 3. Fetch Salesforce Opportunities
    try:
        sf_token = None
        sf_instance = None
        
        # A. Try Token Storage
        tokens = token_storage.get_token("salesforce")
        if tokens:
            sf_token = tokens.get("access_token")
            sf_instance = tokens.get("instance_url")
            
        # B. Fallback to Env
        if not sf_token:
            sf_token = os.getenv("SALESFORCE_ACCESS_TOKEN")
            sf_instance = os.getenv("SALESFORCE_INSTANCE_URL")
            
        if sf_token and sf_instance:
            sf = create_client_with_token(sf_token, sf_instance)
            if sf:
                # Query specific fields to match UnifiedDeal
                query = f"SELECT Id, Name, Amount, StageName, CloseDate, Probability FROM Opportunity ORDER BY CloseDate DESC LIMIT {limit}"
                res = sf.query_all(query)
                records = res.get("records", [])
                
                deals.extend([map_salesforce_opportunity(r, sf_instance) for r in records])
                providers_status["salesforce"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Salesforce opportunities: {e}")

    # 4. Fetch Zoho CRM Deals
    try:
        zoho_token = os.getenv("ZOHO_CRM_ACCESS_TOKEN")
        if zoho_token:
            zoho = ZohoCRMService()
            raw_deals = await zoho.get_deals(token=zoho_token)
            deals.extend([map_zoho_deal(d) for d in raw_deals])
            providers_status["zoho"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Zoho CRM deals: {e}")

    # 5. Fetch Dynamics 365 Deals
    try:
        ms_token = os.getenv("MICROSOFT_365_ACCESS_TOKEN")
        if ms_token:
            res = await microsoft365_service.get_dynamics_deals(access_token=ms_token, top=limit)
            if res.get("status") == "success":
                raw_deals = res.get("data", {}).get("value", [])
                deals.extend([map_dynamics_deal(d) for d in raw_deals])
                providers_status["dynamics"] = True
    except Exception as e:
        logger.warning(f"Failed to fetch live Dynamics 365 deals: {e}")

    # Calculate Stats
    total_value = sum(d.value for d in deals)
    count = len(deals)
    avg_size = total_value / count if count > 0 else 0
    # simple mock calculation for win rate based on 'closed won' status
    won_count = sum(1 for d in deals if 'won' in d.status.lower())
    win_rate = (won_count / count * 100) if count > 0 else 0.0

    return LivePipelineResponse(
        ok=True,
        stats=SalesStats(
            total_pipeline_value=total_value,
            active_deal_count=count,
            win_rate=win_rate,
            avg_deal_size=avg_size
        ),
        deals=sorted(deals, key=lambda x: x.value, reverse=True),
        providers=providers_status
    )
