/**
 * Zoho WorkDrive page tests (pages/integrations/zoho-workdrive.tsx)
 *
 * Covers: the page mounts the ingestion component WITHOUT wrapping itself in
 * <Layout> — _app.tsx already provides the app shell, and a second wrapper
 * rendered a duplicate sidebar (the duplicate-navbar bug documented on
 * ZohoIntegrationDetail). The page no longer derives or forwards a userId —
 * identity is resolved server-side from the authenticated session
 * (JWT/cookie), and the demo-user fallback has been removed.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ZohoWorkDrivePage from "@/pages/integrations/zoho-workdrive";

const mockIngestion = jest.fn();

jest.mock("@/components/Settings/ZohoWorkDriveIngestion", () => ({
  __esModule: true,
  default: (props: any) => mockIngestion(props),
}));

describe("ZohoWorkDrivePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockIngestion.mockImplementation(() => (
      <div data-testid="zoho-ingestion">Ingestion</div>
    ));
  });

  test("renders the ingestion component without a second app shell", () => {
    render(<ZohoWorkDrivePage />);

    expect(screen.queryByTestId("layout")).not.toBeInTheDocument();
    expect(screen.getByTestId("zoho-ingestion")).toBeInTheDocument();
    expect(
      screen.getByTestId("ingestion-status-panel-loading")
    ).toBeInTheDocument();
  });

  test("does not pass a client-derived userId to the ingestion component", () => {
    render(<ZohoWorkDrivePage />);

    expect(mockIngestion).toHaveBeenCalledWith(
      expect.not.objectContaining({ userId: expect.anything() })
    );
  });
});
