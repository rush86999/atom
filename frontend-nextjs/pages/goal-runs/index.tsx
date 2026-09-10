import React, { useState, useEffect, useCallback, useMemo } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Target, Clock, CheckCircle2, XCircle, PauseCircle, Rocket } from "lucide-react";
import { listGoalRuns, listGoals, GoalRun, GoalRunStatus, Goal } from "@/lib/goal-run-api";
import { useUserRole } from "@/lib/user-role";
import StartGoalRunDialog from "@/components/goals/StartGoalRunDialog";

// GoalRuns index — every run's status at a glance. The run timeline page
// (/goal-runs/[id]) is the coaching surface: plan, canvases per step, and
// every decision with its rationale.
//
// 2026-09-10 journey fix: this page was where the journey ended before it
// began — it could only LIST runs (created by hand-rolled HTTP against a
// goal nothing in the UI could create). Now supervisors start a run from
// here and the list shows the goal's TITLE instead of a bare UUID.

const STATUS_BADGE: Record<GoalRunStatus, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string; icon?: React.ReactNode }> = {
    planning: { variant: "outline" },
    active: { variant: "default" },
    waiting: { variant: "secondary", icon: <Clock className="h-3 w-3" /> },
    paused_hitl: { variant: "destructive", icon: <PauseCircle className="h-3 w-3" /> },
    achieved: { variant: "secondary", icon: <CheckCircle2 className="h-3 w-3" /> },
    failed: { variant: "destructive", icon: <XCircle className="h-3 w-3" /> },
    cancelled: { variant: "outline" },
};

const TERMINAL: GoalRunStatus[] = ["achieved", "failed", "cancelled"];

/** "email_reply" → "email reply" for the waiting badge. */
const prettyEvent = (event?: string) =>
    (event ?? "event").replace(/_/g, " ");

export const waitingLabel = (run: GoalRun): string | null => {
    if (run.status !== "waiting" || !run.waiting_on) return null;
    const spec = run.waiting_on as { event?: string; deadline?: string };
    const what = spec.event === "human_checkpoint" ? "human approval" : prettyEvent(spec.event);
    if (!spec.deadline) return what;
    const at = new Date(spec.deadline);
    const when = isNaN(at.getTime())
        ? spec.deadline
        : at.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    return `${what} · until ${when}`;
};

export default function GoalRunsIndexPage() {
    const router = useRouter();
    const { role, isSupervisor } = useUserRole();
    // Fail-open on unknown role (transient /api/auth/me failure): the backend
    // enforces every action; hiding the start button would just strand the
    // operator. Known non-supervisors never see it (post-click 403s).
    const canStart = !role || isSupervisor;
    const [runs, setRuns] = useState<GoalRun[]>([]);
    const [goalTitles, setGoalTitles] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [includeTerminal, setIncludeTerminal] = useState(true);
    const [startOpen, setStartOpen] = useState(false);

    const load = useCallback(async (silent = false) => {
        if (!silent) setLoading(true);
        try {
            const [rows, goals] = await Promise.all([
                listGoalRuns({ includeTerminal }),
                listGoals({ includeTerminal: true }).catch((): Goal[] => []),
            ]);
            setRuns(rows);
            setGoalTitles(Object.fromEntries(goals.map((g) => [g.id, g.title])));
            setError(null);
        } catch (e: any) {
            if (!silent) setError(e?.message || "Failed to load goal runs");
        } finally {
            if (!silent) setLoading(false);
        }
    }, [includeTerminal]);

    useEffect(() => { void load(); }, [load]);

    // Long-running runs change on their own (a wake, a timer, an approval
    // elsewhere). Poll quietly while the tab is visible so "finish" is
    // actually observable without a manual refresh.
    useEffect(() => {
        const tick = () => {
            if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
            void load(true);
        };
        const timer = setInterval(tick, 15000);
        return () => clearInterval(timer);
    }, [load]);

    const goalLabel = useCallback((run: GoalRun) =>
        goalTitles[run.goal_id] || `Goal ${run.goal_id.slice(0, 8)}…`,
        [goalTitles]);

    const activeCount = useMemo(
        () => runs.filter((r) => !TERMINAL.includes(r.status)).length, [runs]);

    return (
        <div className="container mx-auto py-8 max-w-4xl" data-testid="goal-runs-page">
            <Head><title>Goal Runs</title></Head>
            <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
                <h1 className="text-2xl font-semibold flex items-center gap-2">
                    <Target className="h-6 w-6" /> Goal Runs
                </h1>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => setIncludeTerminal((v) => !v)}>
                        {includeTerminal ? "Hide finished" : "Show finished"}
                    </Button>
                    {canStart && (
                        <Button size="sm" onClick={() => setStartOpen(true)}
                                data-testid="new-goal-run">
                            <Rocket className="h-4 w-4" /> New goal run
                        </Button>
                    )}
                </div>
            </div>

            {canStart && (
                <StartGoalRunDialog
                    open={startOpen}
                    onOpenChange={setStartOpen}
                    onStarted={(runId) => { void router.push(`/goal-runs/${runId}`); }}
                />
            )}

            {loading ? (
                <div className="flex items-center gap-2 text-muted-foreground" data-testid="goal-runs-loading">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                </div>
            ) : error ? (
                <p className="text-sm text-destructive">{error}</p>
            ) : runs.length === 0 ? (
                <div className="text-sm text-muted-foreground" data-testid="goal-runs-empty">
                    <p>
                        No goal runs yet. Start one and a role agent works the goal across
                        several touch points — like preparing a quote for a lead over days.
                    </p>
                    {canStart && (
                        <Button size="sm" className="mt-3" onClick={() => setStartOpen(true)}>
                            <Rocket className="h-4 w-4" /> Start your first run
                        </Button>
                    )}
                </div>
            ) : (
                <>
                    <p className="text-xs text-muted-foreground mb-3" data-testid="goal-runs-summary">
                        {activeCount} active · {runs.length - activeCount} finished
                    </p>
                    <div className="grid gap-3" data-testid="goal-runs-list">
                        {runs.map((run) => {
                            const badge = STATUS_BADGE[run.status] ?? STATUS_BADGE.planning;
                            const waiting = waitingLabel(run);
                            return (
                                <Link key={run.id} href={`/goal-runs/${run.id}`} className="block">
                                    <Card className="hover:border-primary/50 transition-colors">
                                        <CardHeader className="pb-2">
                                            <CardTitle className="text-base flex items-center gap-2 flex-wrap">
                                                <Badge variant={badge.variant} className={badge.className}>
                                                    {badge.icon}{run.status.replace("_", " ")}
                                                </Badge>
                                                <span data-testid="run-goal-title">{goalLabel(run)}</span>
                                                {run.role && <Badge variant="outline">{run.role}</Badge>}
                                                {run.supervision_mode !== "shadow" && (
                                                    <Badge variant="outline">{run.supervision_mode}</Badge>
                                                )}
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="text-sm text-muted-foreground">
                                            {waiting && (
                                                <p data-testid="waiting-badge">Waiting on: {waiting}</p>
                                            )}
                                            <p>
                                                {run.steps_executed} step{run.steps_executed === 1 ? "" : "s"} ·{" "}
                                                {run.replan_count} replan{run.replan_count === 1 ? "" : "s"} ·{" "}
                                                {run.decision_log.length} logged decisions
                                            </p>
                                        </CardContent>
                                    </Card>
                                </Link>
                            );
                        })}
                    </div>
                </>
            )}
        </div>
    );
}
