/**
 * TablesPage tests (pages/automations/tables.tsx, was 0% coverage)
 *
 * Covers: rendering WorkflowTables with the full-height class and
 * invoking the onSelectTable handler passed down to it.
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import TablesPage from "@/pages/automations/tables";

let latestTablesProps: any = null;
jest.mock("@/components/Automations/WorkflowTables", () => ({
  __esModule: true,
  default: (props: any) => {
    latestTablesProps = props;
    return <div data-testid="workflow-tables">Tables</div>;
  },
}));

describe("TablesPage", () => {
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    latestTablesProps = null;
    consoleLogSpy = jest.spyOn(console, "log").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
  });

  test("renders WorkflowTables full height", () => {
    render(<TablesPage />);
    expect(screen.getByTestId("workflow-tables")).toBeInTheDocument();
    expect(latestTablesProps.className).toBe("h-full");
  });

  test("logs the selected table when the handler fires", () => {
    render(<TablesPage />);
    act(() => {
      latestTablesProps.onSelectTable({ id: "tbl-1", name: "Leads" });
    });
    expect(consoleLogSpy).toHaveBeenCalledWith("Selected table:", {
      id: "tbl-1",
      name: "Leads",
    });
  });
});
