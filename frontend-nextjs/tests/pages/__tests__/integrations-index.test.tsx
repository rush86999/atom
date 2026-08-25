import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import IntegrationsPage from "@/pages/integrations/index";

// File-local router mock with mutable query/isReady so deep-link tests can
// simulate landing on /integrations?connect=gmail.
jest.mock("next/router", () => {
  const state: { query: Record<string, any>; isReady: boolean } = {
    query: {},
    isReady: true,
  };
  const router = {
    get query() {
      return state.query;
    },
    get isReady() {
      return state.isReady;
    },
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    reload: jest.fn(),
    pathname: "/integrations",
    asPath: "/integrations",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  };
  return {
    __esModule: true,
    __routerState: state,
    useRouter: () => router,
  };
});

const { __routerState } = jest.requireMock("next/router") as any;

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

const navigationErrors: string[] = [];
const vc: any = window._virtualConsole;
if (vc && vc.on) {
  vc.on("jsdomError", (error: any) => {
    const message = String(error && (error.message || error));
    if (message.includes("Not implemented: navigation")) {
      navigationErrors.push(message);
    }
  });
}

describe("IntegrationsPage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
  });

  /**
   * The hub only probes integrations that have a health-endpoint mapping;
   * unmapped cards render as "Connect" by design (round 80). Assert the
   * summary dynamically so catalog growth doesn't break the suite.
   */
  async function expectSummary(): Promise<{ connected: number; total: number }> {
    // wait past the initial "0 of 0" pre-health render
    await waitFor(() => {
      const el = screen.getByText(/\d+ of \d+ Connected/);
      const m = el.textContent!.match(/(\d+) of (\d+)/)!;
      expect(Number(m[2])).toBeGreaterThan(0);
    });
    const el = screen.getByText(/\d+ of \d+ Connected/);
    const match = el.textContent!.match(/(\d+) of (\d+)/)!;
    return { connected: Number(match[1]), total: Number(match[2]) };
  }

  it("shows zero-state while health checks are pending, then all healthy", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({})),
    );

    render(<IntegrationsPage />);
    expect(
      screen.getByRole("heading", { name: /ATOM Integrations Hub/i }),
    ).toBeInTheDocument();

    const { connected, total } = await expectSummary();
    expect(total).toBeGreaterThanOrEqual(30); // catalog keeps growing
    expect(connected).toBeGreaterThan(0);

    const healthyPct = Math.round((connected / total) * 100);
    expect(screen.getByText(`${healthyPct}%`)).toBeInTheDocument();
    expect(screen.getByText("Healthy").previousSibling?.textContent).toBe(
      String(connected),
    );
    // every probed-and-healthy card shows Manage; unmapped ones show Connect
    expect(screen.getAllByText("Manage").length).toBe(connected);
    expect(screen.getAllByText("Connected").length).toBeGreaterThan(0);
  });

  it("marks every integration as an error when all health checks fail", async () => {
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(503)));

    render(<IntegrationsPage />);
    const { total } = await expectSummary();
    await waitFor(() => {
      expect(screen.getByText(`0 of ${total} Connected`)).toBeInTheDocument();
    });
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("Errors").previousSibling?.textContent).toBe(
      String(total),
    );
    expect(screen.getAllByText("Connect").length).toBe(total);
  });

  it("calls every integration health endpoint", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(url.includes("/health") ? okResponse({}) : errResponse(404)),
    );

    render(<IntegrationsPage />);
    const { connected } = await expectSummary();
    expect(connected).toBeGreaterThan(0);

    const healthCalls = mockFetch.mock.calls.filter(([url]: [string]) =>
      String(url).includes("/health"),
    );
    // the hub probes its whole health map; connected ⊆ probed
    expect(healthCalls.length).toBeGreaterThanOrEqual(connected);
    expect(mockFetch.mock.calls).toContainEqual([
      "/api/integrations/salesforce/health",
    ]);
    expect(mockFetch.mock.calls).toContainEqual([
      "/api/integrations/gmail/health",
    ]);
    expect(mockFetch.mock.calls).toContainEqual([
      "/api/integrations/trello/health",
    ]);
  });

  it("filters the grid by category", async () => {
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(503)));
    render(<IntegrationsPage />);
    await waitFor(() => {
      expect(screen.getByText("0%")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /CRM/i }));
    expect(screen.getByText("Salesforce")).toBeInTheDocument();
    expect(screen.getByText("HubSpot")).toBeInTheDocument();
    expect(screen.queryByText("Slack")).not.toBeInTheDocument();
    expect(screen.queryByText("Stripe")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /File Storage/i }));
    expect(screen.getByText("Box")).toBeInTheDocument();
    expect(screen.getByText("Dropbox")).toBeInTheDocument();
    expect(screen.queryByText("Salesforce")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /All Integrations/i }));
    expect(screen.getByText("Slack")).toBeInTheDocument();
    expect(screen.getByText("Stripe")).toBeInTheDocument();
  });

  it("navigates to the integration detail page when a card is clicked", async () => {
    navigationErrors.length = 0;
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(503)));
    render(<IntegrationsPage />);
    await waitFor(() => {
      expect(screen.getByText("0%")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Salesforce"));
    expect(navigationErrors).toHaveLength(1);

    navigationErrors.length = 0;
    fireEvent.click(screen.getByText("Gmail"));
    expect(navigationErrors).toHaveLength(1);
  });

  it("re-fetches health on Refresh Status click", async () => {
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(503)));
    render(<IntegrationsPage />);
    const { total } = await expectSummary();
    await waitFor(() => {
      expect(screen.getByText(`0 of ${total} Connected`)).toBeInTheDocument();
    });

    const callsAfterMount = mockFetch.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Refresh Status/i }));
    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });

  it("deep-links ?connect=<provider> to a highlighted card", async () => {
    __routerState.query = { connect: "gmail" };
    mockFetch.mockImplementation(() => Promise.resolve(okResponse({})));

    render(<IntegrationsPage />);
    await screen.findByRole("heading", { name: /ATOM Integrations Hub/i });

    await waitFor(() => {
      const el = document.getElementById("integration-gmail");
      expect(el).not.toBeNull();
      expect(el!.className).toContain("ring-2");
    });
  });

  it("clears unknown ?connect targets without crashing", async () => {
    __routerState.query = { connect: "nonexistent-provider" };
    mockFetch.mockImplementation(() => Promise.resolve(okResponse({})));

    render(<IntegrationsPage />);
    await screen.findByRole("heading", { name: /ATOM Integrations Hub/i });
    await waitFor(() => {
      expect(screen.getByText(/\d+ of \d+ Connected/)).toBeInTheDocument();
    });
  });
});
