/**
 * CanvasWebView Component
 *
 * WebView-based canvas viewer for rendering web canvases on mobile.
 * Handles communication between React Native and web-based canvas components.
 * Enhanced with touch gestures, pinch-to-zoom, and comprehensive state management.
 */

import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Text,
  Platform,
  RefreshControl,
  Dimensions,
  GestureResponderEvent,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useTheme } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';

// Types
interface CanvasWebViewProps {
  canvasId: string;
  canvasType?: string;
  initialData?: any;
  onMessage?: (data: any) => void;
  onSubmit?: (data: any) => void;
  onClose?: () => void;
  onError?: (error: string) => void;
  onStateChange?: (state: any) => void;
  onTouch?: (gesture: TouchGesture) => void;
  style?: any;
  enableGestures?: boolean;
  enableZoom?: boolean;
  offlineEnabled?: boolean;
}

interface WebViewMessage {
  type: 'canvas_ready' | 'form_submit' | 'canvas_update' | 'error' | 'action' | 'state_change' | 'touch_event' | 'health_check';
  payload: any;
  timestamp?: number;
}

interface TouchGesture {
  type: 'tap' | 'long_press' | 'pinch' | 'pan' | 'double_tap';
  x: number;
  y: number;
  scale?: number;
  timestamp: number;
}

interface CanvasState {
  id: string;
  type: string;
  data: any;
  timestamp: number;
  version: number;
}

interface CanvasHealth {
  isReady: boolean;
  lastPing: number;
  responseTime: number;
  isHealthy: boolean;
}

const { width: screenWidth, height: screenHeight } = Dimensions.get('window');

/**
 * CanvasWebView Component
 *
 * Renders web-based canvas components in a WebView with
 * bidirectional communication bridge, gesture support, and health monitoring.
 */
export const CanvasWebView = React.forwardRef<any, CanvasWebViewProps>(({
  canvasId,
  canvasType = 'generic',
  initialData,
  onMessage,
  onSubmit,
  onClose,
  onError,
  onStateChange,
  onTouch,
  style,
  enableGestures = true,
  enableZoom = true,
  offlineEnabled = true,
}, ref) => {
  const theme = useTheme();
  const webViewRef = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canvasReady, setCanvasReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [canvasState, setCanvasState] = useState<CanvasState | null>(null);
  const [health, setHealth] = useState<CanvasHealth>({
    isReady: false,
    lastPing: 0,
    responseTime: 0,
    isHealthy: false,
  });
  const [currentScale, setCurrentScale] = useState(1);

  // Health check interval
  const healthCheckInterval = useRef<NodeJS.Timeout | null>(null);
  const lastTouchTime = useRef<number>(0);
  const doubleTapTimeout = useRef<NodeJS.Timeout | null>(null);

  /**
   * Generate HTML for canvas rendering with enhanced bridge
   */
  const generateCanvasHTML = () => {
    const API_BASE = __DEV__ ? 'http://localhost:3000' : 'https://atom.example.com';

    return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=${enableZoom ? '3.0' : '1.0'}, user-scalable=${enableZoom ? 'yes' : 'no'}">
  <title>Atom Canvas</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background-color: ${theme.colors.background || '#ffffff'};
      color: ${theme.colors.onBackground || '#000000'};
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
      touch-action: ${enableGestures ? 'pan-x pan-y pinch-zoom' : 'auto'};
    }

    #root {
      min-height: 100vh;
      padding: 16px;
      transform-origin: top center;
      transition: transform 0.3s ease-out;
    }

    .canvas-container {
      max-width: 100%;
      margin: 0 auto;
    }

    .loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      font-size: 16px;
      color: ${theme.colors.onSurface || '#666666'};
    }

    .error {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      padding: 20px;
      text-align: center;
    }

    .error h2 {
      color: ${theme.colors.error || '#d32f2f'};
      margin-bottom: 8px;
    }

    /* Mobile-optimized button styles */
    button {
      padding: 12px 24px;
      font-size: 16px;
      border: none;
      border-radius: 8px;
      background-color: ${theme.colors.primary || '#2196F3'};
      color: ${theme.colors.onPrimary || '#ffffff'};
      cursor: pointer;
      margin: 4px;
      min-width: 120px;
      min-height: 44px;
      touch-action: manipulation;
    }

    button:active {
      opacity: 0.8;
      transform: scale(0.98);
    }

    input, textarea, select {
      width: 100%;
      padding: 12px;
      font-size: 16px;
      border: 1px solid ${theme.colors.outline || '#e0e0e0'};
      border-radius: 8px;
      margin: 8px 0;
      background-color: ${theme.colors.surface || '#f5f5f5'};
      color: ${theme.colors.onSurface || '#000000'};
      touch-action: manipulation;
    }

    input:focus, textarea:focus, select:focus {
      outline: 2px solid ${theme.colors.primary || '#2196F3'};
      outline-offset: -1px;
    }

    /* Chart styles */
    .chart-container {
      width: 100%;
      height: 300px;
      margin: 16px 0;
      border-radius: 8px;
      background-color: ${theme.colors.surfaceVariant || '#eeeeee'};
      padding: 16px;
      touch-action: ${enableZoom ? 'pan-x pan-y pinch-zoom' : 'auto'};
    }

    /* Table styles */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 14px;
      overflow-x: auto;
      display: block;
    }

    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid ${theme.colors.outline || '#e0e0e0'};
      min-width: 100px;
    }

    th {
      background-color: ${theme.colors.surfaceVariant || '#f5f5f5'};
      font-weight: 600;
      position: sticky;
      top: 0;
    }
  </style>
</head>
<body>
  <div id="root"></div>

  <script>
    // Enhanced Canvas Bridge for bidirectional communication
    const AtomCanvasBridge = {
      canvasId: '${canvasId}',
      canvasType: '${canvasType}',
      token: null,
      state: null,
      subscribers: [],
      version: 0,
      lastPing: Date.now(),

      async init() {
        try {
          // Get auth token
          this.token = await this.getToken();

          // Setup state API
          this.setupStateAPI();

          // Send ready message
          this.postMessage({
            type: 'canvas_ready',
            payload: { canvasId: this.canvasId, canvasType: this.canvasType },
            timestamp: Date.now()
          });

          // Load canvas data
          await this.loadCanvas();

          // Setup health check
          this.startHealthCheck();

          // Setup resize observer
          this.setupResizeObserver();
        } catch (error) {
          this.postMessage({
            type: 'error',
            payload: { message: error.message },
            timestamp: Date.now()
          });
        }
      },

      async getToken() {
        return '${initialData?.token || ''}';
      },

      setupStateAPI() {
        // Expose state API globally
        window.atom = window.atom || {};
        window.atom.canvas = {
          getState: () => this.state,
          getAllStates: () => ({ [this.canvasId]: this.state }),
          setState: (newState) => {
            const oldState = this.state;
            this.state = { ...oldState, ...newState, version: ++this.version };
            this.notifySubscribers(this.state);
            this.postMessage({
              type: 'state_change',
              payload: this.state,
              timestamp: Date.now()
            });
          },
          subscribe: (callback) => {
            this.subscribers.push(callback);
            return () => {
              this.subscribers = this.subscribers.filter(cb => cb !== callback);
            };
          }
        };
      },

      notifySubscribers(state) {
        this.subscribers.forEach(callback => {
          try {
            callback(state);
          } catch (error) {
            console.error('Subscriber error:', error);
          }
        });
      },

      async loadCanvas() {
        const response = await fetch('${API_BASE}/api/canvas/${this.canvasId}?platform=mobile', {
          headers: {
            'Authorization': \`Bearer \${this.token}\`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          throw new Error('Failed to load canvas');
        }

        const data = await response.json();
        this.state = data;
        this.renderCanvas(data);
      },

      postMessage(message) {
        // @ts-ignore
        if (window.ReactNativeWebView) {
          // @ts-ignore
          window.ReactNativeWebView.postMessage(JSON.stringify(message));
        } else {
          console.log('WebView Message:', message);
        }
      },

      renderCanvas(data) {
        const root = document.getElementById('root');
        root.innerHTML = this.generateCanvasHTML(data);
        this.attachEventListeners();
      },

      generateCanvasHTML(data) {
        // Override in canvas type-specific implementations
        return '<div class="loading">Loading canvas...</div>';
      },

      attachEventListeners() {
        // Touch events
        let lastTouch = { x: 0, y: 0, time: 0 };
        let longPressTimer = null;

        document.addEventListener('touchstart', (e) => {
          const touch = e.touches[0];
          lastTouch = { x: touch.clientX, y: touch.clientY, time: Date.now() };

          // Long press detection
          longPressTimer = setTimeout(() => {
            this.postMessage({
              type: 'touch_event',
              payload: {
                gesture: 'long_press',
                x: touch.clientX,
                y: touch.clientY,
                timestamp: Date.now()
              }
            });
          }, 500);
        }, { passive: true });

        document.addEventListener('touchmove', () => {
          if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
          }
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
          if (longPressTimer) {
            clearTimeout(longPressTimer);
          }

          const touch = e.changedTouches[0];
          const duration = Date.now() - lastTouch.time;
          const distance = Math.sqrt(
            Math.pow(touch.clientX - lastTouch.x, 2) +
            Math.pow(touch.clientY - lastTouch.y, 2)
          );

          // Tap detection (short duration, minimal movement)
          if (duration < 300 && distance < 10) {
            this.postMessage({
              type: 'touch_event',
              payload: {
                gesture: 'tap',
                x: touch.clientX,
                y: touch.clientY,
                timestamp: Date.now()
              }
            });
          }
        });

        // Form submits
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
          form.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());

            this.postMessage({
              type: 'form_submit',
              payload: { canvasId: this.canvasId, data },
              timestamp: Date.now()
            });
          });
        });

        // Button actions
        const buttons = document.querySelectorAll('button[data-action]');
        buttons.forEach(button => {
          button.addEventListener('click', () => {
            const action = button.getAttribute('data-action');
            const actionData = button.getAttribute('data-action-data');

            this.postMessage({
              type: 'action',
              payload: {
                canvasId: this.canvasId,
                action,
                data: actionData ? JSON.parse(actionData) : {}
              },
              timestamp: Date.now()
            });
          });
        });
      },

      startHealthCheck() {
        setInterval(() => {
          this.postMessage({
            type: 'health_check',
            payload: {
              canvasId: this.canvasId,
              lastPing: this.lastPing
            },
            timestamp: Date.now()
          });
          this.lastPing = Date.now();
        }, 30000); // Every 30 seconds
      },

      setupResizeObserver() {
        if (window.ResizeObserver) {
          const resizeObserver = new ResizeObserver(entries => {
            for (let entry of entries) {
              this.postMessage({
                type: 'canvas_update',
                payload: {
                  type: 'resize',
                  width: entry.contentRect.width,
                  height: entry.contentRect.height
                },
                timestamp: Date.now()
              });
            }
          });
          resizeObserver.observe(document.body);
        }
      }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => AtomCanvasBridge.init());
    } else {
      AtomCanvasBridge.init();
    }

    // Listen for messages from React Native
    document.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.command) {
          case 'getState':
            AtomCanvasBridge.postMessage({
              type: 'state_change',
              payload: AtomCanvasBridge.state
            });
            break;

          case 'setState':
            if (window.atom?.canvas?.setState) {
              window.atom.canvas.setState(data.state);
            }
            break;

          case 'refresh':
            AtomCanvasBridge.loadCanvas();
            break;

          case 'zoom':
            const root = document.getElementById('root');
            if (root && data.scale) {
              root.style.transform = \`scale(\${data.scale})\`;
            }
            break;

          default:
            console.log('Unknown command from React Native:', data);
        }
      } catch (error) {
        console.error('Error handling message from React Native:', error);
      }
    });
  </script>
</body>
</html>
    `;
  };

  /**
   * Handle messages from WebView with enhanced types
   */
  const handleWebViewMessage = useCallback((event: any) => {
    try {
      const message: WebViewMessage = JSON.parse(event.nativeEvent.data);

      switch (message.type) {
        case 'canvas_ready':
          setCanvasReady(true);
          setLoading(false);
          setHealth(prev => ({ ...prev, isReady: true, isHealthy: true, lastPing: Date.now() }));
          onMessage?.(message.payload);
          break;

        case 'form_submit':
          onSubmit?.(message.payload);
          break;

        case 'action':
          onMessage?.(message.payload);
          break;

        case 'state_change':
          const newState = message.payload as CanvasState;
          setCanvasState(newState);
          onStateChange?.(newState);
          break;

        case 'touch_event':
          const gesture = message.payload as TouchGesture;
          onTouch?.(gesture);
          break;

        case 'health_check':
          const responseTime = Date.now() - (message.payload.lastPing || 0);
          setHealth(prev => ({
            ...prev,
            lastPing: Date.now(),
            responseTime,
            isHealthy: responseTime < 5000, // Healthy if response < 5s
          }));
          break;

        case 'canvas_update':
          onMessage?.(message.payload);
          break;

        case 'error':
          setError(message.payload.message);
          setLoading(false);
          onError?.(message.payload.message);
          break;

        default:
          onMessage?.(message.payload);
      }
    } catch (err) {
      console.error('Failed to parse WebView message:', err);
    }
  }, [onMessage, onSubmit, onError, onStateChange, onTouch]);

  /**
   * Handle WebView errors
   */
  const handleWebViewError = () => {
    setError('Failed to load canvas');
    setLoading(false);
    onError?.('Failed to load canvas');
  };

  /**
   * Handle WebView load completion
   */
  const handleWebViewLoad = () => {
    setLoading(false);
  };

  /**
   * Handle pull-to-refresh
   */
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, []);

  /**
   * Send message to WebView
   */
  const sendMessageToWebView = useCallback((message: any) => {
    if (webViewRef.current) {
      webViewRef.current.injectJavaScript(`
        (function() {
          try {
            window.dispatchEvent(new MessageEvent('message', {
              data: ${JSON.stringify(message)}
            }));
          } catch (error) {
            console.error('Error sending message to WebView:', error);
          }
        })();
      `);
    }
  }, []);

  /**
   * Refresh canvas
   */
  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    sendMessageToWebView({ type: 'refresh' });
  }, [sendMessageToWebView]);

  /**
   * Get canvas state
   */
  const getState = useCallback(() => {
    sendMessageToWebView({ command: 'getState' });
  }, [sendMessageToWebView]);

  /**
   * Set canvas state
   */
  const setState = useCallback((state: any) => {
    sendMessageToWebView({ command: 'setState', state });
  }, [sendMessageToWebView]);

  /**
   * Zoom canvas
   */
  const zoom = useCallback((scale: number) => {
    setCurrentScale(scale);
    sendMessageToWebView({ command: 'zoom', scale });
  }, [sendMessageToWebView]);

  /**
   * Handle touch events for double-tap detection
   */
  const handleTouchStart = useCallback((event: GestureResponderEvent) => {
    if (!enableGestures) return;

    const now = Date.now();
    const timeSinceLastTouch = now - lastTouchTime.current;

    // Double-tap detection (within 300ms)
    if (timeSinceLastTouch < 300 && timeSinceLastTouch > 0) {
      const gesture: TouchGesture = {
        type: 'double_tap',
        x: event.nativeEvent.pageX,
        y: event.nativeEvent.pageY,
        timestamp: now,
      };
      onTouch?.(gesture);

      // Double-tap to zoom
      if (enableZoom) {
        const newScale = currentScale === 1 ? 1.5 : 1;
        zoom(newScale);
      }

      if (doubleTapTimeout.current) {
        clearTimeout(doubleTapTimeout.current);
        doubleTapTimeout.current = null;
      }
    } else {
      // Set timeout to detect single tap
      doubleTapTimeout.current = setTimeout(() => {
        const gesture: TouchGesture = {
          type: 'tap',
          x: event.nativeEvent.pageX,
          y: event.nativeEvent.pageY,
          timestamp: now,
        };
        onTouch?.(gesture);
      }, 300);
    }

    lastTouchTime.current = now;
  }, [enableGestures, enableZoom, currentScale, zoom, onTouch]);

  // Monitor network connectivity
  useEffect(() => {
    if (!offlineEnabled) return;

    const unsubscribe = NetInfo.addEventListener(state => {
      setIsOnline(state.isConnected ?? true);
    });

    return unsubscribe;
  }, [offlineEnabled]);

  // Health check cleanup
  useEffect(() => {
    return () => {
      if (healthCheckInterval.current) {
        clearInterval(healthCheckInterval.current);
      }
    };
  }, []);

  // Expose imperative API
  React.useImperativeHandle(ref, () => ({
    refresh,
    getState,
    setState,
    zoom,
    sendMessage: sendMessageToWebView,
  }));

  return (
    <View style={[styles.container, style]}>
      {/* Offline indicator */}
      {!isOnline && offlineEnabled && (
        <View style={[styles.offlineBanner, { backgroundColor: theme.colors.error || '#d32f2f' }]}>
          <Text style={[styles.offlineText, { color: theme.colors.onError || '#fff' }]}>
            Offline - Showing cached version
          </Text>
        </View>
      )}

      {/* Loading skeleton */}
      {loading && !error && (
        <View style={styles.statusContainer}>
          <View style={styles.skeletonContainer}>
            <ActivityIndicator size="large" color={theme.colors.primary} />
            <Text style={[styles.statusText, { color: theme.colors.onSurface }]}>
              Loading canvas...
            </Text>
          </View>
        </View>
      )}

      {/* Error state */}
      {error && !loading && (
        <View style={styles.statusContainer}>
          <View style={styles.errorContainer}>
            <Text style={[styles.errorTitle, { color: theme.colors.error }]}>
              Canvas Error
            </Text>
            <Text style={[styles.errorMessage, { color: theme.colors.onSurface }]}>
              {error}
            </Text>
            <TouchableOpacity
              style={[styles.retryButton, { backgroundColor: theme.colors.primary }]}
              onPress={refresh}
            >
              <Text style={[styles.retryButtonText, { color: theme.colors.onPrimary }]}>
                Retry
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* WebView */}
      <WebView
        ref={webViewRef}
        source={{ html: generateCanvasHTML() }}
        onMessage={handleWebViewMessage}
        onError={handleWebViewError}
        onLoad={handleWebViewLoad}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        startInLoadingState={true}
        scalesPageToFit={true}
        style={[styles.webView, { opacity: loading || error ? 0 : 1 }]}
        renderLoading={() => null}
        originWhitelist={['*']}
        mixedContentMode="compatibility"
        thirdPartyCookiesEnabled={false}
        onTouchStart={enableGestures ? handleTouchStart : undefined}
        cacheEnabled={offlineEnabled}
        incognito={!offlineEnabled}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  webView: {
    flex: 1,
  },
  statusContainer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1,
  },
  skeletonContainer: {
    alignItems: 'center',
    gap: 16,
  },
  statusText: {
    fontSize: 16,
  },
  errorContainer: {
    alignItems: 'center',
    padding: 24,
    gap: 12,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: '600',
    marginBottom: 8,
  },
  errorMessage: {
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 16,
  },
  retryButton: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  offlineBanner: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
  },
  offlineText: {
    fontSize: 12,
    fontWeight: '600',
  },
});

CanvasWebView.displayName = 'CanvasWebView';

export default CanvasWebView;
