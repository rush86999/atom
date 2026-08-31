/**
 * Integration Health page tests (pages/integrations/health.tsx, was 0% coverage)
 *
 * Covers: breadcrumb navigation links, page header/description, the props
 * handed to IntegrationHealthDashboard, and the "About This Dashboard"
 * information card.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import IntegrationHealthPage from "@/pages/integrations/health";

const mockHealthDashboard = jest.fn();

jest.mock("@/components/integrations/IntegrationHealthDashboard", () => ({
  __esModule: true,
  default: (props: any) => mockHealthDashboard(props),
}));

describe("IntegrationHealthPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockHealthDashboard.mockImplementation(() => <div data-testid="health-dashboard" />);
  });

  test("renders breadcrumb navigation links and current crumb", () => {
    render(<IntegrationHealthPage />);
    const home = screen.getByRole("link", { name: "Home" });
    const integrations = screen.getByRole("link", { name: "Integrations" });
    expect(home).toHaveAttribute("href", "/");
    expect(integrations).toHaveAttribute("href", "/integrations");
    expect(screen.getByText("Health Status")).toBeInTheDocument();
  });

  test("renders page header and description", () => {
    render(<IntegrationHealthPage />);
    expect(
      screen.getByRole("heading", { name: /Integration Health Dashboard/ })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/whether their credentials/i)
    ).toBeInTheDocument();
  });

  test("mounts the dashboard with the documented props", () => {
    render(<IntegrationHealthPage />);
    expect(screen.getByTestId("health-dashboard")).toBeInTheDocument();
    expect(mockHealthDashboard).toHaveBeenCalledWith(
      expect.objectContaining({
        autoRefresh: true,
        refreshInterval: 30000,
        showDetails: true,
      })
    );
  });

  test("renders the about section bullets", () => {
    render(<IntegrationHealthPage />);
    expect(screen.getByRole("heading", { name: /About This Dashboard/ })).toBeInTheDocument();
    expect(screen.getByText(/Auto-refresh:/)).toBeInTheDocument();
    expect(screen.getByText(/Status Indicators:/)).toBeInTheDocument();
    expect(screen.getByText(/Verification:/)).toBeInTheDocument();
    expect(screen.getByText(/Response Time:/)).toBeInTheDocument();
    expect(screen.getByText(/Connection Sources:/)).toBeInTheDocument();
  });
});
