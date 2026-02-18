# Canvas AI Accessibility Guide

## Overview

Canvas components in Atom now support AI agent accessibility through dual representation: **visual (pixels)** for humans and **logical (state)** for AI agents.

This guide explains how canvas components expose structured state, how AI agents can read canvas content without OCR, and how canvas context integrates with episodic memory.

---

## The Problem: Canvas Blind Spots

When AI agents visit canvas components, they traditionally see:

```html
<canvas id="term" width="800" height="600"></canvas>
<!-- Empty! No content visible to visiting agents -->
```

This creates blind spots where agents cannot:
- Read terminal output
- See form data
- Understand chart content
- Track user interactions

**Result**: Agents resort to OCR (slow, error-prone) or miss canvas content entirely.

---

## The Solution: Dual Representation

### Hidden Accessibility Trees

Each canvas component now includes a hidden accessibility tree:

```html
<!-- Visual representation (pixels) -->
<canvas id="term" width="800" height="600"></canvas>

<!-- Logical representation (AI-readable) -->
<div
  role="log"
  aria-live="polite"
  aria-label="Terminal state"
  style={{ display: 'none' }}
  data-canvas-state="terminal"
  data-command="npm install"
  data-lines='["$ npm install", "Installing dependencies...", "Done!"]'
>
  JSON_STATE_HERE
</div>
```

**Key Features**:
- `role="log"` - Semantic role for screen readers and AI agents
- `aria-live="polite"` - Announces changes to screen readers
- `style={{ display: 'none' }}` - Hidden from visual display
- `data-canvas-state` - Component identification
- JSON content - Full state serialization

---

## Access Methods

### Method 1: DOM Query (Recommended)

**Best for**: One-time canvas state inspection

```javascript
// Get all canvas states
const canvases = document.querySelectorAll('[data-canvas-state]');

// Get specific canvas
const terminal = document.querySelector('[data-canvas-state="terminal"]');
const state = JSON.parse(terminal.textContent);
```

**Pros**:
- No dependencies
- Works in any browser
- Atomic read (consistent snapshot)

**Cons**:
- No real-time updates
- Manual parsing required

### Method 2: JavaScript API

**Best for**: React components and real-time subscriptions

```javascript
// Get specific canvas state
const state = window.atom.canvas.getState('canvas-id');

// Get all states
const all = window.atom.canvas.getAllStates();

// Subscribe to changes
const unsub = window.atom.canvas.subscribe('canvas-id', (state) => {
  console.log('State changed:', state);
});
```

**Pros**:
- Type-safe (TypeScript definitions)
- Real-time subscriptions
- React hook available (`useCanvasState`)

**Cons**:
- Requires canvas registration
- Polling or subscription needed for updates

### Method 3: WebSocket Events

**Best for**: Real-time state streaming from backend

```javascript
socket.addEventListener('message', (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'canvas:state_change') {
    console.log('Canvas updated:', msg.state);
  }
});
```

**Pros**:
- Real-time push updates
- No polling overhead
- Server-side state management

**Cons**:
- Requires WebSocket connection
- Backend integration needed

---

## Canvas Type Schemas

### AgentOperationTracker

**Component**: Agent operation progress tracking

```typescript
{
  canvas_type: 'generic',
  component: 'agent_operation_tracker',
  operation_id: string,
  agent_id: string,
  agent_name: string,
  status: 'running' | 'waiting' | 'completed' | 'failed',
  progress: number,  // 0-100
  current_step: string,
  context: {
    what?: string,
    why?: string,
    next?: string
  }
}
```

**Use cases**:
- Track long-running agent operations
- Monitor operation progress
- Understand operation context

### ViewOrchestrator

**Component**: Multi-view layout management

```typescript
{
  canvas_type: 'generic',
  component: 'view_orchestrator',
  layout: 'split_horizontal' | 'split_vertical' | 'grid' | 'tabs',
  active_views: Array<{
    view_id: string,
    view_type: 'canvas' | 'browser' | 'terminal' | 'app',
    title: string,
    status: 'active' | 'background' | 'closed'
  }>
}
```

**Use cases**:
- Understand current view layout
- Track active views
- Coordinate multi-view interactions

### Charts (Line, Bar, Pie)

**Component**: Data visualization

```typescript
{
  canvas_type: 'generic',
  component: 'line_chart' | 'bar_chart' | 'pie_chart',
  data_points: Array<{ x: string | number, y: number }>,
  axes_labels?: { x?: string, y?: string },
  title?: string,
  legend?: boolean
}
```

**Use cases**:
- Extract chart data
- Understand trends and patterns
- Compare data points

### Forms

**Component**: Interactive forms

```typescript
{
  canvas_type: 'generic',
  component: 'form',
  form_data: Record<string, any>,
  validation_errors: Array<{ field: string, message: string }>,
  submit_enabled: boolean,
  submitted?: boolean
}
```

**Use cases**:
- Read form field values
- Check validation status
- Monitor form submission

### Terminal

**Component**: Terminal emulator

```typescript
{
  canvas_type: 'terminal',
  lines: string[],
  cursor_pos: { row: number, col: number },
  working_dir: string,
  command: string
}
```

**Use cases**:
- Read command output
- Track terminal state
- Understand working directory

### Orchestration

**Component**: Workflow orchestration boards

```typescript
{
  canvas_type: 'orchestration',
  tasks: Array<{ task_id: string, status: string }>,
  nodes: Array<{ node_id: string, app_name: string }>,
  connections: Array<{ from_node: string, to_node: string }>
}
```

**Use cases**:
- Understand workflow structure
- Track task status
- Visualize node connections

---

## Episodic Memory Integration

Canvas context is automatically captured in episodes for AI agent learning:

### EpisodeSegment Canvas Context

```python
EpisodeSegment {
    canvas_context: {
        "canvas_type": "orchestration",
        "presentation_summary": "Agent presented approval form",
        "visual_elements": ["workflow_board", "approval_form"],
        "user_interaction": "User clicked 'Approve'",
        "critical_data_points": {
            "workflow_id": "wf-123",
            "approval_status": "approved"
        }
    }
}
```

### Canvas-Aware Episode Retrieval

**Find episodes with specific canvas types**:
```python
episodes = retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval",
    canvas_type="orchestration"
)
```

**Find episodes with business data**:
```python
episodes = retrieve_by_business_data(
    agent_id="agent-123",
    filters={
        "approval_status": "approved",
        "revenue": {"$gt": 1000000}
    }
)
```

### Progressive Detail Levels

**Summary level** (~50 tokens, default):
```python
episodes = retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval",
    canvas_context_detail="summary"
)
# Returns: { presentation_summary: "..." }
```

**Standard level** (~200 tokens):
```python
episodes = retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval",
    canvas_context_detail="standard"
)
# Returns: { presentation_summary: "...", critical_data_points: {...} }
```

**Full level** (~500 tokens):
```python
episodes = retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval",
    canvas_context_detail="full"
)
# Returns: All fields including visual_elements
```

---

## Usage Examples

### Example 1: Agent Reads Form State

```javascript
const formState = window.atom.canvas.getState('form-approval');

if (formState.submitted) {
  console.log('Form approved with data:', formState.form_data);
  // Agent can now proceed with approval workflow
} else if (formState.validation_errors.length > 0) {
  console.log('Form has errors:', formState.validation_errors);
  // Agent can help user fix validation errors
}
```

### Example 2: Agent Subscribes to Operation Progress

```javascript
window.atom.canvas.subscribe('operation-123', (state) => {
  if (state.status === 'completed') {
    console.log('Operation complete at', state.progress + '%');
    // Agent can now proceed to next step
  } else if (state.status === 'failed') {
    console.log('Operation failed at step:', state.current_step);
    // Agent can handle failure
  }
});
```

### Example 3: Canvas-Aware Episode Retrieval

```python
# Find episodes where I approved $1M+ workflows
from core.episode_retrieval_service import retrieve_by_business_data

episodes = retrieve_by_business_data(
    agent_id="agent-123",
    filters={
        "approval_status": "approved",
        "revenue": {"$gt": 1000000}
    }
)

for episode in episodes:
    print(f"Workflow {episode.canvas_context['critical_data_points']['workflow_id']}")
    print(f"Revenue: ${episode.canvas_context['critical_data_points']['revenue']}")
```

### Example 4: Progressive Detail for Token Efficiency

```python
# Agent starts with summary (50 tokens)
episodes = retrieve_episodes(
    agent_id="agent-123",
    query="workflow approval",
    canvas_context_detail="summary"
)

# Agent requests more detail only when needed (200 tokens)
if needs_more_context:
    episodes = retrieve_episodes(
        agent_id="agent-123",
        query="workflow approval",
        canvas_context_detail="standard"
    )
```

---

## Performance Considerations

### Accessibility Tree Overhead
- **Per render**: <10ms
- **JSON serialization**: ~1-2ms per component
- **Memory**: ~100-500 bytes per component

### Episode Storage
- **Per episode**: ~200 bytes for canvas_context
- **Storage format**: JSONB (efficient binary JSON)
- **Indexing**: GIN indexes for fast JSON queries (PostgreSQL)

### Retrieval Overhead
- **Canvas-type filtering**: <20ms
- **Progressive detail filtering**: <5ms
- **Business data filtering**: <50ms (JSONB queries)

---

## API Reference

### DOM API

**Query selectors**:
- `document.querySelectorAll('[data-canvas-state]')` - All canvas states
- `document.querySelector('[data-canvas-state="terminal"]')` - Specific canvas

**Data attributes**:
- `data-canvas-state` - Canvas type identifier
- `data-canvas-id` - Unique canvas ID
- Component-specific attributes (e.g., `data-command`, `data-lines`)

### JavaScript API

**Global object**: `window.atom.canvas`

**Methods**:
- `getState(canvasId)` - Get specific canvas state
- `getAllStates()` - Get all active canvas states
- `subscribe(canvasId, callback)` - Subscribe to state changes
- `subscribeAll(callback)` - Subscribe to all canvas changes

**TypeScript types**: See `frontend-nextjs/components/canvas/types/index.ts`

### WebSocket Events

**Event types**:
- `canvas:state_change` - Canvas state updated
- `canvas:created` - New canvas created
- `canvas:destroyed` - Canvas destroyed

**WebSocket endpoint**: `/api/canvas/ws/{canvas_id}`

### HTTP API

**Canvas state endpoints**:
- `GET /api/canvas/state/{canvas_id}` - Get canvas state
- `GET /api/canvas/types` - List canvas types

**Episode retrieval endpoints**:
- `POST /api/episodes/retrieve/canvas-aware` - Canvas-aware retrieval
- `GET /api/episodes/retrieve/canvas-type/{canvas_type}` - Filter by canvas type
- `POST /api/episodes/retrieve/business-data` - Business data filtering
- `GET /api/episodes/canvas-types` - List available canvas types

---

## See Also

- [Canvas State API Documentation](/docs/CANVAS_STATE_API.md)
- [Episodic Memory Implementation](/docs/EPISODIC_MEMORY_IMPLEMENTATION.md)
- [Agent Guidance System](/docs/AGENT_GUIDANCE_IMPLEMENTATION.md)
- [Phase 20 Summary](/.planning/phases/20-canvas-ai-context/20-PHASE-SUMMARY.md)

---

*Generated: 2026-02-18*
*Phase 20: Canvas AI Context*
*Status: COMPLETE*
