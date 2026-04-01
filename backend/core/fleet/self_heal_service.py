import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from core.models import ChainLink, DelegationChain, FleetHealingEvent
from analytics.fleet_optimization_service import FleetOptimizationService

logger = logging.getLogger(__name__)

class SelfHealService:
    """
    Automated recovery service for Agent Fleets (Upstream).
    Monitors chain links and triggers corrective actions (re-recruitment) 
    when failure or critical bottlenecks are detected.
    """

    def __init__(self, db: Session):
        self.db = db
        self.optimization_service = FleetOptimizationService(db)

    async def process_link_update(self, link_id: str):
        """
        Evaluates a link update to determine if healing is required.
        Called by AgentFleetService when a link status changes.
        """
        link = self.db.query(ChainLink).filter(ChainLink.id == link_id).first()
        if not link:
            return

        # 0. Update existing healing event if this link is a retry
        link_metadata = link.context_json or {}
        if link_metadata.get("is_self_heal_retry"):
            healing_event = self.db.query(FleetHealingEvent).filter(
                FleetHealingEvent.retry_link_id == link_id
            ).first()
            if healing_event:
                if link.status in ['completed', 'failed']:
                    healing_event.status = 'succeeded' if link.status == 'completed' else 'failed'
                    self.db.commit()
                    logger.info(f"📈 Self-Heal: Updated healing event {healing_event.id} status to {healing_event.status}")

        # 1. Immediate Heal on Failure
        if link.status == 'failed':
            logger.info(f"🚨 Self-Heal: Detected failure in link {link_id}. Triggering recovery...")
            await self._trigger_recovery(link, reason="Execution Failure")
            return

        # 2. Performance-based Heal (Post-Completion Bottleneck) Logic Parity
        if link.status == 'completed':
            reports = self.optimization_service.analyze_bottlenecks(link.chain_id)
            link_report = next((r for r in reports if r["link_id"] == link_id), None)
            
            if link_report and link_report.get("severity") == "critical":
                domain = link_report.get("domain", "general")
                logger.warning(f"⚠️ Self-Heal: Critical bottleneck detected in link {link_id} ({domain}).")
                await self._trigger_recovery(link, reason=f"Critical Latency Bottleneck ({domain})")

    async def _trigger_recovery(self, original_link: ChainLink, reason: str):
        """
        Triggers a corrective re-recruitment of the same agent with upgraded parameters.
        """
        link_metadata = original_link.context_json or {}
        if link_metadata.get("is_self_heal_retry"):
            logger.info(f"⏭️ Self-Heal: Skipping recovery for {original_link.id} (already a retry).")
            return

        logger.info(f"🛠️ Self-Heal: Re-recruiting agent {original_link.child_agent_id} for chain {original_link.chain_id}")

        from core.agent_fleet_service import AgentFleetService
        fleet_service = AgentFleetService(self.db)

        optimization_overrides = {
            "model": "quality",
            "mentorship_mode": True,
            "max_steps": 12,
            "optimization_reason": f"Self-Heal Recovery: {reason}"
        }

        new_context = original_link.context_json.copy() if original_link.context_json else {}
        new_context["is_self_heal_retry"] = True
        new_context["original_failed_link_id"] = original_link.id

        new_link = fleet_service.recruit_member(
            chain_id=original_link.chain_id,
            parent_agent_id=original_link.parent_agent_id,
            child_agent_id=original_link.child_agent_id,
            task_description=original_link.task_description,
            context_json=new_context,
            link_order=original_link.link_order,
            optimization_metadata=optimization_overrides
        )

        # Record Healing Event
        try:
            # In Upstream, we use original_link.chain.tenant_id
            healing_event = FleetHealingEvent(
                tenant_id=original_link.chain.tenant_id,
                chain_id=original_link.chain_id,
                link_id=original_link.id,
                trigger_type="failed_link" if original_link.status == "failed" else "critical_bottleneck",
                trigger_reason=reason,
                recovery_action="retry_with_quality",
                status="in_progress",
                retry_link_id=new_link.id,
                metadata_json=optimization_overrides
            )
            self.db.add(healing_event)
            self.db.commit()
            logger.info(f"📝 Self-Heal: Recorded healing event {healing_event.id}")
        except Exception as e:
            logger.error(f"❌ Self-Heal: Failed to record healing event: {e}")
            self.db.rollback()

        logger.info(f"✅ Self-Heal: New link {new_link.id} created for recovery.")
