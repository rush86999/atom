/**
 * Canvas Viewer Screen
 * WebView-based canvas viewer for mobile with optimized rendering
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Alert,
  Dimensions,
  Platform,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { WebView } from 'react-native-webview';
import { Icon, MD3Colors } from 'react-native-paper';
import { apiService } from '../../services/api';
import { CanvasType, CanvasAudit } from '../../types/canvas';

type RouteParams = {
  CanvasViewer: {
    canvasId: string;
    canvasType?: CanvasType;
    sessionId?: string;
    agentId?: string;
  };
};

const { width, height } = Dimensions.get('window');

export function CanvasViewerScreen() {
  const route = useRoute<RouteProp<RouteParams, 'CanvasViewer'>>();
  const navigation = useNavigation();

  const { canvasId, canvasType, sessionId, agentId } = route.params;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canGoBack, setCanGoBack] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(1);
  const [canvasData, setCanvasData] = useState<any>(null);

  const webViewRef = useRef<WebView>(null);

  const API_BASE_URL = __DEV__
    ? 'http://localhost:8000'
    : 'https://api.atom-platform.com';

  /**
   * Load canvas data
   */
  const loadCanvasData = async () => {
    try {
      const response = await apiService.get<any>(`/api/canvas/${canvasId}`, {
        params: {
          platform: 'mobile',
          optimized: true,
        },
      });

      if (response.success && response.data) {
        setCanvasData(response.data);
      } else {
        setError(response.error || 'Failed to load canvas');
      }
    } catch (err) {
      setError('Failed to load canvas');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle WebView navigation state change
   */
  const handleNavigationStateChange = (navState: any) => {
    setCanGoBack(navState.canGoBack);
  };

  /**
   * Handle WebView message
   */
  const handleWebViewMessage = (event: any) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);

      switch (data.type) {
        case 'canvas_action':
          handleCanvasAction(data);
          break;

        case 'canvas_error':
          handleCanvasError(data);
          break;

        case 'canvas_ready':
          setIsLoading(false);
          break;

        case 'form_submit':
          handleFormSubmit(data);
          break;

        case 'link_click':
          handleLinkClick(data);
          break;

        default:
          console.log('Unknown WebView message:', data);
      }
    } catch (error) {
      console.error('Failed to parse WebView message:', error);
    }
  };

  /**
   * Handle canvas action
   */
  const handleCanvasAction = async (data: any) => {
    console.log('Canvas action:', data);

    // Audit log
    try {
      await apiService.post('/api/canvas/audit', {
        canvas_id: canvasId,
        canvas_type: canvasType || CanvasType.GENERIC,
        action: 'execute',
        agent_id: agentId,
        session_id: sessionId,
        component_count: data.component_count || 1,
        metadata: data.metadata || {},
      });
    } catch (error) {
      console.error('Failed to audit canvas action:', error);
    }

    // Show feedback
    Alert.alert('Action Executed', data.message || 'Canvas action completed');
  };

  /**
   * Handle canvas error
   */
  const handleCanvasError = (data: any) => {
    console.error('Canvas error:', data);
    Alert.alert('Canvas Error', data.error || 'An error occurred in the canvas');
  };

  /**
   * Handle form submit
   */
  const handleFormSubmit = async (data: any) => {
    console.log('Form submit:', data);

    try {
      const response = await apiService.post('/api/canvas/submit', {
        canvas_id: canvasId,
        form_data: data.formData,
        session_id: sessionId,
        agent_id: agentId,
      });

      if (response.success) {
        Alert.alert('Success', 'Form submitted successfully');
      } else {
        Alert.alert('Error', response.error || 'Failed to submit form');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to submit form');
    }
  };

  /**
   * Handle link click
   */
  const handleLinkClick = (data: any) => {
    console.log('Link click:', data);
    // Could open in a new WebView or external browser
  };

  /**
   * Inject JavaScript for mobile optimization
   */
  const getInjectedJavaScript = () => {
    return `
      (function() {
        // Add mobile meta tag
        const meta = document.createElement('meta');
        meta.name = 'viewport';
        meta.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
        document.head.appendChild(meta);

        // Add mobile-specific CSS
        const style = document.createElement('style');
        style.textContent = \`
          * {
            -webkit-tap-highlight-color: transparent;
            -webkit-touch-callout: none;
          }

          body {
            font-size: 16px;
            overflow-x: hidden;
          }

          button, .btn {
            min-height: 44px;
            min-width: 44px;
          }

          input, textarea, select {
            font-size: 16px; /* Prevent iOS zoom */
          }

          .chart-container {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
          }

          table {
            display: block;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
          }

          table td, table th {
            min-width: 80px;
          }
        \`;
        document.head.appendChild(style);

        // Notify React Native that canvas is ready
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: 'canvas_ready'
        }));

        // Override form submit
        document.addEventListener('submit', (e) => {
          e.preventDefault();
          const formData = new FormData(e.target);
          const data = {};
          formData.forEach((value, key) => {
            data[key] = value;
          });

          window.ReactNativeWebView.postMessage(JSON.stringify({
            type: 'form_submit',
            formData: data
          }));
        });

        // Override link clicks
        document.addEventListener('click', (e) => {
          if (e.target.tagName === 'A') {
            e.preventDefault();
            window.ReactNativeWebView.postMessage(JSON.stringify({
              type: 'link_click',
              url: e.target.href
            }));
          }
        });

        // Override button clicks
        document.addEventListener('click', (e) => {
          if (e.target.tagName === 'BUTTON' || e.target.classList.contains('btn')) {
            window.ReactNativeWebView.postMessage(JSON.stringify({
              type: 'canvas_action',
              action: e.target.textContent,
              elementId: e.target.id || e.target.className
            }));
          }
        });

        // Handle canvas actions
        window.atomCanvasAction = (action, data) => {
          window.ReactNativeWebView.postMessage(JSON.stringify({
            type: 'canvas_action',
            action,
            data,
            elementId: action
          }));
        };

        // Handle canvas errors
        window.atomCanvasError = (error) => {
          window.ReactNativeWebView.postMessage(JSON.stringify({
            type: 'canvas_error',
            error
          }));
        };
      })();
    `;
  };

  /**
   * Generate HTML for canvas
   */
  const generateCanvasHTML = () => {
    return `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Canvas</title>
          <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
          <style>
            * {
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }

            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
              background-color: #f5f5f5;
              color: #333;
              line-height: 1.6;
              padding: 16px;
            }

            .canvas-container {
              max-width: 100%;
              margin: 0 auto;
            }

            .canvas-component {
              background: white;
              border-radius: 12px;
              padding: 16px;
              margin-bottom: 16px;
              box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }

            h1, h2, h3 {
              margin-bottom: 12px;
            }

            h1 { font-size: 24px; }
            h2 { font-size: 20px; }
            h3 { font-size: 18px; }

            p {
              margin-bottom: 12px;
            }

            button {
              background-color: #2196F3;
              color: white;
              border: none;
              padding: 12px 24px;
              border-radius: 8px;
              font-size: 16px;
              font-weight: 600;
              cursor: pointer;
              min-height: 44px;
            }

            button:active {
              opacity: 0.8;
            }

            input, textarea, select {
              width: 100%;
              padding: 12px;
              border: 1px solid #ddd;
              border-radius: 8px;
              font-size: 16px;
              margin-bottom: 12px;
            }

            table {
              width: 100%;
              border-collapse: collapse;
              overflow-x: auto;
              display: block;
            }

            th, td {
              padding: 12px;
              text-align: left;
              border-bottom: 1px solid #ddd;
              min-width: 120px;
            }

            th {
              background-color: #f5f5f5;
              font-weight: 600;
            }

            .chart-container {
              position: relative;
              height: 300px;
              width: 100%;
            }
          </style>
        </head>
        <body>
          <div class="canvas-container">
            <div id="canvas-root"></div>
          </div>
          <script>
            // Canvas data will be loaded here
            const canvasData = ${JSON.stringify(canvasData || {})};

            // Render canvas based on type
            function renderCanvas() {
              const root = document.getElementById('canvas-root');

              if (!canvasData || !canvasData.components) {
                root.innerHTML = '<p>No canvas data available</p>';
                return;
              }

              canvasData.components.forEach(component => {
                const div = document.createElement('div');
                div.className = 'canvas-component';

                switch (component.type) {
                  case 'markdown':
                    div.innerHTML = renderMarkdown(component.data);
                    break;
                  case 'chart':
                    div.innerHTML = renderChart(component);
                    setTimeout(() => initChart(component), 100);
                    break;
                  case 'form':
                    div.innerHTML = renderForm(component);
                    break;
                  case 'table':
                    div.innerHTML = renderTable(component);
                    break;
                  default:
                    div.innerHTML = '<p>Unknown component type</p>';
                }

                root.appendChild(div);
              });
            }

            function renderMarkdown(data) {
              return '<div>' + data.content + '</div>';
            }

            function renderChart(component) {
              return '<div class="chart-container"><canvas id="chart-' + component.id + '"></canvas></div>';
            }

            function initChart(component) {
              const ctx = document.getElementById('chart-' + component.id);
              if (!ctx) return;

              new Chart(ctx, {
                type: component.data.type,
                data: component.data.data,
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      display: component.data.show_legend !== false
                    }
                  }
                }
              });
            }

            function renderForm(component) {
              let html = '<h2>' + component.data.title + '</h2>';

              if (component.data.description) {
                html += '<p>' + component.data.description + '</p>';
              }

              component.data.fields.forEach(field => {
                html += '<label>' + field.label + '</label>';

                if (field.type === 'textarea') {
                  html += '<textarea name="' + field.name + '" placeholder="' + (field.placeholder || '') + '"' + (field.required ? ' required' : '') + '></textarea>';
                } else if (field.type === 'select') {
                  html += '<select name="' + field.name + '"' + (field.required ? ' required' : '') + '>';
                  field.options.forEach(opt => {
                    html += '<option value="' + opt + '">' + opt + '</option>';
                  });
                  html += '</select>';
                } else {
                  html += '<input type="' + field.type + '" name="' + field.name + '" placeholder="' + (field.placeholder || '') + '"' + (field.required ? ' required' : '') + ' />';
                }
              });

              html += '<button type="submit">' + (component.data.submit_button_text || 'Submit') + '</button>';

              return '<form>' + html + '</form>';
            }

            function renderTable(component) {
              let html = '<h2>' + component.data.title + '</h2>';
              html += '<table><thead><tr>';

              component.data.columns.forEach(col => {
                html += '<th>' + col.label + '</th>';
              });

              html += '</tr></thead><tbody>';

              component.data.rows.forEach(row => {
                html += '<tr>';
                component.data.columns.forEach(col => {
                  html += '<td>' + (row.data[col.key] || '') + '</td>';
                });
                html += '</tr>';
              });

              html += '</tbody></table>';
              return html;
            }

            // Initialize
            renderCanvas();
          </script>
        </body>
      </html>
    `;
  };

  /**
   * Go back in WebView history
   */
  const goBack = () => {
    if (canGoBack) {
      webViewRef.current?.goBack();
    } else {
      navigation.goBack();
    }
  };

  /**
   * Refresh canvas
   */
  const refresh = () => {
    setIsLoading(true);
    setError(null);
    loadCanvasData();
    webViewRef.current?.reload();
  };

  /**
   * Zoom in
   */
  const zoomIn = () => {
    const newZoom = Math.min(currentZoom + 0.1, 2);
    setCurrentZoom(newZoom);
    webViewRef.current?.requestContentInsetAdjustment();
  };

  /**
   * Zoom out
   */
  const zoomOut = () => {
    const newZoom = Math.max(currentZoom - 0.1, 0.5);
    setCurrentZoom(newZoom);
  };

  // Load canvas data on mount
  React.useEffect(() => {
    loadCanvasData();
  }, [canvasId]);

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Icon source="alert-circle" size={64} color={MD3Colors.error50} />
        <Text style={styles.errorTitle}>Failed to Load Canvas</Text>
        <Text style={styles.errorMessage}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={refresh}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={goBack}>
          <Icon
            source={canGoBack ? 'arrow-left' : 'close'}
            size={24}
            color="#000"
          />
        </TouchableOpacity>

        <Text style={styles.headerTitle}>Canvas</Text>

        <View style={styles.headerActions}>
          <TouchableOpacity onPress={() => webViewRef.current?.reload()}>
            <Icon source="refresh" size={24} color="#000" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Toolbar */}
      <View style={styles.toolbar}>
        <TouchableOpacity onPress={zoomOut} disabled={currentZoom <= 0.5}>
          <Icon
            source="magnify-minus-outline"
            size={20}
            color={currentZoom <= 0.5 ? MD3Colors.secondary50 : '#000'}
          />
        </TouchableOpacity>

        <Text style={styles.zoomText}>{Math.round(currentZoom * 100)}%</Text>

        <TouchableOpacity onPress={zoomIn} disabled={currentZoom >= 2}>
          <Icon
            source="magnify-plus-outline"
            size={20}
            color={currentZoom >= 2 ? MD3Colors.secondary50 : '#000'}
          />
        </TouchableOpacity>
      </View>

      {/* WebView */}
      {isLoading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={MD3Colors.primary50} />
          <Text style={styles.loadingText}>Loading canvas...</Text>
        </View>
      )}

      <WebView
        ref={webViewRef}
        source={{ html: generateCanvasHTML() }}
        style={styles.webView}
        injectedJavaScript={getInjectedJavaScript()}
        onNavigationStateChange={handleNavigationStateChange}
        onMessage={handleWebViewMessage}
        onLoadEnd={() => setIsLoading(false)}
        onError={(syntheticEvent) => {
          const { nativeEvent } = syntheticEvent;
          setError(nativeEvent.description || 'Unknown error');
          setIsLoading(false);
        }}
        javaScriptEnabled
        domStorageEnabled
        startInLoadingState
        scalesPageToFit
        bounces={false}
        overScrollMode="never"
        cacheEnabled
        incognito={false}
        originWhitelist={['*']}
        mixedContentMode="compatibility"
        thirdPartyCookiesEnabled
        sharedCookiesEnabled
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 18,
    fontWeight: '600',
  },
  headerActions: {
    flexDirection: 'row',
    gap: 16,
  },
  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    gap: 24,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  zoomText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#666',
  },
  loadingContainer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
    zIndex: 1,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#666',
  },
  webView: {
    flex: 1,
    backgroundColor: '#fff',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
  },
  errorMessage: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 24,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#2196F3',
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
