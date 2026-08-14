/**
 * Integration pages that render a page header around a mocked child
 * integration component (were 0% coverage):
 *  - pages/integrations/gdrive.tsx
 *  - pages/integrations/hubspot.tsx
 *  - pages/integrations/onedrive.tsx
 *  - pages/integrations/stripe.tsx
 *
 * The heavy child integration components are mocked; the tests assert the
 * page chrome (Head/meta is declarative, headings, descriptions) and that
 * the child is mounted.
 */

import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("@/components/integrations/GoogleDriveIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="gdrive-integration" />,
}));
jest.mock("@/components/integrations/hubspot/HubSpotIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="hubspot-integration" />,
}));
jest.mock("@/components/integrations/OneDriveIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="onedrive-integration" />,
}));
jest.mock("@/components/StripeIntegration", () => ({
  __esModule: true,
  default: () => <div data-testid="stripe-integration" />,
}));

import GoogleDrivePage from "@/pages/integrations/gdrive";
import HubSpotPage from "@/pages/integrations/hubspot";
import OneDrivePage from "@/pages/integrations/onedrive";
import StripePage from "@/pages/integrations/stripe";

describe("integration pages with headers", () => {
  beforeEach(() => {
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  test("gdrive renders header text and the Google Drive integration child", () => {
    render(<GoogleDrivePage />);
    expect(screen.getByRole("heading", { name: /Google Drive Integration/ })).toBeInTheDocument();
    expect(
      screen.getByText(/Seamlessly connect your Google Drive account/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("gdrive-integration")).toBeInTheDocument();
  });

  test("hubspot renders header text and the HubSpot integration child", () => {
    render(<HubSpotPage />);
    expect(screen.getByRole("heading", { name: /HubSpot Integration/ })).toBeInTheDocument();
    expect(
      screen.getByText(/Complete CRM and marketing automation platform/i, { exact: false })
    ).toBeInTheDocument();
    expect(screen.getByTestId("hubspot-integration")).toBeInTheDocument();
  });

  test("onedrive renders header text and the OneDrive integration child", () => {
    render(<OneDrivePage />);
    expect(screen.getByRole("heading", { name: /OneDrive Integration/ })).toBeInTheDocument();
    expect(
      screen.getByText(/Seamlessly connect your OneDrive account/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("onedrive-integration")).toBeInTheDocument();
  });

  test("stripe renders header text and the Stripe integration child", () => {
    render(<StripePage />);
    expect(screen.getByRole("heading", { name: /Stripe Integration/ })).toBeInTheDocument();
    expect(
      screen.getByText(/Complete payment processing and financial management platform/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("stripe-integration")).toBeInTheDocument();
  });
});
