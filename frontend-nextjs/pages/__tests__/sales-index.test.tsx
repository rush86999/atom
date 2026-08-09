import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SalesIntelligencePage from "@/pages/sales/index";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

let mockWsState: {
  lastMessage: any;
  subscribe: jest.Mock;
  isConnected: boolean;
};

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: () => mockWsState,
}));

const mockToast = jest.fn();

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});

const LEADS = [
  {
    id: "l1",
    email: "ada@example.com",
    first_name: "Ada",
    last_name: "Lovelace",
    company: "Acme Corp",
    source: "referral",
    status: "Qualified",
    ai_score: 92,
    ai_qualification_summary: "Strong intent, budget confirmed",
    is_spam: false,
    created_at: "2026-08-01",
  },
  {
    id: "l2",
    email: "bulk@spam.net",
    first_name: "Bulk",
    last_name: "Sender",
    company: "None Inc",
    source: "web",
    status: "New",
    ai_score: 5,
    ai_qualification_summary: "Junk",
    is_spam: true,
    created_at: "2026-08-01",
  },
];

const DEALS = [
  {
    id: "d1",
    name: "Acme Expansion",
    value: 25000,
    stage: "proposal",
    health_score: 88,
    risk_level: "low",
    expected_close_date: "2026-10-15",
    last_engagement_at: "2026-08-01",
    currency: "USD",
  },
  {
    id: "d2",
    name: "Globex Renewal",
    value: 60000,
    stage: "negotiation",
    health_score: 35,
    risk_level: "high",
    expected_close_date: "2026-09-01",
    last_engagement_at: "2026-08-01",
    currency: "USD",
  },
];

const MEETINGS = [
  {
    id: "m1",
    title: "Acme discovery call",
    date: "2026-08-05",
    summary: "Customer wants faster onboarding.",
    objections: ["Price too high"],
    action_items: ["Send revised proposal"],
    deal_name: "Acme Expansion",
  },
  {
    id: "m2",
    title: "Globex QBR",
    date: "2026-08-06",
    summary: "Renewal discussion",
    objections: [],
    action_items: ["Schedule follow-up"],
    deal_name: "Globex Renewal",
  },
];

const mockFetch = jest.fn();

describe("Sales Intelligence page (pages/sales/index.tsx)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    mockWsState = { lastMessage: null, subscribe: jest.fn(), isConnected: false };
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/sales/leads?workspace_id=temp_ws") {
        return Promise.resolve(okResponse(LEADS));
      }
      if (url === "/api/sales/deals?workspace_id=temp_ws") {
        return Promise.resolve(okResponse(DEALS));
      }
      if (url === "/api/sales/calls?workspace_id=temp_ws") {
        return Promise.resolve(okResponse(MEETINGS));
      }
      return Promise.resolve(okResponse([]));
    });
    global.fetch = mockFetch as any;
  });

  it("renders the header, action buttons, all tabs and subscribes to the workspace channel", () => {
    render(<SalesIntelligencePage />);

    expect(screen.getByText("Sales Intelligence")).toBeInTheDocument();
    expect(
      screen.getByText(/AI-powered lead scoring, deal health tracking, and meeting automation/)
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /sync crm/i }).length
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByRole("button", { name: /forecast report/i }).length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Lead Intake")).toBeInTheDocument();
    expect(screen.getByText("Pipeline Health")).toBeInTheDocument();
    expect(screen.getByText("Meeting Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Executive Overview")).toBeInTheDocument();

    expect(mockWsState.subscribe).toHaveBeenCalledWith("workspace:sales-test-ws");
  });

  it("loads and renders AI-scored leads (default tab)", async () => {
    render(<SalesIntelligencePage />);

    expect(await screen.findByText("AI-Scored Leads")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText(/Strong intent, budget confirmed/)).toBeInTheDocument();
    expect(screen.getByText("Qualified")).toBeInTheDocument();
    expect(screen.getByText("Spam")).toBeInTheDocument();

    expect(mockFetch).toHaveBeenCalledWith("/api/sales/leads?workspace_id=temp_ws");
  });

  it("shows an empty state when no leads match", async () => {
    mockFetch.mockImplementation((url: string) => Promise.resolve(okResponse([])));

    render(<SalesIntelligencePage />);

    expect(
      await screen.findByText("No leads found matching your criteria.")
    ).toBeInTheDocument();
  });

  it("filters leads by the search box", async () => {
    render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    fireEvent.change(screen.getByPlaceholderText("Search leads or companies..."), {
      target: { value: "acme" },
    });

    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.queryByText("Bulk Sender")).not.toBeInTheDocument();
  });

  it("loads pipeline health deals when the tab is opened", async () => {
    render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    fireEvent.click(screen.getByText("Pipeline Health"));

    expect(await screen.findByText("Acme Expansion")).toBeInTheDocument();
    expect(screen.getByText("Pipeline Intelligence")).toBeInTheDocument();
    expect(screen.getByText("Pipeline Value")).toBeInTheDocument();
    expect(screen.getByText("$385,000")).toBeInTheDocument();
    expect(screen.getByText("$25,000.00")).toBeInTheDocument();
    expect(screen.getByText("88/100")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Globex Renewal")).toBeInTheDocument();
    expect(screen.getByText("High Risk")).toBeInTheDocument();

    expect(mockFetch).toHaveBeenCalledWith("/api/sales/deals?workspace_id=temp_ws");
  });

  it("loads meeting intelligence when the tab is opened", async () => {
    render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    fireEvent.click(screen.getByText("Meeting Intelligence"));

    expect((await screen.findAllByText("Acme discovery call")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Recent Calls")).toBeInTheDocument();
    expect(screen.getAllByText("Acme Expansion").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("AI Summary")).toBeInTheDocument();
    expect(screen.getByText("Customer wants faster onboarding.")).toBeInTheDocument();
    expect(screen.getByText("Objections Found")).toBeInTheDocument();
    expect(screen.getByText("Price too high")).toBeInTheDocument();
    expect(screen.getByText("Send revised proposal")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sync to crm/i })).toBeInTheDocument();

    expect(mockFetch).toHaveBeenCalledWith("/api/sales/calls?workspace_id=temp_ws");
  });

  it("renders the executive overview cards", async () => {
    render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    fireEvent.click(screen.getByText("Executive Overview"));

    expect(screen.getByText("Winning More with AI")).toBeInTheDocument();
    expect(screen.getByText(/increased by 14%/)).toBeInTheDocument();
    expect(screen.getByText("Meeting Efficiency")).toBeInTheDocument();
    expect(screen.getByText(/saved 4.5 hours of admin work/)).toBeInTheDocument();
  });

  it("shows a success toast when a high-scored lead arrives over the websocket", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: "new_lead",
        data: { first_name: "Bob", last_name: "Lee", company: "Bolt", ai_score: 85 },
      },
    };
    rerender(<SalesIntelligencePage />);

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "New Lead Ingested", variant: "success" })
      )
    );
    expect(mockToast.mock.calls[0][0].description).toContain("Bob Lee from Bolt");
    expect(mockToast.mock.calls[0][0].description).toContain("85");
  });

  it("uses a default toast variant for a low-scored lead", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: "new_lead",
        data: { first_name: "Sara", last_name: "Kim", company: "Warm Co", ai_score: 40 },
      },
    };
    rerender(<SalesIntelligencePage />);

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "New Lead Ingested", variant: "default" })
      )
    );
  });

  it("shows a warning toast for a deal with a low health score", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: "deal_update",
        data: { name: "Acme Expansion", health_score: 30, risk_level: "high" },
      },
    };
    rerender(<SalesIntelligencePage />);

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Deal Health Updated",
          description: "Acme Expansion: Health Score 30 (high risk)",
          variant: "warning",
        })
      )
    );
  });

  it("uses a default toast for a healthy deal update", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    mockWsState = {
      ...mockWsState,
      lastMessage: {
        type: "deal_update",
        data: { name: "Globex", health_score: 90, risk_level: "low" },
      },
    };
    rerender(<SalesIntelligencePage />);

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Deal Health Updated",
          description: "Globex: Health Score 90 (low risk)",
          variant: "default",
        })
      )
    );
  });

  it("does not crash or toast when a websocket message has no data payload (BUG-095)", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    mockWsState = { ...mockWsState, lastMessage: { type: "new_lead" } };
    rerender(<SalesIntelligencePage />);

    await waitFor(() => expect(mockWsState.subscribe).toHaveBeenCalled());
    expect(mockToast).not.toHaveBeenCalled();
  });

  it("ignores unknown websocket message types", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    await screen.findByText("AI-Scored Leads");

    mockWsState = {
      ...mockWsState,
      lastMessage: { type: "random_event", data: { anything: true } },
    };
    rerender(<SalesIntelligencePage />);

    expect(mockToast).not.toHaveBeenCalled();
  });
});
