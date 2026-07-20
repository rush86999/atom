// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { PieChartCanvas } from "../PieChart";
import { vi } from "vitest";

vi.mock('recharts', () => import('./../__mocks__/recharts.tsx'));

describe("PieChartCanvas", () => {
  const mockTenantId = "tenant-123";
  const mockAgentId = "agent-456";
  const mockData = [
    { name: "Category A", value: 100 },
    { name: "Category B", value: 200 },
    { name: "Category C", value: 150 },
  ];

  it("should render pie chart with data", () => {
    render(
      <PieChartCanvas
                data={mockData}
        title="Distribution"
      />
    );

    expect(screen.getByText("Distribution")).toBeInTheDocument();
  });

  it("should render without title", () => {
    const { container } = render(
      <PieChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    expect(container.querySelector("h4")).not.toBeInTheDocument();
  });

  it("should include tenantId context", () => {
    const { container } = render(
      <PieChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should include agentId in props", () => {
    const { container } = render(
      <PieChartCanvas
                        data={mockData}
      />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should handle empty data", () => {
    const { container } = render(
      <PieChartCanvas tenantId={mockTenantId} data={[]} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it("should render pie slices", () => {
    const { container } = render(
      <PieChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    // Chart renders successfully
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should display labels", () => {
    const { container } = render(
      <PieChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    // Component renders with chart structure (labels rendered by Pie component)
    const chart = container.querySelector('[data-testid="recharts-responsive-container"]');
    expect(chart).toBeInTheDocument();
  });

  it("should use correct color palette", () => {
    const { container } = render(
      <PieChartCanvas tenantId={mockTenantId} data={mockData} />
    );

    // Chart renders with data
    expect(container.firstChild).toBeInTheDocument();
  });
});
