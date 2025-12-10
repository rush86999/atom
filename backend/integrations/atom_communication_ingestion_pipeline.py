"""
ATOM Communication Apps Ingestion Pipeline - LanceDB Integration
Central memory system for all communication data with LanceDB vector storage
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import lancedb
import pyarrow as pa
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)

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
    
    def __init__(self, db_path: str = "./data/atom_memory"):
        self.db_path = Path(db_path)
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
                logger.info("Loading embedding model (all-mpnet-base-v2)...")
                self.model = SentenceTransformer('all-mpnet-base-v2')
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading embedding model: {str(e)}")
                return False
                
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
            pa.field("vector", pa.list_(pa.float32())),  # For vector search
            pa.field("search_vector", pa.list_(pa.float32()))  # Primary search vector
        ])
        
        # Check if table exists
        table_names = self.db.table_names()
        if "atom_communications" not in table_names:
            self.connections_table = self.db.create_table("atom_communications", schema=schema)
            logger.info("Created atom_communications table")
        else:
            self.connections_table = self.db.open_table("atom_communications")
            logger.info("Opened existing atom_communications table")
    
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

    def search_communications(self, query: str, limit: int = 10, app_type: str = None) -> List[Dict]:
        """Search communications using vector similarity"""
        try:
            if not self.connections_table:
                logger.error("Connections table not initialized")
                return []
                
            # Generate query embedding
            query_vector = self.generate_embedding(query)
            
            # Perform vector search
            search_builder = self.connections_table.search(query_vector).limit(limit)
            
            if app_type:
                search_builder = search_builder.where(f"app_type = '{app_type}'")
            
            results = search_builder.to_pandas()
            
            return results.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error searching communications: {str(e)}")
            return []
    
    def get_communications_by_app(self, app_type: str, limit: int = 100) -> List[Dict]:
        """Get communications by app type"""
        try:
            results = self.connections_table.search().where(f"app_type = '{app_type}'").limit(limit).to_pandas()
            return results.to_dict('records')
        except Exception as e:
            logger.error(f"Error getting communications by app: {str(e)}")
            return []
    
    def get_communications_by_timeframe(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get communications within time frame"""
        try:
            filter_query = f"timestamp >= '{start_date}' AND timestamp <= '{end_date}'"
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
        
    def configure_app(self, app_type: CommunicationAppType, config: IngestionConfig):
        """Configure ingestion for specific app"""
        self.ingestion_configs[app_type.value] = {
            **asdict(config),
            "app_type": app_type.value
        }
        logger.info(f"Configured ingestion for {app_type.value}")
    
    def ingest_message(self, app_type: str, message_data: Dict[str, Any]) -> bool:
        """Ingest single message from any communication app"""
        try:
            # Normalize message data
            normalized_data = self._normalize_message(app_type, message_data)
            
            # Convert to CommunicationData
            comm_data = CommunicationData(**normalized_data)
            
            # Generate embedding if needed
            if self.ingestion_configs.get(app_type, {}).get('embed_content', False):
                comm_data.vector_embedding = self._generate_embedding(comm_data.content)
            
            # Ingest into memory
            return self.memory_manager.ingest_communication(comm_data)
            
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
        while True:
            try:
                # Implement actual app-specific real-time ingestion
                if app_type == CommunicationAppType.WHATSAPP.value:
                    await self._ingest_whatsapp_messages()
                elif app_type == CommunicationAppType.SLACK.value:
                    await self._ingest_slack_messages()
                elif app_type == CommunicationAppType.EMAIL.value:
                    await self._ingest_email_messages()
                elif app_type == CommunicationAppType.GMAIL.value:
                    await self._ingest_gmail_messages()
                elif app_type == CommunicationAppType.OUTLOOK.value:
                    await self._ingest_outlook_messages()
                elif app_type == CommunicationAppType.ZOOM.value:
                    await self._ingest_zoom_recordings()
                elif app_type == CommunicationAppType.DISCORD.value:
                    await self._ingest_discord_messages()
                elif app_type == CommunicationAppType.TELEGRAM.value:
                    await self._ingest_telegram_messages()
                else:
                    # Default polling for unsupported apps
                    logger.debug(f"Real-time check for {app_type} (polling mode)")

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in real-time ingestion for {app_type}: {str(e)}")
                await asyncio.sleep(60)  # Wait longer on error
    
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

    # Real-time ingestion implementation methods
    async def _ingest_whatsapp_messages(self):
        """Ingest WhatsApp messages via webhook or API polling"""
        try:
            # Check for new WhatsApp messages
            # This would integrate with WhatsApp Business API
            import aiohttp

            webhook_url = self.ingestion_configs.get("whatsapp", {}).get("webhook_url")
            if webhook_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{webhook_url}/messages") as response:
                        if response.status == 200:
                            messages = await response.json()
                            for msg in messages:
                                comm_data = CommunicationData(
                                    id=msg.get("id"),
                                    app_type="whatsapp",
                                    timestamp=datetime.fromisoformat(msg.get("timestamp")),
                                    direction=msg.get("direction", "inbound"),
                                    sender=msg.get("from"),
                                    recipient=msg.get("to"),
                                    content=msg.get("message"),
                                    metadata={"source": "webhook", **msg.get("metadata", {})}
                                )
                                await self.memory_manager.store_communication(comm_data)
        except Exception as e:
            logger.error(f"WhatsApp ingestion error: {e}")

    async def _ingest_slack_messages(self):
        """Ingest Slack messages via Slack API"""
        try:
            # Check for new Slack messages
            config = self.ingestion_configs.get("slack", {})
            if config.get("access_token"):
                from slack_sdk import WebClient

                client = WebClient(token=config["access_token"])

                # Get list of channels
                channels = client.conversations_list(types="public_channel,private_channel")

                for channel in channels["channels"]:
                    # Get new messages from each channel
                    history = client.conversations_history(
                        channel=channel["id"],
                        oldest=config.get("last_checkpoint", 0)
                    )

                    for msg in history.get("messages", []):
                        if msg.get("user") and msg.get("text"):
                            comm_data = CommunicationData(
                                id=msg.get("ts"),
                                app_type="slack",
                                timestamp=datetime.fromtimestamp(float(msg.get("ts"))),
                                direction="internal",
                                sender=msg.get("user"),
                                recipient=channel["name"],
                                content=msg.get("text"),
                                metadata={"channel_id": channel["id"], "source": "api"}
                            )
                            await self.memory_manager.store_communication(comm_data)
        except Exception as e:
            logger.error(f"Slack ingestion error: {e}")

    async def _ingest_email_messages(self):
        """Ingest email messages via IMAP/POP3"""
        try:
            import imaplib
            import email

            config = self.ingestion_configs.get("email", {})
            if config.get("imap_server") and config.get("username"):
                imap = imaplib.IMAP4_SSL(config["imap_server"])
                imap.login(config["username"], config["password"])
                imap.select("INBOX")

                # Search for unseen emails
                status, messages = imap.search(None, "UNSEEN")
                if status == "OK":
                    for msg_id in messages[0].split():
                        status, msg_data = imap.fetch(msg_id, "(RFC822)")
                        if status == "OK":
                            raw_email = msg_data[0][1]
                            email_message = email.message_from_bytes(raw_email)

                            comm_data = CommunicationData(
                                id=msg_id.decode(),
                                app_type="email",
                                timestamp=datetime.strptime(email_message["Date"], "%a, %d %b %Y %H:%M:%S %z"),
                                direction="inbound",
                                sender=email_message["From"],
                                recipient=email_message["To"],
                                subject=email_message["Subject"],
                                content=self._get_email_body(email_message),
                                metadata={"source": "imap", "folder": "INBOX"}
                            )
                            await self.memory_manager.store_communication(comm_data)

                imap.close()
                imap.logout()
        except Exception as e:
            logger.error(f"Email ingestion error: {e}")

    async def _ingest_gmail_messages(self):
        """Ingest Gmail messages via Gmail API"""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            config = self.ingestion_configs.get("gmail", {})
            if config.get("credentials"):
                creds = Credentials.from_authorized_user_info(config["credentials"])
                service = build("gmail", "v1", credentials=creds)

                # Get new messages
                results = service.users().messages().list(userId="me", q="is:unread").execute()
                messages = results.get("messages", [])

                for message in messages:
                    msg = service.users().messages().get(userId="me", id=message["id"]).execute()

                    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

                    comm_data = CommunicationData(
                        id=message["id"],
                        app_type="gmail",
                        timestamp=datetime.fromtimestamp(int(msg["internalDate"]) / 1000),
                        direction="inbound",
                        sender=headers.get("From"),
                        recipient=headers.get("To"),
                        subject=headers.get("Subject"),
                        content=msg.get("snippet", ""),
                        metadata={"source": "gmail_api", "thread_id": msg.get("threadId")}
                    )
                    await self.memory_manager.store_communication(comm_data)

                    # Mark as read
                    service.users().messages().modify(userId="me", id=message["id"], body={"removeLabelIds": ["UNREAD"]}).execute()
        except Exception as e:
            logger.error(f"Gmail ingestion error: {e}")

    async def _ingest_outlook_messages(self):
        """Ingest Outlook messages via Microsoft Graph API"""
        try:
            from msal import ConfidentialClientApplication

            config = self.ingestion_configs.get("outlook", {})
            if config.get("client_id") and config.get("client_secret"):
                app = ConfidentialClientApplication(
                    config["client_id"],
                    client_credential=config["client_secret"],
                    authority="https://login.microsoftonline.com/" + config["tenant_id"]
                )

                # Get access token
                token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

                headers = {"Authorization": f"Bearer {token['access_token']}"}

                # Get new messages
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://graph.microsoft.com/v1.0/me/messages?$filter=isRead eq false", headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()

                            for msg in data["value"]:
                                comm_data = CommunicationData(
                                    id=msg["id"],
                                    app_type="outlook",
                                    timestamp=datetime.fromisoformat(msg["receivedDateTime"]),
                                    direction="inbound",
                                    sender=msg["from"]["emailAddress"]["address"],
                                    recipient=msg["toRecipients"][0]["emailAddress"]["address"],
                                    subject=msg["subject"],
                                    content=msg["bodyPreview"],
                                    metadata={"source": "graph_api", "conversation_id": msg.get("conversationId")}
                                )
                                await self.memory_manager.store_communication(comm_data)

                                # Mark as read
                                await session.patch(f"https://graph.microsoft.com/v1.0/me/messages/{msg['id']}",
                                                   json={"isRead": True}, headers=headers)
        except Exception as e:
            logger.error(f"Outlook ingestion error: {e}")

    async def _ingest_zoom_recordings(self):
        """Ingest Zoom meeting recordings"""
        try:
            config = self.ingestion_configs.get("zoom", {})
            if config.get("access_token"):
                import aiohttp

                headers = {"Authorization": f"Bearer {config['access_token']}"}

                async with aiohttp.ClientSession() as session:
                    # Get recent recordings
                    async with session.get("https://api.zoom.us/v2/users/me/recordings?from=2025-01-01", headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()

                            for meeting in data.get("meetings", []):
                                for recording in meeting.get("recording_files", []):
                                    comm_data = CommunicationData(
                                        id=recording["id"],
                                        app_type="zoom",
                                        timestamp=datetime.fromisoformat(meeting["start_time"]),
                                        direction="internal",
                                        sender=meeting["host_email"],
                                        recipient=meeting.get("topic", "Zoom Meeting"),
                                        content=f"Zoom Meeting: {meeting.get('topic', 'No Topic')}",
                                        recording_url=recording["download_url"],
                                        metadata={"source": "zoom_api", "meeting_id": meeting["uuid"], "duration": meeting.get("duration", 0)}
                                    )
                                    await self.memory_manager.store_communication(comm_data)
        except Exception as e:
            logger.error(f"Zoom recordings ingestion error: {e}")

    async def _ingest_discord_messages(self):
        """Ingest Discord messages via Discord bot API"""
        try:
            import discord

            config = self.ingestion_configs.get("discord", {})
            if config.get("bot_token"):
                # This would typically run as a Discord bot
                # For now, implement basic polling
                import aiohttp

                headers = {"Authorization": f"Bot {config['bot_token']}"}

                async with aiohttp.ClientSession() as session:
                    # Get channels
                    async with session.get("https://discord.com/api/v10/users/@me/channels", headers=headers) as response:
                        if response.status == 200:
                            channels = await response.json()

                            for channel in channels:
                                if channel.get("type") == 1:  # DM channel
                                    # Get messages
                                    async with session.get(f"https://discord.com/api/v10/channels/{channel['id']}/messages?limit=10", headers=headers) as msg_response:
                                        if msg_response.status == 200:
                                            messages = await msg_response.json()

                                            for msg in messages:
                                                comm_data = CommunicationData(
                                                    id=msg["id"],
                                                    app_type="discord",
                                                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                                                    direction="internal",
                                                    sender=msg["author"]["username"],
                                                    recipient=channel.get("recipients", [{}])[0].get("username", "Unknown"),
                                                    content=msg["content"],
                                                    metadata={"source": "discord_api", "channel_id": channel["id"]}
                                                )
                                                await self.memory_manager.store_communication(comm_data)
        except Exception as e:
            logger.error(f"Discord ingestion error: {e}")

    async def _ingest_telegram_messages(self):
        """Ingest Telegram messages via Telegram Bot API"""
        try:
            config = self.ingestion_configs.get("telegram", {})
            if config.get("bot_token"):
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    # Get updates (messages)
                    offset = self.ingestion_configs.get("telegram", {}).get("last_update_id", 0)
                    async with session.get(f"https://api.telegram.org/bot{config['bot_token']}/getUpdates?offset={offset}") as response:
                        if response.status == 200:
                            data = await response.json()

                            for update in data.get("result", []):
                                if "message" in update:
                                    msg = update["message"]

                                    comm_data = CommunicationData(
                                        id=str(update["update_id"]),
                                        app_type="telegram",
                                        timestamp=datetime.fromtimestamp(msg["date"]),
                                        direction="inbound",
                                        sender=msg.get("from", {}).get("username", "Unknown"),
                                        recipient=msg.get("chat", {}).get("username", "Unknown"),
                                        content=msg.get("text", ""),
                                        metadata={"source": "telegram_bot_api", "chat_id": msg.get("chat", {}).get("id")}
                                    )
                                    await self.memory_manager.store_communication(comm_data)

                                    # Update last update ID
                                    self.ingestion_configs["telegram"]["last_update_id"] = update["update_id"] + 1
        except Exception as e:
            logger.error(f"Telegram ingestion error: {e}")

    def _get_email_body(self, email_message) -> str:
        """Extract email body from email message"""
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode()
                    except:
                        body += part.get_payload()
        else:
            body = email_message.get_payload()
        return body.strip()

# Global instance
memory_manager = LanceDBMemoryManager()
ingestion_pipeline = CommunicationIngestionPipeline(memory_manager)

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