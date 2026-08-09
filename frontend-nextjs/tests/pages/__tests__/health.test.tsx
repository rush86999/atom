import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BusinessHealthDashboard from "@/pages/health";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockToast = jest.fn();

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const badResponse = (status = 500) => ({
  ok: false,
  status,
  json: async () => ({}),
});

const PRIORITIES = {
  owner_advice: "Focus on the Acme renewal before Friday.",
  priorities: [
    {
      id: "p1",
      type: "GROWTH",
      title: "Expand HVAC services",
      description: "Add two service lines",
      priority: "HIGH",
      action_link: "/agents/1",
    },
  ],
};

const FORENSICS = {
  drift: {
    data: [
      {
        vendor_name: "AWS",
        description: "Compute prices drifting up",
        drift_percent: 15,
        latest_price: 412.5,
      },
    ],
    is_mock: true,
  },
  pricing: {
    data: [
      {
        item: "Premium Tune-Up",
        reason: "Underpriced vs market",
        current_price: 89,
        target_price: 119,
      },
    ],
    is_mock: false,
  },
  waste: {
    data: [{ service_name: "Trello", mrr: 24 }],
    is_mock: false,
  },
};

const RISK = {
  churn: {
    churn_risk: [
      { client_name: "Corp X", days_silent: 42, value: 12500, risk_level: "HIGH" },
    ],
    vip_opportunities: [{ name: "Jane", company: "Acme", ai_score: 92 }],
    is_mock: true,
  },
  alerts: {
    ar_alerts: [
      { description: "Invoice #1041 overdue", days_overdue: 18, amount: 4800 },
    ],
    is_mock: false,
  },
  fraud: {
    anomalies: [
      {
        type: "suspicious_refund",
        amount: 3200,
        description: "Refund to new account",
        date: "2026-08-01",
      },
    ],
    is_mock: false,
  },
};

const INTERVENTIONS = [
  {
    id: "int-1",
    type: "URGENT",
    title: "Renegotiate AWS pricing",
    description: "Compute costs exceeded budget",
    suggested_action: "renegotiate",
    action_payload: { vendor: "aws" },
  },
];

const mockFetch = jest.fn();

describe("BusinessHealthDashboard (pages/health.tsx)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/business-health/priorities") {
        return Promise.resolve(okResponse(PRIORITIES));
      }
      if (url === "/api/business-health/forensics/price-drift") {
        return Promise.resolve(okResponse(FORENSICS.drift));
      }
      if (url === "/api/business-health/forensics/pricing-advisor") {
        return Promise.resolve(okResponse(FORENSICS.pricing));
      }
      if (url === "/api/business-health/forensics/waste") {
        return Promise.resolve(okResponse(FORENSICS.waste));
      }
      if (url === "/api/risk/customer-protection?workspace_id=default") {
        return Promise.resolve(okResponse(RISK.churn));
      }
      if (url === "/api/risk/early-warning?workspace_id=default") {
        return Promise.resolve(okResponse(RISK.alerts));
      }
      if (url === "/api/risk/fraud?workspace_id=default") {
        return Promise.resolve(okResponse(RISK.fraud));
      }
      if (url.startsWith("/api/business-health/interventions/generate")) {
        return Promise.resolve(okResponse({ interventions: INTERVENTIONS }));
      }
      if (url.startsWith("/api/business-health/interventions/") && url.endsWith("/execute")) {
        return Promise.resolve(okResponse({ message: "Executed successfully" }));
      }
      if (url === "/api/business-health/simulate") {
        return Promise.resolve(
          okResponse({
            roi: "210%",
            breakeven: "6 Months",
            prediction: "Positive cash flow impact expected.",
          })
        );
      }
      return Promise.resolve(okResponse({}));
    });
    global.fetch = mockFetch as any;
  });

  it("shows the analyzing placeholder while data is pending, then the full dashboard", async () => {
    const pending: Array<(r: any) => void> = [];
    mockFetch.mockImplementation(() => new Promise((resolve) => pending.push(resolve)));

    render(<BusinessHealthDashboard />);

    expect(screen.getByText(/Analyzing business vitals/)).toBeInTheDocument();

    pending.forEach((resolve) => resolve(okResponse(PRIORITIES)));
    await waitFor(() =>
      expect(screen.queryByText(/Analyzing business vitals/)).not.toBeInTheDocument()
    );
    expect(screen.getByText(/Focus on the Acme renewal before Friday/)).toBeInTheDocument();
    expect(screen.getByText("Expand HVAC services")).toBeInTheDocument();
  });

  it("renders owner advice, priorities, interventions, forensics and risk data", async () => {
    render(<BusinessHealthDashboard />);

    // AI narrative advice + priority checklist
    expect(await screen.findByText(/Focus on the Acme renewal before Friday/)).toBeInTheDocument();
    expect(screen.getByText("What Should I Do Today?")).toBeInTheDocument();
    expect(screen.getByText("Expand HVAC services")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("Add two service lines")).toBeInTheDocument();

    // Active interventions (Phase 11)
    expect(screen.getByText("Active Interventions")).toBeInTheDocument();
    expect(screen.getByText("1 Actions Pending")).toBeInTheDocument();
    expect(screen.getByText("Renegotiate AWS pricing")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve & execute/i })).toBeInTheDocument();

    // Forensics default tab (drift) + mock badges
    expect(screen.getByText("Financial Forensics")).toBeInTheDocument();
    expect(screen.getByText("AWS")).toBeInTheDocument();
    expect(screen.getByText("+15%")).toBeInTheDocument();
    expect(screen.getByText("$412.5")).toBeInTheDocument();
    expect(screen.getAllByText("MOCK DATA")).toHaveLength(2); // forensics + risk headers
    expect(screen.getAllByText("MOCK")).toHaveLength(1); // per-row drift badge

    // Risk default tab (churn) + VIP opportunities
    expect(screen.getByText("Risk & Customer Protection")).toBeInTheDocument();
    expect(screen.getByText("Corp X")).toBeInTheDocument();
    expect(screen.getByText(/42 days silent/)).toBeInTheDocument();
    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
    expect(screen.getByText("Jane")).toBeInTheDocument();
    expect(screen.getByText(/AI Score: 92/)).toBeInTheDocument();
    expect(screen.getByText("VIP")).toBeInTheDocument();
  });

  it("switches forensics tabs (pricing, waste) and risk tabs (alerts, fraud)", async () => {
    render(<BusinessHealthDashboard />);
    await screen.findByText("Financial Forensics");

    fireEvent.click(screen.getByText("Pricing Advice"));
    expect(screen.getByText("Premium Tune-Up")).toBeInTheDocument();
    expect(screen.getByText("Save Margin")).toBeInTheDocument();
    expect(screen.getByText("$89")).toBeInTheDocument();
    expect(screen.getByText("$119")).toBeInTheDocument();

    fireEvent.click(screen.getByText("SaaS Waste"));
    expect(screen.getByText("Trello")).toBeInTheDocument();
    expect(screen.getByText("$24/mo")).toBeInTheDocument();
    expect(screen.getByText("ZOMBIE SUBSCRIPTION")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Early Warning"));
    expect(screen.getByText("Invoice #1041 overdue")).toBeInTheDocument();
    expect(screen.getByText(/Overdue by 18 days/)).toBeInTheDocument();
    expect(screen.getByText("$4,800")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Fraud Watch"));
    expect(screen.getByText("suspicious_refund")).toBeInTheDocument();
    expect(screen.getByText("$3,200")).toBeInTheDocument();
    expect(screen.getByText("Refund to new account")).toBeInTheDocument();
  });

  it("renders the smooth-sailing empty state when no issues are detected", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/business-health/priorities") return Promise.resolve(okResponse({}));
      return Promise.resolve(okResponse({ data: [], is_mock: false }));
    });

    render(<BusinessHealthDashboard />);

    expect(await screen.findByText("Everything is running smoothly.")).toBeInTheDocument();
    expect(screen.getByText(/Enjoy the quiet or focus on long-term strategy/)).toBeInTheDocument();
    expect(screen.getByText("No price drift detected.")).toBeInTheDocument();
    expect(screen.getByText("No high-risk clients detected.")).toBeInTheDocument();
    expect(screen.queryByText("Active Interventions")).not.toBeInTheDocument();
  });

  it("survives partial endpoint failures — one bad endpoint does not blank the dashboard (BUG-063)", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/business-health/priorities") return Promise.resolve(badResponse(500));
      if (url === "/api/risk/fraud?workspace_id=default") return Promise.reject(new Error("boom"));
      if (url.startsWith("/api/business-health/interventions/generate")) {
        return Promise.resolve(okResponse({ interventions: INTERVENTIONS }));
      }
      return Promise.resolve(okResponse(FORENSICS.drift));
    });

    render(<BusinessHealthDashboard />);

    // Priorities failed but the rest of the dashboard still renders
    expect(await screen.findByText("Active Interventions")).toBeInTheDocument();
    expect(screen.getByText("Renegotiate AWS pricing")).toBeInTheDocument();
    expect(screen.getByText("AWS")).toBeInTheDocument();
    expect(screen.getByText("Everything is running smoothly.")).toBeInTheDocument();
  });

  it("runs a strategic simulation with the selected decision type and renders the report", async () => {
    render(<BusinessHealthDashboard />);
    await screen.findByText("Strategic Simulator");

    fireEvent.click(screen.getByText("CAPEX"));
    fireEvent.change(screen.getByPlaceholderText(/Describe the decision/), {
      target: { value: "Buy new vans for $80k" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run strategic simulation/i }));

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/business-health/simulate",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            decision_type: "CAPEX",
            data: { context: "Buy new vans for $80k" },
          }),
        })
      )
    );

    expect(await screen.findByText("Simulation Report")).toBeInTheDocument();
    expect(screen.getByText("AI Verified")).toBeInTheDocument();
    expect(screen.getByText("210%")).toBeInTheDocument();
    expect(screen.getByText("6 Months")).toBeInTheDocument();
    expect(screen.getByText(/Positive cash flow impact expected/)).toBeInTheDocument();
  });

  it("disables the simulate button until input is provided", async () => {
    render(<BusinessHealthDashboard />);
    await screen.findByText("Strategic Simulator");

    const runButton = screen.getByRole("button", { name: /run strategic simulation/i });
    expect(runButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/Describe the decision/), {
      target: { value: "Hire a technician" },
    });
    expect(screen.getByRole("button", { name: /run strategic simulation/i })).toBeEnabled();
  });

  it("shows an error toast when the simulation request fails", async () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/business-health/simulate") {
        return Promise.reject(new Error("network down"));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<BusinessHealthDashboard />);
    await screen.findByText("Strategic Simulator");

    fireEvent.change(screen.getByPlaceholderText(/Describe the decision/), {
      target: { value: "Scale marketing" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run strategic simulation/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Simulation failed" })
      )
    );
  });

  it("executes an intervention, marks it completed and shows a toast", async () => {
    render(<BusinessHealthDashboard />);
    await screen.findByText("Active Interventions");

    fireEvent.click(screen.getByRole("button", { name: /approve & execute/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Intervention Executed",
          description: "Executed successfully",
        })
      )
    );
    await waitFor(() => expect(screen.getByText("Done")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /approve & execute/i })).not.toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/business-health/interventions/int-1/execute",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "renegotiate", payload: { vendor: "aws" } }),
      })
    );
  });

  it("shows an error toast and keeps the button when intervention execution fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("/execute")) return Promise.resolve(badResponse(500));
      if (url.startsWith("/api/business-health/interventions/generate")) {
        return Promise.resolve(okResponse({ interventions: INTERVENTIONS }));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<BusinessHealthDashboard />);
    await screen.findByText("Active Interventions");

    fireEvent.click(screen.getByRole("button", { name: /approve & execute/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Execution Error" })
      )
    );
    expect(screen.getByRole("button", { name: /approve & execute/i })).toBeInTheDocument();
    expect(screen.queryByText("Done")).not.toBeInTheDocument();
  });

  it("refetches all diagnostics when Refresh Diagnostics is clicked", async () => {
    render(<BusinessHealthDashboard />);
    await screen.findByText("What Should I Do Today?");

    expect(
      mockFetch.mock.calls.filter(([u]) => u === "/api/business-health/priorities")
    ).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: /refresh diagnostics/i }));

    await waitFor(() =>
      expect(
        mockFetch.mock.calls.filter(([u]) => u === "/api/business-health/priorities")
      ).toHaveLength(2)
    );
  });
});
