# Phase 131: Frontend Custom Hook Testing - Planning Summary

**Planned:** March 3, 2026
**Planner:** Claude (gsd-planner agent)
**Status:** Planning Complete

## Overview

Phase 131 creates comprehensive test coverage for 26 custom React hooks in the Atom frontend. Currently only 3 hooks have test files (useCanvasState, useChatMemory, useWebSocket), leaving 23 hooks (88%) untested. This phase creates isolated test files for all remaining hooks using `renderHook` from `@testing-library/react` v16.3.0.

## Hook Categorization

### Already Tested (3 hooks)
1. **useCanvasState** - Canvas state subscription with global API
2. **useChatMemory** - Async memory storage and retrieval
3. **useWebSocket** - WebSocket connection lifecycle

### Plan 01: Simple State Hooks (3 hooks)
4. **use-toast** - Toast notifications with setTimeout auto-dismiss
5. **useUndoRedo** - History stack with undo/redo state machine
6. **useVoiceIO** - Thin wrapper delegating to useSpeechRecognition

### Plan 02: Async Data Hooks (4 hooks)
7. **useCognitiveTier** - Tier preferences API calls
8. **useFileUpload** - File upload with progress tracking
9. **useLiveContacts** - Polling for contacts (60s interval)
10. **useLiveKnowledge** - Polling for knowledge items

### Plan 03: Browser API Hooks (3 hooks)
11. **useSpeechRecognition** - SpeechRecognition API with wake word
12. **useTextToSpeech** - SpeechSynthesis API with voice selection
13. **useVoiceAgent** - Audio element with blob URL handling

### Plan 04: Live Data Hooks (5 hooks)
14. **useLiveSupport** - Mock support tickets (no real API)
15. **useLiveFinance** - Polling for finance data
16. **useLiveProjects** - Polling for project tasks
17. **useLiveSales** - Polling for sales pipeline
18. **useLiveCommunication** - Polling for messages with data transformation

### Plan 05: Search & Security Hooks (4 hooks)
19. **useCommunicationSearch** - Search with query encoding
20. **useMemorySearch** - Search with tag/appId/limit options
21. **useSecurityScanner** - Desktop (Tauri) + web mode scanning
22. **useCliHandler** - Tauri CLI bridge integration

### Plan 06: Complex Hooks (3 hooks) + Test Helpers
23. **useUserActivity** - setInterval + event listeners + fetch
24. **useWhatsAppWebSocket** - WebSocket with reconnection logic
25. **useWhatsAppWebSocketEnhanced** - Enhanced WebSocket with toast notifications
26. **test-helpers.ts** - Reusable mocking utilities

## Wave Structure

| Wave | Plans | Parallel | Focus |
|------|-------|----------|-------|
| 1 | 131-01 | Independent | Simple state hooks, timer cleanup |
| 2 | 131-02, 131-03 | Parallel | Async and browser API hooks |
| 3 | 131-04, 131-05 | Parallel | Live data and search hooks |
| 4 | 131-06 | Sequential | Complex hooks with test helpers |

## Testing Patterns

### 1. Basic Hook Testing
```typescript
const { result } = renderHook(() => useHook());
expect(result.current.state).toBe(initialValue);
```

### 2. State Updates with act()
```typescript
act(() => {
  result.current.updateState(newValue);
});
expect(result.current.state).toBe(newValue);
```

### 3. Async Testing with waitFor
```typescript
await act(async () => {
  await result.current.asyncOperation();
});
await waitFor(() => {
  expect(result.current.loaded).toBe(true);
});
```

### 4. Timer Testing with jest.useFakeTimers()
```typescript
jest.useFakeTimers();
const { unmount } = renderHook(() => useHook());
act(() => {
  jest.advanceTimersByTime(30000);
});
// Verify timer fired
unmount(); // Verify cleanup
```

### 5. Browser API Mocking
```typescript
global.WebSocket = jest.fn(() => ({
  send: jest.fn(),
  close: jest.fn(),
  addEventListener: jest.fn(),
}));
// Trigger callbacks manually
```

## Success Criteria

1. All 26 hooks have dedicated test files
2. Hook tests cover mount/update/unmount lifecycles
3. State transitions tested for all hooks
4. Error handling tested with try/catch scenarios
5. Cleanup functions tested for memory leak prevention
6. All tests pass independently (no interdependencies)
7. Coverage threshold of 85% met for hooks directory (per jest.config.js)

## Coverage Targets

From `frontend-nextjs/jest.config.js`:
```javascript
'./hooks/**/*.{ts,tsx}': {
  branches: 80,
  functions: 85,
  lines: 85,
  statements: 85,
}
```

Current hooks coverage: **14.56%**
Target hooks coverage: **85%**
Gap: **70.44 percentage points**

## Estimated Test Counts

| Plan | Hooks | Tests/Hook | Total Tests |
|------|-------|-----------|-------------|
| 131-01 | 3 | 8-10 | 24-30 |
| 131-02 | 4 | 8-12 | 32-48 |
| 131-03 | 3 | 10-15 | 30-45 |
| 131-04 | 5 | 8-12 | 40-60 |
| 131-05 | 4 | 10-15 | 40-60 |
| 131-06 | 3 + helpers | 15-20 | 45-60 |
| **Total** | **26** | - | **211-303 tests** |

## Next Steps

Execute: `/gsd:execute-phase 131-frontend-custom-hook-testing`

Wave 1 (Plan 131-01) will start immediately, establishing baseline testing patterns for simple hooks before progressing to more complex async and browser API hooks.
