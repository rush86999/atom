/**
 * pages/dashboard.tsx tests
 *
 * Covers the main ATOM dashboard page (OAuth-driven integration grid):
 * - Financial + sales intelligence cards
 * - Integration cards derived from the real OAuth grant store
 *   (GET /api/v1/auth/oauth/tokens → {integrations: [{provider, status}]}),
 *   "Connected" for active grants / "Expired" otherwise
 * - Quick action / navigation flows, Sync Now re-refresh
 * - JSON parse fallbacks in safeParseJson + empty state
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
  useToast: (): { toast: jest.Mock; dismiss: jest.Mock; toasts: unknown[] } => ({
    toast: mockToast,
    dismiss: jest.fn(),
    toasts: [],
  }),
}));

const okJson = (body: any) => ({
  ok: true,
  headers: { get: () => "application/json" },
  json: async () => body,
});

const failing = (): { ok: boolean; headers: { get: () => null } } => ({
  ok: false,
  headers: { get: () => null },
});

// 13 granted providers, 3 active — drives the Connected/Expired split.
const ACTIVE = new Set(["box", "slack", "github"]);
const OAUTH_PROVIDERS = [
  "box", "slack", "github",
  "zoho", "microsoft", "outlook", "google", "gmail",
  "notion", "dropbox", "trello", "asana", "stripe",
];
const OAUTH_INTEGRATIONS: Array<{
  provider: string;
  status: string;
  expires_at: null | string;
}> = OAUTH_PROVIDERS.map(
  (provider): { provider: string; status: string; expires_at: null | string } => ({
    provider,
    status: ACTIVE.has(provider) ? "active" : "inactive",
    expires_at: null,
  }),
);

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
      if (url.includes("/auth/oauth/tokens")) {
        return Promise.resolve(okJson({ integrations: OAUTH_INTEGRATIONS }));
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

  test("renders the integration grid from the OAuth store with mixed health", async () => {
    render(<DashboardPage />);

    expect(await screen.findByText("Box")).toBeInTheDocument();
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
    expect(screen.getByText("Asana")).toBeInTheDocument();
    // 3 of 13 grants are active
    expect(screen.getAllByText("Connected").length).toBe(3);
    expect(screen.getAllByText("Expired").length).toBe(10);
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

    const tokenCallsBefore = mockFetch.mock.calls.filter(([u]: [string]) =>
      String(u).includes("/auth/oauth/tokens"),
    ).length;
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    await waitFor(() => {
      const after = mockFetch.mock.calls.filter(([u]: [string]) =>
        String(u).includes("/auth/oauth/tokens"),
      ).length;
      expect(after).toBeGreaterThan(tokenCallsBefore);
    });
  });

  test("falls back to nulls when summaries are not ok", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/auth/oauth/tokens")) {
        // grants exist but none active
        return Promise.resolve(
          okJson({
            integrations: OAUTH_INTEGRATIONS.map((i) => ({
              ...i,
              status: "inactive",
            })),
          }),
        );
      }
      return Promise.resolve(failing());
    });

    render(<DashboardPage />);

    expect(await screen.findByText("Box")).toBeInTheDocument();
    expect(screen.getAllByText("$0").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Expired").length).toBe(13);
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });

  test("tolerates rejecting token and summary fetches", async () => {
    mockFetch.mockImplementation(() =>
      Promise.reject(new Error("network down")),
    );

    render(<DashboardPage />);

    // The tokens fetch rejects → the page falls back to an empty grant
    // list (empty state) instead of crashing.
    await waitFor(() => {
      expect(
        screen.getByText("No integrations connected yet"),
      ).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getAllByText("$0").length).toBeGreaterThan(0);
    });
    expect(errorSpy).not.toHaveBeenCalled();
    expect(mockToast).not.toHaveBeenCalled();
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
      if (url.includes("/auth/oauth/tokens")) {
        return Promise.resolve(
          okJson({ integrations: [OAUTH_INTEGRATIONS[0]] }),
        );
      }
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
