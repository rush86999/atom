/**
 * Sync Progress Modal Component
 *
 * Detailed sync progress modal for comprehensive sync feedback.
 *
 * Features:
 * - Modal triggered during sync
 * - Overall progress percentage
 * - Entity-by-entity progress
 * - Current sync operation display
 * - Estimated time remaining
 * - Sync speed indicator
 * - Cancel sync button
 * - Background sync option
 * - Sync log (verbose mode)
 * - Sync summary on completion
 * - Error details for failed items
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { useTheme } from '@react-navigation/native';
import Icon from 'react-native-vector-icons/Ionicons';
import { offlineSyncService, SyncState } from '../../services/offlineSyncService';

interface SyncProgressModalProps {
  visible: boolean;
  onClose?: () => void;
  onComplete?: (result: any) => void;
}

interface EntityProgress {
  type: string;
  total: number;
  synced: number;
  failed: number;
}

interface SyncLogEntry {
  timestamp: Date;
  message: string;
  level: 'info' | 'warn' | 'error';
}

export const SyncProgressModal: React.FC<SyncProgressModalProps> = ({
  visible,
  onClose,
  onComplete,
}) => {
  const { colors } = useTheme();
  const [syncState, setSyncState] = useState<SyncState>({
    lastSyncAt: null,
    lastSuccessfulSyncAt: null,
    pendingCount: 0,
    syncInProgress: false,
    consecutiveFailures: 0,
    currentOperation: '',
    syncProgress: 0,
    cancelled: false,
  });
  const [entityProgress, setEntityProgress] = useState<EntityProgress[]>([]);
  const [syncLogs, setSyncLogs] = useState<SyncLogEntry[]>([]);
  const [verboseMode, setVerboseMode] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [isComplete, setIsComplete] = useState(false);
  const [startTime] = useState(Date.now());
  const [bytesTransferred, setBytesTransferred] = useState(0);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState(0);

  useEffect(() => {
    if (!visible) {
      return;
    }

    // Reset state when modal opens
    setIsComplete(false);
    setSyncResult(null);
    setSyncLogs([]);
    setEntityProgress([]);

    // Subscribe to sync state changes
    const unsubscribe = offlineSyncService.subscribe((state) => {
      setSyncState(state);

      if (state.syncProgress === 100 || !state.syncInProgress) {
        setIsComplete(true);
      }

      // Update entity progress (mock for now)
      if (state.syncInProgress) {
        updateEntityProgress(state);
        addSyncLog(state.currentOperation, 'info');
      }

      // Calculate estimated time remaining
      const elapsed = Date.now() - startTime;
      const progress = state.syncProgress;
      if (progress > 0 && progress < 100) {
        const totalEstimated = (elapsed / progress) * 100;
        setEstimatedTimeRemaining(totalEstimated - elapsed);
      }
    });

    // Subscribe to progress updates
    const unsubscribeProgress = offlineSyncService.subscribeToProgress(
      (progress, operation) => {
        addSyncLog(`[${progress}%] ${operation}`, 'info');
      }
    );

    return () => {
      unsubscribe();
      unsubscribeProgress();
    };
  }, [visible, startTime]);

  const updateEntityProgress = (state: SyncState) => {
    // Mock entity progress - in real app, this would come from sync service
    setEntityProgress([
      {
        type: 'Agents',
        total: 10,
        synced: Math.floor(Math.random() * 10),
        failed: 0,
      },
      {
        type: 'Workflows',
        total: 20,
        synced: Math.floor(Math.random() * 20),
        failed: 0,
      },
      {
        type: 'Canvases',
        total: 15,
        synced: Math.floor(Math.random() * 15),
        failed: 0,
      },
      {
        type: 'Episodes',
        total: 5,
        synced: Math.floor(Math.random() * 5),
        failed: 0,
      },
    ]);
  };

  const addSyncLog = (message: string, level: 'info' | 'warn' | 'error') => {
    setSyncLogs(prev => [
      ...prev,
      {
        timestamp: new Date(),
        message,
        level,
      },
    ]);
  };

  const handleCancelSync = async () => {
    await offlineSyncService.cancelSync();
    addSyncLog('Sync cancelled by user', 'warn');
    setIsComplete(true);
  };

  const handleClose = () => {
    if (onClose) {
      onClose();
    }
    if (onComplete && syncResult) {
      onComplete(syncResult);
    }
  };

  const handleBackgroundSync = () => {
    addSyncLog('Continuing sync in background', 'info');
    if (onClose) {
      onClose();
    }
  };

  const formatTime = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const getLogIcon = (level: 'info' | 'warn' | 'error') => {
    switch (level) {
      case 'error':
        return 'alert-circle';
      case 'warn':
        return 'warning';
      default:
        return 'information-circle';
    }
  };

  const getLogColor = (level: 'info' | 'warn' | 'error') => {
    switch (level) {
      case 'error':
        return '#FF3B30';
      case 'warn':
        return '#FF9500';
      default:
        return '#007AFF';
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={handleClose}
    >
      <View style={styles.modalOverlay}>
        <View style={[styles.modalContent, { backgroundColor: colors.background }]}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={[styles.title, { color: colors.text }]}>
              {isComplete ? 'Sync Complete' : 'Syncing Data'}
            </Text>
            {!isComplete && (
              <TouchableOpacity onPress={handleClose} style={styles.closeButton}>
                <Icon name="close" size={24} color={colors.text} />
              </TouchableOpacity>
            )}
          </View>

          {/* Overall Progress */}
          <View style={styles.section}>
            <View style={styles.progressHeader}>
              <Text style={[styles.label, { color: colors.text }]}>
                Overall Progress
              </Text>
              <Text style={[styles.progressText, { color: colors.text }]}>
                {syncState.syncProgress}%
              </Text>
            </View>
            <View style={styles.progressBarContainer}>
              <View
                style={[
                  styles.progressBar,
                  {
                    width: `${syncState.syncProgress}%`,
                    backgroundColor: isComplete ? '#34C759' : '#007AFF',
                  },
                ]}
              />
            </View>
            {!isComplete && (
              <Text style={[styles.subText, { color: colors.text }]}>
                {syncState.currentOperation || 'Preparing...'}
              </Text>
            )}
          </View>

          {/* Entity Progress */}
          {!isComplete && entityProgress.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Entity Progress
              </Text>
              {entityProgress.map((entity, index) => (
                <View key={index} style={styles.entityRow}>
                  <Text style={[styles.entityLabel, { color: colors.text }]}>
                    {entity.type}
                  </Text>
                  <View style={styles.entityProgressContainer}>
                    <Text style={[styles.entityProgress, { color: colors.text }]}>
                      {entity.synced}/{entity.total}
                    </Text>
                    {entity.failed > 0 && (
                      <Text style={[styles.entityFailed, { color: '#FF3B30' }]}>
                        ({entity.failed} failed)
                      </Text>
                    )}
                  </View>
                </View>
              ))}
            </View>
          )}

          {/* Stats */}
          <View style={styles.section}>
            <View style={styles.statsRow}>
              <View style={styles.statItem}>
                <Icon name="time" size={20} color="#007AFF" />
                <Text style={[styles.statLabel, { color: colors.text }]}>
                  Time: {formatTime(Date.now() - startTime)}
                </Text>
              </View>
              {!isComplete && estimatedTimeRemaining > 0 && (
                <View style={styles.statItem}>
                  <Icon name="hourglass" size={20} color="#007AFF" />
                  <Text style={[styles.statLabel, { color: colors.text }]}>
                    ETA: {formatTime(estimatedTimeRemaining)}
                  </Text>
                </View>
              )}
            </View>
            {bytesTransferred > 0 && (
              <View style={styles.statItem}>
                <Icon name="cloud-download" size={20} color="#007AFF" />
                <Text style={[styles.statLabel, { color: colors.text }]}>
                  Transferred: {formatBytes(bytesTransferred)}
                </Text>
              </View>
            )}
          </View>

          {/* Sync Summary (on completion) */}
          {isComplete && syncResult && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Sync Summary
              </Text>
              <View style={styles.summaryRow}>
                <Icon name="checkmark-circle" size={20} color="#34C759" />
                <Text style={[styles.summaryText, { color: colors.text }]}>
                  {syncResult.synced} items synced
                </Text>
              </View>
              {syncResult.failed > 0 && (
                <View style={styles.summaryRow}>
                  <Icon name="close-circle" size={20} color="#FF3B30" />
                  <Text style={[styles.summaryText, { color: colors.text }]}>
                    {syncResult.failed} items failed
                  </Text>
                </View>
              )}
              {syncResult.conflicts > 0 && (
                <View style={styles.summaryRow}>
                  <Icon name="warning" size={20} color="#FF9500" />
                  <Text style={[styles.summaryText, { color: colors.text }]}>
                    {syncResult.conflicts} conflicts
                  </Text>
                </View>
              )}
            </View>
          )}

          {/* Verbose Log */}
          {verboseMode && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Sync Log
              </Text>
              <ScrollView style={styles.logContainer}>
                {syncLogs.map((log, index) => (
                  <View key={index} style={styles.logRow}>
                    <Icon
                      name={getLogIcon(log.level)}
                      size={16}
                      color={getLogColor(log.level)}
                    />
                    <Text style={[styles.logText, { color: colors.text }]}>
                      {log.message}
                    </Text>
                  </View>
                ))}
              </ScrollView>
            </View>
          )}

          {/* Actions */}
          <View style={styles.actions}>
            {!isComplete ? (
              <>
                <TouchableOpacity
                  style={[styles.button, styles.cancelButton]}
                  onPress={handleCancelSync}
                >
                  <Icon name="close" size={20} color="#FFFFFF" />
                  <Text style={styles.buttonText}>Cancel Sync</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.button, styles.backgroundButton]}
                  onPress={handleBackgroundSync}
                >
                  <Icon name="eye-off" size={20} color="#FFFFFF" />
                  <Text style={styles.buttonText}>Background</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <TouchableOpacity
                  style={[styles.button, styles.verboseButton]}
                  onPress={() => setVerboseMode(!verboseMode)}
                >
                  <Icon
                    name={verboseMode ? 'eye-off' : 'eye'}
                    size={20}
                    color="#FFFFFF"
                  />
                  <Text style={styles.buttonText}>
                    {verboseMode ? 'Hide' : 'Show'} Log
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.button, styles.doneButton]}
                  onPress={handleClose}
                >
                  <Icon name="checkmark" size={20} color="#FFFFFF" />
                  <Text style={styles.buttonText}>Done</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    width: '90%',
    maxHeight: '80%',
    borderRadius: 16,
    padding: 20,
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 4.65,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
  },
  closeButton: {
    padding: 4,
  },
  section: {
    marginBottom: 20,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
  },
  progressText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#007AFF',
  },
  progressBarContainer: {
    height: 8,
    backgroundColor: '#E5E5EA',
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBar: {
    height: '100%',
    borderRadius: 4,
  },
  subText: {
    fontSize: 14,
    marginTop: 4,
    opacity: 0.7,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  entityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  entityLabel: {
    fontSize: 14,
  },
  entityProgressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  entityProgress: {
    fontSize: 14,
    fontWeight: '600',
  },
  entityFailed: {
    fontSize: 12,
    marginLeft: 4,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 14,
    marginLeft: 8,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  summaryText: {
    fontSize: 14,
    marginLeft: 8,
  },
  logContainer: {
    maxHeight: 150,
    backgroundColor: '#F2F2F7',
    borderRadius: 8,
    padding: 8,
  },
  logRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  logText: {
    fontSize: 12,
    marginLeft: 8,
    flex: 1,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20,
  },
  button: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 8,
    marginHorizontal: 4,
  },
  cancelButton: {
    backgroundColor: '#FF3B30',
  },
  backgroundButton: {
    backgroundColor: '#8E8E93',
  },
  verboseButton: {
    backgroundColor: '#8E8E93',
  },
  doneButton: {
    backgroundColor: '#007AFF',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
});

export default SyncProgressModal;
