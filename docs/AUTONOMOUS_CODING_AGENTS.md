# Autonomous Coding Agents - Canvas Documentation

**Last Updated:** February 21, 2026

**Component:** `CodingAgentCanvas`

**Location:** `frontend-nextjs/components/canvas/CodingAgentCanvas.tsx`

**Purpose:** Real-time visualization of autonomous coding agent operations with AI accessibility and episode integration for WorldModel recall.

---

## Table of Contents

1. [Overview](#overview)
2. [Component Features](#component-features)
3. [AI Accessibility](#ai-accessibility)
4. [Usage Example](#usage-example)
5. [Canvas State Structure](#canvas-state-structure)
6. [Approval Workflow](#approval-workflow)
7. [Validation Feedback](#validation-feedback)
8. [History View](#history-view)
9. [Integration with Orchestrator](#integration-with-orchestrator)
10. [WebSocket Protocol](#websocket-protocol)
11. [Episode Integration](#episode-integration)
12. [API Reference](#api-reference)
13. [Troubleshooting](#troubleshooting)

---

## Overview

**CodingAgentCanvas** is a specialized React component that provides real-time visualization of autonomous coding agent operations. It enables AI agents to generate code, run tests, validate results, and request human approval through an intuitive interface.

### Key Capabilities

- **Real-time Code Display**: Shows generated code with syntax highlighting support
- **Operations Tracking**: Live feed of agent operations (generation, testing, validation)
- **Human-in-the-Loop**: Approval workflow for critical code changes
- **Test Results**: Validation feedback with pass/fail rates and coverage metrics
- **Code History**: Diff comparison and change tracking
- **AI Accessibility**: Hidden state exposure for agent context
- **Episode Integration**: Automatic tracking for WorldModel recall

### Use Cases

1. **Autonomous Refactoring**: Agents refactor code with human oversight
2. **Test Generation**: AI generates test suites and validates coverage
3. **Bug Fixes**: Agents diagnose and fix bugs with approval workflow
4. **Documentation**: Automatic code documentation generation
5. **Code Reviews**: AI-assisted code review with validation

---

## Component Features

### 1. Code Editor UI

```typescript
<CodeEditor
  value={codeContent}
  language={language}
  onChange={setCodeContent}
  placeholder="Generated code will appear here..."
/>
```

**Features:**
- Multi-language support (Python, TypeScript, JavaScript, SQL, YAML)
- Monospace font with syntax highlighting
- Auto-resize textarea (256px height)
- Full code content editing capabilities

### 2. Real-Time Operations Feed

Displays agent operations with status indicators:

| Operation Type | Description |
|----------------|-------------|
| `code_generation` | Agent generates code |
| `test_generation` | Agent creates tests |
| `validation` | Agent validates code |
| `documentation` | Agent writes docs |
| `refactoring` | Agent refactors code |

**Status Indicators:**
- ⏳ **Pending**: Operation queued
- ⚡ **Running**: Operation in progress
- ✅ **Complete**: Operation succeeded
- ❌ **Failed**: Operation failed

### 3. Approval Workflow UI

Human-in-the-loop approval for code suggestions:

```tsx
<div className="approval-workspace">
  <h3>Agent Suggestion Requires Approval</h3>
  <pre>{codeContent}</pre>
  <div className="approval-actions">
    <button onClick={onApprove}>Approve</button>
    <button onClick={onRetry}>Retry</button>
    <button onClick={onReject}>Reject</button>
  </div>
</div>
```

**When Approval is Required:**
- Critical file modifications
- Security-sensitive code
- Breaking changes
- External API calls

### 4. Validation Feedback Display

Shows test results and coverage metrics:

```
Test Results
X / Y tests passing (Z%)
Coverage: C%

Failures:
- test_name: error_message
```

**Metrics:**
- Pass rate percentage
- Test coverage percentage
- Individual failure details
- Execution duration

### 5. History View with Diff Comparison

Tracks code changes over time:

```tsx
{codeChanges.map(change => (
  <div key={change.operation_id}>
    <span>{change.file_path}</span>
    <span>{change.timestamp}</span>
    <pre>{change.new_content}</pre>
  </div>
))}
```

**Features:**
- Chronological change log
- File path tracking
- Timestamp recording
- Diff preview (first 200 chars)

---

## AI Accessibility

### Hidden Accessibility Mirror

The component uses a hidden div to expose full state to AI agents:

```tsx
<div
  role="log"
  aria-live="polite"
  aria-label="Coding agent canvas state"
  style={{ display: 'none' }}
  data-canvas-type="coding"
  data-canvas-component="coding_agent_canvas"
  data-session-id={sessionId}
  data-operations-count={operations.length}
  data-code-content-length={codeContent.length}
  data-language={language}
  data-approval-required={approvalRequired || 'false'}
  data-validation-feedback={validationFeedback ? JSON.stringify(validationFeedback) : ''}
  data-current-action={currentAction || ''}
  data-agent-active={isAgentActive}
>
  {JSON.stringify({
    sessionId,
    canvas_type: 'coding',
    component: 'coding_agent_canvas',
    operations,
    codeContent,
    language,
    validationFeedback,
    approvalRequired,
    currentAction,
    agentActive: isAgentActive,
    codeChangesCount: codeChanges.length
  }, null, 2)}
</div>
```

### How AI Agents Read Canvas State

**Method 1: Accessibility Tree (Recommended)**
```javascript
// AI agent queries DOM
const mirror = document.querySelector('[role="log"][aria-live="polite"][data-canvas-type="coding"]');
const state = JSON.parse(mirror.textContent);
console.log(state.operations); // Array of operations
```

**Method 2: Canvas State API**
```typescript
import { useCanvasState } from '@/hooks/useCanvasState';

function AgentComponent() {
  const { getState } = useCanvasState();
  const codingState = getState('coding-canvas');

  console.log(codingState.operations); // Access operations
  console.log(codingState.codeContent); // Access code
  console.log(codingState.validationFeedback); // Access test results
}
```

### Benefits for WorldModel

1. **Context Preservation**: Full state capture for episodic memory
2. **Decision Recall**: Approval decisions tracked for learning
3. **Outcome Tracking**: Test results stored for validation
4. **Semantic Understanding**: Structured data for retrieval

---

## Usage Example

### Basic Integration

```typescript
import { CodingAgentCanvas } from '@/components/canvas/CodingAgentCanvas';
import { useState } from 'react';

function App() {
  const [sessionId] = useState('coding-session-123');

  const handleApprove = (actionId: string) => {
    console.log('Approved:', actionId);
    // Send approval to backend
    fetch('/api/coding/approve', {
      method: 'POST',
      body: JSON.stringify({ actionId, sessionId }),
    });
  };

  const handleRetry = (actionId: string) => {
    console.log('Retry:', actionId);
    // Request regeneration
    fetch('/api/coding/retry', {
      method: 'POST',
      body: JSON.stringify({ actionId, sessionId }),
    });
  };

  const handleReject = (actionId: string) => {
    console.log('Rejected:', actionId);
    // Reject suggestion
    fetch('/api/coding/reject', {
      method: 'POST',
      body: JSON.stringify({ actionId, sessionId }),
    });
  };

  return (
    <CodingAgentCanvas
      sessionId={sessionId}
      onApprove={handleApprove}
      onRetry={handleRetry}
      onReject={handleReject}
      className="max-w-4xl mx-auto"
    />
  );
}
```

### Advanced Integration with Episode Tracking

```typescript
import { CodingAgentCanvas } from '@/components/canvas/CodingAgentCanvas';
import useWebSocket from '@/hooks/useWebSocket';
import { useEffect } from 'react';

function CodingAgentWithEpisodes() {
  const { socket } = useWebSocket();
  const sessionId = 'session-abc-123';

  useEffect(() => {
    if (!socket) return;

    // Subscribe to coding agent updates
    socket.addEventListener('message', (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'coding:operation_complete') {
        // Create episode segment on operation complete
        fetch('/api/episodes/coding-segment', {
          method: 'POST',
          body: JSON.stringify({
            episode_id: data.episodeId,
            canvas_id: data.canvasId,
            session_id: sessionId,
            operations: data.operations,
            code_content: data.codeContent,
            validation_feedback: data.validationFeedback,
            approval_decision: data.approvalDecision,
            language: data.language,
          }),
        });
      }
    });
  }, [socket, sessionId]);

  return <CodingAgentCanvas sessionId={sessionId} />;
}
```

---

## Canvas State Structure

### TypeScript Interface

```typescript
export interface CodingAgentCanvasState extends BaseCanvasState {
  canvas_type: 'coding';
  component: 'coding_agent_canvas';
  session_id: string;
  operations: Array<{
    id: string;
    type: 'code_generation' | 'test_generation' | 'validation' | 'documentation' | 'refactoring';
    status: 'pending' | 'running' | 'complete' | 'failed';
    timestamp: string;
    codeContent?: string;
    testResults?: {
      passed: number;
      total: number;
      coverage: number;
      failures: Array<{
        test: string;
        error: string;
      }>;
      duration: number;
    };
    error?: string;
  }>;
  codeContent: string;
  language: 'python' | 'typescript' | 'javascript' | 'sql' | 'yaml';
  validationFeedback?: {
    passed: number;
    total: number;
    coverage: number;
    failures: Array<{
      test: string;
      error: string;
    }>;
  } | null;
  approvalRequired: string | null;
  currentAction: string | null;
  agentActive: boolean;
  codeChangesCount: number;
}
```

### State Persistence

Canvas state is automatically persisted via WebSocket messages and can be retrieved:

```typescript
// Get current state
const state = window.atom.canvas.getState('coding-canvas');

// Subscribe to changes
const unsubscribe = window.atom.canvas.subscribe('coding-canvas', (newState) => {
  console.log('State updated:', newState);
});

// Get all active coding canvases
const allStates = window.atom.canvas.getAllStates();
const codingCanvases = allStates.filter(s => s.state.canvas_type === 'coding');
```

---

## Approval Workflow

### Triggering Approval Request

Backend sends WebSocket message:

```json
{
  "type": "coding:approval_required",
  "data": {
    "sessionId": "session-123",
    "actionId": "action-abc-456",
    "codeContent": "def new_function():\n    pass",
    "reason": "Critical file modification"
  }
}
```

### User Actions

1. **Approve**: Code is applied to the codebase
   - Callback: `onApprove(actionId)`
   - Backend creates git commit
   - Episode records approval decision

2. **Retry**: Agent regenerates code
   - Callback: `onRetry(actionId)`
   - Backend triggers regeneration
   - New approval request sent

3. **Reject**: Suggestion is discarded
   - Callback: `onReject(actionId)`
   - Episode records rejection
   - Agent learns from feedback

### Decision Tracking

Approval decisions are tracked in episodes:

```python
# EpisodeSegment.canvas_context.critical_data_points
{
  "approval_decision": "approve",  # or "reject", "retry"
  "required_approval": true,
  "human_intervention_count": 1
}
```

---

## Validation Feedback

### Test Results Structure

```json
{
  "passed": 15,
  "total": 20,
  "coverage": 85.5,
  "failures": [
    {
      "test": "test_user_authentication",
      "error": "AssertionError: Expected True, got False"
    },
    {
      "test": "test_database_connection",
      "error": "ConnectionTimeout: Database not responding"
    }
  ]
}
```

### Coverage Metrics

- **Line Coverage**: Percentage of code lines executed
- **Branch Coverage**: Percentage of code branches tested
- **Function Coverage**: Percentage of functions called

**Target Coverage:**
- Unit tests: 85%+
- Integration tests: 70%+
- E2E tests: 60%+

### Failure Analysis

Failures are categorized by type:

| Category | Example |
|----------|---------|
| Assertion | `AssertionError: Expected 5, got 3` |
| Timeout | `TimeoutError: Test exceeded 30s` |
| Import | `ModuleNotFoundError: No module named 'xyz'` |
| Type | `TypeError: unsupported operand type(s)` |

---

## History View

### Code Changes Tracking

Each code change is stored with:

```typescript
interface CodeChange {
  operation_id: string;
  file_path: string;
  old_content: string;
  new_content: string;
  timestamp: Date;
}
```

### Diff Display

```tsx
<pre className="diff-view">
  <span className="diff-removed">- old_line = "old_value"</span>
  <span className="diff-added">+ new_line = "new_value"</span>
  unchanged_line = "same_value"
</pre>
```

### Timestamp Format

All timestamps use ISO 8601 format:

```
2026-02-21T01:30:45.123Z
```

---

## Integration with Orchestrator

### Backend Orchestrator Updates Canvas

Backend sends real-time updates via WebSocket:

```python
# backend/core/coding_orchestrator.py

async def update_canvas_state(session_id: str, updates: dict):
    """Send state update to frontend canvas."""
    message = {
        "type": "canvas:update",
        "data": {
            "action": "update",
            "component": "coding_agent_canvas",
            "sessionId": session_id,
            **updates
        }
    }

    await websocket_manager.send_to_session(session_id, message)
```

### State Synchronization Flow

1. **Agent starts operation** → Backend creates operation record
2. **Backend sends WebSocket message** → Frontend updates operations feed
3. **Operation completes** → Backend sends validation results
4. **Canvas updates** → User sees real-time progress
5. **Approval required** → Backend triggers approval workflow
6. **User approves** → Backend applies code, creates episode segment

---

## WebSocket Protocol

### Message Types

#### 1. Canvas Update

```json
{
  "type": "canvas:update",
  "data": {
    "action": "update",
    "component": "coding_agent_canvas",
    "sessionId": "session-123",
    "operations": [...],
    "codeContent": "...",
    "language": "python"
  }
}
```

#### 2. Operation Update

```json
{
  "type": "coding:operation_update",
  "data": {
    "sessionId": "session-123",
    "operation": {
      "id": "op-456",
      "type": "code_generation",
      "status": "complete",
      "timestamp": "2026-02-21T01:30:00Z"
    }
  }
}
```

#### 3. Code Change

```json
{
  "type": "coding:code_change",
  "data": {
    "sessionId": "session-123",
    "change": {
      "operation_id": "op-456",
      "file_path": "backend/services/user_service.py",
      "old_content": "...",
      "new_content": "...",
      "timestamp": "2026-02-21T01:30:00Z"
    }
  }
}
```

#### 4. Approval Required

```json
{
  "type": "coding:approval_required",
  "data": {
    "sessionId": "session-123",
    "actionId": "action-789",
    "codeContent": "def new_feature():\n    pass",
    "reason": "Critical modification"
  }
}
```

#### 5. Validation Result

```json
{
  "type": "coding:validation_result",
  "data": {
    "sessionId": "session-123",
    "feedback": {
      "passed": 18,
      "total": 20,
      "coverage": 90.0,
      "failures": [...]
    }
  }
}
```

---

## Episode Integration

### Creating Episode Segments

Backend creates episode segments automatically:

```python
# backend/core/episode_segmentation_service.py

await episode_service.create_coding_canvas_segment(
    episode_id="episode-123",
    canvas_id="coding-canvas-456",
    session_id="session-789",
    operations=[
        {"id": "op-1", "type": "code_generation", "status": "complete"},
        {"id": "op-2", "type": "test_generation", "status": "complete"},
        {"id": "op-3", "type": "validation", "status": "complete"}
    ],
    code_content="def example():\n    pass",
    validation_feedback={
        "passed": 15,
        "total": 20,
        "coverage": 85.5,
        "failures": []
    },
    approval_decision="approve",
    language="python"
)
```

### Episode Segment Structure

```python
EpisodeSegment(
    id="segment-123",
    episode_id="episode-456",
    segment_type="canvas_operation",
    content="Coding Canvas Session: coding-canvas-789\nLanguage: python\nOperations: 3...",
    content_summary="Coding agent session: 3 operations in python",
    source_type="coding_canvas",
    source_id="coding-canvas-789",
    canvas_context={
        "canvas_type": "coding",
        "presentation_summary": "Autonomous coding agent session with 3 operations in python",
        "visual_elements": ["code_editor", "operations_feed", "approval_workflow"],
        "user_interaction": "User approved code suggestion",
        "critical_data_points": {
            "session_id": "session-789",
            "language": "python",
            "operation_count": 3,
            "has_validation": True,
            "required_approval": True,
            "approval_decision": "approve",
            "test_pass_rate": 0.75,
            "coverage": 85.5
        }
    },
    metadata={
        "operation_count": 3,
        "language": "python",
        "has_validation": True,
        "required_approval": True,
        "approval_decision": "approve",
        "canvas_action_ids": ["op-1", "op-2", "op-3"],
        "code_length": 24,
        "validation_passed": 15,
        "validation_total": 20,
        "validation_coverage": 85.5,
        "validation_failures": 0
    }
)
```

### WorldModel Recall

Agents retrieve coding episodes for context:

```python
# Retrieve past coding sessions
episodes = await episode_service.retrieve_episodes(
    agent_id="agent-123",
    filters={
        "canvas_type": "coding",
        "language": "python",
        "has_approval": True
    },
    limit=5
)

# Agent learns from past approvals
for episode in episodes:
    if episode.canvas_context.critical_data_points.approval_decision == "approve":
        # Reinforce successful patterns
        pass
```

---

## API Reference

### Component Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `sessionId` | `string` | Yes | Unique session identifier |
| `onApprove` | `(actionId: string) => void` | No | Callback when user approves |
| `onRetry` | `(actionId: string) => void` | No | Callback when user requests retry |
| `onReject` | `(actionId: string) => void` | No | Callback when user rejects |
| `className` | `string` | No | Additional CSS classes |

### WebSocket Events

**Subscribe to:**

```typescript
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'coding:operation_update':
      // Update operations feed
      break;
    case 'coding:approval_required':
      // Show approval workflow
      break;
    case 'coding:validation_result':
      // Show test results
      break;
    case 'coding:code_change':
      // Add to history
      break;
  }
});
```

### REST API Endpoints

**Approval Endpoints:**

```bash
# Approve code suggestion
POST /api/coding/approve
{
  "sessionId": "session-123",
  "actionId": "action-456"
}

# Request retry
POST /api/coding/retry
{
  "sessionId": "session-123",
  "actionId": "action-456"
}

# Reject suggestion
POST /api/coding/reject
{
  "sessionId": "session-123",
  "actionId": "action-456"
}
```

**Episode Endpoints:**

```bash
# Create coding canvas segment
POST /api/episodes/coding-segment
{
  "episode_id": "episode-123",
  "canvas_id": "canvas-456",
  "session_id": "session-789",
  "operations": [...],
  "code_content": "...",
  "validation_feedback": {...},
  "approval_decision": "approve",
  "language": "python"
}
```

---

## Troubleshooting

### Issue: Canvas not updating

**Symptoms:** Operations feed not showing real-time updates

**Diagnosis:**
1. Check WebSocket connection: `socket.connected`
2. Verify sessionId matches backend session
3. Check browser console for WebSocket errors

**Solution:**
```typescript
const { socket, connected } = useWebSocket();

useEffect(() => {
  if (!connected) {
    console.error('WebSocket not connected');
  }
}, [connected]);
```

### Issue: Approval workflow not appearing

**Symptoms:** No approval UI shown when agent requests approval

**Diagnosis:**
1. Check if `approvalRequired` state is set
2. Verify `coding:approval_required` WebSocket message received
3. Check for JavaScript errors in console

**Solution:**
```typescript
// Add debug logging
useEffect(() => {
  console.log('Approval required:', approvalRequired);
}, [approvalRequired]);
```

### Issue: Validation feedback not displaying

**Symptoms:** Test results not showing after validation completes

**Diagnosis:**
1. Check `validationFeedback` state
2. Verify `coding:validation_result` WebSocket message
3. Check validation feedback structure

**Solution:**
```typescript
// Validate feedback structure
if (validationFeedback) {
  console.log('Tests:', validationFeedback.passed, '/', validationFeedback.total);
  console.log('Coverage:', validationFeedback.coverage);
}
```

### Issue: AI accessibility mirror not working

**Symptoms:** AI agents cannot read canvas state

**Diagnosis:**
1. Check hidden div exists: `[role="log"][aria-live="polite"]`
2. Verify JSON is valid in mirror content
3. Check data attributes are present

**Solution:**
```typescript
const mirror = document.querySelector('[role="log"][aria-live="polite"]');
if (mirror) {
  const state = JSON.parse(mirror.textContent || '{}');
  console.log('Canvas state:', state);
}
```

### Issue: Episode segments not created

**Symptoms:** Coding operations not tracked in episodes

**Diagnosis:**
1. Check backend logs for `create_coding_canvas_segment` calls
2. Verify episode_id is valid
3. Check database for EpisodeSegment records

**Solution:**
```python
# Add logging
logger.info(f"Creating coding segment for episode {episode_id}")
segment = await create_coding_canvas_segment(...)
logger.info(f"Created segment {segment.id}")
```

---

## Best Practices

### 1. Session Management

Always use unique session IDs:

```typescript
const sessionId = `coding-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
```

### 2. Error Handling

Handle WebSocket errors gracefully:

```typescript
socket.addEventListener('error', (error) => {
  console.error('WebSocket error:', error);
  // Show user-friendly error message
});
```

### 3. State Cleanup

Clean up WebSocket subscriptions:

```typescript
useEffect(() => {
  const handleMessage = (event) => { /* ... */ };
  socket.addEventListener('message', handleMessage);

  return () => {
    socket.removeEventListener('message', handleMessage);
  };
}, [socket]);
```

### 4. Approval Tracking

Log all approval decisions for learning:

```python
logger.info(f"Approval decision: {decision} for action {action_id}")
```

### 5. Test Coverage Validation

Always validate coverage before applying code:

```typescript
if (validationFeedback.coverage < 80) {
  console.warn('Coverage below 80% threshold');
}
```

---

## Related Documentation

- [Canvas AI Accessibility](/docs/CANVAS_AI_ACCESSIBILITY.md)
- [Episode Segmentation Service](/docs/EPISODIC_MEMORY_IMPLEMENTATION.md)
- [Agent Graduation Guide](/docs/AGENT_GRADUATION_GUIDE.md)
- [Code Quality Standards](/backend/docs/CODE_QUALITY_STANDARDS.md)

---

## Changelog

### February 21, 2026 - Initial Release

- Created CodingAgentCanvas component (492 lines)
- Added CodingAgentCanvasState TypeScript interface
- Implemented episode integration with `create_coding_canvas_segment()`
- Created comprehensive test suite (65 tests, 534 lines)
- Documented WebSocket protocol, approval workflow, validation feedback

---

**Document Version:** 1.0
**Author:** Atom AI Team
**Status:** Production Ready
