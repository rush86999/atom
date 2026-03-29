"""
Integration Catalog Service

Provides admin users with tools to browse integrations by search,
category, and manage tenant-level configuration.

CRITICAL: All methods use tenant_id parameter for multi-tenant security.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from core.models import TenantIntegrationConfig
from core.integration_registry import IntegrationRegistry
from core.structured_logger import get_logger

logger = get_logger(__name__)


class IntegrationCatalogService:
    """Service for managing integration catalog with search and filtering.

    Provides admin users with tools to browse integrations by search,
    category, and manage tenant-level configuration.
    """

    def __init__(self, db: Session):
        """Initialize IntegrationCatalogService.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.registry = IntegrationRegistry()

    async def search_integrations(
        self,
        tenant_id: str,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search integrations by name or description.

        Args:
            tenant_id: Tenant ID for multi-tenant isolation
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of integrations matching search query with tenant status
        """
        all_integrations = self.registry.get_all_integrations()
        query_lower = query.lower()

        # Filter by name or description
        filtered = [
            integration for integration in all_integrations
            if query_lower in integration["name"].lower() or
               query_lower in integration.get("description", "").lower()
        ]

        # Enrich with tenant status
        results = []
        for integration in filtered[:limit]:
            config = self.registry.get_tenant_config(self.db, tenant_id, integration["id"])
            results.append({
                **integration,
                "enabled": config["enabled"] if config else True,
                "connected_user_count": config["connected_user_count"] if config else 0,
            })

        return results

    async def filter_by_category(
        self,
        tenant_id: str,
        category: str
    ) -> List[Dict[str, Any]]:
        """Filter integrations by category.

        Args:
            tenant_id: Tenant ID for multi-tenant isolation
            category: Category to filter by (e.g., "CRM", "Communication", "Productivity")

        Returns:
            List of integrations in category with tenant status
        """
        all_integrations = self.registry.get_all_integrations()

        # Filter by category
        filtered = [
            integration for integration in all_integrations
            if integration.get("category") == category
        ]

        # Enrich with tenant status
        results = []
        for integration in filtered:
            config = self.registry.get_tenant_config(self.db, tenant_id, integration["id"])
            results.append({
                **integration,
                "enabled": config["enabled"] if config else True,
                "connected_user_count": config["connected_user_count"] if config else 0,
            })

        return results

    async def get_categories(self) -> List[str]:
        """Get all available integration categories.

        Returns:
            List of unique categories from integration registry
        """
        all_integrations = self.registry.get_all_integrations()
        categories = set()

        for integration in all_integrations:
            category = integration.get("category")
            if category:
                categories.add(category)

        return sorted(list(categories))

    async def get_integration_config(
        self,
        tenant_id: str,
        integration_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get tenant configuration for an integration with full details.

        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID

        Returns:
            Full configuration with integration details or None
        """
        # Get integration details
        integration = self.registry.get_integration(integration_id)
        if not integration:
            return None

        # Get tenant config
        config = self.registry.get_tenant_config(self.db, tenant_id, integration_id)

        return {
            **integration,
            "enabled": config["enabled"] if config else True,
            "sync_settings": config["sync_settings"] if config else {},
            "connected_user_count": config["connected_user_count"] if config else 0,
            "last_activity_at": config.get("last_activity_at") if config else None,
            "last_sync_at": config.get("last_sync_at") if config else None,
        }

    async def update_integration_config(
        self,
        tenant_id: str,
        integration_id: str,
        enabled: Optional[bool] = None,
        sync_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update tenant configuration for an integration.

        Args:
            tenant_id: Tenant ID
            integration_id: Integration ID
            enabled: Enable/disable flag (optional)
            sync_settings: Sync settings dict (optional)

        Returns:
            Updated configuration

        Raises:
            ValueError: If sync settings are invalid
        """
        # Validate sync settings if provided
        if sync_settings:
            self._validate_sync_settings(sync_settings)

        # Update enabled flag if provided
        if enabled is not None:
            self.registry.set_tenant_enabled(self.db, tenant_id, integration_id, enabled)

        # Update sync settings if provided
        if sync_settings:
            self.registry.update_sync_settings(self.db, tenant_id, integration_id, sync_settings)

        # Return updated config
        return await self.get_integration_config(tenant_id, integration_id)

    def _validate_sync_settings(self, sync_settings: Dict[str, Any]) -> None:
        """Validate sync settings before saving.

        Args:
            sync_settings: Settings dict to validate

        Raises:
            ValueError: If settings are invalid
        """
        # Validate frequency_hours
        if "frequency_hours" in sync_settings:
            frequency = sync_settings["frequency_hours"]
            if not isinstance(frequency, int) or frequency < 1 or frequency > 168:  # Max 1 week
                raise ValueError("frequency_hours must be an integer between 1 and 168")

        # Validate data_limit_mb
        if "data_limit_mb" in sync_settings:
            limit = sync_settings["data_limit_mb"]
            if not isinstance(limit, int) or limit < 1 or limit > 10000:  # Max 10GB
                raise ValueError("data_limit_mb must be an integer between 1 and 10000")

        # Validate entity_types
        if "entity_types" in sync_settings:
            entity_types = sync_settings["entity_types"]
            if not isinstance(entity_types, list):
                raise ValueError("entity_types must be a list")

            if not all(isinstance(et, str) for et in entity_types):
                raise ValueError("All entity_types must be strings")
