# Canvas State API

## Overview

The Canvas State API enables AI agents to programmatically access canvas component state without OCR. All canvas components expose structured state via:

1. **Hidden accessibility trees** - DOM elements with `role="log"` and `data-canvas-state` attributes
2. **JavaScript API** - Global `window.atom.canvas` object
3. **WebSocket events** - Real-time state change broadcasts

## Access Methods

### Method 1: Hidden Accessibility Trees (Recommended for AI Agents)

Query the DOM for hidden state elements:

```javascript
// Get all canvas state elements
const canvasStates = document.querySelectorAll('[data-canvas-state]');

// Get specific canvas state
const operationState = document.querySelector('[data-canvas-state="agent_operation_tracker"]');

// Parse state JSON
const state = JSON.parse(operationState.textContent);
```

**Attributes:**
- `data-canvas-state` - Component identifier (e.g., "agent_operation_tracker", "view_orchestrator")
- `data-canvas-type` - Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)
- `role` - ARIA role ("log" for state, "alert" for errors)

### Method 2: JavaScript API

```javascript
// Get specific canvas state
const state = window.atom.canvas.getState('canvas-id');

// Get all canvas states
const allStates = window.atom.canvas.getAllStates();

// Subscribe to state changes
const unsubscribe = window.atom.canvas.subscribe('canvas-id', (state) => {
  console.log('State changed:', state);
});

// Unsubscribe when done
unsubscribe();

// Subscribe to all canvas changes
const unsubAll = window.atom.canvas.subscribeAll((event) => {
  console.log('Canvas changed:', event.canvas_id, event.state);
});
```

### Method 3: WebSocket Events

Subscribe to canvas state changes via WebSocket:

```javascript
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'canvas:state_change') {
    console.log('Canvas state changed:', message.canvas_id);
    console.log('New state:', message.state);
  }
});
```

## Canvas State Schemas

### AgentOperationTracker

```typescript
{
  canvas_type: 'generic',
  component: 'agent_operation_tracker',
  operation_id: string,
  agent_id: string,
  agent_name: string,
  operation_type: string,
  status: 'running' | 'waiting' | 'completed' | 'failed',
  current_step: string,
  current_step_index: number,
  total_steps?: number,
  progress: number,  // 0-100
  context: {
    what?: string,
    why?: string,
    next?: string
  },
  logs_count: number,
  started_at: string,
  completed_at?: string
}
```

### ViewOrchestrator

```typescript
{
  canvas_type: 'generic',
  component: 'view_orchestrator',
  layout: 'split_horizontal' | 'split_vertical' | 'grid' | 'tabs',
  current_view: string,
  active_views: [{
    view_id: string,
    view_type: 'canvas' | 'browser' | 'terminal' | 'app',
    title: string,
    status: 'active' | 'background' | 'closed',
    url?: string,
    command?: string
  }],
  canvas_guidance?: {
    agent_id: string,
    message: string,
    what_youre_seeing: string,
    controls: Array<{ label: string; action: string }>
  }
}
```

### Chart (LineChart, BarChart, PieChart)

```typescript
{
  canvas_type: 'generic',
  component: 'line_chart' | 'bar_chart' | 'pie_chart',
  chart_type: 'line' | 'bar' | 'pie',
  data_points: Array<{
    x: string | number,
    y: number,
    label?: string
  }>,
  axes_labels?: {
    x?: string,
    y?: string
  },
  title?: string,
  legend?: boolean
}
```

### Form (InteractiveForm)

```typescript
{
  canvas_type: 'generic',
  component: 'form',
  form_schema: {
    fields: Array<{
      name: string,
      type: string,
      label: string,
      required: boolean
    }>
  },
  form_data: Record<string, any>,
  validation_errors: Array<{
    field: string,
    message: string
  }>,
  submit_enabled: boolean,
  submitted?: boolean
}
```

## Usage Examples

### Example 1: AI Agent Reads Operation Progress

```javascript
// Agent wants to check operation progress
const operationDiv = document.querySelector('[data-canvas-state="agent_operation_tracker"]');
const operation = JSON.parse(operationDiv.textContent);

if (operation.status === 'completed') {
  console.log('Operation completed:', operation.progress + '%');
} else {
  console.log('Current step:', operation.current_step);
  console.log('Progress:', operation.progress + '%');
}
```

### Example 2: AI Agent Monitors Form State

```javascript
// Agent monitors form for submission
const formState = window.atom.canvas.getState('form-workflow-approval');

if (formState.submitted) {
  console.log('Form submitted with data:', formState.form_data);
} else if (formState.validation_errors.length > 0) {
  console.log('Form has errors:', formState.validation_errors);
}
```

### Example 3: Subscribe to Canvas Changes

```javascript
// Agent subscribes to all canvas state changes
const unsubscribe = window.atom.canvas.subscribeAll((event) => {
  console.log('Canvas changed:', event.canvas_type);
  console.log('New state:', event.state);

  // Agent decision logic based on state
  if (event.state.status === 'completed') {
    console.log('Operation completed, proceeding to next step...');
  }
});
```

## Performance Considerations

- State serialization overhead: <10ms per canvas render
- Use getState for one-time queries (faster than DOM parsing)
- Use subscribe for real-time monitoring (WebSocket events)
- Accessibility tree is always available (no JavaScript execution required)

## Canvas Type Reference

| Canvas Type | Component | State Fields |
|-------------|-----------|--------------|
| generic | agent_operation_tracker | operation_id, status, progress, context |
| generic | view_orchestrator | layout, active_views, canvas_guidance |
| generic | line_chart | data_points, axes_labels, chart_type |
| generic | bar_chart | data_points, axes_labels, chart_type |
| generic | pie_chart | data_points, legend |
| generic | form | form_data, validation_errors, submit_enabled |
| orchestration | workflow_canvas | tasks, nodes, connections |
| terminal | terminal_canvas | lines, cursor_pos, working_dir |

## See Also

- [Canvas Component Documentation](/docs/canvas/README.md)
- [Agent Guidance System](/docs/AGENT_GUIDANCE_IMPLEMENTATION.md)
- [Episodic Memory Integration](/docs/EPISODIC_MEMORY_IMPLEMENTATION.md)
