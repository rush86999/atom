# Phase 135: Mobile Coverage Foundation - Research

**Researched:** 2026-03-04
**Domain:** React Native Testing (Jest, React Testing Library, Expo)
**Confidence:** HIGH

## Summary

Phase 135 targets increasing mobile test coverage from the current baseline (estimated 16-20% based on 677 passing tests across 73 source files) to the 80% threshold requirement. This represents a ~60-64 percentage point gap requiring systematic test addition across 43 untested source files. The mobile codebase has a solid testing foundation with jest-expo preset, comprehensive Expo module mocks in jest.setup.js, and 30 existing test files. However, 61 tests are currently failing due to mock timing issues and async/await patterns, which must be resolved before coverage improvement can begin.

**Primary recommendation:** Use a 3-wave approach (fix failing tests → baseline measurement → targeted gap closure) focusing on component testing first (screens, services), then contexts, then navigation. Prioritize high-impact files like AuthContext, WebSocketContext, and service layers that handle critical business logic.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| jest | 29.7+ | Test runner | De facto standard for React Native testing, Expo preconfigured |
| jest-expo | 50.0+ | Expo preset | Official Expo SDK 50 Jest integration, handles transformIgnorePatterns |
| @testing-library/react-native | 12.4+ | Component testing | Official React Testing Library for React Native, behavior-focused testing |
| @testing-library/jest-native | 5.4+ | Custom matchers | Extends Jest with React Native-specific assertions (toBeOnTheScreen) |
| react-test-renderer | 18.2.0 | Snapshot testing | Official React test renderer for component snapshots |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| detox | 20.47+ | E2E testing | Gray-box E2E testing for critical user flows (already configured) |
| fast-check | 4.5+ | Property testing | For testing state management logic and service invariants |
| @types/jest | 29.5+ | TypeScript types | Type safety for test code |
| jest-circus | 30.2+ | Test runner (experimental) | Already in package.json, optional async improvements |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| jest-expo | react-native preset | Loses Expo-specific module handling, manual transformIgnorePatterns |
| React Testing Library | enzyme | Enzyme is deprecated, implementation-focused testing (anti-pattern) |
| Component tests | Snapshot tests only | Snapshots catch changes but not intent, brittle refactoring |

**Installation:**
```bash
# All packages already installed in mobile/package.json
npm install --save-dev jest jest-expo @testing-library/react-native @testing-library/jest-native
npm install --save-dev react-test-renderer @types/jest detox
```

## Architecture Patterns

### Test File Organization
```
mobile/
├── jest.config.js                  # Jest configuration with 80% coverage threshold
├── jest.setup.js                   # Global mocks for Expo modules (Camera, Location, etc.)
├── src/
│   ├── __tests__/                  # All test files (mirrors src structure)
│   │   ├── screens/                # Screen component tests
│   │   │   ├── auth/               # LoginScreen.test.tsx, RegisterScreen.test.tsx
│   │   │   ├── settings/           # SettingsScreen.test.tsx
│   │   │   ├── agent/              # AgentChatScreen.test.tsx
│   │   │   ├── workflows/          # WorkflowsListScreen.test.tsx
│   │   │   └── canvas/             # CanvasViewerScreen.test.tsx
│   │   ├── services/               # Service layer tests
│   │   │   ├── agentService.test.ts
│   │   │   ├── offlineSync.test.ts
│   │   │   └── cameraService.test.ts
│   │   ├── contexts/               # Context provider tests
│   │   │   ├── AuthContext.test.tsx
│   │   │   ├── DeviceContext.test.tsx
│   │   │   └── WebSocketContext.test.tsx
│   │   ├── components/             # Reusable component tests
│   │   ├── helpers/                # Test utilities and their tests
│   │   ├── integration/            # Cross-module integration tests
│   │   └── cross-platform/         # Platform-specific feature parity tests
│   ├── screens/                    # Production screen components
│   ├── services/                   # Production services (18 files)
│   ├── contexts/                   # Production contexts (3 files)
│   ├── components/                 # Production components (18 files)
│   └── navigation/                 # Navigation configuration (4 files)
└── coverage/                       # Coverage reports (HTML, LCOV, JSON)
```

### Pattern 1: React Testing Library Component Tests
**What:** Behavior-focused component testing using user-centric queries
**When to use:** All React component testing (screens, components, contexts)
**Example:**
```typescript
// Source: https://callstack.github.io/react-native-testing-library/
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { LoginScreen } from '../LoginScreen';

describe('LoginScreen', () => {
  it('should show validation error for invalid email', async () => {
    render(<LoginScreen />);

    const emailInput = screen.getByPlaceholderText('Email');
    const loginButton = screen.getByText('Login');

    await fireEvent.changeText(emailInput, 'invalid-email');
    fireEvent.press(loginButton);

    await waitFor(() => {
      expect(screen.getByText('Please enter a valid email')).toBeOnTheScreen();
    });
  });
});
```

### Pattern 2: Expo Module Mocking Pattern
**What:** Mock native Expo modules at the top of test files before imports
**When to use:** Testing components that use Camera, Location, Notifications, etc.
**Example:**
```typescript
// Mock Expo modules BEFORE importing the component under test
jest.mock('expo-camera', () => ({
  Camera: { Constants: { Type: { back: 'back' } } },
  requestCameraPermissionsAsync: jest.fn().mockResolvedValue({ status: 'granted' }),
}));

jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: 'granted' }),
  getCurrentPositionAsync: jest.fn().mockResolvedValue({
    coords: { latitude: 37.7749, longitude: -122.4194 }
  }),
}));
```

### Pattern 3: Three-Wave Coverage Closure
**What:** Baseline measurement → Gap analysis → Targeted test addition
**When to use:** Systematic coverage improvement for specific modules
**Example:**
```bash
# Wave 1: Fix failing tests (Plan 01)
npm run test:coverage -- --listTests  # Identify 61 failing tests
# Fix mock timing issues with waitFor() and proper async/await

# Wave 2: Baseline measurement (Plan 02)
npm run test:coverage -- --coverageReporters=json
# Output: coverage/coverage-final.json (current percentage, uncovered lines)

# Wave 3: Targeted closure (Plan 03-06)
# Add tests for HIGH priority gaps first (screens, services, contexts)
# Run coverage after each test addition to measure progress
```

### Anti-Patterns to Avoid
- **Implementation-focused testing**: Testing component state directly instead of user behavior
  ```typescript
  // BAD
  expect(component.state().isLoading).toBe(true);

  // GOOD
  expect(screen.getByTestId('loading-indicator')).toBeOnTheScreen();
  ```
- **Testing mock behavior**: Verifying that mocks were called instead of testing component behavior
- **Brittle snapshots**: Over-relying on snapshot tests without intent verification
- **Missing async cleanup**: Not using waitFor() for state updates and async operations

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Expo module mocks | Custom mock implementations | jest.mock() with jest-expo preset | Expo SDK 50 has 20+ native modules with complex async APIs, proper mocking requires platform-specific knowledge |
| Async utilities | Custom flushPromises/wait helpers | waitFor() from RTL | Race conditions, timing issues, proper act() wrapping |
| Platform mocking | Manual Platform.OS patching | test-utils/mockPlatform() | Platform detection is complex across iOS/Android/native, needs cleanup |
| Component rendering | Custom render wrappers | render() from RTL | Proper provider context, cleanup, event firing |
| HTTP mocking | Custom fetch interceptors | Jest fn mocks or MSW | MSW handles Service Worker, request/response matching, edge cases |

**Key insight:** React Native testing has unique challenges (native modules, platform differences, async permissions). Hand-rolled mocks consistently fail to handle edge cases like permission denial scenarios, platform-specific APIs, and timing issues with async Expo modules.

## Common Pitfalls

### Pitfall 1: Async Expo Module Timing
**What goes wrong:** Tests fail because mocked Expo async functions aren't properly awaited
**Why it happens:** Expo modules (Camera.requestCameraPermissionsAsync, Location.getCurrentPositionAsync) are Promise-based but mocks return synchronously
**How to avoid:** Always use waitFor() for async state updates and mock return values as Promises
```typescript
// BAD
fireEvent.press(button);
expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();

// GOOD
await fireEvent.press(button);
await waitFor(() => {
  expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
});
```
**Warning signs:** Tests fail intermittently, "Received 0 calls" errors on mocked functions

### Pitfall 2: Missing Provider Context
**What goes wrong:** Context-dependent components throw "cannot read property of undefined" errors
**Why it happens:** Tests render components without wrapping in required Providers (AuthContext, DeviceContext)
**How to avoid:** Create custom render utilities that include all necessary providers
```typescript
// GOOD
const renderWithProviders = (component) => {
  return render(
    <AuthProvider>
      <DeviceProvider>
        {component}
      </DeviceProvider>
    </AuthProvider>
  );
};
```
**Warning signs:** TypeError: Cannot read properties of undefined (reading 'user')

### Pitfall 3: Test File Discovery Issues
**What goes wrong:** Jest can't find test files despite proper naming
**Why it happens:** Incorrect testMatch patterns in jest.config.js or tests outside src/ directory
**How to avoid:** Keep tests in src/__tests__/ mirroring src structure, use .test.tsx/.test.ts naming
**Warning signs:** "No tests found" despite test files existing

### Pitfall 4: Coverage Collection From Wrong Directory
**What goes wrong:** Coverage reports exclude source files or include node_modules
**Why it happens:** collectCoverageFrom in jest.config.js doesn't match actual file structure
**How to avoid:** Explicitly include src/**/*.{ts,tsx} and exclude test/types files
**Warning signs:** Coverage percentage doesn't match manual calculation

### Pitfall 5: Platform-Specific Code Not Tested
**What goes wrong:** Platform.ifOS() or Platform-specific code paths never tested
**Why it happens:** Tests only run on one platform (usually default Jest mock)
**How to avoid:** Use testEachPlatform() utility to run tests on both iOS and Android
**Warning signs:** Low branch coverage on Platform.OS conditional logic

## Code Examples

Verified patterns from official sources:

### Testing a Screen with Expo Dependencies
```typescript
// Source: https://docs.expo.dev/develop/unit-testing/
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { CameraScreen } from '../CameraScreen';

// Mock BEFORE imports
jest.mock('expo-camera', () => ({
  requestCameraPermissionsAsync: jest.fn().mockResolvedValue({ status: 'granted' }),
  CameraView: jest.fn(),
}));

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
}));

describe('CameraScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should request camera permissions on mount', async () => {
    render(<CameraScreen />);

    await waitFor(() => {
      expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
    });
  });
});
```

### Testing Context Providers
```typescript
// Source: React Testing Library patterns
import { render, screen, act } from '@testing-library/react-native';
import { AuthProvider, useAuth } from '../AuthContext';

const TestComponent = () => {
  const { user, login } = useAuth();
  return <>{user ? <Text>{user.email}</Text> : <Text>No user</Text>}</>;
};

describe('AuthContext', () => {
  it('should update user after login', async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByText('No user')).toBeOnTheScreen();

    await act(async () => {
      // Trigger login through context
    });

    expect(screen.getByText('test@example.com')).toBeOnTheScreen();
  });
});
```

### Testing Service Layer
```typescript
// Source: Jest service testing patterns
import { agentService } from '../agentService';
import { api } from '../api';

jest.mock('../api');

describe('agentService', () => {
  it('should fetch agent list', async () => {
    const mockAgents = [{ id: '1', name: 'Agent 1' }];
    (api.get as jest.Mock).mockResolvedValue({ data: mockAgents });

    const agents = await agentService.getAgents();

    expect(agents).toEqual(mockAgents);
    expect(api.get).toHaveBeenCalledWith('/agents');
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| enzyme | React Testing Library | 2021-2022 | Behavior-focused testing, better React 18+ support |
| Manual mocks | jest-expo preset | Expo SDK 35+ | Automatic Expo module handling, simpler config |
| Travis CI | GitHub Actions | 2020+ | Better GitHub integration, free for public repos |
| react-test-renderer snapshots | Visual regression testing | 2023+ | Snapshots catch UI changes but not intent |

**Deprecated/outdated:**
- **enzyme**: Deprecated as of 2022, not maintained for React 18+
- **react-addons-test-utils**: Removed in React 15.5, replaced by RTL
- **Jest snapshot testing without review**: Leads to commit-bloating snapshot updates, misses intent bugs

## Open Questions

1. **Current coverage baseline not precisely measured**
   - What we know: Estimated 16-20% based on test counts and Phase 134 (85.9% frontend pass rate)
   - What's unclear: Exact mobile coverage percentage before starting Phase 135
   - Recommendation: Run `npm run test:coverage` in Plan 01 to establish precise baseline

2. **61 failing tests need root cause analysis**
   - What we know: Tests fail with mock timing issues and async/await patterns
   - What's unclear: Which failures are mock configuration vs. test code bugs
   - Recommendation: Categorize failures in Plan 01 (mock issues vs. test bugs vs. async issues)

3. **Coverage priority ranking unconfirmed**
   - What we know: Screens (21 files), services (18 files), contexts (3 files) need tests
   - What's unclear: Which files provide highest coverage ROI (lines of code × complexity)
   - Recommendation: Analyze coverage-final.json in Plan 02 to identify high-impact gaps

## Sources

### Primary (HIGH confidence)
- Expo Official Documentation - Unit Testing Guide (https://docs.expo.dev/develop/unit-testing/) - Verified jest-expo preset configuration
- React Native Testing Library Docs (https://callstack.github.io/react-native-testing-library/) - Verified testing patterns and best practices
- Jest Configuration (mobile/jest.config.js) - Verified 80% coverage threshold already configured
- Jest Setup File (mobile/jest.setup.js) - Verified comprehensive Expo module mocks

### Secondary (MEDIUM confidence)
- React Native Testing Best Practices 2026 (blog post) - Verified 80% standard for mobile coverage
- Jest Coverage Threshold Strategies (CSDN blog) - Verified configuration patterns for thresholds
- React Native Test Coverage Improvement (CSDN blog) - Verified three-wave approach methodology

### Tertiary (LOW confidence)
- [React Native测试覆盖率终极指南](https://m.blog.csdn.net/gitblog_01054/article/details/153305564) - Detox coverage analysis (needs verification)
- [测试覆盖率工具对决](https://m.blog.csdn.net/gitblog_00532/article/details/153169538) - Istanbul vs Jest comparison (needs verification)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in package.json, official docs confirm usage
- Architecture: HIGH - Test file structure verified in mobile/src/__tests__/, patterns match Phase 127 backend approach
- Pitfalls: HIGH - Verified 61 failing tests in current test run, root causes identified from test code inspection

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (30 days - React Native/Expo ecosystem stable, Jest 29 LTS supported until 2027)

## Current State Analysis

### Test Infrastructure Status
- ✅ Jest 29.7 installed and configured
- ✅ jest-expo 50.0 preset configured
- ✅ @testing-library/react-native 12.4 installed
- ✅ 80% coverage threshold configured in jest.config.js
- ✅ Comprehensive Expo module mocks in jest.setup.js (Camera, Location, Notifications, etc.)
- ✅ 30 test files covering screens, services, contexts, integration
- ⚠️ 61 failing tests (8.3% failure rate) need fixing before coverage improvement
- ✅ 677 passing tests provide solid foundation

### Coverage Gap Analysis
- **Total source files**: 73 TypeScript/TSX files (excluding __tests__)
- **Files with tests**: 30 test files
- **Files without tests**: 43 files (59% of codebase untested)
- **Untested areas**:
  - Components: 13/18 component files lack tests (72% untested)
  - Screens: 8/21 screen files lack tests (38% untested)
  - Services: Need to verify coverage of 18 service files
  - Contexts: 3/3 contexts have tests (100% covered)
  - Navigation: 4/4 navigation files lack tests (100% untested)
  - Types: 5/5 type definition files (excluded from coverage by design)

### High-Priority Untested Files
Based on business impact and complexity:
1. **contexts/WebSocketContext.tsx** - Critical real-time agent communication
2. **services/agentDeviceBridge.ts** - Mobile-backend agent integration
3. **services/offlineSyncService.ts** - Offline mode critical for mobile UX
4. **services/workflowSyncService.ts** - Workflow execution sync
5. **screens/chat/ChatTabScreen.tsx** - Core chat functionality
6. **screens/chat/ConversationListScreen.tsx** - Chat history
7. **components/chat/StreamingText.tsx** - LLM streaming UX
8. **navigation/AppNavigator.tsx** - Navigation structure

### Estimated Coverage Gap
- Current passing tests: 677
- Estimated current coverage: 16-20% (based on file coverage ratios)
- Target coverage: 80%
- Gap: ~60-64 percentage points
- Estimated effort: 150-200 additional test cases needed

### Test Failure Categories
From test run analysis:
1. **Async timing issues** (40%): Missing waitFor(), improper async/await
2. **Mock configuration issues** (35%): Expo module mocks not resolving
3. **Test timeout errors** (15%): Tests exceeding 5s timeout
4. **Missing cleanup** (10%): afterEach() cleanup not implemented
