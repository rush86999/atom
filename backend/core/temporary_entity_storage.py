"""
Temporary Entity Storage Models

Stores entity types and nodes temporarily until promoted by user.
Auto-expires after TTL (Time To Live) if not promoted.
Enables non-blocking, memory-efficient backfill operations.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from core.database import Base
from core.models import JSONColumn


class TemporaryEntityType(Base):
    """
    Temporary storage for entity type schemas awaiting user promotion.

    Workflow:
    1. Ingested from memory/semantic data → stored here (status=draft)
    2. User reviews → promoted to EntityTypeDefinition (status=promoted)
    3. User rejects OR TTL expires → marked for cleanup (status=rejected/expired)

    Benefits:
    - Review entity types before adding to schema
    - Validate quality and relevance
    - Prevent schema pollution from low-quality auto-discovered types
    """
    __tablename__ = "temporary_entity_types"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Entity type identity
    slug = Column(String(100), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Schema definition (JSON)
    json_schema = Column(JSONColumn, nullable=False)

    # Promotion tracking
    status = Column(String(20), nullable=False, default="draft")  # draft, promoted, rejected, expired
    promoted_to_id = Column(String, ForeignKey("entity_type_definitions.id"), nullable=True)
    promoted_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    source = Column(String(100), nullable=True)  # e.g., "memory_ingestion", "semantic_extraction"
    ingestion_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)  # TTL-based expiration

    # Quality indicators
    confidence_score = Column(Integer, nullable=True)  # 0-100 auto-discovery confidence
    sample_count = Column(Integer, default=0)  # Number of sample entities discovered
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_temp_entity_types_tenant_slug", "tenant_id", "slug"),
        Index("ix_temp_entity_types_status", "status"),
        Index("ix_temp_entity_types_expires", "expires_at"),
    )

    # Relationships
    promoted_entity = relationship("EntityTypeDefinition", foreign_keys=[promoted_to_id])
    temporary_nodes = relationship("TemporaryEntityNode", back_populates="temporary_type")

    def set_expiration(self, ttl_hours: int = 48):
        """Set expiration time based on TTL."""
        self.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

    def is_expired(self) -> bool:
        """Check if temporary entity type has expired."""
        return datetime.utcnow() > self.expires_at

    def promote(self, promoted_entity_id: str):
        """Mark entity type as promoted."""
        self.status = "promoted"
        self.promoted_to_id = promoted_entity_id
        self.promoted_at = datetime.utcnow()

    def reject(self, reason: str, ttl_hours: int = 1):
        """Mark entity type as rejected with short TTL."""
        self.status = "rejected"
        self.rejection_reason = reason
        self.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)


class TemporaryEntityNode(Base):
    """
    Temporary storage for entity nodes awaiting schema promotion.

    Workflow:
    1. Ingested from semantic data → stored here (status=pending)
    2. Entity type promoted → batch migrated to GraphNodes (status=migrated)
    3. Entity type rejected OR TTL expires → cleaned up (status=expired)

    Benefits:
    - Ingest large datasets without blocking
    - Batch migration for performance
    - Prevent polluting graph with unvalidated entities
    """
    __tablename__ = "temporary_entity_nodes"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, nullable=False, index=True)

    # Reference to temporary entity type
    temporary_type_id = Column(String, ForeignKey("temporary_entity_types.id"), nullable=False, index=True)

    # Entity data
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # Matches temporary_entity_types.slug
    description = Column(Text, nullable=True)
    properties = Column(JSONColumn, default={})

    # Migration tracking
    status = Column(String(20), nullable=False, default="pending")  # pending, migrated, expired
    migrated_to_id = Column(String, ForeignKey("graph_nodes.id"), nullable=True)
    migrated_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    ingestion_timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    ingestion_source = Column(String(100), nullable=True)  # e.g., "document_parsing", "llm_extraction"
    confidence_score = Column(Integer, nullable=True)  # 0-100 extraction confidence

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        Index("ix_temp_entity_nodes_tenant_workspace", "tenant_id", "workspace_id"),
        Index("ix_temp_entity_nodes_type", "type"),
        Index("ix_temp_entity_nodes_status", "status"),
        Index("ix_temp_entity_nodes_temp_type", "temporary_type_id"),
    )

    # Relationships
    temporary_type = relationship("TemporaryEntityType", back_populates="temporary_nodes")
    migrated_node = relationship("GraphNode", foreign_keys=[migrated_to_id])

    def mark_migrated(self, graph_node_id: str):
        """Mark node as migrated to graph."""
        self.status = "migrated"
        self.migrated_to_id = graph_node_id
        self.migrated_at = datetime.utcnow()

    def mark_expired(self):
        """Mark node as expired."""
        self.status = "expired"
