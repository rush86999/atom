/**
 * Workflows List Screen
 * Displays a list of all workflows with search and filter capabilities
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, NavigationProp } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { getWorkflows, triggerWorkflow } from '../../services/workflowService';
import { Workflow, WorkflowFilters } from '../../types/workflow';
import { LoadingState } from '../../types/common';

type NavigationType = {
  WorkflowsList: any;
  WorkflowDetail: { workflowId: string };
  WorkflowTrigger: { workflowId: string; workflowName: string };
};

export const WorkflowsListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp<NavigationType>>();

  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [filteredWorkflows, setFilteredWorkflows] = useState<Workflow[]>([]);
  const [loadingState, setLoadingState] = useState<LoadingState>({
    isLoading: true,
    isRefreshing: false,
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Categories for filter
  const categories = ['All', 'Automation', 'Integration', 'Data Processing', 'AI/ML', 'Monitoring'];

  // Fetch workflows
  const fetchWorkflows = useCallback(async (isRefresh: boolean = false) => {
    try {
      setLoadingState((prev) => ({
        ...prev,
        isRefreshing: isRefresh,
        isLoading: !isRefresh && prev.isLoading,
      }));

      const filters: WorkflowFilters = {
        search: searchQuery || undefined,
        category: selectedCategory && selectedCategory !== 'All' ? selectedCategory.toLowerCase() : undefined,
        sort_by: 'name',
        sort_order: 'asc',
      };

      const { workflows: data } = await getWorkflows(filters);
      setWorkflows(data);
      setFilteredWorkflows(data);

      setLoadingState({ isLoading: false, isRefreshing: false });
    } catch (error: any) {
      setLoadingState({
        isLoading: false,
        isRefreshing: false,
        error: error.message,
      });
    }
  }, [searchQuery, selectedCategory]);

  // Initial load
  useEffect(() => {
    fetchWorkflows();
  }, []);

  // Handle search
  useEffect(() => {
    if (searchQuery || selectedCategory) {
      const filtered = workflows.filter((workflow) => {
        const matchesSearch =
          !searchQuery ||
          workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          workflow.description.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesCategory =
          !selectedCategory ||
          selectedCategory === 'All' ||
          workflow.category.toLowerCase() === selectedCategory.toLowerCase();

        return matchesSearch && matchesCategory;
      });
      setFilteredWorkflows(filtered);
    } else {
      setFilteredWorkflows(workflows);
    }
  }, [searchQuery, selectedCategory, workflows]);

  // Quick trigger workflow
  const handleQuickTrigger = async (workflowId: string, workflowName: string) => {
    navigation.navigate('WorkflowTrigger', { workflowId, workflowName });
  };

  // Navigate to workflow details
  const handleViewDetails = (workflowId: string) => {
    navigation.navigate('WorkflowDetail', { workflowId });
  };

  // Render workflow item
  const renderWorkflowItem = ({ item }: { item: Workflow }) => (
    <TouchableOpacity
      style={styles.workflowCard}
      onPress={() => handleViewDetails(item.id)}
    >
      <View style={styles.cardHeader}>
        <View style={styles.cardHeaderLeft}>
          <Text style={styles.workflowName}>{item.name}</Text>
          <Text style={styles.workflowDescription} numberOfLines={2}>
            {item.description}
          </Text>
        </View>
        <Ionicons
          name="chevron-forward"
          size={20}
          color="#999"
        />
      </View>

      <View style={styles.cardBody}>
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Ionicons name="play-circle" size={16} color="#4CAF50" />
            <Text style={styles.statText}>{item.execution_count} runs</Text>
          </View>
          <View style={styles.statItem}>
            <Ionicons
              name={item.success_rate >= 90 ? 'checkmark-circle' : 'warning'}
              size={16}
              color={item.success_rate >= 90 ? '#4CAF50' : '#FF9800'}
            />
            <Text style={styles.statText}>{item.success_rate.toFixed(1)}% success</Text>
          </View>
        </View>

        <View style={styles.tagsRow}>
          <View style={[styles.badge, { backgroundColor: getCategoryColor(item.category) }]}>
            <Text style={styles.badgeText}>{item.category}</Text>
          </View>
          <View style={[styles.badge, styles.statusBadge]}>
            <Text style={styles.badgeText}>{item.status}</Text>
          </View>
        </View>
      </View>

      <TouchableOpacity
        style={styles.triggerButton}
        onPress={(e) => {
          e.stopPropagation();
          handleQuickTrigger(item.id, item.name);
        }}
      >
        <Ionicons name="flash" size={18} color="#fff" />
        <Text style={styles.triggerButtonText}>Run</Text>
      </TouchableOpacity>
    </TouchableOpacity>
  );

  // Render category filter
  const renderCategoryFilter = () => (
    <View style={styles.categoryFilter}>
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={categories}
        keyExtractor={(item) => item}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[
              styles.categoryChip,
              selectedCategory === item && styles.categoryChipActive,
            ]}
            onPress={() => setSelectedCategory(item)}
          >
            <Text
              style={[
                styles.categoryChipText,
                selectedCategory === item && styles.categoryChipTextActive,
              ]}
            >
              {item}
            </Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );

  // Render list header
  const renderListHeader = () => (
    <View>
      <View style={styles.searchBar}>
        <Ionicons name="search" size={20} color="#999" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search workflows..."
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholderTextColor="#999"
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => setSearchQuery('')}>
            <Ionicons name="close-circle" size={20} color="#999" />
          </TouchableOpacity>
        )}
      </View>
      {renderCategoryFilter()}
    </View>
  );

  if (loadingState.isLoading && !loadingState.isRefreshing) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
        <Text style={styles.loadingText}>Loading workflows...</Text>
      </View>
    );
  }

  if (loadingState.error) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="alert-circle" size={60} color="#f44336" />
        <Text style={styles.errorTitle}>Error Loading Workflows</Text>
        <Text style={styles.errorMessage}>{loadingState.error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => fetchWorkflows()}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={filteredWorkflows}
        keyExtractor={(item) => item.id}
        renderItem={renderWorkflowItem}
        ListHeaderComponent={renderListHeader}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={loadingState.isRefreshing}
            onRefresh={() => fetchWorkflows(true)}
            colors={['#2196F3']}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="document-outline" size={60} color="#ccc" />
            <Text style={styles.emptyText}>
              {searchQuery || selectedCategory
                ? 'No workflows match your search'
                : 'No workflows yet'}
            </Text>
          </View>
        }
      />
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
    backgroundColor: '#fff',
  },
  listContent: {
    padding: 16,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#666',
  },
  errorTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 16,
    color: '#333',
  },
  errorMessage: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 20,
    backgroundColor: '#2196F3',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  searchInput: {
    flex: 1,
    marginLeft: 12,
    fontSize: 16,
    color: '#333',
  },
  categoryFilter: {
    marginBottom: 16,
  },
  categoryChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#fff',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  categoryChipActive: {
    backgroundColor: '#2196F3',
    borderColor: '#2196F3',
  },
  categoryChipText: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  categoryChipTextActive: {
    color: '#fff',
  },
  workflowCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  cardHeaderLeft: {
    flex: 1,
  },
  workflowName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  workflowDescription: {
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
  },
  cardBody: {
    marginBottom: 12,
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
  },
  statText: {
    fontSize: 13,
    color: '#666',
    marginLeft: 4,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
  },
  badgeText: {
    fontSize: 12,
    color: '#fff',
    fontWeight: '500',
  },
  statusBadge: {
    backgroundColor: '#E0E0E0',
  },
  triggerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#2196F3',
    borderRadius: 8,
    paddingVertical: 10,
  },
  triggerButtonText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
    marginLeft: 6,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 16,
    color: '#999',
    marginTop: 12,
  },
});

export default WorkflowsListScreen;
