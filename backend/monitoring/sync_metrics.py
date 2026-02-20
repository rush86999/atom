"""
Prometheus Metrics for Atom SaaS Sync Operations
Exposes sync-specific metrics for monitoring and alerting
"""
import logging
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


# ============================================================================
# Sync Operation Metrics
# ============================================================================

# Sync duration histogram (measures time for sync operations)
sync_duration_seconds = Histogram(
    'sync_duration_seconds',
    'Duration of sync operations in seconds',
    ['operation', 'status'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0]
)

# Total successful syncs counter
sync_success_total = Counter(
    'sync_success_total',
    'Total number of successful sync operations',
    ['operation']
)

# Total sync errors counter
sync_errors_total = Counter(
    'sync_errors_total',
    'Total number of sync errors',
    ['operation', 'error_type']
)

# Skills in cache gauge
sync_skills_cached = Gauge(
    'sync_skills_cached',
    'Number of skills currently in cache'
)

# Categories in cache gauge
sync_categories_cached = Gauge(
    'sync_categories_cached',
    'Number of categories currently in cache'
)

# ============================================================================
# WebSocket Metrics
# ============================================================================

# WebSocket connection status gauge (0=disconnected, 1=connected)
websocket_connected = Gauge(
    'websocket_connected',
    'WebSocket connection status (0=disconnected, 1=connected)'
)

# WebSocket reconnections counter
websocket_reconnects_total = Counter(
    'websocket_reconnects_total',
    'Total number of WebSocket reconnections'
)

# WebSocket messages received counter
websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total number of WebSocket messages received',
    ['message_type']
)

# ============================================================================
# Rating Sync Metrics
# ============================================================================

# Rating sync duration histogram
rating_sync_duration_seconds = Histogram(
    'rating_sync_duration_seconds',
    'Duration of rating sync operations in seconds',
    ['status'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Successful rating syncs counter
rating_sync_success_total = Counter(
    'rating_sync_success_total',
    'Total number of successful rating sync operations'
)

# Rating sync errors counter
rating_sync_errors_total = Counter(
    'rating_sync_errors_total',
    'Total number of rating sync errors',
    ['error_type']
)

# Pending ratings gauge
rating_sync_pending = Gauge(
    'rating_sync_pending',
    'Number of ratings pending sync to Atom SaaS'
)

# Failed rating uploads gauge
rating_sync_failed_uploads = Gauge(
    'rating_sync_failed_uploads',
    'Number of failed rating uploads awaiting retry'
)

# ============================================================================
# Conflict Resolution Metrics
# ============================================================================

# Conflicts detected counter
conflicts_detected_total = Counter(
    'conflicts_detected_total',
    'Total number of sync conflicts detected',
    ['conflict_type']
)

# Conflicts resolved counter
conflicts_resolved_total = Counter(
    'conflicts_resolved_total',
    'Total number of conflicts resolved',
    ['resolution_strategy']
)

# Unresolved conflicts gauge
conflicts_unresolved = Gauge(
    'conflicts_unresolved',
    'Number of unresolved conflicts'
)

# ============================================================================
# Metrics Update Functions
# ============================================================================

def record_sync_operation(operation: str, duration_seconds: float, success: bool, error_type: Optional[str] = None):
    """
    Record sync operation metrics

    Args:
        operation: Operation type (skills, categories, ratings)
        duration_seconds: Operation duration in seconds
        success: Whether operation succeeded
        error_type: Error type if failed (e.g., timeout, network_error, api_error)
    """
    status = 'success' if success else 'error'
    sync_duration_seconds.labels(operation=operation, status=status).observe(duration_seconds)

    if success:
        sync_success_total.labels(operation=operation).inc()
    else:
        sync_errors_total.labels(operation=operation, error_type=error_type or 'unknown').inc()


def update_cache_metrics(skills_count: int, categories_count: int):
    """
    Update cache size metrics

    Args:
        skills_count: Number of skills in cache
        categories_count: Number of categories in cache
    """
    sync_skills_cached.set(skills_count)
    sync_categories_cached.set(categories_count)


def set_websocket_connected(connected: bool):
    """
    Update WebSocket connection status

    Args:
        connected: Whether WebSocket is connected
    """
    websocket_connected.set(1 if connected else 0)


def record_websocket_reconnect():
    """Record WebSocket reconnection event"""
    websocket_reconnects_total.inc()


def record_websocket_message(message_type: str):
    """
    Record received WebSocket message

    Args:
        message_type: Type of message (skill_update, rating_update, etc.)
    """
    websocket_messages_total.labels(message_type=message_type).inc()


def record_rating_sync(duration_seconds: float, success: bool, error_type: Optional[str] = None):
    """
    Record rating sync metrics

    Args:
        duration_seconds: Sync duration in seconds
        success: Whether sync succeeded
        error_type: Error type if failed
    """
    status = 'success' if success else 'error'
    rating_sync_duration_seconds.labels(status=status).observe(duration_seconds)

    if success:
        rating_sync_success_total.inc()
    else:
        rating_sync_errors_total.labels(error_type=error_type or 'unknown').inc()


def update_rating_sync_metrics(pending: int, failed_uploads: int):
    """
    Update rating sync state metrics

    Args:
        pending: Number of pending ratings
        failed_uploads: Number of failed uploads
    """
    rating_sync_pending.set(pending)
    rating_sync_failed_uploads.set(failed_uploads)


def record_conflict_detected(conflict_type: str):
    """
    Record conflict detection

    Args:
        conflict_type: Type of conflict (version_mismatch, data_conflict, etc.)
    """
    conflicts_detected_total.labels(conflict_type=conflict_type).inc()
    conflicts_unresolved.inc()


def record_conflict_resolved(resolution_strategy: str):
    """
    Record conflict resolution

    Args:
        resolution_strategy: Strategy used (local_wins, remote_wins, merge)
    """
    conflicts_resolved_total.labels(resolution_strategy=resolution_strategy).inc()
    conflicts_unresolved.dec()


# ============================================================================
# Metrics Initialization
# ============================================================================

def initialize_metrics():
    """
    Initialize sync metrics with default values
    Called on application startup to set all gauges to known values
    """
    sync_skills_cached.set(0)
    sync_categories_cached.set(0)
    websocket_connected.set(0)
    rating_sync_pending.set(0)
    rating_sync_failed_uploads.set(0)
    conflicts_unresolved.set(0)

    logger.info("Sync metrics initialized with default values")


# Auto-initialize on module import
initialize_metrics()
