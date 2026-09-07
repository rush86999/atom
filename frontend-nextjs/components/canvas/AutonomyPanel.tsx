"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Lock, Zap, RefreshCcw, Loader2, ShieldCheck, ShieldAlert } from "lucide-react";

/**
 * Autonomy policy panel — the owner decides, per action topic, whether the
 * agent ALWAYS needs a human in the loop, may act autonomously once its
 * maturity tier allows, or acts autonomously UNTIL a human correction resets
 * the cycle (the hire proposes again and re-earns autonomy through verified
 * work). Backed by GET/PUT /api/autonomy/topics.
 *
 * Canvas-aware: with canvasId/agentId the backend flags the topics primary
 * for this canvas's type ("On this canvas" section) and attaches each
 * hire's live gate — owner mode × governance maturity × skill-scoped trust
 * × correction cycle — so the panel shows exactly what a turn would enforce
 * today.
 */
interface AutonomyGate {
    outcome: "execute" | "propose";
    reason: string;
    maturity: {
        known: boolean;
        maturity_level: string | null;
        required: string | null;
        ok: boolean;
    };
    trust: {
        enabled: boolean;
        trust: number | null;
        threshold: number;
        cold_start: boolean | null;
        ok: boolean;
    };
    cycle?: {
        reset: boolean;
        tier: string | null;
        required: string | null;
        ok: boolean;
        reason: string | null;
    } | null;
}

interface AutonomyTopic {
    topic: string;
    label: string;
    description: string;
    default_mode: string;
    mode: string;
    canvas_relevant?: boolean;
    gate?: AutonomyGate;
}

function GateChip({ gate }: { gate: AutonomyGate }) {
    const execute = gate.outcome === "execute";
    return (
        <div
            className={`mt-2 flex items-start gap-1.5 rounded px-2 py-1.5 text-[11px] leading-snug ${
                execute
                    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                    : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
            }`}
            data-testid={`autonomy-gate-${execute ? "execute" : "propose"}`}
            title={gate.reason}
        >
            {execute ? (
                <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />
            ) : (
                <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" />
            )}
            <span>
                <strong>{execute ? "Acts autonomously today." : "Proposes for your approval."}</strong>{" "}
                {gate.reason}
            </span>
        </div>
    );
}

function GateDetail({ gate }: { gate: AutonomyGate }) {
    const { maturity, trust, cycle } = gate;
    if (!maturity.known && !trust.enabled && !cycle?.tier) return null;
    const bits: string[] = [];
    if (maturity.known) {
        bits.push(
            `maturity ${maturity.maturity_level ?? "?"} (needs ${maturity.required ?? "?"})`
        );
    }
    if (trust.enabled) {
        bits.push(
            `trust ${(trust.trust ?? 0).toFixed(2)} / ${trust.threshold.toFixed(2)}${
                trust.cold_start ? " (no evidence yet)" : ""
            }`
        );
    }
    if (cycle?.tier) {
        bits.push(
            `cycle ${cycle.tier} (needs ${cycle.required ?? "?"})${
                cycle.reset ? " — reset by a correction" : ""
            }`
        );
    }
    return <p className="mt-1 text-[10px] text-muted-foreground">{bits.join(" · ")}</p>;
}

function TopicCard({
    topic,
    busy,
    onSetMode,
}: {
    topic: AutonomyTopic;
    busy: boolean;
    onSetMode: (topic: string, mode: string) => void;
}) {
    return (
        <div className="border rounded-lg p-3 bg-background" data-testid={`autonomy-${topic.topic}`}>
            <div className="flex items-start justify-between gap-2">
                <div>
                    <p className="text-sm font-medium">{topic.label}</p>
                    <p className="text-[11px] text-muted-foreground">{topic.description}</p>
                </div>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-1">
                <button
                    onClick={() => onSetMode(topic.topic, "human_always")}
                    disabled={busy}
                    className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        topic.mode === "human_always"
                            ? "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40"
                            : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                    }`}
                    data-testid={`autonomy-${topic.topic}-hitl`}
                >
                    <Lock className="h-3 w-3" /> Always require me
                </button>
                <button
                    onClick={() => onSetMode(topic.topic, "auto_if_mature")}
                    disabled={busy}
                    className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        topic.mode === "auto_if_mature"
                            ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/40"
                            : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                    }`}
                    data-testid={`autonomy-${topic.topic}-auto`}
                >
                    <Zap className="h-3 w-3" /> Auto if mature
                </button>
                <button
                    onClick={() => onSetMode(topic.topic, "auto_until_corrected")}
                    disabled={busy}
                    title="Acts autonomously once mature; a human correction resets the cycle — the hire proposes again and re-earns autonomy through verified work."
                    className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        topic.mode === "auto_until_corrected"
                            ? "bg-sky-500/15 text-sky-700 dark:text-sky-400 border border-sky-500/40"
                            : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                    }`}
                    data-testid={`autonomy-${topic.topic}-cycle`}
                >
                    <RefreshCcw className="h-3 w-3" /> Auto until corrected
                </button>
            </div>
            {topic.gate && <GateChip gate={topic.gate} />}
            {topic.gate && <GateDetail gate={topic.gate} />}
        </div>
    );
}

export function AutonomyPanel({
    canvasId,
    agentId,
}: {
    canvasId?: string;
    agentId?: string;
}) {
    const [topics, setTopics] = useState<AutonomyTopic[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(
        async (showSpinner = true) => {
            setError(null);
            if (showSpinner) setLoading(true);
            try {
                const { apiClient } = await import("../../lib/api-client");
                const params = new URLSearchParams();
                if (canvasId) params.set("canvas_id", canvasId);
                if (agentId) params.set("agent_id", agentId);
                const qs = params.toString();
                const res = await apiClient.get(`/api/autonomy/topics${qs ? `?${qs}` : ""}`);
                const data = (res as any).data || res;
                setTopics(data?.topics || []);
            } catch (e) {
                setError("Could not load autonomy settings.");
            } finally {
                setLoading(false);
            }
        },
        [canvasId, agentId]
    );

    useEffect(() => { load(); }, [load]);

    const setMode = async (topic: string, mode: string) => {
        setBusy(topic);
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.put(`/api/autonomy/topics/${topic}`, { mode });
            setTopics(prev => prev.map(t => (t.topic === topic ? { ...t, mode } : t)));
            // Refresh gates silently — the outcome chip can flip with the mode.
            load(false);
        } catch {
            setError("Failed to save — try again.");
        } finally {
            setBusy(null);
        }
    };

    if (loading) {
        return (
            <div className="p-4 flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading autonomy settings…
            </div>
        );
    }

    const canvasTopics = topics.filter(t => t.canvas_relevant);
    const generalTopics = topics.filter(t => !t.canvas_relevant);

    return (
        <div className="flex-1 overflow-y-auto p-3 space-y-3" data-testid="autonomy-panel">
            <p className="text-[11px] text-muted-foreground leading-relaxed">
                Choose which agent actions <strong>always require you</strong>, which the
                agent may do autonomously <strong>once mature enough</strong>, and which run
                autonomously <strong>until a correction resets the cycle</strong> (the hire
                proposes again and re-earns autonomy through verified work). Immature hires
                always propose first and learn from your decisions.
            </p>
            {error && <p className="text-xs text-red-500">{error}</p>}
            {canvasTopics.length > 0 && (
                <>
                    <p
                        className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                        data-testid="autonomy-canvas-section"
                    >
                        On this canvas
                    </p>
                    <div className="space-y-3">
                        {canvasTopics.map(t => (
                            <TopicCard key={t.topic} topic={t} busy={busy === t.topic} onSetMode={setMode} />
                        ))}
                    </div>
                </>
            )}
            {generalTopics.length > 0 && (
                <>
                    <p
                        className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                        data-testid="autonomy-general-section"
                    >
                        General
                    </p>
                    <div className="space-y-3">
                        {generalTopics.map(t => (
                            <TopicCard key={t.topic} topic={t} busy={busy === t.topic} onSetMode={setMode} />
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
