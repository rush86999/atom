"""
Production Monitoring Infrastructure

Provides Prometheus metrics collection and structured logging configuration.

Metrics:
- HTTP requests tracking (method, endpoint, status)
- Agent execution tracking (agent_id, status)
- Skill execution tracking (skill_id, status)
- Database query performance (duration histogram)
- Active agents gauge

Structured Logging:
- JSON-formatted logs with structlog
- Context binding for request_id, agent_id, skill_id
- Processors: timestamp, log_level, logger_name, stack_info

References:
- 15-RESEARCH.md: Monitoring patterns
- Prometheus: https://prometheus.io/docs/practices/naming/
- structlog: https://www.structlog.org/en/stable/
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import structlog
from structlog.types import Processor

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

# HTTP request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Agent execution metrics
agent_executions_total = Counter(
    'agent_executions_total',
    'Total agent executions',
    ['agent_id', 'status']
)

agent_execution_duration_seconds = Histogram(
    'agent_execution_duration_seconds',
    'Agent execution latency',
    ['agent_id']
)

active_agents = Gauge(
    'active_agents',
    'Number of currently running agents'
)

# Skill execution metrics
skill_executions_total = Counter(
    'skill_executions_total',
    'Total skill executions',
    ['skill_id', 'status']
)

skill_execution_duration_seconds = Histogram(
    'skill_execution_duration_seconds',
    'Skill execution latency',
    ['skill_id']
)

# Database query metrics
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query latency',
    ['operation']
)

# Database connection pool metrics
db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections'
)

db_connections_idle = Gauge(
    'db_connections_idle',
    'Idle database connections'
)

# ============================================================================
# DEPLOYMENT METRICS
# ============================================================================

# Track deployment attempts and outcomes
deployment_total = Counter(
    'deployment_total',
    'Total number of deployments',
    ['environment', 'status']  # status: success, failed, rolled_back
)

deployment_duration_seconds = Histogram(
    'deployment_duration_seconds',
    'Deployment duration in seconds',
    ['environment'],
    buckets=[60, 120, 300, 600, 1800, 3600]  # 1min, 2min, 5min, 10min, 30min, 60min
)

deployment_rollback_total = Counter(
    'deployment_rollback_total',
    'Total number of deployment rollbacks',
    ['environment', 'reason']  # reason: smoke_test_failed, high_error_rate, manual
)

# Track deployment frequency (deployments per hour)
deployment_frequency = Gauge(
    'deployment_frequency',
    'Deployment frequency (deployments per hour)',
    ['environment']
)

# Track canary deployment progress
canary_traffic_percentage = Gauge(
    'canary_traffic_percentage',
    'Current canary traffic percentage',
    ['environment', 'deployment_id']
)

# Track smoke test results
smoke_test_total = Counter(
    'smoke_test_total',
    'Total number of smoke tests run',
    ['environment', 'result']  # result: passed, failed
)

smoke_test_duration_seconds = Histogram(
    'smoke_test_duration_seconds',
    'Smoke test duration in seconds',
    ['environment'],
    buckets=[10, 30, 60, 120, 300]  # 10s, 30s, 1min, 2min, 5min
)

# Track Prometheus query success rate
prometheus_query_total = Counter(
    'prometheus_query_total',
    'Total number of Prometheus queries',
    ['workflow', 'result']  # result: success, failed, timeout
)

prometheus_query_duration_seconds = Histogram(
    'prometheus_query_duration_seconds',
    'Prometheus query duration in seconds',
    ['workflow'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]  # 100ms, 500ms, 1s, 2s, 5s, 10s
)

# ============================================================================
# STRUCTLOG CONFIGURATION
# ============================================================================


def add_log_level(logger, method_name: str, event_dict: Dict) -> Dict:
    """
    Add log level to the event dict.
    """
    event_dict["level"] = method_name.upper()
    return event_dict


def add_logger_name(logger, method_name: str, event_dict: Dict) -> Dict:
    """
    Add logger name to the event dict.
    """
    event_dict["logger"] = logger.name
    return event_dict


def configure_structlog():
    """
    Configure structlog with JSON output and processors.

    Sets up:
    - JSON rendering for machine-readable logs
    - Timestamp processor
    - Log level processor
    - Logger name processor
    - Stack info processor for exceptions

    Usage:
        configure_structlog()
        log = structlog.get_logger()
        log.info("message", key="value")
    """
    # Configure structlog
    structlog.configure(
        processors=[
            # Filter out log records below logging level
            structlog.stdlib.filter_by_level,

            # Add logger name
            structlog.stdlib.add_logger_name,

            # Add log level
            structlog.stdlib.add_log_level,

            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso"),

            # Add call stack info for exceptions
            structlog.processors.StackInfoRenderer(),

            # Format exception information
            structlog.processors.format_exc_info,

            # JSON renderer for machine-readable output
            structlog.processors.JSONRenderer()
        ],
        # Use standard library's logging context class
        context_class=dict,

        # Use standard library logger factory
        logger_factory=structlog.stdlib.LoggerFactory(),

        # Cache logger on first use
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structured logger with context binding.

    Args:
        name: Logger name (defaults to calling module name)

    Returns:
        BoundLogger with context binding support

    Example:
        log = get_logger(__name__)
        log.info("Agent started", agent_id="agent-123", request_id="req-456")
    """
    return structlog.get_logger(name)


class RequestContext:
    """
    Context manager for request-scoped logging context.

    Usage:
        with RequestContext(request_id="req-123", user_id="user-456"):
            log.info("Processing request")
            # Logs will include request_id and user_id automatically
    """

    def __init__(self, **context):
        self.context = context
        self.log = None
        self.old_context = None

    def __enter__(self):
        self.log = structlog.get_logger()
        # Bind context to logger
        self.old_context = self.log._context.copy()
        self.log = self.log.bind(**self.context)
        return self.log

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old context
        if self.old_context is not None:
            self.log._context = self.old_context


# ============================================================================
# METRICS HELPERS
# ============================================================================


def track_http_request(method: str, endpoint: str, status: int, duration: float):
    """
    Track HTTP request metrics.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Request endpoint path
        status: HTTP status code
        duration: Request duration in seconds
    """
    http_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status=str(status)
    ).inc()

    http_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)


def track_agent_execution(agent_id: str, status: str, duration: float):
    """
    Track agent execution metrics.

    Args:
        agent_id: Agent identifier
        status: Execution status (success, failure, error)
        duration: Execution duration in seconds
    """
    agent_executions_total.labels(
        agent_id=agent_id,
        status=status
    ).inc()

    agent_execution_duration_seconds.labels(
        agent_id=agent_id
    ).observe(duration)


def track_skill_execution(skill_id: str, status: str, duration: float):
    """
    Track skill execution metrics.

    Args:
        skill_id: Skill identifier
        status: Execution status (success, failure, error)
        duration: Execution duration in seconds
    """
    skill_executions_total.labels(
        skill_id=skill_id,
        status=status
    ).inc()

    skill_execution_duration_seconds.labels(
        skill_id=skill_id
    ).observe(duration)


def track_db_query(operation: str, duration: float):
    """
    Track database query performance.

    Args:
        operation: Query operation (select, insert, update, delete)
        duration: Query duration in seconds
    """
    db_query_duration_seconds.labels(
        operation=operation
    ).observe(duration)


def set_active_agents(count: int):
    """
    Set the current number of active agents.

    Args:
        count: Number of active agents
    """
    active_agents.set(count)


def set_db_connections(active: int, idle: int):
    """
    Set database connection pool metrics.

    Args:
        active: Number of active connections
        idle: Number of idle connections
    """
    db_connections_active.set(active)
    db_connections_idle.set(idle)


# ============================================================================
# DEPLOYMENT METRICS HELPERS
# ============================================================================


@contextmanager
def track_deployment(environment: str):
    """
    Context manager to track deployment metrics.

    Usage:
        with track_deployment('staging'):
            # deployment logic here
            pass
    """
    start_time = time.time()
    try:
        yield
        # Deployment succeeded
        deployment_total.labels(environment=environment, status='success').inc()
    except Exception:
        # Deployment failed
        deployment_total.labels(environment=environment, status='failed').inc()
        raise
    finally:
        # Record deployment duration
        duration = time.time() - start_time
        deployment_duration_seconds.labels(environment=environment).observe(duration)


@contextmanager
def track_smoke_test(environment: str):
    """
    Context manager to track smoke test metrics.

    Usage:
        with track_smoke_test('staging'):
            # smoke test logic here
            pass
    """
    start_time = time.time()
    try:
        yield
        # Smoke test passed
        smoke_test_total.labels(environment=environment, result='passed').inc()
    except Exception:
        # Smoke test failed
        smoke_test_total.labels(environment=environment, result='failed').inc()
        raise
    finally:
        # Record smoke test duration
        duration = time.time() - start_time
        smoke_test_duration_seconds.labels(environment=environment).observe(duration)


def record_rollback(environment: str, reason: str):
    """
    Record a deployment rollback event.

    Args:
        environment: Deployment environment (staging, production)
        reason: Rollback reason (smoke_test_failed, high_error_rate, manual)
    """
    deployment_rollback_total.labels(environment=environment, reason=reason).inc()


def update_canary_traffic(environment: str, deployment_id: str, percentage: int):
    """
    Update canary traffic percentage.

    Args:
        environment: Deployment environment (staging, production)
        deployment_id: Unique deployment identifier (e.g., git SHA)
        percentage: Traffic percentage (0-100)
    """
    canary_traffic_percentage.labels(
        environment=environment,
        deployment_id=deployment_id
    ).set(percentage)


def record_prometheus_query(workflow: str, success: bool, duration: float):
    """
    Record a Prometheus query attempt.

    Args:
        workflow: Workflow name (deploy-staging, deploy-production)
        success: Whether query succeeded
        duration: Query duration in seconds
    """
    result = 'success' if success else 'failed'
    prometheus_query_total.labels(workflow=workflow, result=result).inc()
    prometheus_query_duration_seconds.labels(workflow=workflow).observe(duration)


def initialize_metrics():
    """
    Initialize all Prometheus metrics.

    Starts Prometheus HTTP server on port 8001 for metrics scraping.
    """
    try:
        from prometheus_client import start_http_server
        start_http_server(8001)  # Metrics on port 8001
        log = get_logger(__name__)
        log.info("Prometheus metrics server started", port=8001)
    except OSError as e:
        log = get_logger(__name__)
        log.warning("Prometheus metrics server already running", error=str(e))


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Prometheus metrics
    'http_requests_total',
    'http_request_duration_seconds',
    'agent_executions_total',
    'agent_execution_duration_seconds',
    'active_agents',
    'skill_executions_total',
    'skill_execution_duration_seconds',
    'db_query_duration_seconds',
    'db_connections_active',
    'db_connections_idle',

    # Deployment metrics
    'deployment_total',
    'deployment_duration_seconds',
    'deployment_rollback_total',
    'deployment_frequency',
    'canary_traffic_percentage',
    'smoke_test_total',
    'smoke_test_duration_seconds',
    'prometheus_query_total',
    'prometheus_query_duration_seconds',

    # Structlog
    'configure_structlog',
    'get_logger',
    'RequestContext',

    # Metrics helpers
    'track_http_request',
    'track_agent_execution',
    'track_skill_execution',
    'track_db_query',
    'set_active_agents',
    'set_db_connections',

    # Deployment metrics helpers
    'track_deployment',
    'track_smoke_test',
    'record_rollback',
    'update_canary_traffic',
    'record_prometheus_query',
    'initialize_metrics',
]
