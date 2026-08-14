/**
 * OwnerDashboard tests (pages/dashboard/owner.tsx, was 0% coverage)
 *
 * Covers: successful load (metrics grid + briefing card), failed
 * response toast, network error toast, and the refresh button.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import OwnerDashboard from "@/pages/dashboard/owner";

jest.mock("@/components/layout/Layout", () => ({
  Layout: ({ children }: any) => <div data-testid="layout">{children}</div>,
}));

let latestMetrics: any = null;
jest.mock("@/components/dashboard/HealthMetricsGrid", () => ({
  HealthMetricsGrid: (props: any) => {
    latestMetrics = props.metrics;
    return <div data-testid="health-metrics-grid">Metrics</div>;
  },
}));

let latestBriefing: any = null;
jest.mock("@/components/dashboard/DailyBriefingCard", () => ({
  DailyBriefingCard: (props: any) => {
    latestBriefing = props;
    return <div data-testid="daily-briefing-card">Briefing</div>;
  },
}));

const mockToastError = jest.fn();
jest.mock("sonner", () => ({
  toast: {
    error: (...args: any[]) => mockToastError(...args),
  },
}));

const PAYLOAD = {
  metrics: { revenue: 100 },
  briefing: { owner_advice: "Focus on churn", priorities: ["Call Acme", "Review pricing"] },
};

describe("OwnerDashboard", () => {
  let mockFetch: jest.Mock;
  let consoleErrorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch as any;
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    latestMetrics = null;
    latestBriefing = null;
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  test("loads and renders dashboard data", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => PAYLOAD });
    render(<OwnerDashboard />);

    await waitFor(() => expect(screen.getByTestId("health-metrics-grid")).toBeInTheDocument());
    expect(latestMetrics).toEqual(PAYLOAD.metrics);
    expect(screen.getByTestId("daily-briefing-card")).toBeInTheDocument();
    expect(latestBriefing).toEqual({
      advice: "Focus on churn",
      priorities: ["Call Acme", "Review pricing"],
    });
    expect(screen.getByText("Owner Cockpit")).toBeInTheDocument();
    expect(screen.getByText("Open Simulator (Coming Soon)")).toBeDisabled();
  });

  test("shows an error toast when the response is not ok", async () => {
    mockFetch.mockResolvedValue({ ok: false, json: async () => ({}) });
    render(<OwnerDashboard />);

    await waitFor(() => expect(mockToastError).toHaveBeenCalledWith("Failed to load dashboard data"));
    expect(screen.queryByTestId("health-metrics-grid")).not.toBeInTheDocument();
  });

  test("shows a network error toast when fetch rejects", async () => {
    mockFetch.mockRejectedValue(new Error("offline"));
    render(<OwnerDashboard />);

    await waitFor(() => expect(mockToastError).toHaveBeenCalledWith("Network error"));
    await waitFor(() => expect(consoleErrorSpy).toHaveBeenCalled());
    expect(screen.queryByTestId("health-metrics-grid")).not.toBeInTheDocument();
  });

  test("refresh button re-fetches the dashboard", async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => PAYLOAD });
    render(<OwnerDashboard />);
    // Wait for the load to finish so the Refresh button is enabled again.
    await waitFor(() => expect(screen.getByTestId("health-metrics-grid")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(2));
    expect(mockFetch).toHaveBeenCalledWith("/api/business-health/dashboard");
  });

  test("refresh button is disabled while loading", async () => {
    let resolveFetch: (v: any) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      })
    );
    render(<OwnerDashboard />);
    expect(screen.getByRole("button", { name: /Refresh/ })).toBeDisabled();

    resolveFetch!({ ok: true, json: async () => PAYLOAD });
    await waitFor(() => expect(screen.getByRole("button", { name: /Refresh/ })).toBeEnabled());
  });
});
