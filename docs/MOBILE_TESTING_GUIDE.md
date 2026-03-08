# Mobile Testing Guide

**Platform:** React Native (Expo SDK 50)
**Frameworks:** jest-expo, React Native Testing Library
**Target:** 50%+ coverage across all mobile modules
**Last Updated:** March 7, 2026

---

## Overview

This guide covers mobile testing patterns for Atom's React Native app using Expo SDK 50. Mobile testing uses jest-expo (Jest preset for Expo) and React Native Testing Library (RNTL) for component testing, with platform-specific considerations for iOS and Android devices.

**Key differences from frontend testing:**
- **Platform APIs:** Native modules (expo-camera, expo-location, expo-notifications) require mocking
- **Platform-specific rendering:** iOS vs Android differences (SafeArea, StatusBar, navigation)
- **Device capabilities:** Camera, location, notifications require permission mocking
- **React Native patterns:** Different testing utilities than web React

---

## Quick Start (5 min)

### Run All Tests

```bash
cd mobile
npm test -- --watchAll=false
# Expected: 398 tests pass, 100% pass rate
# Execution time: ~2-3 minutes
```

### Run Specific Test File

```bash
npm test -- AgentCard.test.tsx
```

### Run Tests in Watch Mode

```bash
npm test -- --watch
# Automatically re-runs on file changes
```

### Generate Coverage Report

```bash
npm test -- --coverage --watchAll=false
# Output: coverage/coverage-final.json, coverage/lcov-report/index.html
open coverage/lcov-report/index.html  # View HTML report
```

### Run Platform-Specific Tests

```bash
npm test -- --testPathPattern="platform-specific"
# Runs iOS/Android-specific tests
```

---

## Test Structure

```
mobile/src/__tests__/
├── unit/                    # Isolated component/hook tests
│   ├── components/          # React Native component tests
│   ├── hooks/               # Custom hook tests
│   └── services/            # Service layer tests
├── integration/             # API integration tests (MSW)
│   └── api/                 # API endpoint tests
├── platform-specific/       # iOS vs Android tests
│   ├── ios/                 # iOS-specific tests
│   ├── android/             # Android-specific tests
│   └── cross-platform/      # Dual-platform tests
├── property/                # Property-based tests (FastCheck)
└── helpers/                 # Test utilities
    ├── testUtils.ts         # Platform testing helpers
    └── platformPermissions.test.ts  # Permission mocks
```

### Test File Naming

- Components: `ComponentName.test.tsx`
- Hooks: `useHookName.test.ts`
- Services: `serviceName.test.ts`
- Platform-specific: `featureName.ios.test.tsx`, `featureName.android.test.tsx`

---

## jest-expo Patterns

### Component Testing (React Native Testing Library)

**Basic Component Test:**

```typescript
import { render, screen } from '@testing-library/react-native';
import AgentCard from '../../components/AgentCard';

test('agent card displays agent name and status', () => {
  render(<AgentCard name="Test Agent" status="active" />);
  expect(screen.getByText('Test Agent')).toBeTruthy();
  expect(screen.getByText('active')).toBeTruthy();
});
```

**Test User Interactions:**

```typescript
import { render, screen, fireEvent } from '@testing-library/react-native';
import AgentForm from '../../components/AgentForm';

test('submit button enables when form is valid', () => {
  const onSubmit = jest.fn();
  render(<AgentForm onSubmit={onSubmit} />);

  const submitButton = screen.getByRole('button', { name: /submit/i });
  expect(submitButton).toBeEnabled(); // Initially disabled

  // Fill required fields
  fireEvent.changeText(screen.getByLabelText(/name/i), 'Agent 1');

  expect(submitButton).toBeEnabled(); // Now enabled
});

test('calls onSubmit when form is submitted', () => {
  const onSubmit = jest.fn();
  render(<AgentForm onSubmit={onSubmit} />);

  fireEvent.changeText(screen.getByLabelText(/name/i), 'Agent 1');
  fireEvent.press(screen.getByRole('button', { name: /submit/i }));

  expect(onSubmit).toHaveBeenCalledWith({ name: 'Agent 1' });
});
```

**Test Async Behavior:**

```typescript
import { render, screen, waitFor } from '@testing-library/react-native';
import AgentList from '../../components/AgentList';

test('agent list loads agents asynchronously', async () => {
  render(<AgentList />);

  // Loading state
  expect(screen.getByText(/loading/i)).toBeTruthy();

  // Wait for async data
  await waitFor(() => {
    expect(screen.getByText('Agent 1')).toBeTruthy();
  });

  expect(screen.queryByText(/loading/i)).toBeNull();
});
```

### Platform-Specific Testing

**testEachPlatform Helper:**

```typescript
import { renderWithPlatform } from '../helpers/testUtils';

testEachPlatform('status bar uses correct insets', (platform) => {
  const { getByTestId } = renderWithPlatform(<StatusBar />, platform);

  const insets = platform === 'ios' ? getiOSInsets() : getAndroidInsets();
  expect(getByTestId('status-bar')).toHaveStyle({ paddingTop: insets.top });
});
```

**Platform Detection Tests:**

```typescript
import { Platform } from 'react-native';
import { get_current_platform, is_platform } from '../helpers/testUtils';

test('detects iOS platform correctly', () => {
  mockPlatform('ios');

  expect(get_current_platform()).toBe('ios');
  expect(is_platform('ios')).toBe(true);
  expect(is_platform('android')).toBe(false);

  restorePlatform();
});

test('detects Android platform correctly', () => {
  mockPlatform('android');

  expect(get_current_platform()).toBe('android');
  expect(is_platform('android')).toBe(true);
  expect(is_platform('ios')).toBe(false);

  restorePlatform();
});
```

---

## Platform Mocking

### SafeAreaContext Mock

**Why needed:** SafeAreaContext provides native iOS/Android insets for notched devices. Tests must mock this to avoid native module errors.

```typescript
// jest.setup.js
jest.mock('react-native-safe-area-context', () => ({
  SafeAreaProvider: ({ children }) => children,
  SafeAreaView: ({ children }) => children,
  useSafeAreaInsets: jest.fn(() => ({ top: 0, bottom: 0, left: 0, right: 0 })),
  useSafeAreaFrame: jest.fn(() => ({ width: 320, height: 640 })),
}));
```

**Custom Insets in Tests:**

```typescript
import { render } from '@testing-library/react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

test('status bar respects custom insets', () => {
  useSafeAreaInsets.mockReturnValue({ top: 44, bottom: 34, left: 0, right: 0 });

  const { getByTestId } = render(<StatusBar />);
  expect(getByTestId('status-bar')).toHaveStyle({ paddingTop: 44 });
});
```

### Platform.OS Switching

**Why needed:** Tests must verify both iOS and Android behavior. Platform.OS switching allows testing both platforms in the same test file.

```typescript
// helpers/testUtils.ts
export function mockPlatform(platform: 'ios' | 'android') {
  Object.defineProperty(Platform, 'OS', {
    get: () => platform,
    configurable: true,
  });
}

export function restorePlatform() {
  Object.defineProperty(Platform, 'OS', {
    get: () => Platform.OS,
    configurable: true,
  });
}
```

**Usage in Tests:**

```typescript
import { mockPlatform, restorePlatform } from '../helpers/testUtils';

beforeEach(() => {
  mockPlatform('ios');
});

afterEach(() => {
  restorePlatform();
});

test('iOS status bar uses safe area insets', () => {
  // Test iOS-specific behavior
});

test('Android status bar uses system UI insets', () => {
  mockPlatform('android');
  // Test Android-specific behavior
});
```

### StatusBar Mock

```typescript
import * as ReactNative from 'react-native';

jest.spyOn(ReactNative.StatusBar, 'setBarStyle').mockImplementation(() => {});
jest.spyOn(ReactNative.StatusBar, 'setHidden').mockImplementation(() => {});
```

---

## Device Capability Mocking

### Camera Mock

**Why needed:** expo-camera requires native permissions and hardware access. Tests mock permissions and camera constants.

```typescript
// jest.setup.js
jest.mock('expo-camera', () => ({
  Camera: {
    Constants: {
      Type: {
        back: 'back',
        front: 'front',
      },
      FlashMode: {
        off: 'off',
        on: 'on',
        auto: 'auto',
      },
    },
  },
  requestCameraPermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' })
  ),
}));
```

**Test Camera Permission Flow:**

```typescript
import { requestCameraPermissionsAsync } from 'expo-camera';
import { renderHook, act } from '@testing-library/react-native';
import useCamera from '../../hooks/useCamera';

test('requests camera permission on mount', async () => {
  requestCameraPermissionsAsync.mockResolvedValue({ status: 'granted' });

  const { result } = renderHook(() => useCamera());

  await act(async () => {
    await result.current.requestPermission();
  });

  expect(requestCameraPermissionsAsync).toHaveBeenCalled();
  expect(result.current.hasPermission).toBe(true);
});
```

### Location Mock

```typescript
// jest.setup.js
jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' })
  ),
  requestBackgroundPermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' })
  ),
  getCurrentPositionAsync: jest.fn(() =>
    Promise.resolve({
      coords: {
        latitude: 37.7749,
        longitude: -122.4194,
        altitude: null,
        accuracy: 10,
        altitudeAccuracy: null,
        heading: null,
        speed: null,
      },
      timestamp: 1646928000000,
    })
  ),
}));
```

**Test Location Retrieval:**

```typescript
import { getCurrentPositionAsync } from 'expo-location';
import { renderHook, act } from '@testing-library/react-native';
import useLocation from '../../hooks/useLocation';

test('retrieves current location', async () => {
  getCurrentPositionAsync.mockResolvedValue({
    coords: { latitude: 37.7749, longitude: -122.4194 },
    timestamp: 1646928000000,
  });

  const { result } = renderHook(() => useLocation());

  await act(async () => {
    await result.current.getLocation();
  });

  expect(result.current.location).toEqual({
    latitude: 37.7749,
    longitude: -122.4194,
  });
});
```

### Notifications Mock

```typescript
// jest.setup.js
jest.mock('expo-notifications', () => ({
  requestBadgePermissionsAsync: jest.fn(() =>
    Promise.resolve({ status: 'granted' })
  ),
  setBadgeCountAsync: jest.fn(),
  scheduleNotificationAsync: jest.fn(),
  cancelAllScheduledNotificationsAsync: jest.fn(),
  addNotificationReceivedListener: jest.fn(),
  addNotificationResponseReceivedListener: jest.fn(),
}));
```

**Test Notification Badge:**

```typescript
import { setBadgeCountAsync } from 'expo-notifications';
import { renderHook, act } from '@testing-library/react-native';
import useNotifications from '../../hooks/useNotifications';

test('sets notification badge count', async () => {
  const { result } = renderHook(() => useNotifications());

  await act(async () => {
    await result.current.setBadge(5);
  });

  expect(setBadgeCountAsync).toHaveBeenCalledWith(5);
});
```

---

## Async Testing

### waitFor Pattern

**Why needed:** React Native components often load data asynchronously. `waitFor` retries assertions until they pass or timeout.

```typescript
import { render, screen, waitFor } from '@testing-library/react-native';

test('auth context hydrates from storage', async () => {
  const { result } = renderHook(() => useAuth());

  // Wait for async storage hydration
  await waitFor(() => {
    expect(result.current.isAuthenticated).toBe(true);
  });

  expect(result.current.user).toEqual({ id: '123', name: 'Test User' });
});
```

### waitFor with Timeout

```typescript
test('waits up to 5 seconds for slow operation', async () => {
  const { result } = renderHook(() => useSlowOperation());

  await waitFor(
    () => {
      expect(result.current.data).toBeTruthy();
    },
    { timeout: 5000 }
  );
});
```

### Async Act Pattern

```typescript
import { renderHook, act } from '@testing-library/react-native';

test('async state update works correctly', async () => {
  const { result } = renderHook(() => useAsyncCounter());

  await act(async () => {
    await result.current.incrementAsync();
  });

  expect(result.current.count).toBe(1);
});
```

---

## Coverage

### Current Coverage Status

| Module | Target | Current | Gap |
|--------|--------|---------|-----|
| Navigation | 80% | 95% | -15% (exceeds target) |
| Services | 70% | 52% | +18% |
| Screens | 60% | 42% | +18% |
| Components | 75% | 68% | +7% |
| Hooks | 80% | 71% | +9% |
| **Overall** | **50%** | **~55%** | **-5% (exceeds target)** |

### Generate Coverage Report

```bash
# Run tests with coverage
npm test -- --coverage --watchAll=false

# View HTML report
open coverage/lcov-report/index.html

# Export coverage JSON
cat coverage/coverage-final.json
```

### Per-File Coverage

```bash
# Coverage for specific file
npm test -- --coverage --collectCoverageFrom=src/components/AgentCard.tsx
```

### Coverage Exclusions

**jest.config.js:**

```javascript
collectCoverageFrom: [
  'src/**/*.{ts,tsx}',
  '!src/**/*.d.ts',           // Exclude type definitions
  '!src/types/**',            // Exclude types directory
  '!src/**/*.stories.tsx',    // Exclude Storybook stories
  '!src/**/*.stories.ts',
],
```

---

## CI/CD

### GitHub Actions Workflow

```yaml
# .github/workflows/mobile-tests.yml
name: Mobile Tests

on: [push, pull_request]

jobs:
  mobile-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install dependencies
        working-directory: ./mobile
        run: npm ci

      - name: Run tests with coverage
        working-directory: ./mobile
        run: npm test -- --coverage --watchAll=false

      - name: Enforce 50% coverage threshold
        working-directory: ./mobile
        run: |
          COVERAGE=$(node -p "require('./coverage/coverage-summary.json').total.statements.pct")
          if (( $(echo "$COVERAGE < 50" | bc -l) )); then
            echo "Coverage $COVERAGE% below 50% threshold"
            exit 1
          fi

      - name: Upload coverage reports
        uses: actions/upload-artifact@v3
        with:
          name: mobile-coverage
          path: mobile/coverage/
          retention-days: 30
```

### Flaky Test Detection (Phase 151)

**Multi-run verification:**

```bash
# Run tests 3 times to detect flakiness
node mobile/scripts/jest-retry-wrapper.js --runs 3 --threshold 30
```

**CI/CD integration:**

```yaml
- name: Run mobile tests with flaky detection
  working-directory: ./mobile
  run: |
    node scripts/jest-retry-wrapper.js --runs 3 --threshold 30
    # Exit codes: 0=stable, 1=flaky, 2=error
```

---

## Platform-Specific Considerations

### iOS-Specific Testing

**SafeArea Insets:**

```typescript
test('iPhone 14 Pro Max Dynamic Island insets', () => {
  mockPlatform('ios');

  const insets = getiOSInsets('iPhone14ProMax');
  expect(insets.top).toBe(59); // Dynamic Island height
  expect(insets.bottom).toBe(34);
});
```

**StatusBar Style:**

```typescript
test('iOS status bar uses light style', () => {
  const { getByTestId } = render(<StatusBar style="light" />);
  expect(getByTestId('status-bar')).toHaveStyle({
    backgroundColor: '#000000',
  });
});
```

**Platform Detection:**

```typescript
test('detects iOS device correctly', () => {
  mockPlatform('ios');

  expect(isPlatform('ios')).toBe(true);
  expect(isPlatform('android')).toBe(false);

  restorePlatform();
});
```

### Android-Specific Testing

**Navigation Mode (Gesture vs Button):**

```typescript
test('Android gesture navigation has zero bottom inset', () => {
  mockPlatform('android');

  const insets = getAndroidInsets('gesture');
  expect(insets.bottom).toBe(0);

  restorePlatform();
});

test('Android button navigation has 48dp bottom inset', () => {
  mockPlatform('android');

  const insets = getAndroidInsets('button');
  expect(insets.bottom).toBe(48);

  restorePlatform();
});
```

**BackHandler:**

```typescript
test('Android back button exits app', () => {
  const { result } = renderHook(() => useBackButton());

  act(() => {
    result.current.handleBackButton();
  });

  expect(result.current.hasExited).toBe(true);
});
```

**Permissions:**

```typescript
test('Android requests camera permission', async () => {
  requestCameraPermissionsAsync.mockResolvedValue({ status: 'granted' });

  const { result } = renderHook(() => useCamera());

  await act(async () => {
    await result.current.requestPermission();
  });

  expect(result.current.hasPermission).toBe(true);
});
```

### Cross-Platform Testing

**testEachPlatform Helper:**

```typescript
import { testEachPlatform } from '../helpers/testUtils';

testEachPlatform('safe area provider renders children', (platform) => {
  const { getByText } = renderWithPlatform(
    <SafeAreaProvider>
      <Text>Content</Text>
    </SafeAreaProvider>,
    platform
  );

  expect(getByText('Content')).toBeTruthy();
});
```

**Conditional Rendering Tests:**

```typescript
test('renders iOS-specific component on iOS', () => {
  mockPlatform('ios');

  const { getByTestId } = render(<PlatformSpecificComponent />);
  expect(getByTestId('ios-component')).toBeTruthy();
  expect(getByTestId('android-component')).toBeNull();

  restorePlatform();
});

test('renders Android-specific component on Android', () => {
  mockPlatform('android');

  const { getByTestId } = render(<PlatformSpecificComponent />);
  expect(getByTestId('android-component')).toBeTruthy();
  expect(getByTestId('ios-component')).toBeNull();

  restorePlatform();
});
```

---

## Troubleshooting

### Issue: TurboModule Registry Errors

**Symptom:** `TurboModuleRegistry.getEnforcing(...) is not a function`

**Cause:** Native Expo modules not mocked in jest.setup.js

**Solution:**

```typescript
// jest.setup.js
jest.mock('expo-camera', () => ({
  Camera: { Constants: { Type: { back: 'back' } } },
  requestCameraPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
}));
```

**See also:** Phase 139 platform infrastructure (`mobile/src/__tests__/helpers/testUtils.ts`)

---

### Issue: Async Timing Issues

**Symptom:** Tests fail with "Cannot find element" or "Expected null to be truthy"

**Cause:** Async state updates not awaited

**Solution:**

```typescript
import { waitFor, flushPromises } from '../helpers/testUtils';

test('waits for async data', async () => {
  const { result } = renderHook(() => useAsyncData());

  await waitFor(() => {
    expect(result.current.data).toBeTruthy();
  });
});

test('flushes promises for immediate updates', async () => {
  const { result } = renderHook(() => useAsyncData());

  await flushPromises();

  expect(result.current.data).toBeTruthy();
});
```

**See also:** `testUtils.ts` (flushPromises, waitForCondition helpers)

---

### Issue: Platform Detection Tests Fail

**Symptom:** `Platform.OS is 'ios' but test expects 'android'`

**Cause:** Platform mock not restored between tests

**Solution:**

```typescript
import { mockPlatform, restorePlatform } from '../helpers/testUtils';

beforeEach(() => {
  mockPlatform('ios');
});

afterEach(() => {
  restorePlatform(); // CRITICAL: Cleanup prevents test pollution
});

test('iOS test', () => {
  expect(Platform.OS).toBe('ios');
});

test('Android test', () => {
  mockPlatform('android');
  expect(Platform.OS).toBe('android');
});
```

**See also:** `get_current_platform()` helper in testUtils.ts

---

### Issue: SafeArea Context Returns Zero Insets

**Symptom:** SafeArea insets are `{ top: 0, bottom: 0, left: 0, right: 0 }` in tests

**Cause:** Default mock returns zero insets

**Solution:**

```typescript
import { useSafeAreaInsets } from 'react-native-safe-area-context';

test('uses custom iOS insets', () => {
  useSafeAreaInsets.mockReturnValue({
    top: 44,
    bottom: 34,
    left: 0,
    right: 0,
  });

  const { getByTestId } = render(<StatusBar />);
  expect(getByTestId('status-bar')).toHaveStyle({ paddingTop: 44 });
});
```

**See also:** `getiOSInsets()`, `getAndroidInsets()` helpers in testUtils.ts

---

## Best Practices

### 1. Test Behavior, Not Implementation (RNTL Philosophy)

**Do:**

```typescript
test('agent card displays agent name', () => {
  render(<AgentCard name="Agent 1" />);
  expect(screen.getByText('Agent 1')).toBeTruthy();
});
```

**Don't:**

```typescript
test('agent card renders Text component', () => {
  const { getByTestId } = render(<AgentCard name="Agent 1" />);
  expect(getByTestId('agent-name-text')).toBeTruthy(); // Tests implementation
});
```

**Why:** RNTL encourages testing user-visible behavior, not component internals.

---

### 2. Mock All Expo Modules

**Do:**

```typescript
// jest.setup.js
jest.mock('expo-camera', () => ({ ... }));
jest.mock('expo-location', () => ({ ... }));
jest.mock('expo-notifications', () => ({ ... }));
```

**Don't:**

```typescript
// No mocks - tests fail with TurboModule errors
import { Camera } from 'expo-camera';

test('takes photo', () => {
  // Fails: TurboModuleRegistry not available in Jest
});
```

**Why:** Expo modules require native runtime, Jest runs in Node.js.

---

### 3. Test Platform-Specific Variations

**Do:**

```typescript
testEachPlatform('status bar respects platform insets', (platform) => {
  const insets = platform === 'ios' ? getiOSInsets() : getAndroidInsets();
  const { getByTestId } = renderWithPlatform(<StatusBar />, platform);

  expect(getByTestId('status-bar')).toHaveStyle({ paddingTop: insets.top });
});
```

**Don't:**

```typescript
test('status bar uses iOS insets only', () => {
  // Fails on Android, doesn't test cross-platform behavior
  expect(getByTestId('status-bar')).toHaveStyle({ paddingTop: 44 });
});
```

**Why:** React Native apps run on both iOS and Android, test both platforms.

---

### 4. Use Property Tests (FastCheck)

**Do:**

```typescript
import fc from 'fast-check';

fc.assert(
  fc.property(fc.string(), fc.string(), (name, status) => {
    const { getByText } = render(<AgentCard name={name} status={status} />);
    expect(getByText(name)).toBeTruthy();
    expect(getByText(status)).toBeTruthy();
  }),
  { numRuns: 100 }
);
```

**Don't:**

```typescript
test('agent card displays specific values', () => {
  const { getByText } = render(<AgentCard name="Agent 1" status="active" />);
  expect(getByText('Agent 1')).toBeTruthy(); // Only tests one case
});
```

**Why:** Property tests find edge cases (empty strings, Unicode, etc.)

**See also:** `docs/PROPERTY_TESTING_PATTERNS.md` (FastCheck section)

---

### 5. Isolate Tests (Cleanup Platform Mocks)

**Do:**

```typescript
beforeEach(() => {
  mockPlatform('ios');
});

afterEach(() => {
  restorePlatform(); // CRITICAL: Prevents test pollution
});

test('iOS test', () => {
  expect(Platform.OS).toBe('ios');
});
```

**Don't:**

```typescript
test('iOS test', () => {
  mockPlatform('ios');
  expect(Platform.OS).toBe('ios');
  // No cleanup - affects subsequent tests
});

test('Android test', () => {
  expect(Platform.OS).toBe('android'); // FAILS: Still 'ios' from previous test
});
```

**Why:** Tests must be independent, cleanup prevents pollution.

---

## Further Reading

### Platform-Specific Guides

- **Frontend Testing:** [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) - Shared React patterns (Jest, RTL)
- **Desktop Testing:** [DESKTOP_TESTING_GUIDE.md](DESKTOP_TESTING_GUIDE.md) - Tauri/Rust patterns
- **Backend Testing:** [backend/tests/docs/COVERAGE_GUIDE.md](../backend/tests/docs/COVERAGE_GUIDE.md) - pytest patterns

### Cross-Platform Patterns

- **Property Testing:** [PROPERTY_TESTING_PATTERNS.md](PROPERTY_TESTING_PATTERNS.md) - FastCheck shared across frontend/mobile/desktop
- **E2E Testing:** [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md) - API-level mobile testing (Phase 148)
- **Cross-Platform Coverage:** [CROSS_PLATFORM_COVERAGE.md](CROSS_PLATFORM_COVERAGE.md) - Mobile threshold 50%

### Phase 139 Platform Infrastructure

- **Summary:** [.planning/phases/139-mobile-platform-specific/139-01-SUMMARY.md](../.planning/phases/139-mobile-platform-specific/139-01-SUMMARY.md) - Platform-specific testing infrastructure
- **Test Utilities:** `mobile/src/__tests__/helpers/testUtils.ts` - Platform helpers (mockPlatform, renderWithSafeArea)
- **Platform Mocks:** `mobile/jest.setup.js` - Expo module mocks (camera, location, notifications)

### Testing Documentation Index

- **Central Hub:** [TESTING_INDEX.md](TESTING_INDEX.md) - All testing documentation, use case navigation

---

## See Also

### Internal Documentation

- **Testing Onboarding:** [TESTING_ONBOARDING.md](TESTING_ONBOARDING.md) - 15-min quick start for all platforms
- **Flaky Test Quarantine:** [backend/tests/docs/FLAKY_TEST_QUARANTINE.md](../backend/tests/docs/FLAKY_TEST_QUARANTINE.md) - Multi-run flaky detection
- **Test Isolation:** [backend/tests/docs/TEST_ISOLATION_PATTERNS.md](../backend/tests/docs/TEST_ISOLATION_PATTERNS.md) - Independent test patterns

### External Resources

- **React Native Testing Library:** https://callstack.github.io/react-native-testing-library/
- **Jest-Expo Docs:** https://docs.expo.dev/guides/testing/
- **Expo Modules:** https://docs.expo.dev/versions/latest/sdk/

---

**Document Version:** 1.0
**Last Updated:** March 7, 2026
**Maintainer:** Mobile Testing Team

**For questions or contributions, see:** [TESTING_INDEX.md](TESTING_INDEX.md)
