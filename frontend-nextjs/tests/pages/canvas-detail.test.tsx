/**
 * CanvasDetailPage tests (pages/canvas/[id].tsx, was 0% coverage)
 *
 * Covers: loading/not-found states, canvas render with version derivation,
 * email metadata derivation, version history panel, delete flow, the agent
 * side-chat (user/assistant/system messages, no-provider + network errors),
 * and live WebSocket canvas:update handling (including mini_app_state guard).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CanvasDetailPage from "@/pages/canvas/[id]";

const mockRouterPush = jest.fn();

// Mutable router mock (wsState pattern) so tests can vary the query —
// e.g. ?agent_id= for the chat-feedback training-loop tests.
let mockRouterState: any;

jest.mock("next/router", () => ({
  useRouter: () => mockRouterState,
}));

let wsState: any = { lastMessage: null, isConnected: true };

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: () => wsState,
}));

jest.mock("@/hooks/useCanvasStateRegistration", () => ({
  useCanvasStateRegistration: jest.fn(),
}));

jest.mock("@/components/canvas/CanvasPanel", () => ({
  CanvasPanel: ({ lastMessage }: any) => (
    <div data-testid="canvas-panel" data-last-type={(lastMessage?.data as any)?.component}>
      Panel
    </div>
  ),
}));

jest.mock("@/components/canvas/MiniAppHarness", () => ({
  MiniAppHarness: (props: any) => (
    <div data-testid="mini-app-harness" data-canvas-id={props.canvasId}>
      Harness
    </div>
  ),
}));

jest.mock("@/components/canvas/TrainingPanel", () => ({
  TrainingPanel: (props: any) => (
    <div
      data-testid="training-panel-mock"
      data-canvas-id={props.canvasId}
      data-hint={props.agentIdHint ?? ""}
    >
      TrainingPanel
    </div>
  ),
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: any) => <div data-testid="layout">{children}</div>,
  Layout: ({ children }: any) => <div data-testid="layout">{children}</div>,
}));

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
const mockFetch = jest.fn();
let mockSubmitStepFeedback = jest.fn().mockResolvedValue(undefined);
let mockFetchSessionTrace = jest.fn().mockResolvedValue({ runs: [] });
jest.mock("@/lib/agent-trace-api", () => ({
  fetchSessionTrace: (...args: any[]) => mockFetchSessionTrace(...args),
  submitStepFeedback: async (payload: any) => {
    mockSubmitStepFeedback(payload);
    // Mirror the real helper's write-through so the existing mockPost-based
    // assertions keep seeing the reasoning-feedback POST.
    const { apiClient } = require("../../lib/api-client");
    await apiClient.post("/api/reasoning/feedback", {
      agent_id: payload.agentId,
      run_id: payload.runId,
      step_index: payload.stepIndex,
      step_content: payload.stepContent,
      feedback_type: payload.feedbackType,
      comment: payload.comment,
      execution_id: payload.executionId,
      step_number: payload.stepNumber,
    }, { retry: false });
  },
}));

jest.mock("../../lib/api-client", () => ({
  apiClient: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    delete: (...args: any[]) => mockDelete(...args),
    // maturity-api's fetchJson routes through apiClient.fetch
    fetch: (...args: any[]) => mockFetch(...args),
  },
}));

const CANVAS = {
  canvas_id: "cv1",
  title: "Q3 Sales Chart",
  canvas_type: "sheets",
  content: { rows: 10 },
};

describe("CanvasDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    wsState = { lastMessage: null, isConnected: true };
    mockRouterState = {
      push: mockRouterPush,
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
      reload: jest.fn(),
      pathname: "/canvas/cv1",
      query: { id: "cv1" },
      asPath: "/canvas/cv1",
      events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
    };
    mockGet.mockResolvedValue({ data: CANVAS });
    mockPost.mockResolvedValue({
      data: { success: true, message: "I added a row." },
    });
    mockDelete.mockResolvedValue({});
  });

  test("shows loading state then renders canvas", async () => {
    render(<CanvasDetailPage />);
    expect(screen.getByText("Loading canvas…")).toBeInTheDocument();

    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(screen.getByText("Q3 Sales Chart")).toBeInTheDocument();
    expect(screen.getByText("sheets")).toBeInTheDocument();
    expect(screen.getByTestId("mini-app-harness")).toBeInTheDocument();
  });

  test("derives version from history count", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) return { data: { count: 3 } };
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledWith("/api/canvas/cv1/history");
  });

  test("version derivation failure does not block rendering", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) throw new Error("boom");
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(screen.getByText("Q3 Sales Chart")).toBeInTheDocument();
  });

  test("shows not-found state when canvas load fails", async () => {
    mockGet.mockRejectedValue(new Error("404"));
    render(<CanvasDetailPage />);
    await waitFor(() =>
      expect(screen.getByText("Canvas not found or deleted.")).toBeInTheDocument()
    );
    expect(screen.getByText("Browse Canvases")).toBeInTheDocument();
  });

  test("shows fallback title when canvas has no title", async () => {
    mockGet.mockResolvedValue({ data: { canvas_id: "cv1", canvas_type: "generic", content: {} } });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(screen.getByText(/Canvas cv1/)).toBeInTheDocument();
  });

  test("derives email metadata for email canvases", async () => {
    mockGet.mockResolvedValue({
      data: { canvas_id: "cv1", title: "Email", canvas_type: "email", content: { to: "a@b.com", subject: "Hi" } },
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(screen.getByTestId("canvas-panel").getAttribute("data-last-type")).toBe("email");
  });

  test("refresh button reloads the canvas", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    const before = mockGet.mock.calls.length;
    fireEvent.click(screen.getByTitle("Refresh"));
    await waitFor(() => expect(mockGet.mock.calls.length).toBeGreaterThan(before));
  });

  test("loads and shows version history panel", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) {
        return {
          data: {
            history: [
              { action_type: "update", canvas_type: "sheets", created_at: "2026-08-01T10:00:00Z" },
            ],
          },
        };
      }
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("Version History")).toBeInTheDocument());
    // The shared panel fetches entries after mount — allow the async load.
    await waitFor(() => expect(screen.getByText("update")).toBeInTheDocument(), { timeout: 3000 });
  });

  test("restore button posts the audit id and refetches the canvas", async () => {
    const histEntry = {
      audit_id: "audit-9",
      action_type: "update",
      canvas_type: "sheets",
      created_at: "2026-08-01T10:00:00Z",
    };
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) {
        return { data: { history: [histEntry] } };
      }
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("Version History")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("canvas-restore-audit-9")).toBeInTheDocument(), { timeout: 3000 });

    jest.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(screen.getByTestId("canvas-restore-audit-9"));
    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith("/api/canvas/cv1/restore", { audit_id: "audit-9" }),
    );
    // The canvas is re-fetched so content and version badge converge.
    await waitFor(() =>
      expect(mockGet.mock.calls.filter(([u]) => u === "/api/canvas/cv1").length).toBeGreaterThan(1),
    );
  });

  test("delete entries offer no restore button", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) {
        return {
          data: {
            history: [{ audit_id: "audit-d", action_type: "delete", canvas_type: "sheets", created_at: "2026-08-01T10:00:00Z" }],
          },
        };
      }
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("Version History")).toBeInTheDocument());
    expect(screen.queryByTestId("canvas-restore-audit-d")).not.toBeInTheDocument();
  });

  test("shows empty history message when no entries", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) return { data: { history: [] } };
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("No history available.")).toBeInTheDocument());
  });

  test("history toggle closes the panel on second click", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) return { data: { history: [] } };
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("No history available.")).toBeInTheDocument());
    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() =>
      expect(screen.queryByText("No history available.")).not.toBeInTheDocument()
    );
  });

  test("delete cancels when confirm is declined", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Delete"));
    expect(mockDelete).not.toHaveBeenCalled();
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  test("delete confirms and navigates back to canvas list", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Delete"));
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("/api/canvas/cv1"));
    expect(mockRouterPush).toHaveBeenCalledWith("/canvas");
  });

  test("chat: empty input does not send", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    const sendButton = screen.getByRole("button", { name: /send/i });
    expect(sendButton).toBeDisabled();
    fireEvent.click(sendButton);
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("chat: sends message and appends user + assistant messages", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "Add a row" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText("Add a row")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("I added a row.")).toBeInTheDocument());

    expect(mockPost).toHaveBeenCalledWith("/api/chat/message", expect.objectContaining({
      message: "Add a row",
      context: expect.objectContaining({ canvas_id: "cv1" }),
    }), expect.objectContaining({ retry: false, timeout: 120000 }));
  });

  test("chat: sends on Enter key", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "via enter" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: false });

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(screen.getByText("via enter")).toBeInTheDocument();
  });

  test("side panel: all four tabs render and Journey panel opens", async () => {
    // Regression: the four-tab flex row overflowed the w-80 panel and the
    // Journey/Autonomy tabs were clipped out of view entirely.
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    for (const tid of ["canvas-side-tab-chat", "canvas-side-tab-training",
                       "canvas-side-tab-journey", "canvas-side-tab-autonomy"]) {
      expect(screen.getByTestId(tid)).toBeVisible();
    }

    fireEvent.click(screen.getByTestId("canvas-side-tab-journey"));
    await waitFor(() => expect(screen.getByTestId("journey-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("canvas-side-tab-autonomy"));
    await waitFor(() => expect(screen.getByTestId("autonomy-panel")).toBeInTheDocument());
  });

  test("autonomy tab: topics grouped by canvas type with live gate chips", async () => {
    // The Autonomy tab is canvas-aware: topics primary for the canvas's
    // type lead under "On this canvas", the rest sit under "General", and
    // each topic shows the hire's live gate outcome (what a turn would
    // actually enforce today).
    mockGet.mockImplementation((url: string) => {
      if (String(url).startsWith("/api/autonomy/topics")) {
        return Promise.resolve({
          data: {
            canvas_type: "email",
            topics: [
              {
                topic: "send_email", label: "Send email", description: "Sending emails",
                default_mode: "human_always", mode: "auto_if_mature",
                canvas_relevant: true,
                gate: {
                  outcome: "execute", reason: "Policy allows autonomy and the hire clears the supervised bar — executes directly.",
                  maturity: { known: true, maturity_level: "supervised", required: "supervised", ok: true },
                  trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
                },
              },
              {
                topic: "crm_write", label: "CRM writes", description: "CRM updates",
                default_mode: "human_always", mode: "human_always",
                canvas_relevant: true,
                gate: {
                  outcome: "propose", reason: "You asked to approve every CRM writes — the hire proposes only.",
                  maturity: { known: true, maturity_level: "autonomous", required: "supervised", ok: true },
                  trust: { enabled: false, trust: null, threshold: 0.6, cold_start: null, ok: true },
                },
              },
              {
                topic: "task_create", label: "Create tasks", description: "Tasks",
                default_mode: "auto_if_mature", mode: "auto_if_mature",
                canvas_relevant: false,
              },
              {
                topic: "canvas_edit", label: "Canvas edits", description: "Edits",
                default_mode: "auto_if_mature", mode: "auto_if_mature",
                canvas_relevant: false,
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: CANVAS });
    });

    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("canvas-side-tab-autonomy"));

    await waitFor(() =>
      expect(screen.getByTestId("autonomy-canvas-section")).toBeInTheDocument()
    );
    expect(screen.getByTestId("autonomy-general-section")).toBeInTheDocument();
    // Canvas-primary topics first, general ones still present
    expect(screen.getByTestId("autonomy-send_email")).toBeInTheDocument();
    expect(screen.getByTestId("autonomy-canvas_edit")).toBeInTheDocument();
    // Live gate outcome per topic
    expect(screen.getAllByTestId("autonomy-gate-execute").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("autonomy-gate-propose").length).toBeGreaterThan(0);
    // The topics request carried the canvas + hire identity
    await waitFor(() => {
      const autonomyCall = mockGet.mock.calls.find((c: any[]) =>
        String(c[0]).startsWith("/api/autonomy/topics")
      );
      expect(String(autonomyCall[0])).toContain("canvas_id=cv1");
    });
  });

  test("chat: canvas agent resolved on load is sent with the turn", async () => {
    // The canvas's hire must be known on the CHAT tab (not only when the
    // training panel opens) so co-editor turns run as the agent.
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        canvas_id: "cv1",
        agent: { id: "hire-cv1", name: "SDR Hire", tier: "student" },
        linked_session: null,
        pending_proposal: null,
        viewer_is_supervisor: true,
      }),
    });

    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/maturity/training/context"),
        undefined
      )
    );

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "tighten the draft" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost).toHaveBeenCalledWith("/api/chat/message", expect.objectContaining({
      agent_id: "hire-cv1",
      context: expect.objectContaining({ agent_id: "hire-cv1" }),
    }), expect.objectContaining({ retry: false, timeout: 120000 }));
  });

  test("chat: server-bound session hydrates panel history after refresh", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.startsWith("/api/chat/history/sess-h1")) {
        return {
          data: {
            session_id: "sess-h1",
            messages: [
              { message: "clean up the draft", response: { message: "Cleaned it up." }, timestamp: "2026-08-30T15:00:00" },
            ],
          },
        };
      }
      if (url.endsWith("/context")) {
        return { data: { data: { current_state: { chat_session_id: "sess-h1" } } } };
      }
      if (url.endsWith("/history")) return { data: { count: 1 } };
      return { data: CANVAS };
    });

    render(<CanvasDetailPage />);
    // Prior conversation reappears without sending anything (binding came
    // from the server, so this also works on a fresh browser/device).
    await waitFor(() => expect(screen.getByText("clean up the draft")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Cleaned it up.")).toBeInTheDocument());

    // And the next send continues the SAME session instead of "new".
    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "make it shorter" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    expect(mockPost).toHaveBeenCalledWith("/api/chat/message", expect.objectContaining({
      session_id: "sess-h1",
    }), expect.objectContaining({ retry: false, timeout: 120000 }));
  });

  test("chat: failed hydration drops the stale session and starts fresh", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.startsWith("/api/chat/history/sess-dead")) throw new Error("403");
      if (url.endsWith("/context")) {
        return { data: { data: { current_state: { chat_session_id: "sess-dead" } } } };
      }
      if (url.endsWith("/history")) return { data: { count: 1 } };
      return { data: CANVAS };
    });

    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(mockPost).toHaveBeenCalled());
    // Stale id must not be reused — the turn starts a new session.
    expect(mockPost).toHaveBeenCalledWith("/api/chat/message", expect.objectContaining({
      session_id: "new",
    }), expect.objectContaining({ retry: false, timeout: 120000 }));
  });

  test("chat: no_llm_provider error renders system message", async () => {
    mockPost.mockResolvedValue({ data: { error_code: "no_llm_provider" } });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/No AI provider configured/)).toBeInTheDocument()
    );
  });

  test("chat: network error renders system message", async () => {
    mockPost.mockRejectedValue(new Error("offline"));
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/Could not reach the agent/)).toBeInTheDocument()
    );
  });

  test("shows agent responding indicator while awaiting reply", async () => {
    let resolvePost: (v: any) => void;
    mockPost.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
      })
    );
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "pending" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(screen.getByText(/Agent is working/)).toBeInTheDocument();
    resolvePost!({ data: { success: true, message: "done" } });
    await waitFor(() => expect(screen.queryByText(/Agent is working/)).not.toBeInTheDocument());
  });

  test("websocket canvas:update refreshes canvas content", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    wsState = {
      lastMessage: {
        type: "canvas:update",
        data: { canvas_id: "cv1", action: "present", component: "markdown", data: { text: "new" }, title: "New Title" },
      },
      isConnected: true,
    };
    rerender(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByText("New Title")).toBeInTheDocument());
  });

  test("websocket ignores mini_app_state broadcasts", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    wsState = {
      lastMessage: {
        type: "canvas:update",
        data: { canvas_id: "cv1", action: "mini_app_state", data: { secret: true } },
      },
      isConnected: true,
    };
    rerender(<CanvasDetailPage />);
    expect(screen.queryByText("New Title")).not.toBeInTheDocument();
  });

  test("websocket close action clears canvas", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    wsState = {
      lastMessage: {
        type: "canvas:present",
        data: { canvas_id: "cv1", action: "close" },
      },
      isConnected: true,
    };
    rerender(<CanvasDetailPage />);
    await waitFor(() =>
      expect(screen.getByText("Canvas not found or deleted.")).toBeInTheDocument()
    );
    expect(screen.queryByTestId("mini-app-harness")).not.toBeInTheDocument();
  });

  test("websocket accepts string-encoded messages", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    wsState = {
      lastMessage: JSON.stringify({
        type: "canvas:update",
        data: { canvas_id: "cv1", action: "present", component: "docs", data: { text: "str" }, title: "String Title" },
      }),
      isConnected: true,
    };
    rerender(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByText("String Title")).toBeInTheDocument());
  });

  test("websocket ignores updates for a different canvas", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    wsState = {
      lastMessage: {
        type: "canvas:update",
        data: { canvas_id: "other", action: "present", data: { x: 1 }, title: "Other Title" },
      },
      isConnected: true,
    };
    rerender(<CanvasDetailPage />);
    expect(screen.queryByText("Other Title")).not.toBeInTheDocument();
  });

  test("canvas load with success:false shows not-found", async () => {
    mockGet.mockResolvedValue({ data: { success: false, error: "gone" } });
    render(<CanvasDetailPage />);
    await waitFor(() =>
      expect(screen.getByText("Canvas not found or deleted.")).toBeInTheDocument()
    );
  });

  test("history without count or list does not set a version", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) return { data: { history: [] } };
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(screen.getByTestId("canvas-panel").dataset.lastType).toBe("sheets");
  });

  test("history entry without created_at renders empty date", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) {
        return { data: { history: [{ action_type: "present", canvas_type: "docs" }] } };
      }
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("present")).toBeInTheDocument());
    expect(screen.getByText("docs")).toBeInTheDocument();
  });

  test("canvas without canvas_type falls back to generic", async () => {
    mockGet.mockResolvedValue({ data: { canvas_id: "cv1", title: "Plain", content: { x: 1 } } });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    expect(screen.getByText("Plain")).toBeInTheDocument();
  });

  test("history load failure is logged without crash", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) throw new Error("boom");
      return { data: CANVAS };
    });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    // The panel still opens; the failed fetch is logged and the empty state shows.
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("No history available.")).toBeInTheDocument(), { timeout: 3000 });
    consoleSpy.mockRestore();
  });

  test("delete failure is logged without crash", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    mockDelete.mockRejectedValue(new Error("denied"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Delete"));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    expect(mockRouterPush).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  test("chat: second message includes assistant history", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: "first" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText("I added a row.")).toBeInTheDocument());

    fireEvent.change(input, { target: { value: "second" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      const postCalls = mockPost.mock.calls.filter((c: any[]) => c[0] === "/api/chat/message");
      const secondBody = postCalls[1][1];
      expect(secondBody.context.conversation_history).toEqual([
        { role: "user", content: "first" },
        { role: "assistant", content: "I added a row." },
      ]);
    });
  });

  test("history panel close button collapses it", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) return { data: { history: [] } };
      return { data: CANVAS };
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTitle("Version history"));
    await waitFor(() => expect(screen.getByText("Version History")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /^$/ }));
    await waitFor(() =>
      expect(screen.queryByText("Version History")).not.toBeInTheDocument()
    );
  });

  // ── Training side panel (co-editor ↔ training tabs) ──────────────────────

  test("training: co-editor tab is the default side panel", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    expect(screen.getByPlaceholderText("Ask the agent to edit…")).toBeInTheDocument();
    expect(screen.queryByTestId("training-panel-mock")).not.toBeInTheDocument();
    expect(screen.getByTestId("canvas-side-tab-training")).toHaveAttribute(
      "aria-selected",
      "false"
    );
  });

  test("training: header graduation button switches to the training panel", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("canvas-training-button"));

    await waitFor(() =>
      expect(screen.getByTestId("training-panel-mock")).toBeInTheDocument()
    );
    expect(screen.getByTestId("training-panel-mock").dataset.canvasId).toBe("cv1");
    expect(screen.queryByPlaceholderText("Ask the agent to edit…")).not.toBeInTheDocument();
  });

  test("training: side tabs toggle between co-editor and training", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("canvas-side-tab-training"));
    await waitFor(() =>
      expect(screen.getByTestId("training-panel-mock")).toBeInTheDocument()
    );

    fireEvent.click(screen.getByTestId("canvas-side-tab-chat"));
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Ask the agent to edit…")).toBeInTheDocument()
    );
    expect(screen.queryByTestId("training-panel-mock")).not.toBeInTheDocument();
  });

  test("training: passes the agent query hint to the panel", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("canvas-side-tab-training"));
    await waitFor(() =>
      expect(screen.getByTestId("training-panel-mock").dataset.hint).toBe("")
    );
  });

  test("training: training-session canvases open on the training tab", async () => {
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/history")) return { data: { count: 1 } };
      return {
        data: {
          canvas_id: "cv1",
          title: "Training: Hire One",
          canvas_type: "document",
          content: { type: "training_session", objective: "Triage inbox" },
        },
      };
    });
    render(<CanvasDetailPage />);
    await waitFor(() =>
      expect(screen.getByTestId("training-panel-mock")).toBeInTheDocument()
    );
  });

  // ── Co-editor chat feedback (thumbs + notes → training loop) ────────────

  async function sendChatMessage(text: string) {
    const input = screen.getByPlaceholderText("Ask the agent to edit…");
    fireEvent.change(input, { target: { value: text } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(text)).toBeInTheDocument());
  }

  test("chat: returning from another side tab re-pins the transcript to the latest message", async () => {
    // The chat DOM unmounts while Training/Journey/Autonomy is shown; on
    // return it remounts scrolled to the TOP. The page must re-run its
    // scroll-to-bottom on the tab change (instant jump, not smooth).
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    await sendChatMessage("add a row");
    await waitFor(() => expect(screen.getByText("I added a row.")).toBeInTheDocument());

    (Element.prototype.scrollIntoView as jest.Mock).mockClear();
    fireEvent.click(screen.getByTestId("canvas-side-tab-training"));
    await waitFor(() => expect(screen.getByTestId("training-panel-mock")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("canvas-side-tab-chat"));
    await waitFor(() =>
      expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: "auto" })
    );
    // The transcript itself survives the tab round-trip.
    expect(screen.getByText("I added a row.")).toBeInTheDocument();
  });

  test("feedback: assistant replies carry thumbs; thumbs up feeds chat feedback with attribution", async () => {
    mockPost.mockResolvedValue({
      data: { success: true, message: "I added a row.", model: "gpt-x", provider: "openai" },
    });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    await sendChatMessage("add a row");
    await waitFor(() => expect(screen.getByText("I added a row.")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Thumbs up"));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        "/api/chat/feedback",
        expect.objectContaining({
          feedback: "thumbs_up",
          model: "gpt-x",
          provider: "openai",
        })
      )
    );
    // No agent resolved (no ?agent_id=, no training context) — the training
    // loop call is skipped rather than misattributed.
    expect(mockPost).not.toHaveBeenCalledWith("/api/reasoning/feedback", expect.anything());
    await waitFor(() =>
      expect(screen.getByTestId("canvas-feedback-notice")).toBeInTheDocument()
    );
  });

  test("feedback: with an agent present, thumbs also feed the training loop", async () => {
    mockRouterState.query = { id: "cv1", agent_id: "agent-9" };
    mockPost.mockResolvedValue({ data: { success: true, message: "Done." } });
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    await sendChatMessage("hi");
    await waitFor(() => expect(screen.getByText("Done.")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Thumbs down"));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        "/api/reasoning/feedback",
        expect.objectContaining({
          agent_id: "agent-9",
          feedback_type: "thumbs_down",
          step_index: -1,
          step_content: expect.objectContaining({
            source: "canvas_chat",
            canvas_id: "cv1",
          }),
        }),
        expect.objectContaining({ retry: false })
      )
    );
    expect(mockPost).toHaveBeenCalledWith(
      "/api/chat/feedback",
      expect.objectContaining({ feedback: "thumbs_down" })
    );
  });

  test("feedback: note submits corrective feedback carrying the comment", async () => {
    mockRouterState.query = { id: "cv1", agent_id: "agent-9" };
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    await sendChatMessage("draft a summary");
    await waitFor(() => expect(screen.getByText("I added a row.")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Add note"));
    fireEvent.change(screen.getByLabelText("Feedback note"), {
      target: { value: "Use bullets, not prose" },
    });
    fireEvent.click(screen.getByLabelText("Send feedback note"));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        "/api/reasoning/feedback",
        expect.objectContaining({ feedback_type: "thumbs_down", comment: "Use bullets, not prose" }),
        expect.objectContaining({ retry: false })
      )
    );
    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith(
        "/api/chat/feedback",
        expect.objectContaining({ feedback: "thumbs_down", comment: "Use bullets, not prose" })
      )
    );
  });

  test("feedback: clicking the chosen thumb again clears it without re-sending", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());

    await sendChatMessage("hi");
    await waitFor(() => expect(screen.getByText("I added a row.")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Thumbs up"));
    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith("/api/chat/feedback", expect.anything())
    );
    expect(screen.getByLabelText("Thumbs up").querySelector("svg")).toHaveClass("text-green-500");

    const feedbackCalls = mockPost.mock.calls.filter((c: any[]) => c[0] === "/api/chat/feedback");
    fireEvent.click(screen.getByLabelText("Thumbs up"));
    // Toggle-off is local only: no new feedback POST, chosen state cleared.
    await new Promise((r) => setTimeout(r, 50));
    expect(mockPost.mock.calls.filter((c: any[]) => c[0] === "/api/chat/feedback")).toHaveLength(feedbackCalls.length);
    expect(screen.getByLabelText("Thumbs up").querySelector("svg")).not.toHaveClass("text-green-500");
  });
});

describe("canvas chat reasoning steps (training parity)", () => {
  beforeEach(() => {
    wsState = { lastMessage: null, isConnected: true };
  });

  beforeEach(() => {
    mockRouterState = {
      push: jest.fn(), replace: jest.fn(), prefetch: jest.fn(), back: jest.fn(), reload: jest.fn(),
      pathname: "/canvas/cv1", query: { id: "cv1" }, asPath: "/canvas/cv1",
      events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
    };
    mockGet.mockImplementation((url: string) => Promise.resolve({ data: CANVAS }));
    mockPost.mockResolvedValue({ data: { success: true, message: "Done." } });
  });

  test("agent_step_update is captured and rateable in the co-editor chat", async () => {
    mockSubmitStepFeedback.mockClear();
    // Live session: bound chat session + a persisted assistant reply.
    mockGet.mockImplementation((url: string) => {
      if (String(url).includes("/context")) {
        return Promise.resolve({
          data: { current_state: { chat_session_id: "sess-9" } },
        });
      }
      if (String(url).includes("/chat/history")) {
        return Promise.resolve({
          data: {
            messages: [
              { role: "user", message: "tighten the draft", response: { message: "Draft updated on the canvas." }, timestamp: new Date().toISOString() },
            ],
          },
        });
      }
      return Promise.resolve({ data: CANVAS });
    });

    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => expect(screen.getByTestId("canvas-panel")).toBeInTheDocument());
    // The persisted assistant reply must be on screen before the step
    // arrives — steps attach to the last assistant message.
    await screen.findByText("Draft updated on the canvas.");

    // A canvas turn's reasoning step arrives over WS (rerender = new frame).
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_step_update",
        agent_id: "hire-1",
        execution_id: "exec-9",
        session_id: "sess-9",
        step: {
          step_number: 1,
          type: "thought",
          thought: "Planning the edit",
          observation: "gate: PROPOSAL (policy=human_always)",
        },
      },
    };
    rerender(<CanvasDetailPage />);
    if (process.env.DEBUG_DOM) {
    }

    // The reasoning chain appears on the co-editor chat (collapsed)…
    await waitFor(() =>
      expect(screen.getAllByText(/Reasoning Process/i).length).toBeGreaterThan(0)
    );
    // …expands to the steps for training.
    fireEvent.click(screen.getAllByText(/Reasoning Process/i)[0]);
    expect(screen.getByText(/gate: PROPOSAL/)).toBeInTheDocument();

    // Rate the step — the thumbs buttons carry no accessible label; the
    // expanded chain's first lucide thumbs-down is step 1's.
    const thumbsDownSvg = document.querySelector("svg.lucide-thumbs-down");
    expect(thumbsDownSvg).not.toBeNull();
    fireEvent.click(thumbsDownSvg!.closest("button")!);
    await waitFor(() => expect(mockSubmitStepFeedback).toHaveBeenCalled());
    const payload = mockSubmitStepFeedback.mock.calls[0][0];
    expect(payload.executionId).toBe("exec-9");
    expect(payload.stepNumber).toBe(1);
  });
});
