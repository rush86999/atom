/**
 * Step Controls Component
 *
 * Controls for stepping through workflow execution (step over, into, out, continue, pause).
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  StepForward,
  ArrowRightToLine,
  ArrowDownToLine,
  Play,
  Pause,
  SkipForward,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

interface StepControlsProps {
  sessionId: string | null;
  disabled?: boolean;
  onStep?: (action: string) => void;
}

export const StepControls: React.FC<StepControlsProps> = ({
  sessionId,
  disabled = false,
  onStep,
}) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState<string | null>(null);

  const executeStep = async (action: string) => {
    if (!sessionId || disabled) {
      toast({
        title: 'Not Ready',
        description: 'Please start a debug session first',
        variant: 'error',
      });
      return;
    }

    try {
      setLoading(action);
      const response = await fetch('/api/workflows/debug/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          action: action,
        }),
      });

      if (!response.ok) throw new Error(`Failed to ${action}`);

      const result = await response.json();
      onStep?.(action);

      toast({
        title: action.charAt(0).toUpperCase() + action.slice(1),
        description: `Step ${action} executed successfully`,
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: `Failed to ${action}`,
        variant: 'error',
      });
    } finally {
      setLoading(null);
    }
  };

  const steps = [
    { action: 'step_over', icon: StepForward, label: 'Step Over', description: 'Execute current step and move to next sibling' },
    { action: 'step_into', icon: ArrowRightToLine, label: 'Step Into', description: 'Step into nested workflow' },
    { action: 'step_out', icon: ArrowDownToLine, label: 'Step Out', description: 'Step out to parent workflow' },
    { action: 'continue', icon: Play, label: 'Continue', description: 'Continue until next breakpoint' },
    { action: 'pause', icon: Pause, label: 'Pause', description: 'Pause execution' },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <SkipForward className="h-5 w-5 text-blue-500" />
          Step Controls
        </CardTitle>
        <CardDescription>Control workflow execution step-by-step</CardDescription>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-5 gap-3">
          {steps.map((step) => {
            const Icon = step.icon;
            const isLoading = loading === step.action;

            return (
              <Button
                key={step.action}
                variant="outline"
                disabled={!sessionId || disabled || isLoading}
                onClick={() => executeStep(step.action)}
                className="flex flex-col items-center gap-1 h-20"
                title={step.description}
              >
                <Icon className={`h-5 w-5 ${isLoading ? 'animate-pulse' : ''}`} />
                <span className="text-xs">{step.label}</span>
              </Button>
            );
          })}
        </div>

        {!sessionId && (
          <div className="mt-4 p-3 bg-muted rounded-lg text-center text-sm text-muted-foreground">
            Start a debug session to enable step controls
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default StepControls;
