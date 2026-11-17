/**
 * AuditTrailExplorer — selection identity under deferred responses.
 *
 * The run list lets a reader move from run A to run B while A's timeline is
 * still in flight. Every assertion here drives the real component through a
 * user click and resolves/rejects real deferred promised API calls; no fake
 * replacement of the component's state machine is used. The invariant:
 * whatever is rendered, exported or submitted belongs to the run named in the
 * header, and only the newest request for the newest selection may touch
 * timeline/error/loading/correction state.
 */

import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: any) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: any) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function timelineFor(executionId: string, action: string) {
  return {
    execution_id: executionId,
    found_events: true,
    read_scope: {
      kind: "owner",
      workspace_id: "ws-1",
      supervisor: false,
      note: "Own scope.",
    },
    execution: {
      id: executionId,
      agent_id: `agent-${executionId}`,
      status: "completed",
      correction_targets: [],
    },
    counts: { tool_calls: 0, llm_calls: 0, failed_events: 0 },
    evidence_limits: { signed: false, hash_chain: false, note: "not tamper-evident" },
    events: [
      {
        id: `evt-${executionId}`,
        timestamp: "2026-08-24T10:00:00Z",
        event_type: "agent_action",
        action,
        description: `recorded for ${executionId}`,
        agent_id: `agent-${executionId}`,
        agent_execution_id: executionId,
        user_id: "member",
        workspace_id: "ws-1",
        success: true,
        error_message: null,
        metadata: {},
        model_identity: null,
        correction_targets: [],
        correction: null,
      },
    ],
  };
}

type PendingTimeline = { id: string; deferred: Deferred<any> };
let pendingTimelines: PendingTimeline[] = [];

function requestsFor(id: string): PendingTimeline[] {
  return pendingTimelines.filter((entry) => entry.id === id);
}

async function resolveTimeline(entry: PendingTimeline, value = timelineFor(entry.id, `${entry.id.toUpperCase()}_ACTION`)) {
  await act(async () => {
    entry.deferred.resolve(value);
    await entry.deferred.promise;
  });
}

async function rejectTimeline(entry: PendingTimeline, error: unknown) {
  await act(async () => {
    entry.deferred.reject(error);
    try {
      await entry.deferred.promise;
    } catch {
      // the component owns the rejection
    }
  });
}

async function mountWithRuns() {
  render(<AuditTrailExplorer />);
  await waitFor(() => expect(screen.getAllByTestId("audit-run-row")).toHaveLength(2));
}

async function selectRun(index: number) {
  await userEvent.click(screen.getAllByTestId("audit-run-row")[index]);
}

beforeEach(() => {
  pendingTimelines = [];
  mockBuildBundle.mockReset();
  mockDownloadBundle.mockReset();
  mockedSummary.mockResolvedValue({
    days: 7,
    total_events: 2,
    by_event_type: { agent_action: 2 },
    failures: 0,
    success_rate: 100,
    distinct_agents: 2,
    executions_tracked: 2,
    generated_at: "2026-08-24T10:05:00Z",
    read_scope: {
      kind: "owner",
      workspace_id: "ws-1",
      supervisor: false,
      note: "Own scope.",
    },
  });
  mockedExecutions.mockResolvedValue({
    total: 2,
    items: [
      {
        execution_id: "exec-a",
        agent_id: "agent-exec-a",
        started_at: "2026-08-24T10:00:00Z",
        status: "completed",
        tool_calls: 0,
        llm_calls: 0,
        failed_events: 0,
      },
      {
        execution_id: "exec-b",
        agent_id: "agent-exec-b",
        started_at: "2026-08-24T10:10:00Z",
        status: "completed",
        tool_calls: 0,
        llm_calls: 0,
        failed_events: 0,
      },
    ],
  });
  mockedTimeline.mockImplementation((id: string) => {
    const entry = { id, deferred: deferred<any>() };
    pendingTimelines.push(entry);
    return entry.deferred.promise;
  });
  mockedCorrection.mockResolvedValue({
    id: "fb-1",
    feedback_id: "fb-1",
    correction_status: "recorded",
    correction_audit_id: "aud-1",
    applied: false,
    verified: false,
    status_note: "recorded",
  });
});

test("ROOT deferred counter: a late A response never replaces the displayed B run", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await selectRun(1);
  await waitFor(() => expect(requestsFor("exec-b")).toHaveLength(1));

  await resolveTimeline(requestsFor("exec-b")[0]);
  expect(await screen.findByText("EXEC-B_ACTION")).toBeInTheDocument();
  expect(screen.getByText(/Decision Timeline — exec-b/)).toBeInTheDocument();

  const aRequest = requestsFor("exec-a")[0];
  await resolveTimeline(aRequest);

  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();
  expect(screen.getByText("EXEC-B_ACTION")).toBeInTheDocument();
  expect(screen.getByText(/Decision Timeline — exec-b/)).toBeInTheDocument();

  fireEvent.click(screen.getByTestId("audit-download-evidence"));
  expect(mockBuildBundle).toHaveBeenCalledWith(
    expect.objectContaining({ execution_id: "exec-b" }),
    expect.any(Object),
  );

  // Two explicit selections => two timeline reads, one overview read, and no
  // correction/export network activity behind the reader's back.
  expect(mockedTimeline).toHaveBeenCalledTimes(2);
  expect(mockedExecutions).toHaveBeenCalledTimes(1);
  expect(mockedCorrection).not.toHaveBeenCalled();
  expect(mockDownloadBundle).toHaveBeenCalledTimes(1);
});

test("the newly selected run wins even when the older response settles first", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await selectRun(1);
  await waitFor(() => expect(requestsFor("exec-b")).toHaveLength(1));

  await resolveTimeline(requestsFor("exec-a")[0]);

  // B is still in flight: A's page must not be painted under B's header.
  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();
  expect(screen.getByText(/Loading timeline/)).toBeInTheDocument();
  expect(screen.getByText(/Decision Timeline — exec-b/)).toBeInTheDocument();

  await resolveTimeline(requestsFor("exec-b")[0]);
  expect(await screen.findByText("EXEC-B_ACTION")).toBeInTheDocument();
  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();
});

test("a late failure from the abandoned run does not surface under the displayed run", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await selectRun(1);
  await waitFor(() => expect(requestsFor("exec-b")).toHaveLength(1));

  await resolveTimeline(requestsFor("exec-b")[0]);
  expect(await screen.findByText("EXEC-B_ACTION")).toBeInTheDocument();

  await rejectTimeline(
    requestsFor("exec-a")[0],
    new AuditApiError("deferred A failure", { kind: "server", status: 500 }),
  );

  expect(screen.queryByTestId("audit-timeline-error")).not.toBeInTheDocument();
  expect(screen.getByText("EXEC-B_ACTION")).toBeInTheDocument();
  expect(screen.getByText(/Decision Timeline — exec-b/)).toBeInTheDocument();
});

test("a failure for B never shows A's rows as if they were B's", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await resolveTimeline(requestsFor("exec-a")[0]);
  expect(await screen.findByText("EXEC-A_ACTION")).toBeInTheDocument();

  await selectRun(1);
  await waitFor(() => expect(requestsFor("exec-b")).toHaveLength(1));

  // While B is pending, A's loaded rows must not remain visible under B.
  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();
  expect(screen.getByText(/Loading timeline/)).toBeInTheDocument();

  await rejectTimeline(
    requestsFor("exec-b")[0],
    new AuditApiError("deferred B failure", { kind: "server", status: 500 }),
  );

  expect(await screen.findByTestId("audit-timeline-error")).toHaveTextContent(
    "Audit service error",
  );
  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();
  expect(screen.getByTestId("audit-download-evidence")).toBeDisabled();
});

test("export and correction cannot target an in-flight or mismatched run", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await resolveTimeline(requestsFor("exec-a")[0]);
  expect(await screen.findByText("EXEC-A_ACTION")).toBeInTheDocument();

  // Open the correction form against A's event, then move to B.
  fireEvent.click(screen.getAllByTestId("audit-report-problem")[0]);
  expect(await screen.findByTestId("audit-correction-form")).toBeInTheDocument();

  await selectRun(1);
  await waitFor(() => expect(requestsFor("exec-b")).toHaveLength(1));

  // Nothing may be exported or submitted while B is not the loaded subject.
  expect(screen.queryByTestId("audit-correction-form")).not.toBeInTheDocument();
  expect(screen.getByTestId("audit-download-evidence")).toBeDisabled();
  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();

  await resolveTimeline(requestsFor("exec-b")[0]);
  expect(await screen.findByText("EXEC-B_ACTION")).toBeInTheDocument();
  expect(screen.queryByTestId("audit-correction-form")).not.toBeInTheDocument();

  mockBuildBundle.mockReturnValue({ execution_id: "exec-b", row_count: 1 });
  fireEvent.click(screen.getByTestId("audit-download-evidence"));
  expect(mockBuildBundle).toHaveBeenCalledWith(
    expect.objectContaining({ execution_id: "exec-b" }),
    expect.any(Object),
  );
  expect(mockDownloadBundle).toHaveBeenCalledWith({ execution_id: "exec-b", row_count: 1 });

  fireEvent.click(screen.getAllByTestId("audit-report-problem")[0]);
  fireEvent.click(await screen.findByTestId("audit-correction-submit"));
  await waitFor(() =>
    expect(mockedCorrection).toHaveBeenCalledWith(
      expect.objectContaining({
        auditId: "evt-exec-b",
        executionId: "exec-b",
        agentId: "agent-exec-b",
      }),
    ),
  );
});

test("re-selecting the same run keeps its rows and does not refetch", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await resolveTimeline(requestsFor("exec-a")[0]);
  expect(await screen.findByText("EXEC-A_ACTION")).toBeInTheDocument();

  await selectRun(0);

  expect(screen.getByText("EXEC-A_ACTION")).toBeInTheDocument();
  expect(requestsFor("exec-a")).toHaveLength(1);
  expect(mockedTimeline).toHaveBeenCalledTimes(1);
});

test("an overview refresh keeps the displayed run and adds no timeline read", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await resolveTimeline(requestsFor("exec-a")[0]);
  expect(await screen.findByText("EXEC-A_ACTION")).toBeInTheDocument();

  fireEvent.click(screen.getByTestId("audit-refresh"));
  await waitFor(() => expect(mockedSummary).toHaveBeenCalledTimes(2));

  expect(screen.getByText("EXEC-A_ACTION")).toBeInTheDocument();
  expect(screen.getByText(/Decision Timeline — exec-a/)).toBeInTheDocument();
  expect(screen.getByTestId("audit-download-evidence")).not.toBeDisabled();
  expect(mockedTimeline).toHaveBeenCalledTimes(1);
});

test("a late overview response cannot overwrite the newer read scope", async () => {
  const firstSummary = deferred<any>();
  mockedSummary.mockReset();
  mockedSummary
    .mockReturnValueOnce(firstSummary.promise)
    .mockResolvedValue({
      days: 7,
      total_events: 2,
      by_event_type: { agent_action: 2 },
      failures: 0,
      success_rate: 100,
      distinct_agents: 2,
      executions_tracked: 2,
      generated_at: "2026-08-24T10:05:00Z",
      read_scope: {
        kind: "workspace",
        workspace_id: "ws-1",
        supervisor: true,
        note: "Current workspace.",
      },
    });

  render(<AuditTrailExplorer />);
  fireEvent.click(screen.getByTestId("audit-refresh"));
  await waitFor(() => expect(mockedSummary).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getAllByTestId("audit-run-row")).toHaveLength(2));
  await waitFor(() =>
    expect(screen.getByTestId("audit-read-scope")).toHaveTextContent("Workspace runs"),
  );

  await act(async () => {
    firstSummary.resolve({
      days: 7,
      total_events: 2,
      by_event_type: { agent_action: 2 },
      failures: 0,
      success_rate: 100,
      distinct_agents: 2,
      executions_tracked: 2,
      generated_at: "2026-08-24T10:05:00Z",
      read_scope: {
        kind: "owner",
        workspace_id: "ws-1",
        supervisor: false,
        note: "Own scope.",
      },
    });
    await firstSummary.promise;
  });

  expect(screen.getByTestId("audit-read-scope")).toHaveTextContent("Workspace runs");
  expect(screen.queryByText("Your runs")).not.toBeInTheDocument();
});

test("unmounting while a timeline is pending drops the late response", async () => {
  const consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
  const view = render(<AuditTrailExplorer />);
  await waitFor(() => expect(screen.getAllByTestId("audit-run-row")).toHaveLength(2));

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));

  view.unmount();
  await resolveTimeline(requestsFor("exec-a")[0]);

  expect(consoleError).not.toHaveBeenCalledWith(
    "Failed to load timeline",
    expect.anything(),
  );
  consoleError.mockRestore();
});

test("event disclosure exposes a stable expanded/controls linkage and is keyboard operable", async () => {
  await mountWithRuns();

  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  await resolveTimeline(requestsFor("exec-a")[0]);
  expect(await screen.findByText("EXEC-A_ACTION")).toBeInTheDocument();

  const toggle = screen.getAllByTestId("audit-timeline-event-toggle")[0];
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  const controlsId = toggle.getAttribute("aria-controls");
  expect(controlsId).toBeTruthy();
  const panel = document.getElementById(controlsId as string);
  expect(panel).not.toBeNull();
  expect(screen.queryByTestId("audit-timeline-event-metadata")).not.toBeInTheDocument();

  toggle.focus();
  await userEvent.keyboard("{Enter}");

  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(toggle).toHaveAttribute("aria-controls", controlsId);
  expect(await screen.findByTestId("audit-timeline-event-metadata")).toBeVisible();
  expect(document.getElementById(controlsId as string)).toBe(panel);

  await userEvent.keyboard(" ");

  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByTestId("audit-timeline-event-metadata")).not.toBeInTheDocument();
  expect(mockedTimeline).toHaveBeenCalledTimes(1);
});

test("native run-selection buttons are keyboard operable, preserve mouse selection, and keep the deferred guard", async () => {
  await mountWithRuns();

  const [first, second] = screen.getAllByTestId("audit-run-select");
  expect(first.tagName).toBe("BUTTON");
  expect(first).toHaveAttribute("type", "button");
  expect(first.tabIndex).toBe(0);
  expect(first).toHaveAccessibleName("Select run exec-a from agent-exec-a");
  expect(second).toHaveAccessibleName("Select run exec-b from agent-exec-b");
  expect(first).not.toHaveAttribute("aria-current");
  expect(second).not.toHaveAttribute("aria-current");

  first.focus();
  await userEvent.keyboard("{Enter}");
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(1));
  expect(screen.getByText(/Decision Timeline — exec-a/)).toBeInTheDocument();
  expect(first).toHaveAttribute("aria-current", "true");
  expect(second).not.toHaveAttribute("aria-current");

  // Re-activating the already-selected run stays idempotent: no second request
  // and no reset of the in-flight selection.
  await userEvent.keyboard(" ");
  expect(requestsFor("exec-a")).toHaveLength(1);
  expect(screen.getByText(/Decision Timeline — exec-a/)).toBeInTheDocument();

  second.focus();
  await userEvent.keyboard(" ");
  await waitFor(() => expect(requestsFor("exec-b")).toHaveLength(1));
  expect(screen.getByText(/Decision Timeline — exec-b/)).toBeInTheDocument();
  expect(second).toHaveAttribute("aria-current", "true");
  expect(first).not.toHaveAttribute("aria-current");

  // A late settle of the keyboard-selected A request still cannot replace B.
  await resolveTimeline(requestsFor("exec-a")[0]);
  expect(screen.queryByText("EXEC-A_ACTION")).not.toBeInTheDocument();
  expect(screen.getByText(/Decision Timeline — exec-b/)).toBeInTheDocument();

  await resolveTimeline(requestsFor("exec-b")[0]);
  expect(await screen.findByText("EXEC-B_ACTION")).toBeInTheDocument();

  // Mouse row selection is unchanged and issues a fresh request for A.
  await selectRun(0);
  await waitFor(() => expect(requestsFor("exec-a")).toHaveLength(2));
  expect(screen.getByText(/Decision Timeline — exec-a/)).toBeInTheDocument();
  expect(first).toHaveAttribute("aria-current", "true");

  await resolveTimeline(requestsFor("exec-a")[1]);
  expect(await screen.findByText("EXEC-A_ACTION")).toBeInTheDocument();
});
