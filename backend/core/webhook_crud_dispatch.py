"""
Unified Webhook CRUD Dispatch Engine
Normalizes change event tracking, out-of-order tombstoning, and cascade-triggering deletions
for all Tier 1 and Tier 2 integrations.
"""
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import text

from core.structured_logger import get_logger
from core.models import DiscoveredEntity, WebhookTombstone, UserConnection
from core.integration_registry import WEBHOOK_CRUD_TIERS

logger = get_logger(__name__)

def extract_crud_metadata(
    integration_id: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    query_params: Optional[Dict[str, str]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts normalized change_type and resource_id from incoming webhook event payloads.

    Supported normalization styles:
    - change_type -> "created", "updated", "deleted"
    - resource_id -> native provider-scoped ID

    Returns:
        Tuple[change_type, resource_id]
    """
    headers = headers or {}
    query_params = query_params or {}
    change_type: Optional[str] = None
    resource_id: Optional[str] = None

    if not isinstance(payload, dict):
        return None, None

    # Normalization rules by integration
    if integration_id == "slack":
        # Event callbacks structure
        event = payload.get("event") or {}
        event_type = event.get("type")
        subtype = event.get("subtype")

        if event_type == "message":
            if subtype == "message_deleted":
                change_type = "deleted"
                resource_id = event.get("deleted_ts") or (event.get("previous_message") or {}).get("ts")
            elif subtype == "message_changed":
                change_type = "updated"
                resource_id = (event.get("message") or {}).get("ts")
            elif subtype is None:
                change_type = "created"
                resource_id = event.get("ts")

    elif integration_id == "salesforce":
        # Platform event containing change headers
        header = payload.get("changeEventHeader") or {}
        sf_change = header.get("changeType")
        if sf_change:
            sf_change = sf_change.upper()
            if sf_change == "CREATE":
                change_type = "created"
            elif sf_change == "UPDATE":
                change_type = "updated"
            elif sf_change in ("DELETE", "GAP_DELETE"):
                change_type = "deleted"

            record_ids = header.get("recordIds") or []
            if record_ids:
                resource_id = str(record_ids[0])

    elif integration_id == "hubspot":
        # HubSpot delivers singular notifications or lists of objects
        sub_type = payload.get("subscriptionType")
        if sub_type:
            if ".creation" in sub_type:
                change_type = "created"
            elif ".deletion" in sub_type:
                change_type = "deleted"
            elif ".propertyChange" in sub_type:
                change_type = "updated"
            resource_id = str(payload.get("objectId") or "")

    elif integration_id == "github":
        # GitHub delivers event via X-GitHub-Event header
        github_event = headers.get("x-github-event") or headers.get("X-GitHub-Event")
        action = payload.get("action")

        if github_event in ("issues", "pull_request", "issue_comment"):
            if action in ("opened", "created"):
                change_type = "created"
            elif action == "edited":
                change_type = "updated"
            elif action == "deleted":
                change_type = "deleted"

            if github_event == "issue_comment":
                resource_id = str((payload.get("comment") or {}).get("id") or "")
            elif github_event == "issues":
                resource_id = str((payload.get("issue") or {}).get("number") or "")
            elif github_event == "pull_request":
                resource_id = str((payload.get("pull_request") or {}).get("number") or "")

    elif integration_id == "google_drive":
        # Google Drive sends change states via X-Goog-Resource-State header
        state = headers.get("x-goog-resource-state") or headers.get("X-Goog-Resource-State")
        if state:
            state = state.lower()
            if state in ("add", "create"):
                change_type = "created"
            elif state in ("remove", "trash", "delete"):
                change_type = "deleted"
            elif state in ("update", "change"):
                change_type = "updated"
        resource_id = payload.get("id") or headers.get("x-goog-resource-id") or headers.get("X-Goog-Resource-Id")

    elif integration_id == "notion":
        # Notion pages edit webhook
        change_type = "updated"
        page = payload.get("page") or payload.get("block") or {}
        resource_id = page.get("id")
        if page.get("archived") is True:
            change_type = "deleted"

    elif integration_id == "outlook":
        # Outlook direct pass-through via explicit endpoint extraction
        change_type = payload.get("changeType")
        resource_id = payload.get("resourceId")

    elif integration_id == "teams":
        event_type = payload.get("eventType") or payload.get("event")
        if event_type == "messageDelete":
            change_type = "deleted"
        elif event_type == "messageUpdate":
            change_type = "updated"
        elif event_type == "messageCreate" or event_type is None:
            change_type = "created"
        resource_id = payload.get("id") or (payload.get("message") or {}).get("id")

    elif integration_id == "discord":
        event = payload.get("event")
        if event == "MESSAGE_DELETE":
            change_type = "deleted"
        elif event == "MESSAGE_UPDATE":
            change_type = "updated"
        elif event == "MESSAGE_CREATE" or event is None:
            change_type = "created"
        resource_id = payload.get("id") or payload.get("message_id")

    elif integration_id == "monday":
        event = payload.get("event") or {}
        event_type = event.get("type")
        if event_type == "delete_item":
            change_type = "deleted"
        elif event_type == "change_column_value":
            change_type = "updated"
        elif event_type in ("create_item", "create_subitem"):
            change_type = "created"
        resource_id = str(event.get("pulseId") or "")

    elif integration_id == "jira":
        event = payload.get("webhookEvent")
        if event == "jira:issue_deleted":
            change_type = "deleted"
        elif event == "jira:issue_updated":
            change_type = "updated"
        elif event in ("jira:issue_created", None):
            change_type = "created"
        resource_id = (payload.get("issue") or {}).get("key") or (payload.get("issue") or {}).get("id")

    elif integration_id == "clickup":
        event = payload.get("event")
        if event == "taskDeleted":
            change_type = "deleted"
        elif event == "taskUpdated":
            change_type = "updated"
        elif event in ("taskCreated", None):
            change_type = "created"
        resource_id = payload.get("task_id") or payload.get("taskId")

    elif integration_id == "asana":
        # Asana delivers lists of events
        events = payload.get("events") or []
        if events:
            first_event = events[0]
            action = first_event.get("action")
            if action == "removed":
                change_type = "deleted"
            elif action == "changed":
                change_type = "updated"
            elif action == "added":
                change_type = "created"
            resource_id = (first_event.get("resource") or {}).get("gid")

    # Generic Fallbacks
    if not change_type:
        action = (
            payload.get("changeType")
            or payload.get("change_type")
            or payload.get("action")
            or payload.get("event")
            or payload.get("type")
        )
        if action:
            action = str(action).lower()
            if any(k in action for k in ("delete", "remove", "trash", "destroy")):
                change_type = "deleted"
            elif any(k in action for k in ("update", "edit", "modify", "change")):
                change_type = "updated"
            elif any(k in action for k in ("create", "add", "open", "new")):
                change_type = "created"

    if not resource_id:
        resource_id = (
            payload.get("id")
            or payload.get("objectId")
            or payload.get("object_id")
            or payload.get("resourceId")
            or payload.get("resource_id")
            or payload.get("pulseId")
            or payload.get("ts")
            or payload.get("key")
        )
        if resource_id:
            resource_id = str(resource_id)

    # Default to created if we have resource but no explicit change type
    if resource_id and not change_type:
        change_type = "created"

    return change_type, resource_id

async def crud_dispatch(
    db: Session,
    change_type: str,
    integration_id: str,
    tenant_id: str,
    resource_id: str,
    payload: Dict[str, Any],
    source_connection_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Central router handling Create, Update, and Delete actions for webhook ingestion.
    Resolves out-of-order deliveries using WebhookTombstones and handles cascading graph cleanups.
    """
    from api.routes.webhooks.ingestion_webhooks import webhook_queue

    change_type = change_type.lower()
    tier = WEBHOOK_CRUD_TIERS.get(integration_id, 3)

    logger.info(
        f"CRUD Dispatch: processing event",
        integration_id=integration_id,
        change_type=change_type,
        resource_id=resource_id,
        tenant_id=tenant_id,
        tier=tier
    )

    # 1. Enforcement of Tombstones for Create / Update events
    if change_type in ("created", "updated"):
        tombstone = (
            db.query(WebhookTombstone)
            .filter(
                WebhookTombstone.tenant_id == tenant_id,
                WebhookTombstone.integration_id == integration_id,
                WebhookTombstone.source_record_id == resource_id
            )
            .first()
        )
        if tombstone:
            logger.info(
                f"CRUD Dispatch: event ignored because a deletion tombstone already exists",
                integration_id=integration_id,
                resource_id=resource_id,
                tenant_id=tenant_id
            )
            return {"status": "ignored", "reason": "tombstoned"}

    # 2. DELETE handler
    if change_type == "deleted":
        # Check if matching entities exist
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL row_security = off"))
        try:
            entities = (
                db.query(DiscoveredEntity)
                .filter(
                    DiscoveredEntity.tenant_id == tenant_id,
                    DiscoveredEntity.source_record_type == integration_id,
                    DiscoveredEntity.source_record_id == resource_id
                )
                .all()
            )

            if not entities:
                # Out-of-order delete: record a tombstone
                logger.warning(
                    f"CRUD Dispatch: Delete event arrived but no entity found. Recording tombstone.",
                    integration_id=integration_id,
                    resource_id=resource_id,
                    tenant_id=tenant_id
                )
                # Ensure no duplicate tombstones are written
                existing_tombstone = (
                    db.query(WebhookTombstone)
                    .filter(
                        WebhookTombstone.tenant_id == tenant_id,
                        WebhookTombstone.integration_id == integration_id,
                        WebhookTombstone.source_record_id == resource_id
                    )
                    .first()
                )
                if not existing_tombstone:
                    tombstone = WebhookTombstone(
                        tenant_id=tenant_id,
                        integration_id=integration_id,
                        source_record_id=resource_id
                    )
                    db.add(tombstone)
                    db.commit()
                return {"status": "tombstoned"}

            # Standard deletion cascade
            deleted_count = len(entities)
            for entity in entities:
                db.delete(entity)
            db.commit()
            logger.info(
                f"CRUD Dispatch: successfully deleted {deleted_count} entities.",
                integration_id=integration_id,
                resource_id=resource_id,
                tenant_id=tenant_id
            )
            return {"status": "deleted", "deleted_count": deleted_count}
        finally:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL row_security = on"))

    # 3. UPDATE handler (Tier 1 only)
    elif change_type == "updated":
        if tier != 1:
            logger.debug(
                f"CRUD Dispatch: ignored update event since integration is Tier {tier}",
                integration_id=integration_id,
                resource_id=resource_id,
                tenant_id=tenant_id
            )
            return {"status": "ignored", "reason": "updates_ignored_for_tier"}

        # Enqueue re-ingestion job for Tier 1 updates
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            trigger_type="webhook",
            payload=payload,
            source_connection_id=source_connection_id
        )
        logger.info(
            f"CRUD Dispatch: update event enqueued for Tier 1 re-ingestion",
            integration_id=integration_id,
            resource_id=resource_id,
            tenant_id=tenant_id,
            job_id=job_id
        )
        return {"status": "enqueued", "job_id": job_id}

    # 4. CREATE handler
    else:
        job_id = await webhook_queue.enqueue_ingestion_job(
            tenant_id=tenant_id,
            integration_id=integration_id,
            trigger_type="webhook",
            payload=payload,
            source_connection_id=source_connection_id
        )
        logger.info(
            f"CRUD Dispatch: create event enqueued for ingestion",
            integration_id=integration_id,
            resource_id=resource_id,
            tenant_id=tenant_id,
            job_id=job_id
        )
        return {"status": "enqueued", "job_id": job_id}
