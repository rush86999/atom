import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  getGoalUtility: jest.fn(),
}));

const listGoalRuns = api.listGoalRuns as jest.Mock;
const listGoals = api.listGoals as jest.Mock;
const getGoalUtility = (api as any).getGoalUtility as jest.Mock;

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
    getGoalUtility.mockReset();
    mockUseUserRole.mockReturnValue(supervisor);
  });

  it("shows the goal utility target, winner and ranked/withheld runs on Activity", async () => {
    listGoalRuns.mockResolvedValue([
      run({ id: "run-1", goal_id: "goal-utility", status: "achieved",
            steps_executed: 2 }),
      run({ id: "run-2", goal_id: "goal-utility", status: "failed",
            steps_executed: 9 }),
    ]);
    listGoals.mockResolvedValue([{
      id: "goal-utility", title: "Prepare a quote",
      utility_target: {
        metric: "steps_executed", direction: "minimize",
        source: "goal_run",
      },
    }]);
    getGoalUtility.mockResolvedValue({
      goal_id: "goal-utility",
      target: { metric: "steps_executed", direction: "minimize",
                source: "goal_run" },
      ranking: [
        { id: "run-1", utility: 2, rank: 1, eligible: true, reason: "" },
        { id: "run-2", utility: null, rank: null, eligible: false,
          reason: "incomplete" },
      ],
      winner: "run-1",
      eligible_count: 1,
    });

    render(<GoalRunsIndexPage />);

    const summary = await waitFor(() =>
      screen.getByTestId("activity-utility-summary"));
    expect(summary.textContent).toContain("Steps executed");
    expect(summary.textContent).toContain("lower is better");
    expect(summary.textContent).toContain("1 eligible");
    expect(screen.getByTestId("activity-utility-winner")).toBeTruthy();
    expect(summary.textContent).toContain("run-1");
    expect(screen.getByTestId("activity-utility-withheld").textContent)
      .toContain("incomplete");
    expect(getGoalUtility).toHaveBeenCalledWith("goal-utility");
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


const utilityGoal = (overrides: Record<string, unknown> = {}) => ({
  id: "goal-utility",
  title: "Prepare a quote",
  utility_target: {
    metric: "steps_executed",
    direction: "minimize",
    source: "goal_run",
  },
  ...overrides,
});

const utilityBody = {
  goal_id: "goal-utility",
  target: { metric: "steps_executed", direction: "minimize",
            source: "goal_run" },
  ranking: [
    { id: "run-1", utility: 2, rank: 1, eligible: true, reason: "" },
    { id: "run-2", utility: null, rank: null, eligible: false,
      reason: "incomplete" },
  ],
  winner: "run-1",
  eligible_count: 1,
};

describe("Activity goal utility visibility", () => {
  beforeEach(() => {
    listGoalRuns.mockReset();
    listGoals.mockReset();
    getGoalUtility.mockReset();
    mockUseUserRole.mockReturnValue(supervisor);
  });

  it("does not render a utility card or call the ranking API without a target", async () => {
    listGoalRuns.mockResolvedValue([run({ goal_id: "goal-no-target" })]);
    listGoals.mockResolvedValue([
      { id: "goal-no-target", title: "No target" },
    ]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-list")).toBeTruthy());
    expect(screen.queryByTestId("activity-utility-summary")).toBeNull();
    expect(getGoalUtility).not.toHaveBeenCalled();
  });

  it("shows a typed error and no fresh winner when the first utility read fails", async () => {
    listGoalRuns.mockResolvedValue([run({ goal_id: "goal-utility" })]);
    listGoals.mockResolvedValue([utilityGoal()]);
    getGoalUtility.mockRejectedValue(new Error("utility unavailable"));
    render(<GoalRunsIndexPage />);
    const error = await waitFor(() =>
      screen.getByTestId("activity-utility-error"));
    expect(error.textContent).toContain("utility unavailable");
    expect(screen.queryByTestId("activity-utility-winner")).toBeNull();
    expect(screen.getAllByText("Prepare a quote").length).toBeGreaterThan(0);
  });

  it("preserves the last known ranking but marks it stale after a later failure", async () => {
    listGoalRuns.mockResolvedValue([
      run({ id: "run-1", goal_id: "goal-utility", status: "achieved" }),
      run({ id: "run-2", goal_id: "goal-utility", status: "failed" }),
    ]);
    listGoals.mockResolvedValue([utilityGoal()]);
    getGoalUtility
      .mockResolvedValueOnce(utilityBody)
      .mockRejectedValueOnce(new Error("utility unavailable"));
    render(<GoalRunsIndexPage />);
    await waitFor(() =>
      expect(screen.getByTestId("activity-utility-winner")).toBeTruthy());
    expect(screen.getByTestId("activity-utility-summary").textContent)
      .toContain("run-1");

    fireEvent.click(screen.getByRole("button", { name: /Hide finished/i }));

    const error = await waitFor(() =>
      screen.getByTestId("activity-utility-error"));
    expect(error.textContent).toContain("utility unavailable");
    expect(screen.queryByTestId("activity-utility-winner")).toBeNull();
    // Last known ranked row is preserved, not cleared.
    expect(screen.getByTestId("activity-utility-summary").textContent)
      .toContain("run-1");
  });

  it("lets a member read the Activity utility ranking without write controls", async () => {
    mockUseUserRole.mockReturnValue(member);
    listGoalRuns.mockResolvedValue([
      run({ id: "run-1", goal_id: "goal-utility", status: "achieved" }),
    ]);
    listGoals.mockResolvedValue([utilityGoal()]);
    getGoalUtility.mockResolvedValue(utilityBody);
    render(<GoalRunsIndexPage />);
    await waitFor(() =>
      expect(screen.getByTestId("activity-utility-summary")).toBeTruthy());
    expect(screen.getByTestId("activity-utility-entry")).toBeTruthy();
    expect(screen.queryByText(/Save target/i)).toBeNull();
    expect(screen.queryByText(/Clear target/i)).toBeNull();
  });
});


  it("refreshes the utility ranking through the existing Activity poll", async () => {
    mockUseUserRole.mockReturnValue(supervisor);
    const intervalSpy = jest.spyOn(global, "setInterval");
    listGoalRuns.mockResolvedValue([
      run({ id: "run-1", goal_id: "goal-utility", status: "achieved" }),
    ]);
    listGoals.mockResolvedValue([utilityGoal()]);
    getGoalUtility.mockResolvedValue(utilityBody);
    render(<GoalRunsIndexPage />);
    await waitFor(() =>
      expect(screen.getByTestId("activity-utility-summary")).toBeTruthy());
    const poll = intervalSpy.mock.calls.find((call) => call[1] === 15000)?.[0];
    expect(poll).toBeDefined();
    await act(async () => { await (poll as () => void)(); });
    await waitFor(() => expect(getGoalUtility).toHaveBeenCalledTimes(2));
    intervalSpy.mockRestore();
  });
