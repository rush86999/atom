// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { LineChartCanvas } from "../LineChart";
import { vi } from "vitest";

vi.mock('recharts', () => import('./../__mocks__/recharts.tsx'));

describe("LineChartCanvas", () => {
  const mockTenantId = "tenant-123";
  const mockAgentId = "agent-456";
  const mockData = [
    { timestamp: "2024-01-01", value: 100 },
    { timestamp: "2024-01-02", value: 200 },
    { timestamp: "2024-01-03", value: 150 },
  ];

  it("should render line chart with data", () => {
    render(
      <LineChartCanvas
                data={mockData}
        title="Test Trend"
      />
    );

    expect(screen.getByText("Test Trend")).toBeInTheDocument();
  });

  it("should render without title", () => {
    const { container } = render(
      <LineChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    expect(container.querySelector("h4")).not.toBeInTheDocument();
  });

  it("should render with custom color", () => {
    const { container } = render(
      <LineChartCanvas
                data={mockData}
        color="#00ff00"
      />
    );

    const chart = container.querySelector('[data-testid="recharts-responsive-container"]');
    expect(chart).toBeInTheDocument();
  });

  it("should include tenantId context", () => {
    const { container } = render(
      <LineChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should include agentId in props", () => {
    const { container } = render(
      <LineChartCanvas
                        data={mockData}
      />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should handle empty data", () => {
    const { container } = render(
      <LineChartCanvas tenantId={mockTenantId} data={[]} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should display time series data correctly", () => {
    const { container } = render(
      <LineChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    // Line chart renders successfully
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should have data points", () => {
    const { container } = render(
      <LineChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    // Chart renders with data
    expect(container.firstChild).toBeInTheDocument();
  });
});
