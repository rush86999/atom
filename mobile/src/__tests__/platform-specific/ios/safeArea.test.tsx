/**
 * iOS Safe Area Tests
 *
 * Tests for iOS-specific safe area features:
 * - Notch devices (iPhone X and later)
 * - Dynamic Island devices (iPhone 14 Pro and later)
 * - Home indicator handling
 * - SafeAreaProvider with custom metrics
 * - Portrait vs landscape orientation
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { Platform } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets, useSafeAreaFrame } from 'react-native-safe-area-context';
import {
  mockPlatform,
  restorePlatform,
  renderWithSafeArea,
  getiOSInsets,
} from '../../helpers/testUtils';

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  mockPlatform('ios');
});

afterEach(() => {
  restorePlatform();
});

// ============================================================================
// Notch Device Tests (iPhone X, XS, 11 Pro)
// ============================================================================

describe('iOS Safe Areas - Notch Devices', () => {
  test('should apply notch inset on iPhone X (top: 44, bottom: 34)', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'safe-area',
        style: {
          paddingTop: insets.top,
          paddingBottom: insets.bottom,
        },
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone13Pro') // iPhone 13 Pro has notch
    );

    const safeArea = getByTestId('safe-area');
    expect(safeArea.props.style.paddingTop).toBe(44);  // Notch height
    expect(safeArea.props.style.paddingBottom).toBe(34); // Home indicator
  });

  test('should handle notch device with zero side insets', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'side-insets',
        left: insets.left,
        right: insets.right,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone13Pro')
    );

    const sideInsets = getByTestId('side-insets');
    expect(sideInsets.props.left).toBe(0);
    expect(sideInsets.props.right).toBe(0);
  });

  test('should render correctly on notch device in portrait', () => {
    const TestComponent = () => {
      const frame = useSafeAreaFrame();
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'frame-info',
        width: frame.width,
        height: frame.height,
        topInset: insets.top,
      });
    };

    const { getByTestId } = render(
      React.createElement(SafeAreaProvider, {
        initialMetrics: {
          frame: { x: 0, y: 0, width: 390, height: 844 },  // iPhone 13 Pro portrait
          insets: { top: 44, bottom: 34, left: 0, right: 0 },
        },
      },
        React.createElement(TestComponent)
      )
    );

    const frameInfo = getByTestId('frame-info');
    expect(frameInfo.props.width).toBe(390);
    expect(frameInfo.props.height).toBe(844);
    expect(frameInfo.props.topInset).toBe(44);
  });
});

// ============================================================================
// Dynamic Island Tests (iPhone 14 Pro, 15 Pro)
// ============================================================================

describe('iOS Safe Areas - Dynamic Island', () => {
  test('should apply Dynamic Island inset (top: 47)', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'dynamic-island-inset',
        paddingTop: insets.top,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone14ProMax') // Dynamic Island device
    );

    const dynamicIsland = getByTestId('dynamic-island-inset');
    expect(dynamicIsland.props.paddingTop).toBe(47); // Dynamic Island is taller than notch
  });

  test('should maintain home indicator on Dynamic Island devices', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'home-indicator',
        paddingBottom: insets.bottom,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone14ProMax')
    );

    const homeIndicator = getByTestId('home-indicator');
    expect(homeIndicator.props.paddingBottom).toBe(34); // Same home indicator height
  });
});

// ============================================================================
// Non-Notch Device Tests (iPhone 8, SE)
// ============================================================================

describe('iOS Safe Areas - Non-Notch Devices', () => {
  test('should apply minimal top inset on iPhone 8 (no notch)', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'no-notch-inset',
        paddingTop: insets.top,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone8') // No notch, just status bar
    );

    const noNotch = getByTestId('no-notch-inset');
    expect(noNotch.props.paddingTop).toBe(20); // Status bar only, no notch
  });

  test('should have zero bottom inset on iPhone 8 (home button)', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'home-button-inset',
        paddingBottom: insets.bottom,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone8')
    );

    const homeButton = getByTestId('home-button-inset');
    expect(homeButton.props.paddingBottom).toBe(0); // Physical home button, no inset
  });
});

// ============================================================================
// Home Indicator Tests
// ============================================================================

describe('iOS Safe Areas - Home Indicator', () => {
  test('should reserve space for home indicator at bottom', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'home-indicator-space',
        paddingBottom: insets.bottom,
      });
    };

    const { getByTestId } = renderWithSafeArea(
      React.createElement(TestComponent),
      getiOSInsets('iPhone13Pro')
    );

    const homeIndicator = getByTestId('home-indicator-space');
    expect(homeIndicator.props.paddingBottom).toBeGreaterThan(0); // Home indicator needs space
  });

  test('should handle home indicator on landscape orientation', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'landscape-insets',
        top: insets.top,
        bottom: insets.bottom,
        left: insets.left,
        right: insets.right,
      });
    };

    const { getByTestId } = render(
      React.createElement(SafeAreaProvider, {
        initialMetrics: {
          frame: { x: 0, y: 0, width: 844, height: 390 },  // Landscape
          insets: { top: 0, bottom: 21, left: 47, right: 47 }, // Landscape home indicator
        },
      },
        React.createElement(TestComponent)
      )
    );

    const landscape = getByTestId('landscape-insets');
    // In landscape, home indicator appears on left or right
    expect(landscape.props.left).toBeGreaterThanOrEqual(0);
    expect(landscape.props.right).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// iPad Tests
// ============================================================================

describe('iOS Safe Areas - iPad', () => {
  test('should handle iPad safe areas (no notch, smaller top inset)', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'ipad-insets',
        paddingTop: insets.top,
        paddingBottom: insets.bottom,
      });
    };

    const { getByTestId } = render(
      React.createElement(SafeAreaProvider, {
        initialMetrics: {
          frame: { x: 0, y: 0, width: 1024, height: 768 }, // iPad portrait
          insets: { top: 20, bottom: 0, left: 0, right: 0 }, // No notch/home indicator
        },
      },
        React.createElement(TestComponent)
      )
    );

    const ipad = getByTestId('ipad-insets');
    expect(ipad.props.paddingTop).toBe(20); // Status bar
    expect(ipad.props.paddingBottom).toBe(0); // No home indicator
  });
});

// ============================================================================
// SafeAreaProvider Edge Cases
// ============================================================================

describe('iOS Safe Areas - SafeAreaProvider Edge Cases', () => {
  test('should use default insets when initialMetrics not provided', () => {
    const TestComponent = () => {
      const insets = useSafeAreaInsets();
      return React.createElement('View', {
        testID: 'default-insets',
        top: insets.top,
        bottom: insets.bottom,
      });
    };

    const { getByTestId } = render(
      React.createElement(SafeAreaProvider, null,
        React.createElement(TestComponent)
      )
    );

    const defaults = getByTestId('default-insets');
    expect(defaults.props.top).toBe(0);
    expect(defaults.props.bottom).toBe(0);
  });

  test('should handle component without SafeAreaProvider wrapper', () => {
    // This test verifies that useSafeAreaInsets returns default values
    // when no SafeAreaProvider wraps the component
    const TestComponent = () => {
      try {
        const insets = useSafeAreaInsets();
        return React.createElement('View', {
          testID: 'no-provider-insets',
          top: insets.top,
        });
      } catch (error) {
        return React.createElement('View', {
          testID: 'no-provider-error',
          error: (error as Error).message,
        });
      }
    };

    const { getByTestId } = render(React.createElement(TestComponent));
    // Should not throw with Jest mock
    expect(getByTestId('no-provider-insets')).toBeTruthy();
  });
});

// ============================================================================
// Integration with Platform.select
// ============================================================================

describe('iOS Safe Areas - Platform.select Integration', () => {
  test('should use iOS-specific safe area styles', () => {
    mockPlatform('ios');

    const { StyleSheet } = require('react-native');

    const styles = StyleSheet.create({
      container: {
        flex: 1,
        ...Platform.select({
          ios: {
            paddingTop: 44,  // Notch
            paddingBottom: 34, // Home indicator
          },
          android: {
            paddingTop: 0,
            paddingBottom: 48, // Navigation bar
          },
        }),
      },
    });

    expect(styles.container.paddingTop).toBe(44);
    expect(styles.container.paddingBottom).toBe(34);
  });
});
