/**
 * Canvas journey API — blank-canvas creation, agent attachment, and
 * agent-gated data loading.
 *
 * The journey: create a blank canvas → attach a hire → load data. Data
 * loading is refused by the backend (409 NO_AGENT_ON_CANVAS) until a hire
 * is attached; the UI mirrors that gate. Auth rides the shared apiClient
 * (Bearer token attached by its interceptor).
 */

export interface CanvasAgent {
    agent_id: string;
    canvas_id: string;
    name: string;
    description?: string | null;
    category?: string | null;
    maturity?: string | null;
    confidence?: number | null;
    presence_role?: string | null;
    joined_at?: string | null;
}

/** Registry entry as served by GET /api/agents/ (the attach picker's source). */
export interface AgentRegistryEntry {
    id: string;
    name: string;
    description?: string | null;
    status?: string | null;
    category?: string | null;
    last_run?: string | null;
}

export interface BlankCanvasOptions {
    title?: string;
    description?: string;
    canvas_type?: string;
}

export async function createBlankCanvas(
    opts?: BlankCanvasOptions,
): Promise<{ canvas_id: string; url: string }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post("/api/canvas", {
        title: opts?.title ?? null,
        description: opts?.description ?? null,
        canvas_type: opts?.canvas_type || "document",
    });
    return res.data;
}

/** The user's hires (attach-picker source). Accepts the wrapped
 * {success, data} envelope or a bare array — same tolerance as the
 * agents page, because the endpoint sits behind BaseAPIRouter. */
export async function listAttachableAgents(): Promise<AgentRegistryEntry[]> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.get("/api/agents/");
    const body = res.data;
    return Array.isArray(body) ? body : body?.data || [];
}

export async function listCanvasAgents(canvasId: string): Promise<CanvasAgent[]> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.get(`/api/canvas/${canvasId}/agents`);
    return res.data?.agents || [];
}

export async function attachCanvasAgent(
    canvasId: string,
    agentId: string,
    role = "collaborator",
): Promise<{ agents: CanvasAgent[] }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.post(`/api/canvas/${canvasId}/agents`, {
        agent_id: agentId,
        role,
    });
    return res.data;
}

export async function detachCanvasAgent(
    canvasId: string,
    agentId: string,
): Promise<{ agents: CanvasAgent[] }> {
    const { apiClient } = await import("@/lib/api");
    const res = await apiClient.delete(`/api/canvas/${canvasId}/agents/${agentId}`);
    return res.data;
}

/** Load a file into the canvas's world (agent-gated backend). */
export async function uploadCanvasData(canvasId: string, file: File): Promise<Record<string, any>> {
    const { apiClient } = await import("@/lib/api");
    const form = new FormData();
    form.append("file", file);
    const res = await apiClient.post(`/api/canvas/${canvasId}/data/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
    });
    return res.data;
}
