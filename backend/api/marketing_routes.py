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
async def get_marketing_summary(db: Session = Depends(get_db)):
    """
    Returns a unified marketing intelligence summary for the business owner.
    """
    import os
    
    try:
        # 1. Fetch real metrics from MarketingIntelligenceService
        from marketing.intelligence_service import MarketingIntelligenceService
        marketing_service = MarketingIntelligenceService(db)
        
        # Get channel performance data
        channel_data = marketing_service.get_channel_performance("default")
        
        # Convert to metrics format expected by reporter
        metrics = {}
        for channel in channel_data:
            metrics[channel["channel_name"]] = {
                "leads": channel.get("leads", 0),
                "cost": channel.get("spend", 0),
                "conversions": channel.get("conversions", 0),
                "conversion_rate": channel.get("conversion_rate", 0)
            }
        
        # If no channels configured, provide minimal structure
        if not metrics:
            metrics = {"no_data": {"leads": 0, "cost": 0, "conversions": 0}}
        
        # 2. Generate narrative report
        narrative = await reporter.generate_narrative_report(metrics)
        
        # 3. Get high-intent leads
        high_intent_leads = db.query(Lead).filter(
            Lead.workspace_id == "default",
            Lead.ai_score > 70
        ).order_by(Lead.ai_score.desc()).limit(5).all()
        
        # 4. Check GMB integration status
        mock_mode = os.getenv("MOCK_MODE_ENABLED", "false").lower() == "true"
        gmb_configured = bool(os.getenv("GOOGLE_BUSINESS_API_KEY") or os.getenv("GMB_CREDENTIALS"))
        gmb_status = "active" if gmb_configured else ("mock" if mock_mode else "not_configured")
        
        # 5. Pending reviews
        if gmb_configured:
            pending_reviews = None # Fetch needed
        elif mock_mode:
            pending_reviews = 12 # Mock data
        else:
            pending_reviews = "integration_required"
        
        return {
            "narrative_report": narrative,
            "performance_metrics": metrics,
            "high_intent_leads": [
                {
                    "id": l.id,
                    "name": f"{l.first_name} {l.last_name}" if l.first_name else l.email,
                    "score": l.ai_score,
                    "summary": l.ai_qualification_summary
                } for l in high_intent_leads
            ],
            "gmb_status": gmb_status,
            "pending_reviews": pending_reviews,
            "data_source": "mock" if mock_mode else "live"
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
