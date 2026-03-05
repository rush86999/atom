# Phase 136: Mobile Device Features Testing - Research

**Researched:** March 4, 2026
**Domain:** React Native device feature testing (camera, location, notifications, offline sync)
**Confidence:** HIGH

## Summary

Phase 136 focuses on testing mobile device features (camera, location, notifications, offline sync) to achieve 80%+ coverage for these critical services. Building on Phase 135's stable test infrastructure, this phase will add comprehensive tests for device hardware integration, permission handling, network state management, and synchronization logic.

**Current State:**
- Test infrastructure stable (Phase 135 complete)
- Coverage baseline: 16.16% statements
- Test pass rate: 72.7% (818/1126 passing)
- Existing device service tests: cameraService.test.ts (53 tests), locationService.test.ts (47 tests), notificationService.test.ts (37 tests), offlineSync.test.ts (32 tests)

**Key Challenge:** Existing device tests have good coverage but need improvement in:
1. Hardware integration testing (actual device APIs mocked correctly)
2. Permission flow testing (granted → denied → undetermined transitions)
3. Error state testing (device unavailable, network failures, storage quota exceeded)
4. Cross-platform behavior testing (iOS vs Android differences)
5. GPS mocking for location accuracy testing
6. Network switching simulation for offline sync
7. Push notification flow testing

**Primary Recommendation:** Use Phase 135's stable test infrastructure and shared utilities (flushPromises, waitForCondition, resetAllMocks) to add comprehensive device feature tests with 80%+ target coverage. Focus on integration testing patterns that mock hardware APIs realistically while testing service layer logic thoroughly.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **jest-expo** | ~51.0 | Jest preset for Expo/React Native | Official Expo testing framework, preconfigured for React Native environment |
| **@testing-library/react-native** | ^12.0 | Component testing utilities | Industry standard for React component testing, focuses on user interactions |
| **@testing-library/jest-native** | ^5.0 | Custom Jest matchers (toBeVisible, etc.) | Provides React Native-specific assertions, better error messages |
| **react-test-renderer** | ^18.2 | React component tree rendering | Required by Testing Library for shallow rendering |

### Expo SDK Testing
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **expo-camera** | ~15.0 | Camera hardware access mock | Device camera integration for photo/video capture, barcode scanning |
| **expo-location** | ~17.0 | GPS/location services mock | Foreground/background location tracking, geofencing, geocoding |
| **expo-notifications** | ~0.28 | Push/local notifications mock | Notification permissions, scheduling, token registration, badge management |
| **@react-native-community/netinfo** | ^11.0 | Network state monitoring mock | Online/offline detection, connection type, network switching simulation |
| **expo-secure-store** | ~13.0 | Secure key-value storage mock | Encrypted storage for sensitive data (auth tokens, API keys) |
| **@react-native-async-storage/async-storage** | ^2.0 | Persistent key-value storage mock | Local data persistence, offline queue storage |
| **react-native-mmkv** | ^2.0 | Fast storage mock (already fixed in Phase 135) | High-performance storage for offline sync queues, settings |

### Test Utilities (Phase 135)
| Utility | Purpose | When to Use |
|---------|---------|-------------|
| **flushPromises()** | Resolve pending promises with fake timers | After async operations (camera capture, location fetch, sync) |
| **waitForCondition()** | Wait for state change with timeout | Location updates, network state changes, sync completion |
| **resetAllMocks()** | Reset all mocks and timers | beforeEach cleanup for service singleton tests |
| **setupFakeTimers()** | Configure fake timers | Tests with setTimeout/setInterval (heartbeat, retry logic) |
| **advanceTimersByTime()** | Fast-forward fake timers | Simulate time passing (sync retry delays, location tracking intervals) |
| **createMockWebSocket()** | Mock WebSocket with realistic behavior | Testing WebSocket-dependent services (device communication) |

### Testing Patterns (Phase 135 Established)
| Pattern | Purpose | When to Use |
|---------|---------|-------------|
| **Singleton Service Testing** | Test singleton services with state reset | Camera, Location, Notification, OfflineSync services |
| **Mock Module Pattern** | Mock Expo modules globally | jest.mock('expo-camera') in jest.setup.js |
| **Async Testing with Fake Timers** | Reliable async test execution | setTimeout/setInterval-based operations (heartbeat, sync retry) |
| **Permission Flow Testing** | Test permission state transitions | granted → denied → undetermined → granted |
| **Error State Testing** | Test graceful degradation | Device unavailable, network failure, storage quota exceeded |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **expo-camera** | react-native-vision-camera | Expo Camera official SDK support, simpler API; Vision Camera more powerful but requires native code |
| **expo-location** | react-native-geolocation-service | Expo Location official SDK support, unified API; community library has more features but more complex |
| **expo-notifications** | react-native-push-notification | Expo Notifications official SDK support, managed workflow; community library requires native configuration |
| **@react-native-community/netinfo** | react-native-netinfo | Same library (community maintained is standard) |
| **Jest + Testing Library** | Detox (E2E) | Detox for end-to-end UI testing; Jest for unit/integration testing (complementary, not replacement) |

**Installation:**
```bash
# All dependencies already installed in Phase 135
npm install --save-dev jest-expo @testing-library/react-native @testing-library/jest-native

# Expo modules (SDK 51)
npx expo install expo-camera expo-location expo-notifications expo-secure-store
npm install @react-native-community/netinfo @react-native-async-storage/async-storage react-native-mmkv
```

## Architecture Patterns

### Recommended Project Structure
```
mobile/src/__tests__/
├── services/
│   ├── cameraService.test.ts           # Camera hardware integration (already exists, enhance)
│   ├── locationService.test.ts          # GPS/location tracking (already exists, enhance)
│   ├── notificationService.test.ts      # Push/local notifications (already exists, enhance)
│   ├── offlineSyncService.test.ts       # Offline queue & sync (already exists, enhance)
│   └── integration/
│       ├── devicePermissions.integration.test.ts  # Permission flow integration
│       └── offlineSyncNetwork.integration.test.ts # Network switching integration
├── components/
│   └── device/
│       ├── CameraCapture.test.tsx       # Camera UI component
│       ├── LocationMap.test.tsx          # Location display component
│       └── NotificationPermission.test.tsx  # Permission request component
└── helpers/
    ├── testUtils.ts                     # Shared utilities (already exists, 622 lines)
    └── deviceMocks.ts                   # Device-specific mock factories (create)
```

### Pattern 1: Expo Module Mocking in jest.setup.js
**What:** Global mock configuration for all Expo device modules
**When to use:** All device feature tests requiring hardware API mocking
**Example:**
```javascript
// Source: mobile/jest.setup.js (already implemented in Phase 135)
jest.mock('expo-camera', () => {
  const requestCameraPermissionsAsync = jest.fn().mockResolvedValue({
    status: 'granted',
    canAskAgain: true,
    granted: true,
    expires: 'never',
  });

  return {
    CameraView: {
      requestCameraPermissionsAsync,
      getCameraPermissionsAsync: jest.fn().mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      }),
      isAvailableAsync: jest.fn().mockResolvedValue(true),
      takePictureAsync: jest.fn().mockResolvedValue({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
      }),
      recordAsync: jest.fn().mockResolvedValue({
        uri: 'file:///mock/video.mp4',
      }),
      stopRecording: jest.fn().mockResolvedValue({
        uri: 'file:///mock/video.mp4',
      }),
    },
    CameraType: {
      Front: 'front',
      Back: 'back',
    },
  };
});
```

### Pattern 2: Permission Flow Testing
**What:** Test all permission state transitions (undetermined → granted → denied)
**When to use:** All device services requiring permissions (camera, location, notifications)
**Example:**
```typescript
// Source: mobile/src/__tests__/services/cameraService.test.ts (already exists)
describe('Permissions', () => {
  test('should request camera permissions and return granted', async () => {
    (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });

    const status = await cameraService.requestPermissions();

    expect(status).toBe('granted');
    expect(CameraView.requestCameraPermissionsAsync).toHaveBeenCalledTimes(1);
  });

  test('should handle permission denied', async () => {
    (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
      canAskAgain: false,
      granted: false,
      expires: 'never',
    });

    const status = await cameraService.requestPermissions();

    expect(status).toBe('denied');
  });

  test('should handle undetermined permission status', async () => {
    (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'undetermined',
      canAskAgain: true,
      granted: false,
      expires: 'never',
    });

    const status = await cameraService.requestPermissions();

    expect(status).toBe('undetermined');
  });
});
```

### Pattern 3: GPS Mocking for Location Testing
**What:** Mock location coordinates with varying accuracy levels
**When to use:** Location service testing (getCurrentPosition, geofencing, distance calculation)
**Example:**
```typescript
// Source: mobile/src/__tests__/services/locationService.test.ts (already exists)
const mockLocation = {
  coords: {
    latitude: 37.7749,
    longitude: -122.4194,
    altitude: 100,
    accuracy: 10,
    altitudeAccuracy: 5,
    heading: 45,
    speed: 5.5,
  },
  timestamp: Date.now(),
};

describe('Current Location', () => {
  test('should get current location with valid coordinates', async () => {
    await locationService.requestPermissions();

    const locationInfo = await locationService.getCurrentLocation();

    expect(locationInfo).toEqual({
      latitude: 37.7749,
      longitude: -122.4194,
      altitude: 100,
      accuracy: 10,
      altitudeAccuracy: 5,
      heading: 45,
      speed: 5.5,
      timestamp: mockLocation.timestamp,
    });
  });

  test('should calculate distance between two coordinates (Haversine)', () => {
    const sanFrancisco = { latitude: 37.7749, longitude: -122.4194 };
    const losAngeles = { latitude: 34.0522, longitude: -118.2437 };

    const distance = locationService.calculateDistance(sanFrancisco, losAngeles);

    // SF to LA is approximately 559 km
    expect(distance).toBeGreaterThan(558000);
    expect(distance).toBeLessThan(560000);
  });
});
```

### Pattern 4: Network Switching Simulation for Offline Sync
**What:** Simulate online → offline → online transitions to test sync behavior
**When to use:** Offline sync service testing (queue persistence, sync retry, conflict resolution)
**Example:**
```typescript
// Source: mobile/src/__tests__/services/offlineSync.test.ts (already exists)
describe('Network Switching', () => {
  test('should trigger sync when connection restored', async () => {
    const { apiService } = require('../../services/api');
    apiService.post.mockResolvedValue({ success: true, data: {} });

    const NetInfo = require('@react-native-community/netinfo');
    const addEventListenerMock = NetInfo.addEventListener;

    // Queue actions while offline
    NetInfo.fetch.mockResolvedValue({ isConnected: false });
    await offlineSyncService.queueAction(
      'agent_message',
      { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
      'normal',
      'user_1',
      'device_1'
    );

    // Simulate connection restored
    const callback = addEventListenerMock.mock.calls[0][0];
    callback({ isConnected: true });

    // Should trigger sync automatically
    const state = await offlineSyncService.getSyncState();
    expect(state).toBeDefined();
  });

  test('should process in batches with progress tracking', async () => {
    const { apiService } = require('../../services/api');
    apiService.post.mockResolvedValue({ success: true, data: {} });

    // Queue 15 actions (batch size is 10)
    for (let i = 0; i < 15; i++) {
      await offlineSyncService.queueAction(
        'agent_message',
        { agentId: `agent_${i}`, message: `Test ${i}`, sessionId: `session_${i}` },
        'normal',
        'user_1',
        'device_1'
      );
    }

    const result = await offlineSyncService.triggerSync();

    // Should process all 15 actions in batches
    expect(result.synced).toBe(15);
  });
});
```

### Pattern 5: Notification Permission and Scheduling Testing
**What:** Test notification permissions, local scheduling, and push token registration
**When to use:** Notification service testing (permission flows, scheduling, badge management)
**Example:**
```typescript
// Source: mobile/src/__tests__/services/notificationService.test.ts (already exists)
describe('Permissions', () => {
  test('should initialize with permission check', async () => {
    await notificationService.initialize();
    expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
  });

  test('should request permissions with iOS settings', async () => {
    const status = await notificationService.requestPermissions();
    expect(status).toBe('granted');
    expect(Notifications.requestPermissionsAsync).toHaveBeenCalledWith({
      ios: { allowAlert: true, allowBadge: true, allowSound: true },
      android: {},
    });
  });
});

describe('Local Notifications', () => {
  test('should send local notification', async () => {
    await notificationService.initialize();

    await notificationService.sendLocalNotification({
      title: 'Test',
      body: 'Body',
      data: { key: 'value' },
    });

    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        content: expect.objectContaining({
          title: 'Test',
          body: 'Body',
          data: { key: 'value' },
        }),
      })
    );
  });

  test('should schedule notification with delay', async () => {
    await notificationService.initialize();

    const id = await notificationService.scheduleNotification(
      { title: 'Delayed', body: 'Test' },
      10
    );

    expect(id).toBe('notification-id-123');
    expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        trigger: { seconds: 10 },
      })
    );
  });
});
```

### Anti-Patterns to Avoid

- **Don't use real device APIs in tests:** Always mock expo-camera, expo-location, expo-notifications hardware APIs. Real devices require physical testing (E2E with Detox), not unit testing.
- **Don't skip permission flow testing:** Test all permission states (granted, denied, undetermined). Permission handling is critical for mobile UX.
- **Don't ignore platform differences:** Test iOS vs Android behavior differences (camera auto-save, background permissions, notification channels).
- **Don't forget error states:** Test device unavailable, network failures, storage quota exceeded, permission denied scenarios.
- **Don't use real timers in async tests:** Use fake timers with flushPromises() for reliable async testing. Real timers cause flaky tests.
- **Don't test React Native internals:** Focus on testing your service layer logic, not React Native framework code.
- **Don't skip cleanup:** Always reset mocks in afterEach (resetAllMocks()) to prevent test pollution.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Expo module mocks** | Custom mock functions for each Expo module | jest.mock() in jest.setup.js | Expo modules have complex internal structure, official patterns established |
| **Permission flow testing** | Custom permission state management | Expo's PermissionStatus enum + state transitions | Expo permission API is standardized, custom implementations miss edge cases |
| **GPS coordinate mocking** | Custom location objects | expo-location mock with realistic coordinate objects | Real location data structure is complex (accuracy, altitude, heading, speed) |
| **Network state simulation** | Custom online/offline flags | @react-native-community/netinfo mock | Network state has multiple properties (isConnected, type, details, isInternetReachable) |
| **Async test utilities** | Custom promise/timeout utilities | Phase 135's flushPromises, waitForCondition | Fake timers require careful handling, existing utilities are battle-tested |
| **Storage mocking** | Custom Map-based storage | Phase 135's MMKV mock with getString/setString | MMKV API is specific (String returns, not getString), custom mocks fail |
| **Notification scheduling** | Custom timeout/delay logic | expo-notifications mock with scheduleNotificationAsync | Notification scheduling has platform differences (iOS vs Android channels) |
| **Geofencing calculations** | Custom distance/position logic | expo-location's geofencing or Haversine formula | Geofencing requires accurate distance calculations (Haversine is standard) |

**Key insight:** Device feature testing requires accurate mocking of platform-specific APIs (camera hardware, GPS chipset, notification system, network stack). Hand-rolled mocks inevitably miss platform differences and edge cases. Use Expo's official mock patterns and Phase 135's established utilities.

## Common Pitfalls

### Pitfall 1: Module Import Errors
**What goes wrong:** Tests fail with "Cannot find module 'expo-sharing'" or similar errors
**Why it happens:** Expo modules imported conditionally in components (e.g., `if (Platform.OS !== 'web')`) but not mocked in jest.setup.js
**How to avoid:** Add all Expo module mocks to jest.setup.js, even if not direct dependencies. Phase 135 already added expo-sharing and expo-file-system mocks.
**Warning signs:** Test fails before execution, "Cannot find module" errors, import errors in component files

### Pitfall 2: MMKV getString Mock Issues
**What goes wrong:** Tests fail with "mmkv.getString is not a function" error
**Why it happens:** MMKV mock structure doesn't match actual API (getString returns String, not getString)
**How to avoid:** Use Phase 135's fixed MMKV mock (lines 442-523 in jest.setup.js) with getString returning String/null
**Warning signs:** Type errors in mock, "is not a function" errors, mock returns undefined

### Pitfall 3: Async Timing Issues with Fake Timers
**What goes wrong:** Tests timeout or fail intermittently due to unresolved promises
**Why it happens:** Using waitFor() with jest.useFakeTimers() doesn't work (waitFor uses real timers)
**How to avoid:** Use Phase 135's flushPromises() and waitForCondition() utilities instead of waitFor()
**Warning signs:** Tests pass sometimes and fail sometimes, "timeout" errors, async state not updating

### Pitfall 4: Platform-Specific Behavior Not Tested
**What goes wrong:** Tests pass on iOS simulator but fail on Android emulator (or vice versa)
**Why it happens:** Not testing platform differences (camera auto-save, background permissions, notification channels)
**How to avoid:** Create separate test suites for iOS and Android behavior using Platform.OS mocking
**Warning signs:** Platform-specific code paths untested, conditional logic not covered

### Pitfall 5: Singleton Service State Pollution
**What goes wrong:** Tests pass individually but fail when run together
**Why it happens:** Service singleton state persists across tests (camera permission, location tracking, sync queue)
**How to avoid:** Call service._resetState() or resetAllMocks() in beforeEach for all singleton services
**Warning signs:** Tests pass alone but fail in suite, state leaking between tests

### Pitfall 6: Network Switching Not Properly Simulated
**What goes wrong:** Offline sync tests don't actually test network switching behavior
**Why it happens:** NetInfo mock doesn't trigger state change callbacks, tests don't simulate online → offline → online
**How to avoid:** Call NetInfo.addEventListener callback manually to trigger network state changes
**Warning signs:** Sync tests always pass, no network state variation tested

### Pitfall 7: GPS Coordinates Not Realistic
**What goes wrong:** Location tests use unrealistic coordinates (0, 0 or simple integers)
**Why it happens:** Mock location data doesn't match real GPS accuracy and variability
**How to avoid:** Use realistic coordinate objects with altitude, accuracy, heading, speed fields
**Warning signs:** Distance calculations always return same values, geofencing tests too simple

### Pitfall 8: Notification Scheduling Timing Issues
**What goes wrong:** Scheduled notification tests fail with "notification not found" errors
**Why it happens:** Tests don't advance fake timers to trigger scheduled notifications
**How to avoid:** Use advanceTimersByTime() to fast-forward to scheduled notification time
**Warning signs:** Schedule tests timeout, notification IDs not found, trigger never fires

## Code Examples

Verified patterns from existing tests (Phase 135):

### Camera Permission and Capture Testing
```typescript
// Source: mobile/src/__tests__/services/cameraService.test.ts (already exists)
describe('Photo Capture', () => {
  beforeEach(() => {
    // Ensure permission is granted for capture tests
    (CameraView.getCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      granted: true,
      canAskAgain: true,
      expires: 'never',
    });

    mockCameraRef.current.takePictureAsync.mockResolvedValue({
      uri: 'file:///mock/photo.jpg',
      width: 1920,
      height: 1080,
    });
  });

  test('should take picture successfully', async () => {
    const media = await cameraService.takePicture(mockCameraRef);

    expect(media).toEqual({
      uri: 'file:///mock/photo.jpg',
      type: 'photo',
      width: 1920,
      height: 1080,
      size: 1024000,
    });
    expect(mockCameraRef.current.takePictureAsync).toHaveBeenCalledTimes(1);
  });

  test('should return null when permission not granted', async () => {
    (CameraView.requestCameraPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
      granted: false,
      canAskAgain: false,
      expires: 'never',
    });

    await cameraService.requestPermissions();

    const media = await cameraService.takePicture(mockCameraRef);

    expect(media).toBeNull();
  });
});
```

### Location Service with Geofencing
```typescript
// Source: mobile/src/__tests__/services/locationService.test.ts (already exists)
describe('Geofencing', () => {
  test('should check if point is within geofence', () => {
    const center = { latitude: 37.7749, longitude: -122.4194 };
    const region = {
      id: 'region_1',
      identifier: 'SF Downtown',
      latitude: center.latitude,
      longitude: center.longitude,
      radius: 100, // 100 meters
      notifyOnEntry: true,
      notifyOnExit: true,
    };

    const insidePoint = { latitude: 37.7749, longitude: -122.4194 };
    const outsidePoint = { latitude: 37.78, longitude: -122.42 };

    expect(locationService.isWithinGeofence(insidePoint, region)).toBe(true);
    expect(locationService.isWithinGeofence(outsidePoint, region)).toBe(false);
  });

  test('should detect geofence boundary', () => {
    const center = { latitude: 37.7749, longitude: -122.4194 };
    const region = {
      id: 'region_1',
      identifier: 'SF Downtown',
      latitude: center.latitude,
      longitude: center.longitude,
      radius: 100,
      notifyOnEntry: true,
      notifyOnExit: true,
    };

    // Point approximately 90 meters away
    const nearBoundaryPoint = {
      latitude: 37.7749 + (90 / 111320),
      longitude: -122.4194,
    };

    expect(locationService.isWithinGeofence(nearBoundaryPoint, region)).toBe(true);
  });
});
```

### Notification Permission and Scheduling
```typescript
// Source: mobile/src/__tests__/services/notificationService.test.ts (already exists)
describe('Permissions', () => {
  test('should return denied for simulator', async () => {
    (Device as any).isDevice = false;
    const status = await notificationService.requestPermissions();
    expect(status).toBe('denied');
  });
});

describe('Local Notifications', () => {
  test('should not send without permission', async () => {
    notificationService._resetState();
    (Notifications.getPermissionsAsync as jest.Mock).mockImplementationOnce(() =>
      Promise.resolve({ status: 'denied', canAskAgain: false, granted: false, expires: 'never' })
    );
    await notificationService.initialize();

    await notificationService.sendLocalNotification({ title: 'Test', body: 'Test' });

    expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
  });
});
```

### Offline Sync with Network Switching
```typescript
// Source: mobile/src/__tests__/services/offlineSync.test.ts (already exists)
describe('Sync Execution', () => {
  test('should sync actions when online', async () => {
    const { apiService } = require('../../services/api');
    apiService.post.mockResolvedValue({ success: true, data: {} });

    await offlineSyncService.queueAction(
      'agent_message',
      { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
      'normal',
      'user_1',
      'device_1'
    );

    const result = await offlineSyncService.triggerSync();

    expect(result.synced).toBeGreaterThan(0);
    expect(result.success).toBe(true);
  });

  test('should not sync when offline', async () => {
    const { apiService } = require('../../services/api');
    const NetInfo = require('@react-native-community/netinfo');

    // Mock offline state
    NetInfo.fetch.mockResolvedValue({ isConnected: false });

    await offlineSyncService.queueAction(
      'agent_message',
      { agentId: 'agent_1', message: 'Test', sessionId: 'session_1' },
      'normal',
      'user_1',
      'device_1'
    );

    const result = await offlineSyncService.triggerSync();

    expect(result.synced).toBe(0);
    expect(result.success).toBe(false);
  });
});

describe('Conflicts', () => {
  test('should detect server timestamp conflict', async () => {
    const { apiService } = require('../../services/api');

    // Mock server response with newer timestamp
    apiService.get.mockResolvedValue({
      success: true,
      data: { updated_at: new Date(Date.now() + 10000).toISOString() },
    });

    await offlineSyncService.queueAction(
      'form_submit',
      { canvasId: 'canvas_1', formData: { field1: 'value1' } },
      'normal',
      'user_1',
      'device_1',
      'last_write_wins'
    );

    const result = await offlineSyncService.triggerSync();

    expect(result.conflicts).toBeGreaterThan(0);
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Legacy Camera component** | CameraView component | Expo SDK 49 (2023) | Must use CameraView instead of deprecated Camera component |
| **Manual timer management** | jest.useFakeTimers() + flushPromises() | Phase 135 (Mar 2026) | Reliable async testing, no flaky timer issues |
| **Inconsistent Expo mocks** | Global mocks in jest.setup.js | Phase 135 (Mar 2026) | All tests use same mock structure, consistent behavior |
| **MMKV mock returning undefined** | MMKV mock returning String/null | Phase 135 (Mar 2026) | Matches actual MMKV API, no type errors |
| **No shared test utilities** | testUtils.ts with 8 utilities | Phase 135 (Mar 2026) | Consistent async handling across all tests |
| **No network switching simulation** | NetInfo mock with callback triggering | Phase 135 (Mar 2026) | Realistic offline/online transition testing |
| **Missing Expo module mocks** | expo-sharing, expo-file-system mocks added | Phase 135 (Mar 2026) | No more "Cannot find module" errors |

**Deprecated/outdated:**
- **expo-camera Camera component**: Replaced by CameraView in Expo SDK 49. Use CameraView for all new camera code.
- **Manual permission handling**: Expo now provides useCameraPermissions(), useLocationPermissions(), useNotificationsPermissions() hooks. Use hooks for React components, service methods for background operations.
- **Real timers in async tests**: Jest's waitFor() doesn't work with fake timers. Use flushPromises() and waitForCondition() instead (Phase 135 utilities).
- **Custom storage mocks**: Hand-rolled AsyncStorage/MMKV mocks are fragile. Use Phase 135's standardized mocks instead.

## Open Questions

1. **E2E Testing for Device Features**
   - **What we know:** Unit/integration tests use mocks, but real device behavior may differ
   - **What's unclear:** Whether to add Detox E2E tests for camera/location/notification flows
   - **Recommendation:** Start with comprehensive unit/integration tests (Phase 136), add Detox E2E in Phase 137+ if needed. Unit tests provide faster feedback and are easier to maintain.

2. **Platform-Specific Test Suites**
   - **What we know:** iOS and Android have platform differences (camera auto-save, background permissions, notification channels)
   - **What's unclear:** Whether to create separate test files for iOS vs Android behavior
   - **Recommendation:** Use Platform.OS mocking in same test file with describe blocks for each platform. Keeps tests DRY while testing platform differences.

3. **Mock GPS Accuracy Levels**
   - **What we know:** Location service supports accuracy levels (low, balanced, high, best, navigation)
   - **What's unclear:** Whether to test all accuracy levels with different coordinate precision
   - **Recommendation:** Test 2-3 representative accuracy levels (low, high, best) with realistic accuracy values. Don't need to test all 5 levels exhaustively.

4. **Notification Channel Testing (Android)**
   - **What we know:** Android requires notification channel configuration (importance, vibration, light color)
   - **What's unclear:** How extensively to test channel configuration
   - **Recommendation:** Test channel creation once (already in notificationService.test.ts), don't need to test all channel combinations. Channel configuration is platform API, not business logic.

5. **Offline Sync Storage Limits**
   - **What we know:** Offline sync has storage quota (50MB default) with warning (80%) and enforcement (95%) thresholds
   - **What's unclear:** Whether to test storage quota enforcement with actual large data
   - **Recommendation:** Test quota checking logic with mock storage size, don't need to fill up actual storage. Test cleanup logic (LRU eviction) with realistic data sizes.

6. **Push Notification Integration Testing**
   - **What we know:** Push notifications require backend integration (token registration, FCM/APNs)
   - **What's unclear:** How much to test backend communication vs client-side logic
   - **Recommendation:** Mock fetch/API calls for token registration (already done in notificationService.test.ts). Backend integration testing should be separate (backend test suite).

7. **Geofencing Testing Coverage**
   - **What we know:** Location service supports geofencing (enter/exit events, radius checking)
   - **What's unclear:** Whether to test complex geofencing scenarios (multiple regions, overlapping regions)
   - **Recommendation:** Test basic geofencing logic (single region, inside/outside detection). Complex scenarios (multiple regions, overlap) are edge cases, test if time permits.

## Sources

### Primary (HIGH confidence)
- **mobile/jest.setup.js** - Global Expo module mocks for camera, location, notifications, NetInfo, MMKV, AsyncStorage (Phase 135)
- **mobile/src/__tests__/services/cameraService.test.ts** - 53 existing camera tests (permission, capture, gallery, video, platform differences)
- **mobile/src/__tests__/services/locationService.test.ts** - 47 existing location tests (permissions, current location, tracking, distance, geofencing, geocoding)
- **mobile/src/__tests__/services/notificationService.test.ts** - 37 existing notification tests (permissions, local notifications, scheduling, badge, push token)
- **mobile/src/__tests__/services/offlineSyncService.test.ts** - 32 existing offline sync tests (queue, sync execution, network, conflicts, state, quality)
- **mobile/src/__tests__/helpers/testUtils.ts** - 622 lines of shared test utilities (flushPromises, waitForCondition, resetAllMocks, etc.)

### Secondary (MEDIUM confidence)
- **[Expo中集成推送通知：手把手教程](https://blog.csdn.net/weixin_42527589/article/details/156323254)** (Dec 2025) - Expo notification integration guide with testing approaches
- **[5分钟搞定Expo推送通知：新手必看的完整配置手册](https://m.blog.csdn.net/gitblog_00131/article/details/155872612)** (Dec 2025) - Quick configuration guide for Expo push notifications
- **[Supabase Realtime移动应用集成：离线数据同步策略](https://m.blog.csdn.net/gitblog_00747/article/details/154423823)** (Nov 2025) - React Native offline sync with NetInfo
- **[React Native for OpenHarmony 实战：NetInfo 网络状态详解](https://www.cnblogs.com/ljbguanli/p/19612459)** (Feb 2026) - NetInfo component implementation with offline queue management
- **[离线优先：打造React Native应用的无缝用户体验](https://m.blog.csdn.net/gitblog_01167/article/details/153168506)** (Oct 2025) - Offline-first architecture with NetInfo monitoring

### Tertiary (LOW confidence)
- **[Expo Camera Documentation](https://docs.expo.dev/versions/latest/sdk/camera/)** - Official expo-camera API reference (verify testing patterns)
- **[Expo Location Documentation](https://docs.expo.dev/versions/latest/sdk/location/)** - Official expo-location API reference (verify testing patterns)
- **[Expo Notifications Documentation](https://docs.expo.dev/versions/latest/sdk/notifications/)** - Official expo-notifications API reference (verify testing patterns)
- **Phase 135 Final Summary** (.planning/phases/135-mobile-coverage-foundation/135-FINAL.md) - Test infrastructure status and recommendations

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All Expo modules and testing libraries are standard for React Native development, Phase 135 verified installation
- Architecture: HIGH - All patterns verified from existing tests in codebase (Phase 135 created 250+ tests with these patterns)
- Pitfalls: HIGH - All pitfalls identified from Phase 135 verification (135-VERIFICATION.md) and gap closure (135-07-GAP_CLOSURE_PLAN.md)

**Research date:** March 4, 2026
**Valid until:** March 24, 2026 (20 days - React Native ecosystem evolves rapidly, verify Expo SDK version before Phase 136 execution)

---

## Appendix: Test Coverage Goals by Service

### Camera Service (cameraService.ts)
**Current Coverage:** ~70% (estimated from 53 existing tests)
**Target Coverage:** 80%+ statements
**Test Gaps:**
- Document edge detection (not implemented, returns null)
- Barcode scanning result validation
- Multiple photo capture workflow
- Image manipulation (crop, rotate, flip) with real ImageManipulator mock
- Platform-specific camera availability (web vs mobile)
- EXIF data preservation testing

**Priority Tests to Add:**
1. Document edge detection with realistic mock (if implemented)
2. Barcode scanning with various barcode types (QR, Code128, EAN)
3. Multiple photo capture with delete/clear operations
4. Image manipulation with ImageManipulator mock verification
5. Camera type availability for all platforms (iOS, Android, web)

### Location Service (locationService.ts)
**Current Coverage:** ~75% (estimated from 47 existing tests)
**Target Coverage:** 80%+ statements
**Test Gaps:**
- Background location tracking (Android-specific)
- Geofence event notifications (enter/exit callbacks)
- Location history storage and retrieval (AsyncStorage integration)
- Open settings deep link (Linking API mock)
- Battery usage indicator calculation
- Reverse geocoding with missing address components
- Geocoding with invalid addresses

**Priority Tests to Add:**
1. Background location tracking with permission flow (Android)
2. Geofence enter/exit event notification callbacks
3. Location history CRUD operations (add, get, clear)
4. Open settings deep link (Linking.openURL mock)
5. Battery usage indicator based on tracking state and accuracy level

### Notification Service (notificationService.ts)
**Current Coverage:** ~70% (estimated from 37 existing tests)
**Target Coverage:** 80%+ statements
**Test Gaps:**
- Push token registration with backend API (fetch mock verification)
- Notification received listener callback execution
- Notification response listener callback execution
- Android notification channel configuration verification
- Token registration error handling (E_NOTIFICATIONS_TOKEN_NOT_REGISTERED)
- Badge count increment/decrement operations
- Scheduled notification cancellation by ID

**Priority Tests to Add:**
1. Push token registration with backend API call verification
2. Notification received listener with realistic notification payload
3. Notification response listener with user interaction data
4. Android notification channel configuration (importance, vibration, light color)
5. Badge count operations (set, get, increment, decrement, clear)
6. Scheduled notification lifecycle (schedule, trigger, cancel)

### Offline Sync Service (offlineSyncService.ts)
**Current Coverage:** ~65% (estimated from 32 existing tests)
**Target Coverage:** 80%+ statements
**Test Gaps:**
- Network switching event listener callback (offline → online trigger sync)
- Periodic sync timer execution (5-minute interval)
- Cleanup task execution (hourly old entry cleanup)
- Storage quota enforcement (95% threshold)
- Storage quota cleanup (LRU eviction logic)
- Delta hash generation for change detection
- Quality metrics tracking and aggregation
- Sync progress callback execution

**Priority Tests to Add:**
1. Network switching listener with connection restored callback
2. Periodic sync timer with fake timer advancement (5 minutes)
3. Cleanup task execution with LRU eviction verification
4. Storage quota enforcement at 95% threshold
5. Storage quota cleanup with priority preservation (critical actions not deleted)
6. Delta hash generation for identical payload detection
7. Quality metrics tracking (total syncs, success rate, conflict rate, duration, bytes transferred)
8. Sync progress callback with batch completion updates

### Integration Tests to Create
1. **Device Permissions Integration** (devicePermissions.integration.test.ts)
   - Test camera → location → notification permission request flow
   - Test permission state persistence across service restarts
   - Test multiple permission requests in sequence
   - Test permission denial recovery (open settings flow)

2. **Offline Sync Network Integration** (offlineSyncNetwork.integration.test.ts)
   - Test online → offline → online transition with sync trigger
   - Test network type switching (WiFi → cellular → none)
   - Test sync retry with exponential backoff (real delays)
   - Test sync cancellation during batch processing
   - Test concurrent sync requests (prevent duplicate sync)

### Test Utilities to Enhance (testUtils.ts)
**Current State:** 622 lines, 8 utility functions (Phase 135)
**Enhancements Needed:**
- `createMockCameraRef()` - Factory for mock CameraView refs
- `createMockLocation()` - Factory for realistic mock location objects
- `createMockGeofence()` - Factory for mock geofence regions
- `createMockNotification()` - Factory for mock notification payloads
- `simulateNetworkSwitch()` - Helper for NetInfo state transitions
- `createMockPushToken()` - Factory for mock Expo push tokens
- `advanceTimeBySeconds()` - Wrapper for advanceTimersByTime with human-readable units
- `waitForSyncComplete()` - Helper for waiting for offline sync to finish

**Total New Tests Estimated:** 60-80 tests across 4 services + 2 integration test files + 8 enhanced utilities

---

**Research Status:** ✅ COMPLETE

**Next Action:** Execute `/gsd:plan-phase 136` to create execution plans based on this research.

**Last Updated:** March 4, 2026
**Document Owner:** Claude Code (GSD Phase Researcher)
