/**
 * Agents page wiring for the ordinary information-question journey.
 *
 * Child panels and sockets are leaf doubles; the page's own run-response
 * retention, scoped job locator and authorized job read are the code under
 * test. No live model/provider/browser/account is used.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import userEvent from "@testing-library/user-event";

const push = jest.fn();
const toast = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({ push }),
}));

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: () => ({
    isConnected: false,
    subscribe: jest.fn(),
    onMessage: jest.fn(() => jest.fn()),
  }),
}));

jest.mock("@/hooks/useProviderStatus", () => ({
  useProviderStatus: () => ({ configured: true }),
}));

jest.mock("@/lib/product-profile", () => ({
  useProductProfile: () => ({ isCapabilityEnabled: () => false }),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast }),
}));

jest.mock("@/lib/auth-headers", () => ({
  handleSessionExpired: jest.fn(),
}));

jest.mock("@/components/Agents/AgentCard", () => ({
  __esModule: true,
  default: ({ agent, onRun }: any) => (
    <div data-testid="agent-card">
      <span>{agent.name}</span>
      <button onClick={() => onRun(agent.id)}>Run</button>
    </div>
  ),
}));

jest.mock("@/components/Agents/AgentTerminal", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-terminal" />,
}));
jest.mock("@/components/Agents/MaturityProgression", () => ({
  MaturityProgression: () => null,
}));
jest.mock("@/components/Agents/MaturityApprovalPanel", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/Agents/EmployeeOnboardingGuide", () => ({
  EmployeeOnboardingGuide: () => null,
}));
jest.mock("@/components/Agents/AgentLaunchGuide", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/Agents/GuidedAgentCreator", () => ({
  GuidedAgentCreator: () => null,
}));
jest.mock("@/components/Agents/AutomationSuggestionsPanel", () => ({
  AutomationSuggestionsPanel: () => null,
}));
jest.mock("@/components/Agents/AgentMaturityGuide", () => ({
  AgentMaturityGuideDialog: () => null,
}));
jest.mock("@/components/ReasoningChainViewer", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/shared/ProviderRequiredBanner", () => ({
  ProviderRequiredBanner: () => null,
}));

import AgentsDashboard from "../../pages/agents";

const agent = {
  id: "agent-1",
  name: "Closing Agent",
  description: "closes the books",
  status: "student",
  category: "operations",
  enabled: true,
};

const jobReadback = (jobId: string) => ({
  agent_id: "agent-1",
  job_id: jobId,
  execution_id: `exec-${jobId}`,
  job_status: "waiting",
  outcome: "waiting",
  reason: "execution_waiting",
  next_action: "await_information",
  requires_reconciliation: false,
  wait: {
    id: `wait-${jobId}`,
    status: "pending",
    question: `What does ${jobId} need?`,
    missing_fact: "title",
    correlation_id: `corr-${jobId}`,
    can_answer: true,
  },
});

const json = (data: any, status = 200) =>
  Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => ({ success: status < 400, data }),
  } as any);

describe("Agents page information-question wiring", () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as any;
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "test-token");
    window.localStorage.setItem("user_id", "user-a");
    push.mockReset();
    toast.mockReset();
    fetchMock.mockImplementation((url: string, init: any = {}) => {
      const method = (init.method || "GET").toUpperCase();
      if (method === "POST" && String(url).includes("/run/")) {
        return json({ job_id: "job-new", job_status: "running" });
      }
      if (String(url).includes("/jobs/job-new")) {
        return json(jobReadback("job-new"));
      }
      if (String(url).includes("/jobs/job-old")) {
        return json(jobReadback("job-old"));
      }
      if (String(url).includes("/graduation-progress")) {
        return json({ current_tier: "student", episode_count: 0 });
      }
      if (String(url).includes("/api/agents/")) {
        return json([agent]);
      }
      return json({});
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test("rehydrates the last scoped job on reload from the authorized read", async () => {
    window.localStorage.setItem(
      "atom.agent-job.last.user-a",
      JSON.stringify({ agentId: "agent-1", jobId: "job-old" }),
    );

    render(<AgentsDashboard />);

    expect(
      await screen.findByText("What does job-old need?"),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/agent-1/jobs/job-old"),
      expect.anything(),
    );
  });

  test("does not reuse another user's cached job reference", async () => {
    window.localStorage.setItem(
      "atom.agent-job.last.user-b",
      JSON.stringify({ agentId: "agent-1", jobId: "job-old" }),
    );

    render(<AgentsDashboard />);
    await screen.findByTestId("agent-card");

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/jobs/job-old"),
      ),
    ).toBe(false);
    expect(screen.queryByText("What does job-old need?")).not.toBeInTheDocument();
  });

  test("retains the returned job identity instead of claiming a started run", async () => {
    const user = userEvent.setup();
    render(<AgentsDashboard />);

    await screen.findByTestId("agent-card");
    await user.click(screen.getByRole("button", { name: "Run" }));
    await user.click(screen.getByRole("button", { name: "Run Agent" }));

    expect(
      await screen.findByText("What does job-new need?"),
    ).toBeInTheDocument();
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Agent Started Successfully" }),
    );
    expect(
      JSON.parse(
        window.localStorage.getItem("atom.agent-job.last.user-a") || "{}",
      ),
    ).toEqual({ agentId: "agent-1", jobId: "job-new" });
  });
});
