"""
Hybrid Data Ingestion Service for Atom Memory
Automatically ingests data from frequently used integrations into Atom Memory.
Enables cross-system insights without manual configuration.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


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
    auto_sync_enabled: bool = False
    sync_frequency_minutes: int = 60  # Default: sync hourly


@dataclass
class SyncConfiguration:
    """Configuration for what data to sync from an integration"""
    integration_id: str
    entity_types: List[str] = field(default_factory=list)  # e.g., ["contacts", "deals", "tickets"]
    sync_last_n_days: int = 30
    max_records_per_sync: int = 1000
    include_metadata: bool = True


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
}


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
    
    def __init__(self):
        self.workspace_id = "default" # Single-tenant: always use default
        self.sync_configs: Dict[str, SyncConfiguration] = {}
        self._sync_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        
        # Initialize LanceDB handler
        try:
            from core.lancedb_handler import get_lancedb_handler
            self.memory_handler = get_lancedb_handler("default")
        except ImportError:
            self.memory_handler = None
            logger.warning("LanceDB handler not available for hybrid ingestion")
        
        # Initialize GraphRAG engine
        try:
            from core.graphrag_engine import graphrag_engine
            self.graphrag = graphrag_engine
        except ImportError:
            self.graphrag = None
            logger.warning("GraphRAG engine not available for hybrid ingestion")
    
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
        stats.last_used = datetime.utcnow()
        
        # Check if we should auto-enable sync
        if not stats.auto_sync_enabled:
            self._check_auto_enable_sync(integration_id)
        
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
    
    def enable_auto_sync(
        self, 
        integration_id: str,
        config: Optional[SyncConfiguration] = None
    ):
        """Enable automatic data sync for an integration"""
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
        else:
            # Create basic config
            self.sync_configs[integration_id] = SyncConfiguration(
                integration_id=integration_id,
                entity_types=["records"],
                sync_last_n_days=30
            )
        
        logger.info(f"Auto-sync enabled for {integration_id} in workspace {self.workspace_id}")
    
    def disable_auto_sync(self, integration_id: str):
        """Disable automatic data sync for an integration"""
        if integration_id in self.usage_stats:
            self.usage_stats[integration_id].auto_sync_enabled = False
        if integration_id in self._sync_tasks:
            self._sync_tasks[integration_id].cancel()
            del self._sync_tasks[integration_id]
        logger.info(f"Auto-sync disabled for {integration_id}")
    
    async def sync_integration_data(
        self, 
        integration_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Sync data from an integration into Atom Memory.
        
        Returns:
            Dict with sync results: records_synced, entities_extracted, etc.
        """
        stats = self.usage_stats.get(integration_id)
        config = self.sync_configs.get(integration_id)
        
        if not config:
            return {"error": f"No sync config for {integration_id}"}
        
        # Check if sync is needed (unless forced)
        if not force and stats and stats.last_synced:
            minutes_since_sync = (datetime.utcnow() - stats.last_synced).total_seconds() / 60
            if minutes_since_sync < stats.sync_frequency_minutes:
                return {"skipped": True, "reason": "Recently synced"}
        
        logger.info(f"Starting sync for {integration_id} in workspace {self.workspace_id}")
        
        results = {
            "integration_id": integration_id,
            "workspace_id": self.workspace_id,
            "started_at": datetime.utcnow().isoformat(),
            "records_fetched": 0,
            "records_ingested": 0,
            "entities_extracted": 0,
            "relationships_extracted": 0,
            "errors": []
        }
        
        try:
            # Fetch data from integration
            records = await self._fetch_integration_data(integration_id, config)
            results["records_fetched"] = len(records)
            
            # Ingest each record into Atom Memory
            for record in records:
                try:
                    # Convert record to text for embedding
                    text = self._record_to_text(record, integration_id)
                    
                    # Skip if no meaningful text
                    if not text or len(text) < 10:
                        continue
                    
                    # Ingest into LanceDB
                    if self.memory_handler:
                        success = self.memory_handler.add_document(
                            table_name=f"integration_{integration_id}",
                            text=text,
                            source=integration_id,
                            metadata={
                                "integration_id": integration_id,
                                "record_id": record.get("id", "unknown"),
                                "record_type": record.get("type", "unknown"),
                                "synced_at": datetime.utcnow().isoformat()
                            },
                            user_id=record.get("user_id", "system"),
                            extract_knowledge=True
                        )
                        if success:
                            results["records_ingested"] += 1
                    
                    # Also ingest into GraphRAG for entity/relationship extraction
                    if self.graphrag:
                        graphrag_result = self.graphrag.ingest_document(
                            workspace_id=self.workspace_id,
                            doc_id=f"{integration_id}_{record.get('id', 'unknown')}",
                            text=text,
                            source=integration_id
                        )
                        results["entities_extracted"] += graphrag_result.get("entities", 0)
                        results["relationships_extracted"] += graphrag_result.get("relationships", 0)
                
                except Exception as record_err:
                    results["errors"].append(str(record_err))
                    logger.warning(f"Failed to ingest record from {integration_id}: {record_err}")
            
            # Update last synced time
            if stats:
                stats.last_synced = datetime.utcnow()
            
            results["completed_at"] = datetime.utcnow().isoformat()
            results["success"] = True
            
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
    
    async def _fetch_integration_data(
        self, 
        integration_id: str, 
        config: SyncConfiguration
    ) -> List[Dict[str, Any]]:
        """
        Fetch data from an integration's API.
        This is a dispatcher that routes to specific integration fetchers.
        """
        records = []
        
        try:
            if integration_id == "salesforce":
                records = await self._fetch_salesforce_data(config)
            elif integration_id == "hubspot":
                records = await self._fetch_hubspot_data(config)
            elif integration_id == "slack":
                records = await self._fetch_slack_data(config)
            elif integration_id == "gmail":
                records = await self._fetch_gmail_data(config)
            elif integration_id == "notion":
                records = await self._fetch_notion_data(config)
            elif integration_id == "jira":
                records = await self._fetch_jira_data(config)
            elif integration_id == "zendesk":
                records = await self._fetch_zendesk_data(config)
            else:
                logger.warning(f"No fetcher implemented for {integration_id}")
        
        except Exception as e:
            logger.error(f"Failed to fetch data from {integration_id}: {e}")
        
        return records[:config.max_records_per_sync]
    
    async def _fetch_salesforce_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Salesforce"""
        records = []
        try:
            from integrations.salesforce_service import get_salesforce_client
            client = get_salesforce_client(self.workspace_id)
            
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
            from integrations.hubspot_service import get_hubspot_client
            client = get_hubspot_client(self.workspace_id)
            
            for entity_type in config.entity_types:
                if entity_type == "contacts":
                    contacts = client.crm.contacts.get_all(limit=100)
                    for c in contacts:
                        props = c.properties
                        records.append({
                            "id": c.id,
                            "type": "contact",
                            "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                            "email": props.get("email"),
                            "company": props.get("company")
                        })
                elif entity_type == "deals":
                    deals = client.crm.deals.get_all(limit=100)
                    for d in deals:
                        props = d.properties
                        records.append({
                            "id": d.id,
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
            from integrations.slack_service import get_slack_client
            client = get_slack_client(self.workspace_id)
            
            # Fetch recent messages from public channels
            channels = client.conversations_list(types="public_channel", limit=10)
            for channel in channels.get("channels", [])[:5]:
                history = client.conversations_history(
                    channel=channel["id"],
                    limit=50
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
        # Placeholder - would use Gmail API
        logger.info("Gmail fetcher not fully implemented")
        return records
    
    async def _fetch_notion_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Notion"""
        records = []
        # Placeholder - would use Notion API
        logger.info("Notion fetcher not fully implemented")
        return records
    
    async def _fetch_jira_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Jira"""
        records = []
        try:
            from integrations.jira_service import get_jira_client
            client = get_jira_client(self.workspace_id)
            
            issues = client.search_issues("updated >= -30d", maxResults=100)
            for issue in issues:
                records.append({
                    "id": issue.key,
                    "type": "issue",
                    "summary": issue.fields.summary,
                    "status": issue.fields.status.name,
                    "assignee": issue.fields.assignee.displayName if issue.fields.assignee else None,
                    "priority": issue.fields.priority.name if issue.fields.priority else None
                })
        except Exception as e:
            logger.error(f"Jira fetch error: {e}")
        return records
    
    async def _fetch_zendesk_data(self, config: SyncConfiguration) -> List[Dict[str, Any]]:
        """Fetch data from Zendesk"""
        records = []
        # Placeholder - would use Zendesk API
        logger.info("Zendesk fetcher not fully implemented")
        return records
    
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
                            minutes_since = (datetime.utcnow() - stats.last_synced).total_seconds() / 60
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


def get_hybrid_ingestion_service() -> HybridDataIngestionService:
    """Get or create the HybridDataIngestionService"""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = HybridDataIngestionService()
    return _ingestion_service


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
