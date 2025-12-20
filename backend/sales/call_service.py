import logging
import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sales.models import Deal, CallTranscript, FollowUpTask
from core.automation_settings import get_automation_settings
from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline, CommunicationAppType

logger = logging.getLogger(__name__)

class CallAutomationService:
    """
    Processes meeting transcripts to extract intelligence and tasks.
    """
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_automation_settings()

    def process_call_transcript(self, workspace_id: str, deal_id: str, transcript_data: Dict[str, Any]) -> CallTranscript:
        """
        Ingest a transcript and trigger AI analysis.
        """
        if not self.settings.is_sales_enabled():
            logger.info("Sales automations disabled. Skipping call processing.")
            return None

        # Create transcript record
        transcript = CallTranscript(
            workspace_id=workspace_id,
            deal_id=deal_id,
            meeting_id=transcript_data.get("meeting_id"),
            title=transcript_data.get("title", "Discovery Call"),
            raw_transcript=transcript_data["transcript"]
        )
        
        # Mock AI Analysis (Summarization, Objection Extraction)
        # In real life, we would pass 'transcript_data["transcript"]' to the LLM
        transcript.summary = f"Summary of {transcript.title}: Discussed pricing and integration requirements. Client expressed concern about rollout timeline."
        transcript.objections = ["Timeline risk", "Pricing"]
        transcript.action_items = [
            "Send updated proposal with phased rollout",
            "Schedule technical deep-dive with engineering"
        ]

        self.db.add(transcript)
        self.db.flush()

        # Update deal engagement
        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        if deal:
            from datetime import datetime, timezone
            deal.last_engagement_at = datetime.now(timezone.utc)
        
        # Trigger Talk-to-Task Conversion
        self._generate_follow_ups(workspace_id, deal_id, transcript.action_items)

        self.db.commit()

        # Ingest into LanceDB Memory
        try:
            from datetime import datetime
            ingestion_pipeline.ingest_message(
                CommunicationAppType.CALLS.value,
                {
                    "id": transcript.id,
                    "timestamp": datetime.now().isoformat(),
                    "sender": "Meeting Transcript",
                    "subject": transcript.title,
                    "content": f"Meeting: {transcript.title}. Summary: {transcript.summary}. Action Items: {', '.join(transcript.action_items)}",
                    "metadata": {
                        "transcript_id": transcript.id,
                        "deal_id": deal_id,
                        "workspace_id": workspace_id,
                        "objections": transcript.objections,
                        "meeting_id": transcript.meeting_id
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to ingest transcript into LanceDB: {e}")

        return transcript

    def _generate_follow_ups(self, workspace_id: str, deal_id: str, action_items: List[str]):
        """
        Convert action items into FollowUpTask objects.
        """
        for item in action_items:
            task = FollowUpTask(
                workspace_id=workspace_id,
                deal_id=deal_id,
                description=item,
                ai_rationale="Extracted from discovery call transcript."
            )
            self.db.add(task)
        
        logger.info(f"Generated {len(action_items)} follow-up tasks for deal {deal_id}.")
