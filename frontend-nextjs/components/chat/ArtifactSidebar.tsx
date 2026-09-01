"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
    FileText, Code, Globe, Clock, ChevronRight, Layers, LayoutPanelLeft,
    Table2, Mail, Terminal, BarChart3, Presentation,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { onCanvasRefresh, syncCanvasFromStore } from "@/lib/canvasSync";

/** One entry of GET /api/canvas/?session_id=… — the session-scoped canvas
    list (tools/canvas_crud_tool.list_canvases). The audit trail is the
    durable store; "version" counts this session's audit rows per canvas. */
interface SessionArtifact {
    canvas_id: string;
    canvas_type: string | null;
    action_type: string;
    title: string | null;
    display_title?: string | null;
    snippet?: string | null;
    deleted: boolean;
    last_updated: string | null;
    version?: number;
}

interface ArtifactSidebarProps {
    sessionId: string | null;
    /** Kept for callers that want to observe selection; the sidebar itself
        renders the clicked canvas into the chat's CanvasHost via the same
        convergence path WS frames use (lib/canvasSync). */
    onSelectArtifact?: (canvasId: string) => void;
}

// Audit rows carry canvas_type names from BOTH families: backend canvas
// names (sheets/docs/coding/…) and CanvasHost component names
// (sheet/markdown/code/…) written by the user-edit PUT. Map both, fall back
// to the generic doc icon.
function ArtifactIcon({ type, className }: { type: string | null; className: string }) {
    switch (type) {
        case "code":
        case "coding":
            return <Code className={className} />;
        case "sheets":
        case "sheet":
            return <Table2 className={className} />;
        case "email":
            return <Mail className={className} />;
        case "terminal":
            return <Terminal className={className} />;
        case "orchestration":
            return <Layers className={className} />;
        case "browser_view":
            return <Globe className={className} />;
        case "line_chart":
        case "bar_chart":
        case "pie_chart":
        case "chart":
            return <BarChart3 className={className} />;
        case "office_pptx":
        case "presentation":
            return <Presentation className={className} />;
        default:
            return <FileText className={className} />;
    }
}

export function ArtifactSidebar({ sessionId, onSelectArtifact }: ArtifactSidebarProps) {
    const [artifacts, setArtifacts] = useState<SessionArtifact[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    const fetchArtifacts = useCallback(async () => {
        if (!sessionId) return;
        setIsLoading(true);
        try {
            const response = await apiClient.get(
                `/api/canvas/?session_id=${encodeURIComponent(sessionId)}&limit=50`
            );
            const body = (response as any)?.data ?? response;
            if (body && body.success !== false) {
                setArtifacts(Array.isArray(body.canvases) ? body.canvases : []);
            }
        } catch (error) {
            console.error("Failed to fetch session artifacts:", error);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId) return;
        fetchArtifacts();
        const interval = setInterval(fetchArtifacts, 10000);
        // An agent present/update (WS frame or convergence refresh) changes
        // the list — refetch instead of waiting out the poll.
        const offRefresh = onCanvasRefresh(() => { void fetchArtifacts(); });
        return () => {
            clearInterval(interval);
            offRefresh();
        };
    }, [sessionId, fetchArtifacts]);

    const handleSelect = (canvasId: string) => {
        onSelectArtifact?.(canvasId);
        // Render the canvas into the chat's CanvasHost through the existing
        // local refresh path — no navigation, the user stays in the chat.
        void syncCanvasFromStore(canvasId);
    };

    if (!sessionId) return null;

    return (
        <div className="h-full border-l bg-zinc-50 dark:bg-slate-900 border-zinc-200 dark:border-white/5 flex flex-col w-64">
            <div className="p-4 border-b border-zinc-200 dark:border-white/10 flex items-center gap-2">
                <LayoutPanelLeft className="h-4 w-4 text-indigo-500" />
                <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">Session Artifacts</h3>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                {artifacts.length === 0 && !isLoading && (
                    <div className="text-center py-10 px-4">
                        <Layers className="h-8 w-8 text-zinc-300 dark:text-zinc-800 mx-auto mb-2" />
                        <p className="text-[10px] text-zinc-500 italic">No artifacts yet this session.</p>
                        <p className="text-[10px] text-zinc-400 mt-1">Ask the agent to create a doc, sheet, or chart.</p>
                    </div>
                )}

                {artifacts.map((artifact) => (
                    <button
                        key={artifact.canvas_id}
                        onClick={() => handleSelect(artifact.canvas_id)}
                        title={artifact.snippet || artifact.display_title || artifact.canvas_id}
                        className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-black/5 dark:bg-white/5 group transition-all text-left border border-transparent hover:border-zinc-200 dark:hover:border-black/10 dark:border-white/10 bg-white dark:bg-slate-800/40 shadow-sm dark:shadow-none"
                    >
                        <div className="h-8 w-8 rounded bg-zinc-100 dark:bg-white/5 flex items-center justify-center group-hover:bg-indigo-500/10 transition-colors">
                            <ArtifactIcon type={artifact.canvas_type} className="h-4 w-4 text-zinc-500 group-hover:text-indigo-500" />
                        </div>
                        <div className="flex-1 overflow-hidden">
                            <div className="flex justify-between items-center mb-0.5">
                                <p className="text-xs font-medium text-zinc-900 dark:text-zinc-200 truncate">
                                    {artifact.display_title || artifact.title || artifact.canvas_id}
                                </p>
                                <span className="text-[8px] h-3.5 px-1 bg-zinc-100 dark:bg-black/40 border border-zinc-200 dark:border-white/10 text-zinc-500 flex items-center rounded">
                                    v{artifact.version ?? 1}
                                </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <Clock className="h-2.5 w-2.5 text-zinc-400" />
                                <span className="text-[10px] text-zinc-400">
                                    {formatDate(artifact.last_updated)}
                                </span>
                            </div>
                        </div>
                        <ChevronRight className="h-3 w-3 text-zinc-300 group-hover:text-zinc-500 opacity-0 group-hover:opacity-100 transition-all" />
                    </button>
                ))}
            </div>

            <div className="p-3 border-t border-zinc-200 dark:border-white/5 bg-zinc-50 dark:bg-black/20">
                <Link
                    href="/canvas"
                    data-testid="artifact-full-history"
                    className="block w-full h-8 leading-8 text-center text-[10px] border border-zinc-200 dark:border-white/10 hover:bg-black/5 dark:hover:bg-black/5 dark:bg-white/5 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 rounded transition-all"
                >
                    View Full History
                </Link>
            </div>
        </div>
    );
}

export function formatDate(dateStr: string | null | undefined) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    // Guard against unparseable dates (NaN) — previously fell through every
    // comparison and rendered "Invalid Date" to the user.
    if (isNaN(diff)) return "";
    // Future timestamps (clock skew) produce a negative diff; clamp to "Just
    // now" only for the small near-now window, otherwise show the real date.
    if (diff < 0) return date.toLocaleDateString();
    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
}
