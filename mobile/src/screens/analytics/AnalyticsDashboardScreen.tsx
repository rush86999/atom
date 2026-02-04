/**
 * Analytics Dashboard Screen (Mobile)
 * Mobile-optimized analytics dashboard with KPIs, charts, and metrics
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  VictoryChart,
  VictoryLine,
  VictoryArea,
  VictoryAxis,
  VictoryTheme,
  VictoryLegend,
  VictoryTooltip,
  VictoryVoronoiContainer,
} from 'victory-native';
import { useNavigation, NavigationProp } from '@react-navigation/native';
import {
  getDashboardKPIs,
  getTopWorkflows,
  getExecutionTimeline,
} from '../../services/analyticsService';
import { DashboardKPIs, ExecutionTimelineData, TimeRange } from '../../types/analytics';

type NavigationType = {
  AnalyticsDashboard: any;
  WorkflowsList: any;
};

const TIME_RANGES: TimeRange[] = [
  { value: '1h', label: '1 Hour' },
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
];

export const AnalyticsDashboardScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp<NavigationType>>();

  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange['value']>('24h');
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [timelineData, setTimelineData] = useState<ExecutionTimelineData[]>([]);
  const [topWorkflows, setTopWorkflows] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch analytics data
  const fetchAnalytics = useCallback(async (refresh: boolean = false) => {
    try {
      if (refresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }

      const [kpisData, timeline, workflows] = await Promise.all([
        getDashboardKPIs(selectedTimeRange),
        getExecutionTimeline(selectedTimeRange, '1h'),
        getTopWorkflows(5, 'executions'),
      ]);

      setKpis(kpisData);
      setTimelineData(timeline);
      setTopWorkflows(workflows);

      setIsLoading(false);
      setIsRefreshing(false);
    } catch (error: any) {
      setIsLoading(false);
      setIsRefreshing(false);
      console.error('Error fetching analytics:', error);
    }
  }, [selectedTimeRange]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // Get KPI card color
  const getKPIColor = (key: string): string => {
    const colors: Record<string, string> = {
      total: '#2196F3',
      success: '#4CAF50',
      failed: '#f44336',
      duration: '#FF9800',
    };
    return colors[key] || '#2196F3';
  };

  // Render KPI Card
  const renderKPICard = (
    title: string,
    value: string | number,
    subtitle: string,
    icon: string,
    colorKey: string
  ) => (
    <View style={[styles.kpiCard, { borderLeftColor: getKPIColor(colorKey) }]}>
      <View style={styles.kpiHeader}>
        <View style={[styles.kpiIcon, { backgroundColor: `${getKPIColor(colorKey)}20` }]}>
          <Ionicons name={icon as any} size={24} color={getKPIColor(colorKey)} />
        </View>
      </View>
      <Text style={styles.kpiValue}>{value}</Text>
      <Text style={styles.kpiTitle}>{title}</Text>
      <Text style={styles.kpiSubtitle}>{subtitle}</Text>
    </View>
  );

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
        <Text style={styles.loadingText}>Loading analytics...</Text>
      </View>
    );
  }

  if (!kpis) {
    return (
      <View style={styles.centerContainer}>
        <Ionicons name="alert-circle" size={60} color="#f44336" />
        <Text style={styles.errorText}>Failed to load analytics</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => fetchAnalytics()}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Analytics Dashboard</Text>
        <Text style={styles.headerSubtitle}>Workflow performance metrics</Text>
      </View>

      {/* Time Range Selector */}
      <View style={styles.timeRangeContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {TIME_RANGES.map((range) => (
            <TouchableOpacity
              key={range.value}
              style={[
                styles.timeRangeChip,
                selectedTimeRange === range.value && styles.timeRangeChipActive,
              ]}
              onPress={() => setSelectedTimeRange(range.value)}
            >
              <Text
                style={[
                  styles.timeRangeText,
                  selectedTimeRange === range.value && styles.timeRangeTextActive,
                ]}
              >
                {range.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={() => fetchAnalytics(true)}
            colors={['#2196F3']}
          />
        }
      >
        {/* KPI Cards */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Key Performance Indicators</Text>
          <View style={styles.kpiGrid}>
            {renderKPICard(
              'Total Executions',
              kpis.total_executions,
              'All workflows',
              'stats-chart',
              'total'
            )}
            {renderKPICard(
              'Success Rate',
              `${kpis.success_rate.toFixed(1)}%`,
              `${kpis.successful_executions} successful`,
              'checkmark-circle',
              'success'
            )}
            {renderKPICard(
              'Failed',
              kpis.failed_executions,
              `${kpis.error_rate.toFixed(1)}% error rate`,
              'close-circle',
              'failed'
            )}
            {renderKPICard(
              'Avg Duration',
              `${kpis.average_duration_seconds.toFixed(1)}s`,
              'Per execution',
              'time',
              'duration'
            )}
          </View>
        </View>

        {/* Execution Timeline Chart */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Execution Timeline</Text>
          {timelineData.length > 0 ? (
            <View style={styles.chartContainer}>
              <VictoryChart
                theme={VictoryTheme.material}
                containerComponent={<VictoryVoronoiContainer />}
                height={250}
              >
                <VictoryArea
                  data={timelineData}
                  x="timestamp"
                  y="success_count"
                  style={{
                    data: { fill: '#4CAF50', fillOpacity: 0.3 },
                  }}
                />
                <VictoryLine
                  data={timelineData}
                  x="timestamp"
                  y="success_count"
                  style={{
                    data: { stroke: '#4CAF50', strokeWidth: 2 },
                  }}
                />
                <VictoryArea
                  data={timelineData}
                  x="timestamp"
                  y="failure_count"
                  style={{
                    data: { fill: '#f44336', fillOpacity: 0.3 },
                  }}
                />
                <VictoryLine
                  data={timelineData}
                  x="timestamp"
                  y="failure_count"
                  style={{
                    data: { stroke: '#f44336', strokeWidth: 2 },
                  }}
                />
                <VictoryAxis
                  tickFormat={(tick) => {
                    const date = new Date(tick);
                    return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`;
                  }}
                  style={{
                    tickLabels: { fontSize: 10, angle: -45 },
                  }}
                />
                <VictoryLegend
                  x={125}
                  y={10}
                  orientation="horizontal"
                  gutter={20}
                  style={{
                    labels: { fontSize: 12 },
                  }}
                  data={[
                    { name: 'Success', symbol: { fill: '#4CAF50' } },
                    { name: 'Failure', symbol: { fill: '#f44336' } },
                  ]}
                />
              </VictoryChart>
            </View>
          ) : (
            <View style={styles.emptyChart}>
              <Text style={styles.emptyText}>No timeline data available</Text>
            </View>
          )}
        </View>

        {/* Top Workflows */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Top Workflows</Text>
            <TouchableOpacity onPress={() => navigation.navigate('WorkflowsList' as any)}>
              <Text style={styles.viewAllText}>View All</Text>
            </TouchableOpacity>
          </View>

          {topWorkflows.length === 0 ? (
            <Text style={styles.emptyText}>No workflow data available</Text>
          ) : (
            topWorkflows.map((workflow, index) => (
              <TouchableOpacity
                key={workflow.workflow_id}
                style={styles.workflowItem}
                onPress={() => {
                  // Navigate to workflow details
                }}
              >
                <View style={styles.workflowRank}>
                  <Text style={styles.workflowRankText}>#{index + 1}</Text>
                </View>
                <View style={styles.workflowInfo}>
                  <Text style={styles.workflowName}>{workflow.workflow_name}</Text>
                  <View style={styles.workflowStats}>
                    <View style={styles.workflowStat}>
                      <Ionicons name="play-circle" size={14} color="#4CAF50" />
                      <Text style={styles.workflowStatText}>
                        {workflow.total_executions} runs
                      </Text>
                    </View>
                    <View style={styles.workflowStat}>
                      <Ionicons name="checkmark-circle" size={14} color="#4CAF50" />
                      <Text style={styles.workflowStatText}>
                        {workflow.success_rate.toFixed(1)}% success
                      </Text>
                    </View>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#999" />
              </TouchableOpacity>
            ))
          )}
        </View>

        {/* Quick Stats */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Overview</Text>
          <View style={styles.quickStats}>
            <View style={styles.quickStatItem}>
              <Text style={styles.quickStatValue}>{kpis.unique_workflows}</Text>
              <Text style={styles.quickStatLabel}>Unique Workflows</Text>
            </View>
            <View style={styles.quickStatDivider} />
            <View style={styles.quickStatItem}>
              <Text style={styles.quickStatValue}>{kpis.unique_users}</Text>
              <Text style={styles.quickStatLabel}>Active Users</Text>
            </View>
          </View>
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
  retryButton: {
    marginTop: 16,
    backgroundColor: '#2196F3',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#fff',
    fontWeight: '600',
  },
  header: {
    backgroundColor: '#fff',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#666',
  },
  timeRangeContainer: {
    backgroundColor: '#fff',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  timeRangeChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#f5f5f5',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  timeRangeChipActive: {
    backgroundColor: '#2196F3',
    borderColor: '#2196F3',
  },
  timeRangeText: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  timeRangeTextActive: {
    color: '#fff',
  },
  content: {
    flex: 1,
  },
  section: {
    backgroundColor: '#fff',
    padding: 16,
    marginBottom: 12,
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
    marginBottom: 12,
  },
  viewAllText: {
    fontSize: 14,
    color: '#2196F3',
    fontWeight: '500',
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -6,
  },
  kpiCard: {
    width: '50%',
    backgroundColor: '#f9f9f9',
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 6,
    marginBottom: 12,
    borderLeftWidth: 4,
  },
  kpiHeader: {
    marginBottom: 8,
  },
  kpiIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  kpiValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  kpiTitle: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  kpiSubtitle: {
    fontSize: 12,
    color: '#999',
  },
  chartContainer: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 8,
  },
  emptyChart: {
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
  },
  workflowItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  workflowRank: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#2196F3',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  workflowRankText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  workflowInfo: {
    flex: 1,
  },
  workflowName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  workflowStats: {
    flexDirection: 'row',
  },
  workflowStat: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
  },
  workflowStatText: {
    fontSize: 12,
    color: '#666',
    marginLeft: 4,
  },
  quickStats: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
  },
  quickStatItem: {
    flex: 1,
    alignItems: 'center',
  },
  quickStatValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#2196F3',
    marginBottom: 4,
  },
  quickStatLabel: {
    fontSize: 14,
    color: '#666',
  },
  quickStatDivider: {
    width: 1,
    height: 40,
    backgroundColor: '#e0e0e0',
  },
});

export default AnalyticsDashboardScreen;
