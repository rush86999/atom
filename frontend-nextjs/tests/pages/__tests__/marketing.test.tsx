import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import MarketingDashboard from "@/pages/marketing";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const SUMMARY = {
  status: "success",
  narrative_report: {
    content: "Your paid search spend grew 22% this month.",
  },
  high_intent_leads: [
    { id: "lead-1", name: "Acme Corp", summary: "Visited pricing 3x", score: 92 },
    { id: "lead-2", name: "Globex", summary: "Downloaded whitepaper", score: 87 },
  ],
  performance_metrics: {
    google_ads: { calls: 12 },
    meta_ads: { calls: 6 },
  },
};

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number) {
  return { ok: false, status, json: async () => ({}) };
}

describe("MarketingDashboard", () => {
  const mockFetch = jest.fn();
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    global.fetch = mockFetch;
    jest.spyOn(Storage.prototype, "getItem").mockReturnValue("tok-123");
  });

  it("renders the blueprint header and loading narrative placeholder", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<MarketingDashboard />);

    expect(
      screen.getByRole("heading", { name: /AI Marketing Blueprint/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Analyzing your marketing data for actionable insights\.\.\./)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh strategy/i })).toBeDisabled();
  });

  it("renders the narrative, priority leads, and channel performance from the summary", async () => {
    mockFetch.mockResolvedValue(okResponse(SUMMARY));
    render(<MarketingDashboard />);

    expect(
      await screen.findByText("Your paid search spend grew 22% this month.")
    ).toBeInTheDocument();

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Visited pricing 3x")).toBeInTheDocument();
    expect(screen.getByText("92% Intent")).toBeInTheDocument();

    expect(screen.getByText("google ads")).toBeInTheDocument();
    expect(screen.getByText("12 calls")).toBeInTheDocument();
    expect(screen.getByText("6 calls")).toBeInTheDocument();

    expect(screen.getByText("4.8")).toBeInTheDocument();
    expect(screen.getByText("Positive (92%)")).toBeInTheDocument();
  });

  it("falls back to the local intelligence summary when the API is unavailable", async () => {
    mockFetch.mockResolvedValue(errResponse(500));
    render(<MarketingDashboard />);

    // The fallback message must actually surface in the narrative report
    expect(
      await screen.findByText(
        "AI Marketing Engine Active. Connect ad channels to stream real-time ROI analytics."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("No high-intent leads detected yet.")).toBeInTheDocument();
  });

  it("shows the empty state when there are no high-intent leads", async () => {
    mockFetch.mockResolvedValue(okResponse({ ...SUMMARY, high_intent_leads: [] }));
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(screen.getByText("No high-intent leads detected yet.")).toBeInTheDocument();
    });
  });

  it("runs market research and displays the answer", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/mcp/search")) {
        return Promise.resolve(okResponse({ answer: "Competitors are shifting to AI agents." }));
      }
      return Promise.resolve(okResponse(SUMMARY));
    });
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Ask about competitors/), {
      target: { value: "AI agent trends" },
    });
    fireEvent.click(screen.getByRole("button", { name: "" }));

    expect(
      await screen.findByText('"Competitors are shifting to AI agents."')
    ).toBeInTheDocument();

    const searchCall = mockFetch.mock.calls.find((c) =>
      (c[0] as string).includes("/api/mcp/search")
    );
    expect((searchCall as any[])[0]).toContain(
      "/api/mcp/search?query=AI%20agent%20trends"
    );
    expect((searchCall as any[])[1]?.headers?.Authorization).toBe("Bearer tok-123");
  });

  it("shows an error toast when research returns a non-ok status", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/mcp/search")) return Promise.resolve(errResponse(500));
      return Promise.resolve(okResponse(SUMMARY));
    });
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Ask about competitors/), {
      target: { value: "trends" },
    });
    fireEvent.click(screen.getByRole("button", { name: "" }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Research failed",
          description: "Search returned 500. Please try again.",
        })
      );
    });
    expect(screen.queryByText(/AI Research Summary/)).not.toBeInTheDocument();
  });

  it("shows a generic error toast when research throws", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/mcp/search")) return Promise.reject(new Error("offline"));
      return Promise.resolve(okResponse(SUMMARY));
    });
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/Ask about competitors/), {
      target: { value: "trends" },
    });
    fireEvent.click(screen.getByRole("button", { name: "" }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Research failed",
          description: "Could not perform market research.",
        })
      );
    });
  });

  it("triggers research on Enter in the query input", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/mcp/search")) {
        return Promise.resolve(okResponse({ answer: "Enter works." }));
      }
      return Promise.resolve(okResponse(SUMMARY));
    });
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Ask about competitors/);
    fireEvent.change(input, { target: { value: "local seo" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByText('"Enter works."')).toBeInTheDocument();
  });

  it("re-fetches the summary when Refresh Strategy is clicked", async () => {
    mockFetch.mockResolvedValue(okResponse(SUMMARY));
    render(<MarketingDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });
    const before = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /refresh strategy/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBe(before + 1);
    });
  });
});
