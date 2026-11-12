/**
 * Served Agents page ↔ Auto-Dev review integration.
 *
 * PR888's reviewed prompt-skill approval/apply surface used to exist only in
 * AgentStudio, which no served route mounts. These tests lock the reachable
 * surface: /agents offers a supervisor-only "Fixes" tab that mounts the shared
 * AutoDevReviewPanel, lists the reviewer's workspace-scoped validated skills on
 * the normal page (no run/selection prerequisite), and posts Apply to the
 * typed backend endpoint. The backend still owns eligibility/authority; the
 * role gate only decides whether the tab is offered.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockUseUserRole = jest.fn();

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
  useToast: () => ({ toast: jest.fn() }),
}));

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: require("../helpers/wsMock").createWebSocketMock(),
}));

jest.mock("@/lib/user-role", () => ({
  useUserRole: () => mockUseUserRole(),
}));

jest.mock("@/lib/auth-headers", () => ({
  handleSessionExpired: jest.fn(() => true),
}));

jest.mock("@/lib/api", () => ({
  __esModule: true,
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

// Isolate the page from sibling supervisor/onboarding transports that have
// their own suites; the real AutoDevReviewPanel stays mounted on purpose.
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
  __esModule: true,
  MaturityProgression: () => <div data-testid="maturity-progression" />,
}));
jest.mock("@/components/ReasoningChainViewer", () => ({
  __esModule: true,
  default: () => <div data-testid="reasoning-viewer" />,
}));
jest.mock("@/components/Agents/MaturityApprovalPanel", () => ({
  __esModule: true,
  default: () => <div data-testid="maturity-approval-panel" />,
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
jest.mock("@/components/Agents/EmployeeOnboardingGuide", () => ({
  EmployeeOnboardingGuide: () => null,
}));
jest.mock("@/components/Agents/AgentLaunchGuide", () => ({
  __esModule: true,
  default: () => null,
}));

import AgentsDashboard from "@/pages/agents/index";

const AGENTS = [
  {
    id: "a1",
    name: "Sales Agent",
    description: "Handles sales ops",
    category: "sales",
    status: "supervised",
  },
];

const VALIDATED_SKILL = {
  kind: "skill",
  id: "skill-1",
  agent_id: "a1",
  name: "repair_outlook_search",
  description: "repair outlook customer email search failures",
  failure: "outlook search failed on the customer email",
  code: "def repair_outlook_search():\n    return []",
  status: "validated",
  reviewed: true,
  apply_eligible: true,
  created_at: "2026-09-02T13:00:00Z",
};

const okJson = (body: any) => ({
  ok: true,
  status: 200,
  statusText: "OK",
  json: async () => body,
});

function supervisorRole() {
  mockUseUserRole.mockReturnValue({
    role: "team_lead",
    userId: "u-1",
    level: 4,
    isSupervisor: true,
    isAdmin: false,
    loading: false,
  });
}

function memberRole() {
  mockUseUserRole.mockReturnValue({
    role: "member",
    userId: "u-2",
    level: 3,
    isSupervisor: false,
    isAdmin: false,
    loading: false,
  });
}

describe("Agents page Auto-Dev review surface", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "tok");
    supervisorRole();

    mockGet.mockImplementation(async (path: string) => {
      if (path === "/api/autodev/candidates?status=pending") {
        return { data: { data: { candidates: [], count: 0 } } };
      }
      if (path === "/api/autodev/candidates?status=validated") {
        return {
          data: {
            data: { candidates: [VALIDATED_SKILL], count: 1 },
          },
        };
      }
      if (path === "/api/autodev/guidance") {
        return { data: { data: { guidance: [], count: 0 } } };
      }
      throw new Error(`Unexpected apiClient.get: ${path}`);
    });
    mockPost.mockResolvedValue({
      data: { success: true, data: { status: "promoted" } },
    });

    global.fetch = jest.fn((url: any) => {
      const u = String(url);
      if (u.includes("/graduation-progress")) {
        return Promise.resolve(
          okJson({
            success: true,
            data: {
              agent_id: "a1",
              current_tier: "student",
              next_tier: "intern",
              next_threshold_episodes: 10,
              episodes_to_next: 10,
              episode_count: 0,
              criteria: {},
            },
          })
        );
      }
      return Promise.resolve(okJson({ success: true, data: AGENTS }));
    }) as any;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test("supervisor opens Fixes and applies a reviewed prompt skill from /agents", async () => {
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    // Reachable without starting a run or selecting an agent first.
    const tab = screen.getByTestId("autodev-review-tab");
    expect(tab).toHaveTextContent("Fixes");
    fireEvent.click(tab);

    const card = await screen.findByTestId("autodev-approved-skill-skill-1");
    expect(card).toHaveTextContent("repair_outlook_search");
    // Workspace-wide candidates are labelled with the employee name from the
    // page's list, not an opaque id.
    const agentLabel = screen.getByTestId("autodev-agent-name");
    expect(agentLabel).toHaveTextContent("Agent: Sales Agent");
    expect(agentLabel).not.toHaveTextContent("a1");
    expect(screen.getByText("Agent: Sales Agent")).toBeInTheDocument();

    // The reviewer queue is workspace-scoped server-side; the page must not
    // narrow it to whatever agent happens to be active (that would hide Apply).
    expect(mockGet).toHaveBeenCalledWith("/api/autodev/candidates?status=pending");
    expect(mockGet).toHaveBeenCalledWith("/api/autodev/candidates?status=validated");

    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith("/api/autodev/skills/skill-1/apply")
    );
    await waitFor(() =>
      expect(
        screen.getByText(/Reviewed skill applied as a typed prompt skill/)
      ).toBeInTheDocument()
    );
  });

  test("known non-supervisors are not offered the review surface", async () => {
    memberRole();
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    expect(screen.queryByTestId("autodev-review-tab")).not.toBeInTheDocument();
    expect(screen.queryByTestId("autodev-review-panel")).not.toBeInTheDocument();
    expect(
      mockGet.mock.calls.some(([path]) => String(path).includes("/api/autodev/"))
    ).toBe(false);
  });

  test("unknown role fails open, matching nav gating; backend remains authority", async () => {
    mockUseUserRole.mockReturnValue({
      role: null,
      userId: null,
      level: 0,
      isSupervisor: false,
      isAdmin: false,
      loading: true,
    });
    render(<AgentsDashboard />);
    await waitFor(() => expect(screen.getByTestId("agent-card-a1")).toBeInTheDocument());

    expect(screen.getByTestId("autodev-review-tab")).toBeInTheDocument();
  });
});
