/**
 * Agents page creation→reload join.
 *
 * The real GuidedAgentCreator is mounted by the page; the authoritative list
 * fetch must show the exact returned agent id after a verified create. This
 * complements the component tests (which mock the helper) and the real
 * interceptor counterprobe (which proves no transport auto-replay).
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AgentsDashboard from "@/pages/agents/index";

const mockToast = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: jest.fn(),
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

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: () => ({
    isConnected: false,
    subscribe: jest.fn(),
    onMessage: jest.fn(),
  }),
}));

jest.mock("@/hooks/useProviderStatus", () => ({
  useProviderStatus: () => ({ configured: true, loading: false }),
}));

jest.mock("@/components/Agents/AgentCard", () => ({
  __esModule: true,
  default: ({ agent }: any) => (
    <div data-testid={`agent-card-${agent.id}`}>{agent.name}</div>
  ),
}));

jest.mock("@/components/Agents/AgentTerminal", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-terminal" />,
}));

jest.mock("@/components/Agents/MaturityProgression", () => ({
  MaturityProgression: () => <div data-testid="maturity-progression" />,
}));

jest.mock("@/components/Agents/MaturityApprovalPanel", () => ({
  __esModule: true,
  default: () => <div data-testid="maturity-approval" />,
}));

jest.mock("@/components/Agents/EmployeeOnboardingGuide", () => ({
  EmployeeOnboardingGuide: () => null,
}));

jest.mock("@/components/Agents/AgentLaunchGuide", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/Agents/AutomationSuggestionsPanel", () => ({
  AutomationSuggestionsPanel: () => null,
}));

jest.mock("@/components/Agents/AgentMaturityGuide", () => ({
  AgentMaturityGuideDialog: () => null,
}));

jest.mock("@/components/Agents/AgentJobWaitPanel", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/ReasoningChainViewer", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/lib/agent-onboarding-api", () => ({
  __esModule: true,
  createGuidedAgent: jest.fn(),
  getAutomationSuggestions: jest.fn(),
  newCreationOperationId: jest.fn(() => "ui-intent-1"),
}));

import * as onboardingApi from "@/lib/agent-onboarding-api";

const okJson = (body: any) => ({
  ok: true,
  status: 200,
  statusText: "OK",
  json: async () => body,
});

describe("Agents creation → authoritative reload join", () => {
  const originalFetch = global.fetch;
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "tok");
    (onboardingApi.getAutomationSuggestions as jest.Mock).mockResolvedValue({
      history_summary: {},
      suggestions: [],
    });
    (onboardingApi.newCreationOperationId as jest.Mock).mockReturnValue(
      "ui-intent-1"
    );
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("shows the exact verified agent after guided creation refreshes the list", async () => {
    const create = onboardingApi.createGuidedAgent as jest.Mock;
    let created = false;
    create.mockImplementation(async () => {
      created = true;
      return {
        agent_id: "new-guided-1",
        name: "Guided One",
        category: "Ops",
        maturity: "student",
        created_by: "employee",
        operation_id: "agent:create:intent-1",
        audit_id: "agent:create:intent-1",
        verification: { status: "verified", effect: "committed" },
      };
    });
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/graduation-progress")) {
        const id = u.split("/")[u.split("/").length - 2];
        return Promise.resolve(okJson({
          success: true,
          data: {
            agent_id: id, current_tier: "student", next_tier: "intern",
            next_threshold_episodes: 10, episodes_to_next: 10,
            episode_count: 0, criteria: {},
          },
        }));
      }
      if (u.includes("/api/agents/")) {
        return Promise.resolve(okJson({
          success: true,
          data: created ? [{
            id: "new-guided-1",
            name: "Guided One",
            description: "Created by the guided flow",
            category: "Ops",
            status: "student",
          }] : [],
        }));
      }
      return Promise.resolve(okJson({ success: true, data: [] }));
    });

    render(<AgentsDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/No agents found/)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByTestId("describe-job-button"));
    fireEvent.change(screen.getByTestId("guided-goal-input"), {
      target: { value: "watch invoices and flag overdue ones" },
    });
    fireEvent.click(screen.getByTestId("guided-create-button"));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        "watch invoices and flag overdue ones",
        undefined,
        { operationId: "ui-intent-1" }
      )
    );
    await waitFor(() =>
      expect(screen.getByTestId("agent-card-new-guided-1")).toBeInTheDocument()
    );
    expect(screen.getAllByTestId("agent-card-new-guided-1")).toHaveLength(1);
  });
});
