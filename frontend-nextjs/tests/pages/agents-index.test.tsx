/**
 * AgentsDashboard page tests (pages/agents/index.tsx, was 0% coverage)
 *
 * Covers: loading/error/empty states, agent list rendering + normalization,
 * search filtering, run/edit/stop/reasoning dialogs, feedback submission,
 * WebSocket live-log streaming, auth redirects, and toast reporting.
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import AgentsDashboard from "@/pages/agents/index";

const mockToast = jest.fn();
const mockRouterPush = jest.fn();
const mockSubscribe = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    reload: jest.fn(),
    pathname: "/agents",
    query: {},
    asPath: "/agents",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

let wsState: any = {
  isConnected: false,
  lastMessage: null,
  subscribe: mockSubscribe,
};

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: () => wsState,
}));

jest.mock("@/components/Agents/AgentCard", () => {
  const MockAgentCard = ({ agent, onRun, onStop, onChat, onEdit, onViewReasoning }: any) => (
    <div data-testid={`agent-card-${agent.id}`}>
      <span className="agent-name">{agent.name}</span>
      <button onClick={() => onRun(agent.id)}>Run</button>
      <button onClick={() => onStop(agent.id)}>Stop</button>
      <button onClick={() => onChat(agent.id)}>Chat</button>
      <button onClick={() => onEdit(agent.id)}>Edit</button>
      <button onClick={() => onViewReasoning(agent.id)}>Reasoning</button>
    </div>
  );
  return { __esModule: true, default: MockAgentCard };
});

jest.mock("@/components/Agents/AgentTerminal", () => ({
  __esModule: true,
  default: ({ logs }: any) => (
    <div data-testid="agent-terminal">
      {Array.isArray(logs) && logs.map((l: string, i: number) => <div key={i}>{l}</div>)}
    </div>
  ),
}));

jest.mock("@/components/Agents/MaturityProgression", () => ({
  __esModule: true,
  MaturityProgression: () => <div data-testid="maturity-progression">Maturity</div>,
}));

jest.mock("@/components/ReasoningChainViewer", () => ({
  __esModule: true,
  default: ({ onStepFeedback }: any) => (
    <div data-testid="reasoning-viewer">
      <button onClick={() => onStepFeedback("a1:run1:2", 0.9, "good")}>ThumbsUp</button>
      <button onClick={() => onStepFeedback("a1:run1:2", 0.1, "bad")}>ThumbsDown</button>
    </div>
  ),
}));

const AGENTS = [
  {
    id: "a1",
    name: "Sales Agent",
    description: "Handles sales ops",
    category: "sales",
    status: "supervised",
  },
  {
    id: "a2",
    name: "Support Agent",
    description: "Handles support",
    category: "support",
    status: "running",
  },
];

const okJson = (body: any) => ({ ok: true, status: 200, statusText: "OK", json: async () => body });

describe("AgentsDashboard", () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "tok");
    wsState = { isConnected: false, lastMessage: null, subscribe: mockSubscribe };
    const okProgress = (id: string) =>
      okJson({ success: true, data: {
        agent_id: id, current_tier: "student", next_tier: "intern",
        next_threshold_episodes: 10, episodes_to_next: 10, episode_count: 0,
        criteria: {},
      }});
    mockFetch = jest.fn((url: any) => {
      const u = typeof url === 'string' ? url : String(url);
      if (u.includes('/graduation-progress')) {
        const id = u.split('/')[u.split('/').length - 2];
        return Promise.resolve(okProgress(id));
      }
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    global.fetch = mockFetch;
  });

  test("shows loading state before agents resolve", () => {
    render(<AgentsDashboard />);
    expect(screen.getByText("Loading agents...")).toBeInTheDocument();
    expect(screen.getByText("Agent Control Center")).toBeInTheDocument();
  });

  test("renders agent list with normalized maturity derived from status", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    expect(screen.getByTestId("agent-card-a2")).toBeInTheDocument();
    expect(screen.getByText("Sales Agent")).toBeInTheDocument();
    expect(screen.getByText("Support Agent")).toBeInTheDocument();
    expect(screen.queryByText("Loading agents...")).not.toBeInTheDocument();
  });

  test("accepts a bare array response shape", async () => {
    mockFetch.mockResolvedValue(okJson(AGENTS));
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
  });

  test("renders empty state when no agents", async () => {
    mockFetch.mockResolvedValue(okJson({ success: true, data: [] }));
    render(<AgentsDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/No agents found/)).toBeInTheDocument()
    );
    expect(screen.getByText("Browse templates")).toBeInTheDocument();
  });

  test("redirects to login when no auth token", async () => {
    localStorage.clear();
    render(<AgentsDashboard />);
    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/login"));
    expect(screen.getByText(/Unauthorized: Redirecting to login/)).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  test("shows error when fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("network down"));
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/Failed to load agents: network down/)).toBeInTheDocument()
    );
    unmount();
  });

  test("poll refresh clears a previously shown error", async () => {
    jest.useFakeTimers();
    try {
      mockFetch.mockRejectedValueOnce(new Error("network down"));
      render(<AgentsDashboard />);
      await waitFor(() =>
        expect(screen.getByText(/Failed to load agents: network down/)).toBeInTheDocument()
      );
      await act(async () => {
        jest.advanceTimersByTime(5000);
      });
      await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
      expect(screen.queryByText(/Failed to load agents/)).not.toBeInTheDocument();
    } finally {
      jest.useRealTimers();
    }
  });

  test("surfaces structured backend error on non-ok response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ error: { message: "DB schema drift" } }),
    });
    render(<AgentsDashboard />);
    await waitFor(() =>
      expect(screen.getByText("Failed to load agents: DB schema drift")).toBeInTheDocument()
    );
  });

  test("non-ok non-JSON body keeps statusText as fallback", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    });
    render(<AgentsDashboard />);
    await waitFor(() =>
      expect(screen.getByText("Failed to load agents: Internal Server Error")).toBeInTheDocument()
    );
  });

  test("401 clears token and redirects to login", async () => {
    localStorage.setItem("auth_token", "stale-token");
    mockFetch.mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({}),
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/login"));
    expect(localStorage.getItem("auth_token")).toBeNull();
  });

  test("filters agents by search query on name or category", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    const search = screen.getByTestId("agent-search-input");
    fireEvent.change(search, { target: { value: "support" } });
    expect(screen.getByTestId("agent-card-a2")).toBeInTheDocument();
    expect(screen.queryByTestId("agent-card-a1")).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "sales" } });
    expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument();
    expect(screen.queryByTestId("agent-card-a2")).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "" } });
    expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument();
    expect(screen.getByTestId("agent-card-a2")).toBeInTheDocument();
  });

  test("run dialog executes agent run successfully and closes", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Run")[0]);
    expect(screen.getByRole("heading", { name: "Run Agent" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/e.g. Reconcile inventory/), {
      target: { value: "Close the books" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));

    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Agent Started Successfully" })
    ));
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Agent Started Successfully",
        description: "Agent a1 is now running with your instructions.",
      })
    );
  });

  test("run dialog shows error toast and appends error log on failure", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes('/run')) {
        return Promise.resolve({ ok: false, status: 400, statusText: "Bad Request", json: async () => ({ detail: "Agent busy" }) });
      }
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Failed to start", description: "Agent busy" })
      )
    );
  });

  test("run dialog handles network errors", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes('/run')) return Promise.reject(new Error("offline"));
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Network error" })
      )
    );
  });

  test("stop agent success path", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Stop")[0]);
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Agent Stopped" })
      )
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/a1/stop"),
      expect.objectContaining({ method: "POST" })
    );
  });

  test("stop agent failure path", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes('/stop')) {
        return Promise.resolve({ ok: false, status: 500, statusText: "Error", json: async () => ({ message: "stop failed" }) });
      }
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Stop")[0]);
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Failed to stop", description: "stop failed" })
      )
    );
  });

  test("stop agent network error path", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes('/stop')) return Promise.reject(new Error("offline"));
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Stop")[0]);
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Network error" })
      )
    );
  });

  test("edit dialog saves changes successfully", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Edit")[0]);
    expect(screen.getByText("Edit Agent")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Sales Agent");

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Sales Pro" } });
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Agent Updated" })
      )
    );
  });

  test("edit dialog surfaces backend error", async () => {
    mockFetch.mockImplementation((url: any, opts?: any) => {
      const u = String(url);
      if (u.includes('/api/agents/') && opts?.method && String(opts.method).toUpperCase() !== "GET") {
        return Promise.resolve({ ok: false, status: 400, statusText: "Bad Request", json: async () => ({ error: { message: "name too short" } }) });
      }
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Edit")[0]);
    fireEvent.click(screen.getByText("Save Changes"));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Failed to update", description: "name too short" })
      )
    );
  });

  test("reasoning modal opens and submits thumbs-up feedback", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Reasoning")[0]);
    expect(screen.getByTestId("reasoning-viewer")).toBeInTheDocument();
    expect(screen.getByText(/Agent Reasoning Audit: Sales Agent/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("ThumbsUp"));
    await waitFor(() => {
      const feedbackCall = mockFetch.mock.calls.find((c: any[]) =>
        String(c[0]).includes("/api/reasoning/feedback")
      );
      expect(feedbackCall).toBeDefined();
      const body = JSON.parse((feedbackCall as any[])[1].body);
      expect(body.feedback_type).toBe("thumbs_up");
      expect(body.agent_id).toBe("a1");
      expect(body.run_id).toBe("run1");
      expect(body.step_index).toBe(2);
      expect(body.comment).toBe("good");
    });
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Feedback Recorded" })
      )
    );

    fireEvent.click(screen.getByText("Close"));
    expect(screen.queryByTestId("reasoning-viewer")).not.toBeInTheDocument();
  });

  test("submits thumbs-down feedback for low score", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Reasoning")[0]);
    fireEvent.click(screen.getByText("ThumbsDown"));
    await waitFor(() => {
      const feedbackCall = mockFetch.mock.calls.find((c: any[]) =>
        String(c[0]).includes("/api/reasoning/feedback")
      );
      const body = JSON.parse((feedbackCall as any[])[1].body);
      expect(body.feedback_type).toBe("thumbs_down");
      expect(body.agent_id).toBe("a1");
    });
  });

  test("subscribes to workspace channel when websocket connects", async () => {
    wsState = { isConnected: true, lastMessage: null, subscribe: mockSubscribe };
    render(<AgentsDashboard />);
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalledWith("workspace:default"));
    expect(screen.getByText("Live Connection")).toBeInTheDocument();
  });

  test("shows offline badge when websocket disconnected", async () => {
    render(<AgentsDashboard />);
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  test("streams agent step updates for the active agent into live logs", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_step_update",
        data: { agent_id: "a1", step: { thought: "checking inventory" } },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Thought: checking inventory/).length).toBeGreaterThan(0)
    );
    unmount();
  });

  test("appends Action prefix log when step has no thought", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_step_update",
        data: { agent_id: "a1", step: { action: { name: "search" } } },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Action: \{/).length).toBeGreaterThan(0)
    );
    unmount();
  });

  test("appends Observation prefix log when step only has output", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_step_update",
        data: { agent_id: "a1", step: { output: "found 3" } },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Observation: found 3/).length).toBeGreaterThan(0)
    );
    unmount();
  });

  test("appends final answer log when step has final_answer", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_step_update",
        data: { agent_id: "a1", step: { thought: "done", final_answer: "42" } },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Final Answer: 42/).length).toBeGreaterThan(0)
    );
    unmount();
  });

  test("agent_status_change appends status log and refreshes agents", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_status_change",
        data: { agent_id: "a1", status: "failed", error: "boom" },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    const callsBeforeRun = mockFetch.mock.calls.length;
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Status Changed: failed - Error: boom/).length).toBeGreaterThan(0)
    );
    expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBeforeRun);
    unmount();
  });

  test("agent_status_change appends status log without error suffix", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_status_change",
        data: { agent_id: "a1", status: "success" },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Status Changed: success/).length).toBeGreaterThan(0)
    );
    unmount();
  });

  test("ignores agent_step_update for a different agent", async () => {
    wsState = {
      isConnected: true,
      lastMessage: {
        type: "agent_step_update",
        data: { agent_id: "other", step: { thought: "irrelevant" } },
      },
      subscribe: mockSubscribe,
    };
    const { unmount } = render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Agent Started Successfully" })
      )
    );
    expect(screen.queryByText(/Thought: irrelevant/)).not.toBeInTheDocument();
    unmount();
  });

  test("chat button navigates to /chat with agent id", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());
    fireEvent.click(screen.getAllByText("Chat")[0]);
    expect(mockRouterPush).toHaveBeenCalledWith("/chat?agent_id=a1");
  });

  test("cancel buttons close run and edit dialogs", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Run")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("heading", { name: "Run Agent" })).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByText("Edit")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Edit Agent")).not.toBeInTheDocument();
  });

  test("feedback submission network error shows error toast", async () => {
    mockFetch.mockImplementation((url: any, opts?: any) => {
      const u = String(url);
      if (u.includes('/feedback')) return Promise.reject(new Error("offline"));
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Reasoning")[0]);
    fireEvent.click(screen.getByText("ThumbsUp"));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Failed to submit feedback" })
      )
    );
  });

  test("save changes network error shows error toast", async () => {
    mockFetch.mockImplementation((url: any, opts?: any) => {
      const u = String(url);
      if (u.includes('/api/agents/') && opts?.method && String(opts.method).toUpperCase() !== "GET") {
        return Promise.reject(new Error("offline"));
      }
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Edit")[0]);
    fireEvent.click(screen.getByText("Save Changes"));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Network error" })
      )
    );
  });
});
