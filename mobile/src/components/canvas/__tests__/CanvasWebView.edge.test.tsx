/**
 * CanvasWebView Edge-Case Tests
 *
 * Coverage wave additions targeting the branches the main suite misses:
 * - default canvasType param
 * - theme color fallbacks (mock returns an EMPTY colors object so every
 *   `theme.colors.x || fallback` in the generated HTML takes the fallback)
 * - double-tap zoom toggling (scale 1 -> 1.5 -> 1) and double-tap while a
 *   single-tap timer is pending (timer cancellation)
 * - NetInfo reporting `isConnected: null` (falls back to online)
 */

import React from 'react';
import { render, fireEvent, act } from '@testing-library/react-native';
import { CanvasWebView } from '../CanvasWebView';

// Empty theme colors -> every `theme.colors.x || fallback` branch takes the
// fallback arm (the main test file exercises the defined-color arm).
jest.mock('react-native-paper', () => ({
  useTheme: () => ({ colors: {} }),
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

describe('CanvasWebView Edge Cases', () => {
  const defaultProps = { canvasId: 'canvas-1' };

  const getWebView = (result: any) => result.getByTestId('mock-webview');

  beforeEach(() => {
    mockInjectJavaScript.mockClear();
  });

  test('uses "generic" as default canvasType when not provided', () => {
    const { getByTestId } = render(<CanvasWebView {...defaultProps} />);
    const html: string = getByTestId('mock-webview').props.source.html;
    expect(html).toContain("canvasType: 'generic'");
  });

  test('embeds zoom-disabled viewport and touch-action when enableZoom is false', () => {
    const { getByTestId } = render(
      <CanvasWebView {...defaultProps} enableZoom={false} enableGestures={false} />
    );
    const html: string = getByTestId('mock-webview').props.source.html;
    expect(html).toContain('maximum-scale=1.0');
    expect(html).toContain('user-scalable=no');
  });

  test('embeds theme color fallbacks when theme provides no colors', () => {
    const { getByTestId } = render(<CanvasWebView {...defaultProps} />);
    const html: string = getByTestId('mock-webview').props.source.html;
    // Fallback arms of the theme color ternaries
    expect(html).toContain('background-color: #ffffff');
    expect(html).toContain('color: #000000');
    expect(html).toContain('background-color: #2196F3');
    expect(html).toContain('border: 1px solid #e0e0e0');
  });

  test('treats isConnected null as online (no offline banner)', () => {
    const result = render(<CanvasWebView {...defaultProps} />);

    const listener = netInfoMock.addEventListener.mock.calls[0][0];
    act(() => { listener({ isConnected: null }); });

    expect(result.queryByText('Offline - Showing cached version')).toBeNull();
  });

  test('shows offline banner with fallback colors from empty theme', () => {
    const result = render(<CanvasWebView {...defaultProps} />);

    const listener = netInfoMock.addEventListener.mock.calls[0][0];
    act(() => { listener({ isConnected: false }); });

    expect(result.getByText('Offline - Showing cached version')).toBeTruthy();
  });

  test('double-tap zooms in then zooms back out on a second double-tap', () => {
    jest.useFakeTimers();
    const onTouch = jest.fn();
    const result = render(<CanvasWebView {...defaultProps} onTouch={onTouch} />);

    const touch = { nativeEvent: { pageX: 50, pageY: 60 } };

    // Pair 1: two touches 150ms apart = double-tap (scale 1 -> 1.5)
    fireEvent(getWebView(result), 'touchStart', touch);
    act(() => { jest.advanceTimersByTime(150); });
    fireEvent(getWebView(result), 'touchStart', touch);
    act(() => { jest.advanceTimersByTime(150); });

    expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
      expect.stringContaining('"scale":1.5')
    );

    // Wait past the double-tap window so the next pair does not pair with this one
    act(() => { jest.advanceTimersByTime(400); });

    // Pair 2: double-tap again (scale 1.5 -> 1)
    fireEvent(getWebView(result), 'touchStart', touch);
    act(() => { jest.advanceTimersByTime(150); });
    fireEvent(getWebView(result), 'touchStart', touch);
    act(() => { jest.advanceTimersByTime(150); });

    expect(mockInjectJavaScript).toHaveBeenLastCalledWith(
      expect.stringContaining('"scale":1')
    );
    expect(onTouch).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  test('double-tap cancels a pending single-tap timer', () => {
    jest.useFakeTimers();
    const onTouch = jest.fn();
    const result = render(<CanvasWebView {...defaultProps} onTouch={onTouch} />);

    const touch = { nativeEvent: { pageX: 50, pageY: 60 } };

    // First touch schedules a single-tap timer; second touch within 300ms
    // cancels it and emits a double-tap instead.
    fireEvent(getWebView(result), 'touchStart', touch);
    act(() => { jest.advanceTimersByTime(100); });
    fireEvent(getWebView(result), 'touchStart', touch);
    act(() => { jest.advanceTimersByTime(400); });

    expect(onTouch).toHaveBeenCalledTimes(1);
    expect(onTouch).toHaveBeenCalledWith(expect.objectContaining({ type: 'double_tap' }));
    jest.useRealTimers();
  });

  test('unmounting calls the NetInfo unsubscribe cleanly (no effect-cleanup error)', () => {
    // BUG: the NetInfo mock returned `{ remove: jest.fn() }` from
    // addEventListener while the real API returns an unsubscribe function;
    // the component's `return unsubscribe` effect then left React trying to
    // call `.destroy()` on a plain object ("destroy is not a function" on
    // every unmount). The mock must mirror the real API shape.
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    const result = render(<CanvasWebView {...defaultProps} />);
    const listener = netInfoMock.addEventListener.mock.calls[0][0];
    act(() => { listener({ isConnected: true }); });

    result.unmount();

    const destroyErrors = consoleErrorSpy.mock.calls.filter((call) =>
      call.some((arg) => String(arg).includes('destroy is not a function'))
    );
    expect(destroyErrors).toHaveLength(0);

    consoleErrorSpy.mockRestore();
  });

  test('message events without registered callbacks do not crash', () => {
    const result = render(<CanvasWebView {...defaultProps} />);
    const webView = getWebView(result);

    // Streaming events for unknown stream ids
    fireEvent(webView, 'message', webViewMessage({
      type: 'agent:streaming',
      payload: { stream_id: 'unknown', token: 'x' },
    }));
    fireEvent(webView, 'message', webViewMessage({
      type: 'agent:streaming_complete',
      payload: { stream_id: 'unknown' },
    }));
    fireEvent(webView, 'message', webViewMessage({
      type: 'agent:streaming_error',
      payload: { stream_id: 'unknown', error: 'boom' },
    }));

    // Unknown types fall through to onMessage
    const onMessage = jest.fn();
    const result2 = render(<CanvasWebView {...defaultProps} onMessage={onMessage} />);
    fireEvent(getWebView(result2), 'message', webViewMessage({ type: 'custom', payload: { a: 1 } }));
    expect(onMessage).toHaveBeenCalledWith({ a: 1 });

    expect(webView).toBeTruthy();
  });
});
