import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sales.models import Lead, LeadStatus
from core.automation_settings import get_automation_settings
from core.websockets import manager

logger = logging.getLogger(__name__)

try:
    from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline, CommunicationAppType
    INGESTION_AVAILABLE = True
except ImportError:
    INGESTION_AVAILABLE = False
    logger.warning("Ingestion pipeline not available. Sales memory will be disabled.")

class LeadManager:
    """
    Handles lead ingestion, qualification, and AI scoring.
    """
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_automation_settings()

    async def ingest_lead(self, workspace_id: str, lead_data: Dict[str, Any]) -> Lead:
        """
        Normalize and ingest a lead from any source.
        """
        if not self.settings.is_sales_enabled():
            logger.info("Sales automations are disabled. Skipping lead ingestion.")
            return None

        # Check for duplicate
        existing = self.db.query(Lead).filter(
            Lead.workspace_id == workspace_id,
            Lead.email == lead_data["email"]
        ).first()

        if existing:
            logger.info(f"Lead {lead_data['email']} already exists. Updating...")
            for key, value in lead_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            return existing

        lead = Lead(
            workspace_id=workspace_id,
            email=lead_data["email"],
            first_name=lead_data.get("first_name"),
            last_name=lead_data.get("last_name"),
            company=lead_data.get("company"),
            source=lead_data.get("source"),
            status=LeadStatus.NEW,
            metadata_json=lead_data.get("metadata", {})
        )

        self.db.add(lead)
        self.db.flush()

        # Trigger AI Scoring
        await self.score_lead(lead)

        return lead

    async def score_lead(self, lead: Lead):
        """
        Use AI to score the lead and detect spam/competitors.
        """
        # In a real implementation, this would call an LLM with lead context
        # For now, we'll implement a rule-based mock that simulates AI behavior
        
        email_domain = lead.email.split("@")[-1].lower()
        competitor_domains = ["competitor.com", "rival.io"]
        disposable_domains = ["mailinator.com", "tempmail.com"]

        score = 50.0 # Base score
        
        if email_domain in competitor_domains:
            lead.is_spam = True
            lead.status = LeadStatus.SPAM
            lead.ai_qualification_summary = "Detected as competitor research."
            score = 0.0
        elif email_domain in disposable_domains:
            lead.is_spam = True
            lead.ai_qualification_summary = "Disposable email address used."
            score = 10.0
        else:
            # Simulate positive signals
            if lead.company:
                score += 20.0
            if lead.source == "request_demo":
                score += 20.0
            
            lead.ai_qualification_summary = f"High intent lead from {lead.source}."

        lead.ai_score = score
        self.db.commit()
        logger.info(f"Scored lead {lead.email}: {score}")

        # Broadcast update
        try:
            await manager.broadcast(f"workspace:{lead.workspace_id}", {
                "type": "new_lead",
                "workspace_id": lead.workspace_id,
                "data": {
                    "id": lead.id,
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "company": lead.company,
                    "ai_score": lead.ai_score,
                    "status": lead.status.value,
                    "summary": lead.ai_qualification_summary
                }
            })
        except Exception as e:
            logger.error(f"Failed to broadcast lead update: {e}")

        # Ingest into LanceDB Memory
        if INGESTION_AVAILABLE:
            try:
                from datetime import datetime
                ingestion_pipeline.ingest_message(
                    CommunicationAppType.CRM_LEAD.value,
                    {
                        "id": lead.id,
                        "timestamp": datetime.now().isoformat(),
                        "sender": lead.email,
                        "content": f"New Lead: {lead.first_name or ''} {lead.last_name or ''} from {lead.company or 'Unknown'}. Source: {lead.source}. AI Score: {lead.ai_score}. Summary: {lead.ai_qualification_summary}",
                        "metadata": {
                            "lead_id": lead.id,
                            "workspace_id": lead.workspace_id,
                            "company": lead.company,
                            "ai_score": lead.ai_score,
                            "status": lead.status.value
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Failed to ingest lead into LanceDB: {e}")
