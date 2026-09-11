/**
 * GoalRun detail page — role gating (2026-09-09 role-journey batch 4) plus the
 * 2026-09-10 finish-line fixes: the goal's TITLE leads the page (a UUID is not
 * a goal), terminal runs stop offering loop actions that no-op, and a
 * long-running run shows where it currently is.
 *
 * Every mutating action on this page is team_lead+ on the backend
 * (_require_supervisor in api/goal_run_routes.py). Members previously saw
 * Approve/Advance/Cancel/Distill buttons that 403'd on click — the exact
 * post-click-403 pattern the role-journey passes eliminate. Known
 * non-supervisors now get a read-only timeline with a banner; the role
 * fetch failing (unknown role) stays fail-open — the backend enforces.
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseUserRole = jest.fn();
jest.mock("@/lib/user-role", () => ({
    useUserRole: () => mockUseUserRole(),
}));

jest.mock("next/router", () => ({
    useRouter: () => ({ query: { id: "run-1" }, push: jest.fn() }),
}));

jest.mock("next/head", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("@/lib/goal-run-api", () => ({
  __esModule: true,
  getGoalRun: jest.fn(),
  getGoalRunCanvases: jest.fn().mockResolvedValue([]),
  getGoal: jest.fn(),
  resumeGoalRun: jest.fn(),
  resolveCheckpoint: jest.fn(),
  advanceGoalRun: jest.fn(),
  cancelGoalRun: jest.fn(),
  distillGoalRun: jest.fn(),
  setSupervisionMode: jest.fn(),
  getPromotionEvidence: jest.fn(),
  listAgentLessons: jest.fn(),
  teachAgentFromRun: jest.fn(),
}));

import GoalRunDetailPage from "@/pages/goal-runs/[id]";
import * as api from "@/lib/goal-run-api";
import type { GoalRun } from "@/lib/goal-run-api";

const getGoalRun = api.getGoalRun as jest.Mock;
const getGoalRunCanvases = api.getGoalRunCanvases as jest.Mock;
const getGoal = api.getGoal as jest.Mock;
const getPromotionEvidence = api.getPromotionEvidence as jest.Mock;
const listAgentLessons = api.listAgentLessons as jest.Mock;
const teachAgentFromRun = api.teachAgentFromRun as jest.Mock;
const resumeGoalRun = api.resumeGoalRun as jest.Mock;

const run = (overrides: Partial<GoalRun> = {}): GoalRun => ({
  id: "run-1",
  goal_id: "goal-abcdef12-0000",
  agent_id: "agent-1",
  role: "sales",
  status: "active",
  supervision_mode: "shadow",
  plan: [],
  cursor: null,
  parameters: {},
  waiting_on: null,
  pending_decision: null,
  decision_log: [],
  replan_count: 0,
  steps_executed: 1,
  human_interventions: 0,
  created_by: "owner-1",
  created_at: null,
  ...overrides,
});

const supervisorRole = {
  role: "team_lead", level: 4, isSupervisor: true, isAdmin: false, loading: false,
};

beforeEach(() => {
  getGoalRun.mockReset();
  getGoalRunCanvases.mockReset().mockResolvedValue([]);
  getGoal.mockReset().mockResolvedValue({
    id: "goal-abcdef12-0000",
    title: "Prepare a quote for the Acme lead",
    description: "multi-touch sales process",
    status: "active",
    progress: 0,
    criteria: [],
    key_results: [],
  });
  getPromotionEvidence.mockReset();
  getGoalRun.mockResolvedValue(run());
  listAgentLessons.mockReset().mockResolvedValue([]);
  teachAgentFromRun.mockReset().mockResolvedValue({ status: "ok" });
  resumeGoalRun.mockReset().mockResolvedValue(undefined);
  getPromotionEvidence.mockResolvedValue({
    agent_id: "agent-1",
    recommendation: "shadow",
    evidence: {
      training: { runs: 4, achieved: 3, achieved_ratio: 0.75, interventions_per_run: 0.5 },
      shadow: { runs: 1, achieved: 0, achieved_ratio: 0, interventions_per_run: 0 },
    },
    note: "advisory",
  });
});

describe("GoalRunDetailPage role gating", () => {
  it("member: read-only banner, no coaching actions, no mode switcher", async () => {
    mockUseUserRole.mockReturnValue({
      role: "member", level: 3, isSupervisor: false, isAdmin: false, loading: false,
    });
    render(<GoalRunDetailPage />);
    await waitFor(() =>
      expect(screen.getByTestId("goal-run-detail")).toBeInTheDocument());
    expect(screen.getByTestId("read-only-banner")).toBeInTheDocument();
    expect(screen.queryByTestId("mode-switcher")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /advance/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("promotion-evidence")).not.toBeInTheDocument();
    // The timeline itself stays readable — the record is the point.
    expect(screen.getByTestId("decision-log")).toBeInTheDocument();
  });

  it("supervisor: mode switcher, coaching actions and promotion evidence", async () => {
    mockUseUserRole.mockReturnValue(supervisorRole);
    render(<GoalRunDetailPage />);
    await waitFor(() =>
      expect(screen.getByTestId("mode-switcher")).toBeInTheDocument());
    expect(screen.queryByTestId("read-only-banner")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /advance/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    const evidence = await waitFor(() =>
      screen.getByTestId("promotion-evidence"));
    expect(evidence.textContent).toContain("shadow");
  });

  it("unknown role stays fail-open (backend enforces)", async () => {
    mockUseUserRole.mockReturnValue({
      role: null, level: 0, isSupervisor: false, isAdmin: false, loading: true,
    });
    render(<GoalRunDetailPage />);
    await waitFor(() =>
      expect(screen.getByTestId("mode-switcher")).toBeInTheDocument());
    expect(screen.queryByTestId("read-only-banner")).not.toBeInTheDocument();
  });

  it("member still sees a held decision's rationale (record, not action)", async () => {
    mockUseUserRole.mockReturnValue({
      role: "member", level: 3, isSupervisor: false, isAdmin: false, loading: false,
    });
    getGoalRun.mockResolvedValue(run({
      status: "paused_hitl",
      pending_decision: {
        ts: "", kind: "decision", decision: "SEND_QUOTE",
        rationale: "Quote ready for the lead",
      },
    }));
    render(<GoalRunDetailPage />);
    const card = await waitFor(() => screen.getByTestId("pending-decision"));
    expect(card.textContent).toContain("Quote ready for the lead");
    // But no way to act on it.
    expect(screen.queryByTestId("guidance-input")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^approve/i })).not.toBeInTheDocument();
  });
});

describe("GoalRunDetailPage journey finish-line (2026-09-10)", () => {
  it("leads with the goal's title instead of a bare UUID", async () => {
    mockUseUserRole.mockReturnValue(supervisorRole);
    render(<GoalRunDetailPage />);
    const heading = await waitFor(() => screen.getByTestId("run-goal-heading"));
    expect(heading.textContent).toContain("Prepare a quote for the Acme lead");
    expect(heading.textContent).not.toContain("Goal goal-abc");
  });

  it("active run names its current step in the guidance banner", async () => {
    mockUseUserRole.mockReturnValue(supervisorRole);
    getGoalRun.mockResolvedValue(run({
      status: "active",
      plan: [{ id: "s2", kind: "canvas_work", title: "Draft the quote" }],
      cursor: "s2",
    }));
    render(<GoalRunDetailPage />);
    const guidance = await waitFor(() => screen.getByTestId("run-guidance"));
    expect(guidance.textContent).toContain("Draft the quote");
  });

  it("achieved run: no Advance/Cancel/mode — Distill is the next act", async () => {
    mockUseUserRole.mockReturnValue(supervisorRole);
    getGoalRun.mockResolvedValue(run({ status: "achieved" }));
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("goal-run-detail"));
    expect(screen.queryByRole("button", { name: /advance/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeNull();
    expect(screen.queryByTestId("mode-switcher")).toBeNull();
    expect(screen.getByTestId("distill-button")).toBeInTheDocument();
  });

  it("failed/cancelled runs can still be distilled (learn from the path taken)", async () => {
    mockUseUserRole.mockReturnValue(supervisorRole);
    getGoalRun.mockResolvedValue(run({ status: "failed" }));
    render(<GoalRunDetailPage />);
    await waitFor(() =>
      expect(screen.getByTestId("distill-button")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /advance/i })).toBeNull();
  });
});

describe("GoalRunDetailPage role-based access (any business)", () => {
  const member = (userId: string) => ({
    role: "member", userId, level: 3, isSupervisor: false, isAdmin: false, loading: false,
  });

  it("the run's OWNER works and approves it, but gets no supervisor powers", async () => {
    mockUseUserRole.mockReturnValue(member("owner-1"));
    getGoalRun.mockResolvedValue(run({
      status: "paused_hitl",
      pending_decision: {
        ts: "", kind: "decision", decision: "ADVANCE", rationale: "next step",
      },
    }));
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("pending-decision"));
    // Owner can act on their own run…
    expect(screen.getByRole("button", { name: /^approve/i })).toBeInTheDocument();
    expect(screen.queryByTestId("read-only-banner")).toBeNull();
    // …but mode changes and promotion evidence are supervisor acts.
    expect(screen.queryByTestId("mode-switcher")).toBeNull();
    expect(screen.queryByTestId("promotion-evidence")).toBeNull();
  });

  it("a DIFFERENT member is read-only on someone else's run", async () => {
    mockUseUserRole.mockReturnValue(member("not-the-owner"));
    getGoalRun.mockResolvedValue(run({ status: "active" }));
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("goal-run-detail"));
    expect(screen.getByTestId("read-only-banner")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /advance/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeNull();
  });

  it("a supervisor can act on ANY run they do not own", async () => {
    mockUseUserRole.mockReturnValue({
      role: "team_lead", userId: "not-the-owner", level: 4,
      isSupervisor: true, isAdmin: false, loading: false,
    });
    getGoalRun.mockResolvedValue(run({ status: "active" }));
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("mode-switcher"));
    expect(screen.getByRole("button", { name: /advance/i })).toBeInTheDocument();
    expect(screen.queryByTestId("read-only-banner")).toBeNull();
  });
});

/**
 * Coaching a long-running run (2026-09-11). A goal run is where a supervisor
 * most needs to teach AND to see that the teaching stuck — and "some teaching
 * points are goal specific and others can be generalized", so scope is an
 * explicit, per-lesson choice rather than a global default.
 */
describe("GoalRun detail — coaching", () => {
  beforeEach(() => {
    mockUseUserRole.mockReturnValue({
      role: "team_lead", userId: "owner-1", level: 4,
      isSupervisor: true, isAdmin: false, loading: false,
    });
    getGoalRun.mockResolvedValue(run({ status: "active" }));
    listAgentLessons.mockReset().mockResolvedValue([]);
    teachAgentFromRun.mockReset().mockResolvedValue({ status: "ok" });
    resumeGoalRun.mockReset().mockResolvedValue(undefined);
  });

  it("links to the run agent's chat", async () => {
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("run-coaching"));

    const link = screen.getByTestId("chat-with-run-agent");
    // The run id rides along so a /teach in that chat scopes to this run's
    // goal deterministically (no inference needed).
    expect(link).toHaveAttribute(
      "href", "/chat?agent_id=agent-1&goal_run_id=run-1");
  });

  it("teaches THIS goal by default and confirms where it landed", async () => {
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("run-teach-input"));

    fireEvent.change(screen.getByTestId("run-teach-input"), {
      target: { value: "Always confirm the price with the lead" },
    });
    fireEvent.click(screen.getByTestId("run-teach-submit"));

    await waitFor(() => expect(teachAgentFromRun).toHaveBeenCalledWith(
      "agent-1",
      "Always confirm the price with the lead",
      { scope: "goal", goalId: "goal-abcdef12-0000" },
    ));
    expect(await screen.findByTestId("run-teach-notice")).toHaveTextContent(
      "this goal",
    );
  });

  it("teaches all of the agent's work when the scope is switched", async () => {
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("run-teach-scope"));

    fireEvent.change(screen.getByTestId("run-teach-scope"), {
      target: { value: "global" },
    });
    fireEvent.change(screen.getByTestId("run-teach-input"), {
      target: { value: "Always CC the lead on quotes" },
    });
    fireEvent.click(screen.getByTestId("run-teach-submit"));

    await waitFor(() => expect(teachAgentFromRun).toHaveBeenCalledWith(
      "agent-1",
      "Always CC the lead on quotes",
      { scope: "global", goalId: "goal-abcdef12-0000" },
    ));
    expect(await screen.findByTestId("run-teach-notice")).toHaveTextContent(
      "all of this agent's work",
    );
  });

  it("surfaces a failed teach instead of claiming success", async () => {
    teachAgentFromRun.mockRejectedValue(new Error("Not permitted"));
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("run-teach-input"));

    fireEvent.change(screen.getByTestId("run-teach-input"), {
      target: { value: "Some rule" },
    });
    fireEvent.click(screen.getByTestId("run-teach-submit"));

    expect(await screen.findByTestId("run-teach-notice")).toHaveTextContent(
      "Not permitted",
    );
  });

  it("shows what the agent learned, badged by scope", async () => {
    listAgentLessons.mockResolvedValue([
      { id: "l1", text: "Always log the discount reason", scope: "global" },
      { id: "l2", text: "Use the Q3 price book", scope: "goal", goal_id: "goal-abcdef12-0000" },
    ]);
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("run-lessons"));

    await waitFor(() => expect(screen.getAllByTestId("run-lesson")).toHaveLength(2));
    expect(screen.getByText("Always log the discount reason")).toBeInTheDocument();
    expect(screen.getByText("Use the Q3 price book")).toBeInTheDocument();
    expect(screen.getByTestId("run-lesson-scope-global")).toHaveTextContent("all work");
    expect(screen.getByTestId("run-lesson-scope-goal")).toHaveTextContent("this goal");
  });

  it("sends the override's lesson scope with the resume call", async () => {
    getGoalRun.mockResolvedValue(run({
      status: "active",
      pending_decision: { decision: "ASK_HUMAN", rationale: "unclear pricing" } as any,
    }));
    render(<GoalRunDetailPage />);
    await waitFor(() => screen.getByTestId("guidance-input"));

    fireEvent.change(screen.getByTestId("guidance-input"), {
      target: { value: "check the FX rate first" },
    });
    fireEvent.change(screen.getByTestId("guidance-scope"), {
      target: { value: "goal" },
    });
    fireEvent.click(screen.getByTestId("override-with-guidance"));

    await waitFor(() => expect(resumeGoalRun).toHaveBeenCalledWith(
      "run-1", false, "check the FX rate first", "goal",
    ));
  });
});
