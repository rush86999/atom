"""
Unified Ingestion Pipeline for ATOM Memory
Consolidates data from all integrations into LanceDB vector storage.
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

# Import LanceDB handlers
try:
    from core.lancedb_handler import LanceDBHandler
    from integrations.atom_communication_ingestion_pipeline import (
        CommunicationAppType, 
        LanceDBMemoryManager,
        CommunicationData
    )
except ImportError:
    logging.warning("Core LanceDB and Communication handlers not found. Using local fallbacks for development.")

logger = logging.getLogger(__name__)

class RecordType(Enum):
    """Types of records that can be ingested"""
    COMMUNICATION = "communication"
    CONTACT = "contact"
    LEAD = "lead"
    DEAL = "deal"
    DOCUMENT = "document"
    MEETING = "meeting"
    TASK = "task"
    CAMPAIGN = "campaign"
    ORDER = "order"
    INVENTORY = "inventory"
    AD_PERFORMANCE = "ad_performance"
    SPREADSHEET = "spreadsheet"
    GENERIC = "generic"

@dataclass
class AtomRecordData:
    """Unified record data model for ATOM memory"""
    id: str
    app_type: str
    record_type: RecordType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector_embedding: Optional[List[float]] = None

class AtomIngestionPipeline:
    """Central ingestion pipeline for all ATOM integrations"""
    
    def __init__(self, memory_manager: Optional[Any] = None):
        # We reuse the LanceDBMemoryManager or a similar wrapper
        self.memory_manager = memory_manager
        self.record_counts = {}
        
    def _normalize_record(self, app_type: str, record_type: RecordType, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize data from different integrations to a unified format"""
        
        # Base normalization logic
        normalized = {
            "id": data.get("id") or data.get("Id") or f"{app_type}_{record_type.value}_{datetime.now().timestamp()}",
            "app_type": app_type,
            "record_type": record_type,
            "content": "",
            "timestamp": datetime.now(),
            "metadata": data
        }
        
        # HubSpot Specifics
        if app_type == "hubspot":
            if record_type == RecordType.CONTACT:
                props = data.get("properties", {})
                normalized["content"] = f"Contact: {props.get('firstname')} {props.get('lastname')} ({props.get('email')})"
            elif record_type == RecordType.CAMPAIGN:
                normalized["content"] = f"Campaign: {data.get('name')} - {data.get('description')}"
        
        # Salesforce Specifics
        elif app_type == "salesforce":
            if record_type == RecordType.LEAD:
                normalized["content"] = f"Lead: {data.get('FirstName')} {data.get('LastName')} at {data.get('Company')}"
            elif record_type == RecordType.DEAL or record_type == RecordType.RECORD:
                normalized["content"] = f"Opportunity: {data.get('Name')} (Stage: {data.get('StageName')})"
        
        # Meta & WhatsApp Specifics
        elif app_type in ["meta_business", "whatsapp"]:
            if record_type == RecordType.COMMUNICATION:
                normalized["content"] = f"Message ({app_type}): {data.get('text') or data.get('content')}"
            elif record_type == RecordType.AD_PERFORMANCE:
                normalized["content"] = f"Meta Ad Performance: {data.get('spend')} spend, {data.get('conversions')} conv"

        # Ecommerce Specifics (Amazon, Etsy, WooCommerce, Shopify)
        elif app_type in ["amazon", "etsy", "woocommerce", "shopify"]:
            if record_type == RecordType.ORDER:
                normalized["content"] = f"Order {data.get('id')}: {data.get('total_price')} from {data.get('email')}"
            elif record_type == RecordType.INVENTORY:
                normalized["content"] = f"Inventory Update: {data.get('sku')} -> {data.get('quantity')}"

        # Marketing Specifics (Google Ads, TikTok Ads)
        elif app_type in ["google_ads", "tiktok_ads"]:
            if record_type == RecordType.AD_PERFORMANCE:
                normalized["content"] = f"Marketing Performance ({app_type}): {data.get('spend')} spend, ROI: {data.get('roas', 'N/A')}"
            elif record_type == RecordType.CAMPAIGN:
                normalized["content"] = f"Campaign {data.get('name')}: {data.get('status')}"

        # Document & Spreadsheet Logic Extraction
        elif record_type in [RecordType.DOCUMENT, RecordType.SPREADSHEET]:
            normalized["content"] = f"Business Logic Snippet: {data.get('logic_snippet') or data.get('content')}"
            normalized["metadata"]["file_path"] = data.get("file_path")

        # Fallback for content if not set
        if not normalized["content"]:
            normalized["content"] = str(data)
            
        return normalized

    def ingest_record(self, app_type: str, record_type: str, data: Dict[str, Any]) -> bool:
        """Ingest a single record from any integration"""
        try:
            r_type = RecordType(record_type)
            normalized = self._normalize_record(app_type, r_type, data)
            
            record = AtomRecordData(**normalized)
            
            # Map back to CommunicationData or a more generic format that the 
            # existing LanceDBMemoryManager understands.
            # For now, we reuse the ingest_communication method if it's a communication,
            # or a more generic add_document method if available.
            
            if not self.memory_manager:
                logger.warning("Memory manager not initialized. Logging record instead.")
                logger.info(f"Ingesting {app_type} record: {record.content}")
                return True
            
            # If the manager supports generic ingestion, use it
            if hasattr(self.memory_manager, "ingest_generic_record"):
                return self.memory_manager.ingest_generic_record(record)
            
            # Fallback to ingest_communication if it's a message-like record
            comm_data = CommunicationData(
                id=record.id,
                app_type=record.app_type,
                timestamp=record.timestamp,
                sender=normalized["metadata"].get("sender", "system"),
                recipient=normalized["metadata"].get("recipient", "user"),
                content=record.content,
                metadata=json.dumps(record.metadata),
                vector_embedding=record.vector_embedding
            )
            
            return self.memory_manager.ingest_communication(comm_data)
            
        except Exception as e:
            logger.error(f"Error ingesting record from {app_type}: {str(e)}")
            return False

# Global instance
from integrations.atom_communication_ingestion_pipeline import memory_manager
atom_ingestion_pipeline = AtomIngestionPipeline(memory_manager)
