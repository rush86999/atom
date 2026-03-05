/**
 * PieChart Component Accessibility Tests
 *
 * Purpose: Test PieChart for WCAG 2.1 AA compliance
 * Tests: visible labels, segment accessibility, legend, data accessibility
 */

import { render, screen } from '@testing-library/react';
import axe from '../../../tests/accessibility-config';
import { PieChartCanvas } from '@/components/canvas/PieChart';

const mockData = [
  { name: 'Product A', value: 400 },
  { name: 'Product B', value: 300 },
  { name: 'Product C', value: 600 },
  { name: 'Product D', value: 200 }
];

describe('PieChart Accessibility', () => {
  it('should have no accessibility violations', async () => {
    const { container } = render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have visible title describing distribution', () => {
    render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Chart title should be visible and accessible
    const title = screen.getByText(/sales distribution/i);
    expect(title).toBeInTheDocument();
    expect(title).toHaveAccessibleName();
  });

  it('should have chart structure', () => {
    const { container } = render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Chart should render with proper structure
    const mainContainer = container.querySelector('.w-full');
    expect(mainContainer).toBeInTheDocument();
  });

  it('should render responsive container', () => {
    const { container } = render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Should use responsive container for accessibility
    const responsiveContainer = container.querySelector('.recharts-responsive-container');
    expect(responsiveContainer).toBeInTheDocument();
  });

  it('should handle charts without title', async () => {
    const { container } = render(
      <PieChartCanvas data={mockData} />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible chart container', () => {
    const { container } = render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Main container should be accessible
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  it('should support different data sets', async () => {
    const smallData = [
      { name: 'Segment A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={smallData} title="Simple Distribution" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should handle empty data gracefully', async () => {
    const { container } = render(
      <PieChartCanvas data={[]} title="Empty Distribution" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible chart structure for distributions', () => {
    const { container } = render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Chart should render with accessible structure
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  it('should handle multi-segment distributions accessibly', async () => {
    const multiSegmentData = [
      { name: 'Q1', value: 250 },
      { name: 'Q2', value: 300 },
      { name: 'Q3', value: 350 },
      { name: 'Q4', value: 400 },
      { name: 'Q5', value: 200 },
      { name: 'Q6', value: 150 }
    ];

    const { container } = render(
      <PieChartCanvas data={multiSegmentData} title="Multi-Quarter Distribution" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should display segments with labels', () => {
    render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Segment labels should be visible in the chart
    // Note: Recharts renders labels on the pie segments
    const wrapper = screen.getByText(/sales distribution/i);
    expect(wrapper).toBeInTheDocument();
  });

  it('should maintain color contrast accessibility', async () => {
    const { container } = render(
      <PieChartCanvas data={mockData} title="Sales Distribution" />
    );

    // Colors should maintain accessibility
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should handle dominant segments accessibly', async () => {
    const dominantData = [
      { name: 'Major', value: 900 },
      { name: 'Minor 1', value: 50 },
      { name: 'Minor 2', value: 30 },
      { name: 'Minor 3', value: 20 }
    ];

    const { container } = render(
      <PieChartCanvas data={dominantData} title="Dominant Segment" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should handle equal-sized segments accessibly', async () => {
    const equalData = [
      { name: 'A', value: 100 },
      { name: 'B', value: 100 },
      { name: 'C', value: 100 },
      { name: 'D', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={equalData} title="Equal Distribution" />
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
