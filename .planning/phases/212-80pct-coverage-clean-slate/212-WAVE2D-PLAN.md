---
phase: 212-80pct-coverage-clean-slate
plan: WAVE2D
type: execute
wave: 2
depends_on: ["212-WAVE1A", "212-WAVE1B"]
files_modified:
  - frontend/tests/hooks/useAgentState.test.ts
  - frontend/tests/hooks/useCanvasState.test.ts
autonomous: true

must_haves:
  truths:
    - "useAgentState hook achieves 60%+ line coverage"
    - "useCanvasState hook achieves 60%+ line coverage"
    - "Frontend coverage increases from 13.42% to 45%+"
  artifacts:
    - path: "frontend/tests/hooks/useAgentState.test.ts"
      provides: "Hook tests for agent state management"
      min_lines: 200
      exports: ["test_initial_state", "test_fetch_agents"]
    - path: "frontend/tests/hooks/useCanvasState.test.ts"
      provides: "Hook tests for canvas state management"
      min_lines: 200
      exports: ["test_initial_canvas_state", "test_subscribe_to_canvas"]
  key_links:
    - from: "frontend/tests/hooks/useAgentState.test.ts"
      to: "frontend-nextjs/hooks/useAgentState.ts"
      via: "React hooks testing with @testing-library/react-hooks"
    - from: "frontend/tests/hooks/useCanvasState.test.ts"
      to: "frontend-nextjs/hooks/useCanvasState.ts"
      via: "React hooks testing with @testing-library/react-hooks"
---

<objective>
Increase frontend coverage to 45% by testing state management hooks (useAgentState, useCanvasState).

Purpose: State management hooks are critical for frontend data flow. These hooks manage agent state and canvas state, which are core to the application.

Output: 2 test files with 400+ total lines, achieving frontend 45%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@frontend-nextjs/hooks/useAgentState.ts
@frontend-nextjs/hooks/useCanvasState.ts

# Frontend Hook Test Pattern Reference
From Phase 130: Use @testing-library/react-hooks for hook testing, test hook lifecycle, state updates, and cleanup.

# Target Hook Files Analysis

## 1. useAgentState.ts
Key functionality:
- Manages agent state (list, individual agent)
- Fetches agents from API
- Updates agent state
- Deletes agents
- Filters by maturity

## 2. useCanvasState.ts
Key functionality:
- Manages canvas state (all canvases, individual canvas)
- Subscribes to canvas updates
- Gets current canvas state
- Gets all canvas states
- Unsubscribes from canvas updates
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for useAgentState hook</name>
  <files>frontend/tests/hooks/useAgentState.test.ts</files>
  <action>
Create frontend/tests/hooks/useAgentState.test.ts:

1. Imports: @testing-library/react-hooks, renderHook, waitFor
2. Import useAgentState hook

3. Describe 'useAgentState':
   - test_initial_state(): Initializes with empty state
   - test_fetch_agents(): Fetches agents from API
   - test_fetch_agents_loading(): Handles loading state
   - test_fetch_agents_error(): Handles error state
   - test_update_agent(): Updates agent state
   - test_delete_agent(): Removes from state
   - test_filter_by_maturity(): Filters agents by maturity
   - test_filter_by_status(): Filters agents by status
   - test_search_agents(): Searches agents by name
   - test_cleanup_on_unmount(): Cleans up subscriptions

4. Mock API responses with MSW or fetch mock

5. Test hook lifecycle (mount, update, unmount)

6. Test state transitions
  </action>
  <verify>
cd frontend-nextjs && npm test -- useAgentState.test.ts --coverage
# Hook coverage should be 60%+
  </verify>
  <done>
All useAgentState hook tests passing, 60%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for useCanvasState hook</name>
  <files>frontend/tests/hooks/useCanvasState.test.ts</files>
  <action>
Create frontend/tests/hooks/useCanvasState.test.ts:

1. Imports: @testing-library/react-hooks, renderHook, waitFor
2. Import useCanvasState hook

3. Describe 'useCanvasState':
   - test_initial_canvas_state(): Initializes with empty state
   - test_subscribe_to_canvas(): Subscribes to canvas updates
   - test_unsubscribe_from_canvas(): Unsubscribes from updates
   - test_get_canvas_state(): Gets current canvas state
   - test_get_all_canvas_states(): Gets all canvas states
   - test_canvas_state_updates(): Receives state updates
   - test_multiple_canvas_subscriptions(): Manages multiple subscriptions
   - test_cleanup_on_unmount(): Cleans up subscriptions
   - test_canvas_error_handling(): Handles canvas errors
   - test_canvas_reconnection(): Reconnects to canvas

4. Mock WebSocket or canvas state API

5. Test subscription lifecycle

6. Test state update propagation
  </action>
  <verify>
cd frontend-nextjs && npm test -- useCanvasState.test.ts --coverage
# Hook coverage should be 60%+
  </verify>
  <done>
All useCanvasState hook tests passing, 60%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all hook tests:
   cd frontend-nextjs
   npm test -- useAgentState.test.ts useCanvasState.test.ts --coverage

2. Verify hook coverage (target 60%+):
   cat coverage/coverage-summary.json | jq '.total.lines.pct'
   # Frontend should be 45%+

3. Verify overall frontend coverage:
   npm test -- --coverage --watchAll=false
   # Frontend should be 45%+

4. Verify no regressions in existing tests
</verification>

<success_criteria>
1. All 2 hook test files pass (100% pass rate)
2. Each hook achieves 60%+ coverage
3. Frontend overall coverage >= 45%
4. No regression in existing test coverage
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE2D-SUMMARY.md`
</output>
