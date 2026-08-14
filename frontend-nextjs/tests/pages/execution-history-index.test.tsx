/**
 * ExecutionHistoryPage tests (pages/execution-history/index.tsx, was 0% coverage)
 *
 * Covers: rendering the page shell with the agent history table.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ExecutionHistoryPage from "@/pages/execution-history";

jest.mock("@/components/Agents/AgentHistoryTable", () => ({
  __esModule: true,
  default: () => <div data-testid="agent-history-table">History</div>,
}));

describe("ExecutionHistoryPage", () => {
  test("renders the agent history table", () => {
    render(<ExecutionHistoryPage />);
    expect(screen.getByTestId("agent-history-table")).toBeInTheDocument();
  });
});
