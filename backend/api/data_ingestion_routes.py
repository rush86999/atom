"""
Hybrid Data Ingestion API Routes
Exposes endpoints for managing automatic data sync from integrations.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-ingestion", tags=["Data Ingestion"])

# Governance feature flags
DATA_INGESTION_GOVERNANCE_ENABLED = os.getenv("DATA_INGESTION_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


# Request/Response Models
class EnableSyncRequest(BaseModel):
    integration_id: str
    entity_types: Optional[List[str]] = None
    sync_frequency_minutes: Optional[int] = 60
    sync_last_n_days: Optional[int] = 30


class SyncResponse(BaseModel):
    success: bool
    integration_id: str
    records_fetched: int = 0
    records_ingested: int = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0
    message: Optional[str] = None


class UsageSummaryResponse(BaseModel):
    workspace_id: str
    integrations: List[Dict[str, Any]]
    total_synced_records: int = 0
    auto_sync_enabled_count: int = 0


# Helper to get workspace_id (in production, extract from auth token)
def get_workspace_id() -> str:
    """Get workspace ID from request context"""
    # In production, this would come from JWT/session
    return "default"


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_integration_usage():
    """
    Get usage summary for all integrations in workspace.
    Shows which integrations have auto-sync enabled and their sync status.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service("default")
        summary = service.get_usage_summary()
        return UsageSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Failed to get usage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable-sync")
async def enable_auto_sync(
    request: EnableSyncRequest,
    agent_id: Optional[str] = None
):
    """
    Enable automatic data sync for an integration.
    Data will be synced into Atom Memory for agent queries.

    **Governance**: Requires INTERN+ maturity for data sync configuration.
    """
    # Governance check for data sync configuration
    if DATA_INGESTION_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="enable_auto_sync",
                resource_type="data_sync_config",
                complexity=2  # MODERATE - sync configuration
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for enable_auto_sync by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    try:
        from core.hybrid_data_ingestion import SyncConfiguration, get_hybrid_ingestion_service

        service = get_hybrid_ingestion_service("default")

        config = None
        if request.entity_types:
            config = SyncConfiguration(
                integration_id=request.integration_id,
                entity_types=request.entity_types,
                sync_last_n_days=request.sync_last_n_days or 30,
            )

        service.enable_auto_sync(request.integration_id, config)

        # Update sync frequency if provided
        if request.sync_frequency_minutes:
            stats = service.usage_stats.get(request.integration_id)
            if stats:
                stats.sync_frequency_minutes = request.sync_frequency_minutes

        logger.info(f"Auto-sync enabled for {request.integration_id} by agent {agent_id or 'system'}")
        return {
            "success": True,
            "message": f"Auto-sync enabled for {request.integration_id}",
            "integration_id": request.integration_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable auto-sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable-sync/{integration_id}")
async def disable_auto_sync(
    integration_id: str,
    agent_id: Optional[str] = None
):
    """
    Disable automatic data sync for an integration.

    **Governance**: Requires INTERN+ maturity for data sync configuration.
    """
    # Governance check for data sync configuration
    if DATA_INGESTION_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="disable_auto_sync",
                resource_type="data_sync_config",
                complexity=2  # MODERATE - sync configuration
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for disable_auto_sync by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service("default")
        service.disable_auto_sync(integration_id)

        logger.info(f"Auto-sync disabled for {integration_id} by agent {agent_id or 'system'}")
        return {
            "success": True,
            "message": f"Auto-sync disabled for {integration_id}",
            "integration_id": integration_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable auto-sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/{integration_id}", response_model=SyncResponse)
async def trigger_sync(
    integration_id: str,
    force: bool = Query(False, description="Force sync even if recently synced")
):
    """
    Manually trigger a data sync for an integration.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service("default")
        result = await service.sync_integration_data(integration_id, force=force)
        
        return SyncResponse(
            success=result.get("success", False),
            integration_id=integration_id,
            records_fetched=result.get("records_fetched", 0),
            records_ingested=result.get("records_ingested", 0),
            entities_extracted=result.get("entities_extracted", 0),
            relationships_extracted=result.get("relationships_extracted", 0),
            message=result.get("error") or result.get("skipped") or "Sync completed"
        )
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync-status/{integration_id}")
async def get_sync_status(
    integration_id: str
):
    """
    Get sync status for a specific integration.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service("default")
        
        stats = service.usage_stats.get(integration_id)
        config = service.sync_configs.get(integration_id)
        
        if not stats:
            return {
                "integration_id": integration_id,
                "found": False,
                "message": "No usage data for this integration"
            }
        
        return {
            "integration_id": integration_id,
            "found": True,
            "auto_sync_enabled": stats.auto_sync_enabled,
            "total_calls": stats.total_calls,
            "successful_calls": stats.successful_calls,
            "last_used": stats.last_used.isoformat() if stats.last_used else None,
            "last_synced": stats.last_synced.isoformat() if stats.last_synced else None,
            "sync_frequency_minutes": stats.sync_frequency_minutes,
            "entity_types": config.entity_types if config else []
        }
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-integrations")
async def list_available_integrations():
    """
    List all integrations that support hybrid data ingestion.
    """
    from core.hybrid_data_ingestion import DEFAULT_SYNC_CONFIGS
    
    integrations = []
    for integration_id, config in DEFAULT_SYNC_CONFIGS.items():
        integrations.append({
            "id": integration_id,
            "entity_types": config.entity_types,
            "default_sync_days": config.sync_last_n_days,
            "max_records": config.max_records_per_sync
        })
    
    return {
        "integrations": integrations,
        "count": len(integrations)
    }
