from __future__ import annotations
"""
Mock Webhook Sender Utility

Provides utilities for sending mock webhook payloads to webhook endpoints
during testing. Supports signature generation for various providers.

**Usage:**
```python
from tests.webhooks.fixtures.mock_webhook_sender import send_mock_webhook

# Send a mock Slack webhook
response = send_mock_webhook("slack", payload, signing_secret="secret")

# Send a mock HubSpot webhook
response = send_mock_webhook("hubspot", payload, client_secret="secret")

# Send without signature (for testing signature validation)
response = send_mock_webhook("slack", payload, skip_signature=True)
```
"""

import hashlib
import hmac
import json
import time
from typing import Any, Optional

try:
    from requests import post
except ImportError:
    post = None  # Will skip HTTP tests if requests unavailable


# =============================================================================
# Signature Generators
# =============================================================================

def generate_slack_signature(
    payload: bytes | str,
    signing_secret: str,
    timestamp: Optional[str] = None,
) -> tuple[str, str]:
    """
    Generate Slack webhook signature.

    Args:
        payload: Request body (bytes or string)
        signing_secret: Slack app signing secret
        timestamp: Optional timestamp string (default: current time)

    Returns:
        Tuple of (timestamp, signature)
    """
    if timestamp is None:
        timestamp = str(int(time.time()))

    # Ensure payload is bytes
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    # Create signature base string
    signature_base = f"v0:{timestamp}:".encode() + payload

    # Calculate signature
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        signature_base,
        hashlib.sha256
    ).hexdigest()

    return timestamp, f"v0={signature}"


def generate_hubspot_signature(
    payload: bytes | str,
    client_secret: str,
) -> str:
    """
    Generate HubSpot SHA-256 signature.

    Args:
        payload: Request body (bytes or string)
        client_secret: HubSpot client secret

    Returns:
        Signature string
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    signature = hmac.new(
        client_secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    return signature


def generate_github_signature(
    payload: bytes | str,
    webhook_secret: str,
) -> str:
    """
    Generate GitHub SHA-256 signature.

    Args:
        payload: Request body (bytes or string)
        webhook_secret: GitHub webhook secret

    Returns:
        Signature string with sha256= prefix
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    return f"sha256={signature}"


# =============================================================================
# Payload Generators
# =============================================================================

def generate_slack_payload(
    text: str = "Test message",
    team_id: str = "T_SLACK_123",
    user_id: str = "U_USER_123",
    channel_id: str = "C_CHANNEL_123",
    event_type: str = "message",
) -> dict[str, Any]:
    """
    Generate a mock Slack webhook payload.

    Args:
        text: Message text
        team_id: Slack team ID
        user_id: Slack user ID
        channel_id: Slack channel ID
        event_type: Event type (message, file_created, etc.)

    Returns:
        Mock Slack webhook payload dict
    """
    return {
        "token": "verification_token",
        "team_id": team_id,
        "api_app_id": "A123456",
        "event": {
            "type": event_type,
            "user": user_id,
            "text": text,
            "ts": "1234567890.123456",
            "channel": channel_id,
            "event_ts": "1234567890.123456",
        },
        "type": "event_callback",
        "event_id": "Ev123456789",
        "event_time": 1234567890,
    }


def generate_hubspot_payload(
    object_type: str = "contact",
    event_type: str = "created",
    portal_id: str = "PORTAL_123",
    object_id: str = "123",
) -> dict[str, Any]:
    """
    Generate a mock HubSpot webhook payload.

    Args:
        object_type: Object type (contact, company, deal)
        event_type: Event type (created, updated, deleted)
        portal_id: HubSpot portal ID
        object_id: Object ID

    Returns:
        Mock HubSpot webhook payload dict
    """
    return {
        "eventId": 123,
        "subscriptionId": 456,
        "portalId": portal_id,
        "eventType": f"{object_type}.{event_type}",
        "objectId": object_id,
        "changes": [],
        "source": "HUBSPOT",
        "occurredAt": 1234567890000,
    }


def generate_salesforce_payload(
    object_id: str = "001R000000123",
    event_type: str = "created",
    org_id: str = "00D_SALESFORCE_123",
) -> dict[str, Any]:
    """
    Generate a mock Salesforce webhook payload.

    Args:
        object_id: Salesforce record ID
        event_type: Event type (created, updated, deleted)
        org_id: Salesforce organization ID

    Returns:
        Mock Salesforce webhook payload dict
    """
    return {
        "eventId": "eventID",
        "createdDate": "2024-01-01T00:00:00.000Z",
        "createdBy": "005R000000123",
        "orgId": org_id,
        "payload": {
            "Id": object_id,
            "Name": "Test Record",
            "type": event_type,
        },
        "eventSource": "Salesforce",
        "salesforce_event": event_type,
    }


def generate_gmail_payload(
    email_address: str = "test@example.com",
    history_id: str = "123456789",
) -> dict[str, Any]:
    """
    Generate a mock Gmail Pub/Sub push notification payload.

    Args:
        email_address: Gmail email address
        history_id: Gmail history ID

    Returns:
        Mock Gmail Pub/Sub notification dict
    """
    import base64

    inner_data = {
        "emailAddress": email_address,
        "historyId": history_id,
    }

    return {
        "message": {
            "data": base64.b64encode(json.dumps(inner_data).encode()).decode(),
            "messageId": "123456789",
            "publishTime": "2024-01-01T00:00:00.000Z",
        },
    }


def generate_notion_payload(
    object_type: str = "page",
    event_type: str = "created",
    workspace_id: str = "WORKSPACE_123",
    object_id: str = "PAGE_123",
) -> dict[str, Any]:
    """
    Generate a mock Notion webhook payload.

    Args:
        object_type: Object type (page, database, block)
        event_type: Event type (created, updated, deleted)
        workspace_id: Notion workspace ID
        object_id: Notion object ID

    Returns:
        Mock Notion webhook payload dict
    """
    return {
        "workspace_id": workspace_id,
        "event": {
            "type": event_type,
            "object": {
                "id": object_id,
                "type": object_type,
                "created_time": 1234567890,
            },
        },
    }


def generate_outlook_payload(
    client_state: str = "signed_state",
    subscription_id: str = "SUB_123",
    resource: str = "messages/MSG_123",
) -> dict[str, Any]:
    """
    Generate a mock Outlook (Microsoft Graph) webhook payload.

    Args:
        client_state: Signed clientState value
        subscription_id: Graph subscription ID
        resource: Resource identifier

    Returns:
        Mock Outlook webhook notification dict
    """
    return {
        "value": [
            {
                "clientState": client_state,
                "subscriptionId": subscription_id,
                "resource": resource,
                "changeType": "created",
            }
        ],
    }


# =============================================================================
# Mock Webhook Sender
# =============================================================================

def send_mock_webhook(
    provider: str,
    payload: dict[str, Any],
    base_url: str = "http://localhost:8000",
    signing_secret: Optional[str] = None,
    client_secret: Optional[str] = None,
    webhook_secret: Optional[str] = None,
    skip_signature: bool = False,
) -> dict[str, Any]:
    """
    Send a mock webhook to the webhook endpoint.

    Args:
        provider: Provider name (slack, hubspot, salesforce, gmail, notion, outlook)
        payload: Webhook payload dict
        base_url: Base URL for the API server
        signing_secret: Provider-specific signing secret
        client_secret: Provider-specific client secret
        webhook_secret: Generic webhook secret
        skip_signature: If True, skip signature generation

    Returns:
        Dict with status_code and response_body
    """
    if post is None:
        return {
            "status_code": 0,
            "response_body": "requests library not available",
            "error": "Library not available"
        }

    # Determine endpoint and signature
    endpoint, headers = None, {}

    provider = provider.lower().replace("-", "_")

    if provider == "slack":
        endpoint = f"{base_url}/api/webhooks/slack/events"
        if not skip_signature and signing_secret:
            timestamp, signature = generate_slack_signature(payload, signing_secret)
            headers["X-Slack-Request-Timestamp"] = timestamp
            headers["X-Slack-Signature"] = signature

    elif provider == "hubspot":
        endpoint = f"{base_url}/api/webhooks/hubspot/events"
        if not skip_signature and client_secret:
            signature = generate_hubspot_signature(payload, client_secret)
            headers["X-HubSpot-Signature"] = signature

    elif provider == "salesforce":
        endpoint = f"{base_url}/api/webhooks/salesforce/events"
        if not skip_signature and client_secret:
            signature = generate_salesforce_signature(payload, client_secret or "")
            headers["X-Salesforce-Signature"] = signature

    elif provider == "gmail":
        endpoint = f"{base_url}/api/webhooks/gmail/events"
        # Gmail uses Pub/Sub, no HMAC signature

    elif provider == "notion":
        endpoint = f"{base_url}/api/webhooks/notion/events"
        if not skip_signature and client_secret:
            signature = generate_hubspot_signature(payload, client_secret or "")
            headers["X-Notion-Signature"] = signature

    elif provider == "outlook":
        endpoint = f"{base_url}/api/webhooks/communication/outlook"
        # Outlook uses clientState signing (done in payload generation)

    else:
        return {
            "status_code": 0,
            "response_body": f"Unknown provider: {provider}",
            "error": "Unknown provider"
        }

    # Convert payload to JSON
    json_payload = json.dumps(payload) if isinstance(payload, dict) else payload

    # Send request
    try:
        response = post(
            endpoint,
            data=json_payload,
            headers=headers,
            timeout=5,
        )

        return {
            "status_code": response.status_code,
            "response_body": response.text,
            "headers": dict(response.headers),
        }
    except Exception as e:
        return {
            "status_code": 0,
            "response_body": str(e),
            "error": str(e),
        }


# =============================================================================
# Batch Operations
# =============================================================================

def send_mock_webhooks_batch(
    payloads: list[dict[str, Any]],
    provider: str,
    base_url: str = "http://localhost:8000",
    signing_secret: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Send multiple mock webhooks in batch.

    Args:
        payloads: List of webhook payloads
        provider: Provider name
        base_url: Base URL for the API server
        signing_secret: Provider-specific signing secret

    Returns:
        List of response dicts
    """
    results = []

    for payload in payloads:
        result = send_mock_webhook(
            provider=provider,
            payload=payload,
            base_url=base_url,
            signing_secret=signing_secret,
        )
        results.append(result)

    return results


# =============================================================================
# Verification Utilities
# =============================================================================

def verify_webhook_received(
    tenant_id: str,
    provider: str,
    job_id: str,
    db_session,
) -> bool:
    """
    Verify that a webhook was processed and entities were created.

    Args:
        tenant_id: Tenant UUID
        provider: Provider name
        job_id: Job ID from webhook response
        db_session: Database session

    Returns:
        True if entities were created, False otherwise
    """
    # This would query the database to verify that the webhook
    # resulted in entities being created in graph_nodes or discovered_entities

    # For now, return False (would need actual DB implementation)
    return False


# =============================================================================
# Pre-defined Payload Sets
# =============================================================================

# Standard payloads for quick testing
STANDARD_PAYLOADS = {
    "slack": generate_slack_payload(),
    "hubspot": generate_hubspot_payload(),
    "salesforce": generate_salesforce_payload(),
    "gmail": generate_gmail_payload(),
    "notion": generate_notion_payload(),
    "outlook": generate_outlook_payload(),
}
