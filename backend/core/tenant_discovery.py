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

            cache_key_new = f"discovery:{connector_id}:{external_id}"

            # Cross-tenant guard (BUG-87-1): refuse to link an external_id
            # that is already owned by a DIFFERENT tenant. Two live mappings
            # for the same (connector, external_id) make the reverse-lookup's
            # `.first()` non-deterministic — webhook events can be routed to
            # the wrong tenant (tenant isolation breach). The query excludes
            # the caller's own row, so updating one's own mapping is fine.
            owner = (
                self.db.query(TenantIntegration)
                .filter(
                    TenantIntegration.connector_id == connector_id,
                    TenantIntegration.external_id == external_id,
                    TenantIntegration.tenant_id != tenant_id,
                )
                .first()
            )
            if owner is not None:
                logger.warning(
                    f"Refusing to register external_id {external_id} for tenant "
                    f"{tenant_id} ({connector_id}): already owned by tenant "
                    f"{owner.tenant_id}"
                )
                return False

            if integration:
                # BUG-083: Capture the OLD external_id before overwriting so
                # its cache entry can be invalidated too. Previously only the
                # new id's cache was cleared, leaving the old id resolving to
                # this tenant for up to 1 hour (cross-tenant stale routing).
                old_external_id = integration.external_id
                integration.external_id = external_id
                self.db.commit()

                # Invalidate cache for both old and new external_ids
                await self.cache.delete_async(cache_key_new)
                if old_external_id and old_external_id != external_id:
                    cache_key_old = f"discovery:{connector_id}:{old_external_id}"
                    await self.cache.delete_async(cache_key_old)

                logger.info(
                    f"Registered external_id {external_id} for tenant {tenant_id} ({connector_id})"
                )
                return True

            # BUG-87-2: a brand-new (tenant, connector) pair previously fell
            # through to `return False` — the mapping was NEVER created, so
            # OAuth pre-population was a silent no-op. Create the row.
            new_integration = TenantIntegration(
                tenant_id=tenant_id,
                connector_id=connector_id,
                external_id=external_id,
            )
            self.db.add(new_integration)
            self.db.commit()
            await self.cache.delete_async(cache_key_new)
            logger.info(
                f"Created external_id {external_id} for tenant {tenant_id} ({connector_id})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to register external_id: {e}")
            self.db.rollback()

        return False
