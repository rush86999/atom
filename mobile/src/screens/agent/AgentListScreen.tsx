/**
 * Agent List Screen
 * Displays list of available agents with filtering and search
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Dimensions,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { Icon, MD3Colors } from 'react-native-paper';
import { agentService } from '../../services/agentService';
import { Agent, AgentMaturity, AgentFilters, AgentCapability } from '../../types/agent';

const { width } = Dimensions.get('window');

export function AgentListScreen() {
  const navigation = useNavigation();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [filteredAgents, setFilteredAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Filters
  const [maturityFilter, setMaturityFilter] = useState<AgentMaturity | 'ALL'>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'online' | 'offline'>('online');
  const [capabilityFilter, setCapabilityFilter] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'name' | 'created_at' | 'last_execution'>('name');
  const [showFilters, setShowFilters] = useState(false);

  /**
   * Load agents
   */
  useEffect(() => {
    loadAgents();
  }, []);

  /**
   * Apply filters
   */
  useEffect(() => {
    applyFilters();
  }, [agents, searchQuery, maturityFilter, statusFilter, capabilityFilter, sortBy]);

  /**
   * Load agents from API
   */
  const loadAgents = async () => {
    try {
      const filters: AgentFilters = {
        maturity: maturityFilter !== 'ALL' ? maturityFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        capability: capabilityFilter || undefined,
        sort_by: sortBy,
        sort_order: 'asc',
      };

      const response = await agentService.getAgents(filters);
      if (response.success && response.data) {
        setAgents(response.data);
      } else {
        Alert.alert('Error', response.error || 'Failed to load agents');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to load agents');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Refresh agents
   */
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadAgents();
    setIsRefreshing(false);
  };

  /**
   * Apply filters and search
   */
  const applyFilters = () => {
    let filtered = [...agents];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (agent) =>
          agent.name.toLowerCase().includes(query) ||
          agent.description.toLowerCase().includes(query) ||
          agent.capabilities.some((cap) => cap.name.toLowerCase().includes(query))
      );
    }

    // Maturity filter
    if (maturityFilter !== 'ALL') {
      filtered = filtered.filter((agent) => agent.maturity_level === maturityFilter);
    }

    // Status filter
    if (statusFilter !== 'ALL') {
      filtered = filtered.filter((agent) => agent.status === statusFilter);
    }

    // Capability filter
    if (capabilityFilter) {
      filtered = filtered.filter((agent) =>
        agent.capabilities.some((cap) => cap.name === capabilityFilter && cap.enabled)
      );
    }

    // Sort
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'created_at':
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case 'last_execution':
          if (!a.last_execution_at && !b.last_execution_at) return 0;
          if (!a.last_execution_at) return 1;
          if (!b.last_execution_at) return -1;
          return new Date(b.last_execution_at).getTime() - new Date(a.last_execution_at).getTime();
        default:
          return 0;
      }
    });

    setFilteredAgents(filtered);
  };

  /**
   * Get unique capabilities from all agents
   */
  const getAllCapabilities = (): string[] => {
    const capabilities = new Set<string>();
    agents.forEach((agent) => {
      agent.capabilities.forEach((cap) => {
        if (cap.enabled) {
          capabilities.add(cap.name);
        }
      });
    });
    return Array.from(capabilities).sort();
  };

  /**
   * Navigate to agent chat
   */
  const openAgentChat = (agent: Agent) => {
    (navigation as any).navigate('AgentChat', {
      agentId: agent.id,
    });
  };

  /**
   * Render agent item
   */
  const renderAgent = useCallback(
    ({ item }: { item: Agent }) => (
      <TouchableOpacity style={styles.agentCard} onPress={() => openAgentChat(item)}>
        {/* Agent Header */}
        <View style={styles.agentHeader}>
          <View style={styles.agentIcon}>
            <Icon source="robot" size={32} color={getMaturityColor(item.maturity_level)} />
          </View>

          <View style={styles.agentInfo}>
            <View style={styles.agentNameRow}>
              <Text style={styles.agentName}>{item.name}</Text>
              <View
                style={[
                  styles.maturityBadge,
                  { backgroundColor: getMaturityColor(item.maturity_level) },
                ]}
              >
                <Text style={styles.maturityBadgeText}>{item.maturity_level}</Text>
              </View>
            </View>

            <Text style={styles.agentDescription} numberOfLines={2}>
              {item.description}
            </Text>
          </View>
        </View>

        {/* Agent Status */}
        <View style={styles.agentStatus}>
          <View style={[styles.statusDot, { backgroundColor: getStatusColor(item.status)}]} />
          <Text style={styles.statusText}>{item.status}</Text>

          {item.confidence_score && (
            <Text style={styles.confidenceText}>
              Confidence: {Math.round(item.confidence_score * 100)}%
            </Text>
          )}

          {item.last_execution_at && (
            <Text style={styles.lastExecutionText}>
              Last: {formatRelativeTime(item.last_execution_at)}
            </Text>
          )}
        </View>

        {/* Capabilities */}
        <View style={styles.capabilities}>
          {item.capabilities.slice(0, 4).map((cap) => (
            <View key={cap.name} style={styles.capabilityChip}>
              <Icon
                source={cap.enabled ? 'check-circle' : 'cancel'}
                size={12}
                color={cap.enabled ? MD3Colors.primary50 : MD3Colors.secondary50}
              />
              <Text style={styles.capabilityText}>{cap.name}</Text>
            </View>
          ))}
          {item.capabilities.length > 4 && (
            <Text style={styles.moreCapabilitiesText}>+{item.capabilities.length - 4} more</Text>
          )}
        </View>
      </TouchableOpacity>
    ),
    []
  );

  /**
   * Render filter chip
   */
  const renderFilterChip = (
    label: string,
    value: string,
    selected: boolean,
    onSelect: () => void
  ) => (
    <TouchableOpacity
      key={value}
      style={[styles.filterChip, selected && styles.filterChipSelected]}
      onPress={onSelect}
    >
      <Text style={[styles.filterChipText, selected && styles.filterChipTextSelected]}>{label}</Text>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={MD3Colors.primary50} />
        <Text style={styles.loadingText}>Loading agents...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Icon source="magnify" size={20} color="#999" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search agents by name, description, or capability..."
          placeholderTextColor="#999"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        {searchQuery.length > 0 && (
          <TouchableOpacity onPress={() => setSearchQuery('')}>
            <Icon source="close" size={20} color="#999" />
          </TouchableOpacity>
        )}
      </View>

      {/* Filter Toggle */}
      <TouchableOpacity style={styles.filterToggle} onPress={() => setShowFilters(!showFilters)}>
        <Icon source="filter-variant" size={18} color={MD3Colors.primary50} />
        <Text style={styles.filterToggleText}>Filters</Text>
        {(maturityFilter !== 'ALL' ||
          statusFilter !== 'online' ||
          capabilityFilter !== null) && (
          <View style={styles.filterActiveBadge}>
            <Text style={styles.filterActiveBadgeText}>Active</Text>
          </View>
        )}
        <Icon
          source={showFilters ? 'chevron-up' : 'chevron-down'}
          size={18}
          color="#666"
        />
      </TouchableOpacity>

      {/* Filters */}
      {showFilters && (
        <View style={styles.filtersContainer}>
          {/* Maturity Filter */}
          <View style={styles.filterSection}>
            <Text style={styles.filterSectionTitle}>Maturity Level</Text>
            <View style={styles.filterChips}>
              {renderFilterChip('All', 'ALL', maturityFilter === 'ALL', () =>
                setMaturityFilter('ALL')
              )}
              {renderFilterChip('Autonomous', AgentMaturity.AUTONOMOUS, maturityFilter === AgentMaturity.AUTONOMOUS, () =>
                setMaturityFilter(AgentMaturity.AUTONOMOUS)
              )}
              {renderFilterChip('Supervised', AgentMaturity.SUPERVISED, maturityFilter === AgentMaturity.SUPERVISED, () =>
                setMaturityFilter(AgentMaturity.SUPERVISED)
              )}
              {renderFilterChip('Intern', AgentMaturity.INTERN, maturityFilter === AgentMaturity.INTERN, () =>
                setMaturityFilter(AgentMaturity.INTERN)
              )}
              {renderFilterChip('Student', AgentMaturity.STUDENT, maturityFilter === AgentMaturity.STUDENT, () =>
                setMaturityFilter(AgentMaturity.STUDENT)
              )}
            </View>
          </View>

          {/* Status Filter */}
          <View style={styles.filterSection}>
            <Text style={styles.filterSectionTitle}>Status</Text>
            <View style={styles.filterChips}>
              {renderFilterChip('Online', 'online', statusFilter === 'online', () =>
                setStatusFilter('online')
              )}
              {renderFilterChip('Offline', 'offline', statusFilter === 'offline', () =>
                setStatusFilter('offline')
              )}
              {renderFilterChip('All', 'ALL', statusFilter === 'ALL', () =>
                setStatusFilter('ALL')
              )}
            </View>
          </View>

          {/* Sort By */}
          <View style={styles.filterSection}>
            <Text style={styles.filterSectionTitle}>Sort By</Text>
            <View style={styles.filterChips}>
              {renderFilterChip('Name', 'name', sortBy === 'name', () => setSortBy('name'))}
              {renderFilterChip('Recent', 'last_execution', sortBy === 'last_execution', () =>
                setSortBy('last_execution')
              )}
              {renderFilterChip('Created', 'created_at', sortBy === 'created_at', () =>
                setSortBy('created_at')
              )}
            </View>
          </View>
        </View>
      )}

      {/* Results Count */}
      <View style={styles.resultsHeader}>
        <Text style={styles.resultsCount}>
          {filteredAgents.length} {filteredAgents.length === 1 ? 'agent' : 'agents'}
        </Text>
        {filteredAgents.length !== agents.length && (
          <TouchableOpacity onPress={() => resetFilters()}>
            <Text style={styles.resetFiltersText}>Reset filters</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Agent List */}
      <FlatList
        data={filteredAgents}
        renderItem={renderAgent}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.agentList}
        refreshing={isRefreshing}
        onRefresh={handleRefresh}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon source="robot-off" size={64} color={MD3Colors.secondary20} />
            <Text style={styles.emptyText}>No agents found</Text>
            <Text style={styles.emptySubtext}>
              {searchQuery || maturityFilter !== 'ALL' || statusFilter !== 'ALL'
                ? 'Try adjusting your filters or search query'
                : 'No agents available'}
            </Text>
          </View>
        }
      />
    </View>
  );

  /**
   * Reset filters
   */
  function resetFilters() {
    setSearchQuery('');
    setMaturityFilter('ALL');
    setStatusFilter('online');
    setCapabilityFilter(null);
    setSortBy('name');
  }
}

/**
 * Get maturity level color
 */
function getMaturityColor(maturity: AgentMaturity): string {
  switch (maturity) {
    case AgentMaturity.AUTONOMOUS:
      return '#4CAF50';
    case AgentMaturity.SUPERVISED:
      return '#FF9800';
    case AgentMaturity.INTERN:
      return '#2196F3';
    case AgentMaturity.STUDENT:
      return '#9E9E9E';
    default:
      return '#9E9E9E';
  }
}

/**
 * Get status color
 */
function getStatusColor(status: string): string {
  switch (status) {
    case 'online':
      return '#4CAF50';
    case 'offline':
      return '#9E9E9E';
    case 'busy':
      return '#FF9800';
    case 'maintenance':
      return '#F44336';
    default:
      return '#9E9E9E';
  }
}

/**
 * Format relative time
 */
function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    marginHorizontal: 16,
    marginTop: 16,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 12,
    fontSize: 15,
    color: '#000',
  },
  filterToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  filterToggleText: {
    flex: 1,
    marginLeft: 8,
    fontSize: 14,
    fontWeight: '600',
    color: '#2196F3',
  },
  filterActiveBadge: {
    backgroundColor: '#2196F3',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    marginLeft: 8,
  },
  filterActiveBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
  },
  filtersContainer: {
    backgroundColor: '#fff',
    paddingHorizontal: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  filterSection: {
    marginTop: 12,
  },
  filterSectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  filterChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#f5f5f5',
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  filterChipSelected: {
    backgroundColor: '#2196F3',
    borderColor: '#2196F3',
  },
  filterChipText: {
    fontSize: 13,
    color: '#666',
  },
  filterChipTextSelected: {
    color: '#fff',
    fontWeight: '600',
  },
  resultsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  resultsCount: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  resetFiltersText: {
    fontSize: 13,
    color: '#2196F3',
  },
  agentList: {
    padding: 16,
    gap: 12,
  },
  agentCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  agentHeader: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  agentIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#f5f5f5',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  agentInfo: {
    flex: 1,
  },
  agentNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  agentName: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  maturityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  maturityBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
    textTransform: 'uppercase',
  },
  agentDescription: {
    fontSize: 13,
    color: '#666',
    lineHeight: 18,
  },
  agentStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    gap: 12,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 12,
    color: '#666',
    textTransform: 'capitalize',
  },
  confidenceText: {
    fontSize: 12,
    color: '#2196F3',
  },
  lastExecutionText: {
    fontSize: 12,
    color: '#999',
  },
  capabilities: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  capabilityChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  capabilityText: {
    fontSize: 11,
    color: '#666',
  },
  moreCapabilitiesText: {
    fontSize: 11,
    color: '#999',
    fontStyle: 'italic',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 64,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
    textAlign: 'center',
  },
});
