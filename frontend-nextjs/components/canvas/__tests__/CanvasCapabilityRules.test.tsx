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
    decision_options: ["APPROVE", "REVIEW", "DENY"],
    task_policy: "policy",
    outputs: ["xlsx"],
    required_approvals: [],
  },
  operations: {
    effective: ["read", "select", "calculate", "assess", "edit", "export", "bind"],
  },
  revision: 1,
  dataset: { columns: ["Ref", "Amount", "Status"], row_count: 3 },
};

describe("CanvasCapabilityPanel guided decision rules", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (apiClient.get as jest.Mock).mockResolvedValue({ data: STATE });
    (apiClient.put as jest.Mock).mockImplementation(async (_url: string, body: any) => ({
      data: {
        success: true,
        manifest: body.manifest,
        operations: STATE.operations,
        revision: 2,
        manifest_revision: "manifest-2",
        policy_revision: "policy-2",
      },
    }));
  });

  it("builds deterministic rules from fields without editing JSON", async () => {
    render(<CanvasCapabilityPanel canvasId="canvas-1" />);
    await waitFor(() => expect(screen.getByTestId("capability-effective")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Data operations/i }));
    fireEvent.change(screen.getByTestId("capability-guided-subject"), {
      target: { value: "Ref" },
    });
    fireEvent.change(screen.getByTestId("capability-guided-measure"), {
      target: { value: "Amount" },
    });
    fireEvent.change(screen.getByTestId("capability-guided-status"), {
      target: { value: "Status" },
    });
    fireEvent.click(screen.getByTestId("capability-guided-editable-Amount"));
    fireEvent.click(screen.getByTestId("capability-rule-add"));

    fireEvent.change(screen.getByTestId("capability-rule-0-decision"), {
      target: { value: "APPROVE" },
    });
    fireEvent.change(screen.getByTestId("capability-rule-0-condition-0-field"), {
      target: { value: "Amount" },
    });
    fireEvent.change(screen.getByTestId("capability-rule-0-condition-0-op"), {
      target: { value: "gte" },
    });
    fireEvent.change(screen.getByTestId("capability-rule-0-condition-0-value"), {
      target: { value: "100" },
    });
    fireEvent.change(screen.getByTestId("capability-rule-0-basis"), {
      target: { value: "Open and Amount at least 100" },
    });
    fireEvent.click(screen.getByTestId("capability-guided-save"));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
    const [url, body] = (apiClient.put as jest.Mock).mock.calls[0];
    expect(url).toBe("/api/canvas/canvas-1/capability/manifest");
    expect(body.manifest.assessment_mode).toBe("deterministic");
    expect(body.manifest.data_binding).toMatchObject({
      subject_field: "Ref",
      measure_field: "Amount",
      status_field: "Status",
    });
    expect(body.manifest.editable_fields).toEqual(["Amount"]);
    expect(body.manifest.decision_options).toEqual(["APPROVE", "REVIEW", "DENY"]);
    expect(body.manifest.decision_rules).toEqual([{
      decision: "APPROVE",
      basis: "Open and Amount at least 100",
      when: [{ field: "Amount", op: "gte", value: "100" }],
    }]);
    await waitFor(() => expect(screen.getByTestId("capability-result")).toHaveTextContent("manifest"));
  });

  it("adds the required REVIEW fallback when the labels omit it", async () => {
    render(<CanvasCapabilityPanel canvasId="canvas-1" />);
    await waitFor(() => expect(screen.getByTestId("capability-effective")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Data operations/i }));
    fireEvent.change(screen.getByTestId("capability-guided-decisions"), {
      target: { value: "APPROVE, DENY" },
    });
    fireEvent.click(screen.getByTestId("capability-rule-add"));
    fireEvent.change(screen.getByTestId("capability-rule-0-condition-0-field"), {
      target: { value: "Status" },
    });
    fireEvent.change(screen.getByTestId("capability-rule-0-condition-0-value"), {
      target: { value: "Closed" },
    });
    fireEvent.click(screen.getByTestId("capability-guided-save"));

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledTimes(1));
    const [, body] = (apiClient.put as jest.Mock).mock.calls[0];
    expect(body.manifest.decision_options).toContain("REVIEW");
    expect(body.manifest.decision_rules[0].when).toEqual([
      { field: "Status", op: "eq", value: "Closed" },
    ]);
  });
});
