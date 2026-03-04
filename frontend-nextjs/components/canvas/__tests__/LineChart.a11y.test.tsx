/**
 * LineChart Component Accessibility Tests
 *
 * Purpose: Test LineChart for WCAG 2.1 AA compliance
 * Tests: visible labels, chart structure, trend accessibility, data accessibility
 */

import { render, screen } from '@testing-library/react';
import axe from '../../../tests/accessibility-config';
import { LineChartCanvas } from '@/components/canvas/LineChart';

const mockData = [
  { timestamp: '2024-01-01', value: 400, label: 'Jan' },
  { timestamp: '2024-02-01', value: 300, label: 'Feb' },
  { timestamp: '2024-03-01', value: 600, label: 'Mar' },
  { timestamp: '2024-04-01', value: 800, label: 'Apr' },
  { timestamp: '2024-05-01', value: 500, label: 'May' }
];

describe('LineChart Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <LineChartCanvas data={mockData} title="Revenue Trend" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have visible title describing trend', () => {
    render(
      <LineChartCanvas data={mockData} title="Revenue Trend" />
    );

    // Chart title should be visible and accessible
    const title = screen.getByText(/revenue trend/i);
    expect(title).toBeInTheDocument();
    expect(title).toHaveAccessibleName();
  });

  it('should have chart structure', () => {
    const { container } = render(
      <LineChartCanvas data={mockData} title="Revenue Trend" />
    );

    // Chart should render with proper structure
    const mainContainer = container.querySelector('.w-full');
    expect(mainContainer).toBeInTheDocument();
  });

  it('should render responsive container', () => {
    const { container } = render(
      <LineChartCanvas data={mockData} title="Revenue Trend" />
    );

    // Should use responsive container for accessibility
    const responsiveContainer = container.querySelector('.recharts-responsive-container');
    expect(responsiveContainer).toBeInTheDocument();
  });

  it('should handle charts without title', async () => {
    const { container } = render(
      <LineChartCanvas data={mockData} />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible chart container', () => {
    const { container } = render(
      <LineChartCanvas data={mockData} title="Revenue Trend" />
    );

    // Main container should be accessible
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  it('should support different data sets', async () => {
    const smallData = [
      { timestamp: '2024-01-01', value: 100, label: 'Jan' }
    ];

    const { container } = render(
      <LineChartCanvas data={smallData} title="Simple Trend" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should handle empty data gracefully', async () => {
    const { container } = render(
      <LineChartCanvas data={[]} title="Empty Trend" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should maintain accessibility with time series data', async () => {
    const timeSeriesData = [
      { timestamp: '09:00', value: 100 },
      { timestamp: '10:00', value: 150 },
      { timestamp: '11:00', value: 200 },
      { timestamp: '12:00', value: 175 }
    ];

    const { container } = render(
      <LineChartCanvas data={timeSeriesData} title="Hourly Data" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible chart structure for trends', () => {
    const { container } = render(
      <LineChartCanvas data={mockData} title="Revenue Trend" />
    );

    // Chart should render with accessible structure
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  it('should handle large datasets accessibly', async () => {
    const largeData = Array.from({ length: 50 }, (_, i) => ({
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      value: Math.random() * 1000,
      label: `Day ${i + 1}`
    }));

    const { container } = render(
      <LineChartCanvas data={largeData} title="Long-term Trend" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should support custom colors accessibly', async () => {
    const { container } = render(
      <LineChartCanvas data={mockData} title="Custom Color" color="#FF5733" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
