# Phase 96: Mobile Integration - Research

**Researched:** 2026-02-26
**Domain:** React Native/Expo testing with Jest, device feature mocking, property-based testing
**Confidence:** HIGH

## Summary

Phase 096 implements comprehensive mobile integration tests for the Atom React Native app, building on Jest infrastructure already configured (jest-expo 50.0.0). The mobile app has 17 services implemented (camera, location, notifications, biometric, offline sync, etc.) but limited test coverage. The phase requires (1) integration tests for device features with proper Expo module mocking, (2) offline data sync validation with conflict resolution testing, (3) platform permission and biometric authentication testing, (4) FastCheck property tests for mobile-specific invariants, and (5) cross-platform consistency tests verifying feature parity between web and mobile.

The research confirms that **jest-expo with React Native Testing Library is the standard stack** for React Native testing. Expo provides comprehensive mocking documentation for device modules (expo-camera, expo-location, expo-notifications, expo-local-authentication). The existing jest.setup.js has 522 lines of mocks already configured for all device modules. Offline sync service has comprehensive test patterns established (507 lines in existing test file). Property-based testing with FastCheck should mirror Hypothesis patterns from backend (test_governance_maturity_invariants.py, test_device_tool_invariants.py) but focus on mobile invariants like queue persistence, sync logic, and state management.

**Primary recommendation:** Use existing jest-expo infrastructure with React Native Testing Library for component/service integration tests, expand offline sync test patterns to cover device features, implement FastCheck property tests for queue invariants and sync logic, and integrate mobile coverage into unified aggregation script from Phase 095.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **jest-expo** | 50.0.0 | Jest preset for Expo apps | Official Expo testing framework, handles React Native transforms |
| **@testing-library/react-native** | 12.4.2 | Component testing utilities | Industry standard for React Native component testing |
| **FastCheck** | 4.5.3 | Property-based testing for TypeScript | Hypothesis equivalent for JavaScript/TypeScript, type-safe generators |
| **jest** | 29.7.0 | Test runner | Already configured, 80% coverage threshold enforced |
| **Detox** | 20.47.0 | Grey-box E2E testing | 10x faster than Appium, Expo integration via detox-expo-helpers |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **expo-modules-autoloading** | ~1.0.0 | Auto-load Expo mocks in tests | Required for jest-expo to mock native modules |
| **@react-native-async-storage/async-storage** | 2.2.0 | Async storage mocking | Mock in-memory storage for tests |
| **react-native-mmkv** | 4.1.2 | Fast key-value storage mocking | Already mocked in jest.setup.js for offline queue tests |
| **@react-native-community/netinfo** | 11.5.2 | Network state mocking | Test offline/online transitions for sync logic |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| jest-expo | React Native Jest preset | jest-expo handles Expo SDK 50 modules, RN preset requires manual mock configuration |
| Detox | Appium | Detox 10x faster (grey-box vs black-box), better Expo support, smaller community |
| FastCheck | TestCheck (deprecated) | FastCheck actively maintained, better TypeScript support, richer arbitraries |
| React Native Testing Library | Enzyme (deprecated) | RNTL official standard, Enzyme deprecated, better async handling |

**Installation:**
```bash
# Already installed in mobile/package.json
npm install --save-dev jest jest-expo @testing-library/react-native @testing-library/jest-native

# For property-based testing (need to add)
npm install --save-dev fast-check

# For E2E testing (need to add)
npm install --save-dev detox detox-expo-helpers
```

## Architecture Patterns

### Recommended Project Structure

```
mobile/src/__tests__/
├── unit/                    # Unit tests for services/utils
│   ├── services/
│   │   ├── cameraService.test.ts
│   │   ├── locationService.test.ts
│   │   ├── notificationService.test.ts
│   │   ├── biometricService.test.ts
│   │   └── offlineSyncService.test.ts  # Already exists (507 lines)
│   └── utils/
│       ├── validation.test.ts
│       └── helpers.test.ts
├── integration/             # Service integration tests
│   ├── deviceFeatures.integration.test.ts   # Camera + Location + Notifications
│   ├── offlineSync.integration.test.ts      # Sync logic + API + Storage
│   └── authFlow.integration.test.ts         # Biometric + SecureStore + API
├── property/                # Property-based tests
│   ├── queueInvariants.test.ts              # Offline queue properties
│   ├── syncLogic.test.ts                    # Sync algorithm properties
│   └── stateMachine.test.ts                 # Device state transitions
├── cross-platform/          # Web-mobile consistency tests
│   ├── apiContracts.test.ts                 # Shared API contract validation
│   ├── featureParity.test.ts                # Web vs mobile feature comparison
│   └── dataStructures.test.ts               # Shared type validation
└── e2e/                     # End-to-end tests (Detox)
    ├── authFlow.e2e.test.ts
    ├── agentChat.e2e.test.ts
    └── offlineSync.e2e.test.ts
```

### Pattern 1: Expo Device Feature Mocking

**What:** Mock Expo modules (expo-camera, expo-location, expo-notifications, expo-local-authentication) using jest.mock() in jest.setup.js for consistent, testable device feature access.

**When to use:** All device feature tests (camera capture, location tracking, notifications, biometric auth).

**Example:**
```typescript
// jest.setup.js (already implemented - lines 35-207)

// expo-camera Mock
jest.mock('expo-camera', () => ({
  Camera: {
    Constants: {
      Type: { back: 'back', front: 'front' },
      FlashMode: { off: 'off', on: 'on', auto: 'auto' },
      CameraPermissionStatus: { granted: 'granted', denied: 'denied' },
    },
  },
  requestCameraPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  }),
  takePictureAsync: jest.fn().mockResolvedValue({
    uri: 'file:///mock/photo.jpg',
    width: 1920,
    height: 1080,
  }),
}));

// Test usage
import { requestCameraPermissionsAsync } from 'expo-camera';

describe('CameraService', () => {
  test('should request camera permissions', async () => {
    const result = await requestCameraPermissionsAsync();
    expect(result.status).toBe('granted');
    expect(result.granted).toBe(true);
  });
});
```

### Pattern 2: Offline Sync Integration Testing

**What:** Test offline queue persistence, sync on reconnect, and conflict resolution using mocked storage, network state, and API.

**When to use:** All offline sync scenarios (queue actions, sync batches, handle conflicts, retry logic).

**Example:**
```typescript
// Source: mobile/src/__tests__/services/offlineSync.test.ts (already exists)

import AsyncStorage from '@react-native-async-storage/async-storage';
import { offlineSyncService, OfflineAction } from '../../services/offlineSyncService';

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage');

// Mock fetch
global.fetch = jest.fn();

describe('OfflineSyncService', () => {
  test('should queue action when offline', async () => {
    const action: OfflineAction = {
      id: 'action_1',
      type: 'agent_message',
      data: { message: 'Test' },
      priority: 5,
      created_at: Date.now(),
      retries: 0,
    };

    await offlineSyncService.queueAction(action);
    const queue = await offlineSyncService.getQueue();

    expect(queue).toHaveLength(1);
    expect(queue[0]).toEqual(action);
  });

  test('should sync batch on reconnect', async () => {
    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);

    // Queue 5 actions
    for (let i = 0; i < 5; i++) {
      await offlineSyncService.queueAction({
        id: `action_${i}`,
        type: 'agent_message',
        data: { message: `Test ${i}` },
        priority: 5,
        created_at: Date.now() + i,
        retries: 0,
      });
    }

    const result = await offlineSyncService.syncBatch(5);

    expect(result.processed).toBe(5);
    expect(result.succeeded).toBe(5);
    expect(result.failed).toBe(0);
  });
});
```

### Pattern 3: Biometric Authentication Testing

**What:** Mock expo-local-authentication to test biometric availability, authentication success/failure, and lockout scenarios.

**When to use:** All biometric auth flows (login, payments, sensitive actions).

**Example:**
```typescript
// jest.setup.js (lines 197-207)
jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn().mockResolvedValue(true),
  isEnrolledAsync: jest.fn().mockResolvedValue(true),
  authenticateAsync: jest.fn().mockResolvedValue({
    success: true,
    error: undefined,
    warning: undefined,
  }),
}));

// Test usage
import * as LocalAuthentication from 'expo-local-authentication';
import { biometricService } from '../../services/biometricService';

describe('BiometricService', () => {
  test('should authenticate successfully', async () => {
    jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
      success: true,
      warning: undefined,
      error: undefined,
    });

    const result = await biometricService.authenticate();

    expect(result.success).toBe(true);
  });

  test('should handle authentication failure', async () => {
    jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
      success: false,
      warning: undefined,
      error: 'not_enrolled',
    });

    const result = await biometricService.authenticate();

    expect(result.success).toBe(false);
    expect(result.error).toBe('not_enrolled');
  });

  test('should lock out after max attempts', async () => {
    // Mock 5 failed attempts
    for (let i = 0; i < 5; i++) {
      jest.spyOn(LocalAuthentication, 'authenticateAsync').mockResolvedValue({
        success: false,
        error: 'authentication_failed',
      });
      await biometricService.authenticate();
    }

    // Should be locked out
    const isLockedOut = await biometricService.isLockedOut();
    expect(isLockedOut).toBe(true);
  });
});
```

### Pattern 4: FastCheck Property Tests for Mobile Invariants

**What:** Use FastCheck to generate random inputs and verify mobile-specific invariants (queue persistence, sync logic, state transitions) mirror backend Hypothesis patterns.

**When to use:** Critical invariants that must hold across all inputs (queue ordering, sync idempotency, state machine consistency).

**Example:**
```typescript
// Source: Based on backend/tests/property_tests/governance/test_governance_maturity_invariants.py

import fc from 'fast-check';
import { offlineSyncService } from '../../services/offlineSyncService';

describe('Offline Queue Invariants', () => {
  describe('Queue Ordering Invariant', () => {
    it('should maintain priority ordering regardless of insertion order', () => {
      fc.assert(
        fc.property(
          fc.array(
            fc.record({
              id: fc.string(),
              priority: fc.integer({ min: 1, max: 10 }),
              created_at: fc.integer({ min: 0, max: Date.now() }),
            }),
            { minLength: 1, maxLength: 100 }
          ),
          (actions) => {
            // Queue all actions
            actions.forEach((action) => {
              offlineSyncService.queueAction(action);
            });

            // Get sorted queue
            const sorted = await offlineSyncService.getSortedQueue();

            // Invariant: Higher priority actions should come first
            for (let i = 0; i < sorted.length - 1; i++) {
              expect(sorted[i].priority).toBeGreaterThanOrEqual(sorted[i + 1].priority);
            }

            // Invariant: For equal priority, earlier actions come first
            for (let i = 0; i < sorted.length - 1; i++) {
              if (sorted[i].priority === sorted[i + 1].priority) {
                expect(sorted[i].created_at).toBeLessThanOrEqual(sorted[i + 1].created_at);
              }
            }

            return true;
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('Sync Idempotency Invariant', () => {
    it('should produce same result when syncing same action twice', () => {
      fc.assert(
        fc.property(
          fc.record({
            id: fc.uuid(),
            type: fc.constantFrom('agent_message', 'workflow_trigger', 'form_submit'),
            payload: fc.object(),
          }),
          async (action) => {
            // Queue action
            await offlineSyncService.queueAction(action);

            // Sync first time
            const result1 = await offlineSyncService.syncBatch(1);
            await offlineSyncService.queueAction(action); // Re-queue

            // Sync second time
            const result2 = await offlineSyncService.syncBatch(1);

            // Invariant: Idempotent operations should have same result
            expect(result1.succeeded).toEqual(result2.succeeded);

            return true;
          }
        ),
        { numRuns: 50 }
      );
    });
  });

  describe('Queue Size Invariant', () => {
    it('should enforce max queue size (1000 actions)', () => {
      fc.assert(
        fc.property(
          fc.integer({ min: 1001, max: 2000 }),
          async (count) => {
            // Add actions
            for (let i = 0; i < count; i++) {
              await offlineSyncService.queueAction({
                id: `action_${i}`,
                type: 'test',
                data: {},
                priority: 1,
                created_at: Date.now() + i,
                retries: 0,
              });
            }

            const queue = await offlineSyncService.getQueue();

            // Invariant: Queue size should not exceed max
            expect(queue.length).toBeLessThanOrEqual(1000);

            return true;
          }
        ),
        { numRuns: 10 }
      );
    });
  });
});
```

### Pattern 5: Cross-Platform Consistency Tests

**What:** Verify that mobile and web implementations have identical behavior for shared features (API contracts, data structures, business logic).

**When to use:** Features implemented on both web and mobile (agent chat, canvas presentations, workflows).

**Example:**
```typescript
// Test shared API contracts between web and mobile
import { apiService } from '../../services/api';
import { AGENT_MESSAGE_SCHEMA, CANVAS_STATE_SCHEMA } from '@atom/shared-types';

describe('Cross-Platform API Contracts', () => {
  describe('Agent Message Contract', () => {
    it('should send agent messages matching backend schema', async () => {
      const message = {
        agent_id: 'agent_123',
        session_id: 'session_456',
        message: 'Test message',
        platform: 'mobile',
      };

      // Validate against shared schema
      expect(() => AGENT_MESSAGE_SCHEMA.parse(message)).not.toThrow();

      // Test API call
      const response = await apiService.sendAgentMessage(message);

      // Invariant: Response should match expected schema
      expect(response).toHaveProperty('message_id');
      expect(response).toHaveProperty('status');
      expect(response).toHaveProperty('timestamp');
    });
  });

  describe('Canvas State Contract', () => {
    it('should deserialize canvas state consistently with web', () => {
      const mobileCanvasState = {
        id: 'canvas_123',
        type: 'sheets',
        data: { rows: 10, columns: 5 },
      };

      // Validate against shared schema
      expect(() => CANVAS_STATE_SCHEMA.parse(mobileCanvasState)).not.toThrow();
    });
  });
});

// Test feature parity between web and mobile
describe('Feature Parity: Web vs Mobile', () => {
  it('should support same agent chat features', () => {
    const webFeatures = ['streaming', 'history', 'feedback', 'canvas'];
    const mobileFeatures = Object.keys(agentService.getSupportedFeatures());

    // Invariant: Mobile should support all web chat features
    webFeatures.forEach((feature) => {
      expect(mobileFeatures).toContain(feature);
    });
  });

  it('should support same canvas types', () => {
    const webCanvasTypes = ['generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding'];
    const mobileCanvasTypes = canvasService.getSupportedTypes();

    // Invariant: Mobile should support all web canvas types
    webCanvasTypes.forEach((type) => {
      expect(mobileCanvasTypes).toContain(type);
    });
  });
});
```

### Anti-Patterns to Avoid

- **Testing implementation details:** Don't test internal service methods, test observable behavior (queue state, sync results, API responses)
- **Mocking everything:** Don't mock the service under test, only external dependencies (Expo modules, AsyncStorage, fetch)
- **Fragile selector tests:** Don't test by text content alone, use test IDs and data attributes
- **Testing React Navigation internals:** Don't test navigation state directly, test screen renders and navigation actions
- **Ignoring async behavior:** Don't forget to wait for promises, use waitFor and findBy* queries

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Expo module mocking | Manual mock objects for camera, location, notifications | jest.mock() in jest.setup.js | Expo provides official mock patterns, covers edge cases |
| Async testing | Custom promise wrappers, setTimeout loops | @testing-library/react-native's waitFor, findBy* queries | Handles React Native async rendering, timer mocking |
| Component queries | Manual findByText, findByProps | React Native Testing Library's getBy*, findBy*, queryBy* queries | Industry standard, accessible queries, better error messages |
| Property testing | Random generation with Math.random() | FastCheck arbitraries (fc.integer(), fc.string(), fc.record()) | Shrinking, reproducibility, type safety |
| Network mocking | Custom XMLHttpRequest mock, fetch polyfill | jest.mock() for fetch, MSW (optional) | Simpler, handles edge cases, consistent with Jest |
| Storage mocking | In-memory Map, custom storage adapter | React Native mocked AsyncStorage/MMKV | Matches production API, persistence testing |

**Key insight:** Expo and React Native ecosystems have mature testing infrastructure. Building custom mocks wastes time and misses edge cases (permission states, native module initialization, platform differences).

## Common Pitfalls

### Pitfall 1: Platform Permission Mocking Mismatch
**What goes wrong:** Tests pass on one platform (iOS) but fail on another (Android) due to different permission status values.

**Why it happens:** Expo modules return different permission status strings per platform (e.g., 'granted' vs iOS-specific values).

**How to avoid:** Use jest.mock() to normalize permission responses across platforms, test both iOS and Android scenarios.

```typescript
// Bad: Assumes iOS-specific values
const result = await requestCameraPermissionsAsync();
expect(result.status).toBe('granted'); // Fails on Android

// Good: Mock consistent responses
jest.mock('expo-camera', () => ({
  requestCameraPermissionsAsync: jest.fn().mockResolvedValue({
    status: 'granted', // Consistent across platforms
    granted: true,
  }),
}));
```

**Warning signs:** Tests fail on CI but pass locally, platform-specific test files duplicated.

### Pitfall 2: Timer-Dependent Sync Tests
**What goes wrong:** Offline sync tests fail intermittently due to timing issues (sync timeout, retry delay).

**Why it happens:** Tests use real timers instead of Jest fake timers, causing flaky tests.

**How to avoid:** Always use Jest fake timers in jest.setup.js, advance timers explicitly in tests.

```typescript
// jest.setup.js (already implemented - lines 439-448)
beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
  jest.clearAllMocks();
});

// Test usage
test('should retry sync after delay', async () => {
  await offlineSyncService.syncBatch(10);

  // Fast-forward 1 second (base retry delay)
  jest.advanceTimersByTime(1000);

  // Verify retry attempted
  expect(fetch).toHaveBeenCalledTimes(2);
});
```

**Warning signs:** Flaky tests that fail 1-2% of the time, tests using setTimeout/setInterval, inconsistent CI results.

### Pitfall 3: Storage Mock Not Persisting Between Tests
**What goes wrong:** Tests expect AsyncStorage/MMKV to persist data but mock resets between tests.

**Why it happens:** Mock stores not reset properly in beforeEach(), causing test pollution.

**How to avoid:** Export reset helpers from jest.setup.js, call in beforeEach().

```typescript
// jest.setup.js (lines 229-293)
const mockAsyncStorage = new Map();
global.__resetAsyncStorageMock = () => {
  mockAsyncStorage.clear();
};

// Test usage
beforeEach(() => {
  __resetAsyncStorageMock();
});
```

**Warning signs:** Tests fail when run in suites but pass individually, data leaking between tests.

### Pitfall 4: Property Tests Without Shrinking
**What goes wrong:** FastCheck property tests fail but don't provide minimal counterexample, making debugging hard.

**Why it happens:** Not configuring FastCheck with proper settings (numRuns, timeout, seed).

**How to avoid:** Always configure FastCheck with explicit settings, use seed for reproducibility.

```typescript
// Bad: No configuration
fc.assert(fc.property(fc.string(), (str) => isValid(str)));

// Good: Explicit settings
fc.assert(
  fc.property(fc.string(), (str) => isValid(str)),
  { numRuns: 100, timeout: 10000, seed: 1234 } // Reproducible
);
```

**Warning signs:** Property tests fail with complex counterexamples, hard to minimize failure cases.

### Pitfall 5: Cross-Platform Tests Assuming Web Environment
**What goes wrong:** Mobile tests assume browser APIs (window, localStorage) are available.

**Why it happens:** Reusing web test patterns without React Native adaptations.

**How to avoid:** Use React Native-specific APIs (AsyncStorage instead of localStorage, Platform.OS for platform checks).

```typescript
// Bad: Assumes web environment
localStorage.setItem('key', 'value');

// Good: React Native storage
import AsyncStorage from '@react-native-async-storage/async-storage';
await AsyncStorage.setItem('key', 'value');
```

**Warning signs:** Tests fail with "undefined is not a function" on window/localStorage, platform-specific imports.

## Code Examples

Verified patterns from official sources:

### Device Feature Permission Testing

```typescript
// Source: https://docs.expo.dev/versions/latest/sdk/permissions/
import * as Camera from 'expo-camera';

describe('Camera Permissions', () => {
  test('should request camera permissions on iOS', async () => {
    jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
      status: 'granted',
      granted: true,
      canAskAgain: true,
      expires: 'never',
    });

    const result = await Camera.requestCameraPermissionsAsync();

    expect(result.status).toBe('granted');
    expect(result.granted).toBe(true);
  });

  test('should handle denied permissions', async () => {
    jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
      status: 'denied',
      granted: false,
      canAskAgain: false,
      expires: 'never',
    });

    const result = await Camera.requestCameraPermissionsAsync();

    expect(result.status).toBe('denied');
    expect(result.granted).toBe(false);
  });
});
```

### Network State Testing for Offline Sync

```typescript
// Source: https://github.com/react-native-netinfo/react-native-netinfo
import NetInfo from '@react-native-community/netinfo';

describe('Offline Sync', () => {
  test('should trigger sync when connection restored', async () => {
    // Mock offline state
    jest.spyOn(NetInfo, 'fetch').mockResolvedValue({
      isConnected: false,
      isInternetReachable: false,
      type: 'none',
    });

    await offlineSyncService.initialize();

    // Mock online state
    jest.spyOn(NetInfo, 'fetch').mockResolvedValue({
      isConnected: true,
      isInternetReachable: true,
      type: 'wifi',
    });

    // Trigger network change listener
    const listeners = NetInfo.fetch.mock.calls;
    const listenerCallback = listeners[listeners.length - 1];

    await listenerCallback();

    // Verify sync triggered
    expect(offlineSyncService.isSyncInProgress()).toBe(true);
  });
});
```

### Biometric Authentication State Machine

```typescript
// Source: Based on backend property tests for state machines
import fc from 'fast-check';

describe('Biometric Authentication State Machine', () => {
  const states = ['idle', 'authenticating', 'authenticated', 'locked_out', 'error'];

  it('should never transition from locked_out to authenticating', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...states),
        fc.constantFrom(...states),
        (fromState, toState) => {
          const stateMachine = biometricService.getStateMachine();

          // Invariant: locked_out cannot transition to authenticating
          if (fromState === 'locked_out' && toState === 'authenticating') {
            const isValidTransition = stateMachine.canTransition(fromState, toState);
            expect(isValidTransition).toBe(false);
          }

          return true;
        }
      ),
      { numRuns: 50 }
    );
  });

  it('should reach authenticated state after successful authentication', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 4 }), // Attempt count (0-4)
        async (attempts) => {
          // Mock successful auth after N attempts
          jest.spyOn(LocalAuthentication, 'authenticateAsync')
            .mockResolvedValue({
              success: true,
              error: undefined,
            });

          const result = await biometricService.authenticate();

          // Invariant: Successful auth should reach authenticated state
          if (result.success) {
            const currentState = biometricService.getCurrentState();
            expect(currentState).toBe('authenticated');
          }

          return true;
        }
      ),
      { numRuns: 20 }
    );
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual mocks for each test | jest.setup.js global mocks | Expo SDK 40+ (2021) | Consistent mocks, DRY tests, easier maintenance |
| Appium for E2E | Detox grey-box testing | 2019+ | 10x faster E2E, better debugging, Expo integration |
| Example-based unit tests only | Property-based testing with FastCheck | 2020+ | Catch edge cases, shrinking, reproducible failures |
| Platform-specific test duplication | Cross-platform shared contracts | 2022+ | DRY tests, consistent behavior, easier refactoring |

**Deprecated/outdated:**
- **Enzyme for React Native:** Deprecated, use React Native Testing Library
- **Appium:** Too slow for rapid feedback, use Detox for React Native
- **jest.mock() per test file:** Move to jest.setup.js global mocks
- **Manual timer mocking:** Use Jest fake timers globally in jest.setup.js

## Open Questions

1. **Detox Expo integration complexity**
   - What we know: Detox supports Expo via detox-expo-helpers, but requires ejecting or using dev client
   - What's unclear: Complexity of Detox setup with Expo 50, whether E2E tests fit in Phase 096 timeline
   - Recommendation: Start with integration tests (React Native Testing Library), defer Detox E2E to Phase 099 (Cross-Platform E2E)

2. **Cross-platform test sharing strategy**
   - What we know: Mobile and web share TypeScript types and API contracts
   - What's unclear: How to structure shared test suite without platform-specific coupling
   - Recommendation: Create `tests/shared/` directory with contract tests, import into both mobile and web test suites

3. **FastCheck generator strategies for complex device state**
   - What we know: FastCheck provides basic arbitraries (integer, string, record)
   - What's unclear: How to generate realistic device state (location + camera + notification permissions combined)
   - Recommendation: Start with simple property tests (queue invariants, sync logic), expand to complex state generators in Phase 098 (Property Testing Expansion)

## Sources

### Primary (HIGH confidence)
- **jest-expo documentation** — Official Expo testing framework (https://docs.expo.dev/guides/testing/)
- **React Native Testing Library** — Component testing utilities (https://callstack.github.io/react-native-testing-library/)
- **FastCheck documentation** — Property-based testing for TypeScript (https://fast-check.dev/)
- **Detox documentation** — Grey-box E2E testing (https://wix.github.io/Detox/)
- **Expo Permissions Guide** — Permission handling patterns (https://docs.expo.dev/versions/latest/sdk/permissions/)
- **Existing Atom test infrastructure** — jest.config.js, jest.setup.js (522 lines of mocks), offlineSync.test.ts (507 lines)

### Secondary (MEDIUM confidence)
- **@react-native-community/netinfo** — Network state testing (https://github.com/react-native-netinfo/react-native-netinfo)
- **expo-local-authentication API** — Biometric auth patterns (https://docs.expo.dev/versions/latest/sdk/local-authentication/)
- **Backend Hypothesis property tests** — test_governance_maturity_invariants.py, test_device_tool_invariants.py (patterns to mirror)
- **Research SUMMARY.md** — Phase 096 context, mobile testing requirements (lines 105-128)

### Tertiary (LOW confidence — needs validation)
- **detox-expo-helpers** — Detox integration with Expo (limited documentation, may need prototype testing)
- **Cross-platform test sharing patterns** — Few real-world examples, may need research during planning
- **FastCheck for complex UI state** — Low adoption, limited examples for React Native (Phase 098 concern)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in mobile/package.json, official documentation
- Architecture: HIGH - Existing jest.setup.js with 522 lines of mocks, offline sync test patterns established (507 lines)
- Pitfalls: HIGH - Platform differences documented in Expo guides, React Native testing anti-patterns well-known
- FastCheck integration: MEDIUM - Backend Hypothesis patterns proven, FastCheck adoption lower in production

**Research date:** 2026-02-26
**Valid until:** 2026-03-28 (30 days - Expo SDK 50 stable, React Native 0.73 stable)

---

## Key Takeaways for Planning

1. **Jest infrastructure already configured** — jest-expo 50.0.0, 80% coverage threshold, 522-line jest.setup.js with all Expo modules mocked
2. **Offline sync test patterns exist** — 507-line test file covering queue management, sync orchestration, conflict resolution, state persistence
3. **Property test patterns mirror backend** — Use FastCheck with same invariant approach as Hypothesis tests (governance maturity, device tool invariants)
4. **Device feature mocking documented** — Expo provides official mock patterns for camera, location, notifications, biometric auth
5. **Cross-platform tests leverage shared types** — Test API contracts and data structures shared between web and mobile
6. **Detox E2E can be deferred** — Start with integration tests, add Detox in Phase 099 (Cross-Platform E2E)
