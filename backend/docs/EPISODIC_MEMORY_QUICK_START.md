# Episodic Memory Quick Start Guide

**Last Updated**: February 4, 2026

Get started with Episodic Memory in 5 minutes.

---

## Prerequisites

- PostgreSQL database (for hot storage)
- LanceDB instance (for cold storage and semantic search)
- Agent registered in AgentRegistry
- Database migrations run (`alembic upgrade head`)

---

## Installation

### 1. Verify Database Models

```python
from core.models import Episode, EpisodeSegment, EpisodeAccessLog
from core.database import get_db_session

db = get_db_session()

# Check tables exist
print(Episode.__tablename__)  # "episodes"
print(EpisodeSegment.__tablename__)  # "episode_segments"
print(EpisodeAccessLog.__tablename__)  # "episode_access_logs"
```

### 2. Initialize Services

```python
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.agent_graduation_service import AgentGraduationService

# All services require a database session
db = get_db_session()

segmentation = EpisodeSegmentationService(db)
retrieval = EpisodeRetrievalService(db)
lifecycle = EpisodeLifecycleService(db)
graduation = AgentGraduationService(db)
```

---

## Basic Usage

### Creating Episodes

```python
# Start a new episode when agent begins a task
episode = await segmentation.create_episode(
    agent_id="agent_123",
    context={
        "task": "customer_support",
        "user_id": "user_456",
        "channel": "slack"
    }
)

print(f"Episode {episode.id} created")

# Add segments as interaction progresses
await segmentation.add_segment(
    episode_id=episode.id,
    content="User: I need help with a refund",
    metadata={
        "type": "user_message",
        "timestamp": "2026-02-04T10:00:00Z"
    }
)

await segmentation.add_segment(
    episode_id=episode.id,
    content="Agent: I can help you process a refund",
    metadata={
        "type": "agent_response",
        "confidence": 0.95
    }
)

# Finalize episode when task completes
await segmentation.finalize_episode(episode.id)
```

### Retrieving Episodes

```python
# Method 1: Temporal (last 7 days)
result = await retrieval.retrieve_temporal(
    agent_id="agent_123",
    time_range="7d"
)

for episode in result["episodes"]:
    print(f"Episode: {episode['id']}, Status: {episode['status']}")

# Method 2: Semantic (find similar episodes)
result = await retrieval.retrieve_semantic(
    agent_id="agent_123",
    query="customer refund request",
    limit=5
)

for episode in result["episodes"]:
    print(f"Similar episode: {episode['id']}, Score: {episode['similarity']}")

# Method 3: Sequential (get full episode)
result = await retrieval.retrieve_sequential(
    episode_id="episode_789"
)

print(f"Segments: {len(result['segments'])}")

# Method 4: Contextual (relevant to current task)
result = await retrieval.retrieve_contextual(
    agent_id="agent_123",
    current_context={
        "task": "customer_support",
        "topic": "refund"
    },
    limit=3
)
```

### Agent Graduation

```python
# Check if agent is ready for promotion
readiness = await graduation.calculate_readiness(
    agent_id="agent_123",
    target_level=AgentMaturityLevel.INTERN
)

print(f"Readiness Score: {readiness['readiness_score']}")
print(f"Episode Count: {readiness['episode_count']}/10")
print(f"Intervention Rate: {readiness['intervention_rate']}")
print(f"Constitutional Score: {readiness['constitutional_score']}")

# If readiness_score >= 1.0, run graduation exam
if readiness["readiness_score"] >= 1.0:
    exam_result = await graduation.run_graduation_exam(
        agent_id="agent_123",
        target_level=AgentMaturityLevel.INTERN
    )

    if exam_result["passed"]:
        # Promote agent
        await graduation.promote_agent(
            agent_id="agent_123",
            target_level=AgentMaturityLevel.INTERN
        )
        print("Agent promoted to INTERN!")
```

---

## Common Patterns

### Pattern 1: Episode Lifecycle Management

```python
async def handle_agent_task(agent_id: str, user_id: str, task_data: dict):
    """Complete episode lifecycle for a task"""
    
    # 1. Create episode
    episode = await segmentation.create_episode(
        agent_id=agent_id,
        context={"task": task_data["type"], "user_id": user_id}
    )
    
    try:
        # 2. Add segments during execution
        for message in task_data["messages"]:
            await segmentation.add_segment(
                episode_id=episode.id,
                content=message["content"],
                metadata={"type": message["type"]}
            )
        
        # 3. Execute task
        result = await execute_task(task_data)
        
        # 4. Finalize episode
        await segmentation.finalize_episode(episode.id)
        
        return result
    except Exception as e:
        # Episode will be auto-finalized as failed
        logger.error(f"Task failed: {e}")
        raise
```

### Pattern 2: Learning from Past Episodes

```python
async def leverage_agent_memory(agent_id: str, current_task: dict):
    """Retrieve relevant past episodes before executing task"""
    
    # 1. Find similar past episodes
    similar_episodes = await retrieval.retrieve_semantic(
        agent_id=agent_id,
        query=current_task["description"],
        limit=5
    )
    
    # 2. Extract learnings
    learnings = []
    for episode in similar_episodes["episodes"]:
        if episode["success_rate"] > 0.8:
            learnings.append({
                "episode_id": episode["id"],
                "approach": episode["metadata"]["approach"],
                "outcome": episode["result_summary"]
            })
    
    # 3. Apply learnings to current task
    if learnings:
        current_task["suggested_approach"] = learnings[0]["approach"]
        logger.info(f"Applied learning from {len(learnings)} past episodes")
    
    return current_task
```

### Pattern 3: Continuous Graduation Monitoring

```python
async def monitor_agent_progress(agent_id: str):
    """Track agent progress toward graduation"""
    
    levels = [
        AgentMaturityLevel.INTERN,
        AgentMaturityLevel.SUPERVISED,
        AgentMaturityLevel.AUTONOMOUS
    ]
    
    for level in levels:
        readiness = await graduation.calculate_readiness(
            agent_id=agent_id,
            target_level=level
        )
        
        print(f"\nProgress toward {level.value}:")
        print(f"  Readiness: {readiness['readiness_score']*100:.1f}%")
        print(f"  Episodes: {readiness['episode_count']}/{readiness['required_episodes']}")
        print(f"  Interventions: {readiness['intervention_rate']*100:.1f}%")
        print(f"  Constitutional: {readiness['constitutional_score']:.2f}")
        
        if readiness["readiness_score"] >= 1.0:
            print(f"  ✅ Ready for {level.value} graduation!")
        else:
            print(f"  ⏳ Not ready. Gap: {(1.0 - readiness['readiness_score'])*100:.1f}%")
```

---

## API Usage

### Creating Episodes via API

```bash
curl -X POST http://localhost:8000/api/episodes/create \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_123",
    "user_id": "user_456",
    "context": {
      "task": "customer_support",
      "channel": "slack"
    }
  }'
```

### Retrieving Episodes via API

```bash
# Temporal retrieval
curl -X POST http://localhost:8000/api/episodes/retrieve/temporal \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_123",
    "time_range": "7d",
    "limit": 50
  }'

# Semantic retrieval
curl -X POST http://localhost:8000/api/episodes/retrieve/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_123",
    "query": "customer refund request",
    "limit": 10
  }'
```

### Graduation Checks via API

```bash
# Check readiness
curl http://localhost:8000/api/episodes/graduation/readiness/agent_123?target_level=INTERN

# Run graduation exam
curl -X POST http://localhost:8000/api/episodes/graduation/exam \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_123",
    "target_level": "INTERN"
  }'
```

---

## Configuration

### Environment Variables

```bash
# Episode Segmentation
EPISODE_TIME_GAP_MINUTES=30
EPISODE_SEMANTIC_THRESHOLD=0.75

# Episode Lifecycle
EPISODE_DECAY_DAYS=90
EPISODE_ARCHIVE_DAYS=180
EPISODE_CONSOLIDATION_THRESHOLD=0.85

# Graduation
GRADUATION_MIN_EPISODES_INTERN=10
GRADUATION_MIN_EPISODES_SUPERVISED=25
GRADUATION_MIN_EPISODES_AUTONOMOUS=50
```

### Custom Thresholds

```python
from core.episode_segmentation_service import EpisodeSegmentationService

# Custom time gap threshold (60 minutes instead of 30)
service = EpisodeSegmentationService(db, time_gap_threshold=60)

# Custom semantic threshold (stricter similarity)
service = EpisodeSegmentationService(db, semantic_threshold=0.85)
```

---

## Troubleshooting

### Issue: Episodes not being created

**Solution**:
```python
# Verify agent exists
from core.models import AgentRegistry
agent = db.query(AgentRegistry).filter_by(id="agent_123").first()
if not agent:
    print("Agent not registered!")
```

### Issue: Semantic search returns empty results

**Solution**:
```python
# Check LanceDB connection
from core.lancedb_handler import get_lancedb_handler
lancedb = get_lancedb_handler()
print(f"LanceDB connected: {lancedb is not None}")
```

### Issue: Graduation exam fails

**Solution**:
```python
# Check readiness first
readiness = await graduation.calculate_readiness(
    agent_id="agent_123",
    target_level=AgentMaturityLevel.INTERN
)

print(f"Gaps:")
for key, value in readiness["gaps"].items():
    print(f"  {key}: {value}")
```

---

## Next Steps

1. **Read the full implementation guide**: `EPISODIC_MEMORY_IMPLEMENTATION.md`
2. **Explore graduation framework**: `AGENT_GRADUATION_GUIDE.md`
3. **Review API documentation**: `API_STANDARDS.md`
4. **Run tests**: `pytest tests/test_episode*.py -v`

---

## Quick Reference

| Service | File | Purpose |
|---------|------|---------|
| Segmentation | `core/episode_segmentation_service.py` | Create and manage episodes |
| Retrieval | `core/episode_retrieval_service.py` | Retrieve episodes (4 modes) |
| Lifecycle | `core/episode_lifecycle_service.py` | Decay, consolidate, archive |
| Graduation | `core/agent_graduation_service.py` | Validate agent promotion |

| API Route | Purpose |
|-----------|---------|
| `POST /api/episodes/create` | Create new episode |
| `POST /api/episodes/retrieve/temporal` | Time-based retrieval |
| `POST /api/episodes/retrieve/semantic` | Semantic search |
| `GET /api/episodes/retrieve/{id}` | Get full episode |
| `POST /api/episodes/retrieve/contextual` | Context-aware retrieval |
| `GET /api/episodes/graduation/readiness/{id}` | Check graduation readiness |
| `POST /api/episodes/graduation/exam` | Run graduation exam |

---

**Authors**: Atom Development Team
**Version**: 1.0.0
**Status**: Production Ready ✅
