/**
 * Debug Panel Component
 *
 * Main debugging control panel that orchestrates all debugging features.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Bug,
  Play,
  Pause,
  Square,
  StepForward,
  RotateCcw,
  Settings,
  ChevronDown,
  ChevronRight,
  Trash2,
  Plus,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

interface DebugSession {
  session_id: string;
  workflow_id: string;
  status: string;
  current_step: number;
  current_node_id: string | null;
  session_name: string | null;
  created_at: string;
}

interface DebugPanelProps {
  workflowId: string;
  workflowName: string;
  currentUserId: string;
  onSessionChange?: (session: DebugSession | null) => void;
}

export const DebugPanel: React.FC<DebugPanelProps> = ({
  workflowId,
  workflowName,
  currentUserId,
  onSessionChange,
}) => {
  const { toast } = useToast();

  const [session, setSession] = useState<DebugSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [startingDebug, setStartingDebug] = useState(false);
  const [stopOnEntry, setStopOnEntry] = useState(false);
  const [stopOnExceptions, setStopOnExceptions] = useState(true);
  const [stopOnError, setStopOnError] = useState(true);
  const [showSettings, setShowSettings] = useState(false);

  // Fetch active session
  useEffect(() => {
    fetchActiveSession();
  }, [workflowId]);

  const fetchActiveSession = async () => {
    try {
      const response = await fetch(
        `/api/workflows/${workflowId}/debug/sessions?user_id=${currentUserId}`
      );
      if (response.ok) {
        const sessions = await response.json();
        if (sessions.length > 0) {
          setSession(sessions[0]);
          onSessionChange?.(sessions[0]);
        }
      }
    } catch (err) {
      console.error('Error fetching debug session:', err);
    }
  };

  const startDebugSession = async () => {
    try {
      setStartingDebug(true);
      const response = await fetch(
        `/api/workflows/${workflowId}/debug/sessions?user_id=${currentUserId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workflow_id: workflowId,
            stop_on_entry: stopOnEntry,
            stop_on_exceptions: stopOnExceptions,
            stop_on_error: stopOnError,
          }),
        }
      );

      if (!response.ok) throw new Error('Failed to start debug session');

      const newSession = await response.json();
      setSession(newSession);
      onSessionChange?.(newSession);

      toast({
        title: 'Debug Session Started',
        description: `Session ${newSession.session_id.slice(0, 8)}... created`,
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to start debug session',
        variant: 'error',
      });
    } finally {
      setStartingDebug(false);
    }
  };

  const stopDebugSession = async () => {
    if (!session) return;

    try {
      const response = await fetch(
        `/api/workflows/debug/sessions/${session.session_id}/complete`,
        { method: 'POST' }
      );

      if (!response.ok) throw new Error('Failed to stop debug session');

      setSession(null);
      onSessionChange?.(null);

      toast({
        title: 'Debug Session Stopped',
        description: 'Session completed successfully',
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to stop debug session',
        variant: 'error',
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Bug className="h-5 w-5 text-red-500" />
              Debug Panel
            </CardTitle>
            <CardDescription>{workflowName}</CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {session ? (
              <>
                <Badge variant={session.status === 'running' ? 'default' : 'secondary'}>
                  {session.status}
                </Badge>
                <Button variant="outline" size="sm" onClick={stopDebugSession}>
                  <Square className="h-4 w-4 mr-2" />
                  Stop
                </Button>
              </>
            ) : (
              <Button onClick={startDebugSession} disabled={startingDebug}>
                <Play className="h-4 w-4 mr-2" />
                Start Debugging
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Session Info */}
        {session && (
          <div className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Session ID</span>
              <code className="text-xs">{session.session_id.slice(0, 8)}...</code>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Current Step</span>
              <Badge variant="outline">Step {session.current_step}</Badge>
            </div>
            {session.current_node_id && (
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Current Node</span>
                <code className="text-xs">{session.current_node_id}</code>
              </div>
            )}
          </div>
        )}

        {/* Settings Collapsible */}
        <Collapsible open={showSettings} onOpenChange={setShowSettings}>
          <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium hover:underline">
            <Settings className="h-4 w-4" />
            Debug Settings
            {showSettings ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="stop-on-entry">Stop on Entry</Label>
              <Switch
                id="stop-on-entry"
                checked={stopOnEntry}
                onCheckedChange={setStopOnEntry}
                disabled={!!session}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="stop-on-exceptions">Stop on Exceptions</Label>
              <Switch
                id="stop-on-exceptions"
                checked={stopOnExceptions}
                onCheckedChange={setStopOnExceptions}
                disabled={!!session}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="stop-on-error">Stop on Error</Label>
              <Switch
                id="stop-on-error"
                checked={stopOnError}
                onCheckedChange={setStopOnError}
                disabled={!!session}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
};

export default DebugPanel;
