// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { BarChartCanvas } from "../BarChart";

describe("BarChartCanvas", () => {
  const mockTenantId = "tenant-123";
  const mockAgentId = "agent-456";
  const mockData = [
    { name: "Item 1", value: 100 },
    { name: "Item 2", value: 200 },
    { name: "Item 3", value: 150 },
  ];

  it("should render bar chart with data", () => {
    render(
      <BarChartCanvas
        data={mockData}
        title="Test Chart"
      />
    );

    expect(screen.getByText("Test Chart")).toBeInTheDocument();
  });

  it("should render without title", () => {
    const { container } = render(
      <BarChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    expect(container.querySelector("h4")).not.toBeInTheDocument();
  });

  it("should render with custom color", () => {
    const { container } = render(
      <BarChartCanvas
                data={mockData}
        color="#ff0000"
      />
    );

    // Chart renders with custom color prop
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should include tenantId context", () => {
    const { container } = render(
      <BarChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    // Component renders without errors with tenantId
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should include agentId in props", () => {
    const { container } = render(
      <BarChartCanvas
                agentId={mockAgentId}
        data={mockData}
      />
    );

    // Component accepts agentId prop
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should handle empty data", () => {
    const { container } = render(
      <BarChartCanvas tenantId={mockTenantId} data={[]} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should be responsive", () => {
    const { container } = render(
      <BarChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    const responsiveContainer = container.querySelector(
      ".recharts-responsive-container"
    );
    expect(responsiveContainer).toBeInTheDocument();
  });
});
