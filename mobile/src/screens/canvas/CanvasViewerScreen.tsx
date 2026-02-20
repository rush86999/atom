/**
 * Canvas Viewer Screen
 *
 * Enhanced canvas viewer screen with header actions, sharing, offline support,
 * and comprehensive canvas metadata display.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Alert,
  Dimensions,
  Platform,
  ScrollView,
  Share,
  StatusBar,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { IconButton, Badge, useTheme } from 'react-native-paper';
import * as Haptics from 'expo-haptics';
import NetInfo from '@react-native-community/netinfo';

import { apiService } from '../../services/api';
import { CanvasType } from '../../types/canvas';
import { CanvasWebView } from '../../components/canvas/CanvasWebView';
import { CanvasChart } from '../../components/canvas/CanvasChart';
import { CanvasForm } from '../../components/canvas/CanvasForm';
import { CanvasSheet } from '../../components/canvas/CanvasSheet';
import { CanvasTerminal } from '../../components/canvas/CanvasTerminal';

type RouteParams = {
  CanvasViewer: {
    canvasId: string;
    canvasType?: CanvasType;
    sessionId?: string;
    agentId?: string;
  };
};

const { width, height } = Dimensions.get('window');

interface CanvasMetadata {
  id: string;
  title: string;
  type: CanvasType;
  agent_name: string;
  agent_id: string;
  governance_level: string;
  created_at: string;
  updated_at: string;
  version: number;
  component_count: number;
  related_canvases?: Array<{
    id: string;
    title: string;
    type: CanvasType;
  }>;
}

export function CanvasViewerScreen() {
  const route = useRoute<RouteProp<RouteParams, 'CanvasViewer'>>();
  const navigation = useNavigation();
  const theme = useTheme();

  const { canvasId, canvasType, sessionId, agentId } = route.params;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [isFromCache, setIsFromCache] = useState(false);
  const [canvasData, setCanvasData] = useState<any>(null);
  const [canvasMetadata, setCanvasMetadata] = useState<CanvasMetadata | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<'up' | 'down' | null>(null);

  const webViewRef = useRef<any>(null);

  /**
   * Load canvas data with offline support
   */
  const loadCanvasData = useCallback(async () => {
    try {
      const netInfo = await NetInfo.fetch();
      const isConnected = netInfo.isConnected ?? true;
      setIsOnline(isConnected);

      if (!isConnected) {
        // Try to load from cache
        const cached = await loadCachedCanvas();
        if (cached) {
          setCanvasData(cached.data);
          setCanvasMetadata(cached.metadata);
          setIsFromCache(true);
          setIsLoading(false);
          return;
        }
        setError('No internet connection and no cached version available');
        setIsLoading(false);
        return;
      }

      const response = await apiService.get<any>(`/api/canvas/${canvasId}`, {
        params: {
          platform: 'mobile',
          optimized: true,
        },
      });

      if (response.success && response.data) {
        setCanvasData(response.data);
        setCanvasMetadata(response.data.metadata);
        setIsFromCache(false);
        // Cache the canvas
        await cacheCanvas(response.data);
      } else {
        setError(response.error || 'Failed to load canvas');
      }
    } catch (err) {
      // Try cache on error
      const cached = await loadCachedCanvas();
      if (cached) {
        setCanvasData(cached.data);
        setCanvasMetadata(cached.metadata);
        setIsFromCache(true);
      } else {
        setError('Failed to load canvas');
      }
    } finally {
      setIsLoading(false);
    }
  }, [canvasId]);

  /**
   * Cache canvas data locally
   */
  const cacheCanvas = async (data: any) => {
    try {
      // Could use AsyncStorage here
      console.log('Caching canvas:', canvasId);
    } catch (error) {
      console.error('Failed to cache canvas:', error);
    }
  };

  /**
   * Load cached canvas
   */
  const loadCachedCanvas = async () => {
    try {
      // Could use AsyncStorage here
      return null;
    } catch (error) {
      console.error('Failed to load cached canvas:', error);
      return null;
    }
  };

  /**
   * Handle refresh
   */
  const handleRefresh = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setIsFromCache(false);
    loadCanvasData();
  }, [loadCanvasData]);

  /**
   * Handle fullscreen toggle
   */
  const handleFullscreenToggle = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setIsFullscreen(prev => !prev);
    if (isFullscreen) {
      StatusBar.setHidden(false);
    } else {
      StatusBar.setHidden(true);
    }
  }, [isFullscreen]);

  /**
   * Handle share
   */
  const handleShare = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    try {
      await Share.share({
        message: `Check out this canvas: ${canvasMetadata?.title || canvasId}`,
        url: `${__DEV__ ? 'http://localhost:3000' : 'https://atom.example.com'}/canvas/${canvasId}`,
      });
    } catch (error) {
      console.error('Failed to share:', error);
    }
  }, [canvasId, canvasMetadata]);

  /**
   * Handle feedback
   */
  const handleFeedback = useCallback((type: 'up' | 'down') => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setFeedbackGiven(type);
    // Could send feedback to backend
    console.log('Feedback:', type);
  }, []);

  /**
   * Handle navigation state change
   */
  const handleNavigationStateChange = (navState: any) => {
    // Could track navigation state
  };

  // Network monitoring
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener(state => {
      setIsOnline(state.isConnected ?? true);
    });
    return unsubscribe;
  }, []);

  // Load canvas on mount
  useEffect(() => {
    loadCanvasData();
  }, [loadCanvasData]);

  // Cleanup fullscreen on unmount
  useEffect(() => {
    return () => {
      if (isFullscreen) {
        StatusBar.setHidden(false);
      }
    };
  }, [isFullscreen]);

  /**
   * Handle WebView message
   */
  const handleWebViewMessage = useCallback((event: any) => {
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
  }, []);

  /**
   * Handle canvas action
   */
  const handleCanvasAction = useCallback(async (data: any) => {
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
  }, [canvasId, canvasType, agentId, sessionId]);

  /**
   * Handle canvas error
   */
  const handleCanvasError = useCallback((data: any) => {
    console.error('Canvas error:', data);
    Alert.alert('Canvas Error', data.error || 'An error occurred in the canvas');
  }, []);

  /**
   * Handle form submit
   */
  const handleFormSubmit = useCallback(async (data: any) => {
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
  }, [canvasId, sessionId, agentId]);

  /**
   * Handle link click
   */
  const handleLinkClick = useCallback((data: any) => {
    console.log('Link click:', data);
    // Could open in a new WebView or external browser
  }, []);

  /**
   * Navigate to related canvas
   */
  const navigateToCanvas = useCallback((relatedCanvasId: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    navigation.push('CanvasViewer', {
      canvasId: relatedCanvasId,
    });
  }, [navigation]);

  /**
   * Render canvas by component type
   */
  const renderCanvasComponent = useCallback((component: any) => {
    switch (component.type) {
      case 'chart':
        return <CanvasChart data={component.data} />;

      case 'form':
        return (
          <CanvasForm
            data={component.data}
            onSubmit={async (values) => {
              try {
                await apiService.post('/api/canvas/submit', {
                  canvas_id: canvasId,
                  form_data: values,
                  session_id: sessionId,
                  agent_id: agentId,
                });
                Alert.alert('Success', 'Form submitted successfully');
              } catch (error) {
                Alert.alert('Error', 'Failed to submit form');
              }
            }}
          />
        );

      case 'sheet':
      case 'table':
        return <CanvasSheet data={component.data} />;

      case 'terminal':
        return <CanvasTerminal output={component.data.output || []} />;

      default:
        return null;
    }
  }, [canvasId, sessionId, agentId, apiService]);

  // Loading state
  if (isLoading) {
    return (
      <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.colors.onSurface }]}>
            Loading canvas...
          </Text>
        </View>
      </View>
    );
  }

  // Error state
  if (error && !canvasData) {
    return (
      <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <View style={styles.errorContainer}>
          <IconButton
            icon="alert-circle"
            size={64}
            iconColor={theme.colors.error}
          />
          <Text style={[styles.errorTitle, { color: theme.colors.onSurface }]}>
            Failed to Load Canvas
          </Text>
          <Text style={[styles.errorMessage, { color: theme.colors.onSurfaceVariant }]}>
            {error}
          </Text>
          <TouchableOpacity
            style={[styles.retryButton, { backgroundColor: theme.colors.primary }]}
            onPress={handleRefresh}
          >
            <Text style={[styles.retryButtonText, { color: theme.colors.onPrimary }]}>
              Retry
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      {/* Header */}
      {!isFullscreen && (
        <View style={[styles.header, { borderBottomColor: theme.colors.outline }]}>
          <View style={styles.headerLeft}>
            <IconButton
              icon="arrow-left"
              size={24}
              onPress={navigation.goBack}
              iconColor={theme.colors.onSurface}
            />
            <View style={styles.headerTitleContainer}>
              <Text style={[styles.headerTitle, { color: theme.colors.onSurface }]} numberOfLines={1}>
                {canvasMetadata?.title || 'Canvas'}
              </Text>
              {canvasMetadata?.agent_name && (
                <Text style={[styles.headerSubtitle, { color: theme.colors.onSurfaceVariant }]}>
                  by {canvasMetadata.agent_name}
                </Text>
              )}
            </View>
          </View>

          <View style={styles.headerActions}>
            {/* Offline indicator */}
            {!isOnline && (
              <Badge style={[styles.offlineBadge, { backgroundColor: theme.colors.error }]}>
                Offline
              </Badge>
            )}

            {/* Cached indicator */}
            {isFromCache && (
              <Badge style={[styles.cachedBadge, { backgroundColor: theme.colors.secondary }]}>
                Cached
              </Badge>
            )}

            {/* Governance badge */}
            {canvasMetadata?.governance_level && (
              <Badge
                style={[
                  styles.governanceBadge,
                  {
                    backgroundColor:
                      canvasMetadata.governance_level === 'AUTONOMOUS'
                        ? theme.colors.primary
                        : theme.colors.secondary,
                  },
                ]}
              >
                {canvasMetadata.governance_level}
              </Badge>
            )}

            <IconButton
              icon="fullscreen"
              size={20}
              onPress={handleFullscreenToggle}
              iconColor={theme.colors.onSurface}
            />
            <IconButton
              icon="share-variant"
              size={20}
              onPress={handleShare}
              iconColor={theme.colors.onSurface}
            />
            <IconButton
              icon="refresh"
              size={20}
              onPress={handleRefresh}
              iconColor={theme.colors.onSurface}
            />
          </View>
        </View>
      )}

      {/* Fullscreen close button */}
      {isFullscreen && (
        <View style={styles.fullscreenClose}>
          <IconButton
            icon="fullscreen-exit"
            size={24}
            onPress={handleFullscreenToggle}
            iconColor="#fff"
            style={[styles.fullscreenIconButton, { backgroundColor: theme.colors.surface }]}
          />
        </View>
      )}

      {/* Canvas content */}
      <ScrollView style={styles.canvasContent} showsVerticalScrollIndicator={true}>
        {canvasData?.components && canvasData.components.length > 0 ? (
          canvasData.components.map((component: any, index: number) => (
            <View key={index} style={styles.componentWrapper}>
              {renderCanvasComponent(component)}
            </View>
          ))
        ) : (
          <View style={styles.emptyContainer}>
            <Text style={[styles.emptyText, { color: theme.colors.onSurfaceVariant }]}>
              No canvas components
            </Text>
          </View>
        )}

        {/* Metadata section */}
        {canvasMetadata && !isFullscreen && (
          <View style={[styles.metadataSection, { borderTopColor: theme.colors.outline }]}>
            <Text style={[styles.metadataTitle, { color: theme.colors.onSurface }]}>
              Canvas Details
            </Text>
            <View style={styles.metadataRow}>
              <Text style={[styles.metadataLabel, { color: theme.colors.onSurfaceVariant }]}>
                Type:
              </Text>
              <Text style={[styles.metadataValue, { color: theme.colors.onSurface }]}>
                {canvasMetadata.type}
              </Text>
            </View>
            <View style={styles.metadataRow}>
              <Text style={[styles.metadataLabel, { color: theme.colors.onSurfaceVariant }]}>
                Version:
              </Text>
              <Text style={[styles.metadataValue, { color: theme.colors.onSurface }]}>
                {canvasMetadata.version}
              </Text>
            </View>
            <View style={styles.metadataRow}>
              <Text style={[styles.metadataLabel, { color: theme.colors.onSurfaceVariant }]}>
                Created:
              </Text>
              <Text style={[styles.metadataValue, { color: theme.colors.onSurface }]}>
                {new Date(canvasMetadata.created_at).toLocaleString()}
              </Text>
            </View>
            <View style={styles.metadataRow}>
              <Text style={[styles.metadataLabel, { color: theme.colors.onSurfaceVariant }]}>
                Updated:
              </Text>
              <Text style={[styles.metadataValue, { color: theme.colors.onSurface }]}>
                {new Date(canvasMetadata.updated_at).toLocaleString()}
              </Text>
            </View>
          </View>
        )}

        {/* Related canvases */}
        {canvasMetadata?.related_canvases && canvasMetadata.related_canvases.length > 0 && !isFullscreen && (
          <View style={[styles.relatedSection, { borderTopColor: theme.colors.outline }]}>
            <Text style={[styles.relatedTitle, { color: theme.colors.onSurface }]}>
              Related Canvases
            </Text>
            {canvasMetadata.related_canvases.map((related, index) => (
              <TouchableOpacity
                key={index}
                style={[styles.relatedItem, { borderBottomColor: theme.colors.outline }]}
                onPress={() => navigateToCanvas(related.id)}
              >
                <Text style={[styles.relatedItemTitle, { color: theme.colors.primary }]}>
                  {related.title}
                </Text>
                <Text style={[styles.relatedItemType, { color: theme.colors.onSurfaceVariant }]}>
                  {related.type}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>

      {/* Feedback buttons */}
      {!isFullscreen && (
        <View style={[styles.feedbackBar, { borderTopColor: theme.colors.outline }]}>
          <Text style={[styles.feedbackLabel, { color: theme.colors.onSurfaceVariant }]}>
            Was this canvas helpful?
          </Text>
          <View style={styles.feedbackButtons}>
            <TouchableOpacity
              style={[
                styles.feedbackButton,
                feedbackGiven === 'up' && { backgroundColor: theme.colors.primaryContainer },
              ]}
              onPress={() => handleFeedback('up')}
            >
              <IconButton
                icon="thumb-up"
                size={20}
                iconColor={feedbackGiven === 'up' ? theme.colors.primary : theme.colors.onSurfaceVariant}
              />
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.feedbackButton,
                feedbackGiven === 'down' && { backgroundColor: theme.colors.errorContainer },
              ]}
              onPress={() => handleFeedback('down')}
            >
              <IconButton
                icon="thumb-down"
                size={20}
                iconColor={feedbackGiven === 'down' ? theme.colors.error : theme.colors.onSurfaceVariant}
              />
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  loadingText: {
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    gap: 12,
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: '600',
  },
  errorMessage: {
    fontSize: 14,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  headerTitleContainer: {
    flex: 1,
    marginLeft: 8,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  offlineBadge: {
    fontSize: 10,
  },
  cachedBadge: {
    fontSize: 10,
  },
  governanceBadge: {
    fontSize: 10,
  },
  fullscreenClose: {
    position: 'absolute',
    top: 16,
    right: 16,
    zIndex: 1000,
  },
  fullscreenIconButton: {
    borderRadius: 20,
  },
  canvasContent: {
    flex: 1,
  },
  componentWrapper: {
    marginBottom: 16,
  },
  emptyContainer: {
    padding: 32,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
  },
  metadataSection: {
    padding: 16,
    borderTopWidth: 1,
    marginTop: 8,
  },
  metadataTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  metadataRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  metadataLabel: {
    fontSize: 14,
  },
  metadataValue: {
    fontSize: 14,
    fontWeight: '500',
  },
  relatedSection: {
    padding: 16,
    borderTopWidth: 1,
    marginTop: 8,
  },
  relatedTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  relatedItem: {
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  relatedItemTitle: {
    fontSize: 14,
    fontWeight: '500',
  },
  relatedItemType: {
    fontSize: 12,
    marginTop: 2,
  },
  feedbackBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
  },
  feedbackLabel: {
    fontSize: 14,
  },
  feedbackButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  feedbackButton: {
    padding: 4,
    borderRadius: 20,
  },
});
