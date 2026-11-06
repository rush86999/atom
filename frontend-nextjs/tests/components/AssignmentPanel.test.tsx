/**
 * AssignmentPanel release-surface tests.
 *
 * The empty-source fallback must not send core users to the deferred
 * /integrations surface. The Data upload link remains the supported action;
 * the Integrations link is kept only for a profile that enables connectors.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { AssignmentPanel } from "@/components/assignments/AssignmentPanel";
import { ProductProfileProvider } from "@/lib/product-profile";

const originalFetch = global.fetch;

jest.mock("@/lib/api-client", () => ({
  apiClient: {
    get: jest.fn().mockResolvedValue({ data: [] }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    put: jest.fn().mockResolvedValue({ data: {} }),
    delete: jest.fn().mockResolvedValue({ data: {} }),
  },
}));

describe("AssignmentPanel deferred integrations fallback", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("auth_token", "tok");
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test("core profile keeps Data and omits the deferred Integrations link", async () => {
    render(<AssignmentPanel />);
    await waitFor(() =>
      expect(screen.getByText(/Upload a CSV or workbook in/)).toBeInTheDocument()
    );
    expect(screen.getByText("Data")).toBeInTheDocument();
    expect(screen.queryByText("Integrations")).not.toBeInTheDocument();
  });

  test("full profile keeps the Integrations link", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        profile: "full",
        version: "test",
        statement: "Full test profile",
        capabilities: {
          documents: { label: "Data", enabled: true },
          connectors: { label: "Connector Management", enabled: true },
        },
        enabled_capabilities: ["documents", "connectors"],
        deferred_capabilities: [],
        routes: { "/documents": "documents", "/integrations": "connectors" },
      }),
    }) as any;

    render(
      <ProductProfileProvider>
        <AssignmentPanel />
      </ProductProfileProvider>
    );
    await waitFor(() =>
      expect(screen.getByText("Integrations")).toBeInTheDocument()
    );
  });
});
