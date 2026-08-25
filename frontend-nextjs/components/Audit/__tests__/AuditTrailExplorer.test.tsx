/**
 * AuditTrailExplorer tests — the accountant's decision-timeline view.
 *
 * The audit API module is mocked (not MSW) so the tests exercise the
 * component's data → UI mapping: run list, stat header, and the
 * expandable per-event timeline.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AuditTrailExplorer from "@/components/Audit/AuditTrailExplorer";
import { auditAPI } from "@/lib/audit-api";

jest.mock("@/lib/audit-api", () => ({
  auditAPI: {
    summary: jest.fn(),
    executions: jest.fn(),
    timeline: jest.fn(),
    events: jest.fn(),
  },
}));

const mockedSummary = auditAPI.summary as jest.Mock;
const mockedExecutions = auditAPI.executions as jest.Mock;
const mockedTimeline = auditAPI.timeline as jest.Mock;

const flushPromises = () => new Promise((r) => setTimeout(r, 0));

describe("AuditTrailExplorer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedSummary.mockResolvedValue({
      days: 7,
      total_events: 12,
      by_event_type: { agent_action: 9, llm_call: 3 },
      failures: 1,
      success_rate: 91.7,
      distinct_agents: 2,
      executions_tracked: 2,
      generated_at: "2026-08-24T00:00:00Z",
    });
    mockedExecutions.mockResolvedValue({
      total: 1,
      items: [
        {
          execution_id: "exec-1",
          agent_id: "agent-bookkeeper",
          started_at: "2026-08-24T10:00:00Z",
          status: "failed",
          completed_at: "2026-08-24T10:02:00Z",
          task_input: "reconcile Q3",
          tool_calls: 2,
          llm_calls: 3,
          failed_events: 1,
        },
      ],
    });
    mockedTimeline.mockResolvedValue({
      execution_id: "exec-1",
      found_events: true,
      execution: { id: "exec-1", agent_id: "agent-bookkeeper", status: "failed" },
      counts: { tool_calls: 2, llm_calls: 3, failed_events: 1 },
      events: [
        {
          id: "e1",
          timestamp: "2026-08-24T10:00:01Z",
          event_type: "agent_action",
          action: "execution_start",
          description: "Agent starting task",
          agent_id: "agent-bookkeeper",
          agent_execution_id: "exec-1",
          success: true,
          error_message: null,
          metadata: { task_input: "reconcile Q3" },
        },
        {
          id: "e2",
          timestamp: "2026-08-24T10:00:30Z",
          event_type: "agent_action",
          action: "tool:browser_navigate",
          description: "Tool 'browser_navigate' failed",
          agent_id: "agent-bookkeeper",
          agent_execution_id: "exec-1",
          success: false,
          error_message: "Governance Error: rejected by user",
          metadata: { tool: "browser_navigate", args: { url: "https://bank.example.com" } },
        },
      ],
    });
  });

  test("renders summary stats and audited runs", async () => {
    render(<AuditTrailExplorer />);
    await waitFor(() =>
      expect(screen.getByTestId("audit-summary-stats").textContent).toContain("12"),
    );
    expect(screen.getByText("agent-bookkeeper")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(mockedExecutions).toHaveBeenCalled();
  });

  test("shows empty state when no audited runs exist", async () => {
    mockedExecutions.mockResolvedValue({ total: 0, items: [] });
    mockedSummary.mockResolvedValue({
      days: 7,
      total_events: 0,
      by_event_type: {},
      by_action: {},
      success_rate: null,
      distinct_agents: 0,
      executions_tracked: 0,
      generated_at: "2026-08-24T00:00:00Z",
    });
    render(<AuditTrailExplorer />);
    await waitFor(() =>
      expect(screen.getByText(/No audited agent runs yet/i)).toBeInTheDocument(),
    );
  });

  test("clicking a run loads its decision timeline", async () => {
    render(<AuditTrailExplorer />);
    await waitFor(() => screen.getByTestId("audit-run-row"));
    await userEvent.click(screen.getByTestId("audit-run-row"));
    await waitFor(() => expect(mockedTimeline).toHaveBeenCalledWith("exec-1"));
    await waitFor(() =>
      expect(screen.getAllByTestId("audit-timeline-event")[0].textContent).toContain(
        "execution_start",
      ),
    );
  });

  test("expanding an event reveals its metadata", async () => {
    render(<AuditTrailExplorer />);
    await waitFor(() => screen.getByTestId("audit-run-row"));
    await userEvent.click(screen.getByTestId("audit-run-row"));
    await waitFor(() => screen.getAllByTestId("audit-timeline-event-toggle").length > 0);
    await userEvent.click(screen.getAllByTestId("audit-timeline-event-toggle")[1]);
    await waitFor(() =>
      expect(screen.getByTestId("audit-timeline-event-metadata").textContent).toContain(
        "browser_navigate",
      ),
    );
  });
});
