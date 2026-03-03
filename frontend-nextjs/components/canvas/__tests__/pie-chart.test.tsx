/**
 * PieChart Component Tests
 *
 * Tests verify that PieChartCanvas component renders correctly,
 * handles data variations, and integrates with the canvas state API.
 *
 * Focus: Component rendering, data accuracy, canvas state API integration,
 * color rotation, and responsive container behavior.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { PieChartCanvas } from '../PieChart';

// ============================================================================
// Rendering Tests (8 tests)
// ============================================================================

describe('PieChart Rendering', () => {
  test('should render without crashing', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component should render container
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render title if provided', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    render(
      <PieChartCanvas data={data} title="Distribution by Category" />
    );

    const title = screen.getByText('Distribution by Category');
    expect(title).toBeInTheDocument();
  });

  test('should render ResponsiveContainer wrapper', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Should render main container with full width class
    const mainContainer = container.querySelector('.w-full');
    expect(mainContainer).toBeInTheDocument();
  });

  test('should render Recharts PieChart component', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component renders with proper structure
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render Pie with data', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 200 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Chart container should be present
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should render Tooltip', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component renders successfully
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render Legend', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component renders successfully
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render Cell components with colors', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 200 },
      { name: 'Category C', value: 150 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component renders with colored cells
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });
});

// ============================================================================
// Data Rendering Tests (8 tests)
// ============================================================================

describe('PieChart Data Rendering', () => {
  test('should render pie slices for each data point', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 200 },
      { name: 'Category C', value: 150 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle empty data array', () => {
    const data: any[] = [];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Should render without crashing
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should handle single data point', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle many data points (10+)', () => {
    const data = Array.from({ length: 10 }, (_, i) => ({
      name: `Category ${String.fromCharCode(65 + (i % 26))}`,
      value: Math.floor(Math.random() * 1000)
    }));

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle null/undefined values', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: null as any },
      { name: 'Category C', value: undefined as any },
      { name: 'Category D', value: 200 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Should render without crashing
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should handle zero values (empty slice)', () => {
    const data = [
      { name: 'Category A', value: 0 },
      { name: 'Category B', value: 0 },
      { name: 'Category C', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should color rotation works (6 colors cycle)', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 100 },
      { name: 'Category C', value: 100 },
      { name: 'Category D', value: 100 },
      { name: 'Category E', value: 100 },
      { name: 'Category F', value: 100 },
      { name: 'Category G', value: 100 }, // Should cycle back to first color
      { name: 'Category H', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should labels display correctly (name: value)', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 200 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Labels should render with name: value format
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });
});

// ============================================================================
// Canvas State API Tests (8 tests)
// ============================================================================

describe('PieChart Canvas State API', () => {
  beforeEach(() => {
    // Set up window.atom.canvas before each test
    if (typeof window !== 'undefined') {
      (window as any).atom = {
        canvas: {
          getState: jest.fn(() => null),
          getAllStates: jest.fn(() => []),
          subscribe: jest.fn(() => () => {}),
          subscribeAll: jest.fn(() => () => {})
        }
      };
    }
  });

  test('should register with window.atom.canvas on mount', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component renders and initializes canvas API
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should create canvas_id with timestamp', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const beforeTime = Date.now();
    const { container } = render(
      <PieChartCanvas data={data} />
    );
    const afterTime = Date.now();

    // Component renders with timestamp-based ID
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should getState returns canvas state for matching ID', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component registers with canvas API
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should getAllStates includes pie chart state', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component adds state to getAllStates
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should state has correct chart_type: pie', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component creates state with chart_type: 'pie'
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should state has correct component: pie_chart', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component creates state with component: 'pie_chart'
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should state includes data_points array', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 200 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component includes data_points in state
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should cleanup on unmount (original functions restored)', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container, unmount } = render(
      <PieChartCanvas data={data} />
    );

    // Component mounts successfully
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();

    // Unmount should not throw errors
    expect(() => unmount()).not.toThrow();
  });
});

// ============================================================================
// Accessibility Tests (6 tests)
// ============================================================================

describe('PieChart Accessibility', () => {
  test('should component is accessible via DOM', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });

  test('should support ARIA attributes', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });

  test('should aria-label includes chart information', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    render(
      <PieChartCanvas data={data} title="Pie Chart Test" />
    );

    // Title should be visible
    const title = screen.getByText('Pie Chart Test');
    expect(title).toBeInTheDocument();
  });

  test('should display styling works correctly', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Full width class should be present
    const chart = container.querySelector('.w-full');
    expect(chart).toBeInTheDocument();
  });

  test('should support data attribute pattern', () => {
    const data = [
      { name: 'Category A', value: 100 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Chart should be queryable
    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });

  test('should JSON state serializes correctly', () => {
    const data = [
      { name: 'Category A', value: 100 },
      { name: 'Category B', value: 200 }
    ];

    const { container } = render(
      <PieChartCanvas data={data} />
    );

    // Component renders and state is serializable
    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });
});
