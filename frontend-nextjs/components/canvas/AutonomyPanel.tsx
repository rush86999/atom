"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Lock, Zap, Loader2 } from "lucide-react";

/**
 * Autonomy policy panel — the owner decides, per action topic, whether the
 * agent ALWAYS needs a human in the loop or may act autonomously once its
 * maturity tier allows. Backed by GET/PUT /api/autonomy/topics.
 */
interface AutonomyTopic {
    topic: string;
    label: string;
    description: string;
    default_mode: string;
    mode: string;
}

export function AutonomyPanel() {
    const [topics, setTopics] = useState<AutonomyTopic[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setError(null);
        try {
            const { apiClient } = await import("../../lib/api-client");
            const res = await apiClient.get("/api/autonomy/topics");
            const data = (res as any).data || res;
            setTopics(data?.topics || []);
        } catch (e) {
            setError("Could not load autonomy settings.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const setMode = async (topic: string, mode: string) => {
        setBusy(topic);
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.put(`/api/autonomy/topics/${topic}`, { mode });
            setTopics(prev => prev.map(t => t.topic === topic ? { ...t, mode } : t));
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

    return (
        <div className="flex-1 overflow-y-auto p-3 space-y-3" data-testid="autonomy-panel">
            <p className="text-[11px] text-muted-foreground leading-relaxed">
                Choose which agent actions <strong>always require you</strong> and which the
                agent may do autonomously <strong>once mature enough</strong>. Immature hires
                always propose first and learn from your decisions.
            </p>
            {error && <p className="text-xs text-red-500">{error}</p>}
            {topics.map(t => (
                <div key={t.topic} className="border rounded-lg p-3 bg-background" data-testid={`autonomy-${t.topic}`}>
                    <div className="flex items-start justify-between gap-2">
                        <div>
                            <p className="text-sm font-medium">{t.label}</p>
                            <p className="text-[11px] text-muted-foreground">{t.description}</p>
                        </div>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-1">
                        <button
                            onClick={() => setMode(t.topic, "human_always")}
                            disabled={busy === t.topic}
                            className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                                t.mode === "human_always"
                                    ? "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40"
                                    : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                            }`}
                            data-testid={`autonomy-${t.topic}-hitl`}
                        >
                            <Lock className="h-3 w-3" /> Always require me
                        </button>
                        <button
                            onClick={() => setMode(t.topic, "auto_if_mature")}
                            disabled={busy === t.topic}
                            className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                                t.mode === "auto_if_mature"
                                    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/40"
                                    : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                            }`}
                            data-testid={`autonomy-${t.topic}-auto`}
                        >
                            <Zap className="h-3 w-3" /> Auto if mature
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}
