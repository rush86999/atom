/**
 * CanvasGestures Component
 *
 * Comprehensive touch gesture system for canvas interactions.
 * Supports tap, double-tap, long-press, pinch, pan, swipe, and multi-touch gestures.
 */

import React, { useRef, useCallback, useEffect, ReactNode } from 'react';
import {
  View,
  StyleSheet,
  GestureResponderEvent,
  PanResponder,
  Dimensions,
  NativeSyntheticEvent,
  NativeTouchEvent,
} from 'react-native';
import { useTheme } from 'react-native-paper';
import * as Haptics from 'expo-haptics';

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

// Gesture types
export type GestureType =
  | 'tap'
  | 'double_tap'
  | 'long_press'
  | 'pinch'
  | 'pan'
  | 'swipe'
  | 'two_finger_tap'
  | 'three_finger_swipe';

export interface Gesture {
  type: GestureType;
  x: number;
  y: number;
  deltaX?: number;
  deltaY?: number;
  scale?: number;
  rotation?: number;
  numberOfTouches: number;
  timestamp: number;
}

export interface GestureConfig {
  enableTap?: boolean;
  enableDoubleTap?: boolean;
  enableLongPress?: boolean;
  enablePinch?: boolean;
  enablePan?: boolean;
  enableSwipe?: boolean;
  enableTwoFingerTap?: boolean;
  enableThreeFingerSwipe?: boolean;
  doubleTapDelay?: number;
  longPressDelay?: number;
  swipeThreshold?: number;
  pinchThreshold?: number;
}

interface CanvasGesturesProps {
  children: ReactNode;
  onGesture?: (gesture: Gesture) => void;
  onGestureStateChange?: (state: 'active' | 'end' | 'cancel') => void;
  config?: GestureConfig;
  style?: any;
  disabled?: boolean;
}

const DEFAULT_CONFIG: GestureConfig = {
  enableTap: true,
  enableDoubleTap: true,
  enableLongPress: true,
  enablePinch: true,
  enablePan: true,
  enableSwipe: true,
  enableTwoFingerTap: true,
  enableThreeFingerSwipe: true,
  doubleTapDelay: 300,
  longPressDelay: 500,
  swipeThreshold: 50,
  pinchThreshold: 5,
};

/**
 * CanvasGestures Component
 *
 * Wraps children with comprehensive gesture detection and haptic feedback.
 */
export const CanvasGestures: React.FC<CanvasGesturesProps> = ({
  children,
  onGesture,
  onGestureStateChange,
  config = {},
  style,
  disabled = false,
}) => {
  const theme = useTheme();
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };

  // Refs for gesture state
  const lastTapRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const doubleTapTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const longPressTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const initialTouchRef = useRef<{ x: number; y: number; time: number }[]>([]);
  const panGestureRef = useRef<{ x: number; y: number } | null>(null);
  const pinchStartDistanceRef = useRef<number | null>(null);

  /**
   * Haptic feedback for gestures
   */
  const triggerHaptic = useCallback((type: GestureType) => {
    switch (type) {
      case 'tap':
      case 'two_finger_tap':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        break;
      case 'double_tap':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        break;
      case 'long_press':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
        break;
      case 'pinch':
      case 'swipe':
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        break;
      case 'three_finger_swipe':
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        break;
      default:
        break;
    }
  }, []);

  /**
   * Create gesture object
   */
  const createGesture = useCallback((
    type: GestureType,
    touch: NativeTouchEvent,
    additionalData: Partial<Gesture> = {}
  ): Gesture => {
    return {
      type,
      x: touch.pageX,
      y: touch.pageY,
      numberOfTouches: additionalData.numberOfTouches || 1,
      timestamp: Date.now(),
      ...additionalData,
    };
  }, []);

  /**
   * Handle touch start
   */
  const handleTouchStart = useCallback((event: NativeSyntheticEvent<any>) => {
    if (disabled) return;

    const touch = event.nativeEvent.touches[0];
    const touches = event.nativeEvent.touches;
    const numberOfTouches = touches.length;

    // Store initial touch for multi-touch gestures
    if (numberOfTouches > 0) {
      const touchArray = Array.from(touches).map(t => ({
        x: t.pageX,
        y: t.pageY,
        time: Date.now(),
      }));
      initialTouchRef.current = touchArray;
    }

    // Two-finger tap detection
    if (numberOfTouches === 2 && mergedConfig.enableTwoFingerTap) {
      const gesture = createGesture('two_finger_tap', touch, { numberOfTouches: 2 });
      onGesture?.(gesture);
      triggerHaptic('two_finger_tap');
      onGestureStateChange?.('active');
      return;
    }

    // Three-finger swipe detection start
    if (numberOfTouches === 3 && mergedConfig.enableThreeFingerSwipe) {
      onGestureStateChange?.('active');
      return;
    }

    // Pinch detection start
    if (numberOfTouches === 2 && mergedConfig.enablePinch) {
      const touch1 = touches[0];
      const touch2 = touches[1];
      const distance = Math.sqrt(
        Math.pow(touch2.pageX - touch1.pageX, 2) +
        Math.pow(touch2.pageY - touch1.pageY, 2)
      );
      pinchStartDistanceRef.current = distance;
      onGestureStateChange?.('active');
      return;
    }

    // Long press detection
    if (mergedConfig.enableLongPress && numberOfTouches === 1) {
      longPressTimeoutRef.current = setTimeout(() => {
        const gesture = createGesture('long_press', touch);
        onGesture?.(gesture);
        triggerHaptic('long_press');
        onGestureStateChange?.('active');
      }, mergedConfig.longPressDelay);
    }

    // Single tap detection (with double-tap check)
    if (mergedConfig.enableTap && numberOfTouches === 1) {
      if (doubleTapTimeoutRef.current) {
        clearTimeout(doubleTapTimeoutRef.current);
        doubleTapTimeoutRef.current = null;
      }

      const now = Date.now();
      if (lastTapRef.current) {
        const timeDiff = now - lastTapRef.current.time;
        const distDiff = Math.sqrt(
          Math.pow(touch.pageX - lastTapRef.current.x, 2) +
          Math.pow(touch.pageY - lastTapRef.current.y, 2)
        );

        // Double-tap detection
        if (
          timeDiff < mergedConfig.doubleTapDelay! &&
          distDiff < 30 &&
          mergedConfig.enableDoubleTap
        ) {
          const gesture = createGesture('double_tap', touch);
          onGesture?.(gesture);
          triggerHaptic('double_tap');
          onGestureStateChange?.('active');
          lastTapRef.current = null;
          return;
        }
      }

      lastTapRef.current = { x: touch.pageX, y: touch.pageY, time: now };

      // Schedule single tap if not double-tapped
      doubleTapTimeoutRef.current = setTimeout(() => {
        const gesture = createGesture('tap', touch);
        onGesture?.(gesture);
        triggerHaptic('tap');
        lastTapRef.current = null;
      }, mergedConfig.doubleTapDelay);
    }
  }, [
    disabled,
    mergedConfig,
    onGesture,
    onGestureStateChange,
    createGesture,
    triggerHaptic,
  ]);

  /**
   * Handle touch move
   */
  const handleTouchMove = useCallback((event: NativeSyntheticEvent<any>) => {
    if (disabled) return;

    const touches = event.nativeEvent.touches;
    const numberOfTouches = touches.length;

    // Cancel long press on move
    if (longPressTimeoutRef.current) {
      clearTimeout(longPressTimeoutRef.current);
      longPressTimeoutRef.current = null;
    }

    // Pan gesture detection
    if (numberOfTouches === 1 && mergedConfig.enablePan) {
      const touch = touches[0];
      if (!panGestureRef.current) {
        panGestureRef.current = { x: touch.pageX, y: touch.pageY };
      }
    }

    // Pinch gesture detection
    if (numberOfTouches === 2 && mergedConfig.enablePinch && pinchStartDistanceRef.current) {
      const touch1 = touches[0];
      const touch2 = touches[1];
      const currentDistance = Math.sqrt(
        Math.pow(touch2.pageX - touch1.pageX, 2) +
        Math.pow(touch2.pageY - touch1.pageY, 2)
      );
      const scale = currentDistance / pinchStartDistanceRef.current;

      if (Math.abs(scale - 1) > 0.1) {
        const gesture = createGesture('pinch', touch1, {
          scale,
          numberOfTouches: 2,
        });
        onGesture?.(gesture);
        triggerHaptic('pinch');
      }
    }
  }, [disabled, mergedConfig, onGesture, createGesture, triggerHaptic]);

  /**
   * Handle touch end
   */
  const handleTouchEnd = useCallback((event: NativeSyntheticEvent<any>) => {
    if (disabled) return;

    const touches = event.nativeEvent.touches;
    const numberOfTouches = touches.length;

    // Cancel long press
    if (longPressTimeoutRef.current) {
      clearTimeout(longPressTimeoutRef.current);
      longPressTimeoutRef.current = null;
    }

    // Pan gesture end
    if (numberOfTouches === 0 && panGestureRef.current && mergedConfig.enablePan) {
      const touch = event.nativeEvent.changedTouches[0];
      const deltaX = touch.pageX - panGestureRef.current.x;
      const deltaY = touch.pageY - panGestureRef.current.y;

      const absDeltaX = Math.abs(deltaX);
      const absDeltaY = Math.abs(deltaY);

      // Detect swipe (large movement)
      if (
        absDeltaX > mergedConfig.swipeThreshold! ||
        absDeltaY > mergedConfig.swipeThreshold!
      ) {
        const direction =
          absDeltaX > absDeltaY
            ? deltaX > 0
              ? 'right'
              : 'left'
            : deltaY > 0
            ? 'down'
            : 'up';

        const gesture = createGesture('swipe', touch, {
          deltaX,
          deltaY,
        });
        onGesture?.(gesture);
        triggerHaptic('swipe');
      } else if (absDeltaX > 10 || absDeltaY > 10) {
        // Pan (smaller movement)
        const gesture = createGesture('pan', touch, {
          deltaX,
          deltaY,
        });
        onGesture?.(gesture);
      }

      panGestureRef.current = null;
    }

    // Three-finger swipe detection
    if (numberOfTouches === 0 && initialTouchRef.current.length === 3 && mergedConfig.enableThreeFingerSwipe) {
      const lastTouch = event.nativeEvent.changedTouches[0];
      const firstTouch = initialTouchRef.current[0];
      const deltaX = lastTouch.pageX - firstTouch.x;
      const deltaY = lastTouch.pageY - firstTouch.y;

      if (Math.abs(deltaX) > 100) {
        const gesture = createGesture('three_finger_swipe', lastTouch, {
          deltaX,
          deltaY,
          numberOfTouches: 3,
        });
        onGesture?.(gesture);
        triggerHaptic('three_finger_swipe');
      }

      initialTouchRef.current = [];
    }

    // Reset pinch
    if (numberOfTouches < 2) {
      pinchStartDistanceRef.current = null;
    }

    onGestureStateChange?.('end');
  }, [disabled, mergedConfig, onGesture, onGestureStateChange, createGesture, triggerHaptic]);

  /**
   * Handle touch cancel
   */
  const handleTouchCancel = useCallback(() => {
    if (longPressTimeoutRef.current) {
      clearTimeout(longPressTimeoutRef.current);
      longPressTimeoutRef.current = null;
    }
    if (doubleTapTimeoutRef.current) {
      clearTimeout(doubleTapTimeoutRef.current);
      doubleTapTimeoutRef.current = null;
    }
    panGestureRef.current = null;
    pinchStartDistanceRef.current = null;
    initialTouchRef.current = [];
    onGestureStateChange?.('cancel');
  }, [onGestureStateChange]);

  // Cleanup timeouts
  useEffect(() => {
    return () => {
      if (longPressTimeoutRef.current) {
        clearTimeout(longPressTimeoutRef.current);
      }
      if (doubleTapTimeoutRef.current) {
        clearTimeout(doubleTapTimeoutRef.current);
      }
    };
  }, []);

  return (
    <View
      style={[styles.container, style]}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchCancel}
    >
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});

export default CanvasGestures;

/**
 * Gesture helper utilities
 */
export const GestureUtils = {
  /**
   * Check if gesture is a swipe
   */
  isSwipe(gesture: Gesture): boolean {
    return gesture.type === 'swipe';
  },

  /**
   * Get swipe direction
   */
  getSwipeDirection(gesture: Gesture): 'left' | 'right' | 'up' | 'down' | null {
    if (gesture.type !== 'swipe') return null;

    if (!gesture.deltaX || !gesture.deltaY) return null;

    const absX = Math.abs(gesture.deltaX);
    const absY = Math.abs(gesture.deltaY);

    if (absX > absY) {
      return gesture.deltaX > 0 ? 'right' : 'left';
    } else {
      return gesture.deltaY > 0 ? 'down' : 'up';
    }
  },

  /**
   * Check if gesture is pinch
   */
  isPinch(gesture: Gesture): boolean {
    return gesture.type === 'pinch';
  },

  /**
   * Get pinch scale factor
   */
  getPinchScale(gesture: Gesture): number {
    return gesture.scale || 1;
  },

  /**
   * Check if gesture is zoom in (pinch out)
   */
  isZoomIn(gesture: Gesture): boolean {
    return gesture.type === 'pinch' && (gesture.scale || 1) > 1;
  },

  /**
   * Check if gesture is zoom out (pinch in)
   */
  isZoomOut(gesture: Gesture): boolean {
    return gesture.type === 'pinch' && (gesture.scale || 1) < 1;
  },
};
