"""
Shared Ingestion Models for ATOM Memory
Standardizes record types and data structures across all ingestion pipelines.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
