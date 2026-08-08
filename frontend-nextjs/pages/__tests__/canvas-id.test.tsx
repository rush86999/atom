import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CanvasDetailPage from "@/pages/canvas/[id]";
import { apiClient } from "@/lib/api-client";
import { useRouter } from "next/router";
import { useWebSocket } from "@/hooks/useWebSocket";

jest.mock("@/lib/api-client", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/components/canvas/CanvasPanel", () => ({
  CanvasPanel: ({ lastMessage }: { lastMessage: any }) => (
    <div data-testid="canvas-panel">
      {lastMessage?.data?.title || "no-message"}
    </div>
  ),
}));

jest.mock("@/components/canvas/MiniAppHarness", () => ({
  MiniAppHarness: () => <div data-testid="mini-app-harness" />,
}));

jest.mock("@/hooks/useCanvasStateRegistration", () => ({
  useCanvasStateRegistration: jest.fn(),
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/canvas/[id]",
    pathname: "/canvas/[id]",
    query: { id: "canvas-1" },
    asPath: "/canvas/canvas-1",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

jest.mock("@/hooks/useWebSocket", (): any => ({
  useWebSocket: jest.fn(() => ({
    lastMessage: null as null,
    isConnected: true,
    subscribe: jest.fn(),
  })),
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;
const mockPush = jest.fn();

const CANVAS = {
  id: "canvas-1",
  title: "Q3 Revenue Chart",
  canvas_type: "charts",
  content: { type: "bar", data: [1, 2, 3] },
};

function routerWithQuery(query: Record<string, string>) {
  return {
    route: "/canvas/[id]",
    pathname: "/canvas/[id]",
    query,
    asPath: `/canvas/${query.id}`,
    push: mockPush,
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  };
}

describe("CanvasDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(routerWithQuery({ id: "canvas-1" }));
    (useWebSocket as jest.Mock).mockReturnValue({
      lastMessage: null as null,
      isConnected: true,
      subscribe: jest.fn(),
    });
    (mockApiClient.get as jest.Mock).mockResolvedValue({ data: CANVAS });
    (mockApiClient.post as jest.Mock).mockResolvedValue({
      data: { success: true, message: "Done!" },
    });
    (mockApiClient.delete as jest.Mock).mockResolvedValue({ data: { success: true } });
    window.confirm = jest.fn(() => true) as any;
  });

  it("shows the loading state while fetching the canvas", () => {
    (mockApiClient.get as jest.Mock).mockReturnValue(new Promise(() => {}));
    render(<CanvasDetailPage />);
    expect(screen.getByText("Loading canvas…")).toBeInTheDocument();
  });

  it("renders the canvas title, type badge and panel once loaded", async () => {
    render(<CanvasDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    expect(mockApiClient.get).toHaveBeenCalledWith("/api/canvas/canvas-1");
    expect(screen.getByText("charts")).toBeInTheDocument();
    // CanvasPanel receives a synthetic canvas:update message with the content
    expect(screen.getByTestId("canvas-panel")).toHaveTextContent("Q3 Revenue Chart");
    expect(screen.getByTestId("mini-app-harness")).toBeInTheDocument();
    expect(screen.getByText("Agent Co-Editor")).toBeInTheDocument();
  });

  it("shows the not-found card when the canvas is missing", async () => {
    (mockApiClient.get as jest.Mock).mockResolvedValue({ data: { success: false } });

    render(<CanvasDetailPage />);

    await waitFor(() => {
      expect(screen.getByText("Canvas not found or deleted.")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /browse canvases/i })).toBeInTheDocument();
  });

  it("sends a chat message and renders the assistant reply", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Ask the agent to edit…"), {
      target: { value: "Add a bar chart" },
    });
    fireEvent.click(screen.getByRole("button", { name: "" }));

    await waitFor(() => {
      expect(screen.getByText("Done!")).toBeInTheDocument();
    });

    expect(mockApiClient.post).toHaveBeenCalledWith(
      "/api/chat/message",
      expect.objectContaining({
        message: "Add a bar chart",
        context: expect.objectContaining({ canvas_id: "canvas-1" }),
      })
    );
    expect(screen.getByText("Add a bar chart")).toBeInTheDocument();
  });

  it("does not send an empty chat message", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "" }));

    expect(mockApiClient.post).not.toHaveBeenCalled();
  });

  it("shows a system message when no LLM provider is configured", async () => {
    (mockApiClient.post as jest.Mock).mockResolvedValue({
      data: { success: false, error_code: "no_llm_provider" },
    });

    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Ask the agent to edit…"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "" }));

    await waitFor(() => {
      expect(screen.getByText(/no ai provider configured/i)).toBeInTheDocument();
    });
  });

  it("shows a system error message when the chat request throws", async () => {
    (mockApiClient.post as jest.Mock).mockRejectedValue(new Error("down"));

    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Ask the agent to edit…"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "" }));

    await waitFor(() => {
      expect(screen.getByText(/could not reach the agent/i)).toBeInTheDocument();
    });
  });

  it("loads and displays version history", async () => {
    (mockApiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes("/history")) {
        return Promise.resolve({
          data: {
            history: [
              {
                action_type: "edit",
                created_at: "2026-07-02T00:00:00Z",
                canvas_type: "charts",
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: CANVAS });
    });

    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle("Version history"));

    await waitFor(() => {
      expect(screen.getByText("Version History")).toBeInTheDocument();
    });
    expect(screen.getByText("edit")).toBeInTheDocument();
  });

  it("shows 'No history available' when history is empty", async () => {
    (mockApiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes("/history")) {
        return Promise.resolve({ data: { history: [] } });
      }
      return Promise.resolve({ data: CANVAS });
    });

    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle("Version history"));

    await waitFor(() => {
      expect(screen.getByText("No history available.")).toBeInTheDocument();
    });
  });

  it("deletes the canvas and navigates back to the list", async () => {
    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle("Delete"));

    await waitFor(() => {
      expect(mockApiClient.delete).toHaveBeenCalledWith("/api/canvas/canvas-1");
    });
    expect(mockPush).toHaveBeenCalledWith("/canvas");
  });

  it("does not delete when the user cancels the confirmation", async () => {
    window.confirm = jest.fn(() => false) as any;

    render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle("Delete"));

    expect(mockApiClient.delete).not.toHaveBeenCalled();
  });

  it("updates the rendered canvas when a canvas:update WS message arrives", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    (useWebSocket as jest.Mock).mockReturnValue({
      lastMessage: {
        type: "canvas:update",
        data: {
          action: "present",
          canvas_id: "canvas-1",
          title: "Renamed Chart",
          component: "charts",
          data: { type: "pie" },
        },
      },
      isConnected: true,
      subscribe: jest.fn(),
    });
    rerender(<CanvasDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Renamed Chart" })).toBeInTheDocument();
    });
  });

  it("ignores canvas:update messages for other canvases", async () => {
    const { rerender } = render(<CanvasDetailPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Q3 Revenue Chart" })).toBeInTheDocument();
    });

    (useWebSocket as jest.Mock).mockReturnValue({
      lastMessage: {
        type: "canvas:update",
        data: { action: "present", canvas_id: "other-canvas", title: "Wrong" },
      },
      isConnected: true,
      subscribe: jest.fn(),
    });
    rerender(<CanvasDetailPage />);

    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Wrong")).not.toBeInTheDocument();
  });
});
