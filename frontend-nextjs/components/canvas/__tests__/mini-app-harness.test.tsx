/**
 * MiniAppHarness — agent-driven mini-app authoring panel.
 *
 * Covers the harness surface the bot journey also uses: scaffold →
 * save/dev-run → publish → install, the WS `mini_app_state` live preview, the
 * action-gating (Dev-Run/Publish/Install disabled until scaffold), plus the
 * failure paths (fetch failures, failed runs, RPC throws) and the dev-run
 * result rendering (stdout/stderr/error/state/proposed_ops).
 */
import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
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
    rpcMock.call.mockResolvedValue({ success: true, apps: [] });
    renderHarness();
    expand();
    // Dev-Run / Publish / Install require an app_id.
    expect((screen.getByText("Dev-Run (dry)").closest("button") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText("Publish").closest("button") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText("Install").closest("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("reconnects to the draft app after a reload (blueprint match via mini_app_list)", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_list") {
        return {
          success: true,
          apps: [{ id: "app-reload99", name: "Draft", blueprint_canvas_id: "canvas-1" }],
        };
      }
      return { success: true };
    });
    renderHarness();
    expand();
    await waitFor(() => {
      expect(screen.getByText("app-relo")).toBeInTheDocument(); // badge restored
      expect((screen.getByText("Dev-Run (dry)").closest("button") as HTMLButtonElement).disabled).toBe(false);
    });
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

  it("loads existing logic from the canvas into the editor", async () => {
    apiClientMock.get.mockResolvedValue({ data: { success: true, data: { source: "state = {'loaded': True}" } } });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toHaveValue("state = {'loaded': True}"));
    expect(screen.getByText(/canvas-1/)).toBeInTheDocument(); // editor label targets the canvas
  });

  it("tolerates a logic fetch failure (no logic yet) without crashing", async () => {
    apiClientMock.get.mockRejectedValue(new Error("network down"));
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    expect((screen.getByTestId("logic-editor") as HTMLTextAreaElement).value).toBe("");
  });

  it("clears the editor only on a 404 (no logic yet), not on other fetch errors", async () => {
    apiClientMock.get.mockRejectedValue({ response: { status: 404 } });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    expect((screen.getByTestId("logic-editor") as HTMLTextAreaElement).value).toBe("");
  });

  it("shows a loading placeholder while the logic fetch is pending", async () => {
    let resolveFetch: (v: unknown) => void = () => {};
    apiClientMock.get.mockImplementation(() => new Promise((res) => { resolveFetch = res; }));
    renderHarness();
    expand();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    await act(async () => {
      resolveFetch({ data: { success: true, data: { source: "state = 1" } } });
    });
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
  });

  it("keeps the editor content when the post-scaffold logic refetch fails", async () => {
    // First fetch (canvas-1) succeeds; the refetch for the blueprint canvas 500s.
    apiClientMock.get
      .mockResolvedValueOnce({ data: { success: true, data: { source: "state = {'keep': True}" } } })
      .mockRejectedValueOnce(new Error("boom"));
    rpcMock.call.mockResolvedValue({ success: true, app_id: "app-1", canvas_id: "blueprint-456", logic_source: "" });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toHaveValue("state = {'keep': True}"));
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(apiClientMock.get).toHaveBeenCalledTimes(2));
    // A transient failure must not wipe the source the user is editing.
    // (The refetch flips loading=true, so wait for the editor to come back.)
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toHaveValue("state = {'keep': True}"));
  });

  it("sends comma-separated scopes and dependencies to scaffold", async () => {
    rpcMock.call.mockResolvedValue({ success: true, app_id: "app-9", canvas_id: "bp-9", logic_source: "" });
    renderHarness();
    expand();
    fireEvent.change(screen.getByPlaceholderText("Expense Tracker"), { target: { value: "Reports" } });
    fireEvent.change(screen.getByPlaceholderText("canvas_render"), { target: { value: "canvas_render, storage" } });
    fireEvent.change(screen.getByPlaceholderText("pandas==2.2"), { target: { value: "pandas==2.2, requests" } });
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() =>
      expect(rpcMock.call).toHaveBeenCalledWith(
        "mini_app_scaffold",
        expect.objectContaining({
          name: "Reports",
          declared_scopes: ["canvas_render", "storage"],
          dependencies: ["pandas==2.2", "requests"],
        })
      )
    );
  });

  it("builds on any base canvas type: inherits the host canvas kind, passes spec.canvas_type", async () => {
    rpcMock.call.mockResolvedValue({ success: true, app_id: "app-inv", canvas_id: "bp-inv", logic_source: "" });
    // Mounted on an existing sheets canvas → base type pre-filled.
    renderHarness({ canvasType: "sheets" });
    expand();
    const typeInput = screen.getByPlaceholderText(/crm · accounting/);
    expect(typeInput).toHaveValue("sheets");
    // The user re-targets the app family — any slug is allowed (crm, inventory…).
    fireEvent.change(typeInput, { target: { value: "inventory" } });
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => {
      expect(rpcMock.call).toHaveBeenCalledWith(
        "mini_app_scaffold",
        expect.objectContaining({ spec: { canvas_type: "inventory" } })
      );
      expect(screen.getByText(/\(on inventory\)/)).toBeInTheDocument();
    });
  });

  it("sends no canvas_type when the base type is the native mini_app", async () => {
    rpcMock.call.mockResolvedValue({ success: true, app_id: "app-plain", canvas_id: "bp-plain" });
    renderHarness();
    expand();
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() =>
      expect(rpcMock.call).toHaveBeenCalledWith("mini_app_scaffold", expect.objectContaining({ spec: {} }))
    );
  });

  it("defaults the app name to Untitled Mini-App", async () => {
    rpcMock.call.mockResolvedValue({ success: true, app_id: "app-0", canvas_id: "bp-0" });
    renderHarness();
    expand();
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() =>
      expect(rpcMock.call).toHaveBeenCalledWith("mini_app_scaffold", expect.objectContaining({ name: "Untitled Mini-App" }))
    );
    expect(screen.getByText(/Draft app "Untitled Mini-App" created/)).toBeInTheDocument();
  });

  it("shows the backend error when scaffold fails", async () => {
    rpcMock.call.mockResolvedValue({ success: false, error: "dependency scan failed" });
    renderHarness();
    expand();
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("dependency scan failed")).toBeInTheDocument());
  });

  it("shows the RPC message when scaffold throws", async () => {
    rpcMock.call.mockRejectedValue({ message: "RPC call failed" });
    renderHarness();
    expand();
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("RPC call failed")).toBeInTheDocument());
  });

  it("falls back to a generic message when scaffold throws without a message", async () => {
    rpcMock.call.mockRejectedValue(new Error(""));
    renderHarness();
    expand();
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("Failed to scaffold mini-app")).toBeInTheDocument());
  });

  it("shows the backend detail when saving logic fails", async () => {
    apiClientMock.put.mockRejectedValue({ response: { data: { detail: "syntax error: invalid token" } } });
    renderHarness();
    expand();
    await waitFor(() =>
      expect((screen.getByText("Save Logic").closest("button") as HTMLButtonElement).disabled).toBe(false)
    );
    fireEvent.click(screen.getByText("Save Logic"));
    await waitFor(() => expect(screen.getByText("syntax error: invalid token")).toBeInTheDocument());
  });

  it("shows a generic message when saving logic throws without detail", async () => {
    apiClientMock.put.mockRejectedValue(new Error("network"));
    renderHarness();
    expand();
    await waitFor(() =>
      expect((screen.getByText("Save Logic").closest("button") as HTMLButtonElement).disabled).toBe(false)
    );
    fireEvent.click(screen.getByText("Save Logic"));
    await waitFor(() => expect(screen.getByText("Failed to save logic")).toBeInTheDocument());
  });

  it("edits logic in the editor and saves the new source", async () => {
    apiClientMock.get.mockResolvedValue({ data: { success: true, data: { source: "state = {}" } } });
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("logic-editor"), { target: { value: "state = {'x': 2}" } });
    fireEvent.click(screen.getByText("Save Logic"));
    await waitFor(() =>
      expect(apiClientMock.put).toHaveBeenCalledWith(
        "/api/canvas/canvas-1/logic",
        expect.objectContaining({ source: "state = {'x': 2}", language: "python" })
      )
    );
    expect(screen.getByText(/Logic saved/)).toBeInTheDocument();
  });

  it("saves with the agentId prop (R89 governance requires an AUTONOMOUS agent id)", async () => {
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    renderHarness({ agentId: "agent-autonomous-1" });
    expand();
    await waitFor(() =>
      expect((screen.getByText("Save Logic").closest("button") as HTMLButtonElement).disabled).toBe(false)
    );
    fireEvent.click(screen.getByText("Save Logic"));
    await waitFor(() =>
      expect(apiClientMock.put).toHaveBeenCalledWith(
        "/api/canvas/canvas-1/logic",
        expect.objectContaining({ agent_id: "agent-autonomous-1" })
      )
    );
  });

  it("shows journey guidance when expanded (agent-run path + Firecracker gate)", async () => {
    renderHarness();
    expect(screen.queryByText(/give it to your agent/i)).not.toBeInTheDocument();
    expand();
    expect(screen.getByText(/give it to your agent/i)).toBeInTheDocument();
    expect(screen.getByText(/Firecracker microVM/)).toBeInTheDocument();
  });

  it("dev-runs the blueprint: saves latest source, renders stdout/exit code/state/ops", async () => {
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    apiClientMock.get.mockResolvedValue({ data: { success: true, data: { source: "state = {}" } } });
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1234abcd", canvas_id: "blueprint-456", logic_source: "state = {}" };
      }
      if (action === "mini_app_dev_run") {
        return {
          success: true,
          stdout: "hello from run",
          stderr: "",
          exit_code: 0,
          state_changed: true,
          version: 3,
          state: { runs: 1 },
          proposed_ops: [{ op: "set", key: "runs" }],
        };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1234")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dev-Run (dry)"));
    await waitFor(() => expect(screen.getByText("hello from run")).toBeInTheDocument());
    // Dev-run saves to the blueprint canvas first, then calls the RPC action.
    expect(apiClientMock.put).toHaveBeenCalledWith(
      "/api/canvas/blueprint-456/logic",
      expect.objectContaining({ source: "state = {}" })
    );
    expect(rpcMock.call).toHaveBeenCalledWith("mini_app_dev_run", { app_id: "app-1234abcd", inputs: {} });
    expect(screen.getByText(/exit code: 0 · state_changed: true/)).toBeInTheDocument();
    expect(screen.getByText(/"state": \{/)).toBeInTheDocument();
    expect(screen.getByText(/"proposed_ops": \[/)).toBeInTheDocument();
    // The returned state is mirrored into the live-state preview.
    expect(screen.getByText(/Live instance state \(v3\)/)).toBeInTheDocument();
  });

  it("renders the backend error for a failed dev-run", async () => {
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      if (action === "mini_app_dev_run") {
        return { success: false, error: "SyntaxError: bad token", stdout: "", stderr: "", exit_code: 0 };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dev-Run (dry)"));
    await waitFor(() => expect(screen.getByText("SyntaxError: bad token")).toBeInTheDocument());
  });

  it("renders stderr and the exit code from a failed script run", async () => {
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      if (action === "mini_app_dev_run") {
        return { success: false, stdout: "", stderr: "TypeError: boom", exit_code: 1, state_changed: false };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dev-Run (dry)"));
    await waitFor(() => expect(screen.getByText("TypeError: boom")).toBeInTheDocument());
    expect(screen.getByText(/exit code: 1 · state_changed: false/)).toBeInTheDocument();
    // No committed state on a failed run → no state JSON block.
    expect(screen.queryByText(/"state": \{/)).not.toBeInTheDocument();
  });

  it("shows an error strip when the dev-run call throws", async () => {
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      throw new Error("run crashed");
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dev-Run (dry)"));
    await waitFor(() => expect(screen.getByText("run crashed")).toBeInTheDocument());
  });

  it("publishes and shows the credential-stripped snapshot notice", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1234abcd", canvas_id: "blueprint-456", logic_source: "" };
      }
      if (action === "mini_app_publish") {
        return { success: true, version: 2 };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1234")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Publish"));
    await waitFor(() => expect(screen.getByText(/Published v2/)).toBeInTheDocument());
    expect(screen.getByText(/credential-stripped/)).toBeInTheDocument();
    expect(rpcMock.call).toHaveBeenCalledWith("mini_app_publish", { app_id: "app-1234abcd" });
  });

  it("shows the backend error when publish fails", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      if (action === "mini_app_publish") {
        return { success: false, error: "deps scan failed" };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Publish"));
    await waitFor(() => expect(screen.getByText("deps scan failed")).toBeInTheDocument());
  });

  it("shows a generic message when publish throws", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      throw new Error("Publish failed");
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Publish"));
    await waitFor(() => expect(screen.getByText("Publish failed")).toBeInTheDocument());
  });

  it("installs an immutable instance and previews its WS broadcasts", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1234abcd", canvas_id: "blueprint-456", logic_source: "" };
      }
      if (action === "mini_app_install") {
        return { success: true, canvas_id: "inst-9" };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    const { rerender } = renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1234")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Install"));
    await waitFor(() => expect(screen.getByText(/instance canvas inst-9/)).toBeInTheDocument());
    expect(rpcMock.call).toHaveBeenCalledWith("mini_app_install", { app_id: "app-1234abcd" });
    // Fresh instance → no live state until the first broadcast.
    expect(screen.getByText(/awaiting canvas:update/)).toBeInTheDocument();
    rerender(
      <MiniAppHarness
        canvasId="canvas-1"
        lastMessage={{
          type: "canvas:update",
          data: { action: "mini_app_state", canvas_id: "inst-9", version: 5, data: { saved: true } },
        }}
      />
    );
    await waitFor(() => expect(screen.getByText(/Live instance state \(v5\)/)).toBeInTheDocument());
    expect(screen.getByText(/"saved": true/)).toBeInTheDocument();
  });

  it("shows the backend error when install fails", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      if (action === "mini_app_install") {
        return { success: false, error: "rootfs missing" };
      }
      throw new Error(`unexpected action: ${action}`);
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Install"));
    await waitFor(() => expect(screen.getByText("rootfs missing")).toBeInTheDocument());
  });

  it("shows a generic message when install throws", async () => {
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === "mini_app_scaffold") {
        return { success: true, app_id: "app-1", canvas_id: "bp-1", logic_source: "" };
      }
      throw new Error("Install failed");
    });
    renderHarness();
    expand();
    await waitFor(() => expect(screen.getByTestId("logic-editor")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Scaffold"));
    await waitFor(() => expect(screen.getByText("app-1")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Install"));
    await waitFor(() => expect(screen.getByText("Install failed")).toBeInTheDocument());
  });
});
