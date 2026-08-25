/**
 * UnifiedCommunicationDashboard tests (pages/dashboard/communication/index.tsx, was 0%)
 *
 * Covers: data fetching on mount (implementations + statistics), the four
 * tabs (overview/services/statistics/settings), stat cards, error display,
 * implementation-change callback, and statistics empty state.
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import UnifiedCommunicationDashboard from "@/pages/dashboard/communication/index";

const mockOnImplementationChange = jest.fn();
const mockOnServiceHealthChange = jest.fn();

jest.mock("@/components/UnifiedServicesManager", () => ({
  UnifiedServicesManager: ({ onImplementationChange, onServiceHealthChange }: any) => (
    <div data-testid="services-manager">
      <button onClick={() => onImplementationChange("Slack", "real")}>Switch Slack</button>
      <button onClick={() => onServiceHealthChange({ service: "Teams", health: { status: "healthy" } })}>
        Health Update
      </button>
    </div>
  ),
}));

const SERVICES = {
  environment: "test",
  timestamp: "2026-08-01T10:00:00Z",
  services: {
    Slack: { current: "real", health: { status: "healthy" } },
    Teams: { current: "mock", health: { status: "error" } },
  },
};

const STATS = {
  total_metrics: { total_workspaces: 5, total_channels: 12, total_messages: 340, total_api_calls: 99 },
  services: {
    slack: {
      implementation: "real",
      metrics: {
        workspaces_count: 3,
        channels_count: 8,
        messages_count: 200,
        api_calls_today: 50,
        average_response_time: 120.4,
        uptime_percentage: 99.5,
      },
    },
    teams: {
      implementation: "mock",
      metrics: {
        workspaces_count: 2,
        channels_count: 4,
        messages_count: 140,
        api_calls_today: 49,
        average_response_time: 300.2,
        uptime_percentage: 92.0,
      },
    },
  },
};

const okJson = (body: any) => ({ ok: true, json: async () => body });

describe("UnifiedCommunicationDashboard", () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/implementations")) return okJson(SERVICES);
      if (url.endsWith("/statistics")) return okJson(STATS);
      return okJson({});
    });
    global.fetch = mockFetch;
  });

  test("renders header and services manager by default", async () => {
    render(<UnifiedCommunicationDashboard />);
    expect(screen.getByText("Unified Communication Services")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining("/implementations"));
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining("/statistics"));
  });

  test("shows error banner when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("backend down"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => expect(screen.getByText(/backend down/)).toBeInTheDocument());
    expect(screen.getByText(/Error:/)).toBeInTheDocument();
    consoleSpy.mockRestore();
  });

  test("overview tab renders counts and service statuses", async () => {
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Overview/ }));
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("test")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("Teams")).toBeInTheDocument();
    expect(screen.getByText("healthy")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  test("statistics tab renders total and per-service metrics", async () => {
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Statistics/ }));
    await waitFor(() => expect(screen.getByText("Total Metrics")).toBeInTheDocument());
    expect(screen.getByText("340")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("99.5%")).toBeInTheDocument();
    expect(screen.getByText("92.0%")).toBeInTheDocument();
    expect(screen.getByText("120ms")).toBeInTheDocument();
  });

  test("statistics empty state offers refresh", async () => {
    mockFetch.mockImplementation(async (url: string) => {
      if (url.endsWith("/implementations")) return okJson(SERVICES);
      return { ok: false };
    });
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Statistics/ }));
    expect(screen.getByText("No statistics data available")).toBeInTheDocument();

    mockFetch.mockImplementation(async (url: string) => {
      if (url.endsWith("/implementations")) return okJson(SERVICES);
      if (url.endsWith("/statistics")) return okJson(STATS);
      return okJson({});
    });
    fireEvent.click(screen.getByRole("button", { name: /Refresh Statistics/ }));
    await waitFor(() => expect(screen.getByText("Total Metrics")).toBeInTheDocument());
  });

  test("settings tab renders configuration panels", async () => {
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Settings/ }));
    expect(screen.getByText("Dashboard Settings")).toBeInTheDocument();
    expect(screen.getByText("API Configuration")).toBeInTheDocument();
    expect(
      document.querySelector('input[placeholder="http://localhost:8000"]')
    ).toBeInTheDocument();
    const backendInput = document.querySelector('input[placeholder="http://localhost:8000"]');
    expect(backendInput).toBeInTheDocument();
  });

  test("implementation change callback triggers delayed refresh", async () => {
    jest.useFakeTimers();
    try {
      render(<UnifiedCommunicationDashboard />);
      await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());
      const callsBefore = mockFetch.mock.calls.length;

      fireEvent.click(screen.getByRole("button", { name: /Switch Slack/ }));
      expect(mockOnImplementationChange).not.toHaveBeenCalled();

      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
    } finally {
      jest.useRealTimers();
    }
  });

  test("service health change callback is wired", async () => {
    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    render(<UnifiedCommunicationDashboard />);
    await waitFor(() => expect(screen.getByTestId("services-manager")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Health Update/ }));
    expect(logSpy).toHaveBeenCalledWith(
      "Health update for Teams:",
      expect.objectContaining({ health: { status: "healthy" } })
    );
    logSpy.mockRestore();
  });

  test("overview shows zero counts before data loads", () => {
    render(<UnifiedCommunicationDashboard />);
    fireEvent.click(screen.getByRole("button", { name: /Overview/ }));
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });
});
