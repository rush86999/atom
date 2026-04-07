"""
Domain Marketplace Service (Upstream Client)

Handles discovery and installation of specialist domains from the Atom Agent OS Marketplace.
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.atom_saas_client import AtomAgentOSMarketplaceClient
from core.models import SpecialistDomain
from core.marketplace_usage_tracker import MarketplaceUsageTracker

logger = logging.getLogger(__name__)


class DomainMarketplaceService:
    """
    Client-side service for managing marketplace domains in a self-hosted instance.
    """

    def __init__(self, db: Session, saas_client: Optional[AtomAgentOSMarketplaceClient] = None):
        self.db = db
        self.saas_client = saas_client or AtomAgentOSMarketplaceClient()

    def browse_domains(
        self, 
        query: str = "", 
        category: Optional[str] = None, 
        page: int = 1, 
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Browse specialist domains available in the Atom SaaS Marketplace.
        """
        try:
            return self.saas_client.fetch_domains_sync(
                query=query, 
                category=category, 
                page=page, 
                page_size=page_size
            )
        except Exception as e:
            logger.error(f"Failed to fetch domains from Atom SaaS: {e}")
            return {"domains": [], "total": 0, "error": str(e)}

    def install_domain(
        self, 
        template_domain_id: str, 
        tenant_id: str, 
        custom_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Install a domain template from the marketplace.
        """
        # 1. Fetch template from SaaS
        template = self.saas_client.get_domain_template_sync(template_domain_id)
        if not template:
            return {"success": False, "error": "Domain template not found in marketplace"}

        try:
            # 2. Create local Domain record
            new_domain = SpecialistDomain(
                tenant_id=tenant_id,
                domain_name=custom_name or template["domain_name"],
                domain_slug=f"{(custom_name or template['domain_name']).lower().replace(' ', '_')}_{tenant_id[:8]}",
                description=template.get("description"),
                is_public=False,  # Locally installed domains are private
                parent_domain_id=template_domain_id
            )
            self.db.add(new_domain)

            # 3. Notify SaaS of installation
            self.saas_client.install_domain_sync(template_domain_id, tenant_id)

            # 4. Track usage locally
            MarketplaceUsageTracker.track_usage(
                item_type="domain",
                item_id=template_domain_id,
                success=True
            )

            self.db.commit()
            logger.info(f"Installed domain template {template_domain_id} for tenant {tenant_id}")

            return {
                "success": True,
                "domain_id": new_domain.id,
                "domain_name": new_domain.domain_name
            }

        except Exception as e:
            logger.error(f"Failed to install domain {template_domain_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def uninstall_domain(self, domain_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Uninstall a domain that was installed from the marketplace.
        """
        try:
            domain = self.db.query(SpecialistDomain).filter(
                and_(
                    SpecialistDomain.id == domain_id,
                    SpecialistDomain.tenant_id == tenant_id,
                    SpecialistDomain.is_public == False
                )
            ).first()

            if not domain:
                return {"success": False, "error": "Installed domain not found"}

            template_id = domain.parent_domain_id
            self.db.delete(domain)
            self.db.commit()

            logger.info(f"Uninstalled domain {domain_id} (Template: {template_id})")
            return {"success": True, "message": "Domain uninstalled successfully"}

        except Exception as e:
            logger.error(f"Failed to uninstall domain {domain_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
