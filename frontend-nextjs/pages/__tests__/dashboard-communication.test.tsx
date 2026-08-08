import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import UnifiedCommunicationDashboard from "@/pages/dashboard/communication/index";

jest.mock(
  "@/components/UnifiedServicesManager",
  () => {
    const MockManager = ({ onImplementationChange }: any) => (
      <div data-testid="services-manager">
        <button
          onClick={() => onImplementationChange("Slack", "real")}
        >
          switch-slack-real
        </button>
      </div>
    );
    return { UnifiedServicesManager: MockManager };
  }
);

function okJson(data: unknown) {
  return { ok: true, json: async () => data };
}

const SERVICES = {
  timestamp: "2026-08-01T12:00:00Z",
  environment: "production",
  services: {
    Slack: { current: "real", health: { status: "healthy" } },
    MicrosoftTeams: { current: "mock", health: { status: "error" } },
  },
};

const STATISTICS = {
  total_metrics: {
    total_workspaces: 3,
    total_channels: 14,
    total_messages: 2500,
    total_api_calls: 9100,
  },
  services: {
    slack: {
      implementation: "real",
      metrics: {
        workspaces_count: 1,
        channels_count: 8,
        messages_count: 1500,
        api_calls_today: 4000,
        average_response_time: 120.4,
        uptime_percentage: 99.5,
      },
    },
    teams: {
      implementation: "mock",
      metrics: {
        workspaces_count: 2,
        channels_count: 6,
        messages_count: 1000,
        api_calls_today: 5100,
        average_response_time: 210.2,
        uptime_percentage: 96.2,
      },
    },
  },
};

describe("UnifiedCommunicationDashboard", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/implementations")) return Promise.resolve(okJson(SERVICES));
      if (url.includes("/statistics")) return Promise.resolve(okJson(STATISTICS));
      return Promise.resolve(okJson({}));
    });
  });

  it("renders the services tab by default", async () => {
    render(<UnifiedCommunicationDashboard />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /unified communication services/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId("services-manager")).toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/implementations")
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/statistics")
    );
  });

  it("shows the overview tab with service stats and health", async () => {
    render(<UnifiedCommunicationDashboard />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /unified communication services/i })
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /overview/i }));

    await waitFor(() => {
      // Healthy Services count
      expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    });

    expect(screen.getByText("Total Services")).toBeInTheDocument();
    expect(screen.getByText("Healthy Services")).toBeInTheDocument();
    expect(screen.getByText("Real Implementations")).toBeInTheDocument();
    expect(screen.getByText("Mock Implementations")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("MicrosoftTeams")).toBeInTheDocument();
    expect(screen.getByText("production")).toBeInTheDocument();
    expect(screen.getByText("Auto-refresh")).toBeInTheDocument();
    expect(screen.getByText("30 seconds")).toBeInTheDocument();
  });

  it("shows the statistics tab with aggregated and per-service metrics", async () => {
    render(<UnifiedCommunicationDashboard />);

    fireEvent.click(screen.getByRole("button", { name: /statistics/i }));

    await waitFor(() => {
      expect(screen.getByText("Total Metrics")).toBeInTheDocument();
    });

    expect(screen.getByText("Total Workspaces")).toBeInTheDocument();
    expect(screen.getByText("Total Channels")).toBeInTheDocument();
    expect(screen.getByText("Total Messages")).toBeInTheDocument();
    expect(screen.getByText("2,500")).toBeInTheDocument();
    expect(screen.getByText("9,100")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("Microsoft Teams")).toBeInTheDocument();
    expect(screen.getByText("120ms")).toBeInTheDocument();
    expect(screen.getByText("99.5%")).toBeInTheDocument();
    // Uptime >= 95 but < 99 → yellow (still rendered as text)
    expect(screen.getByText("96.2%")).toBeInTheDocument();
  });

  it("shows the no-data state with a working refresh button when statistics are missing", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/statistics")) return Promise.resolve(okJson(null));
      return Promise.resolve(okJson(SERVICES));
    });

    render(<UnifiedCommunicationDashboard />);

    fireEvent.click(screen.getByRole("button", { name: /statistics/i }));

    await waitFor(() => {
      expect(screen.getByText("No statistics data available")).toBeInTheDocument();
    });

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/statistics")) return Promise.resolve(okJson(STATISTICS));
      return Promise.resolve(okJson(SERVICES));
    });
    fireEvent.click(screen.getByRole("button", { name: /refresh statistics/i }));

    await waitFor(() => {
      expect(screen.getByText("Total Metrics")).toBeInTheDocument();
    });
  });

  it("shows the settings tab", async () => {
    render(<UnifiedCommunicationDashboard />);

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));

    await waitFor(() => {
      expect(screen.getByText("Dashboard Settings")).toBeInTheDocument();
    });
    expect(screen.getByText("API Configuration")).toBeInTheDocument();
    expect(screen.getByDisplayValue("http://localhost:8000")).toBeInTheDocument();
  });

  it("shows the error banner when the fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));

    render(<UnifiedCommunicationDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/connection refused/i)).toBeInTheDocument();
    });
    expect(screen.getByText("Error:")).toBeInTheDocument();
  });

  it("refetches dashboard data after an implementation switch", async () => {
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => {
      expect(screen.getByTestId("services-manager")).toBeInTheDocument();
    });
    const callsAfterMount = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /switch-slack-real/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    }, { timeout: 4000 });
  });
});
