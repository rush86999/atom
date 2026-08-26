/**
 * Zoho WorkDrive page tests (pages/integrations/zoho-workdrive.tsx)
 *
 * Covers: the page renders inside the shared Layout and mounts the ingestion
 * component. The page no longer derives or forwards a userId — identity is
 * resolved server-side from the authenticated session (JWT/cookie), and the
 * demo-user fallback has been removed.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ZohoWorkDrivePage from "@/pages/integrations/zoho-workdrive";

const mockIngestion = jest.fn();

jest.mock("@/components/layout", () => ({
  Layout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

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

  test("renders the ingestion component inside the shared Layout", () => {
    render(<ZohoWorkDrivePage />);

    expect(screen.getByTestId("layout")).toBeInTheDocument();
    expect(screen.getByTestId("zoho-ingestion")).toBeInTheDocument();
  });

  test("does not pass a client-derived userId to the ingestion component", () => {
    render(<ZohoWorkDrivePage />);

    expect(mockIngestion).toHaveBeenCalledWith(
      expect.not.objectContaining({ userId: expect.anything() })
    );
  });
});
