"""
ATOM Communication Apps Ingestion Pipeline - LanceDB Integration
Central memory system for all communication data with LanceDB vector storage
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
try:
    import lancedb
    import pyarrow as pa
    import pandas as pd
    import numpy as np
except ImportError:
    lancedb = None
    pa = None
    pd = None
    np = None
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Heavy dependencies (lancedb, pyarrow, pandas, numpy) not available. Using mocks.")
    from unittest.mock import MagicMock
    lancedb = MagicMock()
    pa = MagicMock()
    pd = MagicMock()
    np = MagicMock()

from pathlib import Path
from core.knowledge_ingestion import get_knowledge_ingestion

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except (ImportError, Exception) as e:
    SentenceTransformer = None
    logger.warning(f"sentence_transformers not available (error: {e}), embeddings will be disabled")

class CommunicationAppType(Enum):
    """Supported communication apps for ingestion"""
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    EMAIL = "email"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SMS = "sms"
    CALLS = "calls"
    MICROSOFT_TEAMS = "microsoft_teams"
    ZOOM = "zoom"
    NOTION = "notion"
    LINEAR = "linear"
    OUTLOOK = "outlook"
    GMAIL = "gmail"
    SALESFORCE = "salesforce"
    ASANA = "asana"
    DROPBOX = "dropbox"
    BOX = "box"
    TABLEAU = "tableau"
    ACCOUNTING = "accounting"
    ZOHO = "zoho"
    XERO = "xero"
    QUICKBOOKS = "quickbooks"
    CRM_LEAD = "crm_lead"
    CRM_DEAL = "crm_deal"

@dataclass
class CommunicationData:
    """Unified communication data structure"""
    id: str
    app_type: str
    timestamp: datetime
    direction: str  # inbound, outbound, internal
    sender: Optional[str]
    recipient: Optional[str]
    subject: Optional[str]
    content: str
    attachments: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    status: str
    priority: str
    tags: List[str]
    vector_embedding: Optional[List[float]] = None

@dataclass
class IngestionConfig:
    """Configuration for ingestion pipeline"""
    app_type: CommunicationAppType
    enabled: bool
    real_time: bool
    batch_size: int
    ingest_attachments: bool
    embed_content: bool
    retention_days: int
    vector_dim: int = 768

class LanceDBMemoryManager:
    """LanceDB-based memory manager for ATOM"""
    
    def __init__(self, db_path: str = None, workspace_id: Optional[str] = None):
        self.workspace_id = workspace_id or "default"
        base_path = db_path or os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
        self.db_path = Path(base_path) / self.workspace_id
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = None
        self.connections_table = None
        self.metadata_table = None
        self.model = None
        
    def initialize(self):
        """Initialize LanceDB connection and tables"""
        try:
            self.db = lancedb.connect(str(self.db_path))
            self._create_connections_table()
            self._create_metadata_table()
            
            # Initialize embedding model
            try:
                if SentenceTransformer:
                    logger.info("Loading embedding model (all-mpnet-base-v2)...")
                    self.model = SentenceTransformer('all-mpnet-base-v2')
                    logger.info("Embedding model loaded successfully")
                else:
                    logger.warning("Embedding model skipped (library missing)")
                    self.model = None
            except Exception as e:
                logger.error(f"Error loading embedding model: {str(e)}")
                # Continue without embeddings
                self.model = None
                
            logger.info("LanceDB memory manager initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing LanceDB: {str(e)}")
            return False
    
    def _create_connections_table(self):
        """Create communications table with vector search"""
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("app_type", pa.string()),
            pa.field("timestamp", pa.timestamp('us')),
            pa.field("direction", pa.string()),
            pa.field("sender", pa.string()),
            pa.field("recipient", pa.string()),
            pa.field("subject", pa.string()),
            pa.field("content", pa.string()),
            pa.field("attachments", pa.string()),  # JSON string
            pa.field("metadata", pa.string()),     # JSON string
            pa.field("status", pa.string()),
            pa.field("priority", pa.string()),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("vector", pa.list_(pa.float32(), 768)),  # For vector search
            pa.field("search_vector", pa.list_(pa.float32(), 768))  # Primary search vector
        ])
        
        # Check if table exists
        table_names = self.db.table_names()
        if "atom_communications" not in table_names:
            self.connections_table = self.db.create_table("atom_communications", schema=schema)
            logger.info("Created atom_communications table")
        else:
            self.connections_table = self.db.open_table("atom_communications")
            logger.info("Opened existing atom_communications table")
            
        # Create FTS index for hybrid search if it doesn't exist
        try:
            # Note: create_fts_index is idempotent in recent lancedb versions or we catch the error
            self.connections_table.create_fts_index("content", replace=False)
            logger.info("FTS index enabled on 'content' column")
        except Exception as e:
            logger.warning(f"Could not create FTS index (might already exist): {e}")
    
    def _create_metadata_table(self):
        """Create metadata table for ingestion pipeline"""
        schema = pa.schema([
            pa.field("app_type", pa.string()),
            pa.field("last_ingested", pa.timestamp('us')),
            pa.field("total_messages", pa.int64()),
            pa.field("config", pa.string()),
            pa.field("status", pa.string()),
        ])
        
        table_names = self.db.table_names()
        if "ingestion_metadata" not in table_names:
            self.metadata_table = self.db.create_table("ingestion_metadata", schema=schema)
            logger.info("Created ingestion_metadata table")
        else:
            self.metadata_table = self.db.open_table("ingestion_metadata")
            logger.info("Opened existing ingestion_metadata table")
    
    def ingest_communication(self, data: CommunicationData) -> bool:
        """Ingest single communication into LanceDB"""
        try:
            # Convert to record
            record = {
                "id": data.id,
                "app_type": data.app_type,
                "timestamp": data.timestamp,
                "direction": data.direction,
                "sender": data.sender,
                "recipient": data.recipient,
                "subject": data.subject,
                "content": data.content,
                "attachments": json.dumps(data.attachments),
                "metadata": json.dumps(data.metadata),
                "status": data.status,
                "priority": data.priority,
                "tags": data.tags,
                "vector": data.vector_embedding or [0.0] * 768,  # Default embedding
                "search_vector": data.vector_embedding or [0.0] * 768
            }
            
            # Add to database
            self.connections_table.add([record])
            
            # Update metadata
            self._update_metadata(data.app_type, 1)
            
            logger.info(f"Ingested communication {data.id} from {data.app_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error ingesting communication: {str(e)}")
            return False

    def ingest_generic_record(self, record_data: Any) -> bool:
        """Ingest a generic record (lead, contact, etc.) into LanceDB memory"""
        try:
            # For simplicity, we currently map generic records to the communications table
            # but with different metadata and record type markers.
            # In a more advanced version, we might use separate tables.
            
            # Map AtomRecordData to a format compatible with atom_communications table
            record = {
                "id": record_data.id,
                "app_type": record_data.app_type,
                "timestamp": record_data.timestamp,
                "direction": "internal", # Generic records are internal state
                "sender": "system",
                "recipient": "user",
                "subject": f"{record_data.record_type.value.title()}: {record_data.id}",
                "content": record_data.content,
                "attachments": "[]",
                "metadata": json.dumps({
                    **(record_data.metadata or {}),
                    "record_type": record_data.record_type.value,
                    "atom_unified_ingestion": True
                }),
                "status": "completed",
                "priority": "normal",
                "tags": [record_data.record_type.value],
                "vector": record_data.vector_embedding or self.generate_embedding(record_data.content),
                "search_vector": record_data.vector_embedding or self.generate_embedding(record_data.content)
            }
            
            # Add to database
            self.connections_table.add([record])
            
            # Update metadata
            self._update_metadata(record_data.app_type, 1)
            
            logger.info(f"Ingested generic record {record_data.id} ({record_data.record_type.value}) from {record_data.app_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error ingesting generic record: {str(e)}")
            return False
    
    def ingest_batch(self, data_list: List[CommunicationData]) -> bool:
        """Ingest batch of communications"""
        try:
            records = []
            for data in data_list:
                record = {
                    "id": data.id,
                    "app_type": data.app_type,
                    "timestamp": data.timestamp,
                    "direction": data.direction,
                    "sender": data.sender,
                    "recipient": data.recipient,
                    "subject": data.subject,
                    "content": data.content,
                    "attachments": json.dumps(data.attachments),
                    "metadata": json.dumps(data.metadata),
                    "status": data.status,
                    "priority": data.priority,
                    "tags": data.tags,
                    "vector": data.vector_embedding or [0.0] * 768,
                    "search_vector": data.vector_embedding or [0.0] * 768
                }
                records.append(record)
            
            # Add batch to database
            self.connections_table.add(records)
            
            # Update metadata
            self._update_metadata(data_list[0].app_type, len(data_list))
            
            logger.info(f"Ingested batch of {len(data_list)} communications")
            return True
            
        except Exception as e:
            logger.error(f"Error ingesting batch: {str(e)}")
            return False
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text content"""
        try:
            if not self.model:
                logger.warning("Embedding model not initialized, returning zero vector")
                return [0.0] * 768
                
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return [0.0] * 768

    def search_communications(self, query: str, limit: int = 10, app_type: str = None, tag: str = None) -> List[Dict]:
        """Search communications using hybrid search (vector + FTS)"""
        try:
            if not self.connections_table:
                logger.error("Connections table not initialized")
                return []
                
            # Generate query embedding for vector search
            query_vector = self.generate_embedding(query)
            
            # Perform hybrid search if FTS is available
            # In LanceDB, hybrid search is done by calling search() with a vector
            # and then filtering or using text search.
            # However, the most direct way for hybrid is often combining results or using the search API
            # with both text and vector if the version supports it directly.
            
            # For older lancedb, we might do:
            # search_builder = self.connections_table.search(query_vector, vector_column_name="vector")
            
            # For newer lancedb (hybrid):
            # Perform hybrid search
            try:
                # LanceDB 0.25.x hybrid search syntax: search(None, query_type="hybrid").vector(v).text(t)
                search_builder = (
                    self.connections_table.search(None, query_type="hybrid", vector_column_name="vector")
                    .vector(query_vector)
                    .text(query)
                    .limit(limit)
                )
            except Exception as e:
                logger.warning(f"Hybrid search failed, falling back to pure vector search: {e}")
                search_builder = self.connections_table.search(query_vector, vector_column_name="vector").limit(limit)
            
            if app_type:
                search_builder = search_builder.where(f"app_type = '{app_type}'")
            
            if tag:
                # Use array_has_any for tag filtering in LanceDB
                search_builder = search_builder.where(f"array_has_any(tags, ['{tag}'])")
            
            results = search_builder.to_pandas()
            
            return results.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error searching communications: {str(e)}")
            return []
    
    def get_communications_by_app(self, app_type: str, limit: int = 100) -> List[Dict]:
        """Get communications by app type"""
        try:
            results = self.connections_table.search().where(f"app_type = '{app_type}'").limit(limit).to_pandas()
            
            if not results.empty:
                # Sort in Pandas as LanceDB sorting in where clause can be finicky
                results = results.sort_values("timestamp", ascending=False)
            return results.to_dict('records')
        except Exception as e:
            logger.error(f"Error getting communications by app: {str(e)}")
            return []
    
    def get_communications_by_timeframe(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get communications within time frame"""
        try:
            # Use ISO format for timestamps in filters
            start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.%f')
            end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.%f')
            filter_query = f"timestamp >= to_timestamp('{start_str}') AND timestamp <= to_timestamp('{end_str}')"
            results = self.connections_table.search().where(filter_query).to_pandas()
            return results.to_dict('records')
        except Exception as e:
            logger.error(f"Error getting communications by timeframe: {str(e)}")
            return []
    
    def _update_metadata(self, app_type: str, message_count: int):
        """Update ingestion metadata"""
        try:
            # Get current metadata
            existing = self.metadata_table.search().where(f"app_type = '{app_type}'").to_pandas()
            
            if len(existing) > 0:
                # Update existing record
                current_count = existing.iloc[0]['total_messages']
                new_count = current_count + message_count
                
                update_data = {
                    "app_type": app_type,
                    "last_ingested": datetime.now(),
                    "total_messages": new_count,
                    "status": "active"
                }
                # Delete existing record
                self.metadata_table.delete(f"app_type = '{app_type}'")
                
                # Add updated record
                self.metadata_table.add([update_data])
            else:
                # Create new record
                metadata = {
                    "app_type": app_type,
                    "last_ingested": datetime.now(),
                    "total_messages": message_count,
                    "config": "{}",
                    "status": "active"
                }
                self.metadata_table.add([metadata])
                
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")

class CommunicationIngestionPipeline:
    """Main ingestion pipeline for all communication apps"""
    
    def __init__(self, memory_manager: LanceDBMemoryManager):
        self.memory_manager = memory_manager
        self.ingestion_configs = {}
        self.active_streams = {}
        self.fetch_timestamps = {}  # Track last fetch time for each app
        self.app_configs = {}  # Store app-specific configurations
        
    def configure_app(self, app_type: CommunicationAppType, config: IngestionConfig):
        """Configure ingestion for specific app"""
        config_dict = {
            **asdict(config),
            "app_type": app_type.value
        }
        self.ingestion_configs[app_type.value] = config_dict
        self.app_configs[app_type.value] = config_dict
        logger.info(f"Configured ingestion for {app_type.value}")
    
    async def ingest_message(self, app_type: str, message_data: Dict[str, Any]) -> bool:
        """Ingest single message from any communication app"""
        try:
            # Initialize memory manager if needed
            if not self.memory_manager.db:
                # Use executor for potentially blocking initialize
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.memory_manager.initialize)

            # Normalize message data
            normalized_data = self._normalize_message(app_type, message_data)
            
            # Convert to CommunicationData
            comm_data = CommunicationData(**normalized_data)
            
            # Generate embedding if needed
            if self.ingestion_configs.get(app_type, {}).get('embed_content', False):
                comm_data.vector_embedding = self._generate_embedding(comm_data.content)
            
            # Ingest into memory (run in executor to avoid blocking)
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(None, self.memory_manager.ingest_communication, comm_data)
            
            if success:
                # Trigger Knowledge Extraction asynchronously if enabled and content exists
                from core.automation_settings import get_automation_settings
                settings = get_automation_settings()
                
                if settings.is_automations_enabled() and settings.is_extraction_enabled() and comm_data.content and len(comm_data.content.strip()) > 20:
                    try:
                        # 1. Standard Knowledge Extraction
                        knowledge_manager = get_knowledge_ingestion()
                        # Use a background task if loop exists
                        try:
                            if loop.is_running():
                                loop.create_task(knowledge_manager.process_document(
                                    text=comm_data.content,
                                    doc_id=comm_data.id,
                                    source=f"integration:{app_type}",
                                    user_id=comm_data.metadata.get("user_id", "default_user")
                                ))
                                
                                # 2. Advanced Communication Intelligence (Intent + Responses)
                                from core.communication_intelligence import CommunicationIntelligenceService
                                intel_service = CommunicationIntelligenceService()
                                loop.create_task(intel_service.analyze_and_route(
                                    comm_data=asdict(comm_data),
                                    user_id=comm_data.metadata.get("user_id", "default_user")
                                ))
                        except RuntimeError:
                            # Not in an async context with a running loop
                            pass
                    except Exception as ex:
                        logger.error(f"Error triggering knowledge extraction in ingestion pipeline: {ex}")
                elif not settings.is_automations_enabled() or not settings.is_extraction_enabled():
                    logger.info(f"Knowledge extraction skipped for {comm_data.id} (automations disabled in settings)")
            
            return success
            
        except Exception as e:
            logger.error(f"Error ingesting message from {app_type}: {str(e)}")
            return False
    
    def start_real_time_stream(self, app_type: str):
        """Start real-time ingestion stream for app"""
        if app_type not in self.ingestion_configs:
            logger.error(f"App {app_type} not configured for ingestion")
            return False
        
        config = self.ingestion_configs[app_type]
        if not config.get('real_time', False):
            logger.info(f"Real-time ingestion not enabled for {app_type}")
            return False
        
        # Start async streaming task
        task = asyncio.create_task(self._real_time_ingestion(app_type))
        self.active_streams[app_type] = task
        
        logger.info(f"Started real-time ingestion stream for {app_type}")
        return True
    
    async def _real_time_ingestion(self, app_type: str):
        """Async real-time ingestion for specific app"""
        config = self.app_configs.get(app_type, {})
        polling_interval = config.get('polling_interval_seconds', 30)

        logger.info(f"Starting real-time ingestion for {app_type} (polling every {polling_interval}s)")

        while True:
            try:
                # Fetch new messages from the app's API
                new_messages = await self._fetch_new_messages(app_type)

                if new_messages:
                    logger.info(f"Fetched {len(new_messages)} new messages from {app_type}")

                    # Ingest each message
                    for message in new_messages:
                        try:
                            await self.ingest_message(app_type, message)
                        except Exception as e:
                            logger.error(f"Failed to ingest message from {app_type}: {e}")

                # Wait before next poll
                await asyncio.sleep(polling_interval)

            except Exception as e:
                logger.error(f"Error in real-time ingestion for {app_type}: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _fetch_new_messages(self, app_type: str) -> List[Dict[str, Any]]:
        """
        Fetch new messages from the app's API.
        This method implements app-specific polling logic.

        Args:
            app_type: The communication app type

        Returns:
            List of new message data dictionaries
        """
        # Get the last fetch timestamp for this app
        last_fetch_key = f"last_fetch_{app_type}"
        last_fetch = self.fetch_timestamps.get(last_fetch_key)

        try:
            # Fetch messages based on app type
            messages = []
            if app_type == CommunicationAppType.WHATSAPP.value:
                messages = await self._fetch_whatsapp_messages(last_fetch)
            elif app_type == CommunicationAppType.SLACK.value:
                messages = await self._fetch_slack_messages(last_fetch)
            elif app_type == CommunicationAppType.MICROSOFT_TEAMS.value:
                messages = await self._fetch_teams_messages(last_fetch)
            elif app_type == CommunicationAppType.EMAIL.value:
                messages = await self._fetch_email_messages(last_fetch)
            elif app_type == CommunicationAppType.GMAIL.value:
                messages = await self._fetch_gmail_messages(last_fetch)
            elif app_type == CommunicationAppType.OUTLOOK.value:
                messages = await self._fetch_outlook_messages(last_fetch)
            else:
                logger.warning(f"No polling implementation for {app_type}")

            # Update last fetch timestamp (only on success)
            self.fetch_timestamps[last_fetch_key] = datetime.now()

            return messages

        except Exception as e:
            logger.error(f"Error fetching messages from {app_type}: {e}")
            # Note: Don't update timestamp on error, so we can retry the same time range
            return []

    async def _fetch_whatsapp_messages(self, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """
        Fetch new WhatsApp messages via Business API or webhook buffer.

        For production, this should use the WhatsApp Business API for polling
        or integrate with a webhook receiver that buffers messages.
        """
        try:
            from integrations.atom_whatsapp_integration import whatsapp_integration_service

            messages = await whatsapp_integration_service.get_messages(
                since=last_fetch,
                limit=100
            )
            return messages
        except ImportError:
            logger.warning("WhatsApp integration service not available")
            return []
        except Exception as e:
            logger.error(f"Error fetching WhatsApp messages: {e}")
            return []

    async def _fetch_slack_messages(self, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """
        Fetch new Slack messages via Slack API.

        Uses the AsyncWebClient from slack_sdk to fetch message history.
        Implements cursor-based pagination and handles rate limiting.

        Requires:
        - SLACK_BOT_TOKEN environment variable
        - channels:history OAuth scope
        - Configured monitored_channels in app config
        """
        try:
            import os
            from slack_sdk.web.async_client import AsyncWebClient
            from slack_sdk.errors import SlackApiError

            bot_token = os.getenv("SLACK_BOT_TOKEN")
            if not bot_token:
                logger.warning("SLACK_BOT_TOKEN not configured for Slack polling")
                return []

            # Get list of channels to monitor
            config = self.app_configs.get(CommunicationAppType.SLACK.value, {})
            channels = config.get("monitored_channels", [])

            if not channels:
                logger.info("No Slack channels configured for monitoring")
                return []

            # Calculate oldest timestamp
            oldest_ts = None
            if last_fetch:
                oldest_ts = str(last_fetch.timestamp())
                logger.debug(f"Fetching Slack messages since {oldest_ts}")
            else:
                logger.debug("Fetching recent Slack messages (no timestamp provided)")

            all_messages = []
            client = AsyncWebClient(token=bot_token)

            # Fetch messages from each channel
            for channel_id in channels:
                try:
                    logger.debug(f"Fetching messages from Slack channel {channel_id}")

                    # Fetch conversations history with pagination
                    cursor = None
                    messages_count = 0

                    while True:
                        # API call to fetch messages
                        response = await client.conversations_history(
                            channel=channel_id,
                            oldest=oldest_ts,
                            limit=100,  # Max messages per request
                            cursor=cursor,
                            inclusive=False  # Exclude the message with oldest_ts
                        )

                        if not response.get("ok"):
                            error_msg = response.get("error", "Unknown error")
                            logger.error(f"Slack API error for channel {channel_id}: {error_msg}")
                            break

                        messages = response.get("messages", [])
                        if not messages:
                            logger.debug(f"No more messages in channel {channel_id}")
                            break

                        # Process and normalize messages
                        for msg in messages:
                            # Skip messages from bots (unless configured to include)
                            msg_type = msg.get("type", "")
                            subtype = msg.get("subtype", "")
                            bot_id = msg.get("bot_id", "")

                            if msg_type != "message":
                                continue

                            # Skip bot messages unless configured
                            if bot_id and not config.get("include_bot_messages", False):
                                continue

                            # Skip message changed/deleted events
                            if subtype in ["message_changed", "message_deleted"]:
                                continue

                            # Normalize message
                            normalized_msg = {
                                "id": msg.get("ts"),  # Use timestamp as ID
                                "app_type": CommunicationAppType.SLACK.value,
                                "timestamp": datetime.fromtimestamp(float(msg.get("ts")), tz=timezone.utc),
                                "direction": "inbound",
                                "sender": msg.get("user", "UNKNOWN"),
                                "recipient": channel_id,  # Channel ID
                                "subject": None,  # Slack messages don't have subjects
                                "content": msg.get("text", ""),
                                "attachments": msg.get("files", []),
                                "metadata": {
                                    "channel_id": channel_id,
                                    "channel_name": await self._get_channel_name(client, channel_id),
                                    "thread_ts": msg.get("thread_ts"),
                                    "parent_user_id": msg.get("parent_user_id"),
                                    "subtype": subtype,
                                    "reactions": msg.get("reactions", []),
                                    "slack_metadata": msg
                                },
                                "status": "active",
                                "priority": "normal",
                                "tags": []
                            }

                            all_messages.append(normalized_msg)
                            messages_count += 1

                        # Check for pagination
                        cursor = response.get("response_metadata", {}).get("next_cursor")
                        if not cursor:
                            logger.debug(f"Fetched {messages_count} messages from channel {channel_id}")
                            break

                        # Rate limiting: small delay between pagination requests
                        await asyncio.sleep(0.5)

                    logger.info(f"Successfully fetched {messages_count} messages from Slack channel {channel_id}")

                except SlackApiError as e:
                    if e.response.get("error") == "ratelimited":
                        # Handle rate limiting
                        retry_after = int(e.response.headers.get("Retry-After", 60))
                        logger.warning(f"Slack API rate limited. Retry after {retry_after}s")
                        # Don't block other channels, just skip this one for now
                        continue
                    else:
                        logger.error(f"Slack API error for channel {channel_id}: {e}")
                        continue

                except Exception as e:
                    logger.error(f"Error fetching from Slack channel {channel_id}: {e}")
                    continue

            # Close the client
            await client.close()

            # Sort by timestamp (oldest first)
            all_messages.sort(key=lambda m: m["timestamp"])

            logger.info(f"Total Slack messages fetched: {len(all_messages)}")
            return all_messages

        except ImportError:
            logger.error("slack_sdk not available. Install with: pip install slack_sdk")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Slack messages: {e}")
            return []

    async def _get_channel_name(self, client, channel_id: str) -> Optional[str]:
        """Get channel name from channel ID"""
        try:
            response = await client.conversations_info(channel=channel_id)
            if response.get("ok"):
                return response.get("channel", {}).get("name")
        except Exception as e:
            logger.debug(f"Could not get channel name for {channel_id}: {e}")
        return None

    async def _fetch_teams_messages(self, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """
        Fetch new Microsoft Teams messages via Microsoft Graph API.

        Fetches from:
        - 1:1 chats
        - Group chats
        - Channel messages (from joined teams)

        Requires Microsoft Teams OAuth access token with Chat.Read, ChannelMessage.Read.All scopes.
        """
        try:
            from core.token_storage import token_storage

            token_data = token_storage.get_token("microsoft")
            if not token_data:
                logger.warning("No Microsoft OAuth token found for Teams polling")
                return []

            access_token = token_data.get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}

            all_messages = []

            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Fetch 1:1 and group chats
                all_messages.extend(await self._fetch_teams_chat_messages(client, headers, last_fetch))

                # 2. Fetch channel messages from teams
                all_messages.extend(await self._fetch_teams_channel_messages(client, headers, last_fetch))

                # Sort by timestamp
                all_messages.sort(key=lambda m: m.get("timestamp", datetime.min))

                logger.info(f"Fetched {len(all_messages)} total messages from Microsoft Teams")
                return all_messages

        except ImportError:
            logger.warning("token_storage module not available for Teams polling")
            return []
        except Exception as e:
            logger.error(f"Error fetching Teams messages: {e}")
            return []

    async def _fetch_teams_chat_messages(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        last_fetch: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Fetch messages from Teams chats (1:1 and group chats)"""
        all_messages = []

        try:
            # Get all chats
            chats_response = await client.get(
                "https://graph.microsoft.com/v1.0/me/chats",
                headers=headers
            )

            if chats_response.status_code != 200:
                logger.warning(f"Failed to fetch Teams chats: {chats_response.status_code}")
                return []

            chats = chats_response.json().get("value", [])
            logger.debug(f"Found {len(chats)} Teams chats")

            for chat in chats:
                chat_id = chat.get("id")
                if not chat_id:
                    continue

                # Build filter for messages since last fetch
                filter_str = None
                if last_fetch:
                    filter_str = f"createdDateTime gt {last_fetch.isoformat()}"

                # Get messages from each chat
                params = {"$top": 50}  # Reduced batch size for better performance
                if filter_str:
                    params["$filter"] = filter_str

                try:
                    msgs_response = await client.get(
                        f"https://graph.microsoft.com/v1.0/me/chats/{chat_id}/messages",
                        headers=headers,
                        params=params
                    )

                    if msgs_response.status_code == 200:
                        messages = msgs_response.json().get("value", [])

                        # Normalize messages
                        for msg in messages:
                            # Extract sender info
                            from_user = msg.get("from", {}).get("user", {})
                            sender_display_name = from_user.get("displayName", "UNKNOWN")
                            sender_email = from_user.get("email", "")

                            # Extract content (handle different formats)
                            body_content = msg.get("body", {})
                            content = body_content.get("content", "")
                            content_type = body_content.get("contentType", "text")

                            # Handle Adaptive Cards
                            attachments = msg.get("attachments", [])
                            adaptive_card_data = None
                            for attachment in attachments:
                                if attachment.get("contentType") == "application/vnd.microsoft.card.adaptive":
                                    adaptive_card_data = attachment.get("content", {})

                            normalized_msg = {
                                "id": msg.get("id"),
                                "app_type": CommunicationAppType.MICROSOFT_TEAMS.value,
                                "timestamp": datetime.fromisoformat(
                                    msg.get("createdDateTime", datetime.now().isoformat())
                                ).replace(tzinfo=None),
                                "direction": "inbound",
                                "sender": sender_display_name,
                                "sender_email": sender_email,
                                "recipient": chat_id,
                                "subject": msg.get("subject"),
                                "content": content,
                                "content_type": content_type,
                                "attachments": attachments,
                                "metadata": {
                                    "chat_id": chat_id,
                                    "chat_type": chat.get("chatType"),
                                    "chat_title": chat.get("topic"),
                                    "web_url": msg.get("webUrl"),
                                    "message_type": msg.get("messageType"),
                                    "created_datetime": msg.get("createdDateTime"),
                                    "last_modified_datetime": msg.get("lastModifiedDateTime"),
                                    "adaptive_card": adaptive_card_data,
                                    "teams_metadata": msg
                                },
                                "status": "active",
                                "priority": "normal",
                                "tags": ["teams", "chat"]
                            }
                            all_messages.append(normalized_msg)

                    elif msgs_response.status_code == 429:
                        # Rate limited - wait and retry
                        retry_after = int(msgs_response.headers.get("Retry-After", 30))
                        logger.warning(f"Teams API rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)

                except Exception as e:
                    logger.error(f"Error fetching messages from chat {chat_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in _fetch_teams_chat_messages: {e}")

        return all_messages

    async def _fetch_teams_channel_messages(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        last_fetch: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Fetch messages from Teams channels (requires ChannelMessage.Read.All permission)"""
        all_messages = []

        try:
            # Get joined teams
            teams_response = await client.get(
                "https://graph.microsoft.com/v1.0/me/joinedTeams",
                headers=headers
            )

            if teams_response.status_code != 200:
                logger.debug(f"Could not fetch Teams (may need ChannelMessage.Read.All permission): {teams_response.status_code}")
                return []

            teams = teams_response.json().get("value", [])
            logger.debug(f"Found {len(teams)} joined Teams")

            for team in teams:
                team_id = team.get("id")
                team_name = team.get("displayName", "Unknown Team")

                if not team_id:
                    continue

                # Get channels for this team
                channels_response = await client.get(
                    f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels",
                    headers=headers
                )

                if channels_response.status_code != 200:
                    logger.debug(f"Could not fetch channels for team {team_id}")
                    continue

                channels = channels_response.json().get("value", [])

                for channel in channels:
                    channel_id = channel.get("id")
                    channel_name = channel.get("displayName", "General")

                    if not channel_id:
                        continue

                    # Build filter for messages since last fetch
                    filter_str = None
                    if last_fetch:
                        filter_str = f"createdDateTime gt {last_fetch.isoformat()}"

                    # Get messages from channel
                    params = {"$top": 50}
                    if filter_str:
                        params["$filter"] = filter_str

                    try:
                        msgs_response = await client.get(
                            f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages",
                            headers=headers,
                            params=params
                        )

                        if msgs_response.status_code == 200:
                            messages = msgs_response.json().get("value", [])

                            for msg in messages:
                                from_user = msg.get("from", {}).get("user", {})
                                sender_display_name = from_user.get("displayName", "UNKNOWN")
                                sender_email = from_user.get("email", "")

                                body_content = msg.get("body", {})
                                content = body_content.get("content", "")
                                content_type = body_content.get("contentType", "text")

                                attachments = msg.get("attachments", [])

                                normalized_msg = {
                                    "id": msg.get("id"),
                                    "app_type": CommunicationAppType.MICROSOFT_TEAMS.value,
                                    "timestamp": datetime.fromisoformat(
                                        msg.get("createdDateTime", datetime.now().isoformat())
                                    ).replace(tzinfo=None),
                                    "direction": "inbound",
                                    "sender": sender_display_name,
                                    "sender_email": sender_email,
                                    "recipient": f"{team_name}/{channel_name}",
                                    "subject": msg.get("subject"),
                                    "content": content,
                                    "content_type": content_type,
                                    "attachments": attachments,
                                    "metadata": {
                                        "team_id": team_id,
                                        "team_name": team_name,
                                        "channel_id": channel_id,
                                        "channel_name": channel_name,
                                        "web_url": msg.get("webUrl"),
                                        "message_type": msg.get("messageType"),
                                        "reply_to_id": msg.get("replyToId"),
                                        "created_datetime": msg.get("createdDateTime"),
                                        "last_modified_datetime": msg.get("lastModifiedDateTime"),
                                        "teams_metadata": msg
                                    },
                                    "status": "active",
                                    "priority": "normal",
                                    "tags": ["teams", "channel"]
                                }
                                all_messages.append(normalized_msg)

                        elif msgs_response.status_code == 429:
                            # Rate limited
                            retry_after = int(msgs_response.headers.get("Retry-After", 30))
                            logger.warning(f"Teams channel API rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)

                    except Exception as e:
                        logger.error(f"Error fetching messages from channel {channel_id}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error in _fetch_teams_channel_messages: {e}")

        return all_messages

    async def _fetch_email_messages(self, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """Fetch new email messages via IMAP"""
        try:
            import imaplib
            import email
            from email.header import decode_header

            imap_server = os.getenv("IMAP_SERVER")
            imap_user = os.getenv("IMAP_USER")
            imap_password = os.getenv("IMAP_PASSWORD")

            if not all([imap_server, imap_user, imap_password]):
                logger.warning("IMAP credentials not configured - set IMAP_SERVER, IMAP_USER, IMAP_PASSWORD")
                return []

            # Run IMAP operations in executor to avoid blocking
            loop = asyncio.get_running_loop()
            messages = await loop.run_in_executor(None, self._fetch_imap_messages, imap_server, imap_user, imap_password, last_fetch)

            return messages

        except Exception as e:
            logger.error(f"Error fetching email via IMAP: {e}")
            return []

    def _fetch_imap_messages(self, imap_server: str, imap_user: str, imap_password: str, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """Synchronous IMAP fetching - runs in executor"""
        try:
            import imaplib
            import email
            from email.header import decode_header

            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(imap_user, imap_password)
            mail.select("INBOX")

            # Search for new messages
            since_date = last_fetch.strftime("%d-%b-%Y") if last_fetch else "01-Jan-1970"
            status, messages = mail.search(None, f'(SINCE "{since_date}")')

            messages_data = []

            if status == "OK":
                for msg_id in messages[0].split()[-100:]:  # Limit to last 100 messages
                    _, msg_data = mail.fetch(msg_id, "(RFC822)")

                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])

                            # Decode subject
                            subject = msg.get("Subject", "")
                            if subject:
                                decoded_parts = decode_header(subject)
                                subject = ""
                                for content, encoding in decoded_parts:
                                    if isinstance(content, bytes):
                                        subject += content.decode(encoding or "utf-8", errors="ignore")
                                    else:
                                        subject += content

                            # Get email body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    content_disposition = str(part.get("Content-Disposition", ""))

                                    if content_type == "text/plain" and "attachment" not in content_disposition:
                                        try:
                                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                            break
                                        except:
                                            pass
                            else:
                                try:
                                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                                except:
                                    body = msg.get_payload()

                            # Extract attachments
                            attachments = []
                            for part in msg.walk():
                                if part.get_filename():
                                    attachments.append({
                                        "filename": part.get_filename(),
                                        "size": part.get("Content-Length"),
                                        "content_type": part.get_content_type()
                                    })

                            messages_data.append({
                                "id": msg_id.decode(),
                                "app_type": CommunicationAppType.EMAIL.value,
                                "timestamp": datetime.fromtimestamp(email.utils.mktime_tz(email.utils.parsedate_tz(msg.get("Date")))),
                                "direction": "inbound",
                                "sender": msg.get("From"),
                                "recipient": msg.get("To"),
                                "subject": subject,
                                "content": body,
                                "attachments": attachments,
                                "metadata": {
                                    "message_id": msg.get("Message-ID"),
                                    "thread_id": msg.get("Thread-Index"),
                                    "email_metadata": {
                                        "cc": msg.get("CC"),
                                        "reply_to": msg.get("Reply-To"),
                                        "in_reply_to": msg.get("In-Reply-To")
                                    }
                                },
                                "status": "active",
                                "priority": "normal",
                                "tags": []
                            })

            mail.close()
            mail.logout()

            logger.info(f"Fetched {len(messages_data)} messages via IMAP")
            return messages_data

        except Exception as e:
            logger.error(f"IMAP fetch error: {e}")
            return []

    async def _fetch_gmail_messages(self, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """
        Fetch new Gmail messages via Gmail API.

        Requires Gmail OAuth access token with gmail.readonly scope.
        Supports incremental fetching and proper message normalization.
        """
        try:
            from integrations.gmail_service import GmailService
            import asyncio

            gmail_service = GmailService()

            # Check if authenticated
            if not gmail_service.service:
                # Try to authenticate
                try:
                    gmail_service._authenticate()
                except Exception as e:
                    logger.warning(f"Gmail authentication failed: {e}")
                    return []

            if not gmail_service.service:
                logger.warning("Gmail service not available after authentication attempt")
                return []

            # Build query for incremental fetching
            query = ""
            if last_fetch:
                # Gmail search query for messages after a date
                # Format: after:YYYY/MM/DD
                date_str = last_fetch.strftime("%Y/%m/%d")
                query = f"after:{date_str}"

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None,
                lambda: gmail_service.get_messages(query=query, max_results=100)
            )

            # Normalize to unified message format
            normalized_messages = []
            for msg in messages:
                try:
                    # Parse timestamp from Gmail message
                    timestamp_str = msg.get("timestamp")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str)
                        except (ValueError, TypeError):
                            timestamp = datetime.fromtimestamp(int(timestamp_str))
                    else:
                        timestamp = datetime.now()

                    # Extract sender name and email
                    sender = msg.get("sender", "")
                    sender_name = sender
                    sender_email = sender

                    # Parse email from "Name <email@domain.com>" format
                    if "<" in sender and ">" in sender:
                        parts = sender.rsplit("<", 1)
                        sender_name = parts[0].strip()
                        sender_email = parts[1].rstrip(">")
                    elif "@" in sender:
                        sender_email = sender
                        sender_name = sender.split("@")[0]

                    # Extract recipients
                    recipient = msg.get("recipient", "")
                    recipients_list = recipient.split(",") if recipient else []

                    # Parse attachments
                    attachments_data = msg.get("attachments", [])
                    attachments = []
                    for att in attachments_data:
                        attachments.append({
                            "id": att.get("id"),
                            "filename": att.get("filename"),
                            "size": att.get("size"),
                            "content_type": att.get("contentType")
                        })

                    normalized_msg = {
                        "id": msg.get("id"),
                        "app_type": CommunicationAppType.GMAIL.value,
                        "timestamp": timestamp,
                        "direction": "inbound",
                        "sender": sender_name,
                        "sender_email": sender_email,
                        "recipient": recipient,
                        "subject": msg.get("subject", ""),
                        "content": msg.get("body", ""),
                        "content_type": "text",
                        "attachments": attachments,
                        "metadata": {
                            "thread_id": msg.get("threadId"),
                            "label_ids": msg.get("labelIds", []),
                            "snippet": msg.get("snippet", ""),
                            "history_id": msg.get("historyId"),
                            "internal_date": msg.get("internalDate"),
                            "size_estimate": msg.get("sizeEstimate"),
                            "gmail_metadata": msg
                        },
                        "status": "active",
                        "priority": "high" if "IMPORTANT" in msg.get("labelIds", []) else "normal",
                        "tags": ["gmail"] + msg.get("labelIds", [])
                    }
                    normalized_messages.append(normalized_msg)

                except Exception as e:
                    logger.error(f"Error normalizing Gmail message {msg.get('id')}: {e}")
                    continue

            logger.info(f"Fetched {len(normalized_messages)} messages from Gmail")
            return normalized_messages

        except ImportError:
            logger.warning("Gmail service not available")
            return []
        except Exception as e:
            logger.error(f"Error fetching Gmail messages: {e}")
            return []

    async def _fetch_outlook_messages(self, last_fetch: Optional[datetime]) -> List[Dict[str, Any]]:
        """
        Fetch new Outlook messages via Microsoft Graph API.

        Requires Outlook OAuth access token with Mail.Read permission.
        Supports incremental fetching and rate limiting.
        """
        try:
            from core.token_storage import token_storage

            token_data = token_storage.get_token("microsoft")
            if not token_data:
                logger.warning("No Microsoft OAuth token found for Outlook polling")
                return []

            access_token = token_data.get("access_token")
            headers = {"Authorization": f"Bearer {access_token}"}

            all_messages = []

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Build filter for messages since last fetch
                params = {"$top": 50}
                if last_fetch:
                    params["$filter"] = f"receivedDateTime gt {last_fetch.isoformat()}"

                # Pagination support
                next_link = None
                fetch_count = 0
                max_fetches = 5  # Prevent infinite loops

                while fetch_count < max_fetches:
                    try:
                        if next_link:
                            response = await client.get(next_link, headers=headers)
                        else:
                            response = await client.get(
                                "https://graph.microsoft.com/v1.0/me/messages",
                                headers=headers,
                                params=params
                            )

                        if response.status_code == 429:
                            # Rate limited
                            retry_after = int(response.headers.get("Retry-After", 30))
                            logger.warning(f"Outlook API rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue

                        elif response.status_code != 200:
                            logger.error(f"Failed to fetch Outlook messages: {response.status_code}")
                            break

                        data = response.json()
                        messages = data.get("value", [])

                        # Normalize messages
                        for msg in messages:
                            try:
                                # Parse timestamp
                                received_datetime = msg.get("receivedDateTime")
                                if received_datetime:
                                    timestamp = datetime.fromisoformat(received_datetime)
                                else:
                                    timestamp = datetime.now()

                                # Extract sender
                                from_data = msg.get("from", {})
                                sender_email = from_data.get("emailAddress", {}).get("address", "UNKNOWN")
                                sender_name = from_data.get("emailAddress", {}).get("name", sender_email)

                                # Extract recipients
                                to_recipients = msg.get("toRecipients", [])
                                recipients_list = [
                                    recipient.get("emailAddress", {}).get("address", "")
                                    for recipient in to_recipients
                                ]
                                recipient = ", ".join(filter(None, recipients_list))

                                # Extract body content (prefer HTML, fallback to text)
                                body_data = msg.get("body", {})
                                body_content = body_data.get("content", "")
                                body_type = body_data.get("contentType", "text")

                                # Parse attachments
                                attachments_data = msg.get("attachments", [])
                                attachments = []
                                for att in attachments_data:
                                    attachments.append({
                                        "id": att.get("id"),
                                        "name": att.get("name"),
                                        "size": att.get("size"),
                                        "content_type": att.get("contentType"),
                                        "is_inline": att.get("isInline", False)
                                    })

                                normalized_msg = {
                                    "id": msg.get("id"),
                                    "app_type": CommunicationAppType.OUTLOOK.value,
                                    "timestamp": timestamp,
                                    "direction": "inbound",
                                    "sender": sender_name,
                                    "sender_email": sender_email,
                                    "recipient": recipient,
                                    "subject": msg.get("subject", ""),
                                    "content": body_content,
                                    "content_type": body_type,
                                    "attachments": attachments,
                                    "metadata": {
                                        "conversation_id": msg.get("conversationId"),
                                        "parent_folder_id": msg.get("parentFolderId"),
                                        "importance": msg.get("importance"),
                                        "is_read": msg.get("isRead"),
                                        "is_draft": msg.get("isRead", False),
                                        "flag": msg.get("flag"),
                                        "web_link": msg.get("webLink"),
                                        "outlook_metadata": msg
                                    },
                                    "status": "read" if msg.get("isRead") else "unread",
                                    "priority": "high" if msg.get("importance") == "High" else "normal",
                                    "tags": ["outlook"]
                                }

                                # Add category tags if present
                                categories = msg.get("categories", [])
                                if categories:
                                    normalized_msg["tags"].extend(categories)

                                all_messages.append(normalized_msg)

                            except Exception as e:
                                logger.error(f"Error normalizing Outlook message {msg.get('id')}: {e}")
                                continue

                        # Check for next page
                        next_link = data.get("@odata.nextLink")
                        if not next_link:
                            break

                        fetch_count += 1

                    except Exception as e:
                        logger.error(f"Error fetching Outlook messages page: {e}")
                        break

            logger.info(f"Fetched {len(all_messages)} messages from Outlook")
            return all_messages

        except ImportError:
            logger.warning("token_storage module not available for Outlook polling")
            return []
        except Exception as e:
            logger.error(f"Error fetching Outlook messages: {e}")
            return []
    
    def _normalize_message(self, app_type: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message data from different apps to unified format"""
        
        # WhatsApp normalization
        if app_type == CommunicationAppType.WHATSAPP.value:
            return {
                "id": message_data.get("id", f"wa_{datetime.now().isoformat()}"),
                "app_type": app_type,
                "timestamp": datetime.fromisoformat(message_data.get("timestamp", datetime.now().isoformat())),
                "direction": message_data.get("direction", "inbound"),
                "sender": message_data.get("from"),
                "recipient": message_data.get("to"),
                "subject": None,
                "content": message_data.get("content", ""),
                "attachments": message_data.get("attachments", []),
                "metadata": {
                    "message_type": message_data.get("message_type", "text"),
                    "status": message_data.get("status", "delivered"),
                    "whatsapp_metadata": message_data.get("metadata", {})
                },
                "status": "active",
                "priority": "normal",
                "tags": message_data.get("tags", [])
            }
        
        # Email normalization
        elif app_type in [CommunicationAppType.EMAIL.value, CommunicationAppType.GMAIL.value, CommunicationAppType.OUTLOOK.value]:
            return {
                "id": message_data.get("id", f"email_{datetime.now().isoformat()}"),
                "app_type": app_type,
                "timestamp": datetime.fromisoformat(message_data.get("date", datetime.now().isoformat())),
                "direction": "inbound" if message_data.get("from") != "user" else "outbound",
                "sender": message_data.get("from"),
                "recipient": message_data.get("to"),
                "subject": message_data.get("subject"),
                "content": message_data.get("body", ""),
                "attachments": message_data.get("attachments", []),
                "metadata": {
                    "message_id": message_data.get("message_id"),
                    "thread_id": message_data.get("thread_id"),
                    "email_metadata": message_data.get("metadata", {})
                },
                "status": "active",
                "priority": message_data.get("priority", "normal"),
                "tags": message_data.get("tags", [])
            }
        
        # Generic normalization for other apps
        else:
            return {
                "id": message_data.get("id", f"{app_type}_{datetime.now().isoformat()}"),
                "app_type": app_type,
                "timestamp": datetime.fromisoformat(message_data.get("timestamp", datetime.now().isoformat())),
                "direction": message_data.get("direction", "inbound"),
                "sender": message_data.get("sender"),
                "recipient": message_data.get("recipient"),
                "subject": message_data.get("subject"),
                "content": message_data.get("content", ""),
                "attachments": message_data.get("attachments", []),
                "metadata": message_data.get("metadata", {}),
                "status": message_data.get("status", "active"),
                "priority": message_data.get("priority", "normal"),
                "tags": message_data.get("tags", [])
            }
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text content"""
        return self.memory_manager.generate_embedding(text)
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        try:
            # Get metadata from LanceDB
            metadata = self.memory_manager.metadata_table.search().to_pandas()
            
            stats = {
                "configured_apps": list(self.ingestion_configs.keys()),
                "active_streams": list(self.active_streams.keys()),
                "total_messages": 0,
                "app_stats": {}
            }
            
            for _, row in metadata.iterrows():
                stats["app_stats"][row["app_type"]] = {
                    "total_messages": row["total_messages"],
                    "last_ingested": row["last_ingested"],
                    "status": row["status"]
                }
                stats["total_messages"] += row["total_messages"]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting ingestion stats: {str(e)}")
            return {"error": str(e)}

# Handle multiple managers for physical isolation
_workspace_memory_managers: Dict[str, 'LanceDBMemoryManager'] = {}

def get_memory_manager(workspace_id: Optional[str] = None) -> LanceDBMemoryManager:
    """Get workspace-isolated memory manager"""
    ws_id = workspace_id or "default"
    if ws_id not in _workspace_memory_managers:
        _workspace_memory_managers[ws_id] = LanceDBMemoryManager(workspace_id=ws_id)
    return _workspace_memory_managers[ws_id]

# Legacy instance for backward compatibility
memory_manager = get_memory_manager()

def get_ingestion_pipeline(workspace_id: Optional[str] = None) -> CommunicationIngestionPipeline:
    """Get workspace-aware ingestion pipeline"""
    mgr = get_memory_manager(workspace_id)
    return CommunicationIngestionPipeline(mgr)

ingestion_pipeline = get_ingestion_pipeline()

# Export for use
__all__ = [
    'CommunicationAppType',
    'CommunicationData',
    'IngestionConfig',
    'LanceDBMemoryManager',
    'CommunicationIngestionPipeline',
    'memory_manager',
    'ingestion_pipeline'
]