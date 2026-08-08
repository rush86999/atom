/**
 * CanvasWebView Component Tests
 *
 * Testing suite for CanvasWebView covering:
 * - WebView message handling (canvas_ready, form_submit, action,
 *   state_change, touch_event, health_check, canvas_update, error)
 * - Loading / error / retry states
 * - Offline banner via NetInfo
 * - Imperative API (refresh/getState/setState/zoom/sendMessage)
 * - Tap and double-tap gesture handling with zoom
 * - enableGestures=false disables touch handlers
 * - Invalid message payloads do not crash
 */

import React from 'react';
import { render, fireEvent, act } from '@testing-library/react-native';
import { CanvasWebView } from '../CanvasWebView';

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: {
    Light: 'light',
    Medium: 'medium',
    Heavy: 'heavy',
  },
}));

const mockInjectJavaScript = jest.fn();

jest.mock('react-native-webview', () => {
  const React = require('react');
  const { View } = require('react-native');
  const WebView = React.forwardRef((props: any, ref: any) => {
    React.useImperativeHandle(ref, () => ({
      injectJavaScript: mockInjectJavaScript,
    }));
    return React.createElement(View, { testID: 'mock-webview', ...props });
  });
  return { WebView };
});

const netInfoMock = jest.requireMock('@react-native-community/netinfo');

const webViewMessage = (message: any) => ({
  nativeEvent: { data: JSON.stringify(message) },
});

describe('CanvasWebView Component', () => {
  const defaultProps = { canvasId: 'canvas-1', canvasType: 'chart' };

  const getWebView = (result: any) => result.getByTestId('mock-webview');

  beforeEach(() => {
    mockInjectJavaScript.mockClear();
  });

  describe('Rendering', () => {
    test('renders loading skeleton initially', () => {
      const { getByText } = render(<CanvasWebView {...defaultProps} />);
      expect(getByText('Loading canvas...')).toBeTruthy();
    });

    test('embeds canvasId and canvasType into the generated HTML source', () => {
      const { getByTestId } = render(<CanvasWebView {...defaultProps} />);
      const webView = getByTestId('mock-webview');
      const html: string = webView.props.source.html;
      expect(html).toContain("canvasId: 'canvas-1'");
      expect(html).toContain("canvasType: 'chart'");
    });

    test('does not attach touch handler when gestures are disabled', () => {
      const { getByTestId } = render(<CanvasWebView {...defaultProps} enableGestures={false} />);
      expect(getByTestId('mock-webview').props.onTouchStart).toBeUndefined();
    });
  });

  describe('Message handling', () => {
    test('handles canvas_ready: stops loading and forwards payload', () => {
      const onMessage = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onMessage={onMessage} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'canvas_ready',
        payload: { canvasId: 'canvas-1' },
      }));

      expect(onMessage).toHaveBeenCalledWith({ canvasId: 'canvas-1' });
      expect(result.queryByText('Loading canvas...')).toBeNull();
    });

    test('handles form_submit: forwards to onSubmit', () => {
      const onSubmit = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onSubmit={onSubmit} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'form_submit',
        payload: { canvasId: 'canvas-1', data: { name: 'Alice' } },
      }));

      expect(onSubmit).toHaveBeenCalledWith({ canvasId: 'canvas-1', data: { name: 'Alice' } });
    });

    test('handles action messages via onMessage', () => {
      const onMessage = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onMessage={onMessage} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'action',
        payload: { action: 'submit', data: {} },
      }));

      expect(onMessage).toHaveBeenCalledWith({ action: 'submit', data: {} });
    });

    test('handles state_change: updates canvas state and notifies onStateChange', () => {
      const onStateChange = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onStateChange={onStateChange} />);

      const state = { id: 'canvas-1', type: 'chart', data: { x: 1 }, timestamp: 0, version: 1 };
      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'state_change',
        payload: state,
      }));

      expect(onStateChange).toHaveBeenCalledWith(state);
    });

    test('handles touch_event gestures via onTouch', () => {
      const onTouch = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onTouch={onTouch} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'touch_event',
        payload: { gesture: 'long_press', x: 10, y: 20, timestamp: 1 },
      }));

      expect(onTouch).toHaveBeenCalledWith({ gesture: 'long_press', x: 10, y: 20, timestamp: 1 });
    });

    test('handles health_check messages and updates health state', () => {
      const result = render(<CanvasWebView {...defaultProps} />);

      // Fresh ping (fast response) — healthy
      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'health_check',
        payload: { lastPing: Date.now() },
      }));

      // Stale ping payload (falls back to 0) — must not crash
      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'health_check',
        payload: { lastPing: 0 },
      }));

      expect(getWebView(result)).toBeTruthy();
    });

    test('stops loading on webview load completion', () => {
      const result = render(<CanvasWebView {...defaultProps} />);
      expect(result.getByText('Loading canvas...')).toBeTruthy();

      fireEvent(getWebView(result), 'load', {});
      expect(result.queryByText('Loading canvas...')).toBeNull();
    });

    test('handles canvas_update via onMessage', () => {
      const onMessage = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onMessage={onMessage} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'canvas_update',
        payload: { type: 'resize', width: 300, height: 500 },
      }));

      expect(onMessage).toHaveBeenCalledWith({ type: 'resize', width: 300, height: 500 });
    });

    test('forwards unknown message types to onMessage', () => {
      const onMessage = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onMessage={onMessage} />);

      fireEvent(getWebView(result), 'message', webViewMessage({ type: 'custom', payload: { a: 1 } }));

      expect(onMessage).toHaveBeenCalledWith({ a: 1 });
    });

    test('does not crash on malformed JSON and logs the error', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      const result = render(<CanvasWebView {...defaultProps} />);

      fireEvent(getWebView(result), 'message', { nativeEvent: { data: 'not-json{{' } });

      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('Error handling', () => {
    test('renders error state and notifies onError when the webview fails', () => {
      const onError = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onError={onError} />);

      fireEvent(getWebView(result), 'error', {});

      expect(result.getByText('Canvas Error')).toBeTruthy();
      expect(result.getByText('Failed to load canvas')).toBeTruthy();
      expect(onError).toHaveBeenCalledWith('Failed to load canvas');
    });

    test('renders error state and retry button on error message', () => {
      const onError = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onError={onError} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'error',
        payload: { message: 'Failed to load canvas data' },
      }));

      expect(getWebView(result)).toBeTruthy();
      expect(result.getByText('Canvas Error')).toBeTruthy();
      expect(result.getByText('Failed to load canvas data')).toBeTruthy();
      expect(onError).toHaveBeenCalledWith('Failed to load canvas data');
    });

    test('retry re-requests state and shows loading again', () => {
      const result = render(<CanvasWebView {...defaultProps} />);

      fireEvent(getWebView(result), 'message', webViewMessage({
        type: 'error',
        payload: { message: 'boom' },
      }));

      expect(result.getByText('Canvas Error')).toBeTruthy();

      fireEvent.press(result.getByText('Retry'));

      expect(result.getByText('Loading canvas...')).toBeTruthy();
      expect(mockInjectJavaScript).toHaveBeenCalledWith(
        expect.stringContaining('"command":"refresh"')
      );
    });
  });

  describe('Offline banner', () => {
    test('shows offline banner when network disconnects', () => {
      const result = render(<CanvasWebView {...defaultProps} />);

      const listener = netInfoMock.addEventListener.mock.calls[0][0];
      act(() => { listener({ isConnected: false }); });

      expect(result.getByText('Offline - Showing cached version')).toBeTruthy();
    });

    test('hides offline banner when network reconnects', () => {
      const result = render(<CanvasWebView {...defaultProps} />);

      const listener = netInfoMock.addEventListener.mock.calls[0][0];
      act(() => { listener({ isConnected: false }); });
      expect(result.getByText('Offline - Showing cached version')).toBeTruthy();

      act(() => { listener({ isConnected: true }); });
      expect(result.queryByText('Offline - Showing cached version')).toBeNull();
    });

    test('does not subscribe when offlineEnabled is false', () => {
      render(<CanvasWebView {...defaultProps} offlineEnabled={false} />);
      expect(netInfoMock.addEventListener).not.toHaveBeenCalled();
    });
  });

  describe('Touch gestures', () => {
    test('fires tap gesture after 300ms with no second touch', () => {
      const onTouch = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onTouch={onTouch} />);

      fireEvent(getWebView(result), 'touchStart', { nativeEvent: { pageX: 50, pageY: 60 } });
      act(() => { jest.advanceTimersByTime(350); });

      expect(onTouch).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'tap', x: 50, y: 60 })
      );
    });

    test('fires double_tap and zooms when two touches land within 300ms', () => {
      const onTouch = jest.fn();
      const result = render(<CanvasWebView {...defaultProps} onTouch={onTouch} />);

      fireEvent(getWebView(result), 'touchStart', { nativeEvent: { pageX: 50, pageY: 60 } });
      act(() => { jest.advanceTimersByTime(150); });
      fireEvent(getWebView(result), 'touchStart', { nativeEvent: { pageX: 55, pageY: 65 } });
      act(() => { jest.advanceTimersByTime(400); });

      // Only the double-tap fires — the pending single-tap timer is cancelled
      expect(onTouch).toHaveBeenCalledTimes(1);
      expect(onTouch).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'double_tap', x: 55, y: 65 })
      );
      // Double-tap triggers zoom into the webview
      expect(mockInjectJavaScript).toHaveBeenCalledWith(
        expect.stringContaining('"command":"zoom"')
      );
    });
  });

  describe('Imperative API', () => {
    test('refresh/getState/setState/zoom/sendMessage reach the WebView', () => {
      const ref = React.createRef<any>();
      render(<CanvasWebView {...defaultProps} ref={ref} />);

      act(() => { ref.current.refresh(); });
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"command":"refresh"')
      );

      act(() => { ref.current.getState(); });
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"command":"getState"')
      );

      act(() => { ref.current.setState({ value: 42 }); });
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"command":"setState"')
      );
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"state":{"value":42}')
      );

      act(() => { ref.current.zoom(1.5); });
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"command":"zoom"')
      );
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"scale":1.5')
      );

      act(() => { ref.current.sendMessage({ hello: 'world' }); });
      expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
        expect.stringContaining('"hello":"world"')
      );
    });
  });
});
