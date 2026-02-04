# Episodic Memory Quick Start Guide

## Introduction

The Episodic Memory system automatically stores and retrieves agent interaction history, enabling agents to learn from past experiences and demonstrate graduation readiness.

## 5-Minute Setup

### 1. Run Database Migration

```bash
cd backend
alembic upgrade head
```

This creates the following tables:
- `episodes` - Main episode storage
- `episode_segments` - Episode segments
- `episode_access_logs` - Audit trail

### 2. Verify Setup

```python
from core.models import Episode
from core.database import get_db_session

with get_db_session() as db:
    episodes = db.query(Episode).count()
    print(f"Episodes in database: {episodes}")
```

## Basic Usage

### Creating Episodes

Episodes are **automatically created** after agent sessions complete:

```python
from core.episode_integration import trigger_episode_creation

# Non-blocking trigger
trigger_episode_creation(
    session_id="chat_123",
    agent_id="agent_456",
    title="Optional custom title"
)
```

### Retrieving Episodes

#### Option 1: Time-Based (Temporal)

```python
from core.episode_retrieval_service import EpisodeRetrievalService
from core.database import get_db_session

with get_db_session() as db:
    service = EpisodeRetrievalService(db)

    # Get episodes from last 7 days
    result = await service.retrieve_temporal(
        agent_id="agent_456",
        time_range="7d"
    )

    for episode in result["episodes"]:
        print(f"{episode['title']}: {episode['started_at']}")
```

#### Option 2: Semantic Search

```python
# Find episodes similar to a query
result = await service.retrieve_semantic(
    agent_id="agent_456",
    query="HST tax calculations for machinery"
)

for episode in result["episodes"]:
    print(f"{episode['title']} (similarity: {episode.get('score', 0)})")
```

#### Option 3: Full Episode (Sequential)

```python
# Get complete episode with all segments
result = await service.retrieve_sequential(
    episode_id="episode_123",
    agent_id="agent_456"
)

print(f"Episode: {result['episode']['title']}")
print(f"Summary: {result['episode']['summary']}")

for segment in result['segments']:
    print(f"\n[{segment['segment_type']}] {segment['content']}")
```

#### Option 4: Contextual (Recommended)

```python
# Find episodes relevant to current task
result = await service.retrieve_contextual(
    agent_id="agent_456",
    current_task="Calculate HST for invoice #12345",
    limit=5
)

for episode in result["episodes"]:
    print(f"{episode['title']} (relevance: {episode.get('relevance_score', 0)})")
```

## Agent Graduation

### Check Readiness

```python
from core.agent_graduation_service import AgentGraduationService
from core.database import get_db_session

with get_db_session() as db:
    service = AgentGraduationService(db)

    result = await service.calculate_readiness_score(
        agent_id="student_agent",
        target_maturity="INTERN"
    )

    if result["ready"]:
        print(f"✓ Ready for promotion! Score: {result['score']}/100")
    else:
        print(f"✗ Not ready. Score: {result['score']}/100")
        print(f"Gaps: {', '.join(result['gaps'])}")
        print(f"Recommendation: {result['recommendation']}")
```

### Graduation Criteria

| Level | Min Episodes | Max Interventions | Min Score |
|-------|--------------|-------------------|-----------|
| INTERN | 10 | 50% | 70/100 |
| SUPERVISED | 25 | 20% | 85/100 |
| AUTONOMOUS | 50 | 0% | 95/100 |

### Promote Agent

```python
# After readiness check passes
await service.promote_agent(
    agent_id="student_agent",
    new_maturity="INTERN",
    validated_by="admin_user"
)
```

### Get Audit Trail

```python
# For governance compliance
audit = await service.get_graduation_audit_trail(agent_id="agent_456")

print(f"Agent: {audit['agent_name']}")
print(f"Maturity: {audit['current_maturity']}")
print(f"Total Episodes: {audit['total_episodes']}")
print(f"Total Interventions: {audit['total_interventions']}")
print(f"Constitutional Score: {audit['avg_constitutional_score']}")
```

## API Endpoints

### Episode Management

```bash
# Create episode
curl -X POST http://localhost:8000/api/episodes/create \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "chat_123",
    "agent_id": "agent_456"
  }'

# Temporal retrieval
curl -X POST http://localhost:8000/api/episodes/retrieve/temporal \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_456",
    "time_range": "7d"
  }'

# Semantic retrieval
curl -X POST http://localhost:8000/api/episodes/retrieve/semantic \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_456",
    "query": "tax calculations"
  }'

# Get full episode
curl http://localhost:8000/api/episodes/retrieve/episode_123?agent_id=agent_456
```

### Graduation

```bash
# Check readiness
curl http://localhost:8000/api/episodes/graduation/readiness/agent_456?target_maturity=INTERN

# Run exam
curl -X POST http://localhost:8000/api/episodes/graduation/exam \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_456",
    "edge_case_episodes": ["ep_1", "ep_2", "ep_3"]
  }'

# Promote agent
curl -X POST http://localhost:8000/api/episodes/graduation/promote \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_456",
    "new_maturity": "INTERN",
    "validated_by": "user_789"
  }'

# Get audit trail
curl http://localhost:8000/api/episodes/graduation/audit/agent_456
```

## Common Patterns

### Pattern 1: Agent Learning from Episodes

```python
from core.agent_world_model import WorldModelService

world_model = WorldModelService()

# Agent automatically recalls relevant past episodes
recall = await world_model.recall_experiences(
    agent=agent,
    current_task_description="Calculate HST for machinery sale",
    limit=5
)

# Episodes included in recall results
for episode in recall["episodes"]:
    # Agent can learn from past successes/failures
    if episode["human_intervention_count"] == 0:
        print(f"Autonomous success: {episode['title']}")
```

### Pattern 2: Tracking Agent Progress

```python
# Monitor agent's journey from STUDENT to AUTONOMOUS
audit = await service.get_graduation_audit_trail(agent_id="agent_456")

episodes_by_maturity = audit["episodes_by_maturity"]
print(f"Student episodes: {episodes_by_maturity.get('STUDENT', 0)}")
print(f"Intern episodes: {episodes_by_maturity.get('INTERN', 0)}")
print(f"Supervised episodes: {episodes_by_maturity.get('SUPERVISED', 0)}")
print(f"Autonomous episodes: {episodes_by_maturity.get('AUTONOMOUS', 0)}")
```

### Pattern 3: Compliance Reporting

```python
# Generate report for hospital board
audit = await service.get_graduation_audit_trail(agent_id="medscribe_agent")

report = f"""
MedScribe Graduation Report
============================

Total Episodes: {audit['total_episodes']}
Total Interventions: {audit['total_interventions']}
Avg Constitutional Score: {audit['avg_constitutional_score']:.2f}
Current Maturity: {audit['current_maturity']}

Compliance Status: {'✓ PASS' if audit['total_interventions'] == 0 else '✗ FAIL'}
"""

print(report)
```

## Performance Tips

1. **Use Temporal Retrieval** for recent episodes (< 30 days) - fastest (~10ms)
2. **Use Semantic Retrieval** for finding similar episodes across all time
3. **Use Contextual Retrieval** as default - balances recency and relevance
4. **Cache Episode IDs** for frequently accessed episodes

## Troubleshooting

### Episodes Not Created

**Problem**: Episodes not appearing after agent sessions

**Solution**:
1. Check if `agent_id` is provided in chat request
2. Verify LanceDB is accessible: `python -c "from core.lancedb_handler import get_lancedb_handler; print(get_lancedb_handler().test_connection())"`
3. Check session has sufficient content (min 2 messages or 1 execution)

### Governance Checks Failing

**Problem**: Retrieval returns "governance_check": {"allowed": False}

**Solution**:
1. Verify agent maturity level
2. Check action complexity matches maturity (see Governance Requirements)
3. Review `governance_check["reason"]` for specific failure reason

### Slow Semantic Search

**Problem**: Semantic retrieval > 100ms

**Solution**:
1. Verify LanceDB connection to S3/local storage
2. Check embedding provider is configured
3. Consider using temporal retrieval for recent episodes

## Next Steps

- Read [Full Implementation Guide](EPISODIC_MEMORY_IMPLEMENTATION.md)
- Review [Agent Graduation Guide](AGENT_GRADUATION_GUIDE.md)
- Check [API Documentation](../api/episode_routes.py)
- Run tests: `pytest tests/test_episode_*.py -v`
