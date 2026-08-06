/**
 * MiniAppHarness — agent-driven mini-app authoring panel.
 *
 * Covers the harness surface the bot journey also uses: scaffold →
 * save/dev-run → publish → install, the WS `mini_app_state` live preview, and
 * the action-gating (Dev-Run/Publish/Install disabled until scaffold).
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MiniAppHarness } from "../MiniAppHarness";
import { apiClient } from "@/lib/api";
import { rpc } from "@/lib/rpc-client";

// Monaco is heavy; swap for a controlled textarea.
jest.mock("@monaco-editor/react", () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="logic-editor"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

jest.mock("@/lib/api", () => ({
  apiClient: { get: jest.fn(), put: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));

jest.mock("@/lib/rpc-client", () => ({
  rpc: { call: jest.fn(), listActions: jest.fn() },
}));

const apiClientMock = apiClient as unknown as {
  get: jest.Mock;
  put: jest.Mock;
  post: jest.Mock;
  delete: jest.Mock;
};
const rpcMock = rpc as unknown as { call: jest.Mock; listActions: jest.Mock };

const renderHarness = (props: any = {}) =>
  render(<MiniAppHarness canvasId="canvas-1" {...props} />);

const expand = () => fireEvent.click(screen.getByText("Mini-App Harness"));

describe("MiniAppHarness", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mount effect loads existing logic (404 → empty source).
    apiClientMock.get.mockResolvedValue({ data: { success: true, data: { source: "" } } });
  });

  it("collapses by default and expands to the authoring actions", async () => {
    renderHarness();
    expect(screen.queryByText("Scaffold")).not.toBeInTheDocument();
    expand();
    expect(screen.getByText("Scaffold")).toBeInTheDocument();
    expect(screen.getByText("Save Logic")).toBeInTheDocument();
    expect(screen.getByText("Dev-Run (dry)")).toBeInTheDocument();
    expect(screen.getByText("Publish")).toBeInTheDocument();
    expect(screen.getByText("Install")).toBeInTheDocument();
  });

  it("disables run/publish/install until scaffolded", async () => {
    renderHarness();
    expand();
    // Dev-Run / Publish / Install require an app_id.
    expect((screen.getByText("Dev-Run (dry)").closest("button") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText("Publish").closest("button") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText("Install").closest("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("scaffolds a draft app and shows the app badge + notice", async () => {
    rpcMock.call.mockResolvedValue({
      success: true,
      app_id: "app-1234abcd",
      canvas_id: "blueprint-456",
      logic_source: "state = {}",
    });
    renderHarness();
    expand();
    fireEvent.change(screen.getByPlaceholderText("Expense Tracker"), { target: { value: "Expense Tracker" } });
    fireEvent.click(screen.getByText("Scaffold"));

    await waitFor(() => {
      expect(rpcMock.call).toHaveBeenCalledWith("mini_app_scaffold", expect.objectContaining({ name: "Expense Tracker" }));
      expect(screen.getByText(/Draft app "Expense Tracker" created/)).toBeInTheDocument();
      expect(screen.getByText("app-1234")).toBeInTheDocument(); // badge (first 8 chars)
    });
  });

  it("saves logic to the target canvas via PUT /api/canvas/{id}/logic", async () => {
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    renderHarness();
    expand();
    // Wait for the mount logic-fetch to finish (loading=false) or the button stays disabled.
    await waitFor(() =>
      expect((screen.getByText("Save Logic").closest("button") as HTMLButtonElement).disabled).toBe(false)
    );
    fireEvent.click(screen.getByText("Save Logic"));
    await waitFor(() => {
      expect(apiClientMock.put).toHaveBeenCalledWith("/api/canvas/canvas-1/logic", expect.objectContaining({ source: "" }));
      expect(screen.getByText(/Logic saved/)).toBeInTheDocument();
    });
  });

  it("previews live instance state from the WS mini_app_state broadcast", async () => {
    renderHarness({ lastMessage: { type: "canvas:update", data: { action: "mini_app_state", canvas_id: "canvas-1", version: 2, data: { runs: 2 } } } });
    expand();
    await waitFor(() => expect(screen.getByText(/Live instance state/)).toBeInTheDocument());
    expect(screen.getByText(/v2/)).toBeInTheDocument();
    expect(screen.getByText(/"runs": 2/)).toBeInTheDocument();
  });

  it("ignores non-mini-app WS broadcasts", async () => {
    renderHarness({ lastMessage: { type: "canvas:update", data: { action: "present", canvas_id: "canvas-1", data: { x: 1 } } } });
    expand();
    expect(screen.getByText(/awaiting canvas:update/)).toBeInTheDocument();
  });
});
