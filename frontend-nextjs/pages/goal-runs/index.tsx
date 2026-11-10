import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Target, Clock, CheckCircle2, XCircle, PauseCircle, Rocket } from "lucide-react";
import {
    getGoalUtility,
    listGoalRuns,
    listGoals,
    GoalRun,
    GoalRunStatus,
    Goal,
    GoalUtility,
    UtilityMetric,
} from "@/lib/goal-run-api";
import { useUserRole, meetsRole, MEMBER_MIN_LEVEL } from "@/lib/user-role";
import StartGoalRunDialog from "@/components/goals/StartGoalRunDialog";

// GoalRuns index — every run's status at a glance. The run timeline page
// (/goal-runs/[id]) is the working + coaching surface: plan, canvases per
// step, and every decision with its rationale.
//
// 2026-09-10 journey fix: this page was where the journey ended before it
// began — it could only LIST runs (created by hand-rolled HTTP against a
// goal nothing in the UI could create). Now the person doing the work starts
// their own role-based run here, and the list shows the goal's TITLE instead
// of a bare UUID. Business-agnostic: the role comes from the business's own
// agents, not a hardcoded industry.

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

const UTILITY_METRIC_LABELS: Record<UtilityMetric, string> = {
    human_interventions: "Human interventions",
    steps_executed: "Steps executed",
    replan_count: "Replans",
};

const utilityErrorText = (err: unknown): string => {
    const message = (err as { message?: string })?.message;
    return message || "Could not load utility ranking; showing the last known state.";
};

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
    // Role-based, generalized: any member does the everyday work (start and
    // work their OWN role-based run); team_lead+ gets the extra powers; a
    // viewer only reads. Fail-open on unknown role (transient /api/auth/me
    // failure) — the backend enforces.
    const canStart = !role || meetsRole(role, MEMBER_MIN_LEVEL);
    const canSupervise = !role || isSupervisor;
    const [runs, setRuns] = useState<GoalRun[]>([]);
    const [goalTitles, setGoalTitles] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [includeTerminal, setIncludeTerminal] = useState(true);
    const [startOpen, setStartOpen] = useState(false);
    const [utilityByGoal, setUtilityByGoal] = useState<Record<string, GoalUtility>>({});
    const [utilityGoals, setUtilityGoals] = useState<Goal[]>([]);
    const [utilityErrors, setUtilityErrors] = useState<Record<string, string>>({});
    const [utilityLoading, setUtilityLoading] = useState(false);
    const [goalMetadataError, setGoalMetadataError] = useState<string | null>(null);
    const activityRequest = useRef(0);

    const load = useCallback(async (silent = false) => {
        // One generation per Activity load, assigned before any await. A
        // superseded load may finish later, but it cannot write any run/goal/
        // utility/loading/error state over the newer whole-page result.
        const requestId = ++activityRequest.current;
        if (!silent) setLoading(true);
        try {
            const [runsResult, goalsResult] = await Promise.allSettled([
                listGoalRuns({ includeTerminal }),
                listGoals({ includeTerminal: true }),
            ]);
            if (requestId !== activityRequest.current) return;

            if (runsResult.status === "rejected") {
                if (!silent) {
                    setError(runsResult.reason?.message || "Failed to load goal runs");
                }
                return;
            }
            setRuns(runsResult.value);
            setError(null);

            if (goalsResult.status === "rejected") {
                // A metadata failure is not "no goals": preserve known titles
                // and utility state, and surface the distinct failure.
                setGoalMetadataError(
                    "Goal metadata is unavailable; utility targets may be stale.");
                return;
            }
            setGoalMetadataError(null);
            const goals = goalsResult.value;
            setGoalTitles(Object.fromEntries(goals.map((g) => [g.id, g.title])));

            const targetGoals = goals.filter((goal) => goal.utility_target);
            if (!targetGoals.length) {
                setUtilityGoals([]);
                setUtilityByGoal({});
                setUtilityErrors({});
                setUtilityLoading(false);
                return;
            }
            setUtilityLoading(true);
            const settled = await Promise.allSettled(
                targetGoals.map(async (goal) => ({
                    goalId: goal.id,
                    utility: await getGoalUtility(goal.id),
                })),
            );
            if (requestId !== activityRequest.current) return;

            const targetIds = new Set(targetGoals.map((goal) => goal.id));
            const nextErrors: Record<string, string> = {};
            settled.forEach((result, index) => {
                if (result.status === "rejected") {
                    // Preserve the legitimate last known ranking. The UI marks
                    // it stale and never presents the old winner as fresh.
                    nextErrors[targetGoals[index].id] = utilityErrorText(result.reason);
                }
            });
            setUtilityByGoal((previous) => {
                const next: Record<string, GoalUtility> = {};
                targetIds.forEach((goalId) => {
                    if (previous[goalId]) next[goalId] = previous[goalId];
                });
                settled.forEach((result, index) => {
                    const goalId = targetGoals[index].id;
                    if (result.status === "fulfilled") {
                        if (result.value.utility.target) {
                            next[goalId] = result.value.utility;
                        } else {
                            // Authoritative fresh read cleared the target.
                            delete next[goalId];
                        }
                    }
                });
                return next;
            });
            setUtilityGoals((previous) => {
                const next: Goal[] = [];
                targetGoals.forEach((goal, index) => {
                    const result = settled[index];
                    if (result.status === "fulfilled") {
                        if (result.value.utility.target) {
                            next.push({ ...goal, utility_target: result.value.utility.target });
                        }
                    } else {
                        // Failed read: keep the metadata target card and mark
                        // it stale; do not turn a read failure into no-target.
                        next.push(goal);
                    }
                });
                return next;
            });
            setUtilityErrors(nextErrors);
        } catch (e: any) {
            if (requestId !== activityRequest.current) return;
            if (!silent) setError(e?.message || "Failed to load goal runs");
        } finally {
            if (requestId !== activityRequest.current) return;
            if (!silent) setLoading(false);
            setUtilityLoading(false);
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
            <Head><title>Activity</title></Head>
            <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
                <h1 className="text-2xl font-semibold flex items-center gap-2">
                    <Target className="h-6 w-6" /> Activity
                </h1>
                <div className="flex items-center gap-2">
                    <Link
                        href="/execution-history"
                        className="text-sm text-blue-600 hover:underline"
                    >
                        Execution history
                    </Link>
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
                    canSupervise={canSupervise}
                    onStarted={(runId) => { void router.push(`/goal-runs/${runId}`); }}
                />
            )}

            {goalMetadataError ? (
                <p className="mb-3 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800"
                   data-testid="activity-goal-metadata-error">
                    {goalMetadataError}
                </p>
            ) : null}

            {utilityGoals.length ? (
                <div className="mb-6 space-y-3" data-testid="activity-utility-summary">
                    <div>
                        <h2 className="text-sm font-semibold">Goal utility</h2>
                        <p className="text-xs text-muted-foreground">
                            Deterministic ranking of completed runs. Members can read;
                            only a supervisor can change a target on the run detail.
                        </p>
                    </div>
                    {utilityGoals.map((goal) => {
                        const utility = utilityByGoal[goal.id];
                        const target = utility?.target ?? goal.utility_target;
                        const error = utilityErrors[goal.id];
                        const eligible = (utility?.ranking || []).filter((entry) => entry.eligible);
                        const withheld = (utility?.ranking || []).filter((entry) => !entry.eligible);
                        const title = goalTitles[goal.id] || goal.title || `Goal ${goal.id.slice(0, 8)}…`;
                        return (
                            <Card key={goal.id} data-testid={`activity-utility-${goal.id}`}
                                  className={error ? "border-amber-300" : undefined}>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm flex items-center gap-2 flex-wrap">
                                        <Target className="h-4 w-4" /> {title}
                                        {target ? (
                                            <Badge variant="secondary">
                                                {UTILITY_METRIC_LABELS[target.metric]
                                                    || target.metric}
                                            </Badge>
                                        ) : null}
                                        {target ? (
                                            <span className="text-xs font-normal text-muted-foreground">
                                                {target.direction === "minimize"
                                                    ? "lower is better"
                                                    : "higher is better"}
                                            </span>
                                        ) : null}
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-2 text-sm">
                                    {error ? (
                                        <p className="text-xs text-amber-700"
                                           data-testid="activity-utility-error">
                                            {error} Last known ranking is shown below,
                                            not as a fresh result.
                                        </p>
                                    ) : null}
                                    {!utility && utilityLoading ? (
                                        <p className="text-xs text-muted-foreground">
                                            Loading utility ranking…
                                        </p>
                                    ) : null}
                                    {utility ? (
                                        <p className="text-xs text-muted-foreground"
                                           data-testid="activity-utility-count">
                                            {utility.eligible_count} eligible
                                            {utility.winner && !error && !goalMetadataError
                                                ? ` · winner ${utility.winner}`
                                                : ""}
                                        </p>
                                    ) : null}
                                    {eligible.length === 0 && utility ? (
                                        <p className="text-xs text-muted-foreground">
                                            No eligible completed trajectory yet.
                                        </p>
                                    ) : (
                                        <ol className="space-y-1">
                                            {eligible.map((entry) => (
                                                <li key={entry.id}
                                                    className="flex items-center justify-between gap-3 text-xs"
                                                    data-testid="activity-utility-entry">
                                                    <span className="flex items-center gap-2">
                                                        <Badge variant="outline">
                                                            #{entry.rank}
                                                        </Badge>
                                                        <span className="font-mono">
                                                            {entry.id}
                                                        </span>
                                                        {entry.id === utility?.winner && !error
                                                            && !goalMetadataError ? (
                                                            <Badge variant="secondary"
                                                                   data-testid="activity-utility-winner">
                                                                best
                                                            </Badge>
                                                        ) : null}
                                                    </span>
                                                    <span className="text-muted-foreground">
                                                        {target
                                                            ? UTILITY_METRIC_LABELS[target.metric]
                                                            : "utility"}{" "}
                                                        {entry.utility ?? "unknown"}
                                                    </span>
                                                </li>
                                            ))}
                                        </ol>
                                    )}
                                    {withheld.length > 0 ? (
                                        <div className="border-t pt-2"
                                             data-testid="activity-utility-withheld">
                                            <p className="text-xs font-medium text-muted-foreground">
                                                Not ranked
                                            </p>
                                            <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
                                                {withheld.map((entry) => (
                                                    <li key={entry.id}>
                                                        <span className="font-mono">
                                                            {entry.id}
                                                        </span>
                                                        {" · "}
                                                        {entry.reason.replace(/_/g, " ")}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    ) : null}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            ) : null}

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
