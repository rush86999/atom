/**
 * Mobile Execution Traces Screen
 *
 * View workflow execution traces on mobile with filtering and search.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChevronRight, ChevronDown, Search, CheckCircle, XCircle, Clock } from 'lucide-react-native';
import axios from 'axios';

interface ExecutionTrace {
  trace_id: string;
  step_number: number;
  node_id: string;
  node_type: string;
  status: 'started' | 'completed' | 'failed';
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error_message: string;
  duration_ms: number;
  started_at: string;
  completed_at: string;
}

interface TracesScreenProps {
  route: {
    params: {
      executionId: string;
      workflowId: string;
    };
  };
}

export const TracesScreen: React.FC<TracesScreenProps> = ({ route }) => {
  const { executionId, workflowId } = route.params;
  const insets = useSafeAreaInsets();

  const [traces, setTraces] = useState<ExecutionTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<'all' | 'started' | 'completed' | 'failed'>('all');

  useEffect(() => {
    fetchTraces();
  }, [statusFilter]);

  const fetchTraces = async () => {
    try {
      setLoading(true);
      const params = statusFilter !== 'all' ? { status: statusFilter } : {};
      const response = await axios.get(`/api/workflows/executions/${executionId}/traces`, { params });
      setTraces(response.data);
    } catch (error) {
      console.error('Failed to fetch traces:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (traceId: string) => {
    setExpandedTraces(prev => {
      const newSet = new Set(prev);
      if (newSet.has(traceId)) {
        newSet.delete(traceId);
      } else {
        newSet.add(traceId);
      }
      return newSet;
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} color="#28a745" />;
      case 'failed':
        return <XCircle size={16} color="#dc3545" />;
      case 'started':
        return <Clock size={16} color="#ffc107" />;
      default:
        return <Clock size={16} color="#6c757d" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#d4edda';
      case 'failed':
        return '#f8d7da';
      case 'started':
        return '#fff3cd';
      default:
        return '#e9ecef';
    }
  };

  const filterOptions = [
    { key: 'all', label: 'All' },
    { key: 'started', label: 'Started' },
    { key: 'completed', label: 'Completed' },
    { key: 'failed', label: 'Failed' },
  ];

  const renderTrace = ({ item }: { item: ExecutionTrace }) => {
    const isExpanded = expandedTraces.has(item.trace_id);

    return (
      <View style={styles.traceItem}>
        <TouchableOpacity
          style={styles.traceHeader}
          onPress={() => toggleExpand(item.trace_id)}
        >
          <View style={styles.traceHeaderLeft}>
            {isExpanded ? <ChevronDown size={20} color="#6c757d" /> : <ChevronRight size={20} color="#6c757d" />}
            {getStatusIcon(item.status)}
            <View>
              <Text style={styles.stepNumber}>Step {item.step_number}</Text>
              <Text style={styles.nodeId}>{item.node_id}</Text>
            </View>
          </View>

          <View style={styles.traceHeaderRight}>
            <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
              <Text style={styles.statusText}>{item.status}</Text>
            </View>
            <Text style={styles.duration}>{item.duration_ms}ms</Text>
          </View>
        </TouchableOpacity>

        {isExpanded && (
          <View style={styles.traceDetails}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Type:</Text>
              <Text style={styles.detailValue}>{item.node_type}</Text>
            </View>

            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Started:</Text>
              <Text style={styles.detailValue}>{new Date(item.started_at).toLocaleString()}</Text>
            </View>

            {item.completed_at && (
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Completed:</Text>
                <Text style={styles.detailValue}>{new Date(item.completed_at).toLocaleString()}</Text>
              </View>
            )}

            {item.input_data && Object.keys(item.input_data).length > 0 && (
              <View style={styles.dataSection}>
                <Text style={styles.dataSectionTitle}>Input Data:</Text>
                <Text style={styles.dataContent}>{JSON.stringify(item.input_data, null, 2)}</Text>
              </View>
            )}

            {item.output_data && Object.keys(item.output_data).length > 0 && (
              <View style={styles.dataSection}>
                <Text style={styles.dataSectionTitle}>Output Data:</Text>
                <Text style={styles.dataContent}>{JSON.stringify(item.output_data, null, 2)}</Text>
              </View>
            )}

            {item.error_message && (
              <View style={styles.errorSection}>
                <Text style={styles.errorTitle}>Error:</Text>
                <Text style={styles.errorMessage}>{item.error_message}</Text>
              </View>
            )}
          </View>
        )}
      </View>
    );
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Execution Traces</Text>
        <Text style={styles.executionId}>{executionId}</Text>
      </View>

      {/* Filter Buttons */}
      <View style={styles.filterContainer}>
        {filterOptions.map(option => (
          <TouchableOpacity
            key={option.key}
            style={[
              styles.filterButton,
              statusFilter === option.key && styles.filterButtonActive,
            ]}
            onPress={() => setStatusFilter(option.key as any)}
          >
            <Text
              style={[
                styles.filterButtonText,
                statusFilter === option.key && styles.filterButtonTextActive,
              ]}
            >
              {option.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Traces List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007bff" />
          <Text style={styles.loadingText}>Loading traces...</Text>
        </View>
      ) : traces.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No traces found</Text>
        </View>
      ) : (
        <FlatList
          data={traces}
          renderItem={renderTrace}
          keyExtractor={(item) => item.trace_id}
          contentContainerStyle={styles.list}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e9ecef',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  executionId: {
    fontSize: 12,
    color: '#6c757d',
  },
  filterContainer: {
    flexDirection: 'row',
    padding: 15,
    gap: 10,
    flexWrap: 'wrap',
  },
  filterButton: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#dee2e6',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
  },
  filterButtonActive: {
    backgroundColor: '#007bff',
    borderColor: '#007bff',
  },
  filterButtonText: {
    color: '#495057',
    fontSize: 12,
    fontWeight: '600',
  },
  filterButtonTextActive: {
    color: '#fff',
  },
  list: {
    padding: 15,
  },
  traceItem: {
    backgroundColor: '#fff',
    borderRadius: 10,
    marginBottom: 10,
    overflow: 'hidden',
  },
  traceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
  },
  traceHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stepNumber: {
    fontSize: 14,
    fontWeight: '600',
  },
  nodeId: {
    fontSize: 12,
    color: '#6c757d',
  },
  traceHeaderRight: {
    alignItems: 'flex-end',
    gap: 6,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  duration: {
    fontSize: 12,
    color: '#6c757d',
  },
  traceDetails: {
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#e9ecef',
    gap: 8,
  },
  detailRow: {
    flexDirection: 'row',
  },
  detailLabel: {
    fontSize: 12,
    color: '#6c757d',
    width: 80,
  },
  detailValue: {
    fontSize: 12,
    color: '#212529',
    flex: 1,
  },
  dataSection: {
    marginTop: 8,
    padding: 10,
    backgroundColor: '#f8f9fa',
    borderRadius: 6,
  },
  dataSectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  dataContent: {
    fontSize: 11,
    color: '#495057',
    fontFamily: 'monospace',
  },
  errorSection: {
    marginTop: 8,
    padding: 10,
    backgroundColor: '#f8d7da',
    borderRadius: 6,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#721c24',
    marginBottom: 4,
  },
  errorMessage: {
    fontSize: 12,
    color: '#721c24',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 10,
  },
  loadingText: {
    fontSize: 16,
    color: '#6c757d',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    color: '#6c757d',
  },
});

export default TracesScreen;
