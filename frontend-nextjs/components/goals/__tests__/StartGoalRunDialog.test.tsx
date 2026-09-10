/**
 * StartGoalRunDialog — the missing first link of the GoalRun journey
 * (2026-09-10). A supervisor picks an existing goal or writes a new one,
 * binds the role agent + supervision mode, and starts the run. The component
 * is presentational about the start semantics: the backend kicks off the
 * first loop turn, so `onStarted` is the hand-off to the run timeline.
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/lib/goal-run-api", () => ({
  __esModule: true,
  listGoals: jest.fn(),
  createGoal: jest.fn(),
  createGoalRun: jest.fn(),
}));

jest.mock("@/lib/canvas-api", () => ({
  __esModule: true,
  listAttachableAgents: jest.fn(),
}));

import StartGoalRunDialog from "@/components/goals/StartGoalRunDialog";
import * as api from "@/lib/goal-run-api";
import * as canvasApi from "@/lib/canvas-api";

const listGoals = api.listGoals as jest.Mock;
const createGoal = api.createGoal as jest.Mock;
const createGoalRun = api.createGoalRun as jest.Mock;
const listAttachableAgents = canvasApi.listAttachableAgents as jest.Mock;

const goal = (id: string, title: string) => ({
  id, title, status: "active", progress: 0, criteria: [], key_results: [],
});

beforeEach(() => {
  listGoals.mockReset().mockResolvedValue([
    goal("g-1", "Prepare a quote for Acme"),
    goal("g-2", "Onboard a new vendor"),
  ]);
  listAttachableAgents.mockReset().mockResolvedValue([
    { id: "agent-1", name: "Sales Rep" },
  ]);
  createGoal.mockReset();
  createGoalRun.mockReset().mockResolvedValue({
    id: "run-9", run: { id: "run-9" }, started: { advanced: true }, seed_source: null,
  });
});

describe("StartGoalRunDialog", () => {
  it("lists existing goals and starts a run against the selected one", async () => {
    const onStarted = jest.fn();
    render(<StartGoalRunDialog open onOpenChange={() => {}} onStarted={onStarted} />);

    const select = await waitFor(() => screen.getByTestId("goal-select"));
    expect(screen.getByText("Prepare a quote for Acme")).toBeTruthy();

    fireEvent.change(select, { target: { value: "g-2" } });
    fireEvent.change(screen.getByTestId("mode-select"), { target: { value: "shadow" } });
    fireEvent.click(screen.getByTestId("submit-start-run"));

    await waitFor(() => expect(createGoalRun).toHaveBeenCalledTimes(1));
    expect(createGoal).not.toHaveBeenCalled();
    expect(createGoalRun).toHaveBeenCalledWith(expect.objectContaining({
      goal_id: "g-2",
      supervision_mode: "shadow",
    }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith("run-9"));
  });

  it("creates a NEW goal first, then the run against it", async () => {
    createGoal.mockResolvedValue(goal("g-new", "Weird goal"));
    const onStarted = jest.fn();
    render(<StartGoalRunDialog open onOpenChange={() => {}} onStarted={onStarted} />);

    await waitFor(() => screen.getByTestId("goal-select"));
    fireEvent.click(screen.getByRole("button", { name: /new goal/i }));

    const submit = screen.getByTestId("submit-start-run") as HTMLButtonElement;
    expect(submit.disabled).toBe(true); // no title yet

    fireEvent.change(screen.getByTestId("new-goal-title"), {
      target: { value: "  Prepare a quote  " },
    });
    fireEvent.click(submit);

    await waitFor(() => expect(createGoal).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Prepare a quote" })));
    await waitFor(() => expect(createGoalRun).toHaveBeenCalledWith(
      expect.objectContaining({ goal_id: "g-new" })));
  });

  it("binds the selected role agent and role", async () => {
    const onStarted = jest.fn();
    render(<StartGoalRunDialog open onOpenChange={() => {}} onStarted={onStarted} />);

    // Wait for the async goal load to seat a selection — the submit button is
    // disabled until a goal is bound.
    await waitFor(() =>
      expect((screen.getByTestId("submit-start-run") as HTMLButtonElement).disabled).toBe(false));
    fireEvent.change(screen.getByTestId("agent-select"), { target: { value: "agent-1" } });
    fireEvent.change(screen.getByTestId("role-input"), { target: { value: "sales" } });
    fireEvent.click(screen.getByTestId("submit-start-run"));

    await waitFor(() => expect(createGoalRun).toHaveBeenCalledWith(
      expect.objectContaining({ agent_id: "agent-1", role: "sales" })));
  });

  it("surfaces a start failure instead of closing silently", async () => {
    createGoalRun.mockRejectedValue(new Error("goal is already achieved"));
    const onOpenChange = jest.fn();
    const onStarted = jest.fn();
    render(<StartGoalRunDialog open onOpenChange={onOpenChange} onStarted={onStarted} />);

    await waitFor(() =>
      expect((screen.getByTestId("submit-start-run") as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByTestId("submit-start-run"));

    const alert = await waitFor(() => screen.getByTestId("start-error"));
    expect(alert.textContent).toContain("already achieved");
    expect(onOpenChange).not.toHaveBeenCalled(); // dialog stays open for a retry
    expect(onStarted).not.toHaveBeenCalled();
  });

  it("defaults to training mode and defaults a brand-new install to the new-goal form", async () => {
    listGoals.mockResolvedValue([]);
    render(<StartGoalRunDialog open onOpenChange={() => {}} onStarted={() => {}} />);
    // No existing goals → the new-goal form is the only viable path.
    const title = await waitFor(() => screen.getByTestId("new-goal-title"));
    expect(title).toBeTruthy();
    const mode = screen.getByTestId("mode-select") as HTMLSelectElement;
    expect(mode.value).toBe("training");
  });
});
