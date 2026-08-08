import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AgentsDashboard from "@/pages/agents/index";
import { useRouter } from "next/router";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/hooks/useWebSocket", (): any => ({
  useWebSocket: jest.fn(() => ({
    isConnected: true,
    lastMessage: null as null,
    subscribe: jest.fn(),
  })),
}));

jest.mock("@/components/Agents/AgentTerminal", () => ({
  __esModule: true,
  default: ({ agentName, logs, status }: any) => (
    <div data-testid="agent-terminal">
      <span>{agentName}</span>
      <span>{status}</span>
      {(logs as string[]).map((l, i) => (
        <div key={i} data-testid="terminal-log">{l}</div>
      ))}
    </div>
  ),
}));

jest.mock("@/components/ReasoningChainViewer", () => ({
  __esModule: true,
  default: ({ chainId, onStepFeedback }: any) => (
    <div data-testid="reasoning-viewer">
      <span>chain:{chainId}</span>
      <button
        onClick={() => onStepFeedback("agent-1:run-1:2", 0.9, "good job")}
      >
        rate-step
      </button>
    </div>
  ),
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/agents",
    pathname: "/agents",
    query: {},
    asPath: "/agents",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockPush = jest.fn();
const mockToast = jest.fn();

const AGENTS = [
  {
    id: "agent-1",
    name: "Sales Assistant",
    description: "Handles outreach",
    status: "idle",
    category: "Sales",
    maturity_level: "intern",
  },
  {
    id: "agent-2",
    name: "Reconciler",
    description: "Reconciles inventory",
    status: "running",
    category: "Operations",
    maturity_level: "autonomous",
  },
];

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number, body: any) {
  return { ok: false, status, json: async () => body };
}

describe("AgentsDashboard", () => {
  const mockFetch = jest.fn();
  let getItemSpy: jest.SpyInstance;
  let removeItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue("test-token");
    removeItemSpy = jest.spyOn(Storage.prototype, "removeItem");
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    (useWebSocket as jest.Mock).mockReturnValue({
      isConnected: true,
      lastMessage: null as null,
      subscribe: jest.fn(),
    });
    (useRouter as jest.Mock).mockReturnValue({
      route: "/agents",
      pathname: "/agents",
      query: {},
      asPath: "/agents",
      push: mockPush,
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/run/")) return Promise.resolve(okResponse({ success: true }));
      if (url.includes("/stop")) return Promise.resolve(okResponse({ success: true }));
      if (url.includes("/api/reasoning/feedback")) return Promise.resolve(okResponse({}));
      if (url.endsWith("/api/agents/") || url.includes("/api/agents/agent-")) {
        return Promise.resolve(okResponse({ success: true, data: AGENTS }));
      }
      return Promise.resolve(okResponse({}));
    });
  });

  it("shows the loading state before agents arrive", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<AgentsDashboard />);
    expect(screen.getByText("Loading agents...")).toBeInTheDocument();
  });

  it("renders the agent list fetched from the backend", async () => {
    render(<AgentsDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/"),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      })
    );
    expect(screen.getByText("Reconciler")).toBeInTheDocument();
    expect(screen.getByText("Sales")).toBeInTheDocument();
    expect(screen.getByText("intern")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /agent control center/i })).toBeInTheDocument();
    // Terminal defaults to the first selection state
    expect(screen.getByTestId("agent-terminal")).toHaveTextContent("Terminal");
  });

  it("redirects to login and shows an error when no token exists", async () => {
    getItemSpy.mockReturnValue(null);

    render(<AgentsDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/unauthorized: redirecting to login/i)).toBeInTheDocument();
    });
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("clears the token and redirects on a 401 response", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("/api/agents/")) return Promise.resolve(errResponse(401, {}));
      return Promise.resolve(okResponse({}));
    });

    render(<AgentsDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/session expired/i)).toBeInTheDocument();
    });
    expect(removeItemSpy).toHaveBeenCalledWith("auth_token");
    expect(mockPush).toHaveBeenCalledWith("/login");
  });

  it("shows a server error message when the fetch fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("/api/agents/")) return Promise.resolve(errResponse(500, {}));
      return Promise.resolve(okResponse({}));
    });

    render(<AgentsDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load agents/i)).toBeInTheDocument();
    });
  });

  it("shows the empty state with a marketplace CTA", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("/api/agents/")) {
        return Promise.resolve(okResponse({ success: true, data: [] }));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<AgentsDashboard />);

    await waitFor(() => {
      expect(
        screen.getByText(/no agents found\. create your first agent/i)
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /browse templates/i })).toBeInTheDocument();
  });

  it("runs an agent from the dialog and posts instructions", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /run/i })[0]);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /run agent/i })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/reconcile inventory/i), {
      target: { value: "Close the Q3 deals" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run agent/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/agent-1/run/"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            parameters: { task_input: "Close the Q3 deals" },
          }),
        })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Agent Started Successfully" })
    );
  });

  it("shows the failure toast and a terminal log when the run fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/run/")) {
        return Promise.resolve(errResponse(400, { detail: "Agent is busy" }));
      }
      return Promise.resolve(okResponse({ success: true, data: AGENTS }));
    });

    render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /run/i })[0]);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /run agent/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /run agent/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Failed to start" })
      );
    });
    expect(screen.getByTestId("agent-terminal")).toHaveTextContent("Error: Agent is busy");
  });

  it("stops a running agent", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Reconciler")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /stop/i })[0]);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/agent-2/stop"),
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Agent Stopped" })
    );
  });

  it("edits an agent via the edit dialog", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByTitle("Edit Agent")[0]);

    await waitFor(() => {
      expect(screen.getByText("Edit Agent")).toBeInTheDocument();
    });

    const nameInput = document.getElementById("name") as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "Sales Assistant Pro" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/agent-1"),
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            name: "Sales Assistant Pro",
            description: "Handles outreach",
          }),
        })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Agent Updated" })
    );
  });

  it("opens the reasoning audit and submits step feedback", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByTitle("View Reasoning Trace")[0]);

    await waitFor(() => {
      expect(screen.getByText(/agent reasoning audit/i)).toBeInTheDocument();
    });
    expect(screen.getByTestId("reasoning-viewer")).toHaveTextContent("chain:agent-1");

    fireEvent.click(screen.getByText("rate-step"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/reasoning/feedback"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            agent_id: "agent-1",
            run_id: "run-1",
            step_index: 2,
            step_content: { thought: "" },
            feedback_type: "thumbs_up",
            comment: "good job",
          }),
        })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Feedback Recorded" })
    );
  });

  it("navigates to chat when the chat button is pressed", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByTitle("Chat with Agent")[0]);

    expect(mockPush).toHaveBeenCalledWith("/chat?agent_id=agent-1");
  });

  it("appends agent step updates for the active agent to the terminal", async () => {
    const { rerender } = render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });

    // Activate agent-1 by running it first
    fireEvent.click(screen.getAllByRole("button", { name: /run/i })[0]);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /run agent/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /run agent/i }));
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalled();
    });

    (useWebSocket as jest.Mock).mockReturnValue({
      isConnected: true,
      subscribe: jest.fn(),
      lastMessage: {
        type: "agent_step_update",
        data: {
          agent_id: "agent-1",
          step: { thought: "Looking up inventory", final_answer: "Done" },
        },
      },
    });
    rerender(<AgentsDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId("agent-terminal")).toHaveTextContent(
        "Thought: Looking up inventory"
      );
    });
    expect(screen.getByTestId("agent-terminal")).toHaveTextContent("Final Answer: Done");
  });

  it("refreshes the agent list on an agent_status_change message", async () => {
    const { rerender } = render(<AgentsDashboard />);
    await waitFor(() => {
      expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    });
    const callsAfterMount = mockFetch.mock.calls.length;

    (useWebSocket as jest.Mock).mockReturnValue({
      isConnected: true,
      subscribe: jest.fn(),
      lastMessage: {
        type: "agent_status_change",
        data: { agent_id: "agent-1", status: "success" },
      },
    });
    rerender(<AgentsDashboard />);

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });
});
