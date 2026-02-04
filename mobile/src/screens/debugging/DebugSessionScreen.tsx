/**
 * Mobile Debug Session Screen
 *
 * Main debugging interface for mobile devices with touch-optimized controls.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Play, Pause, SkipForward, ArrowRight, ArrowDown } from 'lucide-react-native';
import axios from 'axios';

interface DebugSession {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  current_step: number;
  current_node_id: string;
  variables: Record<string, any>;
  created_at: string;
}

interface DebugSessionScreenProps {
  route: {
    params: {
      workflowId: string;
      workflowName: string;
    };
  };
}

export const DebugSessionScreen: React.FC<DebugSessionScreenProps> = ({ route }) => {
  const { workflowId, workflowName } = route.params;
  const insets = useSafeAreaInsets();

  const [session, setSession] = useState<DebugSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    startDebugSession();
  }, []);

  const startDebugSession = async () => {
    try {
      setLoading(true);
      const response = await axios.post('/api/workflows/${workflowId}/debug/sessions', {
        stop_on_entry: false,
        stop_on_exceptions: true,
        stop_on_error: true,
      });

      setSession(response.data);
    } catch (error) {
      Alert.alert('Error', 'Failed to start debug session');
    } finally {
      setLoading(false);
    }
  };

  const executeStep = async (action: 'step_over' | 'step_into' | 'step_out' | 'continue' | 'pause') => {
    if (!session) return;

    try {
      setActionLoading(action);
      const response = await axios.post('/api/workflows/debug/step', {
        session_id: session.id,
        action: action,
      });

      setSession(prev => ({ ...prev, ...response.data }));
    } catch (error) {
      Alert.alert('Error', `Failed to ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  const StepButton = ({
    action,
    icon: Icon,
    label,
  }: {
    action: string;
    icon: any;
    label: string;
  }) => (
    <TouchableOpacity
      style={[styles.stepButton, actionLoading === action && styles.stepButtonDisabled]}
      onPress={() => executeStep(action as any)}
      disabled={actionLoading === action || !session}
    >
      <Icon size={24} color="#fff" />
      <Text style={styles.stepButtonLabel}>{label}</Text>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <Text style={styles.loadingText}>Starting debug session...</Text>
      </View>
    );
  }

  if (!session) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <Text style={styles.errorText}>Failed to start debug session</Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Debug Session</Text>
        <Text style={styles.workflowName}>{workflowName}</Text>
        <View style={styles.statusBadge}>
          <Text style={styles.statusText}>{session.status}</Text>
        </View>
      </View>

      {/* Session Info */}
      <View style={styles.sessionInfo}>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Step:</Text>
          <Text style={styles.infoValue}>{session.current_step}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Node:</Text>
          <Text style={styles.infoValue}>{session.current_node_id || 'N/A'}</Text>
        </View>
      </View>

      {/* Variables Preview */}
      <View style={styles.variablesSection}>
        <Text style={styles.sectionTitle}>Variables</Text>
        <ScrollView style={styles.variablesList} horizontal>
          {Object.entries(session.variables || {}).slice(0, 10).map(([key, value]) => (
            <View key={key} style={styles.variableChip}>
              <Text style={styles.variableName}>{key}:</Text>
              <Text style={styles.variableValue}>{JSON.stringify(value)}</Text>
            </View>
          ))}
        </ScrollView>
      </View>

      {/* Step Controls */}
      <View style={styles.controlsSection}>
        <Text style={styles.sectionTitle}>Controls</Text>
        <View style={styles.stepButtons}>
          <StepButton action="step_over" icon={SkipForward} label="Over" />
          <StepButton action="step_into" icon={ArrowRight} label="Into" />
          <StepButton action="step_out" icon={ArrowDown} label="Out" />
          <StepButton action="continue" icon={Play} label="Run" />
          <StepButton action="pause" icon={Pause} label="Pause" />
        </View>
      </View>

      {/* Actions */}
      <View style={styles.actionsSection}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => {/* Navigate to breakpoints */}}
        >
          <Text style={styles.actionButtonText}>Manage Breakpoints</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => {/* Navigate to traces */}}
        >
          <Text style={styles.actionButtonText}>View Execution Traces</Text>
        </TouchableOpacity>
      </View>
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
  workflowName: {
    fontSize: 16,
    color: '#6c757d',
    marginBottom: 10,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#28a745',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  sessionInfo: {
    flexDirection: 'row',
    padding: 15,
    backgroundColor: '#fff',
    marginTop: 10,
    marginHorizontal: 15,
    borderRadius: 10,
  },
  infoRow: {
    flex: 1,
  },
  infoLabel: {
    fontSize: 12,
    color: '#6c757d',
    marginBottom: 2,
  },
  infoValue: {
    fontSize: 16,
    fontWeight: '600',
  },
  variablesSection: {
    marginTop: 15,
    paddingHorizontal: 15,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 10,
  },
  variablesList: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 10,
  },
  variableChip: {
    backgroundColor: '#f1f3f5',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    marginRight: 10,
  },
  variableName: {
    fontSize: 12,
    fontWeight: '600',
    color: '#495057',
  },
  variableValue: {
    fontSize: 11,
    color: '#868e96',
  },
  controlsSection: {
    marginTop: 20,
    paddingHorizontal: 15,
  },
  stepButtons: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  stepButton: {
    width: 70,
    height: 80,
    backgroundColor: '#007bff',
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 5,
  },
  stepButtonDisabled: {
    opacity: 0.5,
  },
  stepButtonLabel: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  actionsSection: {
    marginTop: 20,
    paddingHorizontal: 15,
    gap: 10,
  },
  actionButton: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#dee2e6',
  },
  actionButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007bff',
    textAlign: 'center',
  },
  loadingText: {
    fontSize: 16,
    color: '#6c757d',
    textAlign: 'center',
  },
  errorText: {
    fontSize: 16,
    color: '#dc3545',
    textAlign: 'center',
  },
});

export default DebugSessionScreen;
