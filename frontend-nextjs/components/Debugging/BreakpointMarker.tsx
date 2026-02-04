/**
 * Breakpoint Marker Component
 *
 * Manages breakpoints on workflow nodes/edges with visual indicators.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertCircle,
  CheckCircle,
  Circle,
  CircleDot,
  Trash2,
  Plus,
  X,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface Breakpoint {
  breakpoint_id: string;
  node_id: string;
  edge_id: string | null;
  breakpoint_type: string;
  condition: string | null;
  hit_count: number;
  hit_limit: number | null;
  is_active: boolean;
  is_disabled: boolean;
  log_message: string | null;
  created_at: string;
}

interface BreakpointMarkerProps {
  workflowId: string;
  currentUserId: string;
  debugSessionId?: string | null;
  onBreakpointsChange?: (breakpoints: Breakpoint[]) => void;
  nodes: Array<{ id: string; name: string; type: string }>;
}

export const BreakpointMarker: React.FC<BreakpointMarkerProps> = ({
  workflowId,
  currentUserId,
  debugSessionId,
  onBreakpointsChange,
  nodes,
}) => {
  const { toast } = useToast();

  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newBreakpointNode, setNewBreakpointNode] = useState('');
  const [newCondition, setNewCondition] = useState('');
  const [newHitLimit, setNewHitLimit] = useState<string>('');
  const [newLogMessage, setNewLogMessage] = useState('');

  useEffect(() => {
    fetchBreakpoints();
  }, [workflowId, debugSessionId]);

  const fetchBreakpoints = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/workflows/${workflowId}/debug/breakpoints?user_id=${currentUserId}&active_only=true`
      );

      if (response.ok) {
        const data = await response.json();
        setBreakpoints(data);
        onBreakpointsChange?.(data);
      }
    } catch (err) {
      console.error('Error fetching breakpoints:', err);
    } finally {
      setLoading(false);
    }
  };

  const addBreakpoint = async () => {
    if (!newBreakpointNode) {
      toast({
        title: 'Error',
        description: 'Please select a node',
        variant: 'error',
      });
      return;
    }

    try {
      const response = await fetch(
        `/api/workflows/${workflowId}/debug/breakpoints?user_id=${currentUserId}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workflow_id: workflowId,
            node_id: newBreakpointNode,
            debug_session_id: debugSessionId,
            condition: newCondition || null,
            hit_limit: newHitLimit ? parseInt(newHitLimit) : null,
            log_message: newLogMessage || null,
          }),
        }
      );

      if (!response.ok) throw new Error('Failed to add breakpoint');

      await fetchBreakpoints();
      setShowAddForm(false);
      setNewBreakpointNode('');
      setNewCondition('');
      setNewHitLimit('');
      setNewLogMessage('');

      toast({
        title: 'Breakpoint Added',
        description: `Breakpoint added to ${newBreakpointNode}`,
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to add breakpoint',
        variant: 'error',
      });
    }
  };

  const removeBreakpoint = async (breakpointId: string) => {
    try {
      const response = await fetch(
        `/api/workflows/debug/breakpoints/${breakpointId}?user_id=${currentUserId}`,
        { method: 'DELETE' }
      );

      if (!response.ok) throw new Error('Failed to remove breakpoint');

      await fetchBreakpoints();

      toast({
        title: 'Breakpoint Removed',
        description: 'Breakpoint removed successfully',
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to remove breakpoint',
        variant: 'error',
      });
    }
  };

  const toggleBreakpoint = async (breakpointId: string) => {
    try {
      const response = await fetch(
        `/api/workflows/debug/breakpoints/${breakpointId}/toggle?user_id=${currentUserId}`,
        { method: 'PUT' }
      );

      if (!response.ok) throw new Error('Failed to toggle breakpoint');

      await fetchBreakpoints();
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to toggle breakpoint',
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
              <CircleDot className="h-5 w-5 text-red-500" />
              Breakpoints
            </CardTitle>
            <CardDescription>{breakpoints.length} breakpoint{breakpoints.length !== 1 ? 's' : ''}</CardDescription>
          </div>

          <Button size="sm" onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Add Breakpoint Form */}
        {showAddForm && (
          <div className="border rounded-lg p-4 space-y-3 bg-muted">
            <h4 className="font-semibold text-sm">Add Breakpoint</h4>

            <div>
              <Label htmlFor="node-select">Node</Label>
              <select
                id="node-select"
                className="w-full border rounded px-3 py-2 text-sm"
                value={newBreakpointNode}
                onChange={(e) => setNewBreakpointNode(e.target.value)}
              >
                <option value="">Select a node...</option>
                {nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.name} ({node.id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label htmlFor="condition">Condition (Optional)</Label>
              <Input
                id="condition"
                placeholder="e.g., user_id == '123'"
                value={newCondition}
                onChange={(e) => setNewCondition(e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="hit-limit">Hit Limit (Optional)</Label>
              <Input
                id="hit-limit"
                type="number"
                placeholder="Leave empty for unlimited"
                value={newHitLimit}
                onChange={(e) => setNewHitLimit(e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="log-message">Log Message (Optional)</Label>
              <Input
                id="log-message"
                placeholder="Log message instead of stopping"
                value={newLogMessage}
                onChange={(e) => setNewLogMessage(e.target.value)}
              />
            </div>

            <div className="flex gap-2">
              <Button size="sm" onClick={addBreakpoint}>
                <Plus className="h-4 w-4 mr-2" />
                Add
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowAddForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Breakpoints List */}
        {loading ? (
          <div className="text-center py-4 text-muted-foreground">Loading breakpoints...</div>
        ) : breakpoints.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Circle className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No breakpoints set</p>
            <p className="text-sm">Click + to add a breakpoint</p>
          </div>
        ) : (
          <div className="space-y-2">
            {breakpoints.map((bp) => (
              <div
                key={bp.breakpoint_id}
                className={`flex items-center justify-between p-3 border rounded-lg ${
                  bp.is_disabled ? 'opacity-50' : ''
                }`}
              >
                <div className="flex items-center gap-3">
                  {bp.is_disabled ? (
                    <Circle className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-red-500" />
                  )}

                  <div>
                    <p className="font-medium text-sm">{bp.node_id}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      {bp.condition && <span>Cond: {bp.condition}</span>}
                      {bp.hit_limit && <span>Limit: {bp.hit_limit}</span>}
                      {bp.hit_count > 0 && <span>Hits: {bp.hit_count}</span>}
                      {bp.log_message && <span>Log: {bp.log_message}</span>}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleBreakpoint(bp.breakpoint_id)}
                  >
                    {bp.is_disabled ? 'Enable' : 'Disable'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeBreakpoint(bp.breakpoint_id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default BreakpointMarker;
