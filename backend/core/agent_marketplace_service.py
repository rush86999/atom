"""
Agent Marketplace Service (Upstream Client)

Handles discovery and installation of agents from the Atom Agent OS Marketplace.
Syncs with the SaaS backend and records local installation metadata.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.atom_saas_client import AtomAgentOSMarketplaceClient
from core.models import (
    AgentRegistry, 
    AgentTemplate, 
    AgentInstallation, 
    OperationErrorResolution, 
    AgentSkill,
    Tenant
)
from core.marketplace_usage_tracker import MarketplaceUsageTracker

logger = logging.getLogger(__name__)


class AgentMarketplaceService:
    """
    Client-side service for managing marketplace agents in a self-hosted instance.
    Communicates with Atom SaaS to fetch templates and report installations.
    """

    def __init__(self, db: Session, saas_client: Optional[AtomAgentOSMarketplaceClient] = None):
        self.db = db
        self.saas_client = saas_client or AtomAgentOSMarketplaceClient()

    def browse_agents(
        self, 
        query: str = "", 
        category: Optional[str] = None, 
        page: int = 1, 
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Browse public agents available in the Atom SaaS Marketplace.
        """
        try:
            logger.info(f"Browsing marketplace agents: query={query}, category={category}")
            result = self.saas_client.fetch_agents_sync(
                query=query, 
                category=category, 
                page=page, 
                page_size=page_size
            )
            return result
        except Exception as e:
            logger.error(f"Failed to fetch agents from Atom SaaS: {e}")
            return {
                "agents": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "source": "error",
                "error": str(e)
            }

    def get_template_details(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full details for an agent template from the SaaS marketplace.
        """
        try:
            return self.saas_client.get_agent_template_sync(template_id)
        except Exception as e:
            logger.error(f"Failed to fetch template details for {template_id}: {e}")
            return None

    def install_agent(self, template_id: str, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """
        Install an agent from the marketplace.
        1. Fetches template data from SaaS.
        2. Creates local AgentRegistry record.
        3. Pre-loads anonymized experience memory.
        4. Connects required skills.
        5. Records installation locally and with SaaS.
        """
        # 1. Fetch template from SaaS
        template_data = self.get_template_details(template_id)
        if not template_data:
            return {"success": False, "error": "Agent template not found in marketplace"}

        try:
            # 2. Instantiate local Agent
            new_agent = AgentRegistry(
                name=template_data["name"],
                display_name=f"{template_data['name']} (Marketplace)",
                description=template_data["description"],
                category=template_data.get("category", "General"),
                role="agent",
                type="marketplace",
                user_id=user_id,
                tenant_id=tenant_id,
                status="intern",  # Marketplace agents start as internship level
                configuration=template_data.get("configuration", {}),
            )
            self.db.add(new_agent)
            self.db.flush()

            # 3. Pre-load accelerated learning memory
            memory_bundle = template_data.get("anonymized_memory_bundle", {})
            heuristics = memory_bundle.get("heuristics", [])
            
            for heuristic in heuristics:
                new_res = OperationErrorResolution(
                    tenant_id=tenant_id,
                    error_type=heuristic.get("error_type"),
                    error_code=heuristic.get("error_code"),
                    resolution_attempted=heuristic.get("resolution"),
                    success=True,
                    user_feedback="Pre-loaded from Marketplace",
                    resolution_metadata={
                        "source_template_id": template_id,
                        "imported_at": uuid.uuid4().hex
                    }
                )
                self.db.add(new_res)

            # 4. Connect skills (if they exist locally)
            capabilities = template_data.get("capabilities", [])
            for skill_id in capabilities:
                # Note: In a real scenario, we might need to install missing skills first
                agent_skill = AgentSkill(
                    agent_id=new_agent.id,
                    skill_id=skill_id,
                    enabled=True
                )
                self.db.add(agent_skill)

            # 5. Create local installation record
            installation = AgentInstallation(
                tenant_id=tenant_id,
                template_id=template_id,
                instantiated_agent_id=new_agent.id,
                installed_version=template_data.get("version", "1.0.0"),
                is_active=True
            )
            self.db.add(installation)

            # 6. Notify SaaS of installation (for stats)
            self.saas_client.install_agent_sync(template_id, tenant_id)

            # 7. Track usage locally
            MarketplaceUsageTracker.track_usage(
                item_type="agent",
                item_id=template_id,
                success=True
            )

            self.db.commit()
            logger.info(f"Successfully installed marketplace agent {template_id} as local agent {new_agent.id}")

            return {
                "success": True,
                "agent_id": new_agent.id,
                "message": f"Installed {template_data['name']} successfully"
            }

        except Exception as e:
            logger.error(f"Failed to install marketplace agent {template_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def uninstall_agent(self, tenant_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Uninstall a marketplace agent.
        Removes the agent registry, installation record, and linked memory.
        """
        try:
            # 1. Find installation
            installation = self.db.query(AgentInstallation).filter(
                and_(
                    AgentInstallation.tenant_id == tenant_id,
                    AgentInstallation.instantiated_agent_id == agent_id
                )
            ).first()

            if not installation:
                return {"success": False, "error": "Agent was not installed from marketplace"}

            template_id = installation.template_id

            # 2. Cleanup linked memory
            self.db.query(OperationErrorResolution).filter(
                and_(
                    OperationErrorResolution.tenant_id == tenant_id,
                    OperationErrorResolution.resolution_metadata["source_template_id"].astext == template_id
                )
            ).delete(synchronize_session=False)

            # 3. Cleanup skills
            self.db.query(AgentSkill).filter(AgentSkill.agent_id == agent_id).delete()

            # 4. Remove installation and agent
            self.db.delete(installation)
            
            agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            if agent:
                self.db.delete(agent)

            self.db.commit()
            logger.info(f"Uninstalled marketplace agent {agent_id} (Template: {template_id})")

            return {"success": True, "message": "Agent uninstalled successfully"}

        except Exception as e:
            logger.error(f"Failed to uninstall agent {agent_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
