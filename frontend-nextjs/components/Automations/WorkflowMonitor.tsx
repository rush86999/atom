import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play, Pause, RotateCcw, Trash2, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { getWebSocketClient, WebSocketMessage } from '@/lib/websocket-client';
import { toast } from 'sonner';

interface Execution {
  execution_id: string;
  workflow_id: string;
  status: 'running' | 'completed' | 'failed' | 'paused';
  started_at: string;
  completed_at?: string;
  steps_executed: number;
  current_step?: string;
  error?: string;
}

interface WorkflowMonitorProps {
  initialExecutions?: Execution[];
  workflowId?: string;
}

const WorkflowMonitor: React.FC<WorkflowMonitorProps> = ({ 
  initialExecutions = [],
  workflowId 
}) => {
  const [executions, setExecutions] = useState<Execution[]>(initialExecutions);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Initialize WebSocket connection
    const wsClient = getWebSocketClient({
      userId: 'user_' + Math.random().toString(36).substr(2, 9),
      channels: ['workflows', 'system']
    });

    const connect = async () => {
      try {
        await wsClient.connect();
        setIsConnected(true);
        
        if (workflowId) {
          wsClient.subscribe(`workflow:${workflowId}`);
        }
      } catch (error) {
        console.error('WebSocket connection failed:', error);
        toast.error('Failed to connect to real-time updates');
      }
    };

    connect();

    // Subscribe to workflow events
    const handleWorkflowEvent = (message: WebSocketMessage) => {
      if (message.type.startsWith('workflow.')) {
        updateExecutionState(message);
      }
    };

    // Register event listeners
    const unsubscribeStarted = wsClient.on('workflow.started', handleWorkflowEvent);
    const unsubscribeProgress = wsClient.on('workflow.progress', handleWorkflowEvent);
    const unsubscribeCompleted = wsClient.on('workflow.completed', handleWorkflowEvent);
    const unsubscribeFailed = wsClient.on('workflow.failed', handleWorkflowEvent);
    const unsubscribePaused = wsClient.on('workflow.paused', handleWorkflowEvent);
    const unsubscribeResumed = wsClient.on('workflow.resumed', handleWorkflowEvent);

    return () => {
      unsubscribeStarted();
      unsubscribeProgress();
      unsubscribeCompleted();
      unsubscribeFailed();
      unsubscribePaused();
      unsubscribeResumed();
      wsClient.disconnect();
    };
  }, [workflowId]);

  const updateExecutionState = (message: WebSocketMessage) => {
    const { execution_id, data } = message;
    
    setExecutions(prev => {
      const existingIndex = prev.findIndex(e => e.execution_id === execution_id);
      
      if (existingIndex === -1) {
        // New execution
        if (message.type === 'workflow.started') {
          return [{
            execution_id: execution_id!,
            workflow_id: data.workflow_id,
            status: 'running',
            started_at: message.timestamp,
            steps_executed: 0
          }, ...prev];
        }
        return prev;
      }

      // Update existing execution
      const newExecutions = [...prev];
      const execution = { ...newExecutions[existingIndex] };

      switch (message.type) {
        case 'workflow.progress':
          execution.steps_executed = data.steps_executed;
          execution.current_step = data.current_step;
          break;
        case 'workflow.completed':
          execution.status = 'completed';
          execution.completed_at = message.timestamp;
          execution.steps_executed = data.steps_executed;
          break;
        case 'workflow.failed':
          execution.status = 'failed';
          execution.completed_at = message.timestamp;
          execution.error = data.error;
          break;
        case 'workflow.paused':
          execution.status = 'paused';
          execution.current_step = data.current_step;
          toast.warning(`Workflow execution paused: ${data.reason || 'Waiting for input'}`);
          break;
        case 'workflow.resumed':
          execution.status = 'running';
          break;
      }

      newExecutions[existingIndex] = execution;
      return newExecutions;
    });
  };

  const handleResume = async (executionId: string) => {
    try {
      const response = await fetch(`/api/v1/workflows/${executionId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'resume' }) // Add necessary input data here if needed
      });

      if (!response.ok) throw new Error('Failed to resume workflow');
      
      toast.success('Workflow resumed successfully');
    } catch (error) {
      console.error('Resume failed:', error);
      toast.error('Failed to resume workflow');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-blue-500';
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      case 'paused': return 'bg-yellow-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <Clock className="w-4 h-4" />;
      case 'completed': return <CheckCircle className="w-4 h-4" />;
      case 'failed': return <XCircle className="w-4 h-4" />;
      case 'paused': return <Pause className="w-4 h-4" />;
      default: return <AlertCircle className="w-4 h-4" />;
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Live Executions</CardTitle>
        <Badge variant={isConnected ? "default" : "destructive"}>
          {isConnected ? "Connected" : "Disconnected"}
        </Badge>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {executions.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                No active executions
              </div>
            ) : (
              executions.map((exec) => (
                <div key={exec.execution_id} className="flex items-center justify-between p-4 border rounded-lg bg-card">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-full ${getStatusColor(exec.status)} bg-opacity-10 text-white`}>
                      {getStatusIcon(exec.status)}
                    </div>
                    <div>
                      <div className="font-medium">{exec.workflow_id}</div>
                      <div className="text-sm text-muted-foreground">
                        ID: {exec.execution_id.slice(0, 8)} • Steps: {exec.steps_executed}
                      </div>
                      {exec.error && (
                        <div className="text-sm text-red-500 mt-1">{exec.error}</div>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="capitalize">
                      {exec.status}
                    </Badge>
                    
                    {exec.status === 'paused' && (
                      <Button 
                        size="sm" 
                        onClick={() => handleResume(exec.execution_id)}
                        className="bg-yellow-500 hover:bg-yellow-600"
                      >
                        <Play className="w-4 h-4 mr-1" /> Resume
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default WorkflowMonitor;
