/**
 * Zoho suite integration UI tests — every app page must exist and render
 * with a Connect control that starts the unified Zoho OAuth initiate flow
 * (one Server-based app consent connects Books/Inventory/CRM/WorkDrive).
 *
 * The control is a BUTTON, not an <a href>: browser navigation cannot send
 * the Authorization header, and the JWT must never sit in a URL (history /
 * request-log leak). Clicking fetches the provider URL via authFetch
 * (JWT in header, format=json) and redirects to the returned URL.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

jest.mock("@/components/layout", () => ({
  Layout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

const baseProps = {
  appName: "Zoho Books",
  description: "Accounting — invoices, expenses and chart of accounts",
  category: "finance",
  coveredServices: ["Zoho Books", "Zoho Inventory", "Zoho CRM", "Zoho WorkDrive"],
};

describe("ZohoIntegrationDetail", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Status calls (tokens / sync-status) + the initiate call share fetch.
    (global as any).fetch = jest.fn(async (input: any) => {
      const url = String(input);
      if (url.includes("/oauth/tokens")) {
        return { ok: true, json: async () => ({ integrations: [] }) };
      }
      if (url.includes("sync-status")) {
        return { ok: true, json: async () => ({ found: false }) };
      }
      if (url.includes("/initiate")) {
        return {
          ok: true,
          json: async () => ({ url: "https://accounts.zoho.com/oauth2/v2/auth?state=x" }),
        };
      }
      return { ok: false, json: async () => ({}) };
    });
  });

  it("renders the app name, covered services and a connect control", () => {
    render(<ZohoIntegrationDetail {...baseProps} />);

    expect(screen.getByText("Zoho Books Integration")).toBeInTheDocument();
    expect(screen.getByText("Zoho Inventory")).toBeInTheDocument();
    const ctrl = screen.getByTestId("zoho-connect-link");
    // Regression: must NOT be an <a href> — a navigable URL would drop the
    // Authorization header (401 "Could not validate credentials") or, with a
    // ?token= query, leak the app JWT into history/logs.
    expect(ctrl.tagName).toBe("BUTTON");
    expect(ctrl.getAttribute("href")).toBeNull();
  });

  it("starts the flow via an authenticated initiate fetch, never a URL-bound JWT", async () => {
    render(<ZohoIntegrationDetail {...baseProps} />);

    fireEvent.click(screen.getByTestId("zoho-connect-link"));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/oauth/zoho/initiate?format=json"),
        expect.anything(),
      );
    });
  });
});

describe("Zoho suite pages", () => {
  const pages: Array<[string, string]> = [
    ["zoho-books", "Zoho Books"],
    ["zoho-inventory", "Zoho Inventory"],
    ["zoho-crm", "Zoho CRM"],
    ["zoho-projects", "Zoho Projects"],
    ["zoho-mail", "Zoho Mail"],
  ];

  test.each(pages)(
    "%s page renders with a connect control (no URL-bound JWT)",
    async (id, name) => {
      const mod = await import(`@/pages/integrations/${id}`);
      const Page = mod.default;
      render(<Page />);
      expect(screen.getByText(`${name} Integration`)).toBeInTheDocument();
      const ctrl = screen.getByTestId("zoho-connect-link");
      expect(ctrl.tagName).toBe("BUTTON");
      expect(ctrl.getAttribute("href")).toBeNull();
    },
  );
});
