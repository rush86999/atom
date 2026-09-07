"""Per-app ingestion feedback recording.

User- or agent-triggered ingests that bypass the hybrid sync (the panels'
Ingest buttons, multi-folder batches, journey /sync calls, document-ingestion
syncs, structure indexing, the agent's just-in-time item pulls) must still
land in the integration's per-app usage stats — otherwise an integration
card's "Records ingested / Last ingested" never moves no matter what gets
ingested. One seam, one contract: resolve the workspace, record the outcome
on the hybrid service under the integration's STATUS key, never raise (a
recording failure must not turn a successful ingest into a 500).
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Catalog id -> the sync/usage-stats key its card actually reads. Suite apps
# share one grant/one sync entry (mirrors _INGESTION_APP_TYPES in
# api/integration_status_routes.py — keep the two in sync). Everything else
# records under its own catalog id.
_SUITE_SYNC_KEY: Dict[str, str] = {
    "zoho-books": "zoho",
    "zoho_books": "zoho",
    "zoho-crm": "zoho",
    "zoho_crm": "zoho",
    "zoho-inventory": "zoho",
    "zoho_inventory": "zoho",
    "zoho-mail": "zoho",
    "zoho_mail": "zoho",
    "zoho-projects": "zoho",
    "zoho_projects": "zoho",
    "zoho-workdrive": "zoho",
    "zoho_workdrive": "zoho",
}


def status_sync_key(integration_id: str) -> str:
    """The usage-stats key an integration's ingestion-status card reads."""
    return _SUITE_SYNC_KEY.get(integration_id, integration_id)


def record_ingestion_feedback(
    user,
    integration_id: str,
    records_ingested: int,
    success: bool = True,
    workspace_id: Optional[str] = None,
) -> None:
    """Record a completed user/agent-triggered ingestion for an integration.

    ``user`` is the authenticated user (its workspace is resolved from it);
    callers without a user object (agent tools) pass ``workspace_id``
    instead. Safe to call with either.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service

        if user is not None:
            from core.personal_scope import resolve_workspace_id

            workspace_id = resolve_workspace_id(user)
        get_hybrid_ingestion_service(workspace_id or "default") \
            .record_sync_completion(
                status_sync_key(integration_id),
                int(records_ingested or 0),
                success,
            )
    except Exception as e:
        logger.warning(
            f"Ingestion feedback recording failed for {integration_id}: {e}"
        )
