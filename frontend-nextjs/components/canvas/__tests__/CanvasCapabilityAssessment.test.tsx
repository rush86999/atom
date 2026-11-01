import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
  },
}));

import { apiClient } from "@/lib/api";
import { CanvasCapabilityPanel } from "../CanvasCapabilityPanel";

const STATE = {
  success: true,
  manifest: {
    schema_version: 1,
    base_component: "table",
    operations: ["read", "select", "calculate", "assess", "edit", "export", "bind"],
    data_binding: { subject_field: "Ref", measure_field: "Amount", status_field: "Status" },
    editable_fields: [],
    teaching_binding: { agent_id: "agent-1", scope_id: "task-1" },
    decision_options: ["APPROVE", "REVIEW"],
    task_policy: "policy",
    outputs: ["xlsx"],
    required_approvals: [],
  },
  operations: {
    effective: ["read", "select", "calculate", "assess", "edit", "export", "bind"],
  },
  revision: 1,
  dataset: { columns: ["Ref", "Amount"], row_count: 2 },
};

const DRAFT = {
  success: true,
  operation: "assess",
  certified: true,
  authorized: false,
  rendered: "",
  rendered_suppressed: true,
  execution_id: "exec-1",
  assessments: [
    { subject_id: "R-1", decision: "APPROVE", evidence_refs: [] },
  ],
  clarification: { state: "none", requirements: [], open_count: 0 },
};

function mockApi() {
  (apiClient.get as jest.Mock).mockImplementation(async (url: string) => {
    if (String(url).includes("/capability/decisions")) {
      return { data: { success: true, decisions: { "R-1": "APPROVE" } } };
    }
    return { data: STATE };
  });
  (apiClient.post as jest.Mock).mockImplementation(async (url: string) => {
    if (String(url).endsWith("/clarify")) {
      return {
        data: {
          ...DRAFT,
          certified: true,
          authorized: true,
          execution_id: "exec-2",
          clarification_resumed: true,
          clarification: { state: "none", requirements: [], open_count: 0 },
        },
      };
    }
    if (String(url).endsWith("/approve")) {
      return {
        data: {
          success: true,
          authorization: { state: "authorized", approved_by: "owner-1" },
        },
      };
    }
    return { data: DRAFT };
  });
}

async function openAndAssess() {
  render(<CanvasCapabilityPanel canvasId="canvas-1" />);
  await waitFor(() => expect(screen.getByTestId("capability-effective")).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /Data operations/i }));
  fireEvent.click(screen.getByTestId("capability-assess"));
  await waitFor(() => expect(screen.getByTestId("capability-assessment-state")).toBeInTheDocument());
}

describe("CanvasCapabilityPanel assessment treatment", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi();
  });

  it("labels an unapproved assessment as a draft and approves the exact execution", async () => {
    await openAndAssess();
    expect(screen.getByText(/Draft assessment — not authorized/i)).toBeInTheDocument();
    expect(screen.getByTestId("capability-assess-approve")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("capability-assess-approve"));
    await waitFor(() =>
      expect(screen.getByText(/Authorized assessment/i)).toBeInTheDocument());
    expect(screen.getByTestId("capability-decisions")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("capability-decisions"));
    await waitFor(() =>
      expect(screen.getByTestId("capability-decisions-result")).toHaveTextContent("R-1: APPROVE"));
  });

  it("shows clarification questions and resumes the same assessment", async () => {
    (apiClient.post as jest.Mock).mockImplementationOnce(async () => ({
      data: {
        ...DRAFT,
        certified: true,
        authorized: false,
        clarification: {
          state: "open",
          open_count: 1,
          requirements: [{
            subject: "R-2",
            requirement: "Confirm the amount for R-2.",
            answer: null,
          }],
        },
      },
    }));
    await openAndAssess();
    expect(screen.getByTestId("capability-clarification")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Clarification answer R-2"), {
      target: { value: "95.00" },
    });
    fireEvent.click(screen.getByTestId("capability-clarification-submit"));
    await waitFor(() =>
      expect(screen.getByText(/Authorized assessment/i)).toBeInTheDocument());
  });
});
