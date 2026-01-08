import asyncio
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.getcwd())

from core.database import SessionLocal, engine
from sales.models import Lead, Deal, DealStage, CallTranscript, FollowUpTask
import core.models
from sales.lead_manager import LeadManager
from sales.intelligence import SalesIntelligence
from sales.call_service import CallAutomationService
from core.automation_settings import get_automation_settings

async def test_sales_flow():
    db = SessionLocal()
    workspace_id = "sales-test-ws"
    
    # Create workspace if not exists
    from core.models import Workspace
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        ws = Workspace(id=workspace_id, name="Sales Test Workspace")
        db.add(ws)
        db.commit()
    
    print("\n--- Phase 1: Lead Ingestion & Scoring ---")
    lead_manager = LeadManager(db)
    
    # Test valid lead
    lead1_data = {
        "email": "potential_customer@example.com",
        "first_name": "Alice",
        "company": "GrowthCorp",
        "source": "request_demo"
    }
    lead1 = await lead_manager.ingest_lead(workspace_id, lead1_data)
    print(f"✅ Lead 1 Ingested. Score: {lead1.ai_score}, Status: {lead1.status}")
    
    # Test competitor/spam detection
    lead2_data = {
        "email": "spy@competitor.com",
        "company": "Rival Inc",
        "source": "website"
    }
    lead2 = await lead_manager.ingest_lead(workspace_id, lead2_data)
    print(f"✅ Lead 2 Ingested. Score: {lead2.ai_score}, Status: {lead2.status} (Is Spam: {lead2.is_spam})")

    print("\n--- Phase 2: Deal Intelligence & Health ---")
    # Create a deal
    deal = Deal(
        workspace_id=workspace_id,
        name="GrowthCorp Enterprise Deal",
        value=50000.0,
        stage=DealStage.DISCOVERY,
        probability=0.2
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    
    intelligence = SalesIntelligence(db)
    health = await intelligence.analyze_deal_health(deal)
    print(f"✅ Deal Health Analyzed: Score {health['health_score']}, Risk: {health['risk_level']}")
    print(f"Risks found: {health['risks']}")

    print("\n--- Phase 3: Call Automation & Follow-ups ---")
    call_service = CallAutomationService(db)
    transcript_data = {
        "meeting_id": "zoom_123",
        "title": "Initial Discovery Call",
        "transcript": "Customer is interested but worried about the Q1 rollout. Price seems okay if we include premium support."
    }
    transcript = call_service.process_call_transcript(workspace_id, deal.id, transcript_data)
    print(f"✅ Call Processed. Summary: {transcript.summary}")
    
    # Verify follow-ups
    follow_ups = db.query(FollowUpTask).filter(FollowUpTask.deal_id == deal.id).all()
    print(f"✅ Generated {len(follow_ups)} follow-up tasks.")
    for task in follow_ups:
        print(f"  - Task: {task.description}")

    # Verify engagement update
    db.refresh(deal)
    print(f"✅ Deal Last Engagement updated: {deal.last_engagement_at}")

    print("\nAI Sales Flow Verified!")
    
    # Cleanup
    db.query(FollowUpTask).filter(FollowUpTask.workspace_id == workspace_id).delete()
    db.query(CallTranscript).filter(CallTranscript.workspace_id == workspace_id).delete()
    db.query(Deal).filter(Deal.workspace_id == workspace_id).delete()
    db.query(Lead).filter(Lead.workspace_id == workspace_id).delete()
    db.query(Workspace).filter(Workspace.id == workspace_id).delete()
    db.commit()
    db.close()

if __name__ == "__main__":
    asyncio.run(test_sales_flow())
