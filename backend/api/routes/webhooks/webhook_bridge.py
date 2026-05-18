from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Union

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.circuit_breaker import circuit_breaker
from core.ingestion_pipeline import IngestionPipelineService
from core.integration_registry import IntegrationRegistry
from core.universal_communication_bridge import UniversalCommunicationBridge

logger = logging.getLogger(__name__)


class UnifiedIncomingMessage(BaseModel):
    """Standardized incoming message from any communication platform"""

    platform: str
    sender_id: str
    recipient_id: str
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    thread_id: Union[str, None] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WebhookBridge:
    """
    Standardized bridge for incoming webhooks dispatching events
    to the IntegrationRegistry and ChatOrchestrator.
    """

    def __init__(self):
        self._orchestrator = None
        # Register rollback fallback callback
        circuit_breaker.register_on_open(self._on_circuit_open_fallback)

    async def _on_circuit_open_fallback(self, service: str, stats: dict[str, Any]):
        """
        Callback triggered when a circuit breaker opens.
        Automatically falls back to historical polling sync to prevent data loss.
        """
        if ":" not in service:
            return

        platform, tenant_id = service.split(":", 1)
        logger.warning(
            f"Webhook Bridge: Circuit Breaker OPENED for platform '{platform}' on tenant '{tenant_id}'. "
            f"Initiating automatic fallback historical polling sync..."
        )

        try:
            from datetime import datetime, timedelta, timezone

            from core.database import SessionLocal
            from core.historical_sync_service import HistoricalSyncService
            from core.models import UserConnection

            db = SessionLocal()
            try:
                # Find the active connection for this tenant and platform integration
                conn = (
                    db.query(UserConnection)
                    .filter(
                        UserConnection.tenant_id == tenant_id,
                        UserConnection.integration_id == platform,
                        UserConnection.status == "active",
                    )
                    .first()
                )

                if conn:
                    logger.info(
                        f"Webhook Bridge: Active connection found (ID: {conn.id}). "
                        f"Scheduling background polling sync job..."
                    )
                    # Initialize the historical sync service
                    sync_service = HistoricalSyncService(tenant_id=tenant_id, db=db)

                    # Sync the last 24 hours to cover any potential downtime/gaps
                    start_date = datetime.now(timezone.utc) - timedelta(days=1)
                    end_date = datetime.now(timezone.utc)

                    job_id = await sync_service.start_historical_sync(
                        integration_id=platform,
                        connection_id=str(conn.id),
                        start_date=start_date,
                        end_date=end_date,
                        use_worker_queue=True,
                    )
                    logger.info(
                        f"Webhook Bridge: Successfully triggered fallback historical sync job '{job_id}' "
                        f"for '{platform}' on tenant '{tenant_id}'."
                    )
                else:
                    logger.warning(
                        f"Webhook Bridge: Fallback skipped. No active connection found for "
                        f"platform '{platform}' on tenant '{tenant_id}'."
                    )
            finally:
                db.close()

        except Exception as e:
            logger.error(
                f"Webhook Bridge: Failed to trigger fallback historical sync for service '{service}': {e}",
                exc_info=True,
            )

    def _get_orchestrator(self):
        """Lazy logic to handle circular dependencies."""
        if self._orchestrator is None:
            try:
                from integrations.chat_orchestrator import ChatOrchestrator

                self._orchestrator = ChatOrchestrator(workspace_id="default")
            except Exception as e:
                logger.error(f"Failed to initialize ChatOrchestrator: {e}")
        return self._orchestrator

    async def process_event(
        self,
        platform: str,
        tenant_id: str,
        data: dict[str, Any],
        registry: IntegrationRegistry,
        db: Session,
    ) -> dict[str, Any]:
        """Process an incoming platform event via the UniversalCommunicationBridge."""
        logger.info(f"Webhook Bridge: Dispatching event from {platform} for tenant {tenant_id}")

        # 0. Feature Flag Check
        from core.feature_flags import FeatureFlags

        if not FeatureFlags.is_webhook_enabled(platform):
            logger.warning(
                f"Webhook Bridge: Webhooks disabled for platform {platform} via Feature Flag."
            )
            return {"status": "ignored", "reason": "webhook_feature_flag_disabled"}

        # 0.1 Canary Rollout Check
        if not FeatureFlags.is_webhook_canary_enabled(platform, tenant_id):
            logger.warning(
                f"Webhook Bridge: Tenant {tenant_id} is not in the canary cohort "
                f"for platform {platform}. Ignoring webhook event."
            )
            return {"status": "ignored", "reason": "webhook_canary_cohort_excluded"}

        # 0.2 Circuit Breaker Check
        cb_key = f"{platform}:{tenant_id}"
        if not await circuit_breaker.is_enabled(cb_key):
            logger.warning(f"Webhook Bridge: Circuit breaker OPEN for {cb_key}. Ignoring event.")
            return {"status": "ignored", "reason": "circuit_breaker_open"}

        try:
            # 1. Use UniversalCommunicationBridge for standardized normalization
            ucb = UniversalCommunicationBridge(db)
            ucb_result = await ucb.receive_message(
                tenant_id=tenant_id, platform=platform, payload=data
            )

            if not ucb_result:
                return {"status": "ignored", "reason": "ucb_ignored_or_error"}

            # Handle standardized interactions (buttons, etc.)
            if ucb_result.get("type") == "interaction":
                return {
                    "status": "success",
                    "processed": True,
                    "type": "interaction",
                    "result": ucb_result.get("result"),
                }

            # Handle standard text messages
            if ucb_result.get("type") != "message":
                return {"status": "ignored", "reason": "unsupported_ucb_type"}

            unified_msg = ucb_result["message"]
            text_content = unified_msg.content
            sender_id = unified_msg.sender_id

            # 1.5 Resolve source_connection_id for downstream credential/LLM access.
            # Without this, transformers can't fetch provider resources and LLM BYOK fails.
            source_connection_id = None
            conn = None
            try:
                from sqlalchemy import text
                from core.models import UserConnection
                # Bypass RLS — this is an unauthenticated webhook request
                if db.bind and db.bind.dialect.name == "postgresql":
                    db.execute(text("SET LOCAL row_security = off"))
                try:
                    conn = (
                        db.query(UserConnection)
                        .filter(
                            UserConnection.tenant_id == tenant_id,
                            UserConnection.integration_id == platform,
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
                logger.warning(f"Webhook Bridge: Failed to resolve source_connection_id: {e}")

            # 1.6 Tiered Ingestion (Basic Search Indexing + Deep GraphRAG)
            try:
                from core.models import Workspace

                # Determine workspace_id based on connection scope (org vs personal)
                workspace_id = None
                if conn:
                    if conn.scope == "org":
                        # Org scope: data is available to every member of the tenant.
                        workspace = db.query(Workspace).filter(Workspace.tenant_id == tenant_id).first()
                        workspace_id = str(workspace.id) if workspace else tenant_id
                        logger.info(f"Webhook Bridge: Connection is org-scoped. Using shared workspace_id '{workspace_id}'")
                    else:
                        # Personal scope: isolate to the specific workspace that this user's connection belongs to.
                        workspace_id = str(conn.workspace_id) if conn.workspace_id else tenant_id
                        logger.info(f"Webhook Bridge: Connection is personal-scoped. Using isolated workspace_id '{workspace_id}'")
                
                if not workspace_id:
                    workspace = db.query(Workspace).filter(Workspace.tenant_id == tenant_id).first()
                    workspace_id = str(workspace.id) if workspace else tenant_id

                ingestion = IngestionPipelineService(
                    tenant_id=tenant_id, workspace_id=workspace_id, db=db
                )
                # Dispatch to tiered pipeline (Basic is always run, Deep is gated by ACU)
                await ingestion.process_webhook_payload_tiered(
                    integration_id=platform, webhook_data=data,
                    source_connection_id=source_connection_id
                )
                # Record success on circuit breaker
                await circuit_breaker.record_success(cb_key)
            except Exception as ingest_err:
                logger.error(
                    f"Webhook Bridge: Tiered ingestion failed: {ingest_err}",
                    extra={"platform": platform, "tenant_id": tenant_id},
                )
                # Record failure on circuit breaker
                await circuit_breaker.record_failure(cb_key, error=ingest_err)
                # Continue processing even if ingestion fails (don't block the message response)

            # 2. Command Handling (e.g., /run)
            if text_content.startswith("/"):
                # Convert to local model for compatibility with _handle_command
                compat_msg = UnifiedIncomingMessage(
                    platform=platform,
                    sender_id=sender_id,
                    recipient_id="bot",  # Model doesn't have recipient_id
                    text=text_content,
                    thread_id=unified_msg.metadata_json.get("thread_id")
                    if unified_msg.metadata_json
                    else None,
                    metadata=unified_msg.metadata_json or {},
                )
                return await self._handle_command(compat_msg, tenant_id, registry)

            # 3. Chat Orchestrator Integration
            orchestrator = self._get_orchestrator()
            if not orchestrator:
                return {"status": "error", "message": "ChatOrchestrator unavailable"}

            session_id = f"{platform}_{sender_id}"
            response = await orchestrator.process_chat_message(
                message=text_content,
                session_id=session_id,
                user_id=f"ext_{sender_id}",
                context={
                    "platform": platform,
                    "tenant_id": tenant_id,
                    "sender_id": sender_id,
                    "recipient_id": "bot",
                    "thread_id": unified_msg.metadata_json.get("thread_id")
                    if unified_msg.metadata_json
                    else None,
                },
            )

            # 4. Auto-Response Dispatch (Optional based on response)
            if response and response.get("message"):
                # Use UCB for standard response
                ucb = UniversalCommunicationBridge(db)
                await ucb.send_message(
                    tenant_id=tenant_id,
                    platform=platform,
                    target_id=sender_id,
                    content=response["message"],
                    metadata={
                        "thread_ts": unified_msg.metadata_json.get("thread_id")
                        if unified_msg.metadata_json
                        else None
                    },
                )

            return {"status": "success", "processed": True, "orchestrator_response": response}

        except Exception as e:
            logger.error(f"Webhook Bridge Error ({platform}): {e}")
            await circuit_breaker.record_failure(cb_key, error=e)
            return {"status": "error", "message": str(e)}

    async def _handle_command(
        self, msg: UnifiedIncomingMessage, tenant_id: str, registry: IntegrationRegistry
    ) -> dict[str, Any]:
        """Handle platform commands (e.g., /run) via Registry."""
        parts = msg.text[1:].split(" ", 2)
        command = parts[0].lower()

        if command == "run" and len(parts) > 1:
            agent_name = parts[1]
            task_input = parts[2] if len(parts) > 2 else "Run Default"

            # Use registry to trigger agent task (simulated execution)
            # In production, we'd use core.agent_routes.execute_agent_task
            return {"status": "command_triggered", "command": "run", "agent": agent_name}

        return {"status": "command_ignored", "command": command}


# Global instance
webhook_bridge = WebhookBridge()
