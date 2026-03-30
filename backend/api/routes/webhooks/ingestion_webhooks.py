"""
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

import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import UserConnection, TenantIntegration
from core.webhook_ingestion_triggers import WebhookIngestionQueue
from api.routes.webhooks.base import verify_hmac_signature
from core.tenant_discovery import TenantDiscoveryService
from core.structured_logger import get_logger

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
    db: Session = Depends(get_db)
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
        integration = db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.connector_id == "slack",
            TenantIntegration.is_active == True
        ).first()

        if integration and integration.config:
            signing_secret = integration.config.get("slack_signing_secret")
            if signing_secret:
                if not verify_hmac_signature(payload, x_slack_signature, signing_secret):
                    logger.error(f"Unauthorized Slack webhook for tenant {tenant_id}")
                    raise HTTPException(status_code=401, detail="Invalid signature")

        # 5. Enqueue ingestion job
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id="slack",
            trigger_type="webhook",
            payload=event_data
        )

        logger.info(
            f"Slack webhook enqueued for ingestion",
            tenant_id=tenant_id,
            team_id=team_id,
            job_id=job_id
        )

        return {"status": "enqueued", "job_id": job_id}

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
    request: Request,
    x_hubspot_signature: str = Header(None),
    db: Session = Depends(get_db)
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
            integration = db.query(TenantIntegration).filter(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.connector_id == "hubspot",
                TenantIntegration.is_active == True
            ).first()

            if integration and integration.config:
                client_secret = integration.config.get("client_secret")
                if client_secret:
                    import hashlib
                    if not verify_hmac_signature(payload, x_hubspot_signature, client_secret, algorithm=hashlib.sha256):
                        logger.error(f"Unauthorized HubSpot webhook for tenant {tenant_id}")
                        raise HTTPException(status_code=401, detail="Invalid signature")

            # Enqueue ingestion job
            job_id = await webhook_queue.enqueue_ingestion_job(
                tenant_id=tenant_id,
                integration_id="hubspot",
                trigger_type="webhook",
                payload=event
            )

            logger.info(
                f"HubSpot webhook enqueued for ingestion",
                tenant_id=tenant_id,
                portal_id=portal_id,
                job_id=job_id
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
    request: Request,
    x_salesforce_signature: str = Header(None),
    db: Session = Depends(get_db)
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
        integration = db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.connector_id == "salesforce",
            TenantIntegration.is_active == True
        ).first()

        if integration and integration.config:
            client_secret = integration.config.get("client_secret")
            if client_secret:
                if not verify_hmac_signature(payload, x_salesforce_signature, client_secret):
                    logger.error(f"Unauthorized Salesforce webhook for tenant {tenant_id}")
                    raise HTTPException(status_code=401, detail="Invalid signature")

        # Enqueue ingestion job
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id="salesforce",
            trigger_type="webhook",
            payload=event_data
        )

        logger.info(
            f"Salesforce webhook enqueued for ingestion",
            tenant_id=tenant_id,
            org_id=org_id,
            job_id=job_id
        )

        return {"status": "enqueued", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Salesforce webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}


# ============================================================================
# Gmail Webhook Handler
# ============================================================================

@router.post("/webhooks/gmail/events")
async def gmail_webhook_handler(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Gmail push notification webhook and trigger ingestion.

    Gmail uses Google's Pub/Sub authentication instead of HMAC.
    Extracts tenant_id from email_address and enqueues ingestion job.

    Returns 200 OK immediately to avoid Google retry issues.
    """
    try:
        # Gmail push notification payload
        event_data = await request.json()

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

        # Enqueue ingestion job
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id="gmail",
            trigger_type="webhook",
            payload=event_data
        )

        logger.info(
            f"Gmail webhook enqueued for ingestion",
            tenant_id=tenant_id,
            email_address=email_address,
            job_id=job_id
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
    request: Request,
    x_notion_signature: str = Header(None),
    db: Session = Depends(get_db)
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
        integration = db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.connector_id == "notion",
            TenantIntegration.is_active == True
        ).first()

        if integration and integration.config:
            client_secret = integration.config.get("client_secret")
            if client_secret:
                if not verify_hmac_signature(payload, x_notion_signature, client_secret):
                    logger.error(f"Unauthorized Notion webhook for tenant {tenant_id}")
                    raise HTTPException(status_code=401, detail="Invalid signature")

        # Enqueue ingestion job
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id="notion",
            trigger_type="webhook",
            payload=event_data
        )

        logger.info(
            f"Notion webhook enqueued for ingestion",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            job_id=job_id
        )

        return {"status": "enqueued", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Notion webhook handler error: {e}")
        return {"status": "error", "message": "Webhook processing failed"}
