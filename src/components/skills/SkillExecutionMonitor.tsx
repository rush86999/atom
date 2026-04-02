/**
 * SkillExecutionMonitor Component
 *
 * Real-time monitoring for OpenClaw skill executions.
 * Displays execution status, duration, ACU cost, and provides cancel button.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  getExecution,
  pollExecution,
  cancelExecution,
  ExecutionDetail,
  ExecutionStatus,
  getStatusColor,
  getStatusLabel,
} from '@/lib/openclaw/openclaw-executions';
import { Play, Square, Clock, Cpu, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface SkillExecutionMonitorProps {
  executionId: string;
  onComplete?: (execution: ExecutionDetail) => void;
  onError?: (error: Error) => void;
  autoPoll?: boolean;
  pollInterval?: number;
}

export function SkillExecutionMonitor({
  executionId,
  onComplete,
  onError,
  autoPoll = true,
  pollInterval = 2000,
}: SkillExecutionMonitorProps) {
  const [execution, setExecution] = useState<ExecutionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load execution status
  const loadExecution = useCallback(async () => {
    try {
      const data = await getExecution(executionId);
      setExecution(data);
      setError(null);

      // Trigger completion callback
      if (['completed', 'failed', 'cancelled'].includes(data.status)) {
        onComplete?.(data);
      }

      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load execution';
      setError(message);
      onError?.(err instanceof Error ? err : new Error(message));
      return null;
    } finally {
      setLoading(false);
    }
  }, [executionId, onComplete, onError]);

  // Start polling on mount
  useEffect(() => {
    if (!autoPoll) return;

    loadExecution(); // Initial load

    // Set up polling for running executions
    const interval = setInterval(async () => {
      const data = await loadExecution();
      if (data && ['completed', 'failed', 'cancelled'].includes(data.status)) {
        clearInterval(interval);
      }
    }, pollInterval);

    return () => clearInterval(interval);
  }, [autoPoll, pollInterval, loadExecution]);

  // Cancel execution handler
  const handleCancel = async () => {
    if (!execution) return;

    setCancelling(true);
    try {
      await cancelExecution(executionId);
      await loadExecution(); // Refresh to show cancelled status
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel');
    } finally {
      setCancelling(false);
    }
  };

  // Calculate duration
  const getDuration = () => {
    if (!execution) return '-';
    if (execution.completed_at) {
      return execution.execution_seconds.toFixed(2) + 's';
    }
    // For running executions, calculate from created_at
    const created = new Date(execution.created_at).getTime();
    const now = Date.now();
    return ((now - created) / 1000).toFixed(1) + 's';
  };

  // Loading state
  if (loading && !execution) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading execution status...
        </div>
      </Card>
    );
  }

  // Error state
  if (error && !execution) {
    return (
      <Card className="p-6 border-red-200 dark:border-red-800">
        <div className="text-sm text-red-600 dark:text-red-400">
          Failed to load execution: {error}
        </div>
      </Card>
    );
  }

  if (!execution) return null;

  const isRunning = execution.status === 'running';
  const canCancel = isRunning || execution.status === 'pending';

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b dark:border-gray-800 flex items-center justify-between bg-gray-50 dark:bg-gray-900/50">
        <div className="flex items-center gap-3">
          <Play className="w-4 h-4 text-gray-600 dark:text-gray-400" />
          <div>
            <h3 className="font-semibold text-sm">Execution: {execution.id.slice(0, 8)}...</h3>
            {execution.skill_name && (
              <p className="text-xs text-gray-500 dark:text-gray-400">{execution.skill_name}</p>
            )}
          </div>
        </div>
        <Badge className={getStatusColor(execution.status as ExecutionStatus)}>
          {getStatusLabel(execution.status as ExecutionStatus)}
        </Badge>
      </div>

      {/* Details */}
      <div className="p-4 space-y-3">
        {/* Status indicators */}
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            <span className="text-gray-600 dark:text-gray-400">Duration:</span>
            <span className="font-medium">{getDuration()}</span>
          </div>
          {execution.environment && (
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600 dark:text-gray-400">Environment:</span>
              <span className="font-medium capitalize">{execution.environment}</span>
            </div>
          )}
          {execution.acus && (
            <div className="flex items-center gap-2">
              <span className="text-gray-600 dark:text-gray-400">Cost:</span>
              <span className="font-medium">{execution.acus.toFixed(3)} ACU</span>
            </div>
          )}
        </div>

        {/* Execution output */}
        {(execution.output_result || execution.error_message) && (
          <div className="mt-4">
            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Output</h4>
            <ScrollArea className="h-32 w-full rounded-md border bg-gray-50 dark:bg-gray-900/50 p-3">
              {execution.error_message ? (
                <pre className="text-xs text-red-600 dark:text-red-400 whitespace-pre-wrap">
                  {execution.error_message}
                </pre>
              ) : execution.output_result?.formatted_output ? (
                <div className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {execution.output_result.formatted_output}
                </div>
              ) : execution.output_result?.stdout ? (
                <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                  {execution.output_result.stdout}
                </pre>
              ) : (
                <p className="text-xs text-gray-400 italic">No output</p>
              )}
            </ScrollArea>
          </div>
        )}

        {/* Input params (collapsed by default) */}
        {execution.input_params && Object.keys(execution.input_params).length > 0 && (
          <details className="mt-3">
            <summary className="text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">
              Input Parameters
            </summary>
            <pre className="mt-2 text-xs bg-gray-50 dark:bg-gray-900/50 p-2 rounded overflow-x-auto">
              {JSON.stringify(execution.input_params, null, 2)}
            </pre>
          </details>
        )}
      </div>

      {/* Actions */}
      <div className="p-4 border-t dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 flex justify-between items-center">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Started: {new Date(execution.created_at).toLocaleString()}
        </div>
        {canCancel && (
          <Button
            variant="destructive"
            size="sm"
            onClick={handleCancel}
            disabled={cancelling}
            className="gap-1"
          >
            <Square className="w-3 h-3" />
            {cancelling ? 'Cancelling...' : 'Cancel'}
          </Button>
        )}
        {execution.status === 'completed' && (
          <div className="flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
            <CheckCircle className="w-4 h-4" />
            Completed successfully
          </div>
        )}
        {execution.status === 'failed' && (
          <div className="flex items-center gap-1 text-sm text-red-600 dark:text-red-400">
            <XCircle className="w-4 h-4" />
            Failed
          </div>
        )}
        {execution.status === 'cancelled' && (
          <div className="flex items-center gap-1 text-sm text-yellow-600 dark:text-yellow-400">
            <Square className="w-4 h-4" />
            Cancelled
          </div>
        )}
      </div>
    </Card>
  );
}

export default SkillExecutionMonitor;
