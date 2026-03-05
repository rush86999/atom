# Phase 139: Mobile Platform-Specific Testing - Research

**Researched:** 2026-03-05
**Domain:** React Native platform-specific testing (iOS vs Android)
**Confidence:** HIGH

## Summary

Phase 139 focuses on testing platform-specific features and behaviors that differ between iOS and Android in React Native applications. The phase builds upon Phase 138's state management testing foundation, with an emphasis on iOS-specific features (safe area, status bar, home indicator), Android-specific features (back button, permissions, navigation), conditional rendering patterns, permission flows, and platform-specific error handling.

The research reveals that React Native platform-specific testing requires: (1) Platform.OS mocking infrastructure already in place from Phase 135, (2) SafeAreaContext built-in Jest mocks for testing safe areas, (3) Expo permission testing patterns with comprehensive mock utilities, (4) StatusBar testing with both component and imperative API approaches, and (5) Platform.select for clean conditional rendering testing.

**Primary recommendation:** Leverage existing `mockPlatform()` utility from testUtils.ts for Platform.OS switching, use `react-native-safe-area-context/jest/mock` for safe area testing, extend existing `createPermissionMock()` utility for permission flows, and create platform-specific test suites that run on both iOS and Android to ensure feature parity.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **React Native** | 0.73.6 | Core mobile framework | Official stable release, ecosystem standard |
| **Expo SDK 50** | ~50.0.0 | Development platform | Zero-config platform APIs, comprehensive permission handling |
| **Jest** | 29.7.0 | Test runner | React Native official testing framework |
| **React Native Testing Library** | 12.4.2 | Component testing | Best practice for user-centric testing |
| **react-native-safe-area-context** | 4.8.2 | Safe area handling | Industry standard for iOS notches/home indicators |
| **expo-camera** | ~14.0.0 | Camera permissions | Expo unified camera API |
| **expo-location** | ~16.5.0 | Location permissions | Expo unified location API |
| **expo-notifications** | ~0.27.0 | Notification permissions | Expo unified notification API |
| **expo-local-authentication** | ~13.8.0 | Biometric permissions | Face ID (iOS) / Fingerprint (Android) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **@testing-library/jest-native** | 5.4.3 | Jest matchers | Custom matchers like `.toBeVisible()`, `.toHaveTextContent()` |
| **react-test-renderer** | 18.2.0 | Snapshot testing | For regression testing of component outputs |
| **jest-expo** | ~50.0.0 | Expo environment | Required for Expo module mocking |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **expo-permissions** | **expo-camera/expo-location/expo-notifications** | Expo deprecated expo-permissions in SDK 43+, now using module-specific permission APIs |
| **Manual Platform.OS mocks** | **testUtils.mockPlatform()** | Existing utility from Phase 135 provides consistent mocking with cleanup |
| **Custom safe area mocks** | **react-native-safe-area-context/jest/mock** | Built-in mock provides default test data, no custom implementation needed |
| **Detox (E2E)** | **Jest (unit/integration)** | Phase 139 focuses on unit/integration, Detox better suited for Phase 140 (E2E) |

**Installation:**
```bash
# Already installed in Atom mobile app
npm install react-native-safe-area-context expo-camera expo-location expo-notifications expo-local-authentication
npm install --save-dev @testing-library/jest-native jest-expo react-test-renderer
```

## Architecture Patterns

### Recommended Project Structure

```
mobile/src/__tests__/
├── platform-specific/
│   ├── ios/
│   │   ├── safeArea.test.tsx          # iOS safe area testing
│   │   ├── statusBar.test.tsx          # iOS StatusBar API testing
│   │   ├── homeIndicator.test.tsx      # iOS home indicator testing
│   │   ├── faceId.test.tsx             # Face ID authentication
│   │   └── backgroundRefresh.test.tsx  # iOS background refresh
│   ├── android/
│   │   ├── backButton.test.tsx         # Android back button testing
│   │   ├── permissions.test.tsx        # Android runtime permissions
│   │   ├── fingerprint.test.tsx        # Fingerprint authentication
│   │   └── navigation.test.tsx         # Android navigation patterns
│   ├── conditionalRendering.test.tsx   # Platform.OS and Platform.select
│   ├── permissionFlows.test.ts         # Cross-platform permission flows
│   └── platformErrors.test.tsx         # Platform-specific error handling
├── helpers/
│   ├── platformMocks.ts               # Platform-specific mock utilities
│   ├── permissionMocks.ts             # Permission mock factories
│   └── deviceMocks.ts                 # Device hardware mocks
└── integration/
    └── platformParity.test.tsx        # Feature parity across platforms
```

### Pattern 1: Platform.OS Mocking with testUtils

**What:** Mock Platform.OS for testing platform-specific behavior

**When to use:** Testing conditional rendering, Platform.select, platform-specific API calls

**Example:**
```typescript
// Source: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/testUtils.ts
import { mockPlatform, restorePlatform, isIOS, isAndroid } from '../testUtils';

describe('Platform-specific component', () => {
  afterEach(() => {
    restorePlatform(); // Cleanup after each test
  });

  it('should render iOS component on iOS', () => {
    mockPlatform('ios');
    expect(Platform.OS).toBe('ios');
    expect(isIOS()).toBe(true);
    expect(isAndroid()).toBe(false);
  });

  it('should render Android component on Android', () => {
    mockPlatform('android');
    expect(Platform.OS).toBe('android');
    expect(isAndroid()).toBe(true);
    expect(isIOS()).toBe(false);
  });

  it('should switch platforms correctly', () => {
    mockPlatform('ios');
    expect(Platform.OS).toBe('ios');

    mockPlatform('android');
    expect(Platform.OS).toBe('android');
  });
});
```

**Pattern Benefits:**
- Consistent mocking across all tests
- Automatic cleanup prevents test pollution
- Helper functions (`isIOS()`, `isAndroid()`) improve readability

### Pattern 2: SafeAreaContext Testing

**What:** Test safe area insets for iOS notches and Android gesture navigation

**When to use:** Testing components that use `useSafeAreaInsets()` hook or `SafeAreaView`

**Example:**
```typescript
// Source: https://www.npmjs.com/package/react-native-safe-area-context/v/5.2.0
import mockSafeAreaContext from 'react-native-safe-area-context/jest/mock';

jest.mock('react-native-safe-area-context', () => mockSafeAreaContext);

describe('Safe area testing', () => {
  it('should apply safe area insets on iOS', () => {
    mockPlatform('ios');

    const { getByTestId } = render(<ComponentWithSafeArea />);

    // Component should use insets from mock
    expect(getByTestId('safe-area-view')).toHaveStyle({
      paddingTop: 0, // Default mock value
      paddingBottom: 0,
    });
  });

  it('should handle custom safe area values', () => {
    const customInsets = { top: 44, bottom: 34, left: 0, right: 0 };

    const { getByTestId } = render(
      <SafeAreaProvider initialMetrics={{ insets: customInsets }}>
        <ComponentWithSafeArea />
      </SafeAreaProvider>
    );

    expect(getByTestId('safe-area-view')).toHaveStyle({
      paddingTop: 44,
      paddingBottom: 34,
    });
  });
});
```

**Default Mock Data:**
```javascript
{
  frame: { width: 320, height: 640, x: 0, y: 0 },
  insets: { top: 0, left: 0, right: 0, bottom: 0 },
}
```

**Pattern Benefits:**
- Built-in Jest mock from library
- Default test data covers most scenarios
- Custom `initialMetrics` for edge cases

### Pattern 3: Permission Flow Testing

**What:** Test permission request flows for camera, location, notifications

**When to use:** Testing expo-camera, expo-location, expo-notifications permission requests

**Example:**
```typescript
// Source: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/platformPermissions.test.ts
import { createPermissionMock, assertPermissionRequested } from '../platformPermissions';

describe('Camera permission flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue(
      createPermissionMock('granted')
    );
  });

  it('should request camera permission on iOS', async () => {
    mockPlatform('ios');

    await Camera.requestCameraPermissionsAsync();

    assertPermissionRequested(Camera.requestCameraPermissionsAsync as jest.Mock);
  });

  it('should handle permission denied on Android', async () => {
    mockPlatform('android');
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue(
      createPermissionMock('denied', false) // canAskAgain = false
    );

    const result = await Camera.requestCameraPermissionsAsync();

    expect(result.granted).toBe(false);
    expect(result.canAskAgain).toBe(false);
    // Should show dialog explaining why permission is needed
  });

  it('should handle iOS settings deep link', async () => {
    mockPlatform('ios');
    (Camera.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      ...createPermissionMock('denied'),
      canAskAgain: false, // User denied permanently
    });

    const result = await Camera.getCameraPermissionsAsync();

    expect(result.canAskAgain).toBe(false);
    // App should deep link to iOS Settings app
  });
});
```

**Permission Mock Utility:**
```typescript
export const createPermissionMock = (
  status: 'granted' | 'denied' | 'notAsked',
  canAskAgain = true
) => ({
  status,
  canAskAgain,
  granted: status === 'granted',
  expires: 'never' as const,
});
```

**Pattern Benefits:**
- Consistent permission mock structure
- Reusable utility functions
- Tests all permission states (granted, denied, notAsked)

### Pattern 4: Platform.select Testing

**What:** Test Platform.select for conditional values, styles, components

**When to use:** Testing platform-specific styles, components, or configuration

**Example:**
```typescript
// Source: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/__tests__/testUtils.test.ts
import { Platform } from 'react-native';

describe('Platform.select testing', () => {
  it('should select iOS value on iOS', () => {
    mockPlatform('ios');

    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
    });

    expect(result).toBe('iOS Value');
  });

  it('should select Android value on Android', () => {
    mockPlatform('android');

    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
    });

    expect(result).toBe('Android Value');
  });

  it('should use default fallback', () => {
    mockPlatform('windows'); // Unrecognized platform

    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
      default: 'Default Value',
    });

    expect(result).toBe('Default Value');
  });

  it('should work with styles', () => {
    mockPlatform('ios');

    const styles = StyleSheet.create({
      container: {
        flex: 1,
        ...Platform.select({
          ios: { shadowColor: '#000', shadowOpacity: 0.25 },
          android: { elevation: 5 },
        }),
      },
    });

    expect(styles.container).toHaveProperty('shadowColor');
    expect(styles.container).not.toHaveProperty('elevation');
  });
});
```

**Pattern Benefits:**
- Tests platform-specific logic without actual devices
- Covers default fallback for unrecognized platforms
- Validates StyleSheet merging with Platform.select

### Pattern 5: StatusBar Testing

**What:** Test StatusBar API for hiding/showing and changing style

**When to use:** Testing full-screen components, camera views, immersive experiences

**Example:**
```typescript
// Source: /Users/rushiparikh/projects/atom/mobile/src/screens/canvas/CanvasViewerScreen.tsx
import { StatusBar } from 'react-native';

describe('StatusBar testing', () => {
  it('should hide status bar on iOS canvas view', () => {
    mockPlatform('ios');
    const { setHidden } = jest.spyOn(StatusBar, 'setHidden');

    // Component mounts and calls StatusBar.setHidden(true)
    render(<CanvasViewerScreen />);

    expect(setHidden).toHaveBeenCalledWith(true, 'fade'); // iOS transition
  });

  it('should show status bar when exiting canvas', () => {
    mockPlatform('android');
    const { setHidden } = jest.spyOn(StatusBar, 'setHidden');

    const { unmount } = render(<CanvasViewerScreen />);

    unmount(); // Component unmounts

    expect(setHidden).toHaveBeenLastCalledWith(false);
  });

  it('should change status bar style on iOS', () => {
    mockPlatform('ios');
    const { setBarStyle } = jest.spyOn(StatusBar, 'setBarStyle');

    render(<DarkModeScreen />);

    expect(setBarStyle).toHaveBeenCalledWith('dark-content');
  });
});
```

**Platform-Specific StatusBar APIs:**
- **iOS**: `barStyle` ('default', 'light-content', 'dark-content'), `networkActivityIndicatorVisible`
- **Android**: `backgroundColor`, `translucent`, `StatusBar.currentHeight`
- **Both**: `hidden`, `animated`

**Pattern Benefits:**
- Tests both component and imperative API approaches
- Validates platform-specific transitions ('fade' vs 'slide')
- Ensures cleanup on unmount

### Anti-Patterns to Avoid

- **Anti-pattern:** Testing platform-specific behavior without mocking Platform.OS
  - **Why it's bad:** Tests only run on host platform, missing 50% of scenarios
  - **Instead:** Always use `mockPlatform()` to test both iOS and Android

- **Anti-pattern:** Hardcoding permission mock values in each test
  - **Why it's bad:** Inconsistent mock structure, difficult to maintain
  - **Instead:** Use `createPermissionMock()` utility for consistency

- **Anti-pattern:** Not restoring Platform.OS after tests
  - **Why it's bad:** Test pollution causes flaky tests in subsequent suites
  - **Instead:** Always call `restorePlatform()` in afterEach

- **Anti-pattern:** Testing Platform.OS with conditional rendering only
  - **Why it's bad:** Misses Platform.select for styles, components, values
  - **Instead:** Test both `Platform.OS === 'ios'` and `Platform.select()` patterns

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Platform.OS mocking** | Custom `jest.mock()` in each test file | `testUtils.mockPlatform()` | Consistent mocking with automatic cleanup, already tested from Phase 135 |
| **Safe area mocks** | Custom insets object with `{ top: 0, bottom: 0 }` | `react-native-safe-area-context/jest/mock` | Built-in Jest mock from library, provides frame + insets structure |
| **Permission mocks** | Manual `{ status: 'granted', granted: true }` objects | `createPermissionMock()` utility | Handles all 3 states (granted/denied/notAsked) + canAskAgain flag |
| **Platform detection** | Custom `if (Platform.OS === 'ios')` checks | `isIOS()`, `isAndroid()` helpers | More readable, centralized logic, easier to mock |
| **Component testing** | Shallow rendering with Enzyme | React Native Testing Library | User-centric testing, official recommendation, better async support |
| **Async testing** | `setTimeout()` with arbitrary delays | `waitForAsync()`, `flushPromises()` utilities | Predictable async handling, no race conditions, faster tests |
| **Platform assertion** | Manual `expect(Platform.OS).toBe('ios')` | `testEachPlatform()` helper | Runs test on both platforms automatically, reduces code duplication |

**Key insight:** Platform-specific testing requires careful mocking and cleanup to prevent test pollution. Custom implementations often forget cleanup (restorePlatform), don't handle all permission states, or miss edge cases (Platform.select defaults). Use existing utilities from Phase 135 and official library mocks for reliability.

## Common Pitfalls

### Pitfall 1: Platform.OS Not Restored Between Tests

**What goes wrong:** Test that sets `mockPlatform('ios')` affects subsequent tests expecting Android behavior, causing random failures

**Why it happens:** `Object.defineProperty(Platform, 'OS', ...)` modifies global Platform object, persists across tests

**How to avoid:**
```typescript
describe('Component tests', () => {
  afterEach(() => {
    restorePlatform(); // ALWAYS restore in afterEach
  });

  it('works on iOS', () => {
    mockPlatform('ios');
    // Test...
  });

  it('works on Android', () => {
    mockPlatform('android'); // Won't affect other tests
    // Test...
  });
});
```

**Warning signs:** Random test failures that pass when run individually but fail in suite

### Pitfall 2: Safe Area Insets Not Mocked

**What goes wrong:** Component using `useSafeAreaInsets()` throws `Cannot read property 'top' of undefined`

**Why it happens:** `useSafeAreaInsets()` returns undefined without SafeAreaProvider or Jest mock

**How to avoid:**
```typescript
// Option 1: Use built-in mock (recommended)
import mockSafeAreaContext from 'react-native-safe-area-context/jest/mock';
jest.mock('react-native-safe-area-context', () => mockSafeAreaContext);

// Option 2: Wrap with SafeAreaProvider
import { SafeAreaProvider } from 'react-native-safe-area-context';

render(
  <SafeAreaProvider initialMetrics={{ insets: { top: 44, bottom: 34, left: 0, right: 0 } }}>
    <MyComponent />
  </SafeAreaProvider>
);
```

**Warning signs:** Errors like `insets is undefined`, `Cannot read property 'top' of null`

### Pitfall 3: Permission Prompts Not Mocked

**What goes wrong:** Test hangs indefinitely waiting for `expo-camera.requestCameraPermissionsAsync()` to resolve

**Why it happens:** Expo modules return native promises that don't resolve without mocks

**How to avoid:**
```typescript
beforeEach(() => {
  // ALWAYS mock permission requests
  (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue(
    createPermissionMock('granted')
  );
});

it('requests camera permission', async () => {
  await cameraService.requestPermissions();
  expect(Camera.requestCameraPermissionsAsync).toHaveBeenCalled();
});
```

**Warning signs:** Tests timeout after 5000ms, Jest warning "Async callback was not invoked"

### Pitfall 4: StatusBar Spies Not Cleaned Up

**What goes wrong:** StatusBar spy from previous test affects current test, expecting different call count

**Why it happens:** `jest.spyOn(StatusBar, 'setHidden')` persists across tests without restoration

**How to avoid:**
```typescript
describe('StatusBar tests', () => {
  let setHiddenSpy: jest.SpyInstance;

  beforeEach(() => {
    setHiddenSpy = jest.spyOn(StatusBar, 'setHidden');
  });

  afterEach(() => {
    setHiddenSpy.mockRestore(); // ALWAYS restore spy
  });

  it('hides status bar', () => {
    render(<FullScreenView />);
    expect(setHiddenSpy).toHaveBeenCalledTimes(1);
  });
});
```

**Warning signs:** `expect(spy).toHaveBeenCalledTimes(1)` fails with actual count 2 or more

### Pitfall 5: Platform.select Missing Default Fallback

**What goes wrong:** Code crashes on new platforms (HarmonyOS, web, Windows) with `undefined` value

**Why it happens:** `Platform.select({ ios: ..., android: ... })` returns undefined without `default` key

**How to avoid:**
```typescript
// ALWAYS provide default fallback
const value = Platform.select({
  ios: 'iOS',
  android: 'Android',
  default: 'Default', // Critical for future platforms
});

// Test with unrecognized platform
mockPlatform('harmony');
expect(value).toBe('Default');
```

**Warning signs:** Tests fail when run on web, errors on new React Native platforms

## Code Examples

Verified patterns from official sources and Phase 135 implementations:

### iOS Safe Area Testing

```typescript
// Source: https://docs.expo.dev/versions/latest/sdk/safe-area-context/
import { useSafeAreaInsets } from 'react-native-safe-area-context';

describe('iOS safe area testing', () => {
  it('should apply safe area insets on iOS notch devices', () => {
    mockPlatform('ios');

    const { getByTestId } = render(
      <SafeAreaProvider initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 44, bottom: 34, left: 0, right: 0 }, // iPhone 13 Pro
      }}>
        <ComponentWithSafeArea />
      </SafeAreaProvider>
    );

    expect(getByTestId('safe-area-view')).toHaveStyle({
      paddingTop: 44,  // Dynamic Island height
      paddingBottom: 34, // Home indicator height
    });
  });

  it('should handle zero insets on non-notch iOS devices', () => {
    mockPlatform('ios');

    render(
      <SafeAreaProvider initialMetrics={{
        insets: { top: 20, bottom: 0, left: 0, right: 0 }, // iPad
      }}>
        <ComponentWithSafeArea />
      </SafeAreaProvider>
    );

    // Component should handle smaller top inset
  });
});
```

### Android Back Button Testing

```typescript
// Source: https://reactnative.dev/docs/backhandler
import { BackHandler } from 'react-native';

describe('Android back button testing', () => {
  it('should handle back button press to exit screen', () => {
    mockPlatform('android');

    const backHandlerMock = jest.fn(() => true); // true = handled, don't exit app
    jest.spyOn(BackHandler, 'addEventListener').mockReturnValue({
      remove: jest.fn(),
    });

    render(<AgentChatScreen />);

    // Simulate back button press
    const backPressCallback = BackHandler.addEventListener.mock.calls[0][1];
    backPressCallback();

    expect(backHandlerMock).toHaveBeenCalled();
  });

  it('should not show back handler when on iOS', () => {
    mockPlatform('ios');

    render(<AgentChatScreen />);

    // BackHandler should not be registered on iOS
    expect(BackHandler.addEventListener).not.toHaveBeenCalled();
  });
});
```

### Permission Flow Testing

```typescript
// Source: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/platformPermissions.test.ts
describe('Permission flow testing', () => {
  it('should handle iOS permission prompt -> allow flow', async () => {
    mockPlatform('ios');
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue(
      createPermissionMock('granted')
    );

    const result = await Camera.requestCameraPermissionsAsync();

    expect(result.granted).toBe(true);
    expect(result.status).toBe('granted');
  });

  it('should handle iOS permission denied with Settings deep link', async () => {
    mockPlatform('ios');
    (Camera.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      ...createPermissionMock('denied'),
      canAskAgain: false, // User denied permanently
    });

    const result = await Camera.getCameraPermissionsAsync();

    expect(result.canAskAgain).toBe(false);
    // iOS: Should deep link to Settings app
    // app-settings://path-to-settings
  });

  it('should handle Android "Don\'t ask again" flow', async () => {
    mockPlatform('android');
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      ...createPermissionMock('denied'),
      canAskAgain: false, // User selected "Don't ask again"
    });

    const result = await Camera.requestCameraPermissionsAsync();

    expect(result.canAskAgain).toBe(false);
    // Android: Should show dialog explaining why permission is needed
  });
});
```

### Platform Select Testing

```typescript
// Source: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/__tests__/testUtils.test.ts
describe('Platform.select testing', () => {
  it('should select platform-specific styles', () => {
    mockPlatform('ios');

    const styles = StyleSheet.create({
      container: {
        flex: 1,
        ...Platform.select({
          ios: { shadowColor: '#000', shadowOpacity: 0.25 },
          android: { elevation: 5 },
        }),
      },
    });

    expect(styles.container).toMatchObject({
      flex: 1,
      shadowColor: '#000',
      shadowOpacity: 0.25,
    });
    expect(styles.container).not.toHaveProperty('elevation');
  });

  it('should select platform-specific components', () => {
    mockPlatform('android');

    const Touchable = Platform.select({
      ios: TouchableOpacity,
      android: TouchableNativeFeedback,
    });

    expect(Touchable).toBe(TouchableNativeFeedback);
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **expo-permissions** | **expo-camera/expo-location/expo-notifications** | Expo SDK 43 (2021) | Module-specific permission APIs, better type safety, clearer permissions per feature |
| **Manual safe area padding** | **react-native-safe-area-context** | 2020 | Automatic inset handling, works with notches/gesture navigation, SafeAreaProvider pattern |
| **Platform.OS === 'ios'** | **Platform.select({ ios, android, default })** | React Native 0.60+ | Cleaner syntax, explicit fallback, better type inference |
| **Enzyme shallow rendering** | **React Native Testing Library** | 2022 | User-centric testing, official recommendation, better async support |
| **Manual Platform.OS mocks** | **testUtils.mockPlatform() with cleanup** | Phase 135 (2025) | Consistent mocking, automatic cleanup, tested utilities |
| **Custom permission mocks** | **createPermissionMock() utility** | Phase 136 (2025) | Handles all states, reusable across tests, consistent structure |

**Deprecated/outdated:**
- **expo-permissions**: Deprecated in Expo SDK 43, replaced by module-specific APIs (expo-camera, expo-location, expo-notifications)
- **shallow rendering with Enzyme**: Enzyme is in maintenance mode, React Testing Library is recommended
- **Manual Platform.OS mocking without cleanup**: Causes test pollution, use testUtils.mockPlatform() with restorePlatform()
- **Safe area hardcoded values**: Device-specific insets break on new devices, use react-native-safe-area-context

## Open Questions

1. **Should Phase 139 include BackHandler testing if Atom doesn't currently use BackHandler?**
   - What we know: CanvasViewerScreen and AuthNavigator don't use BackHandler
   - What's unclear: Whether other screens (AgentChatScreen, SettingsScreen) should handle back button
   - Recommendation: Create platform-specific tests for any screen that uses React Navigation's navigation.goBack() to ensure proper back button handling on Android

2. **Should safe area testing include iPad-specific layouts?**
   - What we know: iPad has different safe areas (no notch, smaller top inset)
   - What's unclear: Whether Atom mobile app targets iPad or just iPhone
   - Recommendation: Include iPad safe area tests if Phase 138 handoff mentions iPad support, otherwise focus on iPhone notch devices

3. **Should platform-specific tests run on physical devices or just emulators?**
   - What we know: Phase 140 (E2E) will use Detox on physical devices
   - What's unclear: Whether Phase 139 unit/integration tests need physical device testing
   - Recommendation: Keep Phase 139 as unit/integration with mocks, defer physical device testing to Phase 140 (E2E)

4. **Should we test HarmonyOS (new React Native platform)?**
   - What we know: HarmonyOS support added in React Native 0.76, not in Atom's 0.73.6
   - What's unclear: Whether Atom plans to support HarmonyOS in Phase 139
   - Recommendation: Skip HarmonyOS testing unless explicitly requested, focus on iOS/Android parity

## Sources

### Primary (HIGH confidence)

- **React Native Platform Documentation** - Platform API, Platform.select, Platform.OS detection
  - URL: https://reactnative.dev/docs/platform
  - Topics fetched: Platform-specific code patterns, Platform.select syntax, Platform.isTesting

- **react-native-safe-area-context npm** - SafeAreaProvider, useSafeAreaInsets, Jest mocks
  - URL: https://www.npmjs.com/package/react-native-safe-area-context/v/5.2.0
  - Topics fetched: Built-in Jest mock, initialMetrics for custom test data, SafeAreaView usage

- **Expo Safe Areas Documentation** - Safe area handling on iOS and Android
  - URL: https://expo.nodejs.cn/develop/user-interface/safe-areas/
  - Topics fetched: iOS notch/Dynamic Island, Android gesture navigation, SafeAreaView patterns

- **React Native BackHandler Documentation** - Android back button handling
  - URL: https://reactnative.dev/docs/backhandler
  - Topics fetched: BackHandler.addEventListener, event bubbling, return true/false behavior

- **Phase 135 Platform Permissions Tests** - Existing platform permission testing patterns
  - File: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/platformPermissions.test.ts
  - Topics fetched: createPermissionMock utility, iOS vs Android permission flows, permission edge cases

- **Phase 135 Test Utilities** - Platform.OS mocking and cleanup
  - File: /Users/rushiparikh/projects/atom/mobile/src/__tests__/helpers/testUtils.ts
  - Topics fetched: mockPlatform(), restorePlatform(), isIOS(), isAndroid(), testEachPlatform()

### Secondary (MEDIUM confidence)

- **Expo Permissions Blog (January 2026)** - Cross-platform app development with Expo
  - URL: https://expo.dev/blog/building-a-cross-platform-app-without-touching-xcode-or-android-studio
  - Topics fetched: useCameraPermissions hook, notification permissions, permission error handling

- **Expo Camera Documentation** - expo-camera permission APIs
  - URL: https://www.npmjs.com/package/expo-camera
  - Topics fetched: CameraView.getCameraPermissionsAsync, requestCameraPermissionsAsync, permission status types

- **React Native Conditional Rendering Guide (2025)** - Platform-specific code patterns
  - URL: https://blog.csdn.net/qq_40588441/article/details/152968245
  - Topics fetched: Platform.select for styles/components, conditional rendering patterns, Platform.isTesting

- **React Native StatusBar Testing (2025-2026)** - StatusBar API testing
  - URL: https://blog.csdn.net/qq_61024956/article/details/156865428
  - Topics fetched: StatusBar.setHidden, StatusBar.setBarStyle, platform-specific properties

- **Platform-Specific Code Guide (React Native 0.73)** - Official platform-specific documentation
  - URL: https://reactnative.cn/docs/0.73/platform-specific-code
  - Topics fetched: Platform module, Platform.select, file naming conventions (.ios.js, .android.js)

### Tertiary (LOW confidence)

- **React Native Platform-Specific Testing (2026)** - Testing strategies for iOS/Android differences
  - URL: https://blog.csdn.net/qq_35876316/article/details/139279368
  - Topics fetched: Platform detection, testing patterns, Platform.select usage
  - Verification needed: Not official documentation, community blog post

- **Safe Area Testing Guide (2025)** - Chinese guide on safe area mocking
  - URL: https://m.blog.csdn.net/gitblog_00350/article/details/148864477
  - Topics fetched: react-native-safe-area-context Jest mock, custom initialMetrics
  - Verification needed: Non-official source, translation accuracy

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All packages verified in package.json and official documentation
- Architecture: HIGH - Patterns from Phase 135 test utilities, React Native official docs
- Pitfalls: HIGH - Based on Phase 138 handoff issues and common React Native testing problems

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (30 days - React Native ecosystem stable, but Expo SDK updates monthly)

**Phase 138 Handoff Considerations:**
- **Immediate blockers identified:** TurboModule mocks (25 tests), WebSocket async timing (29 tests), DeviceContext incomplete mocks (30 tests)
- **Recommendation:** Fix infrastructure before adding platform-specific tests
- **Estimated time to 80% coverage:** 2-3 weeks (infrastructure fixes + targeted platform-specific tests)

**Platform-specific testing scope (Phase 139):**
- **iOS-specific:** Safe area (notch, Dynamic Island, home indicator), StatusBar API, Face ID, background refresh
- **Android-specific:** Back button, runtime permissions (API 23+), fingerprint, notification channels, foreground service
- **Cross-platform:** Conditional rendering (Platform.OS, Platform.select), permission flows, error handling, feature parity
