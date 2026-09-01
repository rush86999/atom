"use client";

/**
 * Version history + restore, shared by every canvas host (CanvasPanel on
 * /canvas/{id}, CanvasHost on /chat) and every canvas type — the audit trail
 * stores each version's full content regardless of type, and the backend
 * POST /restore appends the restored version as a new audit row (append-only:
 * the pre-restore state stays in history).
 *
 * After a restore, the content fans out through lib/canvasSync so EVERY
 * mounted canvas host converges — this one, and the same canvas open in
 * other tabs (the WS broadcast alone can be silently missed).
 */
import React, { useEffect, useState } from "react";
import { syncCanvasFromStore } from "@/lib/canvasSync";

interface HistoryEntry {
    audit_id?: string;
    action_type: string;
    canvas_type?: string;
    created_at?: string | null;
}

interface CanvasVersionHistoryProps {
    canvasId: string;
    /** Called after a successful restore so the host can converge immediately. */
    onRestored?: () => void;
}

export function CanvasVersionHistory({ canvasId, onRestored }: CanvasVersionHistoryProps) {
    const [history, setHistory] = useState<any[]>([]);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const { apiClient } = await import("@/lib/api-client");
                const resp = await apiClient.get(`/api/canvas/${canvasId}/history`);
                const data = (resp as any).data || resp;
                if (!cancelled) setHistory(data.history || []);
            } catch (e) {
                console.error("Failed to load history:", e);
            } finally {
                if (!cancelled) setLoaded(true);
            }
        })();
        return () => { cancelled = true; };
    }, [canvasId]);

    const handleRestore = async (auditId: string) => {
        if (!confirm("Restore this version? The current version stays in history.")) return;
        try {
            const { apiClient } = await import("@/lib/api-client");
            await apiClient.post(`/api/canvas/${canvasId}/restore`, { audit_id: auditId });
            // Fan the restored content out to every mounted canvas host (this
            // one and other tabs), refresh this list so the new restore row is
            // visible, and let the host converge its own version badge.
            await syncCanvasFromStore(canvasId);
            const resp = await apiClient.get(`/api/canvas/${canvasId}/history`);
            const data = (resp as any).data || resp;
            setHistory(data.history || []);
            onRestored?.();
        } catch (e) {
            console.error("Restore failed:", e);
        }
    };

    return (
        <div className="divide-y">
            {history.length === 0 ? (
                <p className="text-sm text-muted-foreground p-4">{loaded ? "No history available." : "Loading…"}</p>
            ) : (
                history.map((h: HistoryEntry, i: number) => (
                    <div key={i} className="p-3 text-xs">
                        <div className="flex justify-between mb-1">
                            <span className="font-medium uppercase">{h.action_type}</span>
                            <span className="text-muted-foreground">
                                {h.created_at ? new Date(h.created_at).toLocaleString() : ""}
                            </span>
                        </div>
                        <div className="flex justify-between items-center gap-2">
                            <span className="text-muted-foreground">{h.canvas_type}</span>
                            {h.action_type !== "delete" && h.audit_id && (
                                <button
                                    onClick={() => handleRestore(h.audit_id as string)}
                                    title="Restore this version — appends it as the newest version (current stays in history)"
                                    data-testid={`canvas-restore-${h.audit_id}`}
                                    className="text-[10px] px-2 py-0.5 rounded border border-zinc-200 dark:border-white/10 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors"
                                >
                                    Restore
                                </button>
                            )}
                        </div>
                    </div>
                ))
            )}
        </div>
    );
}
