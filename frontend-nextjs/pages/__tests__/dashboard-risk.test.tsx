import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import RiskDashboard from "@/pages/dashboard/risk";

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  Layout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/components/desktop/DesktopSecurityAudit", () => ({
  __esModule: true,
  DesktopSecurityAudit: () => <div data-testid="security-audit" />,
}));

function okJson(data: unknown) {
  return { ok: true, json: async () => data };
}

const CHURN = [
  {
    customer_id: "cust-1",
    customer_name: "Acme Corp",
    churn_probability: 0.85,
    risk_factors: ["low engagement", "missed renewals"],
    mrr_at_risk: 1200,
    recommended_action: "Schedule executive check-in",
  },
  {
    customer_id: "cust-2",
    customer_name: "Globex",
    churn_probability: 0.3,
    risk_factors: ["contract ends soon"],
    mrr_at_risk: 400,
    recommended_action: "Send renewal proposal",
  },
];

const FINANCIAL = {
  fraud_alerts: [
    { transaction_id: "tx-99", amount: 2500, flag_reason: "Unusual velocity" },
  ],
  ar_delays: [
    {
      invoice_id: "inv-7",
      client_name: "Initech",
      due_date: "2026-08-15T00:00:00Z",
      amount: 8500,
      likelihood_late: 0.62,
    },
  ],
};

const GROWTH = {
  readiness_score: 74,
  bottlenecks: [
    { area: "Hiring capacity", status: "strained" },
    { area: "Cloud spend", status: "healthy" },
  ],
};

describe("RiskDashboard", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/risk/churn")) return Promise.resolve(okJson({ data: CHURN }));
      if (url.includes("/api/risk/financial")) return Promise.resolve(okJson({ data: FINANCIAL }));
      if (url.includes("/api/risk/growth")) return Promise.resolve(okJson({ data: GROWTH }));
      return Promise.resolve(okJson({}));
    });
  });

  it("renders churn predictions, financial risk and growth data", async () => {
    render(<RiskDashboard />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /risk control center/i })
      ).toBeInTheDocument();
    });

    // Top-level stats: 1 customer above 0.5 probability
    await waitFor(() => {
      expect(screen.getByText("1 Customers")).toBeInTheDocument();
    });
    expect(screen.getByText("74/100")).toBeInTheDocument();
    // Active alerts = fraud + AR delays
    expect(screen.getByText("2")).toBeInTheDocument();

    // Churn predictions
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("85% Risk")).toBeInTheDocument();
    expect(screen.getByText("$1200 MRR")).toBeInTheDocument();
    expect(screen.getByText(/low engagement, missed renewals/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /action: schedule executive check-in/i })
    ).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();

    // Fraud alerts
    expect(screen.getByText("Fraud Alerts")).toBeInTheDocument();
    expect(screen.getByText("#tx-99")).toBeInTheDocument();
    expect(screen.getByText("$2500")).toBeInTheDocument();
    expect(screen.getByText("Unusual velocity")).toBeInTheDocument();

    // AR delays
    expect(screen.getByText("Predicted AR Delays")).toBeInTheDocument();
    expect(screen.getByText("Initech")).toBeInTheDocument();
    expect(screen.getByText("62% Late Chance")).toBeInTheDocument();

    // Scaling constraints
    expect(screen.getByText("Scaling Constraints")).toBeInTheDocument();
    expect(screen.getByText("Hiring capacity")).toBeInTheDocument();
    expect(screen.getByText("Strained ⚠️")).toBeInTheDocument();
    expect(screen.getByText("Healthy ✅")).toBeInTheDocument();

    expect(screen.getByTestId("security-audit")).toBeInTheDocument();
  });

  it("renders zeroed stats without crashing when all payloads are empty", async () => {
    mockFetch.mockImplementation((url: string) => Promise.resolve(okJson({ data: {} })));

    render(<RiskDashboard />);

    await waitFor(() => {
      expect(screen.getByText("0 Customers")).toBeInTheDocument();
    });
    expect(screen.getByText("0/100")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("does not crash when the risk endpoints fail", async () => {
    mockFetch.mockRejectedValue(new Error("down"));

    render(<RiskDashboard />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /risk control center/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText("0 Customers")).toBeInTheDocument();
  });

  it("fetches all three risk endpoints on mount", async () => {
    render(<RiskDashboard />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /risk control center/i })
      ).toBeInTheDocument();
    });

    const calledUrls = mockFetch.mock.calls.map((c) => String(c[0]));
    expect(calledUrls).toContainEqual(expect.stringContaining("/api/risk/churn"));
    expect(calledUrls).toContainEqual(expect.stringContaining("/api/risk/financial"));
    expect(calledUrls).toContainEqual(expect.stringContaining("/api/risk/growth"));
  });
});
