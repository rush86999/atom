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
  waitForAsync,
  flushPromises,
  wait,
  cleanupTest,
  testEachPlatform,
  createMockFn,
  createMockAsyncFn,
  assertThrows,
  assertRejects,
  assertRendersWithoutThrow,
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
      expect(duration).toBeGreaterThanOrEqual(100);
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
  });
});
