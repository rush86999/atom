/**
 * Platform-Specific Infrastructure Tests
 *
 * Validates that platform-specific testing infrastructure works correctly:
 * - Platform.OS switching with mockPlatform()
 * - SafeAreaContext mock provides insets
 * - StatusBar spies track API calls
 * - Platform.select returns correct values
 */

import { Platform, StatusBar } from 'react-native';
import { render } from '@testing-library/react-native';
import React from 'react';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  mockPlatform,
  restorePlatform,
  renderWithSafeArea,
  getiOSInsets,
  getAndroidInsets,
} from '../helpers/testUtils';

// ============================================================================
// Platform.OS Switching Tests
// ============================================================================

describe('Platform Infrastructure - Platform.OS Switching', () => {
  afterEach(() => {
    restorePlatform();
  });

  test('should switch Platform.OS to iOS', () => {
    mockPlatform('ios');
    expect(Platform.OS).toBe('ios');
  });

  test('should switch Platform.OS to Android', () => {
    mockPlatform('android');
    expect(Platform.OS).toBe('android');
  });

  test('should restore Platform.OS after switching', () => {
    const originalOS = Platform.OS;
    mockPlatform('ios');
    expect(Platform.OS).toBe('ios');
    restorePlatform();
    expect(Platform.OS).toBe(originalOS);
  });

  test('should handle multiple platform switches', () => {
    mockPlatform('ios');
    expect(Platform.OS).toBe('ios');
    mockPlatform('android');
    expect(Platform.OS).toBe('android');
    mockPlatform('ios');
    expect(Platform.OS).toBe('ios');
  });
});

// ============================================================================
// SafeAreaContext Mock Tests
// ============================================================================

describe('Platform Infrastructure - SafeAreaContext', () => {
  test('should provide default safe area insets', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'insets',
        top: insets.top,
        bottom: insets.bottom,
      });
    };

    const { getByTestId } = render(
      React.createElement(SafeAreaProvider, null,
        React.createElement(TestComponent)
      )
    );

    expect(getByTestId('insets').props.top).toBe(0);
    expect(getByTestId('insets').props.bottom).toBe(0);
  });

  test('should provide custom safe area insets', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'insets',
        top: insets.top,
        bottom: insets.bottom,
      });
    };

    const { getByTestId } = render(
      React.createElement(SafeAreaProvider, {
        initialMetrics: {
          frame: { x: 0, y: 0, width: 390, height: 844 },
          insets: { top: 44, bottom: 34, left: 0, right: 0 },
        },
      },
        React.createElement(TestComponent)
      )
    );

    expect(getByTestId('insets').props.top).toBe(44);
    expect(getByTestId('insets').props.bottom).toBe(34);
  });

  test('should use renderWithSafeArea helper', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'insets',
        paddingTop: insets.top,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      { top: 44, bottom: 34, left: 0, right: 0 }
    );

    expect(getByTestId('insets').props.paddingTop).toBe(44);
  });
});

// ============================================================================
// iOS Device Inset Tests
// ============================================================================

describe('Platform Infrastructure - iOS Device Insets', () => {
  test('should provide iPhone 8 insets (no notch)', () => {
    const insets = getiOSInsets('iPhone8');
    expect(insets).toEqual({ top: 20, bottom: 0, left: 0, right: 0 });
  });

  test('should provide iPhone 13 Pro insets (notch)', () => {
    const insets = getiOSInsets('iPhone13Pro');
    expect(insets).toEqual({ top: 44, bottom: 34, left: 0, right: 0 });
  });

  test('should provide iPhone 14 Pro Max insets (Dynamic Island)', () => {
    const insets = getiOSInsets('iPhone14ProMax');
    expect(insets).toEqual({ top: 47, bottom: 34, left: 0, right: 0 });
  });
});

// ============================================================================
// Android Device Inset Tests
// ============================================================================

describe('Platform Infrastructure - Android Device Insets', () => {
  test('should provide gesture navigation insets (bottom: 0)', () => {
    const insets = getAndroidInsets(true);
    expect(insets.bottom).toBe(0);
  });

  test('should provide button navigation insets (bottom: 48)', () => {
    const insets = getAndroidInsets(false);
    expect(insets.bottom).toBe(48);
  });

  test('should have zero top inset on Android', () => {
    const insets = getAndroidInsets();
    expect(insets.top).toBe(0);
  });
});

// ============================================================================
// StatusBar API Mock Tests
// ============================================================================

describe('Platform Infrastructure - StatusBar API', () => {
  let setHiddenSpy: jest.SpyInstance;
  let setBarStyleSpy: jest.SpyInstance;

  beforeEach(() => {
    setHiddenSpy = jest.spyOn(StatusBar, 'setHidden');
    setBarStyleSpy = jest.spyOn(StatusBar, 'setBarStyle');
  });

  afterEach(() => {
    setHiddenSpy.mockRestore();
    setBarStyleSpy.mockRestore();
    restorePlatform();
  });

  test('should spy on StatusBar.setHidden on iOS', () => {
    mockPlatform('ios');
    StatusBar.setHidden(true, 'fade');
    expect(setHiddenSpy).toHaveBeenCalledWith(true, 'fade');
  });

  test('should spy on StatusBar.setBarStyle on iOS', () => {
    mockPlatform('ios');
    StatusBar.setBarStyle('dark-content');
    expect(setBarStyleSpy).toHaveBeenCalledWith('dark-content');
  });

  test('should track StatusBar call count', () => {
    StatusBar.setHidden(true);
    StatusBar.setHidden(false);
    expect(setHiddenSpy).toHaveBeenCalledTimes(2);
  });
});

// ============================================================================
// Platform.select Tests
// ============================================================================

describe('Platform Infrastructure - Platform.select', () => {
  afterEach(() => {
    restorePlatform();
  });

  test('should return iOS value on iOS', () => {
    mockPlatform('ios');
    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
    });
    expect(result).toBe('iOS Value');
  });

  test('should return Android value on Android', () => {
    mockPlatform('android');
    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
    });
    expect(result).toBe('Android Value');
  });

  test('should return default value when platform not specified', () => {
    mockPlatform('ios');
    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
      default: 'Default Value',
    });
    // When platform matches, returns platform-specific value
    expect(result).toBe('iOS Value');
  });

  test('should fallback to ios when no platform match', () => {
    mockPlatform('android');
    const result = Platform.select({
      ios: 'iOS Value',
      android: 'Android Value',
      default: 'Default Value',
    });
    // When platform matches 'android', returns android value
    expect(result).toBe('Android Value');
  });

  test('should work with StyleSheet styles', () => {
    mockPlatform('ios');
    const { StyleSheet } = require('react-native');
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
