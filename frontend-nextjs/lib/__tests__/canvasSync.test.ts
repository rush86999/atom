/**
 * canvasSync — the missed-WS-broadcast convergence for canvas co-editing.
 * Covers the response-flag detection (chat_routes maps `data` → `metadata`!),
 * the synthetic canvas:update payload shape hosts apply, and the tab bridge.
 */
import { chatTurnTouchedCanvas, onCanvasRefresh, syncCanvasFromStore, CANVAS_REFRESH_EVENT, type CanvasRefreshDetail } from "../canvasSync";

// api-client mock — syncCanvasFromStore dynamic-imports it.
const getMock = jest.fn();
jest.mock("@/lib/api-client", () => ({
    apiClient: { get: (...args: unknown[]) => getMock(...args) },
}));

// Registry mock — the fallback canvas-id source.
const contextMock = jest.fn();
jest.mock("@/hooks/useCanvasStateRegistration", () => ({
    getOpenCanvasChatContext: (...args: unknown[]) => contextMock(...args),
}));

describe("chatTurnTouchedCanvas", () => {
    it("detects an applied canvas edit under metadata (the real response shape)", () => {
        expect(chatTurnTouchedCanvas({
            success: true,
            metadata: { canvas_edit: { canvas_id: "c-1", updated: true } },
        })).toBe(true);
    });

    it("detects a handled canvas action", () => {
        expect(chatTurnTouchedCanvas({
            metadata: { canvas_action: { canvas_id: "c-1" } },
        })).toBe(true);
    });

    it("ignores a conversational turn and a FAILED edit (updated:false)", () => {
        expect(chatTurnTouchedCanvas({ success: true, message: "hello" })).toBe(false);
        expect(chatTurnTouchedCanvas({
            metadata: { canvas_edit: { canvas_id: "c-1", updated: false } },
        })).toBe(false);
        expect(chatTurnTouchedCanvas(undefined)).toBe(false);
    });
});

describe("syncCanvasFromStore", () => {
    it("fetches the audit trail and dispatches a WS-shaped canvas:update (email metadata included)", async () => {
        getMock.mockResolvedValue({
            data: {
                success: true,
                canvas_id: "c-1",
                canvas_type: "email",
                title: "Draft",
                content: { to: "a@b.c", cc: "", subject: "S", body: "B" },
            },
        });
        const seen: CanvasRefreshDetail[] = [];
        const stop = onCanvasRefresh((d) => seen.push(d));

        await syncCanvasFromStore("c-1");
        stop();

        expect(getMock).toHaveBeenCalledWith("/api/canvas/c-1");
        expect(seen).toHaveLength(1);
        expect(seen[0].canvasId).toBe("c-1");
        expect(seen[0].message.type).toBe("canvas:update");
        expect(seen[0].message.data).toMatchObject({
            action: "update",
            canvas_id: "c-1",
            component: "email",
            data: { to: "a@b.c", subject: "S", body: "B" },
            metadata: { to: "a@b.c", cc: "", subject: "S" },
        });
    });

    it("falls back to the registered open canvas when no id is given", async () => {
        contextMock.mockReturnValue({ canvas_id: "c-open", canvas_type: "markdown" });
        getMock.mockResolvedValue({
            data: { success: true, canvas_id: "c-open", canvas_type: "markdown", content: "# hi" },
        });
        const seen: CanvasRefreshDetail[] = [];
        const stop = onCanvasRefresh((d) => seen.push(d));

        await syncCanvasFromStore();
        stop();

        expect(seen).toHaveLength(1);
        expect(seen[0].message.data.component).toBe("markdown");
    });

    it("is a no-op without any canvas id and never throws on fetch failure", async () => {
        contextMock.mockReturnValue(undefined);
        const seen: CanvasRefreshDetail[] = [];
        const stop = onCanvasRefresh((d) => seen.push(d));
        await syncCanvasFromStore();
        expect(seen).toHaveLength(0);

        getMock.mockRejectedValue(new Error("boom"));
        await syncCanvasFromStore("c-1");
        expect(seen).toHaveLength(0);
        stop();
    });
});

describe("onCanvasRefresh tab bridge", () => {
    it("delivers refreshes posted from another tab via BroadcastChannel", async () => {
        // jsdom has no BroadcastChannel — install a minimal, spec-faithful
        // stub: postMessage reaches every OTHER channel instance with the
        // same name, never the sender itself.
        const RealBC = (global as any).BroadcastChannel;
        const instances: Set<any> = new Set();
        class FakeBroadcastChannel {
            name: string;
            onmessage: ((e: { data: any }) => void) | null = null;
            constructor(name: string) {
                this.name = name;
                instances.add(this);
            }
            postMessage(data: any) {
                for (const inst of instances) {
                    if (inst !== this) inst.onmessage?.({ data });
                }
            }
            close() { instances.delete(this); }
        }
        (global as any).BroadcastChannel = FakeBroadcastChannel;

        const seen: CanvasRefreshDetail[] = [];
        const stop = onCanvasRefresh((d) => seen.push(d));

        const detail: CanvasRefreshDetail = {
            canvasId: "c-2",
            message: { type: "canvas:update", data: { action: "update", canvas_id: "c-2", component: "sheet", data: [["a"]] } },
        };
        new BroadcastChannel(CANVAS_REFRESH_EVENT).postMessage(detail);
        await new Promise((r) => setTimeout(r, 20));
        stop();
        (global as any).BroadcastChannel = RealBC;

        expect(seen).toHaveLength(1);
        expect(seen[0].canvasId).toBe("c-2");
    });
});
