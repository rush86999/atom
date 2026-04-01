"""LLM Model Registry - SQLAlchemy Models

This module defines the SQLAlchemy model for the LLM model registry,
which stores metadata about LLM models from multiple providers
(OpenAI, Anthropic, OpenRouter, etc.) with tenant isolation.

The registry supports:
- Multi-provider model registration
- Hybrid metadata storage (structured columns + JSONB)
- Tenant isolation via Row Level Security (RLS)
- Pricing and capability tracking
"""
from typing import Optional, Dict, Any, List, Set
from datetime import datetime

from sqlalchemy import Column, String, Integer, Numeric, DateTime, Boolean, UniqueConstraint, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped
import uuid

from core.database import Base
from core.models import UUID, JSONBColumn # Use platform-independent types


class LLMModel(Base):
    """
    LLM Model Registry Entry

    Represents a single LLM model from a provider with its metadata,
    pricing, and capabilities. Each model is scoped to a tenant for
    multi-tenancy support.

    Attributes:
        id: Unique identifier for the model entry
        tenant_id: Tenant identifier for multi-tenancy
        provider: Provider name (e.g., 'openai', 'anthropic', 'openrouter')
        model_name: Model identifier (e.g., 'gpt-4', 'claude-3-opus')
        context_window: Maximum context window in tokens
        input_price_per_token: Cost per input token in USD
        output_price_per_token: Cost per output token in USD
        capabilities: JSONB array of capabilities (e.g., ['vision', 'tools', 'function_calling'])
        metadata: JSONB object for provider-specific fields
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
        last_refreshed_at: Timestamp when model metadata was last refreshed from provider API
    """
    __tablename__ = 'llm_models'

    # Primary key
    id: Mapped[uuid.UUID] = Column(
        UUID,
        primary_key=True,
        default=uuid.uuid4
    )

    # Tenant isolation (required for multi-tenancy)
    tenant_id: Mapped[str] = Column(
        String,
        nullable=False,
        index=True
    )

    # Provider identification
    provider: Mapped[str] = Column(
        String,
        nullable=False,
        index=True
    )
    model_name: Mapped[str] = Column(
        String,
        nullable=False
    )

    # Model specifications
    context_window: Mapped[Optional[int]] = Column(Integer)
    input_price_per_token: Mapped[Optional[float]] = Column(Numeric(10, 7))
    output_price_per_token: Mapped[Optional[float]] = Column(Numeric(10, 7))

    # JSONB metadata for flexible provider-specific fields
    capabilities: Mapped[List[str]] = Column(
        JSONBColumn,
        default=list
    )
    # Note: 'metadata' is reserved in SQLAlchemy, so we use provider_metadata
    # but map it to the 'metadata' column in the database
    provider_metadata: Mapped[Dict[str, Any]] = Column(
        'metadata',  # Maps to 'metadata' column in database
        JSONBColumn,
        default=dict
    )

    # Hybrid capability columns for common capabilities (indexed)
    # These provide fast boolean lookups for frequently queried capabilities
    supports_vision: Mapped[bool] = Column(
        Boolean,
        default=False,
        index=True
    )
    supports_tools: Mapped[bool] = Column(
        Boolean,
        default=False,
        index=True
    )
    supports_function_calling: Mapped[bool] = Column(
        Boolean,
        default=False,
        index=True
    )
    supports_audio: Mapped[bool] = Column(
        Boolean,
        default=False,
        index=True
    )
    supports_computer_use: Mapped[bool] = Column(
        Boolean,
        default=False,
        index=True
    )

    # Timestamps
    discovered_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        onupdate=func.now()
    )
    last_refreshed_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True)
    )

    # Deprecation tracking
    is_deprecated: Mapped[bool] = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    deprecated_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True
    )
    deprecation_reason: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True
    )

    # Quality benchmark score (0-100) from LMSYS or heuristics
    quality_score: Mapped[Optional[float]] = Column(
        Numeric(5, 2),
        nullable=True,
        comment='Quality benchmark score (0-100) from LMSYS Chatbot Arena or heuristic scoring'
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'provider',
            'model_name',
            name='llm_models_unique_model'
        ),
        Index('idx_llm_models_tenant_provider_model', 'tenant_id', 'provider', 'model_name'),
        # Partial indexes on hybrid columns (only index TRUE values for efficiency)
        Index('idx_llm_models_vision_partial',
              'supports_vision',
              postgresql_where=text('supports_vision = TRUE')),
        Index('idx_llm_models_tools_partial',
              'supports_tools',
              postgresql_where=text('supports_tools = TRUE')),
        Index('idx_llm_models_function_calling_partial',
              'supports_function_calling',
              postgresql_where=text('supports_function_calling = TRUE')),
        Index('idx_llm_models_audio_partial',
              'supports_audio',
              postgresql_where=text('supports_audio = TRUE')),
        Index('idx_llm_models_computer_use_partial',
              'supports_computer_use',
              postgresql_where=text('supports_computer_use = TRUE')),
        # Partial index on is_deprecated (only index FALSE values for efficient filtering)
        Index('idx_llm_models_deprecated_partial',
              'is_deprecated',
              postgresql_where=text('is_deprecated = FALSE')),
    )

    # Common capabilities that have dedicated hybrid columns
    HYBRID_CAPABILITIES = {'vision', 'tools', 'function_calling', 'audio', 'computer_use'}

    def sync_capabilities(self) -> None:
        """
        Sync hybrid capability columns with capabilities JSONB array.

        This method ensures the boolean columns (supports_vision, supports_tools, etc.)
        stay in sync with the capabilities JSONB array. Call this before saving
        if capabilities are modified.

        Example:
            model.capabilities.append('vision')
            model.sync_capabilities()  # Sets supports_vision = True
            session.commit()
        """
        caps_set = set(self.capabilities) if self.capabilities else set()
        self.supports_vision = 'vision' in caps_set
        self.supports_tools = 'tools' in caps_set
        self.supports_function_calling = 'function_calling' in caps_set
        self.supports_audio = 'audio' in caps_set
        self.supports_computer_use = 'computer_use' in caps_set

    @classmethod
    def get_hybrid_capabilities(cls) -> Set[str]:
        """
        Get the set of capabilities that have dedicated hybrid columns.

        Returns:
            Set of capability names that have boolean columns for fast lookups
        """
        return cls.HYBRID_CAPABILITIES.copy()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Returns:
            Dictionary representation of the model with all fields
        """
        return {
            'id': str(self.id),
            'tenant_id': self.tenant_id,
            'provider': self.provider,
            'model_name': self.model_name,
            'context_window': self.context_window,
            'input_price_per_token': float(self.input_price_per_token) if self.input_price_per_token else None,
            'output_price_per_token': float(self.output_price_per_token) if self.output_price_per_token else None,
            'capabilities': self.capabilities if self.capabilities else [],
            'metadata': self.provider_metadata if self.provider_metadata else {},
            'supports_vision': self.supports_vision,
            'supports_tools': self.supports_tools,
            'supports_function_calling': self.supports_function_calling,
            'supports_audio': self.supports_audio,
            'supports_computer_use': self.supports_computer_use,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_refreshed_at': self.last_refreshed_at.isoformat() if self.last_refreshed_at else None,
            'is_deprecated': self.is_deprecated,
            'deprecated_at': self.deprecated_at.isoformat() if self.deprecated_at else None,
            'deprecation_reason': self.deprecation_reason,
            'quality_score': float(self.quality_score) if self.quality_score else None,
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<LLMModel(id={self.id}, tenant_id={self.tenant_id}, "
            f"provider={self.provider}, model_name={self.model_name})>"
        )
