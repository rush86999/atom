from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from core.database import get_db
from sales.lead_manager import LeadManager
from sales.intelligence import SalesIntelligence
from sales.call_service import CallAutomationService
from sales.models import Lead, Deal, CallTranscript

router = APIRouter(prefix="/api/sales", tags=["Sales Automation"])

@router.post("/leads/ingest")
async def ingest_lead(
    workspace_id: str, 
    lead_data: Dict[str, Any], 
    db: Session = Depends(get_db)
):
    manager = LeadManager(db)
    lead = manager.ingest_lead(workspace_id, lead_data)
    if not lead:
        return {"status": "skipped", "message": "Lead ingestion disabled or failed"}
    return {"status": "success", "lead_id": lead.id, "ai_score": lead.ai_score}

@router.get("/leads")
async def list_leads(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    leads = db.query(Lead).filter(Lead.workspace_id == workspace_id).order_by(Lead.ai_score.desc()).all()
    return leads

@router.get("/deals/{deal_id}/health")
async def get_deal_health(
    deal_id: str, 
    db: Session = Depends(get_db)
):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    intelligence = SalesIntelligence(db)
    result = intelligence.analyze_deal_health(deal)
    return result

@router.get("/deals")
async def list_deals(
    workspace_id: str,
    db: Session = Depends(get_db)
):
    deals = db.query(Deal).filter(Deal.workspace_id == workspace_id).all()
    return deals

@router.post("/calls/process")
async def process_call(
    workspace_id: str,
    deal_id: str,
    transcript_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    service = CallAutomationService(db)
    transcript = service.process_call_transcript(workspace_id, deal_id, transcript_data)
    if not transcript:
         return {"status": "skipped", "message": "Call processing disabled"}
    return {
        "status": "success", 
        "transcript_id": transcript.id, 
        "summary": transcript.summary,
        "action_items": transcript.action_items
    }

@router.get("/calls")
async def list_calls(
    workspace_id: str,
    deal_id: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(CallTranscript).filter(CallTranscript.workspace_id == workspace_id)
    if deal_id:
        query = query.filter(CallTranscript.deal_id == deal_id)
    return query.order_by(CallTranscript.created_at.desc()).all()

@router.post("/deals/{deal_id}/win")
async def win_deal(
    deal_id: str,
    credentials: Dict[str, Any],
    db: Session = Depends(get_db)
):
    from sales.order_to_cash import OrderToCashService
    service = OrderToCashService(db)
    # In a real app, this would be a background task
    await service.handle_deal_closed_won("temp_ws", deal_id, credentials)
    return {"status": "success", "message": "Order-to-Cash process triggered"}
