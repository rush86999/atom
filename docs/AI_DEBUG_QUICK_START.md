# AI Debug System - Quick Start Guide

Get started with the AI Debug System in 5 minutes.

---

## Prerequisites

- Atom Platform backend running
- PostgreSQL database
- Redis server (optional, for real-time features)

---

## Installation

### 1. Run Database Migration

```bash
cd backend
alembic upgrade head
```

This creates the following tables:
- `debug_events` - Raw debug events
- `debug_insights` - Abstracted insights
- `debug_state_snapshots` - Component state snapshots
- `debug_metrics` - Time-series metrics
- `debug_sessions` - Debug sessions

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Enable debug system
DEBUG_SYSTEM_ENABLED=true

# Retention settings
DEBUG_EVENT_RETENTION_HOURS=168    # 7 days
DEBUG_INSIGHT_RETENTION_HOURS=720  # 30 days

# Cache settings
DEBUG_CACHE_TTL_SECONDS=300        # 5 minutes

# Redis (optional)
DEBUG_REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# WebSocket
DEBUG_STREAMING_ENABLED=true
```

### 3. Verify Installation

```bash
# Run tests
pytest backend/tests/test_debug_models.py -v

# Check database tables
sqlite3 data/atom.db ".tables" | grep debug
# Should see: debug_events debug_insights debug_state_snapshots debug_metrics debug_sessions
```

---

## Basic Usage

### 1. Collect Debug Events

```python
from core.debug_collector import init_debug_collector
from sqlalchemy.orm import Session

from core.database import get_db

# Get database session
db: Session = next(get_db())

# Initialize collector
collector = init_debug_collector(db_session=db)

# Collect an event
event = await collector.collect_event(
    event_type="log",
    component_type="agent",
    component_id="agent-123",
    correlation_id="corr-456",
    level="INFO",
    message="Agent started successfully",
    data={"timestamp": "2026-02-06T10:00:00Z"}
)

print(f"Event collected: {event.id}")
```

### 2. Collect State Snapshots

```python
# Collect component state
snapshot = await collector.collect_state_snapshot(
    component_type="agent",
    component_id="agent-123",
    operation_id="op-789",
    state_data={
        "status": "running",
        "progress": 0.65,
        "current_step": "data_processing"
    },
    checkpoint_name="midpoint",
    snapshot_type="full"
)

print(f"Snapshot collected: {snapshot.id}")
```

### 3. Generate Insights

```python
from core.debug_insight_engine import DebugInsightEngine

# Initialize insight engine
engine = DebugInsightEngine(db)

# Generate insights from events
insights = await engine.generate_insights_from_events(
    correlation_id="corr-456",
    component_type="agent",
    component_id="agent-123"
)

print(f"Generated {len(insights)} insights")
for insight in insights:
    print(f"  - [{insight.severity}] {insight.title}")
    print(f"    {insight.summary}")
```

### 4. Query Debug Data

```python
from core.debug_query import DebugQuery

# Initialize query API
query = DebugQuery(db)

# Get component health
health = await query.get_component_health(
    component_type="agent",
    component_id="agent-123",
    time_range="1h"
)

print(f"Component Health:")
print(f"  Status: {health['status']}")
print(f"  Score: {health['health_score']}")
print(f"  Total Events: {health['total_events']}")
print(f"  Error Rate: {health['error_rate']*100:.1f}%")

# Get operation progress
progress = await query.get_operation_progress("op-789")
print(f"\nOperation Progress:")
print(f"  Status: {progress['status']}")
print(f"  Progress: {progress['progress']*100:.1f}%")
print(f"  Steps: {progress['completed_steps']}/{progress['total_steps']}")
```

### 5. Use REST API

```bash
# Collect event
curl -X POST http://localhost:8000/api/debug/events \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "event_type": "log",
    "component_type": "agent",
    "component_id": "agent-123",
    "correlation_id": "corr-456",
    "level": "INFO",
    "message": "Agent started"
  }'

# Query events
curl http://localhost:8000/api/debug/events?component_type=agent&component_id=agent-123 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Generate insights
curl -X POST http://localhost:8000/api/debug/insights/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "component_type": "agent",
    "component_id": "agent-123"
  }'

# Get component health
curl -X POST http://localhost:8000/api/debug/analytics/component-health \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "component_type": "agent",
    "component_id": "agent-123",
    "time_range": "1h"
  }'
```

### 6. Subscribe to Real-Time Events (WebSocket)

```python
from fastapi import WebSocket
from core.debug_streaming import init_debug_streaming

# Initialize streaming
streaming = init_debug_streaming()

@app.websocket("/ws/debug/{component_id}")
async def debug_endpoint(websocket: WebSocket, component_id: str):
    await websocket.accept()

    # Subscribe to debug stream
    await streaming.subscribe_client(
        websocket,
        f"debug:{component_id}",
        filters={"level": ["ERROR", "CRITICAL"]}
    )

    try:
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await streaming.unsubscribe_client(websocket)
```

---

## Common Patterns

### Debug a Failing Operation

```python
from core.debug_query import DebugQuery

query = DebugQuery(db)

# 1. Check operation progress
progress = await query.get_operation_progress("op-failing-123")
print(f"Operation: {progress['status']}, Progress: {progress['progress']*100:.1f}%")

# 2. Get component health
health = await query.get_component_health("workflow", "workflow-789", "1h")
print(f"Health: {health['status']} (score: {health['health_score']})")

# 3. Get error explanation if unhealthy
if health['status'] == 'unhealthy':
    # Find recent errors
    insights = health.get('insights', [])
    error_insights = [i for i in insights if i.get('type') == 'error']

    if error_insights:
        error_id = error_insights[0]['id']
        explanation = await query.explain_error(error_id)
        print(f"Root Cause: {explanation['root_cause']}")
        print(f"Suggestions: {explanation['suggestions']}")
```

### Monitor Distributed System Consistency

```python
from core.debug_insight_engine import DebugInsightEngine

engine = DebugInsightEngine(db)

# Analyze consistency across nodes
insight = await engine.analyze_state_consistency(
    operation_id="op-distributed-456",
    component_ids=["node-1", "node-2", "node-3", "node-4", "node-5"],
    component_type="agent"
)

if insight.confidence_score >= 0.7:
    print(f"Consistency Analysis:")
    print(f"  {insight.title}")
    print(f"  {insight.summary}")

    if insight.suggestions:
        print(f"  Recommendations:")
        for suggestion in insight.suggestions:
            print(f"    - {suggestion}")
```

### Natural Language Querying

```python
from core.debug_query import DebugQuery

query = DebugQuery(db)

# Ask questions in natural language
result = await query.ask("Why is workflow-789 failing?")
print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence']}")

if result['evidence']:
    print(f"Evidence:")
    for evidence in result['evidence']:
        print(f"  - {evidence}")
```

---

## Troubleshooting

### Events Not Being Collected

**Problem**: Events are not appearing in the database.

**Solution**:
1. Check if debug system is enabled: `DEBUG_SYSTEM_ENABLED=true`
2. Verify database connection
3. Check logs for errors: `tail -f logs/atom.log | grep debug`

### Insights Not Being Generated

**Problem**: No insights are being generated from events.

**Solution**:
1. Ensure events are being collected first
2. Check confidence threshold: `DEBUG_INSIGHT_CONFIDENCE_THRESHOLD=0.7`
3. Verify insight auto-generation: `DEBUG_INSIGHT_AUTO_GENERATE=true`
4. Manually trigger insight generation via API

### Real-Time Streaming Not Working

**Problem**: WebSocket clients not receiving events.

**Solution**:
1. Check Redis connection: `REDIS_URL`
2. Verify streaming is enabled: `DEBUG_STREAMING_ENABLED=true`
3. Ensure client is subscribed to correct stream ID: `debug:{component_id}`

### Cache Hit Rate Low

**Problem**: Cache hit rate is below 90%.

**Solution**:
1. Increase cache size: `DEBUG_CACHE_MAX_SIZE=2000`
2. Adjust TTL: `DEBUG_CACHE_TTL_SECONDS=600`
3. Check cache stats via API

---

## Performance Tuning

### High-Volume Event Ingestion

For systems with >10k events/sec:

```bash
# Increase batch size
DEBUG_BATCH_SIZE_MS=50  # Flush more frequently

# Use connection pooling
DATABASE_POOL_SIZE=20

# Disable archiving during peak load
DEBUG_PG_AUTO_ARCHIVE=false
```

### Low-Latency Queries

For <50ms query latency:

```bash
# Increase cache size
DEBUG_CACHE_MAX_SIZE=5000

# Extend cache TTL
DEBUG_CACHE_TTL_SECONDS=600

# Use Redis for hot storage
DEBUG_REDIS_HOT_TTL_HOURS=24
```

---

## Next Steps

1. **Read Full Documentation**: See `docs/AI_DEBUG_SYSTEM.md`
2. **Explore Tests**: Check `backend/tests/test_debug_*.py` for examples
3. **Review API**: Visit `http://localhost:8000/docs` for interactive API docs
4. **Monitor Performance**: Use `/api/debug/analytics/component-health` endpoint

---

## Support

- **Issues**: Create GitHub issue
- **Questions**: Check existing documentation
- **Contributing**: See `CONTRIBUTING.md`
