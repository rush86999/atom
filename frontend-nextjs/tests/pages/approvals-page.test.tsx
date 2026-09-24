/**
 * Approvals page (pages/approvals.tsx) — R82.
 *
 * Covers the HITL queue legs (agent actions) and the newly-wired Training
 * Proposals (STUDENT → INTERN) section backed by /api/maturity/training/*:
 * both fetch with the stored JWT, list render, approve/reject POST to the
 * correct endpoints, and failures surface as error notices.
 */
import React from "react";
import { screen, waitFor, fireEvent, within } from "@testing-library/react";
import { renderWithProviders as render } from "../../tests/test-utils";
import "@testing-library/jest-dom";

const mockUseActionProposals = jest.fn();
jest.mock("@/hooks/useActionProposals", () => ({
  useActionProposals: (...args: any[]) => mockUseActionProposals(...args),
}));

import ApprovalsPage from "@/pages/approvals";

const mockFetch = jest.fn();
const okJson = (body: any) => ({ ok: true, status: 200, statusText: "OK", json: async () => body });

const pendingActions = {
  id: "act-1",
  agent_id: "a1",
  action_type: "send_message",
  params: { channel: "slack" },
  reason: "Supervised action needs approval",
  created_at: "2026-01-01T10:00:00Z",
};

const selfDirectedAgent = {
  agent_id: "sd-1",
  agent_name: "Student Hire",
  tier: "student",
  confidence: 0.6,
  episode_progress: 1,
  ready_for_review: true,
  completed_sessions: 1,
  evidence: { episodes: 3, successes: 3, success_ratio: 1, required_episodes: 3 },
  readiness: { ready: true, pathway: "mentor_taught", reason: null },
  recent_episodes: [],
  guidance: [{ label: "Real work recorded: 3/3 episodes", done: true }],
};

const trainingProposal = {
  id: "tp-1",
  agent_id: "a2",
  agent_name: "Support Agent",
  title: "Train on ticket triage",
  description: "Teach the agent to classify urgent tickets.",
  status: "pending",
  capability_gaps: ["urgency classification"],
  created_at: "2026-01-02T09:00:00Z",
};

const actionProposal = {
  id: "ap-1",
  agent_id: "agent-sales-123456789",
  agent_name: "Sales Agent",
  title: "Follow up with the new lead",
  description: "Review the action before it runs.",
  proposal_type: "action",
  status: "pending_approval",
  proposed_action: {
    action_type: "agent_execute",
    prompt: "Draft a reply to the lead",
    parameters: {
      source: "inbox",
      password: "never-render-this",
      nested: { api_token: "also-never-render" },
    },
    source_content: "Lead replied: please follow up today",
  },
  reasoning: "The agent is not mature enough to send automatically.",
  created_at: "2026-01-03T09:00:00Z",
};

const ALL = "/api/agents/approvals/pending";
const TRAIN = "/api/maturity/training/proposals";

const actionQueryState = (overrides: any = {}) => ({
  data: [],
  pendingProposals: [],
  pendingCount: 0,
  isPending: false,
  isError: false,
  isSuccess: true,
  isAuthoritativeEmpty: true,
  approveMutation: { mutateAsync: jest.fn().mockResolvedValue({ execution_result: { success: true } }) },
  rejectMutation: { mutateAsync: jest.fn().mockResolvedValue(undefined) },
  ...overrides,
});

describe("ApprovalsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseActionProposals.mockReturnValue({
      data: [],
      pendingProposals: [],
      pendingCount: 0,
      isPending: false,
      isError: false,
      isSuccess: true,
      isAuthoritativeEmpty: true,
      approveMutation: { mutateAsync: jest.fn().mockResolvedValue({ execution_result: { success: true } }) },
      rejectMutation: { mutateAsync: jest.fn().mockResolvedValue(undefined) },
    });
    localStorage.setItem("auth_token", "tok");
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [selfDirectedAgent], count: 1 }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [trainingProposal] }));
      }
      if (u.includes("/episodes/graduation/promote")) {
        return Promise.resolve(okJson({ agent_id: "sd-1", new_maturity: "intern", promoted: true }));
      }
      return Promise.resolve(okJson([pendingActions]));
    });
    global.fetch = mockFetch as any;
  });

  it("loads and renders the HITL action queue with the auth token", async () => {
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText("send_message")).toBeInTheDocument());
    expect(screen.getByText(/Supervised action needs approval/)).toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/approvals/pending"),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer tok" }) })
    );
  });

  it("renders pending training proposals with agent name and gap count", async () => {
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText("Train on ticket triage")).toBeInTheDocument());
    expect(screen.getByText(/Support Agent/)).toBeInTheDocument();
    expect(screen.getByText(/1 capability gap identified/)).toBeInTheDocument();
  });

  it("renders a bounded, redacted text preview before approval", async () => {
    mockUseActionProposals.mockReturnValue(actionQueryState({
      data: [actionProposal],
      pendingProposals: [actionProposal],
      pendingCount: 1,
      isAuthoritativeEmpty: false,
    }));
    render(<ApprovalsPage />);

    const title = await screen.findByText("Follow up with the new lead");
    const card = title.closest("[aria-busy]") as HTMLElement;
    expect(card).toHaveAttribute("aria-busy", "false");
    expect(within(card).getByText(/Target agent: Sales Agent/)).toBeInTheDocument();
    expect(within(card).getByText(/action: agent_execute/)).toBeInTheDocument();
     expect(within(card).getByText(/^Prompt:/).parentElement).toHaveTextContent("Draft a reply to the lead");
     expect(within(card).getByText(/^Source content:/).parentElement).toHaveTextContent("Lead replied: please follow up today");
    const payload = within(card).getByTestId("action-proposal-payload-preview");
    expect(payload).toHaveTextContent("[REDACTED]");
    expect(payload).not.toHaveTextContent("never-render-this");
    expect(payload).not.toHaveTextContent("also-never-render");
  });

  it("requires a reason for action rejection and passes it to the mutation", async () => {
    const rejectMutation = { mutateAsync: jest.fn().mockResolvedValue(undefined) };
    mockUseActionProposals.mockReturnValue(actionQueryState({
      data: [actionProposal],
      pendingProposals: [actionProposal],
      pendingCount: 1,
      isAuthoritativeEmpty: false,
      rejectMutation,
    }));
    render(<ApprovalsPage />);

    const title = await screen.findByText("Follow up with the new lead");
    const card = title.closest("[aria-busy]") as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "Reject" }));
    const confirm = within(card).getByRole("button", { name: "Confirm rejection" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(card).getByRole("textbox"), { target: { value: "Wait for confirmation" } });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => expect(rejectMutation.mutateAsync).toHaveBeenCalledWith({
      proposalId: "ap-1",
      reason: "Wait for confirmation",
    }));
    expect(await screen.findByText("Proposal rejected.")).toBeInTheDocument();
  });

  it("guards duplicate approvals per proposal while execution is pending", async () => {
    let resolveApproval: (value: { execution_result: { success: boolean } }) => void = () => {};
    const approveMutation = {
      mutateAsync: jest.fn(() => new Promise((resolve) => {
        resolveApproval = resolve;
      })),
    };
    mockUseActionProposals.mockReturnValue(actionQueryState({
      data: [actionProposal],
      pendingProposals: [actionProposal],
      pendingCount: 1,
      isAuthoritativeEmpty: false,
      approveMutation,
    }));
    render(<ApprovalsPage />);

    const title = await screen.findByText("Follow up with the new lead");
    const card = title.closest("[aria-busy]") as HTMLElement;
    const approve = within(card).getByRole("button", { name: "Approve & run" });
    fireEvent.click(approve);
    fireEvent.click(approve);

    expect(approveMutation.mutateAsync).toHaveBeenCalledTimes(1);
    expect(card).toHaveAttribute("aria-busy", "true");
    resolveApproval({ execution_result: { success: true } });
    expect(await screen.findByText("Proposal approved and executed.")).toBeInTheDocument();
  });

  it("renders failed execution separately from a successful approval", async () => {
    const approveMutation = {
      mutateAsync: jest.fn().mockResolvedValue({
        execution_result: { success: false, error: "downstream failed" },
      }),
    };
    mockUseActionProposals.mockReturnValue(actionQueryState({
      data: [actionProposal],
      pendingProposals: [actionProposal],
      pendingCount: 1,
      isAuthoritativeEmpty: false,
      approveMutation,
    }));
    render(<ApprovalsPage />);

    const title = await screen.findByText("Follow up with the new lead");
    const card = title.closest("[aria-busy]") as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "Approve & run" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/execution failed/i);
    expect(screen.queryByText("Proposal approved and executed.")).not.toBeInTheDocument();
  });

  it("shows backend non-2xx decision failures and never renders them as empty", async () => {
    const approveMutation = { mutateAsync: jest.fn().mockRejectedValue(new Error("Approve failed (500)")) };
    mockUseActionProposals.mockReturnValue(actionQueryState({
      data: [actionProposal],
      pendingProposals: [actionProposal],
      pendingCount: 1,
      isAuthoritativeEmpty: false,
      approveMutation,
    }));
    render(<ApprovalsPage />);

    const title = await screen.findByText("Follow up with the new lead");
    const card = title.closest("[aria-busy]") as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "Approve & run" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Approve failed \(500\)/);
    expect(screen.queryByText("No agent action proposals waiting.")).not.toBeInTheDocument();
  });

  it("shows an authoritative error instead of a zero-proposal empty state", async () => {
    mockUseActionProposals.mockReturnValue(actionQueryState({
      data: undefined,
      pendingProposals: undefined,
      pendingCount: null,
      isPending: false,
      isError: true,
      isSuccess: false,
      isAuthoritativeEmpty: false,
    }));
    render(<ApprovalsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not load agent action proposals/);
    expect(screen.queryByText("No agent action proposals waiting.")).not.toBeInTheDocument();
  });

  it("posts approval to the training approve endpoint", async () => {
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText("Train on ticket triage")).toBeInTheDocument());
    const approveBtn = screen.getAllByText("Approve").find((b) => b.closest(".rounded-xl")?.textContent?.includes("Train on ticket triage"))!;
    fireEvent.click(approveBtn);
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/maturity/training/proposals/tp-1/approve"),
        expect.objectContaining({ body: JSON.stringify({ approve: true }) })
      )
    );
  });

  it("posts rejection to the training reject endpoint with a reason", async () => {
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText("Train on ticket triage")).toBeInTheDocument());
    const rejectBtn = screen.getAllByText("Reject").find((b) => b.closest(".rounded-xl")?.textContent?.includes("Train on ticket triage"))!;
    fireEvent.click(rejectBtn);
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/maturity/training/proposals/tp-1/reject"),
        expect.objectContaining({ method: "POST" })
      )
    );
  });

  it("surfaces a supervisor-permission error when training decisions are rejected", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/proposals/tp-1/approve")) {
        return Promise.resolve({ ok: false, status: 403, statusText: "Forbidden", json: async () => ({}) });
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [trainingProposal] }));
      }
      return Promise.resolve(okJson([pendingActions]));
    });
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText("Train on ticket triage")).toBeInTheDocument());
    const approveBtn = screen.getAllByText("Approve").find((b) => b.closest(".rounded-xl")?.textContent?.includes("Train on ticket triage"))!;
    fireEvent.click(approveBtn);
    await waitFor(() =>
      expect(screen.getByText(/Supervisor \(TEAM_LEAD\+\) permission required/)).toBeInTheDocument()
    );
  });

  it("shows the empty states when nothing is waiting", async () => {
    mockFetch.mockResolvedValue(okJson([]));
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText(/Nothing waiting for approval/)).toBeInTheDocument());
     expect(screen.getByText(/No training proposals waiting/)).toBeInTheDocument();
     expect(screen.getByText(/No agent action proposals waiting/)).toBeInTheDocument();
  });
});


describe("Self-directed graduation queue", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseActionProposals.mockReturnValue({
      data: [],
      pendingProposals: [],
      pendingCount: 0,
      isPending: false,
      isError: false,
      isSuccess: true,
      isAuthoritativeEmpty: true,
      approveMutation: { mutateAsync: jest.fn().mockResolvedValue({ execution_result: { success: true } }) },
      rejectMutation: { mutateAsync: jest.fn().mockResolvedValue(undefined) },
    });
    localStorage.setItem("auth_token", "tok");
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [selfDirectedAgent], count: 1 }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [trainingProposal] }));
      }
      if (u.includes("/episodes/graduation/promote")) {
        return Promise.resolve(okJson({ agent_id: "sd-1", new_maturity: "intern", promoted: true }));
      }
      return Promise.resolve(okJson([pendingActions]));
    });
    global.fetch = mockFetch as any;
  });

  it("renders STUDENT evidence cards from the queue endpoint", async () => {
    render(<ApprovalsPage />);
    await waitFor(() =>
      expect(screen.getByTestId("self-directed-pathway-card")).toBeInTheDocument()
    );
    expect(screen.getByText("Student Hire")).toBeInTheDocument();
    expect(screen.getByText("Verified episodes 3/3")).toBeInTheDocument();
  });

  it("promotes from the queue via the graduation endpoint and refreshes", async () => {
    render(<ApprovalsPage />);
    const btn = await screen.findByTestId("self-directed-promote-button");
    fireEvent.click(btn);
    await waitFor(() => {
      const promoteCalls = mockFetch.mock.calls.filter((c: any[]) =>
        String(c[0]).includes("/episodes/graduation/promote")
      );
      expect(promoteCalls.length).toBeGreaterThan(0);
      expect(String(promoteCalls[0][0])).toContain("new_maturity=INTERN");
      expect(promoteCalls[0][1]?.method).toBe("POST");
    });
  });
});
