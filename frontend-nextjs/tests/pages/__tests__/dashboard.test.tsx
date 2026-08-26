/**
 * pages/dashboard.tsx tests
 *
 * Covers the main ATOM dashboard page:
 * - Integration health grid (mixed connected/disconnected)
 * - Financial + sales intelligence cards
 * - Quick action / navigation flows
 * - JSON parse fallbacks in safeParseJson
 *
 * Source: pages/dashboard.tsx
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import DashboardPage from "@/pages/dashboard";

const mockPush = jest.fn();
jest.mock("next/router", () => ({
  useRouter: () => ({ push: mockPush, query: {}, pathname: "/" }),
}));

const mockToast = jest.fn();
jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
}));

const okJson = (body: any) => ({
  ok: true,
  headers: { get: () => "application/json" },
  json: async () => body,
});

const failing = () => ({ ok: false, headers: { get: () => null } });

const HEALTHY = new Set(["box", "slack", "github"]);

const FINANCIALS = {
  total_cash: 125000,
  runway_months: 18,
  accounts_payable: 5000,
  accounts_receivable: 8000,
};

const SALES = {
  pipeline_value: 400000,
  weighted_forecast: 250000,
  active_deals_count: 12,
  high_risk_deals_count: 2,
  conversion_rate: 34,
};

describe("pages/dashboard", () => {
  const mockFetch = jest.fn();
  let errorSpy: jest.SpyInstance;
  let warnSpy: jest.SpyInstance;

  const setupDefault = () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/health")) {
        const id = url.split("/integrations/")[1]?.split("/")[0];
        return Promise.resolve(HEALTHY.has(id) ? okJson({ status: "healthy" }) : failing());
      }
      if (url.includes("/accounting/dashboard/summary")) {
        return Promise.resolve(okJson(FINANCIALS));
      }
      if (url.includes("/sales/dashboard/summary")) {
        return Promise.resolve(okJson(SALES));
      }
      return Promise.resolve(failing());
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch as any;
    setupDefault();
    errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  });

  test("renders intelligence cards from financial and sales summaries", async () => {
    render(<DashboardPage />);

    expect(await screen.findByText("$125,000")).toBeInTheDocument();
    expect(screen.getByText("18 months")).toBeInTheDocument();
    expect(screen.getByText("$400,000")).toBeInTheDocument();
    expect(screen.getByText("$250,000")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("2 at risk")).toBeInTheDocument();
    expect(screen.getByText("34%")).toBeInTheDocument();
    expect(screen.getByText("$5,000")).toBeInTheDocument();
    expect(screen.getByText("$8,000")).toBeInTheDocument();
  });

  test("renders the integration grid with mixed health", async () => {
    render(<DashboardPage />);

    expect(await screen.findByText("Box")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
    expect(screen.getByText("Asana")).toBeInTheDocument();
    // 3 of 13 connected
    expect(screen.getAllByText("Connected").length).toBe(3);
    expect(screen.getAllByText("Disconnected").length).toBe(10);
    expect(screen.getAllByText("healthy").length).toBe(3);
    expect(screen.getAllByText("error").length).toBe(10);
  });

  test("navigates when an integration card is clicked", async () => {
    render(<DashboardPage />);

    const boxCard = (await screen.findByText("Box")).closest(
      ".cursor-pointer",
    ) as HTMLElement;
    fireEvent.click(boxCard);
    expect(mockPush).toHaveBeenCalledWith("/integrations/box");
  });

  test("quick action buttons navigate", async () => {
    render(<DashboardPage />);
    await screen.findByText("Box");

    fireEvent.click(screen.getByRole("button", { name: /process invoice/i }));
    expect(mockPush).toHaveBeenCalledWith("/accounting/bills/upload");

    // Exact match: the getting-started card's "Configure AI" CTA also
    // matches /config/i.
    fireEvent.click(screen.getByRole("button", { name: "Config" }));
    expect(mockPush).toHaveBeenCalledWith("/integrations");

    fireEvent.click(screen.getByRole("button", { name: /view all/i }));
    expect(mockPush).toHaveBeenCalledWith("/integrations");
  });

  test("Sync Now re-runs the dashboard refresh", async () => {
    render(<DashboardPage />);
    await screen.findByText("Box");

    const healthCallsBefore = mockFetch.mock.calls.filter(([u]: [string]) =>
      String(u).includes("/health"),
    ).length;
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    await waitFor(() => {
      const after = mockFetch.mock.calls.filter(([u]: [string]) =>
        String(u).includes("/health"),
      ).length;
      expect(after).toBeGreaterThan(healthCallsBefore);
    });
  });

  test("falls back to nulls when summaries are not ok", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/health")) {
        return Promise.resolve(failing());
      }
      return Promise.resolve(failing());
    });

    render(<DashboardPage />);

    expect(await screen.findByText("Box")).toBeInTheDocument();
    expect(screen.getAllByText("$0").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Disconnected").length).toBe(13);
  });

  test("tolerates rejecting health and summary fetches", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/health")) {
        // All health endpoints reject outright (network down).
        return Promise.reject(new Error("network down"));
      }
      return Promise.reject(new Error("summaries down"));
    });

    render(<DashboardPage />);

    expect(await screen.findByText("Box")).toBeInTheDocument();
    expect(screen.getAllByText("Disconnected").length).toBe(13);
    await waitFor(() => {
      expect(screen.getAllByText("$0").length).toBeGreaterThan(0);
    });
  });

  test("shows a refresh-failed toast when fetch throws synchronously", async () => {
    mockFetch.mockImplementation(() => {
      throw new Error("fetch is broken");
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        "Dashboard refresh failed:",
        expect.anything(),
      );
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Refresh failed" }),
      );
    });
  });

  test("warns when a summary response has invalid JSON", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/health")) return Promise.resolve(failing());
      return Promise.resolve({
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => {
          throw new Error("bad json");
        },
      });
    });

    render(<DashboardPage />);

    await screen.findByText("Box");
    await waitFor(() => {
      expect(warnSpy).toHaveBeenCalledWith(
        "JSON parse error:",
        expect.anything(),
      );
    });
    expect(mockToast).not.toHaveBeenCalled();
  });
});
