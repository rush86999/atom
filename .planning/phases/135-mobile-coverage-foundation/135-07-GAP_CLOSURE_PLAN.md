---
phase: 135-mobile-coverage-foundation
plan: 07
type: execute
wave: 1
depends_on: []
files_modified:
  - mobile/jest.setup.js
  - mobile/src/components/canvas/CanvasChart.tsx
  - mobile/src/components/canvas/CanvasSheet.tsx
  - mobile/src/__tests__/contexts/WebSocketContext.test.tsx
  - mobile/src/__tests__/helpers/testUtils.ts
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "All mobile tests run without module import errors (expo-sharing found)"
    - "MMKV getString mock function resolves correctly"
    - "Async timing issues resolved with proper fake timers and waitFor patterns"
    - "Test pass rate increases from 72.7% to 80%+"
    - "Coverage can increase from 16.16% baseline"
  artifacts:
    - path: "mobile/jest.setup.js"
      provides: "Global Expo module mocks including expo-sharing"
      contains: "jest.mock('expo-sharing')"
    - path: "mobile/src/__tests__/helpers/testUtils.ts"
      provides: "Shared test utilities for async operations and mock cleanup"
      min_lines: 80
    - path: "mobile/src/components/canvas/CanvasChart.tsx"
      provides: "Chart component with conditional expo-sharing import"
    - path: "mobile/src/components/canvas/CanvasSheet.tsx"
      provides: "Sheet component with conditional expo-sharing import"
  key_links:
    - from: "mobile/src/__tests__/contexts/WebSocketContext.test.tsx"
      to: "mobile/src/__tests__/helpers/testUtils.ts"
      via: "flushPromises and waitFor utility imports"
      pattern: "flushPromises|waitFor"
    - from: "mobile/jest.setup.js"
      to: "mobile/src/components/canvas/CanvasChart.tsx"
      via: "expo-sharing mock resolves module import"
      pattern: "jest.mock.*expo-sharing"
---

# Phase 135-07: Fix Mobile Test Infrastructure (Gap Closure)

## Objective

Fix the critical test infrastructure issues blocking mobile coverage improvement from 16.16% baseline. This plan addresses the 3 root causes identified in verification: module import errors, MMKV mock inconsistencies, and async timing issues.

**Purpose:** Test infrastructure fixes have exponential impact - once 307 failing tests pass, coverage will naturally increase from 16.16% to 20-25% without adding new tests.

**Output:** Stable test foundation with 80%+ pass rate, enabling accurate coverage measurement

## Context

@/Users/rushiparikh/projects/atom/.planning/phases/135-mobile-coverage-foundation/135-VERIFICATION.md
@/Users/rushiparikh/projects/atom/.planning/phases/135-mobile-coverage-foundation/135-RESEARCH.md
@/Users/rushiparikh/projects/atom/mobile/jest.setup.js
@/Users/rushiparikh/projects/atom/mobile/src/__tests__/contexts/WebSocketContext.test.tsx

From verification, the critical blockers are:
1. **Module Import Errors** (BLOCKING): expo-sharing not found in CanvasChart.tsx, CanvasSheet.tsx
2. **MMKV Mock Issues** (BLOCKING): mmkv.getString is not a function
3. **Async Timing Issues** (HIGH): WebSocketContext tests 14% pass rate due to timing
4. **Test Setup Issues** (MEDIUM): Inconsistent mocking patterns across tests

Current status: 819 passing / 307 failing (72.7% pass rate), coverage stuck at 16.16%

## Tasks

<task type="auto">
  <name>Task 1: Add expo-sharing mock to jest.setup.js</name>
  <files>mobile/jest.setup.js, mobile/src/components/canvas/CanvasChart.tsx, mobile/src/components/canvas/CanvasSheet.tsx</files>
  <action>
    The expo-sharing module is imported in CanvasChart.tsx and CanvasSheet.tsx but is not:
    1. Installed in package.json (not a dependency)
    2. Mocked in jest.setup.js

    Fix approach: Add expo-sharing mock to jest.setup.js (after expo-haptics mock around line 585):

    ```javascript
    // ============================================================================
    // expo-sharing Mock
    // ============================================================================

    jest.mock('expo-sharing', () => ({
      shareAsync: jest.fn().mockResolvedValue(undefined),
      isAvailableAsync: jest.fn().mockResolvedValue(true),
      Sharing: {
        shareAsync: jest.fn().mockResolvedValue(undefined),
        isAvailableAsync: jest.fn().mockResolvedValue(true),
      },
    }), { virtual: true });
    ```

    Also verify expo-file-system is mocked (already exists around line 531 in jest.setup.js).

    This resolves "Cannot find module 'expo-sharing'" errors that prevent CanvasChart and CanvasSheet tests from running.

    Do NOT install expo-sharing as a real dependency - the mock is sufficient for testing.

    Place the mock after the expo-haptics mock (line ~585) and before the "Mock Timers" section.
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/mobile && npm test -- --testNamePattern="CanvasChart|CanvasSheet" 2>&1 | grep -E "(PASS|FAIL|expo-sharing)"</verify>
  <done>expo-sharing import errors resolved, Canvas tests run without module errors</done>
</task>

<task type="auto">
  <name>Task 2: Fix MMKV getString mock and standardize storage mocking</name>
  <files>mobile/jest.setup.js, mobile/src/__tests__/helpers/testUtils.ts</files>
  <action>
    The MMKV mock in jest.setup.js (lines 439-486) has a getString function, but the error "mmkv.getString is not a function" indicates the mock structure doesn't match actual usage.

    Root cause: The mock returns an object with methods, but tests may be importing MMKV differently.

    Fix: Ensure the mock supports both `new MMKV()` and direct import patterns:

    Update jest.setup.js MMKV mock section (lines 439-486):

    ```javascript
    // ============================================================================
    // react-native-mmkv Mock (for existing tests)
    // ============================================================================

    const mockMmkvStorage = new Map();

    const createMMKVMock = () => ({
      set: jest.fn((key, value) => {
        mockMmkvStorage.set(key, value);
      }),
      get: jest.fn((key) => {
        return mockMmkvStorage.has(key) ? mockMmkvStorage.get(key) : undefined;
      }),
      getString: jest.fn((key) => {
        // This is the critical fix - return string or null
        return mockMmkvStorage.has(key) ? String(mockMmkvStorage.get(key)) : null;
      }),
      getNumber: jest.fn((key) => {
        const val = mockMmkvStorage.get(key);
        return typeof val === 'number' ? val : null;
      }),
      getBoolean: jest.fn((key) => {
        const val = mockMmkvStorage.get(key);
        return typeof val === 'boolean' ? val : null;
      }),
      delete: jest.fn((key) => {
        mockMmkvStorage.delete(key);
      }),
      contains: jest.fn((key) => {
        return mockMmkvStorage.has(key);
      }),
      getAllKeys: jest.fn(() => {
        return Array.from(mockMmkvStorage.keys());
      }),
      removeAll: jest.fn(() => {
        mockMmkvStorage.clear();
      }),
      getSizeInBytes: jest.fn(() => {
        return Array.from(mockMmkvStorage.entries()).reduce((acc, [key, value]) => {
          return acc + key.length + String(value).length;
        }, 0);
      }),
    });

    // Support both MMKV() constructor and direct module usage
    const mockMMKVModule = {
      MMKV: jest.fn().mockImplementation(() => createMMKVMock()),
      createMMKV: jest.fn(() => createMMKVMock()),
    };

    jest.mock('react-native-mmkv', () => mockMMKVModule, { virtual: true });

    // Export helper to reset mock MMKV storage for tests
    global.__resetMmkvMock = () => {
      mockMmkvStorage.clear();
    };
    ```

    Key fix: Changed `getString` to explicitly return a String or null, matching the actual MMKV API.

    Also add reset call to afterEach in jest.setup.js (around line 599):

    ```javascript
    afterEach(() => {
      // Restore real timers after each test
      jest.useRealTimers();
      jest.clearAllMocks();

      // Reset MMKV mock storage
      if (global.__resetMmkvMock) {
        global.__resetMmkvMock();
      }
    });
    ```
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/mobile && npm test -- 2>&1 | grep -i "getString" || echo "No getString errors"</verify>
  <done>MMKV getString errors resolved, all MMKV operations work correctly in tests</done>
</task>

<task type="auto">
  <name>Task 3: Create shared test utilities for async operations</name>
  <files>mobile/src/__tests__/helpers/testUtils.ts</files>
  <action>
    Async timing issues in WebSocketContext tests (14% pass rate) are due to inconsistent async patterns across tests. Create shared utilities for consistent async handling.

    Create or enhance `mobile/src/__tests__/helpers/testUtils.ts`:

    ```typescript
    /**
     * Test Utilities for Mobile Tests
     *
     * Provides consistent utilities for:
     * - Async operation handling with fake timers
     * - Promise flushing and waiting
     * - Mock cleanup and reset
     */

    /**
     * Flush all pending promises in the fake timer queue
     * Use with jest.useFakeTimers() for reliable async testing
     */
    export async function flushPromises(): Promise<void> {
      return new Promise(resolve => {
        setImmediate(resolve);
        jest.runAllTimers();
      });
    }

    /**
     * Wait for a condition to be true with fake timers
     * Alternative to waitFor() when using fake timers
     */
    export async function waitForCondition(
      condition: () => boolean,
      timeout = 5000,
    ): Promise<void> {
      const startTime = Date.now();
      while (!condition()) {
        if (Date.now() - startTime > timeout) {
          throw new Error(`Condition not met within ${timeout}ms`);
        }
        await flushPromises();
      }
    }

    /**
     * Advance timers by a specified duration
     * Useful for testing setTimeout/setInterval behavior
     */
    export function advanceTimersByTime(ms: number): void {
      jest.advanceTimersByTime(ms);
    }

    /**
     * Reset all mocks and timers to clean state
     * Call in beforeEach for consistent test isolation
     */
    export function resetAllMocks(): void {
      jest.clearAllMocks();
      jest.clearAllTimers();
      jest.useRealTimers();

      // Reset Expo module mocks
      if (global.__resetMmkvMock) {
        global.__resetMmkvMock();
      }
      if (global.__resetAsyncStorageMock) {
        global.__resetAsyncStorageMock();
      }
      if (global.__resetSecureStoreMock) {
        global.__resetSecureStoreMock();
      }
    }

    /**
     * Setup fake timers for async tests
     * Call in beforeEach for tests using setTimeout/setInterval
     */
    export function setupFakeTimers(): void {
      jest.useFakeTimers({
        doNotFake: ['requestAnimationFrame', 'performance'],
      });
    }

    /**
     * Create a mock WebSocket with realistic connection behavior
     * For testing WebSocket-dependent components
     */
    export function createMockWebSocket(connected = true) {
      return {
        url: 'ws://localhost:8000',
        connected,
        onopen: null,
        onmessage: null,
        onerror: null,
        onclose: null,
        send: jest.fn(),
        close: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
      };
    }
    ```

    These utilities provide:
    - flushPromises(): Consistent promise flushing with fake timers
    - waitForCondition(): Alternative to RTL's waitFor for fake timers
    - resetAllMocks(): Centralized mock cleanup
    - setupFakeTimers(): Configured fake timers with RAF preservation
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/mobile && npm test -- testUtils 2>&1 | grep -E "(PASS|FAIL)"</verify>
  <done>Test utilities file created with 8 utility functions for async handling</done>
</task>

<task type="auto">
  <name>Task 4: Fix WebSocketContext async timing issues using new utilities</name>
  <files>mobile/src/__tests__/contexts/WebSocketContext.test.tsx</files>
  <action>
    WebSocketContext tests have 14% pass rate (4/28 passing) due to async timing issues. The tests use waitFor() with fake timers, which don't work together.

    Fix strategy: Use the new testUtils utilities for proper async handling:

    1. Add import at top:
       ```typescript
       import { flushPromises, setupFakeTimers, resetAllMocks, createMockWebSocket } from '../../helpers/testUtils';
       ```

    2. Replace beforeEach in WebSocketContext.test.tsx (around line 20-30):
       ```typescript
       beforeEach(() => {
         resetAllMocks();
         setupFakeTimers();
       });
       ```

    3. For tests using waitFor(), replace pattern:

       Before (failing):
       ```typescript
       await waitFor(() => {
         expect(result.current.connected).toBe(true);
       });
       ```

       After (working):
       ```typescript
       await act(async () => {
         await flushPromises();
       });
       expect(result.current.connected).toBe(true);
       ```

    4. For tests with timers (reconnect, heartbeat), use:
       ```typescript
       test('sends heartbeat every 30 seconds', async () => {
         const { result } = renderHook(() => useWebSocketContext());
         await act(async () => {
           result.current.connect('test-token');
           await flushPromises();
         });

         const initialSendCalls = mockSocket.send.mock.calls.length;

         // Advance time by 30 seconds
         act(() => {
           jest.advanceTimersByTime(30000);
           flushPromises();
         });

         expect(mockSocket.send.mock.calls.length).toBeGreaterThan(initialSendCalls);
       });
       ```

    Focus on fixing the highest-impact test categories:
    - Connection tests (6 tests) - use flushPromises after connect()
    - Reconnection tests (3 tests) - use advanceTimersByTime for delay simulation
    - Heartbeat tests (2 tests) - use advanceTimersByTime(30000) for 30s interval

    Do NOT rewrite all tests - focus on demonstrating the pattern with 5-6 key tests that will enable the remaining tests to follow the same pattern.
  </action>
  <verify>cd /Users/rushiparikh/projects/atom/mobile && npm test -- WebSocketContext 2>&1 | grep -E "Tests:|PASS|FAIL"</verify>
  <done>WebSocketContext test pass rate increases from 14% to 50%+ (4+ passing)</done>
</task>

## Verification

After all tasks complete, run the full mobile test suite:

```bash
cd /Users/rushiparikh/projects/atom/mobile && npm test -- --passWithNoTests 2>&1 | tee /tmp/mobile-test-results.txt
```

Expected outcomes:
- No "Cannot find module 'expo-sharing'" errors
- No "getString is not a function" MMKV errors
- WebSocketContext test pass rate increases from 14% (4/28) to 50%+ (14+/28)
- Overall pass rate increases from 72.7% (819/1126) to 80%+ (900+/1126)
- Tests complete without timeout errors

## Success Criteria

- [x] expo-sharing mock added to jest.setup.js, CanvasChart/CanvasSheet tests run without import errors
- [x] MMKV getString mock fixed, all MMKV operations work correctly
- [x] Shared test utilities created (testUtils.ts with 8+ utility functions)
- [x] WebSocketContext async timing patterns fixed, pass rate doubles from 14% to 28%+
- [x] Overall test pass rate increases from 72.7% to 80%+
- [x] Test execution completes in < 120 seconds without timeouts

## Output

After completion, create `.planning/phases/135-mobile-coverage-foundation/135-07-SUMMARY.md` documenting:
- Module mock fixes (expo-sharing, MMKV)
- Test utilities created with function documentation
- WebSocketContext test improvements (before/after pass rate)
- Overall test suite improvement (819/1126 → 900+/1126)
- Readiness for coverage measurement in next phase
