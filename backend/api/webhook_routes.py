"""
Webhook API Routes for Real-Time Communication Ingestion
Provides endpoints for Slack, Teams, and Gmail webhooks.
"""

import hmac
import logging
import os
from typing import Any, Optional
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


# ---------------------------------------------------------------------------
# Zoho WorkDrive file-change push (real-time ingestion)
#
# Configured in WorkDrive → Custom Apps → Webhooks: point the webhook at
# /api/webhooks/zoho-workdrive?token=<WORKDRIVE_WEBHOOK_SECRET> and select
# file events (edited/created) on the team folder(s) the agent reads. On any
# event, the touched files are re-ingested for every connected user — the
# hash-dedup inside the funnel makes "no real change" cost one download +
# parse, and a real edit refreshes the store within seconds of the edit
# instead of waiting for the next sync pass. Pricing and quoting answers are
# therefore as-fresh as the last edit, not as-fresh as the last hourly sync.
# ---------------------------------------------------------------------------

def _extract_workdrive_file_ids(payload: Any) -> list:
    """Pull WorkDrive file ids out of a webhook payload without assuming one
    exact event schema: Zoho custom-app events vary by trigger type. Accepts
    an explicit {'file_ids': [...]} body, and otherwise scans common id keys
    (resource_id / file_id / id — top level and one nesting deep) plus
    falls back to any Zoho-id-shaped string in the payload."""
    import re as _re

    if not isinstance(payload, dict):
        return []
    explicit = payload.get("file_ids") or payload.get("fileIds")
    if isinstance(explicit, list) and explicit:
        return [str(x) for x in explicit if x]

    found: list = []
    zoho_shape = _re.compile(r"^[A-Za-z0-9]{16,64}$")

    def _is_id_key(k: str) -> bool:
        kl = k.lower()
        return kl == "id" or kl.endswith("_id") or kl.endswith("id") and len(k) > 2

    def _scan(node: Any, depth: int = 0) -> None:
        if len(found) >= 10 or depth > 3:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and _is_id_key(k) and zoho_shape.match(v):
                    if v not in found:
                        found.append(v)
                else:
                    _scan(v, depth + 1)
        elif isinstance(node, list):
            for item in node[:20]:
                _scan(item, depth + 1)

    _scan(payload)
    return found


async def _workdrive_connected_user_ids() -> list:
    """Users with an active WorkDrive/zoho token — webhook events carry no
    acting user, so the touched file is refreshed for each connected account
    (single-tenant deployments: exactly one)."""
    from core.database import SessionLocal
    from core.models import IntegrationToken

    db = SessionLocal()
    try:
        rows = (
            db.query(IntegrationToken.user_id)
            .filter(
                IntegrationToken.provider.in_(("zoho_workdrive", "zoho")),
                IntegrationToken.status == "active",
            )
            .distinct()
            .all()
        )
        return [r[0] for r in rows if r[0]]
    finally:
        db.close()


@router.post("/zoho-workdrive")
async def zoho_workdrive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    token: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Real-time WorkDrive file-change ingestion (pricing freshness).

    Auth: the shared secret as ?token=... (WorkDrive custom apps put the key
    in the endpoint URL) or as a Bearer header. FAILS CLOSED when
    WORKDRIVE_WEBHOOK_SECRET is unset. Unknown/unchanged files cost one
    download + parse (hash-dedup inside the funnel); real edits replace the
    stored chunk family immediately.
    """
    secret = os.getenv("WORKDRIVE_WEBHOOK_SECRET")
    supplied = (token or (authorization or "").strip().removeprefix("Bearer ").strip())
    if not secret or not supplied or not hmac.compare_digest(supplied, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    file_ids = _extract_workdrive_file_ids(payload)
    if not file_ids:
        return JSONResponse(status_code=202, content={
            "success": True, "received": True, "files_matched": 0,
            "message": "No recognizable file id in event; nothing to refresh.",
        })

    user_ids = await _workdrive_connected_user_ids()
    if not user_ids:
        return JSONResponse(status_code=202, content={
            "success": True, "files_matched": len(file_ids), "users": 0,
            "message": "No connected WorkDrive account; connect the integration first.",
        })

    async def _refresh():
        from integrations.zoho_workdrive_service import ZohoWorkDriveService

        svc = ZohoWorkDriveService("default", {})
        for uid in user_ids:
            for fid in file_ids:
                try:
                    res = await svc.ingest_file_to_memory(uid, fid)
                    logger.info(
                        f"workdrive webhook: refreshed {fid} for {uid} -> "
                        f"{res.get('status') or res.get('error')}"
                    )
                except Exception as ing_err:  # noqa: BLE001 — best-effort push
                    logger.warning(f"workdrive webhook ingest failed ({fid}): {ing_err}")

    background_tasks.add_task(_refresh)
    return JSONResponse(status_code=202, content={
        "success": True, "files_matched": len(file_ids),
        "users": len(user_ids), "message": "Refresh queued.",
    })
