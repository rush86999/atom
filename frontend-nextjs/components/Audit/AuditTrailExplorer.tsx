'use client';

/**
 * Audit Trail Explorer — the accountant's view of every AI agent decision.
 *
 * Left: list of audited runs (execution_start events) with tool/LLM call
 * counts and outcome. Right: the replayable decision timeline for the
 * selected run — every tool invocation (args + result), every LLM call
 * (model + prompt excerpt), ordered as it happened.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
    Bot,
    ChevronDown,
    ChevronRight,
    CircleDot,
    Clock,
    FileSearch,
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
    AuditSummaryStats,
    ExecutionSummary,
    ExecutionTimeline,
} from "@/lib/audit-api";

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
    if (status === "success") return "default";
    if (["failed", "timeout", "budget_exceeded", "stuck"].includes(status)) return "destructive";
    if (status === "running") return "secondary";
    return "outline";
}

/** One node in the decision timeline. */
function TimelineEvent({
    event,
}: {
    event: ExecutionTimeline["events"][number];
}) {
    const [expanded, setExpanded] = useState(false);

    const isLlm = event.event_type === "llm_call";
    const isTool = (event.action || "").startsWith("tool:");
    const isStart = event.action === "execution_start";
    const isComplete = event.action === "execution_complete";

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
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                        {formatTime(event.timestamp)}
                    </span>
                </button>
                <p className="mt-1 truncate text-sm text-muted-foreground" title={event.description || ""}>
                    {event.description}
                </p>
                {expanded && (
                    <pre
                        className="mt-2 max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed"
                        data-testid="audit-timeline-event-metadata"
                    >
                        {metaEntries.length
                            ? JSON.stringify(Object.fromEntries(metaEntries), null, 2)
                            : "(no metadata)"}
                        {event.error_message ? `\nerror: ${event.error_message}` : ""}
                    </pre>
                )}
                {isStart && !expanded && typeof event.metadata?.task_input === "string" && (
                    <p className="mt-1 truncate text-xs text-muted-foreground italic">
                        task: {String(event.metadata.task_input)}
                    </p>
                )}
            </div>
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
    const [error, setError] = useState<string | null>(null);
    const [agentFilter, setAgentFilter] = useState("");

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
            setError("Failed to load audit trail. Is the backend running?");
        } finally {
            setLoading(false);
        }
    }, []);

    const loadTimeline = useCallback(async (executionId: string) => {
        setTimelineLoading(true);
        try {
            const tl = await auditAPI.timeline(executionId);
            setTimeline(tl);
        } catch (err) {
            console.error("Failed to load timeline", err);
            setTimeline(null);
            setError(`Failed to load timeline for ${executionId}`);
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
        if (selectedId) loadTimeline(selectedId);
        else setTimeline(null);
    }, [selectedId, loadTimeline]);

    const visibleExecutions = agentFilter
        ? executions.filter((e) => (e.agent_id || "").includes(agentFilter))
        : executions;

    return (
        <div className="flex h-full min-h-0 flex-col gap-4" data-testid="audit-trail-explorer">
            {/* Header + summary stats */}
            <div className="flex flex-wrap items-center gap-3">
                <h1 className="flex items-center gap-2 text-lg font-semibold">
                    <FileSearch className="h-5 w-5" />
                    Agent Audit Trail
                </h1>
                <Badge variant="outline">last {stats?.days ?? 7} days</Badge>
                <Button variant="outline" size="sm" onClick={loadOverview} data-testid="audit-refresh">
                    <RefreshCw className="mr-1 h-3.5 w-3.5" />
                    Refresh
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
                    {error}
                </div>
            )}

            <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(380px,2fr)_3fr]">
                {/* Runs list */}
                <Card className="flex min-h-0 flex-col">
                    <CardHeader className="flex-row items-center justify-between space-y-0">
                        <CardTitle className="text-base">Audited Runs</CardTitle>
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
                                No audited agent runs yet. Run an agent and its full decision
                                trail will appear here.
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
                            <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                                <span>{timeline.counts.tool_calls} tool calls</span>
                                <span>{timeline.counts.llm_calls} LLM calls</span>
                                {timeline.counts.failed_events > 0 && (
                                    <span className="text-destructive">
                                        {timeline.counts.failed_events} failures
                                    </span>
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
                        ) : timeline ? (
                            <div className="space-y-3" data-testid="audit-timeline-list">
                                {timeline.execution.status && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <span className="text-muted-foreground">outcome:</span>
                                        <Badge variant={statusVariant(timeline.execution.status)}>
                                            {timeline.execution.status}
                                        </Badge>
                                    </div>
                                )}
                                {timeline.events.length === 0 && (
                                    <div className="p-6 text-center text-sm text-muted-foreground">
                                        This run has an execution record but no per-event audit
                                        trail (it may predate per-event auditing).
                                    </div>
                                )}
                                {timeline.events.map((event) => (
                                    <TimelineEvent key={event.id} event={event} />
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
