/**
 * Zoho suite integration UI tests — every app page must exist and render
 * with a Connect button targeting the unified Zoho OAuth initiate flow
 * (one Server-based app consent connects Books/Inventory/CRM/WorkDrive).
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ZohoIntegrationDetail from "@/components/integrations/ZohoIntegrationDetail";

jest.mock("@/components/layout", () => ({
  Layout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

describe("ZohoIntegrationDetail", () => {
  it("renders the app name, covered services and a connect link to the unified Zoho flow", () => {
    render(
      <ZohoIntegrationDetail
        appName="Zoho Books"
        description="Accounting — invoices, expenses and chart of accounts"
        category="finance"
        coveredServices={["Zoho Books", "Zoho Inventory", "Zoho CRM", "Zoho WorkDrive"]}
      />,
    );

    expect(screen.getByText("Zoho Books Integration")).toBeInTheDocument();
    expect(screen.getByText("Zoho Inventory")).toBeInTheDocument();
    const link = screen.getByTestId("zoho-connect-link") as HTMLAnchorElement;
    expect(link.getAttribute("href")).toContain("/api/v1/auth/oauth/zoho/initiate");
  });
});

describe("Zoho suite pages", () => {
  const pages: Array<[string, string, string]> = [
    ["zoho-books", "Zoho Books", "finance"],
    ["zoho-inventory", "Zoho Inventory", "ecommerce"],
    ["zoho-crm", "Zoho CRM", "crm"],
    ["zoho-projects", "Zoho Projects", "productivity"],
    ["zoho-mail", "Zoho Mail", "communication"],
  ];

  test.each(pages)(
    "%s page renders with a connect link",
    async (id, name) => {
      const mod = await import(`@/pages/integrations/${id}`);
      const Page = mod.default;
      render(<Page />);
      expect(screen.getByText(`${name} Integration`)).toBeInTheDocument();
      const link = screen.getByTestId("zoho-connect-link") as HTMLAnchorElement;
      expect(link.getAttribute("href")).toContain("/zoho/initiate");
    },
  );
});