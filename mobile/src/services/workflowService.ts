/**
 * Workflow Service
 * API calls for workflow management
 */

import apiService from './api';
import {
  Workflow,
  WorkflowExecution,
  WorkflowTriggerRequest,
  WorkflowTriggerResponse,
  WorkflowFilters,
  ExecutionLog,
  WorkflowStep,
} from '../types/workflow';

/**
 * Fetch all workflows with optional filtering
 */
export const getWorkflows = async (
  filters?: WorkflowFilters
): Promise<{ workflows: Workflow[]; total: number }> => {
  const params = new URLSearchParams();

  if (filters?.status) params.append('status', filters.status);
  if (filters?.category) params.append('category', filters.category);
  if (filters?.search) params.append('search', filters.search);
  if (filters?.sort_by) params.append('sort_by', filters.sort_by);
  if (filters?.sort_order) params.append('sort_order', filters.sort_order);

  const response = await apiService.get<Workflow[]>(
    `/api/mobile/workflows?${params.toString()}`
  );

  if (response.success && response.data) {
    return {
      workflows: response.data,
      total: response.data.length,
    };
  }

  throw new Error(response.error || 'Failed to fetch workflows');
};

/**
 * Get workflow details by ID
 */
export const getWorkflowById = async (
  workflowId: string
): Promise<Workflow> => {
  const response = await apiService.get<Workflow>(
    `/api/workflows/${workflowId}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch workflow');
};

/**
 * Trigger workflow execution
 */
export const triggerWorkflow = async (
  request: WorkflowTriggerRequest
): Promise<WorkflowTriggerResponse> => {
  const response = await apiService.post<WorkflowTriggerResponse>(
    '/api/mobile/workflows/trigger',
    request
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to trigger workflow');
};

/**
 * Get execution details
 */
export const getExecutionById = async (
  executionId: string
): Promise<WorkflowExecution> => {
  const response = await apiService.get<WorkflowExecution>(
    `/api/executions/${executionId}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch execution');
};

/**
 * Get execution logs
 */
export const getExecutionLogs = async (
  executionId: string
): Promise<ExecutionLog[]> => {
  const response = await apiService.get<ExecutionLog[]>(
    `/api/executions/${executionId}/logs`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch execution logs');
};

/**
 * Get execution steps with status
 */
export const getExecutionSteps = async (
  executionId: string
): Promise<WorkflowStep[]> => {
  const response = await apiService.get<WorkflowStep[]>(
    `/api/executions/${executionId}/steps`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch execution steps');
};

/**
 * Cancel a running execution
 */
export const cancelExecution = async (
  executionId: string
): Promise<{ message: string }> => {
  const response = await apiService.post<{ message: string }>(
    `/api/executions/${executionId}/cancel`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to cancel execution');
};

/**
 * Get recent executions for a workflow
 */
export const getWorkflowExecutions = async (
  workflowId: string,
  limit: number = 10
): Promise<WorkflowExecution[]> => {
  const response = await apiService.get<WorkflowExecution[]>(
    `/api/workflows/${workflowId}/executions?limit=${limit}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to fetch workflow executions');
};

/**
 * Search workflows by query
 */
export const searchWorkflows = async (
  query: string
): Promise<Workflow[]> => {
  const response = await apiService.get<Workflow[]>(
    `/api/mobile/workflows?search=${encodeURIComponent(query)}`
  );

  if (response.success && response.data) {
    return response.data;
  }

  throw new Error(response.error || 'Failed to search workflows');
};
