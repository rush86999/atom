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

jest.mock("sonner", () => ({
  __esModule: true,
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("@/lib/goal-run-api", () => ({
  __esModule: true,
  listGoalRuns: jest.fn(),
}));

const listGoalRuns = api.listGoalRuns as jest.Mock;

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

describe("GoalRunsIndexPage", () => {
  beforeEach(() => {
    listGoalRuns.mockReset();
  });

  it("renders runs with status badges and counters", async () => {
    listGoalRuns.mockResolvedValue([run({})]);
    render(<GoalRunsIndexPage />);
    await waitFor(() => expect(screen.getByTestId("goal-runs-list")).toBeTruthy());
    expect(screen.getByText("active")).toBeTruthy();
    expect(screen.getByText(/2 steps/)).toBeTruthy();
    expect(screen.getByText(/1 replan/)).toBeTruthy();
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
    expect(badge.textContent).toContain("email_reply");
    expect(badge.textContent).toContain("2026-09-12");
  });

  it("empty state explains where runs come from", async () => {
    listGoalRuns.mockResolvedValue([]);
    render(<GoalRunsIndexPage />);
    await waitFor(() =>
      expect(screen.getByText(/No goal runs yet/)).toBeTruthy());
  });

  describe("waitingLabel", () => {
    it("labels human checkpoints", () => {
      expect(waitingLabel(run({
        status: "waiting",
        waiting_on: { event: "human_checkpoint" },
      }))).toContain("human approval");
    });
    it("returns null for active runs", () => {
      expect(waitingLabel(run({ status: "active" }))).toBeNull();
    });
  });

  describe("guidanceFor", () => {
    it("held decisions demand action and explain override learning", () => {
      const g = guidanceFor(run({
        status: "paused_hitl",
        pending_decision: { ts: "", kind: "decision", decision: "ADVANCE" },
      }));
      expect(g.tone).toBe("action");
      expect(g.text).toContain("teaches the agent instantly");
    });
    it("waiting runs tell the supervisor to do nothing", () => {
      const g = guidanceFor(run({
        status: "waiting",
        waiting_on: { event: "email_reply", deadline: "2026-09-12T00:00:00Z" },
      }));
      expect(g.text).toContain("Nothing to do");
      expect(g.text).toContain("email_reply");
      expect(g.text).toContain("2026-09-12");
    });
    it("training mode explains the approval contract", () => {
      const g = guidanceFor(run({ supervision_mode: "training" }));
      expect(g.tone).toBe("action");
      expect(g.text).toContain("waits for your approval");
    });
    it("achieved runs point at distillation", () => {
      const g = guidanceFor(run({ status: "achieved" }));
      expect(g.tone).toBe("success");
      expect(g.text).toContain("Distill");
    });
    it("shadow mode describes guardrails-only pausing", () => {
      const g = guidanceFor(run({ supervision_mode: "shadow" }));
      expect(g.text).toContain("guardrails");
    });
  });
});
