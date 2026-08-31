"""
Hybrid Data Ingestion API Routes
Exposes endpoints for managing automatic data sync from integrations.
"""

import base64
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.llm.gateway.auth import get_gateway_identity

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/data-ingestion", tags=["Data Ingestion"])


def org_sharing_enabled() -> bool:
    """Master switch for org ingestion sharing (default OFF)."""
    return os.getenv("ATOM_ORG_SHARING_ENABLED", "false").lower() in ("1", "true", "yes")


def require_org_sharing():
    if not org_sharing_enabled():
        raise router.permission_denied_error(
            "org ingestion sharing",
            details={"reason": "ATOM_ORG_SHARING_ENABLED is false"},
        )


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


# Helper to resolve the workspace from the authenticated user
def get_workspace_id(current_user: Optional[User] = None) -> str:
    """Resolve workspace ID from the auth context (Personal Edition → "default")."""
    from core.personal_scope import resolve_workspace_id
    return resolve_workspace_id(current_user)


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_integration_usage(current_user: User = Depends(get_current_user)):
    """
    Get usage summary for all integrations in workspace.
    Shows which integrations have auto-sync enabled and their sync status.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service(get_workspace_id(current_user))
        summary = service.get_usage_summary()
        return UsageSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Failed to get usage summary: {e}")
        raise router.internal_error(detail="Internal error")


@router.post("/enable-sync")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="enable_auto_sync",
    feature="data_ingestion",
    agent_id_is_scope=True  # ?agent_id= scopes memory, not the actor
)
async def enable_auto_sync(
    request: EnableSyncRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = Query(None, description="Optional AI-employee id to scope auto-sync to; its role is persisted so scheduled runs tag records for that employee's memory"),
):
    """
    Enable automatic data sync for an integration.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Data sync configuration is a moderate action
    - Requires INTERN maturity or higher

    Round 80s: when ``agent_id`` is provided, the AI employee's role
    (``AgentRegistry.category``, lowercased) is resolved and persisted on the
    SyncConfiguration — every scheduled auto-sync then tags new records with
    it.
    """
    try:
        from core.hybrid_data_ingestion import SyncConfiguration, get_hybrid_ingestion_service

        service = get_hybrid_ingestion_service(get_workspace_id(current_user))

        # Round 80s: agent_id -> role persisted on the config so every
        # scheduled auto-sync tags records for this employee's memory.
        role = None
        if agent_id:
            try:
                from core.models import AgentRegistry
                reg_agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id).first()
                if reg_agent and getattr(reg_agent, "category", None):
                    role = str(reg_agent.category).lower()
            except Exception as resolve_err:
                logger.debug(f"agent_id role resolution failed: {resolve_err}")

        config = None
        if request.entity_types:
            config = SyncConfiguration(
                integration_id=request.integration_id,
                entity_types=request.entity_types,
                sync_last_n_days=request.sync_last_n_days or 30,
                role=role,
            )

        service.enable_auto_sync(request.integration_id, config)

        # Update sync frequency if provided
        if request.sync_frequency_minutes:
            stats = service.usage_stats.get(request.integration_id)
            if stats:
                stats.sync_frequency_minutes = request.sync_frequency_minutes

        logger.info(f"Auto-sync enabled for {request.integration_id}")
        return router.success_response(
            data={"integration_id": request.integration_id},
            message=f"Auto-sync enabled for {request.integration_id}"
        )
    except Exception as e:
        logger.error(f"Failed to enable auto-sync: {e}")
        raise router.internal_error(detail="Internal error")


@router.post("/disable-sync/{integration_id}")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="disable_auto_sync",
    feature="data_ingestion"
)
async def disable_auto_sync(
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """
    Disable automatic data sync for an integration.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Data sync configuration is a moderate action
    - Requires INTERN maturity or higher
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service(get_workspace_id(current_user))
        service.disable_auto_sync(integration_id)

        logger.info(f"Auto-sync disabled for {integration_id}")
        return router.success_response(
            data={"integration_id": integration_id},
            message=f"Auto-sync disabled for {integration_id}"
        )
    except Exception as e:
        logger.error(f"Failed to disable auto-sync: {e}")
        raise router.internal_error(detail="Internal error")


@router.post("/sync/{integration_id}", response_model=SyncResponse)
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="trigger_sync",
    feature="data_ingestion",
    agent_id_is_scope=True  # ?agent_id= scopes memory, not the actor
)
async def trigger_sync(
    integration_id: str,
    force: bool = Query(False, description="Force sync even if recently synced"),
    agent_id: Optional[str] = Query(None, description="Optional AI-employee (agent) id to scope the sync to; the agent's role (category) tags the ingested records so they are recalled into that employee's memory"),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger a data sync for an integration.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Manual sync triggering is a moderate action
    - Requires INTERN maturity or higher

    Round 80: when ``agent_id`` is provided, the AI employee's role
    (``AgentRegistry.category``, lowercased) is resolved and stamped onto the
    synced records so recall surfaces them for that employee's work/role/
    responsibilities.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service(get_workspace_id(current_user))

        role = None
        if agent_id and db:
            try:
                from core.models import AgentRegistry
                agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                if agent and getattr(agent, "category", None):
                    role = str(agent.category).lower()
            except Exception as resolve_err:
                # Role resolution is best-effort; ingest as general knowledge.
                logger.debug(f"agent_id role resolution failed for {agent_id}: {resolve_err}")

        result = await service.sync_integration_data(integration_id, force=force, role=role)

        # "skipped" (concurrent-sync backoff) is a bool with a separate
        # "reason" — feeding it into the str message field crashed the
        # response model with a 500 whenever a sync raced the background
        # sync scheduled on connect.
        if result.get("error"):
            message: Optional[str] = str(result["error"])
        elif result.get("skipped"):
            message = str(result.get("reason") or "Sync already in progress")
        else:
            message = "Sync completed"

        return SyncResponse(
            success=result.get("success", False),
            integration_id=integration_id,
            records_fetched=result.get("records_fetched", 0),
            records_ingested=result.get("records_ingested", 0),
            entities_extracted=result.get("entities_extracted", 0),
            relationships_extracted=result.get("relationships_extracted", 0),
            message=message,
        )
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        raise router.internal_error(detail="Internal error")


@router.get("/sync-status/{integration_id}")
async def get_sync_status(
    integration_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get sync status for a specific integration.
    """
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service
        service = get_hybrid_ingestion_service(get_workspace_id(current_user))
        
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
        raise router.internal_error(detail="Internal error")


@router.get("/memory/records")
async def search_memory_records(
    q: str = Query(..., description="Search text — record name, company, content"),
    agent_id: Optional[str] = Query(None, description="AI employee id — role-scopes the search"),
    limit: int = Query(8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
):
    """Search the hire's ingested records (all integrations, role-aware).

    Used by task composers to pin SPECIFIC items — a lead, invoice, document —
    to a suggested task, so the agent works the exact object, not a guess.
    """
    from core.memory_context_assembler import _integration_records_leg
    from core.models import AgentRegistry
    from core.database import SessionLocal

    workspace_id = get_workspace_id(current_user)
    role = None
    if agent_id:
        db = SessionLocal()
        try:
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            role = (agent.category or "").lower() if agent else None
        finally:
            db.close()

    lines = await _integration_records_leg(q, workspace_id, role)
    return {
        "success": True,
        "results": [
            {"record": line}
            for line in (lines or [])[:limit]
        ],
    }


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

    return router.success_response(
        data=integrations,
        metadata={"count": len(integrations)}
    )


# ============================================================================
# Org Ingestion Sharing (Phases 1-2) — docs/architecture/ORG_INGESTION_SHARING_PLAN.md
# Flag-gated: ATOM_ORG_SHARING_ENABLED (default false).
# ============================================================================


class RegisterOrgKeyRequest(BaseModel):
    public_key: str  # base64 raw Ed25519 public key (from the exporting member)
    label: str = "peer"


class ProfileImportRequest(BaseModel):
    profile: Dict[str, Any]  # signed envelope from GET /profile/export


class BundleExportRequest(BaseModel):
    sources: List[str]
    sensitivity_ceiling: str = "internal"  # public|internal|confidential|restricted
    destination: Optional[str] = None
    include: Optional[List[str]] = None  # payload sections: records | graph | texts (default all)


class BundleImportRequest(BaseModel):
    bundle: Dict[str, Any]  # signed envelope from POST /bundle/export


@router.get("/org-key")
async def get_own_org_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get (generating on first use) this instance's org-sharing public key.

    Members exchange public keys out-of-band once; each side registers the
    other's key via POST /org-key/register before importing profiles/bundles.
    """
    require_org_sharing()
    from core import org_sharing_crypto
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    workspace_id = resolve_workspace_id(current_user)
    tenant_id = resolve_tenant_id(current_user)
    public_key = org_sharing_crypto.ensure_own_key_registered(db, workspace_id, tenant_id)
    fingerprint = org_sharing_crypto.fingerprint(
        base64.b64decode(public_key)
    )
    return router.success_response(
        data={"public_key": public_key, "fingerprint": fingerprint},
    )


@router.post("/org-key/register")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="register_org_public_key",
    feature="data_ingestion"
)
async def register_peer_org_key(
    request: RegisterOrgKeyRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """Trust a peer member's org-sharing public key for signature verification."""
    require_org_sharing()
    from core import org_sharing_crypto
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    try:
        row = org_sharing_crypto.register_public_key(
            db,
            request.public_key,
            label=request.label,
            workspace_id=resolve_workspace_id(current_user),
            tenant_id=resolve_tenant_id(current_user),
        )
        return router.success_response(
            data={"fingerprint": row.fingerprint, "label": row.label},
            message=f"Registered org public key {row.fingerprint[:16]}…"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/profile/export")
async def export_ingestion_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export this instance's ingestion configuration as a signed profile.

    The profile contains no credentials (P5 sanitizer, fail-closed) and no
    data — only how to sync (integrations, entity types, frequencies, rules).
    """
    require_org_sharing()
    from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService
    from core.personal_scope import resolve_workspace_id

    try:
        envelope = IngestionProfileService().export_profile(
            db, resolve_workspace_id(current_user)
        )
        return router.success_response(data=envelope)
    except IngestionProfileError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/profile/import")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="import_ingestion_profile",
    feature="data_ingestion"
)
async def import_ingestion_profile(
    request: ProfileImportRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """Import a signed ingestion profile from another org member.

    **Governance**: HIGH complexity — changes sync behavior for the listed
    integrations. Signature must verify against a registered org key.
    """
    require_org_sharing()
    from core.ingestion_profile_service import IngestionProfileError, IngestionProfileService
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    try:
        result = IngestionProfileService().apply_profile(
            db,
            request.profile,
            workspace_id=resolve_workspace_id(current_user),
            tenant_id=resolve_tenant_id(current_user),
            performed_by=getattr(current_user, "id", None),
        )
        return router.success_response(data=result, message="Ingestion profile imported")
    except IngestionProfileError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bundle/export")
@require_governance(
    action_complexity=ActionComplexity.CRITICAL,
    action_name="export_org_data_bundle",
    feature="data_ingestion"
)
async def export_org_data_bundle(
    request: BundleExportRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """Export normalized ingested records as a signed org data bundle.

    **Governance**: CRITICAL — this is an exfiltration surface; records leave
    the instance. Restricted/confidential records are excluded unless the
    ceiling is explicitly raised for a scoped sub-bundle.
    """
    require_org_sharing()
    from core.org_data_bundle_service import BundleError, OrgDataBundleService
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    try:
        envelope = OrgDataBundleService().build_bundle(
            db,
            workspace_id=resolve_workspace_id(current_user),
            sources=request.sources,
            sensitivity_ceiling=request.sensitivity_ceiling,
            destination=request.destination,
            include=request.include,
        )
        return router.success_response(data=envelope)
    except BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bundle/import")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="import_org_data_bundle",
    feature="data_ingestion"
)
async def import_org_data_bundle(
    request: BundleImportRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """Import a signed org data bundle from another member.

    **Governance**: HIGH — writes records into local memory. The signature is
    verified BEFORE any record is parsed; the importer re-embeds locally
    through the governed ingestion paths.
    """
    require_org_sharing()
    from core.org_data_bundle_service import BundleError, OrgDataBundleService
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    try:
        result = await OrgDataBundleService().apply_bundle(
            db,
            request.bundle,
            workspace_id=resolve_workspace_id(current_user),
            tenant_id=resolve_tenant_id(current_user),
            performed_by=getattr(current_user, "id", None),
        )
        return router.success_response(data=result, message="Org data bundle imported")
    except BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Phase 3 — Org Ingestion Hub (continuous sync; flag ATOM_ORG_HUB_ENABLED)
# ============================================================================


def org_hub_enabled() -> bool:
    """Master switch for the hub-side pull endpoint (default OFF)."""
    return os.getenv("ATOM_ORG_HUB_ENABLED", "false").lower() in ("1", "true", "yes")


def require_org_hub():
    if not org_hub_enabled():
        raise router.permission_denied_error(
            "org ingestion hub",
            details={"reason": "ATOM_ORG_HUB_ENABLED is false"},
        )


class HubPullRequest(BaseModel):
    hub_url: str
    api_key: str  # the member's atom_sk_* key on the hub
    sources: List[str]
    sensitivity_ceiling: str = "internal"


@router.get("/hub/bundles", dependencies=[Depends(require_org_hub)])
async def hub_delta_bundles(
    since: Optional[str] = Query(None, description="Per-source cursor JSON (from a previous pull)"),
    sources: str = Query("", description="Comma-separated integration ids; empty = all"),
    sensitivity_ceiling: str = Query("internal"),
    request: Request = None,
    db: Session = Depends(get_db),
    identity: Any = Depends(get_gateway_identity),
):
    """Hub-side: serve signed delta bundles to members with atom_sk_* keys.

    Members pull with ``Authorization: Bearer <atom_sk_*>`` (reusing the LLM
    gateway key mechanism), pass the cursor from their last pull, and receive
    a Phase-2-shaped signed bundle containing only newer records + tombstones,
    plus the next cursor.
    """
    from core.org_hub_service import (
        OrgHubService,
        apply_hub_source_policy,
        cursor_from_json,
    )
    from core.personal_scope import resolve_workspace_id

    try:
        source_list = apply_hub_source_policy(
            [s.strip() for s in sources.split(",") if s.strip()]
        )
        envelope = OrgHubService().build_delta_bundle(
            db,
            workspace_id=resolve_workspace_id(identity.user),
            sources=source_list,
            since_cursor=cursor_from_json(since),
            sensitivity_ceiling=sensitivity_ceiling,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return router.success_response(data=envelope)


@router.post("/hub/pull")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="pull_org_hub",
    feature="data_ingestion"
)
async def hub_pull(
    request: HubPullRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """Member-side: pull the latest delta bundle from the org hub and apply it.

    **Governance**: HIGH — imports records into local memory via the Phase 2
    import path (signature verified, deduped, re-embedded). The cursor is
    persisted so the next pull continues incrementally.
    """
    require_org_sharing()
    from core.org_hub_service import HubError, OrgHubService
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    try:
        result = await OrgHubService().pull_and_apply(
            db,
            hub_url=request.hub_url,
            api_key=request.api_key,
            sources=request.sources,
            workspace_id=resolve_workspace_id(current_user),
            tenant_id=resolve_tenant_id(current_user),
            sensitivity_ceiling=request.sensitivity_ceiling,
            performed_by=getattr(current_user, "id", None),
        )
        return router.success_response(data=result, message="Org hub delta applied")
    except HubError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Org sharing ops: key lifecycle + hub sync status (real-world prep)
# ============================================================================


@router.get("/org-key/list")
async def list_org_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List registered org-sharing public keys (own + peers) with fingerprints.

    Rotating a peer: register the new key, verify a bundle imports, then
    DELETE the old key id — imports verify against any registered key.
    """
    require_org_sharing()
    from core.models import OrgPublicKey
    from core.personal_scope import resolve_workspace_id

    workspace_id = resolve_workspace_id(current_user)
    rows = db.query(OrgPublicKey).filter(
        (OrgPublicKey.workspace_id == workspace_id) | (OrgPublicKey.workspace_id.is_(None))
    ).all()
    return router.success_response(data={
        "keys": [
            {
                "id": row.id,
                "label": row.label,
                "fingerprint": row.fingerprint,
                "is_own": row.is_own,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    })


@router.delete("/org-key/{key_id}")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="revoke_org_public_key",
    feature="data_ingestion"
)
async def revoke_org_key(
    key_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agent_id: Optional[str] = None
):
    """Revoke a registered org public key — bundles signed by it stop verifying.

    **Governance**: HIGH — changes which signers this instance trusts. The
    instance's OWN key cannot be revoked this way (it is the local identity);
    rotate it by deleting ./data/org_sharing_key and re-registering.
    """
    require_org_sharing()
    from core.models import OrgPublicKey

    row = db.query(OrgPublicKey).filter_by(id=key_id).first()
    if row is None:
        raise router.not_found_error("OrgPublicKey", key_id)
    if row.is_own:
        raise HTTPException(
            status_code=400,
            detail="Refusing to revoke the instance's own key — rotate via "
                   "./data/org_sharing_key instead (see ORG_SHARING_SETUP.md)",
        )
    fingerprint = row.fingerprint
    db.delete(row)
    db.commit()
    return router.success_response(
        data={"revoked": key_id, "fingerprint": fingerprint},
        message=f"Revoked org public key {fingerprint[:16]}…",
    )


@router.get("/hub/status")
async def hub_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Member-side hub sync status: persisted cursor + recent import results.

    Ops/validation endpoint — answers "when did we last pull, and did it
    apply cleanly?" without touching the hub.
    """
    require_org_sharing()
    from core.models import BundleImport, IngestionSettings
    from core.org_hub_service import HUB_CURSOR_INTEGRATION, cursor_from_json
    from core.personal_scope import resolve_workspace_id

    workspace_id = resolve_workspace_id(current_user)
    row = db.query(IngestionSettings).filter(
        IngestionSettings.workspace_id == workspace_id,
        IngestionSettings.integration_id == HUB_CURSOR_INTEGRATION,
    ).first()
    cursor = {}
    last_cursor_update = None
    if row is not None:
        usage = row.usage_stats_json or {}
        cursor = cursor_from_json(usage.get("org_hub_cursor"))
        last_cursor_update = row.updated_at.isoformat() if row.updated_at else None

    recent = db.query(BundleImport).filter(
        BundleImport.workspace_id == workspace_id
    ).order_by(BundleImport.created_at.desc()).limit(5).all()

    return router.success_response(data={
        "hub_pull_configured": bool(os.getenv("ATOM_ORG_HUB_URL")),
        "cursor": cursor,
        "cursor_sources": sorted(cursor.keys()),
        "last_cursor_update": last_cursor_update,
        "recent_imports": [
            {
                "id": imp.id,
                "created_at": imp.created_at.isoformat() if imp.created_at else None,
                "records_ingested": imp.records_ingested,
                "records_skipped": imp.records_skipped,
                "tombstones_applied": imp.tombstones_applied,
                "section_counts": imp.section_counts or {},
            }
            for imp in recent
        ],
    })
