import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/lib/assignment-api", () => ({
  __esModule: true,
  listAssignments: jest.fn(),
  createEmployeeAssignment: jest.fn(),
  getAssignment: jest.fn(),
  resumeAssignment: jest.fn(),
  cancelAssignment: jest.fn(),
  resolveAssignmentGap: jest.fn(),
  recordAssignmentResponse: jest.fn(),
  approveAssignmentStep: jest.fn(),
  reconcileAssignmentStep: jest.fn(),
}));

import {
  approveAssignmentStep,
  createEmployeeAssignment,
  getAssignment,
  listAssignments,
  reconcileAssignmentStep,
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
  expect(resumeAssignment).not.toHaveBeenCalled();
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
      "provider receipt row 42"
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
      authorized_actions: ["retrieve"],
      use_model: true,
    }),
  ));
});
