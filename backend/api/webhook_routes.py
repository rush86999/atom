"""
Webhook API Routes for Real-Time Communication Ingestion
Provides endpoints for Slack, Teams, and Gmail webhooks.
"""

import hmac
import logging
import os
from typing import Optional
from fastapi import BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from core.base_routes import BaseAPIRouter
from core.webhook_handlers import get_webhook_processor

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Get webhook processor
webhook_processor = get_webhook_processor()


def _require_webhook_secret(env_var: str):
    """Shared-secret dependency for external webhook endpoints.

    R69: these endpoints previously had no auth and handlers never called the
    (weak, dev-only) platform verifiers. Require a Bearer token compared in
    constant time against an env secret; FAIL CLOSED (401) when unset.
    """
    async def _check(authorization: Optional[str] = Header(None)):
        secret = os.getenv(env_var)
        if not secret:
            raise HTTPException(status_code=401, detail="Webhook not configured")
        token = (authorization or "").strip().removeprefix("Bearer ").strip()
        if not token or not hmac.compare_digest(token, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook token")
    return _check


@router.post("/slack")
async def slack_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Receive Slack webhook events for real-time message processing.

    Slack sends events when:
    - New messages are posted
    - Messages are edited/deleted
    - Reactions are added/removed
    - Channels are created/archived

    Expected headers:
    - X-Slack-Request-Timestamp: Timestamp of request
    - X-Slack-Signature: HMAC signature for verification
    """
    result = await webhook_processor.process_slack_webhook(request, background_tasks)

    # Handle URL verification challenge
    if "challenge" in result:
        return JSONResponse(content={"challenge": result["challenge"]})

    return result


@router.post("/teams")
async def teams_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_webhook_secret("ATOM_TEAMS_WEBHOOK_SECRET")),
):
    """
    Receive Microsoft Teams webhook events for real-time message processing.

    Teams sends events when:
    - New chat messages are posted
    - Channel messages are posted
    - Message updates occur

    Note: This endpoint requires proper Microsoft Graph webhook subscription.
    """
    result = await webhook_processor.process_teams_webhook(request, background_tasks)
    return result


@router.post("/gmail")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_require_webhook_secret("ATOM_GMAIL_WEBHOOK_SECRET")),
):
    """
    Receive Gmail push notifications for real-time email processing.

    Gmail sends push notifications when:
    - New emails arrive
    - Email labels change
    - Emails are deleted

    Note: This endpoint requires Google Cloud Pub/Sub subscription.
    """
    result = await webhook_processor.process_gmail_webhook(request, background_tasks)
    return result


@router.get("/health")
async def webhook_health():
    """Check webhook endpoint health"""
    return router.success_response(
        data={
            "status": "healthy",
            "webhooks": {
                "slack": "enabled",
                "teams": "enabled",
                "gmail": "enabled"
            },
            "processed_events": len(webhook_processor.processed_events)
        },
        message="Webhook endpoints are healthy"
    )


# ============================================================================
# Zoho Flow (Zoho's automation app) — webhook ingestion
# ============================================================================
@router.post("/zoho-flow")
async def zoho_flow_webhook(
    request: Request,
    agent_id: Optional[str] = None,
    _check=Depends(_require_webhook_secret("ZOHOFLOW_WEBHOOK_SECRET")),
):
    """Ingest events pushed by a Zoho Flow (Zoho's automation/iPaaS app).

    Point a Zoho Flow "Webhook" task at this URL with
    `Authorization: Bearer $ZOHOFLOW_WEBHOOK_SECRET`. Accepts a single record
    or `{"records": [...]}`; each record lands in agent memory
    (role/freshness-stamped) and fires the AI trigger coordinator — so a
    sales-domain event routes to the domain agent and hits its trust gate
    exactly like synced data.
    """
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON")

    records = payload.get("records") if isinstance(payload, dict) else None
    if records is None:
        records = [payload]
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=400, detail="No records in payload")

    from core.database import SessionLocal
    from core.hybrid_data_ingestion import get_hybrid_ingestion_service
    from core.vector_upsert import upsert_document
    from core.models import AgentRegistry

    # Role-scope: ?agent_id= resolves the hire's category (same rule as sync)
    role = None
    if agent_id:
        db = SessionLocal()
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            role = (agent.category or "").lower() if agent else None
        finally:
            db.close()

    service = get_hybrid_ingestion_service("default")
    if service.memory_handler is None:
        await service.memory_handler.initialize() if hasattr(service.memory_handler, "initialize") else None

    now = _dt.now(_tz.utc).isoformat()
    written = 0
    trigger_payloads = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rid = str(rec.get("id") or rec.get("record_id") or _uuid.uuid4())
        rtype = str(rec.get("type") or rec.get("module") or "event")
        name = rec.get("name") or rec.get("subject") or rec.get("title") or rtype
        parts = [f"{rtype.title()} from zoho_flow", f"name: {name}"]
        for k in ("description", "summary", "status", "amount", "company", "email"):
            if rec.get(k):
                parts.append(f"{k}: {rec[k]}")
        text = "\n".join(parts)

        record = {
            "id": rid,
            "type": rtype,
            "name": name,
            "modified_at": rec.get("modified_time") or rec.get("modified_at"),
        }

        try:
            from core.data_taint_tracker import classify_sensitivity
            sensitivity = classify_sensitivity(text)
        except Exception:
            sensitivity = "internal"

        meta = {
            "integration_id": "zoho_flow",
            "record_id": rid,
            "record_type": rtype,
            "sensitivity": sensitivity,
            "synced_at": now,
            "source_modified_at": record.get("modified_at"),
            "last_verified_at": now,
            "freshness_status": "fresh",
        }
        if role:
            meta["role"] = role

        status = "write_failed"
        if service.memory_handler is not None:
            status = await upsert_document(
                service.memory_handler,
                table_name="integration_zoho_flow",
                text=text,
                doc_id=f"rec_zoho_flow:{rid}",
                source="zoho_flow",
                metadata=meta,
                user_id="system",
            )
        if status == "written":
            written += 1
        # The trigger classifier scores payload text — pass the full record
        # (email/company/description carry the classification signal).
        trigger_rec = dict(rec)
        trigger_rec["id"] = rid
        trigger_rec["type"] = rtype
        trigger_rec.setdefault("name", name)
        trigger_payloads.append(trigger_rec)

    # Fire the domain trigger pipeline (trust gate / training proposals)
    triggered = 0
    try:
        from core.ai_trigger_coordinator import on_data_ingested

        for rec in trigger_payloads[:10]:  # cap trigger fan-out per push
            await on_data_ingested(
                rec,
                source="zoho_flow",
                workspace_id="default",
                metadata={"role": role, "force_trigger": True},
            )
            triggered += 1
    except Exception as trig_err:
        logger.warning(f"zoho_flow trigger pass failed: {trig_err}")

    return {
        "success": True,
        "received": len(records),
        "ingested": written,
        "triggers_fired": triggered,
        "role": role,
    }
