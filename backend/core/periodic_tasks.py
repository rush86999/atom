"""
Periodic System Tasks
Executed by the SQS Worker on a schedule (Heartbeat).
"""
import logging

from core.config import get_config
from core.database import SessionLocal
from core.models import Workspace

logger = logging.getLogger(__name__)


async def run_gateway_log_sweep():
    """
    Retention sweep for the LLM gateway request log (Phase B4).

    Deletes ``GatewayRequestLog`` rows older than ``ATOM_GATEWAY_LOG_RETENTION_DAYS``
    (default 30). Uses the shared ``SessionLocal`` so it doesn't leak a new
    connection pool per invocation (the prior ``create_engine`` per call was a
    slow connection leak on the recurring heartbeat).
    """
    try:
        with SessionLocal() as db:
            from core.llm.gateway.request_logger import sweep_gateway_logs

            deleted = sweep_gateway_logs(db)
            logger.info(f"Gateway log sweep complete: deleted {deleted} rows")
            return {"gateway_logs_deleted": deleted}
    except Exception as e:
        logger.warning(f"Gateway log sweep failed: {e}")
        return {"error": str(e)}

async def run_global_ingestion_pulse():
    """
    Heartbeat Task: Triggers document ingestion sync for all active workspaces.

    Architecture:
    1. AWS EventBridge fires 'System Heartbeat' every 5 minutes.
    2. API receives pulse -> Dispatches this task to SQS.
    3. This task iterates ALL Workspaces.
    4. Dispatches individual 'sync_integration' tasks for each enabled integration.
    5. The individual tasks check Tier Limits (Tier 1 = Skip if <60m, Tier 2 = Sync).
    6. Dispatches a 'reevaluate_doc_freshness' task per workspace so docs whose
       integrations are disabled/skipped still get aged to 'outdated'.
    """
    logger.info("❤️ Global Ingestion Heartbeat Started")

    try:
        with SessionLocal() as db:
            workspaces = db.query(Workspace).all()
            logger.info(f"Found {len(workspaces)} workspaces to check")

            from sqs_worker import dispatch_task

            from core.auto_document_ingestion import get_document_ingestion_service

            total_dispatched = 0

            for ws in workspaces:
                # Get service for this workspace (R80 intent restored: the
                # per-workspace service reads THAT workspace's settings and
                # handlers, not the default singleton's).
                service = get_document_ingestion_service(ws.id)
                settings_list = service.get_all_settings()

                for settings in settings_list:
                    if settings["enabled"]:
                        # Dispatch Sync Task
                        # We do NOT force here. We let the task logic decide if it's time based on Tier.
                        dispatch_task(
                            task_name="handle_document_ingestion_sync",
                            payload={
                                "integration_id": settings["integration_id"],
                                "workspace_id": ws.id,
                                "force": False
                            }
                        )

                # Also trigger Dashboard Analytics Sync (Check if due)
                # The worker service will handle frequency checks (e.g. once per hour)
                dispatch_task(
                    task_name="sync_dashboard_stats",
                    payload={"workspace_id": ws.id}
                )

                # Freshness age-out: docs in disabled/skipped integrations never
                # hit sync_integration, so their last_verified_at would never
                # age to 'outdated' without this dedicated pass.
                dispatch_task(
                    task_name="reevaluate_doc_freshness",
                    payload={"workspace_id": ws.id}
                )

                total_dispatched += 1

            logger.info(f"❤️ Heartbeat Complete: and dispatched analytics syncs")

            return {"workspaces_checked": len(workspaces), "tasks_dispatched": total_dispatched}

    except Exception as e:
        logger.error(f"Heartbeat failed: {e}")
        return {"error": str(e)}


async def run_doc_freshness_reevaluate(workspace_id: str):
    """Age-only freshness reevaluation for a single workspace.

    Runs via the 'reevaluate_doc_freshness' SQS task. Unlike the per-integration
    sync pass (which also detects removed-upstream docs via the file listing),
    this is a pure age-out pass: it marks docs whose ``last_verified_at`` is
    beyond the TTL as ``outdated``. Removal detection requires the actual file
    listing and only happens during a real sync. See
    core/doc_freshness_service.py.
    """
    from core.doc_freshness_service import DocFreshnessService

    try:
        with SessionLocal() as db:
            svc = DocFreshnessService(db, workspace_id=workspace_id)
            # Empty seen-set → skip removal detection, age-out only.
            summary = svc.reevaluate_workspace(workspace_id, set())
            logger.info(
                f"Freshness reevaluate for {workspace_id}: {summary.as_dict()}"
            )
            return summary.as_dict()
    except Exception as e:
        logger.error(f"Freshness reevaluate failed for {workspace_id}: {e}")
        return {"error": str(e)}
