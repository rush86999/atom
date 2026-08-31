/**
 * Zoho Forms + Zoho Flow page tests (webhook-push Zoho apps)
 *
 * Covers: each page mounts the shared ZohoWebhookIntegrationDetail with the
 * right backend wiring (webhook path, secret env, readback path), and the
 * component renders the setup instructions + recent-records readback states.
 * These apps have no OAuth connect flow — Zoho exposes no public read API
 * for either product — so the detail must never render a Connect button.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ZohoFormsPage from "@/pages/integrations/zoho-forms";
import ZohoFlowPage from "@/pages/integrations/zoho-flow";

const mockDetail = jest.fn();

jest.mock("@/components/integrations/ZohoWebhookIntegrationDetail", () => ({
  __esModule: true,
  default: (props: any) => mockDetail(props),
}));

// The module-level mock above replaces the component for the whole file;
// pull the real implementation for the behavior tests below.
const ZohoWebhookIntegrationDetail: React.FC<any> =
  jest.requireActual("@/components/integrations/ZohoWebhookIntegrationDetail").default;

describe("zoho-forms / zoho-flow pages", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockDetail.mockImplementation(() => (
      <div data-testid="zoho-webhook-detail" />
    ));
  });

  test("forms page mounts the shared detail with the forms webhook wiring", () => {
    render(<ZohoFormsPage />);
    expect(mockDetail).toHaveBeenCalledWith(
      expect.objectContaining({
        integrationId: "zoho-forms",
        webhookPath: "/api/v1/integrations/zoho-forms/webhook",
        secretEnv: "ZOHOFORMS_WEBHOOK_SECRET",
        recordsPath: "/api/v1/integrations/zoho-forms/submissions",
      })
    );
  });

  test("flow page mounts the shared detail with the platform webhook wiring", () => {
    render(<ZohoFlowPage />);
    expect(mockDetail).toHaveBeenCalledWith(
      expect.objectContaining({
        integrationId: "zoho-flow",
        webhookPath: "/webhooks/zoho-flow",
        secretEnv: "ZOHOFLOW_WEBHOOK_SECRET",
        recordsPath: "/api/v1/integrations/zoho-flow/events",
      })
    );
  });
});

describe("ZohoWebhookIntegrationDetail", () => {
  const props = {
    appName: "Zoho Forms",
    description: "desc",
    category: "productivity",
    integrationId: "zoho-forms" as const,
    webhookPath: "/api/v1/integrations/zoho-forms/webhook",
    secretEnv: "ZOHOFORMS_WEBHOOK_SECRET",
    recordsLabel: "submissions",
    recordsPath: "/api/integrations/zoho-forms/submissions",
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  test("renders setup instructions with the webhook path and secret env", async () => {
    render(<ZohoWebhookIntegrationDetail {...props} />);
    expect(screen.getByText("Zoho Forms Integration")).toBeInTheDocument();
    expect(await screen.findByText(/How data ingests/i)).toBeInTheDocument();
    expect(screen.getAllByText(/ZOHOFORMS_WEBHOOK_SECRET/).length).toBeGreaterThan(0);
    // push-only app: no OAuth Connect button
    expect(screen.queryByText(/^Connect /)).not.toBeInTheDocument();
  });

  test("shows the empty state before any submission is pushed", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    });
    render(<ZohoWebhookIntegrationDetail {...props} />);
    expect(
      await screen.findByText(/Nothing ingested yet/i)
    ).toBeInTheDocument();
  });

  test("lists recent ingested records when the readback returns data", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [{ id: "r1", title: "Contact Us — Jane", text_preview: "pricing" }],
      }),
    });
    render(<ZohoWebhookIntegrationDetail {...props} />);
    expect(
      await screen.findByText("Contact Us — Jane")
    ).toBeInTheDocument();
    expect(screen.getByTestId("zoho-forms-recent-list")).toBeInTheDocument();
  });
});
