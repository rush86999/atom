/**
 * Zoho WorkDrive page tests (pages/integrations/zoho-workdrive.tsx, was 0% coverage)
 *
 * Covers: session-derived userId propagation to ZohoWorkDriveIngestion and
 * the 'demo-user' fallback when there is no session.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ZohoWorkDrivePage from "@/pages/integrations/zoho-workdrive";

const mockUseSession = jest.fn();
const mockIngestion = jest.fn();

jest.mock("next-auth/react", () => ({
  useSession: (...args: any[]) => mockUseSession(...args),
}));

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
    mockIngestion.mockImplementation((props: any) => (
      <div data-testid="zoho-ingestion">Ingestion for {props.userId}</div>
    ));
  });

  test("renders Layout and passes the session user id to the ingestion component", () => {
    mockUseSession.mockReturnValue({ data: { user: { id: "user-42" } } });

    render(<ZohoWorkDrivePage />);

    expect(mockUseSession).toHaveBeenCalled();
    expect(screen.getByTestId("layout")).toBeInTheDocument();
    expect(screen.getByTestId("zoho-ingestion")).toHaveTextContent("Ingestion for user-42");
    expect(mockIngestion).toHaveBeenCalledWith(expect.objectContaining({ userId: "user-42" }));
  });

  test("falls back to 'demo-user' when there is no session", () => {
    mockUseSession.mockReturnValue({ data: null });

    render(<ZohoWorkDrivePage />);

    expect(screen.getByTestId("zoho-ingestion")).toHaveTextContent("Ingestion for demo-user");
    expect(mockIngestion).toHaveBeenCalledWith(expect.objectContaining({ userId: "demo-user" }));
  });
});
