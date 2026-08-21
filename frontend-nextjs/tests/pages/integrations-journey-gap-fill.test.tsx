/**
 * Round 80 journey-gap fill pages (were 404s / dead stubs / orphaned).
 *
 * These pages make the hub-reachable integrations real:
 * - dropbox / telegram / gitlab / xero previously 404'd (no page) or were
 *   dead stubs with an inert "Connect" button.
 * - monday / whatsapp had fully-built components that no page rendered.
 *
 * monday/whatsapp are thin wrappers around the pre-existing (now reachable)
 * components. dropbox/telegram/gitlab/xero render IntegrationStatusCard
 * (tested directly in tests/components/integrations-IntegrationStatusCard.test.tsx).
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

jest.mock("@/components/integrations/IntegrationStatusCard", () => {
  return {
    __esModule: true,
    default: (props: any) => (
      <div data-testid="status-card">
        <span data-testid={`connects-${props.connectUrl}`}>connect</span>
      </div>
    ),
  };
});
jest.mock("@/components/integrations/monday/MondayIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="monday-integration" />,
}));
jest.mock("@/components/integrations/WhatsAppBusinessIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="whatsapp-integration" />,
}));

import DropboxPage from "@/pages/integrations/dropbox";
import TelegramPage from "@/pages/integrations/telegram";
import GitLabPage from "@/pages/integrations/gitlab";
import XeroPage from "@/pages/integrations/xero";
import MondayPage from "@/pages/integrations/monday";
import WhatsAppPage from "@/pages/integrations/whatsapp";

describe("integration journey-gap pages", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  test.each([
    ["dropbox", DropboxPage, "/api/dropbox/oauth/url"],
    ["gitlab", GitLabPage, "/api/gitlab/auth/url"],
    ["xero", XeroPage, "/api/xero/auth/url"],
  ])("%s page renders a status card wired to a real OAuth connect endpoint", (_, Page, connectUrl) => {
    render(<Page />);
    expect(screen.getByTestId("status-card")).toBeInTheDocument();
    expect(screen.getByTestId(`connects-${connectUrl}`)).toBeInTheDocument();
  });

  test("telegram page renders a status card", () => {
    render(<TelegramPage />);
    expect(screen.getByTestId("status-card")).toBeInTheDocument();
  });

  test("monday page renders the previously-orphaned Monday component", async () => {
    render(<MondayPage />);
    await waitFor(() => expect(screen.getByTestId("monday-integration")).toBeInTheDocument());
  });

  test("whatsapp page renders the previously-orphaned WhatsApp component", () => {
    render(<WhatsAppPage />);
    expect(screen.getByTestId("whatsapp-integration")).toBeInTheDocument();
  });
});
