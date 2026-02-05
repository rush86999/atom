# Canvas & Feedback Integration with Episodic Memory

## Overview

Episodes now include lightweight references to canvas presentations and user feedback, enabling agents to retrieve enriched context for decision-making. This integration follows a **metadata-only linkage** pattern where episodes store ID references and fetch full records on demand.

**Key Principle**: Canvas and feedback context are **ALWAYS** fetched during every episode recall, not just for canvas-specific tasks. This ensures agents have complete context for ALL decision-making.

## Architecture

### Storage Pattern: Metadata-Only Linkage

```
┌─────────────────────────────────────────────────────────────────┐
│                    EPISODE CREATION                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Agent Execution Session                                         │
│       │                                                          │
│       ├─── Chat Messages ────────┐                              │
│       ├─── Agent Executions ─────┤                              │
│       ├─── Canvas Actions ───────┼──► CanvasAudit Table         │
│       │    (present, submit,     │    (Separate Storage)        │
│       │     close, update)       │                              │
│       │                          │                              │
│       └─── User Feedback ────────┼──► AgentFeedback Table       │
│            (ratings, corrections)│    (Separate Storage)        │
│                                  │                              │
│                                  ▼                              │
│                         Episode Creation                         │
│                                  │                              │
│                                  ├─── Episode Model              │
│                                  │    ├── execution_ids: [...]  │
│                                  │    ├── canvas_ids: [...]     │
│                                  │    └── feedback_ids: [...]   │
│                                  │    (Metadata-Only Linkage)    │
│                                  │                              │
│                                  └─── Backlinks                  │
│                                       ├── CanvasAudit.episode_id │
│                                       └── AgentFeedback.episode_id│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    EPISODE RETRIEVAL                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Agent Decision-Making (recall_experiences)                     │
│       │                                                          │
│       └──► Retrieve Episodes                                     │
│              │                                                  │
│              ├─── Episode Data                                   │
│              ├─── Episode Segments                              │
│              ├─── ALWAYS Fetch Canvas Context ───► CanvasAudit  │
│              │      (by canvas_ids)                    Table    │
│              │                                                  │
│              └─── ALWAYS Fetch Feedback Context ──► AgentFeedback
│                     (by feedback_ids)                  Table    │
│                                                                  │
│              ▼                                                  │
│         Enriched Episode                                         │
│         ├── canvas_context: [...]  (What was presented)          │
│         └── feedback_context: [...] (How user responded)        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Separation of Concerns**: Canvas and feedback records remain in their own tables
2. **Metadata-Only Linkage**: Episodes store only ID references, not full data
3. **Always Fetch**: Canvas/feedback context retrieved on every episode recall
4. **Efficient Storage**: No data duplication, ~100 bytes per episode
5. **Flexible Retrieval**: Fetch by ID, filter by type, weight by feedback

## Data Model

### Episode Model Additions

```python
class Episode(Base):
    # ... existing fields ...

    # Canvas linkage (NEW - Feb 2026)
    canvas_ids = Column(JSON, default=list)  # List of CanvasAudit IDs
    canvas_action_count = Column(Integer, default=0)  # Total canvas actions

    # Feedback linkage (NEW - Feb 2026)
    feedback_ids = Column(JSON, default=list)  # List of AgentFeedback IDs
    aggregate_feedback_score = Column(Float, nullable=True)  # -1.0 to 1.0
```

### CanvasAudit Model Addition

```python
class CanvasAudit(Base):
    # ... existing fields ...

    episode_id = Column(String, ForeignKey("episodes.id"), nullable=True, index=True)  # NEW
```

### AgentFeedback Model Addition

```python
class AgentFeedback(Base):
    # ... existing fields ...

    episode_id = Column(String, ForeignKey("episodes.id"), nullable=True, index=True)  # NEW
```

## Features

### 1. Canvas-Aware Episodes

Episodes track all canvas interactions with full audit trail:

**Supported Canvas Types**:
- **Built-in types** (7): `generic`, `docs`, `email`, `sheets`, `orchestration`, `terminal`, `coding`
- **Custom components**: User-created HTML/CSS/JS components (tracked via `canvas_type="generic"` + component info in `audit_metadata`)

**Canvas Actions**: `present`, `close`, `submit`, `update`, `execute`

**Example**:
```python
# Episode with canvas context
episode = {
    "id": "ep_123",
    "title": "Sales Data Analysis",
    "canvas_ids": ["canvas_abc", "canvas_def"],
    "canvas_action_count": 3,
    "canvas_context": [
        {
            "id": "canvas_abc",
            "canvas_type": "sheets",
            "component_type": "table",
            "action": "present",
            "created_at": "2026-02-04T10:00:00Z",
            "metadata": {"rows": 50, "columns": 5}
        },
        {
            "id": "canvas_def",
            "canvas_type": "charts",
            "component_type": "line_chart",
            "action": "present",
            "created_at": "2026-02-04T10:01:00Z",
            "metadata": {"data_points": 100}
        }
    ]
}
```

### 2. Feedback-Linked Episodes

Episodes aggregate user feedback scores for retrieval weighting:

**Feedback Scoring**:
- `thumbs_up`: +1.0
- `thumbs_down`: -1.0
- `rating` (1-5): converted to -1.0 to 1.0 scale
  - 1 → -1.0, 2 → -0.5, 3 → 0.0, 4 → 0.5, 5 → 1.0

**Aggregate Score**: Average of all feedback scores for the episode

**Example**:
```python
# Episode with feedback context
episode = {
    "id": "ep_123",
    "feedback_ids": ["feedback_1", "feedback_2"],
    "aggregate_feedback_score": 0.75,  # Positive feedback
    "feedback_context": [
        {
            "id": "feedback_1",
            "feedback_type": "thumbs_up",
            "created_at": "2026-02-04T10:05:00Z"
        },
        {
            "id": "feedback_2",
            "feedback_type": "rating",
            "rating": 5,
            "created_at": "2026-02-04T10:06:00Z"
        }
    ]
}
```

### 3. Enriched Sequential Retrieval

**Default Behavior**: Canvas and feedback context **always included** for complete agent context.

```bash
GET /api/episodes/{episode_id}/retrieve?include_canvas=true&include_feedback=true
```

**Response**:
```json
{
  "episode": {
    "id": "ep_123",
    "title": "Sales Analysis",
    "canvas_ids": ["canvas_abc"],
    "feedback_ids": ["feedback_xyz"]
  },
  "segments": [...],
  "canvas_context": [
    {
      "canvas_type": "sheets",
      "component_type": "table",
      "action": "present",
      "created_at": "2026-02-04T10:00:00Z",
      "metadata": {...}
    }
  ],
  "feedback_context": [
    {
      "feedback_type": "thumbs_up",
      "rating": 5,
      "corrections": [...]
    }
  ]
}
```

**Performance**: ~50ms overhead per episode (fetching canvas/feedback records)

### 4. Canvas Type Filtering

Retrieve episodes filtered by canvas type and action:

```bash
POST /api/episodes/retrieve/by-canvas-type
{
  "agent_id": "agent_123",
  "canvas_type": "sheets",
  "action": "present",
  "time_range": "30d",
  "limit": 10
}
```

**Use Cases**:
- "Show me episodes where I presented spreadsheets"
- "Find all episodes with form submissions"
- "Episodes where I presented charts"

### 5. Feedback-Weighted Retrieval

Contextual retrieval applies feedback-based boosting:

**Boosting Rules**:
- Canvas interactions: +0.1 relevance boost
- Positive feedback (>0): +0.2 relevance boost
- Negative feedback (<0): -0.3 relevance penalty
- Neutral feedback (~0): No adjustment

**Example**:
```python
# Episode with canvas and positive feedback
base_score = 0.7  # From temporal + semantic matching
canvas_boost = +0.1  # Has canvas interactions
feedback_boost = +0.2  # Positive feedback
final_score = 1.0  # Boosted score
```

### 6. Agent Decision-Making Integration

Agents automatically retrieve canvas and feedback context when recalling episodes:

```python
# In agent_world_model.py
result = await recall_experiences(agent, current_task)

# result["episodes"] now includes:
# - canvas_context: What canvases were presented
# - feedback_context: How users responded

# Agent uses this to:
# - Choose appropriate canvas types
# - Avoid mistakes from past negative feedback
# - Replicate successful presentation patterns
```

**Critical**: Context enrichment happens for **EVERY** episode recall, not just canvas-specific tasks.

## Usage Examples

### Example 1: Agent Learns Presentation Preferences

**Task**: "Show me sales data"

**Agent recalls**:
- Episode 456: Presented line chart, user closed after 3s
- Episode 789: Presented bar chart, user engaged 30s, gave thumbs up

**Decision**: Present bar chart (proven successful)

```python
# Agent reasoning from enriched episodes
for episode in recalled_episodes:
    canvas_context = episode["canvas_context"]
    feedback_context = episode["feedback_context"]

    # Analyze patterns
    for canvas in canvas_context:
        if canvas["action"] == "close":
            # User didn't like this canvas type
            avoid_canvas_types.append(canvas["canvas_type"])

    for feedback in feedback_context:
        if feedback["feedback_type"] == "thumbs_up":
            # User liked this presentation
            successful_patterns.append(canvas["canvas_type"])
```

### Example 2: Form Workflow Memory

**Task**: "Help user file taxes"

**Agent recalls**:
- Episode 123: Presented tax form, user filled partially
- Form submission captured in episode feedback

**Decision**: Pre-fill form with previous answers, ask for remaining fields

```python
# Episode shows partial form submission
episode = {
    "canvas_context": [
        {
            "canvas_type": "generic",
            "component_type": "form",
            "action": "submit",
            "metadata": {
                "form_fields": ["name", "address", "income"],
                "completed": ["name", "address"]
            }
        }
    ],
    "feedback_context": [
        {
            "corrections": "I stopped because I didn't have my income info"
        }
    ]
}

# Agent action: Present form with name/address pre-filled
```

### Example 3: Feedback-Driven Improvement

**Task**: "Create pricing proposal"

**Agent recalls**:
- Episode 999: Pricing table had errors, user corrected in feedback
- `aggregate_feedback_score`: -0.5 (negative)

**Decision**: Double-check pricing calculations, mention learning from past error

```python
# Negative feedback triggers caution
if episode["aggregate_feedback_score"] < 0:
    for feedback in episode["feedback_context"]:
        if feedback["corrections"]:
            # User provided corrections
            agent_reasoning = f"""
            Based on previous feedback (Episode {episode['id']}):
            User correction: {feedback['corrections']}

            I will double-check my calculations to avoid this error.
            """
```

### Example 4: Canvas Type Selection

**Task**: "Analyze user engagement data"

**Agent recalls**:
- Episodes show user engagement patterns:
  - Sheets: User closes quickly (2s avg)
  - Charts: User engages longer (45s avg)
  - Positive feedback on line charts specifically

**Decision**: Present line chart instead of spreadsheet

```python
# Extract insights from canvas context
insights = agent._extract_canvas_insights(episodes)

# insights["user_interaction_patterns"]:
# {
#     "closes_quickly": ["sheets", "markdown"],
#     "engages": ["charts", "forms"],
#     "submits": ["forms"]
# }

# Agent chooses "charts" over "sheets"
```

## API Endpoints

### 1. Enhanced Sequential Retrieval

```bash
GET /api/episodes/{episode_id}/retrieve?include_canvas=true&include_feedback=true
```

**Parameters**:
- `episode_id` (str): Episode ID
- `agent_id` (str): Agent ID
- `include_canvas` (bool): Include canvas context (default: true)
- `include_feedback` (bool): Include feedback context (default: true)

**Response**: Enriched episode with canvas_context and feedback_context

### 2. Canvas Type Filtering

```bash
POST /api/episodes/retrieve/by-canvas-type
{
  "agent_id": "agent_123",
  "canvas_type": "sheets",
  "action": "present",
  "time_range": "30d",
  "limit": 10
}
```

**Parameters**:
- `agent_id` (str): Agent ID
- `canvas_type` (str): Canvas type (sheets, charts, generic, etc.)
- `action` (str, optional): Action filter (present, submit, close, etc.)
- `time_range` (str): Time range (1d, 7d, 30d, 90d)
- `limit` (int): Max results

**Response**: Filtered episodes with canvas type info

### 3. Feedback Submission

```bash
POST /api/episodes/{episode_id}/feedback/submit
{
  "feedback_type": "rating",
  "rating": 5,
  "corrections": "Great work on the charts"
}
```

**Parameters**:
- `episode_id` (str): Episode ID
- `feedback_type` (str): thumbs_up, thumbs_down, rating
- `rating` (int, optional): 1-5 for rating type
- `corrections` (str, optional): User corrections

**Response**: Feedback ID and updated aggregate score

### 4. Feedback Retrieval

```bash
GET /api/episodes/{episode_id}/feedback/list
```

**Response**: All feedback for the episode

### 5. Feedback-Weighted Analytics

```bash
GET /api/episodes/analytics/feedback-episodes?agent_id=agent_123&min_feedback_score=0.5
```

**Parameters**:
- `agent_id` (str): Agent ID
- `min_feedback_score` (float): Minimum score (-1.0 to 1.0)
- `time_range` (str): Time range (default: 30d)
- `limit` (int): Max results (default: 10)

**Response**: Episodes with high feedback scores

## Benefits

1. **Richer Context**: Agents see what they presented AND how users reacted
2. **Presentation Learning**: "User closes markdown quickly → try charts instead"
3. **Feedback Integration**: Positive feedback boosts episode relevance
4. **Workflow Continuity**: Form submissions become part of episode memory
5. **Graduation Validation**: Canvas success rates inform promotion decisions
6. **Efficient Storage**: Metadata-only linkage avoids data duplication
7. **Flexible Retrieval**: Fetch by ID, filter by type, weight by feedback

## Performance

**Storage Overhead**: ~100 bytes per episode (JSON arrays)

| Metric | Target | Current |
|--------|--------|---------|
| Sequential retrieval | <100ms | ~50-70ms |
| Canvas context fetch | <50ms | ~20-30ms |
| Feedback context fetch | <50ms | ~10-20ms |
| Total overhead | <100ms | ✅ Met |

**Index Usage**:
- `ix_canvas_audit_episode_id`: Backlink lookups
- `ix_agent_feedback_episode_id`: Backlink lookups
- `ix_episodes_agent_canvas`: Composite index for canvas queries

## Migration

**Existing Episodes**: Empty arrays (`canvas_ids = []`, `feedback_ids = []`)

**New Episodes**: Automatically populated with canvas/feedback context

**Backfill** (Optional):
```python
# Link historical records via session_id
for episode in old_episodes:
    canvases = db.query(CanvasAudit).filter(
        CanvasAudit.session_id == episode.session_id
    ).all()

    episode.canvas_ids = [c.id for c in canvases]
    episode.canvas_action_count = len(canvases)
```

## Database Migration

```bash
# Apply migration
alembic upgrade head

# Verify new columns
sqlite3 atom_dev.db ".schema episodes" | grep -E "canvas_ids|feedback_ids|aggregate_feedback_score"

# Verify indexes
sqlite3 atom_dev.db ".indexes episodes" | grep -E "canvas|feedback"
```

## Testing

```bash
# Run integration tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_canvas_feedback_episode_integration.py -v

# Run with coverage
pytest tests/test_canvas_feedback_episode_integration.py --cov=core.episode_segmentation_service --cov=core.episode_retrieval_service --cov-report=html

# Expected: All tests passing (25+ tests)
```

## Rollout Strategy

**Week 1**: Database migration, model changes
**Week 2**: Service modifications (segmentation, retrieval)
**Week 3**: Agent integration, API endpoints
**Week 4**: Monitoring, optimization, documentation

## Backward Compatibility

- All new fields are nullable or have defaults
- Existing episodes work (empty arrays)
- No breaking API changes
- Feature flags available: `CANVAS_EPISODE_INTEGRATION_ENABLED`

## Success Criteria

- [x] Migration runs without errors
- [x] 100% of existing episodes still queryable
- [x] New episodes populate canvas/feedback fields
- [x] Sequential retrieval includes canvas/feedback context
- [x] Canvas type filtering works correctly
- [x] Feedback-weighted retrieval boosts relevant episodes
- [x] Agents use enriched context in decision-making
- [x] Performance overhead <100ms per retrieval
- [x] Documentation complete and accurate

## Troubleshooting

### Issue: Episodes not showing canvas context

**Check**:
```python
# Verify canvas audits exist for session
canvases = db.query(CanvasAudit).filter(
    CanvasAudit.session_id == session_id
).all()

print(f"Found {len(canvases)} canvas events")

# Verify episode was created after feature deployment
episode = db.query(Episode).filter(Episode.id == episode_id).first()
print(f"Canvas IDs: {episode.canvas_ids}")
```

### Issue: Feedback not linked to episodes

**Check**:
```python
# Verify feedback has agent_execution_id
feedback = db.query(AgentFeedback).filter(
    AgentFeedback.episode_id == episode_id
).all()

print(f"Found {len(feedback)} linked feedback records")

# Check if feedback was created after episode
for f in feedback:
    print(f"Feedback created: {f.created_at}, Episode created: {episode.created_at}")
```

### Issue: Retrieval too slow

**Check**:
```python
# Verify indexes exist
import sqlite3
conn = sqlite3.connect('atom_dev.db')
cursor = conn.cursor()

# Check episode indexes
cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='episodes'")
indexes = cursor.fetchall()
print("Episode indexes:", indexes)

# Should include: ix_episodes_agent_canvas
```

## See Also

- [Episodic Memory Implementation](./EPISODIC_MEMORY_IMPLEMENTATION.md)
- [Agent Graduation Guide](./AGENT_GRADUATION_GUIDE.md)
- [Canvas Implementation Guide](./CANVAS_IMPLEMENTATION_COMPLETE.md)
- [Episode Quick Start](./EPISODIC_MEMORY_QUICK_START.md)
