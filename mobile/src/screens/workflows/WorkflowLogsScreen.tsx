/**
 * Workflow Logs Screen
 * Displays detailed logs for a workflow execution
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { getExecutionLogs, getExecutionById } from '../../services/workflowService';
import { ExecutionLog, WorkflowExecution } from '../../types/workflow';

type RouteType = RouteProp<
  { WorkflowLogs: { executionId: string } },
  'WorkflowLogs'
>;

type LogLevel = 'all' | 'info' | 'warning' | 'error' | 'debug';

export const WorkflowLogsScreen: React.FC = () => {
  const navigation = useNavigation();
  const route = useRoute<RouteType>();

  const { executionId } = route.params;

  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [execution, setExecution] = useState<WorkflowExecution | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filterLevel, setFilterLevel] = useState<LogLevel>('all');

  // Fetch logs
  const fetchLogs = useCallback(async () => {
    try {
      setIsLoading(true);

      const [logsData, executionData] = await Promise.all([
        getExecutionLogs(executionId),
        getExecutionById(executionId),
      ]);

      setLogs(logsData);
      setExecution(executionData);

      // Set header title
      navigation.setOptions({
        title: `Logs - ${executionData.workflow_name}`,
      });

      setIsLoading(false);
    } catch (error: any) {
      setIsLoading(false);
      console.error('Error fetching logs:', error);
    }
  }, [executionId, navigation]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Filter logs by level
  const filteredLogs = logs.filter((log) => {
    if (filterLevel === 'all') return true;
    return log.level === filterLevel;
  });

  // Get log level color
  const getLogLevelColor = (level: string): string => {
    const colors: Record<string, string> = {
      info: '#2196F3',
      warning: '#FF9800',
      error: '#f44336',
      debug: '#757575',
    };
    return colors[level] || '#757575';
  };

  // Get log level icon
  const getLogLevelIcon = (level: string): string => {
    const icons: Record<string, string> = {
      info: 'information-circle',
      warning: 'warning',
      error: 'alert-circle',
      debug: 'bug',
    };
    return icons[level] || 'ellipse';
  };

  // Render log item
  const renderLogItem = ({ item, index }: { item: ExecutionLog; index: number }) => (
    <View style={[styles.logItem, { borderLeftColor: getLogLevelColor(item.level) }]}>
      <View style={styles.logHeader}>
        <View style={styles.logLevelBadge}>
          <Ionicons
            name={getLogLevelIcon(item.level) as any}
            size={16}
            color={getLogLevelColor(item.level)}
          />
          <Text style={[styles.logLevelText, { color: getLogLevelColor(item.level) }]}>
            {item.level.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.logTimestamp}>
          {new Date(item.timestamp).toLocaleTimeString()}
        </Text>
      </View>

      <Text style={styles.logMessage}>{item.message}</Text>

      {item.step_id && (
        <Text style={styles.logStepId}>Step: {item.step_id}</Text>
      )}

      {item.metadata && Object.keys(item.metadata).length > 0 && (
        <View style={styles.logMetadata}>
          <Text style={styles.metadataTitle}>Metadata:</Text>
          {Object.entries(item.metadata).map(([key, value]) => (
            <Text key={key} style={styles.metadataItem}>
              {key}: {JSON.stringify(value)}
            </Text>
          ))}
        </View>
      )}
    </View>
  );

  // Render filter chip
  const renderFilterChip = (level: LogLevel) => (
    <TouchableOpacity
      key={level}
      style={[styles.filterChip, filterLevel === level && styles.filterChipActive]}
      onPress={() => setFilterLevel(level)}
    >
      <Text
        style={[
          styles.filterChipText,
          filterLevel === level && styles.filterChipTextActive,
        ]}
      >
        {level.charAt(0).toUpperCase() + level.slice(1)}
      </Text>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
        <Text style={styles.loadingText}>Loading logs...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Execution Summary */}
      {execution && (
        <View style={styles.summaryCard}>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Status:</Text>
            <View style={[
              styles.statusBadge,
              { backgroundColor: getLogLevelColor(execution.status) }
            ]}>
              <Text style={styles.statusText}>{execution.status}</Text>
            </View>
          </View>
          {execution.duration_seconds && (
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Duration:</Text>
              <Text style={styles.summaryValue}>{execution.duration_seconds}s</Text>
            </View>
          )}
        </View>
      )}

      {/* Filter Chips */}
      <View style={styles.filterContainer}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={['all', 'info', 'warning', 'error', 'debug'] as LogLevel[]}
          keyExtractor={(item) => item}
          renderItem={({ item }) => renderFilterChip(item)}
          contentContainerStyle={styles.filterList}
        />
      </View>

      {/* Logs Count */}
      <View style={styles.countBar}>
        <Text style={styles.countText}>
          Showing {filteredLogs.length} of {logs.length} logs
        </Text>
      </View>

      {/* Logs List */}
      {filteredLogs.length === 0 ? (
        <View style={styles.centerContainer}>
          <Ionicons name="document-outline" size={60} color="#ccc" />
          <Text style={styles.emptyText}>
            {filterLevel === 'all' ? 'No logs available' : `No ${filterLevel} logs`}
          </Text>
        </View>
      ) : (
        <FlatList
          data={filteredLogs}
          keyExtractor={(item) => item.id}
          renderItem={renderLogItem}
          contentContainerStyle={styles.logsList}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
  },
  emptyText: {
    fontSize: 16,
    color: '#999',
    marginTop: 12,
  },
  summaryCard: {
    backgroundColor: '#fff',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  summaryLabel: {
    fontSize: 15,
    color: '#666',
    marginRight: 8,
  },
  summaryValue: {
    fontSize: 15,
    color: '#333',
    fontWeight: '500',
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  filterContainer: {
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  filterList: {
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#f5f5f5',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  filterChipActive: {
    backgroundColor: '#2196F3',
    borderColor: '#2196F3',
  },
  filterChipText: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  filterChipTextActive: {
    color: '#fff',
  },
  countBar: {
    backgroundColor: '#fff',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  countText: {
    fontSize: 13,
    color: '#666',
  },
  logsList: {
    padding: 16,
  },
  separator: {
    height: 8,
  },
  logItem: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 12,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  logHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  logLevelBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  logLevelText: {
    fontSize: 12,
    fontWeight: '600',
    marginLeft: 4,
  },
  logTimestamp: {
    fontSize: 12,
    color: '#999',
  },
  logMessage: {
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
    marginBottom: 4,
  },
  logStepId: {
    fontSize: 12,
    color: '#666',
    fontStyle: 'italic',
  },
  logMetadata: {
    marginTop: 8,
    backgroundColor: '#f9f9f9',
    padding: 8,
    borderRadius: 4,
  },
  metadataTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#666',
    marginBottom: 4,
  },
  metadataItem: {
    fontSize: 11,
    color: '#666',
    fontFamily: 'monospace',
    marginBottom: 2,
  },
});

export default WorkflowLogsScreen;
