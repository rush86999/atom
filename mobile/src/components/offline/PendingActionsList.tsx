/**
 * Pending Actions List Component
 *
 * List component showing all pending offline actions with management options.
 *
 * Features:
 * - List of all pending actions
 * - Action type icons
 * - Timestamp display
 * - Retry failed actions
 * - Delete pending actions
 * - Prioritize actions
 * - Select multiple actions
 * - Batch operations (retry, delete)
 * - Sort by type, time, priority
 * - Filter by status
 * - Empty state
 * - Pull-to-refresh
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { useTheme } from '@react-navigation/native';
import Icon from 'react-native-vector-icons/Ionicons';
import { offlineSyncService, OfflineAction, OfflineActionStatus } from '../../services/offlineSyncService';
import { useRefreshControl } from '../hooks/useRefreshControl';

interface PendingActionsListProps {
  style?: any;
  onActionPress?: (action: OfflineAction) => void;
}

type SortOption = 'time' | 'priority' | 'type';
type FilterOption = 'all' | 'pending' | 'failed';

export const PendingActionsList: React.FC<PendingActionsListProps> = ({
  style,
  onActionPress,
}) => {
  const { colors } = useTheme();
  const [actions, setActions] = useState<OfflineAction[]>([]);
  const [selectedActions, setSelectedActions] = useState<Set<string>>(new Set());
  const [sortBy, setSortBy] = useState<SortOption>('time');
  const [filterBy, setFilterBy] = useState<FilterOption>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [isSelectMode, setIsSelectMode] = useState(false);

  const { refreshControl, refreshing } = useRefreshControl({
    onRefresh: useCallback(() => loadActions(), []),
  });

  useEffect(() => {
    loadActions();

    // Subscribe to sync state changes
    const unsubscribe = offlineSyncService.subscribe(() => {
      loadActions();
    });

    return unsubscribe;
  }, []);

  const loadActions = async () => {
    setIsLoading(true);
    try {
      // Get pending actions from sync service
      const queue = await (offlineSyncService as any).getQueue();
      const pending = queue.filter((a: OfflineAction) => a.status === 'pending' || a.status === 'failed');
      setActions(pending);
    } catch (error) {
      console.error('Failed to load pending actions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getActionIcon = (type: string) => {
    switch (type) {
      case 'agent_message':
        return 'chatbubble';
      case 'workflow_trigger':
        return 'git-network';
      case 'form_submit':
        return 'document-text';
      case 'feedback':
        return 'star';
      case 'canvas_update':
        return 'color-palette';
      case 'device_command':
        return 'hardware-chip';
      case 'agent_sync':
        return 'person';
      case 'workflow_sync':
        return 'git-branch';
      case 'canvas_sync':
        return 'layers';
      case 'episode_sync':
        return 'albums';
      default:
        return 'document';
    }
  };

  const getActionColor = (type: string) => {
    switch (type) {
      case 'agent_message':
        return '#007AFF';
      case 'workflow_trigger':
        return '#5856D6';
      case 'form_submit':
        return '#34C759';
      case 'feedback':
        return '#FF9500';
      case 'canvas_update':
        return '#AF52DE';
      default:
        return '#8E8E93';
    }
  };

  const formatTimestamp = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - new Date(date).getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const handleRetryAction = async (action: OfflineAction) => {
    try {
      // Reset sync attempts
      action.syncAttempts = 0;
      action.status = 'pending';
      await loadActions();
      // Trigger sync
      offlineSyncService.triggerSync();
    } catch (error) {
      Alert.alert('Error', 'Failed to retry action');
    }
  };

  const handleDeleteAction = async (actionId: string) => {
    Alert.alert(
      'Delete Action',
      'Are you sure you want to delete this action?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              // Remove from queue
              const queue = await (offlineSyncService as any).getQueue();
              const filtered = queue.filter((a: OfflineAction) => a.id !== actionId);
              await (offlineSyncService as any).saveQueue(filtered);
              await loadActions();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete action');
            }
          },
        },
      ]
    );
  };

  const handlePrioritizeAction = async (action: OfflineAction) => {
    try {
      // Increase priority
      action.priority = Math.min(action.priority + 2, 10);
      await loadActions();
    } catch (error) {
      Alert.alert('Error', 'Failed to prioritize action');
    }
  };

  const handleSelectAction = (actionId: string) => {
    const newSelected = new Set(selectedActions);
    if (newSelected.has(actionId)) {
      newSelected.delete(actionId);
    } else {
      newSelected.add(actionId);
    }
    setSelectedActions(newSelected);
  };

  const handleBatchRetry = async () => {
    try {
      for (const actionId of selectedActions) {
        const action = actions.find(a => a.id === actionId);
        if (action) {
          action.syncAttempts = 0;
          action.status = 'pending';
        }
      }
      await loadActions();
      offlineSyncService.triggerSync();
      setSelectedActions(new Set());
      setIsSelectMode(false);
    } catch (error) {
      Alert.alert('Error', 'Failed to retry actions');
    }
  };

  const handleBatchDelete = async () => {
    Alert.alert(
      'Delete Actions',
      `Are you sure you want to delete ${selectedActions.size} actions?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const queue = await (offlineSyncService as any).getQueue();
              const filtered = queue.filter((a: OfflineAction) => !selectedActions.has(a.id));
              await (offlineSyncService as any).saveQueue(filtered);
              await loadActions();
              setSelectedActions(new Set());
              setIsSelectMode(false);
            } catch (error) {
              Alert.alert('Error', 'Failed to delete actions');
            }
          },
        },
      ]
    );
  };

  const sortActions = (actionsToSort: OfflineAction[]) => {
    const sorted = [...actionsToSort];
    switch (sortBy) {
      case 'time':
        return sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      case 'priority':
        return sorted.sort((a, b) => b.priority - a.priority);
      case 'type':
        return sorted.sort((a, b) => a.type.localeCompare(b.type));
      default:
        return sorted;
    }
  };

  const filterActions = (actionsToFilter: OfflineAction[]) => {
    switch (filterBy) {
      case 'pending':
        return actionsToFilter.filter(a => a.status === 'pending');
      case 'failed':
        return actionsToFilter.filter(a => a.status === 'failed');
      default:
        return actionsToFilter;
    }
  };

  const filteredAndSortedActions = sortActions(filterActions(actions));

  const renderAction = ({ item }: { item: OfflineAction }) => {
    const isSelected = selectedActions.has(item.id);
    const isFailed = item.status === 'failed';

    return (
      <TouchableOpacity
        style={[
          styles.actionItem,
          { backgroundColor: colors.card, borderColor: colors.border },
          isFailed && styles.failedItem,
        ]}
        onPress={() => {
          if (isSelectMode) {
            handleSelectAction(item.id);
          } else if (onActionPress) {
            onActionPress(item);
          }
        }}
        onLongPress={() => {
          setIsSelectMode(true);
          handleSelectAction(item.id);
        }}
      >
        {isSelectMode && (
          <TouchableOpacity
            style={styles.checkbox}
            onPress={() => handleSelectAction(item.id)}
          >
            <Icon
              name={isSelected ? 'checkbox' : 'square-outline'}
              size={24}
              color={isSelected ? '#007AFF' : colors.text}
            />
          </TouchableOpacity>
        )}

        <View style={[styles.iconContainer, { backgroundColor: getActionColor(item.type) + '20' }]}>
          <Icon name={getActionIcon(item.type)} size={24} color={getActionColor(item.type)} />
        </View>

        <View style={styles.actionContent}>
          <View style={styles.actionHeader}>
            <Text style={[styles.actionType, { color: colors.text }]}>
              {item.type.replace(/_/g, ' ').toUpperCase()}
            </Text>
            <Text style={[styles.timestamp, { color: colors.text }]}>
              {formatTimestamp(item.createdAt)}
            </Text>
          </View>

          <Text style={[styles.priorityLabel, { color: colors.text }]} numberOfLines={1}>
            Priority: {item.priority}/10
          </Text>

          {item.syncAttempts > 0 && (
            <Text style={[styles.retryLabel, { color: '#FF9500' }]}>
              Retry {item.syncAttempts}/{5}
            </Text>
          )}

          {isFailed && item.lastSyncError && (
            <Text style={[styles.errorLabel, { color: '#FF3B30' }]} numberOfLines={1}>
              {item.lastSyncError}
            </Text>
          )}
        </View>

        {!isSelectMode && (
          <View style={styles.actionButtons}>
            {isFailed && (
              <TouchableOpacity
                style={styles.actionButton}
                onPress={() => handleRetryAction(item)}
              >
                <Icon name="refresh" size={20} color="#007AFF" />
              </TouchableOpacity>
            )}
            <TouchableOpacity
              style={styles.actionButton}
              onPress={() => handlePrioritizeAction(item)}
            >
              <Icon name="arrow-up" size={20} color="#FF9500" />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.actionButton}
              onPress={() => handleDeleteAction(item.id)}
            >
              <Icon name="trash" size={20} color="#FF3B30" />
            </TouchableOpacity>
          </View>
        )}
      </TouchableOpacity>
    );
  };

  const renderHeader = () => (
    <View style={[styles.header, { borderColor: colors.border }]}>
      <View style={styles.sortFilterRow}>
        <Text style={[styles.headerTitle, { color: colors.text }]}>
          {filteredAndSortedActions.length} Actions
        </Text>

        <View style={styles.headerButtons}>
          <TouchableOpacity
            style={styles.headerButton}
            onPress={() => setIsSelectMode(!isSelectMode)}
          >
            <Icon name="checkboxes-outline" size={24} color={colors.text} />
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.sortFilterRow}>
        <TouchableOpacity
          style={[styles.filterChip, sortBy === 'time' && styles.activeFilter]}
          onPress={() => setSortBy('time')}
        >
          <Text style={[styles.filterText, { color: colors.text }]}>
            Time
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterChip, sortBy === 'priority' && styles.activeFilter]}
          onPress={() => setSortBy('priority')}
        >
          <Text style={[styles.filterText, { color: colors.text }]}>
            Priority
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterChip, sortBy === 'type' && styles.activeFilter]}
          onPress={() => setSortBy('type')}
        >
          <Text style={[styles.filterText, { color: colors.text }]}>
            Type
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.filterChip, filterBy === 'all' && styles.activeFilter]}
          onPress={() => setFilterBy('all')}
        >
          <Text style={[styles.filterText, { color: colors.text }]}>
            All
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterChip, filterBy === 'pending' && styles.activeFilter]}
          onPress={() => setFilterBy('pending')}
        >
          <Text style={[styles.filterText, { color: colors.text }]}>
            Pending
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterChip, filterBy === 'failed' && styles.activeFilter]}
          onPress={() => setFilterBy('failed')}
        >
          <Text style={[styles.filterText, { color: colors.text }]}>
            Failed
          </Text>
        </TouchableOpacity>
      </View>

      {isSelectMode && selectedActions.size > 0 && (
        <View style={styles.batchActions}>
          <Text style={[styles.selectedCount, { color: colors.text }]}>
            {selectedActions.size} selected
          </Text>
          <TouchableOpacity
            style={styles.batchButton}
            onPress={handleBatchRetry}
          >
            <Icon name="refresh" size={18} color="#FFFFFF" />
            <Text style={styles.batchButtonText}>Retry All</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.batchButton, styles.deleteButton]}
            onPress={handleBatchDelete}
          >
            <Icon name="trash" size={18} color="#FFFFFF" />
            <Text style={styles.batchButtonText}>Delete All</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );

  const renderEmptyState = () => (
    <View style={styles.emptyState}>
      <Icon name="checkmark-circle" size={64} color="#34C759" />
      <Text style={[styles.emptyTitle, { color: colors.text }]}>
        All Caught Up!
      </Text>
      <Text style={[styles.emptyText, { color: colors.text }]}>
        No pending actions to sync
      </Text>
    </View>
  );

  return (
    <View style={[styles.container, style]}>
      <FlatList
        data={filteredAndSortedActions}
        renderItem={renderAction}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={!isLoading ? renderEmptyState : null}
        refreshControl={refreshControl}
        contentContainerStyle={filteredAndSortedActions.length === 0 ? styles.emptyList : undefined}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    padding: 16,
    borderBottomWidth: 1,
  },
  sortFilterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    flexWrap: 'wrap',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    flex: 1,
  },
  headerButtons: {
    flexDirection: 'row',
  },
  headerButton: {
    padding: 8,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#E5E5EA',
    marginRight: 8,
    marginBottom: 8,
  },
  activeFilter: {
    backgroundColor: '#007AFF',
  },
  filterText: {
    fontSize: 12,
    fontWeight: '600',
  },
  batchActions: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  selectedCount: {
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  batchButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginLeft: 8,
  },
  deleteButton: {
    backgroundColor: '#FF3B30',
  },
  batchButtonText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4,
  },
  actionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
  },
  failedItem: {
    backgroundColor: '#FFE5E5',
  },
  checkbox: {
    marginRight: 12,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  actionContent: {
    flex: 1,
  },
  actionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  actionType: {
    fontSize: 14,
    fontWeight: '600',
  },
  timestamp: {
    fontSize: 12,
    opacity: 0.6,
  },
  priorityLabel: {
    fontSize: 12,
    opacity: 0.8,
    marginBottom: 2,
  },
  retryLabel: {
    fontSize: 11,
    marginBottom: 2,
  },
  errorLabel: {
    fontSize: 11,
    marginBottom: 2,
  },
  actionButtons: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  actionButton: {
    padding: 8,
  },
  emptyList: {
    flex: 1,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    marginTop: 8,
    opacity: 0.6,
  },
});

export default PendingActionsList;
