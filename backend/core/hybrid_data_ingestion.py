"""
Hybrid Data Ingestion Service for Atom Memory
Automatically ingests data from frequently used integrations into Atom Memory.
Enables cross-system insights without manual configuration.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Union
from core.database import SessionLocal
logger = logging.getLogger(__name__)

class SyncMode(str, Enum):
    """Modes for data synchronization"""
    INCREMENTAL = "incremental"
    FULL = "full"
    DISCOVERY = "discovery"
    HYBRID = "hybrid"

@dataclass
class IntegrationUsageStats:
    """Tracks usage statistics for an integration"""
    integration_id: str
    integration_name: str
    workspace_id: str = "default"
    total_calls: int = 0
    successful_calls: int = 0
    last_used: Optional[datetime] = None
    last_synced: Optional[datetime] = None
    # Auto-sync defaults ON: once an integration has synced, the scheduled
    # loop keeps it fresh (per-integration frequency). Users can still turn
    # it off explicitly — the stored False wins over this default.
    auto_sync_enabled: bool = True
    sync_frequency_minutes: int = 60  # Default: sync hourly
    # Per-integration incremental-sync cursors (ISO timestamps keyed by
    # fetch scope, e.g. "zoho_fetch"). Advanced only when a sync completes
    # cleanly; a failed sync keeps the old cursor so the next run re-pulls
    # the same window (record upserts are idempotent).
    sync_cursors: Dict[str, str] = field(default_factory=dict)
    # Cumulative records pulled across all syncs — surfaced on integration
    # pages whose Data Ingestion card has no communication-pipeline stats.
    total_records_synced: int = 0
    # Measured wall-clock duration of the most recent sync plus a running
    # average across syncs (seconds). These ground the "first ingestion takes
    # ~X min" guidance: a real measurement from this workspace beats the
    # static per-integration estimate once one sync has completed.
    last_sync_duration_seconds: Optional[float] = None
    avg_sync_duration_seconds: Optional[float] = None
    sync_duration_samples: int = 0

    def record_sync_duration(self, seconds: float) -> None:
        """Fold one completed sync's wall-clock duration into the stats."""
        self.last_sync_duration_seconds = max(0.0, float(seconds))
        # Incremental mean over all samples — cheap, stable, and precise
        # enough for a "~N min" label (no bounded window needed).
        self.sync_duration_samples += 1
        if self.avg_sync_duration_seconds is None:
            self.avg_sync_duration_seconds = self.last_sync_duration_seconds
        else:
            self.avg_sync_duration_seconds += (
                self.last_sync_duration_seconds - self.avg_sync_duration_seconds
            ) / self.sync_duration_samples


@dataclass
class SyncConfiguration:
    """Configuration for what data to sync from an integration"""
    integration_id: str
    entity_types: List[str] = field(default_factory=list)  # e.g., ["contacts", "deals", "tickets"]
    sync_last_n_days: int = 30
    max_records_per_sync: int = 1000
    include_metadata: bool = True
    sync_mode: str = "incremental"  # "incremental", "discovery"
    discovery_frequency_hours: int = 168  # Weekly by default
    # Round 80s: AI-employee role (AgentRegistry.category, lowercased) this
    # integration's records are relevant to. Persisted so SCHEDULED auto-syncs
    # keep tagging new records with the role, not just one-shot triggers.
    role: Optional[str] = None


# Default sync configurations for popular integrations
DEFAULT_SYNC_CONFIGS: Dict[str, SyncConfiguration] = {
    "salesforce": SyncConfiguration(
        integration_id="salesforce",
        entity_types=["contacts", "leads", "opportunities", "accounts"],
        sync_last_n_days=30,
        max_records_per_sync=500
    ),
    "hubspot": SyncConfiguration(
        integration_id="hubspot",
        entity_types=["contacts", "companies", "deals", "tickets"],
        sync_last_n_days=30,
        max_records_per_sync=500
    ),
    "slack": SyncConfiguration(
        integration_id="slack",
        entity_types=["messages", "channels"],
        sync_last_n_days=7,
        max_records_per_sync=1000
    ),
    "gmail": SyncConfiguration(
        integration_id="gmail",
        entity_types=["emails", "threads"],
        sync_last_n_days=14,
        max_records_per_sync=500
    ),
    "notion": SyncConfiguration(
        integration_id="notion",
        entity_types=["pages", "databases"],
        sync_last_n_days=30,
        max_records_per_sync=200
    ),
    "jira": SyncConfiguration(
        integration_id="jira",
        entity_types=["issues", "projects", "comments"],
        sync_last_n_days=30,
        max_records_per_sync=500
    ),
    "google_calendar": SyncConfiguration(
        integration_id="google_calendar",
        entity_types=["events", "attendees"],
        sync_last_n_days=60,
        max_records_per_sync=300
    ),
    "zendesk": SyncConfiguration(
        integration_id="zendesk",
        entity_types=["tickets", "users", "organizations"],
        sync_last_n_days=30,
        max_records_per_sync=500
    ),
    "zoho": SyncConfiguration(
        integration_id="zoho",
        # workdrive_files first: tiny list, ingested before the hundreds of
        # CRM/Books records so documents are queryable within minutes of sync.
        entity_types=["workdrive_files", "crm_leads", "crm_deals", "books_invoices", "projects_tasks", "inventory_items", "inventory_sales_orders"],
        sync_last_n_days=30,
        max_records_per_sync=1000
    ),
    "shopify": SyncConfiguration(
        integration_id="shopify",
        entity_types=["products", "orders", "customers"],
        sync_last_n_days=30,
        max_records_per_sync=500,
    ),
    "onedrive": SyncConfiguration(
        integration_id="onedrive",
        entity_types=["files"],
        sync_last_n_days=30,
        max_records_per_sync=200,
    ),
    "google_drive": SyncConfiguration(
        integration_id="google_drive",
        entity_types=["files"],
        sync_last_n_days=30,
        max_records_per_sync=200,
    ),
    "telegram": SyncConfiguration(
        integration_id="telegram",
        entity_types=["messages"],
        sync_last_n_days=7,
        max_records_per_sync=500,
    ),
}

# Per-module record bound for the Zoho multi-app sync (Books invoices,
# Inventory items/sales orders). The adapter pages the provider API up to
# this many records; 500 keeps a sync to ≤5 requests per module, well
# inside Books/Inventory rate limits (~100 req/min per org).
_ZOHO_PER_MODULE_SYNC_LIMIT = 500


class HybridDataIngestionService:
    """
    Manages automatic data ingestion from frequently used integrations.
    
    Key features:
    - Tracks integration usage across workspace
    - Automatically enables sync for high-usage integrations
    - Ingests data into Atom Memory for agent queries
    - Respects rate limits and sync frequencies
    """
    
    # Threshold for auto-enabling sync (calls per day)
    AUTO_SYNC_USAGE_THRESHOLD = 10

    # Content-sync modes for storage drives (see get/set_content_mode).
    CONTENT_MODES = ("full", "hybrid", "list_only")
    # Storage drives default to "hybrid" — index every file/folder, ingest
    # content only for user-selected or agent-needed files (bounds disk +
    # LLM extraction cost).
    STORAGE_INTEGRATIONS = {
        "zoho_workdrive",
        "onedrive",
        "google_drive",
        "gdrive",
        "dropbox",
        "box",
    }

    def __init__(self, workspace_id: str = "default", tenant_id: str = "default"):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        logger.info(f"HybridDataIngestionService initialized for {workspace_id} / {tenant_id}")
        self.usage_stats: Dict[str, IntegrationUsageStats] = {}
        self.sync_configs: Dict[str, SyncConfiguration] = {}
        self._sync_tasks: Dict[str, asyncio.Task] = {}
        self._sync_locks: Dict[str, asyncio.Lock] = {}
        self._running = False
        # Per-integration content mode for storage drives: "full" ingests
        # every file's content, "hybrid" (default) indexes everything but
        # ingests content only for user-selected / agent-needed files,
        # "list_only" keeps just the file/folder index.
        self.content_modes: Dict[str, str] = {}
        
        # Initialize LanceDB handler
        try:
            from core.lancedb_handler import get_lancedb_handler
            self.memory_handler = get_lancedb_handler(workspace_id)
        except ImportError:
            self.memory_handler = None
            logger.warning("LanceDB handler not available for hybrid ingestion")
        
        # Initialize GraphRAG engine
        try:
            from core.graphrag_engine import GraphRAGEngine
            self.graphrag = GraphRAGEngine()
        except ImportError:
            self.graphrag = None
            logger.warning("GraphRAG engine not available for hybrid ingestion")
            
        # Initialize LLM Service
        try:
            from core.llm_service import get_llm_service
            self.llm = get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
        except ImportError:
            self.llm = None
            logger.warning("LLM Service not available for hybrid ingestion schema discovery")

        # Phase 0 (org ingestion sharing): restore persisted sync configs and
        # usage stats. Previously these were in-memory only and silently lost
        # on every restart.
        self._load_state()
        # Module fetch failures from the most recent Zoho suite fetch (the
        # adapter's [] -on-error contract hides them from the record count).
        self._last_zoho_fetch_errors: List[str] = []
        # Active OAuth grant ⇒ a scheduled sync exists. Without this, an
        # integration whose first sync never completed (restart mid-walk)
        # vanishes from run_scheduled_syncs on every restart — its
        # ingestion_settings row is only written by a COMPLETED sync.
        self._seed_token_backed_integrations()

    # ------------------------------------------------------------------
    # Phase 0: persistence to ingestion_settings
    # ------------------------------------------------------------------

    @staticmethod
    def _persistence_enabled() -> bool:
        return os.getenv("ATOM_INGESTION_PERSIST_STATE", "true").lower() in ("1", "true", "yes")

    def _seed_token_backed_integrations(self):
        """Seed usage_stats for shipped integrations that have an active token.

        Uses single-operator token semantics (any active row, mirroring
        ZohoAdapter._load_token's fallback) — workspace drift between the
        token row and this service must not silently unschedule an
        integration. Only fills gaps; existing state always wins.
        """
        if not self._persistence_enabled():
            return
        try:
            from core.models import IntegrationToken

            db = SessionLocal()
            try:
                active_providers = {
                    row[0]
                    for row in db.query(IntegrationToken.provider)
                    .filter(IntegrationToken.status == "active")
                    .all()
                }
            finally:
                db.close()
            seeded: List[str] = []
            for integration_id, config in DEFAULT_SYNC_CONFIGS.items():
                if integration_id in self.usage_stats or integration_id not in active_providers:
                    continue
                self.usage_stats[integration_id] = IntegrationUsageStats(
                    integration_id=integration_id,
                    integration_name=integration_id,
                    workspace_id=self.workspace_id,
                    auto_sync_enabled=True,
                )
                self.sync_configs[integration_id] = config
                seeded.append(integration_id)
            for integration_id in seeded:
                self._persist_integration(integration_id)
            if seeded:
                logger.info(
                    f"Seeded sync state for token-backed integrations: {sorted(seeded)}"
                )
        except Exception as e:
            # Non-fatal by design — degrade to previous in-memory behaviour.
            logger.debug(f"Token-backed sync seeding skipped: {e}")

    def _load_state(self):
        """Rebuild usage_stats / sync_configs from persisted ingestion_settings rows.

        Non-fatal by design: a missing/unavailable DB degrades to the previous
        in-memory behaviour instead of breaking ingestion startup.
        """
        if not self._persistence_enabled():
            return
        try:
            from core.models import IngestionSettings
            db = SessionLocal()
            try:
                rows = db.query(IngestionSettings).filter(
                    IngestionSettings.workspace_id == self.workspace_id
                ).all()
                for row in rows:
                    usage = (row.usage_stats_json or {}) if isinstance(row.usage_stats_json, dict) else {}
                    # JSON columns default to []/{} on insert, so a document-
                    # ingestion-only row shows entity_types==[] — treat that
                    # as "no hybrid state" too.
                    has_config = bool(row.entity_types)
                    if not usage and not has_config:
                        continue  # document-ingestion-only row — not hybrid state
                    last_used = self._parse_dt(usage.get("last_used"))
                    last_synced = self._parse_dt(usage.get("last_synced")) or row.last_sync
                    stats = IntegrationUsageStats(
                        integration_id=row.integration_id,
                        integration_name=usage.get("integration_name", row.integration_id),
                        workspace_id=self.workspace_id,
                        total_calls=usage.get("total_calls", 0),
                        successful_calls=usage.get("successful_calls", 0),
                        last_used=last_used,
                        last_synced=last_synced,
                        auto_sync_enabled=bool(usage.get("auto_sync_enabled", row.enabled)),
                        sync_frequency_minutes=usage.get("sync_frequency_minutes", row.sync_frequency_minutes or 60),
                        total_records_synced=usage.get("total_records_synced", 0),
                        last_sync_duration_seconds=usage.get("last_sync_duration_seconds"),
                        avg_sync_duration_seconds=usage.get("avg_sync_duration_seconds"),
                        sync_duration_samples=usage.get("sync_duration_samples", 0),
                        sync_cursors=usage.get("sync_cursors") or {},
                    )
                    if usage.get("content_mode"):
                        self.content_modes[self._normalize_content_key(row.integration_id)] = usage["content_mode"]
                    self.usage_stats[row.integration_id] = stats
                    if has_config:
                        self.sync_configs[row.integration_id] = SyncConfiguration(
                            integration_id=row.integration_id,
                            entity_types=list(row.entity_types or []),
                            sync_last_n_days=row.sync_last_n_days or 30,
                            max_records_per_sync=row.max_records_per_sync or 1000,
                            include_metadata=True,
                            sync_mode=row.sync_mode or "incremental",
                            role=usage.get("sync_role"),
                        )
                if self.usage_stats:
                    logger.info(
                        f"Restored hybrid ingestion state for {len(self.usage_stats)} "
                        f"integration(s) in workspace {self.workspace_id}"
                    )
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not load persisted ingestion state: {e}")

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _normalize_content_key(self, integration_id: str) -> str:
        return (integration_id or "").strip().lower().replace("-", "_")

    def default_content_mode(self, integration_id: str) -> str:
        """Storage drives default to hybrid (index all, ingest on demand) to
        keep disk + LLM cost bounded; everything else ingests fully."""
        return (
            "hybrid"
            if self._normalize_content_key(integration_id) in self.STORAGE_INTEGRATIONS
            else "full"
        )

    def get_content_mode(self, integration_id: str) -> str:
        key = self._normalize_content_key(integration_id)
        return self.content_modes.get(key) or self.default_content_mode(key)

    def set_content_mode(self, integration_id: str, mode: str) -> None:
        if mode not in self.CONTENT_MODES:
            raise ValueError(f"Invalid content mode: {mode}")
        key = self._normalize_content_key(integration_id)
        self.content_modes[key] = mode
        # Ensure a persisted row exists for this integration so the mode
        # survives restarts (set_content_mode may run before the first sync
        # creates usage stats).
        if key not in self.usage_stats:
            self.usage_stats[key] = IntegrationUsageStats(
                integration_id=key,
                integration_name=key,
                workspace_id=self.workspace_id,
                auto_sync_enabled=True,
            )
        self._persist_integration(key)

    def record_sync_completion(self, integration_id: str,
                               records_ingested: int, success: bool = True) -> None:
        """Record a completed sync from OUTSIDE the hybrid pipeline (e.g. the
        WorkDrive full-sync starter) so integration cards surface real counts.

        Creates the usage entry when missing — same contract as the sync path,
        so first-run completions are never silently dropped.
        """
        stats = self.usage_stats.get(integration_id)
        if stats is None:
            stats = IntegrationUsageStats(
                integration_id=integration_id,
                integration_name=integration_id,
                workspace_id=self.workspace_id,
            )
            self.usage_stats[integration_id] = stats
        stats.total_calls += 1
        if success:
            stats.successful_calls += 1
        stats.last_used = datetime.now(timezone.utc)
        if success:
            stats.last_synced = datetime.now(timezone.utc)
            stats.total_records_synced += int(records_ingested or 0)
        self._persist_integration(integration_id)

    def _persist_integration(self, integration_id: str):
        """Write-through the current in-memory state for one integration.

        Non-fatal: persistence failures are logged and never break the sync
        flow (the in-memory dicts remain the operational source of truth for
        the running process).
        """
        if not self._persistence_enabled():
            return
        try:
            from core.models import IngestionSettings
            stats = self.usage_stats.get(integration_id)
            config = self.sync_configs.get(integration_id)
            if stats is None and config is None:
                return

            usage_json: Dict[str, Any] = {}
            if stats:
                usage_json = {
                    "integration_name": stats.integration_name,
                    "total_calls": stats.total_calls,
                    "successful_calls": stats.successful_calls,
                    "last_used": stats.last_used.isoformat() if stats.last_used else None,
                    "last_synced": stats.last_synced.isoformat() if stats.last_synced else None,
                    "auto_sync_enabled": stats.auto_sync_enabled,
                    "sync_frequency_minutes": stats.sync_frequency_minutes,
                    "total_records_synced": stats.total_records_synced,
                    "last_sync_duration_seconds": stats.last_sync_duration_seconds,
                    "avg_sync_duration_seconds": stats.avg_sync_duration_seconds,
                    "sync_duration_samples": stats.sync_duration_samples,
                    "sync_cursors": stats.sync_cursors or {},
                    **({"sync_role": config.role} if config and config.role else {}),
                }
                content_mode = self.content_modes.get(
                    self._normalize_content_key(integration_id)
                )
                if content_mode:
                    usage_json["content_mode"] = content_mode

            db = SessionLocal()
            try:
                row = db.query(IngestionSettings).filter(
                    IngestionSettings.workspace_id == self.workspace_id,
                    IngestionSettings.integration_id == integration_id,
                ).first()
                if row is None:
                    row = IngestionSettings(
                        workspace_id=self.workspace_id,
                        tenant_id=self.tenant_id,
                        integration_id=integration_id,
                    )
                    db.add(row)

                if stats:
                    row.enabled = stats.auto_sync_enabled
                    row.sync_frequency_minutes = stats.sync_frequency_minutes
                    row.last_sync = stats.last_synced
                    row.usage_stats_json = usage_json
                if config:
                    row.entity_types = list(config.entity_types)
                    row.sync_last_n_days = config.sync_last_n_days
                    row.max_records_per_sync = config.max_records_per_sync
                    row.sync_mode = config.sync_mode
                    if config.role:
                        usage_json["sync_role"] = config.role
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not persist ingestion state for {integration_id}: {e}")

    def record_integration_usage(
        self, 
        integration_id: str, 
        integration_name: str,
        success: bool = True,
        user_id: Optional[str] = None
    ):
        """
        Record that an integration was used.
        Called by integration routes/services when APIs are invoked.
        """
        if integration_id not in self.usage_stats:
            self.usage_stats[integration_id] = IntegrationUsageStats(
                integration_id=integration_id,
                integration_name=integration_name,
                workspace_id=self.workspace_id
            )
        
        stats = self.usage_stats[integration_id]
        stats.total_calls += 1
        if success:
            stats.successful_calls += 1
        stats.last_used = datetime.now(timezone.utc)
        
        # Check if we should auto-enable sync
        if not stats.auto_sync_enabled:
            self._check_auto_enable_sync(integration_id)

        self._persist_integration(integration_id)

        logger.debug(f"Recorded usage for {integration_id}: {stats.total_calls} total calls")
    
    def _check_auto_enable_sync(self, integration_id: str):
        """Check if integration meets threshold for auto-sync"""
        stats = self.usage_stats.get(integration_id)
        if not stats:
            return
        
        # Calculate calls per day (rough estimate)
        if stats.last_used:
            # If high usage, enable auto-sync
            if stats.total_calls >= self.AUTO_SYNC_USAGE_THRESHOLD:
                logger.info(f"Auto-enabling sync for {integration_id} (usage: {stats.total_calls})")
                self.enable_auto_sync(integration_id)
    
    def enable_auto_sync(self, integration_id: str, config: Optional[SyncConfiguration] = None):
        """Enable automatic data sync for an integration"""
        logger.info(f"enable_auto_sync called for {integration_id}")
        if integration_id not in self.usage_stats:
            self.usage_stats[integration_id] = IntegrationUsageStats(
                integration_id=integration_id,
                integration_name=integration_id,
                workspace_id=self.workspace_id
            )
        
        self.usage_stats[integration_id].auto_sync_enabled = True
        
        # Use provided config or default
        if config:
            self.sync_configs[integration_id] = config
        elif integration_id in DEFAULT_SYNC_CONFIGS:
            self.sync_configs[integration_id] = DEFAULT_SYNC_CONFIGS[integration_id]
            logger.info(f"Loaded default sync config for {integration_id}")
        else:
            # Create basic config
            self.sync_configs[integration_id] = SyncConfiguration(
                integration_id=integration_id,
                entity_types=["records"],
                sync_last_n_days=30
            )
        
        logger.info(f"Auto-sync enabled for {integration_id} in workspace {self.workspace_id}")
        self._persist_integration(integration_id)
    
    def disable_auto_sync(self, integration_id: str):
        """Disable automatic data sync for an integration"""
        if integration_id in self.usage_stats:
            self.usage_stats[integration_id].auto_sync_enabled = False
        if integration_id in self._sync_tasks:
            self._sync_tasks[integration_id].cancel()
            del self._sync_tasks[integration_id]
        logger.info(f"Auto-sync disabled for {integration_id}")
        self._persist_integration(integration_id)
    
    async def sync_integration_data(
        self,
        integration_id: str,
        force: bool = False,
        discovery_mode: bool = False,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """Serialize per-integration syncs.

        Overlapping syncs used to clobber each other (shared rate budget, a
        second fetch zeroing out mid-ingest). A second caller while one sync
        is running is skipped, not queued — the running pass already covers it.
        """
        # Lazy-init so partially-constructed instances (test stubs bypassing
        # __init__) still satisfy the per-integration lock contract.
        if not hasattr(self, "_sync_locks"):
            self._sync_locks: Dict[str, asyncio.Lock] = {}
        lock = self._sync_locks.setdefault(integration_id, asyncio.Lock())
        if lock.locked():
            return {"skipped": True, "reason": "Sync already in progress for this integration"}
        async with lock:
            # Start-time bookkeeping so status polls can show elapsed time.
            if not hasattr(self, "_sync_started_at"):
                self._sync_started_at: Dict[str, datetime] = {}
            started_at = datetime.now(timezone.utc)
            self._sync_started_at[integration_id] = started_at
            try:
                return await self._sync_integration_data_impl(
                    integration_id, force=force, discovery_mode=discovery_mode, role=role
                )
            finally:
                self._sync_started_at.pop(integration_id, None)
                # Wall-clock duration (skipped concurrent calls return early,
                # so this only sees syncs that actually ran). Feeds the
                # measured first-ingestion ETA on the integration cards.
                try:
                    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
                    stats = self.usage_stats.get(integration_id)
                    if stats is not None:
                        stats.record_sync_duration(duration)
                        self._persist_integration(integration_id)
                except Exception as e:
                    logger.debug(f"Duration recording failed for {integration_id}: {e}")

    def _mirror_crm_records_to_sql(self, records: List[Dict[str, Any]], workspace_id: str) -> None:
        """Upsert Zoho CRM leads/deals into sales_leads / sales_deals.

        Keyed by external_id (= Zoho record id) so re-syncs update in place.
        Best-effort: SQL is the dashboard ledger; failures never block the
        memory ingestion that follows.
        """
        try:
            from sales.models import Lead, Deal, LeadStatus, DealStage

            _STAGE_MAP = [
                ("closed won", DealStage.CLOSED_WON, 100.0),
                ("closed lost", DealStage.CLOSED_LOST, 0.0),
                ("negotiat", DealStage.NEGOTIATION, 75.0),
                ("proposal", DealStage.PROPOSAL, 60.0),
                ("quote", DealStage.PROPOSAL, 60.0),
                ("qualif", DealStage.QUALIFICATION, 30.0),
                ("needs analysis", DealStage.QUALIFICATION, 30.0),
            ]

            def _stage(raw_stage: str):
                s = (raw_stage or "").lower()
                for needle, stage, prob in _STAGE_MAP:
                    if needle in s:
                        return stage, prob
                return DealStage.DISCOVERY, 10.0

            db = SessionLocal()
            leads_up = deals_up = 0
            try:
                for r in records:
                    ext = str(r.get("id") or "").strip()
                    if not ext:
                        continue
                    rtype = r.get("type")
                    if rtype == "lead":
                        row = db.query(Lead).filter(
                            Lead.workspace_id == workspace_id,
                            Lead.external_id == ext,
                        ).first()
                        if not row:
                            # email is NOT NULL — synthesize a stable pointer
                            # when Zoho has no email on the lead
                            row = Lead(
                                workspace_id=workspace_id,
                                external_id=ext,
                                email=r.get("email") or f"zoho-{ext}@crm.local",
                            )
                            db.add(row)
                        if r.get("email"):
                            row.email = r["email"]
                        parts = (r.get("name") or "").split(" ", 1)
                        row.first_name = parts[0] or None
                        row.last_name = parts[1] if len(parts) > 1 else None
                        row.company = r.get("company")
                        row.source = "zoho_crm"
                        st = (r.get("status") or "").lower()
                        if "convert" in st:
                            row.status = LeadStatus.QUALIFIED
                            row.is_converted = True
                        elif "qualif" in st:
                            row.status = LeadStatus.QUALIFIED
                        elif "contact" in st or "attempt" in st:
                            row.status = LeadStatus.CONTACTED
                        leads_up += 1
                    elif rtype == "deal":
                        row = db.query(Deal).filter(
                            Deal.workspace_id == workspace_id,
                            Deal.external_id == ext,
                        ).first()
                        if not row:
                            row = Deal(
                                workspace_id=workspace_id,
                                external_id=ext,
                                name=r.get("name") or f"Zoho deal {ext}",
                            )
                            db.add(row)
                        row.name = r.get("name") or row.name
                        try:
                            row.value = float(r.get("amount") or 0.0)
                        except (TypeError, ValueError):
                            pass
                        stage, prob = _stage(r.get("stage"))
                        row.stage = stage
                        row.probability = prob
                        deals_up += 1
                db.commit()
                if leads_up or deals_up:
                    logger.info(
                        f"Mirrored CRM records to SQL: {leads_up} leads, {deals_up} deals (workspace {workspace_id})"
                    )
            finally:
                db.close()
        except Exception as mirror_err:
            logger.warning(f"CRM SQL mirror failed (non-fatal): {mirror_err}")

    async def _sync_integration_data_impl(
        self,
        integration_id: str,
        force: bool = False,
        discovery_mode: bool = False,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync data from an integration into Atom Memory.

        Args:
            integration_id: Id of the integration to sync.
            force: Bypass the recently-synced guard.
            discovery_mode: Whether new entity types may be discovered.
            role: Optional AI-employee role (AgentRegistry.category, lowercased)
                the synced records are relevant to. Tagged in the integration_
                LanceDB metadata so role-aware recall surfaces them to the right
                employee's memory. None/empty = general knowledge.

        Returns:
            Dict with sync results: records_synced, entities_extracted, etc.
        """
        stats = self.usage_stats.get(integration_id)
        if stats is None:
            # First sync on a fresh install: create the entry here. Leaving it
            # None skipped EVERY stats update below AND persistence (the
            # `if stats:` guards) — last_synced never landed and the
            # IngestionSettings row was never written, so integration pages
            # showed "Never / 0" no matter how many syncs ran.
            stats = IntegrationUsageStats(
                integration_id=integration_id,
                integration_name=integration_id,
                workspace_id=self.workspace_id,
            )
            self.usage_stats[integration_id] = stats
        config = self.sync_configs.get(integration_id)
        if not config:
            # Default-registry fallback: per-workspace config is optional —
            # the plain trigger path (POST /api/data-ingestion/sync/{id} and
            # the connect-time background sync) must work out of the box for
            # integrations with shipped defaults (e.g. zoho) without the user
            # first hitting enable-sync. RED→GREEN journey fix: was
            # "No sync config for zoho" for every fresh connect.
            config = DEFAULT_SYNC_CONFIGS.get(integration_id)
        
        if not config:
            return {"error": f"No sync config for {integration_id}"}

        # Explicit role param wins; else inherit the persistent config role
        # (set via enable-sync/trigger with agent_id) so scheduled auto-syncs
        # keep tagging records for the right AI employee.
        _role = str(role).lower() if role else (
            str(getattr(config, "role", None)).lower()
            if getattr(config, "role", None) else None)

        # Check if sync is needed (unless forced)
        if not force and stats and stats.last_synced:
            minutes_since_sync = (datetime.now(timezone.utc) - stats.last_synced).total_seconds() / 60
            if minutes_since_sync < stats.sync_frequency_minutes:
                return {"skipped": True, "reason": "Recently synced"}
        
        logger.info(f"Starting sync for {integration_id} in workspace {self.workspace_id}")
        
        results = {
            "integration_id": integration_id,
            "workspace_id": self.workspace_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "records_fetched": 0,
            "records_ingested": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": []
        }
        
        try:
            # Watermark for the incremental cursor: taken BEFORE the fetch so
            # records modified mid-sync are picked up by the next window.
            fetch_started_at = datetime.now(timezone.utc)
            # Reset per-run module-error tracking (set by the Zoho fetcher).
            self._last_zoho_fetch_errors = []
            # Fetch data from integration
            records = await self._fetch_integration_data(integration_id, config, discovery_mode=discovery_mode, role=_role)
            results["records_fetched"] = len(records)

            # A module fetch that failed under its [] -on-error contract must
            # not mark the sync complete — that would advance the
            # incremental cursor over records never pulled.
            fetch_incomplete = integration_id == "zoho" and bool(self._last_zoho_fetch_errors)
            if fetch_incomplete:
                results["errors"].extend(self._last_zoho_fetch_errors)
                results["partial"] = True

            # Mirror Zoho CRM leads/deals into the SQL sales tables so the
            # sales dashboard (/api/sales/dashboard/summary) reflects the
            # ingested CRM instead of zeros. Memory stays the retrieval
            # source; this is the structured ledger for KPIs.
            if integration_id == "zoho":
                self._mirror_crm_records_to_sql(records, self.workspace_id)

            # Keep-set for the FULL-sync stale-fact GC (O2): every fetched id
            # still exists at the source, even if its ingest is skipped below.
            fetched_record_ids = [
                str(r.get("id") or "").strip() for r in records if r.get("id")
            ]

            # Ingest each record into Atom Memory
            seen_types = set()
            # R84: one fact budget per sync run caps total fact writes.
            from core.integration_ontology_bridge import FactBudget
            fact_budget = FactBudget()
            for record in records:
                try:
                    record_type = record.get("type", "unknown")
                    
                    # 1. Automated Schema Discovery (Dynamic Intelligence)
                    if record_type not in seen_types and record_type != "unknown":
                        try:
                            from core.entity_type_service import EntityTypeService
                            from core.database import SessionLocal
                            
                            db = SessionLocal()
                            try:
                                et_service = EntityTypeService(db=db)
                                # Only discover if it's likely a new or customized type
                                discovered_schema = await self._discover_schema(record)
                                
                                # Register as draft (is_active=False)
                                # Sanitize record_type for slug (e.g. replace : with _)
                                sanitized_type = record_type.replace(":", "_").replace(" ", "_").lower()
                                slug = f"{self.workspace_id}_{integration_id}_{sanitized_type}"
                                et_service.resolve_or_create_draft(
                                    tenant_id=self.tenant_id,
                                    slug=slug,
                                    display_name=record_type.replace("_", " ").title(),
                                    json_schema=discovered_schema,
                                    description=f"Automatically discovered from {integration_id} sync."
                                )
                                seen_types.add(record_type)
                            finally:
                                db.close()
                        except Exception as discovery_err:
                            logger.warning(f"Failed to perform dynamic discovery for {record_type}: {discovery_err}")

                    # 2. Convert record to text for embedding
                    text = self._record_to_text(record, integration_id)
                    
                    # Skip if no meaningful text
                    if not text or len(text) < 10:
                        continue
                    
                    # R83 (P4): classify sensitivity per record so the taint
                    # gates downstream (org-bundle export, recall ceilings,
                    # R84 fact metadata, and the raw vector row below) have
                    # real data instead of the "internal" default.
                    from core.data_taint_tracker import classify_sensitivity
                    try:
                        _sensitivity = classify_sensitivity(text)
                        # Source-side modified time, when the provider exposes
                        # one (CRM Modified_Time, WorkDrive modified_at, …).
                        _source_modified_at = (
                            record.get("modified_at")
                            or record.get("modified_time")
                            or record.get("Modified_Time")
                        )
                    except Exception:  # noqa: BLE001 — classification must never block ingestion
                        _sensitivity = "internal"

                    # Ingest into LanceDB (to_thread: sync add_document from
                    # the loop thread can never embed — same-thread guard)
                    # None when there is no memory handler — the GraphRAG
                    # leg below reads this, so it must always be bound.
                    _upsert_status = None
                    if self.memory_handler:
                        _meta = {
                            "integration_id": integration_id,
                            "record_id": record.get("id", "unknown"),
                            "record_type": record.get("type", "unknown"),
                            "sensitivity": _sensitivity,
                            "synced_at": datetime.now(timezone.utc).isoformat(),
                            # Freshness signals (doc_freshness_service model):
                            # the source's own modified time + when this mirror
                            # was last verified against the source. Source-change
                            # → index lag = now - source_modified_at.
                            "source_modified_at": _source_modified_at,
                            "last_verified_at": datetime.now(timezone.utc).isoformat(),
                            "freshness_status": "fresh",
                        }
                        # AI-employee relevance tag (Round 80)
                        if _role:
                            _meta["role"] = _role
                        # Upsert on a stable per-record id: re-syncing updates
                        # the row in place instead of appending a duplicate
                        # per run (skip when unchanged, replace when changed).
                        from core.vector_upsert import upsert_document

                        _record_key = f"rec_{integration_id}:{record.get('id', 'unknown')}"
                        _upsert_status = "skipped_unchanged"
                        if self.memory_handler:
                            _upsert_status = await upsert_document(
                                self.memory_handler,
                                table_name=f"integration_{integration_id}",
                                text=text,
                                doc_id=_record_key,
                                source=integration_id,
                                metadata=_meta,
                                user_id=record.get("user_id", "system"),
                            )
                        if _upsert_status == "written":
                            results["records_ingested"] += 1
                        else:
                            results["records_unchanged"] = (
                                results.get("records_unchanged", 0) + 1
                            )

                    # Also ingest into GraphRAG for entity/relationship extraction
                    # LLM extraction only for NEW/CHANGED records — re-running
                    # it for unchanged mirrors made every re-sync crawl at
                    # LLM latency per record. The LanceDB row already carries
                    # the entities from the first pass.
                    if self.graphrag and _upsert_status == "written":
                        # ingest_document is a coroutine — must be awaited, or
                        # the truthy coroutine crashes on .get() and every
                        # record is recorded as an error.
                        graphrag_result = await self.graphrag.ingest_document(
                            workspace_id=self.workspace_id,
                            # tenant_id must be explicit: the engine's own
                            # default is "default", which filed every node from
                            # this path under the wrong tenant.
                            tenant_id=self.tenant_id,
                            doc_id=f"{integration_id}_{record.get('id', 'unknown')}",
                            text=text,
                            source=integration_id,
                            sensitivity=_sensitivity,
                        )
                        if graphrag_result:
                            results["entities_extracted"] += graphrag_result.get("entities", 0)
                            results["relationships_extracted"] += graphrag_result.get("relationships", 0)

                    # R84: deterministic business-fact auto-extraction
                    # (LLM-free; unverified observations, idempotent per
                    # record via DocumentIngestion markers). Budget caps the
                    # whole sync run.
                    try:
                        from core.integration_ontology_bridge import write_integration_fact
                        fact_stats = await write_integration_fact(
                            workspace_id=self.workspace_id,
                            tenant_id=self.tenant_id,
                            integration_id=integration_id,
                            record_type=record_type,
                            record=record,
                            text=text,
                            sensitivity=_sensitivity,
                            memory_handler=self.memory_handler,
                            budget=fact_budget,
                        )
                        results["facts_written"] = results.get("facts_written", 0) + fact_stats.get("written", 0)
                        _skip_reason = fact_stats.get("skipped")
                        if _skip_reason:
                            # Surfaced, not swallowed: a persistent "no_handler"
                            # here means the fact layer is silently OFF for the
                            # whole workspace — visible in sync results instead
                            # of an eternal zero.
                            results["facts_skipped"] = (
                                results.get("facts_skipped", 0) + 1
                            )
                            if _skip_reason == "no_handler":
                                results.setdefault("facts_skip_reason", "no_handler")
                    except Exception as fact_err:  # noqa: BLE001 — observation layer never blocks ingestion
                        logger.warning(f"Fact extraction skipped for {integration_id}: {fact_err}")
                
                except Exception as record_err:
                    results["errors"].append(str(record_err))
                    logger.warning(f"Failed to ingest record from {integration_id}: {record_err}")

            # Only mark fully synced if there were no errors. Previously, even
            # a sync where most records failed was marked success=True and the
            # "recently synced" guard blocked retries (Bug #7).
            error_count = len(results.get("errors", []))
            total_records = results.get("records_fetched", 0)
            if error_count > 0 and total_records > 0:
                error_rate = error_count / total_records
                if error_rate > 0.5:
                    # Majority failed — don't mark as synced, allow retry.
                    results["success"] = False
                    results["partial"] = True
                    logger.warning(
                        f"Sync for {integration_id} had {error_count}/{total_records} "
                        f"errors ({error_rate:.0%}) — not marking as fully synced"
                    )
                else:
                    # Minority errors — mark success but record the partial.
                    results["success"] = True
                    results["partial"] = True
                    if stats:
                        stats.last_synced = datetime.now(timezone.utc)
                        stats.total_records_synced += int(results.get("records_ingested") or 0)
            else:
                results["success"] = True
                if stats:
                    stats.last_synced = datetime.now(timezone.utc)
                    stats.total_records_synced += int(results.get("records_ingested") or 0)

            # An incomplete module fetch downgrades the run regardless of the
            # per-record error rate: last_synced stays untouched (retry soon)
            # and the incremental cursor does NOT advance over unpulled data.
            if fetch_incomplete:
                results["success"] = False
                results["partial"] = True
            elif results["success"] and stats is not None and integration_id == "zoho":
                stats.sync_cursors[self._ZOHO_CURSOR_KEY] = fetch_started_at.isoformat()

            if stats:
                self._persist_integration(integration_id)

            # O2 stale-fact GC: only after a CLEAN, non-partial FULL sync is
            # the fetched keep-set a complete deletion ledger. Incremental
            # fetches (recent-only) and partial failures must NEVER GC —
            # a small keep-set there would destroy live facts.
            if (
                results["success"]
                and not results.get("partial")
                and not discovery_mode
                and str(getattr(config, "sync_mode", "incremental")).lower() == "full"
            ):
                try:
                    from core.integration_ontology_bridge import (
                        retract_stale_integration_facts,
                    )

                    gc = await retract_stale_integration_facts(
                        workspace_id=self.workspace_id,
                        integration_id=integration_id,
                        keep_record_ids=fetched_record_ids,
                        memory_handler=self.memory_handler,
                    )
                    if gc.get("retracted"):
                        results["facts_retracted"] = gc["retracted"]
                        logger.info(
                            f"Stale-fact GC for {integration_id}: "
                            f"{gc['retracted']} facts retracted (FULL sync)"
                        )
                except Exception as gc_err:  # noqa: BLE001 — never blocks close-out
                    logger.warning(f"Stale-fact GC skipped for {integration_id}: {gc_err}")

            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            logger.info(
                f"Sync completed for {integration_id}: "
                f"{results['records_ingested']}/{results['records_fetched']} records, "
                f"{results['entities_extracted']} entities"
            )
            
        except Exception as e:
            results["error"] = str(e)
            results["success"] = False
            logger.error(f"Sync failed for {integration_id}: {e}")
        
        return results

    async def _estimate_api_cost(self, integration_id: str, mode: Union[SyncMode, str]) -> int:
        """Estimate the API credit cost for a specific sync mode"""
        if isinstance(mode, str):
            try:
                mode = SyncMode(mode)
            except ValueError:
                mode = SyncMode.INCREMENTAL
        
        base_cost = 10 
        if mode == SyncMode.DISCOVERY:
            return base_cost * 10
        elif mode == SyncMode.HYBRID:
            return base_cost * 3
        elif mode == SyncMode.FULL:
            return base_cost * 5
        return base_cost

    async def _fetch_integration_data(
        self, 
        integration_id: str, 
        config: SyncConfiguration,
        discovery_mode: bool = False,
        role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        """
        records = []

        try:
            if integration_id == "salesforce":
                records = await self._fetch_salesforce_data(config)
            elif integration_id in ["hubspot", "notion", "airtable", "jira", "zoho", "zoho_crm"]:
                # Use the new Universal discovery/fetch pattern
                records = await self._fetch_universal_adapter_data(integration_id, config, discovery_mode)
            elif integration_id == "slack":
                records = await self._fetch_slack_data(config)
            elif integration_id == "gmail":
                records = await self._fetch_gmail_data(config)
            elif integration_id == "zendesk":
                records = await self._fetch_zendesk_data(config)
            elif integration_id == "shopify":
                records = await self._fetch_shopify_data(config)
            elif integration_id == "onedrive":
                records = await self._fetch_onedrive_data(config, role=role)
            elif integration_id == "google_drive":
                records = await self._fetch_google_drive_data(config, role=role)
            elif integration_id == "telegram":
                records = await self._fetch_telegram_data(config)
            else:
                logger.warning(f"No fetcher implemented for {integration_id}")

        except Exception as e:
            logger.error(f"Failed to fetch data from {integration_id}: {e}")

        return records[:config.max_records_per_sync]

    async def _fetch_universal_adapter_data(self, integration_id: str, config: SyncConfiguration, discovery_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Generic fetcher that uses the standardized adapter interface for discovery and data retrieval.
        Supported by: Zoho, HubSpot, Notion, Airtable, Jira.
        """
        records = []
        try:
            from core.service_factory import ServiceFactory
            from core.database import SessionLocal
            
            db = SessionLocal()
            try:
                # 1. Get the adapter from ServiceFactory
                # ServiceFactory methods are named get_{provider}_adapter
                adapter_method_name = f"get_{integration_id.replace('_crm', '')}_adapter"
                if not hasattr(ServiceFactory, adapter_method_name):
                    logger.error(f"ServiceFactory has no method {adapter_method_name}")
                    return []
                
                adapter_method = getattr(ServiceFactory, adapter_method_name)
                # Some adapters might need workspace_id or other params
                adapter = adapter_method(db=db, workspace_id=self.workspace_id)
                
                # Ensure token is valid (if adapter supports it)
                if hasattr(adapter, "ensure_token"):
                    await adapter.ensure_token()
                
                # 2. Discovery: If discovery_mode is True, find all available entity types
                entity_types = config.entity_types
                if discovery_mode:
                    if hasattr(adapter, "get_available_schemas"):
                        discovered_schemas = await adapter.get_available_schemas()
                        # Extract the unique identifiers for fetching
                        # Format varies by adapter (e.g., 'objectApiName' for HubSpot, 'id' for Notion)
                        new_entities = []
                        for schema in discovered_schemas:
                            if integration_id == "hubspot":
                                new_entities.append(schema.get("name"))
                            elif integration_id == "notion":
                                new_entities.append(schema.get("id"))
                            elif integration_id == "airtable":
                                new_entities.append(f"{schema.get('base_id')}:{schema.get('id')}")
                            elif integration_id == "jira":
                                new_entities.append(f"{schema.get('project_key')}:{schema.get('issue_type')}")
                            elif integration_id in ["zoho", "zoho_crm"]:
                                new_entities.append(schema.get("api_name"))
                        
                        # Merge with config (avoid duplicates)
                        entity_types = list(set(entity_types + new_entities))
                        logger.info(f"Discovery mode for {integration_id} found {len(new_entities)} potential entities.")

                # 3. Fetch data for each entity type
                if hasattr(adapter, "fetch_records"):
                    for etype in entity_types:
                        try:
                            # Paginated fetch: loop through all pages instead of
                            # a single limit=100 call that silently truncated
                            # entities with >100 records (Bug #6).
                            page_size = 100
                            offset = 0
                            while True:
                                response = await adapter.fetch_records(
                                    entity_type=etype, limit=page_size, offset=offset
                                )
                                batch = response.get("results", [])

                                for r in batch:
                                    r["type"] = etype
                                    r["source"] = integration_id
                                    records.append(r)

                                # Stop if fewer than a full page was returned
                                # (last page) or we hit the max-records cap.
                                if len(batch) < page_size:
                                    break
                                if len(records) >= config.max_records_per_sync:
                                    break
                                offset += page_size
                        except Exception as fetch_err:
                            logger.error(f"Error fetching {etype} from {integration_id}: {fetch_err}")
                else:
                    # Fallback to legacy app-specific fetchers if fetch_records is missing
                    if integration_id in ["zoho", "zoho_crm"]:
                        return await self._fetch_zoho_multi_app_data(config, discovery_mode)
                    logger.warning(f"Adapter for {integration_id} does not support fetch_records")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Universal fetch error for {integration_id}: {e}")
            
        return records
    
    async def _fetch_salesforce_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Salesforce"""
        records = []
        try:
            from integrations.salesforce_service import get_salesforce_client
            # get_salesforce_client is async and takes the workspace/user id
            client = await get_salesforce_client(self.workspace_id)
            if not client:
                return records
            
            for entity_type in config.entity_types:
                if entity_type == "contacts":
                    contacts = client.query("SELECT Id, Name, Email, Title, Account.Name FROM Contact LIMIT 100")
                    for c in contacts.get("records", []):
                        records.append({
                            "id": c.get("Id"),
                            "type": "contact",
                            "name": c.get("Name"),
                            "email": c.get("Email"),
                            "title": c.get("Title"),
                            "company": c.get("Account", {}).get("Name") if c.get("Account") else None
                        })
                elif entity_type == "opportunities":
                    opps = client.query("SELECT Id, Name, StageName, Amount FROM Opportunity LIMIT 100")
                    for o in opps.get("records", []):
                        records.append({
                            "id": o.get("Id"),
                            "type": "opportunity",
                            "name": o.get("Name"),
                            "stage": o.get("StageName"),
                            "amount": o.get("Amount")
                        })
        except Exception as e:
            logger.error(f"Salesforce fetch error: {e}")
        return records
    
    async def _fetch_hubspot_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from HubSpot"""
        records = []
        try:
            from integrations.hubspot_service import get_hubspot_service
            service = get_hubspot_service()
            if service is None:
                logger.warning("HubSpot service not configured — skipping hubspot sync")
                return records

            for entity_type in config.entity_types:
                if entity_type == "contacts":
                    contacts = await service.get_contacts(limit=100)
                    for c in contacts:
                        props = c.get("properties", {})
                        records.append({
                            "id": c.get("id"),
                            "type": "contact",
                            "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                            "email": props.get("email"),
                            "company": props.get("company")
                        })
                elif entity_type == "deals":
                    deals = await service.get_deals(limit=100)
                    for d in deals:
                        props = d.get("properties", {})
                        records.append({
                            "id": d.get("id"),
                            "type": "deal",
                            "name": props.get("dealname"),
                            "stage": props.get("dealstage"),
                            "amount": props.get("amount")
                        })
        except Exception as e:
            logger.error(f"HubSpot fetch error: {e}")
        return records
    
    async def _fetch_slack_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Slack"""
        records = []
        try:
            from core.token_storage import token_storage
            from integrations.slack_service_unified import slack_unified_service

            token_data = token_storage.get_token("slack")
            token = token_data.get("access_token") if token_data else None
            if not token:
                logger.warning("Slack token not configured — skipping slack sync")
                return records

            # Fetch recent messages from public channels
            channels = await slack_unified_service.list_channels(
                token=token, types="public_channel")
            for channel in channels[:5]:
                history = await slack_unified_service.get_channel_history(
                    token=token, channel_id=channel.get("id"), limit=50
                )
                for msg in history.get("messages", []):
                    if msg.get("type") == "message" and msg.get("text"):
                        records.append({
                            "id": msg.get("ts"),
                            "type": "message",
                            "channel": channel.get("name"),
                            "text": msg.get("text"),
                            "user": msg.get("user")
                        })
        except Exception as e:
            logger.error(f"Slack fetch error: {e}")
        return records
    
    async def _fetch_gmail_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Gmail"""
        records = []
        try:
            from integrations.gmail_service import get_gmail_service

            gmail_service = get_gmail_service()

            # Build date query for last N days
            days_query = f"after:{datetime.now().timestamp() - config.sync_last_n_days * 86400}"

            # Fetch emails
            messages = gmail_service.get_messages(
                query=days_query,
                max_results=min(config.max_records_per_sync, 500)
            )

            for msg in messages:
                records.append({
                    "id": msg.get("id"),
                    "type": "email",
                    "thread_id": msg.get("threadId"),
                    "subject": msg.get("subject", ""),
                    "from": msg.get("from", ""),
                    "to": msg.get("to", ""),
                    "date": msg.get("date"),
                    "snippet": msg.get("snippet", ""),
                    "body": msg.get("body", ""),
                    "labels": msg.get("labels", [])
                })

            logger.info(f"Fetched {len(records)} emails from Gmail")

        except ImportError:
            logger.warning("Gmail service not available - install google-api-python-client")
        except Exception as e:
            logger.error(f"Gmail fetch error: {e}")

        return records
    
    async def _fetch_notion_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Notion"""
        records = []
        try:
            from integrations.notion_service import NotionService

            notion_service = NotionService()

            # Fetch pages
            if "pages" in config.entity_types:
                pages = notion_service.search_pages_in_workspace(
                    query=""  # Get all pages
                )

                for page in pages[:config.max_records_per_sync]:
                    page_id = page.get("id", "")
                    title = page.get("title", "Untitled")

                    # Get page content
                    children = notion_service.get_block_children(page_id, page_size=50)
                    content_blocks = children.get("results", [])

                    records.append({
                        "id": page_id,
                        "type": "page",
                        "title": title,
                        "url": page.get("url", ""),
                        "created_time": page.get("created_time"),
                        "last_edited_time": page.get("last_edited_time"),
                        "content_blocks_count": len(content_blocks),
                        "archived": page.get("archived", False)
                    })

            # Fetch databases
            if "databases" in config.entity_types:
                databases = notion_service.search_databases_in_workspace(
                    query=""  # Get all databases
                )

                for db in databases[:config.max_records_per_sync]:
                    db_id = db.get("id", "")
                    db_info = notion_service.get_database(db_id)

                    if db_info:
                        records.append({
                            "id": db_id,
                            "type": "database",
                            "title": db_info.get("title", [{}])[0].get("plain_text", "Untitled") if db_info.get("title") else "Untitled",
                            "created_time": db_info.get("created_time"),
                            "last_edited_time": db_info.get("last_edited_time"),
                            "properties_count": len(db_info.get("properties", {}))
                        })

            logger.info(f"Fetched {len(records)} items from Notion (pages + databases)")

        except ImportError:
            logger.warning("Notion service not available")
        except Exception as e:
            logger.error(f"Notion fetch error: {e}")

        return records
    
    async def _fetch_jira_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Jira"""
        records = []
        try:
            from integrations.jira_service import get_jira_service
            client = get_jira_service()
            if client is None:
                logger.warning("Jira service not configured — skipping jira sync")
                return records

            data = client.search_issues("updated >= -30d", max_results=100)
            for issue in data.get("issues", []):
                fields = issue.get("fields", {})
                assignee = fields.get("assignee")
                priority = fields.get("priority")
                records.append({
                    "id": issue.get("key"),
                    "type": "issue",
                    "summary": fields.get("summary"),
                    "status": fields.get("status", {}).get("name") if fields.get("status") else None,
                    "assignee": assignee.get("displayName") if assignee else None,
                    "priority": priority.get("name") if priority else None
                })
        except Exception as e:
            logger.error(f"Jira fetch error: {e}")
        return records
    
    async def _fetch_zendesk_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Zendesk"""
        records = []
        try:
            from integrations.zendesk_service import ZendeskService

            zendesk_service = ZendeskService()

            # Fetch tickets
            if "tickets" in config.entity_types or not config.entity_types:
                tickets = await zendesk_service.get_tickets(
                    per_page=min(config.max_records_per_sync, 100)
                )

                for ticket in tickets:
                    records.append({
                        "id": ticket.get("id"),
                        "type": "ticket",
                        "subject": ticket.get("subject", ""),
                        "status": ticket.get("status", ""),
                        "priority": ticket.get("priority", ""),
                        "created_at": ticket.get("created_at"),
                        "updated_at": ticket.get("updated_at"),
                        "requester_id": ticket.get("requester_id"),
                        "assignee_id": ticket.get("assignee_id"),
                        "ticket_type": ticket.get("type", ""),
                        "description": ticket.get("description", "")
                    })

            # Fetch users
            if "users" in config.entity_types:
                users = await zendesk_service.get_users(
                    per_page=min(config.max_records_per_sync, 100)
                )

                for user in users:
                    records.append({
                        "id": user.get("id"),
                        "type": "user",
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "role": user.get("role", ""),
                        "created_at": user.get("created_at"),
                        "last_login_at": user.get("last_login_at"),
                        "verified": user.get("verified", False)
                    })

            logger.info(f"Fetched {len(records)} items from Zendesk (tickets + users)")

        except ImportError:
            logger.warning("Zendesk service not available")
        except Exception as e:
            logger.error(f"Zendesk fetch error: {e}")

        return records

    # One incremental cursor for the whole suite sync. Per-module cursors
    # would be finer-grained, but every module is bounded by its per-sync
    # limit and record upserts are idempotent, so a shared window is safe.
    _ZOHO_CURSOR_KEY = "zoho_fetch"
    # Re-pull everything when the cursor gets this stale — a periodic full
    # pass reconciles any delta a provider-side last_modified filter missed
    # (some Books endpoints filter inconsistently; Airbyte hit this too).
    _ZOHO_FULL_REPULL_AFTER = timedelta(days=7)
    # Total WorkDrive file/folder records per suite sync. The walk is
    # already capped per folder (MAX_RECURSIVE_ITEMS = 2000) — without a
    # TOTAL cap, 8 folders × 2000 items = 16k records through the ingest
    # loop, which is what made suite syncs run for hours and die to
    # restarts before the CRM/Books modules ever ran.
    # Per-sync cap on WorkDrive records entering the pipeline. Env-tunable
    # for TB-scale drives (cursor pagination made the metadata walk cheap;
    # this bounds per-cycle record processing instead).
    _WD_SYNC_FILE_RECORD_CAP = int(os.getenv("WD_SYNC_FILE_RECORD_CAP", "2000"))

    def _zoho_incremental_cursor(self) -> Optional[datetime]:
        """Last cleanly-synced fetch watermark for the Zoho suite — None when
        absent or stale (stale ⇒ full re-pull for reconciliation)."""
        stats = self.usage_stats.get("zoho")
        raw = (stats.sync_cursors or {}).get(self._ZOHO_CURSOR_KEY) if stats else None
        parsed = self._parse_dt(raw) if raw else None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - parsed > self._ZOHO_FULL_REPULL_AFTER:
            return None
        return parsed

    async def _fetch_zoho_multi_app_data(self, config: SyncConfiguration, discovery_mode: bool = False) -> List[Dict[str, Any]]:
        """Fetch data from all enabled Zoho applications using the Universal Adapter"""
        records = []
        fetch_errors: List[str] = []
        modified_since = self._zoho_incremental_cursor()
        try:
            from core.integrations.adapters.zoho import ZohoAdapter
            from core.models import IntegrationToken
            
            db = SessionLocal()
            try:
                # Get the api_domain (instance_url) from the stored token
                token = db.query(IntegrationToken).filter(
                    IntegrationToken.tenant_id == self.tenant_id,
                    IntegrationToken.provider == "zoho"
                ).first()

                # LOGGING SECURITY FIX: Don't log token metadata (could contain credentials)
                # Only log token existence for debugging
                logger.debug(f"IntegrationToken found for tenant {self.tenant_id}: {token is not None}")

                instance_url = token.instance_url if token else None
                adapter = ZohoAdapter(db=db, workspace_id=self.workspace_id, instance_url=instance_url)
                
                # Ensure we have a valid access token
                await adapter.ensure_token()

                # Books/Inventory sync is gated on organization_id, which the
                # OAuth callback never sees. Discover it from the Zoho org
                # endpoint on first sync and persist it back onto the token so
                # every later sync fetches invoices/items/sales orders without
                # a manual step (RED→GREEN journey fix: only CRM ever synced).
                _resolved_org_id: Optional[str] = None

                async def _resolve_org_id() -> Optional[str]:
                    nonlocal _resolved_org_id
                    if _resolved_org_id:
                        return _resolved_org_id
                    meta = token.credential_metadata if token and token.credential_metadata else {}
                    _resolved_org_id = meta.get("organization_id")
                    if _resolved_org_id:
                        return _resolved_org_id
                    for module in ("books", "inventory"):
                        orgs = await adapter.get_organizations(module=module)
                        if orgs and orgs[0].get("organization_id"):
                            _resolved_org_id = orgs[0]["organization_id"]
                            if token:
                                if not token.credential_metadata:
                                    token.credential_metadata = {}
                                token.credential_metadata["organization_id"] = _resolved_org_id
                                db.commit()
                            break
                    return _resolved_org_id

                def _note_fetch_error(module: str) -> None:
                    # Fetchers return [] on error (contract) — capture the
                    # adapter's error flag per module so the sync can refuse
                    # to advance the incremental cursor over a failed pull.
                    if adapter.last_error:
                        fetch_errors.append(f"{module}: {adapter.last_error}")

                for entity_type in config.entity_types:
                    if entity_type == "crm_leads":
                        records.extend(await adapter.get_leads(limit=100, modified_since=modified_since))
                        _note_fetch_error("crm_leads")
                    elif entity_type == "crm_deals":
                        records.extend(await adapter.get_deals(limit=100, modified_since=modified_since))
                        _note_fetch_error("crm_deals")
                    elif entity_type in ("books_invoices", "inventory_items", "inventory_sales_orders"):
                        # Books/Inventory require organization_id — discovered
                        # and persisted on first sync if absent.
                        org_id = await _resolve_org_id()
                        if org_id:
                            if entity_type == "books_invoices":
                                records.extend(await adapter.get_invoices(organization_id=org_id, limit=_ZOHO_PER_MODULE_SYNC_LIMIT, modified_since=modified_since))
                                _note_fetch_error("books_invoices")
                            elif entity_type == "inventory_items":
                                records.extend(await adapter.get_items(organization_id=org_id, limit=_ZOHO_PER_MODULE_SYNC_LIMIT, modified_since=modified_since))
                                _note_fetch_error("inventory_items")
                            else:
                                records.extend(await adapter.get_sales_orders(organization_id=org_id, limit=_ZOHO_PER_MODULE_SYNC_LIMIT, modified_since=modified_since))
                                _note_fetch_error("inventory_sales_orders")
                    elif entity_type == "projects_tasks":
                        # Discovery mode gates expensive portal/project traversal
                        portal_id = token.credential_metadata.get("portal_id") if token and token.credential_metadata else None
                        
                        if discovery_mode and not portal_id:
                            portals = await adapter.get_portals()
                            if portals:
                                portal_id = portals[0]["id"]
                                # Update metadata if needed (deferred)
                                
                        projects = token.credential_metadata.get("active_projects", []) if token and token.credential_metadata else []
                        if discovery_mode and portal_id and not projects:
                            discovered_projects = await adapter.get_projects(portal_id)
                            projects = [p["id"] for p in discovered_projects[:3]]
                            
                        if portal_id:
                            for project_id in projects[:3]: # Sync top 3 active projects
                                records.extend(await adapter.get_tasks(portal_id=portal_id, project_id=project_id))
                        _note_fetch_error("projects_tasks")

                    elif entity_type == "workdrive_files":
                        # WorkDrive files/team-folders — the OAuth grant covers
                        # WorkDrive.files/teamfolders; ingest file metadata
                        # (name, extension, modified time) into memory so the
                        # employee can recall documents by content of title.
                        try:
                            from integrations.zoho_workdrive_service import zoho_workdrive_service

                            wd_user = token.user_id if token else None
                            logger.info(f"[WD] token={'yes' if token else 'no'} wd_user={wd_user}")
                            if wd_user:
                                # Real team folders (H Drive, Accounting, …) via
                                # /teams traversal (requires WorkDrive.teams.READ);
                                # accounts without Teams fall back to the
                                # personal root workspace.
                                folders = await zoho_workdrive_service.get_team_folders(wd_user)
                                if not folders:
                                    folder_ids = ["root"]
                                else:
                                    # Record the team folders themselves so
                                    # structure is queryable, then their files.
                                    for f in folders[:8]:
                                        records.append({
                                            "id": f"wd_{f.get('id')}",
                                            "type": "workdrive_folder",
                                            "name": f.get("name") or "Untitled folder",
                                            "description": f"team folder in {f.get('team_name') or 'WorkDrive'}",
                                            "folder_id": f.get("team_id"),
                                        })
                                    folder_ids = [f.get("id") for f in folders[:8] if f.get("id")]

                                # Relevance funnel (mirrors the OneDrive fetcher
                                # and the enterprise-RAG pattern: whitelist →
                                # binary exclusion → content parsing). Only
                                # document-like files become records; parseable
                                # ones also get their content extracted via
                                # AutoDocumentIngestion so retrieval matches
                                # substance, not just filenames.
                                _DOC_EXTS = (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".md", ".pptx", ".ppt")
                                _SKIP_EXTS = (".pst", ".ost", ".zip", ".exe", ".dmg", ".mp4", ".mov", ".7z", ".rar", ".iso", ".img", ".sql", ".bak")
                                _MAX_CONTENT_BYTES = 8 * 1024 * 1024
                                _content_budget = 25  # max downloads per sync
                                try:
                                    from core.auto_document_ingestion import AutoDocumentIngestionService
                                    _doc_ingestor = AutoDocumentIngestionService(workspace_id=self.workspace_id)
                                except Exception:
                                    _doc_ingestor = None

                                _wd_appended = 0  # total WD records this sync
                                # Modified-since cursor (2026-09-05): WorkDrive's
                                # API has no delta endpoint, so cursor lives
                                # client-side — last successful zoho sync.
                                # Files older than the cursor are already
                                # ingested (upserts dedupe by modified time);
                                # skipping them avoids re-processing on every
                                # cycle. Folders are NEVER filtered: their
                                # mtime doesn't bubble up from descendants, so
                                # filtering would break subtree traversal.
                                _zoho_stats = self.usage_stats.get("zoho")
                                _wd_modified_since = (
                                    _zoho_stats.last_synced if _zoho_stats else None
                                )
                                if _wd_modified_since:
                                    logger.info(
                                        f"[WD] modified-since cursor: {_wd_modified_since.isoformat()}"
                                    )
                                for fid in folder_ids[:8]:  # top team folders per sync
                                    if _wd_appended >= self._WD_SYNC_FILE_RECORD_CAP:
                                        break
                                    wd_files = await zoho_workdrive_service.list_files(
                                        wd_user, parent_id=fid, recursive=True
                                    )
                                    for f in wd_files:
                                        if _wd_appended >= self._WD_SYNC_FILE_RECORD_CAP:
                                            logger.info(
                                                f"WorkDrive record cap ({self._WD_SYNC_FILE_RECORD_CAP}) "
                                                "reached for this sync — remaining files next sync"
                                            )
                                            break
                                        f_name = (f.get("name") or "").lower()
                                        is_folder = f.get("type") == "folder"
                                        if is_folder:
                                            # Empty subfolders are structure
                                            # noise (AR aging buckets etc.);
                                            # keep only non-empty ones.
                                            if not f.get("size"):
                                                continue
                                            records.append({
                                                "id": f"wd_{f.get('id')}",
                                                "type": "workdrive_folder",
                                                "name": f.get("name") or "Untitled folder",
                                                "description": "folder",
                                                "modified_at": f.get("modified_at"),
                                                "folder_id": fid,
                                            })
                                            _wd_appended += 1
                                            continue
                                        ext = ("." + f["extension"].lower()) if f.get("extension") else ""
                                        if ext in _SKIP_EXTS or (ext not in _DOC_EXTS and ext):
                                            # binary archives / non-documents:
                                            # no retrieval value, pure noise
                                            continue
                                        # Cursor filter: unchanged files are
                                        # already ingested — skip by modified
                                        # time instead of re-appending (the
                                        # DB upsert dedupes anyway, but this
                                        # avoids the record-processing and
                                        # content-parse budget spend).
                                        if _wd_modified_since and f.get("modified_at"):
                                            try:
                                                from datetime import datetime as _dt
                                                _fm = _dt.fromisoformat(
                                                    str(f["modified_at"]).replace("Z", "+00:00")
                                                )
                                                if _fm.tzinfo is None:
                                                    _fm = _fm.replace(tzinfo=timezone.utc)
                                                if _fm <= _wd_modified_since:
                                                    continue
                                            except (ValueError, TypeError):
                                                pass  # unparseable mtime — let dedupe handle it
                                        records.append({
                                            "id": f"wd_{f.get('id')}",
                                            "type": "workdrive_file",
                                            "name": f.get("name") or "Untitled",
                                            "description": (
                                                f"{('.'.join(ext.split('.'))) if ext else 'file'} "
                                                f"{(f.get('size') or 0)} bytes"
                                            ).strip(),
                                            "modified_at": f.get("modified_at"),
                                            "folder_id": fid,
                                        })
                                        _wd_appended += 1
                                        if (
                                            _doc_ingestor
                                            and ext in (".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".pptx")
                                            and (f.get("size") or 0) <= _MAX_CONTENT_BYTES
                                            and _content_budget > 0
                                        ):
                                            try:
                                                _bytes = await zoho_workdrive_service.download_file(wd_user, f.get("id"))
                                                if _bytes:
                                                    await _doc_ingestor.process_file_bytes(
                                                        content=_bytes,
                                                        file_name=f.get("name") or "workdrive-file",
                                                        source="zoho_workdrive",
                                                        user_id=wd_user,
                                                        workspace_id=self.workspace_id,
                                                        role=getattr(config, "role", None),
                                                        external_id=f"zoho_workdrive:{f.get('id')}",
                                                        extra_metadata={"folder_id": fid, "source_modified_at": f.get("modified_at")},
                                                    )
                                                    _content_budget -= 1
                                            except Exception as c_err:
                                                logger.debug(f"WorkDrive content extraction skipped for {f.get('name')}: {c_err}")
                        except Exception as wd_err:
                            logger.warning(f"WorkDrive fetch failed (non-fatal): {wd_err}")

                logger.info(f"Universal Zoho Sync (Discovery={discovery_mode}): Fetched {len(records)} items across modules")
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Universal Zoho fetch error: {e}")
            fetch_errors.append(f"fetch: {type(e).__name__}: {e}")

        # Survives the caller's swallow-all except: the sync impl reads this
        # to mark the run failed so the incremental cursor stays put and the
        # next pass re-pulls the same window (upserts are idempotent).
        self._last_zoho_fetch_errors = fetch_errors

        return records

    # =========================================================================
    # Shopify ingestion fetcher
    # =========================================================================
    async def _fetch_shopify_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch products/orders/customers from Shopify into the knowledge graph."""
        records: List[Dict[str, Any]] = []
        try:
            from integrations.shopify_service import ShopifyService

            service = ShopifyService(tenant_id=self.tenant_id, config={})
            token = getattr(service, "config", {}).get("access_token") or os.getenv("SHOPIFY_ACCESS_TOKEN")
            shop = service.shop_name or os.getenv("SHOPIFY_SHOP_NAME") or os.getenv("SHOPIFY_SHOP_DOMAIN")
            if not token or not shop:
                logger.warning("Shopify fetch skipped: missing access token or shop name")
                return []

            for entity_type in config.entity_types:
                try:
                    if entity_type == "products":
                        items = await service.get_products(access_token=token, shop=shop)
                        for p in items:
                            p.setdefault("type", "shopify_product")
                            p.setdefault("id", p.get("id"))
                            p["source"] = "shopify"
                            records.append(p)
                    elif entity_type == "orders":
                        items = await service.get_orders(access_token=token, shop=shop)
                        for o in items:
                            o.setdefault("type", "shopify_order")
                            o.setdefault("id", o.get("id"))
                            o["source"] = "shopify"
                            records.append(o)
                    elif entity_type == "customers":
                        items = await service.get_customers(access_token=token, shop=shop)
                        for c in items:
                            c.setdefault("type", "shopify_customer")
                            c.setdefault("id", c.get("id"))
                            c["source"] = "shopify"
                            records.append(c)
                except Exception as fetch_err:
                    logger.error(f"Error fetching {entity_type} from Shopify: {fetch_err}")

            logger.info(f"Shopify sync: fetched {len(records)} records")
        except Exception as e:
            logger.error(f"Shopify fetch error: {e}")

        return records

    # =========================================================================
    # OneDrive ingestion fetcher
    # =========================================================================
    async def _fetch_onedrive_data(self, config: SyncConfiguration, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """List OneDrive files, download document content, and ingest into memory.

        Downloads file content for parseable document types (.docx/.xlsx/.pdf/.csv/.txt)
        and routes it through AutoDocumentIngestionService so the agent "remembers"
        cloud-drive files. Non-document items are recorded as file entities.
        """
        records: List[Dict[str, Any]] = []
        try:
            from integrations.onedrive_service import OneDriveService
            from core.connection_service import connection_service

            service = OneDriveService(tenant_id=self.tenant_id, config={})
            access_token = await service.get_access_token(self.tenant_id)
            if not access_token:
                # Fall back to the OAuth callback's IntegrationToken store
                # (auto-refreshing) — connection_service rows are not written
                # by the unified OAuth flow, so a fresh Microsoft connect has
                # no connection-service record.
                from integrations.outlook_service import outlook_service

                access_token = await outlook_service._get_access_token(None)
            if not access_token:
                logger.warning("OneDrive fetch skipped: no access token resolved")
                return []

            list_res = await service.list_files(access_token)
            if list_res.get("status") != "success":
                logger.warning(f"OneDrive list_files failed: {list_res.get('message')}")
                return []

            items = list_res.get("data", {}).get("value", [])

            # Download and parse documents that we can extract knowledge from.
            parseable_exts = (".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".md", ".pptx")
            try:
                from core.auto_document_ingestion import AutoDocumentIngestionService

                doc_ingestor = AutoDocumentIngestionService(workspace_id=self.workspace_id)
            except Exception:
                doc_ingestor = None
                logger.warning("AutoDocumentIngestionService unavailable; OneDrive content not parsed")

            for item in items:
                # Skip folders
                if "folder" in item:
                    continue
                file_id = item.get("id")
                name = item.get("name", "")
                record = {
                    "type": "onedrive_file",
                    "id": file_id,
                    "name": name,
                    "source": "onedrive",
                    "object_type": "file",
                    # top-level so the sync loop records it as a freshness signal
                    "modified_at": item.get("lastModifiedDateTime"),
                    "properties": {
                        "id": file_id,
                        "name": name,
                        "webUrl": item.get("webUrl"),
                        "size": item.get("size"),
                        "lastModifiedDateTime": item.get("lastModifiedDateTime"),
                        "createdDateTime": item.get("createdDateTime"),
                        "createdBy": item.get("createdBy"),
                    },
                }
                records.append(record)

                # Attempt content ingestion for parseable document types.
                if doc_ingestor and name.lower().endswith(parseable_exts):
                    try:
                        content_bytes = await service.download_file_bytes(access_token, file_id)
                        if content_bytes:
                            await doc_ingestor.process_file_bytes(
                                file_name=name,
                                content=content_bytes,
                                source="onedrive",
                                workspace_id=self.workspace_id,
                                role=role,
                            )
                    except Exception as content_err:
                        logger.debug(f"OneDrive content ingestion skipped for {name}: {content_err}")

            logger.info(f"OneDrive sync: fetched {len(records)} items")
        except Exception as e:
            logger.error(f"OneDrive fetch error: {e}")

        return records

    # =========================================================================
    # Google Drive ingestion fetcher
    # =========================================================================
    async def _fetch_google_drive_data(self, config: SyncConfiguration, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Google Drive files, download document content, and ingest into memory.

        Mirrors the OneDrive fetcher: lists files, downloads parseable document
        content and routes it through AutoDocumentIngestionService so the agent
        "remembers" Drive files.
        """
        records: List[Dict[str, Any]] = []
        try:
            from integrations.google_drive_service import GoogleDriveService

            service = GoogleDriveService(tenant_id=self.tenant_id, config={})
            access_token = await service.get_access_token(self.tenant_id)
            if not access_token:
                logger.warning("Google Drive fetch skipped: no access token resolved")
                return []

            list_res = await service.list_files(access_token)
            if list_res.get("status") != "success":
                logger.warning(f"Google Drive list_files failed: {list_res.get('message')}")
                return []

            items = list_res.get("data", {}).get("value", []) or list_res.get("data", {}).get("files", [])

            parseable_exts = (".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".md", ".pptx")
            try:
                from core.auto_document_ingestion import AutoDocumentIngestionService

                # Workspace-scoped ingestor: parses/writes into THIS
                # workspace's stores, not the default singleton's.
                doc_ingestor = AutoDocumentIngestionService(
                    workspace_id=self.workspace_id
                )
            except Exception:
                doc_ingestor = None
                logger.warning("AutoDocumentIngestionService unavailable; Google Drive content not parsed")

            for item in items:
                file_id = item.get("id")
                name = item.get("name", "")
                mime = item.get("mimeType", "")
                # Skip folders and Google-native formats that aren't directly parseable
                # (download_file_bytes exports them, but keep the file entity regardless).
                is_folder = mime == "application/vnd.google-apps.folder"
                record = {
                    "type": "google_drive_file",
                    "id": file_id,
                    "name": name,
                    "source": "google_drive",
                    "object_type": "folder" if is_folder else "file",
                    "properties": {
                        "id": file_id,
                        "name": name,
                        "mimeType": mime,
                        "webViewLink": item.get("webViewLink"),
                        "size": item.get("size"),
                        "modifiedTime": item.get("modifiedTime"),
                        "createdTime": item.get("createdTime"),
                    },
                }
                records.append(record)

                if doc_ingestor and not is_folder:
                    # download_file_bytes handles both binary files and Google Docs exports.
                    try:
                        content_bytes = await service.download_file_bytes(access_token, file_id)
                        if content_bytes:
                            await doc_ingestor.process_file_bytes(
                                file_name=name,
                                content=content_bytes,
                                source="google_drive",
                                workspace_id=self.workspace_id,
                                role=role,
                            )
                    except Exception as content_err:
                        logger.debug(f"Google Drive content ingestion skipped for {name}: {content_err}")

            logger.info(f"Google Drive sync: fetched {len(records)} items")
        except Exception as e:
            logger.error(f"Google Drive fetch error: {e}")

        return records

    # =========================================================================
    # Telegram ingestion fetcher (poll-based)
    # =========================================================================
    async def _fetch_telegram_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Poll recent Telegram bot updates and ingest messages into the knowledge graph.

        Uses getUpdates (long-poll disabled for ingestion; offset tracked in-memory).
        Each message becomes a record so the agent remembers chat conversations.
        """
        records: List[Dict[str, Any]] = []
        try:
            from core.communication.adapters.telegram import TelegramAdapter

            adapter = TelegramAdapter()
            updates = await adapter.get_updates(limit=config.max_records_per_sync)
            if not updates:
                return []

            for update in updates:
                message = update.get("message") or update.get("channel_post") or {}
                if not message:
                    continue
                text = message.get("text", "")
                chat = message.get("chat", {})
                sender = message.get("from", {})
                record = {
                    "type": "telegram_message",
                    "id": str(message.get("message_id", "")),
                    "name": f"Telegram message from {sender.get('username') or sender.get('first_name', 'unknown')}",
                    "source": "telegram",
                    "object_type": "message",
                    "text": text,
                    "properties": {
                        "message_id": message.get("message_id"),
                        "chat_id": chat.get("id"),
                        "chat_title": chat.get("title") or chat.get("username"),
                        "sender_id": sender.get("id"),
                        "sender_name": sender.get("username") or sender.get("first_name"),
                        "date": message.get("date"),
                        "text": text,
                    },
                }
                records.append(record)

            logger.info(f"Telegram sync: fetched {len(records)} messages")
        except Exception as e:
            logger.error(f"Telegram fetch error: {e}")

        return records

    async def _discover_schema(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Infer JSON Schema from a sample record using LLM refinement if available"""
        properties = {}
        
        # 1. Base inference
        for key, value in record.items():
            if key in ["raw_metadata"]: continue
            
            if isinstance(value, bool):
                properties[key] = {"type": "boolean"}
            elif isinstance(value, int):
                properties[key] = {"type": "integer"}
            elif isinstance(value, float):
                properties[key] = {"type": "number"}
            elif isinstance(value, dict):
                properties[key] = {"type": "object"}
            elif isinstance(value, list):
                properties[key] = {"type": "array"}
            else:
                properties[key] = {"type": "string"}
        
        # 2. LLM Refinement for metadata if available
        if self.llm:
            try:
                from pydantic import BaseModel
                
                class SchemaMetadata(BaseModel):
                    display_names: Dict[str, str]
                    descriptions: Dict[str, str]
                
                sample_json = json.dumps({k: record[k] for k in list(record.keys())[:10]}, indent=2)
                prompt = f"Analyze this Zoho record and provide human-readable display names and descriptions for these fields:\n\n{sample_json}"
                
                metadata = await self.llm.generate_structured_response(
                    prompt=prompt,
                    response_model=SchemaMetadata,
                    system_instruction="You are a data architect. Generate professional metadata for discovered CRM/ERP entities."
                )
                
                for key in properties:
                    if key in metadata.display_names:
                        properties[key]["title"] = metadata.display_names[key]
                    if key in metadata.descriptions:
                        properties[key]["description"] = metadata.descriptions[key]
            except Exception as e:
                logger.warning(f"LLM schema refinement failed: {e}")
                
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": properties
        }
    
    def _record_to_text(self, record: Dict[str, Any], integration_id: str) -> str:
        """Convert a record to searchable text for embedding"""
        parts = []
        
        record_type = record.get("type", "record")
        parts.append(f"{record_type.title()} from {integration_id}")
        
        # Add key fields
        for key in ["name", "title", "summary", "subject", "text", "description"]:
            if key in record and record[key]:
                parts.append(f"{key}: {record[key]}")
        
        # Add other relevant fields
        for key in ["email", "company", "stage", "status", "amount", "assignee", "channel"]:
            if key in record and record[key]:
                parts.append(f"{key}: {record[key]}")
        
        return "\n".join(parts)
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get summary of integration usage and sync status"""
        summary = {
            "workspace_id": self.workspace_id,
            "integrations": [],
            "total_synced_records": 0,
            "auto_sync_enabled_count": 0
        }
        
        for integration_id, stats in self.usage_stats.items():
            config = self.sync_configs.get(integration_id)
            
            integration_summary = {
                "id": integration_id,
                "name": stats.integration_name,
                "total_calls": stats.total_calls,
                "successful_calls": stats.successful_calls,
                "last_used": stats.last_used.isoformat() if stats.last_used else None,
                "last_synced": stats.last_synced.isoformat() if stats.last_synced else None,
                "auto_sync_enabled": stats.auto_sync_enabled,
                "entity_types": config.entity_types if config else []
            }
            
            summary["integrations"].append(integration_summary)
            
            if stats.auto_sync_enabled:
                summary["auto_sync_enabled_count"] += 1
        
        return summary
    
    async def run_scheduled_syncs(self):
        """Run scheduled syncs for all enabled integrations"""
        self._running = True
        logger.info(f"Starting scheduled sync service for workspace {self.workspace_id}")
        
        while self._running:
            try:
                for integration_id, stats in self.usage_stats.items():
                    if stats.auto_sync_enabled:
                        # Check if sync is due
                        should_sync = False
                        if not stats.last_synced:
                            should_sync = True
                        else:
                            minutes_since = (datetime.now(timezone.utc) - stats.last_synced).total_seconds() / 60
                            should_sync = minutes_since >= stats.sync_frequency_minutes
                        
                        if should_sync:
                            await self.sync_integration_data(integration_id)
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Scheduled sync error: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop the scheduled sync service"""
        self._running = False
        for task in self._sync_tasks.values():
            task.cancel()


# Global internal instance for single-tenant
_ingestion_service: Optional[HybridDataIngestionService] = None
# One instance PER workspace, kept alive side by side. The old single-global
# getter REPLACED the instance whenever a caller resolved a different
# workspace — destroying the running sync's lock + usage stats mid-flight
# (observed: suite sync badge flickered off and state vanished between polls
# because admin ("f348d47d…") and other callers ("default") alternated).
_ingestion_services: dict[tuple[str, str], HybridDataIngestionService] = {}


def get_hybrid_ingestion_service(workspace_id: str = "default", tenant_id: str = "default") -> HybridDataIngestionService:
    """Get or create the HybridDataIngestionService for this workspace."""
    global _ingestion_service
    key = (workspace_id, tenant_id)
    instance = _ingestion_services.get(key)
    if instance is None:
        instance = HybridDataIngestionService(workspace_id, tenant_id)
        _ingestion_services[key] = instance
    # Back-compat: code that reads the module global still gets a valid
    # instance (the most recently requested workspace).
    _ingestion_service = instance
    return instance


def record_integration_call(
    integration_id: str,
    integration_name: str,
    success: bool = True,
    user_id: Optional[str] = None
):
    """
    Convenience function to record an integration call.
    Should be called by integration routes/services.
    """
    service = get_hybrid_ingestion_service()
    service.record_integration_usage(integration_id, integration_name, success, user_id)
