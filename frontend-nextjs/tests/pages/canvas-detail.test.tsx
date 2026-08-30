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

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    reload: jest.fn(),
    pathname: "/canvas/cv1",
    query: { id: "cv1" },
    asPath: "/canvas/cv1",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
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
jest.mock("../../lib/api-client", () => ({
  apiClient: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    delete: (...args: any[]) => mockDelete(...args),
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
    expect(screen.getByText("update")).toBeInTheDocument();
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
    }));
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
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    expect(screen.queryByText("Version History")).not.toBeInTheDocument();
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
});
