/**
 * Convergence for canvas co-editing (every canvas app, not just email).
 *
 * The WS `canvas:update` broadcast is the primary live carrier for agent
 * edits, but it can be silently missed: an auth-expiry close never reconnects
 * while the JWT lives in localStorage, and a throttled background tab can
 * miss frames. The chat reply still arrives (REST), so the user reads
 * "Updated the draft…" while the open canvas shows stale content — observed
 * live on /canvas/{id} (audit row + broadcast landed; page never changed).
 *
 * After a chat turn the backend flagged as a handled canvas edit/action, the
 * chat surface calls syncCanvasFromStore(): it fetches the canvas's current
 * content from the durable audit trail (the same source GET /api/canvas/{id}
 * and the co-editor planner read) and re-broadcasts it LOCALLY as a synthetic
 * `canvas:update` via a window event. Every mounted canvas host (CanvasPanel
 * on /canvas/{id}, CanvasHost on /chat) applies it through the exact guarded
 * path it already uses for WS messages — echo-guard, per-type state seeding,
 * everything.
 */
import { getOpenCanvasChatContext } from "@/hooks/useCanvasStateRegistration";

export const CANVAS_REFRESH_EVENT = "atom:canvas-refresh";

export interface CanvasRefreshDetail {
    canvasId: string;
    /** WS-shaped message — hosts apply it like an incoming socket frame. */
    message: { type: "canvas:update"; data: Record<string, unknown> };
}

/** Subscribe a canvas host to local refreshes. Returns the unsubscribe fn.
    Bridges tabs via BroadcastChannel — the co-editor turn often happens in a
    DIFFERENT tab (chat page) than the one showing the canvas, and window
    events don't cross tabs. */
export function onCanvasRefresh(
    handler: (detail: CanvasRefreshDetail) => void,
): () => void {
    if (typeof window === "undefined") return () => {};
    const listener = (e: Event) => handler((e as CustomEvent).detail);
    window.addEventListener(CANVAS_REFRESH_EVENT, listener);
    let channel: BroadcastChannel | null = null;
    try {
        channel = new BroadcastChannel(CANVAS_REFRESH_EVENT);
        channel.onmessage = (e) => handler(e.data as CanvasRefreshDetail);
    } catch {
        // No BroadcastChannel (old browser / privacy mode) — same-tab only.
    }
    return () => {
        window.removeEventListener(CANVAS_REFRESH_EVENT, listener);
        channel?.close();
    };
}

/**
 * True when the chat response flags a handled canvas turn. NOTE the shape:
 * chat_routes maps the orchestrator's `data` to `metadata` in the response
 * body, so the flags live at `metadata.canvas_edit` / `metadata.canvas_action`
 * (not `data.canvas_edit` — that mistake cost a debugging round).
 */
export function chatTurnTouchedCanvas(data: Record<string, any> | undefined | null): boolean {
    return !!(
        data?.metadata?.canvas_edit?.updated ||
        data?.metadata?.canvas_action
    );
}

/**
 * Fetch the canvas's current content from the audit trail and dispatch the
 * local refresh event. ``canvasId`` optional — falls back to the single
 * registered open canvas (the same registry the co-editor context reads).
 * Best-effort by design: any failure just skips this convergence pass.
 */
export async function syncCanvasFromStore(canvasId?: string): Promise<void> {
    try {
        const resolved = canvasId
            ? { canvas_id: canvasId }
            : (getOpenCanvasChatContext() || undefined);
        const id = resolved?.canvas_id;
        if (!id) return;

        const { apiClient } = await import("@/lib/api-client");
        const resp = await apiClient.get(`/api/canvas/${id}`);
        const body = (resp as any).data || resp;
        if (!body || body.success === false) return;

        const content = body.content;
        const canvasType = String(body.canvas_type || "generic");
        // Mirror tools/canvas_crud_tool.update_canvas_content's WS broadcast
        // shape exactly — hosts are built for that contract, and the email
        // composer reads To/Cc/Subject from `metadata`.
        const payload: Record<string, unknown> = {
            action: "update",
            canvas_id: id,
            component: canvasType,
            data: content,
            title: body.title,
        };
        if (canvasType === "email" && content && typeof content === "object") {
            payload.metadata = {
                to: (content as any).to || "",
                cc: (content as any).cc || "",
                subject: (content as any).subject || "",
            };
        }

        const detail: CanvasRefreshDetail = {
            canvasId: id,
            message: { type: "canvas:update", data: payload },
        };
        window.dispatchEvent(new CustomEvent(CANVAS_REFRESH_EVENT, { detail }));
        try {
            // Same refresh in every other tab of this origin.
            new BroadcastChannel(CANVAS_REFRESH_EVENT).postMessage(detail);
        } catch {
            // Same-tab only (see onCanvasRefresh).
        }
    } catch {
        // Convergence is additive: a missed refresh is no worse than the
        // missed broadcast it compensates for.
    }
}
