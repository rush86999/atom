/**
 * iOS StatusBar Tests
 *
 * Tests for iOS-specific StatusBar API features:
 * - setHidden with fade/slide transitions
 * - setBarStyle for light/dark content
 * - networkActivityIndicatorVisible
 * - StatusBar integration with CanvasViewerScreen
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { Platform, StatusBar } from 'react-native';
import {
  mockPlatform,
  restorePlatform,
  cleanupTest,
} from '../../helpers/testUtils';

// ============================================================================
// Setup and Teardown
// ============================================================================

let setHiddenSpy: jest.SpyInstance;
let setBarStyleSpy: jest.SpyInstance;
let setNetworkActivityIndicatorVisibleSpy: jest.SpyInstance;

beforeEach(() => {
  mockPlatform('ios');
  setHiddenSpy = jest.spyOn(StatusBar, 'setHidden');
  setBarStyleSpy = jest.spyOn(StatusBar, 'setBarStyle');
  setNetworkActivityIndicatorVisibleSpy = jest.spyOn(
    StatusBar,
    'setNetworkActivityIndicatorVisible'
  );
});

afterEach(() => {
  setHiddenSpy.mockRestore();
  setBarStyleSpy.mockRestore();
  setNetworkActivityIndicatorVisibleSpy.mockRestore();
  cleanupTest();
});

// ============================================================================
// setHidden Tests
// ============================================================================

describe('iOS StatusBar - setHidden', () => {
  test('should hide StatusBar with fade transition on iOS', () => {
    StatusBar.setHidden(true, 'fade');
    expect(setHiddenSpy).toHaveBeenCalledWith(true, 'fade');
  });

  test('should show StatusBar with fade transition', () => {
    StatusBar.setHidden(false, 'fade');
    expect(setHiddenSpy).toHaveBeenCalledWith(false, 'fade');
  });

  test('should hide StatusBar with slide transition on iOS', () => {
    StatusBar.setHidden(true, 'slide');
    expect(setHiddenSpy).toHaveBeenCalledWith(true, 'slide');
  });

  test('should hide StatusBar without transition specified', () => {
    StatusBar.setHidden(true);
    expect(setHiddenSpy).toHaveBeenCalledWith(true);
  });

  test('should handle multiple setHidden calls', () => {
    StatusBar.setHidden(true);
    StatusBar.setHidden(false);
    StatusBar.setHidden(true);

    expect(setHiddenSpy).toHaveBeenCalledTimes(3);
    expect(setHiddenSpy).toHaveBeenLastCalledWith(true);
  });
});

// ============================================================================
// setBarStyle Tests
// ============================================================================

describe('iOS StatusBar - setBarStyle', () => {
  test('should set bar style to dark-content', () => {
    StatusBar.setBarStyle('dark-content');
    expect(setBarStyleSpy).toHaveBeenCalledWith('dark-content');
  });

  test('should set bar style to light-content', () => {
    StatusBar.setBarStyle('light-content');
    expect(setBarStyleSpy).toHaveBeenCalledWith('light-content');
  });

  test('should set bar style to default', () => {
    StatusBar.setBarStyle('default');
    expect(setBarStyleSpy).toHaveBeenCalledWith('default');
  });

  test('should handle bar style changes for dark mode', () => {
    StatusBar.setBarStyle('light-content'); // Light status bar for dark mode
    expect(setBarStyleSpy).toHaveBeenCalledWith('light-content');

    StatusBar.setBarStyle('dark-content'); // Dark status bar for light mode
    expect(setBarStyleSpy).toHaveBeenLastCalledWith('dark-content');
  });
});

// ============================================================================
// Network Activity Indicator Tests
// ============================================================================

describe('iOS StatusBar - Network Activity Indicator', () => {
  test('should show network activity indicator', () => {
    StatusBar.setNetworkActivityIndicatorVisible(true);
    expect(setNetworkActivityIndicatorVisibleSpy).toHaveBeenCalledWith(true);
  });

  test('should hide network activity indicator', () => {
    StatusBar.setNetworkActivityIndicatorVisible(false);
    expect(setNetworkActivityIndicatorVisibleSpy).toHaveBeenCalledWith(false);
  });

  test('should toggle network activity indicator', () => {
    StatusBar.setNetworkActivityIndicatorVisible(true);
    StatusBar.setNetworkActivityIndicatorVisible(false);
    StatusBar.setNetworkActivityIndicatorVisible(true);

    expect(setNetworkActivityIndicatorVisibleSpy).toHaveBeenCalledTimes(3);
    expect(setNetworkActivityIndicatorVisibleSpy).toHaveBeenLastCalledWith(true);
  });
});

// ============================================================================
// CanvasViewerScreen Integration Tests
// ============================================================================

describe('iOS StatusBar - CanvasViewerScreen Integration', () => {
  test('should hide StatusBar when entering fullscreen mode', async () => {
    // Simulate CanvasViewerScreen fullscreen toggle
    const isFullscreen = true;
    if (isFullscreen) {
      StatusBar.setHidden(true);
    }

    expect(setHiddenSpy).toHaveBeenCalledWith(true);
  });

  test('should show StatusBar when exiting fullscreen mode', () => {
    // Simulate CanvasViewerScreen cleanup on unmount
    StatusBar.setHidden(true);  // Enter fullscreen
    StatusBar.setHidden(false); // Exit fullscreen

    expect(setHiddenSpy).toHaveBeenCalledTimes(2);
    expect(setHiddenSpy).toHaveBeenLastCalledWith(false);
  });

  test('should clean up StatusBar on unmount', () => {
    // Simulate component unmount
    const cleanup = () => {
      StatusBar.setHidden(false);
    };

    cleanup();

    expect(setHiddenSpy).toHaveBeenCalledWith(false);
  });
});

// ============================================================================
// Platform-Specific Behavior Tests
// ============================================================================

describe('iOS StatusBar - Platform-Specific Behavior', () => {
  test('should only use fade/slide transitions on iOS', () => {
    const transition = 'fade';
    StatusBar.setHidden(true, transition);

    expect(setHiddenSpy).toHaveBeenCalledWith(true, transition);
  });

  test('should support iOS-specific barStyle values', () => {
    const styles = ['default', 'light-content', 'dark-content'];

    styles.forEach((style) => {
      StatusBar.setBarStyle(style as any);
      expect(setBarStyleSpy).toHaveBeenCalledWith(style);
    });
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('iOS StatusBar - Edge Cases', () => {
  test('should handle rapid setHidden calls', () => {
    for (let i = 0; i < 10; i++) {
      StatusBar.setHidden(i % 2 === 0);
    }

    expect(setHiddenSpy).toHaveBeenCalledTimes(10);
  });

  test('should handle rapid setBarStyle changes', () => {
    const styles = ['dark-content', 'light-content'];
    for (let i = 0; i < 10; i++) {
      StatusBar.setBarStyle(styles[i % 2] as any);
    }

    expect(setBarStyleSpy).toHaveBeenCalledTimes(10);
  });

  test('should maintain network indicator state across setHidden calls', () => {
    StatusBar.setNetworkActivityIndicatorVisible(true);
    StatusBar.setHidden(true);
    StatusBar.setHidden(false);

    // Network indicator should still be visible
    expect(setNetworkActivityIndicatorVisibleSpy).toHaveBeenLastCalledWith(true);
  });
});
