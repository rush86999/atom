import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from core.models import DelegationChain, ChainLink, AgentRegistry

logger = logging.getLogger(__name__)

class AgentFleetService:
    """
    Service for orchestrating multi-agent fleets (Admiralty model).
    Manages delegation chains, recruitment, and shared blackboard context.
    """

    def __init__(self, db: Session):
        self.db = db

    def initialize_fleet(
        self,
        tenant_id: str,
        root_agent_id: str,
        root_task: str,
        root_execution_id: Optional[str] = None,
        initial_metadata: Optional[Dict[str, Any]] = None
    ) -> DelegationChain:
        """
        Initializes a new delegation chain (a fleet root).
        """
        logger.info(f"Initializing fleet for root agent {root_agent_id}, task: {root_task[:50]}...")
        
        chain = DelegationChain(
            tenant_id=tenant_id,
            root_agent_id=root_agent_id,
            root_task=root_task,
            root_execution_id=root_execution_id,
            status="active",
            metadata_json=initial_metadata or {},
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(chain)
        self.db.commit()
        self.db.refresh(chain)
        
        return chain

    def recruit_member(
        self,
        chain_id: str,
        parent_agent_id: str,
        child_agent_id: str,
        task_description: str,
        context_json: Optional[Dict[str, Any]] = None,
        link_order: int = 0,
        optimization_metadata: Optional[Dict[str, Any]] = None
    ) -> ChainLink:
        """
        Adds a new specialized agent to an active fleet.
        """
        logger.info(f"Recruiting fleet member {child_agent_id} for chain {chain_id}")
        
        # Merge optimization data into context
        final_context = context_json or {}
        if optimization_metadata:
            final_context["optimization"] = optimization_metadata

        link = ChainLink(
            chain_id=chain_id,
            parent_agent_id=parent_agent_id,
            child_agent_id=child_agent_id,
            task_description=task_description,
            context_json=final_context,
            status="pending",
            link_order=link_order,
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(link)
        
        # Increment total links in chain
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        if chain:
            chain.total_links += 1
            
        self.db.commit()
        self.db.refresh(link)
        
        return link

    def update_blackboard(self, chain_id: str, updates: Dict[str, Any]):
        """
        Updates the shared fleet context (blackboard).
        """
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        if not chain:
            logger.error(f"Cannot update blackboard: Chain {chain_id} not found")
            return

        current_metadata = chain.metadata_json or {}
        current_metadata.update(updates)
        chain.metadata_json = current_metadata
        
        self.db.commit()
        logger.info(f"Updated blackboard for chain {chain_id}")

    def get_blackboard(self, chain_id: str) -> Dict[str, Any]:
        """
        Retrieves the shared fleet context.
        """
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        return chain.metadata_json if chain else {}

    def update_link_status(
        self, 
        link_id: str, 
        status: str, 
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Updates the status and result of a specific delegation link.
        """
        link = self.db.query(ChainLink).filter(ChainLink.id == link_id).first()
        if not link:
            logger.error(f"Link {link_id} not found")
            return

        link.status = status
        if result is not None:
            link.result_json = result
        if error is not None:
            link.error_message = error
            
        if status in ["completed", "failed"]:
            link.completed_at = datetime.now(timezone.utc)
            if link.started_at:
                delta = link.completed_at - link.started_at
                link.duration_ms = int(delta.total_seconds() * 1000)

        self.db.commit()
        logger.info(f"Link {link_id} updated to {status}")

        # Trigger Self-Healing (Async)
        if status in ["completed", "failed"]:
            try:
                from core.fleet.self_heal_service import SelfHealService
                import asyncio
                
                self_heal = SelfHealService(self.db)
                # In Upstream, we also use background tasks to ensure low latency for the orchestrator
                asyncio.create_task(self_heal.process_link_update(link_id))
            except Exception as e:
                logger.error(f"⚠️ Self-Heal Trigger Failed: {e}")

    def complete_chain(self, chain_id: str, status: str = "completed"):
        """
        Marks a delegation chain as finished.
        """
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        if not chain:
            return

        chain.status = status
        chain.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info(f"Chain {chain_id} finalized with status: {status}")
