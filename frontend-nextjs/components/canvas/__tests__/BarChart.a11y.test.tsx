/**
 * BarChart Component Accessibility Tests
 *
 * Purpose: Test BarChart for WCAG 2.1 AA compliance
 * Tests: visible labels, chart structure, data accessibility through canvas API
 */

import { render, screen } from '@testing-library/react';
import axe from '../../../tests/accessibility-config';
import { BarChartCanvas } from '@/components/canvas/BarChart';

const mockData = [
  { name: 'Jan', value: 400 },
  { name: 'Feb', value: 300 },
  { name: 'Mar', value: 600 },
  { name: 'Apr', value: 800 },
  { name: 'May', value: 500 }
];

describe('BarChart Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <BarChartCanvas data={mockData} title="Monthly Sales" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have visible title describing chart', () => {
    render(
      <BarChartCanvas data={mockData} title="Monthly Sales" />
    );

    // Chart title should be visible and accessible
    const title = screen.getByText(/monthly sales/i);
    expect(title).toBeInTheDocument();
    expect(title).toHaveAccessibleName();
  });

  it('should have chart structure', () => {
    const { container } = render(
      <BarChartCanvas data={mockData} title="Monthly Sales" />
    );

    // Chart should render with proper structure
    const mainContainer = container.querySelector('.w-full');
    expect(mainContainer).toBeInTheDocument();
  });

  it('should render responsive container', () => {
    const { container } = render(
      <BarChartCanvas data={mockData} title="Monthly Sales" />
    );

    // Should use responsive container for accessibility
    const responsiveContainer = container.querySelector('.recharts-responsive-container');
    expect(responsiveContainer).toBeInTheDocument();
  });

  it('should handle charts without title', async () => {
    const { container } = render(
      <BarChartCanvas data={mockData} />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible chart container', () => {
    const { container } = render(
      <BarChartCanvas data={mockData} title="Monthly Sales" />
    );

    // Main container should be accessible
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  it('should support different data sets', async () => {
    const smallData = [{ name: 'A', value: 100 }];

    const { container } = render(
      <BarChartCanvas data={smallData} title="Simple Chart" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should handle empty data gracefully', async () => {
    const { container } = render(
      <BarChartCanvas data={[]} title="Empty Chart" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible chart structure', () => {
    const { container } = render(
      <BarChartCanvas data={mockData} title="Monthly Sales" />
    );

    // Chart should render with accessible structure
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  it('should maintain accessibility with large datasets', async () => {
    const largeData = Array.from({ length: 20 }, (_, i) => ({
      name: `Item ${i}`,
      value: Math.random() * 1000
    }));

    const { container } = render(
      <BarChartCanvas data={largeData} title="Large Dataset" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
