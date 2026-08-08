import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import IntegrationsPage from "@/pages/integrations/index";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number) {
  return { ok: false, status, json: async () => ({}) };
}

describe("IntegrationsPage", () => {
  const mockFetch = jest.fn();
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    global.fetch = mockFetch;
  });

  it("renders the hub header and initial zero-connected state", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    render(<IntegrationsPage />);

    expect(
      screen.getByRole("heading", { name: /atom integrations hub/i })
    ).toBeInTheDocument();
    expect(screen.getByText("0 of 0 Connected")).toBeInTheDocument();
    // Loading state must not render a NaN percentage (0/0 division)
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("reports connected counts and health tallies after health checks", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("box/health") || url.includes("slack/health")
          ? okResponse({})
          : errResponse(404)
      )
    );
    render(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("2 of 30 Connected")).toBeInTheDocument();
    });
    expect(screen.getByText("2")).toBeInTheDocument(); // Healthy tally
    expect(screen.getByText("28")).toBeInTheDocument(); // Errors tally
    // Connection progress
    expect(screen.getByText("7%")).toBeInTheDocument();
  });

  it("filters the grid by category", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({}))
    );
    render(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("30 of 30 Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /file storage/i }));

    expect(screen.getByText("Box")).toBeInTheDocument();
    expect(screen.getByText("Dropbox")).toBeInTheDocument();
    expect(screen.getByText("Zoho WorkDrive")).toBeInTheDocument();
    expect(screen.queryByText("Slack")).not.toBeInTheDocument();
    expect(screen.queryByText("Salesforce")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /crm/i }));
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.getByText("HubSpot")).toBeInTheDocument();
    expect(screen.queryByText("Box")).not.toBeInTheDocument();
  });

  it("keeps the grid interactive when integration cards are clicked", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({}))
    );
    render(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("30 of 30 Connected")).toBeInTheDocument();
    });

    // Every card click triggers a navigation attempt to its integration page;
    // in jsdom the assignment is a no-op, so assert the handler is wired.
    expect(() => fireEvent.click(screen.getByText("GitHub"))).not.toThrow();
    expect(() => fireEvent.click(screen.getByText("Stripe"))).not.toThrow();
    expect(screen.getByText("30 of 30 Connected")).toBeInTheDocument();
  });

  it("re-fetches health when Refresh Status is clicked", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({}))
    );
    render(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("30 of 30 Connected")).toBeInTheDocument();
    });
    const callsBefore = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /refresh status/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  it("falls back to the full list with error health when every health check fails", async () => {
    mockFetch.mockImplementation(() => Promise.reject(new Error("network down")));
    render(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("0 of 30 Connected")).toBeInTheDocument();
    });

    // The static fallback list is still rendered so users can navigate
    expect(screen.getByText("Mailchimp")).toBeInTheDocument();
    expect(screen.getByText("Tableau")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument(); // Errors tally
  });

  it("labels cards as Connected/Manage when healthy and Connect when not", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({}))
    );
    const { unmount } = render(<IntegrationsPage />);

    await waitFor(() => {
      expect(screen.getByText("30 of 30 Connected")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Connected").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /manage/i }).length).toBe(30);
    unmount();

    mockFetch.mockImplementation(() => Promise.reject(new Error("down")));
    render(<IntegrationsPage />);
    await waitFor(() => {
      expect(screen.getByText("0 of 30 Connected")).toBeInTheDocument();
    });
    expect(screen.getAllByRole("button", { name: /connect/i }).length).toBe(30);
  });
});
