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
  is_mock: true,
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
  is_mock: false,
};
const WASTE = {
  data: [{ service_name: "Trello", mrr: 24 }],
  is_mock: false,
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

const INTERVENTIONS = {
  interventions: [
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
  ],
};

const okJson = (body: any) => ({ ok: true, json: async () => body });
const errJson = { ok: false, status: 500, json: async () => ({}) };

const emptyData = () => ({
  drift: { data: [], is_mock: false },
  pricing: { data: [], is_mock: false },
  waste: { data: [], is_mock: false },
  churn: { churn_risk: [], vip_opportunities: [], is_mock: false },
  alerts: { ar_alerts: [], is_mock: false },
  fraud: { anomalies: [], is_mock: false },
  priorities: { owner_advice: null, priorities: [] },
  interventions: { interventions: [] },
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
      return Promise.resolve(okJson(d.priorities));
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
      return Promise.resolve(okJson(d.interventions));
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
        return Promise.resolve(okJson({ interventions: [] }));
      }
      return Promise.resolve(okJson(PRIORITIES));
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
