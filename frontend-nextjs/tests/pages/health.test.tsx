import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BusinessHealthDashboard from "@/pages/health";

const mockToast = jest.fn();

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

const PRIORITIES = {
  owner_advice: "Focus on collections to stabilize cash flow.",
  priorities: [
    {
      id: "p1",
      type: "RISK",
      title: "Chase overdue invoices",
      description: "3 accounts are past 60 days",
      priority: "HIGH",
      action_link: "/collections",
    },
    {
      id: "p2",
      type: "GROWTH",
      title: "Raise prices on Pro plan",
      description: "Margin recovery opportunity",
      priority: "MEDIUM",
      action_link: "/pricing",
    },
  ],
};

const DRIFT = {
  data: [
    {
      vendor_name: "Acme Cloud",
      description: "Price increased above threshold",
      drift_percent: 12,
      latest_price: 1200,
    },
  ],
  metadata: { is_mock: true },
};
const PRICING = {
  data: [
    {
      item: "Pro Plan",
      reason: "Below market benchmark",
      current_price: 49,
      target_price: 59,
    },
  ],
  metadata: { is_mock: false },
};
const WASTE = {
  data: [{ service_name: "Trello", mrr: 24 }],
  metadata: { is_mock: false },
};

const CHURN = {
  churn_risk: [
    { client_name: "Northwind", days_silent: 21, value: 12000, risk_level: "HIGH" },
  ],
  vip_opportunities: [{ name: "Acme Corp", company: "Acme", ai_score: 92 }],
  is_mock: false,
};
const ALERTS = {
  ar_alerts: [
    { description: "Invoice #1042 unpaid", days_overdue: 5, amount: 15000 },
  ],
  is_mock: false,
};
const FRAUD = {
  anomalies: [
    {
      type: "Duplicate Invoice",
      description: "Two identical invoices paid",
      amount: 850,
      date: "2026-07-01",
    },
  ],
  is_mock: false,
};

// Shapes published by backend/core/risk_prevention.py for live workspaces.
const LIVE_CHURN = {
  churn_risk: [
    {
      customer_id: "cus_1",
      customer_name: "Northwind Traders",
      churn_probability: 1.0,
      risk_factors: ["Subscription recorded as canceled"],
      mrr_at_risk: 1200,
      recommended_action: "Confirm the cancellation and close the billing record.",
    },
  ],
  vip_opportunities: [],
  is_mock: false,
};
const LIVE_ALERTS = {
  ar_alerts: [
    {
      invoice_id: "inv-9",
      client_name: "Contoso Ltd",
      amount: 2500,
      due_date: "2025-11-01T00:00:00+00:00",
      likelihood_late: 1.0,
      reason: "Invoice due date has passed and it is still unpaid.",
    },
  ],
  is_mock: false,
};
const LIVE_FRAUD = {
  anomalies: [
    {
      transaction_id: "ord-42",
      type: "REFUNDED",
      amount: 450,
      timestamp: "2026-07-01T12:00:00+00:00",
      severity: "MEDIUM",
      flag_reason: "Order recorded as refunded.",
    },
  ],
  is_mock: false,
};

const INTERVENTIONS = [
  {
    id: "i1",
    type: "URGENT",
    suggested_action: "send_reminder",
    title: "Send payment reminder",
    description: "Follow up with Northwind on the overdue balance.",
    action_payload: { client: "Northwind" },
  },
  {
    id: "i2",
    type: "OPPORTUNITY",
    suggested_action: "upsell",
    title: "Upsell Pro plan",
    description: "Offer migration to the Pro plan.",
    action_payload: {},
  },
];

const okJson = (body: any) => ({ ok: true, json: async () => body });
const errJson = { ok: false, status: 500, json: async () => ({}) };

const emptyData = () => ({
  drift: { data: [], metadata: { is_mock: false } },
  pricing: { data: [], metadata: { is_mock: false } },
  waste: { data: [], metadata: { is_mock: false } },
  churn: { churn_risk: [], vip_opportunities: [], is_mock: false },
  alerts: { ar_alerts: [], is_mock: false },
  fraud: { anomalies: [], is_mock: false },
  priorities: { owner_advice: null, priorities: [] },
  interventions: [],
});

function routeFetch(
  mockFetch: jest.Mock,
  data: any = {},
  overrides: Record<string, any> = {}
) {
  const d = { ...emptyData(), ...data };
  mockFetch.mockImplementation((url: string) => {
    for (const [needle, response] of Object.entries(overrides)) {
      if (url.includes(needle)) return Promise.resolve(response);
    }
    if (url.includes("/business-health/priorities")) {
      return Promise.resolve(okJson({ success: true, data: d.priorities, timestamp: "2026-11-18T00:00:00Z" }));
    }
    if (url.includes("/forensics/price-drift")) {
      return Promise.resolve(okJson(d.drift));
    }
    if (url.includes("/forensics/pricing-advisor")) {
      return Promise.resolve(okJson(d.pricing));
    }
    if (url.includes("/forensics/waste")) {
      return Promise.resolve(okJson(d.waste));
    }
    if (url.includes("/risk/customer-protection")) {
      return Promise.resolve(okJson(d.churn));
    }
    if (url.includes("/risk/early-warning")) {
      return Promise.resolve(okJson(d.alerts));
    }
    if (url.includes("/risk/fraud")) {
      return Promise.resolve(okJson(d.fraud));
    }
    if (url.includes("/interventions/generate")) {
      return Promise.resolve(okJson({ success: true, data: d.interventions, timestamp: "2026-11-18T00:00:00Z" }));
    }
    if (url.includes("/simulate")) {
      return Promise.resolve(
        okJson({ roi: "215%", breakeven: "3 Months", prediction: "Proceed with hiring." })
      );
    }
    if (url.includes("/execute")) {
      return Promise.resolve(okJson({ message: "Intervention executed." }));
    }
    return Promise.resolve(errJson);
  });
}

const fullData = () => ({
  priorities: PRIORITIES,
  drift: DRIFT,
  pricing: PRICING,
  waste: WASTE,
  churn: CHURN,
  alerts: ALERTS,
  fraud: FRAUD,
  interventions: INTERVENTIONS,
});

describe("BusinessHealthDashboard", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
  });

  it("shows a loading state while endpoints are pending", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<BusinessHealthDashboard />);
    expect(
      screen.getByRole("heading", { name: /Business Health Control Center/i })
    ).toBeInTheDocument();
    expect(screen.getByText('"Analyzing business vitals..."')).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Refresh Diagnostics/i })).toBeInTheDocument();
  });

  it("renders priorities, forensics, risk and interventions from live data", async () => {
    routeFetch(mockFetch, fullData());
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });

    expect(
      screen.getByText('"Focus on collections to stabilize cash flow."')
    ).toBeInTheDocument();
    expect(screen.getByText("Raise prices on Pro plan")).toBeInTheDocument();

    // Interventions
    expect(screen.getByText("Active Interventions")).toBeInTheDocument();
    expect(screen.getByText("2 Actions Pending")).toBeInTheDocument();
    expect(screen.getByText("Send payment reminder")).toBeInTheDocument();
    expect(screen.getByText("URGENT")).toBeInTheDocument();
    expect(screen.getByText("OPPORTUNITY")).toBeInTheDocument();

    // Forensics (default "drift" tab)
    expect(screen.getByText("MOCK DATA")).toBeInTheDocument();
    expect(screen.getByText("Acme Cloud")).toBeInTheDocument();
    expect(screen.getByText("+12%")).toBeInTheDocument();
    expect(screen.getByText("$1200")).toBeInTheDocument();

    // Risk (default "churn" tab)
    expect(screen.getByText("Northwind")).toBeInTheDocument();
    expect(screen.getByText(/21 days silent/)).toBeInTheDocument();
    expect(screen.getByText("HIGH RISK")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("VIP")).toBeInTheDocument();
  });

  it("switches forensic and risk tabs to reveal their data", async () => {
    routeFetch(mockFetch, fullData());
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Pricing Advice/i }));
    expect(screen.getByText("Pro Plan")).toBeInTheDocument();
    expect(screen.getByText("Save Margin")).toBeInTheDocument();
    expect(screen.getByText("$49")).toBeInTheDocument();
    expect(screen.getByText("$59")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /SaaS Waste/i }));
    expect(screen.getByText("Trello")).toBeInTheDocument();
    expect(screen.getByText("$24/mo")).toBeInTheDocument();
    expect(screen.getByText("ZOMBIE SUBSCRIPTION")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Early Warning/i }));
    expect(screen.getByText("Invoice #1042 unpaid")).toBeInTheDocument();
    expect(screen.getByText("Overdue by 5 days")).toBeInTheDocument();
    expect(screen.getByText("$15,000")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Fraud Watch/i }));
    expect(screen.getByText("Duplicate Invoice")).toBeInTheDocument();
    expect(screen.getByText("$850")).toBeInTheDocument();
  });

  it("renders empty states when there is no data", async () => {
    routeFetch(mockFetch);
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Everything is running smoothly.")).toBeInTheDocument();
    });
    expect(screen.getByText("No price drift detected.")).toBeInTheDocument();
    expect(screen.getByText("No high-risk clients detected.")).toBeInTheDocument();
    expect(screen.queryByText("Active Interventions")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Early Warning/i }));
    expect(screen.getByText("No early warnings.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Fraud Watch/i }));
    expect(screen.getByText("Systems Secure")).toBeInTheDocument();
  });

  it("shows an unavailable state for a failed risk tab without hiding healthy tabs", async () => {
    routeFetch(
      mockFetch,
      { churn: LIVE_CHURN, alerts: LIVE_ALERTS, fraud: LIVE_FRAUD },
      { "/risk/early-warning": errJson }
    );
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Northwind Traders")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Early Warning/i }));
    expect(screen.getByText("Early warning data is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("No early warnings.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Fraud Watch/i }));
    expect(screen.getByText("Refund recorded")).toBeInTheDocument();
    expect(screen.getByText("$450")).toBeInTheDocument();
  });

  it("renders live recorded risk payloads with labels, amounts and dates", async () => {
    routeFetch(mockFetch, {
      churn: LIVE_CHURN,
      alerts: LIVE_ALERTS,
      fraud: LIVE_FRAUD,
    });
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Northwind Traders")).toBeInTheDocument();
    });
    expect(screen.getByText("At Risk (Recorded Churn Signals)")).toBeInTheDocument();
    expect(
      screen.getByText("Recorded cancellation • Churn signal 100%")
    ).toBeInTheDocument();
    expect(screen.getByText("Subscription recorded as canceled")).toBeInTheDocument();
    expect(screen.getByText("MRR at risk: $1,200")).toBeInTheDocument();
    expect(
      screen.getByText("Confirm the cancellation and close the billing record.")
    ).toBeInTheDocument();
    expect(screen.getByText("CANCELED")).toBeInTheDocument();
    expect(screen.queryByText("No high-risk clients detected.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Early Warning/i }));
    expect(screen.getByText("Contoso Ltd")).toBeInTheDocument();
    expect(screen.getByText("RECORDED OVERDUE")).toBeInTheDocument();
    expect(screen.getByText("Invoice inv-9 • Due Nov 1, 2025")).toBeInTheDocument();
    expect(screen.getByText("$2,500")).toBeInTheDocument();
    expect(
      screen.getByText("Invoice due date has passed and it is still unpaid.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Fraud Watch/i }));
    expect(screen.getByText("Refund recorded")).toBeInTheDocument();
    expect(screen.getByText("$450")).toBeInTheDocument();
    expect(screen.getByText("Order recorded as refunded.")).toBeInTheDocument();
    expect(screen.getByText("Transaction ord-42 • Jul 1, 2026")).toBeInTheDocument();
  });

  it("renders unavailable amounts instead of zeros or NaN for malformed live payloads", async () => {
    routeFetch(mockFetch, {
      churn: {
        churn_risk: [
          {
            customer_name: "No Amount Co",
            churn_probability: 1.0,
            risk_factors: [],
            mrr_at_risk: null,
          },
        ],
        vip_opportunities: [],
        is_mock: false,
      },
      alerts: {
        ar_alerts: [
          {
            invoice_id: "inv-bad",
            client_name: "Bad Amount Ltd",
            amount: "not-a-number",
            due_date: "not-a-date",
          },
        ],
        is_mock: false,
      },
      fraud: {
        anomalies: [
          {
            transaction_id: "tx-bad",
            type: "CHARGEBACK",
            amount: -50,
            timestamp: null,
            flag_reason: "",
          },
        ],
        is_mock: false,
      },
    });
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("No Amount Co")).toBeInTheDocument();
    });
    expect(screen.getByText("MRR at risk: unavailable")).toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Early Warning/i }));
    expect(screen.getByText("Bad Amount Ltd")).toBeInTheDocument();
    expect(screen.getByText("Invoice inv-bad • Due date unavailable")).toBeInTheDocument();
    expect(screen.getByText("Amount unavailable")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Fraud Watch/i }));
    expect(screen.getByText("Chargeback recorded")).toBeInTheDocument();
    expect(screen.getByText("Amount unavailable")).toBeInTheDocument();
    expect(screen.getByText("Transaction tx-bad • Date unavailable")).toBeInTheDocument();
  });

  it("keeps rendering other sections when one endpoint fails (allSettled)", async () => {
    routeFetch(mockFetch, fullData(), { "/forensics/price-drift": errJson });
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });
    expect(screen.getByText("Send payment reminder")).toBeInTheDocument();
    expect(screen.getByText("No price drift detected.")).toBeInTheDocument();
    expect(screen.getByText("Northwind")).toBeInTheDocument();
  });

  it("does not render the hard-coded business vitals", async () => {
    routeFetch(mockFetch, fullData());
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });

    expect(screen.queryByText("Business Vitals")).not.toBeInTheDocument();
    expect(screen.queryByText("Cash Runway")).not.toBeInTheDocument();
    expect(screen.queryByText("Margin Health")).not.toBeInTheDocument();
    expect(screen.queryByText("Staff Utilization")).not.toBeInTheDocument();
  });

  it("shows a truthful unavailable state when priorities fails (no perpetual loading)", async () => {
    routeFetch(mockFetch, fullData(), { "/business-health/priorities": errJson });
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Priorities unavailable.")).toBeInTheDocument();
    });
    expect(
      screen.getByText('"Business priorities are temporarily unavailable."')
    ).toBeInTheDocument();
    expect(screen.queryByText("Everything is running smoothly.")).not.toBeInTheDocument();
    expect(screen.queryByText('"Analyzing business vitals..."')).not.toBeInTheDocument();
    // Unrelated live sections still render.
    expect(screen.getByText("Send payment reminder")).toBeInTheDocument();
    expect(screen.getByText("Northwind")).toBeInTheDocument();
  });

  it("runs a strategic simulation and renders the report", async () => {
    routeFetch(mockFetch, fullData());
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });

    const runButton = screen.getByRole("button", { name: /Run Strategic Simulation/i });
    expect(runButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/Describe the decision/i), {
      target: { value: "Hire a full-time HVAC tech for $60k/yr" },
    });
    expect(runButton).not.toBeDisabled();
    fireEvent.click(runButton);

    await waitFor(() => {
      expect(screen.getByText("Simulation Report")).toBeInTheDocument();
    });
    expect(screen.getByText("215%")).toBeInTheDocument();
    expect(screen.getByText("3 Months")).toBeInTheDocument();
    expect(screen.getByText('"Proceed with hiring."')).toBeInTheDocument();

    const simCall = mockFetch.mock.calls.find(
      ([url, init]: any) => String(url).includes("/simulate")
    );
    expect(simCall).toBeTruthy();
    const body = JSON.parse((simCall as any[])[1].body);
    expect(body.decision_type).toBe("HIRING");
    expect(body.data.context).toBe("Hire a full-time HVAC tech for $60k/yr");
  });

  it("toasts an error when the simulation request fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/simulate")) return Promise.reject(new Error("boom"));
      if (url.includes("/interventions/generate")) {
        return Promise.resolve(okJson({ success: true, data: [] }));
      }
      return Promise.resolve(okJson({ success: true, data: PRIORITIES }));
    });
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText(/Describe the decision/i), {
      target: { value: "Hire a marketer" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Run Strategic Simulation/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Simulation failed" })
      );
    });
    expect(screen.queryByText("Simulation Report")).not.toBeInTheDocument();
  });

  it("executes an intervention and marks it complete", async () => {
    routeFetch(mockFetch, fullData());
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Send payment reminder")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /Approve & Execute/i })[0]);

    await waitFor(() => {
      expect(screen.getByText("Done")).toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Intervention Executed" })
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/business-health/interventions/i1/execute",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "send_reminder", payload: { client: "Northwind" } }),
      })
    );
  });

  it("toasts an error when intervention execution fails", async () => {
    routeFetch(mockFetch, fullData(), { "/execute": errJson });
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Send payment reminder")).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Approve & Execute/i })[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Execution Error" })
      );
    });
  });

  it("refetches all endpoints when Refresh Diagnostics is clicked", async () => {
    routeFetch(mockFetch, fullData());
    render(<BusinessHealthDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Chase overdue invoices")).toBeInTheDocument();
    });
    const callsBefore = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /Refresh Diagnostics/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});
