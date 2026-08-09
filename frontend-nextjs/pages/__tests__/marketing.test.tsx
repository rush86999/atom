import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import MarketingDashboard from "@/pages/marketing";
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
const errResponse = (status: number) => ({
  ok: false,
  status,
  json: async () => ({}),
});

const searchSubmitButton = () =>
  screen
    .getAllByRole("button")
    .find((button) => button.textContent?.trim() === "");

const SUMMARY = {
  status: "success",
  summary: "Paid search spend grew 22%",
  narrative_report: {
    content: "Your paid search spend grew 22% this month.",
  },
  high_intent_leads: [
    {
      id: "lead-1",
      name: "Acme Corp",
      summary: "Visited pricing 3x",
      score: 92,
    },
    {
      id: "lead-2",
      name: "Globex",
      summary: "Downloaded whitepaper",
      score: 87,
    },
  ],
  performance_metrics: {
    google_ads: { calls: 12 },
    meta_ads: { calls: 6 },
  },
};

describe("MarketingDashboard", () => {
  const mockFetch = jest.fn();
  let getItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    getItemSpy = jest.spyOn(Storage.prototype, "getItem");
    getItemSpy.mockReturnValue("tok-123");
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
  });

  it("shows the loading narrative placeholder while summary is pending", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<MarketingDashboard />);
    expect(
      screen.getByRole("heading", { name: /AI Marketing Blueprint/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Analyzing your marketing data for actionable insights...",
      ),
    ).toBeInTheDocument();
  });

  it("renders the summary narrative, leads, and channel metrics", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/api/marketing/dashboard/summary")
        ? Promise.resolve(okResponse(SUMMARY))
        : Promise.resolve(errResponse(404)),
    );

    render(<MarketingDashboard />);
    await waitFor(() => {
      expect(
        screen.getByText("Your paid search spend grew 22% this month."),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("92% Intent")).toBeInTheDocument();
    expect(screen.getByText("Visited pricing 3x")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();
    expect(screen.getByText("google ads")).toBeInTheDocument();
    expect(screen.getByText("12 calls")).toBeInTheDocument();
    expect(screen.getByText("meta ads")).toBeInTheDocument();
    expect(screen.getByText("6 calls")).toBeInTheDocument();
    expect(
      screen.queryByText("No high-intent leads detected yet."),
    ).not.toBeInTheDocument();
  });

  it("falls back to the default intelligence summary when the API fails", async () => {
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(500)));
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "AI Marketing Engine Active. Connect ad channels to stream real-time ROI analytics.",
        ),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("No high-intent leads detected yet."),
    ).toBeInTheDocument();
  });

  it("shows an empty state when the summary has no leads", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve(
        okResponse({
          status: "success",
          narrative_report: { content: "No campaigns yet." },
        }),
      ),
    );
    render(<MarketingDashboard />);
    await waitFor(() => {
      expect(screen.getByText("No campaigns yet.")).toBeInTheDocument();
    });
    expect(
      screen.getByText("No high-intent leads detected yet."),
    ).toBeInTheDocument();
  });

  it("runs a market research query and renders the answer", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/api/mcp/search")
        ? Promise.resolve(okResponse({ answer: "Competitor X raised Series B" }))
        : Promise.resolve(errResponse(500)),
    );

    render(<MarketingDashboard />);
    fireEvent.change(
      screen.getByPlaceholderText(
        "Ask about competitors, trends, or Local SEO...",
      ),
      { target: { value: "local seo trends" } },
    );
    fireEvent.click(searchSubmitButton()!);

    await waitFor(() => {
      expect(
        screen.getByText('"Competitor X raised Series B"'),
      ).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/mcp/search?query=local%20seo%20trends",
      expect.objectContaining({ headers: { Authorization: "Bearer tok-123" } }),
    );
  });

  it("shows an error toast when research returns a non-ok status", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/api/mcp/search")
        ? Promise.resolve(errResponse(503))
        : Promise.resolve(errResponse(500)),
    );

    render(<MarketingDashboard />);
    fireEvent.change(
      screen.getByPlaceholderText(
        "Ask about competitors, trends, or Local SEO...",
      ),
      { target: { value: "whatever" } },
    );
    fireEvent.keyDown(
      screen.getByPlaceholderText(
        "Ask about competitors, trends, or Local SEO...",
      ),
      { key: "Enter", code: "Enter" },
    );

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Research failed",
          description: "Search returned 503. Please try again.",
        }),
      );
    });
    expect(
      screen.queryByRole("heading", { name: /AI Research Summary/i }),
    ).not.toBeInTheDocument();
  });

  it("does not fire a research request for an empty query", () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve(okResponse(SUMMARY)),
    );
    render(<MarketingDashboard />);
    fireEvent.click(searchSubmitButton()!);
    expect(
      mockFetch.mock.calls.filter(([url]: [string]) =>
        String(url).includes("/api/mcp/search"),
      ),
    ).toHaveLength(0);
  });

  it("refetches the summary via the Refresh Strategy button", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/api/marketing/dashboard/summary")
        ? Promise.resolve(okResponse(SUMMARY))
        : Promise.resolve(errResponse(404)),
    );
    render(<MarketingDashboard />);
    await waitFor(() => {
      expect(
        screen.getByText("Your paid search spend grew 22% this month."),
      ).toBeInTheDocument();
    });

    const summaryCalls = mockFetch.mock.calls.filter(([url]: [string]) =>
      String(url).includes("/api/marketing/dashboard/summary"),
    ).length;
    fireEvent.click(
      screen.getByRole("button", { name: /Refresh Strategy/i }),
    );
    await waitFor(() => {
      const after = mockFetch.mock.calls.filter(([url]: [string]) =>
        String(url).includes("/api/marketing/dashboard/summary"),
      ).length;
      expect(after).toBeGreaterThan(summaryCalls);
    });
  });
});
