"""
Canvas Component Marketplace Service (Upstream Client)

Handles discovery and installation of canvas components from the Atom Agent OS Marketplace.
Provides proxy logic to the commercial atomagentos.com mothership.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.atom_saas_client import AtomAgentOSMarketplaceClient
from core.models import CanvasComponent, ComponentInstallation
from core.marketplace_usage_tracker import MarketplaceUsageTracker

logger = logging.getLogger(__name__)


class CanvasMarketplaceService:
    """
    Client-side service for managing marketplace canvas components in a self-hosted instance.
    """

    def __init__(self, db: Session, saas_client: Optional[AtomAgentOSMarketplaceClient] = None):
        self.db = db
        self.saas_client = saas_client or AtomAgentOSMarketplaceClient()

    def browse_components(
        self,
        query: str = "",
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Browse canvas components available in the Atom SaaS Marketplace.
        """
        try:
            return self.saas_client.fetch_components_sync(
                query=query,
                category=category,
                page=page,
                page_size=page_size
            )
        except Exception as e:
            logger.error(f"Failed to fetch components from Atom SaaS: {e}")
            return {"components": [], "total": 0, "error": str(e)}

    def get_component_details(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed component information from the marketplace.
        """
        try:
            return self.saas_client.get_component_details_sync(component_id)
        except Exception as e:
            logger.error(f"Failed to fetch component details for {component_id}: {e}")
            return None

    def install_component(
        self,
        component_id: str,
        canvas_id: str,
        tenant_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Install a canvas component from the marketplace.
        """
        # 1. Fetch component metadata from SaaS
        metadata = self.saas_client.get_component_details_sync(component_id)
        if not metadata:
            return {"success": False, "error": "Component not found in marketplace"}

        try:
            # 2. Check if component already exists locally, otherwise create it
            local_comp = self.db.query(CanvasComponent).filter(CanvasComponent.id == component_id).first()
            if not local_comp:
                local_comp = CanvasComponent(
                    id=component_id,
                    tenant_id=None,  # Marketplace components are system-level
                    author_id=metadata.get("author_id", "system"),
                    name=metadata["name"],
                    description=metadata.get("description"),
                    category=metadata["category"],
                    component_type=metadata["component_type"],
                    code=metadata["code"],
                    config_schema=metadata.get("config_schema"),
                    preview_url=metadata.get("preview_url"),
                    version=metadata.get("version", "1.0.0"),
                    is_public=True,
                    is_approved=True,
                    license=metadata.get("license", "Proprietary"),
                    dependencies=metadata.get("dependencies"),
                    css_dependencies=metadata.get("css_dependencies")
                )
                self.db.add(local_comp)

            # 3. Create component installation record
            installation = ComponentInstallation(
                tenant_id=tenant_id,
                canvas_id=canvas_id,
                component_id=component_id,
                config=config or metadata.get("default_config")
            )
            self.db.add(installation)

            # 4. Notify SaaS of installation (Commercial requirement)
            self.saas_client.install_component_sync(component_id, canvas_id)

            # 5. Track usage locally for analytics push
            MarketplaceUsageTracker.track_usage(
                item_type="canvas_component",
                item_id=component_id,
                success=True
            )

            self.db.commit()
            logger.info(f"Installed marketplace component {component_id} for canvas {canvas_id}")

            return {
                "success": True,
                "installation_id": installation.id,
                "component_name": local_comp.name
            }

        except Exception as e:
            logger.error(f"Failed to install component {component_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def uninstall_component(self, installation_id: str, tenant_id: str) -> Dict[str, Any]:
        """
        Uninstall a component from a canvas.
        """
        try:
            installation = self.db.query(ComponentInstallation).filter(
                and_(
                    ComponentInstallation.id == installation_id,
                    ComponentInstallation.tenant_id == tenant_id
                )
            ).first()

            if not installation:
                return {"success": False, "error": "Installation not found"}

            component_id = installation.component_id
            self.db.delete(installation)

            # Note: We keep the CanvasComponent record itself in case other canvases use it
            
            self.db.commit()
            logger.info(f"Uninstalled component installation {installation_id}")

            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to uninstall component installation {installation_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
