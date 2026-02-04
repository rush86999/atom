/**
 * Mobile Workflow Types
 * TypeScript definitions for workflow-related data structures
 */

export interface Workflow {
  id: string;
  name: string;
  description: string;
  category: string;
  status: 'active' | 'inactive' | 'draft';
  created_at: string;
  updated_at: string;
  last_execution?: string;
  execution_count: number;
  success_rate: number;
  tags: string[];
}

export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  triggered_by: string;
  error_message?: string;
  output?: Record<string, any>;
  current_step?: string;
  total_steps?: number;
  progress_percentage: number;
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: 'trigger' | 'action' | 'condition' | 'loop' | 'sub_workflow';
  service?: string;
  action?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  output?: any;
  error?: string;
}

export interface WorkflowTriggerRequest {
  workflow_id: string;
  parameters?: Record<string, any>;
  synchronous?: boolean;
}

export interface WorkflowTriggerResponse {
  execution_id: string;
  status: string;
  message: string;
}

export interface WorkflowFilters {
  status?: string;
  category?: string;
  search?: string;
  sort_by?: 'name' | 'created_at' | 'execution_count' | 'success_rate';
  sort_order?: 'asc' | 'desc';
}

export interface ExecutionLog {
  id: string;
  execution_id: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  timestamp: string;
  step_id?: string;
  metadata?: Record<string, any>;
}
