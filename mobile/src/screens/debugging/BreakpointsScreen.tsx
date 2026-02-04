/**
 * Mobile Breakpoints Management Screen
 *
 * Touch-optimized interface for managing workflow breakpoints on mobile.
 */

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
  TextInput,
  Modal,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Plus, Trash2, X, Check } from 'lucide-react-native';
import axios from 'axios';

interface Breakpoint {
  id: string;
  node_id: string;
  condition: string | null;
  hit_count: number;
  hit_limit: number | null;
  is_disabled: boolean;
}

interface BreakpointsScreenProps {
  route: {
    params: {
      workflowId: string;
    };
  };
}

export const BreakpointsScreen: React.FC<BreakpointsScreenProps> = ({ route }) => {
  const { workflowId } = route.params;
  const insets = useSafeAreaInsets();

  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newNodeId, setNewNodeId] = useState('');
  const [newCondition, setNewCondition] = useState('');

  useEffect(() => {
    fetchBreakpoints();
  }, []);

  const fetchBreakpoints = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/workflows/${workflowId}/debug/breakpoints`);
      setBreakpoints(response.data);
    } catch (error) {
      Alert.alert('Error', 'Failed to fetch breakpoints');
    } finally {
      setLoading(false);
    }
  };

  const addBreakpoint = async () => {
    if (!newNodeId) {
      Alert.alert('Error', 'Please enter a node ID');
      return;
    }

    try {
      await axios.post(`/api/workflows/${workflowId}/debug/breakpoints`, {
        node_id: newNodeId,
        condition: newCondition || null,
      });

      setShowAddModal(false);
      setNewNodeId('');
      setNewCondition('');
      fetchBreakpoints();
    } catch (error) {
      Alert.alert('Error', 'Failed to add breakpoint');
    }
  };

  const removeBreakpoint = async (breakpointId: string) => {
    Alert.alert(
      'Remove Breakpoint',
      'Are you sure you want to remove this breakpoint?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await axios.delete(`/api/workflows/debug/breakpoints/${breakpointId}`);
              fetchBreakpoints();
            } catch (error) {
              Alert.alert('Error', 'Failed to remove breakpoint');
            }
          },
        },
      ]
    );
  };

  const toggleBreakpoint = async (breakpointId: string) => {
    try {
      await axios.put(`/api/workflows/debug/breakpoints/${breakpointId}/toggle`);
      fetchBreakpoints();
    } catch (error) {
      Alert.alert('Error', 'Failed to toggle breakpoint');
    }
  };

  const renderBreakpoint = ({ item }: { item: Breakpoint }) => (
    <View style={[styles.breakpointItem, item.is_disabled && styles.breakpointDisabled]}>
      <View style={styles.breakpointHeader}>
        <Text style={styles.nodeId}>{item.node_id}</Text>
        <TouchableOpacity
          style={[styles.toggleButton, item.is_disabled && styles.toggleButtonOff]}
          onPress={() => toggleBreakpoint(item.id)}
        >
          <Text style={styles.toggleButtonText}>{item.is_disabled ? 'Disabled' : 'Enabled'}</Text>
        </TouchableOpacity>
      </View>

      {item.condition && (
        <Text style={styles.condition}>Condition: {item.condition}</Text>
      )}

      <View style={styles.breakpointFooter}>
        <Text style={styles.hitCount}>Hit count: {item.hit_count}</Text>
        {item.hit_limit && (
          <Text style={styles.hitLimit}>Limit: {item.hit_limit}</Text>
        )}
      </View>

      <TouchableOpacity
        style={styles.removeButton}
        onPress={() => removeBreakpoint(item.id)}
      >
        <Trash2 size={18} color="#dc3545" />
        <Text style={styles.removeButtonText}>Remove</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Breakpoints</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => setShowAddModal(true)}
        >
          <Plus size={20} color="#fff" />
          <Text style={styles.addButtonText}>Add Breakpoint</Text>
        </TouchableOpacity>
      </View>

      {/* Breakpoints List */}
      {loading ? (
        <Text style={styles.loadingText}>Loading breakpoints...</Text>
      ) : breakpoints.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No breakpoints set</Text>
          <Text style={styles.emptySubtext}>Tap "Add Breakpoint" to get started</Text>
        </View>
      ) : (
        <FlatList
          data={breakpoints}
          renderItem={renderBreakpoint}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
        />
      )}

      {/* Add Breakpoint Modal */}
      <Modal
        visible={showAddModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowAddModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add Breakpoint</Text>
              <TouchableOpacity onPress={() => setShowAddModal(false)}>
                <X size={24} color="#495057" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Node ID</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., node-action-1"
              value={newNodeId}
              onChangeText={setNewNodeId}
              autoCapitalize="none"
            />

            <Text style={styles.inputLabel}>Condition (Optional)</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., count > 5"
              value={newCondition}
              onChangeText={setNewCondition}
              autoCapitalize="none"
            />

            <TouchableOpacity style={styles.confirmButton} onPress={addBreakpoint}>
              <Check size={20} color="#fff" />
              <Text style={styles.confirmButtonText}>Add Breakpoint</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e9ecef',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  addButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#28a745',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    gap: 5,
  },
  addButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  list: {
    padding: 15,
  },
  breakpointItem: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: '#007bff',
  },
  breakpointDisabled: {
    borderColor: '#dee2e6',
    opacity: 0.6,
  },
  breakpointHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  nodeId: {
    fontSize: 16,
    fontWeight: '600',
  },
  toggleButton: {
    backgroundColor: '#28a745',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  toggleButtonOff: {
    backgroundColor: '#6c757d',
  },
  toggleButtonText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  condition: {
    fontSize: 14,
    color: '#495057',
    marginBottom: 8,
  },
  breakpointFooter: {
    flexDirection: 'row',
    gap: 15,
    marginTop: 8,
  },
  hitCount: {
    fontSize: 12,
    color: '#6c757d',
  },
  hitLimit: {
    fontSize: 12,
    color: '#6c757d',
  },
  removeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 10,
  },
  removeButtonText: {
    color: '#dc3545',
    fontWeight: '600',
  },
  loadingText: {
    fontSize: 16,
    color: '#6c757d',
    textAlign: 'center',
    marginTop: 20,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 5,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#6c757d',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 20,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 5,
    marginTop: 10,
  },
  input: {
    backgroundColor: '#f8f9fa',
    borderWidth: 1,
    borderColor: '#dee2e6',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  confirmButton: {
    flexDirection: 'row',
    backgroundColor: '#007bff',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 14,
    borderRadius: 8,
    marginTop: 20,
    gap: 8,
  },
  confirmButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 16,
  },
});

export default BreakpointsScreen;
