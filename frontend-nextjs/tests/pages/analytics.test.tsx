/**
 * AnalyticsPage tests (pages/analytics.tsx, was 0% coverage)
 *
 * Covers: loading/error/retry states, summary cards, success-rate math,
 * workflow performance table (with + without data), integration health
 * table (present/absent), CSV export, and manual refresh.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AnalyticsPage from "@/pages/analytics";

const DASHBOARD = {
  workflows: {
    total_executions: 10,
    total_time_saved_hours: 3,
    total_business_value: 2500,
    workflow_count: 2,
    workflows: {
      "invoice-sync": {
        execution_count: 8,
        success_count: 7,
        failure_count: 1,
        total_duration_seconds: 3600,
        total_time_saved_seconds: 7200,
        total_business_value: 2000,
        last_executed: "2026-08-01",
        success_rate: 95,
        average_duration: 450,
      },
      "lead-score": {
        execution_count: 2,
        success_count: 1,
        failure_count: 1,
        total_duration_seconds: 600,
        total_time_saved_seconds: 900,
        total_business_value: 500,
        last_executed: "2026-08-02",
        success_rate: 75,
        average_duration: 300,
      },
    },
  },
  integrations: {
    total_integrations: 3,
    ready_count: 1,
    integrations: {
      slack: {
        call_count: 42,
        error_count: 2,
        total_response_time_ms: 10000,
        last_called: "2026-08-02",
        status: "READY",
        error_rate: 4.8,
        average_response_time: 238,
        uptime_percentage: 99.2,
      },
      shopify: {
        call_count: 10,
        error_count: 3,
        total_response_time_ms: 5000,
        last_called: "2026-08-01",
        status: "ERROR",
        error_rate: 30,
        average_response_time: 500,
        uptime_percentage: 95.0,
      },
      mailchimp: {
        call_count: 5,
        error_count: 1,
        total_response_time_ms: 2000,
        last_called: "2026-08-03",
        status: "PARTIAL",
        error_rate: 20,
        average_response_time: 400,
        uptime_percentage: 97.0,
      },
    },
  },
};

const okJson = (body: any) => ({ ok: true, json: async () => body });

describe("AnalyticsPage", () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  test("shows loading state initially", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<AnalyticsPage />);
    expect(screen.getByText("Loading analytics...")).toBeInTheDocument();
  });

  test("shows failure state and retries", async () => {
    mockFetch
      .mockRejectedValueOnce(new Error("down"))
      .mockResolvedValueOnce(okJson(DASHBOARD));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("Failed to load analytics data")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    await waitFor(() => expect(screen.getByText("Analytics Dashboard")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  test("renders summary cards and success rate", async () => {
    mockFetch.mockResolvedValue(okJson(DASHBOARD));
    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("Total Executions")).toBeInTheDocument());
    expect(screen.getAllByText("10").length).toBeGreaterThan(0);
    expect(screen.getByText("80.0%")).toBeInTheDocument();
    expect(screen.getByText("3h")).toBeInTheDocument();
    expect(screen.getByText("$2,500")).toBeInTheDocument();
  });

  test("workflow table renders per-workflow metrics", async () => {
    mockFetch.mockResolvedValue(okJson(DASHBOARD));
    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("invoice-sync")).toBeInTheDocument());
    expect(screen.getByText("lead-score")).toBeInTheDocument();
    expect(screen.getAllByText(/95.0/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/75.0/).length).toBeGreaterThan(0);
    expect(screen.getByText("450.00s")).toBeInTheDocument();
    expect(screen.getByText("2.00h")).toBeInTheDocument();
  });

  test("workflow table shows empty message when no workflows", async () => {
    mockFetch.mockResolvedValue(
      okJson({ ...DASHBOARD, workflows: { ...DASHBOARD.workflows, workflows: {} } })
    );
    render(<AnalyticsPage />);

    await waitFor(() =>
      expect(screen.getByText(/No workflow data yet/)).toBeInTheDocument()
    );
  });

  test("integration health table renders when integrations exist", async () => {
    mockFetch.mockResolvedValue(okJson(DASHBOARD));
    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("Integration Health")).toBeInTheDocument());
    expect(screen.getByText("slack")).toBeInTheDocument();
    expect(screen.getByText("shopify")).toBeInTheDocument();
    expect(screen.getByText("99.2%")).toBeInTheDocument();
    expect(screen.getByText("238ms")).toBeInTheDocument();
    expect(screen.getByText("1 of 3 integrations ready")).toBeInTheDocument();
    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
  });

  test("integration health section hidden when no integrations", async () => {
    mockFetch.mockResolvedValue(
      okJson({ ...DASHBOARD, integrations: { total_integrations: 0, ready_count: 0, integrations: {} } })
    );
    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("Analytics Dashboard")).toBeInTheDocument());
    expect(screen.queryByText("Integration Health")).not.toBeInTheDocument();
  });

  test("success rate is zero when no executions", async () => {
    mockFetch.mockResolvedValue(
      okJson({
        workflows: {
          total_executions: 0,
          total_time_saved_hours: 0,
          total_business_value: 0,
          workflow_count: 0,
          workflows: {},
        },
        integrations: { total_integrations: 0, ready_count: 0, integrations: {} },
      })
    );
    render(<AnalyticsPage />);
    await waitFor(() => expect(screen.getAllByText("0.0%").length).toBeGreaterThan(0));
  });

  test("refresh button refetches data", async () => {
    mockFetch.mockResolvedValue(okJson(DASHBOARD));
    render(<AnalyticsPage />);
    await waitFor(() => expect(screen.getByText("Total Executions")).toBeInTheDocument());
    const before = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() => expect(mockFetch.mock.calls.length).toBeGreaterThan(before));
  });

  test("export CSV for workflows triggers download", async () => {
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const blob = new Blob(["csv"], { type: "text/csv" });
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("/api/analytics/dashboard/kpis")) return okJson(DASHBOARD);
      return { ok: true, blob: async () => blob };
    });
    render(<AnalyticsPage />);
    await waitFor(() => expect(screen.getByText("Total Executions")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Export CSV/ }));
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/analytics/export/csv?metric_type=workflow")
    );
    clickSpy.mockRestore();
  });

  test("export CSV failure is logged without crash", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("/api/analytics/dashboard/kpis")) return okJson(DASHBOARD);
      throw new Error("export failed");
    });
    render(<AnalyticsPage />);
    await waitFor(() => expect(screen.getByText("Total Executions")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Export CSV/ }));
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    consoleSpy.mockRestore();
  });
});
