"""
Hybrid Data Ingestion Service for Atom Memory
Automatically ingests data from frequently used integrations into Atom Memory.
Enables cross-system insights without manual configuration.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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
    sync_mode: str = "incremental"  # "incremental", "discovery"
    discovery_frequency_hours: int = 168  # Weekly by default


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
        entity_types=["crm_leads", "crm_deals", "books_invoices", "projects_tasks", "inventory_items", "inventory_sales_orders"],
        sync_last_n_days=30,
        max_records_per_sync=1000
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
    
    def __init__(self, workspace_id: str = "default", tenant_id: str = "default"):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        logger.error(f"DEBUG: HybridDataIngestionService initialized for {workspace_id} / {tenant_id}")
        self.usage_stats: Dict[str, IntegrationUsageStats] = {}
        self.sync_configs: Dict[str, SyncConfiguration] = {}
        self._sync_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        
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
    
    def enable_auto_sync(self, integration_id: str, config: Optional[SyncConfiguration] = None):
        """Enable automatic data sync for an integration"""
        logger.error(f"DEBUG: enable_auto_sync called for {integration_id}")
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
            logger.error(f"DEBUG: Loaded default sync config for {integration_id}: {self.sync_configs[integration_id]}")
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
        force: bool = False,
        discovery_mode: bool = False
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
            records = await self._fetch_integration_data(integration_id, config, discovery_mode=discovery_mode)
            results["records_fetched"] = len(records)
            
            # Ingest each record into Atom Memory
            seen_types = set()
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
                        if graphrag_result:
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
        discovery_mode: bool = False
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
                            # Fetch a single page for discovery/sync
                            response = await adapter.fetch_records(entity_type=etype, limit=100)
                            batch = response.get("results", [])
                            
                            for r in batch:
                                # Ensure record has type and source for ingestion loop
                                r["type"] = etype
                                r["source"] = integration_id
                                records.append(r)
                                
                            if len(records) >= config.max_records_per_sync:
                                break
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
            from integrations.notion_service import get_notion_service

            notion_service = get_notion_service()

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
        try:
            from integrations.zendesk_service import get_zendesk_service

            zendesk_service = get_zendesk_service()

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

    async def _fetch_zoho_multi_app_data(self, config: SyncConfiguration, discovery_mode: bool = False) -> List[Dict[str, Any]]:
        """Fetch data from all enabled Zoho applications using the Universal Adapter"""
        records = []
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
                
                logger.error(f"DEBUG: Token found for {self.tenant_id}: {token is not None}")
                if token:
                    logger.error(f"DEBUG: Token metadata: {token.metadata}")
                
                instance_url = token.instance_url if token else None
                adapter = ZohoAdapter(db=db, workspace_id=self.workspace_id, instance_url=instance_url)
                
                # Ensure we have a valid access token
                await adapter.ensure_token()
                
                for entity_type in config.entity_types:
                    if entity_type == "crm_leads":
                        records.extend(await adapter.get_leads(limit=100))
                    elif entity_type == "crm_deals":
                        records.extend(await adapter.get_deals(limit=100))
                    elif entity_type == "books_invoices":
                        # Note: Books requires organization_id which should be in connection metadata
                        org_id = token.metadata.get("organization_id") if token and token.metadata else None
                        if org_id:
                            records.extend(await adapter.get_invoices(organization_id=org_id, limit=100))
                    elif entity_type == "inventory_items":
                        org_id = token.metadata.get("organization_id") if token and token.metadata else None
                        if org_id:
                            records.extend(await adapter.get_items(organization_id=org_id, limit=100))
                    elif entity_type == "inventory_sales_orders":
                        org_id = token.metadata.get("organization_id") if token and token.metadata else None
                        if org_id:
                            records.extend(await adapter.get_sales_orders(organization_id=org_id, limit=100))
                    elif entity_type == "projects_tasks":
                        # Discovery mode gates expensive portal/project traversal
                        portal_id = token.metadata.get("portal_id") if token and token.metadata else None
                        
                        if discovery_mode and not portal_id:
                            portals = await adapter.get_portals()
                            if portals:
                                portal_id = portals[0]["id"]
                                # Update metadata if needed (deferred)
                                
                        projects = token.metadata.get("active_projects", []) if token and token.metadata else []
                        if discovery_mode and portal_id and not projects:
                            discovered_projects = await adapter.get_projects(portal_id)
                            projects = [p["id"] for p in discovered_projects[:3]]
                            
                        if portal_id:
                            for project_id in projects[:3]: # Sync top 3 active projects
                                records.extend(await adapter.get_tasks(portal_id=portal_id, project_id=project_id))
                                
                logger.info(f"Universal Zoho Sync (Discovery={discovery_mode}): Fetched {len(records)} items across modules")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Universal Zoho fetch error: {e}")
            
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


def get_hybrid_ingestion_service(workspace_id: str = "default", tenant_id: str = "default") -> HybridDataIngestionService:
    """Get or create the HybridDataIngestionService"""
    global _ingestion_service
    if _ingestion_service is None or _ingestion_service.workspace_id != workspace_id:
        _ingestion_service = HybridDataIngestionService(workspace_id, tenant_id)
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
