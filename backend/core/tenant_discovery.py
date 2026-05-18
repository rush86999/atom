from __future__ import annotations
from typing import Union
"""
Tenant Discovery Service

Reverse-lookup service to resolve ATOM tenant_id from third-party provider IDs
(e.g., Slack team_id, Salesforce OrganizationId).

Includes Redis caching for high-performance webhook dispatching.
"""

from sqlalchemy.orm import Session

from core.cache import redis_cache
from core.models import TenantIntegration
from core.structured_logger import get_logger

logger = get_logger(__name__)


class TenantDiscoveryService:
    """Service for resolving tenant identity from external integration events."""

    def __init__(self, db: Session):
        self.db = db
        self.cache = redis_cache
        self.cache_ttl = 3600  # 1 hour

    async def get_tenant_id_by_external_id(self, connector_id: str, external_id: str) -> Union[str, None]:
        """
        Resolve ATOM tenant_id from external (provider-side) ID.

        Args:
            connector_id: Literal provider name (e.g. 'slack', 'salesforce')
            external_id: The unique ID from the provider (e.g. 'T012345')

        Returns:
            tenant_id if found, else None
        """
        if not external_id:
            return None

        cache_key = f"discovery:{connector_id}:{external_id}"

        # 1. Try Cache
        cached_tenant_id = await self.cache.get_async(cache_key)
        if cached_tenant_id:
            return str(cached_tenant_id)

        # 2. Database Lookup
        try:
            from sqlalchemy import text
            if self.db.bind and self.db.bind.dialect.name == "postgresql":
                self.db.execute(text("SET LOCAL row_security = off"))
            try:
                integration = (
                    self.db.query(TenantIntegration)
                    .filter(
                        TenantIntegration.connector_id == connector_id,
                        TenantIntegration.external_id == external_id,
                        TenantIntegration.is_active == True,
                    )
                    .first()
                )
            finally:
                if self.db.bind and self.db.bind.dialect.name == "postgresql":
                    self.db.execute(text("SET LOCAL row_security = on"))

            if integration:
                tenant_id = str(integration.tenant_id)
                # Update Cache
                await self.cache.set_async(cache_key, tenant_id, ttl=self.cache_ttl)
                return tenant_id

        except Exception as e:
            logger.error(f"Tenant discovery failed for {connector_id}/{external_id}: {e}")

        return None

    async def register_external_id(
        self, tenant_id: str, connector_id: str, external_id: str
    ) -> bool:
        """
        Manually link an external ID to a tenant (e.g. during OAuth callback).
        Useful for pre-populating the discovery mapping.
        """
        try:
            integration = (
                self.db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.connector_id == connector_id,
                )
                .first()
            )

            if integration:
                integration.external_id = external_id
                self.db.commit()

                # Invalidate cache to be safe
                cache_key = f"discovery:{connector_id}:{external_id}"
                await self.cache.delete_async(cache_key)

                logger.info(
                    f"Registered external_id {external_id} for tenant {tenant_id} ({connector_id})"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to register external_id: {e}")
            self.db.rollback()

        return False
