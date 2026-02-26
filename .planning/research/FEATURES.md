# Feature Landscape

**Domain:** Frontend/Mobile/Desktop Integration & Property-Based Testing
**Researched:** February 26, 2026
**Overall confidence:** MEDIUM

## Executive Summary

Integration testing and property-based testing for frontend (Next.js), mobile (React Native), and desktop (Tauri) applications require different approaches than backend testing. While the backend has comprehensive Hypothesis-based property tests, frontend/mobile/desktop testing focuses on component integration, state consistency, API contracts, UI predictability, and platform-specific features (camera, location, filesystem). Based on analysis of the Atom codebase, industry patterns, and existing backend test infrastructure, this document outlines table stakes features, differentiators, and anti-features for v4.0 platform integration testing.

**Key Findings:**
- **Frontend integration testing**: Component-level testing with React Testing Library + Jest is standard (40% pass rate currently, needs improvement)
- **Mobile testing**: React Native Testing Library with device-specific mocks (camera, location, biometrics) required for comprehensive coverage
- **Desktop testing**: Tauri requires native module mocking and cross-platform validation (Windows/macOS/Linux)
- **Property-based testing**: fast-check for TypeScript/JavaScript frontend state invariants, not widely adopted in production yet
- **API contract testing**: Existing backend property tests provide good foundation, frontend needs contract validation
- **Gap analysis**: No property-based tests exist for frontend/mobile/desktop, 21/35 frontend tests failing, mobile tests lack property-based invariants

## Table Stakes

Features users expect in any frontend/mobile/desktop testing system. Missing = product feels incomplete or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Component Integration Tests** | Verify components work together with state management, API calls, routing | Low | React Testing Library for Next.js, React Native Testing Library for mobile |
| **API Contract Validation** | Frontend must correctly call backend APIs and handle responses | Medium | Test request/response shapes, error handling, timeout scenarios |
| **State Management Consistency** | Redux/Zustand/Context state must be predictable and consistent | Medium | Test state updates, selectors, async actions, middleware |
| **Form Validation & Submission** | Forms must validate correctly and submit data to backend | Low | Test validation rules, error display, success/error states |
| **Navigation & Routing** | Users must navigate between screens/pages correctly | Low | Test routing, navigation params, deep links, back navigation |
| **Authentication Flow** | Login/register/logout must work correctly with token storage | Medium | Test auth flows, token refresh, session persistence, biometric auth |
| **Offline Data Sync** | Mobile/desktop must handle offline mode gracefully | High | Test offline queue, sync on reconnect, conflict resolution |
| **Device Feature Mocking** | Camera, location, notifications must work across platforms | Medium | Mock Expo modules, device APIs, test permissions |
| **Error Boundary Handling** | React error boundaries must catch errors gracefully | Low | Test error boundaries, fallback UI, error logging |
| **Responsive Layout** | UI must work across screen sizes (mobile, tablet, desktop) | Medium | Test breakpoints, responsive components, orientation changes |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Property-Based State Testing** | Use fast-check to generate random state transitions and verify invariants | High | State machines, Redux reducers, context providers should maintain invariants |
| **Visual Regression Testing** | Detect unintended UI changes across releases | Medium | Percy, Chromatic, or Playwright screenshots |
| **Cross-Platform Consistency** | Verify feature parity across web/mobile/desktop | High | Same tests run on multiple platforms, validate consistent behavior |
| **Performance Regression Tests** | Detect rendering performance degradation | Medium | Lighthouse CI, render time budgets, bundle size tracking |
| **Accessibility Testing** | Ensure WCAG compliance with automated tests | Medium | jest-axe, aria labels, keyboard navigation, screen reader tests |
| **Network Failure Simulation** | Test app behavior under poor network conditions | Medium | Mock slow networks, offline mode, retry logic, timeout handling |
| **End-to-End User Flows** | Test complete workflows from UI to backend | High | Playwright for web, Detox for mobile,跨组件集成测试 |
| **Mutation Testing** | Verify test quality by mutating code | Medium | StrykerJS for frontend, ensures tests catch bugs |
| **Component Contract Tests** | Verify props, events, and behavior contracts | Medium | Test component API, prop validation, event callbacks |
| **State Snapshot Testing** | Detect unintended state shape changes | Low | Immutable state snapshots,Redux store serialization |
| **Memory Leak Detection** | Find memory leaks in long-running sessions | High | Test component unmount, cleanup, subscription disposal |
| **Internationalization Testing** | Verify UI works across languages/locales | Medium | Test translations, date/currency formatting, RTL languages |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Testing Implementation Details** | Tests break on refactoring, become brittle | Test user behavior and component contracts, not internal state |
| **Flaky Async Tests** | Non-deterministic test failures destroy trust | Use proper async/await, waitFor, fake timers, mock timers consistently |
| **Over-Mocking External Libraries** | Tests mock too much, don't validate real behavior | Only mock network, device APIs, time - test real component logic |
| **Brittle Selector Tests** | CSS classes change, tests break | Use data-testid attributes for stable selectors |
| **Testing Third-Party Libraries** | Don't test what library authors test | Trust React, Next.js, React Native - test your code only |
| **Shared State Between Tests** | Tests interfere with each other, flaky failures | Isolate test data, cleanup after each test, use fixtures |
| **Hardcoded Test Data** | Doesn't test edge cases, misses bugs | Use property-based testing, fuzzing, data generators |
| **Missing Error Path Tests** | Only testing happy path misses critical bugs | Test 401, 500, network errors, malformed responses |
| **Testing Browser APIs Directly** | Different browsers behave differently | Use jsdom for tests, Playwright for real browser validation |
| **E2E Tests for Everything** | Slow, brittle, expensive | Use component tests for speed, E2E for critical paths only |

## Feature Dependencies

```
Component Integration Tests → API Contract Validation (need components to call APIs)
API Contract Validation → Offline Data Sync (need API calls to queue offline)
State Management Consistency → Property-Based State Testing (state must exist first)
Device Feature Mocking → Offline Data Sync (need device APIs to test)
Authentication Flow → State Management Consistency (auth state drives other features)
Property-Based State Testing → Cross-Platform Consistency (invariants should hold everywhere)
```

## MVP Recommendation

**Prioritize for v4.0:**

### 1. Frontend Integration Testing (High Priority)
- Fix 21 failing frontend tests (40% → 100% pass rate)
- Add API contract tests for all backend endpoints
- Add state management tests (Redux/Zustand/Context)
- Add form validation and submission tests
- Add navigation and routing tests
- Add authentication flow tests
- **Target**: 80%+ test coverage, <2min test runtime

### 2. Mobile Integration Testing (High Priority)
- Add device feature mocks (camera, location, biometrics, notifications)
- Add offline sync tests (queue, retry, conflict resolution)
- Add platform permission tests (iOS vs Android differences)
- Add React Native component integration tests
- Add cross-platform consistency tests
- **Target**: 70%+ test coverage, support iOS 13+, Android 8+

### 3. Desktop Integration Testing (Medium Priority)
- Add Tauri native module mocks (filesystem, system APIs)
- Add cross-platform tests (Windows/macOS/Linux)
- Add desktop-specific feature tests (menu bar, notifications, auto-updates)
- Add desktop-backend integration tests
- **Target**: 60%+ test coverage, cross-platform validation

### 4. Property-Based Testing (Medium Priority)
- **Frontend State Invariants**: fast-check for Redux reducers, context providers, state machines
- **Component Contract Tests**: Props validation, event callbacks, ref forwarding
- **API Contract Tests**: Request/response shape validation with fast-check generators
- **Data Transformation Invariants**: Sorting, filtering, pagination with random inputs
- **Target**: 20-30 property tests covering critical state invariants

### 5. Advanced Testing (Low Priority - Defer to v4.1+)
- Visual regression testing (Percy/Chromatic)
- Performance regression tests (Lighthouse CI)
- Accessibility testing (jest-axe)
- Mutation testing (StrykerJS)
- Memory leak detection
- E2E tests with Playwright/Detox

**Defer to Future Releases:**
- Visual regression testing (requires screenshot infrastructure)
- Performance regression testing (requires performance budgets)
- Mutation testing (requires baseline test quality)
- E2E testing infrastructure (requires test environment setup)

## Complexity Assessment

| Area | Complexity | Why |
|------|------------|-----|
| Component Integration Tests | **Low** | React Testing Library well-documented, straightforward patterns |
| API Contract Tests | **Medium** | Need to mock fetch, handle async, validate response shapes |
| State Management Tests | **Medium** | Redux/reducer logic, async actions, middleware, selectors |
| Form Validation | **Low** | Straightforward validation rules, user input simulation |
| Device Feature Mocking | **High** | Platform-specific APIs, iOS vs Android differences, permissions |
| Offline Sync | **High** | Queue management, retry logic, conflict resolution, sync orchestration |
| Property-Based Testing | **Medium** | fast-check learning curve, invariant identification, generator design |
| Cross-Platform Testing | **High** | Different platforms, inconsistent APIs, environment-specific code |
| Visual Regression | **Medium** | Screenshot infrastructure, image diffing, baseline management |
| Performance Testing | **Medium** | Lighthouse setup, performance budgets, CI integration |
| Accessibility Testing | **Low** | jest-axe straightforward, aria validation simple |
| Mutation Testing | **Low** | StrykerJS setup easy, but requires good baseline tests |

## Integration with Existing Atom Architecture

**Existing Infrastructure to Leverage:**

1. **Backend Property-Based Testing Framework** ✅
   - `backend/tests/property_tests/` has comprehensive Hypothesis tests
   - Test patterns: `@given`, `@settings`, `st.*` strategies
   - Reuse patterns for frontend property tests with fast-check
   - Example: `test_governance_maturity_invariants.py` (1,205 lines) shows property test structure

2. **Frontend Test Infrastructure** ✅
   - Jest + React Testing Library configured
   - Test scripts: `npm test`, `npm run test:coverage`, `npm run test:ci`
   - Test setup: `tests/setup.ts` with mocks for React contexts
   - Current baseline: 35 tests, 14 passing (40% pass rate)

3. **Mobile Test Infrastructure** ✅
   - React Native Testing Library for component tests
   - Jest configured with mobile-specific mocks
   - Test files in `mobile/src/__tests__/` (20+ test files)
   - Existing mocks: Expo modules, device APIs, AsyncStorage

4. **CI/CD Pipeline** ✅
   - GitHub Actions workflows for smoke, property, fuzz, mutation tests
   - Coverage thresholds: >80% target
   - Test runtimes: <2min for property tests
   - Parallel test execution support

**New Components Needed:**

1. **Frontend Property Tests** (`frontend-nextjs/tests/property/`)
   - `testStateInvariants.ts` - Redux/context state consistency with fast-check
   - `testComponentContracts.ts` - Props validation, event callbacks
   - `testAPIContracts.ts` - Request/response shape validation
   - `testDataTransformations.ts` - Sorting, filtering, pagination

2. **Mobile Integration Tests** (`mobile/src/__tests__/integration/`)
   - `testOfflineSync.test.ts` - Offline queue, sync, conflict resolution
   - `testDeviceFeatures.test.ts` - Camera, location, biometrics, notifications
   - `testPlatformPermissions.test.ts` - iOS vs Android permission differences
   - `testCrossPlatform.test.ts` - Consistent behavior across platforms

3. **Desktop Integration Tests** (`desktop/src/tests/`)
   - `testTauriAPI.test.ts` - Native module mocking, system APIs
   - `testCrossPlatform.test.ts` - Windows/macOS/Linux differences
   - `testDesktopFeatures.test.ts` - Menu bar, notifications, auto-updates

4. **Test Utilities**
   - `frontend-nextjs/tests/utils/testHelpers.ts` - Custom render, waitFor enhancements
   - `mobile/src/__tests__/helpers/deviceMocks.ts` - Expo module mocks
   - `backend/tests/contract_tests/api_contracts.py` - OpenAPI contract validation

## Test Coverage Targets

| Area | Target Coverage | Priority | Rationale |
|------|----------------|----------|-----------|
| **Frontend Components** | 80%+ | High | Critical UI paths, user interactions |
| **Frontend State Management** | 90%+ | High | State bugs affect entire app |
| **Frontend API Integration** | 85%+ | High | API contracts prevent integration bugs |
| **Mobile Components** | 75%+ | High | Mobile-specific UI patterns |
| **Mobile Device Features** | 70%+ | Medium | Device APIs harder to test |
| **Mobile Offline Sync** | 85%+ | High | Offline bugs cause data loss |
| **Desktop Components** | 65%+ | Medium | Desktop shares code with web |
| **Desktop Native APIs** | 60%+ | Low | Platform-specific, lower usage |
| **Property Tests (State)** | 20-30 tests | Medium | Focus on critical invariants |
| **Property Tests (API)** | 15-20 tests | Medium | Contract validation |
| **E2E Tests** | 10-15 flows | Low | Only critical user workflows |

## Existing Atom Test Infrastructure

**Already Implemented (from codebase analysis):**

### Backend Property Tests (Comprehensive)
1. **Governance Maturity Invariants** (1,205 lines)
   - Permission matrix completeness (all role-action combos defined)
   - Maturity gate enforcement (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
   - Action complexity mapping (1-4 levels)
   - RBAC verification (role-based access control)
   - Cache consistency (governance cache maintains correctness)
   - Confidence score transitions (boundary values: 0.5, 0.7, 0.9)

2. **Financial Invariants** (814 lines)
   - Cost leak detection, budget guardrails
   - Invoice reconciliation, multi-currency handling
   - Tax calculations, net worth calculations
   - Revenue recognition, invoice aging

3. **Database CRUD Invariants** (150+ lines)
   - CRUD behavior (create, read, update, delete)
   - Foreign key constraints, unique constraints
   - Transaction atomicity, cascade behaviors

4. **AI Accounting Invariants** (705 lines)
   - Transaction ingestion, categorization
   - Confidence scoring thresholds (0.85 = auto-post)
   - Audit trail integrity, ledger integration

**Key Patterns to Follow:**
```python
# From test_governance_maturity_invariants.py
@given(
    agent_status=st.sampled_from([
        AgentStatus.STUDENT,
        AgentStatus.INTERN,
        AgentStatus.SUPERVISED,
        AgentStatus.AUTONOMOUS
    ]),
    action_type=st.sampled_from([
        "present_chart", "stream_chat", "submit_form", "delete"
    ])
)
@settings(max_examples=200, deadline=None)
def test_maturity_gate_enforcement(self, db_session, agent_status, action_type):
    """
    INVARIANT: Maturity gates enforce action complexity restrictions.

    Tests that:
    - STUDENT agents can only do complexity 1 actions
    - INTERN agents can do complexity 1-2 actions
    - SUPERVISED agents can do complexity 1-3 actions
    - AUTONOMOUS agents can do all actions (1-4)
    """
    # Test implementation...
```

### Frontend Tests (Baseline Established)
1. **Test Infrastructure** ✅
   - Jest + React Testing Library configured
   - Module resolution fixed (@/ imports working)
   - React contexts mocked (useToast, AgentAudioControlProvider, WakeWordProvider)
   - Test scripts: test, test:watch, test:coverage, test:ci

2. **Current Tests** (35 tests, 14 passing)
   - AgentManager tests (10 tests, 1 passing - needs fixes)
   - VoiceCommands tests (3 tests, 0 passing)
   - WhatsAppBusinessIntegration tests (21 tests, 13 passing)
   - Issues: Missing props, test expectations don't match implementation

3. **Test Configuration** ✅
   - `jest.config.js`: Module resolution, transform, coverage collection
   - `tests/setup.ts`: Global mocks, test environment setup
   - `package.json`: Test scripts, dependencies (@testing-library/*)

### Mobile Tests (React Native)
1. **Test Files** (20+ test files)
   - `agentService.test.ts` - Agent API communication
   - `cameraService.test.ts` - Camera feature testing
   - `locationService.test.ts` - Geolocation testing
   - `storageService.test.ts` - AsyncStorage persistence
   - `notificationService.test.ts` - Push notifications
   - Screen tests: AgentChatScreen, CanvasViewerScreen, SettingsScreen
   - Context tests: AuthContext, DeviceContext, BiometricAuth

2. **Test Infrastructure** ✅
   - Jest configured for React Native
   - Mock helpers: `mockExpoModules.ts`, `testUtils.ts`
   - Platform mocks: Expo modules, device APIs
   - AsyncStorage mock for persistence tests

## Platform-Specific Considerations

### Frontend (Next.js + React)
**Testing Challenges:**
- Server Components vs Client Components (Next.js 13+ App Router)
- Streaming and Suspense boundaries
- API routes integration
- Authentication sessions
- File uploads/downloads

**Recommended Tools:**
- **Jest** - Test runner (already configured)
- **React Testing Library** - Component testing
- **MSW (Mock Service Worker)** - API mocking
- **Playwright** - E2E testing (for critical flows)
- **fast-check** - Property-based testing

**Test Patterns:**
```typescript
// Example: API contract test with MSW
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/agents', (req, res, ctx) => {
    return res(ctx.json({ agents: [] }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test('fetches agents from API', async () => {
  const { result } = renderHook(() => useAgents());
  await waitFor(() => expect(result.current.agents).toEqual([]));
});
```

### Mobile (React Native + Expo)
**Testing Challenges:**
- Platform-specific APIs (iOS vs Android)
- Device permissions (camera, location, notifications)
- Biometric authentication (Face ID/Touch ID)
- Offline mode and network switching
- Deep linking and app state transitions

**Recommended Tools:**
- **Jest** - Test runner (already configured)
- **React Native Testing Library** - Component testing
- **expo-mock** - Expo module mocking
- **Detox** - E2E testing (gray-box)
- **react-native-network_logger** - Network debugging

**Test Patterns:**
```typescript
// Example: Device feature mock
import * as ImagePicker from 'expo-image-picker';

jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(),
  MediaTypeOptions: {
    Images: 'images',
  },
}));

test('picks image from gallery', async () => {
  (ImagePicker.launchImageLibraryAsync as jest.Mock).mockResolvedValue({
    canceled: false,
    assets: [{ uri: 'file://image.jpg' }],
  });

  await pickImage();
  expect(ImagePicker.launchImageLibraryAsync).toHaveBeenCalled();
});
```

### Desktop (Tauri + Rust)
**Testing Challenges:**
- Native module mocking (filesystem, system APIs)
- Cross-platform differences (Windows/macOS/Linux)
- Tauri invoke/bridge communication
- Desktop-specific features (menu bar, notifications, auto-updates)

**Recommended Tools:**
- **Jest** - Test runner (reuse frontend config)
- **React Testing Library** - Component testing (same as web)
- **Tauri API Mocks** - Mock @tauri-apps/plugin-* modules
- **Spectron** (deprecated) or Playwright - E2E testing

**Test Patterns:**
```typescript
// Example: Tauri API mock
import { invoke } from '@tauri-apps/api/tauri';

jest.mock('@tauri-apps/api/tauri', () => ({
  invoke: jest.fn(),
}));

test('reads file from disk', async () => {
  (invoke as jest.Mock).mockResolvedValue('file content');

  const content = await readFile('test.txt');
  expect(content).toBe('file content');
  expect(invoke).toHaveBeenCalledWith('read_file', { path: 'test.txt' });
});
```

## Property-Based Testing Strategy

### Why Property-Based Testing for Frontend/Mobile/Desktop?

**Traditional example-based tests:**
```typescript
test('sorts agents by name', () => {
  const agents = [
    { name: 'Charlie' },
    { name: 'Alice' },
    { name: 'Bob' },
  ];
  const sorted = sortAgents(agents);
  expect(sorted[0].name).toBe('Alice');
  expect(sorted[1].name).toBe('Bob');
  expect(sorted[2].name).toBe('Charlie');
});
```

**Property-based tests (fast-check):**
```typescript
import fc from 'fast-check';

test('sorts agents by name (property-based)', () => {
  fc.assert(
    fc.property(
      fc.array(fc.record({ name: fc.string() })),
      (agents) => {
        const sorted = sortAgents(agents);

        // Property: Sorted list is always same length as input
        expect(sorted.length).toBe(agents.length);

        // Property: Sorted list contains same elements as input
        expect(sorted.sort()).toEqual(agents.sort());

        // Property: Each element is <= next element
        for (let i = 0; i < sorted.length - 1; i++) {
          expect(sorted[i].name <= sorted[i + 1].name).toBe(true);
        }
      }
    )
  );
});
```

### Critical Invariants to Test

**1. State Management Invariants**
- Redux reducer purity: Same input → same output
- State immutability: No mutations, always return new objects
- Selector consistency: Same state → same selected value
- Middleware order: Applied in correct sequence

**2. Component Contract Invariants**
- Props validation: Required props always provided
- Event callbacks: Called with correct arguments
- Ref forwarding: Refs attached to correct DOM elements
- Context values: All consumers receive same context value

**3. API Contract Invariants**
- Request serialization: Request body matches API schema
- Response deserialization: Response matches expected types
- Error handling: All error paths handled gracefully
- Idempotency: Duplicate requests handled correctly

**4. Data Transformation Invariants**
- Sorting: Output is always sorted
- Filtering: Output is subset of input
- Pagination: Total count consistent across pages
- Searching: Search term appears in results

**5. UI Invariants**
- Accessibility: All interactive elements are accessible
- Responsiveness: Layout works at all breakpoints
- Performance: Render time < 16ms (60fps)
- Consistency: Same props → same rendered output

### Recommended Property Tests (v4.0 MVP)

**Priority 1: State Management (10 tests)**
- Reducer purity and immutability
- Selector consistency
- Middleware execution order
- Context provider values
- State hydration/dehydration

**Priority 2: API Contracts (8 tests)**
- Request body serialization
- Response shape validation
- Error response handling
- Timeout/retry logic

**Priority 3: Data Transformations (7 tests)**
- Sorting algorithms
- Filtering/pagination
- Search relevance
- Data aggregation

**Priority 4: Component Contracts (5 tests)**
- Props validation
- Event callback signatures
- Ref forwarding
- Context propagation

**Total: 30 property tests for v4.0**

## Integration Testing Strategy

### Frontend Integration Tests

**Component Integration (What to Test):**
1. **Component + State Management**
   - Component reads from Redux/Zustand store
   - Component dispatches actions
   - State updates trigger re-renders

2. **Component + API Layer**
   - Component fetches data on mount
   - Loading/error/success states
   - Retry/refetch logic

3. **Component + Routing**
   - Navigation between pages
   - Route params passed correctly
   - Deep links work correctly

4. **Component + Forms**
   - Form validation
   - Error display
   - Submission to API

**Test Pattern: Component + State + API**
```typescript
test('agent list fetches on mount and displays agents', async () => {
  // Mock API response
  mockAPI.getAgents.mockResolvedValue({
    agents: [
      { id: '1', name: 'Agent 1', maturity: 'AUTONOMOUS' },
    ],
  });

  // Render component
  render(<AgentList />);

  // Verify loading state
  expect(screen.getByText('Loading...')).toBeInTheDocument();

  // Wait for API call
  await waitFor(() => expect(mockAPI.getAgents).toHaveBeenCalled());

  // Verify agents displayed
  expect(screen.getByText('Agent 1')).toBeInTheDocument();
});
```

### Mobile Integration Tests

**Device Feature Integration (What to Test):**
1. **Camera Integration**
   - Permission request
   - Image capture
   - Image upload to backend

2. **Location Integration**
   - Permission request
   - Location fetch
   - Location updates
   - Geofencing

3. **Biometric Authentication**
   - Face ID/Touch ID availability
   - Authentication success/failure
   - Fallback to PIN

4. **Push Notifications**
   - Permission request
   - Notification receipt
   - Notification tap handling

5. **Offline Sync**
   - Queue requests when offline
   - Sync when online
   - Conflict resolution

**Test Pattern: Offline Sync**
```typescript
test('queues agent message when offline', async () => {
  // Mock offline network
  NetInfo.fetch.mockResolvedValue({ isInternetReachable: false });

  // Send message
  await agentService.sendMessage('agent-1', 'test message');

  // Verify queued (not sent)
  expect(AsyncStorage.setItem).toHaveBeenCalledWith(
    'offline_queue',
    expect.arrayContaining([
      expect.objectContaining({
        type: 'SEND_MESSAGE',
        agentId: 'agent-1',
        message: 'test message',
      }),
    ])
  );
});

test('syncs queued messages when online', async () => {
  // Mock offline queue
  AsyncStorage.getItem.mockResolvedValue(JSON.stringify([
    { type: 'SEND_MESSAGE', agentId: 'agent-1', message: 'queued' },
  ]));

  // Mock online network
  NetInfo.fetch.mockResolvedValue({ isInternetReachable: true });

  // Trigger sync
  await offlineSyncService.sync();

  // Verify API called
  expect(apiService.sendMessage).toHaveBeenCalledWith('agent-1', 'queued');

  // Verify queue cleared
  expect(AsyncStorage.setItem).toHaveBeenCalledWith('offline_queue', '[]');
});
```

### Desktop Integration Tests

**Tauri Integration (What to Test):**
1. **Filesystem Access**
   - File picker dialog
   - File read/write
   - Directory traversal

2. **System Integration**
   - Menu bar actions
   - System notifications
   - Auto-update checks

3. **Cross-Platform Behavior**
   - Same feature works on Windows/macOS/Linux
   - Platform-specific code paths tested

**Test Pattern: Tauri File Read**
```typescript
test('reads file from filesystem', async () => {
  // Mock Tauri invoke
  (invoke as jest.Mock).mockResolvedValue('file content');

  // Call file read
  const content = await readFile('/path/to/file.txt');

  // Verify result
  expect(content).toBe('file content');

  // Verify Tauri API called
  expect(invoke).toHaveBeenCalledWith('read_file', {
    path: '/path/to/file.txt',
  });
});
```

## Cross-Platform Consistency Tests

**Goal:** Verify feature parity across web/mobile/desktop

**Strategy:**
1. **Shared Test Suite**
   - Write tests once, run on all platforms
   - Use conditional imports for platform-specific code
   - Assert same behavior across platforms

2. **Platform Matrix**
   - Test combinations: web (Chrome/Safari), mobile (iOS/Android), desktop (macOS/Windows/Linux)
   - Validate consistent API responses
   - Validate consistent UI behavior

3. **Feature Flags**
   - Test features enabled/disabled per platform
   - Validate fallback behavior for unsupported features

**Test Pattern: Cross-Platform**
```typescript
// test: shared/agentList.test.ts
describe('AgentList (cross-platform)', () => {
  test('displays agents on all platforms', async () => {
    // Mock API (same for all platforms)
    mockAPI.getAgents.mockResolvedValue({
      agents: [
        { id: '1', name: 'Agent 1' },
      ],
    });

    // Render platform-specific component
    const Component = Platform.select({
      web: () => render(<WebAgentList />),
      ios: () => render(<MobileAgentList />),
      android: () => render(<MobileAgentList />),
      desktop: () => render(<DesktopAgentList />),
    });

    const { getByText } = Component();

    // Assert same behavior
    await waitFor(() => {
      expect(getByText('Agent 1')).toBeInTheDocument();
    });
  });
});
```

## Test Execution Strategy

### Local Development
- **Fast feedback**: Run only changed tests (`jest --onlyChanged`)
- **Watch mode**: Re-run tests on file change (`jest --watch`)
- **Coverage**: Generate coverage reports (`jest --coverage`)

### CI/CD Pipeline
- **Parallel execution**: Run frontend/mobile/desktop tests in parallel
- **Test splitting**: Split test suites by platform for faster feedback
- **Flaky test detection**: Retry failed tests, mark as flaky
- **Coverage thresholds**: Fail PR if coverage drops

### Test Stages
1. **Smoke Tests** (< 30s)
   - Critical paths only
   - Block PR if failing

2. **Integration Tests** (< 5min)
   - Component integration tests
   - API contract tests
   - Block deployment if failing

3. **Property Tests** (< 2min)
   - Fast-check property tests
   - Run on every commit

4. **E2E Tests** (< 15min)
   - Critical user workflows
   - Run on merge to main

## Quality Gates

**Must Pass Before Merge:**
- All smoke tests passing
- 80%+ code coverage
- No flaky tests
- Property tests passing
- API contracts validated

**Must Pass Before Deployment:**
- All integration tests passing
- Cross-platform consistency validated
- E2E tests passing
- Performance budgets met
- Accessibility checks passing

## Sources

### High Confidence (Official Documentation)
- **React Testing Library** - Component testing patterns, queries, async utilities
- **fast-check** - Property-based testing for TypeScript/JavaScript
- **React Native Testing Library** - React Native component testing
- **Jest** - Test runner configuration, mocking, async testing
- **MSW (Mock Service Worker)** - API mocking for integration tests
- **Tauri Testing** - Desktop application testing patterns

### Medium Confidence (Codebase Analysis)
- **Atom Backend Property Tests** - 1,205 lines of governance maturity tests showing Hypothesis patterns
- **Atom Frontend Tests** - 35 tests with 40% pass rate, showing baseline infrastructure
- **Atom Mobile Tests** - 20+ test files covering device features, services, screens
- **Atom Test Configuration** - Jest configs, setup files, test scripts

### Low Confidence (WebSearch Only - Needs Verification)
- **Property-based testing for React** - Limited adoption, few production examples
- **Cross-platform testing patterns** - Platform-specific differences hard to generalize
- **Visual regression testing** - Multiple tools (Percy, Chromatic), unclear best practices
- **Mobile testing patterns** - Detox vs Appium debate, unclear winner
- **Desktop testing patterns** - Tauri testing less documented than web/mobile

### Gaps Identified
- **Property-based testing for frontend** - fast-check adoption is low, few real-world examples
- **Cross-platform consistency** - Limited patterns for shared test suites
- **Tauri testing best practices** - Less documentation than web/mobile
- **Visual regression testing** - Tool fragmentation, unclear industry standards
- **Performance regression testing** - Lighthouse CI patterns still evolving

**Next Research Phases:**
- Phase-specific research needed for property-based test design (which invariants matter most)
- Investigation into fast-check generator strategies for complex UI state
- Deep dive on cross-platform test sharing patterns
- Research on Tauri native module mocking strategies
- Investigation into visual regression testing infrastructure

---

*Feature research for: Atom v4.0 Platform Integration & Property-Based Testing*
*Researched: February 26, 2026*
*Confidence: MEDIUM (mix of official docs, codebase analysis, and limited WebSearch verification)*
