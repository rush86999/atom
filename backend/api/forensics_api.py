
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.financial_forensics import get_forensics_services

router = BaseAPIRouter(prefix="/api/forensics", tags=["Forensics"])

@router.get("/vendor-drift")
async def get_vendor_drift(
    db: Session = Depends(get_db)
):
    """Detect vendors with increasing costs"""
    try:
        services = get_forensics_services(db)
        drift_data = await services["vendor"].detect_price_drift("default")
        return router.success_response(
            data=drift_data,
            message="Vendor drift data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to detect vendor drift",
            details={"error": str(e)}
        )

@router.get("/pricing-opportunities")
async def get_pricing_opportunities(
    db: Session = Depends(get_db)
):
    """Get recommendations for price optimization"""
    try:
        services = get_forensics_services(db)
        opportunities = await services["pricing"].get_pricing_recommendations("default")
        return router.success_response(
            data=opportunities,
            message="Pricing opportunities retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to get pricing opportunities",
            details={"error": str(e)}
        )

@router.get("/subscription-waste")
async def get_subscription_waste(
    db: Session = Depends(get_db)
):
    """Identify unused subscriptions"""
    try:
        services = get_forensics_services(db)
        waste_data = await services["waste"].find_zombie_subscriptions("default")
        return router.success_response(
            data=waste_data,
            message="Subscription waste data retrieved successfully"
        )
    except Exception as e:
        raise router.internal_error(
            message="Failed to identify subscription waste",
            details={"error": str(e)}
        )
