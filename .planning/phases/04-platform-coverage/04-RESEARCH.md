# Phase 4: Platform Coverage (Mobile + Desktop) - Research

**Researched:** February 11, 2026
**Domain:** React Native Testing (Expo), Tauri Desktop Testing, Cross-Platform Test Infrastructure
**Confidence:** MEDIUM

## Summary

Phase 4 focuses on implementing comprehensive test coverage for mobile (React Native/Expo) and desktop (Tauri) applications. The mobile directory has partial implementation with device contexts, services, and one existing test file (offlineSync.test.ts), while the desktop application exists in `frontend-nextjs/src-tauri/` with basic Tauri v2 configuration.

**Key findings:**
- **Mobile Stack:** Expo 50.0, React Native 0.73.6, with device capabilities (expo-camera, expo-location, expo-notifications, expo-local-authentication)
- **Testing Stack:** jest-expo preset already configured, React Native Testing Library (@testing-library/react-native 12.4.2), jest-expo ~50.0.0
- **Desktop Stack:** Tauri v2 (config shows schema v2), React frontend, Rust backend
- **Existing Mobile Tests:** One comprehensive offline sync test (507 lines) covering queue management, batch processing, conflict resolution, state persistence, and performance
- **Backend Integration:** Existing backend tests (`test_mobile_auth.py`, `test_device_governance.py`) provide patterns for mobile API testing

**Primary challenges:**
1. React Native testing requires mocking native modules (expo-camera, expo-location, expo-notifications, expo-local-authentication)
2. Platform-specific testing (iOS vs Android permission flows, biometric differences)
3. Tauri desktop testing is Rust-centric with mock runtime for integration tests
4. Cross-platform test organization requires separating shared logic from platform-specific implementations
5. Device capability testing without physical devices (mocking hardware)

**Primary recommendation:** Use jest-expo with React Native Testing Library for mobile component tests, mock Expo modules using jest.mock(), create platform-specific test suites using Platform.OS detection, and implement Tauri tests using Rust's built-in testing with mock runtime for integration tests. Follow the existing offlineSync.test.ts pattern for comprehensive service testing.

## Standard Stack

### Mobile Testing (React Native/Expo)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **jest** | 29.7.0 | Test runner | Industry standard, already configured in mobile/package.json |
| **jest-expo** | ~50.0.0 | Expo preset | Official Expo Jest configuration, handles native module mocking |
| **@testing-library/react-native** | 12.4.2 | Component testing | Recommended approach for React Native, focuses on user behavior |
| **@testing-library/jest-native** | 5.4.3 | Custom Jest matchers | Provides toBeDisabled(), toHaveTextContent(), etc. for React Native |
| **react-test-renderer** | 18.2.0 | Snapshot testing | Already installed, for component snapshot testing |

### Desktop Testing (Tauri)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Rust built-in testing** | Built-in | Unit & integration tests | Standard Rust testing, no dependencies needed |
| **Tauri mock runtime** | v2 | Integration testing | Official Tauri testing approach, tests without running desktop environment |
| **WebDriver** | W3C standard | E2E testing | Tauri v2 supports WebDriver interface for automated testing |

### Backend Mobile Integration Testing

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner | Already in use (Phases 1-3), consistent with backend tests |
| **FastAPI TestClient** | Built-in | API testing | Mobile backend API integration testing |
| **factory_boy** | 3.3+ | Test data | Already in use (6 factories from Phase 2) |
| **pytest-asyncio** | 0.21+ | Async tests | Required for mobile auth endpoints |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **@react-native-async-storage/async-storage** | 1.x | Storage mocking | Test local storage persistence (mock in tests) |
| **react-native-mmkv** | Latest | High-performance storage | Alternative storage, mock in tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| jest-expo | @testing-library/react-native alone | jest-expo provides Expo-specific mocks and preset configuration |
| React Native Testing Library | Enzyme | RNTL is maintained, Enzyme is deprecated for React Native |
| Tauri mock runtime | Selenium E2E | Mock runtime is faster, doesn't require running actual desktop |
| Rust testing | JavaScript testing | Rust backend requires Rust tests, JS can't test Rust code |

**Installation:**
```bash
# Mobile (already installed in mobile/package.json)
npm install --save-dev jest jest-expo @testing-library/react-native @testing-library/jest-native react-test-renderer

# Desktop (Rust - no additional installation needed)
# Rust testing is built-in: cargo test

# Backend mobile integration (already installed)
pip install pytest pytest-asyncio fastapi factory_boy
```

## Architecture Patterns

### Recommended Project Structure

```
mobile/
├── src/
│   ├── __tests__/               # Test files
│   │   ├── components/          # Component tests
│   │   │   ├── WorkflowsListScreen.test.tsx
│   │   │   ├── AgentChatScreen.test.tsx
│   │   │   └── CanvasViewerScreen.test.tsx
│   │   ├── screens/             # Screen integration tests
│   │   │   ├── workflows/
│   │   │   ├── agent/
│   │   │   └── analytics/
│   │   ├── services/            # Service tests (already exists)
│   │   │   ├── offlineSync.test.ts
│   │   │   ├── cameraService.test.ts
│   │   │   ├── locationService.test.ts
│   │   │   ├── notificationService.test.ts
│   │   │   └── agentService.test.ts
│   │   ├── contexts/            # Context provider tests
│   │   │   ├── AuthContext.test.tsx
│   │   │   └── DeviceContext.test.tsx
│   │   ├── platform/            # Platform-specific tests
│   │   │   ├── ios/
│   │   │   │   ├── permissions.test.ts
│   │   │   │   └── biometric.test.ts
│   │   │   └── android/
│   │   │       ├── permissions.test.ts
│   │   │       └── biometric.test.ts
│   │   └── helpers/             # Test helpers and mocks
│   │       ├── mockExpoModules.ts
│   │       ├── mockPermissions.ts
│   │       └── testUtils.ts
│   ├── components/
│   ├── screens/
│   ├── services/
│   └── contexts/
├── jest.setup.js                # NEW: Test setup (global mocks, custom matchers)
└── package.json                 # Already configured with jest-expo

frontend-nextjs/src-tauri/
├── tests/                       # NEW: Rust tests
│   ├── integration/             # Integration tests with mock runtime
│   │   ├── menu_bar_test.rs
│   │   ├── window_test.rs
│   │   └── backend_api_test.rs
│   └── unit/                    # Unit tests for Rust backend
│       ├── commands_test.rs
│       └── menu_test.rs
├── src/
│   ├── lib.rs                   # Main Rust entry point
│   └── menu.rs                  # Menu bar logic
└── tauri.conf.json             # Already configured (Tauri v2)

backend/tests/
├── test_mobile_*.py             # Already exist (auth, workflows, agent chat)
├── test_device_*.py             # Already exist (tool, governance)
└── factories/                   # Already exist (6 factories from Phase 2)
```

### Pattern 1: React Native Component Testing with RNTL

**What:** Test React Native components using React Native Testing Library, focusing on user interactions and behavior rather than implementation details.

**When to use:** Component testing for screens, UI components, and user interactions.

**Example:**
```typescript
// Source: https://oss.callstack.com/react-native-testing-library/
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import WorkflowsListScreen from '../../screens/workflows/WorkflowsListScreen';

// Mock Expo modules
jest.mock('expo-camera', () => ({
  requestCameraPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  getCameraPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
}));

jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  getForegroundPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
}));

describe('WorkflowsListScreen', () => {
  it('renders workflow list', () => {
    render(<WorkflowsListScreen />);
    expect(screen.getByText('Workflows')).toBeTruthy();
  });

  it('navigates to workflow detail on tap', async () => {
    const mockNavigate = jest.fn();
    render(<WorkflowsListScreen navigation={{ navigate: mockNavigate }} />);

    const workflowItem = screen.getByText('Test Workflow');
    fireEvent.press(workflowItem);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('WorkflowDetail', { workflowId: '123' });
    });
  });
});
```

### Pattern 2: Expo Module Mocking

**What:** Mock Expo native modules (camera, location, notifications, biometric) to test device capabilities without physical hardware.

**When to use:** Testing device permissions, service integration with native modules, and error handling.

**Example:**
```typescript
// Source: https://docs.expo.dev/develop/unit-testing/
// File: mobile/src/__tests__/helpers/mockExpoModules.ts

export const mockCamera = {
  requestCameraPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  getCameraPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  takePictureAsync: jest.fn(() => Promise.resolve({ uri: 'file:///test.jpg' })),
};

export const mockLocation = {
  requestForegroundPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  getForegroundPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  getCurrentPositionAsync: jest.fn(() => Promise.resolve({
    coords: { latitude: 37.7749, longitude: -122.4194 }
  })),
};

export const mockNotifications = {
  requestPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  getPermissionsAsync: jest.fn(() => Promise.resolve({ status: 'granted' })),
  scheduleNotificationAsync: jest.fn(() => Promise.resolve('notification-id')),
};

export const mockLocalAuthentication = {
  hasHardwareAsync: jest.fn(() => Promise.resolve(true)),
  isEnrolledAsync: jest.fn(() => Promise.resolve(true)),
  authenticateAsync: jest.fn(() => Promise.resolve({ success: true })),
};

// In jest.setup.js:
jest.mock('expo-camera', () => mockCamera);
jest.mock('expo-location', () => mockLocation);
jest.mock('expo-notifications', () => mockNotifications);
jest.mock('expo-local-authentication', () => mockLocalAuthentication);
```

### Pattern 3: Platform-Specific Testing

**What:** Test platform-specific code paths using Platform.OS detection and Platform.select().

**When to use:** Testing iOS vs Android differences, permission flows, biometric authentication (Face ID vs fingerprint).

**Example:**
```typescript
// Source: https://reactnative.dev/docs/platform-specific-code
import { Platform } from 'react-native';
import { render, screen } from '@testing-library/react-native';

describe('Platform-specific behavior', () => {
  beforeEach(() => {
    // Mock Platform.OS
    jest.spyOn(Platform, 'OS', 'get').mockReturnValue('ios');
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('shows iOS-specific biometric prompt', () => {
    jest.spyOn(Platform, 'OS', 'get').mockReturnValue('ios');
    const { getByText } = render(<BiometricAuth />);
    expect(getByText('Use Face ID')).toBeTruthy();
  });

  it('shows Android-specific biometric prompt', () => {
    jest.spyOn(Platform, 'OS', 'get').mockReturnValue('android');
    const { getByText } = render(<BiometricAuth />);
    expect(getByText('Use Fingerprint')).toBeTruthy();
  });
});
```

### Pattern 4: Tauri Desktop Testing with Rust

**What:** Test Tauri Rust backend using Rust's built-in testing with mock runtime for integration tests.

**When to use:** Testing Tauri commands, menu bar functionality, window management, and backend API integration.

**Example:**
```rust
// Source: https://v2.tauri.app/develop/tests/
// File: frontend-nextjs/src-tauri/tests/integration/menu_bar_test.rs

#[cfg(test)]
mod tests {
    use tauri::Manager;
    use super::*;

    #[test]
    fn test_menu_creation() {
        let menu = Menu::new();
        assert!(menu.items().len() > 0);
    }

    #[test]
    fn test_menu_item_label() {
        let item = MenuItem::new("File", true, None);
        assert_eq!(item.label(), Some("File"));
    }

    #[test(tokio::test)]
    async fn test_backend_command() {
        // Test Tauri command with mock runtime
        let result = some_tauri_command("test_input").await;
        assert_eq!(result, Ok("expected_output"));
    }
}
```

### Pattern 5: Backend Mobile API Integration Testing

**What:** Test mobile backend API endpoints using FastAPI TestClient and factory_boy fixtures.

**When to use:** Testing mobile authentication, device registration, workflow API endpoints.

**Example:**
```python
# Source: backend/tests/test_mobile_auth.py (already exists)
from fastapi.testclient import TestClient
from core.models import MobileDevice
from factories.user_factory import UserFactory

@pytest.mark.asyncio
async def test_mobile_login_success(db_session, test_user):
    """Test successful mobile login with device registration."""
    with patch('core.auth.verify_password', return_value=True):
        result = await authenticate_mobile_user(
            email=test_user.email,
            password="test_password",
            device_token="new_device_token",
            platform="ios",
            db=db_session
        )

        assert result is not None
        assert "access_token" in result
        assert "device_id" in result
```

### Anti-Patterns to Avoid

- **Testing implementation details:** Don't test component state directly, test user behavior (use RNTL queries, not state access)
- **Skipping platform differences:** Don't assume iOS and Android behave identically (permissions, biometric, notification flows differ)
- **Mocking everything:** Don't over-mock; test integration points with real Expo modules where possible
- **Ignoring Tauri mock runtime:** Don't test Tauri by spawning actual desktop processes (use mock runtime)
- **Hardcoding platform-specific values:** Don't hardcode iOS/Android behavior; use Platform.OS detection

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| React Native component testing | Custom render utilities | React Native Testing Library | Battle-tested, maintained, handles async updates, deep rendering |
| Expo module mocking | Manual mock objects | jest.mock() with jest-expo preset | jest-expo provides pre-configured mocks for all Expo modules |
| Platform detection | Custom platform detection | Platform.OS and Platform.select() | Official React Native API, handles edge cases |
| Tauri integration testing | Spawning desktop processes | Tauri mock runtime | Faster, no UI required, tests backend logic in isolation |
| Test data generation | Hardcoded test users | factory_boy (already in use) | Dynamic data, avoids ID collisions, relationships handled automatically |
| Async testing | Manual promise handling | React Native Testing Library's waitFor | Handles act() updates, flaky-free async testing |

**Key insight:** Cross-platform testing has unique challenges (native modules, hardware capabilities, platform differences). Standard testing libraries handle these edge cases better than custom solutions.

## Common Pitfalls

### Pitfall 1: Expo Module Mocking Not Working
**What goes wrong:** Jest tests fail with "Cannot read property 'askAsync' of undefined" when testing Expo modules.

**Why it happens:** jest-expo preset doesn't mock all native modules by default (see [GitHub issue #26893](https://github.com/expo/expo/issues/26893)).

**How to avoid:**
- Always create explicit mocks in jest.setup.js for each Expo module used
- Use jest.mock() before importing components that use native modules
- Verify mocks are loaded by checking setupFilesAfterEnv in jest.config.js

**Warning signs:** Tests pass in development but fail in CI, or "TypeError: Cannot read properties of undefined" errors.

### Pitfall 2: Platform-Specific Code Not Tested
**What goes wrong:** iOS-only or Android-only features are never tested, leading to runtime crashes on one platform.

**Why it happens:** Developers test on one platform only, or Platform.OS is always mocked to 'ios' in tests.

**How to avoid:**
- Create separate test suites for iOS and Android using describe blocks
- Use test.each() to run the same test on both platforms
- Mock Platform.OS to both 'ios' and 'android' in different test suites

**Warning signs:** Skipped tests or TODO comments for platform-specific features.

### Pitfall 3: Biometric Authentication Testing on Emulators
**What goes wrong:** Biometric tests fail on emulators without enrolled fingerprints/Face ID.

**Why it happens:** Emulators don't have biometric hardware, expo-local-authentication checks for hardware availability.

**How to avoid:**
- Mock hasHardwareAsync() to return true
- Mock isEnrolledAsync() to return true
- Mock authenticateAsync() to return { success: true } for success scenarios
- Test failure scenarios by mocking { success: false }

**Warning signs:** Tests pass on physical devices but fail on CI emulators.

### Pitfall 4: Tauri Tests Spawning Actual Desktop
**What goes wrong:** Tauri integration tests are slow, flaky, or require a GUI environment.

**Why it happens:** Tests don't use Tauri's mock runtime, instead spawning actual desktop processes.

**How to avoid:**
- Use Tauri's mock runtime for integration tests (see [Tauri testing docs](https://v2.tauri.app/develop/tests/))
- Only use E2E tests for critical user flows, not for unit tests
- Mock external dependencies (file system, network) in Rust tests

**Warning signs:** Tests take >10 seconds, fail in headless CI environments.

### Pitfall 5: AsyncStorage Not Mocked
**What goes wrong:** Tests fail with "AsyncStorage is not defined" or storage operations don't persist between test runs.

**Why it happens:** AsyncStorage is a native module not automatically mocked by jest-expo.

**How to avoid:**
- Mock @react-native-async-storage/async-storage in jest.setup.js
- Use in-memory storage for tests (or mock AsyncStorage with a Map)
- Clear AsyncStorage in beforeEach() to ensure test isolation

**Warning signs:** Tests pass individually but fail when run together, or storage-related errors.

### Pitfall 6: Platform Permission Testing Without Real Devices
**What goes wrong:** Permission tests (camera, location, notifications) fail because permissions are always "granted" in mocks.

**Why it happens:** Developers mock all permission requests to return 'granted', never testing denial flows.

**How to avoid:**
- Test both granted and denied permission scenarios
- Test permission flow after user changes settings
- Mock permission status to 'undetermined' for first-request scenarios
- Verify error handling and user prompts for denied permissions

**Warning signs:** All permission tests have status: 'granted' hardcoded in mocks.

## Code Examples

Verified patterns from official sources:

### React Native Component Test with Platform Detection

```typescript
// Source: https://reactnative.dev/docs/platform-specific-code
import { render, screen } from '@testing-library/react-native';
import { Platform } from 'react-native';
import BiometricScreen from '../screens/BiometricScreen';

describe('BiometricScreen', () => {
  it('shows Face ID prompt on iOS', () => {
    jest.spyOn(Platform, 'OS', 'get').mockReturnValue('ios');
    render(<BiometricScreen />);
    expect(screen.getByText(/face id/i)).toBeTruthy();
  });

  it('shows fingerprint prompt on Android', () => {
    jest.spyOn(Platform, 'OS', 'get').mockReturnValue('android');
    render(<BiometricScreen />);
    expect(screen.getByText(/fingerprint/i)).toBeTruthy();
  });
});
```

### Expo Camera Mocking

```typescript
// Source: https://docs.expo.dev/develop/unit-testing/
jest.mock('expo-camera', () => ({
  Camera: {
    requestCameraPermissionsAsync: jest.fn(),
    getCameraPermissionsAsync: jest.fn(),
  },
  Constants: {
    Type: {
      back: 'back',
      front: 'front',
    },
  },
}));

import { render } from '@testing-library/react-native';
import CameraScreen from '../CameraScreen';

test('requests camera permission on mount', async () => {
  const mockRequestPermission = require('expo-camera').Camera.requestCameraPermissionsAsync;
  mockRequestPermission.mockResolvedValue({ status: 'granted' });

  render(<CameraScreen />);

  expect(mockRequestPermission).toHaveBeenCalled();
});
```

### Tauri Integration Test with Mock Runtime

```rust
// Source: https://v2.tauri.app/develop/tests/
#[cfg(test)]
mod tests {
    use tauri::test::mock_context;

    #[test]
    fn test_menu_creation() {
        let app = mock_context();
        let menu = Menu::with_items(app, &[...]);
        assert_eq!(menu.items().len(), 3);
    }
}
```

### Backend Mobile Device Registration Test

```python
# Source: backend/tests/test_mobile_auth.py (existing pattern)
@pytest.mark.asyncio
async def test_mobile_device_registration(db_session: Session, test_user):
    """Test device registration on mobile login."""
    with patch('core.auth.verify_password', return_value=True):
        result = await authenticate_mobile_user(
            email=test_user.email,
            password="test_password",
            device_token="new_device_token",
            platform="ios",
            device_info={"model": "iPhone 14", "os_version": "17.0"},
            db=db_session
        )

        # Verify device was created
        device = db_session.query(MobileDevice).filter(
            MobileDevice.device_token == "new_device_token"
        ).first()
        assert device is not None
        assert device.platform == "ios"
        assert device.status == "active"
```

### Offline Sync Test (Existing Pattern)

```typescript
// Source: mobile/src/__tests__/services/offlineSync.test.ts (already exists, 507 lines)
import AsyncStorage from '@react-native-async-storage/async-storage';
import { offlineSyncService } from '../../services/offlineSyncService';

jest.mock('@react-native-async-storage/async-storage');

describe('OfflineSyncService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    offlineSyncService.clearQueue();
  });

  test('should add action to queue', async () => {
    const action = {
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
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Enzyme for React Native | React Native Testing Library | 2022-2023 | Enzyme deprecated, RNTL is official standard |
| Manual native module mocks | jest-expo preset with auto-mocking | Expo 40+ (2023) | Less mock boilerplate, official Expo support |
| Detox E2E for all tests | Jest + RNTL for unit/integration, Detox for E2E only | 2024 | Faster test suite, better separation of concerns |
| Tauri v1 testing | Tauri v2 mock runtime | October 2024 | Tauri v2 introduces mock runtime for integration tests |
| Platform-specific test files | Platform.OS detection in shared test files | 2023-2024 | Reduced duplication, better cross-platform coverage |

**Deprecated/outdated:**
- **Enzyme:** Deprecated for React Native, use React Native Testing Library instead
- **expo-permissions:** Replaced by individual permission modules (expo-camera, expo-location, etc.)
- **Detox for unit testing:** Too slow, use Jest + RNTL for unit/integration tests
- **React Native 0.7x testing patterns:** Old async handling patterns replaced by React Native Testing Library's waitFor()

## Open Questions

1. **Tauri v2 testing documentation maturity**
   - What we know: Tauri v2 has official testing docs with mock runtime support
   - What's unclear: How mature are the testing patterns? Are there community best practices?
   - Recommendation: Start with Rust's built-in testing, adopt Tauri mock runtime once documentation stabilizes

2. **Expo 50 module mocking completeness**
   - What we know: jest-expo preset exists, but [issue #26893](https://github.com/expo/expo/issues/26893) shows not all modules are mocked
   - What's unclear: Which specific Expo 50 modules require manual mocking?
   - Recommendation: Create explicit mocks for all device capability modules (camera, location, notifications, local-authentication)

3. **Biometric authentication testing without physical devices**
   - What we know: Can mock expo-local-authentication, but real device behavior differs
   - What's unclear: Can we reliably test biometric failures, cancellations, and enrollment flows?
   - Recommendation: Mock for unit tests, use physical devices for E2E biometric flows (document as TODO)

4. **Tauri menu bar testing patterns**
   - What we know: Tauri supports menu creation, but testing menu interactions is unclear
   - What's unclear: How to test menu item clicks, tray icon interactions, window menu updates?
   - Recommendation: Research Tauri menu testing examples, start with Rust unit tests for menu logic

5. **Cross-platform test organization**
   - What we know: React Native has Platform.OS, but test file organization is unclear
   - What's unclear: Should we separate ios/ and android/ test directories, or use describe blocks?
   - Recommendation: Use describe blocks for platform-specific tests, organize by feature (components/, services/)

## Sources

### Primary (HIGH confidence)

- [React Native Testing Library Official Site](https://oss.callstack.com/react-native-testing-library/) - Official RNTL documentation with examples
- [Expo Unit Testing Documentation](https://docs.expo.dev/develop/unit-testing/) - Official Expo Jest setup and module mocking (July 2025)
- [Tauri Tests Documentation](https://v2.tauri.app/develop/tests/) - Official Tauri v2 testing with mock runtime (February 22, 2025)
- [React Native Platform-Specific Code](https://reactnative.dev/docs/platform-specific-code) - Official Platform.OS and Platform.select() docs (December 16, 2025)
- [Testing - React Native](https://reactnative.dev/docs/testing-overview) - Official React Native testing overview (January 16, 2026)

### Secondary (MEDIUM confidence)

- [Unit Testing React Native with Jest - OneUptime](https://oneuptime.com/blog/post/2026-01-15-react-native-jest-testing/view) - Modern 2026 guide for Jest + RNTL (January 15, 2026)
- [Platform-Specific Code in React Native - OneUptime](https://oneuptime.com/blog/post/2026-01-15-react-native-platform-specific/view) - iOS vs Android patterns (January 15, 2026)
- [Testing React Native Apps on iOS and Android - BrowserStack](https://www.browserstack.com/guide/test-react-native-apps-ios-android) - Cross-platform testing strategies (December 4, 2025)
- [Tauri Architecture](https://v2.tauri.app/concept/architecture/) - Tauri v2 architecture and testing approach (February 22, 2025)
- [Master React Native Testing: Jest & Detox](https://codercrafter.in/blogs/react-native/master-react-native-testing-a-deep-dive-into-jest-detox) - Testing pyramid with Jest, RNTL, Detox
- [Jest problems with Expo 50 #26856 - GitHub](https://github.com/expo/expo/discussions/26856) - Expo 50 Jest configuration issues (July 2024)

### Tertiary (LOW confidence)

- [Simple Step-by-Step Detox for React Native Android 2026](https://medium.com/@svbala99/simple-step-by-step-setup-detox-for-react-native-android-e2e-testing-2026-ed497fd9d301) - Detox E2E setup guide (unverified 2026 date)
- [Jest Mocking Expo Permissions - Stack Overflow](https://stackoverflow.com/questions/56441730/jest-mocking-permissions-of-expo-typeerror-cannot-read-property-askasync-of-u) - Specific expo-permissions mocking issue (2019, outdated)
- [Test Biometric Authentication - BrowserStack](https://www.browserstack.com/docs/app-automate/appium/advanced-features/biometric-authentication) - Biometric testing on real devices (Appium-specific)
- [Tauri Menu Bar App Development - LinkedIn](https://www.linkedin.com/posts/mihirbagga_tauri-reactjs-rust-activity-7420759990690275328-wyZk) - Menu bar development post (January 24, 2026)

### Existing Codebase (HIGH confidence)

- `/Users/rushiparikh/projects/atom/mobile/src/__tests__/services/offlineSync.test.ts` - 507-line comprehensive test pattern (already exists)
- `/Users/rushiparikh/projects/atom/backend/tests/test_mobile_auth.py` - Backend mobile auth testing patterns (already exists)
- `/Users/rushiparikh/projects/atom/backend/tests/test_device_governance.py` - Device capability governance tests (already exists)
- `/Users/rushiparikh/projects/atom/mobile/package.json` - Jest + RNTL configuration (already installed)
- `/Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/tauri.conf.json` - Tauri v2 configuration (already exists)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are industry standards, versions verified from package.json and official docs
- Architecture: MEDIUM - RNTL patterns are well-documented, but Tauri testing patterns are less mature
- Pitfalls: MEDIUM - Expo and React Native pitfalls verified from GitHub issues, Tauri pitfalls inferred from Rust testing patterns

**Research date:** February 11, 2026
**Valid until:** March 13, 2026 (30 days - React Native/Expo ecosystem moves fast)

**Key uncertainties:**
1. Tauri v2 testing patterns are new (October 2024), community best practices still emerging
2. Expo 50 jest-expo module mocking has open issues (#26893, #26893)
3. Biometric testing without physical devices requires manual mocking verification
