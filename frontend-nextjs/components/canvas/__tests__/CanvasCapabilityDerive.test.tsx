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
    schema_version: 2,
    base_component: "table",
    operations: ["read", "derive", "edit", "bind"],
    manifest_revision: "manifest-3",
    data_binding: { subject_field: "Item" },
    fields: [
      { id: "item_id", label: "Item", type: "string", column: "Item" },
      { id: "quantity", label: "Quantity", type: "decimal", column: "Qty", unit: "each" },
      { id: "unit_price", label: "Unit price", type: "currency", column: "Price", currency: "USD" },
      { id: "line_total", label: "Line total", type: "currency", column: "Line Total", currency: "USD", derived: "quantity * unit_price", aggregate: "sum" },
    ],
    outputs: ["xlsx"],
    editable_fields: ["Qty", "Price"],
  },
  operations: {
    effective: ["read", "derive", "edit", "bind"],
    declared: ["read", "derive", "edit", "bind"],
  },
  revision: 3,
  dataset: {
    columns: ["Item", "Qty", "Price"],
    row_count: 2,
    source: { source_version: "source-1" },
  },
};

describe("CanvasCapabilityPanel typed derive", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (apiClient.get as jest.Mock).mockResolvedValue({ data: STATE });
    (apiClient.post as jest.Mock).mockResolvedValue({
      data: {
        success: true,
        operation: "derive",
        status: "complete",
        aggregates: { line_total: "350.00" },
        groups: [
          { field_id: "line_total", group_by: "item_id", group: "A", value: "200.00" },
        ],
        row_count: 2,
        input_receipt: { digest: "abcdef0123456789" },
        manifest_revision: "manifest-3",
        revision: 3,
      },
    });
  });

  it("shows typed fields and sends all three revisions", async () => {
    render(<CanvasCapabilityPanel canvasId="canvas-typed-1" />);
    await waitFor(() => expect(screen.getByTestId("capability-effective")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Data operations/i }));
    await waitFor(() => expect(screen.getByTestId("capability-typed-fields")).toBeInTheDocument());
    expect(screen.getByTestId("capability-typed-fields")).toHaveTextContent("line_total");
    expect(screen.getByTestId("capability-typed-fields")).toHaveTextContent("quantity * unit_price");

    fireEvent.click(screen.getByTestId("capability-derive"));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    const [url, body] = (apiClient.post as jest.Mock).mock.calls[0];
    expect(url).toBe("/api/canvas/canvas-typed-1/capability/derive");
    expect(body).toEqual({
      expected_revision: 3,
      manifest_revision: "manifest-3",
      source_version: "source-1",
    });
    await waitFor(() => expect(screen.getByTestId("capability-derive-result")).toHaveTextContent("350.00"));
    expect(screen.getByTestId("capability-derive-result")).toHaveTextContent("receipt: abcdef012345");
  });

  it("answers a missing value and resumes the same derive", async () => {
    (apiClient.post as jest.Mock).mockImplementation(async (url: string) => {
      if (String(url).includes("/answer")) {
        return {
          data: {
            success: true,
            status: "resolved",
            result: {
              success: true,
              operation: "derive",
              status: "complete",
              aggregates: { line_total: "200.00" },
              row_count: 1,
              input_receipt: { digest: "resumed-digest" },
            },
          },
        };
      }
      return {
        data: {
          success: true,
          operation: "derive",
          status: "clarification",
          clarification: {
            id: "derive-clarify-1",
            question: "Answer the missing value before a total can be calculated.",
            missing: [
              { row: 2, field_id: "quantity", label: "Quantity", unit: "each" },
            ],
          },
          revision: 3,
        },
      };
    });
    render(<CanvasCapabilityPanel canvasId="canvas-typed-1" />);
    await waitFor(() => expect(screen.getByTestId("capability-effective")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Data operations/i }));
    fireEvent.click(await screen.findByTestId("capability-derive"));
    await waitFor(() => expect(screen.getByTestId("capability-derive-clarification")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("capability-derive-answer-2-quantity"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByTestId("capability-derive-answer-submit"));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2));
    const [url, body] = (apiClient.post as jest.Mock).mock.calls[1];
    expect(url).toBe("/api/canvas/canvas-typed-1/capability/derive/derive-clarify-1/answer");
    expect(body).toEqual({
      expected_revision: 3,
      answers: [{ row: 2, field_id: "quantity", value: "2" }],
    });
    await waitFor(() => expect(screen.getByTestId("capability-derive-result")).toHaveTextContent("200.00"));
  });
});
