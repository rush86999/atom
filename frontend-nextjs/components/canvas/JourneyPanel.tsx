"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Bot, User, GraduationCap, ShieldCheck, Loader2, RefreshCw, Check, X, ArrowRight, ChevronDown } from "lucide-react";

/**
 * Journey panel — the audit timeline for everything that happened on this
 * canvas: agent edits vs. human edits (by which hire), supervisor
 * corrections with original→corrected previews, and HITL action proposals
 * (send email etc.) with approve/reject. Backed by GET /api/canvas/{id}/journey
 * and the /api/maturity/proposals endpoints.
 */
interface JourneyEvent {
    kind: string;
    action: string;
    actor_type: string;
    actor: string;
    at: string | null;
    summary: string;
    status?: string;
    proposal_id?: string;
    title?: string;
    to?: string;
    original?: string;
    corrected?: string;
    content_preview?: string;
    content?: string | null;
    subject?: string;
}

export function JourneyPanel({ canvasId }: { canvasId: string }) {
    const [events, setEvents] = useState<JourneyEvent[]>([]);
    const [pending, setPending] = useState<JourneyEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [deciding, setDeciding] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [expanded, setExpanded] = useState<string | null>(null);

    const load = useCallback(async () => {
        try {
            const { apiClient } = await import("../../lib/api-client");
            const res = await apiClient.get(`/api/canvas/${canvasId}/journey`);
            const data = (res as any).data || res;
            setEvents(data?.events || []);
            setPending(data?.pending_proposals || []);
        } catch {
            setNotice("Could not load the journey.");
        } finally {
            setLoading(false);
        }
    }, [canvasId]);

    useEffect(() => { load(); }, [load]);

    const decide = async (proposalId: string, approve: boolean) => {
        setDeciding(proposalId);
        setNotice(null);
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.post(`/api/maturity/proposals/${proposalId}/approve`, { approve });
            setNotice(approve ? "Approved and executed." : "Rejected.");
            await load();
        } catch (e: any) {
            const msg = (e as any)?.response?.data?.detail || (e as any)?.message;
            setNotice(typeof msg === "string" ? msg : "Decision failed — you may need supervisor permissions.");
        } finally {
            setDeciding(null);
        }
    };

    const iconFor = (e: JourneyEvent) => {
        if (e.kind === "proposal") return <ShieldCheck className="h-3.5 w-3.5 text-indigo-500" />;
        if (e.kind === "correction") return <GraduationCap className="h-3.5 w-3.5 text-amber-500" />;
        if (e.actor_type === "agent") return <Bot className="h-3.5 w-3.5 text-blue-500" />;
        return <User className="h-3.5 w-3.5 text-zinc-500" />;
    };

    return (
        <div className="flex-1 overflow-y-auto p-3 space-y-3" data-testid="journey-panel">
            <div className="flex items-center justify-between">
                <p className="text-[11px] text-muted-foreground">
                    Full change history: who did what, when — hires, you, and approvals.
                </p>
                <button onClick={load} className="text-muted-foreground hover:text-foreground" title="Refresh">
                    <RefreshCw className="h-3.5 w-3.5" />
                </button>
            </div>
            {notice && <p className="text-xs text-muted-foreground bg-muted/60 rounded p-2">{notice}</p>}

            {pending.length > 0 && (
                <div className="space-y-2">
                    {pending.map(p => (
                        <div key={p.proposal_id} className="border border-indigo-500/40 bg-indigo-500/5 rounded-lg p-3" data-testid={`proposal-${p.proposal_id}`}>
                            <div className="flex items-start justify-between gap-2">
                                <div>
                                    <p className="text-sm font-medium">🔐 {p.title || p.action}</p>
                                    <p className="text-[11px] text-muted-foreground">
                                        Proposed by {p.actor}{p.to ? ` → ${p.to}` : ""}
                                    </p>
                                </div>
                            </div>
                            <div className="mt-2 flex gap-2">
                                <button
                                    onClick={() => decide(p.proposal_id!, true)}
                                    disabled={deciding === p.proposal_id}
                                    className="flex items-center gap-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] px-2.5 py-1.5 font-medium disabled:opacity-50"
                                >
                                    {deciding === p.proposal_id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                                    Approve &amp; send
                                </button>
                                <button
                                    onClick={() => decide(p.proposal_id!, false)}
                                    disabled={deciding === p.proposal_id}
                                    className="flex items-center gap-1 rounded border border-red-500/40 text-red-600 dark:text-red-400 text-[11px] px-2.5 py-1.5 font-medium hover:bg-red-500/10 disabled:opacity-50"
                                >
                                    <X className="h-3 w-3" /> Reject
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground p-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading journey…
                </div>
            ) : events.length === 0 ? (
                <p className="text-sm text-muted-foreground p-2">No history yet.</p>
            ) : (
                <div className="space-y-1.5">
                    {events.map((e, i) => {
                        const key = `${e.kind}-${e.proposal_id || e.at}-${i}`;
                        const isOpen = expanded === key;
                        const hasDetail = Boolean(
                            e.content || e.original || e.corrected || e.subject || e.to
                        );
                        return (
                            <div key={key} className="border rounded-lg p-2.5 bg-background text-xs" data-testid={`journey-event-${i}`}>
                                <div className="flex items-center gap-2">
                                    {iconFor(e)}
                                    <span className="font-medium">{e.actor}</span>
                                    <span className="text-muted-foreground">·</span>
                                    <span className="text-muted-foreground flex-1 truncate" title={e.summary}>
                                        {e.summary}
                                    </span>
                                    <span className="text-[10px] text-muted-foreground shrink-0">
                                        {e.at ? new Date(e.at).toLocaleTimeString() : ""}
                                    </span>
                                    {hasDetail && (
                                        <button
                                            onClick={() => setExpanded(isOpen ? null : key)}
                                            className="text-muted-foreground hover:text-foreground shrink-0"
                                            aria-label={isOpen ? "Collapse" : "Expand"}
                                            data-testid={`journey-expand-${i}`}
                                        >
                                            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                                        </button>
                                    )}
                                </div>
                                {/* one-line peek of the ACTUAL content, always visible */}
                                {e.content_preview && !isOpen && (
                                    <p className="mt-1 text-[10.5px] text-muted-foreground/80 line-clamp-1 pl-6">
                                        {e.content_preview}
                                    </p>
                                )}
                                {isOpen && (
                                    <div className="mt-2 pl-6 space-y-1.5">
                                        {(e.to || e.subject) && (
                                            <div className="text-[11px] text-muted-foreground">
                                                {e.to && <p>To: <span className="text-foreground">{e.to}</span></p>}
                                                {e.subject && <p>Subject: <span className="text-foreground">{e.subject}</span></p>}
                                            </div>
                                        )}
                                        {e.content && (
                                            <pre className="whitespace-pre-wrap break-words text-[10.5px] text-muted-foreground bg-muted/40 border rounded p-2 max-h-56 overflow-y-auto">
                                                {e.content}
                                            </pre>
                                        )}
                                        {e.kind === "correction" && (e.original || e.corrected) && (
                                            <div className="grid grid-cols-[1fr_auto_1fr] gap-1.5 items-start text-[10px]">
                                                <div className="bg-red-500/5 border border-red-500/20 rounded p-1.5 text-muted-foreground">
                                                    {e.original || "(empty)"}
                                                </div>
                                                <ArrowRight className="h-3 w-3 mt-1 text-muted-foreground" />
                                                <div className="bg-emerald-500/5 border border-emerald-500/20 rounded p-1.5 text-muted-foreground">
                                                    {e.corrected || "(empty)"}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                                {e.kind === "correction" && !isOpen && (e.original || e.corrected) && (
                                    <p className="mt-1 text-[10.5px] text-muted-foreground/80 line-clamp-1 pl-6">
                                        {e.original || ""} → {e.corrected || ""}
                                    </p>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
