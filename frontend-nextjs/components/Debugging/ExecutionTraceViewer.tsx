/**
 * Execution Trace Viewer Component
 *
 * Displays detailed execution trace logs for debugging workflows.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  FileText,
  Search,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Filter,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { formatDistanceToNow } from 'date-fns';

interface ExecutionTrace {
  trace_id: string;
  workflow_id: string;
  execution_id: string;
  debug_session_id: string;
  step_number: number;
  node_id: string;
  node_type: string;
  status: string;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  error_message: string;
  variable_changes: Array<{
    variable: string;
    type: string;
    old_value: any;
    new_value: any;
  }>;
  started_at: string;
  completed_at: string;
  duration_ms: number;
}

interface ExecutionTraceViewerProps {
  executionId: string;
  workflowId: string;
  currentUserId: string;
  debugSessionId?: string | null;
}

export const ExecutionTraceViewer: React.FC<ExecutionTraceViewerProps> = ({
  executionId,
  workflowId,
  currentUserId,
  debugSessionId,
}) => {
  const { toast } = useToast();

  const [traces, setTraces] = useState<ExecutionTrace[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchTraces();
  }, [executionId, debugSessionId]);

  const fetchTraces = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/workflows/executions/${executionId}/traces${debugSessionId ? `?debug_session_id=${debugSessionId}` : ''}`
      );

      if (response.ok) {
        const data = await response.json();
        setTraces(data);
      }
    } catch (err) {
      console.error('Error fetching traces:', err);
      toast({
        title: 'Error',
        description: 'Failed to fetch execution traces',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (traceId: string) => {
    const newExpanded = new Set(expandedTraces);
    if (newExpanded.has(traceId)) {
      newExpanded.delete(traceId);
    } else {
      newExpanded.add(traceId);
    }
    setExpandedTraces(newExpanded);
  };

  const filteredTraces = traces.filter((t) => {
    const matchesSearch =
      !searchTerm ||
      t.node_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.node_type.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'all' || t.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'started':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'started':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-green-500" />
              Execution Trace
            </CardTitle>
            <CardDescription>
              {traces.length} step{traces.length !== 1 ? 's' : ''}
            </CardDescription>
          </div>

          <Button variant="outline" size="sm" onClick={fetchTraces} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Search and Filter */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search traces..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8"
            />
          </div>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="started">Started</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Traces List */}
        {loading ? (
          <div className="text-center py-4 text-muted-foreground">Loading traces...</div>
        ) : filteredTraces.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No execution traces found</p>
          </div>
        ) : (
          <ScrollArea className="h-[500px]">
            <div className="space-y-2">
              {filteredTraces.map((trace) => {
                const isExpanded = expandedTraces.has(trace.trace_id);

                return (
                  <div key={trace.trace_id} className="border rounded-lg">
                    {/* Trace Header */}
                    <div
                      className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50"
                      onClick={() => toggleExpand(trace.trace_id)}
                    >
                      <div className="flex items-center gap-3">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}

                        {getStatusIcon(trace.status)}

                        <div>
                          <p className="font-medium text-sm">Step {trace.step_number}</p>
                          <p className="text-xs text-muted-foreground">{trace.node_id}</p>
                        </div>

                        <Badge className={getStatusColor(trace.status)}>{trace.status}</Badge>
                        <Badge variant="outline" className="text-xs">
                          {trace.node_type}
                        </Badge>
                      </div>

                      <div className="text-xs text-muted-foreground">
                        {trace.duration_ms ? (
                          <span>{trace.duration_ms}ms</span>
                        ) : (
                          <span>Running...</span>
                        )}
                      </div>
                    </div>

                    {/* Expanded Details */}
                    {isExpanded && (
                      <div className="border-t p-4 space-y-4">
                        {/* Timestamps */}
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="text-muted-foreground">Started</p>
                            <p>{new Date(trace.started_at).toLocaleString()}</p>
                          </div>
                          {trace.completed_at && (
                            <div>
                              <p className="text-muted-foreground">Completed</p>
                              <p>{new Date(trace.completed_at).toLocaleString()}</p>
                            </div>
                          )}
                        </div>

                        {/* Input/Output */}
                        <div>
                          <p className="text-sm font-medium mb-2">Input Data</p>
                          <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">
                            {JSON.stringify(trace.input_data, null, 2)}
                          </pre>
                        </div>

                        {trace.output_data && Object.keys(trace.output_data).length > 0 && (
                          <div>
                            <p className="text-sm font-medium mb-2">Output Data</p>
                            <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">
                              {JSON.stringify(trace.output_data, null, 2)}
                            </pre>
                          </div>
                        )}

                        {trace.error_message && (
                          <div>
                            <p className="text-sm font-medium mb-2 text-red-500">Error</p>
                            <p className="text-sm bg-red-50 dark:bg-red-900/20 p-2 rounded text-red-600">
                              {trace.error_message}
                            </p>
                          </div>
                        )}

                        {/* Variable Changes */}
                        {trace.variable_changes && trace.variable_changes.length > 0 && (
                          <div>
                            <p className="text-sm font-medium mb-2">Variable Changes</p>
                            <div className="space-y-1">
                              {trace.variable_changes.map((change, idx) => (
                                <div key={idx} className="text-xs bg-muted p-2 rounded">
                                  <span className={change.type === 'added' ? 'text-green-600' : change.type === 'removed' ? 'text-red-600' : 'text-yellow-600'}>
                                    [{change.type.toUpperCase()}]
                                  </span>{' '}
                                  <span className="font-medium">{change.variable}</span>
                                  {change.old_value !== undefined && (
                                    <span>
                                      {' '} Old: {JSON.stringify(change.old_value)}
                                    </span>
                                  )}
                                  {change.new_value !== undefined && (
                                    <span>
                                      {' '} New: {JSON.stringify(change.new_value)}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
};

export default ExecutionTraceViewer;
