/**
 * Execution Progress Screen
 * Real-time monitoring of workflow execution progress
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { getExecutionById, getExecutionSteps, cancelExecution } from '../../services/workflowService';
import { WorkflowExecution, WorkflowStep } from '../../types/workflow';

type RouteType = RouteProp<
  { ExecutionProgress: { executionId: string } },
  'ExecutionProgress'
>;

export const ExecutionProgressScreen: React.FC = () => {
  const navigation = useNavigation();
  const route = useRoute<RouteType>();

  const { executionId } = route.params;

  const [execution, setExecution] = useState<WorkflowExecution | null>(null);
  const [steps, setSteps] = useState<WorkflowStep[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  // Polling interval for real-time updates
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  // Fetch execution data
  const fetchExecutionData = useCallback(async (refresh: boolean = false) => {
    try {
      if (refresh) {
        setIsRefreshing(true);
      }

      const [executionData, stepsData] = await Promise.all([
        getExecutionById(executionId),
        getExecutionSteps(executionId),
      ]);

      setExecution(executionData);
      setSteps(stepsData);

      setIsLoading(false);
      setIsRefreshing(false);

      // Stop polling if execution is complete
      if (executionData.status === 'completed' ||
          executionData.status === 'failed' ||
          executionData.status === 'cancelled') {
        if (pollingInterval) {
          clearInterval(pollingInterval);
          setPollingInterval(null);
        }
      }
    } catch (error: any) {
      setIsLoading(false);
      setIsRefreshing(false);
      console.error('Error fetching execution data:', error);
    }
  }, [executionId, pollingInterval]);

  // Start polling for running executions
  useEffect(() => {
    fetchExecutionData();

    const interval = setInterval(() => {
      if (execution?.status === 'running') {
        fetchExecutionData(true);
      }
    }, 3000); // Poll every 3 seconds

    setPollingInterval(interval);

    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [executionId]);

  // Handle cancel execution
  const handleCancel = async () => {
    if (isCancelling) return;

    setIsCancelling(true);
    try {
      await cancelExecution(executionId);
      // Refresh data
      await fetchExecutionData(true);
    } catch (error: any) {
      console.error('Error cancelling execution:', error);
    } finally {
      setIsCancelling(false);
    }
  };

  // Get status color
  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      running: '#2196F3',
      completed: '#4CAF50',
      failed: '#f44336',
      cancelled: '#FF9800',
      pending: '#757575',
    };
    return colors[status] || '#757575';
  };

  // Get step status icon
  const getStepIcon = (status?: string): string => {
    switch (status) {
      case 'completed':
        return 'checkmark-circle';
      case 'running':
        return 'time';
      case 'failed':
        return 'close-circle';
      case 'skipped':
        return 'remove-circle';
      default:
        return 'ellipse';
    }
  };

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
        <Text style={styles.loadingText}>Loading execution details...</Text>
      </View>
    );
  }

  if (!execution) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="alert-circle" size={60} color="#f44336" />
        <Text style={styles.errorText}>Execution not found</Text>
      </View>
    );
  }

  const isRunning = execution.status === 'running';
  const progressPercentage = execution.progress_percentage || 0;

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerContent}>
          <Text style={styles.workflowName}>{execution.workflow_name}</Text>
          <Text style={styles.executionId}>Execution ID: {execution.id}</Text>
        </View>

        <View style={[styles.statusBadge, { backgroundColor: getStatusColor(execution.status) }]}>
          <Ionicons
            name={isRunning ? 'time' : execution.status === 'completed' ? 'checkmark-circle' : 'close-circle'}
            size={20}
            color="#fff"
          />
          <Text style={styles.statusText}>{execution.status.toUpperCase()}</Text>
        </View>
      </View>

      {/* Progress Bar */}
      {isRunning && (
        <View style={styles.progressSection}>
          <View style={styles.progressHeader}>
            <Text style={styles.progressLabel}>Execution Progress</Text>
            <Text style={styles.progressPercentage}>{progressPercentage.toFixed(0)}%</Text>
          </View>
          <View style={styles.progressBarContainer}>
            <View style={[styles.progressBar, { width: `${progressPercentage}%` }]} />
          </View>
          <Text style={styles.progressDetail}>
            Step {execution.current_step || 0} of {execution.total_steps || 0}
          </Text>
        </View>
      )}

      {/* Actions */}
      {isRunning && (
        <View style={styles.actionsSection}>
          <TouchableOpacity
            style={[styles.actionButton, styles.cancelButton]}
            onPress={handleCancel}
            disabled={isCancelling}
          >
            {isCancelling ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <>
                <Ionicons name="close-circle" size={20} color="#fff" />
                <Text style={styles.cancelButtonText}>Cancel Execution</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* Content */}
      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={() => fetchExecutionData(true)}
            colors={['#2196F3']}
          />
        }
      >
        {/* Execution Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Execution Details</Text>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Started At</Text>
            <Text style={styles.infoValue}>
              {new Date(execution.started_at).toLocaleString()}
            </Text>
          </View>

          {execution.completed_at && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Completed At</Text>
              <Text style={styles.infoValue}>
                {new Date(execution.completed_at).toLocaleString()}
              </Text>
            </View>
          )}

          {execution.duration_seconds && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Duration</Text>
              <Text style={styles.infoValue}>{execution.duration_seconds}s</Text>
            </View>
          )}

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Triggered By</Text>
            <Text style={styles.infoValue}>{execution.triggered_by}</Text>
          </View>
        </View>

        {/* Error Message */}
        {execution.error_message && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Error</Text>
            <View style={styles.errorBox}>
              <Ionicons name="alert-circle" size={20} color="#f44336" />
              <Text style={styles.errorText}>{execution.error_message}</Text>
            </View>
          </View>
        )}

        {/* Steps */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Execution Steps</Text>

          {steps.length === 0 ? (
            <Text style={styles.emptyText}>No steps recorded yet</Text>
          ) : (
            steps.map((step, index) => (
              <View key={step.id} style={styles.stepCard}>
                <View style={styles.stepHeader}>
                  <View style={styles.stepNumber}>
                    <Text style={styles.stepNumberText}>{index + 1}</Text>
                  </View>
                  <View style={styles.stepInfo}>
                    <Text style={styles.stepName}>{step.name}</Text>
                    <Text style={styles.stepType}>{step.type}</Text>
                  </View>
                  <Ionicons
                    name={getStepIcon(step.status)}
                    size={24}
                    color={getStatusColor(step.status || 'pending')}
                  />
                </View>

                {step.started_at && (
                  <Text style={styles.stepTime}>
                    Started: {new Date(step.started_at).toLocaleString()}
                  </Text>
                )}

                {step.completed_at && (
                  <Text style={styles.stepTime}>
                    Completed: {new Date(step.completed_at).toLocaleString()}
                  </Text>
                )}

                {step.duration_ms && (
                  <Text style={styles.stepDuration}>
                    Duration: {(step.duration_ms / 1000).toFixed(2)}s
                  </Text>
                )}

                {step.error && (
                  <View style={styles.stepErrorBox}>
                    <Text style={styles.stepErrorText}>{step.error}</Text>
                  </View>
                )}
              </View>
            ))
          )}
        </View>
      </ScrollView>
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
    marginBottom: 12,
  },
  workflowName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  executionId: {
    fontSize: 14,
    color: '#666',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  statusText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 6,
  },
  progressSection: {
    backgroundColor: '#fff',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  progressPercentage: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2196F3',
  },
  progressBarContainer: {
    height: 8,
    backgroundColor: '#E0E0E0',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 8,
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#2196F3',
  },
  progressDetail: {
    fontSize: 14,
    color: '#666',
  },
  actionsSection: {
    backgroundColor: '#fff',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    paddingVertical: 14,
  },
  cancelButton: {
    backgroundColor: '#f44336',
  },
  cancelButtonText: {
    color: '#fff',
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
  errorBox: {
    flexDirection: 'row',
    backgroundColor: '#FFEBEE',
    padding: 12,
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#f44336',
  },
  emptyText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    paddingVertical: 20,
  },
  stepCard: {
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  stepHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#2196F3',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  stepNumberText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  stepInfo: {
    flex: 1,
  },
  stepName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 2,
  },
  stepType: {
    fontSize: 12,
    color: '#999',
  },
  stepTime: {
    fontSize: 12,
    color: '#666',
    marginTop: 4,
    marginLeft: 44,
  },
  stepDuration: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
    marginLeft: 44,
  },
  stepErrorBox: {
    marginTop: 8,
    marginLeft: 44,
    backgroundColor: '#FFEBEE',
    padding: 8,
    borderRadius: 4,
    borderLeftWidth: 3,
    borderLeftColor: '#f44336',
  },
  stepErrorText: {
    fontSize: 12,
    color: '#c62828',
  },
});

export default ExecutionProgressScreen;
