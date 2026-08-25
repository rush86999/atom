import React, { useCallback, useEffect, useState } from 'react';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Lightbulb, Loader2, Sparkles, GraduationCap, CheckCircle2, Clock } from 'lucide-react';
import {
  AutomationSuggestion,
  GuidedAgentResult,
  GuidedAgentPending,
  createGuidedAgent,
  getAutomationSuggestions,
} from '@/lib/agent-onboarding-api';

interface GuidedAgentCreatorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAgentCreated?: () => void; // e.g. refresh the agent list
  initialGoal?: string | null; // prefilled from a suggestion card
}

/**
 * Employee self-serve agent creation: describe the job in plain language,
 * get an agent. No admin knowledge, no config forms.
 *
 * Shows history-mined automation suggestions as inspiration chips the user
 * can click to prefill the goal. On success, sets expectations up front:
 * the agent starts as a STUDENT and becomes useful as it matures.
 */
export function GuidedAgentCreator({ open, onOpenChange, onAgentCreated, initialGoal }: GuidedAgentCreatorProps) {
  const [goal, setGoal] = useState('');
  const [context, setContext] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [suggestions, setSuggestions] = useState<AutomationSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [result, setResult] = useState<GuidedAgentResult | GuidedAgentPending | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && initialGoal) setGoal(initialGoal);
  }, [open, initialGoal]);

  useEffect(() => {
    if (!open || suggestions.length || suggestionsLoading) return;
    setSuggestionsLoading(true);
    getAutomationSuggestions(3)
      .then((res) => setSuggestions(res?.suggestions ?? []))
      .catch(() => setSuggestions([])) // inspiration is optional — never block creation
      .finally(() => setSuggestionsLoading(false));
  }, [open, suggestions.length, suggestionsLoading]);

  const reset = useCallback(() => {
    setGoal('');
    setContext('');
    setResult(null);
    setError(null);
  }, []);

  const handleClose = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const handleCreate = async () => {
    if (goal.trim().length < 5) {
      setError('Describe the job in a few more words so we can design the right agent.');
      return;
    }
    setIsCreating(true);
    setError(null);
    try {
      const res = await createGuidedAgent(goal.trim(), context.trim() || undefined);
      setResult(res);
      onAgentCreated?.();
    } catch (e: any) {
      const body = e?.response?.data;
      setError(body?.error?.message || body?.detail || body?.message || 'Failed to create the agent. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg" data-testid="guided-agent-creator">
        {!result ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-blue-500" />
                Describe a job — we&apos;ll build the agent
              </DialogTitle>
              <DialogDescription>
                What repetitive task should an agent handle? One or two sentences is enough.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-2">
              <div className="grid gap-2">
                <Label htmlFor="guided-goal">The job</Label>
                <Textarea
                  id="guided-goal"
                  data-testid="guided-goal-input"
                  placeholder="e.g. Watch our vendor invoices and flag anything overdue every morning"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="min-h-[90px]"
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="guided-context">Extra context <span className="text-gray-400 font-normal">(optional)</span></Label>
                <Textarea
                  id="guided-context"
                  data-testid="guided-context-input"
                  placeholder="Tools it should use, examples, things to avoid..."
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  className="min-h-[60px]"
                />
              </div>

              {suggestions.length > 0 && (
                <div className="grid gap-2" data-testid="guided-suggestion-chips">
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <Lightbulb className="h-3.5 w-3.5" />
                    Based on your workspace history, you repeat:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {suggestions.map((s) => (
                      <button
                        key={s.title}
                        type="button"
                        data-testid={`guided-suggestion-chip-${s.title.slice(0, 12)}`}
                        onClick={() => setGoal(s.description || s.title)}
                        className="text-xs px-3 py-1.5 rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-300 text-left"
                        title={s.evidence}
                      >
                        {s.title.slice(0, 60)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <p className="text-sm text-red-600" data-testid="guided-error">{error}</p>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => handleClose(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={isCreating} data-testid="guided-create-button">
                {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create my agent
              </Button>
            </DialogFooter>
          </>
        ) : 'status' in result && result.status === 'pending_approval' ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-amber-500" />
                Waiting for approval
              </DialogTitle>
              <DialogDescription>
                An agent requested this creation but needs a human to approve it first.
              </DialogDescription>
            </DialogHeader>
            <div className="py-2 text-sm text-gray-600 dark:text-gray-300" data-testid="guided-pending">
              <p><span className="font-medium">Reason:</span> {(result as GuidedAgentPending).reason}</p>
              <p className="mt-2">You can review it in the approvals panel. Nothing was created yet.</p>
            </div>
            <DialogFooter>
              <Button onClick={() => handleClose(false)}>Got it</Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                {(result as GuidedAgentResult).name} is here!
              </DialogTitle>
              <DialogDescription>
                Your agent was created — and it starts at the very beginning of its career.
              </DialogDescription>
            </DialogHeader>
            <div className="py-2 space-y-3" data-testid="guided-success">
              <div className="flex items-center gap-2">
                <Badge className="bg-slate-100 text-slate-700 border-slate-300">
                  <GraduationCap className="mr-1 h-3.5 w-3.5" />
                  Student
                </Badge>
                <Badge variant="outline">{(result as GuidedAgentResult).category}</Badge>
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-300 bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 rounded p-3">
                <p className="font-medium text-blue-800 dark:text-blue-200">When will it be useful?</p>
                <p className="mt-1">
                  Right now it watches and learns — from your feedback and from what gets
                  approved in this workspace. With regular use it graduates to an
                  <strong> Intern</strong> (drafts work for you), then <strong>Supervised</strong>
                  (does the work, you approve), and finally <strong>Autonomous</strong> (runs on its own).
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => handleClose(false)} data-testid="guided-done-button">Start teaching it</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
