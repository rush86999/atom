/**
 * Offline Indicator Component
 *
 * Prominent offline indicator with sync status and action buttons.
 *
 * Features:
 * - Top banner indicator when offline
 * - Connection status (connected, connecting, disconnected)
 * - Pending actions count
 * - "Sync Now" button when online
 * - Last successful sync time
 * - Animated icon for connecting state
 * - Dismissible banner
 * - Sync progress bar during sync
 * - Error state with retry
 * - Tap to view pending actions
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Dimensions,
} from 'react-native';
import { useTheme } from '@react-navigation/native';
import Icon from 'react-native-vector-icons/Ionicons';
import { offlineSyncService, SyncState } from '../../services/offlineSyncService';

const { width } = Dimensions.get('window');

interface OfflineIndicatorProps {
  onViewPendingActions?: () => void;
  style?: any;
}

export const OfflineIndicator: React.FC<OfflineIndicatorProps> = ({
  onViewPendingActions,
  style,
}) => {
  const { colors } = useTheme();
  const [syncState, setSyncState] = useState<SyncState>({
    lastSyncAt: null,
    lastSuccessfulSyncAt: null,
    pendingCount: 0,
    syncInProgress: false,
    consecutiveFailures: 0,
  });
  const [isVisible, setIsVisible] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [hasError, setHasError] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // Animation for connecting state
  const [rotateAnim] = useState(new Animated.Value(0));

  useEffect(() => {
    // Subscribe to sync state changes
    const unsubscribe = offlineSyncService.subscribe((state) => {
      setSyncState(state);
      setSyncProgress(state.syncProgress);
      setHasError(state.consecutiveFailures > 2);

      // Show banner if offline or has pending actions
      const shouldShow = !isOnline || state.pendingCount > 0 || state.syncInProgress;
      setIsVisible(shouldShow && !dismissed);

      // Start/stop connecting animation
      if (state.syncInProgress && !isConnecting) {
        setIsConnecting(true);
        startRotationAnimation();
      } else if (!state.syncInProgress && isConnecting) {
        setIsConnecting(false);
        stopRotationAnimation();
      }
    });

    // Check initial online status
    checkOnlineStatus();

    // Periodic online check (every 10 seconds)
    const interval = setInterval(checkOnlineStatus, 10000);

    return () => {
      unsubscribe();
      clearInterval(interval);
      stopRotationAnimation();
    };
  }, [dismissed, isOnline]);

  const checkOnlineStatus = async () => {
    try {
      // Simple ping to check connectivity
      const state = await offlineSyncService.getSyncState();
      const online = !state.syncInProgress; // Simplified check
      setIsOnline(online);
    } catch (error) {
      setIsOnline(false);
    }
  };

  const startRotationAnimation = () => {
    Animated.loop(
      Animated.timing(rotateAnim, {
        toValue: 1,
        duration: 1000,
        useNativeDriver: true,
      })
    ).start();
  };

  const stopRotationAnimation = () => {
    rotateAnim.stopAnimation();
  };

  const handleSyncNow = async () => {
    try {
      setHasError(false);
      await offlineSyncService.triggerSync();
    } catch (error) {
      setHasError(true);
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    setIsVisible(false);

    // Show again after 5 minutes
    setTimeout(() => {
      setDismissed(false);
    }, 5 * 60 * 1000);
  };

  const handleTap = () => {
    if (syncState.pendingCount > 0 && onViewPendingActions) {
      onViewPendingActions();
    }
  };

  if (!isVisible) {
    return null;
  }

  const getStatusText = () => {
    if (hasError) {
      return 'Sync Error - Tap to Retry';
    }
    if (!isOnline) {
      return 'Offline - Changes Saved Locally';
    }
    if (syncState.syncInProgress) {
      return `Syncing... ${syncProgress}%`;
    }
    if (syncState.pendingCount > 0) {
      return `${syncState.pendingCount} Pending Changes`;
    }
    return 'All Synced';
  };

  const getStatusColor = () => {
    if (hasError) return '#FF3B30'; // Red
    if (!isOnline) return '#FF9500'; // Orange
    if (syncState.syncInProgress) return '#007AFF'; // Blue
    return '#34C759'; // Green
  };

  const getStatusIcon = () => {
    if (hasError) return 'alert-circle';
    if (!isOnline) return 'cloud-offline';
    if (syncState.syncInProgress) return 'sync';
    return 'cloud-done';
  };

  const formatLastSyncTime = () => {
    if (!syncState.lastSuccessfulSyncAt) {
      return 'Never';
    }

    const now = new Date();
    const diff = now.getTime() - new Date(syncState.lastSuccessfulSyncAt).getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const rotate = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <TouchableOpacity
      style={[
        styles.container,
        { backgroundColor: getStatusColor() },
        style,
      ]}
      onPress={handleTap}
      activeOpacity={0.9}
    >
      <View style={styles.content}>
        <View style={styles.leftContent}>
          {isConnecting ? (
            <Animated.View style={{ transform: [{ rotate }] }}>
              <Icon name={getStatusIcon()} size={24} color="#FFFFFF" />
            </Animated.View>
          ) : (
            <Icon name={getStatusIcon()} size={24} color="#FFFFFF" />
          )}

          <View style={styles.textContainer}>
            <Text style={styles.statusText}>{getStatusText()}</Text>
            {!syncState.syncInProgress && (
              <Text style={styles.subText}>
                Last sync: {formatLastSyncTime()}
              </Text>
            )}
          </View>
        </View>

        <View style={styles.rightContent}>
          {hasError && (
            <TouchableOpacity
              style={styles.syncButton}
              onPress={(e) => {
                e.stopPropagation();
                handleSyncNow();
              }}
            >
              <Icon name="refresh" size={20} color="#FFFFFF" />
              <Text style={styles.syncButtonText}>Retry</Text>
            </TouchableOpacity>
          )}

          {isOnline && !syncState.syncInProgress && syncState.pendingCount > 0 && !hasError && (
            <TouchableOpacity
              style={styles.syncButton}
              onPress={(e) => {
                e.stopPropagation();
                handleSyncNow();
              }}
            >
              <Icon name="sync" size={20} color="#FFFFFF" />
              <Text style={styles.syncButtonText}>Sync Now</Text>
            </TouchableOpacity>
          )}

          <TouchableOpacity
            style={styles.dismissButton}
            onPress={(e) => {
              e.stopPropagation();
              handleDismiss();
            }}
          >
            <Icon name="close" size={20} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
      </View>

      {syncState.syncInProgress && (
        <View style={styles.progressBarContainer}>
          <View
            style={[
              styles.progressBar,
              { width: `${syncProgress}%` },
            ]}
          />
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    paddingHorizontal: 16,
    paddingVertical: 12,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  leftContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  textContainer: {
    marginLeft: 12,
    flex: 1,
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  subText: {
    fontSize: 12,
    color: '#FFFFFF',
    opacity: 0.9,
  },
  rightContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
  },
  syncButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#FFFFFF',
    marginLeft: 4,
  },
  dismissButton: {
    padding: 4,
  },
  progressBarContainer: {
    height: 3,
    backgroundColor: 'rgba(255, 255, 255, 0.3)',
    borderRadius: 2,
    marginTop: 8,
    overflow: 'hidden',
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 2,
  },
});

export default OfflineIndicator;
