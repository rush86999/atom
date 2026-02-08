# Episodic Memory Implementation Guide

**Last Updated**: February 4, 2026

## Overview

The Episodic Memory system enables AI agents to learn from past experiences by storing, retrieving, and analyzing interaction episodes. This system is tightly integrated with the Agent Graduation Framework to validate agent promotion readiness.

### Core Concepts

**Episode**: A coherent sequence of agent interactions representing a single task or conversation session.

**EpisodeSegment**: Atomic units within an episode (individual messages, actions, or decisions).

**Graduation**: The process of promoting agents through maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) based on episodic learning.

---

## Architecture

### Hybrid Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hot Storage (PostgreSQL)                  │
│  - Recent episodes (< 90 days)                              │
│  - Fast queries (~10ms)                                      │
│  - Episode, EpisodeSegment, EpisodeAccessLog models         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Cold Storage (LanceDB)                       │
│  - Archived episodes (> 90 days)                            │
│  - Semantic vector search                                    │
│  - Embeddings for similarity matching                        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Agent Interaction → Episode Segmentation → Storage → Retrieval → Learning
                      │                            │            │
                 Boundary Detection          PostgreSQL    Graduation
                 (Time/Topic/Task)           + LanceDB      Validation
```

---

## Core Components

### 1. Episode Segmentation Service

**File**: `core/episode_segmentation_service.py`

**Purpose**: Automatically segments agent interactions into coherent episodes.

#### Boundary Detection Methods

1. **Time Gap Detection**
   - Default threshold: 30 minutes
   - Detects pauses in interaction
   - Configurable via `TIME_GAP_THRESHOLD_MINUTES`

2. **Topic Change Detection**
   - Semantic similarity threshold: 0.75
   - Uses cosine similarity on message embeddings
   - Configurable via `SEMANTIC_SIMILARITY_THRESHOLD`

3. **Task Completion Detection**
   - Identifies completed agent executions
   - Marks successful task conclusions
   - Results in episode finalization

#### Key Classes

```python
class EpisodeBoundaryDetector:
    def detect_time_gap(messages: List[ChatMessage]) -> List[int]
    def detect_topic_changes(messages: List[ChatMessage]) -> List[int]
    def detect_task_completion(executions: List[AgentExecution]) -> List[int]

class EpisodeSegmentationService:
    async def create_episode(agent_id: str, context: Dict) -> Episode
    async def add_segment(episode_id: str, content: str, metadata: Dict) -> EpisodeSegment
    async def finalize_episode(episode_id: str) -> Episode
```

#### Usage Example

```python
from core.episode_segmentation_service import EpisodeSegmentationService

service = EpisodeSegmentationService(db)

# Create new episode
episode = await service.create_episode(
    agent_id="agent_123",
    context={"task": "customer_support", "user_id": "user_456"}
)

# Add segments during interaction
await service.add_segment(
    episode_id=episode.id,
    content="User asked about refund policy",
    metadata={"type": "user_query"}
)

# Finalize when task is complete
await service.finalize_episode(episode.id)
```

---

### 2. Episode Retrieval Service

**File**: `core/episode_retrieval_service.py`

**Purpose**: Provides four retrieval modes with governance integration.

#### Retrieval Modes

1. **Temporal Retrieval** (`retrieve_temporal`)
   - Time-based queries: 1d, 7d, 30d, 90d
   - Performance: ~10ms
   - Governance: Level 1 (STUDENT+)

2. **Semantic Retrieval** (`retrieve_semantic`)
   - Vector similarity search
   - Performance: ~50-100ms
   - Uses LanceDB embeddings
   - Governance: Level 1 (STUDENT+)

3. **Sequential Retrieval** (`retrieve_sequential`)
   - Full episode with all segments
   - Ordered chronologically
   - Performance: ~20ms
   - Governance: Level 1 (STUDENT+)

4. **Contextual Retrieval** (`retrieve_contextual`)
   - Hybrid scoring for current task
   - Combines temporal + semantic + sequential
   - Optimized for decision-making
   - Governance: Level 2 (INTERN+)

#### Key Methods

```python
class EpisodeRetrievalService:
    async def retrieve_temporal(
        agent_id: str,
        time_range: str = "7d",
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]

    async def retrieve_semantic(
        agent_id: str,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]

    async def retrieve_sequential(
        episode_id: str
    ) -> Dict[str, Any]

    async def retrieve_contextual(
        agent_id: str,
        current_context: Dict[str, Any],
        limit: int = 5
    ) -> Dict[str, Any]
```

#### Usage Example

```python
from core.episode_retrieval_service import EpisodeRetrievalService

service = EpisodeRetrievalService(db)

# Temporal: Get last 7 days of episodes
result = await service.retrieve_temporal(
    agent_id="agent_123",
    time_range="7d"
)
print(f"Found {result['count']} episodes")

# Semantic: Find similar episodes
result = await service.retrieve_semantic(
    agent_id="agent_123",
    query="customer refund request"
)

# Contextual: Get relevant episodes for current task
result = await service.retrieve_contextual(
    agent_id="agent_123",
    current_context={"task": "customer_support", "topic": "refund"}
)
```

---

### 3. Episode Lifecycle Service

**File**: `core/episode_lifecycle_service.py`

**Purpose**: Manages episode lifecycle including decay, consolidation, and archival.

#### Lifecycle Stages

1. **Active** (< 90 days)
   - Full accessibility
   - No decay applied

2. **Decaying** (90-180 days)
   - Decay score: 0.0 → 1.0
   - Formula: `decay = max(0, 1 - (days_old / 180))`
   - Still retrievable but lower priority

3. **Archived** (> 180 days)
   - Moved to LanceDB cold storage
   - Accessible via semantic search only
   - Cost-effective long-term storage

#### Key Methods

```python
class EpisodeLifecycleService:
    async def decay_old_episodes(days_threshold: int = 90) -> Dict[str, int]
    async def consolidate_similar_episodes(
        agent_id: str,
        similarity_threshold: float = 0.85
    ) -> Dict[str, int]
    async def archive_episode(episode_id: str) -> bool
    async def update_importance_score(episode_id: str, score: float) -> bool
```

#### Consolidation Algorithm

```python
# 1. Find semantically similar episodes using LanceDB
similar_episodes = lancedb.search(
    query=episode_embedding,
    threshold=similarity_threshold
)

# 2. Create parent episode
parent_episode = Episode(
    type="consolidated",
    metadata={"child_episodes": [e1.id, e2.id, ...]}
)

# 3. Link child episodes to parent
for episode in similar_episodes:
    episode.consolidated_into = parent_episode.id
```

---

### 4. Agent Graduation Service

**File**: `core/agent_graduation_service.py`

**Purpose**: Validate agent promotion readiness using episodic memory metrics.

#### Graduation Criteria by Level

| Level | Episode Count | Intervention Rate | Constitutional Score | Readiness |
|-------|--------------|-------------------|---------------------|-----------|
| STUDENT → INTERN | ≥ 10 | ≤ 50% | ≥ 0.70 | 100% required |
| INTERN → SUPERVISED | ≥ 25 | ≤ 20% | ≥ 0.85 | 100% required |
| SUPERVISED → AUTONOMOUS | ≥ 50 | 0% | ≥ 0.95 | 100% required |

#### Readiness Score Calculation

```
readiness_score = (
    (episode_score * 0.40) +
    (intervention_score * 0.30) +
    (constitutional_score * 0.30)
)

where:
  - episode_score = min(1.0, actual_episodes / required_episodes)
  - intervention_score = 1.0 - (intervention_rate / threshold)
  - constitutional_score = compliance_validation_score
```

#### Key Methods

```python
class AgentGraduationService:
    async def calculate_readiness(
        agent_id: str,
        target_level: AgentMaturityLevel
    ) -> Dict[str, Any]

    async def run_graduation_exam(
        agent_id: str,
        exam_config: Optional[Dict] = None
    ) -> Dict[str, Any]

    async def validate_constitutional_compliance(
        agent_id: str,
        episode_window: int = 100
    ) -> Dict[str, Any]

    async def promote_agent(
        agent_id: str,
        target_level: AgentMaturityLevel
    ) -> Dict[str, Any]
```

---

## API Endpoints

### Episode Management

#### Create Episode
```http
POST /api/episodes/create
Content-Type: application/json

{
  "agent_id": "agent_123",
  "user_id": "user_456",
  "context": {
    "task": "customer_support",
    "channel": "slack"
  }
}
```

#### Retrieve Episodes

**Temporal**: `POST /api/episodes/retrieve/temporal`
**Semantic**: `POST /api/episodes/retrieve/semantic`
**Sequential**: `GET /api/episodes/retrieve/{episode_id}`
**Contextual**: `POST /api/episodes/retrieve/contextual`

### Graduation Endpoints

**Check Readiness**: `GET /api/episodes/graduation/readiness/{agent_id}`
**Run Exam**: `POST /api/episodes/graduation/exam`
**Promote Agent**: `POST /api/episodes/graduation/promote`
**Audit Trail**: `GET /api/episodes/graduation/audit/{agent_id}`

### Lifecycle Endpoints

**Decay**: `POST /api/episodes/lifecycle/decay`
**Consolidate**: `POST /api/episodes/lifecycle/consolidate`
**Statistics**: `GET /api/episodes/stats/{agent_id}`

---

## Performance Characteristics

| Operation | Performance | Notes |
|-----------|-------------|-------|
| Episode Creation | < 5s | Includes segmentation and embedding |
| Temporal Retrieval | ~10ms | PostgreSQL indexed query |
| Semantic Retrieval | ~50-100ms | LanceDB vector search |
| Sequential Retrieval | ~20ms | Full episode with segments |
| Contextual Retrieval | ~100-200ms | Hybrid scoring algorithm |

---

## Security and Authentication

### Document Data Protection (February 4, 2026)

**CRITICAL**: All document ingestion and memory endpoints now require user authentication to protect episodic learning data.

**Protected Endpoints:**
- `/api/document-ingestion/settings` - Get/update ingestion settings
- `/api/document-ingestion/sync/{integration_id}` - Trigger document sync
- `/api/document-ingestion/memory/{integration_id}` - Remove integration memory
- `/api/documents/ingest` - Ingest document
- `/api/documents/upload` - Upload document

**Impact on Episodic Memory:**
1. **Protected Learning Data**: Document ingestion sources (agents, workflows) now require authentication
2. **Memory Removal Protected**: Deleting integration memories requires user verification
3. **Settings Guarded**: Ingestion settings cannot be modified without authentication

**Implementation**: See `backend/docs/API_STANDARDS.md` → "User Authentication" section

### Error Handling and Debugging

**Enhanced Exception Context (February 4, 2026)**:

Exception classes now carry debugging context for episodic memory operations:
- `DeepLinkParseException` - Includes URL and details for episodic recall errors
- `DeepLinkSecurityException` - Includes security_issue for validation failures
- `ComponentSecurityError` - Includes component_name and validation_reason

**Logging Improvements**:
- Cost estimation failures logged (LLM operations for embeddings)
- WebSocket close failures logged (real-time episode updates)
- Browser selector timeouts logged (agent interaction tracking)

These improvements make it easier to diagnose issues in:
- Episode segmentation failures
- Memory retrieval errors
- Graduation validation problems

See `backend/docs/IMPLEMENTATION_FIXES.md` → Phase 7 for details.

---

## Testing

```bash
# All episodic memory tests
pytest tests/test_episode*.py -v

# Specific test suite
pytest tests/test_episode_segmentation.py -v
pytest tests/test_agent_graduation.py -v

# With coverage
pytest tests/test_episode*.py --cov=core.episode_segmentation_service
```

---

**Authors**: Atom Development Team
**Version**: 1.0.0
**Status**: Production Ready ✅
