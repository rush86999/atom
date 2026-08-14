/**
 * RiskDashboard tests (pages/dashboard/risk.tsx, was 0% coverage)
 *
 * Covers: summary stats (high churn count, readiness score, active
 * alerts), churn rows across every risk color band, fraud alerts,
 * AR delays, growth bottlenecks, empty-data defaults, and the
 * fetch-failure path.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import RiskDashboard from "@/pages/dashboard/risk";

jest.mock("@/components/layout/Layout", () => ({
  Layout: ({ children }: any) => <div data-testid="layout">{children}</div>,
}));

jest.mock("@/components/desktop/DesktopSecurityAudit", () => ({
  DesktopSecurityAudit: () => <div data-testid="desktop-security-audit">Security</div>,
}));

const CHURN = [
  {
    customer_id: "c1",
    customer_name: "Acme Corp",
    churn_probability: 0.85,
    risk_factors: ["usage drop", "support ticket"],
    mrr_at_risk: 500,
    recommended_action: "Schedule call",
  },
  {
    customer_id: "c2",
    customer_name: "Beta LLC",
    churn_probability: 0.5,
    risk_factors: ["invoice delay"],
    mrr_at_risk: 250,
    recommended_action: "Send nudge",
  },
  {
    customer_id: "c3",
    customer_name: "Gamma Inc",
    churn_probability: 0.2,
    risk_factors: ["none"],
    mrr_at_risk: 100,
    recommended_action: "Monitor",
  },
];

const FINANCIAL = {
  fraud_alerts: [
    { transaction_id: "tx-1", amount: 999, flag_reason: "velocity spike" },
  ],
  ar_delays: [
    { invoice_id: "inv-1", client_name: "Delta Co", due_date: "2026-09-01T00:00:00Z", amount: 4200, likelihood_late: 0.7 },
  ],
};

const GROWTH = {
  readiness_score: 72,
  bottlenecks: [
    { area: "Support", status: "strained" },
    { area: "Infra", status: "healthy" },
  ],
};

const okJson = (body: any) => ({ ok: true, json: async () => body });

describe("RiskDashboard", () => {
  let mockFetch: jest.Mock;
  let consoleErrorSpy: jest.SpyInstance;

  const mockDataFetch = () =>
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/risk/churn")) return Promise.resolve(okJson({ data: CHURN }));
      if (url.includes("/api/risk/financial")) return Promise.resolve(okJson({ data: FINANCIAL }));
      return Promise.resolve(okJson({ data: GROWTH }));
    });

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch as any;
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockDataFetch();
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  test("renders summary stat cards", async () => {
    render(<RiskDashboard />);
    // Only Acme (0.85) clears the > 0.5 churn threshold (0.5 is not > 0.5).
    await waitFor(() => expect(screen.getByText("1 Customers")).toBeInTheDocument());
    expect(screen.getByText("72/100")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // 1 fraud + 1 AR delay
    expect(screen.getByText("Fraud & AR Flags")).toBeInTheDocument();
    expect(screen.getByTestId("desktop-security-audit")).toBeInTheDocument();
  });

  test("renders churn predictions with all risk bands and actions", async () => {
    render(<RiskDashboard />);
    await waitFor(() => expect(screen.getByText("Acme Corp")).toBeInTheDocument());

    expect(screen.getByText("85% Risk")).toBeInTheDocument();
    expect(screen.getByText("50% Risk")).toBeInTheDocument();
    expect(screen.getByText("20% Risk")).toBeInTheDocument();
    expect(screen.getByText("Risk: usage drop, support ticket")).toBeInTheDocument();
    expect(screen.getByText("$500 MRR")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Action: Schedule call" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Action: Send nudge" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Action: Monitor" })).toBeInTheDocument();
  });

  test("renders fraud alerts and AR delays", async () => {
    render(<RiskDashboard />);
    await waitFor(() => expect(screen.getByText("#tx-1")).toBeInTheDocument());

    expect(screen.getByText("$999")).toBeInTheDocument();
    expect(screen.getByText("velocity spike")).toBeInTheDocument();

    expect(screen.getByText("Delta Co")).toBeInTheDocument();
    expect(screen.getByText("70% Late Chance")).toBeInTheDocument();
  });

  test("renders scaling constraints with strained and healthy states", async () => {
    render(<RiskDashboard />);
    await waitFor(() => expect(screen.getByText("72")).toBeInTheDocument());

    expect(screen.getByText("Support")).toBeInTheDocument();
    expect(screen.getByText("Strained ⚠️")).toBeInTheDocument();
    expect(screen.getByText("Infra")).toBeInTheDocument();
    expect(screen.getByText("Healthy ✅")).toBeInTheDocument();
    expect(screen.getByText("Readiness Score")).toBeInTheDocument();
  });

  test("falls back to zeroed stats when endpoints return no data", async () => {
    mockFetch.mockImplementation((url: string) => Promise.resolve(okJson({})));
    render(<RiskDashboard />);
    await waitFor(() => expect(screen.getByText("0 Customers")).toBeInTheDocument());
    expect(screen.getByText("0/100")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  test("handles fetch failure gracefully", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    render(<RiskDashboard />);
    await waitFor(() => expect(screen.getByText("0 Customers")).toBeInTheDocument());
    await waitFor(() =>
      expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to load risk data", expect.any(Error))
    );
  });
});
