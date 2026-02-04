import logging
from typing import Any, Dict, List
from fastapi import Body, Depends
from sqlalchemy.orm import Session

from core.active_intervention_service import active_intervention_service
from core.base_routes import BaseAPIRouter
from core.business_health_service import business_health_service
from core.cross_system_reasoning import CrossSystemReasoningEngine
from core.database import get_db

router = BaseAPIRouter(prefix="/api/business-health", tags=["operational-intelligence"])
logger = logging.getLogger(__name__)

@router.get("/priorities")
async def get_daily_priorities(db: Session = Depends(get_db)):
    """
    Returns a curated list of high-impact tasks for the owner.
    """
    try:
        # Update service with current DB session if needed
        business_health_service._db = db
        result = await business_health_service.get_daily_priorities("default")
        return router.success_response(data=result)
    except Exception as e:
        logger.error(f"Error fetching daily priorities: {e}")
        raise router.internal_error(message=f"Failed to fetch daily priorities: {str(e)}")

@router.post("/simulate")
async def simulate_business_decision(
    decision_type: str = Body(...),
    data: Dict[str, Any] = Body(...)
):
    """
    Simulates the impact of a business decision (Hiring, Spend, etc.)
    """
    try:
        result = await business_health_service.simulate_decision("default", decision_type, data)
        return router.success_response(data=result)
    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        raise router.internal_error(message=f"Failed to run simulation: {str(e)}")

@router.get("/forensics/price-drift")
async def get_price_drift(db: Session = Depends(get_db)):
    """
    Detects vendor and ad-spend price drift.
    """
    try:
        from core.financial_forensics import MOCK_MODE, VendorIntelligence
        service = VendorIntelligence(db)
        data = await service.detect_price_drift("default")
        return router.success_response(
            data=data,
            metadata={"is_mock": MOCK_MODE}
        )
    except Exception as e:
        logger.error(f"Error fetching price drift: {e}")
        raise router.internal_error(message=f"Failed to fetch price drift: {str(e)}")

@router.get("/forensics/pricing-advisor")
async def get_pricing_advice(db: Session = Depends(get_db)):
    """
    Provides margin protection and underpricing recommendations.
    """
    try:
        from core.financial_forensics import MOCK_MODE, PricingAdvisor
        service = PricingAdvisor(db)
        data = await service.get_pricing_recommendations("default")
        return router.success_response(
            data=data,
            metadata={"is_mock": MOCK_MODE}
        )
    except Exception as e:
        logger.error(f"Error fetching pricing advice: {e}")
        raise router.internal_error(message=f"Failed to fetch pricing advice: {str(e)}")

@router.get("/forensics/waste")
async def get_subscription_waste(db: Session = Depends(get_db)):
    """
    Identifies SaaS waste and zombie subscriptions.
    """
    try:
        from core.financial_forensics import MOCK_MODE, SubscriptionWasteService
        service = SubscriptionWasteService(db)
        data = await service.find_zombie_subscriptions("default")
        return router.success_response(
            data=data,
            metadata={"is_mock": MOCK_MODE}
        )
    except Exception as e:
        # Graceful fallback if checking is_mock fails
        logger.error(f"Error fetching subscription waste: {e}")
        return router.success_response(data=[], metadata={"is_mock": False})

# Phase 11: Active Interventions

@router.post("/interventions/generate")
async def generate_interventions(
    db: Session = Depends(get_db)
):
    """
    Triggers the Cross-System Reasoning Engine to find active interventions.
    """
    engine = CrossSystemReasoningEngine(db)
    interventions = await engine.generate_interventions("default")
    return router.success_response(
        data=interventions,
        message="Interventions generated successfully"
    )

@router.post("/interventions/{id}/execute")
async def execute_intervention(
    id: str,
    payload: Dict[str, Any] = Body(...),
    action: str = Body(..., embed=True)
):
    """
    Executes a specific intervention action.
    """
    try:
        result = await active_intervention_service.execute_intervention(id, action, payload)
        return router.success_response(
            data=result,
            message="Intervention executed successfully"
        )
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise router.internal_error(message=f"Failed to execute intervention: {str(e)}")
