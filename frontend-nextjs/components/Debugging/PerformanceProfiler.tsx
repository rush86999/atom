/**
 * Performance Profiler Component
 *
 * Displays performance metrics and identifies bottlenecks in workflow execution.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Gauge, TrendingUp, Clock, Zap, Play, BarChart3, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { formatDistanceToNow } from 'date-fns';

interface StepTiming {
  node_id: string;
  node_type: string;
  duration_ms: number;
  timestamp: string;
}

interface NodeMetrics {
  node_id: string;
  count: number;
  total_ms: number;
  avg_ms: number;
  min_ms: number;
  max_ms: number;
}

interface PerformanceReport {
  session_id: string;
  total_duration_ms: number;
  total_steps: number;
  average_step_duration_ms: number;
  slowest_steps: StepTiming[];
  slowest_nodes: NodeMetrics[];
  profiling_started_at: string | null;
  generated_at: string;
}

interface PerformanceProfilerProps {
  sessionId: string | null;
  workflowId: string | null;
  currentUserId: string;
}

export const PerformanceProfiler: React.FC<PerformanceProfilerProps> = ({
  sessionId,
  workflowId,
  currentUserId,
}) => {
  const { toast } = useToast();

  const [profiling, setProfiling] = useState(false);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<PerformanceReport | null>(null);

  useEffect(() => {
    if (sessionId && profiling) {
      // Auto-refresh report every 2 seconds when profiling
      const interval = setInterval(fetchReport, 2000);
      return () => clearInterval(interval);
    }
  }, [sessionId, profiling]);

  const fetchReport = async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      const response = await fetch(`/api/workflows/debug/sessions/${sessionId}/profiling/report`);

      if (response.ok) {
        const data = await response.json();
        setReport(data);
      }
    } catch (err) {
      console.error('Error fetching performance report:', err);
    } finally {
      setLoading(false);
    }
  };

  const startProfiling = async () => {
    if (!sessionId) return;

    try {
      const response = await fetch(`/api/workflows/debug/sessions/${sessionId}/profiling/start`, {
        method: 'POST',
      });

      if (!response.ok) throw new Error('Failed to start profiling');

      setProfiling(true);
      toast({
        title: 'Profiling Started',
        description: 'Performance profiling is now active',
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to start profiling',
        variant: 'error',
      });
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
    return `${(ms / 60000).toFixed(2)}m`;
  };

  const getNodeTypeColor = (nodeType: string) => {
    const colors: Record<string, string> = {
      trigger: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      action: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      condition: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      loop: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    };
    return colors[nodeType] || 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-purple-500" />
              Performance Profiler
            </CardTitle>
            <CardDescription>
              {report ? `Total: ${formatDuration(report.total_duration_ms)}` : 'Not started'}
            </CardDescription>
          </div>

          {!profiling ? (
            <Button onClick={startProfiling} disabled={!sessionId} size="sm">
              <Play className="h-4 w-4 mr-2" />
              Start Profiling
            </Button>
          ) : (
            <Badge variant="default" className="animate-pulse">
              <Zap className="h-3 w-3 mr-1" />
              Recording
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {loading && !report ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : !report ? (
          <div className="text-center py-8 text-muted-foreground">
            <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Start profiling to see performance metrics</p>
          </div>
        ) : (
          <>
            {/* Summary Metrics */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-muted p-3 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                  <Clock className="h-4 w-4" />
                  Total Duration
                </div>
                <p className="text-lg font-semibold">{formatDuration(report.total_duration_ms)}</p>
              </div>

              <div className="bg-muted p-3 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                  <TrendingUp className="h-4 w-4" />
                  Total Steps
                </div>
                <p className="text-lg font-semibold">{report.total_steps}</p>
              </div>

              <div className="bg-muted p-3 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                  <Gauge className="h-4 w-4" />
                  Avg Step Time
                </div>
                <p className="text-lg font-semibold">
                  {formatDuration(Math.round(report.average_step_duration_ms))}
                </p>
              </div>
            </div>

            {/* Slowest Steps */}
            <div>
              <h4 className="text-sm font-medium mb-2">Slowest Steps</h4>
              <ScrollArea className="h-[200px]">
                <div className="space-y-2">
                  {report.slowest_steps.slice(0, 10).map((step, idx) => {
                    const maxDuration = report.slowest_steps[0]?.duration_ms || 1;
                    const percentage = (step.duration_ms / maxDuration) * 100;

                    return (
                      <div key={idx} className="p-3 border rounded-lg">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Badge className={getNodeTypeColor(step.node_type)}>
                              {step.node_type}
                            </Badge>
                            <span className="text-sm font-medium">{step.node_id}</span>
                          </div>
                          <span className="text-sm font-semibold">{formatDuration(step.duration_ms)}</span>
                        </div>
                        <Progress value={percentage} className="h-2" />
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </div>

            {/* Slowest Nodes (by average) */}
            <div>
              <h4 className="text-sm font-medium mb-2">Slowest Nodes (Average)</h4>
              <ScrollArea className="h-[200px]">
                <div className="space-y-2">
                  {report.slowest_nodes.slice(0, 10).map((node, idx) => (
                    <div key={idx} className="p-3 border rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium">{node.node_id}</span>
                        <span className="text-sm text-muted-foreground">
                          {node.count}x executed
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <span className="text-muted-foreground">Avg: </span>
                          {formatDuration(Math.round(node.avg_ms))}
                        </div>
                        <div>
                          <span className="text-muted-foreground">Min: </span>
                          {formatDuration(node.min_ms)}
                        </div>
                        <div>
                          <span className="text-muted-foreground">Max: </span>
                          {formatDuration(node.max_ms)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Metadata */}
            <div className="text-xs text-muted-foreground pt-2 border-t">
              {report.profiling_started_at && (
                <p>Started: {formatDistanceToNow(new Date(report.profiling_started_at))} ago</p>
              )}
              <p>Generated: {new Date(report.generated_at).toLocaleString()}</p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default PerformanceProfiler;
