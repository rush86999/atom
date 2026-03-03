# Phase 108: Frontend Property Tests - Research

**Researched:** 2026-02-28
**Domain:** Frontend Property-Based Testing with FastCheck
**Confidence:** HIGH

## Summary

Phase 108 requires expanding FastCheck property tests for frontend state machines beyond what was created in Phase 106. Phase 106 created 40 property tests for state transitions (12 WebSocket, 10 Canvas, 10 Chat Memory, 8 Auth), but Phase 108 needs to focus on state machine invariants with 50-100 examples per test.

The codebase already has extensive property testing infrastructure:
- **FastCheck 4.5.3** installed and configured
- **3,238 lines** of property tests across 5 test files
- **Established patterns**: state machine invariants, reducer invariants, API roundtrips, Tauri commands
- **Strategic numRuns**: 50 (IO-bound), 100 (standard), 200 (critical)

The key insight from Phase 106 is that 12/40 WebSocket property tests fail due to jest.mock setup issues (test infrastructure, not state machine bugs). Phase 108 must fix these mock patterns and add comprehensive state machine invariant tests using the established numRuns strategy.

**Primary recommendation:** Use Phase 106's state-transition-validation.test.ts as the template, fix the jest.mock pattern for next-auth/react, and expand from 40 tests to ~150 tests (50 per state machine: Chat, Canvas, Auth) using numRuns: 50-100.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **fast-check** | 4.5.3 | Property-based testing framework | Industry standard for JavaScript/TypeScript PBT, inspired by Haskell's QuickCheck |
| **@testing-library/react** | 16.3.0 | renderHook for testing React hooks | Official React testing library, provides renderHook for hook testing |
| **jest** | 30.0.5 | Test runner | Project's test runner, already configured for fast-check |
| **@testing-library/jest-dom** | 6.6.3 | Custom DOM matchers | Provides expect() extensions for DOM assertions |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **jest-environment-jsdom** | 30.0.5 | JSDOM environment for React tests | Required for all React component/hook tests |
| **next-auth** | 4.24.11 | Authentication mocking | Required for auth state machine tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fast-check | jsverify | fast-check has better TypeScript support, more mature API, faster test execution |
| fast-check | testcheck-js | fast-check is more actively maintained, better shrinkage (failure minimization) |

**Installation:**
```bash
# Already installed - verify versions
npm list fast-check @testing-library/react jest
```

## Architecture Patterns

### Recommended Project Structure
```
frontend-nextjs/tests/property/
├── __tests__/
│   ├── chat-state-machine-invariants.test.ts    # NEW - Chat state machine (50 tests)
│   ├── canvas-state-machine-invariants.test.ts  # NEW - Canvas state machine (50 tests)
│   ├── auth-state-machine-invariants.test.ts    # NEW - Auth state machine (50 tests)
│   └── state-transition-validation.test.ts       # EXISTING - From Phase 106 (40 tests)
├── api-roundtrip-invariants.test.ts              # EXISTING - API roundtrips (754 lines)
├── reducer-invariants.test.ts                    # EXISTING - Reducer patterns (412 lines)
├── state-machine-invariants.test.ts              # EXISTING - General state machines (709 lines)
├── state-management.test.ts                      # EXISTING - State management (423 lines)
└── tauriCommandInvariants.test.ts                # EXISTING - Tauri commands (940 lines)
```

### Pattern 1: State Machine Invariant Testing with FastCheck
**What:** Use FastCheck's `fc.property()` to test state machine invariants across many randomly generated inputs
**When to use:** Testing state machine transitions, validating invariants that must hold true
**Example:**
```typescript
// Source: Phase 106 state-transition-validation.test.ts
import fc from 'fast-check';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '@/hooks/useWebSocket';

describe('WebSocket State Machine Invariants', () => {
  it('should have valid initial state', () => {
    fc.assert(
      fc.property(fc.boolean(), fc.array(fc.string()), (autoConnect, initialChannels) => {
        const { result } = renderHook(() => useWebSocket({ autoConnect, initialChannels }));

        return (
          typeof result.current.isConnected === 'boolean' &&
          result.current.streamingContent instanceof Map &&
          result.current.lastMessage === null
        );
      }),
      { numRuns: 50, seed: 20001 }
    );
  });

  it('should maintain consistent API shape', () => {
    fc.assert(
      fc.property(fc.boolean(), (autoConnect) => {
        const { result } = renderHook(() => useWebSocket({ autoConnect }));

        return (
          typeof result.current.isConnected === 'boolean' &&
          typeof result.current.connect === 'function' &&
          typeof result.current.disconnect === 'function' &&
          typeof result.current.sendMessage === 'function' &&
          typeof result.current.subscribe === 'function' &&
          typeof result.current.unsubscribe === 'function'
        );
      }),
      { numRuns: 50, seed: 20011 }
    );
  });
});
```

### Pattern 2: Strategic numRuns Configuration
**What:** Use different numRuns values based on test category
**When to use:** All FastCheck property tests
**Standard values from codebase:**
- **200**: Critical invariants (state machine core logic, authentication security)
- **100**: Standard business rules, data transformations, API contracts
- **50**: IO-bound operations, network requests, slow operations

**Example:**
```typescript
// Source: Existing property tests in codebase
{ numRuns: 200, seed: 22345 }  // Critical - reducer immutability
{ numRuns: 100, seed: 23020 }  // Standard - API roundtrips
{ numRuns: 50, seed: 23021 }   // IO-bound - network calls
```

### Pattern 3: Fixed Seeds for Reproducibility
**What:** Use fixed `seed` values in fc.assert() for reproducible test runs
**When to use:** All property tests (required for CI reproducibility)
**Seed ranges from codebase:**
- 20001-20040: Phase 106 state transitions (WebSocket, Canvas, Chat Memory, Auth)
- 22000-22999: Reducer invariants
- 23000-23999: State machine invariants, API roundtrips
- 24000-24999: Tauri commands

**Example:**
```typescript
// Source: Phase 106 pattern
{ numRuns: 50, seed: 20001 }  // Chat state machine
{ numRuns: 50, seed: 20013 }  // Canvas state machine
{ numRuns: 50, seed: 20023 }  // Auth state machine
```

### Pattern 4: Mock Setup for React Hooks
**What:** Mock external dependencies (next-auth, WebSocket, window.atom) before rendering hooks
**When to use:** Testing hooks that depend on external APIs
**Critical from Phase 106:** The jest.mock for next-auth/react must be at top level, not inside tests

**Example:**
```typescript
// Source: Phase 106 state-transition-validation.test.ts (LINE 31-33)
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

// Then in beforeEach:
beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({
    data: { backendToken: 'test-session-token' },
    status: 'authenticated',
  });
});
```

**Anti-pattern to avoid:**
```typescript
// DON'T DO THIS - mock inside test file after imports
// This caused 12/40 WebSocket tests to fail in Phase 106
import { useWebSocket } from '@/hooks/useWebSocket';
jest.mock('next-auth/react', () => ({ useSession: jest.fn() }));  // TOO LATE
```

### Pattern 5: Test Organization by State Machine
**What:** Group tests by state machine (Chat, Canvas, Auth) with describe blocks
**When to use:** All property test files
**Example:**
```typescript
// Source: Phase 106 structure
describe('State Machine Transition Validation Tests', () => {
  describe('WebSocket State Machine', () => {
    // 12 tests with seeds 20001-20012
  });

  describe('Canvas State Machine', () => {
    // 10 tests with seeds 20013-20022
  });

  describe('Chat Memory State Machine', () => {
    // 10 tests with seeds 20023-20032
  });

  describe('Auth State Machine', () => {
    // 8 tests with seeds 20033-20040
  });
});
```

### Anti-Patterns to Avoid
- **Testing implementation details**: Don't test internal state variables, test observable state and API shape
- **Random seeds without reproduction**: Never use { seed: undefined } - CI must be reproducible
- **Too many numRuns for slow tests**: IO-bound tests with numRuns: 200 will timeout, use numRuns: 50
- **Mock setup inside tests**: Always mock at top level, not in beforeEach or test functions
- **Missing cleanup**: Always cleanup hooks with `unmount()` if using manual cleanup

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Random input generation | Custom random number generators | `fc.string()`, `fc.integer()`, `fc.boolean()`, `fc.constantFrom()` | FastCheck provides shrinkage (failure minimization), better distribution |
| State machine modeling | Custom state transition logic | `fc.stateMachine()` or `fc.property()` with invariants | FastCheck's state machine runner handles parallel execution, edge cases |
| Async testing | Custom async handlers | `act()` from @testing-library/react | React state updates are batched, act() ensures proper timing |
| Mock management | Manual mock tracking | Jest's `jest.mock()` and `jest.clearAllMocks()` | Automatic cleanup, consistent mock lifecycle |

**Key insight:** Custom random generators lack shrinkage, making test failures hard to debug. FastCheck automatically finds minimal counterexamples.

## Common Pitfalls

### Pitfall 1: Mock Setup Timing
**What goes wrong:** jest.mock applied after imports, causing "Cannot destructure property 'data'" errors
**Why it happens:** ES modules are hoisted, jest.mock must be at top level before imports
**How to avoid:** Always place jest.mock at the very top of test file, before any imports
**Warning signs:** TypeError about undefined properties on mocked modules

**Example from Phase 106 failure:**
```typescript
// WRONG - This caused 12 WebSocket tests to fail
import { useWebSocket } from '@/hooks/useWebSocket';
jest.mock('next-auth/react', () => ({ useSession: jest.fn() }));

// CORRECT - Mock first
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));
import { useWebSocket } from '@/hooks/useWebSocket';
```

### Pitfall 2: numRuns Too High for IO-Bound Tests
**What goes wrong:** Tests timeout or take too long with numRuns: 200 for network operations
**Why it happens:** Property tests execute numRuns times, 200 network calls = slow
**How to avoid:** Use numRuns: 50 for IO-bound, numRuns: 100 for standard, numRuns: 200 for critical
**Warning signs:** Tests taking >10 seconds, CI timeouts

### Pitfall 3: Missing Fixed Seeds
**What goes wrong:** Tests pass locally but fail in CI, or failures can't be reproduced
**Why it happens:** Without fixed seeds, FastCheck generates different random inputs each run
**How to avoid:** Always use `{ seed: 20001 }` (or any number) in fc.assert()
**Warning signs:** Flaky tests, "can't reproduce" failures

### Pitfall 4: Testing Private State
**What goes wrong:** Tests break when implementation changes, even if public API is stable
**Why it happens:** Testing internal state variables instead of observable state
**How to avoid:** Only test what's returned from hook API (isConnected, state, memories, etc.)
**Warning signs:** Tests accessing `result.current._internalState`

### Pitfall 5: Not Using act() for State Updates
**What goes wrong:** State updates don't apply, tests see stale values
**Why it happens:** React batches state updates, act() ensures batches are flushed
**How to avoid:** Wrap all state-changing operations in `act(() => { ... })`
**Warning signs:** "Not wrapped in act()" warnings, state not updating

## Code Examples

Verified patterns from existing codebase:

### Chat State Machine Invariant Test
```typescript
// Source: Phase 106 state-transition-validation.test.ts
it('should have valid initial state', () => {
  fc.assert(
    fc.property(fc.boolean(), (autoStore) => {
      const { result } = renderHook(() => useChatMemory({ autoStore }));

      return (
        Array.isArray(result.current.memories) &&
        result.current.memories.length === 0 &&
        typeof result.current.isLoading === 'boolean' &&
        result.current.isLoading === false &&
        result.current.error === null &&
        typeof result.current.hasRelevantContext === 'boolean' &&
        result.current.hasRelevantContext === false &&
        typeof result.current.contextRelevanceScore === 'number' &&
        result.current.contextRelevanceScore === 0
      );
    }),
    { numRuns: 50, seed: 20023 }
  );
});
```

### Canvas State Machine Invariant Test
```typescript
// Source: Phase 106 state-transition-validation.test.ts
it('should have valid initial state', () => {
  fc.assert(
    fc.property(fc.option(fc.string(), { nil: null }), (canvasId) => {
      const { result } = renderHook(() => useCanvasState(canvasId));

      return (
        result.current.state === null &&
        Array.isArray(result.current.allStates) &&
        typeof result.current.getState === 'function' &&
        typeof result.current.getAllStates === 'function'
      );
    }),
    { numRuns: 50, seed: 20013 }
  );
});
```

### Auth State Machine Invariant Test
```typescript
// Source: Phase 106 state-transition-validation.test.ts
it('should have valid auth status', () => {
  fc.assert(
    fc.property(
      fc.constantFrom('loading', 'authenticated', 'unauthenticated'),
      (status) => {
        return ['loading', 'authenticated', 'unauthenticated'].includes(status);
      }
    ),
    { numRuns: 50, seed: 20033 }
  );
});
```

### WebSocket Mock Setup Pattern
```typescript
// Source: Phase 106 state-transition-validation.test.ts (CORRECT PATTERN)
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();

  // Mock useSession to return a session with backendToken
  (useSession as jest.Mock).mockReturnValue({
    data: { backendToken: 'test-session-token' },
    status: 'authenticated',
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Example-based testing (hardcoded inputs) | Property-based testing (randomized inputs) | Phase 103 (Backend) | 98 property tests for backend state machines |
| Manual state machine validation | FastCheck fc.property() invariants | Phase 106 (Frontend) | 40 property tests for state transitions |
| No property tests for frontend | 3,238 lines of property tests | Phase 96-106 | Comprehensive coverage of state machines, reducers, API roundtrips |

**Deprecated/outdated:**
- **jsverify**: Replaced by fast-check (better TypeScript support, more maintainers)
- **testcheck-js**: No longer maintained, replaced by fast-check
- **Manual random generators**: Replaced by FastCheck's arbitrary generators (fc.string(), fc.integer(), etc.)

**Phase 106 baseline:**
- 40 property tests created (12 WebSocket, 10 Canvas, 10 Chat Memory, 8 Auth)
- 70% pass rate (28/40 passing, 12 WebSocket tests have mock issue)
- Seeds 20001-20040 used for reproducibility
- Tests validate state transitions and invariants

**What Phase 108 must add:**
- Fix jest.mock pattern (1-2 hours)
- Expand to ~150 property tests (50 per state machine)
- Use numRuns: 50-100 (50 for IO-bound, 100 for standard)
- Document state machine invariants
- 100% pass rate target (fix mock setup issues)

## Open Questions

1. **Phase 106 mock issue resolution**
   - What we know: 12/40 WebSocket tests fail due to jest.mock not applying correctly
   - What's unclear: Whether the fix is simple (move mock to top) or requires refactoring
   - Recommendation: Start with chat-state-machine-invariants.test.ts (new file) using correct mock pattern from useWebSocket.test.ts, then backport fix to state-transition-validation.test.ts

2. **Canvas state machine complexity**
   - What we know: Canvas has 7 types (generic, docs, email, sheets, orchestration, terminal, coding)
   - What's unclear: Whether to test each type separately or use fc.constantFrom()
   - Recommendation: Use fc.constantFrom() for canvas types (pattern from Phase 106), test invariants common to all types

3. **Auth state machine scope**
   - What we know: Auth state machine has 3 states (loading, authenticated, unauthenticated)
   - What's unclear: Whether to include token refresh, session persistence in property tests
   - Recommendation: Keep property tests focused on state machine invariants (status transitions), leave token refresh to integration tests

## Sources

### Primary (HIGH confidence)
- **frontend-nextjs/tests/property/__tests__/state-transition-validation.test.ts** - Phase 106 property tests (40 tests, seeds 20001-20040)
- **frontend-nextjs/tests/property/state-machine-invariants.test.ts** - General state machine invariants (709 lines)
- **frontend-nextjs/tests/property/reducer-invariants.test.ts** - Reducer immutability patterns (412 lines)
- **frontend-nextjs/hooks/__tests__/useWebSocket.test.ts** - Working mock pattern for WebSocket tests
- **frontend-nextjs/hooks/useWebSocket.ts** - WebSocket hook implementation
- **frontend-nextjs/hooks/useChatMemory.ts** - Chat memory hook implementation
- **frontend-nextjs/hooks/useCanvasState.ts** - Canvas state hook implementation
- **frontend-nextjs/package.json** - fast-check 4.5.3, @testing-library/react 16.3.0
- **.planning/phases/106-frontend-state-management-tests/106-PHASE-SUMMARY.md** - Phase 106 results (230 tests, 87.74% coverage)
- **.planning/phases/106-frontend-state-management-tests/106-VERIFICATION.md** - FRNT-02 validation report (1,082 lines)

### Secondary (MEDIUM confidence)
- **.planning/ROADMAP.md** - Phase 108 requirements (FRNT-04: Frontend Property Tests)
- **.planning/STATE.md** - Current position (Phase 107 in progress, Phase 108 pending)
- **Phase 106 Plans** - Test patterns established in Phase 106 (state machine validation)

### Tertiary (LOW confidence)
- **fast-check documentation** (version 4.5.3) - Property testing API reference
- **React Testing Library documentation** - renderHook and act() patterns
- **Jest documentation** - jest.mock() patterns and setup

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries installed and verified in package.json
- Architecture: HIGH - 3,238 lines of existing property tests provide proven patterns
- Pitfalls: HIGH - Phase 106 identified mock setup issue with documented fix
- Code examples: HIGH - All examples from actual codebase (Phase 106, existing property tests)

**Research date:** 2026-02-28
**Valid until:** 2026-03-31 (30 days - stable domain, library versions won't change)

**Key findings:**
1. FastCheck 4.5.3 is installed and production-ready
2. 3,238 lines of property tests exist with proven patterns
3. Phase 106 created 40 property tests but 12 fail due to mock setup (known issue)
4. Strategic numRuns: 50 (IO-bound), 100 (standard), 200 (critical)
5. Fixed seeds (20001-20040) ensure reproducibility
6. Mock setup must be at top level before imports (critical pattern)
7. Chat, Canvas, Auth state machines are the focus for Phase 108
