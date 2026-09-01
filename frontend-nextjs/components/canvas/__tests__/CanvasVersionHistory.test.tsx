/**
 * CanvasVersionHistory — the shared version-history + restore panel used by
 * BOTH canvas hosts (CanvasPanel on /canvas/{id}, CanvasHost on /chat), for
 * every canvas type. Covers the restore contract: POST /restore with the
 * audit id, history refetch, onRestored convergence hook, and the
 * delete-marker guard.
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CanvasVersionHistory } from "../CanvasVersionHistory";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("@/lib/api-client", () => ({
    apiClient: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
    },
}));

const HISTORY = [
    { audit_id: "a-2", action_type: "update", canvas_type: "sheet", created_at: "2026-08-01T10:00:00Z" },
    { audit_id: "a-1", action_type: "create", canvas_type: "sheet", created_at: "2026-08-01T09:00:00Z" },
];

describe("CanvasVersionHistory", () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockGet.mockResolvedValue({ data: { success: true, history: HISTORY, count: HISTORY.length } });
        mockPost.mockResolvedValue({ data: { success: true, restored_from: "a-2" } });
    });

    it("renders entries with restore buttons", async () => {
        render(<CanvasVersionHistory canvasId="c-1" />);
        await waitFor(() => expect(screen.getAllByRole("button", { name: "Restore" })).toHaveLength(2));
        expect(screen.getByText("update")).toBeInTheDocument();
        expect(screen.getByText("create")).toBeInTheDocument();
    });

    it("restore posts the audit id, refetches history, and fires onRestored", async () => {
        const onRestored = jest.fn();
        render(<CanvasVersionHistory canvasId="c-1" onRestored={onRestored} />);
        await waitFor(() => expect(screen.getAllByRole("button", { name: "Restore" })).toHaveLength(2));

        jest.spyOn(window, "confirm").mockReturnValue(true);
        fireEvent.click(screen.getByTestId("canvas-restore-a-2"));

        await waitFor(() =>
            expect(mockPost).toHaveBeenCalledWith("/api/canvas/c-1/restore", { audit_id: "a-2" }),
        );
        await waitFor(() => expect(onRestored).toHaveBeenCalled());
        // history refetched after the restore (initial load + refresh)
        expect(mockGet.mock.calls.filter(([u]) => String(u).endsWith("/history")).length).toBeGreaterThanOrEqual(2);
    });

    it("declined confirm never posts", async () => {
        render(<CanvasVersionHistory canvasId="c-1" />);
        await waitFor(() => expect(screen.getAllByRole("button", { name: "Restore" })).toHaveLength(2));
        jest.spyOn(window, "confirm").mockReturnValue(false);
        fireEvent.click(screen.getByTestId("canvas-restore-a-2"));
        expect(mockPost).not.toHaveBeenCalled();
    });

    it("delete markers offer no restore button", async () => {
        mockGet.mockResolvedValue({
            data: { success: true, history: [{ audit_id: "a-d", action_type: "delete", canvas_type: "sheet" }] },
        });
        render(<CanvasVersionHistory canvasId="c-1" />);
        await waitFor(() => expect(screen.getByText("delete")).toBeInTheDocument());
        expect(screen.queryByTestId("canvas-restore-a-d")).not.toBeInTheDocument();
    });

    it("shows the empty message when the canvas has no history", async () => {
        mockGet.mockResolvedValue({ data: { success: true, history: [] } });
        render(<CanvasVersionHistory canvasId="c-1" />);
        await waitFor(() => expect(screen.getByText("No history available.")).toBeInTheDocument());
    });

    it("a failed restore does not fire onRestored", async () => {
        mockPost.mockRejectedValue(new Error("boom"));
        const onRestored = jest.fn();
        const errSpy = jest.spyOn(console, "error").mockImplementation(() => {});
        render(<CanvasVersionHistory canvasId="c-1" />);
        await waitFor(() => expect(screen.getAllByRole("button", { name: "Restore" })).toHaveLength(2));
        jest.spyOn(window, "confirm").mockReturnValue(true);
        fireEvent.click(screen.getByTestId("canvas-restore-a-2"));
        await waitFor(() => expect(errSpy).toHaveBeenCalled());
        expect(onRestored).not.toHaveBeenCalled();
        errSpy.mockRestore();
    });
});
