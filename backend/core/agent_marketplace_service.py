"""
Agent Marketplace Service (Upstream Client)

Handles discovery and installation of agents from the Atom Agent OS Marketplace.
Syncs with the SaaS backend and records local installation metadata.

MANAGED-AGENT MODEL (IP protection): installed agents store a *reference*
configuration (template_id/version/tunables) — never the publisher's prompts
or experience memory. Those live in the AgentTemplate manifest (local row for
local publishes; server-side on the SaaS for marketplace installs) and are
resolved at execution time by ``core.marketplace_runtime``.
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
    Skill,
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

    def publish_agent(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish an agent to the marketplace, stripping credentials.

        P5 Blueprint Security: sharing never leaks credentials. The published
        payload is run through ``strip_credentials`` so any nested secret keys
        (api_key / access_token / refresh_token / secret / password) are
        removed before the agent is shared with other tenants.

        Args:
            template_data: The agent payload to publish (configuration,
                capabilities, canvas UI schemas, etc.).

        Returns:
            A deep copy of ``template_data`` with credential keys removed —
            suitable for publishing to the marketplace.
        """
        from core.blueprint_sanitizer import strip_credentials
        return strip_credentials(template_data)

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
        The SaaS serves the LISTING only — configuration and memory stay
        server-side under the managed-agent model.
        """
        try:
            return self.saas_client.get_agent_template_sync(template_id)
        except Exception as e:
            logger.error(f"Failed to fetch template details for {template_id}: {e}")
            return None

    def install_agent(self, template_id: str, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """
        Install an agent from the marketplace as a MANAGED agent.

        1. Fetches listing data from SaaS.
        2. If the payload carries manifest data (local publish / legacy
           backend), upserts a local AgentTemplate manifest row.
        3. Creates a local AgentRegistry record whose configuration is a
           reference — prompts/memory are resolved at execution time.
        4. Connects skills that exist locally (never dangling links).
        5. Records installation locally and with SaaS.
        """
        # 1. Fetch listing from SaaS
        template_data = self.get_template_details(template_id)
        if not template_data:
            return {"success": False, "error": "Agent template not found in marketplace"}

        try:
            # 2. Local manifest (only when the payload actually carries one)
            payload_config = template_data.get("configuration") or {}
            memory_bundle = template_data.get("anonymized_memory_bundle") or {}
            if payload_config or memory_bundle:
                local_template = (
                    self.db.query(AgentTemplate)
                    .filter(AgentTemplate.id == template_id)
                    .first()
                )
                if local_template:
                    if payload_config:
                        local_template.configuration = payload_config
                    if memory_bundle:
                        local_template.anonymized_memory_bundle = memory_bundle
                    local_template.is_active = True
                else:
                    local_template = AgentTemplate(
                        id=template_id,
                        tenant_id=None,
                        author_id=None,
                        name=str(template_data.get("name", ""))[:100],
                        description=str(template_data.get("description", ""))[:500],
                        category=template_data.get("category", "General"),
                        version=template_data.get("version", "1.0.0"),
                        price=template_data.get("price", 0.0),
                        configuration=payload_config,
                        capabilities=template_data.get("capabilities", []),
                        canvas_ui_schemas=template_data.get("canvas_ui_schemas", []),
                        anonymized_memory_bundle=memory_bundle,
                        tunable_keys=template_data.get("tunable_keys", []),
                        permission_profile=template_data.get("permission_profile", {}),
                        is_public=True,
                        is_approved=True,
                        is_active=True,
                    )
                    self.db.add(local_template)

            # 3. Instantiate local MANAGED agent — configuration is a
            # reference, not a copy of the manifest.
            # #10 fix: validate/truncate remote data before writing to
            # fixed-width VARCHAR columns (name=String(100), description=String(500)).
            _name = str(template_data.get("name", ""))[:100]
            _desc = str(template_data.get("description", ""))[:500]
            _display = f"{_name} (Marketplace)"[:100]
            _version = template_data.get("version", "1.0.0")
            new_agent = AgentRegistry(
                name=_name,
                display_name=_display,
                description=_desc,
                category=template_data.get("category", "General"),
                role="agent",
                type="marketplace",
                # module_path/class_name are NOT NULL columns — omitting them
                # made every install fail with IntegrityError on a real DB
                # (mock-session tests masked it). Marketplace agents run the
                # generic agent, mirroring atom_meta_agent's convention.
                module_path="core.generic_agent",
                class_name="GenericAgent",
                user_id=user_id,
                tenant_id=tenant_id,
                status="intern",  # Marketplace agents start as internship level
                configuration={
                    "marketplace_managed": True,
                    "template_id": str(template_id),
                    "managed_version": _version,
                    "capabilities": [],
                    "tunables": {},
                },
            )
            self.db.add(new_agent)
            self.db.flush()

            # 4. Connect skills that exist locally — dangling AgentSkill
            # links 500 the skills API, so missing ones are skipped.
            warnings: List[str] = []
            linked_names: List[str] = []
            for skill_id in template_data.get("capabilities", []):
                skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
                if not skill:
                    warnings.append(f"Skill {skill_id} not available locally; skipped")
                    continue
                agent_skill = AgentSkill(
                    agent_id=new_agent.id,
                    skill_id=skill_id,
                    enabled=True
                )
                self.db.add(agent_skill)
                linked_names.append(getattr(skill, "name", None) or str(skill_id))

            config = new_agent.configuration
            config["capabilities"] = linked_names
            new_agent.configuration = config

            # 5. Create local installation record
            installation = AgentInstallation(
                tenant_id=tenant_id,
                template_id=template_id,
                instantiated_agent_id=new_agent.id,
                installed_version=_version,
                is_active=True,
                last_synced_version=_version,
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
            logger.info(f"Successfully installed marketplace agent {template_id} as managed agent {new_agent.id}")

            result = {
                "success": True,
                "agent_id": new_agent.id,
                "managed": True,
                "message": f"Installed {template_data['name']} successfully",
            }
            if warnings:
                result["skill_warnings"] = warnings
            return result

        except Exception as e:
            logger.error(f"Failed to install marketplace agent {template_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def uninstall_agent(self, tenant_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Uninstall a marketplace agent.
        Removes the agent registry and installation record. Legacy installs
        (pre-managed model) also drop their pre-loaded memory rows.
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

            # 2. Cleanup linked memory — only for LEGACY installs; managed
            # agents never had memory copied into tenant tables.
            agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            config = (agent.configuration if agent else None) or {}
            if not config.get("marketplace_managed"):
                # SQLite (default Personal Edition DB) does not support the
                # PostgreSQL-only `.astext` on JSON index access — it raised
                # AttributeError on every uninstall. The plain JSON index op
                # compiles to json_extract() on SQLite and works everywhere.
                self.db.query(OperationErrorResolution).filter(
                    and_(
                        OperationErrorResolution.tenant_id == tenant_id,
                        OperationErrorResolution.resolution_metadata["source_template_id"] == template_id
                    )
                ).delete(synchronize_session=False)

            # 3. Cleanup skills
            self.db.query(AgentSkill).filter(AgentSkill.agent_id == agent_id).delete()

            # 4. Remove installation and agent
            self.db.delete(installation)

            if agent:
                self.db.delete(agent)

            self.db.commit()
            logger.info(f"Uninstalled marketplace agent {agent_id} (Template: {template_id})")

            return {"success": True, "message": "Agent uninstalled successfully"}

        except Exception as e:
            logger.error(f"Failed to uninstall agent {agent_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
