from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from integrations.ai_enhanced_service import ai_enhanced_service
from core.marketing_manager import AIMarketingManager
from core.reputation_service import ReputationManager
from core.marketing_analytics import PlainEnglishReporter
from sales.models import Lead
from typing import List, Dict, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize managers (ideally these would be injected or handled via a startup event)
marketing_manager = AIMarketingManager(ai_service=ai_enhanced_service)
reputation_manager = ReputationManager(ai_service=ai_enhanced_service)
reporter = PlainEnglishReporter(ai_service=ai_enhanced_service)

@router.get("/dashboard/summary")
async def get_marketing_summary(workspace_id: str = "default-workspace", db: Session = Depends(get_db)):
    """
    Returns a unified marketing intelligence summary for the business owner.
    """
    try:
        # 1. Fetch some raw data for the reporter
        # (In a real app, this would come from MarketingIntelligenceService)
        mock_metrics = {
            "google_search": {"calls": 12, "cost": 120, "clicks": 85},
            "facebook_ads": {"calls": 3, "cost": 90, "clicks": 140},
            "referral": {"calls": 5, "cost": 0, "clicks": 0}
        }
        
        # 2. Generate narrative report
        narrative = await reporter.generate_narrative_report(mock_metrics)
        
        # 3. Get high-intent leads
        high_intent_leads = db.query(Lead).filter(
            Lead.workspace_id == workspace_id,
            Lead.ai_score > 70
        ).order_by(Lead.ai_score.desc()).limit(5).all()
        
        return {
            "narrative_report": narrative,
            "performance_metrics": mock_metrics,
            "high_intent_leads": [
                {
                    "id": l.id,
                    "name": f"{l.first_name} {l.last_name}" if l.first_name else l.email,
                    "score": l.ai_score,
                    "summary": l.ai_qualification_summary
                } for l in high_intent_leads
            ],
            "gmb_status": "active",
            "pending_reviews": 0 # Logic to be added
        }
    except Exception as e:
        logger.error(f"Error fetching marketing summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/leads/{lead_id}/score")
async def score_lead(lead_id: str, db: Session = Depends(get_db)):
    """
    Triggers AI scoring for a specific lead.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    # Get interaction history (Simplified)
    history = [f"Lead source: {lead.source}"]
    
    scoring_result = await marketing_manager.lead_scoring.calculate_score(
        {"email": lead.email, "name": lead.first_name},
        history
    )
    
    # Update lead record
    lead.ai_score = float(scoring_result.get("score", 0))
    lead.ai_qualification_summary = scoring_result.get("rationale")
    db.commit()
    
    return scoring_result

@router.get("/reputation/analyze")
async def analyze_reputation(interaction: str):
    """
    Analyzes an interaction and suggests a feedback strategy (Public vs Private).
    """
    strategy = await reputation_manager.determine_feedback_strategy(interaction)
    return strategy

@router.get("/gmb/weekly-post/suggest")
async def suggest_gmb_post(business_name: str, location: str, events: List[str] = Query(None)):
    """
    Suggests a weekly GMB post.
    """
    events = events or ["Open for business", "New services available"]
    post = await marketing_manager.gmb.generate_weekly_update(
        {"name": business_name, "location": location},
        events
    )
    return {"suggested_post": post}
