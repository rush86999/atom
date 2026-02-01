/**
 * Workflow Detail Screen
 * Shows detailed information about a workflow with actions to trigger, edit, view history
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useNavigation, useRoute, RouteProp, NavigationProp } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { getWorkflowById, getWorkflowExecutions, triggerWorkflow } from '../../services/workflowService';
import { Workflow, WorkflowExecution } from '../../types/workflow';

type NavigationType = {
  WorkflowDetail: { workflowId: string };
  WorkflowTrigger: { workflowId: string; workflowName: string };
  ExecutionProgress: { executionId: string };
  WorkflowLogs: { executionId: string };
};

type RouteType = RouteProp<NavigationType, 'WorkflowDetail'>;

export const WorkflowDetailScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp<NavigationType>>();
  const route = useRoute<RouteType>();

  const { workflowId } = route.params;

  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [recentExecutions, setRecentExecutions] = useState<WorkflowExecution[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);

  // Fetch workflow details
  const fetchWorkflowDetails = useCallback(async (refresh: boolean = false) => {
    try {
      if (refresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }

      const [workflowData, executionsData] = await Promise.all([
        getWorkflowById(workflowId),
        getWorkflowExecutions(workflowId, 5),
      ]);

      setWorkflow(workflowData);
      setRecentExecutions(executionsData);

      setIsLoading(false);
      setIsRefreshing(false);
    } catch (error: any) {
      setIsLoading(false);
      setIsRefreshing(false);
      Alert.alert('Error', error.message || 'Failed to load workflow details');
    }
  }, [workflowId]);

  // Initial load
  useEffect(() => {
    fetchWorkflowDetails();
  }, [fetchWorkflowDetails]);

  // Handle trigger workflow
  const handleTriggerWorkflow = () => {
    if (!workflow) return;

    navigation.navigate('WorkflowTrigger', {
      workflowId: workflow.id,
      workflowName: workflow.name,
    });
  };

  // Handle quick trigger (with default parameters)
  const handleQuickTrigger = async () => {
    if (!workflow) return;

    setIsTriggering(true);
    try {
      const result = await triggerWorkflow({
        workflow_id: workflow.id,
        synchronous: false,
      });

      Alert.alert(
        'Workflow Triggered',
        `Execution started successfully!\nExecution ID: ${result.execution_id}`,
        [
          {
            text: 'View Progress',
            onPress: () => navigation.navigate('ExecutionProgress', {
              executionId: result.execution_id,
            }),
          },
          { text: 'OK' },
        ]
      );

      // Refresh executions
      fetchWorkflowDetails(true);
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to trigger workflow');
    } finally {
      setIsTriggering(false);
    }
  };

  // Navigate to execution logs
  const handleViewLogs = (executionId: string) => {
    navigation.navigate('WorkflowLogs', { executionId });
  };

  // Get status color
  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      running: '#2196F3',
      completed: '#4CAF50',
      failed: '#f44336',
      cancelled: '#FF9800',
    };
    return colors[status] || '#757575';
  };

  // Render loading state
  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
        <Text style={styles.loadingText}>Loading workflow details...</Text>
      </View>
    );
  }

  if (!workflow) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="document-outline" size={60} color="#ccc" />
        <Text style={styles.errorText}>Workflow not found</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerContent}>
          <Text style={styles.workflowName}>{workflow.name}</Text>
          <Text style={styles.workflowDescription}>{workflow.description}</Text>

          <View style={styles.headerStats}>
            <View style={styles.statBadge}>
              <Ionicons name="play-circle" size={16} color="#4CAF50" />
              <Text style={styles.statText}>{workflow.execution_count} executions</Text>
            </View>
            <View style={styles.statBadge}>
              <Ionicons name="checkmark-circle" size={16} color="#4CAF50" />
              <Text style={styles.statText}>{workflow.success_rate.toFixed(1)}% success</Text>
            </View>
          </View>

          <View style={styles.tagsRow}>
            <View style={[styles.categoryBadge, { backgroundColor: getCategoryColor(workflow.category) }]}>
              <Text style={styles.categoryBadgeText}>{workflow.category}</Text>
            </View>
            <View style={[styles.statusBadge, { backgroundColor: getStatusColor(workflow.status) }]}>
              <Text style={styles.statusBadgeText}>{workflow.status}</Text>
            </View>
          </View>
        </View>
      </View>

      {/* Actions */}
      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={[styles.actionButton, styles.primaryButton]}
          onPress={handleQuickTrigger}
          disabled={isTriggering}
        >
          {isTriggering ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Ionicons name="flash" size={20} color="#fff" />
              <Text style={styles.primaryButtonText}>Run Now</Text>
            </>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.secondaryButton]}
          onPress={handleTriggerWorkflow}
        >
          <Ionicons name="settings" size={20} color="#2196F3" />
          <Text style={styles.secondaryButtonText}>Configure</Text>
        </TouchableOpacity>
      </View>

      {/* Content */}
      <ScrollView
        style={styles.content}
        refreshControl={{
          refreshing: isRefreshing,
          onRefresh: () => fetchWorkflowDetails(true),
          colors: ['#2196F3'],
        }}
      >
        {/* Info Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Information</Text>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Created</Text>
            <Text style={styles.infoValue}>
              {new Date(workflow.created_at).toLocaleDateString()}
            </Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Last Modified</Text>
            <Text style={styles.infoValue}>
              {new Date(workflow.updated_at).toLocaleDateString()}
            </Text>
          </View>
          {workflow.last_execution && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Last Execution</Text>
              <Text style={styles.infoValue}>
                {new Date(workflow.last_execution).toLocaleString()}
              </Text>
            </View>
          )}
        </View>

        {/* Tags */}
        {workflow.tags && workflow.tags.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Tags</Text>
            <View style={styles.tagsContainer}>
              {workflow.tags.map((tag, index) => (
                <View key={index} style={styles.tag}>
                  <Text style={styles.tagText}>{tag}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Recent Executions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent Executions</Text>
          {recentExecutions.length === 0 ? (
            <Text style={styles.emptyText}>No executions yet</Text>
          ) : (
            recentExecutions.map((execution) => (
              <TouchableOpacity
                key={execution.id}
                style={styles.executionCard}
                onPress={() => handleViewLogs(execution.id)}
              >
                <View style={styles.executionHeader}>
                  <View style={styles.executionStatus}>
                    <Ionicons
                      name={
                        execution.status === 'completed'
                          ? 'checkmark-circle'
                          : execution.status === 'running'
                          ? 'time'
                          : 'close-circle'
                      }
                      size={18}
                      color={getStatusColor(execution.status)}
                    />
                    <Text style={[styles.executionStatusText, { color: getStatusColor(execution.status) }]}>
                      {execution.status}
                    </Text>
                  </View>
                  <Text style={styles.executionDate}>
                    {new Date(execution.started_at).toLocaleString()}
                  </Text>
                </View>

                {execution.duration_seconds && (
                  <Text style={styles.executionDuration}>
                    Duration: {execution.duration_seconds}s
                  </Text>
                )}

                {execution.error_message && (
                  <Text style={styles.executionError} numberOfLines={2}>
                    {execution.error_message}
                  </Text>
                )}
              </TouchableOpacity>
            ))
          )}
        </View>
      </ScrollView>
    </View>
  );
};

const getCategoryColor = (category: string): string => {
  const colors: Record<string, string> = {
    automation: '#4CAF50',
    integration: '#2196F3',
    'data processing': '#FF9800',
    'ai/ml': '#9C27B0',
    monitoring: '#F44336',
    business: '#00BCD4',
  };
  return colors[category.toLowerCase()] || '#757575';
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
  errorText: {
    fontSize: 16,
    color: '#999',
    marginTop: 12,
  },
  header: {
    backgroundColor: '#fff',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerContent: {
    paddingBottom: 16,
  },
  workflowName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  workflowDescription: {
    fontSize: 16,
    color: '#666',
    lineHeight: 22,
    marginBottom: 16,
  },
  headerStats: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  statBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
  },
  statText: {
    fontSize: 13,
    color: '#666',
    marginLeft: 4,
    fontWeight: '500',
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  categoryBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
  },
  categoryBadgeText: {
    fontSize: 13,
    color: '#fff',
    fontWeight: '600',
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  statusBadgeText: {
    fontSize: 13,
    color: '#fff',
    fontWeight: '600',
  },
  actionsRow: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 12,
  },
  primaryButton: {
    backgroundColor: '#2196F3',
  },
  primaryButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  secondaryButton: {
    backgroundColor: '#fff',
    borderWidth: 2,
    borderColor: '#2196F3',
  },
  secondaryButtonText: {
    color: '#2196F3',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
  content: {
    flex: 1,
  },
  section: {
    backgroundColor: '#fff',
    padding: 16,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 12,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  infoLabel: {
    fontSize: 15,
    color: '#666',
  },
  infoValue: {
    fontSize: 15,
    color: '#333',
    fontWeight: '500',
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  tag: {
    backgroundColor: '#E3F2FD',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    marginRight: 8,
    marginBottom: 8,
  },
  tagText: {
    fontSize: 13,
    color: '#2196F3',
    fontWeight: '500',
  },
  emptyText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    paddingVertical: 20,
  },
  executionCard: {
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  executionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  executionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  executionStatusText: {
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 6,
  },
  executionDate: {
    fontSize: 12,
    color: '#999',
  },
  executionDuration: {
    fontSize: 13,
    color: '#666',
    marginBottom: 4,
  },
  executionError: {
    fontSize: 12,
    color: '#f44336',
  },
});

export default WorkflowDetailScreen;
