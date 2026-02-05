# Episodic Memory Implementation Guide

## Overview

The Episodic Memory system provides AI agents with the ability to remember, retrieve, and learn from past interactions. It automatically segments agent sessions into coherent episodes, stores them in a hybrid PostgreSQL (hot) + LanceDB (cold) architecture, and provides multiple retrieval modes optimized for different use cases.

## Table of Contents

- [Architecture](#architecture)
- [Data Models](#data-models)
- [Episode Canvas & Feedback Integration](#episode-canvas--feedback-integration-)
- [Core Services](#core-services)
- [API Endpoints](#api-endpoints)
- [Graduation Framework](#graduation-framework)
- [Usage Examples](#usage-examples)
- [Performance Characteristics](#performance-characteristics)
- [Governance Requirements](#governance-requirements)

---

## Architecture

### Storage Strategy: Hybrid PostgreSQL + LanceDB

```
┌─────────────────────────────────────────────────────────────────┐
│                     EPISODIC MEMORY LAYERS                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  HOT STORAGE (PostgreSQL)                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Episode Metadata (structured data)                       │   │
│  │  - Episode records (id, title, status, timestamps)       │   │
│  │  - EpisodeSegment records (sequence, content summary)    │   │
│  │  - EpisodeAccessLog (audit trail)                        │   │
│  │  - Indexed queries: temporal, status-based, pagination   │   │
│  │  - Recent episodes: last 30 days                         │   │
│  │  - Fast retrieval: ~10ms (indexed)                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          ↓ (aging)                               │
│  COLD STORAGE (LanceDB on S3)                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Full Episode Content (vector search)                     │   │
│  │  - Complete episode text (all segments)                  │   │
│  │  - Embeddings for semantic search                        │   │
│  │  - Older episodes: 30+ days                              │   │
│  │  - Semantic retrieval: ~50-100ms                         │   │
│  │  - Scales to millions of episodes                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Lifecycle

1. **Episode Created** (ChatSession completes)
   - PostgreSQL: Episode + segments created (HOT)
   - LanceDB: Full content archived immediately (COLD)

2. **Episode Access** (First 30 days)
   - Temporal queries: PostgreSQL indexed lookup (~10ms)
   - Semantic queries: LanceDB vector search (~50-100ms)
   - Sequential queries: PostgreSQL joins (~20ms)

3. **Episode Aging** (30-180 days)
   - Decay score gradually applied
   - Still accessible via all retrieval modes

4. **Episode Archival** (180+ days)
   - PostgreSQL: status → "archived"
   - LanceDB: Permanent storage, still searchable

---

## Data Models

### Episode Model

```python
class Episode(Base):
    """Episodic memory container for agent interactions"""

    # Core identity
    id: str                    # UUID
    title: str                 # Episode title
    description: str           # Optional description
    summary: str               # Generated summary

    # Attribution
    agent_id: str              # FK to agent_registry
    user_id: str               # FK to users
    workspace_id: str          # FK to workspaces
    session_id: str            # Links to ChatSession

    # Boundaries
    started_at: DateTime       # Episode start
    ended_at: DateTime         # Episode end
    duration_seconds: int      # Calculated duration

    # State
    status: str                # active, completed, archived, consolidated
    topics: JSON               # Extracted topics
    entities: JSON             # Named entities
    importance_score: float    # 0.0 to 1.0

    # Graduation tracking
    maturity_at_time: str      # STUDENT, INTERN, SUPERVISED, AUTONOMOUS
    human_intervention_count: int
    human_edits: JSON          # List of corrections
    constitutional_score: float # 0.0 to 1.0
    world_model_state: str     # Version identifier

    # Lifecycle
    decay_score: float         # 0.0 to 1.0, decays over time
    access_count: int          # Track usage
    consolidated_into: str     # FK to parent episode
```

### EpisodeSegment Model

```python
class EpisodeSegment(Base):
    """Individual segments within an episode"""

    id: str
    episode_id: str            # FK to episodes (CASCADE delete)
    segment_type: str          # conversation, execution, reflection
    sequence_order: int        # For ordering within episode
    content: Text              # Full segment content
    content_summary: str       # Shortened version
    source_type: str           # chat_message, agent_execution, manual
    source_id: str             # ID of source object
```

### EpisodeAccessLog Model

```python
class EpisodeAccessLog(Base):
    """Audit trail for episode access"""

    id: str
    episode_id: str            # FK to episodes (CASCADE delete)
    accessed_by: str           # FK to users
    accessed_by_agent: str     # FK to agent_registry
    access_type: str           # temporal, semantic, sequential, contextual
    retrieval_query: str
    governance_check_passed: bool
    agent_maturity_at_access: str
    results_count: int
    access_duration_ms: int
```

### Episode Canvas & Feedback Integration ✨ NEW

Episodes now include lightweight references to canvas presentations and user feedback for enriched agent reasoning.

**Architecture Pattern**: Metadata-Only Linkage
- Episodes store ID arrays (`canvas_ids`, `feedback_ids`)
- Full records fetched on demand during retrieval
- Storage overhead: ~100 bytes per episode

**Episode Model Additions**:
```python
class Episode(Base):
    # ... existing fields ...

    # Canvas linkage (NEW - Feb 2026)
    canvas_ids = List[str]              # CanvasAudit IDs
    canvas_action_count = int           # Total canvas actions

    # Feedback linkage (NEW - Feb 2026)
    feedback_ids = List[str]            # AgentFeedback IDs
    aggregate_feedback_score = float    # -1.0 to 1.0
```

**Backlinks**:
```python
class CanvasAudit(Base):
    episode_id = str  # Backlink to episode

class AgentFeedback(Base):
    episode_id = str  # Backlink to episode
```

**Features**:
1. **Canvas-Aware Episodes**: Track all canvas interactions (present, submit, close, update, execute)
2. **Feedback-Linked Episodes**: Aggregate user feedback scores for retrieval weighting
3. **Enriched Sequential Retrieval**: Episodes include `canvas_context` and `feedback_context` by default
4. **Canvas Type Filtering**: Retrieve episodes by canvas type (sheets, charts, forms)
5. **Feedback-Weighted Retrieval**: Positive feedback +0.2 boost, negative -0.3 penalty

**Example Enriched Episode**:
```python
episode = {
    "id": "ep_123",
    "canvas_ids": ["canvas_abc", "canvas_def"],
    "feedback_ids": ["feedback_xyz"],
    "canvas_context": [
        {
            "canvas_type": "sheets",
            "component_type": "table",
            "action": "present",
            "created_at": "2026-02-04T10:00:00Z"
        }
    ],
    "feedback_context": [
        {
            "feedback_type": "thumbs_up",
            "rating": 5,
            "created_at": "2026-02-04T10:05:00Z"
        }
    ]
}
```

**Agent Decision-Making**: Agents **ALWAYS** fetch canvas/feedback context during episode recall, not just for canvas-specific tasks.

**See Also**: [`CANVAS_FEEDBACK_EPISODIC_MEMORY.md`](./CANVAS_FEEDBACK_EPISODIC_MEMORY.md) for complete documentation.

---

## Core Services

### 1. EpisodeSegmentationService

**Purpose**: Automatically creates episodes from agent sessions

**Location**: `backend/core/episode_segmentation_service.py`

**Key Methods**:

```python
async def create_episode_from_session(
    session_id: str,
    agent_id: str,
    title: Optional[str] = None,
    force_create: bool = False
) -> Optional[Episode]
```

**Boundary Detection**:

- **Time Gap Detection**: Detects gaps > 30 minutes between messages
- **Topic Change Detection**: Uses semantic similarity (< 0.75) to detect topic shifts
- **Task Completion Detection**: Identifies completed agent executions

**Example Usage**:

```python
from core.episode_segmentation_service import EpisodeSegmentationService
from core.database import get_db_session

with get_db_session() as db:
    service = EpisodeSegmentationService(db)
    episode = await service.create_episode_from_session(
        session_id="chat_123",
        agent_id="agent_456",
        title="HST Calculation for Woodstock Client"
    )
    print(f"Created episode: {episode.id}")
```

### 2. EpisodeRetrievalService

**Purpose**: Multi-mode episode retrieval with governance

**Location**: `backend/core/episode_retrieval_service.py`

**Four Retrieval Modes**:

#### Temporal Retrieval

```python
async def retrieve_temporal(
    agent_id: str,
    time_range: str = "7d",  # 1d, 7d, 30d, 90d
    user_id: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]
```

**Use Case**: "What has this agent done in the past week?"

**Performance**: ~10ms (indexed PostgreSQL query)

**Example**:

```python
result = await service.retrieve_temporal(
    agent_id="agent_456",
    time_range="7d"
)
for episode in result["episodes"]:
    print(f"{episode['title']}: {episode['started_at']}")
```

#### Semantic Retrieval

```python
async def retrieve_semantic(
    agent_id: str,
    query: str,
    limit: int = 10
) -> Dict[str, Any]
```

**Use Case**: "Find past episodes similar to this tax calculation task"

**Performance**: ~50-100ms (LanceDB vector search)

**Example**:

```python
result = await service.retrieve_semantic(
    agent_id="agent_456",
    query="HST calculation for machinery sales in Ontario"
)
for episode in result["episodes"]:
    print(f"{episode['title']} (score: {episode.get('score', 0)})")
```

#### Sequential Retrieval

```python
async def retrieve_sequential(
    episode_id: str,
    agent_id: str
) -> Dict[str, Any]
```

**Use Case**: "Show me the full episode with all segments"

**Performance**: ~20ms (PostgreSQL joins)

**Example**:

```python
result = await service.retrieve_sequential(
    episode_id="episode_123",
    agent_id="agent_456"
)
print(f"Episode: {result['episode']['title']}")
for segment in result['segments']:
    print(f"  [{segment['segment_type']}] {segment['content_summary']}")
```

#### Contextual Retrieval

```python
async def retrieve_contextual(
    agent_id: str,
    current_task: str,
    limit: int = 5
) -> Dict[str, Any]
```

**Use Case**: "Find episodes most relevant to the current task"

**Performance**: ~100ms (hybrid approach)

**Example**:

```python
result = await service.retrieve_contextual(
    agent_id="agent_456",
    current_task="Calculating HST for invoice #12345"
)
for episode in result["episodes"]:
    print(f"{episode['title']} (relevance: {episode.get('relevance_score', 0)})")
```

### 3. EpisodeLifecycleService

**Purpose**: Manages episode lifecycle (decay, consolidation, archival)

**Location**: `backend/core/episode_lifecycle_service.py`

**Key Methods**:

```python
# Apply decay to old episodes
async def decay_old_episodes(days_threshold: int = 90) -> Dict[str, int]

# Consolidate similar episodes
async def consolidate_similar_episodes(
    agent_id: str,
    similarity_threshold: float = 0.85
) -> Dict[str, int]

# Update importance based on user feedback
async def update_importance_scores(
    episode_id: str,
    user_feedback: float  # -1.0 to 1.0
) -> bool
```

**Example Usage**:

```python
# Trigger decay process
result = await service.decay_old_episodes(days_threshold=90)
print(f"Applied decay to {result['affected']} episodes")

# Update importance based on feedback
await service.update_importance_scores(
    episode_id="episode_123",
    user_feedback=0.8  # Positive feedback
)
```

### 4. AgentGraduationService

**Purpose**: Validates agent promotion readiness using episodic memory

**Location**: `backend/core/agent_graduation_service.py`

**Key Methods**:

```python
# Calculate readiness score
async def calculate_readiness_score(
    agent_id: str,
    target_maturity: str,  # INTERN, SUPERVISED, AUTONOMOUS
    min_episodes: int = None
) -> Dict[str, Any]

# Run graduation exam on edge cases
async def run_graduation_exam(
    agent_id: str,
    edge_case_episodes: List[str]
) -> Dict[str, Any]

# Promote agent after validation
async def promote_agent(
    agent_id: str,
    new_maturity: str,
    validated_by: str
) -> bool

# Get full audit trail
async def get_graduation_audit_trail(
    agent_id: str
) -> Dict[str, Any]
```

**Example Usage**:

```python
# Check if agent is ready for promotion
result = await service.calculate_readiness_score(
    agent_id="agent_456",
    target_maturity="INTERN"
)

if result["ready"]:
    print(f"Agent ready! Score: {result['score']}/100")
else:
    print(f"Agent not ready. Gaps: {result['gaps']}")
    print(f"Recommendation: {result['recommendation']}")
```

---

## API Endpoints

### Episode Management

#### Create Episode

```http
POST /api/episodes/create
Content-Type: application/json

{
  "session_id": "chat_123",
  "agent_id": "agent_456",
  "title": "HST Calculation Episode"
}
```

#### Temporal Retrieval

```http
POST /api/episodes/retrieve/temporal
Content-Type: application/json

{
  "agent_id": "agent_456",
  "time_range": "7d",
  "limit": 50
}
```

#### Semantic Retrieval

```http
POST /api/episodes/retrieve/semantic
Content-Type: application/json

{
  "agent_id": "agent_456",
  "query": "tax calculations for machinery",
  "limit": 10
}
```

#### Sequential Retrieval

```http
GET /api/episodes/retrieve/{episode_id}?agent_id=agent_456
```

#### Contextual Retrieval

```http
POST /api/episodes/retrieve/contextual
Content-Type: application/json

{
  "agent_id": "agent_456",
  "current_task": "Calculate HST for invoice #12345",
  "limit": 5
}
```

### Graduation Endpoints

#### Readiness Score

```http
GET /api/episodes/graduation/readiness/{agent_id}?target_maturity=INTERN
```

#### Run Graduation Exam

```http
POST /api/episodes/graduation/exam
Content-Type: application/json

{
  "agent_id": "agent_456",
  "edge_case_episodes": ["ep_1", "ep_2", "ep_3"]
}
```

#### Promote Agent

```http
POST /api/episodes/graduation/promote
Content-Type: application/json

{
  "agent_id": "agent_456",
  "new_maturity": "INTERN",
  "validated_by": "user_789"
}
```

#### Audit Trail

```http
GET /api/episodes/graduation/audit/{agent_id}
```

---

## Graduation Framework

### Graduation Criteria

| Target Level | Min Episodes | Max Intervention Rate | Min Constitutional Score |
|--------------|--------------|----------------------|--------------------------|
| STUDENT → INTERN | 10 | 50% | 0.70 |
| INTERN → SUPERVISED | 25 | 20% | 0.85 |
| SUPERVISED → AUTONOMOUS | 50 | 0% | 0.95 |

### Readiness Score Calculation

```
Score = (Episode Score × 40%) + (Intervention Score × 30%) + (Constitutional Score × 30%)

Where:
- Episode Score = min(episode_count / min_episodes, 1.0) × 40
- Intervention Score = (1 - intervention_rate / max_intervention) × 30
- Constitutional Score = (constitutional_score / min_constitutional) × 30
```

### Use Cases

#### Use Case 1: MedScribe (Clinical Documentation)

**Scenario**: Hospital board requires proof that agent can document clinical encounters with zero errors.

**Implementation**:
1. Create 100 episodes of clinical documentation
2. Track `human_intervention_count` for each episode
3. Validate against HIPAA rules (`constitutional_score`)
4. Generate audit trail showing 0 interventions, 1.0 constitutional score

```python
result = await service.get_graduation_audit_trail(agent_id="medscribe_agent")
# Returns:
# {
#   "total_episodes": 100,
#   "total_interventions": 0,
#   "avg_constitutional_score": 1.0,
#   "episodes_by_maturity": {"AUTONOMOUS": 100}
# }
```

#### Use Case 2: Brennan.ca (Sales Tax Compliance)

**Scenario**: Sales agent must understand Woodstock, Ontario pricing nuances before sending autonomous emails.

**Implementation**:
1. Create episodes for each tax jurisdiction training
2. Validate HST calculations for Woodstock
3. Track corrections in `human_edits` field
4. Only promote to AUTONOMOUS after 50 Woodstock-specific episodes with 0 interventions

```python
result = await service.calculate_readiness_score(
    agent_id="sales_bot",
    target_maturity="AUTONOMOUS"
)
# Verify Woodstock-specific episodes have 0 interventions
```

---

## Usage Examples

### Example 1: Auto-Create Episodes After Chat

```python
from core.episode_integration import trigger_episode_creation

# After agent completes chat session
trigger_episode_creation(
    session_id="chat_123",
    agent_id="agent_456",
    title="Tax Calculation Session"
)
```

### Example 2: Recall Episodes in Agent Execution

```python
from core.agent_world_model import WorldModelService

world_model = WorldModelService()
recall = await world_model.recall_experiences(
    agent=agent,
    current_task_description="Calculate HST for machinery sale",
    limit=5
)

# Episodes are now included in recall results
for episode in recall["episodes"]:
    print(f"Similar episode: {episode['title']}")
    print(f"  Interventions: {episode['human_intervention_count']}")
    print(f"  Constitutional score: {episode['constitutional_score']}")
```

### Example 3: Graduation Workflow

```python
from core.agent_graduation_service import AgentGraduationService

service = AgentGraduationService(db)

# 1. Check readiness
readiness = await service.calculate_readiness_score(
    agent_id="student_agent",
    target_maturity="INTERN"
)

if readiness["ready"]:
    # 2. Run edge case exams
    exam_result = await service.run_graduation_exam(
        agent_id="student_agent",
        edge_case_episodes=["edge_case_1", "edge_case_2"]
    )

    if exam_result["passed"]:
        # 3. Promote agent
        await service.promote_agent(
            agent_id="student_agent",
            new_maturity="INTERN",
            validated_by="admin_user"
        )
```

---

## Performance Characteristics

| Operation | Target | Actual | Notes |
|-----------|--------|--------|-------|
| Episode creation | <5s | ~1-2s | Includes segmentation + LanceDB archival |
| Temporal retrieval | <100ms | ~10ms | Indexed PostgreSQL query |
| Semantic retrieval | <100ms | ~50-100ms | LanceDB vector search |
| Sequential retrieval | <20ms | ~20ms | PostgreSQL joins |
| Contextual retrieval | <100ms | ~100ms | Hybrid approach |
| Decay processing | <60s | ~30s | Batch operation for 1000+ episodes |

---

## Governance Requirements

### Access Control by Maturity

| Operation | Complexity | Required Maturity |
|-----------|-----------|-------------------|
| View episodes | 1 (LOW) | STUDENT+ |
| Retrieve temporal | 1 (LOW) | STUDENT+ |
| Retrieve semantic | 2 (MODERATE) | INTERN+ |
| Retrieve contextual | 2 (MODERATE) | INTERN+ |
| Create episode | 2 (MODERATE) | INTERN+ |
| Update importance | 3 (HIGH) | SUPERVISED+ |
| **View graduation readiness** | 2 (MODERATE) | INTERN+ |
| **Run graduation exam** | 3 (HIGH) | SUPERVISED+ |
| **Promote agent** | 4 (CRITICAL) | AUTONOMOUS only |
| Consolidate episodes | 4 (CRITICAL) | AUTONOMOUS |
| Archive episodes | 4 (CRITICAL) | AUTONOMOUS |

### Audit Trail

All episode access is logged via `EpisodeAccessLog`:
- Accessor (user or agent)
- Access type (temporal, semantic, etc.)
- Governance check result
- Agent maturity at access time
- Results count and duration

---

## Running Database Migrations

```bash
# Create migration
alembic revision -m "add episodic memory tables"

# Apply migration
alembic upgrade head

# Verify migration
alembic current

# Rollback if needed
alembic downgrade -1
```

---

## Testing

```bash
# Run all episode tests
pytest tests/test_episode_*.py -v

# Run specific test file
pytest tests/test_episode_segmentation.py -v

# Run with coverage
pytest tests/test_episode_*.py --cov=core.episode_segmentation_service --cov-report=html
```
