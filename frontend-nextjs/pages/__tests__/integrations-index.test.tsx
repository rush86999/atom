import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import IntegrationsPage from "@/pages/integrations/index";

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

  const healthUrlCount = 34;
  const integrationCount = 30;

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
  });

  it("shows zero-state while health checks are pending, then all healthy", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({})),
    );

    render(<IntegrationsPage />);
    expect(
      screen.getByRole("heading", { name: /ATOM Integrations Hub/i }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText(
          `${integrationCount} of ${integrationCount} Connected`,
        ),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("Healthy").previousSibling?.textContent).toBe(
      String(integrationCount),
    );
    expect(screen.getAllByText("Manage").length).toBe(integrationCount);
    expect(screen.getAllByText("Connected").length).toBeGreaterThan(0);
  });

  it("marks every integration as an error when all health checks fail", async () => {
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(503)));

    render(<IntegrationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(`0 of ${integrationCount} Connected`),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("Errors").previousSibling?.textContent).toBe(
      String(integrationCount),
    );
    expect(screen.getAllByText("Connect").length).toBe(integrationCount);
  });

  it("calls every integration health endpoint", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(url.includes("/health") ? okResponse({}) : errResponse(404)),
    );

    render(<IntegrationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(
          `${integrationCount} of ${integrationCount} Connected`,
        ),
      ).toBeInTheDocument();
    });

    const healthCalls = mockFetch.mock.calls.filter(([url]: [string]) =>
      String(url).includes("/health"),
    );
    expect(healthCalls.length).toBe(healthUrlCount);
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
    await waitFor(() => {
      expect(screen.getByText("0 of 30 Connected")).toBeInTheDocument();
    });

    const callsAfterMount = mockFetch.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Refresh Status/i }));
    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });
});
