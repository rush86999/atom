/**
 * Workflow Trigger Screen
 * Configure and trigger a workflow with parameters
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { triggerWorkflow } from '../../services/workflowService';
import { WorkflowTriggerRequest, WorkflowTriggerResponse } from '../../types/workflow';

type RouteType = RouteProp<
  { WorkflowTrigger: { workflowId: string; workflowName: string } },
  'WorkflowTrigger'
>;

export const WorkflowTriggerScreen: React.FC = () => {
  const navigation = useNavigation();
  const route = useRoute<RouteType>();

  const { workflowId, workflowName } = route.params;

  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [synchronous, setSynchronous] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);

  // Handle trigger workflow
  const handleTrigger = async () => {
    setIsTriggering(true);
    try {
      const request: WorkflowTriggerRequest = {
        workflow_id: workflowId,
        parameters: Object.keys(parameters).length > 0 ? parameters : undefined,
        synchronous,
      };

      const response: WorkflowTriggerResponse = await triggerWorkflow(request);

      Alert.alert(
        'Success',
        `Workflow "${workflowName}" triggered successfully!\n\nExecution ID: ${response.execution_id}\nStatus: ${response.status}`,
        [
          {
            text: 'OK',
            onPress: () => navigation.goBack(),
          },
        ]
      );
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to trigger workflow');
    } finally {
      setIsTriggering(false);
    }
  };

  // Add a parameter
  const addParameter = () => {
    const key = `param_${Object.keys(parameters).length + 1}`;
    setParameters({ ...parameters, [key]: '' });
  };

  // Remove a parameter
  const removeParameter = (key: string) => {
    const newParams = { ...parameters };
    delete newParams[key];
    setParameters(newParams);
  };

  // Update parameter
  const updateParameter = (key: string, value: any) => {
    setParameters({ ...parameters, [key]: value });
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Trigger Workflow</Text>
        <Text style={styles.subtitle}>{workflowName}</Text>
      </View>

      <ScrollView style={styles.content}>
        {/* Parameters Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Parameters</Text>
            <TouchableOpacity onPress={addParameter} style={styles.addButton}>
              <Ionicons name="add-circle" size={24} color="#2196F3" />
            </TouchableOpacity>
          </View>

          {Object.keys(parameters).length === 0 ? (
            <Text style={styles.emptyText}>
              No parameters configured. Tap + to add parameters.
            </Text>
          ) : (
            Object.entries(parameters).map(([key, value]) => (
              <View key={key} style={styles.parameterRow}>
                <TextInput
                  style={styles.paramKeyInput}
                  value={key}
                  onChangeText={(newKey) => {
                    const newParams = { ...parameters };
                    delete newParams[key];
                    newParams[newKey] = value;
                    setParameters(newParams);
                  }}
                  placeholder="Parameter name"
                />
                <TextInput
                  style={styles.paramValueInput}
                  value={value}
                  onChangeText={(newValue) => updateParameter(key, newValue)}
                  placeholder="Value"
                />
                <TouchableOpacity
                  onPress={() => removeParameter(key)}
                  style={styles.removeButton}
                >
                  <Ionicons name="close-circle" size={24} color="#f44336" />
                </TouchableOpacity>
              </View>
            ))
          )}

          <Text style={styles.hintText}>
            Add key-value pairs to pass as parameters to the workflow execution.
          </Text>
        </View>

        {/* Execution Mode */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Execution Mode</Text>

          <TouchableOpacity
            style={[styles.modeOption, synchronous && styles.modeOptionActive]}
            onPress={() => setSynchronous(false)}
          >
            <Ionicons
              name={!synchronous ? 'radio-button-on' : 'radio-button-off'}
              size={24}
              color={!synchronous ? '#2196F3' : '#999'}
            />
            <View style={styles.modeContent}>
              <Text style={styles.modeTitle}>Asynchronous (Recommended)</Text>
              <Text style={styles.modeDescription}>
                Workflow runs in background. Get immediate response with execution ID.
              </Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.modeOption, synchronous && styles.modeOptionActive]}
            onPress={() => setSynchronous(true)}
          >
            <Ionicons
              name={synchronous ? 'radio-button-on' : 'radio-button-off'}
              size={24}
              color={synchronous ? '#2196F3' : '#999'}
            />
            <View style={styles.modeContent}>
              <Text style={styles.modeTitle}>Synchronous</Text>
              <Text style={styles.modeDescription}>
                Wait for workflow completion. Get full execution results.
              </Text>
            </View>
          </TouchableOpacity>
        </View>

        {/* Info Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Information</Text>
          <View style={styles.infoRow}>
            <Ionicons name="information-circle" size={20} color="#2196F3" />
            <Text style={styles.infoText}>
              {synchronous
                ? 'Synchronous mode may timeout for long-running workflows. Use asynchronous mode for workflows that take more than 30 seconds.'
                : 'You can track execution progress using the execution ID returned in the response.'}
            </Text>
          </View>
        </View>
      </ScrollView>

      {/* Trigger Button */}
      <View style={styles.footer}>
        <TouchableOpacity
          style={[styles.triggerButton, isTriggering && styles.triggerButtonDisabled]}
          onPress={handleTrigger}
          disabled={isTriggering}
        >
          {isTriggering ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Ionicons name="flash" size={20} color="#fff" />
              <Text style={styles.triggerButtonText}>Trigger Workflow</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#fff',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  section: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
  },
  addButton: {
    padding: 4,
  },
  emptyText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    paddingVertical: 16,
  },
  parameterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  paramKeyInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    backgroundColor: '#f9f9f9',
    marginRight: 8,
  },
  paramValueInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    backgroundColor: '#f9f9f9',
    marginRight: 8,
  },
  removeButton: {
    padding: 4,
  },
  hintText: {
    fontSize: 12,
    color: '#999',
    marginTop: 8,
    fontStyle: 'italic',
  },
  modeOption: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 12,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#e0e0e0',
    marginBottom: 12,
  },
  modeOptionActive: {
    borderColor: '#2196F3',
    backgroundColor: '#E3F2FD',
  },
  modeContent: {
    flex: 1,
    marginLeft: 12,
  },
  modeTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  modeDescription: {
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: '#666',
    marginLeft: 8,
    lineHeight: 20,
  },
  footer: {
    backgroundColor: '#fff',
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  triggerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2196F3',
    borderRadius: 12,
    paddingVertical: 16,
  },
  triggerButtonDisabled: {
    backgroundColor: '#BDBDBD',
  },
  triggerButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginLeft: 8,
  },
});

export default WorkflowTriggerScreen;
