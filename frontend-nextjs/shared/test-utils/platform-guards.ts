/**
 * Platform Guard Utilities for Cross-Platform Testing
 *
 * Runtime platform detection functions for conditional test logic.
 * Works across web (jsdom), mobile (React Native), and desktop (Tauri).
 *
 * @module @atom/test-utils/platform-guards
 */

/**
 * Check if running in web environment
 * Uses typeof checks to detect browser/jsdom environment
 *
 * @returns true if window and document objects are defined
 *
 * @example
 * if (isWeb()) {
 *   // Web-specific test setup
 *   render(<MyComponent />, { wrapper: BrowserRouter });
 * }
 */
export const isWeb = (): boolean => {
  return typeof window !== 'undefined' && typeof window.document !== 'undefined';
};

/**
 * Check if running in React Native environment
 * Detects React Native runtime by checking navigator.product
 *
 * @returns true if ReactNative product is detected
 *
 * @example
 * if (isReactNative()) {
 *   // React Native-specific test setup
 *   render(<MyComponent />, { wrapper: SafeAreaProvider });
 * }
 */
export const isReactNative = (): boolean => {
  return typeof navigator !== 'undefined' && (navigator as any).product === 'ReactNative';
};

/**
 * Check if running in Tauri desktop environment
 * Detects Tauri runtime by checking window.__TAURI__
 *
 * @returns true if Tauri API is available
 *
 * @example
 * if (isTauri()) {
 *   // Desktop-specific test setup
 *   mockTauriWindow();
 * }
 */
export const isTauri = (): boolean => {
  return typeof window !== 'undefined' && (window as any).__TAURI__ !== undefined;
};

/**
 * Check if running on iOS platform (React Native only)
 * Safely checks Platform.OS with typeof guard for web/desktop compatibility
 *
 * @returns true if Platform.OS is 'ios', false otherwise
 *
 * @example
 * if (isIOS()) {
 *   // iOS-specific test setup
 *   mockPlatform('ios');
 * }
 */
export const isIOS = (): boolean => {
  // Use defensive typeof check since Platform is React Native only
  if (typeof (Platform as any) === 'undefined') {
    return false;
  }
  // Platform.OS check will only execute in React Native environment
  return (Platform as any).OS === 'ios';
};

/**
 * Check if running on Android platform (React Native only)
 * Safely checks Platform.OS with typeof guard for web/desktop compatibility
 *
 * @returns true if Platform.OS is 'android', false otherwise
 *
 * @example
 * if (isAndroid()) {
 *   // Android-specific test setup
 *   mockPlatform('android');
 * }
 */
export const isAndroid = (): boolean => {
  // Use defensive typeof check since Platform is React Native only
  if (typeof (Platform as any) === 'undefined') {
    return false;
  }
  // Platform.OS check will only execute in React Native environment
  return (Platform as any).OS === 'android';
};

/**
 * Skip test if not running in web environment
 * Returns test.skip if not web, otherwise returns test
 *
 * @returns test or test.skip function
 *
 * @example
 * skipIfNotWeb()('web-only feature', () => {
 *   // This test only runs in web environment
 *   expect(window.document).toBeDefined();
 * });
 */
export const skipIfNotWeb = () => {
  return isWeb() ? test : test.skip;
};

/**
 * Skip test if not running in React Native environment
 * Returns test.skip if not React Native, otherwise returns test
 *
 * @returns test or test.skip function
 *
 * @example
 * skipIfNotReactNative()('mobile-only feature', () => {
 *   // This test only runs in React Native environment
 *   expect(Platform.OS).toBeDefined();
 * });
 */
export const skipIfNotReactNative = () => {
  return isReactNative() ? test : test.skip;
};

/**
 * Skip test if not running in Tauri desktop environment
 * Returns test.skip if not Tauri, otherwise returns test
 *
 * @returns test or test.skip function
 *
 * @example
 * skipIfNotTauri()('desktop-only feature', () => {
 *   // This test only runs in Tauri environment
 *   expect(window.__TAURI__).toBeDefined();
 * });
 */
export const skipIfNotTauri = () => {
  return isTauri() ? test : test.skip;
};

/**
 * Run test callback on both iOS and Android platforms
 * Automatically handles platform switching and cleanup
 *
 * @param testCallback - Callback function to run on each platform
 *
 * @example
 * testEachPlatform((platform) => {
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
    // Dynamically import Platform only in React Native environment
    if (typeof (Platform as any) !== 'undefined') {
      // Mock Platform.OS for the current platform
      const originalOS = (Platform as any).OS;
      Object.defineProperty((Platform as any), 'OS', {
        get: () => platform,
        configurable: true,
      });

      try {
        await testCallback(platform);
      } finally {
        // Restore original platform
        Object.defineProperty((Platform as any), 'OS', {
          get: () => originalOS,
          configurable: true,
        });
      }
    } else {
      // In non-RN environments, still call the callback for consistency
      // Tests using Platform.OS will need to mock it themselves
      await testCallback(platform);
    }
  }
};

/**
 * Skip test on specific platform
 * @param platform - Platform to skip on ('ios' | 'android')
 * @returns test or test.skip function
 *
 * @example
 * skipOnPlatform('android')('iOS-only feature', () => {
 *   // This test will be skipped on Android
 *   expect(StatusBar.style).toBe('default');
 * });
 */
export const skipOnPlatform = (
  platform: 'ios' | 'android'
): typeof test => {
  if (typeof (Platform as any) === 'undefined') {
    return test; // No platform detected, run the test
  }
  return (Platform as any).OS === platform ? test.skip : test;
};

/**
 * Run test only on specific platform
 * @param platform - Platform to run on ('ios' | 'android')
 * @returns test or test.skip function
 *
 * @example
 * onlyOnPlatform('ios')('iOS-only feature', () => {
 *   // This test only runs on iOS
 *   expect(StatusBar.style).toBe('default');
 * });
 */
export const onlyOnPlatform = (
  platform: 'ios' | 'android'
): typeof test => {
  if (typeof (Platform as any) === 'undefined') {
    return test.skip; // No platform detected, skip the test
  }
  return (Platform as any).OS === platform ? test : test.skip;
};
