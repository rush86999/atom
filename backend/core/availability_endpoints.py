from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.availability_negotiator import availability_negotiator
from core.auth import get_current_user
from core.models import User

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])

class NegotiationRequest(BaseModel):
    duration_minutes: int
    search_start: datetime
    search_end: datetime
    min_wellness_score: Optional[float] = 40.0

class NegotiationResponse(BaseModel):
    success: bool
    slots: List[Dict[str, Any]]
    message: str

@router.post("/negotiate", response_model=NegotiationResponse)
async def negotiate_availability(
    request: NegotiationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Find best compromise time slots for a meeting, 
    accounting for cross-calendar availability and burnout risk.
    """
    try:
        slots = await availability_negotiator.negotiate_slots(
            user_id=current_user.id,
            duration_minutes=request.duration_minutes,
            search_start=request.search_start,
            search_end=request.search_end,
            min_wellness_score=request.min_wellness_score
        )
        
        if not slots:
            return NegotiationResponse(
                success=True,
                slots=[],
                message="No available slots found in the specified range with acceptable wellness score."
            )
            
        return NegotiationResponse(
            success=True,
            slots=slots,
            message=f"Found {len(slots)} optimal time slots with high wellness alignment."
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Negotiation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
