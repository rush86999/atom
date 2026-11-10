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


const target={metric:"steps_executed",direction:"minimize",source:"goal_run"};
const goal={id:"goal-current",title:"Current objective",utility_target:target};
const body={goal_id:goal.id,target,ranking:[{id:"run-current",utility:2,rank:1,eligible:true,reason:""}],winner:"run-current",eligible_count:1};
describe("Independent Activity utility consistency",()=>{
 beforeEach(()=>{listGoalRuns.mockReset().mockResolvedValue([run({id:"run-current",goal_id:goal.id,status:"achieved"})]);listGoals.mockReset().mockResolvedValue([goal]);getGoalUtility.mockReset();mockUseUserRole.mockReturnValue(member);});
 it("does not retain a fresh winner after the authoritative utility target is cleared",async()=>{
  getGoalUtility.mockResolvedValueOnce(body).mockResolvedValueOnce({...body,target:null,ranking:[],winner:null,eligible_count:0});
  render(<GoalRunsIndexPage/>);
  await waitFor(()=>expect(screen.getByTestId("activity-utility-winner")).toBeTruthy());
  fireEvent.click(screen.getByRole("button",{name:/Hide finished/i}));
  await waitFor(()=>expect(getGoalUtility).toHaveBeenCalledTimes(2));
  await act(async()=>{await Promise.resolve();await Promise.resolve();});
  expect(screen.queryByTestId("activity-utility-winner")).toBeNull();
 });
 it("an older slow Activity load cannot revive a target after a newer targetless load",async()=>{
  let resolveOldRuns:any;let resolveOldGoals:any;
  listGoalRuns.mockReset().mockImplementationOnce(()=>new Promise(r=>{resolveOldRuns=r;})).mockResolvedValueOnce([]);
  listGoals.mockReset().mockImplementationOnce(()=>new Promise(r=>{resolveOldGoals=r;})).mockResolvedValueOnce([]);
  getGoalUtility.mockResolvedValue(body);
  render(<GoalRunsIndexPage/>);
  fireEvent.click(screen.getByRole("button",{name:/Hide finished/i}));
  await waitFor(()=>expect(listGoalRuns).toHaveBeenCalledTimes(2));
  await act(async()=>{await Promise.resolve();await Promise.resolve();});
  await act(async()=>{resolveOldRuns([run({id:"run-current",goal_id:goal.id,status:"achieved"})]);resolveOldGoals([goal]);await Promise.resolve();await Promise.resolve();});
  expect(screen.queryByTestId("activity-utility-winner")).toBeNull();
  expect(screen.queryByTestId("activity-utility-summary")).toBeNull();
 });
});
