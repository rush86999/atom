"""
from __future__ import annotations
Integration Webhook Handlers for Ingestion Pipeline

Handles webhook notifications from integrations (Slack, HubSpot, Salesforce, Gmail, Notion)
and triggers the ingestion pipeline for near real-time data sync to Knowledge Graph.

All handlers verify HMAC signatures before processing and enqueue background jobs
to avoid webhook timeout issues.

Key features:
    pass
- HMAC signature verification for security
- Tenant extraction from webhook payloads
- Background job enqueueing via WebhookIngestionQueue
- 200 OK immediate response pattern
- Integration-specific handlers for 5+ platforms
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
import asyncio
import hmac
import hashlib
import os

from api.routes.webhooks.base import verify_hmac_signature
from core.database import get_db
from core.models import TenantIntegration, UserConnection, DiscoveredEntity
from core.structured_logger import get_logger
from core.tenant_discovery import TenantDiscoveryService
from core.webhook_ingestion_triggers import WebhookIngestionQueue

logger = get_logger(__name__)

# Create router and queue
router = APIRouter()
webhook_queue = WebhookIngestionQueue()


# ============================================================================
# R89: shared fail-closed verification for the generic webhook families.
#
# The zoho / pm-crm / communication / dev-prod handlers resolved tenants from
# public/enumerable payload fields (Jira clientKey, Twilio AccountSid, Zoho
# orgId…) and dispatched CRUD — including deletions — using the victim
# tenant's stored credentials, with NO verification at all. Same contract as
# the R69 family secrets: env must be set (503 otherwise) and the request
# must carry X-Atom-Webhook-Signature = hex HMAC-SHA256 over the RAW body.
# ============================================================================

async def _verify_family_webhook(request: Request, secret_env: str, label: str) -> None:
    """Fail-closed shared-secret verification for a webhook family.

    HEAD probes (health checks) carry no side effects and no body — skipped.
    """
    if request.method == "HEAD":
        return

    expected_secret = os.getenv(secret_env, "")
    if not expected_secret:
        logger.error(f"{label} webhook received but {secret_env} not set — rejecting")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    raw_body = await request.body()
    supplied_sig = request.headers.get("X-Atom-Webhook-Signature", "")
    if not supplied_sig:
        logger.error(f"{label} webhook missing signature header — rejecting")
        raise HTTPException(status_code=401, detail="Missing signature")
    computed_sig = hmac.new(
        expected_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(computed_sig, supplied_sig):
        logger.error(f"{label} webhook signature mismatch — rejecting")
        raise HTTPException(status_code=401, detail="Invalid signature")


# ============================================================================
# Zendesk Webhook Handler
# ============================================================================


@router.post("/webhooks/zendesk/events")
async def zendesk_webhook_handler(request: Request, db: Session = Depends(get_db)):
    """
    Handle Zendesk Support webhook (ticket comments) and trigger ingestion.

    Verification (fail-closed, R69 pattern): ZENDESK_WEBHOOK_SECRET must be
    set; the request must carry X-Zendesk-Webhook-Signature — a base64
    HMAC-SHA256 over the RAW request body. Missing secret -> 503; invalid
    or missing signature -> 401.

    Tenant resolution: the first active zendesk UserConnection (Zendesk
    accounts are 1:1 with an Atom tenant in this deployment shape).
    """
    import base64 as _base64
    import hashlib

    from sqlalchemy import text as _sa_text

    expected_secret = os.getenv("ZENDESK_WEBHOOK_SECRET", "")
    if not expected_secret:
        logger.error("Zendesk webhook received but ZENDESK_WEBHOOK_SECRET not set — rejecting")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    raw_body = await request.body()
    supplied_sig = request.headers.get("X-Zendesk-Webhook-Signature", "")
    if not supplied_sig:
        logger.error("Zendesk webhook missing signature header — rejecting")
        raise HTTPException(status_code=401, detail="Missing signature")
    computed_sig = _base64.b64encode(
        hmac.new(expected_secret.encode(), raw_body, hashlib.sha256).digest()
    ).decode()
    if not hmac.compare_digest(computed_sig, supplied_sig):
        logger.error("Zendesk webhook signature mismatch — rejecting")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event_data = await request.json()

        # Tenant resolution: first active zendesk connection
        from core.models import UserConnection

        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(_sa_text("SET LOCAL row_security = off"))

        connection = (
            db.query(UserConnection)
            .filter(
                UserConnection.integration_id == "zendesk",
                UserConnection.status == "active",
            )
            .first()
        )

        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(_sa_text("SET LOCAL row_security = on"))

        if not connection:
            logger.warning("No active Zendesk connection found for webhook")
            return {"status": "ignored", "reason": "no_active_connection"}

        tenant_id = str(connection.tenant_id)
        source_connection_id = str(connection.id)

        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id="zendesk",
            trigger_type="webhook",
            payload=event_data,
            source_connection_id=source_connection_id,
        )

        logger.info(
            "Zendesk webhook enqueued for ingestion",
            tenant_id=tenant_id,
            job_id=job_id,
        )
        return {"status": "enqueued", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Zendesk webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Slack Webhook Handler
# ============================================================================


@router.post("/webhooks/slack/events")
async def slack_webhook_handler(
    request: Request,
    x_slack_signature: str = Header(None),
    x_slack_request_timestamp: str = Header(None),
    db: Session = Depends(get_db),
):
    """
    Handle Slack event webhook and trigger ingestion.

    Verifies HMAC signature, extracts tenant_id from team_id,
    and enqueues ingestion job for background processing.

    Returns 200 OK immediately to avoid Slack retry issues.
    """
    try:
        pass
        # Get raw body for signature verification
        payload = await request.body()
        event_data = await request.json()

        # 1. Challenge Response (Slack requirement)
        if event_data.get("type") == "url_verification":
            return {"challenge": event_data.get("challenge")}

        # 2. Extract team_id for tenant resolution
        team_id = event_data.get("team_id")
        if not team_id:
            pass
            # Check inside event if not top-level
            team_id = event_data.get("event", {}).get("team")

        if not team_id:
            logger.warning("Slack webhook missing team_id")
            raise HTTPException(status_code=400, detail="Missing team_id")

        # 3. Resolve tenant using Discovery Service
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id("slack", team_id)

        if not tenant_id:
            logger.warning(f"No tenant found for Slack team_id: {team_id}")
            # Return 200 to avoid Slack retries, but log it
            return {"status": "ignored", "reason": "tenant_not_found"}

        # 4. Verify HMAC signature
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            integration = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.connector_id == "slack",
                    TenantIntegration.is_active == True,
                )
                .first()
            )
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))

        if not integration or not integration.config:
            logger.error(f"Slack integration not configured for tenant {tenant_id}")
            raise HTTPException(status_code=401, detail="Slack integration not configured")

        signing_secret = integration.config.get("slack_signing_secret")
        if not signing_secret:
            logger.error(f"Slack signing secret not configured for tenant {tenant_id}")
            raise HTTPException(status_code=503, detail="Webhook verification not configured")

        if not verify_hmac_signature(payload, x_slack_signature, signing_secret):
            logger.error(f"Unauthorized Slack webhook for tenant {tenant_id}")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # 4.5. Resolve source_connection_id for BYOK credential lookup
        # This is critical for transformers that need to fetch provider resources
        # and for LLM BYOK context. Without this, BYOK tenants get "No credentials available".
        source_connection_id = None
        try:
            from sqlalchemy import text
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = off"))
            try:
                conn = (
                    db.query(UserConnection)
                    .filter(
                        UserConnection.tenant_id == tenant_id,
                        UserConnection.integration_id == "slack",
                        UserConnection.status == "active",
                    )
                    .order_by(UserConnection.updated_at.desc())
                    .first()
                )
                if conn:
                    source_connection_id = str(conn.id)
            finally:
                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = on"))
        except Exception as e:
            logger.warning(f"Slack webhook: Failed to resolve source_connection_id: {e}")

        # 5. CRUD Dispatch handling
        from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
        change_type, resource_id = extract_crud_metadata("slack", event_data, dict(request.headers), dict(request.query_params))
        if not change_type or not resource_id:
            change_type = change_type or "created"
            resource_id = resource_id or "generic"

        result = await crud_dispatch(
            db=db,
            change_type=change_type,
            integration_id="slack",
            tenant_id=tenant_id,
            resource_id=resource_id,
            payload=event_data,
            source_connection_id=source_connection_id,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slack webhook handler error: {e}")
        # Return 200 OK even on error (webhook best practice)
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# HubSpot Webhook Handler
# ============================================================================


@router.post("/webhooks/hubspot/events")
async def hubspot_webhook_handler(
    request: Request, x_hubspot_signature: str = Header(None), db: Session = Depends(get_db)
):
    """
    Handle HubSpot CRM webhook and trigger ingestion.

    Verifies HMAC signature (SHA-256), extracts tenant_id from portal_id,
    and enqueues ingestion jobs for batch processing.

    Returns 200 OK immediately to avoid HubSpot retry issues.
    """
    try:
        pass
        # Get raw body for signature verification
        payload = await request.body()
        event_data = await request.json()

        # Handle batch events (HubSpot sends multiple events in one webhook)
        events = event_data if isinstance(event_data, list) else [event_data]

        for event in events:
            pass
            # Extract portal_id for tenant resolution
            portal_id = event.get("portalId")
            if not portal_id:
                logger.warning("HubSpot webhook missing portal_id")
                continue

            # Resolve tenant using Discovery Service
            discoverer = TenantDiscoveryService(db)
            tenant_id = await discoverer.get_tenant_id_by_external_id("hubspot", portal_id)

            if not tenant_id:
                logger.warning(f"No tenant found for HubSpot portal_id: {portal_id}")
                continue

            # Verify HMAC signature
            from sqlalchemy import text
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = off"))
            try:
                integration = (
                    db.query(TenantIntegration)
                    .filter(
                        TenantIntegration.tenant_id == tenant_id,
                        TenantIntegration.connector_id == "hubspot",
                        TenantIntegration.is_active == True,
                    )
                    .first()
                )
            finally:
                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = on"))

            # Round 45: fail CLOSED — when the integration or its signing
            # secret is not configured, reject instead of processing the
            # event unverified (previously the HMAC check was skipped and
            # forged events were dispatched). Mirrors the Slack handler.
            if not integration or not integration.config or not integration.config.get("client_secret"):
                logger.error(f"HubSpot signing secret not configured for tenant {tenant_id}")
                raise HTTPException(status_code=503, detail="Webhook verification not configured")

            import hashlib

            client_secret = integration.config.get("client_secret")
            if not verify_hmac_signature(
                payload, x_hubspot_signature, client_secret, algorithm=hashlib.sha256
            ):
                logger.error(f"Unauthorized HubSpot webhook for tenant {tenant_id}")
                raise HTTPException(status_code=401, detail="Invalid signature")

            # 4.5. Resolve source_connection_id for BYOK credential lookup
            source_connection_id = None
            try:
                from sqlalchemy import text
                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = off"))
                try:
                    conn = (
                        db.query(UserConnection)
                        .filter(
                            UserConnection.tenant_id == tenant_id,
                            UserConnection.integration_id == "hubspot",
                            UserConnection.status == "active",
                        )
                        .order_by(UserConnection.updated_at.desc())
                        .first()
                    )
                    if conn:
                        source_connection_id = str(conn.id)
                finally:
                    if db.bind and db.bind.dialect.name == "postgresql":
                        db.execute(text("SET LOCAL row_security = on"))
            except Exception as e:
                logger.warning(f"HubSpot webhook: Failed to resolve source_connection_id: {e}")

            # CRUD Dispatch handling
            from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
            change_type, resource_id = extract_crud_metadata("hubspot", event, dict(request.headers), dict(request.query_params))
            if not change_type or not resource_id:
                change_type = change_type or "created"
                resource_id = resource_id or "generic"

            await crud_dispatch(
                db=db,
                change_type=change_type,
                integration_id="hubspot",
                tenant_id=tenant_id,
                resource_id=resource_id,
                payload=event,
                source_connection_id=source_connection_id,
            )

        return {"status": "enqueued"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HubSpot webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Salesforce Webhook Handler
# ============================================================================


@router.post("/webhooks/salesforce/events")
async def salesforce_webhook_handler(
    request: Request, x_salesforce_signature: str = Header(None), db: Session = Depends(get_db)
):
    """
    Handle Salesforce event webhook and trigger ingestion.

    Verifies HMAC signature, extracts tenant_id from orgId,
    and enqueues ingestion job for background processing.

    Returns 200 OK immediately to avoid Salesforce retry issues.
    """
    try:
        pass
        # Get raw body for signature verification
        payload = await request.body()
        event_data = await request.json()

        # Extract org_id for tenant resolution
        org_id = event_data.get("orgId")
        if not org_id:
            logger.warning("Salesforce webhook missing orgId")
            raise HTTPException(status_code=400, detail="Missing orgId")

        # Resolve tenant using Discovery Service
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id("salesforce", org_id)

        if not tenant_id:
            logger.warning(f"No tenant found for Salesforce orgId: {org_id}")
            return {"status": "ignored", "reason": "tenant_not_found"}

        # Verify HMAC signature
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            integration = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.connector_id == "salesforce",
                    TenantIntegration.is_active == True,
                )
                .first()
            )
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))

        # Round 45: fail CLOSED — reject when the integration/secret is not
        # configured (previously the HMAC check was skipped entirely).
        if not integration or not integration.config or not integration.config.get("client_secret"):
            logger.error(f"Salesforce signing secret not configured for tenant {tenant_id}")
            raise HTTPException(status_code=503, detail="Webhook verification not configured")

        client_secret = integration.config.get("client_secret")
        if not verify_hmac_signature(payload, x_salesforce_signature, client_secret):
            logger.error(f"Unauthorized Salesforce webhook for tenant {tenant_id}")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # 4.5. Resolve source_connection_id for BYOK credential lookup
        source_connection_id = None
        try:
            from sqlalchemy import text
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = off"))
            try:
                conn = (
                    db.query(UserConnection)
                    .filter(
                        UserConnection.tenant_id == tenant_id,
                        UserConnection.integration_id == "salesforce",
                        UserConnection.status == "active",
                    )
                    .order_by(UserConnection.updated_at.desc())
                    .first()
                )
                if conn:
                    source_connection_id = str(conn.id)
            finally:
                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = on"))
        except Exception as e:
            logger.warning(f"Salesforce webhook: Failed to resolve source_connection_id: {e}")

        # CRUD Dispatch handling
        from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
        change_type, resource_id = extract_crud_metadata("salesforce", event_data, dict(request.headers), dict(request.query_params))
        if not change_type or not resource_id:
            change_type = change_type or "created"
            resource_id = resource_id or "generic"

        result = await crud_dispatch(
            db=db,
            change_type=change_type,
            integration_id="salesforce",
            tenant_id=tenant_id,
            resource_id=resource_id,
            payload=event_data,
            source_connection_id=source_connection_id,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Salesforce webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Gmail Webhook Handler
# ============================================================================


@router.post("/webhooks/gmail/events")
async def gmail_webhook_handler(request: Request, db: Session = Depends(get_db)):
    """
    Handle Gmail push notification webhook and trigger ingestion.

    Gmail uses Google's Pub/Sub authentication instead of HMAC: push
    subscriptions are registered with a `token` query parameter that the
    endpoint must verify (Google's documented pattern). Round 45/69 pattern:
    fail CLOSED — when GMAIL_WEBHOOK_VERIFY_TOKEN is unset or the supplied
    token mismatches, reject instead of processing forged notifications.
    """
    expected_token = os.getenv("GMAIL_WEBHOOK_VERIFY_TOKEN", "")
    if not expected_token:
        logger.error("Gmail webhook received but GMAIL_WEBHOOK_VERIFY_TOKEN not set — rejecting")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")
    supplied_token = request.query_params.get("token", "")
    if not supplied_token or not hmac.compare_digest(expected_token, supplied_token):
        logger.error("Gmail webhook received with invalid verification token — rejecting")
        raise HTTPException(status_code=401, detail="Invalid webhook verification token")

    try:
        pass
        # Gmail push notification payload
        event_data = await request.json()

        # 1. Handle Google Pub/Sub wrapper format (base64-encoded inner JSON in message.data)
        if "message" in event_data and isinstance(event_data["message"], dict):
            pubsub_msg = event_data["message"]
            base64_data = pubsub_msg.get("data")
            if base64_data:
                import base64
                import json
                try:
                    missing_padding = len(base64_data) % 4
                    if missing_padding:
                        base64_data += "=" * (4 - missing_padding)
                    decoded_bytes = base64.b64decode(base64_data)
                    decoded_json = json.loads(decoded_bytes.decode("utf-8"))
                    event_data = decoded_json
                    logger.info("Successfully decoded base64 Gmail Pub/Sub notification payload")
                except Exception as b64_err:
                    logger.error(f"Failed to decode Gmail Pub/Sub base64 data: {b64_err}")

        # Extract email address for tenant resolution
        email_address = event_data.get("emailAddress")
        if not email_address:
            logger.warning("Gmail webhook missing emailAddress")
            raise HTTPException(status_code=400, detail="Missing emailAddress")

        # Resolve tenant by email address (Gmail integration maps user email to tenant)
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id("gmail", email_address)

        if not tenant_id:
            logger.warning(f"No tenant found for Gmail email: {email_address}")
            return {"status": "ignored", "reason": "tenant_not_found"}

        # Resolve active UserConnection for Gmail
        from sqlalchemy import text
        from core.models import UserConnection

        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))

        connection = (
            db.query(UserConnection)
            .filter(
                UserConnection.tenant_id == tenant_id,
                UserConnection.integration_id == "gmail",
                UserConnection.status == "active",
            )
            .first()
        )

        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = on"))

        source_connection_id = str(connection.id) if connection else None

        # Enqueue ingestion job
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id="gmail",
            trigger_type="webhook",
            payload=event_data,
            source_connection_id=source_connection_id,
        )

        logger.info(
            "Gmail webhook enqueued for ingestion",
            tenant_id=tenant_id,
            email_address=email_address,
            job_id=job_id,
        )

        return {"status": "enqueued", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Notion Webhook Handler
# ============================================================================


@router.post("/webhooks/notion/events")
async def notion_webhook_handler(
    request: Request, x_notion_signature: str = Header(None), db: Session = Depends(get_db)
):
    """
    Handle Notion webhook and trigger ingestion.

    Verifies HMAC signature, extracts tenant_id from workspace_id,
    and enqueues ingestion job for background processing.

    Returns 200 OK immediately to avoid Notion retry issues.
    """
    try:
        pass
        # Get raw body for signature verification
        payload = await request.body()
        event_data = await request.json()

        # Extract workspace_id for tenant resolution
        workspace_id = event_data.get("workspace_id")
        if not workspace_id:
            logger.warning("Notion webhook missing workspace_id")
            raise HTTPException(status_code=400, detail="Missing workspace_id")

        # Resolve tenant using Discovery Service
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id("notion", workspace_id)

        if not tenant_id:
            logger.warning(f"No tenant found for Notion workspace_id: {workspace_id}")
            return {"status": "ignored", "reason": "tenant_not_found"}

        # Verify HMAC signature
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            integration = (
                db.query(TenantIntegration)
                .filter(
                    TenantIntegration.tenant_id == tenant_id,
                    TenantIntegration.connector_id == "notion",
                    TenantIntegration.is_active == True,
                )
                .first()
            )
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))

        # Round 45: fail CLOSED — reject when the integration/secret is not
        # configured (previously the HMAC check was skipped entirely).
        if not integration or not integration.config or not integration.config.get("client_secret"):
            logger.error(f"Notion signing secret not configured for tenant {tenant_id}")
            raise HTTPException(status_code=503, detail="Webhook verification not configured")

        client_secret = integration.config.get("client_secret")
        if not verify_hmac_signature(payload, x_notion_signature, client_secret):
            logger.error(f"Unauthorized Notion webhook for tenant {tenant_id}")
            raise HTTPException(status_code=401, detail="Invalid signature")

        # 4.5. Resolve source_connection_id for BYOK credential lookup
        source_connection_id = None
        try:
            from sqlalchemy import text
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = off"))
            try:
                conn = (
                    db.query(UserConnection)
                    .filter(
                        UserConnection.tenant_id == tenant_id,
                        UserConnection.integration_id == "notion",
                        UserConnection.status == "active",
                    )
                    .order_by(UserConnection.updated_at.desc())
                    .first()
                )
                if conn:
                    source_connection_id = str(conn.id)
            finally:
                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = on"))
        except Exception as e:
            logger.warning(f"Notion webhook: Failed to resolve source_connection_id: {e}")

        # CRUD Dispatch handling
        from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
        change_type, resource_id = extract_crud_metadata("notion", event_data, dict(request.headers), dict(request.query_params))
        if not change_type or not resource_id:
            change_type = change_type or "created"
            resource_id = resource_id or "generic"

        result = await crud_dispatch(
            db=db,
            change_type=change_type,
            integration_id="notion",
            tenant_id=tenant_id,
            resource_id=resource_id,
            payload=event_data,
            source_connection_id=source_connection_id,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notion webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Outlook Webhook Handler
# ============================================================================


@router.api_route("/webhooks/communication/outlook", methods=["POST", "GET"])
async def outlook_webhook_handler(
    request: Request,
    validationToken: str = Header(None),  # Microsoft Graph handshake
    db: Session = Depends(get_db),
):
    """
    Handle Outlook (Microsoft Graph) webhook and trigger ingestion.

    Supports:
        pass
    1. Validation handshake (validationToken)
    2. Change notifications for Mail, Calendar, and Drive
    3. Tenant resolution via clientState (standardized as tenant_id)
    4. Async processing via WebhookIngestionQueue
    """
    logger.info("[OUTLOOK_WEBHOOK_START] Handler called at /api/webhooks/communication/outlook")
    logger.info(f"[OUTLOOK_WEBHOOK] Host: {request.headers.get('host')}")
    logger.info(f"[OUTLOOK_WEBHOOK] URL: {request.url.path}")

    try:
        # 1. Handle Handshake
        # During subscription creation, Graph sends a validationToken to verify the endpoint
        params = request.query_params
        validation_token = params.get("validationToken")
        if validation_token:
            logger.info("Handling Outlook webhook validation handshake")
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse(content=validation_token)

        # 2. Process Notifications
        # Check for empty body first (lifecycle notifications from Microsoft)
        content_length = request.headers.get("content-length", "0")
        if not content_length or int(content_length) == 0:
            logger.info("[OUTLOOK_WEBHOOK] Empty request body - lifecycle notification, ignoring")
            return {"status": "ignored", "reason": "empty_body_lifecycle_notification"}

        try:
            payload = await request.json()
        except Exception as e:
            logger.warning(f"[OUTLOOK_WEBHOOK] Failed to parse JSON payload: {e}")
            return {"status": "error", "message": "invalid_json"}

        notifications = payload.get("value", [])

        logger.info(f"[OUTLOOK_WEBHOOK] Received {len(notifications)} notifications")

        if not notifications:
            logger.warning("[OUTLOOK_WEBHOOK] Empty notification payload")
            return {"status": "ignored", "reason": "empty_payload"}

        processed_jobs = []

        for idx, notification in enumerate(notifications):
            logger.info(f"[OUTLOOK_WEBHOOK] Processing notification {idx + 1}/{len(notifications)}")

            # BRUTAL DEBUGGING: Wrap entire loop in try/except
            try:
                pass
                # 1. Log raw notification payload
                logger.info(f"[OUTLOOK_WEBHOOK] Notification keys: {list(notification.keys())}")

                # 2. Extract clientState
                client_state_signed = notification.get("clientState")

                if not client_state_signed:
                    logger.warning("Outlook notification missing clientState")
                    continue

                # 3. Verify/decrypt clientState
                from core.webhook_security import get_client_state_data, verify_client_state

                is_valid = verify_client_state(client_state_signed)

                if not is_valid:
                    pass
                    # Round 46: FAIL CLOSED — previously this only logged a
                    # warning and processing continued (tenant resolution via
                    # the client-controlled Host header, connection lookup,
                    # enqueue, and even DiscoveredEntity deletion for forged
                    # "deleted" events). A forged clientState (valid JSON,
                    # no signature) was enough.
                    logger.warning(
                        f"Outlook clientState signature verification failed for: {client_state_signed[:20]}..."
                    )
                    continue

                client_state_raw = get_client_state_data(client_state_signed)

                # 4. Parse clientState JSON
                import json

                state_data = json.loads(client_state_raw)

                # 5. Resolve tenant from subdomain
                # Check X-Forwarded-Host first (set by Fly.io/Next.js proxy) before falling back to Host
                host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")

                subdomain = host.split(".")[0] if host else None

                if not subdomain:
                    logger.warning("Could not extract subdomain from request")
                    continue

                # 6. Database lookup (bypass RLS)
                from sqlalchemy import text

                from core.models import Tenant

                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = off"))

                tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()

                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = on"))


                if not tenant:
                    logger.warning(f"Could not find tenant for subdomain: {subdomain}")
                    continue

                tenant_id = str(tenant.id)

                # 6. Deletion detection & execution
                change_type = notification.get("changeType", "")
                resource_path = notification.get("resource", "")
                if "deleted" in change_type.lower():
                    message_id = None
                    if resource_path:
                        path_clean = resource_path.split("?")[0].strip("/")
                        message_id = path_clean.split("/")[-1]

                    if not message_id:
                        continue

                    if db.bind and db.bind.dialect.name == "postgresql":
                        db.execute(text("SET LOCAL row_security = off"))

                    try:
                        entities = (
                            db.query(DiscoveredEntity)
                            .filter(
                                DiscoveredEntity.tenant_id == tenant_id,
                                DiscoveredEntity.source_record_id == message_id,
                                DiscoveredEntity.source_record_type == "outlook",
                            )
                            .all()
                        )
                        for entity in entities:
                            db.delete(entity)
                        db.commit()
                    except Exception as db_err:
                        db.rollback()
                        logger.error(f"Failed during DB deletion of Outlook entities: {db_err}")
                    finally:
                        if db.bind and db.bind.dialect.name == "postgresql":
                            db.execute(text("SET LOCAL row_security = on"))

                    continue

                # 6b. Resolve connection from clientState prefix
                from sqlalchemy import String, cast

                from core.models import UserConnection

                connection_prefix = state_data.get("c", "")
                source_connection_id = None
                if connection_prefix:
                    pass
                    # RLS is still off from tenant lookup
                    # Cast UUID to text for LIKE comparison (PostgreSQL limitation)
                    connection = (
                        db.query(UserConnection)
                        .filter(
                            UserConnection.tenant_id == tenant_id,
                            UserConnection.integration_id == "outlook",
                            cast(UserConnection.id, String).like(f"{connection_prefix}%"),
                            UserConnection.status == "active",
                        )
                        .first()
                    )
                    if connection:
                        source_connection_id = str(connection.id)
                    else:
                        pass

                # 7. Enqueue to Redis

                # Verify Redis client before enqueue

                job_id = await webhook_queue.enqueue_ingestion_job(
                    tenant_id=tenant_id,
                    integration_id="outlook",
                    trigger_type="webhook",
                    payload=notification,
                    source_connection_id=source_connection_id,
                )

                # Check queue depth immediately after enqueue
                queue_depth = await webhook_queue.get_queue_depth()

                logger.info(f"[OUTLOOK_WEBHOOK] Successfully enqueued job {job_id}")
                processed_jobs.append(job_id)

                # 8. Trigger the governed email agent for message notifications.
                # Replaces the scripted outlook_automation_service loop: the
                # agent itself triages and drafts via MCP tools, and every send
                # flows through the harness (capability -> sandbox -> HITL ->
                # deterministic email policy). Fire-and-forget; never blocks the
                # webhook response.
                if "message" in (resource_path or "").lower():
                    try:
                        from core.email_agent import dispatch_for_incoming_email

                        resource_data = notification.get("resourceData") or {}
                        # Best-effort sender extraction (Graph message create
                        # notifications may carry `from`/`sender`); passed as
                        # an untrusted hint — validated before any agent run.
                        sender_hint = ""
                        if isinstance(resource_data, dict):
                            _from = resource_data.get("from") or resource_data.get("sender")
                            if isinstance(_from, dict):
                                sender_hint = (
                                    _from.get("emailAddress")
                                    if isinstance(_from.get("emailAddress"), str)
                                    else (_from.get("emailAddress") or {}).get("address")
                                    if isinstance(_from.get("emailAddress"), dict)
                                    else _from.get("address")
                                ) or ""
                            elif isinstance(_from, str):
                                sender_hint = _from
                        asyncio.create_task(
                            dispatch_for_incoming_email(
                                tenant_id=tenant_id,
                                workspace_id=(
                                    getattr(connection, "workspace_id", None) or "default"
                                ),
                                user_id=(
                                    getattr(connection, "user_id", None) or "default_user"
                                ),
                                subject_hint=(
                                    resource_data.get("subject") if isinstance(resource_data, dict) else ""
                                ) or "",
                                resource_hint=resource_path,
                                sender_hint=sender_hint or "",
                            )
                        )
                    except Exception as _agent_trigger_err:
                        logger.warning(
                            f"[OUTLOOK_WEBHOOK] email agent trigger failed: {_agent_trigger_err}"
                        )


            except Exception as e:
                logger.error(
                    f"[OUTLOOK_WEBHOOK] CRASH in loop iteration {idx + 1}: {e}", exc_info=True
                )

        logger.info(f"[OUTLOOK_WEBHOOK] Completed processing notifications")
        return {"status": "enqueued", "job_count": len(processed_jobs), "job_ids": processed_jobs}

    except Exception as e:
        logger.error(f"Outlook webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Zoho Suite Webhook Handlers
# ============================================================================

ZOHO_INTEGRATIONS = {
    "zoho_crm",
    "zoho_books",
    "zoho_inventory",
    "zoho_projects",
    "zoho_desk",
    "zoho_recruit",
    "zoho_campaigns",
    "zoho_forms",
    "zoho_showtime",
    "zoho_meeting",
    "zoho_assist",
}


@router.post("/webhooks/zoho/{integration_id}")
async def zoho_webhook_handler(
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Zoho suite webhooks and trigger ingestion.

    Supports zoho_crm, zoho_books, zoho_inventory, zoho_projects, zoho_desk,
    zoho_recruit, zoho_campaigns, zoho_forms, zoho_showtime, zoho_meeting,
    and zoho_assist.

    Extracts external Zoho org_id/portal_id to resolve tenant_id using Discovery Service,
    and enqueues the payload to WebhookIngestionQueue.
    """
    # R89: fail-closed shared-secret verification (see _verify_family_webhook)
    await _verify_family_webhook(request, "ATOM_ZOHO_WEBHOOK_SECRET", "Zoho")

    # Normalize integration_id with underscore
    integration_id = integration_id.replace("-", "_")
    if integration_id not in ZOHO_INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported Zoho integration: {integration_id}")

    try:
        payload = await request.json()
    except Exception:
        pass
        # Fallback if body is not valid JSON
        payload = {}

    # 1. Resolve org_id / portal_id from payload for tenant discovery
    org_id = None
    if isinstance(payload, dict):
        org_id = (
            payload.get("orgId")
            or payload.get("organization_id")
            or payload.get("org_id")
            or payload.get("portalId")
            or payload.get("portal_id")
            or payload.get("organization", {}).get("organization_id")
        )

    if not org_id:
        pass
        # Check inside first item if payload is a list
        if isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], dict):
            org_id = payload[0].get("orgId") or payload[0].get("organization_id")

    if not org_id:
        logger.warning(f"Zoho webhook {integration_id} missing organization identifier")
        raise HTTPException(status_code=400, detail="Missing organization identifier (orgId or organization_id)")

    # 2. Resolve tenant using Discovery Service
    discoverer = TenantDiscoveryService(db)
    # The external_id registered in TenantIntegration/Discovery is the org_id/portal_id
    tenant_id = await discoverer.get_tenant_id_by_external_id(integration_id, str(org_id))

    if not tenant_id:
        pass
        # Fallback: check if we can resolve using the generic "zoho" base connector ID
        tenant_id = await discoverer.get_tenant_id_by_external_id("zoho", str(org_id))

    if not tenant_id:
        logger.warning(f"No tenant found for Zoho {integration_id} org_id: {org_id}")
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 3. Resolve source_connection_id for BYOK credential lookup
    # This is critical for transformers that need to fetch provider resources
    # and for LLM BYOK context. Without this, BYOK tenants get "No credentials available".
    # Zoho is tenant-scoped (org-level), so any active connection works.
    source_connection_id = None
    try:
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.tenant_id == tenant_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.status == "active",
                )
                .order_by(UserConnection.updated_at.desc())
                .first()
            )
            if conn:
                source_connection_id = str(conn.id)
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))
    except Exception as e:
        logger.warning(f"Zoho {integration_id} webhook: Failed to resolve source_connection_id: {e}")

    # 4. CRUD Dispatch handling
    from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
    change_type, resource_id = extract_crud_metadata(integration_id, payload, dict(request.headers), dict(request.query_params))
    if not change_type or not resource_id:
        change_type = change_type or "created"
        resource_id = resource_id or "generic"

    result = await crud_dispatch(
        db=db,
        change_type=change_type,
        integration_id=integration_id,
        tenant_id=tenant_id,
        resource_id=resource_id,
        payload=payload,
        source_connection_id=source_connection_id,
    )
    return result


# ============================================================================
# Project Management & CRM Webhook Handlers (Batch 2B)
# ============================================================================

PM_CRM_INTEGRATIONS = {
    "jira",
    "asana",
    "trello",
    "monday",
    "clickup",
    "linear",
    "pipedrive",
    "zendesk_sell",
    "insightly",
    "freshsales",
}


@router.api_route("/webhooks/pm-crm/{integration_id}", methods=["POST", "HEAD"])
async def pm_crm_webhook_handler(
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle webhooks for Project Management and CRM suite integrations and trigger ingestion.

    Supports: jira, asana, trello, monday, clickup, linear, pipedrive,
    zendesk_sell, insightly, and freshsales.

    Resolves external organization/workspace identifiers to tenant_id using the
    Discovery Service, manages handshakes (Asana X-Hook-Secret, Monday challenge, Trello HEAD),
    and enqueues the payload to WebhookIngestionQueue.
    """
    from fastapi import Response

    # 1. Handle Trello / generic HEAD handshakes
    if request.method == "HEAD":
        return Response(status_code=200)

    # R89: fail-closed shared-secret verification
    await _verify_family_webhook(request, "ATOM_PMCRM_WEBHOOK_SECRET", "PM/CRM")

    # Normalize integration_id with underscore
    integration_id = integration_id.replace("-", "_")
    if integration_id not in PM_CRM_INTEGRATIONS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported Project Management / CRM integration: {integration_id}"
        )

    # 2. Handle Asana X-Hook-Secret handshake header
    x_hook_secret = request.headers.get("X-Hook-Secret")
    if x_hook_secret:
        return Response(status_code=200, headers={"X-Hook-Secret": x_hook_secret})

    try:
        payload = await request.json()
    except Exception:
        pass
        # Fallback if body is not valid JSON
        payload = {}

    # 3. Handle Monday challenge handshake in payload
    if isinstance(payload, dict) and "challenge" in payload:
        return {"challenge": payload["challenge"]}

    # 4. Resolve external organization/workspace identifier from payload
    external_id = None
    if isinstance(payload, dict):
        external_id = (
            # Monday account
            payload.get("accountId")
            or (payload.get("event", {}) or {}).get("accountId")
            # Linear organization
            or payload.get("organizationId")
            # Pipedrive company
            or payload.get("company_id")
            # ClickUp workspace or webhook reference
            or payload.get("team_id")
            or payload.get("webhook_id")
            # Zendesk Sell account
            or payload.get("account_id")
            # Insightly organization
            or payload.get("insightly_org_id")
            # Freshsales account
            or payload.get("account_id")
            # Jira client key or base URL
            or payload.get("clientKey")
            or (payload.get("serverInfo", {}) or {}).get("baseUrl")
            # Trello board/organization
            or (payload.get("model", {}) or {}).get("idOrganization")
            or (payload.get("model", {}) or {}).get("id")
            # Asana workspace
            or (
                payload.get("events", [{}])[0]
                if isinstance(payload.get("events"), list) and len(payload.get("events")) > 0
                else {}
            ).get("workspace")
        )

    # Fallback to query parameters
    query_params = dict(request.query_params)
    if not external_id:
        external_id = (
            query_params.get("org_id")
            or query_params.get("workspace_id")
            or query_params.get("accountId")
            or query_params.get("clientKey")
        )

    # 5. Resolve tenant using Discovery Service
    tenant_id = None
    if external_id:
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id(integration_id, str(external_id))

        if not tenant_id:
            pass
            # Fallback: check if we can resolve using the generic "pm_crm" base connector ID
            tenant_id = await discoverer.get_tenant_id_by_external_id("pm_crm", str(external_id))

    # Security: do NOT fall back to tenant_id from query params — that would
    # allow an attacker to inject webhooks into any tenant (cross-tenant
    # injection). If tenant resolution failed above, the request is rejected below.

    if not tenant_id:
        logger.warning(
            f"No tenant found for PM/CRM {integration_id} with external_id: {external_id}"
        )
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 5.5. Resolve source_connection_id for BYOK credential lookup
    # This is critical for transformers that need to fetch provider resources
    # and for LLM BYOK context. Without this, BYOK tenants get "No credentials available".
    # PM_CRM integrations are tenant-scoped (workspace/org level), so any active connection works.
    source_connection_id = None
    try:
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.tenant_id == tenant_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.status == "active",
                )
                .order_by(UserConnection.updated_at.desc())
                .first()
            )
            if conn:
                source_connection_id = str(conn.id)
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))
    except Exception as e:
        logger.warning(f"PM/CRM {integration_id} webhook: Failed to resolve source_connection_id: {e}")

    # 6. CRUD Dispatch handling
    from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
    change_type, resource_id = extract_crud_metadata(integration_id, payload, dict(request.headers), dict(request.query_params))
    if not change_type or not resource_id:
        change_type = change_type or "created"
        resource_id = resource_id or "generic"

    result = await crud_dispatch(
        db=db,
        change_type=change_type,
        integration_id=integration_id,
        tenant_id=tenant_id,
        resource_id=resource_id,
        payload=payload,
        source_connection_id=source_connection_id,
    )
    return result


# ============================================================================
# Communication Webhook Handlers (Batch 2C)
# ============================================================================

COMMUNICATION_INTEGRATIONS = {
    "discord",
    "teams",
    "telegram",
    "twilio",
    "intercom",
}


@router.api_route("/webhooks/communication/{integration_id}", methods=["POST", "HEAD"])
async def communication_webhook_handler(
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle webhooks for Communication suite integrations and trigger ingestion.

    Supports: discord, teams, telegram, twilio, and intercom.

    Resolves external tenant context using Discovery Service, manages payload formats
    (handles application/json and application/x-www-form-urlencoded for Twilio),
    and enqueues the payload to WebhookIngestionQueue.
    """
    from fastapi import Response

    # 1. Handle HEAD handshakes
    if request.method == "HEAD":
        return Response(status_code=200)

    # R89: fail-closed shared-secret verification
    await _verify_family_webhook(request, "ATOM_COMMUNICATION_WEBHOOK_SECRET", "Communication")

    # Normalize integration_id with underscore
    integration_id = integration_id.replace("-", "_")
    if integration_id not in COMMUNICATION_INTEGRATIONS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported Communication integration: {integration_id}"
        )

    # 2. Parse payload based on Content-Type (important for Twilio form bodies)
    content_type = request.headers.get("content-type", "")
    payload = {}
    if "application/x-www-form-urlencoded" in content_type:
        try:
            form_data = await request.form()
            payload = dict(form_data)
        except Exception:
            payload = {}
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    # 3. Resolve external organization/channel/workspace identifier from payload
    external_id = None
    if isinstance(payload, dict):
        external_id = (
            # Twilio account
            payload.get("AccountSid")
            # Intercom app
            or payload.get("app_id")
            # Teams tenant
            or payload.get("tenantId")
            or (payload.get("conversation", {}) or {}).get("tenantId")
            or (payload.get("channelData", {}) or {}).get("tenant", {}).get("id")
            # Telegram chat
            or (payload.get("message", {}) or {}).get("chat", {}).get("id")
            or (payload.get("edited_message", {}) or {}).get("chat", {}).get("id")
            # Discord guild/channel
            or payload.get("guild_id")
            or payload.get("channel_id")
        )

    # Fallback to query parameters
    query_params = dict(request.query_params)
    if not external_id:
        external_id = (
            query_params.get("account_sid")
            or query_params.get("app_id")
            or query_params.get("chat_id")
            or query_params.get("guild_id")
        )

    # 4. Resolve tenant using Discovery Service
    tenant_id = None
    if external_id:
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id(integration_id, str(external_id))

        if not tenant_id:
            pass
            # Fallback: check if we can resolve using the generic "communication" base connector ID
            tenant_id = await discoverer.get_tenant_id_by_external_id("communication", str(external_id))

    # Security: do NOT fall back to tenant_id from query params — that would
    # allow an attacker to inject webhooks into any tenant (cross-tenant
    # injection). If tenant resolution failed above, the request is rejected below.

    if not tenant_id:
        logger.warning(
            f"No tenant found for Communication {integration_id} with external_id: {external_id}"
        )
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 4.5. Resolve source_connection_id for BYOK credential lookup
    # This is critical for transformers that need to fetch provider resources
    # and for LLM BYOK context. Without this, BYOK tenants get "No credentials available".
    # Communication integrations are tenant-scoped, so any active connection works.
    source_connection_id = None
    try:
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.tenant_id == tenant_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.status == "active",
                )
                .order_by(UserConnection.updated_at.desc())
                .first()
            )
            if conn:
                source_connection_id = str(conn.id)
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))
    except Exception as e:
        logger.warning(f"Communication {integration_id} webhook: Failed to resolve source_connection_id: {e}")

    # 5. CRUD Dispatch handling
    from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
    change_type, resource_id = extract_crud_metadata(integration_id, payload, dict(request.headers), dict(request.query_params))
    if not change_type or not resource_id:
        change_type = change_type or "created"
        resource_id = resource_id or "generic"

    result = await crud_dispatch(
        db=db,
        change_type=change_type,
        integration_id=integration_id,
        tenant_id=tenant_id,
        resource_id=resource_id,
        payload=payload,
        source_connection_id=source_connection_id,
    )
    return result


# ============================================================================
# Dev & Productivity Webhook Handlers (Batch 2D)
# ============================================================================

DEV_PROD_INTEGRATIONS = {
    "github",
    "gitlab",
    "bitbucket",
    "google_drive",
    "dropbox",
    "box",
    "onedrive",
    "salesloft",
}


@router.api_route("/webhooks/dev-prod/{integration_id}", methods=["POST", "GET"])
async def dev_prod_webhook_handler(
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle webhooks for Dev & Productivity suite integrations and trigger ingestion.

    Supports: github, gitlab, bitbucket, google_drive, dropbox, box, onedrive, and salesloft.

    Resolves external tenant context using Discovery Service, manages handshakes
    (Dropbox GET challenge, OneDrive GET/POST validationToken, GitHub ping),
    and enqueues the payload to WebhookIngestionQueue.
    """
    from fastapi.responses import PlainTextResponse

    # 1. Dropbox validation challenge handshake
    challenge = request.query_params.get("challenge")
    if challenge:
        return PlainTextResponse(content=challenge)

    # 2. OneDrive (Microsoft Graph) validation token handshake
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return PlainTextResponse(content=validation_token)

    # R89: fail-closed shared-secret verification
    await _verify_family_webhook(request, "ATOM_DEVPROD_WEBHOOK_SECRET", "Dev/Productivity")

    # Normalize integration_id with underscore
    integration_id = integration_id.replace("-", "_")
    if integration_id not in DEV_PROD_INTEGRATIONS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported Dev/Productivity integration: {integration_id}"
        )

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # 3. GitHub ping check handshake
    if request.headers.get("X-GitHub-Event") == "ping" or payload.get("zen"):
        return {"status": "ok", "zen": payload.get("zen", "Active")}

    # 4. Resolve external organization/workspace/path identifier from payload
    external_id = None
    if isinstance(payload, dict):
        external_id = (
            # GitHub organization/owner
            (payload.get("organization", {}) or {}).get("login")
            or (payload.get("organization", {}) or {}).get("id")
            or (payload.get("repository", {}) or {}).get("owner", {}).get("login")
            or (payload.get("repository", {}) or {}).get("owner", {}).get("id")
            # GitLab path/project
            or (payload.get("project", {}) or {}).get("path_with_namespace")
            or (payload.get("project", {}) or {}).get("id")
            # Bitbucket workspace/repo
            or (payload.get("repository", {}) or {}).get("workspace", {}).get("uuid")
            or (payload.get("repository", {}) or {}).get("uuid")
            # Google Drive channel
            or payload.get("channelId")
            or payload.get("resourceId")
            # Dropbox accounts
            or (
                payload.get("accounts", [""])[0]
                if isinstance(payload.get("accounts"), list) and len(payload.get("accounts")) > 0
                else None
            )
            # Box enterprise
            or (payload.get("enterprise", {}) or {}).get("id")
            # OneDrive clientState
            or (
                payload.get("value", [{}])[0]
                if isinstance(payload.get("value"), list) and len(payload.get("value")) > 0
                else {}
            ).get("clientState")
            # Salesloft tenant
            or payload.get("tenant_id")
            or payload.get("account_id")
        )

    # Fallback to query parameters
    query_params = dict(request.query_params)
    if not external_id:
        external_id = (
            query_params.get("org_id")
            or query_params.get("workspace_id")
            or query_params.get("clientState")
        )

    # 5. Resolve tenant using Discovery Service
    tenant_id = None
    if external_id:
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id(integration_id, str(external_id))

        if not tenant_id:
            pass
            # Fallback: check if we can resolve using the generic "dev_prod" base connector ID
            tenant_id = await discoverer.get_tenant_id_by_external_id("dev_prod", str(external_id))

    # Security: do NOT fall back to tenant_id from query params — that would
    # allow an attacker to inject webhooks into any tenant (cross-tenant
    # injection). If tenant resolution failed above, the request is rejected below.

    if not tenant_id:
        logger.warning(
            f"No tenant found for Dev/Prod {integration_id} with external_id: {external_id}"
        )
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 5.5. Resolve source_connection_id for BYOK credential lookup
    # This is critical for transformers that need to fetch provider resources
    # and for LLM BYOK context. Without this, BYOK tenants get "No credentials available".
    # Dev & Productivity integrations are tenant-scoped, so any active connection works.
    source_connection_id = None
    try:
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.tenant_id == tenant_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.status == "active",
                )
                .order_by(UserConnection.updated_at.desc())
                .first()
            )
            if conn:
                source_connection_id = str(conn.id)
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))
    except Exception as e:
        logger.warning(f"Dev/Prod {integration_id} webhook: Failed to resolve source_connection_id: {e}")

    # 6. CRUD Dispatch handling
    from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
    change_type, resource_id = extract_crud_metadata(integration_id, payload, dict(request.headers), dict(request.query_params))
    if not change_type or not resource_id:
        change_type = change_type or "created"
        resource_id = resource_id or "generic"

    result = await crud_dispatch(
        db=db,
        change_type=change_type,
        integration_id=integration_id,
        tenant_id=tenant_id,
        resource_id=resource_id,
        payload=payload,
        source_connection_id=source_connection_id,
    )
    return result


# ============================================================================
# E-commerce, Marketing & Other Webhook Handlers (Batch 2E)
# ============================================================================

ECOMMERCE_MARKETING_INTEGRATIONS = {
    "shopify",
    "woocommerce",
    "bigcommerce",
    "magento",
    "stripe",
    "mailchimp",
    "activecampaign",
    "sendgrid",
    "convertkit",
    "getresponse",
    "airtable",
    "webex",
    "zoom",
    "freshdesk",
    "figma",
}


@router.api_route(
    "/webhooks/ecommerce-marketing/{integration_id}", methods=["POST", "GET", "HEAD"]
)
async def ecommerce_marketing_webhook_handler(
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle webhooks for E-commerce, Marketing & Other integrations and trigger ingestion.

    Supports: shopify, woocommerce, bigcommerce, magento, stripe, mailchimp, activecampaign,
    sendgrid, convertkit, getresponse, airtable, webex, zoom, freshdesk, and figma.

    Resolves external tenant context using Discovery Service, manages handshakes
    (Zoom verification tokens, Mailchimp GET validations), and enqueues to WebhookIngestionQueue.
    """
    from fastapi import Response

    # 1. Handle HEAD request
    if request.method == "HEAD":
        return Response(status_code=200)

    # 2. Handle GET request validation check (e.g. Mailchimp webhook setup validation)
    if request.method == "GET":
        return Response(status_code=200)

    # Normalize integration_id with underscore
    integration_id = integration_id.replace("-", "_")
    if integration_id not in ECOMMERCE_MARKETING_INTEGRATIONS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported E-commerce/Marketing integration: {integration_id}"
        )

    # 3. Parse payload based on Content-Type (important for Mailchimp form bodies)
    content_type = request.headers.get("content-type", "")
    payload = {}
    if "application/x-www-form-urlencoded" in content_type:
        try:
            form_data = await request.form()
            payload = dict(form_data)
        except Exception:
            payload = {}
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    # 4. Zoom URL validation handshake
    if isinstance(payload, dict) and payload.get("event") == "endpoint.url_validation":
        plain_token = payload.get("payload", {}).get("plainToken", "")
        return {"plainToken": plain_token, "encryptedToken": plain_token}

    # 5. Resolve external organization/workspace/store identifier from payload
    external_id = None
    if isinstance(payload, dict):
        external_id = (
            # Shopify shop domain or account
            payload.get("domain")
            or payload.get("shop_id")
            # WooCommerce shop URL
            or payload.get("store_url")
            # BigCommerce store hash
            or payload.get("store_hash")
            or payload.get("producer")
            # Magento store code
            or payload.get("store_id")
            # Stripe account/livemode
            or payload.get("account")
            # Mailchimp list ID
            or (payload.get("data", {}) or {}).get("list_id")
            # ActiveCampaign account
            or payload.get("account")
            # ConvertKit account
            or payload.get("account_name")
            # GetResponse campaign
            or (payload.get("contact", {}) or {}).get("campaign_id")
            # Airtable base/webhook
            or payload.get("base_id")
            or payload.get("webhookId")
            # Webex org/space
            or payload.get("orgId")
            # Zoom account
            or payload.get("accountId")
            # Freshdesk domain
            or payload.get("domain")
            # Figma team/webhook
            or payload.get("team_id")
        )
    elif isinstance(payload, list) and len(payload) > 0:
        pass
        # SendGrid sends batch event arrays
        first_event = payload[0]
        if isinstance(first_event, dict):
            external_id = first_event.get("useragent") or first_event.get("ip")

    # Fallback to query parameters
    query_params = dict(request.query_params)
    if not external_id:
        external_id = (
            query_params.get("store_id")
            or query_params.get("account_id")
            or query_params.get("list_id")
        )

    # 6. Resolve tenant using Discovery Service
    tenant_id = None
    if external_id:
        discoverer = TenantDiscoveryService(db)
        tenant_id = await discoverer.get_tenant_id_by_external_id(integration_id, str(external_id))

        if not tenant_id:
            pass
            # Fallback: check if we can resolve using the generic "ecommerce_marketing" base connector ID
            tenant_id = await discoverer.get_tenant_id_by_external_id(
                "ecommerce_marketing", str(external_id)
            )

    # Security: do NOT fall back to tenant_id from query params — that would
    # allow an attacker to inject webhooks into any tenant (cross-tenant
    # injection). If tenant resolution failed above, the request is rejected below.

    if not tenant_id:
        logger.warning(
            f"No tenant found for E-commerce/Marketing {integration_id} with external_id: {external_id}"
        )
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 6.5. Resolve source_connection_id for BYOK credential lookup
    # This is critical for transformers that need to fetch provider resources
    # and for LLM BYOK context. Without this, BYOK tenants get "No credentials available".
    # E-commerce & Marketing integrations are tenant-scoped, so any active connection works.
    source_connection_id = None
    try:
        from sqlalchemy import text
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            conn = (
                db.query(UserConnection)
                .filter(
                    UserConnection.tenant_id == tenant_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.status == "active",
                )
                .order_by(UserConnection.updated_at.desc())
                .first()
            )
            if conn:
                source_connection_id = str(conn.id)
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))
    except Exception as e:
        logger.warning(f"E-commerce/Marketing {integration_id} webhook: Failed to resolve source_connection_id: {e}")

    # 7. CRUD Dispatch handling
    from core.webhook_crud_dispatch import extract_crud_metadata, crud_dispatch
    change_type, resource_id = extract_crud_metadata(integration_id, payload, dict(request.headers), dict(request.query_params))
    if not change_type or not resource_id:
        change_type = change_type or "created"
        resource_id = resource_id or "generic"

    result = await crud_dispatch(
        db=db,
        change_type=change_type,
        integration_id=integration_id,
        tenant_id=tenant_id,
        resource_id=resource_id,
        payload=payload,
        source_connection_id=source_connection_id,
    )
    return result





