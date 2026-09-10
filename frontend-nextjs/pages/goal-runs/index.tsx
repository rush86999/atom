import React, { useState, useEffect, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Target, Clock, CheckCircle2, XCircle, PauseCircle } from "lucide-react";
import { listGoalRuns, GoalRun, GoalRunStatus } from "@/lib/goal-run-api";

// GoalRuns index — every run's status at a glance. The run timeline page
// (/goal-runs/[id]) is the coaching surface: plan, canvases per step, and
// every decision with its rationale.

const STATUS_BADGE: Record<GoalRunStatus, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string; icon?: React.ReactNode }> = {
    planning: { variant: "outline" },
    active: { variant: "default" },
    waiting: { variant: "secondary", icon: <Clock className="h-3 w-3" /> },
    paused_hitl: { variant: "destructive", icon: <PauseCircle className="h-3 w-3" /> },
    achieved: { variant: "secondary", icon: <CheckCircle2 className="h-3 w-3" /> },
    failed: { variant: "destructive", icon: <XCircle className="h-3 w-3" /> },
    cancelled: { variant: "outline" },
};

export const waitingLabel = (run: GoalRun): string | null => {
    if (run.status !== "waiting" || !run.waiting_on) return null;
    const spec = run.waiting_on as { event?: string; deadline?: string };
    const what = spec.event === "human_checkpoint" ? "human approval" : (spec.event ?? "event");
    return spec.deadline ? `${what} · until ${spec.deadline}` : what;
};

export default function GoalRunsIndexPage() {
    const [runs, setRuns] = useState<GoalRun[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [includeTerminal, setIncludeTerminal] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setRuns(await listGoalRuns({ includeTerminal }));
        } catch (e: any) {
            setError(e?.message || "Failed to load goal runs");
        } finally {
            setLoading(false);
        }
    }, [includeTerminal]);

    useEffect(() => { void load(); }, [load]);

    return (
        <div className="container mx-auto py-8 max-w-4xl" data-testid="goal-runs-page">
            <Head><title>Goal Runs</title></Head>
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-semibold flex items-center gap-2">
                    <Target className="h-6 w-6" /> Goal Runs
                </h1>
                <Button variant="outline" size="sm" onClick={() => setIncludeTerminal((v) => !v)}>
                    {includeTerminal ? "Hide finished" : "Show finished"}
                </Button>
            </div>

            {loading ? (
                <div className="flex items-center gap-2 text-muted-foreground" data-testid="goal-runs-loading">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                </div>
            ) : error ? (
                <p className="text-sm text-destructive">{error}</p>
            ) : runs.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                    No goal runs yet. A run starts when a role agent begins working a goal —
                    like preparing a quote for a lead across several touch points.
                </p>
            ) : (
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
                                            <span>Goal {run.goal_id.slice(0, 8)}…</span>
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
            )}
        </div>
    );
}
