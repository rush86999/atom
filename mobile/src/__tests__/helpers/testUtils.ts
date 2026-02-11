/**
 * Test Utilities
 *
 * Helper functions for React Native testing, including Platform.OS mocking,
 * component rendering, and async utilities.
 *
 * Usage:
 * ```typescript
 * import { mockPlatform, restorePlatform, createMockTestComponent } from './testUtils';
 * import { render } from '@testing-library/react-native';
 *
 * beforeEach(() => {
 *   mockPlatform('ios');
 * });
 *
 * afterEach(() => {
 *   restorePlatform();
 * });
 * ```
 */

import { Platform } from 'react-native';
import { render, RenderAPI, waitFor } from '@testing-library/react-native';
import React from 'react';

// ============================================================================
// Platform.OS Mocking
// ============================================================================

let originalOS: string = '';
let platformSpies: jest.SpyInstance[] = [];

/**
 * Mock Platform.OS to simulate iOS or Android
 * @param platform - Platform to simulate ('ios' | 'android')
 *
 * @example
 * mockPlatform('ios');
 * expect(Platform.OS).toBe('ios');
 *
 * mockPlatform('android');
 * expect(Platform.OS).toBe('android');
 */
export const mockPlatform = (platform: 'ios' | 'android'): void => {
  // Save original on first call
  if (!originalOS) {
    originalOS = Platform.OS as string;
  }

  // Mock Platform.OS directly by redefining it
  Object.defineProperty(Platform, 'OS', {
    get: () => platform,
    configurable: true,
  });

  // Mock Platform.select to return platform-specific value
  const selectSpy = jest.spyOn(Platform, 'select').mockImplementation((spec) => {
    return spec[platform] ?? spec.ios ?? spec.android ?? spec.default ?? spec.native;
  });

  platformSpies.push(selectSpy);
};

/**
 * Restore original Platform.OS value
 * Call this in afterEach() to clean up after mockPlatform()
 *
 * @example
 * afterEach(() => {
 *   restorePlatform();
 * });
 */
export const restorePlatform = (): void => {
  // Restore Platform.OS
  Object.defineProperty(Platform, 'OS', {
    get: () => originalOS,
    configurable: true,
  });

  // Restore all spies
  platformSpies.forEach((spy) => spy.mockRestore());
  platformSpies = [];
};

/**
 * Check if current platform is iOS
 * @returns true if Platform.OS is 'ios'
 */
export const isIOS = (): boolean => {
  return Platform.OS === 'ios';
};

/**
 * Check if current platform is Android
 * @returns true if Platform.OS is 'android'
 */
export const isAndroid = (): boolean => {
  return Platform.OS === 'android';
};

// ============================================================================
// Device Mocking
// ============================================================================

let deviceSpy: jest.SpyInstance | null = null;

interface DeviceInfo {
  osName?: string;
  osVersion?: string;
  modelName?: string;
  modelId?: string;
  brand?: string;
  manufacturerName?: string;
  platformApiLevel?: number;
  deviceYearClass?: number;
  totalMemory?: number;
}

/**
 * Mock expo-device Device object
 * @param deviceInfo - Device information to mock
 *
 * @example
 * mockDevice({
 *   osName: 'iOS',
 *   modelName: 'iPhone 14',
 *   modelId: 'iPhone14,7'
 * });
 */
export const mockDevice = (deviceInfo: DeviceInfo): void => {
  // Import expo-device mock
  const Device = jest.requireMock('expo-device').Device;

  // Update device properties
  Object.assign(Device, deviceInfo);
};

/**
 * Restore device mock to defaults
 */
export const restoreDevice = (): void => {
  const Device = jest.requireMock('expo-device').Device;

  Object.assign(Device, {
    osName: 'iOS',
    osVersion: '16.0',
    modelName: 'iPhone 14',
    modelId: 'iPhone14,7',
    brand: 'Apple',
    manufacturerName: 'Apple',
    platformApiLevel: 16,
    deviceYearClass: 2022,
    totalMemory: 6 * 1024 * 1024 * 1024,
  });
};

// ============================================================================
// Component Rendering Helpers
// ============================================================================

interface MockTestComponentProps {
  testID?: string;
  children?: React.ReactNode;
  [key: string]: unknown;
}

/**
 * Create a mock test component with default props
 * Useful for testing components that require specific props
 *
 * @param Component - Component to render
 * @param props - Props to pass to component
 * @returns Rendered component API
 *
 * @example
 * const { getByTestId, getByText } = createMockTestComponent(
 *   <MyComponent value="test" />
 * );
 */
export const createMockTestComponent = (
  element: React.ReactElement,
  options?: {
    wrapper?: React.ComponentType<{ children: React.ReactNode }>;
  }
): RenderAPI => {
  return render(element, options);
};

/**
 * Render component with test wrapper
 * @param component - Component to render
 * @param wrapper - Optional wrapper component
 * @returns RenderAPI from @testing-library/react-native
 */
export const renderWithTestWrapper = (
  component: React.ReactElement,
  wrapper?: React.ComponentType<{ children: React.ReactNode }>
): RenderAPI => {
  return render(component, { wrapper });
};

// ============================================================================
// Async Utilities
// ============================================================================

/**
 * Wrapper around waitFor with default timeout
 * @param callback - Callback to wait for
 * @param timeout - Timeout in milliseconds (default: 3000ms)
 *
 * @example
 * await waitForAsync(() => {
 *   expect(getByText('Loaded')).toBeTruthy();
 * });
 */
export const waitForAsync = async (
  callback: () => void,
  timeout: number = 3000
): Promise<void> => {
  await waitFor(callback, { timeout });
};

/**
 * Flush all pending promises
 * Useful for testing async operations that use setTimeout or Promises
 *
 * @example
 * await flushPromises();
 * expect(mockFunction).toHaveBeenCalled();
 */
export const flushPromises = async (): Promise<void> => {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
};

/**
 * Wait for a specific amount of time
 * @param ms - Milliseconds to wait
 *
 * @example
 * await wait(500); // Wait 500ms
 */
export const wait = async (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms));
};

/**
 * Advance timers by a specific amount
 * Useful for testing setTimeout/setInterval
 * @param ms - Milliseconds to advance
 *
 * @example
 * jest.useFakeTimers();
 * await advanceTimersByTime(1000);
 * jest.useRealTimers();
 */
export const advanceTimersByTime = async (ms: number): Promise<void> => {
  jest.advanceTimersByTime(ms);
  await flushPromises();
};

// ============================================================================
// Cleanup Utilities
// ============================================================================

/**
 * Clean up all mocks and restore original implementations
 * Call this in afterEach() blocks
 *
 * @example
 * afterEach(() => {
 *   cleanupTest();
 * });
 */
export const cleanupTest = (): void => {
  restorePlatform();
  restoreDevice();
  jest.clearAllMocks();
};

/**
 * Clean up all mocks and reset modules
 * More thorough cleanup, use between tests that share modules
 *
 * @example
 * afterEach(() => {
 *   cleanupTestWithReset();
 * });
 */
export const cleanupTestWithReset = (): void => {
  cleanupTest();
  jest.resetModules();
};

// ============================================================================
// Platform-Specific Test Helpers
// ============================================================================

/**
 * Run a test callback on both iOS and Android platforms
 * @param testCallback - Callback to run on each platform
 *
 * @example
 * testEachPlatform(async (platform) => {
 *   mockPlatform(platform);
 *   const { getByTestId } = render(<MyComponent />);
 *   expect(getByTestId('component')).toBeTruthy();
 * });
 */
export const testEachPlatform = async (
  testCallback: (platform: 'ios' | 'android') => void | Promise<void>
): Promise<void> => {
  const platforms: Array<'ios' | 'android'> = ['ios', 'android'];

  for (const platform of platforms) {
    mockPlatform(platform);
    try {
      await testCallback(platform);
    } finally {
      restorePlatform();
    }
  }
};

/**
 * Skip test on specific platform
 * @param platform - Platform to skip on
 * @param testCallback - Test callback
 *
 * @example
 * skipOnPlatform('android', () => {
 *   // This test will be skipped on Android
 *   test('iOS-only feature', () => {
 *     // ...
 *   });
 * });
 */
export const skipOnPlatform = (
  platform: 'ios' | 'android',
  testCallback: () => void
): void => {
  const testOrSkip = Platform.OS === platform ? test.skip : test;

  testOrSkip('Skipped on ' + platform, testCallback);
};

/**
 * Run test only on specific platform
 * @param platform - Platform to run on
 * @param testCallback - Test callback
 *
 * @example
 * onlyOnPlatform('ios', () => {
 *   test('iOS-only feature', () => {
 *     // This test only runs on iOS
 *   });
 * });
 */
export const onlyOnPlatform = (
  platform: 'ios' | 'android',
  testCallback: () => void
): void => {
  const testOrSkip = Platform.OS === platform ? test : test.skip;

  testOrSkip('Only on ' + platform, testCallback);
};

// ============================================================================
// Mock Helper Utilities
// ============================================================================

/**
 * Create a mock function with implementation
 * @param implementation - Implementation function
 * @returns Mock function
 *
 * @example
 * const mockFn = createMockFn((x) => x * 2);
 * expect(mockFn(5)).toBe(10);
 */
export const createMockFn = <T extends (...args: unknown[]) => unknown>(
  implementation: T
): jest.MockedFunction<T> => {
  return jest.fn(implementation) as jest.MockedFunction<T>;
};

/**
 * Create a mock async function with implementation
 * @param implementation - Implementation function
 * @returns Mock async function
 *
 * @example
 * const mockAsyncFn = createMockAsyncFn(async (id) => {
 *   return { id, name: 'Test' };
 * });
 * const result = await mockAsyncFn(1);
 */
export const createMockAsyncFn = <T extends (...args: unknown[]) => Promise<unknown>>(
  implementation: T
): jest.MockedFunction<T> => {
  return jest.fn(implementation) as jest.MockedFunction<T>;
};

// ============================================================================
// Assertion Helpers
// ============================================================================

/**
 * Assert that a function throws a specific error
 * @param fn - Function to test
 * @param errorMessage - Expected error message (optional)
 *
 * @example
 * assertThrows(() => {
 *   throw new Error('Test error');
 * }, 'Test error');
 */
export const assertThrows = (
  fn: () => void,
  errorMessage?: string
): void => {
  expect(fn).toThrow(errorMessage);
};

/**
 * Assert that an async function rejects with a specific error
 * @param fn - Async function to test
 * @param errorMessage - Expected error message (optional)
 *
 * @example
 * await assertRejects(async () => {
 *   throw new Error('Async error');
 * }, 'Async error');
 */
export const assertRejects = async (
  fn: () => Promise<unknown>,
  errorMessage?: string
): Promise<void> => {
  await expect(fn).rejects.toThrow(errorMessage);
};

/**
 * Assert that a component renders without throwing
 * @param component - Component to render
 *
 * @example
 * assertRendersWithoutThrow(<MyComponent />);
 */
export const assertRendersWithoutThrow = (component: React.ReactElement): void => {
  expect(() => render(component)).not.toThrow();
};

// ============================================================================
// Export All
// ============================================================================

export default {
  // Platform mocking
  mockPlatform,
  restorePlatform,
  isIOS,
  isAndroid,

  // Device mocking
  mockDevice,
  restoreDevice,

  // Component rendering
  createMockTestComponent,
  renderWithTestWrapper,

  // Async utilities
  waitForAsync,
  flushPromises,
  wait,
  advanceTimersByTime,

  // Cleanup
  cleanupTest,
  cleanupTestWithReset,

  // Platform-specific testing
  testEachPlatform,
  skipOnPlatform,
  onlyOnPlatform,

  // Mock helpers
  createMockFn,
  createMockAsyncFn,

  // Assertion helpers
  assertThrows,
  assertRejects,
  assertRendersWithoutThrow,
};
