import asyncio
from datetime import datetime, timedelta, timezone
import logging
from sales.models import CallTranscript, Deal, DealStage, Lead, LeadStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import DATABASE_URL, Base
from core.models import Workspace

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def seed_data():
    db = SessionLocal()
    try:
        # 1. Ensure Workspace exists
        workspace_id = "temp_ws"
        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            workspace = Workspace(id=workspace_id, name="Demo Sales Workspace")
            db.add(workspace)
            db.commit()
            logger.info(f"Created workspace: {workspace_id}")

        # 2. Seed Leads
        leads_data = [
            {
                "email": "ceo@growthcorp.com",
                "first_name": "Sarah",
                "last_name": "Johnson",
                "company": "GrowthCorp",
                "source": "request_demo",
                "status": LeadStatus.NEW,
                "ai_score": 92.0,
                "ai_qualification_summary": "High intent lead from target sector. Company recently raised Series B."
            },
            {
                "email": "marketing@startup.io",
                "first_name": "Mike",
                "last_name": "Chen",
                "company": "StartupIO",
                "source": "newsletter",
                "status": LeadStatus.CONTACTED,
                "ai_score": 65.0,
                "ai_qualification_summary": "Good fit, but early stage. Follow up in 2 weeks."
            },
            {
                "email": "competitor@rival.com",
                "first_name": "Jack",
                "last_name": "Splatt",
                "company": "Rival Corp",
                "source": "direct",
                "status": LeadStatus.SPAM,
                "is_spam": True,
                "ai_score": 0.0,
                "ai_qualification_summary": "Detected as competitor research."
            }
        ]

        for ld in leads_data:
            existing = db.query(Lead).filter(Lead.email == ld["email"]).first()
            if not existing:
                lead = Lead(workspace_id=workspace_id, **ld)
                db.add(lead)
                logger.info(f"Added lead: {ld['email']}")

        # 3. Seed Deals
        deals_data = [
            {
                "name": "Enterprise License - GrowthCorp",
                "value": 120000.0,
                "stage": DealStage.NEGOTIATION,
                "health_score": 85.0,
                "risk_level": "low"
            },
            {
                "name": "Global Rollout - TechSystems",
                "value": 250000.0,
                "stage": DealStage.PROPOSAL,
                "health_score": 35.0,
                "risk_level": "high"
            }
        ]

        for dd in deals_data:
            existing = db.query(Deal).filter(Deal.name == dd["name"]).first()
            if not existing:
                deal = Deal(workspace_id=workspace_id, **dd)
                db.add(deal)
                db.flush()
                
                # Add a call transcript for each deal
                transcript = CallTranscript(
                    workspace_id=workspace_id,
                    deal_id=deal.id,
                    title=f"Discovery Call - {deal.name}",
                    raw_transcript="Discussing the rollout and pricing structures.",
                    summary=f"Summary for {deal.name}: Stakeholders approved value prop. Focus on security next.",
                    objections=["Pricing", "Rollout Timeline"],
                    action_items=["Send proposal", "Schedule tech deep-dive"]
                )
                db.add(transcript)
                logger.info(f"Added deal and transcript: {dd['name']}")

        db.commit()
        logger.info("Database seeding complete!")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
