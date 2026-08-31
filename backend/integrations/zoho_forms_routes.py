"""Thin integration router for zoho_forms (webhook-push app).

Zoho Forms has no public read API, so this surface is: /health +
/capabilities for the Integrations hub, /submissions for readback of
ingested records, and the secret-protected /webhook that Zoho Forms'
own webhook integration (Forms → Settings → Integrations → Webhook)
pushes submissions to. The service class is the source of truth.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import User, get_current_user
from integrations.zoho_forms_service import ZohoFormsService, zoho_forms_service

logger = logging.getLogger(__name__)

# No router-level prefix or auth: /health + /capabilities stay public for
# hub probes (sibling zoho_*_routes style); data endpoints declare their
# own auth; /webhook carries its own shared-secret check.
router = APIRouter(tags=["zoho-forms"])


def _webhook_secret_check():
    # Reuse the platform's fail-closed shared-secret dependency (constant-
    # time compare, 401 when unset) instead of re-implementing it here.
    from api.webhook_routes import _require_webhook_secret as _factory

    return _factory("ZOHOFORMS_WEBHOOK_SECRET")


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the zoho_forms integration."""
    try:
        return zoho_forms_service.health_check()
    except Exception as exc:
        logger.warning("zoho_forms health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this zoho_forms service supports."""
    try:
        return zoho_forms_service.get_capabilities()
    except Exception as exc:
        logger.warning("zoho_forms capabilities failed: %s", exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@router.get("/submissions")
async def list_submissions(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Recent ingested form submissions (push arrived via /webhook)."""
    service = ZohoFormsService(config={"workspace_id": "default"})
    return {
        "success": True,
        "data": await service.list_submissions(limit=min(limit, 100)),
    }


@router.post("/webhook", dependencies=[Depends(_webhook_secret_check())])
async def zoho_forms_webhook(request: Request) -> Dict[str, Any]:
    """Ingest form submissions pushed by Zoho Forms' webhook integration.

    Point the Zoho Forms webhook task at this URL with
    `Authorization: Bearer $ZOHOFORMS_WEBHOOK_SECRET`. Accepts a single
    submission or `{"records": [...]}`; arbitrary field-label → value maps
    are flattened into searchable text and land in the
    `integration_zoho_forms` memory table, freshness/role-stamped, firing
    the AI trigger coordinator like every other ingested record.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON")

    records = payload.get("records") if isinstance(payload, dict) else None
    if records is None:
        records = [payload]
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=400, detail="No records in payload")

    result = await zoho_forms_service.ingest_records(records)
    return {"success": True, **result}
