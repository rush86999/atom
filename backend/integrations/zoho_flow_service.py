"""Zoho Flow integration service.

Zoho Flow (Zoho's automation/iPaaS app) has no public REST API for listing
flows or execution history — the help docs expose history only through the
web UI, and community requests for a read API remain open. Flow CAN push
execution events to a webhook, which the platform already ingests at
``POST /webhooks/zoho-flow`` (api/webhook_routes.py, secret
``ZOHOFLOW_WEBHOOK_SECRET``) into the ``integration_zoho_flow`` LanceDB
table.

This service gives that data the same first-class surface every other
integration has: registry entry, /health + /capabilities routes, readback
(``list_events``) and vector search (``search_events``) over the ingested
table for the agent tool planner. It intentionally registers NO hybrid
pull-sync — there is nothing to pull from.
"""

import logging
import os
from typing import Any, Dict, Optional

from core.integration_service import IntegrationService
from integrations.zoho_webhook_ingestion import (
    ingest_records,
    list_recent,
    search_records,
)

logger = logging.getLogger(__name__)

WEBHOOK_SECRET_ENV = "ZOHOFLOW_WEBHOOK_SECRET"


class ZohoFlowService(IntegrationService):
    """Webhook-push integration for Zoho Flow (no public read API)."""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.workspace_id = config.get("workspace_id") or tenant_id or "default"

    # ---- IntegrationService ABC contract ----

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": ["list_events", "search_events", "ingest_records"],
            "required_params": [],
            "optional_params": ["workspace_id", "limit", "query"],
            "ingestion_mode": "webhook_push",
            "webhook_path": "/webhooks/zoho-flow",
            "webhook_secret_env": WEBHOOK_SECRET_ENV,
            "supports_webhooks": True,
            "supports_pull_sync": False,
            "note": (
                "Zoho Flow exposes flows/executions only through its UI; "
                "execution events arrive via the webhook above and land in "
                "the integration_zoho_flow memory table."
            ),
        }

    def health_check(self) -> Dict[str, Any]:
        from datetime import datetime, timezone

        secret_configured = bool(os.getenv(WEBHOOK_SECRET_ENV))
        return {
            "healthy": True,
            "message": (
                "webhook ingestion ready"
                if secret_configured
                else f"set {WEBHOOK_SECRET_ENV} to accept pushed flow events"
            ),
            "webhook_configured": secret_configured,
            "ingestion_mode": "webhook_push",
            "last_check": datetime.now(timezone.utc).isoformat(),
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            if operation == "list_events":
                return {"success": True, "result": await self.list_events()}
            if operation == "search_events":
                return {
                    "success": True,
                    "result": await self.search_events(parameters.get("query", "")),
                }
            if operation == "ingest_records":
                return {
                    "success": True,
                    "result": await self.ingest_records(parameters.get("records", [])),
                }
            return {
                "success": False,
                "error": f"Unsupported operation: {operation}",
                "supported": ["list_events", "search_events", "ingest_records"],
            }
        except Exception as exc:
            logger.error(f"Zoho Flow operation '{operation}' failed: {exc}")
            return {"success": False, "error": "Zoho Flow operation failed"}

    # ---- ingestion + readback ----

    def _memory_handler(self, workspace_id: Optional[str] = None):
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service

        service = get_hybrid_ingestion_service(workspace_id or self.workspace_id)
        return getattr(service, "memory_handler", None)

    async def ingest_records(
        self,
        records,
        workspace_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upsert pushed flow events into agent memory (never raises).

        The live /webhooks/zoho-flow route has its own inline writer; this
        method exists so the agent/registry surface (and any future
        producer) uses the same table and stamps.
        """
        return await ingest_records(
            self._memory_handler(workspace_id),
            records,
            integration_id="zoho_flow",
            workspace_id=workspace_id or self.workspace_id,
            role=role,
            default_type="event",
        )

    async def list_events(self, workspace_id: Optional[str] = None, limit: int = 20):
        return list_recent(self._memory_handler(workspace_id), "zoho_flow", limit=limit)

    async def search_events(
        self, query: str, workspace_id: Optional[str] = None, limit: int = 10
    ):
        return search_records(
            self._memory_handler(workspace_id), "zoho_flow", query, limit=limit
        )


zoho_flow_service = ZohoFlowService()
