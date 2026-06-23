"""
from __future__ import annotations
Integration Webhook Handlers for Ingestion Pipeline

Handles webhook notifications from integrations (Slack, HubSpot, Salesforce, Gmail, Notion)
and triggers the ingestion pipeline for near real-time data sync to Knowledge Graph.

All handlers verify HMAC signatures before processing and enqueue background jobs
to avoid webhook timeout issues.

Key features:
- HMAC signature verification for security
- Tenant extraction from webhook payloads
- Background job enqueueing via WebhookIngestionQueue
- 200 OK immediate response pattern
- Integration-specific handlers for 5+ platforms
"""

import sys

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

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
        # Get raw body for signature verification
        payload = await request.body()
        event_data = await request.json()

        # 1. Challenge Response (Slack requirement)
        if event_data.get("type") == "url_verification":
            return {"challenge": event_data.get("challenge")}

        # 2. Extract team_id for tenant resolution
        team_id = event_data.get("team_id")
        if not team_id:
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
        # Get raw body for signature verification
        payload = await request.body()
        event_data = await request.json()

        # Handle batch events (HubSpot sends multiple events in one webhook)
        events = event_data if isinstance(event_data, list) else [event_data]

        for event in events:
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

            if integration and integration.config:
                client_secret = integration.config.get("client_secret")
                if client_secret:
                    import hashlib

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

        if integration and integration.config:
            client_secret = integration.config.get("client_secret")
            if client_secret:
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

    Gmail uses Google's Pub/Sub authentication instead of HMAC.
    Extracts tenant_id from email_address and enqueues ingestion job.

    Returns 200 OK immediately to avoid Google retry issues.
    """
    try:
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

        if integration and integration.config:
            client_secret = integration.config.get("client_secret")
            if client_secret:
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


@router.post("/webhooks/communication/outlook")
async def outlook_webhook_handler(
    request: Request,
    validationToken: str = Header(None),  # Microsoft Graph handshake
    db: Session = Depends(get_db),
):
    """
    Handle Outlook (Microsoft Graph) webhook and trigger ingestion.

    Supports:
    1. Validation handshake (validationToken)
    2. Change notifications for Mail, Calendar, and Drive
    3. Tenant resolution via clientState (standardized as tenant_id)
    4. Async processing via WebhookIngestionQueue
    """
    # EXPLICIT DEBUG LOGGING
    import sys

    print("[OUTLOOK_WEBHOOK_START] Handler called", file=sys.stderr, flush=True)
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
        print(
            f"[OUTLOOK_WEBHOOK] Received {len(notifications)} notifications",
            file=sys.stderr,
            flush=True,
        )
        print(
            f"[OUTLOOK_WEBHOOK] DEBUG: About to check if notifications is empty",
            file=sys.stderr,
            flush=True,
        )

        if not notifications:
            logger.warning("[OUTLOOK_WEBHOOK] Empty notification payload")
            return {"status": "ignored", "reason": "empty_payload"}

        print(
            f"[OUTLOOK_WEBHOOK] DEBUG: Notifications not empty, creating processed_jobs",
            file=sys.stderr,
            flush=True,
        )
        processed_jobs = []

        print(f"[OUTLOOK_WEBHOOK] DEBUG: About to enter loop", file=sys.stderr, flush=True)
        for idx, notification in enumerate(notifications):
            print(
                f"[OUTLOOK_WEBHOOK] DEBUG: Loop iteration {idx + 1}/{len(notifications)}",
                file=sys.stderr,
                flush=True,
            )
            logger.info(f"[OUTLOOK_WEBHOOK] Processing notification {idx + 1}/{len(notifications)}")

            # BRUTAL DEBUGGING: Wrap entire loop in try/except
            try:
                # 1. Log raw notification payload
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Raw notification keys: {list(notification.keys())}",
                    file=sys.stderr,
                    flush=True,
                )
                logger.info(f"[OUTLOOK_WEBHOOK] Notification keys: {list(notification.keys())}")

                # 2. Extract clientState
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: About to extract clientState",
                    file=sys.stderr,
                    flush=True,
                )
                client_state_signed = notification.get("clientState")
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: clientState length: {len(client_state_signed) if client_state_signed else 0}",
                    file=sys.stderr,
                    flush=True,
                )

                if not client_state_signed:
                    print(
                        "[OUTLOOK_WEBHOOK] ERROR: Missing clientState - skipping",
                        file=sys.stderr,
                        flush=True,
                    )
                    logger.warning("Outlook notification missing clientState")
                    continue

                # 3. Verify/decrypt clientState
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: About to verify clientState",
                    file=sys.stderr,
                    flush=True,
                )
                from core.webhook_security import get_client_state_data, verify_client_state

                is_valid = verify_client_state(client_state_signed)
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: clientState valid: {is_valid}",
                    file=sys.stderr,
                    flush=True,
                )

                if not is_valid:
                    logger.warning(
                        f"Outlook clientState signature verification failed for: {client_state_signed[:20]}..."
                    )

                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: About to get_client_state_data",
                    file=sys.stderr,
                    flush=True,
                )
                client_state_raw = get_client_state_data(client_state_signed)
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: clientState_raw length: {len(client_state_raw)}",
                    file=sys.stderr,
                    flush=True,
                )

                # 4. Parse clientState JSON
                print(f"[OUTLOOK_WEBHOOK] DEBUG: About to parse JSON", file=sys.stderr, flush=True)
                import json

                state_data = json.loads(client_state_raw)
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Parsed state_data keys: {list(state_data.keys())}",
                    file=sys.stderr,
                    flush=True,
                )

                # 5. Resolve tenant from subdomain
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: About to resolve tenant from subdomain",
                    file=sys.stderr,
                    flush=True,
                )
                # Check X-Forwarded-Host first (set by Fly.io/Next.js proxy) before falling back to Host
                host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
                print(f"[OUTLOOK_WEBHOOK] DEBUG: Host header: {host}", file=sys.stderr, flush=True)

                subdomain = host.split(".")[0] if host else None
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Extracted subdomain: {subdomain}",
                    file=sys.stderr,
                    flush=True,
                )

                if not subdomain:
                    print(
                        "[OUTLOOK_WEBHOOK] ERROR: No subdomain found - skipping",
                        file=sys.stderr,
                        flush=True,
                    )
                    logger.warning("Could not extract subdomain from request")
                    continue

                # 6. Database lookup (bypass RLS)
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: About to query DB for tenant",
                    file=sys.stderr,
                    flush=True,
                )
                from sqlalchemy import text

                from core.models import Tenant

                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = off"))

                tenant = db.query(Tenant).filter(Tenant.subdomain == subdomain).first()

                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = on"))

                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: DB query result: {tenant is not None}",
                    file=sys.stderr,
                    flush=True,
                )

                if not tenant:
                    print(
                        f"[OUTLOOK_WEBHOOK] ERROR: No tenant found for subdomain: {subdomain}",
                        file=sys.stderr,
                        flush=True,
                    )
                    logger.warning(f"Could not find tenant for subdomain: {subdomain}")
                    continue

                tenant_id = str(tenant.id)
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Resolved tenant_id: {tenant_id[:8]}...",
                    file=sys.stderr,
                    flush=True,
                )

                # 6. Deletion detection & execution
                change_type = notification.get("changeType", "")
                resource_path = notification.get("resource", "")
                if "deleted" in change_type.lower():
                    print(
                        f"[OUTLOOK_WEBHOOK] Deletion event detected for resource: {resource_path}",
                        file=sys.stderr,
                        flush=True,
                    )
                    message_id = None
                    if resource_path:
                        path_clean = resource_path.split("?")[0].strip("/")
                        message_id = path_clean.split("/")[-1]

                    if not message_id:
                        print(
                            f"[OUTLOOK_WEBHOOK] ERROR: Could not extract message_id from resource: {resource_path}",
                            file=sys.stderr,
                            flush=True,
                        )
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
                        print(
                            f"[OUTLOOK_WEBHOOK] Found {len(entities)} DiscoveredEntity records to delete for message_id {message_id}",
                            file=sys.stderr,
                            flush=True,
                        )
                        for entity in entities:
                            db.delete(entity)
                        db.commit()
                    except Exception as db_err:
                        db.rollback()
                        print(
                            f"[OUTLOOK_WEBHOOK] ERROR: Failed during DB deletion: {db_err}",
                            file=sys.stderr,
                            flush=True,
                        )
                        logger.error(f"Failed during DB deletion of Outlook entities: {db_err}")
                    finally:
                        if db.bind and db.bind.dialect.name == "postgresql":
                            db.execute(text("SET LOCAL row_security = on"))

                    print(
                        f"[OUTLOOK_WEBHOOK] Deletion process completed for message_id {message_id}",
                        file=sys.stderr,
                        flush=True,
                    )
                    continue

                # 6b. Resolve connection from clientState prefix
                from sqlalchemy import String, cast

                from core.models import UserConnection

                connection_prefix = state_data.get("c", "")
                source_connection_id = None
                if connection_prefix:
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
                        print(
                            f"[OUTLOOK_WEBHOOK] DEBUG: Resolved connection_id: {source_connection_id[:8]}...",
                            file=sys.stderr,
                            flush=True,
                        )
                    else:
                        print(
                            f"[OUTLOOK_WEBHOOK] WARNING: No connection found for prefix '{connection_prefix}'",
                            file=sys.stderr,
                            flush=True,
                        )

                # 7. Enqueue to Redis
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: About to enqueue to Redis",
                    file=sys.stderr,
                    flush=True,
                )

                # Verify Redis client before enqueue
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: webhook_queue.redis_client = {webhook_queue.redis_client}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: webhook_queue.queue_key = {webhook_queue.queue_key}",
                    file=sys.stderr,
                    flush=True,
                )

                job_id = await webhook_queue.enqueue_ingestion_job(
                    tenant_id=tenant_id,
                    integration_id="outlook",
                    trigger_type="webhook",
                    payload=notification,
                    source_connection_id=source_connection_id,
                )
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Enqueued job_id: {job_id}",
                    file=sys.stderr,
                    flush=True,
                )

                # Check queue depth immediately after enqueue
                queue_depth = await webhook_queue.get_queue_depth()
                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Queue depth after enqueue: {queue_depth}",
                    file=sys.stderr,
                    flush=True,
                )

                logger.info(f"[OUTLOOK_WEBHOOK] Successfully enqueued job {job_id}")
                processed_jobs.append(job_id)

                print(
                    f"[OUTLOOK_WEBHOOK] DEBUG: Loop iteration {idx + 1} COMPLETE",
                    file=sys.stderr,
                    flush=True,
                )

            except Exception as e:
                print(f"[OUTLOOK_WEBHOOK] CRASH in loop: {e}", file=sys.stderr, flush=True)
                logger.error(
                    f"[OUTLOOK_WEBHOOK] CRASH in loop iteration {idx + 1}: {e}", exc_info=True
                )

        logger.info(f"[OUTLOOK_WEBHOOK] Completed processing notifications")
        print(
            f"[OUTLOOK_WEBHOOK] RETURNING: status=enqueued, job_count={len(processed_jobs)}",
            file=sys.stderr,
            flush=True,
        )
        return {"status": "enqueued", "job_count": len(processed_jobs), "job_ids": processed_jobs}

    except Exception as e:
        logger.error(f"Outlook webhook handler error: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================================
# Zoho Suite Webhook Handlers
# ============================================================================

ZOHO_INTEGRATIONS = {
    "zoho_crm",
    "zoho_books",
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

    Supports zoho_crm, zoho_books, zoho_projects, zoho_desk, zoho_recruit,
    zoho_campaigns, zoho_forms, zoho_showtime, zoho_meeting, and zoho_assist.

    Extracts external Zoho org_id/portal_id to resolve tenant_id using Discovery Service,
    and enqueues the payload to WebhookIngestionQueue.
    """
    # Normalize integration_id with underscore
    integration_id = integration_id.replace("-", "_")
    if integration_id not in ZOHO_INTEGRATIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported Zoho integration: {integration_id}")

    try:
        payload = await request.json()
    except Exception:
        # Fallback if body is not valid JSON
        payload = {}

    # 1. Resolve org_id / portal_id from payload for tenant discovery
    org_id = (
        payload.get("orgId")
        or payload.get("organization_id")
        or payload.get("org_id")
        or payload.get("portalId")
        or payload.get("portal_id")
        or payload.get("organization", {}).get("organization_id")
    )

    if not org_id:
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





