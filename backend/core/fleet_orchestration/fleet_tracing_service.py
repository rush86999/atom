"""
FleetTracingService for distributed tracing across parallel fleet operations.

Provides distributed tracing capabilities with trace_id/span_id/parent_span_id
hierarchy for correlating logs across parallel fleet executions.

**Key Features:**
- TraceContext dataclass with trace/span hierarchy
- Fleet-level trace creation with automatic context binding
- Agent-level span creation with parent-child relationships
- Graceful degradation when tracing unavailable
- Structured logging with trace context propagation
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from core.logging_context import (
    bind_context,
    generate_trace_id,
    generate_span_id,
    _trace_id,
    _span_id,
    _parent_span_id
)

logger = logging.getLogger(__name__)

@dataclass
class TraceContext:
    """
    Distributed tracing context for fleet operations.

    Represents a span in a distributed trace with full hierarchy information
    for correlating logs across parallel fleet executions.

    Attributes:
        trace_id: Root trace ID (correlates all spans in a fleet operation)
        span_id: Current span ID (unique to this operation)
        parent_span_id: Parent span ID for nested operations (None for root span)
        chain_id: Fleet delegation chain ID
        agent_id: Agent executing this span
        tenant_id: Any ID (truncated to 8 chars for PII protection)
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    chain_id: Optional[str] = None
    agent_id: Optional[str] = None
    tenant_id: Optional[str] = None

    def __post_init__(self):
        """Truncate tenant_id to 8 chars for PII protection after initialization."""
        if self.tenant_id and len(self.tenant_id) > 8:
            object.__setattr__(self, 'tenant_id', self.tenant_id[:8])

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trace context to dictionary representation.

        Returns:
            Dict with all trace context fields
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "chain_id": self.chain_id,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id[:8] if self.tenant_id else None
        }

    def create_child_span(self, agent_id: str) -> 'TraceContext':
        """
        Create a child span from this trace context.

        Child spans inherit the trace_id and have this span as parent.

        Args:
            agent_id: Agent ID for the child span

        Returns:
            New TraceContext with child span_id
        """
        return TraceContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
            chain_id=self.chain_id,
            agent_id=agent_id)

class FleetTracingService:
    """
    Distributed tracing service for fleet operations.

    Manages trace lifecycle for fleet operations, creating root spans for
    fleet execution and child spans for individual agent tasks. All spans
    are logged with full trace context for log correlation.

    Gracefully degrades when tracing unavailable - fleet execution continues
    even if tracing fails.
    """

    def __init__(self, db: Session):
        """
        Initialize the fleet tracing service.

        Args:
            db: Database session (not currently used, reserved for future persistence)
        """
        self.db = db
        self.logger = logging.getLogger(__name__)

    def start_fleet_trace(
        self,
        chain_id: str,
        
        root_task: str
    ) -> TraceContext:
        """
        Start a root trace for a fleet operation.

        Creates a root TraceContext with new trace_id and span_id, binds
        context to thread-local storage, and logs the trace start event.

        Args:
            chain_id: Fleet delegation chain ID
            tenant_id: Any ID (will be truncated to 8 chars)
            root_task: Root task description (will be truncated to 200 chars)

        Returns:
            TraceContext with trace_id, span_id, chain_id
        """
        # Generate trace and span IDs
        trace_id = generate_trace_id()
        span_id = generate_span_id()

        # Create root trace context
        context = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,  # Root span has no parent
            chain_id=chain_id,
            agent_id=None,  # Root span not tied to specific agent
                    )

        # Bind context to thread-local storage
        bind_context(
            self.logger,
                        trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None
        )

        # Log fleet trace start
        self.logger.info(
            "fleet_trace_start",
            extra={
                "event": "fleet_trace_start",
                "chain_id": chain_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "root_task": root_task[:200],  # Truncate to prevent log bloat
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return context

    def start_agent_span(
        self,
        chain_id: str,
        agent_id: str,
        task_description: str,
        parent_context: Optional[TraceContext] = None
    ) -> TraceContext:
        """
        Start a span for an agent task.

        Creates a child span if parent_context provided, otherwise creates
        a new span with current trace_id from contextvars. Binds span context
        to thread-local storage for automatic log propagation.

        Args:
            chain_id: Fleet delegation chain ID
            agent_id: Agent executing this task
            task_description: Task description (will be truncated to 200 chars)
            parent_context: Optional parent TraceContext for child span creation

        Returns:
            TraceContext with trace_id, span_id, parent_span_id, agent_id
        """
        if parent_context:
            # Create child span from parent
            context = parent_context.create_child_span(agent_id)
            # Ensure chain_id matches
            context.chain_id = chain_id
        else:
            # Create new span with current trace_id from contextvars
            current_trace_id = _trace_id.get()
            if not current_trace_id:
                # No active trace, generate new trace_id
                current_trace_id = generate_trace_id()

            context = TraceContext(
                trace_id=current_trace_id,
                span_id=generate_span_id(),
                parent_span_id=_span_id.get(),  # Current span becomes parent
                chain_id=chain_id,
                agent_id=agent_id# Will be inherited from context
            )

        # Bind span context to thread-local storage
        bind_context(
            self.logger,
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_span_id=context.parent_span_id,
            agent_id=agent_id
        )

        # Log agent span start
        self.logger.info(
            "agent_span_start",
            extra={
                "event": "agent_span_start",
                "chain_id": chain_id,
                "agent_id": agent_id,
                "trace_id": context.trace_id,
                "span_id": context.span_id,
                "parent_span_id": context.parent_span_id,
                "task_description": task_description[:200],  # Truncate
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        return context

    def finish_span(
        self,
        context: TraceContext,
        status: str = "completed",
        result_summary: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Finish a span with status and optional result/error.

        Logs span completion with status, result summary, and error details.
        Clears span contextvars if this is the current span to prevent
        context leakage.

        Args:
            context: TraceContext for the span being finished
            status: Span status ("completed", "failed", "cancelled")
            result_summary: Optional result summary (truncated to 200 chars)
            error: Optional error message (truncated to 500 chars)
        """
        # Build log extra dict
        log_extra = {
            "event": "span_finish",
            "trace_id": context.trace_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "chain_id": context.chain_id,
            "agent_id": context.agent_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add result summary if provided (truncate to prevent log bloat)
        if result_summary:
            log_extra["result_summary"] = result_summary[:200]

        # Add error if provided (truncate to prevent log bloat)
        if error:
            log_extra["error"] = error[:500]

        # Log span finish
        if status == "failed":
            self.logger.error("span_finish", extra=log_extra)
        elif status == "cancelled":
            self.logger.warning("span_finish", extra=log_extra)
        else:
            self.logger.info("span_finish", extra=log_extra)

        # Clear span contextvars if this is the current span
        # Check by comparing span_id
        current_span_id = _span_id.get()
        if current_span_id == context.span_id:
            # This is the current span, clear context
            _span_id.set(None)
            _parent_span_id.set(None)

    def get_current_trace_context(self) -> Optional[TraceContext]:
        """
        Get current trace context from contextvars.

        Reads thread-local trace context variables and builds a TraceContext
        object for downstream consumers.

        Returns:
            TraceContext if trace active, None otherwise
        """
        trace_id = _trace_id.get()
        if not trace_id:
            return None

        return TraceContext(
            trace_id=trace_id,
            span_id=_span_id.get(),
            parent_span_id=_parent_span_id.get(),
            chain_id=None,  # Not stored in contextvars
            agent_id=None,  # Not stored in contextvars
                    )
