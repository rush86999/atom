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
                # This would connect to the actual app's webhook/API
                # For now, simulate real-time ingestion
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # TODO: Implement actual app-specific real-time ingestion
                logger.debug(f"Real-time check for {app_type}")
                
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