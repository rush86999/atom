import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AnalyticsPage from "@/pages/analytics";

const KPI_RESPONSE = {
  workflows: {
    total_executions: 10,
    total_time_saved_hours: 12.5,
    total_business_value: 4200,
    workflow_count: 2,
    workflows: {
      "invoice-approval": {
        execution_count: 7,
        success_count: 6,
        failure_count: 1,
        total_duration_seconds: 7200,
        total_time_saved_seconds: 5400,
        total_business_value: 3000,
        last_executed: "2026-08-01T00:00:00Z",
        success_rate: 85.7,
        average_duration: 1028.57,
      },
      "lead-scoring": {
        execution_count: 3,
        success_count: 3,
        failure_count: 0,
        total_duration_seconds: 900,
        total_time_saved_seconds: 1800,
        total_business_value: 1200,
        last_executed: "2026-08-02T00:00:00Z",
        success_rate: 100,
        average_duration: 300,
      },
    },
  },
  integrations: {
    total_integrations: 1,
    ready_count: 1,
    integrations: {
      Slack: {
        call_count: 42,
        error_count: 2,
        total_response_time_ms: 5000,
        last_called: "2026-08-02T00:00:00Z",
        status: "READY",
        error_rate: 4.76,
        average_response_time: 119.05,
        uptime_percentage: 99.9,
      },
    },
  },
};

describe("AnalyticsPage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
  });

  it("shows a loading state while fetching KPIs", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<AnalyticsPage />);
    expect(screen.getByText("Loading analytics...")).toBeInTheDocument();
  });

  it("renders summary cards and per-workflow metrics from KPI data", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => KPI_RESPONSE,
    });

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /analytics dashboard/i })
      ).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/analytics/dashboard/kpis")
    );

    // Summary cards
    expect(screen.getByText("Total Executions")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    // success rate = (6 + 3) / 10 = 90.0%
    expect(screen.getByText("90.0%")).toBeInTheDocument();
    expect(screen.getByText("12.5h")).toBeInTheDocument();
    expect(screen.getByText("$4,200")).toBeInTheDocument();
    expect(screen.getByText("2 workflows tracked")).toBeInTheDocument();

    // Workflow table rows
    expect(screen.getByText("invoice-approval")).toBeInTheDocument();
    expect(screen.getByText("85.7%")).toBeInTheDocument();
    expect(screen.getByText("lead-scoring")).toBeInTheDocument();
    expect(screen.getByText("1028.57s")).toBeInTheDocument();
    expect(screen.getByText("1.50h")).toBeInTheDocument();

    // Integration health table
    expect(screen.getByText("Integration Health")).toBeInTheDocument();
    expect(screen.getByText("1 of 1 integrations ready")).toBeInTheDocument();
    expect(screen.getByText("99.9%")).toBeInTheDocument();
    expect(screen.getByText("119ms")).toBeInTheDocument();
  });

  it("shows an empty-workflow message when no workflows are tracked", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        workflows: { ...KPI_RESPONSE.workflows, workflows: {} },
        integrations: { total_integrations: 0, ready_count: 0, integrations: {} },
      }),
    });

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText(/no workflow data yet/i)).toBeInTheDocument();
    });
    // Success rate falls back to 0.0% when there are no executions
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("hides the integration health card when no integrations exist", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        workflows: KPI_RESPONSE.workflows,
        integrations: { total_integrations: 0, ready_count: 0, integrations: {} },
      }),
    });

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Executions")).toBeInTheDocument();
    });
    expect(screen.queryByText("Integration Health")).not.toBeInTheDocument();
  });

  it("shows an error state with a working Retry button when the fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("network down"));
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => KPI_RESPONSE,
    });

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Failed to load analytics data")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("Total Executions")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("refreshes data when the Refresh button is clicked", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => KPI_RESPONSE,
    });

    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Total Executions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.filter((c) =>
        String(c[0]).includes("/api/analytics/dashboard/kpis")
      )).toHaveLength(2);
    });
  });

  it("exports workflow CSV via a download link", async () => {
    const createObjectURL = jest.fn(() => "blob:mock");
    const revokeObjectURL = jest.fn();
    Object.defineProperty(window.URL, "createObjectURL", { value: createObjectURL, configurable: true });
    Object.defineProperty(window.URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
    const clickSpy = jest.fn();
    jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(clickSpy);

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => KPI_RESPONSE,
      blob: async () => new Blob(["a,b"], { type: "text/csv" }),
    });

    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Total Executions")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));

    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalled();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/analytics/export/csv?metric_type=workflow")
    );
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalled();
  });
});
