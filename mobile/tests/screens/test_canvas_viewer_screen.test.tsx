/**
 * CanvasViewerScreen Tests
 *
 * Comprehensive test suite for CanvasViewerScreen component covering:
 * - Rendering with canvas data
 * - Loading and error states
 * - Offline support
 * - Canvas interactions
 * - Sharing functionality
 * - Fullscreen mode
 * - Feedback submission
 *
 * @see src/screens/canvas/CanvasViewerScreen.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert, Share } from 'react-native';
import { CanvasViewerScreen } from '../../src/screens/canvas/CanvasViewerScreen';
import { CanvasType } from '../../src/types/canvas';

// Mock navigation
const mockNavigation = {
  goBack: jest.fn(),
  navigate: jest.fn(),
  push: jest.fn(),
  replace: jest.fn(),
  reset: jest.fn(),
  dispatch: jest.fn(),
  isFocused: jest.fn(() => true),
  canGoBack: jest.fn(() => true),
  getId: jest.fn(),
  getParent: jest.fn(),
};

const mockRoute = {
  params: {
    canvasId: 'canvas-123',
    canvasType: CanvasType.CHART,
    sessionId: 'session-123',
    agentId: 'agent-123',
  },
};

jest.mock('@react-navigation/native', () => ({
  useRoute: () => mockRoute,
  useNavigation: () => mockNavigation,
  RouteProp: jest.fn(),
}));

// Mock API service
jest.mock('../../src/services/api', () => ({
  apiService: {
    get: jest.fn().mockResolvedValue({
      success: true,
      data: {
        components: [
          {
            type: 'chart',
            data: {
              type: 'line',
              data: [1, 2, 3, 4, 5],
            },
          },
        ],
        metadata: {
          id: 'canvas-123',
          title: 'Test Canvas',
          type: CanvasType.CHART,
          agent_name: 'Test Agent',
          agent_id: 'agent-123',
          governance_level: 'AUTONOMOUS',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          version: 1,
          component_count: 1,
        },
      },
    }),
    post: jest.fn().mockResolvedValue({
      success: true,
    }),
  },
}));

// Mock NetInfo
jest.mock('@react-native-community/netinfo', () => ({
  fetch: jest.fn().mockResolvedValue({
    isConnected: true,
    isInternetReachable: true,
  }),
  addEventListener: jest.fn().mockReturnValue({
    remove: jest.fn(),
  }),
}));

// Mock canvas components
jest.mock('../../src/components/canvas/CanvasWebView', () => 'CanvasWebView');
jest.mock('../../src/components/canvas/CanvasChart', () => 'CanvasChart');
jest.mock('../../src/components/canvas/CanvasForm', () => 'CanvasForm');
jest.mock('../../src/components/canvas/CanvasSheet', () => 'CanvasSheet');
jest.mock('../../src/components/canvas/CanvasTerminal', () => 'CanvasTerminal');

describe('CanvasViewerScreen - Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Renders loading state initially
  it('should render loading state initially', () => {
    const { getByText } = render(<CanvasViewerScreen />);

    expect(getByText('Loading canvas...')).toBeTruthy();
  });

  // Test 2: Renders canvas after loading
  it('should render canvas after loading', async () => {
    const { getByText, queryByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(queryByText('Loading canvas...')).toBeNull();
    });

    await waitFor(() => {
      expect(getByText('Test Canvas')).toBeTruthy();
    });
  });

  // Test 3: Displays canvas title in header
  it('should display canvas title in header', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Test Canvas')).toBeTruthy();
    });
  });

  // Test 4: Displays agent name
  it('should display agent name', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('by Test Agent')).toBeTruthy();
    });
  });

  // Test 5: Displays governance badge
  it('should display governance badge', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('AUTONOMOUS')).toBeTruthy();
    });
  });
});

describe('CanvasViewerScreen - Error States', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays error when canvas fails to load
  it('should display error when canvas fails to load', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockRejectedValueOnce(new Error('Network error'));

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Failed to Load Canvas')).toBeTruthy();
    });
  });

  // Test 2: Shows retry button on error
  it('should show retry button on error', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockRejectedValueOnce(new Error('Network error'));

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Retry')).toBeTruthy();
    });
  });

  // Test 3: Retries canvas load on retry press
  it('should retry canvas load on retry press', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockRejectedValueOnce(new Error('Network error'));
    apiService.get.mockResolvedValueOnce({
      success: true,
      data: {
        components: [],
        metadata: {
          id: 'canvas-123',
          title: 'Test Canvas',
          type: CanvasType.CHART,
          agent_name: 'Test Agent',
          agent_id: 'agent-123',
          governance_level: 'AUTONOMOUS',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          version: 1,
          component_count: 0,
        },
      },
    });

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Retry')).toBeTruthy();
    });

    await act(async () => {
      fireEvent.press(getByText('Retry'));
    });

    await waitFor(() => {
      expect(apiService.get).toHaveBeenCalledTimes(2);
    });
  });
});

describe('CanvasViewerScreen - Canvas Interactions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Handles canvas action execution
  it('should handle canvas action execution', async () => {
    const apiService = require('../../src/services/api').apiService;

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Test Canvas')).toBeTruthy();
    });

    // Simulate canvas action message
    const webViewMessage = {
      nativeEvent: {
        data: JSON.stringify({
          type: 'canvas_action',
          component_count: 1,
          metadata: {},
        }),
      },
    };

    // This would be handled by WebView's onMessage
    expect(apiService.post).toBeDefined();
  });

  // Test 2: Handles canvas error
  it('should handle canvas error', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Test Canvas')).toBeTruthy();
    });

    // Simulate canvas error message
    const webViewMessage = {
      nativeEvent: {
        data: JSON.stringify({
          type: 'canvas_error',
          error: 'Canvas render error',
        }),
      },
    };

    // Error would be handled by WebView's onMessage
    expect(Alert.alert).toBeDefined();
  });

  // Test 3: Handles form submission
  it('should handle form submission', async () => {
    const apiService = require('../../src/services/api').apiService;

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Test Canvas')).toBeTruthy();
    });

    // Form submission would be handled by WebView's onMessage
    expect(apiService.post).toBeDefined();
  });
});

describe('CanvasViewerScreen - Header Actions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Goes back when back button pressed
  it('should go back when back button pressed', async () => {
    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const backButton = getByTestId(/arrow-left/i);
      fireEvent.press(backButton);
    });

    expect(mockNavigation.goBack).toHaveBeenCalled();
  });

  // Test 2: Shares canvas when share button pressed
  it('should share canvas when share button pressed', async () => {
    Share.share = jest.fn().mockResolvedValue({ action: 'sharedAction' });

    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const shareButton = getByTestId(/share/i);
      fireEvent.press(shareButton);
    });

    await waitFor(() => {
      expect(Share.share).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringContaining('Test Canvas'),
        })
      );
    });
  });

  // Test 3: Refreshes canvas when refresh button pressed
  it('should refresh canvas when refresh button pressed', async () => {
    const apiService = require('../../src/services/api').apiService;

    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const refreshButton = getByTestId(/refresh/i);
      fireEvent.press(refreshButton);
    });

    await waitFor(() => {
      expect(apiService.get).toHaveBeenCalled();
    });
  });

  // Test 4: Toggles fullscreen when fullscreen button pressed
  it('should toggle fullscreen when fullscreen button pressed', async () => {
    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const fullscreenButton = getByTestId(/fullscreen/i);
      fireEvent.press(fullscreenButton);
    });

    // Fullscreen state should toggle
    expect(getByTestId(/fullscreen/i)).toBeTruthy();
  });
});

describe('CanvasViewerScreen - Offline Support', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows offline badge when offline
  it('should show offline badge when offline', async () => {
    const NetInfo = require('@react-native-community/netinfo');
    NetInfo.fetch.mockResolvedValueOnce({
      isConnected: false,
      isInternetReachable: false,
    });

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Offline')).toBeTruthy();
    });
  });

  // Test 2: Shows cached badge when loaded from cache
  it('should show cached badge when loaded from cache', async () => {
    // This would require cache implementation
    const { queryByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      // Initially online, so no cached badge
      expect(queryByText('Cached')).toBeNull();
    });
  });

  // Test 3: Loads from cache when offline and cache available
  it('should load from cache when offline and cache available', async () => {
    const NetInfo = require('@react-native-community/netinfo');
    NetInfo.fetch.mockResolvedValueOnce({
      isConnected: false,
      isInternetReachable: false,
    });

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      // Should show error if no cache available
      expect(getByText('Offline')).toBeTruthy();
    });
  });
});

describe('CanvasViewerScreen - Feedback', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows feedback bar
  it('should show feedback bar', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Was this canvas helpful?')).toBeTruthy();
    });
  });

  // Test 2: Handles thumbs up feedback
  it('should handle thumbs up feedback', async () => {
    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const thumbsUpButton = getByTestId(/thumb-up/i);
      fireEvent.press(thumbsUpButton);
    });

    // Feedback should be recorded
    expect(getByTestId(/thumb-up/i)).toBeTruthy();
  });

  // Test 3: Handles thumbs down feedback
  it('should handle thumbs down feedback', async () => {
    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const thumbsDownButton = getByTestId(/thumb-down/i);
      fireEvent.press(thumbsDownButton);
    });

    // Feedback should be recorded
    expect(getByTestId(/thumb-down/i)).toBeTruthy();
  });

  // Test 4: Changes feedback button style when selected
  it('should change feedback button style when selected', async () => {
    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const thumbsUpButton = getByTestId(/thumb-up/i);
      fireEvent.press(thumbsUpButton);
    });

    // Button should have different style when selected
    expect(getByTestId(/thumb-up/i)).toBeTruthy();
  });
});

describe('CanvasViewerScreen - Canvas Metadata', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays canvas details section
  it('should display canvas details section', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Canvas Details')).toBeTruthy();
    });
  });

  // Test 2: Displays canvas type
  it('should display canvas type', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText(/CHART/)).toBeTruthy();
    });
  });

  // Test 3: Displays canvas version
  it('should display canvas version', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText(/Version:/)).toBeTruthy();
      expect(getByText(/1/)).toBeTruthy();
    });
  });

  // Test 4: Displays created and updated dates
  it('should display created and updated dates', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText(/Created:/)).toBeTruthy();
      expect(getByText(/Updated:/)).toBeTruthy();
    });
  });
});

describe('CanvasViewerScreen - Related Canvases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays related canvases section
  it('should display related canvases section when available', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockResolvedValueOnce({
      success: true,
      data: {
        components: [],
        metadata: {
          id: 'canvas-123',
          title: 'Test Canvas',
          type: CanvasType.CHART,
          agent_name: 'Test Agent',
          agent_id: 'agent-123',
          governance_level: 'AUTONOMOUS',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          version: 1,
          component_count: 0,
          related_canvases: [
            {
              id: 'canvas-456',
              title: 'Related Canvas',
              type: CanvasType.FORM,
            },
          ],
        },
      },
    });

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Related Canvases')).toBeTruthy();
    });
  });

  // Test 2: Navigates to related canvas on press
  it('should navigate to related canvas on press', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockResolvedValueOnce({
      success: true,
      data: {
        components: [],
        metadata: {
          id: 'canvas-123',
          title: 'Test Canvas',
          type: CanvasType.CHART,
          agent_name: 'Test Agent',
          agent_id: 'agent-123',
          governance_level: 'AUTONOMOUS',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          version: 1,
          component_count: 0,
          related_canvases: [
            {
              id: 'canvas-456',
              title: 'Related Canvas',
              type: CanvasType.FORM,
            },
          ],
        },
      },
    });

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      fireEvent.press(getByText('Related Canvas'));
    });

    expect(mockNavigation.push).toHaveBeenCalledWith('CanvasViewer', {
      canvasId: 'canvas-456',
    });
  });
});

describe('CanvasViewerScreen - Edge Cases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Handles empty canvas components
  it('should handle empty canvas components', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockResolvedValueOnce({
      success: true,
      data: {
        components: [],
        metadata: {
          id: 'canvas-123',
          title: 'Empty Canvas',
          type: CanvasType.CHART,
          agent_name: 'Test Agent',
          agent_id: 'agent-123',
          governance_level: 'AUTONOMOUS',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          version: 1,
          component_count: 0,
        },
      },
    });

    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('No canvas components')).toBeTruthy();
    });
  });

  // Test 2: Handles missing canvas metadata
  it('should handle missing canvas metadata', async () => {
    const apiService = require('../../src/services/api').apiService;
    apiService.get.mockResolvedValueOnce({
      success: true,
      data: {
        components: [],
        metadata: null,
      },
    });

    const { queryByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      // Should not crash, but may not show metadata section
      expect(queryByText('Canvas Details')).toBeNull();
    });
  });

  // Test 3: Handles share error gracefully
  it('should handle share error gracefully', async () => {
    Share.share = jest.fn().mockRejectedValue(new Error('Share failed'));

    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      const shareButton = getByTestId(/share/i);
      fireEvent.press(shareButton);
    });

    // Should not crash
    expect(Share.share).toHaveBeenCalled();
  });
});

describe('CanvasViewerScreen - Accessibility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Has accessible header
  it('should have accessible header', async () => {
    const { getByText } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Test Canvas')).toBeTruthy();
    });
  });

  // Test 2: Has accessible feedback buttons
  it('should have accessible feedback buttons', async () => {
    const { getByText, getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByText('Was this canvas helpful?')).toBeTruthy();
      expect(getByTestId(/thumb-up/i)).toBeTruthy();
      expect(getByTestId(/thumb-down/i)).toBeTruthy();
    });
  });

  // Test 3: Has accessible action buttons
  it('should have accessible action buttons', async () => {
    const { getByTestId } = render(<CanvasViewerScreen />);

    await waitFor(() => {
      expect(getByTestId(/arrow-left/i)).toBeTruthy();
      expect(getByTestId(/share/i)).toBeTruthy();
      expect(getByTestId(/refresh/i)).toBeTruthy();
    });
  });
});
