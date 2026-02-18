# Phase 20 Research: Canvas AI Context & Episodic Memory Integration

**Phase**: 20-canvas-ai-context
**Date**: February 18, 2026
**Status**: Research Complete

---

## Executive Summary

Phase 20 addresses two critical gaps in the Atom platform:

1. **Canvas AI Accessibility**: Canvas terminals/components create blind spots for AI agents who can't "read" canvas content (only see `<canvas id="term"></canvas>` with empty content)
2. **Canvas Context for Episodic Memory**: Episodes lack semantic understanding of what was presented on canvases, limiting retrieval quality

**Opportunity**: Dual implementation - make canvas components AI-readable AND enrich episodic memory with canvas context summaries for semantic search.

---

## Problem 1: Canvas AI Accessibility

### Current State: The "Black Box" Problem

**Issue**: When AI agents visit canvas components, they see:

```html
<canvas id="term" width="800" height="600"></canvas>
<!-- Empty! No content visible to visiting agents -->
```

**Why it matters**:
- AI agents can't read terminal output (lines of text)
- AI agents can't see form data (user inputs, validation errors)
- AI agents can't understand chart content (data points, trends)
- OCR is unreliable (pixel-based, slow, error-prone)

### Root Cause

Canvas rendering uses **immediate mode graphics**:
- JavaScript draws pixels directly to canvas
- No DOM structure for screen readers or AI agents
- Content exists only as pixels (visual representation)

### Proposed Solution: Dual Representation Pattern

**Pattern**: Expose both visual (pixels) and logical (state) representations

```html
<!-- Visual representation (pixels) -->
<canvas id="term" width="800" height="600"></canvas>

<!-- Logical representation (AI-readable) -->
<div id="term-state" role="log" aria-live="polite" style="display:none">
  {
    "lines": ["$ npm install", "Installing dependencies...", "Done!"],
    "cursorPos": {"row": 3, "col": 0},
    "scrollOffset": 0
  }
</div>
```

**Benefits**:
- AI agents can read state without OCR (instant, accurate)
- Screen readers can announce canvas changes (accessibility)
- No visual changes (hidden divs don't affect UI)
- Minimal performance overhead (JSON serialization)

### Implementation Scope

**Canvas Types** (7 built-in):
1. **Generic**: Basic canvas with custom content
2. **Docs**: Markdown documents
3. **Email**: Email composer/viewer
4. **Sheets**: Spreadsheets with data tables
5. **Orchestration**: Workflow orchestration canvas
6. **Terminal**: Terminal/console output
7. **Coding**: Code editor canvas

**State to Expose**:
- **Terminal**: `lines[]`, `cursorPos`, `scrollOffset`
- **Charts**: `data_points`, `chart_type`, `axes_labels`
- **Forms**: `form_schema`, `user_inputs`, `validation_errors`
- **Tables**: `rows[]`, `columns[]`, `sort_state`, `filters`

---

## Problem 2: Canvas Context for Episodic Memory

### Current State: Limited Episode Retrieval

**EpisodeSegment** currently links to CanvasAudit:

```python
EpisodeSegment {
    canvas_audit_id: 123  # Links to audit record
    action: "submit"       # What happened
    timestamp: "2026-02-17T22:30:00Z"
}
```

**Retrieval queries work for basic events**:
- "Find episodes where I submitted a form" ✅ (action="submit")
- "Show me episodes with canvases from yesterday" ✅ (timestamp filter)

**But fail for semantic queries**:
- "Find episodes where I approved workflows over $1M" ❌ (no business context)
- "Show me times the agent presented revenue charts" ❌ (no content type)
- "When did I last click 'Reject' on a pricing change?" ❌ (no user intent)

### Root Cause

Episodes track **WHAT happened** (audit events) but not **WHAT IT MEANT** (semantic content).

**CanvasAudit** (existing):
- Tracks canvas lifecycle events (create, present, submit, close)
- Compliance and governance requirements
- Audit trail for security reviews

**Missing**: Semantic understanding of canvas content.

### Proposed Solution: Canvas Context Enrichment

**Pattern**: Enrich EpisodeSegment with `canvas_context` field

```python
EpisodeSegment {
    canvas_audit_id: 123
    action: "submit"

    # NEW: Canvas context for semantic understanding
    canvas_context: {
        "canvas_type": "orchestration",
        "presentation_summary": "Agent presented workflow approval form with 3 charts",
        "visual_elements": ["approval_form", "line_chart", "data_table"],
        "user_interaction": "User clicked 'Approve Workflow' button",
        "critical_data_points": {
            "workflow_id": "wf-123",
            "approval_status": "approved",
            "revenue": "$1.2M",
            "timestamp": "2026-02-17T22:30:00Z"
        }
    }
}
```

**Benefits**:
1. **Semantic Search**: Query by business context, not just action types
2. **User Intent**: Track what users actually did (clicked "Approve" vs "Reject")
3. **Business Logic**: Capture critical data (workflow IDs, amounts, status)
4. **Content Awareness**: Know what was presented (charts, forms, tables)

### Canvas Context Schema

```python
canvas_context: {
    # Canvas identification
    "canvas_type": str,  # "generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"

    # Presentation summary (LLM-generated)
    "presentation_summary": str,  # "Agent presented 3 charts: user growth, revenue, engagement"

    # Visual elements presented
    "visual_elements": List[str],  # ["line_chart", "data_table", "approval_form"]

    # User interaction (what they actually did)
    "user_interaction": str,  # "User clicked 'Approve Workflow' button"

    # Critical data points (business logic)
    "critical_data_points": {
        # Workflow-specific
        "workflow_id": str,
        "approval_status": str,  # "approved", "rejected", "pending"

        # Business data
        "revenue": str,  # "$1.2M"
        "amount": float,
        "priority": int,

        # Timestamps
        "created_at": str,
        "updated_at": str
    }
}
```

### Canvas-Aware Episode Retrieval

**Two Access Patterns**:

#### Pattern 1: Historical Episodes (DB-stored canvas_context)

**Default: Agent gets summary automatically**

```python
# Agent retrieves episodes - gets summary by default (~50 tokens)
episodes = retrieval_service.retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval over $1M"
)

# Returns with summary level included automatically:
Episode {
    episode_id: "ep-456",
    segments: [
        EpisodeSegment {
            canvas_context: {
                "presentation_summary": "Agent presented approval form with revenue chart"
                # Summary only (~50 tokens) - included by default
            }
        }
    ]
}
```

**Agent decides to get more detail if needed**

```python
# Agent reviews summary and decides: "I need more context on the revenue amounts"
episodes_detailed = retrieval_service.retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval over $1M",
    canvas_context_detail="standard"  # Agent requests more
)

# Returns with standard level (~200 tokens):
Episode {
    episode_id: "ep-456",
    segments: [
        EpisodeSegment {
            canvas_context: {
                "presentation_summary": "Agent presented approval form with revenue chart",
                "critical_data_points": {
                    "workflow_id": "wf-123",
                    "approval_status": "approved",
                    "revenue": "$1.2M"  # Agent needed this detail
                }
            }
        }
    ]
}
```

#### Pattern 2: Real-time Canvas Access (live DOM state)

Agent reads current canvas state during task execution:

```python
# Agent decision: "I need to see the current workflow form state"
canvas_state = canvas_service.get_canvas_state(canvas_id="canvas-123")

# Returns from hidden accessibility tree (real-time):
{
    "canvas_type": "orchestration",
    "timestamp": "2026-02-18T10:30:00Z",

    # Terminal state (if terminal canvas)
    "terminal": {
        "lines": ["$ approve workflow wf-123", "Confirming..."],
        "cursorPos": {"row": 2, "col": 15},
        "scrollOffset": 0
    },

    # Form state (if form canvas)
    "form": {
        "formData": {
            "workflow_id": "wf-123",
            "approval_status": "pending",
            "revenue": 1500000
        },
        "validationErrors": [],
        "submitEnabled": true
    },

    # Chart state (if chart canvas)
    "chart": {
        "chartType": "line",
        "dataPoints": [...],
        "axesLabels": {"x": "Date", "y": "Revenue"}
    }
}
```

**Agent Decision Workflow**:

```
1. Agent receives task: "Approve $1.5M workflow wf-456"

2. Agent queries episodic memory:
   "What did I do last time I approved a $1M+ workflow?"

3. Agent receives episodes with SUMMARY level (automatic, ~50 tokens):
   - "Presented approval form with revenue chart"
   - "User approved workflow via form submission"

4. Agent reviews summaries and decides:
   "I need to see the actual revenue amounts to make informed decision"

5. Agent requests more detail:
   retrieve_episodes(episode_ids=["ep-123", "ep-456"], canvas_context_detail="standard")

6. Agent receives STANDARD level (~200 tokens):
   - critical_data_points: {workflow_id: "wf-123", revenue: "$1.2M", approval_status: "approved"}

7. Agent learns and applies:
   "Last time I required additional validation for amounts >$1M"
   "Request validation for wf-456 before approving"
```

### Canvas Context Detail Levels

| Level | Fields Included | Token Estimate | When Agent Requests |
|-------|----------------|----------------|---------------------|
| **summary** | presentation_summary only | ~50 tokens | **Default** - always included |
| **standard** | summary + critical_data_points | ~200 tokens | Agent needs business logic (amounts, IDs, status) |
| **full** | all fields (visual_elements, user_interaction) | ~500 tokens | Agent needs full reconstruction |

**Agent Progressive Enhancement**:
```python
# Agent workflow:
# 1. Get episodes with summary (automatic)
episodes = retrieve_episodes(query="workflow approval")
# Returns: Summary level (~50 tokens per episode)

# 2. Agent reviews summaries
for episode in episodes:
    summary = episode.canvas_context["presentation_summary"]
    # Agent: "This looks relevant, but I need to know the revenue amounts"

# 3. Agent requests more detail for specific episodes
relevant_episodes = retrieve_episodes(
    query="workflow approval",
    episode_ids=["ep-123", "ep-456"],  # Specific episodes
    canvas_context_detail="standard"  # Get critical_data_points
)
# Returns: Standard level (~200 tokens) - agent can see revenue amounts
```

### New Retrieval Filters

```python
# Filter by canvas type
episodes = retrieval_service.retrieve(
    filters={"canvas_type": "orchestration", "action": "submit"}
)
# Result: All workflow submission episodes

# Filter by business data
episodes = retrieval_service.retrieve(
    filters={
        "canvas_type": "orchestration",
        "critical_data_points": {
            "approval_status": "approved",
            "revenue": {"$gt": 1000000}  # $1M+ workflows
        }
    }
)
# Result: Episodes where user approved high-value workflows

# Filter by user interaction
episodes = retrieval_service.retrieve(
    filters={"user_interaction": {"$contains": "Reject"}}
)
# Result: Episodes where user clicked "Reject"
```

### Semantic Search Examples

**Before** (without canvas context):
- "Find episodes where I submitted forms" ✅ Works (action="submit")
- "Find episodes where I approved workflows" ❌ Fails (no approval context)

**After** (with canvas context):
- "Find episodes where I approved workflows" ✅ Works (canvas_context.user_interaction contains "Approve")
- "Find episodes with revenue over $1M" ✅ Works (canvas_context.critical_data_points.revenue filter)
- "Show me times the agent presented charts" ✅ Works (canvas_context.visual_elements contains "line_chart")

---

## Implementation Strategy

### Phase 20 Plans (6 plans total)

#### Wave 1: Canvas AI Accessibility (Plans 01-02, parallel)

**Plan 01**: Add canvas accessibility trees
- Create hidden `div` elements with `role="log"` for all 7 canvas types
- Populate with state JSON (lines, cursorPos, form data, chart metadata)
- Add `aria-live` attributes for screen reader announcements
- Test accessibility with screen readers (VoiceOver, NVDA)

**Plan 02**: Expose canvas state API
- Create JavaScript API for reading canvas state
- Document state schema for each canvas type
- Add WebSocket events for state changes (real-time updates)
- Test state API with visiting AI agents

#### Wave 2: Canvas Context for Episodic Memory (Plans 03-05, sequential)

**Plan 03**: Enrich EpisodeSegment with canvas context
- Add `canvas_context` JSONB field to EpisodeSegment model
- Create migration for existing episodes (populate with null)
- Update episode_segmentation_service.py to capture canvas context
- Write unit tests for canvas context enrichment

**Plan 04**: Implement canvas-aware episode retrieval with progressive detail
- Add canvas_type filter to episode_retrieval_service.py
- Add critical_data_points filter (business logic queries)
- Add user_interaction filter (intent-based search)
- **Default behavior**: Always include summary level canvas_context (~50 tokens)
- **Agent-controlled progressive detail**:
  - `canvas_context_detail` parameter ("summary" | "standard" | "full") - Agent requests more when needed
  - Default: "summary" (automatic inclusion)
  - Agent can request "standard" for business logic (critical_data_points)
  - Agent can request "full" for complete reconstruction (all fields)
- Create real-time canvas state API for live canvas access during task execution
- Write integration tests for progressive detail retrieval (summary → standard → full)

**Plan 05**: Test canvas context enrichment
- Create episodes for all 7 canvas types
- Populate canvas_context with realistic data
- Test retrieval across canvas types
- Verify 50%+ coverage on episodic memory services

#### Wave 3: Coverage Validation (Plan 06)

**Plan 06**: Coverage validation and Phase 20 summary
- Run coverage report on episodic memory services
- Verify 50%+ coverage target achieved
- Document canvas context features
- Create Phase 20 summary with results

---

## Technical Considerations

### Canvas State Storage

**Where to store canvas state?**

Option 1: **Hidden DOM elements** (recommended for AI accessibility)
- Pros: Instant access for visiting agents, no DB writes
- Cons: State lost on page refresh, not queryable

Option 2: **CanvasAudit metadata_json** (existing)
- Pros: Already persisted, queryable
- Cons: Not designed for semantic content, mixed with audit metadata

Option 3: **EpisodeSegment.canvas_context** (new)
- Pros: Semantic meaning, queryable, indexed
- Cons: Requires schema change, migration

**Decision**: Use **both** Option 1 and Option 3
- Hidden DOM elements for real-time AI agent access
- EpisodeSegment.canvas_context for episode retrieval and semantic search

### Performance Impact

**Canvas context enrichment**:
- Episode creation: +5ms (JSON serialization)
- Episode retrieval: +10ms (JSONB filter)
- Storage: +200 bytes per episode (estimated)

**Acceptable**: <20ms overhead for semantic search capabilities

### Privacy & Security

**Critical data points** may contain sensitive information:
- Financial amounts (revenue, budgets)
- User decisions (approve/reject)
- Workflow IDs (internal business logic)

**Mitigation**:
- Respect canvas governance (AUTONOMOUS agents only)
- Encrypt canvas_context at rest (JSONB encryption)
- Audit access to canvas_context (episode access logs)

---

## Success Metrics

### Canvas AI Accessibility

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Hidden accessibility trees created | 7/7 canvas types | DOM inspection |
| State exposed for AI agents | 100% of canvas state | Agent can read without OCR |
| Screen reader compatibility | 100% of canvas types | VoiceOver/NVDA testing |
| Performance overhead | <10ms per canvas render | Benchmark tests |

### Canvas Context for Episodic Memory

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Episodes enriched with canvas_context | 100% of canvas episodes | Database query |
| Canvas type coverage | 7/7 types tested | Unit tests |
| Semantic query accuracy | >90% relevant results | User acceptance testing |
| Episodic memory coverage increase | +5-10% from current | Coverage report |
| Episode retrieval performance | <100ms with canvas filters | Benchmark tests |

---

## Related Work

### Phase 12: Episodic Memory Implementation
- Created EpisodeSegment, Episode, EpisodeAccessLog models
- Implemented 4 retrieval modes (temporal, semantic, sequential, contextual)
- Already has `canvas_audit_id` field linking to CanvasAudit

**Phase 20 builds on**: Adding `canvas_context` to EpisodeSegment for semantic understanding

### Phase 14: Community Skills Integration
- Skill execution creates EpisodeSegments
- Skills can present canvases (charts, forms)

**Phase 20 benefits**: Skill episodes will have rich canvas context for better retrieval

### Canvas & Feedback Integration (Feb 4, 2026)
- Episodes link to CanvasAudit and AgentFeedback records
- Canvas-aware episodes track interactions (present, submit, close, update, execute)

**Phase 20 extends**: Adding semantic meaning to canvas interactions, not just action tracking

---

## Open Questions

1. **LLM-generated summaries**: Should presentation_summary be generated by LLM or extracted from canvas metadata?
   - **Recommendation**: Start with metadata extraction (deterministic, fast), add LLM generation later (Phase 21+)

2. **Backfilling existing episodes**: Should we populate canvas_context for historical episodes?
   - **Recommendation**: No, backfill only for active/recent episodes (last 30 days) to reduce migration cost

3. **Canvas context versioning**: What if canvas state schema changes?
   - **Recommendation**: Use JSONB schema validation, version canvas_context schema with `v1`, `v2` fields

4. **Real-time updates**: Should canvas_context update when canvas state changes?
   - **Recommendation**: No, canvas_context is snapshot at episode creation time (immutable)

---

## Next Steps

1. ✅ Research complete
2. ⏭️ Create Plan 01: Canvas accessibility trees
3. ⏭️ Create Plan 02: Canvas state API
4. ⏭️ Create Plan 03: EpisodeSegment canvas context enrichment
5. ⏭️ Create Plan 04: Canvas-aware episode retrieval
6. ⏭️ Create Plan 05: Canvas context testing
7. ⏭️ Create Plan 06: Coverage validation and summary

---

**Research Duration**: 45 minutes
**Researcher**: Claude (gsd-phase-researcher)
**Status**: ✅ COMPLETE - Ready for plan creation
