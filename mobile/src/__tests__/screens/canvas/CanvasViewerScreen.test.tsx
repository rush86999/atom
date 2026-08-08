/**
 * CanvasViewerScreen Component Tests
 *
 * Tests for canvas loading, rendering, interactions, offline support,
 * WebView messaging, metadata display, fullscreen, share, and feedback.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert, Share, StatusBar } from 'react-native';
import { mockPlatform, restorePlatform } from '../../helpers/testUtils';

// Mock React Navigation (route params are mutable so per-test canvas types work)
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
  push: jest.fn(),
};

const mockRouteParams: any = {
  canvasId: 'canvas-123',
  canvasType: 'chart',
  sessionId: 'session-456',
  agentId: 'agent-789',
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  useRoute: () => ({
    params: mockRouteParams,
  }),
}));

// react-native-webview is mocked via CanvasWebView below; keep this for safety
jest.mock('react-native-webview', () => ({
  WebView: 'WebView',
}));

// Canvas subcomponents load heavy native deps (datetimepicker); mock them
jest.mock('@react-native-community/datetimepicker', () => ({ default: 'DateTimePicker' }), { virtual: true });

// CanvasWebView is the web-canvas renderer — a functional mock that spreads
// its props onto a View, so tests can read props (canvasId, onMessage, ...)
// and drive the message handlers straight from the rendered tree.
jest.mock('../../../components/canvas/CanvasWebView', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    CanvasWebView: (props: any) => React.createElement(View, { ...props, testID: 'mock-webview' }),
  };
});

jest.mock('../../../components/canvas/CanvasChart', () => {
  const React = require('react');
  const { View } = require('react-native');
  return { CanvasChart: (props: any) => React.createElement(View, { testID: 'mock-canvas-chart' }) };
});

// CanvasForm is mocked with a functional component so tests can trigger the
// inline onSubmit handler the screen wires to apiService.
jest.mock('../../../components/canvas/CanvasForm', () => {
  const React = require('react');
  const { TouchableOpacity, Text } = require('react-native');
  return {
    CanvasForm: (props: any) =>
      React.createElement(
        TouchableOpacity,
        { testID: 'mock-form-submit', onPress: () => props.onSubmit?.({ name: 'Test User' }) },
        React.createElement(Text, null, 'Mock Form')
      ),
  };
});

jest.mock('../../../components/canvas/CanvasSheet', () => {
  const React = require('react');
  const { View } = require('react-native');
  return { CanvasSheet: (props: any) => React.createElement(View, { testID: 'mock-canvas-sheet' }) };
});
jest.mock('../../../components/canvas/CanvasTerminal', () => {
  const React = require('react');
  const { View } = require('react-native');
  return { CanvasTerminal: (props: any) => React.createElement(View, { testID: 'mock-canvas-terminal' }) };
});

// Mock apiService
const mockApiGet = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: {
      id: 'canvas-123',
      type: 'chart',
      components: [
        {
          id: 'comp-1',
          type: 'markdown',
          data: {
            content: '# Test Canvas\n\nThis is a test canvas.',
          },
        },
        {
          id: 'comp-2',
          type: 'chart',
          data: {
            type: 'line',
            data: {
              labels: ['Jan', 'Feb', 'Mar'],
              datasets: [
                {
                  label: 'Sales',
                  data: [10, 20, 30],
                },
              ],
            },
            show_legend: true,
          },
        },
      ],
    },
  })
);

const mockApiPost = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: {},
  })
);

jest.mock('../../../services/api', () => ({
  apiService: {
    get: mockApiGet,
    post: mockApiPost,
  },
}));

// Mock NetInfo so tests can flip connectivity per test
jest.mock('@react-native-community/netinfo', () => {
  const listeners: Array<(state: any) => void> = [];
  const mockFetch = jest.fn().mockResolvedValue({ isConnected: true });
  return {
    fetch: mockFetch,
    addEventListener: jest.fn((cb) => {
      listeners.push(cb);
      return { remove: jest.fn(() => {}) };
    }),
    // Test helper to fire connectivity changes
    _emit: (state: any) => listeners.forEach((cb) => cb(state)),
  };
});

// require() AFTER the mocks/data are declared — a static import would run the
// api mock factory before mockApiGet is initialized (hoisted var).
const { CanvasViewerScreen } = require('../../../screens/canvas/CanvasViewerScreen');
const NetInfo = require('@react-native-community/netinfo');

// Mock react-native-paper
jest.mock('react-native-paper', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return {
    useTheme: () => ({
      colors: {
        primary: '#2196F3',
        onSurface: '#000',
        surface: '#fff',
        surfaceVariant: '#f5f5f5',
        onSurfaceVariant: '#666',
        onSurfaceDisabled: '#ccc',
        error: '#f44336',
        outline: '#e0e0e0',
        secondary: '#FF9800',
        background: '#fff',
        onPrimary: '#fff',
        primaryContainer: '#E3F2FD',
        onPrimaryContainer: '#1565C0',
        errorContainer: '#FFEBEE',
      },
    }),
    IconButton: ({ icon, onPress, ...props }: any) =>
      React.createElement(View, { ...props, onPress, testID: `icon-btn-${icon}` }),
    Badge: ({ children, ...props }: any) =>
      React.createElement(View, props, React.createElement(Text, null, children)),
    Icon: 'Icon',
    MD3Colors: {
      primary50: '#2196F3',
      secondary50: '#FF9800',
      error50: '#f44336',
      secondary20: '#E0E0E0',
    },
  };
});

describe('CanvasViewerScreen', () => {
  beforeEach(() => {
    mockPlatform('ios');
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockRouteParams.canvasId = 'canvas-123';
    mockRouteParams.canvasType = 'chart';
    mockRouteParams.sessionId = 'session-456';
    mockRouteParams.agentId = 'agent-789';
    (NetInfo.fetch as jest.Mock).mockResolvedValue({ isConnected: true });
  });

  afterEach(() => {
    restorePlatform();
    jest.useRealTimers();
    jest.clearAllTimers();
  });

  const renderCanvas = () => render(<CanvasViewerScreen />);

  const waitForLoaded = async () => {
    await waitFor(() => {
      expect(screen.getByText('Canvas')).toBeTruthy();
    });
  };

  const metadataPayload = (overrides: any = {}) => ({
    success: true,
    data: {
      id: 'canvas-123',
      type: 'sheets',
      metadata: {
        id: 'canvas-123',
        title: 'Quarterly Sales',
        type: 'sheets',
        agent_name: 'Sales Agent',
        agent_id: 'agent-789',
        governance_level: 'AUTONOMOUS',
        created_at: '2024-01-02T12:00:00Z',
        updated_at: '2024-02-03T12:00:00Z',
        version: 3,
        component_count: 2,
        related_canvases: [
          { id: 'canvas-rel-1', title: 'Monthly Report', type: 'chart' },
        ],
      },
      components: [],
      ...overrides,
    },
  });

  describe('Screen Rendering', () => {
    it('renders loading state initially', async () => {
      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Loading canvas...')).toBeTruthy();
      });
    });

    it('renders header with title', async () => {
      const { getByText } = renderCanvas();

      await waitForLoaded();
    });
  });

  describe('Canvas Loading', () => {
    it('loads canvas data on mount with mobile params', async () => {
      const { getByText } = renderCanvas();

      await waitForLoaded();

      expect(mockApiGet).toHaveBeenCalledWith('/api/canvas/canvas-123', {
        params: { platform: 'mobile', optimized: true },
      });
    });

    it('hides loading indicator after loading', async () => {
      const { queryByText } = renderCanvas();

      await waitFor(() => {
        expect(queryByText('Loading canvas...')).toBeNull();
      }, { timeout: 5000 });
    });
  });

  describe('Canvas Error State', () => {
    it('renders error state with server-provided message', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: false,
        error: 'Canvas not found',
      });

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Failed to Load Canvas')).toBeTruthy();
        expect(getByText('Canvas not found')).toBeTruthy();
      });
    });

    it('renders generic error when the API throws and no cache exists', async () => {
      mockApiGet.mockRejectedValueOnce(new Error('Network error'));

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Failed to Load Canvas')).toBeTruthy();
        expect(getByText('Failed to load canvas')).toBeTruthy();
      });
    });

    it('shows retry button on error', async () => {
      mockApiGet.mockRejectedValueOnce(new Error('Network error'));

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Retry')).toBeTruthy();
      });
    });

    it('retries canvas load when retry button pressed', async () => {
      mockApiGet.mockRejectedValueOnce(new Error('Network error'));
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'chart',
          components: [],
        },
      });

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Failed to Load Canvas')).toBeTruthy();
      });

      fireEvent.press(getByText('Retry'));

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledTimes(2);
        expect(getByText('No canvas components')).toBeTruthy();
      });
    });
  });

  describe('Offline Support', () => {
    it('shows offline error when disconnected and no cache exists', async () => {
      (NetInfo.fetch as jest.Mock).mockResolvedValueOnce({ isConnected: false });

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('No internet connection and no cached version available')).toBeTruthy();
      });
    });

    it('shows Offline badge when connectivity drops while viewing', async () => {
      const { getByText, queryByText } = renderCanvas();

      await waitForLoaded();
      expect(queryByText('Offline')).toBeNull();

      act(() => {
        NetInfo._emit({ isConnected: false });
      });

      expect(getByText('Offline')).toBeTruthy();
    });
  });

  describe('Fullscreen', () => {
    it('enters fullscreen and hides the header', async () => {
      const setHiddenSpy = jest.spyOn(StatusBar, 'setHidden');
      const { getByTestId, queryByText } = renderCanvas();

      await waitForLoaded();
      expect(queryByText('Was this canvas helpful?')).toBeTruthy();

      fireEvent.press(getByTestId('icon-btn-fullscreen'));

      // Header actions hidden in fullscreen — share/refresh buttons gone
      expect(queryByTestIdSafe('icon-btn-share-variant')).toBeNull();
      expect(setHiddenSpy).toHaveBeenCalledWith(true);
    });

    it('exits fullscreen and restores the status bar', async () => {
      const setHiddenSpy = jest.spyOn(StatusBar, 'setHidden');
      const { getByTestId } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-fullscreen'));
      expect(setHiddenSpy).toHaveBeenCalledWith(true);

      fireEvent.press(getByTestId('icon-btn-fullscreen-exit'));
      expect(setHiddenSpy).toHaveBeenCalledWith(false);
    });

    it('restores status bar on unmount while fullscreen', async () => {
      const setHiddenSpy = jest.spyOn(StatusBar, 'setHidden');
      const { getByTestId, unmount } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-fullscreen'));
      expect(setHiddenSpy).toHaveBeenCalledWith(true);

      unmount();
      expect(setHiddenSpy).toHaveBeenCalledWith(false);
    });
  });

  describe('Share', () => {
    it('shares the canvas with its title', async () => {
      mockApiGet.mockResolvedValueOnce(metadataPayload());
      const shareSpy = jest.spyOn(Share, 'share').mockResolvedValue({} as any);

      const { getByTestId } = renderCanvas();

      await waitFor(() => {
        expect(screen.getByText('Quarterly Sales')).toBeTruthy();
      });

      fireEvent.press(getByTestId('icon-btn-share-variant'));

      expect(shareSpy).toHaveBeenCalledWith({
        message: 'Check out this canvas: Quarterly Sales',
        url: expect.stringContaining('/canvas/canvas-123'),
      });
    });

    it('falls back to canvas id in share message without metadata', async () => {
      const shareSpy = jest.spyOn(Share, 'share').mockResolvedValue({} as any);

      const { getByTestId, getByText } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-share-variant'));

      expect(shareSpy).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Check out this canvas: canvas-123' })
      );
    });

    it('logs an error when share fails', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      jest.spyOn(Share, 'share').mockRejectedValue(new Error('share failed'));

      const { getByTestId, getByText } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-share-variant'));

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalled();
      });
      errorSpy.mockRestore();
    });
  });

  describe('Feedback', () => {
    it('records thumbs-up feedback', async () => {
      const { getByTestId } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-thumb-up'));

      // Icon color switches to primary after selecting "up"
      expect(getByTestId('icon-btn-thumb-up').props.iconColor).toBe('#2196F3');
      expect(getByTestId('icon-btn-thumb-down').props.iconColor).toBe('#666');
    });

    it('records thumbs-down feedback', async () => {
      const { getByTestId } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-thumb-down'));

      expect(getByTestId('icon-btn-thumb-down').props.iconColor).toBe('#f44336');
      expect(getByTestId('icon-btn-thumb-up').props.iconColor).toBe('#666');
    });
  });

  describe('Canvas Metadata & Related Canvases', () => {
    it('renders metadata section with title, type, version and timestamps', async () => {
      mockApiGet.mockResolvedValueOnce(metadataPayload());

      const { getByText, getAllByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Quarterly Sales')).toBeTruthy();
        expect(getByText('by Sales Agent')).toBeTruthy();
      });

      expect(getByText('Canvas Details')).toBeTruthy();
      expect(getByText('sheets')).toBeTruthy();
      expect(getByText('3')).toBeTruthy();
      expect(screen.getAllByText(/2024/).length).toBeGreaterThanOrEqual(2);
    });

    it('renders governance badge for non-autonomous canvas', async () => {
      const payload = metadataPayload();
      payload.data.metadata.governance_level = 'SUPERVISED';
      mockApiGet.mockResolvedValueOnce(payload);

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('SUPERVISED')).toBeTruthy();
      });
    });

    it('navigates to a related canvas on press', async () => {
      mockApiGet.mockResolvedValueOnce(metadataPayload());

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Monthly Report')).toBeTruthy();
      });

      fireEvent.press(getByText('Monthly Report'));

      expect(mockNavigation.push).toHaveBeenCalledWith('CanvasViewer', {
        canvasId: 'canvas-rel-1',
      });
    });

    it('renders empty state when canvas has no components', async () => {
      mockApiGet.mockResolvedValueOnce(metadataPayload());

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('No canvas components')).toBeTruthy();
      });
    });
  });

  describe('Native Component Rendering', () => {
    it('renders a chart component', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'chart',
          components: [{ id: 'c1', type: 'chart', data: { type: 'line' } }],
        },
      });

      const { getByTestId } = renderCanvas();

      await waitFor(() => {
        expect(getByTestId('mock-canvas-chart')).toBeTruthy();
      });
    });

    it('renders a sheet component', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'sheets',
          components: [{ id: 'c1', type: 'sheet', data: {} }],
        },
      });

      const { getByTestId } = renderCanvas();

      await waitFor(() => {
        expect(getByTestId('mock-canvas-sheet')).toBeTruthy();
      });
    });

    it('renders a table component', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'sheets',
          components: [{ id: 'c1', type: 'table', data: {} }],
        },
      });

      const { getByTestId } = renderCanvas();

      await waitFor(() => {
        expect(getByTestId('mock-canvas-sheet')).toBeTruthy();
      });
    });

    it('renders a terminal component with output', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'terminal',
          components: [{ id: 'c1', type: 'terminal', data: { output: ['line 1'] } }],
        },
      });

      const { getByTestId } = renderCanvas();

      await waitFor(() => {
        expect(getByTestId('mock-canvas-terminal')).toBeTruthy();
      });
    });

    it('submits form component values through the API', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'chart',
          components: [
            {
              id: 'f1',
              type: 'form',
              data: { title: 'My Form', fields: [{ name: 'name', label: 'Name' }] },
            },
          ],
        },
      });

      const { getByTestId, getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Mock Form')).toBeTruthy();
      });

      fireEvent.press(getByTestId('mock-form-submit'));

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith('/api/canvas/submit', {
          canvas_id: 'canvas-123',
          form_data: { name: 'Test User' },
          session_id: 'session-456',
          agent_id: 'agent-789',
        });
        expect(Alert.alert).toHaveBeenCalledWith('Success', 'Form submitted successfully');
      });
    });

    it('shows error alert when form component submission fails', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-123',
          type: 'chart',
          components: [
            {
              id: 'f1',
              type: 'form',
              data: { title: 'My Form', fields: [{ name: 'name', label: 'Name' }] },
            },
          ],
        },
      });
      mockApiPost.mockRejectedValueOnce(new Error('boom'));

      const { getByTestId, getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Mock Form')).toBeTruthy();
      });

      fireEvent.press(getByTestId('mock-form-submit'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to submit form');
      });
    });
  });

  describe('Web Canvas Rendering (CanvasWebView)', () => {
    const renderWebCanvas = async () => {
      mockRouteParams.canvasType = 'generic';
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: { id: 'canvas-web', type: 'generic', components: [] },
      });
      const utils = renderCanvas();
      await waitFor(() => {
        expect(screen.getByTestId('mock-webview').props.canvasId).toBe('canvas-123');
      });
      return utils;
    };

    it('renders CanvasWebView for web-oriented canvas types', async () => {
      const { getByTestId } = await renderWebCanvas();

      expect(getByTestId('mock-webview')).toBeTruthy();
      expect(screen.getByTestId('mock-webview').props.canvasType).toBe('generic');
      expect(screen.getByTestId('mock-webview').props.initialData).toBeDefined();
      expect(screen.getByTestId('mock-webview').props.onMessage).toBeDefined();
      expect(screen.getByTestId('mock-webview').props.onSubmit).toBeDefined();
      expect(screen.getByTestId('mock-webview').props.onError).toBeDefined();
    });

    it('does not render WebView for chart canvases', async () => {
      const { queryByTestId } = renderCanvas();

      await waitForLoaded();

      expect(queryByTestId('mock-webview')).toBeNull();
    });

    it('handles canvas_ready message', async () => {
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({ nativeEvent: { data: JSON.stringify({ type: 'canvas_ready' }) } });
      });

      // No crash; loading already complete
      expect(screen.getByText('Canvas')).toBeTruthy();
    });

    it('handles canvas_action message with audit logging', async () => {
      const { getByText } = await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: {
            data: JSON.stringify({ type: 'canvas_action', message: 'Saved!', component_count: 2, metadata: { k: 'v' } }),
          },
        });
      });

      expect(mockApiPost).toHaveBeenCalledWith('/api/canvas/audit', {
        canvas_id: 'canvas-123',
        canvas_type: 'generic',
        action: 'execute',
        agent_id: 'agent-789',
        session_id: 'session-456',
        component_count: 2,
        metadata: { k: 'v' },
      });
      expect(Alert.alert).toHaveBeenCalledWith('Action Executed', 'Saved!');
      expect(getByText('Canvas')).toBeTruthy();
    });

    it('logs audit failure without crashing the action alert', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      mockApiPost.mockRejectedValueOnce(new Error('audit failed'));
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: { data: JSON.stringify({ type: 'canvas_action', message: 'Done' }) },
        });
      });

      expect(Alert.alert).toHaveBeenCalledWith('Action Executed', 'Done');
      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });

    it('handles canvas_error message', async () => {
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: { data: JSON.stringify({ type: 'canvas_error', error: 'Render failed' }) },
        });
      });

      expect(Alert.alert).toHaveBeenCalledWith('Canvas Error', 'Render failed');
    });

    it('handles form_submit message successfully', async () => {
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: {
            data: JSON.stringify({ type: 'form_submit', formData: { email: 'a@b.com' } }),
          },
        });
      });

      expect(mockApiPost).toHaveBeenCalledWith('/api/canvas/submit', {
        canvas_id: 'canvas-123',
        form_data: { email: 'a@b.com' },
        session_id: 'session-456',
        agent_id: 'agent-789',
      });
      expect(Alert.alert).toHaveBeenCalledWith('Success', 'Form submitted successfully');
    });

    it('handles form_submit message failure response', async () => {
      mockApiPost.mockResolvedValueOnce({ success: false, error: 'Validation failed' });
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: { data: JSON.stringify({ type: 'form_submit', formData: {} }) },
        });
      });

      expect(Alert.alert).toHaveBeenCalledWith('Error', 'Validation failed');
    });

    it('handles form_submit message network error', async () => {
      mockApiPost.mockRejectedValueOnce(new Error('offline'));
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: { data: JSON.stringify({ type: 'form_submit', formData: {} }) },
        });
      });

      expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to submit form');
    });

    it('handles link_click message', async () => {
      const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({
          nativeEvent: { data: JSON.stringify({ type: 'link_click', url: 'https://example.com' }) },
        });
      });

      expect(logSpy).toHaveBeenCalled();
      logSpy.mockRestore();
    });

    it('logs unknown message types', async () => {
      const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({ nativeEvent: { data: JSON.stringify({ type: 'mystery' }) } });
      });

      expect(logSpy).toHaveBeenCalledWith('Unknown WebView message:', expect.anything());
      logSpy.mockRestore();
    });

    it('logs a parse error for invalid JSON messages', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      await renderWebCanvas();

      await act(async () => {
        screen.getByTestId('mock-webview').props.onMessage({ nativeEvent: { data: 'not-json{' } });
      });

      expect(errorSpy).toHaveBeenCalledWith('Failed to parse WebView message:', expect.any(Error));
      errorSpy.mockRestore();
    });

    it('renders WebView for every web canvas type', async () => {
      for (const type of ['docs', 'email', 'orchestration', 'coding', 'generic']) {
        mockRouteParams.canvasType = type;
        mockApiGet.mockResolvedValueOnce({
          success: true,
          data: { id: `canvas-${type}`, type, components: [] },
        });
        const { unmount } = renderCanvas();
        await waitFor(() => {
          expect(screen.getByTestId('mock-webview').props.canvasId).toBe('canvas-123');
        });
        unmount();
      }
    });
  });

  describe('Edge Cases', () => {
    it('handles canvas with no components', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: { id: 'canvas-no-components', type: 'chart' },
      });

      const { getByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('No canvas components')).toBeTruthy();
      });
    });

    it('handles canvases with unsupported component types without crashing', async () => {
      mockApiGet.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'canvas-mixed',
          type: 'chart',
          components: [
            { id: 'c1', type: 'markdown', data: { content: 'x' } },
            { id: 'c2', type: 'code', data: {} },
            { id: 'c3', type: 'custom', data: {} },
          ],
        },
      });

      const { getByText, queryByText } = renderCanvas();

      await waitFor(() => {
        expect(getByText('Canvas')).toBeTruthy();
      });

      // Unsupported types render nothing but don't crash
      expect(queryByText('No canvas components')).toBeNull();
    });
  });

  describe('Navigation Back', () => {
    it('navigates back when back button pressed', async () => {
      const { getByTestId } = renderCanvas();

      await waitForLoaded();

      fireEvent.press(getByTestId('icon-btn-arrow-left'));
      expect(mockNavigation.goBack).toHaveBeenCalled();
    });
  });

  describe('Refresh', () => {
    it('reloads canvas when refresh button pressed', async () => {
      const { getByTestId } = renderCanvas();

      await waitForLoaded();
      expect(mockApiGet).toHaveBeenCalledTimes(1);

      fireEvent.press(getByTestId('icon-btn-refresh'));

      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Platform-Specific Behavior', () => {
    it('renders correctly on Android', async () => {
      mockPlatform('android');
      const { getByText } = renderCanvas();

      await waitForLoaded();
    });
  });
});

// Helper so queryByTestId is available in scope of tests that didn't destructure it
function queryByTestIdSafe(id: string) {
  return screen.queryByTestId(id);
}
