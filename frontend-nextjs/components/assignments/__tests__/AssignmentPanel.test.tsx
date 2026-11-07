import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/lib/assignment-api", () => ({
  __esModule: true,
  listAssignments: jest.fn(),
  listAssignmentSources: jest.fn(),
  createEmployeeAssignment: jest.fn(),
  addAssignmentSource: jest.fn(),
  advanceAssignment: jest.fn(),
  getAssignment: jest.fn(),
  resumeAssignment: jest.fn(),
  cancelAssignment: jest.fn(),
  resolveAssignmentGap: jest.fn(),
  recordAssignmentResponse: jest.fn(),
  approveAssignmentStep: jest.fn(),
  reconcileAssignmentStep: jest.fn(),
}));

import {
  addAssignmentSource,
  advanceAssignment,
  approveAssignmentStep,
  createEmployeeAssignment,
  getAssignment,
  listAssignments,
  listAssignmentSources,
  reconcileAssignmentStep,
  recordAssignmentResponse,
  resolveAssignmentGap,
  resumeAssignment,
} from "@/lib/assignment-api";
import { AssignmentPanel } from "../AssignmentPanel";

const detail = {
  run_id: "run-1",
  assignment: {
    assignment_id: "asg-1",
    objective: "Prepare the controlled response",
    employee_id: "owner-1",
    workspace_id: "ws-1",
    plan_revision: 1,
    status: "waiting",
    teaching_revision: "teach-r1",
    teaching_fingerprint: "fp",
    deliverables: [
      {
        deliverable_id: "doc-1",
        kind: "document",
        description: "Prepared response",
        required: true,
        step_id: "doc",
        status: "applied",
        artifact_revision: "rev-1",
        artifact_path: "/tmp/doc.docx",
        sha256: "sha",
      },
    ],
    sources: [],
    authorized_actions: ["present"],
    budget: {},
    steps: [
      {
        step_id: "doc",
        title: "Render response",
        operation_type: "present",
        adapter: "artifact.document",
        depends_on: [],
        required: true,
        effect: "local",
        status: "applied",
        recovery_class: "terminal",
        operation_id: "op-doc",
        attempts: 0,
        result_summary: "rendered",
        artifact_revision: "rev-1",
        gap_ids: [],
        waiting: {},
        approval_request: {},
        failure: {},
      },
      {
        step_id: "send",
        title: "Send response",
        operation_type: "outbound",
        adapter: "test.route.send",
        depends_on: ["doc"],
        required: true,
        effect: "external",
        status: "awaiting_approval",
        recovery_class: "awaiting_approval",
        operation_id: "op-send",
        attempts: 0,
        result_summary: null,
        artifact_revision: "rev-1",
        gap_ids: [],
        waiting: {},
        approval_request: {
          purpose: "Send the prepared response",
          payload_sha256: "abc123def456",
          artifact_revision: "rev-1",
        },
        failure: {},
      },
    ],
    created_at: null,
    updated_at: null,
    completed_at: null,
  },
  open_gaps: [
    {
      question_id: "q-1",
      question: "What expiry applies?",
      reason: "missing expiry",
      next_retrieval: "ask the owner",
      resolver: "owner",
    },
  ],
  employee_job: {
    objective: "Prepare the controlled response",
    status: "waiting",
    business_outcome: {
      state: "unresolved",
      basis: "criteria_unknown",
      verdict: null,
    },
    steps: [
      {
        step_id: "doc",
        title: "Render response",
        status: "applied",
        readiness: null,
      },
      {
        step_id: "send",
        title: "Send response",
        status: "pending",
        readiness: {
          truth: "unknown",
          blockers: [
            { kind: "qualification", fact_id: "expiry", reason: "missing" },
          ],
        },
      },
    ],
    open_obligations: [],
  },
  operations: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  (listAssignments as jest.Mock).mockResolvedValue([
    {
      run_id: "run-1",
      status: "waiting",
      assignment: {
        assignment_id: "asg-1",
        objective: "Prepare the controlled response",
        state: "waiting",
        plan_revision: 1,
        current_action: "Send response",
      },
    },
  ]);
  (getAssignment as jest.Mock).mockResolvedValue(detail);
  (listAssignmentSources as jest.Mock).mockResolvedValue([{
    dataset_name: "supplier-invoices",
    sheet: "Invoices",
    kind: "workbook",
    source: "onedrive",
    external_id: "invoice-drive-1",
    source_version: "v1",
  }]);
  (approveAssignmentStep as jest.Mock).mockResolvedValue({ status: "approved" });
  (resolveAssignmentGap as jest.Mock).mockResolvedValue(detail);
  (resumeAssignment as jest.Mock).mockResolvedValue(detail);
  (reconcileAssignmentStep as jest.Mock).mockResolvedValue(detail);
});

test("shows objective, completed work, gaps, waiting party and approval payload", async () => {
  render(<AssignmentPanel />);
  const detailNode = await screen.findByTestId("assignment-detail");
  expect(within(detailNode).getByText(
    "Prepare the controlled response")).toBeInTheDocument();
  expect(within(detailNode).getByText("Render response")).toBeInTheDocument();
  expect(within(detailNode).getByText("Prepared response")).toBeInTheDocument();
  expect(within(detailNode).getByText("What expiry applies?")).toBeInTheDocument();
  expect(within(detailNode).getByText(/Approval required/)).toBeInTheDocument();
  expect(within(detailNode).getByText(/Send the prepared response/)).toBeInTheDocument();
  expect(within(detailNode).getByTestId("assignment-employee-job").textContent)
    .toContain("unresolved");
  expect(within(detailNode).getByTestId("assignment-readiness-reasons").textContent)
    .toContain("expiry");
  expect(resumeAssignment).not.toHaveBeenCalled();
});

test("shows a business-safe configuration notice without model branding", async () => {
  (getAssignment as jest.Mock).mockResolvedValue({
    ...detail,
    employee_job: {
      ...detail.employee_job,
      routing_notice: {
        state: "configuration_required",
        code: "no_suitable_configured_model",
        message:
          "No configured model currently meets this work's requirements. "
          + "The employee's job, completed work and questions are preserved.",
        next_action:
          "Add or enable an eligible model in settings, then resume the same job.",
      },
    },
  });
  render(<AssignmentPanel />);
  const notice = await screen.findByTestId("assignment-routing-notice");
  expect(notice.textContent).toContain("No configured model");
  expect(notice.textContent).toContain("resume the same job");
  expect(notice.textContent).not.toContain("ollama");
  expect(notice.textContent).not.toContain("llama");
});

test("shows the unresolved business result after the question is answered", async () => {
  (getAssignment as jest.Mock).mockResolvedValue({
    ...detail,
    employee_job: {
      ...detail.employee_job,
      business_requirements: [{
        requirement_id: "result-invoice_reconciliation-abc",
        operation: "invoice_reconciliation",
        label: "invoice reconciliation",
        subject: "PO-8841",
        fact: "receiving",
        status: "unresolved",
        next_action: "Complete the invoice reconciliation.",
      }],
    },
  });
  render(<AssignmentPanel />);
  const requirement = await screen.findByTestId(
    "assignment-result-requirement");
  expect(requirement.textContent).toContain("invoice reconciliation");
  expect(requirement.textContent).toContain(
    "Complete the invoice reconciliation");
});

test("approve sends the concrete step identity", async () => {
  render(<AssignmentPanel />);
  const approve = await screen.findByRole("button", {
    name: /Approve this payload/i,
  });
  fireEvent.click(approve);
  await waitFor(() =>
    expect(approveAssignmentStep).toHaveBeenCalledWith("run-1", "send")
  );
  expect(resumeAssignment).not.toHaveBeenCalled();
});

test("resolving a gap posts the answer and resumes through the backend", async () => {
  render(<AssignmentPanel />);
  const input = await screen.findByLabelText("Gap answer");
  fireEvent.change(input, { target: { value: "2027-01-01" } });
  fireEvent.click(screen.getByRole("button", {
    name: /Resolve gap: What expiry applies/i,
  }));
  await waitFor(() =>
    expect(resolveAssignmentGap).toHaveBeenCalledWith(
      "run-1",
      "q-1",
      "2027-01-01"
    )
  );
});

test("uncertain effect reconciliation sends evidence and verdict", async () => {
  const uncertain = JSON.parse(JSON.stringify(detail));
  uncertain.assignment.steps[1].status = "uncertain";
  uncertain.assignment.steps[1].failure = {
    message: "The provider may have accepted the effect.",
  };
  (getAssignment as jest.Mock).mockResolvedValue(uncertain);

  render(<AssignmentPanel />);
  const evidence = await screen.findByTestId("assignment-reconcile-evidence");
  fireEvent.change(evidence, {
    target: { value: "provider receipt row 42" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Mark applied/i }));
  await waitFor(() =>
    expect(reconcileAssignmentStep).toHaveBeenCalledWith(
      "run-1",
      "send",
      "applied",
      "provider receipt row 42",
      undefined,
      undefined
    )
  );
});


test("employee-decides starts objective-only work without a supplied DAG", async () => {
  (createEmployeeAssignment as jest.Mock).mockResolvedValue({
    run_id: "run-2",
    assignment: detail,
  });
  render(<AssignmentPanel />);
  await screen.findByTestId("assignment-start");

  fireEvent.change(screen.getByTestId("assignment-objective-input"), {
    target: { value: "Prepare a delivery answer for the customer" },
  });
  fireEvent.click(screen.getByTestId("assignment-employee-decides-checkbox"));
  fireEvent.click(screen.getByTestId("assignment-discover-checkbox"));
  fireEvent.change(screen.getByTestId("assignment-scope-input"), {
    target: { value: "commercial notes" },
  });
  fireEvent.click(screen.getByTestId("assignment-start-button"));

  await waitFor(() => expect(createEmployeeAssignment).toHaveBeenCalledWith(
    expect.objectContaining({
      objective: "Prepare a delivery answer for the customer",
      source_scope: { query: "commercial notes" },
      authorized_actions: ["retrieve", "calculate"],
      requested_output: "document",
      use_model: true,
    }),
  ));
});


test("answers an open prerequisite with the selected authorized source", async () => {
  (getAssignment as jest.Mock).mockResolvedValue({
    ...detail,
    employee_job: {
      ...detail.employee_job,
      open_obligations: [{
        question_id: "q-invoice",
        question: "Which authorized source contains the invoice for PO-8?",
        kind: "missing_evidence",
      }],
    },
  });
  (addAssignmentSource as jest.Mock).mockResolvedValue({
    status: "applied", resolved_question_ids: ["q-invoice"],
  });
  render(<AssignmentPanel />);
  const button = await screen.findByTestId("assignment-use-source");
  fireEvent.click(button);
  await waitFor(() =>
    expect(addAssignmentSource).toHaveBeenCalledWith(
      "run-1",
      expect.objectContaining({
        dataset_name: "supplier-invoices",
        sheet: "Invoices",
        source_version: "v1",
      }),
      expect.stringContaining("open question"),
    )
  );
  // The source route owns the same-task continuation; a second client
  // advance would duplicate that consumer call.
  expect(advanceAssignment).not.toHaveBeenCalled();
});


test("explains a durable wait and delivers the source-bound answer", async () => {
  const waitingDetail = {
    ...detail,
    assignment: {
      ...detail.assignment,
      status: "waiting",
      steps: [
        {
          step_id: "await",
          title: "Wait for received_quantity for PO-7",
          operation_type: "retrieve",
          adapter: "assignment.wait",
          depends_on: [],
          required: true,
          effect: "read_only",
          status: "waiting",
          recovery_class: "waiting",
          operation_id: "op-wait",
          attempts: 0,
          result_summary: null,
          artifact_revision: null,
          gap_ids: [],
          waiting: {
            correlation_id: "await-abc",
            party: "warehouse receiving",
            fact: "received_quantity",
            subject: "PO-7",
            detail: "received_quantity for PO-7",
            blocks: "invoice reconciliation",
            expected_answer_type: "quantity",
          },
          approval_request: {},
          failure: {},
        },
      ],
    },
    employee_job: {
      ...detail.employee_job,
      waiting: [{
        step_id: "await",
        fact: "received_quantity",
        subject: "PO-7",
        party: "warehouse receiving",
        detail: "received_quantity for PO-7",
        blocks: "invoice reconciliation",
        expected_answer_type: "quantity",
        correlation_id: "await-abc",
      }],
      ready_work: [{
        operation: "quote_calculation",
        label: "quote calculation",
      }],
    },
  };
  (getAssignment as jest.Mock).mockResolvedValue(waitingDetail);
  (recordAssignmentResponse as jest.Mock).mockResolvedValue({
    status: "resumed",
  });
  render(<AssignmentPanel />);
  await waitFor(() =>
    expect(screen.getByTestId("assignment-detail")).toBeInTheDocument());
  const panel = screen.getByTestId("assignment-detail");
  expect(panel.textContent).toContain(
    "Waiting for received_quantity for PO-7");
  expect(panel.textContent).toContain(
    "This blocks invoice reconciliation.");
  expect(panel.textContent).toContain(
    "Work that can continue: quote calculation.");
  fireEvent.change(
    within(panel).getByLabelText("Correlated response"),
    { target: { value: "received 2 units" } });
  fireEvent.change(
    within(panel).getByTestId("assignment-resolution-value"),
    { target: { value: "2" } });
  fireEvent.click(within(panel).getByText("Deliver"));
  await waitFor(() => expect(recordAssignmentResponse)
    .toHaveBeenCalledWith(
      "run-1", "await-abc", "received 2 units", "", "2",
      "warehouse receiving"));
});
