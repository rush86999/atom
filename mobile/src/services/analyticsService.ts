/**
 * Analytics Service
 * API calls for analytics and metrics
 */

import apiService from './api';
import {
  DashboardKPIs,
  WorkflowPerformanceRanking,
  ExecutionTimelineData,
} from '../types/analytics';

/**
 * Get dashboard KPIs
 */
export const getDashboardKPIs = async (
  timeWindow: '1h' | '24h' | '7d' | '30d' = '24h'
): Promise<DashboardKPIs> => {
  const response = await apiService.get<DashboardKPIs>(
    `/api/analytics/dashboard/kpis?time_window=${timeWindow}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch dashboard KPIs');
};

/**
 * Get top performing workflows
 */
export const getTopWorkflows = async (
  limit: number = 10,
  sortBy: 'success_rate' | 'executions' | 'duration' = 'success_rate'
): Promise<WorkflowPerformanceRanking[]> => {
  const response = await apiService.get<WorkflowPerformanceRanking[]>(
    `/api/analytics/dashboard/workflows/top-performing?limit=${limit}&sort_by=${sortBy}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch top workflows');
};

/**
 * Get execution timeline data
 */
export const getExecutionTimeline = async (
  timeWindow: '1h' | '24h' | '7d' | '30d' = '24h',
  interval: '5m' | '15m' | '1h' | '1d' = '1h'
): Promise<ExecutionTimelineData[]> => {
  const response = await apiService.get<ExecutionTimelineData[]>(
    `/api/analytics/dashboard/timeline?time_window=${timeWindow}&interval=${interval}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch execution timeline');
};

/**
 * Get real-time execution feed
 */
export const getRealtimeFeed = async (
  limit: number = 50
): Promise<any[]> => {
  const response = await apiService.get<any[]>(
    `/api/analytics/dashboard/realtime-feed?limit=${limit}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch real-time feed');
};

/**
 * Get error breakdown
 */
export const getErrorBreakdown = async (
  timeWindow: '1h' | '24h' | '7d' | '30d' = '24h'
): Promise<any> => {
  const response = await apiService.get<any>(
    `/api/analytics/dashboard/errors/breakdown?time_window=${timeWindow}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch error breakdown');
};

/**
 * Get comprehensive metrics summary
 */
export const getMetricsSummary = async (
  timeWindow: '1h' | '24h' | '7d' | '30d' = '24h'
): Promise<any> => {
  const response = await apiService.get<any>(
    `/api/analytics/dashboard/metrics/summary?time_window=${timeWindow}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch metrics summary');
};
