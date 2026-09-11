import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import GoalRunsIndexPage, { waitingLabel } from "@/pages/goal-runs/index";
import { guidanceFor } from "@/pages/goal-runs/[id]";
import * as api from "@/lib/goal-run-api";
import type { GoalRun } from "@/lib/goal-run-api";

jest.mock("next/head", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
}));

jest.mock("next/router", () => ({
  __esModule: true,
  useRouter: () => ({ push: jest.fn(), query: {} }),
}));

jest.mock("sonner", () => ({
  __esModule: true,
  toast: { success: jest.fn(), error: jest.fn() },
}));

const mockUseUserRole = jest.fn();
jest.mock("@/lib/user-role", () => ({
  __esModule: true,
  useUserRole: () => mockUseUserRole(),
  // The page gates "can this person start a run" on the shared helper; keep
  // the real semantics (member=3) rather than stubbing a boolean.
  meetsRole: (role: string | null, minLevel: number) => {
    const levels: Record<string, number> = {
      viewer: 2, member: 3, team_lead: 4, workspace_admin: 5, owner: 7,
    };
    return (levels[String(role)] ?? 0) >= minLevel;
  },
  MEMBER_MIN_LEVEL: 3,
}));

jest.mock("@/lib/canvas-api", () => ({
  __esModule: true,
  listAttachableAgents: jest.fn().mockResolvedValue([]),
}));

jest.mock("@/lib/goal-run-api", () => ({
  __esModule: true,
  listGoalRuns: jest.fn(),
  listGoals: jest.fn(),
  createGoal: jest.fn(),
  createGoalRun: jest.fn(),
}));

const listGoalRuns = api.listGoalRuns as jest.Mock;
const listGoals = api.listGoals as jest.Mock;

const run = (overrides: Partial<GoalRun>): GoalRun => ({
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
  replan_count: 1,
  steps_executed: 2,
  human_interventions: 0,
  created_at: null,
  ...overrides,
});

const supervisor = { role: "team_lead", level: 4, isSupervisor: true, isAdmin: false, loading: false };
const member = { role: "member", level: 3, isSupervisor: false, isAdmin: false, loading: false };

describe("GoalRunsIndexPage", () => {
  beforeEach(() => {
    listGoalRuns.mockReset();
    listGoals.mockReset().mockResolvedValue([]);
    mockUseUserRole.mockReturnValue(supervisor);
  });

  it("renders runs with status badges and counters", async () => {
    listGoalRuns.mockResolvedValue([run({})]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-list")).toBeTruthy());
    expect(screen.getByText("active")).toBeTruthy();
    expect(screen.getByText(/2 steps/)).toBeTruthy();
    expect(screen.getByText(/1 replan/)).toBeTruthy();
  });

  it("shows the goal title, not a bare UUID (2026-09-10 journey fix)", async () => {
    listGoalRuns.mockResolvedValue([run({})]);
    listGoals.mockResolvedValue([
      { id: "goal-abcdef12-0000", title: "Prepare a quote for Acme" },
    ]);
    render(<GoalRunsIndexPage />);
    const title = await waitFor(() => screen.getByTestId("run-goal-title"));
    expect(title.textContent).toContain("Prepare a quote for Acme");
    expect(screen.queryByText(/goal-abcdef/)).toBeNull();
  });

  it("falls back to the goal id when the goal fetch has no title", async () => {
    listGoalRuns.mockResolvedValue([run({})]);
    listGoals.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    const title = await waitFor(() => screen.getByTestId("run-goal-title"));
    expect(title.textContent).toContain("goal-abc"); // slice(0,8) of the id
  });

  it("shows the waiting badge for sleeping runs", async () => {
    listGoalRuns.mockResolvedValue([
      run({
        id: "run-2",
        status: "waiting",
        waiting_on: { event: "email_reply", deadline: "2026-09-12T00:00:00Z" },
      }),
    ]);
    render(<GoalRunsIndexPage />);
    const badge = await waitFor(() => screen.getByTestId("waiting-badge"));
    expect(badge.textContent).toContain("email reply");
    expect(badge.textContent).toContain("2026");
  });

  it("empty state explains where runs come from and offers the start CTA", async () => {
    listGoalRuns.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    await waitFor(() =>
      expect(screen.getByText(/No goal runs yet/)).toBeTruthy());
    expect(screen.getByRole("button", { name: /Start your first run/i })).toBeTruthy();
  });

  it("supervisor sees the New goal run affordance", async () => {
    listGoalRuns.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-empty")).toBeTruthy());
    expect(screen.getByTestId("new-goal-run")).toBeTruthy();
  });

  it("member sees the start affordance — role-based everyday work", async () => {
    mockUseUserRole.mockReturnValue(member);
    listGoalRuns.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-empty")).toBeTruthy());
    expect(screen.getByTestId("new-goal-run")).toBeTruthy();
  });

  it("viewer does not see the start affordance (backend would 403)", async () => {
    mockUseUserRole.mockReturnValue({
      role: "viewer", level: 2, isSupervisor: false, isAdmin: false, loading: false,
    });
    listGoalRuns.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-empty")).toBeTruthy());
    expect(screen.queryByTestId("new-goal-run")).toBeNull();
    expect(screen.queryByText(/Start your first run/i)).toBeNull();
  });

  it("unknown role stays fail-open (backend enforces)", async () => {
    mockUseUserRole.mockReturnValue({ role: null, level: 0, isSupervisor: false, isAdmin: false, loading: true });
    listGoalRuns.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-empty")).toBeTruthy());
    expect(screen.getByTestId("new-goal-run")).toBeTruthy();
  });

  describe("waitingLabel", () => {
    it("labels human checkpoints", () => {
      expect(waitingLabel(run({
        status: "waiting",
        waiting_on: { event: "human_checkpoint" },
      }))).toContain("human approval");
    });
    it("reads event names as words", () => {
      expect(waitingLabel(run({
        status: "waiting",
        waiting_on: { event: "email_reply" },
      }))).toContain("email reply");
    });
    it("returns null for active runs", () => {
      expect(waitingLabel(run({ status: "active" }))).toBeNull();
    });
  });

  describe("guidanceFor active run", () => {
    it("names the current step so a long run is legible", () => {
      const g = guidanceFor(run({
        status: "active",
        plan: [{ id: "s2", kind: "canvas_work", title: "Draft the quote" }],
        cursor: "s2",
      }));
      expect(g.text).toContain("Draft the quote");
    });
    it("flags an active run with no current step", () => {
      const g = guidanceFor(run({ status: "active", plan: [], cursor: null }));
      expect(g.tone).toBe("action");
      expect(g.text).toMatch(/no current step/i);
    });
  });
});
