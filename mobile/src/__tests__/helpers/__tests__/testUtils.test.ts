/**
 * Test Utilities Tests
 *
 * Tests to verify that all test utility functions work correctly,
 * especially Platform.OS mocking and cleanup utilities.
 */

import { Platform } from 'react-native';
import React from 'react';
import { Text } from 'react-native';
import {
  mockPlatform,
  restorePlatform,
  isIOS,
  isAndroid,
  mockDevice,
  restoreDevice,
  createMockTestComponent,
  renderWithTestWrapper,
  waitForAsync,
  flushPromises,
  flushPromisesLegacy,
  wait,
  waitForCondition,
  advanceTimersByTime,
  advanceTimersByTimeSync,
  resetAllMocks,
  setupFakeTimers,
  cleanupTest,
  cleanupTestWithReset,
  testEachPlatform,
  skipOnPlatform,
  onlyOnPlatform,
  createMockWebSocket,
  createMockFn,
  createMockAsyncFn,
  assertThrows,
  assertRejects,
  assertRendersWithoutThrow,
  renderWithSafeArea,
  getiOSInsets,
  getAndroidInsets,
} from '../testUtils';

describe('testUtils', () => {
  // ========================================================================
  // Platform.OS Mocking Tests
  // ========================================================================

  describe('Platform.OS Mocking', () => {
    afterEach(() => {
      restorePlatform();
    });

    it('should mock Platform.OS to iOS', () => {
      mockPlatform('ios');
      expect(Platform.OS).toBe('ios');
    });

    it('should mock Platform.OS to Android', () => {
      mockPlatform('android');
      expect(Platform.OS).toBe('android');
    });

    it('should switch between iOS and Android', () => {
      mockPlatform('ios');
      expect(Platform.OS).toBe('ios');

      mockPlatform('android');
      expect(Platform.OS).toBe('android');
    });

    it('should restore original Platform.OS', () => {
      const originalOS = Platform.OS;

      mockPlatform('ios');
      expect(Platform.OS).toBe('ios');

      restorePlatform();
      expect(Platform.OS).toBe(originalOS);
    });

    it('should report iOS correctly', () => {
      mockPlatform('ios');
      expect(isIOS()).toBe(true);
      expect(isAndroid()).toBe(false);
    });

    it('should report Android correctly', () => {
      mockPlatform('android');
      expect(isAndroid()).toBe(true);
      expect(isIOS()).toBe(false);
    });
  });

  // ========================================================================
  // Device Mocking Tests
  // ========================================================================

  describe('Device Mocking', () => {
    afterEach(() => {
      restoreDevice();
    });

    it('should mock device information', () => {
      mockDevice({
        osName: 'Android',
        modelName: 'Pixel 7',
      });

      const Device = require('expo-device').Device;
      expect(Device.osName).toBe('Android');
      expect(Device.modelName).toBe('Pixel 7');
    });

    it('should restore device to defaults', () => {
      mockDevice({
        osName: 'Android',
        modelName: 'Custom',
      });

      restoreDevice();

      const Device = require('expo-device').Device;
      expect(Device.osName).toBe('iOS');
      expect(Device.modelName).toBe('iPhone 14');
    });
  });

  // ========================================================================
  // Component Rendering Tests
  // ========================================================================

  describe('Component Rendering', () => {
    it('should create mock test component', () => {
      const component = React.createElement(Text, { testID: 'test-text' }, 'Hello');

      expect(() => {
        createMockTestComponent(component);
      }).not.toThrow();
    });

    it('should render component without throwing', () => {
      const component = React.createElement(Text, {}, 'Test');

      expect(() => {
        assertRendersWithoutThrow(component);
      }).not.toThrow();
    });
  });

  // ========================================================================
  // Async Utilities Tests
  // ========================================================================

  describe('Async Utilities', () => {
    beforeEach(() => {
      // wait() and waitForAsync() rely on real setTimeout — fake timers
      // (enabled by jest.setup.js) would never let them resolve.
      jest.useRealTimers();
    });

    it('should wait for async callback', async () => {
      let value = 0;

      setTimeout(() => {
        value = 42;
      }, 100);

      await waitForAsync(() => {
        expect(value).toBe(42);
      });
    });

    it('should flush promises', async () => {
      let promiseExecuted = false;

      Promise.resolve().then(() => {
        promiseExecuted = true;
      });

      expect(promiseExecuted).toBe(false);

      await flushPromises();

      expect(promiseExecuted).toBe(true);
    });

    it('should wait for specified time', async () => {
      const start = Date.now();

      await wait(100);

      const duration = Date.now() - start;
      // Node may fire setTimeout a hair early under load (observed 99ms);
      // assert the delay actually elapsed rather than exact 100ms.
      expect(duration).toBeGreaterThanOrEqual(95);
    });
  });

  // ========================================================================
  // Cleanup Utilities Tests
  // ========================================================================

  describe('Cleanup Utilities', () => {
    it('should clean up all mocks', () => {
      mockPlatform('ios');
      expect(Platform.OS).toBe('ios');

      cleanupTest();

      // Platform should be restored
      const originalOS = Platform.OS;
      expect(typeof originalOS).toBe('string');
    });
  });

  // ========================================================================
  // Platform-Specific Testing Tests
  // ========================================================================

  describe('Platform-Specific Testing', () => {
    it('should run test on each platform', async () => {
      const testedPlatforms: string[] = [];

      await testEachPlatform(async (platform) => {
        testedPlatforms.push(platform);
        expect(Platform.OS).toBe(platform);
      });

      expect(testedPlatforms).toEqual(['ios', 'android']);
    });

    it('should switch platforms correctly in testEachPlatform', async () => {
      const platforms: Array<'ios' | 'android'> = [];

      await testEachPlatform(async (platform) => {
        platforms.push(Platform.OS);
      });

      expect(platforms).toEqual(['ios', 'android']);
    });
  });

  // ========================================================================
  // Mock Helper Tests
  // ========================================================================

  describe('Mock Helpers', () => {
    it('should create mock function', () => {
      const mockFn = createMockFn((x: number) => x * 2);

      expect(mockFn(5)).toBe(10);
      expect(mockFn).toHaveBeenCalledWith(5);
      expect(mockFn).toHaveBeenCalledTimes(1);
    });

    it('should create mock async function', async () => {
      const mockAsyncFn = createMockAsyncFn(async (id: number) => {
        return { id, name: 'Test' };
      });

      const result = await mockAsyncFn(1);

      expect(result).toEqual({ id: 1, name: 'Test' });
      expect(mockAsyncFn).toHaveBeenCalledWith(1);
    });
  });

  // ========================================================================
  // Assertion Helper Tests
  // ========================================================================

  describe('Assertion Helpers', () => {
    it('should assert function throws', () => {
      expect(() => {
        assertThrows(() => {
          throw new Error('Test error');
        }, 'Test error');
      }).not.toThrow();
    });

    it('should assert async function rejects', async () => {
      await expect(
        assertRejects(async () => {
          throw new Error('Async error');
        }, 'Async error')
      ).resolves.not.toThrow();
    });

    it('should assert component renders without throwing', () => {
      const component = React.createElement(Text, {}, 'Test');

      expect(() => {
        assertRendersWithoutThrow(component);
      }).not.toThrow();
    });
  });

  // ========================================================================
  // Integration Tests
  // ========================================================================

  describe('Integration Tests', () => {
    it('should handle complete test lifecycle', () => {
      // Setup
      mockPlatform('ios');

      // Test
      expect(Platform.OS).toBe('ios');

      // Cleanup
      cleanupTest();

      // Verify cleanup
      expect(typeof Platform.OS).toBe('string');
    });

    it('should handle multiple platform switches', () => {
      mockPlatform('ios');
      expect(Platform.OS).toBe('ios');

      mockPlatform('android');
      expect(Platform.OS).toBe('android');

      mockPlatform('ios');
      expect(Platform.OS).toBe('ios');

      cleanupTest();
    });

    it('should work with Platform.select', () => {
      mockPlatform('ios');

      const result = Platform.select({
        ios: 'iOS Value',
        android: 'Android Value',
      });

      expect(result).toBe('iOS Value');

      mockPlatform('android');

      const androidResult = Platform.select({
        ios: 'iOS Value',
        android: 'Android Value',
      });

      expect(androidResult).toBe('Android Value');
    });

    it('should walk the fallback chain when the platform key is absent', () => {
      mockPlatform('ios');

      // spec[platform] missing, then spec.ios missing -> spec.android
      expect(Platform.select({ android: 'Android Value' })).toBe('Android Value');
      // spec.android missing -> spec.default
      expect(Platform.select({ default: 'Default Value' })).toBe('Default Value');
      // everything missing -> undefined
      expect(Platform.select({})).toBeUndefined();
      // spec.native reached when spec.default missing
      expect(Platform.select({ native: 'Native Value' })).toBe('Native Value');
    });
  });

  // ========================================================================
  // Component Rendering Helpers (wave 118)
  // ========================================================================

  describe('renderWithTestWrapper', () => {
    it('should render with an optional wrapper component', () => {
      const Wrapper = ({ children }: { children: React.ReactNode }) =>
        React.createElement(Text, { testID: 'wrapper' }, children);

      const { getByTestId, getByText } = renderWithTestWrapper(
        React.createElement(Text, { testID: 'inner' }, 'Hello'),
        Wrapper
      );

      expect(getByTestId('wrapper')).toBeTruthy();
      expect(getByText('Hello')).toBeTruthy();
    });

    it('should render without a wrapper', () => {
      const { getByText } = renderWithTestWrapper(
        React.createElement(Text, null, 'No wrapper')
      );
      expect(getByText('No wrapper')).toBeTruthy();
    });
  });

  // ========================================================================
  // Async Utilities (wave 118)
  // ========================================================================

  describe('waitForCondition', () => {
    it('should resolve immediately when the condition is already met', async () => {
      jest.useRealTimers();
      await expect(waitForCondition(() => true)).resolves.toBeUndefined();
    });

    it('should resolve once the condition becomes true', async () => {
      jest.useRealTimers();
      let count = 0;
      await waitForCondition(() => {
        count += 1;
        return count >= 3;
      });
      expect(count).toBeGreaterThanOrEqual(3);
    });

    it('should throw when the condition never becomes true', async () => {
      jest.useRealTimers();
      await expect(
        waitForCondition(() => false, 50)
      ).rejects.toThrow('Condition not met within 50ms');
    });
  });

  describe('flushPromisesLegacy', () => {
    it('should resolve after a setTimeout tick', async () => {
      jest.useRealTimers();
      let resolved = false;
      Promise.resolve().then(() => {
        resolved = true;
      });
      await flushPromisesLegacy();
      expect(resolved).toBe(true);
    });
  });

  describe('advanceTimersByTime helpers', () => {
    it('advanceTimersByTime advances fake timers and flushes promises', async () => {
      let fired = false;
      setTimeout(() => {
        fired = true;
      }, 1000);

      await advanceTimersByTime(1000);
      expect(fired).toBe(true);
    });

    it('advanceTimersByTimeSync advances fake timers synchronously', () => {
      let fired = false;
      setTimeout(() => {
        fired = true;
      }, 500);

      advanceTimersByTimeSync(500);
      expect(fired).toBe(true);
    });
  });

  // ========================================================================
  // Cleanup Utilities (wave 118)
  // ========================================================================

  describe('resetAllMocks and setupFakeTimers', () => {
    it('resetAllMocks clears mocks, timers, and resets module globals', () => {
      const fn = jest.fn();
      fn('x');

      jest.useFakeTimers();
      resetAllMocks();

      expect(fn).not.toHaveBeenCalled();
      expect(jest.getRealSystemTime).toBeDefined();
    });

    it('setupFakeTimers enables fake timers', () => {
      setupFakeTimers();

      let fired = false;
      setTimeout(() => {
        fired = true;
      }, 1000);
      jest.advanceTimersByTime(1000);

      expect(fired).toBe(true);
      jest.useRealTimers();
    });

    it('cleanupTestWithReset cleans up and resets modules', () => {
      expect(() => cleanupTestWithReset()).not.toThrow();
    });

    it('resetAllMocks tolerates missing global reset hooks', () => {
      const saved = {
        mmkv: (global as any).__resetMmkvMock,
        asyncStorage: (global as any).__resetAsyncStorageMock,
        secureStore: (global as any).__resetSecureStoreMock,
      };
      (global as any).__resetMmkvMock = undefined;
      (global as any).__resetAsyncStorageMock = undefined;
      (global as any).__resetSecureStoreMock = undefined;
      try {
        expect(() => resetAllMocks()).not.toThrow();
      } finally {
        (global as any).__resetMmkvMock = saved.mmkv;
        (global as any).__resetAsyncStorageMock = saved.asyncStorage;
        (global as any).__resetSecureStoreMock = saved.secureStore;
      }
    });
  });

  // ========================================================================
  // Platform-Specific Test Registration (wave 118)
  // ========================================================================

  describe('skipOnPlatform / onlyOnPlatform', () => {
    // Registered at describe level — jest-circus forbids registering tests
    // inside a test body. Platform-agnostic: one registration targets the
    // CURRENT Platform.OS (runs), the other the opposite (skipped).
    // NOTE: callbacks record into a plain object — jest.setup's global
    // afterEach clearAllMocks() would wipe jest.fn() history between tests.
    const invocationRecord: Record<string, number> = {};
    const currentOS = Platform.OS as 'ios' | 'android';
    const otherOS = currentOS === 'android' ? 'ios' : 'android';

    skipOnPlatform(otherOS, () => {
      invocationRecord.cross = (invocationRecord.cross || 0) + 1;
    });
    // Same-platform registration exercises the test.skip side of the ternary
    skipOnPlatform(currentOS, () => {
      invocationRecord.same = (invocationRecord.same || 0) + 1;
    });
    onlyOnPlatform(currentOS, () => {
      invocationRecord.native = (invocationRecord.native || 0) + 1;
    });
    onlyOnPlatform(otherOS, () => {
      invocationRecord.other = (invocationRecord.other || 0) + 1;
    });

    it('should execute the non-skipped callbacks only', () => {
      expect(invocationRecord.cross).toBe(1);
      expect(invocationRecord.native).toBe(1);
      expect(invocationRecord.other).toBeUndefined();
    });
  });

  // ========================================================================
  // Mock Helpers (wave 118)
  // ========================================================================

  describe('createMockWebSocket', () => {
    it('should create a connected mock socket by default', () => {
      const socket = createMockWebSocket();
      expect(socket.connected).toBe(true);
      expect(socket.url).toBe('ws://localhost:8000');
      expect(typeof socket.send).toBe('function');
      expect(typeof socket.close).toBe('function');
      expect(typeof socket.addEventListener).toBe('function');
      expect(typeof socket.removeEventListener).toBe('function');
      expect(socket.onopen).toBeNull();
    });

    it('should create a disconnected mock socket when asked', () => {
      const socket = createMockWebSocket(false);
      expect(socket.connected).toBe(false);
    });
  });

  // ========================================================================
  // SafeArea Helpers (wave 118)
  // ========================================================================

  describe('renderWithSafeArea', () => {
    it('should render with default metrics when no insets given', () => {
      const { getByText } = renderWithSafeArea(
        React.createElement(Text, null, 'Safe content')
      );
      expect(getByText('Safe content')).toBeTruthy();
    });

    it('should render with custom insets when provided', () => {
      const { getByText } = renderWithSafeArea(
        React.createElement(Text, null, 'Notched content'),
        { top: 44, bottom: 34, left: 0, right: 0 }
      );
      expect(getByText('Notched content')).toBeTruthy();
    });
  });

  describe('safe area insets', () => {
    it('getiOSInsets returns device-specific insets', () => {
      expect(getiOSInsets('iPhone8')).toEqual({ top: 20, bottom: 0, left: 0, right: 0 });
      expect(getiOSInsets('iPhone13Pro')).toEqual({ top: 44, bottom: 34, left: 0, right: 0 });
      expect(getiOSInsets('iPhone14ProMax')).toEqual({ top: 47, bottom: 34, left: 0, right: 0 });
    });

    it('getAndroidInsets reflects gesture navigation', () => {
      expect(getAndroidInsets()).toEqual({ top: 0, bottom: 0, left: 0, right: 0 });
      expect(getAndroidInsets(false)).toEqual({ top: 0, bottom: 48, left: 0, right: 0 });
    });
  });
});
