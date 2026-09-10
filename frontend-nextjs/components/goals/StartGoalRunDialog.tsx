import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    createGoal, createGoalRun, listGoals, Goal, SupervisionMode,
} from "@/lib/goal-run-api";
import { listAttachableAgents, AgentRegistryEntry } from "@/lib/canvas-api";

// Start-a-goal-run dialog — the missing first link of the journey
// (GOAL_RUN_ORCHESTRATION.md §6 Journey A). Before this, a run could only be
// created by hand-rolled HTTP with a goal_id nothing in the UI could produce
// or show. Now the person doing the work picks an existing goal or writes a
// new one, binds the role agent, and starts — the backend kicks off the first
// loop turn, so the run is working immediately (training mode holds that
// first decision for approval, by design).
//
// Business-type agnostic: "role" is the business function the run belongs to
// and is DERIVED from the business's own agents (their category), with free
// text for anything not yet configured. Sales/quoting is one instance;
// support, claims, recruiting, procurement are the same mechanism. Only
// supervisors may self-promote a run to `autonomous`.

export interface StartGoalRunDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** Called with the new run id after a successful start. */
    onStarted: (runId: string) => void;
    /** team_lead+: unlocks `autonomous` and makes the role optional. */
    canSupervise?: boolean;
}

const MODE_HINT: Record<SupervisionMode, string> = {
    training: "every decision waits for approval",
    shadow: "decisions execute; guardrails pause for approval",
    autonomous: "runs alone; checkpoints still notify",
};

/** Modes a non-supervisor may pick (autonomous is a supervisor act). */
const MODES_FOR_MEMBER: SupervisionMode[] = ["training", "shadow"];

export default function StartGoalRunDialog({
    open, onOpenChange, onStarted, canSupervise = true,
}: StartGoalRunDialogProps) {
    const [goals, setGoals] = useState<Goal[]>([]);
    const [agents, setAgents] = useState<AgentRegistryEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [starting, setStarting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [goalMode, setGoalMode] = useState<"existing" | "new">("existing");
    const [goalId, setGoalId] = useState("");
    const [newTitle, setNewTitle] = useState("");
    const [newDescription, setNewDescription] = useState("");
    const [role, setRole] = useState("");
    const [agentId, setAgentId] = useState("");
    const [mode, setMode] = useState<SupervisionMode>("training");

    // Role suggestions come from the business's OWN configured agents — no
    // hardcoded industry list.
    const roleOptions = useMemo(() => {
        const seen = new Set<string>();
        const out: string[] = [];
        for (const a of agents) {
            const c = (a.category || "").trim();
            if (c && !seen.has(c.toLowerCase())) {
                seen.add(c.toLowerCase());
                out.push(c);
            }
        }
        return out.sort((a, b) => a.localeCompare(b));
    }, [agents]);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [goalRows, agentRows] = await Promise.all([
                listGoals({ includeTerminal: false }),
                listAttachableAgents().catch((): AgentRegistryEntry[] => []),
            ]);
            setGoals(goalRows);
            setAgents(agentRows);
            if (goalRows.length > 0 && !goalId) setGoalId(goalRows[0].id);
            if (goalRows.length === 0) setGoalMode("new");
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load goals");
        } finally {
            setLoading(false);
        }
    }, [goalId]);

    useEffect(() => {
        if (!open) return;
        setNewTitle("");
        setNewDescription("");
        void load();
        // Re-fetch each time the dialog opens; `load` reads goalId only to
        // avoid clobbering a selection, so it is intentionally not a dep loop.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    // Picking an agent fills the role from what that agent IS in this
    // business (its category), unless the user already typed one.
    const handleAgentChange = useCallback((value: string) => {
        setAgentId(value);
        const agent = agents.find((a) => a.id === value);
        const implied = (agent?.category || "").trim();
        if (implied) setRole((current) => current.trim() ? current : implied);
    }, [agents]);

    const modeChoices = canSupervise
        ? (["training", "shadow", "autonomous"] as SupervisionMode[])
        : MODES_FOR_MEMBER;

    const canSubmit = !starting && (
        goalMode === "existing" ? Boolean(goalId) : newTitle.trim().length > 0)
        && (canSupervise || role.trim().length > 0);

    const handleStart = useCallback(async () => {
        if (!canSubmit) return;
        setStarting(true);
        setError(null);
        try {
            let gid = goalId;
            if (goalMode === "new") {
                const goal = await createGoal({
                    title: newTitle.trim(),
                    description: newDescription.trim(),
                });
                gid = goal.id;
            }
            const started = await createGoalRun({
                goal_id: gid,
                agent_id: agentId || undefined,
                role: role.trim() || undefined,
                supervision_mode: mode,
            });
            onOpenChange(false);
            onStarted(started.id);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to start the run");
        } finally {
            setStarting(false);
        }
    }, [canSubmit, goalId, goalMode, newTitle, newDescription, agentId, role,
        mode, onOpenChange, onStarted]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg" id="start-goal-run">
                <DialogHeader>
                    <DialogTitle>Start a goal run</DialogTitle>
                    <DialogDescription>
                        Bind a role agent to a goal and let it work the goal across
                        steps and canvases. The run starts immediately; in training
                        mode its first decision waits for your approval.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2" data-testid="start-goal-run-dialog">
                    <div className="space-y-2">
                        <Label>Goal</Label>
                        <div className="flex gap-2">
                            <Button type="button" size="sm"
                                    variant={goalMode === "existing" ? "default" : "outline"}
                                    onClick={() => setGoalMode("existing")}
                                    disabled={goals.length === 0}>
                                Existing goal
                            </Button>
                            <Button type="button" size="sm"
                                    variant={goalMode === "new" ? "default" : "outline"}
                                    onClick={() => setGoalMode("new")}>
                                New goal
                            </Button>
                        </div>
                        {goalMode === "existing" ? (
                            loading ? (
                                <p className="text-sm text-muted-foreground flex items-center gap-2">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading goals…
                                </p>
                            ) : (
                                <select
                                    aria-label="Goal"
                                    data-testid="goal-select"
                                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                    value={goalId}
                                    onChange={(e) => setGoalId(e.target.value)}
                                >
                                    {goals.map((g) => (
                                        <option key={g.id} value={g.id}>{g.title}</option>
                                    ))}
                                </select>
                            )
                        ) : (
                            <div className="space-y-2">
                                <Input
                                    aria-label="New goal title"
                                    data-testid="new-goal-title"
                                    placeholder="e.g. Prepare a quote for the Acme lead"
                                    value={newTitle}
                                    onChange={(e) => setNewTitle(e.target.value)}
                                />
                                <Textarea
                                    aria-label="New goal description"
                                    placeholder="Optional — what does success look like?"
                                    value={newDescription}
                                    onChange={(e) => setNewDescription(e.target.value)}
                                />
                            </div>
                        )}
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="gr-role">
                                Role{!canSupervise && <span className="text-destructive"> *</span>}
                            </Label>
                            <Input id="gr-role" data-testid="role-input"
                                   list="goal-run-role-options"
                                   placeholder="e.g. Sales, Support, Procurement"
                                   value={role}
                                   onChange={(e) => setRole(e.target.value)} />
                            <datalist id="goal-run-role-options">
                                {roleOptions.map((r) => <option key={r} value={r} />)}
                            </datalist>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="gr-agent">Role agent</Label>
                            <select
                                id="gr-agent"
                                aria-label="Role agent"
                                data-testid="agent-select"
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                value={agentId}
                                onChange={(e) => handleAgentChange(e.target.value)}
                            >
                                <option value="">No agent (I&apos;ll work the canvases)</option>
                                {agents.map((a) => (
                                    <option key={a.id} value={a.id}>{a.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="gr-mode">Supervision mode</Label>
                        <select
                            id="gr-mode"
                            aria-label="Supervision mode"
                            data-testid="mode-select"
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            value={mode}
                            onChange={(e) => setMode(e.target.value as SupervisionMode)}
                        >
                            {modeChoices.map((m) => (
                                <option key={m} value={m}>{m} — {MODE_HINT[m]}</option>
                            ))}
                        </select>
                        {!canSupervise && (
                            <p className="text-xs text-muted-foreground">
                                Autonomous runs need a supervisor. Your run is seeded from
                                your role's approved playbooks.
                            </p>
                        )}
                    </div>

                    {error && (
                        <p role="alert" className="text-sm text-destructive" data-testid="start-error">
                            {error}
                        </p>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={() => onOpenChange(false)}
                            disabled={starting}>
                        Cancel
                    </Button>
                    <Button onClick={() => void handleStart()} disabled={!canSubmit}
                            data-testid="submit-start-run">
                        {starting ? <Loader2 className="h-4 w-4 animate-spin" />
                                  : <Rocket className="h-4 w-4" />}
                        Start run
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
