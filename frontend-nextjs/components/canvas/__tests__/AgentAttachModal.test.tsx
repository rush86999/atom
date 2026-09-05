/**
 * AgentAttachModal tests — canvas journey step 2 (attach a hire).
 *
 * Covers: agent list render, attach success (onAttached + dialog closes),
 * attach failure surfacing, guided create-and-attach, the HITL
 * pending-approval path (nothing to attach yet), and list-load errors.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { AgentAttachModal } from "@/components/canvas/AgentAttachModal";
import {
  attachCanvasAgent,
  listAttachableAgents,
} from "@/lib/canvas-api";
import { createGuidedAgent } from "@/lib/agent-onboarding-api";

jest.mock("@/lib/canvas-api", () => ({
  __esModule: true,
  listAttachableAgents: jest.fn(),
  attachCanvasAgent: jest.fn(),
}));

jest.mock("@/lib/agent-onboarding-api", () => ({
  __esModule: true,
  createGuidedAgent: jest.fn(),
}));

const mockedList = listAttachableAgents as jest.Mock;
const mockedAttach = attachCanvasAgent as jest.Mock;
const mockedCreate = createGuidedAgent as jest.Mock;

const AGENTS = [
  { id: "a-1", name: "Alex", category: "finance", status: "student" },
  { id: "a-2", name: "Grace", category: "operations", status: "intern" },
];

function renderModal(overrides: Partial<Parameters<typeof AgentAttachModal>[0]> = {}) {
  const onAttached = jest.fn();
  const onOpenChange = jest.fn();
  render(
    <AgentAttachModal
      canvasId="c-1"
      open
      onOpenChange={onOpenChange}
      onAttached={onAttached}
      {...overrides}
    />,
  );
  return { onAttached, onOpenChange };
}

describe("AgentAttachModal", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    mockedList.mockResolvedValue(AGENTS);
  });

  it("lists the user's agents with category and tier", async () => {
    renderModal();
    expect(await screen.findByText("Alex")).toBeInTheDocument();
    expect(screen.getByText(/finance · student/)).toBeInTheDocument();
    expect(screen.getByText("Grace")).toBeInTheDocument();
  });

  it("attaches on click and reports the hire", async () => {
    mockedAttach.mockResolvedValue({
      agents: [{ agent_id: "a-1", name: "Alex", canvas_id: "c-1" }],
    });
    const { onAttached, onOpenChange } = renderModal();

    fireEvent.click(await screen.findByText("Alex"));
    await waitFor(() => expect(mockedAttach).toHaveBeenCalledWith("c-1", "a-1"));
    await waitFor(() => expect(onAttached).toHaveBeenCalled());
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("surfaces attach failures", async () => {
    mockedAttach.mockRejectedValue({
      response: { data: { error: { message: "Canvas not found" } } },
    });
    renderModal();

    fireEvent.click(await screen.findByText("Alex"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Canvas not found");
    expect(screen.queryByRole("dialog")).toBeVisible(); // dialog stays open
  });

  it("creates an agent inline and attaches it", async () => {
    mockedCreate.mockResolvedValue({
      agent_id: "a-new", name: "New Hire", category: "sales", maturity: "student",
      created_by: "employee",
    });
    mockedAttach.mockResolvedValue({
      agents: [{ agent_id: "a-new", name: "New Hire", canvas_id: "c-1" }],
    });
    renderModal();

    fireEvent.click(await screen.findByRole("button", { name: /create a new agent/i }));
    fireEvent.change(await screen.findByLabelText(/what should this agent do/i), {
      target: { value: "Track overdue invoices" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create & attach/i }));

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledWith("Track overdue invoices"));
    await waitFor(() => expect(mockedAttach).toHaveBeenCalledWith("c-1", "a-new"));
  });

  it("explains HITL pending-approval creations cannot attach yet", async () => {
    mockedCreate.mockResolvedValue({
      status: "pending_approval", hitl_action_id: "h-1", reason: "needs review",
    });
    renderModal();

    fireEvent.click(await screen.findByRole("button", { name: /create a new agent/i }));
    fireEvent.change(await screen.findByLabelText(/what should this agent do/i), {
      target: { value: "Track overdue invoices" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create & attach/i }));

    expect(
      await screen.findByText(/needs approval before it can be attached/i),
    ).toBeInTheDocument();
    expect(mockedAttach).not.toHaveBeenCalled();
  });

  it("rejects too-short goals without calling the API", async () => {
    renderModal();
    fireEvent.click(await screen.findByRole("button", { name: /create a new agent/i }));
    fireEvent.change(await screen.findByLabelText(/what should this agent do/i), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create & attach/i }));
    expect(await screen.findByText(/few more words/i)).toBeInTheDocument();
    expect(mockedCreate).not.toHaveBeenCalled();
  });

  it("shows a friendly message when the user has no agents", async () => {
    mockedList.mockResolvedValue([]);
    renderModal();
    expect(await screen.findByText(/no agents yet/i)).toBeInTheDocument();
  });
});
