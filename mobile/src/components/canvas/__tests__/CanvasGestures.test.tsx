/**
 * CanvasGestures Component Tests
 *
 * Testing suite for the CanvasGestures touch gesture system:
 * tap, double-tap, long-press, pinch, pan, swipe, two-finger tap,
 * three-finger swipe, disabled state, config overrides, state changes,
 * and the GestureUtils helper functions.
 */

import React from 'react';
import { render, fireEvent, act } from '@testing-library/react-native';
import { Text } from 'react-native';
import { CanvasGestures, GestureUtils } from '../CanvasGestures';

describe('CanvasGestures Component', () => {
  const renderGestures = (props: any = {}) => {
    const result = render(
      <CanvasGestures {...props}>
        <Text>Content</Text>
      </CanvasGestures>
    );
    return { container: result.root, ...result };
  };

  const touchEvent = (touches: any[], changedTouches?: any[]) => ({
    nativeEvent: { touches, changedTouches: changedTouches || touches },
  });

  const singleTouch = (x: number, y: number) => [
    { pageX: x, pageY: y, identifier: 1 },
  ];

  describe('Single tap', () => {
    test('fires tap gesture after double-tap delay', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      act(() => { jest.advanceTimersByTime(300); });

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'tap', x: 10, y: 20, numberOfTouches: 1 })
      );
    });

    test('does not fire tap when enableTap is disabled', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({
        onGesture,
        config: { enableTap: false, enableLongPress: false },
      });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      act(() => { jest.advanceTimersByTime(600); });

      expect(onGesture).not.toHaveBeenCalled();
    });
  });

  describe('Double tap', () => {
    test('fires double_tap when two touches land within the delay window', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      act(() => { jest.advanceTimersByTime(100); });
      fireEvent(container, 'touchStart', touchEvent(singleTouch(12, 22)));
      act(() => { jest.advanceTimersByTime(300); });

      expect(onGesture).toHaveBeenCalledTimes(1);
      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'double_tap', x: 12, y: 22 })
      );
    });

    test('fires single tap when second touch is too far away', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      act(() => { jest.advanceTimersByTime(100); });
      fireEvent(container, 'touchStart', touchEvent(singleTouch(100, 200)));
      act(() => { jest.advanceTimersByTime(300); });

      expect(onGesture).toHaveBeenCalledTimes(1);
      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'tap', x: 100, y: 200 })
      );
    });

    test('fires single tap when enableDoubleTap is disabled', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({
        onGesture,
        config: { enableDoubleTap: false },
      });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      act(() => { jest.advanceTimersByTime(100); });
      fireEvent(container, 'touchStart', touchEvent(singleTouch(12, 22)));
      act(() => { jest.advanceTimersByTime(300); });

      expect(onGesture).toHaveBeenCalledTimes(1);
      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'tap' })
      );
    });
  });

  describe('Long press', () => {
    test('fires long_press after the configured delay', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(30, 40)));
      act(() => { jest.advanceTimersByTime(500); });

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'long_press', x: 30, y: 40 })
      );
    });

    test('is cancelled by touch move', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(30, 40)));
      act(() => { jest.advanceTimersByTime(200); });
      fireEvent(container, 'touchMove', touchEvent(singleTouch(35, 45)));
      act(() => { jest.advanceTimersByTime(600); });

      expect(onGesture).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'long_press' })
      );
    });
  });

  describe('Pan and swipe', () => {
    test('fires pan for small movement above 10px', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      fireEvent(container, 'touchMove', touchEvent(singleTouch(25, 20)));
      fireEvent(container, 'touchEnd', touchEvent([], singleTouch(40, 20)));

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'pan', deltaX: 15, deltaY: 0 })
      );
    });

    test('fires swipe for movement above the threshold', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      fireEvent(container, 'touchMove', touchEvent(singleTouch(25, 20)));
      fireEvent(container, 'touchEnd', touchEvent([], singleTouch(125, 20)));

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'swipe', deltaX: 100, deltaY: 0 })
      );
    });

    test('does not fire for movement below 10px', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      fireEvent(container, 'touchMove', touchEvent(singleTouch(15, 20)));
      fireEvent(container, 'touchEnd', touchEvent([], singleTouch(15, 20)));
      expect(onGesture).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'pan' })
      );
      expect(onGesture).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'swipe' })
      );
    });

    test('respects enablePan=false', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({
        onGesture,
        config: { enablePan: false, enableSwipe: false },
      });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      fireEvent(container, 'touchMove', touchEvent(singleTouch(110, 20)));
      fireEvent(container, 'touchEnd', touchEvent([], singleTouch(110, 20)));

      expect(onGesture).not.toHaveBeenCalled();
    });
  });

  describe('Two-finger tap', () => {
    test('fires two_finger_tap immediately on two-touch start', () => {
      const onGesture = jest.fn();
      const onGestureStateChange = jest.fn();
      const { container } = renderGestures({ onGesture, onGestureStateChange });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20).concat(singleTouch(50, 60))));
      act(() => { jest.advanceTimersByTime(300); });

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'two_finger_tap', numberOfTouches: 2 })
      );
      expect(onGestureStateChange).toHaveBeenCalledWith('active');
      // No tap/double-tap fired afterwards
      expect(onGesture).toHaveBeenCalledTimes(1);
    });
  });

  describe('Three-finger swipe', () => {
    test('fires three_finger_swipe when moved horizontally beyond 100px', () => {
      const onGesture = jest.fn();
      const onGestureStateChange = jest.fn();
      const { container } = renderGestures({ onGesture, onGestureStateChange });

      fireEvent(container, 'touchStart', touchEvent([
        { pageX: 10, pageY: 20 },
        { pageX: 50, pageY: 20 },
        { pageX: 90, pageY: 20 },
      ]));
      expect(onGestureStateChange).toHaveBeenCalledWith('active');
      onGestureStateChange.mockClear();

      fireEvent(container, 'touchEnd', touchEvent([], [{ pageX: 160, pageY: 20 }]));

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'three_finger_swipe',
          deltaX: 150,
          numberOfTouches: 3,
        })
      );
      expect(onGestureStateChange).toHaveBeenCalledWith('end');
    });

    test('does not fire three_finger_swipe for small movement', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({ onGesture });

      fireEvent(container, 'touchStart', touchEvent([
        { pageX: 10, pageY: 20 },
        { pageX: 50, pageY: 20 },
        { pageX: 90, pageY: 20 },
      ]));
      fireEvent(container, 'touchEnd', touchEvent([], [{ pageX: 60, pageY: 20 }]));

      expect(onGesture).not.toHaveBeenCalled();
    });
  });

  describe('Pinch', () => {
    test('fires pinch when scale changes beyond threshold', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({
        onGesture,
        config: { enableTwoFingerTap: false },
      });

      // Start with two fingers 100px apart
      fireEvent(container, 'touchStart', touchEvent([
        { pageX: 10, pageY: 20 },
        { pageX: 110, pageY: 20 },
      ]));

      // Move fingers to 130px apart -> scale 1.3
      fireEvent(container, 'touchMove', touchEvent([
        { pageX: 10, pageY: 20 },
        { pageX: 140, pageY: 20 },
      ]));

      expect(onGesture).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'pinch',
          scale: 1.3,
          numberOfTouches: 2,
        })
      );
    });

    test('does not fire pinch when scale stays within 10%', () => {
      const onGesture = jest.fn();
      const { container } = renderGestures({
        onGesture,
        config: { enableTwoFingerTap: false },
      });

      fireEvent(container, 'touchStart', touchEvent([
        { pageX: 10, pageY: 20 },
        { pageX: 110, pageY: 20 },
      ]));
      fireEvent(container, 'touchMove', touchEvent([
        { pageX: 10, pageY: 20 },
        { pageX: 115, pageY: 20 },
      ]));

      expect(onGesture).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'pinch' })
      );
    });
  });

  describe('Disabled state', () => {
    test('ignores all touch events when disabled', () => {
      const onGesture = jest.fn();
      const onGestureStateChange = jest.fn();
      const { container } = renderGestures({
        onGesture,
        onGestureStateChange,
        disabled: true,
      });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      act(() => { jest.advanceTimersByTime(600); });
      fireEvent(container, 'touchEnd', touchEvent([], singleTouch(10, 20)));

      expect(onGesture).not.toHaveBeenCalled();
      expect(onGestureStateChange).not.toHaveBeenCalled();
    });
  });

  describe('Gesture state changes', () => {
    test('reports end on touch end', () => {
      const onGestureStateChange = jest.fn();
      const { container } = renderGestures({ onGestureStateChange });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      fireEvent(container, 'touchEnd', touchEvent([], singleTouch(10, 20)));

      expect(onGestureStateChange).toHaveBeenCalledWith('end');
    });

    test('reports cancel on touch cancel and clears pending timers', () => {
      const onGesture = jest.fn();
      const onGestureStateChange = jest.fn();
      const { container } = renderGestures({ onGesture, onGestureStateChange });

      fireEvent(container, 'touchStart', touchEvent(singleTouch(10, 20)));
      fireEvent(container, 'touchCancel', {});

      expect(onGestureStateChange).toHaveBeenCalledWith('cancel');
      act(() => { jest.advanceTimersByTime(600); });
      expect(onGesture).not.toHaveBeenCalled();
    });
  });

  describe('Rendering', () => {
    test('renders children inside the gesture container', () => {
      const { getByText } = renderGestures();
      expect(getByText('Content')).toBeTruthy();
    });
  });
});

describe('GestureUtils', () => {
  const baseGesture: any = {
    type: 'swipe',
    x: 0,
    y: 0,
    numberOfTouches: 1,
    timestamp: 0,
  };

  test('isSwipe detects swipe gestures only', () => {
    expect(GestureUtils.isSwipe({ ...baseGesture, type: 'swipe' })).toBe(true);
    expect(GestureUtils.isSwipe({ ...baseGesture, type: 'tap' })).toBe(false);
    expect(GestureUtils.isSwipe({ ...baseGesture, type: 'pan' })).toBe(false);
  });

  test('getSwipeDirection returns horizontal then vertical direction', () => {
    expect(GestureUtils.getSwipeDirection({ ...baseGesture, deltaX: 50, deltaY: 10 })).toBe('right');
    expect(GestureUtils.getSwipeDirection({ ...baseGesture, deltaX: -50, deltaY: 10 })).toBe('left');
    expect(GestureUtils.getSwipeDirection({ ...baseGesture, deltaX: 10, deltaY: 50 })).toBe('down');
    expect(GestureUtils.getSwipeDirection({ ...baseGesture, deltaX: 10, deltaY: -50 })).toBe('up');
  });

  test('getSwipeDirection returns null for non-swipe or missing deltas', () => {
    expect(GestureUtils.getSwipeDirection({ ...baseGesture, type: 'tap', deltaX: 50, deltaY: 10 })).toBeNull();
    expect(GestureUtils.getSwipeDirection({ ...baseGesture, deltaX: 0, deltaY: 0 })).toBeNull();
  });

  test('isPinch detects pinch gestures', () => {
    expect(GestureUtils.isPinch({ ...baseGesture, type: 'pinch' })).toBe(true);
    expect(GestureUtils.isPinch({ ...baseGesture, type: 'swipe' })).toBe(false);
  });

  test('getPinchScale returns scale or defaults to 1', () => {
    expect(GestureUtils.getPinchScale({ ...baseGesture, type: 'pinch', scale: 2.5 })).toBe(2.5);
    expect(GestureUtils.getPinchScale({ ...baseGesture, type: 'pinch' })).toBe(1);
  });

  test('isZoomIn/isZoomOut classify pinch direction', () => {
    expect(GestureUtils.isZoomIn({ ...baseGesture, type: 'pinch', scale: 1.5 })).toBe(true);
    expect(GestureUtils.isZoomIn({ ...baseGesture, type: 'pinch', scale: 0.5 })).toBe(false);
    expect(GestureUtils.isZoomIn({ ...baseGesture, type: 'pinch' })).toBe(false);
    expect(GestureUtils.isZoomOut({ ...baseGesture, type: 'pinch', scale: 0.5 })).toBe(true);
    expect(GestureUtils.isZoomOut({ ...baseGesture, type: 'pinch', scale: 1.5 })).toBe(false);
    expect(GestureUtils.isZoomOut({ ...baseGesture, type: 'swipe', scale: 0.5 })).toBe(false);
  });
});
