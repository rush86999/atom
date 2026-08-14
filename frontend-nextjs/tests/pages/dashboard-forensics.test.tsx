/**
 * ForensicsDashboard tests (pages/dashboard/forensics.tsx, was 0% coverage)
 *
 * Covers: loading state, summary stat cards, all three tab panels
 * (vendor drift / pricing / subscription waste), and the fetch-failure path.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ForensicsDashboard from "@/pages/dashboard/forensics";

jest.mock("@/components/layout/Layout", () => ({
  Layout: ({ children }: any) => <div data-testid="layout">{children}</div>,
}));

const DRIFT = [
  {
    vendor_id: "v1",
    vendor_name: "Acme Supplies",
    category: "Office",
    drift_percent: 15,
    avg_spend: 1000,
    current_spend: 1150,
    detected_at: "2026-08-01T00:00:00Z",
  },
];

const PRICING = [
  {
    sku: "sku-1",
    item: "Consulting Retainer",
    reason: "Underpriced vs market",
    margin_impact: "+12 pts",
    current_price: 200,
    target_price: 250,
    confidence: 0.91,
  },
];

const WASTE = [
  {
    subscription_id: "s1",
    service_name: "Unused SaaS",
    status: "inactive",
    mrr: 99,
    last_login: "2026-01-15T00:00:00Z",
  },
];

const okJson = (body: any) => ({ ok: true, json: async () => body });

describe("ForensicsDashboard", () => {
  let mockFetch: jest.Mock;
  let consoleErrorSpy: jest.SpyInstance;

  const mockDataFetch = () =>
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("vendor-drift")) return Promise.resolve(okJson({ data: DRIFT }));
      if (url.includes("pricing-opportunities")) return Promise.resolve(okJson({ data: PRICING }));
      return Promise.resolve(okJson({ data: WASTE }));
    });

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch as any;
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockDataFetch();
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  test("shows the loading message while analysis is in flight", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<ForensicsDashboard />);
    expect(screen.getByText("Loading analysis...")).toBeInTheDocument();
  });

  test("renders summary cards with dataset counts", async () => {
    render(<ForensicsDashboard />);
    await waitFor(() => expect(screen.getByText("1 Vendors")).toBeInTheDocument());
    expect(screen.getByText("1 Opportunities")).toBeInTheDocument();
    expect(screen.getByText("1 Subscriptions")).toBeInTheDocument();
  });

  test("drift tab renders vendor details", async () => {
    render(<ForensicsDashboard />);
    await waitFor(() => expect(screen.getByText("Acme Supplies")).toBeInTheDocument());
    expect(screen.getByText("Office")).toBeInTheDocument();
    expect(screen.getByText("+15% Drift")).toBeInTheDocument();
    expect(screen.getByText("$1000")).toBeInTheDocument();
    expect(screen.getByText("$1150")).toBeInTheDocument();
    expect(screen.getByText("Historical Avg")).toBeInTheDocument();
    expect(screen.getByText("Current Spend")).toBeInTheDocument();
    expect(screen.getByText("Detected")).toBeInTheDocument();
  });

  test("pricing tab renders opportunities", async () => {
    render(<ForensicsDashboard />);
    await waitFor(() => expect(screen.getByText("Acme Supplies")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Smart Pricing" }));
    expect(screen.getByText("Consulting Retainer")).toBeInTheDocument();
    expect(screen.getByText("Underpriced vs market")).toBeInTheDocument();
    expect(screen.getByText("+12 pts Margin")).toBeInTheDocument();
    expect(screen.getByText("$200")).toBeInTheDocument();
    expect(screen.getByText("$250")).toBeInTheDocument();
    expect(screen.getByText("Confidence: 0.91")).toBeInTheDocument();
  });

  test("waste tab renders subscriptions with a cancel button", async () => {
    render(<ForensicsDashboard />);
    await waitFor(() => expect(screen.getByText("Acme Supplies")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Subscription Manager" }));
    expect(screen.getByText("Unused SaaS")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
    expect(screen.getByText("Monthly Cost")).toBeInTheDocument();
    expect(screen.getByText("$99")).toBeInTheDocument();
    expect(screen.getByText("Last Active")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel Subscription" })).toBeInTheDocument();
  });

  test("handles fetch failure gracefully", async () => {
    mockFetch.mockRejectedValue(new Error("down"));
    render(<ForensicsDashboard />);
    await waitFor(() => expect(screen.getByText("0 Vendors")).toBeInTheDocument());
    expect(screen.getByText("0 Opportunities")).toBeInTheDocument();
    expect(screen.getByText("0 Subscriptions")).toBeInTheDocument();
    await waitFor(() =>
      expect(consoleErrorSpy).toHaveBeenCalledWith("Failed to load forensics", expect.any(Error))
    );
  });

  test("falls back to empty lists when responses carry no data key", async () => {
    mockFetch.mockImplementation((url: string) => Promise.resolve(okJson({})));
    render(<ForensicsDashboard />);
    await waitFor(() => expect(screen.getByText("0 Vendors")).toBeInTheDocument());
    expect(screen.getByText("0 Opportunities")).toBeInTheDocument();
    expect(screen.getByText("0 Subscriptions")).toBeInTheDocument();
  });
});
