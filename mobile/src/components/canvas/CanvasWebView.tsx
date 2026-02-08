/**
 * CanvasWebView Component
 *
 * WebView-based canvas viewer for rendering web canvases on mobile.
 * Handles communication between React Native and web-based canvas components.
 */

import React, { useRef, useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Text,
  Platform,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useTheme } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Types
interface CanvasWebViewProps {
  canvasId: string;
  canvasType?: string;
  initialData?: any;
  onMessage?: (data: any) => void;
  onSubmit?: (data: any) => void;
  onClose?: () => void;
  onError?: (error: string) => void;
  style?: any;
}

interface WebViewMessage {
  type: 'canvas_ready' | 'form_submit' | 'canvas_update' | 'error' | 'action';
  payload: any;
}

/**
 * CanvasWebView Component
 *
 * Renders web-based canvas components in a WebView with
 * bidirectional communication bridge.
 */
export const CanvasWebView: React.FC<CanvasWebViewProps> = ({
  canvasId,
  canvasType = 'generic',
  initialData,
  onMessage,
  onSubmit,
  onClose,
  onError,
  style,
}) => {
  const theme = useTheme();
  const webViewRef = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canvasReady, setCanvasReady] = useState(false);

  /**
   * Generate HTML for canvas rendering
   */
  const generateCanvasHTML = () => {
    const API_BASE = __DEV__ ? 'http://localhost:3000' : 'https://atom.example.com';

    return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Atom Canvas</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background-color: ${theme.colors.background};
      color: ${theme.colors.onBackground};
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }

    #root {
      min-height: 100vh;
      padding: 16px;
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
      color: ${theme.colors.onSurface};
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
      color: ${theme.colors.error};
      margin-bottom: 8px;
    }

    /* Mobile-optimized button styles */
    button {
      padding: 12px 24px;
      font-size: 16px;
      border: none;
      border-radius: 8px;
      background-color: ${theme.colors.primary};
      color: ${theme.colors.onPrimary};
      cursor: pointer;
      margin: 4px;
      min-width: 120px;
    }

    button:active {
      opacity: 0.8;
    }

    input, textarea, select {
      width: 100%;
      padding: 12px;
      font-size: 16px;
      border: 1px solid ${theme.colors.outline};
      border-radius: 8px;
      margin: 8px 0;
      background-color: ${theme.colors.surface};
      color: ${theme.colors.onSurface};
    }

    input:focus, textarea:focus, select:focus {
      outline: 2px solid ${theme.colors.primary};
      outline-offset: -1px;
    }

    /* Chart styles */
    .chart-container {
      width: 100%;
      height: 300px;
      margin: 16px 0;
      border-radius: 8px;
      background-color: ${theme.colors.surfaceVariant};
      padding: 16px;
    }

    /* Table styles */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 14px;
    }

    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid ${theme.colors.outline};
    }

    th {
      background-color: ${theme.colors.surfaceVariant};
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div id="root"></div>

  <script>
    // Canvas bridge for communication with React Native
    const AtomCanvasBridge = {
      canvasId: '${canvasId}',
      canvasType: '${canvasType}',
      token: null,

      async init() {
        try {
          // Get auth token
          this.token = await this.getToken();

          // Send ready message
          this.postMessage({
            type: 'canvas_ready',
            payload: { canvasId: this.canvasId }
          });

          // Load canvas data
          await this.loadCanvas();
        } catch (error) {
          this.postMessage({
            type: 'error',
            payload: { message: error.message }
          });
        }
      },

      async getToken() {
        // In production, this would come from AsyncStorage or injected by React Native
        return '${initialData?.token || ''}';
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
        // Attach event listeners for forms, buttons, etc.
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
          form.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());

            this.postMessage({
              type: 'form_submit',
              payload: { canvasId: this.canvasId, data }
            });
          });
        });

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
              }
            });
          });
        });
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
      const data = JSON.parse(event.data);
      // Handle messages from React Native if needed
      console.log('Message from React Native:', data);
    });
  </script>
</body>
</html>
    `;
  };

  /**
   * Handle messages from WebView
   */
  const handleWebViewMessage = (event: any) => {
    try {
      const message: WebViewMessage = JSON.parse(event.nativeEvent.data);

      switch (message.type) {
        case 'canvas_ready':
          setCanvasReady(true);
          setLoading(false);
          onMessage?.(message);
          break;

        case 'form_submit':
          onSubmit?.(message.payload);
          break;

        case 'action':
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
  };

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
   * Send message to WebView
   */
  const sendMessageToWebView = (message: any) => {
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
  };

  /**
   * Refresh canvas
   */
  const refresh = () => {
    setLoading(true);
    setError(null);
    sendMessageToWebView({ type: 'refresh' });
  };

  return (
    <View style={[styles.container, style]}>
      {(loading || error) && (
        <View style={styles.statusContainer}>
          {loading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={theme.colors.primary} />
              <Text style={[styles.statusText, { color: theme.colors.onSurface }]}>
                Loading canvas...
              </Text>
            </View>
          )}

          {error && (
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
          )}
        </View>
      )}

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
        onError={handleWebViewError}
        renderLoading={() => null}
        originWhitelist={['*']}
        mixedContentMode="compatibility"
        thirdPartyCookiesEnabled={false}
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
  loadingContainer: {
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
});

export default CanvasWebView;
