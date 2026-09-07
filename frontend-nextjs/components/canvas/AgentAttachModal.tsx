"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Plus, UserPlus } from "lucide-react";
import {
  attachCanvasAgent,
  listAttachableAgents,
  type AgentRegistryEntry,
  type CanvasAgent,
} from "@/lib/canvas-api";
import { createGuidedAgent } from "@/lib/agent-onboarding-api";

/**
 * Attach a hire to a canvas — step 2 of the canvas journey
 * (create → attach → load data). Lists the user's existing agents; "create
 * new" runs the guided creator inline and attaches the result. A
 * pending-approval (HITL) creation can't be attached yet — the user is told
 * to approve it from the Agents page first.
 */
export function AgentAttachModal({
  canvasId,
  open,
  onOpenChange,
  onAttached,
}: {
  canvasId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAttached?: (agent: CanvasAgent) => void;
}) {
  const [agents, setAgents] = useState<AgentRegistryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attachingId, setAttachingId] = useState<string | null>(null);

  // Inline "create a new agent" form
  const [creating, setCreating] = useState(false);
  const [goal, setGoal] = useState("");
  const [creatingAgent, setCreatingAgent] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAgents(await listAttachableAgents());
    } catch (e: any) {
      setError(e?.response?.data?.error?.message || e?.message || "Couldn't load your agents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setCreating(false);
      setGoal("");
      setCreateError(null);
      void loadAgents();
    }
  }, [open, loadAgents]);

  const attach = useCallback(async (agentId: string) => {
    setAttachingId(agentId);
    setError(null);
    try {
      const res = await attachCanvasAgent(canvasId, agentId);
      const attached = res?.agents?.find(a => a.agent_id === agentId);
      if (attached) onAttached?.(attached);
      onOpenChange(false);
    } catch (e: any) {
      setError(e?.response?.data?.error?.message || e?.response?.data?.detail || e?.message || "Couldn't attach the agent.");
    } finally {
      setAttachingId(null);
    }
  }, [canvasId, onAttached, onOpenChange]);

  const handleCreate = useCallback(async () => {
    if (goal.trim().length < 5) {
      setCreateError("Describe the job in a few more words so we can design the right agent.");
      return;
    }
    setCreatingAgent(true);
    setCreateError(null);
    try {
      const res = await createGuidedAgent(goal.trim());
      if ("agent_id" in res && res.agent_id) {
        await attach(res.agent_id);
      } else {
        // HITL: an agent (or governance rule) proposed this hire instead of
        // creating it — nothing to attach until a supervisor approves.
        setCreateError("This agent needs approval before it can be attached — approve it from the Agents page, then attach it here.");
      }
    } catch (e: any) {
      setCreateError(e?.response?.data?.error?.message || e?.message || "Failed to create the agent. Please try again.");
    } finally {
      setCreatingAgent(false);
    }
  }, [goal, attach]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="agent-attach-modal">
        <DialogHeader>
          <DialogTitle>Add an agent to this canvas</DialogTitle>
          <DialogDescription>
            A canvas works through its agent — attach a hire to collaborate in chat, load data, and train it here.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p role="alert" className="text-xs text-red-600 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1">
            {error}
          </p>
        )}

        {creating ? (
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="attach-agent-goal">What should this agent do?</label>
            <Textarea
              id="attach-agent-goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. Track overdue invoices and draft polite follow-ups"
              rows={3}
              autoFocus
            />
            {createError && (
              <p role="alert" className="text-xs text-amber-700 bg-amber-50 dark:bg-amber-900/20 rounded px-2 py-1">
                {createError}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setCreating(false)} disabled={creatingAgent}>
                Back to list
              </Button>
              <Button size="sm" onClick={() => void handleCreate()} disabled={creatingAgent}>
                {creatingAgent ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
                Create &amp; attach
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {loading ? (
              <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" /> Loading your agents…
              </div>
            ) : agents.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                You have no agents yet — create your first one below.
              </p>
            ) : (
              <ul className="max-h-64 overflow-y-auto space-y-1" data-testid="attach-agent-list">
                {agents.map(a => (
                  <li key={a.id}>
                    <button
                      className="w-full flex items-center justify-between gap-2 text-left px-2.5 py-2 rounded-md border hover:bg-accent transition-colors disabled:opacity-50"
                      onClick={() => void attach(a.id)}
                      disabled={attachingId !== null}
                      data-testid={`attach-agent-option-${a.id}`}
                    >
                      <span className="min-w-0">
                        <span className="block text-sm font-medium truncate">{a.name}</span>
                        <span className="block text-xs text-muted-foreground truncate">
                          {a.category || "general"} · {a.status || "student"}
                        </span>
                      </span>
                      <span className="shrink-0 text-xs font-medium text-primary">
                        {attachingId === a.id ? <Loader2 className="h-4 w-4 animate-spin" /> : "Attach"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="pt-1 border-t">
              <Button variant="outline" size="sm" className="w-full mt-1" onClick={() => setCreating(true)}>
                <UserPlus className="h-4 w-4 mr-1" />
                Create a new agent
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
