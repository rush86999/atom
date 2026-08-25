/**
 * Approvals page (pages/approvals.tsx) — R82.
 *
 * Covers the HITL queue legs (agent actions) and the newly-wired Training
 * Proposals (STUDENT → INTERN) section backed by /api/maturity/training/*:
 * both fetch with the stored JWT, list render, approve/reject POST to the
 * correct endpoints, and failures surface as error notices.
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
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

const ALL = "/api/agents/approvals/pending";
const TRAIN = "/api/maturity/training/proposals";

describe("ApprovalsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.setItem("auth_token", "tok");
    mockFetch.mockImplementation((url: any) => {
      const u = String(url);
      if (u.includes("/maturity/training/proposals")) {
        return Promise.resolve(okJson({ proposals: [trainingProposal] }));
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
  });
});
