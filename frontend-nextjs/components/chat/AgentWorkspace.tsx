'use client';

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Brain, ListTodo, Globe, AlertTriangle, Trash2, Maximize2, Minimize2,
    ThumbsUp, ThumbsDown, ChevronDown, ChevronRight, Eye, EyeOff, Loader2,
    MessageSquare, CircleCheck, CircleX, PanelRightClose,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ArtifactSidebar } from "./ArtifactSidebar";
import { CanvasHost } from "./canvas-host";
import {
    fetchSessionTrace, submitStepFeedback, TraceRun,
} from "@/lib/agent-trace-api";

interface AgentStep {
    step: number;
    thought?: string;
    action?: string;
    action_input?: string;
    observation?: string;
    step_type?: string;
    confidence?: number;
    verified?: string;
    duration_ms?: number;
    resolved_model?: string;
    timestamp?: string;
    execution_id?: string | null;
}

type FeedbackType = "thumbs_up" | "thumbs_down";

interface AgentRun {
    /** Persisted execution id; "live" is the pseudo-run for legacy payloads. */
    executionId: string;
    agentId?: string;
    status: "running" | "success" | "failed" | "completed" | "unknown";
    steps: AgentStep[];
    startedAt?: string;
    inputSummary?: string;
    fromHistory?: boolean;
    /** step_number -> submitted feedback (optimistic local state) */
    stepFeedback: Record<number, FeedbackType>;
    runFeedback?: FeedbackType | null;
}

interface AgentWorkspaceProps {
    sessionId: string | null;
    initialAgentId?: string | null;
    /** Rail mode: the panel collapses to a slim activity strip (stays mounted). */
    collapsed?: boolean;
    onToggleCollapsed?: () => void;
    /** Fires on any step arrival or run start (auto-show trigger). */
    onAgentActivity?: (kind: "step" | "run_start") => void;
    /** Fires when a run reaches a terminal state (auto-hide trigger). */
    onRunSettled?: () => void;
    /** Fires on clicks inside the panel (cancels the auto-hide timer). */
    onUserInteraction?: () => void;
    /** Auto-hide preference (owned by the page; persisted to localStorage). */
    autoHide?: boolean;
    onAutoHideToggle?: (enabled: boolean) => void;
}

function runStatusFromWire(status?: string): AgentRun["status"] {
    switch ((status || "").toLowerCase()) {
        case "running": return "running";
        case "success": return "success";
        case "failed": return "failed";
        case "completed": return "completed";
        default: return "unknown";
    }
}

function runFromHistory(run: TraceRun): AgentRun {
    const stepFeedback: Record<number, FeedbackType> = {};
    run.steps.forEach((s) => {
        if (s.feedback_score === 1) stepFeedback[s.step_number] = "thumbs_up";
        if (s.feedback_score === -1) stepFeedback[s.step_number] = "thumbs_down";
    });
    return {
        executionId: run.execution_id,
        agentId: run.agent_id ?? undefined,
        // backend persists "completed"; treat it as a settled success
        status: runStatusFromWire(
            run.status === "completed" ? "success" : run.status || undefined
        ),
        steps: run.steps.map((s) => ({
            step: s.step_number,
            thought: s.thought ?? undefined,
            action: s.action ?? undefined,
            action_input: s.action_input ?? undefined,
            observation: s.observation ?? undefined,
            step_type: s.step_type ?? undefined,
            confidence: s.confidence ?? undefined,
            verified: s.verified ?? undefined,
            duration_ms: s.duration_ms ?? undefined,
            resolved_model: s.resolved_model ?? undefined,
            timestamp: s.timestamp ?? undefined,
        })),
        startedAt: run.started_at ?? undefined,
        inputSummary: run.input_summary ?? undefined,
        fromHistory: true,
        stepFeedback,
        runFeedback: null,
    };
}

const AgentWorkspace: React.FC<AgentWorkspaceProps> = ({
    sessionId,
    initialAgentId,
    collapsed = false,
    onToggleCollapsed,
    onAgentActivity,
    onRunSettled,
    onUserInteraction,
    autoHide,
    onAutoHideToggle,
}) => {
    const [runs, setRuns] = useState<AgentRun[]>([]);
    const [agentStatus, setAgentStatus] = useState<string>("idle");
    const [activeAgentId, setActiveAgentId] = useState<string | null>(initialAgentId || null);
    const [activeTab, setActiveTab] = useState<string>("tasks");
    const [isMaximized, setIsMaximized] = useState(false);
    const [unreadCount, setUnreadCount] = useState(0);
    const [expandedHistory, setExpandedHistory] = useState<Set<string>>(new Set());
    const [commentTarget, setCommentTarget] = useState<{ runId: string; stepNumber: number } | null>(null);
    const [commentText, setCommentText] = useState("");
    const [traceLoading, setTraceLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Update active agent if initial changes (e.g. navigation)
    useEffect(() => {
        if (initialAgentId) setActiveAgentId(initialAgentId);
    }, [initialAgentId]);

    // Subscribe to workspace events
    const { lastMessage, isConnected } = useWebSocket({
        initialChannels: ["workspace:default"]
    });

    // ── Trace history restore ────────────────────────────────────────────
    // Load persisted runs for the session so the trace survives reloads;
    // live events merge into the same run keyed by execution id.
    useEffect(() => {
        let cancelled = false;
        if (!sessionId || sessionId === "new" || sessionId === "unknown") {
            setRuns([]);
            return;
        }
        setTraceLoading(true);
        fetchSessionTrace(sessionId)
            .then((res) => {
                if (cancelled) return;
                const history = res.runs.map(runFromHistory);
                setRuns((prev) => {
                    const live = prev.filter(
                        (r) => !history.some((h) => h.executionId === r.executionId)
                    );
                    return [...history, ...live];
                });
            })
            .catch(() => {
                // history restore is best-effort; live events still work
            })
            .finally(() => {
                if (!cancelled) setTraceLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    // ── Event ingestion ──────────────────────────────────────────────────
    const processedMessageRef = useRef<any>(null);
    useEffect(() => {
        if (!lastMessage) return;
        // process each message exactly once even when the effect re-runs
        // because of collapsed/callback/session identity changes
        if (processedMessageRef.current === lastMessage) return;
        processedMessageRef.current = lastMessage;

        if (lastMessage.type === "agent_step_update") {
            // Handle various payload shapes (flat or nested in data):
            //   {step: {...}}                     — flat step object
            //   {data: {step: {...}}}             — step object nested in data
            //   {data: {step: 1, thought: "..."}} — data IS the step object
            let payload: any = lastMessage.data ?? lastMessage;
            let newStep: any = null;
            if (payload.step && typeof payload.step === "object") {
                newStep = payload.step;
            } else if (
                payload &&
                typeof payload === "object" &&
                typeof payload.step === "number"
            ) {
                newStep = payload;
            }
            if (!newStep) return;

            // The live emitters disagree on keys (`output` vs `observation`);
            // normalize here so every consumer can rely on `observation`.
            if (newStep.observation === undefined || newStep.observation === null) {
                newStep = { ...newStep, observation: newStep.output ?? "" };
            }

            // Drop events that belong to a different chat session
            const evtSession = payload.session_id ?? newStep.session_id;
            if (evtSession && sessionId && evtSession !== sessionId) return;

            const executionId: string =
                payload.execution_id ?? newStep.execution_id ?? "live";
            const step: AgentStep = {
                ...newStep,
                execution_id: newStep.execution_id ?? executionId,
            };
            const wireAgentId = payload.agent_id ?? lastMessage.agent_id;

            setRuns((prev) => {
                const current = prev[prev.length - 1];
                // No matching current run → start one. For legacy payloads
                // (no execution id) a step 1 also resets, preserving the
                // old fresh-run behavior.
                if (
                    !current ||
                    current.executionId !== executionId ||
                    (step.step === 1 && current.executionId === "live")
                ) {
                    return [
                        ...prev,
                        {
                            executionId,
                            agentId: wireAgentId ?? undefined,
                            status: "running" as const,
                            steps: [step],
                            stepFeedback: {},
                        },
                    ];
                }
                if (current.steps.some((s) => s.step === step.step)) {
                    // same step number within the run → replace (progressive update)
                    return [
                        ...prev.slice(0, -1),
                        {
                            ...current,
                            steps: current.steps.map((s) =>
                                s.step === step.step ? step : s
                            ),
                        },
                    ];
                }
                return [
                    ...prev.slice(0, -1),
                    { ...current, steps: [...current.steps, step] },
                ];
            });
            setAgentStatus("running");
            if (collapsed) setUnreadCount((n) => n + 1);
            if (wireAgentId) setActiveAgentId(wireAgentId);
            onAgentActivity?.(step.step === 1 ? "run_start" : "step");
        } else if (lastMessage.type === "agent_status_change") {
            // Handle flat or nested status
            const payload = lastMessage.data ?? lastMessage;
            const status = payload.status || "unknown";
            setAgentStatus(status);

            const agentId = payload.agent_id ?? lastMessage.agent_id;
            if (agentId) setActiveAgentId(agentId);

            const evtSession = payload.session_id;
            if (!(evtSession && sessionId && evtSession !== sessionId)) {
                const executionId: string = payload.execution_id ?? "live";
                const runStatus = runStatusFromWire(status);

                setRuns((prev) => {
                    const current = prev[prev.length - 1];
                    if (current && current.executionId === executionId) {
                        return [
                            ...prev.slice(0, -1),
                            { ...current, status: runStatus },
                        ];
                    }
                    // run started before its first step arrived
                    return [
                        ...prev,
                        {
                            executionId,
                            agentId: agentId ?? undefined,
                            status: runStatus,
                            steps: [],
                            stepFeedback: {},
                        },
                    ];
                });

                if (status === "running") {
                    onAgentActivity?.("run_start");
                } else if (runStatus === "success" || runStatus === "failed" || runStatus === "completed") {
                    onRunSettled?.();
                }
            }
        }

        // Auto-switch to artifacts tab when a canvas presentation occurs
        if (lastMessage.type === "canvas:update" || lastMessage.type === "canvas:present") {
            if (lastMessage.data?.action !== "close") {
                setActiveTab("artifacts");
            }
        }
    }, [lastMessage, sessionId, collapsed, onAgentActivity, onRunSettled]);

    // Reset unread when the panel is expanded
    useEffect(() => {
        if (!collapsed) setUnreadCount(0);
    }, [collapsed]);

    // Auto-scroll to bottom of steps
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [runs]);

    const currentRun = runs.length > 0 ? runs[runs.length - 1] : null;
    const historyRuns = runs.slice(0, -1);
    const totalSteps = currentRun?.steps.length ?? 0;

    const handleClear = () => {
        setRuns([]);
        setAgentStatus("idle");
        setActiveAgentId(null);
    };

    // ── Feedback (understanding → training loop) ─────────────────────────
    const sendFeedback = useCallback(
        async (run: AgentRun, opts: {
            step?: AgentStep;
            type: FeedbackType;
            comment?: string;
        }) => {
            // Only persisted runs carry an execution id for the DB write-through;
            // legacy "live" runs fall back to governance-only feedback.
            const executionId = run.executionId === "live" ? undefined : run.executionId;
            try {
                await submitStepFeedback({
                    agentId: run.agentId || activeAgentId || "atom_main",
                    runId: run.executionId,
                    stepIndex: opts.step
                        ? run.steps.findIndex((s) => s.step === opts.step!.step)
                        : -1,
                    stepContent: opts.step
                        ? {
                              step: opts.step.step,
                              thought: opts.step.thought,
                              action: opts.step.action,
                              observation: opts.step.observation,
                          }
                        : { input_summary: run.inputSummary ?? "" },
                    feedbackType: opts.type,
                    comment: opts.comment,
                    executionId,
                    stepNumber: opts.step ? opts.step.step : undefined,
                });
            } catch {
                // feedback is best-effort; UI state stays optimistic
            }
        },
        [activeAgentId]
    );

    const handleStepFeedback = (run: AgentRun, step: AgentStep, type: FeedbackType) => {
        onUserInteraction?.();
        const prev = run.stepFeedback[step.step];
        const next = prev === type ? undefined : type;
        setRuns((all) =>
            all.map((r) => {
                if (r.executionId !== run.executionId) return r;
                const stepFeedback = { ...r.stepFeedback };
                if (next) stepFeedback[step.step] = next;
                else delete stepFeedback[step.step];
                return { ...r, stepFeedback };
            })
        );
        if (next) sendFeedback(run, { step, type: next });
    };

    const handleRunFeedback = (run: AgentRun, type: FeedbackType) => {
        onUserInteraction?.();
        const next = run.runFeedback === type ? null : type;
        setRuns((all) =>
            all.map((r) =>
                r.executionId === run.executionId ? { ...r, runFeedback: next } : r
            )
        );
        if (next) sendFeedback(run, { type: next });
    };

    const handleCommentSubmit = (run: AgentRun, step: AgentStep) => {
        const text = commentText.trim();
        setCommentTarget(null);
        setCommentText("");
        if (!text) return;
        // Comments arrive as corrective feedback (thumbs_down + note),
        // matching the message-level comment convention.
        setRuns((all) =>
            all.map((r) =>
                r.executionId === run.executionId
                    ? { ...r, stepFeedback: { ...r.stepFeedback, [step.step]: "thumbs_down" as FeedbackType } }
                    : r
            )
        );
        sendFeedback(run, { step, type: "thumbs_down", comment: text });
    };

    const toggleHistory = (executionId: string) => {
        setExpandedHistory((prev) => {
            const next = new Set(prev);
            if (next.has(executionId)) next.delete(executionId);
            else next.add(executionId);
            return next;
        });
    };

    // ── Rail mode (collapsed) ────────────────────────────────────────────
    if (collapsed && !isMaximized) {
        const isRunning = agentStatus === "running";
        return (
            <div
                className="h-full w-11 flex flex-col items-center gap-3 border-l border-slate-800 bg-[#0F172A] py-3"
                data-testid="workspace-rail"
            >
                <button
                    type="button"
                    aria-label="Expand agent workspace"
                    title="Show agent workspace"
                    className="relative p-1.5 rounded-md text-indigo-400 hover:bg-slate-800"
                    onClick={() => {
                        onUserInteraction?.();
                        onToggleCollapsed?.();
                    }}
                >
                    <Brain className="h-4 w-4" />
                    {isRunning && (
                        <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                    )}
                    {unreadCount > 0 && (
                        <span
                            aria-label={`${unreadCount} unread steps`}
                            className="absolute -bottom-1 -right-1 min-w-[14px] h-[14px] px-0.5 rounded-full bg-indigo-600 text-white text-[9px] font-bold flex items-center justify-center"
                        >
                            {unreadCount > 9 ? "9+" : unreadCount}
                        </span>
                    )}
                </button>
                {totalSteps > 0 && (
                    <span
                        className="text-[10px] text-slate-500 font-mono"
                        title={`${totalSteps} steps in current run`}
                    >
                        {totalSteps}
                    </span>
                )}
            </div>
        );
    }

    // ── Step cards + run headers ─────────────────────────────────────────
    const renderStepFeedback = (run: AgentRun, step: AgentStep) => {
        const selected = run.stepFeedback[step.step];
        const hasComment = commentTarget?.runId === run.executionId && commentTarget?.stepNumber === step.step;
        return (
            <div className="flex items-center gap-1 mt-2 flex-wrap">
                <Button
                    variant="ghost"
                    size="sm"
                    aria-label="Thumbs up"
                    title="Good step — helps training"
                    className={`h-6 w-6 p-0 ${selected === "thumbs_up" ? "text-green-400" : "text-slate-500 hover:text-slate-300"}`}
                    onClick={() => handleStepFeedback(run, step, "thumbs_up")}
                >
                    <ThumbsUp className="h-3 w-3" />
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    aria-label="Thumbs down"
                    title="Bad step — helps training"
                    className={`h-6 w-6 p-0 ${selected === "thumbs_down" ? "text-red-400" : "text-slate-500 hover:text-slate-300"}`}
                    onClick={() => handleStepFeedback(run, step, "thumbs_down")}
                >
                    <ThumbsDown className="h-3 w-3" />
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    aria-label="Add note"
                    title="Add a correction note"
                    className="h-6 w-6 p-0 text-slate-500 hover:text-slate-300"
                    onClick={() => {
                        onUserInteraction?.();
                        setCommentText("");
                        setCommentTarget({ runId: run.executionId, stepNumber: step.step });
                    }}
                >
                    <MessageSquare className="h-3 w-3" />
                </Button>
                {hasComment && (
                    <span className="flex items-center gap-1 flex-1 min-w-[140px]">
                        <input
                            aria-label="Feedback note"
                            className="flex-1 h-6 text-xs bg-slate-800 border border-slate-700 rounded px-2 text-slate-200 focus:outline-none"
                            placeholder="What was wrong?"
                            value={commentText}
                            onChange={(e) => setCommentText(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter") handleCommentSubmit(run, step);
                            }}
                        />
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs text-slate-300"
                            onClick={() => handleCommentSubmit(run, step)}
                        >
                            Send
                        </Button>
                    </span>
                )}
            </div>
        );
    };

    // Backend step events carry `action` as a structured object
    // ({tool, params}) and `action_input` as the params OBJECT — rendering
    // either directly throws "Objects are not valid as a React child".
    // Derive display strings defensively at render time.
    const actionLabel = (action: unknown): string | undefined => {
        if (!action) return undefined;
        if (typeof action === "string") return action;
        if (typeof action === "object") {
            const tool = (action as Record<string, unknown>).tool;
            return typeof tool === "string" ? tool : JSON.stringify(action).slice(0, 60);
        }
        return String(action);
    };
    const inputLabel = (value: unknown): string | undefined => {
        if (value === undefined || value === null || value === "") return undefined;
        if (typeof value === "string") return value;
        try {
            return JSON.stringify(value).slice(0, 120);
        } catch {
            return String(value);
        }
    };

    const renderStepCard = (run: AgentRun, step: AgentStep) => (
        <div key={`${run.executionId}-${step.step}`} className="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
                <Badge variant="outline" className="text-indigo-400 border-indigo-400">Step {step.step}</Badge>
                {actionLabel(step.action) && <Badge variant="secondary" className="bg-indigo-600 text-white">{actionLabel(step.action)}</Badge>}
                {step.step_type && (
                    <Badge variant="outline" className="text-slate-400 border-slate-600 text-[10px]">{step.step_type}</Badge>
                )}
                {step.verified === "verified" && (
                    <Badge variant="outline" className="text-green-400 border-green-400 text-[10px]">verified</Badge>
                )}
                {step.verified === "failed_verification" && (
                    <Badge variant="outline" className="text-red-400 border-red-400 text-[10px]">failed verification</Badge>
                )}
                {typeof step.confidence === "number" && (
                    <span className="ml-auto flex items-center gap-1 text-[10px] text-slate-500">
                        confidence
                        <span className="inline-block w-12 h-1 rounded bg-slate-700 overflow-hidden">
                            <span
                                className="block h-full bg-indigo-500"
                                style={{ width: `${Math.round(Math.min(1, Math.max(0, step.confidence)) * 100)}%` }}
                            />
                        </span>
                        {Math.round(step.confidence * 100)}%
                    </span>
                )}
            </div>
            {step.thought && (
                <p className="text-sm text-slate-300 mb-1"><strong>Thinking:</strong> {step.thought}</p>
            )}
            {inputLabel(step.action_input) && (
                <p className="text-xs text-slate-500 font-mono mb-1 truncate" title={inputLabel(step.action_input)}>
                    input: {inputLabel(step.action_input)}
                </p>
            )}
            {step.observation && (
                <p className="text-sm text-slate-400"><strong>Result:</strong> {step.observation}</p>
            )}
            <div className="flex items-center justify-between flex-wrap gap-1">
                <div className="flex items-center gap-2 text-[10px] text-slate-600">
                    {typeof step.duration_ms === "number" && step.duration_ms > 0 && (
                        <span>{(step.duration_ms / 1000).toFixed(1)}s</span>
                    )}
                    {step.resolved_model && <span>{step.resolved_model}</span>}
                </div>
                {renderStepFeedback(run, step)}
            </div>
        </div>
    );

    const renderRunMeta = (run: AgentRun) => (
        <div className="flex items-center gap-2 flex-wrap">
            {run.status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />}
            {(run.status === "success" || run.status === "completed") && <CircleCheck className="h-3.5 w-3.5 text-green-400" />}
            {run.status === "failed" && <CircleX className="h-3.5 w-3.5 text-red-400" />}
            <span className="text-xs text-slate-300 font-medium">
                {run.executionId === "live" ? "Current run" : run.executionId.slice(0, 8)}
            </span>
            {run.agentId && (
                <Badge variant="outline" className="text-[10px] text-slate-400 border-slate-600">{run.agentId}</Badge>
            )}
            {run.inputSummary && (
                <span className="text-[10px] text-slate-500 truncate max-w-[220px]" title={run.inputSummary}>
                    {run.inputSummary}
                </span>
            )}
        </div>
    );

    return (
        <div
            className={`h-full flex flex-col border-l border-slate-800 bg-[#0F172A] transition-all duration-300 ${isMaximized ? 'fixed inset-0 z-[60] bg-[#020617]' : 'relative overflow-hidden'}`}
            onClick={() => onUserInteraction?.()}
        >
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h2 className="font-semibold flex items-center gap-2 text-slate-100">
                    <Brain className="h-4 w-4 text-indigo-400" />
                    Agent Workspace
                    {isConnected && <Badge variant="outline" className="text-green-400 border-green-400 text-[10px]">Live</Badge>}
                </h2>
                <div className="flex items-center gap-2">
                    {onToggleCollapsed && (
                        <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Collapse workspace"
                            title="Collapse to the activity rail"
                            className="h-8 w-8 text-slate-500 hover:text-white"
                            onClick={() => {
                                onUserInteraction?.();
                                onToggleCollapsed();
                            }}
                        >
                            <PanelRightClose className="h-4 w-4" />
                        </Button>
                    )}
                    {onAutoHideToggle && (
                        <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Toggle auto-hide"
                            title={autoHide ? "Auto-hide is on — panel collapses when idle" : "Auto-hide is off — panel stays open"}
                            className={`h-8 w-8 ${autoHide ? "text-indigo-400" : "text-slate-500"} hover:text-white`}
                            onClick={() => onAutoHideToggle(!autoHide)}
                        >
                            {autoHide ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                    )}
                    {runs.length > 0 && (
                        <Button variant="ghost" size="sm" onClick={handleClear} className="text-slate-400 hover:text-slate-200">
                            <Trash2 className="h-4 w-4" />
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-slate-500 hover:text-white"
                        onClick={() => setIsMaximized(!isMaximized)}
                    >
                        {isMaximized ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                    </Button>
                </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 min-h-0 flex flex-col">
                <div className="px-4 pt-2">
                    <TabsList className="w-full grid grid-cols-3 bg-slate-800">
                        <TabsTrigger value="tasks" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white uppercase text-[10px] font-bold">Tasks</TabsTrigger>
                        <TabsTrigger value="artifacts" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white uppercase text-[10px] font-bold">Artifacts</TabsTrigger>
                        <TabsTrigger value="browser" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white uppercase text-[10px] font-bold">Browser View</TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="tasks" className="flex-1 min-h-0 p-4 overflow-hidden flex flex-col gap-4">
                    {/* Self Reflection / Status */}
                    <Card className="bg-indigo-900/10 border-indigo-500/20">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-indigo-300">
                                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                Agent Status: {agentStatus}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-sm text-slate-400 italic">
                                &quot;{totalSteps > 0 ? `Processing step ${totalSteps}...` : "I am standing by. Start a chat to see my execution plan."}&quot;
                            </p>
                        </CardContent>
                    </Card>

                    {/* Execution Steps — current run, with reasoning trace */}
                    <Card className="flex-1 min-h-0 flex flex-col overflow-hidden bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-slate-200">
                                <ListTodo className="h-4 w-4" />
                                Execution Steps ({totalSteps})
                            </CardTitle>
                            {currentRun && (
                                <div className="mt-1 flex items-center justify-between">
                                    {renderRunMeta(currentRun)}
                                    {currentRun.executionId !== "live" && (
                                        <span className="flex items-center gap-1">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                aria-label="Thumbs up for run"
                                                title="Good run"
                                                className={`h-6 w-6 p-0 ${currentRun.runFeedback === "thumbs_up" ? "text-green-400" : "text-slate-500 hover:text-slate-300"}`}
                                                onClick={() => handleRunFeedback(currentRun, "thumbs_up")}
                                            >
                                                <ThumbsUp className="h-3 w-3" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                aria-label="Thumbs down for run"
                                                title="Bad run"
                                                className={`h-6 w-6 p-0 ${currentRun.runFeedback === "thumbs_down" ? "text-red-400" : "text-slate-500 hover:text-slate-300"}`}
                                                onClick={() => handleRunFeedback(currentRun, "thumbs_down")}
                                            >
                                                <ThumbsDown className="h-3 w-3" />
                                            </Button>
                                        </span>
                                    )}
                                </div>
                            )}
                        </CardHeader>
                        <CardContent className="flex-1 overflow-auto" ref={scrollRef}>
                            {traceLoading && totalSteps === 0 && (
                                <p className="text-xs text-slate-500 flex items-center gap-2">
                                    <Loader2 className="h-3 w-3 animate-spin" /> Loading trace…
                                </p>
                            )}
                            <div className="space-y-3">
                                {totalSteps === 0 && !traceLoading ? (
                                    <p className="text-sm text-slate-500 dark:text-slate-400 italic">No execution steps yet. Send a message to see the agent's reasoning.</p>
                                ) : (
                                    currentRun?.steps.map((step) => renderStepCard(currentRun, step))
                                )}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Previous runs — history restore + earlier runs this session */}
                    {historyRuns.length > 0 && (
                        <div className="shrink-0 max-h-48 overflow-auto space-y-2">
                            <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Previous runs ({historyRuns.length})</p>
                            {historyRuns.slice().reverse().map((run) => {
                                const expanded = expandedHistory.has(run.executionId);
                                return (
                                    <div key={run.executionId} className="rounded-lg border border-slate-800 bg-slate-900/40">
                                        <button
                                            type="button"
                                            className="w-full px-3 py-2 flex items-center text-left"
                                            onClick={() => toggleHistory(run.executionId)}
                                        >
                                            {expanded
                                                ? <ChevronDown className="h-3.5 w-3.5 text-slate-500 mr-2" />
                                                : <ChevronRight className="h-3.5 w-3.5 text-slate-500 mr-2" />}
                                            <div className="flex-1">{renderRunMeta(run)}</div>
                                            <span className="text-[10px] text-slate-500 ml-2">{run.steps.length} steps</span>
                                        </button>
                                        {expanded && (
                                            <div className="px-3 pb-3 space-y-2">
                                                {run.steps.map((step) => renderStepCard(run, step))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </TabsContent>

                <TabsContent value="artifacts" className="flex-1 min-h-0 p-0 overflow-hidden relative">
                    <div className="flex flex-col h-full">
                        <div className="flex-1 overflow-hidden">
                            <CanvasHost lastMessage={lastMessage} sessionId={sessionId} />
                        </div>
                        <div className="h-1/3 border-t border-slate-800 shrink-0">
                            <ArtifactSidebar
                                sessionId={sessionId}
                                onSelectArtifact={(id: string) => {
                                    console.log("Selected artifact:", id);
                                }}
                            />
                        </div>
                    </div>
                </TabsContent>

                <TabsContent value="browser" className="flex-1 min-h-0 p-4 h-full">
                    <Card className="h-full flex flex-col bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2 border-b border-slate-800">
                            <CardTitle className="text-sm font-medium flex items-center gap-2 text-slate-200">
                                <Globe className="h-4 w-4" />
                                Headless Browser Preview
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="flex-1 bg-slate-950 flex items-center justify-center p-0">
                            <div className="text-center p-4">
                                <Globe className="h-12 w-12 text-slate-700 dark:text-slate-300 mx-auto mb-2 opacity-20" />
                                <p className="text-sm text-slate-500 dark:text-slate-400">
                                    Browser view will appear here when the agent is interacting with web pages.
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default AgentWorkspace;
