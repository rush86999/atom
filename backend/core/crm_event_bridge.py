import logging
import asyncio
from typing import List
from core.database import SessionLocal
from sales.models import Deal, DealStage
from core.pm_orchestrator import pm_orchestrator

logger = logging.getLogger(__name__)

class CRMEventBridge:
    """
    Monitors CRM activities and triggers delivery workflows.
    """
    
    def __init__(self):
        self.running = False
        self._processed_deals = set() # Simple in-memory de-duplication for MVP

    async def check_for_closed_won_deals(self, user_id: str, workspace_id: str):
        """
        Scans for deals that have moved to CLOSED_WON and haven't been provisioned yet.
        """
        logger.info("Scanning for newly CLOSED_WON deals...")
        
        try:
            with SessionLocal() as db:
                # Find deals that are CLOSED_WON
                new_deals = db.query(Deal).filter(
                    Deal.stage == DealStage.CLOSED_WON
                ).all()
                
                for deal in new_deals:
                    if deal.id not in self._processed_deals:
                        logger.info(f"Detected newly won deal: {deal.name} ({deal.id})")
                        
                        # Trigger Provisioning
                        result = await pm_orchestrator.provision_from_deal(
                            deal_id=deal.id,
                            user_id=user_id,
                            workspace_id=workspace_id
                        )
                        
                        if result["status"] == "success":
                            self._processed_deals.add(deal.id)
                            # Optional: Send notification
                            await pm_orchestrator.notify_startup(
                                project_id=result["project_id"],
                                stakeholders=result.get("stakeholders_identified", [])
                            )
                        else:
                            logger.error(f"Failed to auto-provision deal {deal.id}: {result.get('message')}")
                            
        except Exception as e:
            logger.error(f"Error in CRM event bridge: {e}")

    async def start_polling(self, user_id: str, workspace_id: str, interval_seconds: int = 60):
        """
        Background polling loop for CRM events.
        """
        self.running = True
        while self.running:
            await self.check_for_closed_won_deals(user_id, workspace_id)
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self.running = False

# Global Instance
crm_event_bridge = CRMEventBridge()
