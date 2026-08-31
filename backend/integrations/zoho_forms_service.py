"""Zoho Forms integration service.

Zoho Forms has NO public read API (Zoho's official reply: "we do not
support the API in Zoho Forms" — help.zoho.com community, "Zoho Forms
API"), and no working `ZohoForms.*` OAuth scope exists; a fabricated scope
would fail the whole suite consent URL. The product CAN push each
submission to a webhook (Forms → Settings → Integrations → Webhook), so
this app is webhook-push only:

    POST /api/v1/integrations/zoho-forms/webhook
        Authorization: Bearer $ZOHOFORMS_WEBHOOK_SECRET

Submissions land in the `integration_zoho_forms` LanceDB table via the
shared webhook-push ingestion helper (same freshness/role stamps and
trigger coordinator as every other ingested record), so they are
recallable in chat through the memory assembler's integration-records
leg. There is deliberately NO hybrid pull-sync registration: a sync
button that fetched nothing would be dishonest about a push-only product.
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

WEBHOOK_SECRET_ENV = "ZOHOFORMS_WEBHOOK_SECRET"


class ZohoFormsService(IntegrationService):
    """Webhook-push integration for Zoho Forms (no public read API)."""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.workspace_id = config.get("workspace_id") or tenant_id or "default"

    # ---- IntegrationService ABC contract ----

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": ["list_submissions", "search_submissions", "ingest_records"],
            "required_params": [],
            "optional_params": ["workspace_id", "limit", "query"],
            "ingestion_mode": "webhook_push",
            "webhook_path": "/api/v1/integrations/zoho-forms/webhook",
            "webhook_secret_env": WEBHOOK_SECRET_ENV,
            "supports_webhooks": True,
            "supports_pull_sync": False,
            "note": (
                "Zoho Forms exposes no public read API and no working "
                "ZohoForms.* OAuth scope; submissions are ingested via the "
                "webhook push endpoint above."
            ),
        }

    def health_check(self) -> Dict[str, Any]:
        from datetime import datetime, timezone

        secret_configured = bool(os.getenv(WEBHOOK_SECRET_ENV))
        return {
            "healthy": True,  # readback/search always available; push needs the secret
            "message": (
                "webhook ingestion ready"
                if secret_configured
                else f"set {WEBHOOK_SECRET_ENV} to accept pushed submissions"
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
            if operation == "list_submissions":
                return {"success": True, "result": await self.list_submissions()}
            if operation == "search_submissions":
                return {
                    "success": True,
                    "result": await self.search_submissions(parameters.get("query", "")),
                }
            if operation == "ingest_records":
                return {
                    "success": True,
                    "result": await self.ingest_records(parameters.get("records", [])),
                }
            return {
                "success": False,
                "error": f"Unsupported operation: {operation}",
                "supported": ["list_submissions", "search_submissions", "ingest_records"],
            }
        except Exception as exc:
            logger.error(f"Zoho Forms operation '{operation}' failed: {exc}")
            return {"success": False, "error": "Zoho Forms operation failed"}

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
        """Upsert pushed form submissions into agent memory (never raises)."""
        return await ingest_records(
            self._memory_handler(workspace_id),
            records,
            integration_id="zoho_forms",
            workspace_id=workspace_id or self.workspace_id,
            role=role,
            default_type="form_submission",
        )

    async def list_submissions(self, workspace_id: Optional[str] = None, limit: int = 20):
        return list_recent(
            self._memory_handler(workspace_id), "zoho_forms", limit=limit
        )

    async def search_submissions(
        self, query: str, workspace_id: Optional[str] = None, limit: int = 10
    ):
        return search_records(
            self._memory_handler(workspace_id), "zoho_forms", query, limit=limit
        )


zoho_forms_service = ZohoFormsService()
