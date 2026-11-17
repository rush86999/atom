/**
 * AuditTrailExplorer — owner/workspace scope, honest permission errors,
 * correction REQUEST flow and evidence export (F1/F2/F3/F6).
 *
 * The API module and export module are mocked so the tests exercise the
 * component's data → UI decisions; the real fetch error taxonomy and export
 * bundle math are covered by their own focused tests.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AuditTrailExplorer from "@/components/Audit/AuditTrailExplorer";
import { auditAPI, AuditApiError } from "@/lib/audit-api";

const mockBuildBundle = jest.fn();
const mockDownloadBundle = jest.fn();

jest.mock("@/lib/audit-api", () => {
  const actual = jest.requireActual("@/lib/audit-api");
  return {
    ...actual,
    auditAPI: {
      summary: jest.fn(),
      executions: jest.fn(),
      timeline: jest.fn(),
      events: jest.fn(),
      correctionRequest: jest.fn(),
    },
  };
});

jest.mock("@/lib/audit-export", () => ({
  buildAuditEvidenceBundle: (...args: any[]) => mockBuildBundle(...args),
  downloadAuditEvidenceBundle: (...args: any[]) => mockDownloadBundle(...args),
}));

const mockedSummary = auditAPI.summary as jest.Mock;
const mockedExecutions = auditAPI.executions as jest.Mock;
const mockedTimeline = auditAPI.timeline as jest.Mock;
const mockedCorrection = auditAPI.correctionRequest as jest.Mock;

const TIMELINE = {
  execution_id: "exec-1",
  found_events: true,
  read_scope: {
    kind: "owner",
    workspace_id: "ws-1",
    supervisor: false,
    note: "Own scope: only audited rows recorded for your user.",
  },
  execution: {
    id: "exec-1",
    agent_id: "agent-bookkeeper",
    status: "completed",
    outcome: {
      status: "completed",
      basis: "recorded_execution_status",
      verification: "partially_verified",
      note: "Recorded run status. Audit replay does not independently re-verify the business outcome.",
    },
    verification: {
      status: "partially_verified",
      basis: "recorded_reasoning_step_tri_state",
      counts: { verified: 1, unverified: 1, failed_verification: 0 },
      evidence: [],
      note: "Step-level oracle state as recorded.",
    },
    usage: {
      status: "recorded_estimate",
      cost_usd: 0.0123,
      currency: "USD",
      basis: "recorded_usage_estimate",
      rows: 2,
      priced_rows: 2,
      unpriced_rows: 0,
      total_tokens: 40,
      note: "Recorded provider-usage estimate; not invoice price.",
    },
    model_identity: {
      recorded_llm_call_labels: ["tier:auto"],
      execution_provenance: null,
      requested_models: ["requested-x"],
      resolved_models: ["served-y"],
      note: "labels are router-requested",
    },
    correction_targets: [
      {
        channel: "activity",
        label: "Activity (goal run)",
        target_id: "goal-123",
        href: "/goal-runs/goal-123",
      },
    ],
  },
  counts: { tool_calls: 1, llm_calls: 1, failed_events: 0 },
  evidence_limits: {
    signed: false,
    hash_chain: false,
    note: "Rows are returned as stored; not tamper-evident.",
  },
  events: [
    {
      id: "e-start",
      timestamp: "2026-08-24T10:00:00Z",
      event_type: "agent_action",
      action: "execution_start",
      description: "Agent starting task",
      agent_id: "agent-bookkeeper",
      agent_execution_id: "exec-1",
      user_id: "member",
      workspace_id: "ws-1",
      success: true,
      error_message: null,
      metadata: { task_input: "reconcile Q3" },
      model_identity: null,
      correction_targets: [],
      correction: null,
    },
    {
      id: "e-tool",
      timestamp: "2026-08-24T10:00:30Z",
      event_type: "agent_action",
      action: "tool:send_email",
      description: "Sent the report to the wrong recipient",
      agent_id: "agent-bookkeeper",
      agent_execution_id: "exec-1",
      user_id: "member",
      workspace_id: "ws-1",
      success: true,
      error_message: null,
      metadata: { args: { to: "wrong@example.com" } },
      model_identity: null,
      correction_targets: [],
      correction: null,
    },
    {
      id: "e-llm",
      timestamp: "2026-08-24T10:00:31Z",
      event_type: "llm_call",
      action: "llm_call:tier:auto",
      description: "LLM call",
      agent_id: "agent-bookkeeper",
      agent_execution_id: "exec-1",
      user_id: "member",
      workspace_id: "ws-1",
      success: true,
      error_message: null,
      metadata: { model: "tier:auto" },
      model_identity: {
        recorded_label: "tier:auto",
        label_kind: "router_tier_or_alias",
        served_model: null,
        provider: "route",
        provenance: "recorded_label_only",
        note: "Recorded router-requested label.",
      },
      correction_targets: [],
      correction: null,
    },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  mockedSummary.mockResolvedValue({
    days: 7,
    total_events: 3,
    by_event_type: { agent_action: 2, llm_call: 1 },
    failures: 0,
    success_rate: 100,
    distinct_agents: 1,
    executions_tracked: 1,
    generated_at: "2026-08-24T10:05:00Z",
    read_scope: TIMELINE.read_scope,
  });
  mockedExecutions.mockResolvedValue({
    total: 1,
    items: [
      {
        execution_id: "exec-1",
        agent_id: "agent-bookkeeper",
        started_at: "2026-08-24T10:00:00Z",
        status: "completed",
        completed_at: "2026-08-24T10:02:00Z",
        tool_calls: 1,
        llm_calls: 1,
        failed_events: 0,
        usage: TIMELINE.execution.usage,
      },
    ],
  });
  mockedTimeline.mockResolvedValue(TIMELINE);
  mockedCorrection.mockResolvedValue({
    id: "fb-1",
    feedback_id: "fb-1",
    correction_status: "recorded",
    correction_audit_id: "aud-1",
    applied: false,
    verified: false,
    channel: "activity",
    channel_target_id: "goal-123",
    status_note: "recorded",
  });
});

async function openTimeline() {
  render(<AuditTrailExplorer />);
  await waitFor(() => screen.getByTestId("audit-run-row"));
  await userEvent.click(screen.getByTestId("audit-run-row"));
  await waitFor(() => expect(mockedTimeline).toHaveBeenCalledWith("exec-1"));
  await waitFor(() => expect(screen.getAllByTestId("audit-timeline-event").length).toBe(3));
}

test("default mount keeps the quiet audit read count (no extra correction/export calls)", async () => {
  render(<AuditTrailExplorer />);
  await waitFor(() => expect(mockedExecutions).toHaveBeenCalledTimes(1));

  expect(mockedSummary).toHaveBeenCalledTimes(1);
  expect(mockedTimeline).not.toHaveBeenCalled();
  expect(mockedCorrection).not.toHaveBeenCalled();
  expect(mockBuildBundle).not.toHaveBeenCalled();
  expect(mockDownloadBundle).not.toHaveBeenCalled();
});

test("labels the server-returned owner scope instead of claiming a global feed", async () => {
  render(<AuditTrailExplorer />);
  expect(await screen.findByTestId("audit-read-scope")).toHaveTextContent("Your runs");
  expect(screen.getByText("Your Runs")).toBeInTheDocument();
});

test("403 renders a permission message, not 'backend down'", async () => {
  const forbidden = new AuditApiError("Insufficient permissions", {
    kind: "forbidden",
    status: 403,
  });
  mockedSummary.mockRejectedValue(forbidden);
  mockedExecutions.mockRejectedValue(forbidden);

  render(<AuditTrailExplorer />);
  const error = await screen.findByTestId("audit-error");
  expect(error).toHaveTextContent("Not authorized to view this");
  expect(error).toHaveTextContent("own user");
  expect(error.textContent || "").not.toContain("backend running");
});

test("network failure gets the reachability message", async () => {
  const offline = new AuditApiError("offline", { kind: "network" });
  mockedSummary.mockRejectedValue(offline);
  mockedExecutions.mockRejectedValue(offline);

  render(<AuditTrailExplorer />);
  const error = await screen.findByTestId("audit-error");
  expect(error).toHaveTextContent("Audit service unreachable");
  expect(error).toHaveTextContent("backend is running");
});

test("a 404 timeline shows an authorized-scope message inline", async () => {
  mockedTimeline.mockRejectedValue(
    new AuditApiError("not in scope", { kind: "not_found", status: 404 }),
  );
  render(<AuditTrailExplorer />);
  await waitFor(() => screen.getByTestId("audit-run-row"));
  await userEvent.click(screen.getByTestId("audit-run-row"));

  const error = await screen.findByTestId("audit-timeline-error");
  expect(error).toHaveTextContent("Not in your authorized scope");
  expect(error.textContent || "").not.toContain("backend running");
});

test("evidence details stay optional and model identity is labelled honestly", async () => {
  await openTimeline();

  // Default view is quiet: metadata is collapsed until the user asks.
  expect(screen.queryByTestId("audit-timeline-event-metadata")).not.toBeInTheDocument();

  const toggles = screen.getAllByTestId("audit-timeline-event-toggle");
  await userEvent.click(toggles[2]); // the LLM event
  expect(await screen.findByTestId("audit-model-identity")).toHaveTextContent(
    "served model not recorded",
  );
  expect(screen.getByTestId("audit-model-identity")).toHaveTextContent("tier:auto");

  // Recorded execution provenance and the oracle state are shown as recorded.
  expect(screen.getByTestId("audit-execution-model-identity")).toHaveTextContent("served-y");
  expect(screen.getByTestId("audit-verification-badge")).toHaveTextContent(
    "partially verified",
  );
  expect(screen.getByTestId("audit-usage-status")).toHaveTextContent("recorded usage estimate");
});

test("report problem is prefilled and records a REQUEST with a safe channel link", async () => {
  await openTimeline();

  const reportButtons = screen.getAllByTestId("audit-report-problem");
  fireEvent.click(reportButtons[1]); // the send_email event

  const form = await screen.findByTestId("audit-correction-form");
  expect(form).toHaveTextContent("tool:send_email");
  expect(screen.getByTestId("audit-correction-subject")).toHaveTextContent(
    "Sent the report to the wrong recipient",
  );

  fireEvent.change(screen.getByTestId("audit-correction-reason"), {
    target: { value: "Wrong result" },
  });
  fireEvent.change(screen.getByTestId("audit-correction-detail"), {
    target: { value: "went to the wrong person" },
  });
  fireEvent.change(screen.getByTestId("audit-correction-channel"), {
    target: { value: "activity" },
  });
  fireEvent.click(screen.getByTestId("audit-correction-submit"));

  await waitFor(() =>
    expect(mockedCorrection).toHaveBeenCalledWith(
      expect.objectContaining({
        auditId: "e-tool",
        executionId: "exec-1",
        agentId: "agent-bookkeeper",
        reason: "Wrong result",
        channel: "activity",
        targetId: "goal-123",
      }),
    ),
  );

  const result = await screen.findByTestId("audit-correction-result");
  expect(result).toHaveTextContent("recorded and linked");
  expect(result).toHaveTextContent("applied:");
  expect(result).toHaveTextContent("no");
  expect(result.textContent || "").not.toMatch(/verified:\s*yes/i);
  expect(screen.getByTestId("audit-correction-channel-link")).toHaveAttribute(
    "href",
    "/goal-runs/goal-123",
  );
});

test("a denied correction request is reported as not recorded", async () => {
  mockedCorrection.mockRejectedValue(
    new AuditApiError("denied", { kind: "forbidden", status: 403 }),
  );
  await openTimeline();
  fireEvent.click(screen.getAllByTestId("audit-report-problem")[1]);
  fireEvent.click(await screen.findByTestId("audit-correction-submit"));

  const error = await screen.findByTestId("audit-correction-error");
  expect(error).toHaveTextContent("Not authorized to view this");
});

test("an audit-link write failure is shown instead of a fake correction", async () => {
  mockedCorrection.mockResolvedValue({
    id: "fb-2",
    feedback_id: "fb-2",
    correction_status: "feedback_recorded_audit_unavailable",
    correction_audit_id: null,
    applied: false,
    verified: false,
    status_note: "feedback saved; link unavailable",
  });
  await openTimeline();
  fireEvent.click(screen.getAllByTestId("audit-report-problem")[1]);
  fireEvent.click(await screen.findByTestId("audit-correction-submit"));

  const result = await screen.findByTestId("audit-correction-result");
  expect(result).toHaveTextContent(
    "Feedback saved, but the audit link could not be recorded.",
  );
  expect(result.textContent || "").not.toMatch(/verified:\s*yes/i);
});

test("download exports the exact authorized timeline payload", async () => {
  mockBuildBundle.mockReturnValue({ execution_id: "exec-1", row_count: 3 });
  await openTimeline();

  fireEvent.click(screen.getByTestId("audit-download-evidence"));

  expect(mockBuildBundle).toHaveBeenCalledWith(
    expect.objectContaining({
      execution_id: "exec-1",
      events: TIMELINE.events,
    }),
    expect.any(Object),
  );
  expect(mockDownloadBundle).toHaveBeenCalledWith({ execution_id: "exec-1", row_count: 3 });
});

test("download is disabled until a run is selected", async () => {
  render(<AuditTrailExplorer />);
  await waitFor(() => screen.getByTestId("audit-run-row"));
  expect(screen.getByTestId("audit-download-evidence")).toBeDisabled();
});
