import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from core.database import get_db_session
from sales.models import Deal
from service_delivery.models import Contract, Project, ContractType, ProjectStatus
from core.pm_engine import pm_engine
from core.graphrag_engine import graphrag_engine
from core.external_pm_sync import external_pm_sync

logger = logging.getLogger(__name__)

class PMOrchestrator:
    """
    Orchestrates the transition from Sales (Deals) to Delivery (Contracts/Projects).
    """

    async def provision_from_deal(self, deal_id: str, user_id: str, workspace_id: str = "default", external_platform: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a Contract and launches an AI-managed Project from a Closed Won Deal.
        """
        logger.info(f"Provisioning delivery for deal {deal_id}")
        
        with get_db_session() as db:
            # 1. Fetch Deal
            deal = db.query(Deal).filter(Deal.id == deal_id).first()
            if not deal:
                return {"status": "error", "message": "Deal not found"}
            
            # 2. Create Contract
            contract = Contract(
                id=f"cnt_{uuid.uuid4().hex[:8]}",
                workspace_id="default",
                deal_id=deal_id,
                name=f"Contract for {deal.name}",
                total_amount=deal.value,
                currency=deal.currency,
                type=ContractType.FIXED_FEE, # Default for auto-provisioning
                start_date=datetime.now()
            )
            db.add(contract)
            db.flush()
            
            # 3. Launch AI Project
            # Use deal name and value as context for the PM engine
            prompt = f"Create a project plan for deal '{deal.name}' with a value of {deal.value} {deal.currency}. Decompose into milestones based on the name."
            
            pm_result = await pm_engine.generate_project_from_nl(
                prompt=prompt,
                user_id=user_id,
                workspace_id="default",
                contract_id=contract.id
            )
            
            if pm_result["status"] != "success":
                db.rollback()
                return {"status": "error", "message": f"Project generation failed: {pm_result.get('error')}"}
            
            project_id = pm_result["project_id"]
            
            # 4. Identify Stakeholders using GraphRAG
            stakeholders = await self._identify_stakeholders(deal.name, user_id)
            
            # 5. Optional External Sync (Phase 45)
            sync_details = None
            if external_platform:
                sync_details = await external_pm_sync.sync_project_to_external(
                    project_id=project_id,
                    platform=external_platform,
                    workspace_id="default"
                )

            db.commit()
            
            logger.info(f"Successfully provisioned project {project_id} from deal {deal_id}")
            return {
                "status": "success",
                "contract_id": contract.id,
                "project_id": project_id,
                "project_name": pm_result["name"],
                "stakeholders_identified": stakeholders,
                "external_sync": sync_details
            }

    async def _identify_stakeholders(self, context_name: str, user_id: str) -> List[str]:
        """
        Uses GraphRAG to find people associated with the deal context.
        """
        try:
            query = f"Who are the key stakeholders or points of contact for '{context_name}'?"
            # Use local search for entity-specific reasoning
            rag_result = graphrag_engine.query(user_id, query, mode="local")
            
            # Extract names from entities found
            entities = rag_result.get("entities", [])
            stakeholders = [e["name"] for e in entities if e.get("type") in ["person", "contact", "user"]]
            
            return stakeholders
        except Exception as e:
            logger.warning(f"Failed to identify stakeholders via GraphRAG: {e}")
            return []

    async def notify_startup(self, project_id: str, stakeholders: List[str]):
        """
        Placeholder for sending welcome/kickoff notifications.
        """
        for sh in stakeholders:
            logger.info(f"NOTIFY: Project {project_id} launched. Welcome {sh}!")

# Global Instance
pm_orchestrator = PMOrchestrator()
