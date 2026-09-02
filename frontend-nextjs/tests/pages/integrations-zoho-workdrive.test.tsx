/**
 * Zoho WorkDrive page tests (pages/integrations/zoho-workdrive.tsx)
 *
 * Covers: the page mounts the ingestion component. The shared sidebar Layout
 * is provided by _app.tsx — the page must NOT wrap itself in <Layout> (doing
 * so rendered the sidebar twice). Identity is resolved server-side from the
 * authenticated session (JWT/cookie); no client-derived userId is forwarded.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ZohoWorkDrivePage from "@/pages/integrations/zoho-workdrive";

const mockIngestion = jest.fn();

jest.mock("@/components/Settings/ZohoWorkDriveIngestion", () => ({
  __esModule: true,
  default: (props: any) => mockIngestion(props),
}));

// IngestionStatusPanel fetches on mount — stub it out.
jest.mock("@/components/integrations/IngestionStatusPanel", () => ({
  __esModule: true,
  default: () => <div data-testid="status-panel">Status</div>,
}));

describe("ZohoWorkDrivePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockIngestion.mockImplementation(() => (
      <div data-testid="zoho-ingestion">Ingestion</div>
    ));
  });

  test("renders the ingestion component; sidebar Layout comes from _app.tsx", () => {
    render(<ZohoWorkDrivePage />);

    expect(screen.getByTestId("zoho-ingestion")).toBeInTheDocument();
    // Regression: the page previously wrapped itself in <Layout> on top of
    // _app.tsx's Layout → two sidebars. The page must not render its own.
    expect(screen.queryByTestId("layout")).not.toBeInTheDocument();
  });

  test("does not pass a client-derived userId to the ingestion component", () => {
    render(<ZohoWorkDrivePage />);

    expect(mockIngestion).toHaveBeenCalledWith(
      expect.not.objectContaining({ userId: expect.anything() })
    );
  });
});
