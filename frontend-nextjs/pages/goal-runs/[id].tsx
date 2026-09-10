import React, { useState, useEffect, useCallback } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, ArrowLeft, Check, X, Play, Ban, FileText, Sparkles, Info, TrendingUp } from "lucide-react";
import {
    getGoalRun, getGoalRunCanvases, resumeGoalRun, resolveCheckpoint,
    advanceGoalRun, cancelGoalRun, distillGoalRun, setSupervisionMode,
    getPromotionEvidence, getGoal,
    GoalRun, GoalRunCanvas, DecisionEntry, PromotionEvidence, SupervisionMode, Goal,
} from "@/lib/goal-run-api";
import { useUserRole } from "@/lib/user-role";

// Run timeline — the coaching surface (GOAL_RUN_ORCHESTRATION.md §6, §7
// slice 5): the plan, the canvases each step produced, and EVERY decision
// with its rationale. Supervisors coach judgment here: approve or override
// held decisions (an override is a correction — the agent learns instantly),
// resolve process checkpoints (quote approval), advance/cancel. A guidance
// banner interprets the current state so the supervisor never has to guess
// what to do ("nothing silent" — the matching notifications carry the same
// guidance and deep-link here via the bell).

const STEP_KIND_LABEL: Record<string, string> = {
    canvas_work: "Canvas",
    integration_action: "Action",
    human_checkpoint: "Checkpoint",
    wait_for: "Wait",
};

export interface RunGuidance {
    tone: "info" | "action" | "success";
    text: string;
}

/** " Current step: Draft the quote." when the run has a live plan step —
    a long-running run is only legible if the operator can see where it is. */
function stepHint(run: GoalRun): string {
    const step = (run.plan || []).find((s) => s.id === run.cursor);
    return step?.title ? ` Current step: ${step.title}.` : "";
}

/** What the supervisor should know/do RIGHT NOW, per state. */
export function guidanceFor(run: GoalRun): RunGuidance {
    if (run.status === "paused_hitl" || run.pending_decision) {
        return {
            tone: "action",
            text: "Your approval is needed below. Approve to continue — or override with guidance: an override teaches the agent instantly (it becomes a lesson on the very next decision).",
        };
    }
    if (run.status === "waiting") {
        const spec = run.waiting_on as { event?: string; deadline?: string } | null;
        const what = spec?.event === "human_checkpoint"
            ? "your approval at the checkpoint below"
            : `an external event (${spec?.event ?? "…"})`;
        return {
            tone: "info",
            text: `This run is sleeping until ${what}${spec?.deadline ? ` — next wake by ${spec.deadline}` : ""}. Nothing to do right now; you'll be notified when it wakes.`,
        };
    }
    if (run.status === "achieved") {
        return {
            tone: "success",
            text: "Goal achieved. Distill this run into a playbook draft so the whole role learns the path that worked — it queues for review in the Training panel.",
        };
    }
    if (run.status === "cancelled" || run.status === "failed") {
        return {
            tone: "info",
            text: "This run stopped before reaching its goal. The decision log shows the path taken — overrides you made along the way already taught the agent.",
        };
    }
    if (run.supervision_mode === "training") {
        return {
            tone: "action",
            text: "Training mode — every decision this agent makes waits for your approval before it executes. Approve what looks right; override with guidance what doesn't.",
        };
    }
    if (run.supervision_mode === "autonomous") {
        return {
            tone: "info",
            text: `Autonomous mode — the run executes on its own with guardrails only (replan budget, stuck detector, send gates). You'll be notified at checkpoints and on outcome.${stepHint(run)}`,
        };
    }
    if (run.status === "active" && !run.cursor) {
        // A run with no cursor and no plan steps is a dead end the operator
        // must resolve by hand (start=False staging, or a replan that emptied
        // the plan). Say so instead of promising autonomous progress.
        return {
            tone: "action",
            text: "This run is active but has no current step. Use Advance to have the router re-decide, or cancel it.",
        };
    }
    return {
        tone: "info",
        text: `Shadow mode — decisions execute and are logged with their rationale below. Only guardrails (big replans, stuck loops) pause for you.${stepHint(run)}`,
    };
}

const MODES: SupervisionMode[] = ["training", "shadow", "autonomous"];

const MODE_HINT: Record<SupervisionMode, string> = {
    training: "every decision waits for approval",
    shadow: "decisions execute; guardrails pause for you",
    autonomous: "runs alone; checkpoints still notify you",
};

export default function GoalRunDetailPage() {
    const router = useRouter();
    const { id } = router.query;
    const { role, isSupervisor } = useUserRole();
    // Fail-open on unknown role (transient /api/auth/me failure): the
    // backend enforces every action — hiding buttons would just strand the
    // operator mid-coaching.
    const roleKnown = Boolean(role);
    const canAct = !roleKnown || isSupervisor;
    const [run, setRun] = useState<GoalRun | null>(null);
    const [goal, setGoal] = useState<Goal | null>(null);
    const [canvases, setCanvases] = useState<GoalRunCanvas[]>([]);
    const [promotion, setPromotion] = useState<PromotionEvidence | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [guidance, setGuidance] = useState("");
    const [busy, setBusy] = useState(false);

    const load = useCallback(async (silent = false) => {
        if (typeof id !== "string") return;
        try {
            const r = await getGoalRun(id);
            setRun(r);
            setCanvases(await getGoalRunCanvases(id));
            // The goal's TITLE is the run's identity to a human — a UUID is
            // not a goal. Advisory: a goal fetch failure must not hide the run.
            getGoal(r.goal_id)
                .then(setGoal)
                .catch(() => { /* title falls back to the id */ });
            setError(null);
        } catch (e: any) {
            if (!silent) setError(e?.message || "Failed to load run");
        } finally {
            if (!silent) setLoading(false);
        }
    }, [id]);

    useEffect(() => { void load(); }, [load]);

    // A long-running run advances on its own (wake, timer, canvas edit
    // elsewhere). Poll quietly while non-terminal so the timeline — and the
    // finish — are observable without a manual refresh.
    useEffect(() => {
        if (!run || ["achieved", "failed", "cancelled"].includes(run.status)) return;
        const tick = () => {
            if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
            void load(true);
        };
        const timer = setInterval(tick, 10000);
        return () => clearInterval(timer);
    }, [run?.status, load]);

    // Promotion evidence is advisory supervisor material (team_lead+ on the
    // backend) — only fetched for users who can act on it.
    useEffect(() => {
        if (typeof id !== "string" || !run?.agent_id || !canAct) return;
        let cancelled = false;
        getPromotionEvidence(run.agent_id)
            .then((e) => { if (!cancelled) setPromotion(e); })
            .catch(() => { /* advisory only — silence is fine */ });
        return () => { cancelled = true; };
    }, [id, run?.agent_id, canAct]);

    const act = useCallback(async (fn: () => Promise<void>, successMsg?: string) => {
        setBusy(true);
        try {
            await fn();
            if (successMsg) toast.success(successMsg);
            await load();
        } catch (e: any) {
            setError(e?.message || "Action failed");
            toast.error(e?.message || "Action failed");
        } finally {
            setBusy(false);
        }
    }, [load]);

    const handleDistill = useCallback(() => {
        if (typeof id !== "string") return;
        void act(async () => {
            const draft = await distillGoalRun(id);
            toast.success(`Playbook draft "${draft.name}" queued for review in the Training panel`);
        });
    }, [id, act]);

    const handleMode = useCallback((mode: SupervisionMode) => {
        if (typeof id !== "string") return;
        void act(async () => {
            await setSupervisionMode(id, mode);
            toast.success(`Supervision mode set to ${mode}`);
        }, `Supervision mode set to ${mode}`);
    }, [id, act]);

    if (loading) {
        return <div className="container mx-auto py-8 flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading run…
        </div>;
    }
    if (error && !run) {
        return <div className="container mx-auto py-8 text-sm text-destructive">{error}</div>;
    }
    if (!run) return null;

    const pending = run.pending_decision;
    const terminal = ["achieved", "failed", "cancelled"].includes(run.status);
    const pendingCheckpointHitl = run.status === "waiting" &&
        (run.waiting_on as { event?: string; match?: { hitl_id?: string } } | null)?.event === "human_checkpoint"
        ? (run.waiting_on as { match?: { hitl_id?: string } }).match?.hitl_id
        : undefined;

    return (
        <div className="container mx-auto py-8 max-w-4xl" data-testid="goal-run-detail">
            <Head><title>{goal?.title ? `Goal run — ${goal.title}` : `Goal Run ${run.id.slice(0, 8)}`}</title></Head>
            <Button variant="ghost" size="sm" onClick={() => router.push("/goal-runs")} className="mb-4">
                <ArrowLeft className="h-4 w-4" /> All runs
            </Button>

            <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
                <div>
                    <h1 className="text-2xl font-semibold flex items-center gap-2 flex-wrap"
                        data-testid="run-goal-heading">
                        {goal?.title || `Goal ${run.goal_id.slice(0, 8)}…`}
                        <Badge variant="outline">{run.status.replace("_", " ")}</Badge>
                        <Badge variant="outline">{run.supervision_mode}</Badge>
                        {run.role && <Badge variant="outline">{run.role}</Badge>}
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {run.steps_executed} steps · {run.replan_count} replans ·{" "}
                        {run.human_interventions} human interventions
                        {goal?.description ? ` · ${goal.description}` : ""}
                    </p>
                </div>
                <div className="flex gap-2 flex-wrap items-center">
                    {canAct && (
                        <>
                            {!terminal && (
                                <div className="flex items-center gap-1 mr-1" data-testid="mode-switcher">
                                    {MODES.map((m) => (
                                        <Button key={m} size="sm"
                                                variant={run.supervision_mode === m ? "default" : "ghost"}
                                                disabled={busy || run.supervision_mode === m}
                                                title={MODE_HINT[m]}
                                                onClick={() => handleMode(m)}>
                                            {m}
                                        </Button>
                                    ))}
                                </div>
                            )}
                            {terminal && (
                                <Button size="sm" variant="outline" disabled={busy} onClick={handleDistill}
                                        data-testid="distill-button">
                                    <Sparkles className="h-4 w-4" /> Distill to playbook
                                </Button>
                            )}
                            {!terminal && (
                                <>
                                    <Button size="sm" variant="outline" disabled={busy}
                                            onClick={() => void act(() => advanceGoalRun(run.id), "Advanced one decision cycle")}>
                                        <Play className="h-4 w-4" /> Advance
                                    </Button>
                                    <Button size="sm" variant="outline" disabled={busy}
                                            onClick={() => void act(async () => {
                                                await cancelGoalRun(run.id);
                                                toast.success("Run cancelled");
                                                router.push("/goal-runs");
                                            })}>
                                        <Ban className="h-4 w-4" /> Cancel
                                    </Button>
                                </>
                            )}
                        </>
                    )}
                </div>
            </div>

            {roleKnown && !canAct && (
                <div className="mb-6 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
                     data-testid="read-only-banner">
                    Read-only view — approving, overriding, advancing, cancelling and mode
                    changes need a supervisor (team_lead or higher). The run timeline below
                    is the full record of what this agent decided and why.
                </div>
            )}

            {(() => {
                const g = guidanceFor(run);
                const toneClass = g.tone === "action"
                    ? "border-amber-500/50 bg-amber-500/10 text-amber-900 dark:text-amber-200"
                    : g.tone === "success"
                        ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200"
                        : "border-border bg-muted/40 text-muted-foreground";
                return (
                    <div className={`mb-6 flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${toneClass}`}
                         data-testid="run-guidance">
                        <Info className="h-4 w-4 mt-0.5 shrink-0" />
                        <span>{g.text}</span>
                    </div>
                );
            })()}

            {error && <p className="text-sm text-destructive mb-4">{error}</p>}

            {/* Training/shadow checkpoint: the held decision, with rationale. */}
            {pending && (
                <Card className="mb-6 border-primary/50" data-testid="pending-decision">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">Held for your approval — {pending.decision}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <p className="text-sm">{pending.rationale}</p>
                        {canAct && (
                            <>
                                <Textarea
                                    placeholder="Guidance (optional) — overriding teaches the agent instantly"
                                    value={guidance}
                                    onChange={(e) => setGuidance(e.target.value)}
                                    data-testid="guidance-input"
                                />
                                <div className="flex gap-2">
                                    <Button size="sm" disabled={busy}
                                            onClick={() => void act(() => resumeGoalRun(run.id, true), "Approved — the run continues")}>
                                        <Check className="h-4 w-4" /> Approve
                                    </Button>
                                    <Button size="sm" variant="destructive" disabled={busy}
                                            onClick={() => void act(() => resumeGoalRun(run.id, false, guidance), "Overridden — your guidance became the agent's instant lesson")}>
                                        <X className="h-4 w-4" /> Override with guidance
                                    </Button>
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Process-intrinsic checkpoint (e.g. quote approval before send). */}
            {pendingCheckpointHitl && (
                <Card className="mb-6 border-primary/50" data-testid="pending-checkpoint">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">Checkpoint: human approval requested</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {canAct && (
                            <Textarea
                                placeholder="Note (optional) — recorded with your decision"
                                value={guidance}
                                onChange={(e) => setGuidance(e.target.value)}
                            />
                        )}
                        {canAct && (
                            <div className="flex gap-2">
                                <Button size="sm" disabled={busy}
                                        onClick={() => void act(() => resolveCheckpoint(run.id, pendingCheckpointHitl, true, guidance), "Checkpoint approved — the run resumes")}>
                                    <Check className="h-4 w-4" /> Approve
                                </Button>
                                <Button size="sm" variant="destructive" disabled={busy}
                                        onClick={() => void act(() => resolveCheckpoint(run.id, pendingCheckpointHitl, false, guidance), "Checkpoint rejected — the agent re-decides with your note")}>
                                    <X className="h-4 w-4" /> Reject
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Promotion evidence (§3.7B): advisory — a supervisor applies it
                per run with the mode switcher above, never automatic. */}
            {canAct && promotion && (
                <Card className="mb-6" data-testid="promotion-evidence">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <TrendingUp className="h-4 w-4" /> Promotion evidence —
                            recommends <Badge variant="outline">{promotion.recommendation}</Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid sm:grid-cols-2 gap-4 text-sm">
                            {(["training", "shadow"] as const).map((mode) => {
                                const s = promotion.evidence[mode];
                                if (!s) return null;
                                return (
                                    <div key={mode} className="rounded-md border border-border p-3">
                                        <p className="font-medium mb-1 capitalize">{mode} runs</p>
                                        <p className="text-muted-foreground">
                                            {s.runs} runs · {Math.round(s.achieved_ratio * 100)}% achieved ·{" "}
                                            {s.interventions_per_run} interventions/run
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Promotion floor: ≥3 runs · ≥60% achieved · ≤1 intervention/run
                                        </p>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            <div className="grid md:grid-cols-2 gap-6">
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-base">Plan (advisory path)</CardTitle></CardHeader>
                    <CardContent>
                        {run.plan.length === 0 ? (
                            <p className="text-sm text-muted-foreground" data-testid="plan-empty">
                                No plan yet — the router decides the next step as the run advances.
                            </p>
                        ) : (
                        <ol className="space-y-2 text-sm">
                            {run.plan.map((step) => (
                                <li key={step.id} className="flex items-start gap-2">
                                    <span className="font-mono text-xs text-muted-foreground mt-0.5">
                                        {step.id === run.cursor ? "▸" : step.done ? "✓" : "·"}
                                    </span>
                                    <span>
                                        <Badge variant="outline" className="mr-1.5 text-[10px]">
                                            {STEP_KIND_LABEL[step.kind] ?? step.kind}
                                        </Badge>
                                        {step.title}
                                    </span>
                                </li>
                            ))}
                        </ol>
                        )}
                        <h3 className="text-sm font-medium mt-5 mb-2">Canvases produced</h3>
                        {canvases.length === 0 ? (
                            <p className="text-sm text-muted-foreground">None yet.</p>
                        ) : (
                            <ul className="space-y-1.5 text-sm">
                                {canvases.map((c) => (
                                    <li key={c.id}>
                                        <Link href={`/canvas/${c.id}`} className="inline-flex items-center gap-1.5 hover:underline">
                                            <FileText className="h-3.5 w-3.5" /> {c.name}
                                            <span className="text-muted-foreground">({c.canvas_type})</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">Decision log — the path taken</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ol className="space-y-3 text-sm" data-testid="decision-log">
                            {run.decision_log.length === 0 && (
                                <li className="text-muted-foreground">No decisions logged yet.</li>
                            )}
                            {run.decision_log.slice().reverse().map((d: DecisionEntry, i: number) => (
                                <li key={`${d.ts}-${i}`} className="border-l-2 pl-3 border-muted">
                                    <p className="text-xs text-muted-foreground">
                                        {d.ts} · {d.kind}{d.decision ? ` · ${d.decision}` : ""}
                                        {typeof d.confidence === "number" ? ` · ${Math.round(d.confidence * 100)}%` : ""}
                                    </p>
                                    {d.rationale && <p data-testid="decision-rationale">{d.rationale}</p>}
                                    {d.parameter_diff && Object.keys(d.parameter_diff).length > 0 && (
                                        <p className="text-xs text-muted-foreground">
                                            parameters: {Object.keys(d.parameter_diff).join(", ")}
                                        </p>
                                    )}
                                </li>
                            ))}
                        </ol>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
