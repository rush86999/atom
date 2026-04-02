"""
Correlation Context Helper for Integration Logging

Provides context binding for structured logging with correlation IDs
(trace_id, workflow_id, agent_id) across integration execution.

**Key Features:**
- Bind context to logger for automatic correlation ID propagation
- Thread-safe context storage using contextvars
- Integration with existing structlog infrastructure
"""
import logging
import uuid
from typing import Optional, Dict, Any
from contextvars import ContextVar

# Context variables for thread-safe storage
_trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
_workflow_id: ContextVar[Optional[str]] = ContextVar('workflow_id', default=None)
_agent_id: ContextVar[Optional[str]] = ContextVar('agent_id', default=None)
_span_id: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
_parent_span_id: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)
_execution_path: ContextVar[Optional[str]] = ContextVar('execution_path', default=None)


def generate_trace_id() -> str:
    """
    Generate a unique trace ID for correlation.

    Returns:
        UUID string for tracing requests across services
    """
    return str(uuid.uuid4())


def bind_context(
    logger: logging.Logger,
    workflow_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    execution_path: Optional[str] = None,
    **kwargs
) -> logging.Logger:
    """
    Bind correlation context to a logger instance.

    All subsequent log calls will include these context fields automatically.

    Args:
        logger: Logger instance to bind context to
        workflow_id: Workflow execution ID (if triggered by workflow)
        agent_id: Agent ID (if triggered by agent)
        trace_id: Trace ID for request correlation (auto-generated if not provided)
        span_id: Span ID for distributed tracing
        parent_span_id: Parent span ID for nested operations
        execution_path: Execution path ("workflow" or "agent")
        **kwargs: Additional context fields

    Returns:
        Logger with bound context (structlog BoundLogger if available)

    Example:
        ```python
        logger = bind_context(
            get_logger(__name__),
            workflow_id="workflow-123",
            agent_id="agent-456",
            trace_id="trace-789"
        )
        logger.info("Processing task")  # Automatically includes all context
        ```
    """
    # Generate trace_id if not provided
    if trace_id is None:
        trace_id = generate_trace_id()

    # Store in context variables for thread-safe access
    _trace_id.set(trace_id)
    if workflow_id:
        _workflow_id.set(workflow_id)
    if agent_id:
        _agent_id.set(agent_id)
    if span_id:
        _span_id.set(span_id)
    if parent_span_id:
        _parent_span_id.set(parent_span_id)
    if execution_path:
        _execution_path.set(execution_path)

    # Try to use structlog for context binding
    try:
        import structlog

        # Create context dict
        context = {
            'trace_id': trace_id,
            'workflow_id': workflow_id,
            'agent_id': agent_id,
            'span_id': span_id,
            'parent_span_id': parent_span_id,
            'execution_path': execution_path,
            **kwargs
        }

        # Bind context to structlog logger
        bound_logger = structlog.get_logger(logger.name).bind(**context)

        return bound_logger

    except ImportError:
        # Fall back to standard logging with LoggerAdapter
        extra = {
            'trace_id': trace_id,
            'workflow_id': workflow_id,
            'agent_id': agent_id,
            'span_id': span_id,
            'parent_span_id': parent_span_id,
            'execution_path': execution_path,
            **kwargs
        }

        return logging.LoggerAdapter(logger, extra)


def generate_span_id() -> str:
    """
    Generate a unique span ID for distributed tracing.

    Returns:
        UUID string for span identification
    """
    return str(uuid.uuid4())


def get_context() -> Dict[str, Any]:
    """
    Get current correlation context from context variables.

    Returns:
        Dict with all context fields (trace_id, workflow_id, agent_id, etc.)
    """
    return {
        'trace_id': _trace_id.get(),
        'workflow_id': _workflow_id.get(),
        'agent_id': _agent_id.get(),
        'span_id': _span_id.get(),
        'parent_span_id': _parent_span_id.get(),
        'execution_path': _execution_path.get()
    }


def clear_context():
    """
    Clear all correlation context from context variables.

    Call this after request processing completes to avoid context leakage.
    """
    _trace_id.set(None)
    _workflow_id.set(None)
    _agent_id.set(None)
    _span_id.set(None)
    _parent_span_id.set(None)
    _execution_path.set(None)
