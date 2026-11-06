/**
 * SettingsPage tests (pages/settings/index.tsx, was 0% coverage)
 *
 * Covers: header, default preferences tab, switching to the Data
 * Pipelines tab, and the disabled workspace/account tabs.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SettingsPage from "@/pages/settings";
import { ProductProfileProvider } from "@/lib/product-profile";

const originalFetch = global.fetch;

jest.mock("@/components/Settings/PreferencesTab", () => ({
  PreferencesTab: () => <div data-testid="preferences-tab">Preferences</div>,
}));

jest.mock("@/components/Settings/DataPipelinesTab", () => ({
  DataPipelinesTab: () => <div data-testid="data-pipelines-tab">Pipelines</div>,
}));

describe("SettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test("renders the header and defaults to the preferences tab", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText(/Manage your workspace preferences/)).toBeInTheDocument();
    expect(screen.getByTestId("preferences-tab")).toBeInTheDocument();
  });

  test("switches to the Data Pipelines tab", () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Data Pipelines" }));
    expect(screen.getByTestId("data-pipelines-tab")).toBeInTheDocument();
    expect(screen.queryByTestId("preferences-tab")).not.toBeInTheDocument();
  });

  test("disables the workspace and account tabs", () => {
    render(<SettingsPage />);
    expect(screen.getByRole("button", { name: "Workspace" })).toBeDisabled();
    const accountTab = screen.getByRole("button", { name: "Account" });
    expect(accountTab).not.toBeDisabled();
  });

  test("core profile hides the deferred governance link", () => {
    render(<SettingsPage />);
    expect(
      screen.queryByRole("link", { name: /Learning & Verification/ })
    ).not.toBeInTheDocument();
  });

  test("full profile shows the governance link", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        profile: "full",
        version: "test",
        statement: "Full test profile",
        capabilities: {
          settings: { label: "Settings", enabled: true },
          governance: { label: "Governance", enabled: true },
        },
        enabled_capabilities: ["settings", "governance"],
        deferred_capabilities: [],
        routes: { "/settings": "settings", "/admin": "governance" },
      }),
    }) as any;

    render(
      <ProductProfileProvider>
        <SettingsPage />
      </ProductProfileProvider>
    );
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: /Learning & Verification/ })
      ).toBeInTheDocument()
    );
  });
});
