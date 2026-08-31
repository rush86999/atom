/**
 * Persist a canvas edit to the append-only canvas audit trail
 * (PUT /api/canvas/{id}) — the store the /canvas/{id} page reads, the
 * websocket broadcast updates, and the chat co-editor plans against.
 * Saving anywhere else (the legacy artifacts store) makes the edit
 * invisible to all three, so the next co-edit silently reverts it.
 *
 * Content is the canvas type's NATIVE shape: dict for email drafts
 * ({to, cc, subject, body}), list-of-rows for sheets, plain string for
 * markdown/code/document bodies. The backend stores it verbatim.
 *
 * Returns false on any failure (including 404 — state.id naming a legacy
 * artifact, not a canvas) so the caller can fall back rather than drop
 * the edit.
 */
export async function saveCanvasAudit(
    canvasId: string,
    canvasType: string,
    title: string | undefined,
    content: unknown
): Promise<boolean> {
    try {
        const { apiClient } = await import("@/lib/api");
        // JSON-encode EXPLICITLY: axios passes bare strings/arrays through
        // unserialized, and the backend's `content: Any = Body(...)` only
        // accepts a JSON document.
        await apiClient.put(
            `/api/canvas/${canvasId}` +
            `?canvas_type=${encodeURIComponent(canvasType)}` +
            `&title=${encodeURIComponent(title || "")}`,
            JSON.stringify(content),
            { headers: { "Content-Type": "application/json" } }
        );
        return true;
    } catch {
        return false;
    }
}
