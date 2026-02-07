"""
Debug API Routes

REST endpoints for AI Debug System with governance integration.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.debug_collector import get_debug_collector, init_debug_collector
from core.debug_insight_engine import DebugInsightEngine
from core.debug_query import DebugQuery
from core.debug_ai_assistant import DebugAIAssistant
from core.debug_storage import HybridDebugStorage
from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugMetric,
    DebugSession,
    User,
)
from core.security_dependencies import get_current_user
from redis import Redis
from core.config import get_config
from sqlalchemy import and_


logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/debug", tags=["debug"])

# Feature flags
DEBUG_SYSTEM_ENABLED = os.getenv("DEBUG_SYSTEM_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


# ============================================================================
# Request Models
# ============================================================================

class CollectEventRequest(BaseModel):
    """Request to collect a debug event."""
    event_type: str = Field(..., description="Event type (log, state_snapshot, metric, error, system)")
    component_type: str = Field(..., description="Component type (agent, browser, workflow, system)")
    component_id: Optional[str] = Field(None, description="Component identifier")
    correlation_id: str = Field(..., description="Correlation ID to link related events")
    level: Optional[str] = Field(None, description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    message: Optional[str] = Field(None, description="Log message")
    data: Optional[Dict[str, Any]] = Field(None, description="Full event data")
    event_metadata: Optional[Dict[str, Any]] = Field(None, description="Tags, labels, additional context")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID for event chains")


class CollectBatchEventsRequest(BaseModel):
    """Request to collect multiple debug events."""
    events: List[Dict[str, Any]] = Field(..., description="List of event dictionaries")


class CollectStateSnapshotRequest(BaseModel):
    """Request to collect a state snapshot."""
    component_type: str = Field(..., description="Component type")
    component_id: str = Field(..., description="Component identifier")
    operation_id: str = Field(..., description="Operation correlation ID")
    state_data: Dict[str, Any] = Field(..., description="Full state capture")
    checkpoint_name: Optional[str] = Field(None, description="Optional checkpoint label")
    snapshot_type: str = Field("full", description="Snapshot type (full, incremental, partial)")
    diff_from_previous: Optional[Dict[str, Any]] = Field(None, description="Delta from previous snapshot")


class QueryEventsRequest(BaseModel):
    """Request to query debug events."""
    component_type: Optional[str] = Field(None, description="Filter by component type")
    component_id: Optional[str] = Field(None, description="Filter by component ID")
    correlation_id: Optional[str] = Field(None, description="Filter by correlation ID")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    level: Optional[str] = Field(None, description="Filter by log level")
    time_range: Optional[str] = Field(None, description="Time range filter (last_1h, last_24h, last_7d)")
    limit: int = Field(100, description="Maximum number of results")
    offset: int = Field(0, description="Result offset for pagination")


class QueryInsightsRequest(BaseModel):
    """Request to query debug insights."""
    insight_type: Optional[str] = Field(None, description="Filter by insight type")
    severity: Optional[str] = Field(None, description="Filter by severity")
    scope: Optional[str] = Field(None, description="Filter by scope")
    resolved: Optional[bool] = Field(None, description="Filter by resolution status")
    time_range: Optional[str] = Field(None, description="Time range filter")
    limit: int = Field(100, description="Maximum number of results")


class GenerateInsightsRequest(BaseModel):
    """Request to generate insights from events."""
    correlation_id: Optional[str] = Field(None, description="Filter by correlation ID")
    component_type: Optional[str] = Field(None, description="Filter by component type")
    component_id: Optional[str] = Field(None, description="Filter by component ID")
    time_range: Optional[str] = Field(None, description="Time range for analysis")


class CreateDebugSessionRequest(BaseModel):
    """Request to create a debug session."""
    session_name: str = Field(..., description="Session name")
    description: Optional[str] = Field(None, description="Session description")
    filters: Optional[Dict[str, Any]] = Field(None, description="Applied filters")
    scope: Optional[Dict[str, Any]] = Field(None, description="Component scope")


class ComponentHealthRequest(BaseModel):
    """Request to get component health."""
    component_type: str = Field(..., description="Component type")
    component_id: str = Field(..., description="Component ID")
    time_range: str = Field("1h", description="Time range for analysis")


class NaturalLanguageQueryRequest(BaseModel):
    """Request for natural language query."""
    question: str = Field(..., description="Natural language question")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (user_id, component_id, etc.)")


# ============================================================================
# Event Collection Endpoints
# ============================================================================

@router.post("/events")
async def collect_event(
    request: CollectEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Collect a single debug event."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    collector = get_debug_collector()
    if not collector:
        collector = init_debug_collector(db_session=db)

    event = await collector.collect_event(
        event_type=request.event_type,
        component_type=request.component_type,
        component_id=request.component_id,
        correlation_id=request.correlation_id,
        level=request.level,
        message=request.message,
        data=request.data,
        event_metadata=request.event_metadata,
        parent_event_id=request.parent_event_id,
    )

    return router.success_response(
        data={"event_id": event.id} if event else {"event_id": None},
        message="Event collected successfully"
    )


@router.post("/events/batch")
async def collect_batch_events(
    request: CollectBatchEventsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Collect multiple debug events in batch."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    collector = get_debug_collector()
    if not collector:
        collector = init_debug_collector(db_session=db)

    events = await collector.collect_batch_events(request.events)

    return router.success_response(
        data={
            "collected_count": len(events),
            "event_ids": [e.id if e else None for e in events]
        },
        message=f"Collected {len(events)} events"
    )


@router.get("/events")
async def query_events(
    component_type: Optional[str] = None,
    component_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    event_type: Optional[str] = None,
    level: Optional[str] = None,
    time_range: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query debug events with filters."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"events": [], "enabled": False},
            message="Debug system is disabled"
        )

    storage = _get_storage(db)
    events = await storage.query_events(
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        event_type=event_type,
        level=level,
        time_range=time_range,
        limit=limit,
        offset=offset,
    )

    return router.success_response(
        data={
            "events": events,
            "count": len(events)
        },
        message=f"Found {len(events)} events"
    )


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single debug event by ID."""
    if not DEBUG_SYSTEM_ENABLED:
        raise router.error_response(
            error_code="DEBUG_DISABLED",
            message="Debug system is disabled",
            status_code=400
        )

    storage = _get_storage(db)
    event = await storage.get_event(event_id)

    if not event:
        raise router.error_response(
            error_code="EVENT_NOT_FOUND",
            message=f"Event {event_id} not found",
            status_code=404
        )

    return router.success_response(data=event, message="Event retrieved")


# ============================================================================
# State Snapshot Endpoints
# ============================================================================

@router.post("/state")
async def collect_state_snapshot(
    request: CollectStateSnapshotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Collect a component state snapshot."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    collector = get_debug_collector()
    if not collector:
        collector = init_debug_collector(db_session=db)

    snapshot = await collector.collect_state_snapshot(
        component_type=request.component_type,
        component_id=request.component_id,
        operation_id=request.operation_id,
        state_data=request.state_data,
        checkpoint_name=request.checkpoint_name,
        snapshot_type=request.snapshot_type,
        diff_from_previous=request.diff_from_previous,
    )

    return router.success_response(
        data={"snapshot_id": snapshot.id} if snapshot else {"snapshot_id": None},
        message="State snapshot collected"
    )


@router.get("/state/{component_type}/{component_id}")
async def get_component_state(
    component_type: str,
    component_id: str,
    operation_id: Optional[str] = None,
    checkpoint_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get component state snapshot."""
    if not DEBUG_SYSTEM_ENABLED:
        raise router.error_response(
            error_code="DEBUG_DISABLED",
            message="Debug system is disabled",
            status_code=400
        )

    if not operation_id:
        raise router.error_response(
            error_code="MISSING_OPERATION_ID",
            message="operation_id is required",
            status_code=400
        )

    storage = _get_storage(db)
    snapshot = await storage.get_state_snapshot(
        component_type=component_type,
        component_id=component_id,
        operation_id=operation_id,
        checkpoint_name=checkpoint_name,
    )

    if not snapshot:
        raise router.error_response(
            error_code="SNAPSHOT_NOT_FOUND",
            message="State snapshot not found",
            status_code=404
        )

    return router.success_response(data=snapshot, message="State snapshot retrieved")


# ============================================================================
# Insight Endpoints
# ============================================================================

@router.get("/insights")
async def query_insights(
    insight_type: Optional[str] = None,
    severity: Optional[str] = None,
    scope: Optional[str] = None,
    resolved: Optional[bool] = None,
    time_range: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query debug insights with filters."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"insights": [], "enabled": False},
            message="Debug system is disabled"
        )

    storage = _get_storage(db)
    insights = await storage.query_insights(
        insight_type=insight_type,
        severity=severity,
        scope=scope,
        resolved=resolved,
        time_range=time_range,
        limit=limit,
    )

    return router.success_response(
        data={
            "insights": insights,
            "count": len(insights)
        },
        message=f"Found {len(insights)} insights"
    )


@router.get("/insights/{insight_id}")
async def get_insight(
    insight_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single insight by ID."""
    if not DEBUG_SYSTEM_ENABLED:
        raise router.error_response(
            error_code="DEBUG_DISABLED",
            message="Debug system is disabled",
            status_code=400
        )

    storage = _get_storage(db)
    insight = await storage.get_insight(insight_id)

    if not insight:
        raise router.error_response(
            error_code="INSIGHT_NOT_FOUND",
            message=f"Insight {insight_id} not found",
            status_code=404
        )

    return router.success_response(data=insight, message="Insight retrieved")


@router.post("/insights/generate")
async def generate_insights(
    request: GenerateInsightsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate insights from debug events."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"insights": [], "enabled": False},
            message="Debug system is disabled"
        )

    engine = DebugInsightEngine(db)
    insights = await engine.generate_insights_from_events(
        correlation_id=request.correlation_id,
        component_type=request.component_type,
        component_id=request.component_id,
        time_range=request.time_range,
    )

    return router.success_response(
        data={
            "insights": [engine._insight_to_dict(i) for i in insights],
            "count": len(insights)
        },
        message=f"Generated {len(insights)} insights"
    )


@router.put("/insights/{insight_id}/resolve")
async def resolve_insight(
    insight_id: str,
    resolution_notes: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an insight as resolved."""
    if not DEBUG_SYSTEM_ENABLED:
        raise router.error_response(
            error_code="DEBUG_DISABLED",
            message="Debug system is disabled",
            status_code=400
        )

    insight = db.query(DebugInsight).filter(DebugInsight.id == insight_id).first()

    if not insight:
        raise router.error_response(
            error_code="INSIGHT_NOT_FOUND",
            message=f"Insight {insight_id} not found",
            status_code=404
        )

    insight.resolved = True
    insight.resolution_notes = resolution_notes
    db.commit()

    return router.success_response(
        data={"insight_id": insight_id, "resolved": True},
        message="Insight marked as resolved"
    )


# ============================================================================
# Debug Session Endpoints
# ============================================================================

@router.post("/sessions")
async def create_debug_session(
    request: CreateDebugSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new debug session."""
    if not DEBUG_SYSTEM_ENABLED:
        raise router.error_response(
            error_code="DEBUG_DISABLED",
            message="Debug system is disabled",
            status_code=400
        )

    session = DebugSession(
        session_name=request.session_name,
        description=request.description,
        filters=request.filters,
        scope=request.scope,
    )

    db.add(session)
    db.commit()

    return router.success_response(
        data={"session_id": session.id},
        message="Debug session created"
    )


@router.get("/sessions")
async def list_debug_sessions(
    active: Optional[bool] = None,
    resolved: Optional[bool] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List debug sessions."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"sessions": [], "enabled": False},
            message="Debug system is disabled"
        )

    query = db.query(DebugSession)

    if active is not None:
        query = query.filter(DebugSession.active == active)
    if resolved is not None:
        query = query.filter(DebugSession.resolved == resolved)

    sessions = query.order_by(DebugSession.created_at.desc()).limit(limit).all()

    return router.success_response(
        data={
            "sessions": [
                {
                    "id": s.id,
                    "session_name": s.session_name,
                    "description": s.description,
                    "active": s.active,
                    "resolved": s.resolved,
                    "event_count": s.event_count,
                    "insight_count": s.insight_count,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
            "count": len(sessions)
        },
        message=f"Found {len(sessions)} sessions"
    )


@router.put("/sessions/{session_id}/close")
async def close_debug_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close a debug session."""
    if not DEBUG_SYSTEM_ENABLED:
        raise router.error_response(
            error_code="DEBUG_DISABLED",
            message="Debug system is disabled",
            status_code=400
        )

    session = db.query(DebugSession).filter(DebugSession.id == session_id).first()

    if not session:
        raise router.error_response(
            error_code="SESSION_NOT_FOUND",
            message=f"Session {session_id} not found",
            status_code=404
        )

    from datetime import datetime
    session.active = False
    session.closed_at = datetime.utcnow()
    db.commit()

    return router.success_response(
        data={"session_id": session_id, "closed": True},
        message="Debug session closed"
    )


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.post("/analytics/component-health")
async def get_component_health(
    request: ComponentHealthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get component health status."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    query = DebugQuery(db)
    health = await query.get_component_health(
        component_type=request.component_type,
        component_id=request.component_id,
        time_range=request.time_range,
    )

    return router.success_response(data=health, message="Component health retrieved")


@router.get("/analytics/error-patterns")
async def get_error_patterns(
    time_range: str = "last_24h",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get error patterns and analytics."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    # Query error events
    time_filter = _parse_time_range(time_range)

    error_events = (
        db.query(DebugEvent)
        .filter(
            and_(
                DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                DebugEvent.timestamp >= time_filter,
            )
        )
        .all()
    )

    # Analyze patterns
    error_patterns = {}
    for event in error_events:
        pattern_key = f"{event.component_type}:{event.message[:50] if event.message else 'unknown'}"
        if pattern_key not in error_patterns:
            error_patterns[pattern_key] = {
                "component_type": event.component_type,
                "message": event.message,
                "count": 0,
                "first_seen": event.timestamp,
                "last_seen": event.timestamp,
            }
        error_patterns[pattern_key]["count"] += 1
        if event.timestamp < error_patterns[pattern_key]["first_seen"]:
            error_patterns[pattern_key]["first_seen"] = event.timestamp
        if event.timestamp > error_patterns[pattern_key]["last_seen"]:
            error_patterns[pattern_key]["last_seen"] = event.timestamp

    patterns_list = list(error_patterns.values())
    patterns_list.sort(key=lambda x: x["count"], reverse=True)

    return router.success_response(
        data={
            "error_patterns": patterns_list[:20],  # Top 20
            "total_errors": len(error_events),
            "time_range": time_range,
        },
        message=f"Found {len(patterns_list)} error patterns"
    )


@router.get("/analytics/system-health")
async def get_system_health_analytics(
    time_range: str = "last_1h",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get system-wide health metrics."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    from core.debug_monitor import DebugMonitor

    monitor = DebugMonitor(db)
    health = await monitor.get_system_health(time_range)

    return router.success_response(data=health, message="System health retrieved")


@router.get("/analytics/active-operations")
async def get_active_operations(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get currently active operations."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"operations": [], "enabled": False},
            message="Debug system is disabled"
        )

    from core.debug_monitor import DebugMonitor

    monitor = DebugMonitor(db)
    operations = await monitor.get_active_operations(limit=limit)

    return router.success_response(
        data={
            "operations": operations,
            "count": len(operations),
        },
        message=f"Found {len(operations)} active operations"
    )


@router.get("/analytics/throughput")
async def get_throughput_analytics(
    time_range: str = "last_1h",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get throughput metrics."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    from core.debug_monitor import DebugMonitor

    monitor = DebugMonitor(db)
    throughput = await monitor.get_throughput_metrics(time_range)

    return router.success_response(data=throughput, message="Throughput metrics retrieved")


@router.get("/analytics/insights-summary")
async def get_insights_summary(
    time_range: str = "last_24h",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get insights summary by type and severity."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    from core.debug_monitor import DebugMonitor

    monitor = DebugMonitor(db)
    summary = await monitor.get_insight_summary(time_range)

    return router.success_response(data=summary, message="Insights summary retrieved")


@router.post("/analytics/performance")
async def get_performance_analytics(
    request: ComponentHealthRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get performance analytics for a component."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    from core.debug_insights.performance import PerformanceInsightGenerator

    perf_gen = PerformanceInsightGenerator(db)
    insight = await perf_gen.analyze_component_latency(
        component_type=request.component_type,
        component_id=request.component_id,
        time_range=request.time_range,
    )

    if not insight:
        return router.success_response(
            data={"insight": None},
            message="No performance data available"
        )

    return router.success_response(
        data={
            "insight": {
                "id": insight.id,
                "type": insight.insight_type,
                "severity": insight.severity,
                "title": insight.title,
                "summary": insight.summary,
                "description": insight.description,
                "evidence": insight.evidence,
                "confidence_score": insight.confidence_score,
                "suggestions": insight.suggestions,
            }
        },
        message="Performance analytics retrieved"
    )


@router.get("/analytics/error-rate")
async def get_error_rate_analytics(
    time_range: str = "last_1h",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get error rate by component."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    from core.debug_monitor import DebugMonitor

    monitor = DebugMonitor(db)
    error_rates = await monitor.get_error_rate_by_component(time_range)

    return router.success_response(
        data={
            "error_rates": error_rates,
            "time_range": time_range,
        },
        message=f"Error rates for {len(error_rates)} components"
    )


# ============================================================================
# AI Query Endpoints
# ============================================================================

@router.post("/ai/query")
async def natural_language_query(
    request: NaturalLanguageQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Natural language query for debug information with AI-powered analysis."""
    if not DEBUG_SYSTEM_ENABLED:
        return router.success_response(
            data={"enabled": False},
            message="Debug system is disabled"
        )

    assistant = DebugAIAssistant(
        db_session=db,
        enable_prediction=True,
        enable_self_healing=False,
    )
    result = await assistant.ask(
        question=request.question,
        context=request.context,
    )

    return router.success_response(data=result, message="Query processed")


# ============================================================================
# Helper Functions
# ============================================================================

def _get_storage(db: Session) -> HybridDebugStorage:
    """Get or create hybrid storage instance."""
    try:
        config = get_config()
        redis_client = Redis.from_url(config.redis_url)
    except:
        redis_client = None

    return HybridDebugStorage(db_session=db, redis_client=redis_client)


def _parse_time_range(time_range: str):
    """Parse time range string to datetime."""
    from datetime import datetime, timedelta

    now = datetime.utcnow()

    if time_range == "last_1h":
        return now - timedelta(hours=1)
    elif time_range == "last_24h":
        return now - timedelta(hours=24)
    elif time_range == "last_7d":
        return now - timedelta(days=7)
    elif time_range == "last_30d":
        return now - timedelta(days=30)
    else:
        return now - timedelta(hours=1)
