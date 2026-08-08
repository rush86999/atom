import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SalesIntelligencePage from "@/pages/sales/index";
import { useWebSocket } from "@/hooks/useWebSocket";

const mockToast = jest.fn();
const mockSubscribe = jest.fn();

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

jest.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: jest.fn(() => ({
    isConnected: false,
    lastMessage: null,
    subscribe: mockSubscribe,
    disconnect: jest.fn(),
  })),
}));

const LEADS = [
  {
    id: "l1",
    email: "ada@analytical.com",
    first_name: "Ada",
    last_name: "Lovelace",
    company: "Analytical Engines",
    source: "website",
    status: "new",
    ai_score: 85,
    ai_qualification_summary: "High intent, budget confirmed",
    is_spam: false,
    created_at: "2026-07-01",
  },
  {
    id: "l2",
    email: "bob@builders.io",
    first_name: "Bob",
    last_name: "Builder",
    company: "Can We Fix It Co",
    source: "referral",
    status: "contacted",
    ai_score: 40,
    ai_qualification_summary: "Early stage exploration",
    is_spam: true,
    created_at: "2026-07-02",
  },
];

const DEALS = [
  {
    id: "d1",
    name: "Acme Renewal",
    value: 120000,
    stage: "Negotiation",
    health_score: 35,
    risk_level: "high",
    expected_close_date: "2026-09-30",
    last_engagement_at: "2026-08-01",
    currency: "USD",
  },
];

const MEETINGS = [
  {
    id: "m1",
    title: "Q3 Pipeline Review",
    date: "2026-08-01",
    summary: "The client is happy with progress so far.",
    objections: ["Pricing"],
    action_items: ["Send updated proposal"],
    deal_name: "Acme Renewal",
  },
];

const okJson = (body: any) => ({ ok: true, json: async () => body });

const routeFetch = (mockFetch: jest.Mock) => {
  mockFetch.mockImplementation((url: string) => {
    if (url.includes("/api/sales/leads")) return Promise.resolve(okJson(LEADS));
    if (url.includes("/api/sales/deals")) return Promise.resolve(okJson(DEALS));
    if (url.includes("/api/sales/calls")) return Promise.resolve(okJson(MEETINGS));
    return Promise.resolve(okJson([]));
  });
};

describe("SalesIntelligencePage", () => {
  const mockFetch = jest.fn();
  const wsMock = useWebSocket as jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    routeFetch(mockFetch);
    wsMock.mockReturnValue({
      isConnected: false,
      lastMessage: null,
      subscribe: mockSubscribe,
      disconnect: jest.fn(),
    });
  });

  it("subscribes to the workspace channel on mount", () => {
    render(<SalesIntelligencePage />);
    expect(mockSubscribe).toHaveBeenCalledWith("workspace:sales-test-ws");
  });

  it("renders the header and the default Lead Intake tab with leads", async () => {
    render(<SalesIntelligencePage />);

    expect(
      screen.getByRole("heading", { name: /Sales Intelligence/i })
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("AI-Scored Leads")).toBeInTheDocument();
    });
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@analytical.com")).toBeInTheDocument();
    expect(screen.getByText("Analytical Engines")).toBeInTheDocument();
    expect(screen.getByText("High intent, budget confirmed")).toBeInTheDocument();
    expect(screen.getByText("Spam")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add Lead/i })).toBeInTheDocument();
  });

  it("filters leads by search term", async () => {
    render(<SalesIntelligencePage />);
    await waitFor(() => {
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Search leads or companies..."), {
      target: { value: "bob" },
    });
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument();
    expect(screen.getByText("Bob Builder")).toBeInTheDocument();
  });

  it("shows an empty state when there are no leads", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/sales/leads")) return Promise.resolve(okJson([]));
      return Promise.resolve(okJson([]));
    });
    render(<SalesIntelligencePage />);
    await waitFor(() => {
      expect(
        screen.getByText("No leads found matching your criteria.")
      ).toBeInTheDocument();
    });
  });

  it("switches to the Pipeline Health tab and renders deal intelligence", async () => {
    render(<SalesIntelligencePage />);
    fireEvent.click(screen.getByRole("button", { name: /Pipeline Health/i }));

    await waitFor(() => {
      expect(screen.getByText("Pipeline Intelligence")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("Acme Renewal")).toBeInTheDocument();
    });
    expect(screen.getByText(/\$120,000/)).toBeInTheDocument();
    expect(screen.getByText("Negotiation")).toBeInTheDocument();
    expect(screen.getByText("High Risk")).toBeInTheDocument();
    expect(screen.getByText("35/100")).toBeInTheDocument();
  });

  it("switches to the Meeting Intelligence tab and renders call summaries", async () => {
    render(<SalesIntelligencePage />);
    fireEvent.click(screen.getByRole("button", { name: /Meeting Intelligence/i }));

    await waitFor(() => {
      expect(screen.getByText("Recent Calls")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getAllByText("Q3 Pipeline Review").length).toBeGreaterThanOrEqual(1);
    });
    expect(
      screen.getByText("The client is happy with progress so far.")
    ).toBeInTheDocument();
    expect(screen.getByText("Objections Found")).toBeInTheDocument();
    expect(screen.getByText("Pricing")).toBeInTheDocument();
    expect(screen.getByText("Send updated proposal")).toBeInTheDocument();
  });

  it("switches to the Executive Overview tab with static highlight cards", async () => {
    render(<SalesIntelligencePage />);
    fireEvent.click(screen.getByRole("button", { name: /Executive Overview/i }));

    expect(screen.getByText("Winning More with AI")).toBeInTheDocument();
    expect(screen.getByText("Meeting Efficiency")).toBeInTheDocument();
    expect(screen.getByText(/increased by 14%/)).toBeInTheDocument();
    expect(screen.getByText(/saved 4.5 hours/)).toBeInTheDocument();
  });

  it("toasts a new-lead notification from the websocket", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    wsMock.mockReturnValue({
      lastMessage: {
        type: "new_lead",
        data: {
          first_name: "Ada",
          last_name: "Lovelace",
          company: "Analytical Engines",
          ai_score: 85,
        },
      },
      subscribe: mockSubscribe,
    });
    rerender(<SalesIntelligencePage />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "New Lead Ingested",
          description:
            "Ada Lovelace from Analytical Engines (Score: 85)",
          variant: "success",
        })
      );
    });
  });

  it("toasts a deal-health warning from the websocket", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    wsMock.mockReturnValue({
      lastMessage: {
        type: "deal_update",
        data: { name: "Acme Renewal", health_score: 35, risk_level: "high" },
      },
      subscribe: mockSubscribe,
    });
    rerender(<SalesIntelligencePage />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Deal Health Updated",
          description: "Acme Renewal: Health Score 35 (high risk)",
          variant: "warning",
        })
      );
    });
  });

  it("ignores websocket messages with a null data payload", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    wsMock.mockReturnValue({
      lastMessage: { type: "new_lead", data: null },
      subscribe: mockSubscribe,
    });
    rerender(<SalesIntelligencePage />);

    await waitFor(() => {
      expect(screen.getByText("AI-Scored Leads")).toBeInTheDocument();
    });
    expect(mockToast).not.toHaveBeenCalled();
  });

  it("falls back to safe defaults when websocket data fields are missing", async () => {
    const { rerender } = render(<SalesIntelligencePage />);
    wsMock.mockReturnValue({
      lastMessage: { type: "deal_update", data: {} },
      subscribe: mockSubscribe,
    });
    rerender(<SalesIntelligencePage />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          description: "Unknown: Health Score N/A (unknown risk)",
          variant: "default",
        })
      );
    });
  });
});
