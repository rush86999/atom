'use client';

/**
 * Audit Trail Explorer — the per-decision record of every AI agent run.
 *
 * Ordinary members see their OWN audited runs (the backend applies one
 * owner-scoped read predicate to all four endpoints); supervisors see their
 * current workspace, never a global all-users feed. This component never
 * guesses authority from client state — the scope label comes from the
 * server's `read_scope` and a 403 is rendered as a permission message, not
 * as "is the backend running?".
 *
 * Default UX stays quiet: the run list + timeline are primary. "View
 * evidence" (expanded metadata) and "Report a problem" are optional. The
 * correction form is inline and prefilled with the event context; submitting
 * records a REQUEST (never an applied/verified repair) and offers a safe,
 * server-validated deep link into an existing governed review surface.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
    Bot,
    ChevronDown,
    ChevronRight,
    CircleDot,
    Clock,
    Download,
    FileSearch,
    Flag,
    Loader2,
    RefreshCw,
    Terminal,
    XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

import {
    auditAPI,
    AuditEvent,
    AuditSummaryStats,
    CorrectionRequestResult,
    CorrectionTarget,
    ExecutionSummary,
    ExecutionTimeline,
    ModelIdentity,
    ReadScope,
    UsageSummary,
    VerificationSummary,
} from "@/lib/audit-api";
import {
    buildAuditEvidenceBundle,
    downloadAuditEvidenceBundle,
} from "@/lib/audit-export";

const REFRESH_MS = 15000;

function formatTime(iso: string | null | undefined): string {
    if (!iso) return "-";
    try {
        return new Date(iso).toLocaleString();
    } catch {
        return iso;
    }
}

function statusVariant(status: string): "default" | "destructive" | "secondary" | "outline" {
    if (status === "success" || status === "completed") return "default";
    if (["failed", "timeout", "budget_exceeded", "stuck"].includes(status)) return "destructive";
    if (status === "running" || status === "partial") return "secondary";
    return "outline";
}

function verificationVariant(
    status: string | undefined,
): "default" | "destructive" | "secondary" | "outline" {
    if (status === "verified") return "default";
    if (status === "failed_verification") return "destructive";
    if (status === "partially_verified") return "secondary";
    return "outline";
}

function verificationLabel(status: string | undefined): string {
    switch (status) {
        case "verified": return "verified (step oracle)";
        case "partially_verified": return "partially verified";
        case "failed_verification": return "failed verification";
        case "unverified": return "unverified";
        case "not_recorded": return "verification not recorded";
        case "unavailable": return "verification unavailable";
        default: return status ? `verification: ${status}` : "verification unknown";
    }
}

function usageLabel(usage: UsageSummary | undefined): string | null {
    if (!usage) return null;
    if (usage.status === "recorded_estimate") {
        return `recorded usage estimate: $${(usage.cost_usd ?? 0).toFixed(4)}`;
    }
    if (usage.status === "partial") {
        return `recorded usage subtotal: $${(usage.cost_usd ?? 0).toFixed(4)} (incomplete)`;
    }
    if (usage.status === "known_free") return "recorded cost: known-free (not an invoice)";
    return "cost unavailable";
}

function describeError(err: unknown, fallback: string): { title: string; detail: string } {
    // Duck-typed first: tests (and bundlers) can load the real module through
    // a mocked namespace, making `instanceof` unreliable across copies.
    const kind = (err as { kind?: string } | null)?.kind;
    if (kind) {
        if (kind === "forbidden") {
            return {
                title: "Not authorized to view this",
                detail:
                    "You can inspect audited work recorded for your own user. " +
                    "Ask a workspace supervisor for broader access.",
            };
        }
        if (kind === "unauthorized") {
            return {
                title: "Your session expired",
                detail: "Sign in again to view the audit trail.",
            };
        }
        if (kind === "not_found") {
            return {
                title: "Not in your authorized scope",
                detail:
                    "This run is not available to you. No data from another user " +
                    "or workspace is shown.",
            };
        }
        if (kind === "network") {
            return {
                title: "Audit service unreachable",
                detail: "Check that the backend is running and your connection is available.",
            };
        }
        if (kind === "invalid") {
            return { title: "Invalid audit request", detail: (err as Error).message };
        }
        if (kind === "server") {
            return {
                title: "Audit service error",
                detail: "The backend returned an error. Try again shortly.",
            };
        }
        return { title: "Audit read failed", detail: (err as Error).message };
    }
    return { title: fallback, detail: "" };
}

function ScopeBadge({ scope }: { scope?: ReadScope | null }) {
    if (!scope) return null;
    return (
        <Badge variant="outline" data-testid="audit-read-scope">
            {scope.kind === "workspace" ? "Workspace runs" : "Your runs"}
        </Badge>
    );
}

/** One node in the decision timeline. */
function TimelineEvent({
    event,
    onReport,
}: {
    event: ExecutionTimeline["events"][number];
    onReport: (event: AuditEvent) => void;
}) {
    const [expanded, setExpanded] = useState(false);

    const isLlm = event.event_type === "llm_call";
    const isTool = (event.action || "").startsWith("tool:");
    const isStart = event.action === "execution_start";
    const isComplete = event.action === "execution_complete";
    const identity: ModelIdentity | null | undefined = event.model_identity;

    const icon = isLlm ? (
        <Bot className="h-4 w-4" />
    ) : isTool ? (
        <Terminal className="h-4 w-4" />
    ) : isComplete ? (
        <CircleDot className="h-4 w-4" />
    ) : (
        <Clock className="h-4 w-4" />
    );

    const metaEntries = Object.entries(event.metadata || {}).filter(
        ([k]) => !["agent_id", "agent_execution_id"].includes(k),
    );

    return (
        <div className="flex gap-3" data-testid="audit-timeline-event">
            <div
                className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${
                    event.success
                        ? "border-border bg-muted text-muted-foreground"
                        : "border-destructive/50 bg-destructive/10 text-destructive"
                }`}
            >
                {icon}
            </div>
            <div className="min-w-0 flex-1 border-b border-border pb-3">
                <button
                    type="button"
                    className="flex w-full items-center gap-2 text-left"
                    onClick={() => setExpanded((v) => !v)}
                    data-testid="audit-timeline-event-toggle"
                >
                    {expanded ? (
                        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    ) : (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    )}
                    <span className="font-medium">{event.action}</span>
                    {!event.success && (
                        <Badge variant="destructive" className="h-5">
                            <XCircle className="mr-1 h-3 w-3" />
                            failed
                        </Badge>
                    )}
                    {event.correction && (
                        <Badge variant="secondary" className="h-5" data-testid="audit-correction-receipt">
                            correction requested — not applied
                        </Badge>
                    )}
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                        {formatTime(event.timestamp)}
                    </span>
                </button>
                <p className="mt-1 truncate text-sm text-muted-foreground" title={event.description || ""}>
                    {event.description}
                </p>
                {isStart && !expanded && typeof event.metadata?.task_input === "string" && (
                    <p className="mt-1 truncate text-xs text-muted-foreground italic">
                        task: {String(event.metadata.task_input)}
                    </p>
                )}
                {event.correction && (
                    <p className="mt-1 text-xs text-amber-600 dark:text-amber-400" data-testid="audit-correction-status">
                        Recorded as a request only — applied: no, verified: no.
                    </p>
                )}
                <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-muted-foreground"
                        onClick={() => onReport(event)}
                        disabled={Boolean(event.correction)}
                        data-testid="audit-report-problem"
                        aria-label={`Report a problem with ${event.action}`}
                    >
                        <Flag className="mr-1 h-3 w-3" />
                        Report a problem
                    </Button>
                </div>
                {expanded && (
                    <div className="mt-2 space-y-2">
                        {identity && (
                            <p
                                className="rounded-md border border-border bg-muted/40 p-2 text-xs"
                                data-testid="audit-model-identity"
                            >
                                {identity.recorded_label ? (
                                    <>
                                        <strong>recorded label:</strong> {identity.recorded_label}{" "}
                                        <span className="text-muted-foreground">
                                            ({identity.label_kind === "router_tier_or_alias"
                                                ? "router-requested label — served model not recorded"
                                                : identity.label_kind})
                                        </span>
                                    </>
                                ) : (
                                    <span>model: unknown — no label recorded</span>
                                )}
                            </p>
                        )}
                        <pre
                            className="max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed"
                            data-testid="audit-timeline-event-metadata"
                        >
                            {metaEntries.length
                                ? JSON.stringify(Object.fromEntries(metaEntries), null, 2)
                                : "(no metadata)"}
                            {event.error_message ? `\nerror: ${event.error_message}` : ""}
                        </pre>
                        {event.correction_targets && event.correction_targets.length > 0 && (
                            <p className="text-xs text-muted-foreground">
                                Linked review channel: {event.correction_targets[0].label}. Opening it
                                changes nothing by itself.
                            </p>
                        )}
                        {event.authority && (
                            <p className="text-xs text-muted-foreground" data-testid="audit-recorded-authority">
                                recorded authority:{" "}
                                {[
                                    event.authority.reviewed_by ? `reviewed by ${String(event.authority.reviewed_by)}` : null,
                                    event.authority.reviewed_at ? `at ${formatTime(String(event.authority.reviewed_at))}` : null,
                                    event.authority.required_role ? `required role ${String(event.authority.required_role)}` : null,
                                ]
                                    .filter(Boolean)
                                    .join(" · ") || "recorded decision details are shown in the metadata"}
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

const REASONS = [
    "Wrong result",
    "Wrong action taken",
    "Missing or wrong evidence",
    "Other",
] as const;

function CorrectionRequestForm({
    event,
    executionId,
    targets,
    onCancel,
}: {
    event: AuditEvent;
    executionId: string;
    targets: CorrectionTarget[];
    onCancel: () => void;
}) {
    const [reason, setReason] = useState<string>(REASONS[0]);
    const [detail, setDetail] = useState("");
    const [channel, setChannel] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<CorrectionRequestResult | null>(null);
    const [error, setError] = useState<{ title: string; detail: string } | null>(null);

    const selectedTarget = targets.find((target) => target.channel === channel) || null;

    const submit = async () => {
        if (!event.agent_id || !event.agent_execution_id) {
            setError({
                title: "No linked correction available",
                detail:
                    "This event has no recorded agent/execution identity, so a linked " +
                    "request cannot be recorded.",
            });
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            const receipt = await auditAPI.correctionRequest({
                agentId: event.agent_id,
                executionId: event.agent_execution_id,
                auditId: event.id,
                description: event.description || undefined,
                eventAction: event.action,
                reason,
                detail: detail.trim() || undefined,
                channel: selectedTarget?.channel || null,
                targetId: selectedTarget?.target_id || null,
            });
            setResult(receipt);
        } catch (err) {
            setError(describeError(err, "Could not record the correction request"));
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div
            className="mb-3 rounded-md border border-border bg-muted/30 p-3"
            data-testid="audit-correction-form"
        >
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <p className="text-sm font-medium">Report a problem</p>
                    <p
                        className="truncate text-xs text-muted-foreground"
                        data-testid="audit-correction-subject"
                        title={event.description || event.action}
                    >
                        {event.action}
                        {event.description ? ` — ${event.description}` : ""}
                        {event.timestamp ? ` · ${formatTime(event.timestamp)}` : ""}
                    </p>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={onCancel}
                    data-testid="audit-correction-cancel"
                >
                    Cancel
                </Button>
            </div>

            {result ? (
                <div className="mt-2 space-y-1" data-testid="audit-correction-result">
                    <p className="text-sm">
                        {result.correction_status === "feedback_recorded_audit_unavailable"
                            ? "Feedback saved, but the audit link could not be recorded."
                            : "Correction request recorded and linked to this event."}
                    </p>
                    <p className="text-xs text-muted-foreground">
                        Requested only — applied: <strong>no</strong>; verified:{" "}
                        <strong>no</strong>.
                    </p>
                    {result.correction_audit_id && (
                        <p className="text-xs text-muted-foreground">
                            Request id: {result.correction_audit_id}
                        </p>
                    )}
                    {!result.correction_audit_id && (
                        <p className="text-xs text-amber-600 dark:text-amber-400">
                            No audit receipt was written; nothing is shown as applied.
                        </p>
                    )}
                    {targets.length > 0 && selectedTarget?.href && (
                        <a
                            className="inline-block text-xs font-medium text-primary underline"
                            href={selectedTarget.href}
                            data-testid="audit-correction-channel-link"
                        >
                            Open {selectedTarget.label} to review a repair
                        </a>
                    )}
                    {targets.length === 0 && (
                        <p className="text-xs text-muted-foreground">
                            No supported repair channel is linked to this event. The request is
                            recorded for review; nothing is changed automatically.
                        </p>
                    )}
                </div>
            ) : (
                <div className="mt-2 space-y-2">
                    <label className="block text-xs font-medium" htmlFor="audit-correction-reason">
                        What is wrong?
                    </label>
                    <select
                        id="audit-correction-reason"
                        className="h-8 w-full rounded-md border border-border bg-background px-2 text-sm"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        data-testid="audit-correction-reason"
                    >
                        {REASONS.map((value) => (
                            <option key={value} value={value}>
                                {value}
                            </option>
                        ))}
                    </select>
                    <Input
                        aria-label="Correction detail (optional)"
                        placeholder="Optional detail — no need to re-enter the task"
                        value={detail}
                        onChange={(e) => setDetail(e.target.value)}
                        data-testid="audit-correction-detail"
                    />
                    {targets.length > 0 && (
                        <div>
                            <label
                                className="block text-xs font-medium"
                                htmlFor="audit-correction-channel"
                            >
                                Repair review channel (optional)
                            </label>
                            <select
                                id="audit-correction-channel"
                                className="h-8 w-full rounded-md border border-border bg-background px-2 text-sm"
                                value={channel}
                                onChange={(e) => setChannel(e.target.value)}
                                data-testid="audit-correction-channel"
                            >
                                <option value="">None — record the request only</option>
                                {targets.map((target) => (
                                    <option key={`${target.channel}:${target.target_id}`} value={target.channel}>
                                        {target.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
                    {error && (
                        <div
                            className="rounded-md border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive"
                            data-testid="audit-correction-error"
                        >
                            <strong>{error.title}.</strong> {error.detail}
                        </div>
                    )}
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            onClick={submit}
                            disabled={submitting}
                            data-testid="audit-correction-submit"
                        >
                            {submitting && <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />}
                            Record request
                        </Button>
                        <span className="text-[11px] text-muted-foreground">
                            This records a request only. Nothing is applied or verified.
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}

export default function AuditTrailExplorer() {
    const [stats, setStats] = useState<AuditSummaryStats | null>(null);
    const [executions, setExecutions] = useState<ExecutionSummary[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [timeline, setTimeline] = useState<ExecutionTimeline | null>(null);
    const [loading, setLoading] = useState(true);
    const [timelineLoading, setTimelineLoading] = useState(false);
    const [error, setError] = useState<{ title: string; detail: string } | null>(null);
    const [timelineError, setTimelineError] = useState<{ title: string; detail: string } | null>(null);
    const [agentFilter, setAgentFilter] = useState("");
    const [reporting, setReporting] = useState<{ event: AuditEvent; executionId: string } | null>(
        null,
    );

    const loadOverview = useCallback(async () => {
        try {
            setError(null);
            const [summary, execs] = await Promise.all([
                auditAPI.summary(7),
                auditAPI.executions(undefined, 100),
            ]);
            setStats(summary);
            setExecutions(execs.items);
        } catch (err) {
            console.error("Failed to load audit overview", err);
            setError(describeError(err, "Failed to load the audit trail"));
        } finally {
            setLoading(false);
        }
    }, []);

    const loadTimeline = useCallback(async (executionId: string) => {
        setTimelineLoading(true);
        setTimelineError(null);
        try {
            const tl = await auditAPI.timeline(executionId);
            setTimeline(tl);
        } catch (err) {
            console.error("Failed to load timeline", err);
            setTimeline(null);
            setTimelineError(describeError(err, "Failed to load this run's timeline"));
        } finally {
            setTimelineLoading(false);
        }
    }, []);

    useEffect(() => {
        loadOverview();
        const interval = setInterval(loadOverview, REFRESH_MS);
        return () => clearInterval(interval);
    }, [loadOverview]);

    useEffect(() => {
        setReporting(null);
        if (selectedId) loadTimeline(selectedId);
        else setTimeline(null);
    }, [selectedId, loadTimeline]);

    const visibleExecutions = agentFilter
        ? executions.filter((e) => (e.agent_id || "").includes(agentFilter))
        : executions;

    const scope = stats?.read_scope || timeline?.read_scope || null;
    const executionUsage = timeline?.execution?.usage;
    const executionVerification: VerificationSummary | undefined =
        timeline?.execution?.verification;
    const correctionTargets = reporting?.event.correction_targets?.length
        ? reporting.event.correction_targets
        : timeline?.execution?.correction_targets || [];

    const downloadEvidence = () => {
        if (!timeline) return;
        const bundle = buildAuditEvidenceBundle(timeline, {
            appVersion: process.env.NEXT_PUBLIC_APP_VERSION || "unknown",
        });
        downloadAuditEvidenceBundle(bundle);
    };

    return (
        <div className="flex h-full min-h-0 flex-col gap-4" data-testid="audit-trail-explorer">
            {/* Header + summary stats */}
            <div className="flex flex-wrap items-center gap-3">
                <h1 className="flex items-center gap-2 text-lg font-semibold">
                    <FileSearch className="h-5 w-5" />
                    Audit Trail
                </h1>
                <Badge variant="outline">last {stats?.days ?? 7} days</Badge>
                <ScopeBadge scope={scope} />
                <Button variant="outline" size="sm" onClick={loadOverview} data-testid="audit-refresh">
                    <RefreshCw className="mr-1 h-3.5 w-3.5" />
                    Refresh
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={downloadEvidence}
                    disabled={!timeline}
                    title="Download a bounded JSON copy of the authorized rows for the selected run"
                    data-testid="audit-download-evidence"
                >
                    <Download className="mr-1 h-3.5 w-3.5" />
                    Download evidence
                </Button>
                <div className="ml-auto flex gap-4 text-sm text-muted-foreground" data-testid="audit-summary-stats">
                    <span>
                        <strong className="text-foreground">{stats?.total_events ?? "–"}</strong> events
                    </span>
                    <span>
                        <strong className="text-foreground">{stats?.executions_tracked ?? "–"}</strong> runs
                    </span>
                    <span>
                        <strong className="text-foreground">{stats?.distinct_agents ?? "–"}</strong> agents
                    </span>
                    {stats?.success_rate != null && (
                        <span>
                            <strong
                                className={
                                    stats.success_rate >= 95
                                        ? "text-foreground"
                                        : "text-destructive"
                                }
                            >
                                {stats.success_rate}%
                            </strong>{" "}
                            success
                        </span>
                    )}
                </div>
            </div>

            {error && (
                <div
                    className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
                    data-testid="audit-error"
                >
                    <p className="font-medium">{error.title}</p>
                    {error.detail && <p className="mt-1 text-xs">{error.detail}</p>}
                </div>
            )}

            <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(380px,2fr)_3fr]">
                {/* Runs list */}
                <Card className="flex min-h-0 flex-col">
                    <CardHeader className="flex-row items-center justify-between space-y-0">
                        <CardTitle className="text-base">
                            {scope?.kind === "workspace" ? "Workspace Runs" : "Your Runs"}
                        </CardTitle>
                        <Input
                            placeholder="Filter by agent id…"
                            value={agentFilter}
                            onChange={(e) => setAgentFilter(e.target.value)}
                            className="h-8 w-48"
                            data-testid="audit-agent-filter"
                        />
                    </CardHeader>
                    <CardContent className="min-h-0 flex-1 overflow-y-auto">
                        {loading ? (
                            <div className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Loading audit trail…
                            </div>
                        ) : visibleExecutions.length === 0 ? (
                            <div className="p-6 text-center text-sm text-muted-foreground">
                                {error ? (
                                    "No audited runs can be shown for this account."
                                ) : (
                                    <>
                                        No audited agent runs yet. Run an agent and its full decision
                                        trail will appear here.
                                    </>
                                )}
                            </div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Run</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead className="text-right">Tools</TableHead>
                                        <TableHead className="text-right">LLM</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {visibleExecutions.map((exec) => (
                                        <TableRow
                                            key={exec.execution_id || exec.started_at}
                                            className={`cursor-pointer ${
                                                selectedId === exec.execution_id ? "bg-muted" : ""
                                            }`}
                                            onClick={() => setSelectedId(exec.execution_id)}
                                            data-testid="audit-run-row"
                                        >
                                            <TableCell className="max-w-[180px]">
                                                <div className="truncate font-medium" title={exec.agent_id || ""}>
                                                    {exec.agent_id || "(unknown agent)"}
                                                </div>
                                                <div className="truncate text-xs text-muted-foreground">
                                                    {formatTime(exec.started_at)}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant={statusVariant(exec.status)}>
                                                    {exec.status}
                                                </Badge>
                                                {exec.failed_events > 0 && (
                                                    <div className="mt-1 text-xs text-destructive">
                                                        {exec.failed_events} failed event
                                                        {exec.failed_events > 1 ? "s" : ""}
                                                    </div>
                                                )}
                                                {exec.usage && (
                                                    <div
                                                        className="mt-1 text-[11px] text-muted-foreground"
                                                        data-testid="audit-run-usage"
                                                    >
                                                        {usageLabel(exec.usage)}
                                                    </div>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-right">{exec.tool_calls}</TableCell>
                                            <TableCell className="text-right">{exec.llm_calls}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>

                {/* Decision timeline */}
                <Card className="flex min-h-0 flex-col">
                    <CardHeader>
                        <CardTitle className="text-base">
                            {selectedId ? `Decision Timeline — ${selectedId}` : "Decision Timeline"}
                        </CardTitle>
                        {timeline?.found_events && (
                            <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                                <span>{timeline.counts.tool_calls} tool calls</span>
                                <span>{timeline.counts.llm_calls} LLM calls</span>
                                {timeline.counts.failed_events > 0 && (
                                    <span className="text-destructive">
                                        {timeline.counts.failed_events} failures
                                    </span>
                                )}
                                <span data-testid="audit-usage-status">
                                    {usageLabel(executionUsage) || "cost unavailable"}
                                </span>
                                {executionVerification && (
                                    <Badge
                                        variant={verificationVariant(executionVerification.status)}
                                        data-testid="audit-verification-badge"
                                        title={executionVerification.note}
                                    >
                                        {verificationLabel(executionVerification.status)}
                                    </Badge>
                                )}
                            </div>
                        )}
                    </CardHeader>
                    <CardContent className="min-h-0 flex-1 overflow-y-auto">
                        {!selectedId ? (
                            <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
                                Select a run to replay every decision the agent made.
                            </div>
                        ) : timelineLoading ? (
                            <div className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Loading timeline…
                            </div>
                        ) : timelineError ? (
                            <div
                                className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
                                data-testid="audit-timeline-error"
                            >
                                <p className="font-medium">{timelineError.title}</p>
                                {timelineError.detail && (
                                    <p className="mt-1 text-xs">{timelineError.detail}</p>
                                )}
                            </div>
                        ) : timeline ? (
                            <div className="space-y-3" data-testid="audit-timeline-list">
                                {timeline.execution.status && (
                                    <div className="flex flex-wrap items-center gap-2 text-sm">
                                        <span className="text-muted-foreground">outcome:</span>
                                        <Badge variant={statusVariant(timeline.execution.status)}>
                                            {timeline.execution.status}
                                        </Badge>
                                        <span className="text-xs text-muted-foreground">
                                            {timeline.execution.outcome?.note ||
                                                "Recorded run status; not independently re-verified."}
                                        </span>
                                    </div>
                                )}
                                {timeline.execution.model_identity && (
                                    <p
                                        className="text-xs text-muted-foreground"
                                        data-testid="audit-execution-model-identity"
                                    >
                                        {timeline.execution.model_identity.resolved_models.length > 0 ? (
                                            <>
                                                recorded served model(s):{" "}
                                                {timeline.execution.model_identity.resolved_models.join(", ")}
                                            </>
                                        ) : (
                                            "served model: unknown — only the recorded label is available"
                                        )}
                                        {timeline.execution.model_identity.recorded_llm_call_labels.length > 0 && (
                                            <>
                                                {" "}· LLM-call labels:{" "}
                                                {timeline.execution.model_identity.recorded_llm_call_labels.join(", ")}
                                            </>
                                        )}
                                    </p>
                                )}
                                {reporting && (
                                    <CorrectionRequestForm
                                        event={reporting.event}
                                        executionId={reporting.executionId}
                                        targets={correctionTargets}
                                        onCancel={() => setReporting(null)}
                                    />
                                )}
                                {timeline.events.length === 0 && (
                                    <div className="p-6 text-center text-sm text-muted-foreground">
                                        This run has an execution record but no per-event audit
                                        trail (it may predate per-event auditing).
                                    </div>
                                )}
                                {timeline.events.map((event) => (
                                    <TimelineEvent
                                        key={event.id}
                                        event={event}
                                        onReport={(subject) =>
                                            setReporting({
                                                event: subject,
                                                executionId: timeline.execution_id,
                                            })
                                        }
                                    />
                                ))}
                            </div>
                        ) : (
                            <div className="p-6 text-center text-sm text-muted-foreground">
                                No timeline available.
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
