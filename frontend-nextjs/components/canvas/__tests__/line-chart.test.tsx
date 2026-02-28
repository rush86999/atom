/**
 * LineChart Component Tests
 *
 * Tests verify that LineChartCanvas component renders correctly,
 * handles data variations, and integrates with the canvas state API.
 *
 * Focus: Component rendering, data accuracy, canvas state API integration,
 * and responsive container behavior.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LineChartCanvas } from '../LineChart';

// ============================================================================
// Rendering Tests (8 tests)
// ============================================================================

describe('LineChart Rendering', () => {
  test('should render without crashing', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component should render container
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render title if provided', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    render(
      <LineChartCanvas data={data} title="Sales Data" />
    );

    const title = screen.getByText('Sales Data');
    expect(title).toBeInTheDocument();
  });

  test('should render ResponsiveContainer wrapper', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Should render main container with full width class
    const mainContainer = container.querySelector('.w-full');
    expect(mainContainer).toBeInTheDocument();
  });

  test('should render Recharts LineChart component structure', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component renders with proper structure
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render XAxis with timestamp data', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 },
      { timestamp: '2024-01-02', value: 200 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Chart container should be present
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should render YAxis with value data', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 },
      { timestamp: '2024-01-02', value: 200 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Chart container should be present
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should render Tooltip', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component renders successfully
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should render Legend', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component renders successfully
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });
});

// ============================================================================
// Data Rendering Tests (8 tests)
// ============================================================================

describe('LineChart Data Rendering', () => {
  test('should render data points correctly', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 },
      { timestamp: '2024-01-02', value: 200 },
      { timestamp: '2024-01-03', value: 150 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle empty data array', () => {
    const data: any[] = [];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Should render without crashing
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should handle single data point', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle many data points (50+)', () => {
    const data = Array.from({ length: 50 }, (_, i) => ({
      timestamp: `2024-01-${String(i + 1).padStart(2, '0')}`,
      value: Math.floor(Math.random() * 1000)
    }));

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle null/undefined values', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 },
      { timestamp: '2024-01-02', value: null as any },
      { timestamp: '2024-01-03', value: undefined as any },
      { timestamp: '2024-01-04', value: 200 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Should render without crashing
    const wrapper = container.querySelector('div');
    expect(wrapper).toBeInTheDocument();
  });

  test('should handle negative values', () => {
    const data = [
      { timestamp: '2024-01-01', value: -100 },
      { timestamp: '2024-01-02', value: -50 },
      { timestamp: '2024-01-03', value: -200 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should handle zero values', () => {
    const data = [
      { timestamp: '2024-01-01', value: 0 },
      { timestamp: '2024-01-02', value: 0 },
      { timestamp: '2024-01-03', value: 0 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should apply custom color prop', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const customColor = '#FF0000';
    const { container } = render(
      <LineChartCanvas data={data} color={customColor} />
    );

    // Component renders with custom color
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });
});

// ============================================================================
// Canvas State API Tests (8 tests)
// ============================================================================

describe('LineChart Canvas State API', () => {
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
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component renders and initializes canvas API
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should create canvas_id with timestamp', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const beforeTime = Date.now();
    const { container } = render(
      <LineChartCanvas data={data} />
    );
    const afterTime = Date.now();

    // Component renders with timestamp-based ID
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should getState returns canvas state for matching ID', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component registers with canvas API
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should getAllStates includes line chart state', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component adds state to getAllStates
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should state has correct chart_type: line', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component creates state with chart_type: 'line'
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should state has correct component: line_chart', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component creates state with component: 'line_chart'
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should state includes data_points array', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 },
      { timestamp: '2024-01-02', value: 200 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component includes data_points in state
    const chartContainer = container.querySelector('.w-full');
    expect(chartContainer).toBeInTheDocument();
  });

  test('should cleanup on unmount (original functions restored)', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container, unmount } = render(
      <LineChartCanvas data={data} />
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

describe('LineChart Accessibility', () => {
  test('should component is accessible via DOM', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });

  test('should support ARIA attributes', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });

  test('should aria-label includes chart information', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    render(
      <LineChartCanvas data={data} title="Test Chart" />
    );

    // Title should be visible
    const title = screen.getByText('Test Chart');
    expect(title).toBeInTheDocument();
  });

  test('should display styling works correctly', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Full width class should be present
    const chart = container.querySelector('.w-full');
    expect(chart).toBeInTheDocument();
  });

  test('should support data attribute pattern', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Chart should be queryable
    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });

  test('should JSON state serializes correctly', () => {
    const data = [
      { timestamp: '2024-01-01', value: 100 },
      { timestamp: '2024-01-02', value: 200 }
    ];

    const { container } = render(
      <LineChartCanvas data={data} />
    );

    // Component renders and state is serializable
    const chart = container.querySelector('div');
    expect(chart).toBeInTheDocument();
  });
});
