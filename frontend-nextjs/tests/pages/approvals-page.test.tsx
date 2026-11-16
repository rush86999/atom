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

const activeTrainingProposal = {
  ...trainingProposal,
  status: "approved",
  active_session_id: "sess-1",
  session_status: "active",
  agent_tier: "student",
  agent_confidence: 0.6,
  lesson_plan: { mentor: "atom_main", objective: "Triage tickets", tasks: ["Classify one ticket"] },
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

  it("does not announce promotion when completion returns a blocked readiness object", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [], count: 0 }));
      }
      if (u.includes("/maturity/training/sessions/sess-1/complete")) {
        return Promise.resolve(okJson({
          promoted_to_intern: false,
          promotion: { ready: false, reason: "needs work episodes" },
        }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [activeTrainingProposal] }));
      }
      return Promise.resolve(okJson([]));
    });
    render(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Complete Training Session" }));

    expect(await screen.findByText("Training session completed.")).toBeInTheDocument();
    expect(screen.queryByText(/Promotion granted/)).not.toBeInTheDocument();
  });

  it("announces promotion only for an actual true promoted_to_intern flag", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [], count: 0 }));
      }
      if (u.includes("/maturity/training/sessions/sess-1/complete")) {
        return Promise.resolve(okJson({
          promoted_to_intern: true,
          promotion: { ready: true, pathway: "self_directed" },
        }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [activeTrainingProposal] }));
      }
      return Promise.resolve(okJson([]));
    });
    render(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Complete Training Session" }));

    expect(await screen.findByText(/Training session completed\. .*Promotion granted!/)).toBeInTheDocument();
  });

  it("does not announce promotion when the completion response omits the flag", async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [], count: 0 }));
      }
      if (u.includes("/maturity/training/sessions/sess-1/complete")) {
        return Promise.resolve(okJson({ promotion: { ready: true } }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [activeTrainingProposal] }));
      }
      return Promise.resolve(okJson([]));
    });
    render(<ApprovalsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Complete Training Session" }));

    expect(await screen.findByText("Training session completed.")).toBeInTheDocument();
    expect(screen.queryByText(/Promotion granted/)).not.toBeInTheDocument();
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

  it("surfaces a stale goal-approval conflict with the refresh message", async () => {
    mockFetch.mockImplementation((url: any, init?: any) => {
      const u = String(url);
      if (u.includes("/api/agents/approvals/act-1") && init?.method === "POST") {
        return Promise.resolve({
          ok: false,
          status: 409,
          statusText: "Conflict",
          json: async () => ({
            detail: {
              error: "stale_decision_review",
              message: "The pending decision changed after it was reviewed. Refresh the run and review the current decision.",
            },
          }),
        });
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [] }));
      }
      return Promise.resolve(okJson([pendingActions]));
    });
    render(<ApprovalsPage />);
    await waitFor(() => expect(screen.getByText("send_message")).toBeInTheDocument());
    const card = screen.getByText("send_message").closest(".rounded-xl") as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText(/pending decision changed after it was reviewed/)).toBeInTheDocument();
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
  it("does not announce a denied promotion from the queue", async () => {
    const original = mockFetch.getMockImplementation();
    mockFetch.mockImplementation((url: any, init: any) =>
      String(url).includes("/episodes/graduation/promote")
        ? Promise.resolve(okJson({ success: true, data: {
            agent_id: "sd-1", new_maturity: "INTERN", promoted: false,
          } }))
        : original!(url, init));
    render(<ApprovalsPage />);
    fireEvent.click(await screen.findByTestId("self-directed-promote-button"));
    await waitFor(() => expect(screen.getByText(/Promotion was not applied/)).toBeInTheDocument());
    expect(screen.queryByText("Agent promoted to INTERN.")).not.toBeInTheDocument();
    expect(mockFetch.mock.calls.filter((c: any[]) =>
      String(c[0]).includes("/episodes/graduation/promote"))).toHaveLength(1);
  });
});

describe("Never-autonomous task admission presentation", () => {
  const baseAdmission = {
    id: "nt-1",
    agent_id: "agent-finance-12345678",
    action_type: "never_autonomous_task",
    reason:
      "Never-autonomous “Finance January close” matched this task — a human must approve this execution.",
    created_at: "2026-01-05T10:00:00Z",
    params: {
      execution_id: "exec-abc-123",
      task_fingerprint: "sha256:feedfacecafebeef",
      rule_ids: ["rule-fin-jan-close"],
      rule_bindings: [{ id: "rule-fin-jan-close", revision: 7 }],
      owner_user_id: "7bcb8b3c-owner",
      task_profile: {
        difficulty: "complex",
        category: "extraction",
        domain: "finance",
        source: "server",
        signals: {
          difficulty_source: "query_complexity",
          category_source: "task_domain",
          domain_source: "domain_attribution",
        },
      },
      task_input: "Prepare the January finance close and reconcile every ledger account.",
    },
  };

  const taskAdmission = (overrides: any = {}) => ({
    ...baseAdmission,
    ...overrides,
    params: { ...baseAdmission.params, ...(overrides.params || {}) },
  });

  const mockPending = (actions: any[]) => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [], count: 0 }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [] }));
      }
      return Promise.resolve(okJson(actions));
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseActionProposals.mockReturnValue(actionQueryState());
    localStorage.setItem("auth_token", "tok");
    global.fetch = mockFetch as any;
  });

  it("shows the full readable task, server classification and one-execution wording without ids in the primary flow", async () => {
    const visibleMarker = "VISIBLE_MARKER_AFTER_OLD_TRUNCATION";
    const hiddenTailMarker = "HIDDEN_TAIL_MARKER";
    const longTask =
      "Prepare the January finance close. ".padEnd(300, ".") +
      `${visibleMarker} ${"x".repeat(1100)} ${hiddenTailMarker}`;
    mockPending([taskAdmission({ params: { task_input: longTask } })]);

    render(<ApprovalsPage />);

    const card = await screen.findByTestId("approval-action-nt-1");
    expect(within(card).getByText("Task execution admission")).toBeInTheDocument();

    const preview = within(card).getByTestId("task-admission-task-input");
    expect(preview).toHaveTextContent(visibleMarker);
    expect(preview).not.toHaveTextContent(hiddenTailMarker);
    expect(within(card).getByText(/Preview truncated/)).toBeInTheDocument();

    expect(within(card).getByText("Difficulty: complex")).toBeInTheDocument();
    expect(within(card).getByText("Category: extraction")).toBeInTheDocument();
    expect(within(card).getByText("Domain: finance")).toBeInTheDocument();
    expect(within(card).getByText(/Finance January close/)).toBeInTheDocument();

    const oneExecution = within(card).getByTestId("task-admission-one-execution");
    expect(oneExecution).toHaveTextContent("Approving admits this one task execution only.");
    expect(oneExecution).toHaveTextContent("no Modify step");

    const primary = within(card).getByTestId("task-admission-primary");
    expect(primary).not.toHaveTextContent("exec-abc-123");
    expect(primary).not.toHaveTextContent("sha256:feedfacecafebeef");
    expect(primary).not.toHaveTextContent("rule-fin-jan-close");
    expect(within(card).queryByText(/^never_autonomous_task$/)).not.toBeInTheDocument();

    const binding = within(card).getByTestId("task-admission-binding");
    expect((binding as HTMLDetailsElement).open).toBe(false);
    expect(binding).toHaveTextContent("exec-abc-123");
    expect(binding).toHaveTextContent("sha256:feedfacecafebeef");
    expect(binding).toHaveTextContent("rule-fin-jan-close");
    expect(binding).toHaveTextContent("revision 7");

    expect(within(card).queryByRole("button", { name: "Modify" })).not.toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Approve this execution" }));

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/approvals/nt-1"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ decision: "approved" }),
        })
      )
    );
  });

  it("renders hostile task text as escaped literal text, never markup", async () => {
    const hostileTask =
      '<script>window.__pwned=1</script><img src=x onerror="alert(1)"> & <b>literal</b>';
    mockPending([
      taskAdmission({
        params: { task_input: hostileTask },
        reason:
          'Never-autonomous “<img src=x onerror="alert(2)">” matched this task — a human must approve this execution.',
      }),
    ]);

    render(<ApprovalsPage />);

    const card = await screen.findByTestId("approval-action-nt-1");
    const preview = within(card).getByTestId("task-admission-task-input");
    expect(preview.textContent).toBe(hostileTask);
    expect(preview.querySelector("script")).toBeNull();
    expect(preview.querySelector("img")).toBeNull();
    expect(card.querySelector("script")).toBeNull();
    expect(card.querySelector("img")).toBeNull();
    expect(card.textContent).toContain('<img src=x onerror="alert(2)">');
    expect((window as any).__pwned).toBeUndefined();
  });

  it("states task text and classification are unavailable instead of inventing them", async () => {
    mockPending([
      taskAdmission({
        id: "nt-missing",
        reason: undefined,
        params: {
          execution_id: "exec-missing",
          task_fingerprint: "sha256:missing",
          owner_user_id: "owner-missing",
          rule_ids: [],
          rule_bindings: [],
          task_profile: undefined,
          task_input: undefined,
        },
      }),
    ]);

    render(<ApprovalsPage />);

    const card = await screen.findByTestId("approval-action-nt-missing");
    expect(
      within(card).getByTestId("task-admission-task-input-missing")
    ).toHaveTextContent("Task text unavailable");
    expect(
      within(card).getByTestId("task-admission-classification-missing")
    ).toHaveTextContent("Task classification unavailable");
    expect(within(card).queryByText(/^Difficulty:/)).not.toBeInTheDocument();
    expect(within(card).queryByText(/^Category:/)).not.toBeInTheDocument();
    expect(within(card).queryByText(/^Domain:/)).not.toBeInTheDocument();
    expect(
      within(card).getByText(/server did not provide a reason/)
    ).toBeInTheDocument();

    const binding = within(card).getByTestId("task-admission-binding");
    expect(binding).toHaveTextContent("No reviewed rule IDs or revisions were recorded");
    expect(binding).toHaveTextContent("exec-missing");
    expect(within(card).queryByRole("button", { name: "Modify" })).not.toBeInTheDocument();
    expect(
      within(card).getByRole("button", { name: "Approve this execution" })
    ).toBeInTheDocument();
  });

  it("keeps Modify and exact-id decisions for other approval kinds beside an immutable task admission", async () => {
    const ordinaryAction = {
      ...pendingActions,
      id: "act-keep",
      action_type: "send_message",
      params: { channel: "slack", body: "Keep this ordinary approval editable." },
    };
    mockPending([
      taskAdmission({ id: "nt-keep" }),
      ordinaryAction,
    ]);

    render(<ApprovalsPage />);

    const taskCard = await screen.findByTestId("approval-action-nt-keep");
    const ordinaryCard = await screen.findByTestId("approval-action-act-keep");
    expect(within(ordinaryCard).getByText("send_message")).toBeInTheDocument();
    expect(within(ordinaryCard).getByText(/Keep this ordinary approval editable/)).toBeInTheDocument();

    expect(within(taskCard).queryByRole("button", { name: "Modify" })).not.toBeInTheDocument();
    expect(within(ordinaryCard).getByRole("button", { name: "Modify" })).toBeInTheDocument();

    fireEvent.click(within(ordinaryCard).getByRole("button", { name: "Modify" }));
    expect(
      within(ordinaryCard).getByRole("button", { name: "Approve modified" })
    ).toBeInTheDocument();
    fireEvent.click(within(ordinaryCard).getByRole("button", { name: "Cancel" }));

    fireEvent.click(within(taskCard).getByRole("button", { name: "Reject" }));
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/approvals/nt-keep"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ decision: "rejected" }),
        })
      )
    );
    expect(mockFetch).not.toHaveBeenCalledWith(
      expect.stringContaining("/api/agents/approvals/act-keep"),
      expect.objectContaining({ method: "POST" })
    );

    fireEvent.click(within(ordinaryCard).getByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/approvals/act-keep"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ decision: "approved" }),
        })
      )
    );
  });
});

describe("Self-directed graduation queue — qualification details", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseActionProposals.mockReturnValue(actionQueryState());
    localStorage.setItem("auth_token", "tok");
    global.fetch = mockFetch as any;
  });

  it('renders qualification rubric and scoped evidence details', async () => {
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/self-directed")) {
        return Promise.resolve(okJson({ agents: [], count: 0 }));
      }
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [] }));
      }
      if (u.includes("/agents/approvals/pending")) {
        return Promise.resolve(okJson([{
          id: "qual-1",
          agent_id: "a1",
          action_type: "agent_qualification_review",
          reason: "Capability qualification review",
          created_at: "2026-01-04T10:00:00Z",
          params: {
            rubric_criteria: [
              { id: "task_context", label: "Task/context is inspectable" },
              { id: "task_completion", label: "Task objective is completed" },
            ],
            evidence: [
              {
                kind: "agent_execution",
                id: "exec-1",
                task_preview: "Review invoice 1",
                output_preview: "Decision: approve",
              },
            ],
          },
        }]));
      }
      return Promise.resolve(okJson([]));
    });
    render(<ApprovalsPage />);
    await waitFor(() =>
      expect(screen.getAllByText("Capability qualification review").length).toBeGreaterThan(0)
    );
    expect(screen.getByText(/task_context: Task\/context is inspectable/)).toBeInTheDocument();
    expect(screen.getByText(/task_completion: Task objective is completed/)).toBeInTheDocument();
    expect(screen.getByText(/Review invoice 1/)).toBeInTheDocument();
    expect(screen.getByText(/Decision: approve/)).toBeInTheDocument();
  });
});
