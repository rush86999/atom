/**
 * Mobile Analytics Types
 * TypeScript definitions for analytics and metrics data
 */

export interface DashboardKPIs {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  average_duration_ms: number;
  average_duration_seconds: number;
  unique_workflows: number;
  unique_users: number;
  error_rate: number;
}

export interface WorkflowPerformanceRanking {
  workflow_id: string;
  workflow_name: string;
  total_executions: number;
  success_rate: number;
  average_duration_ms: number;
  last_execution: string;
  trend: 'up' | 'down' | 'stable';
}

export interface ExecutionTimelineData {
  timestamp: string;
  count: number;
  success_count: number;
  failure_count: number;
  average_duration_ms: number;
}

export interface MetricCardData {
  title: string;
  value: string | number;
  description?: string;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  color?: 'success' | 'warning' | 'error' | 'info';
}

export interface TimeRange {
  value: '1h' | '24h' | '7d' | '30d';
  label: string;
}
