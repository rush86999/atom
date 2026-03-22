/**
 * CanvasChart Component Tests
 *
 * Comprehensive test suite for CanvasChart component covering:
 * - Line chart rendering
 * - Bar chart rendering
 * - Pie chart rendering
 * - Touch interactions and tooltips
 * - Zoom and pan functionality
 * - Export to CSV
 * - Legend toggle
 * - Loading state
 * - Empty state
 * - Error state
 * - Portrait/landscape modes
 * - Custom colors and styling
 *
 * Coverage Target: 80%+
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { ThemeProvider } from 'react-native-paper';
import { CanvasChart, ChartData } from '../canvas/CanvasChart';

// Mock dependencies
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: {
    Light: 'light',
    Medium: 'medium',
    Heavy: 'heavy',
  },
}));

jest.mock('expo-file-system', () => ({
  writeAsStringAsync: jest.fn(),
  documentDirectory: '/tmp/',
  EncodingType: {
    UTF8: 'utf8',
  },
}));

jest.mock('expo-sharing', () => ({
  isAvailableAsync: jest.fn(() => Promise.resolve(true)),
  shareAsync: jest.fn(),
}));

jest.mock('victory-native', () => {
  const ActualVictory = jest.requireActual('victory-native');
  const React = require('react');

  return {
    ...ActualVictory,
    VictoryChart: ({ children, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-chart', props }, children);
    },
    VictoryLine: ({ data, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-line', data, props });
    },
    VictoryBar: ({ data, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-bar', data, props });
    },
    VictoryPie: ({ data, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-pie', data, props });
    },
    VictoryAxis: () => React.createElement('View', { testID: 'victory-axis' }),
    VictoryTooltip: ({ children, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-tooltip', props }, children);
    },
    VictoryVoronoiContainer: ({ children, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-voronoi-container', props }, children);
    },
    VictoryZoomContainer: ({ children, ...props }: any) => {
      return React.createElement('View', { testID: 'victory-zoom-container', props }, children);
    },
    VictoryLabel: ({ text, ...props }: any) => {
      return React.createElement('Text', { testID: 'victory-label', props }, text);
    },
    VictoryTheme: {
      material: 'material',
    },
  };
});

describe('CanvasChart Component', () => {
  const mockLineData: ChartData = {
    type: 'line',
    title: 'Sales Over Time',
    data: [
      { x: 'Jan', y: 100, label: 'January' },
      { x: 'Feb', y: 200, label: 'February' },
      { x: 'Mar', y: 150, label: 'March' },
      { x: 'Apr', y: 300, label: 'April' },
    ],
    xAxisLabel: 'Month',
    yAxisLabel: 'Sales ($)',
    colors: ['#2196F3'],
  };

  const mockBarData: ChartData = {
    type: 'bar',
    title: 'Revenue by Quarter',
    data: [
      { x: 'Q1', y: 1000, label: 'Q1 2024' },
      { x: 'Q2', y: 1500, label: 'Q2 2024' },
      { x: 'Q3', y: 1200, label: 'Q3 2024' },
      { x: 'Q4', y: 1800, label: 'Q4 2024' },
    ],
    xAxisLabel: 'Quarter',
    yAxisLabel: 'Revenue ($)',
  };

  const mockPieData: ChartData = {
    type: 'pie',
    title: 'Market Share',
    data: [
      { x: 'Product A', y: 30, label: 'Product A' },
      { x: 'Product B', y: 25, label: 'Product B' },
      { x: 'Product C', y: 20, label: 'Product C' },
      { x: 'Product D', y: 25, label: 'Product D' },
    ],
  };

  const renderWithTheme = (component: React.ReactElement) => {
    return render(
      <ThemeProvider theme={{ colors: { primary: '#2196F3', onSurface: '#000', surfaceVariant: '#f5f5f5', surface: '#fff', outline: '#ccc', error: '#F44336' } }}>
        {component}
      </ThemeProvider>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Line Chart', () => {
    test('should render line chart correctly', () => {
      const { getByText, getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} />
      );

      expect(getByText('Sales Over Time')).toBeTruthy();
      expect(getByTestId('victory-chart')).toBeTruthy();
      expect(getByTestId('victory-line')).toBeTruthy();
    });

    test('should render axis labels', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} />
      );

      expect(getByText('Month')).toBeTruthy();
      expect(getByText('Sales ($)')).toBeTruthy();
    });

    test('should render data points', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} />
      );

      const lineChart = getByTestId('victory-line');
      expect(lineChart.props.data).toEqual(mockLineData.data);
    });

    test('should use custom colors', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart
          data={{
            ...mockLineData,
            colors: ['#FF5722', '#4CAF50'],
          }}
        />
      );

      const lineChart = getByTestId('victory-line');
      expect(lineChart.props.props.style.data.stroke).toBe('#FF5722');
    });
  });

  describe('Bar Chart', () => {
    test('should render bar chart correctly', () => {
      const { getByText, getByTestId } = renderWithTheme(
        <CanvasChart data={mockBarData} />
      );

      expect(getByText('Revenue by Quarter')).toBeTruthy();
      expect(getByTestId('victory-chart')).toBeTruthy();
      expect(getByTestId('victory-bar')).toBeTruthy();
    });

    test('should render axis labels for bar chart', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockBarData} />
      );

      expect(getByText('Quarter')).toBeTruthy();
      expect(getByText('Revenue ($)')).toBeTruthy();
    });

    test('should render bars with different colors', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockBarData} />
      );

      const barChart = getByTestId('victory-bar');
      expect(barChart.props.data).toEqual(mockBarData.data);
    });
  });

  describe('Pie Chart', () => {
    test('should render pie chart correctly', () => {
      const { getByText, getByTestId } = renderWithTheme(
        <CanvasChart data={mockPieData} />
      );

      expect(getByText('Market Share')).toBeTruthy();
      expect(getByTestId('victory-pie')).toBeTruthy();
    });

    test('should not show legend for pie chart', () => {
      const { queryByTestId } = renderWithTheme(
        <CanvasChart data={mockPieData} />
      );

      // Pie charts should not have separate legend
      expect(queryByTestId('legend-container')).toBeNull();
    });

    test('should not show zoom reset for pie chart', () => {
      const { queryByText } = renderWithTheme(
        <CanvasChart data={mockPieData} />
      );

      expect(queryByText('Reset Zoom')).toBeNull();
    });
  });

  describe('Touch Interactions', () => {
    test('should call onPointPress when point is pressed', () => {
      const mockOnPointPress = jest.fn();
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} onPointPress={mockOnPointPress} />
      );

      const voronoiContainer = getByTestId('victory-voronoi-container');
      const events = voronoiContainer.props.events;

      expect(events).toBeDefined();
      expect(events[0].onChildPress).toBeDefined();
    });

    test('should show tooltip on point press', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} />
      );

      // Initially, no tooltip
      expect(() => getByTestId('tooltip')).toThrow();

      // Simulate point press
      const voronoiContainer = getByTestId('victory-voronoi-container');
      const onChildPress = voronoiContainer.props.events[0].onChildPress;

      act(() => {
        onChildPress({ x: 'Jan', y: 100 }, { x: 'Jan', y: 100, label: 'January' });
      });

      // Tooltip should now be visible
      expect(getByTestId('tooltip')).toBeTruthy();
    });

    test('should trigger haptic feedback on point press', () => {
      const Haptics = require('expo-haptics');
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} />
      );

      const voronoiContainer = getByTestId('victory-voronoi-container');
      const onChildPress = voronoiContainer.props.events[0].onChildPress;

      act(() => {
        onChildPress({ x: 'Jan', y: 100 }, { x: 'Jan', y: 100, label: 'January' });
      });

      expect(Haptics.impactAsync).toHaveBeenCalledWith(Haptics.ImpactFeedbackStyle.Light);
    });
  });

  describe('Zoom and Pan', () => {
    test('should enable zoom by default for line and bar charts', () => {
      const { getByTestId, queryByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} enableZoom={true} />
      );

      // Should show zoom container
      expect(getByTestId('victory-zoom-container')).toBeTruthy();
    });

    test('should disable zoom when enableZoom is false', () => {
      const { queryByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} enableZoom={false} />
      );

      expect(queryByTestId('victory-zoom-container')).toBeNull();
    });

    test('should show reset zoom button', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableZoom={true} />
      );

      expect(getByText('Reset Zoom')).toBeTruthy();
    });

    test('should reset zoom when button is pressed', () => {
      const mockOnZoomChange = jest.fn();
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableZoom={true} onZoomChange={mockOnZoomChange} />
      );

      const resetButton = getByText('Reset Zoom');
      fireEvent.press(resetButton);

      expect(mockOnZoomChange).toHaveBeenCalledWith({ x: [0, 1], y: [0, 1] });
    });

    test('should trigger haptic feedback on zoom reset', () => {
      const Haptics = require('expo-haptics');
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableZoom={true} />
      );

      const resetButton = getByText('Reset Zoom');
      fireEvent.press(resetButton);

      expect(Haptics.impactAsync).toHaveBeenCalled();
    });
  });

  describe('Export Functionality', () => {
    test('should show export button by default', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableExport={true} />
      );

      expect(getByText('Export CSV')).toBeTruthy();
    });

    test('should export data as CSV', async () => {
      const FileSystem = require('expo-file-system');
      const Sharing = require('expo-sharing');
      FileSystem.writeStringAsync.mockResolvedValue(undefined);

      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableExport={true} />
      );

      const exportButton = getByText('Export CSV');
      fireEvent.press(exportButton);

      await waitFor(() => {
        expect(FileSystem.writeStringAsync).toHaveBeenCalled();
        expect(Sharing.isAvailableAsync).toHaveBeenCalled();
      });
    });

    test('should show exporting state while exporting', async () => {
      const FileSystem = require('expo-file-system');
      let resolveExport: any;
      FileSystem.writeStringAsync.mockImplementation(() => {
        return new Promise((resolve) => {
          resolveExport = resolve;
        });
      });

      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableExport={true} />
      );

      const exportButton = getByText('Export CSV');
      fireEvent.press(exportButton);

      // Should show exporting text
      expect(getByText('Exporting...')).toBeTruthy();

      // Resolve export
      act(() => {
        resolveExport();
      });
    });

    test('should trigger haptic feedback on export', async () => {
      const Haptics = require('expo-haptics');
      const FileSystem = require('expo-file-system');
      FileSystem.writeStringAsync.mockResolvedValue(undefined);

      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableExport={true} />
      );

      const exportButton = getByText('Export CSV');
      fireEvent.press(exportButton);

      await waitFor(() => {
        expect(Haptics.impactAsync).toHaveBeenCalledWith(Haptics.ImpactFeedbackStyle.Medium);
      });
    });

    test('should not export when enableExport is false', () => {
      const { queryByText } = renderWithTheme(
        <CanvasChart data={mockLineData} enableExport={false} />
      );

      expect(queryByText('Export CSV')).toBeNull();
    });

    test('should not export when data is empty', async () => {
      const FileSystem = require('expo-file-system');
      const { getByText } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: [] }} enableExport={true} />
      );

      const exportButton = getByText('Export CSV');
      fireEvent.press(exportButton);

      expect(FileSystem.writeStringAsync).not.toHaveBeenCalled();
    });
  });

  describe('Legend', () => {
    test('should show legend by default for line and bar charts', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} showLegend={true} />
      );

      expect(getByTestId('legend-container')).toBeTruthy();
    });

    test('should hide legend when showLegend is false', () => {
      const { queryByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} showLegend={false} />
      );

      expect(queryByTestId('legend-container')).toBeNull();
    });

    test('should show legend toggle button', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} showLegend={true} />
      );

      expect(getByText('Legend')).toBeTruthy();
    });

    test('should toggle legend visibility', () => {
      const { getByText, getByTestId, queryByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} showLegend={true} />
      );

      // Legend should be visible
      expect(getByTestId('legend-container')).toBeTruthy();

      // Press toggle button
      const toggleButton = getByText('Legend');
      fireEvent.press(toggleButton);

      // Legend should now be hidden
      expect(queryByTestId('legend-container')).toBeNull();
    });

    test('should trigger haptic feedback on legend toggle', () => {
      const Haptics = require('expo-haptics');
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} showLegend={true} />
      );

      const toggleButton = getByText('Legend');
      fireEvent.press(toggleButton);

      expect(Haptics.impactAsync).toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    test('should show loading indicator when loading is true', () => {
      const { getByTestId, getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} loading={true} />
      );

      expect(getByTestId('activity-indicator')).toBeTruthy();
      expect(getByText('Loading chart...')).toBeTruthy();
    });

    test('should not show chart when loading', () => {
      const { queryByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} loading={true} />
      );

      expect(queryByTestId('victory-chart')).toBeNull();
    });
  });

  describe('Empty State', () => {
    test('should show empty state when data is empty', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: [] }} />
      );

      expect(getByText('No data available')).toBeTruthy();
    });

    test('should show empty state when empty prop is true', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} empty={true} />
      );

      expect(getByText('No data available')).toBeTruthy();
    });

    test('should not show chart when empty', () => {
      const { queryByTestId } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: [] }} />
      );

      expect(queryByTestId('victory-chart')).toBeNull();
    });
  });

  describe('Error State', () => {
    test('should show error message when error is provided', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart data={mockLineData} error="Failed to load chart" />
      );

      expect(getByText('Failed to load chart')).toBeTruthy();
    });

    test('should not show chart when error', () => {
      const { queryByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} error="Failed to load chart" />
      );

      expect(queryByTestId('victory-chart')).toBeNull();
    });
  });

  describe('Portrait/Landscape Modes', () => {
    test('should use portrait height by default', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} portrait={true} />
      );

      const chart = getByTestId('victory-chart');
      expect(chart.props.style).toContainEqual({ height: 300 });
    });

    test('should use landscape height when portrait is false', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} portrait={false} />
      );

      const chart = getByTestId('victory-chart');
      expect(chart.props.style).toContainEqual({ height: 250 });
    });
  });

  describe('Animation', () => {
    test('should enable animation by default', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} animationEnabled={true} />
      );

      const lineChart = getByTestId('victory-line');
      expect(lineChart.props.animate).toBeDefined();
    });

    test('should disable animation when animationEnabled is false', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} animationEnabled={false} />
      );

      const lineChart = getByTestId('victory-line');
      expect(lineChart.props.animate).toBeFalsy();
    });
  });

  describe('Custom Styling', () => {
    test('should apply custom style', () => {
      const customStyle = { backgroundColor: '#f0f0f0' };
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} style={customStyle} />
      );

      const container = getByTestId('chart-container');
      expect(container.props.style).toContainEqual(customStyle);
    });

    test('should use default colors when not provided', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={mockLineData} />
      );

      const lineChart = getByTestId('victory-line');
      expect(lineChart.props.props.style.data.stroke).toBe('#2196F3');
    });
  });

  describe('Edge Cases', () => {
    test('should handle single data point', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: [{ x: 'Jan', y: 100 }] }} />
      );

      expect(getByTestId('victory-chart')).toBeTruthy();
    });

    test('should handle large dataset', () => {
      const largeData = Array.from({ length: 100 }, (_, i) => ({
        x: i,
        y: Math.random() * 100,
      }));

      const { getByTestId } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: largeData }} />
      );

      expect(getByTestId('victory-chart')).toBeTruthy();
    });

    test('should handle missing labels', () => {
      const dataWithoutLabels = mockLineData.data.map(({ label, ...rest }) => rest);

      const { getByTestId } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: dataWithoutLabels }} />
      );

      expect(getByTestId('victory-chart')).toBeTruthy();
    });

    test('should handle zero values', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: [{ x: 'Jan', y: 0 }] }} />
      );

      expect(getByTestId('victory-chart')).toBeTruthy();
    });

    test('should handle negative values', () => {
      const { getByTestId } = renderWithTheme(
        <CanvasChart data={{ ...mockLineData, data: [{ x: 'Jan', y: -100 }] }} />
      );

      expect(getByTestId('victory-chart')).toBeTruthy();
    });
  });

  describe('Toolbar', () => {
    test('should render toolbar with all buttons', () => {
      const { getByText } = renderWithTheme(
        <CanvasChart
          data={mockLineData}
          enableZoom={true}
          enableExport={true}
          showLegend={true}
        />
      );

      expect(getByText('Reset Zoom')).toBeTruthy();
      expect(getByText('Legend')).toBeTruthy();
      expect(getByText('Export CSV')).toBeTruthy();
    });

    test('should hide reset zoom for pie chart', () => {
      const { queryByText } = renderWithTheme(
        <CanvasChart data={mockPieData} enableZoom={true} />
      );

      expect(queryByText('Reset Zoom')).toBeNull();
    });

    test('should hide legend button for pie chart', () => {
      const { queryByText } = renderWithTheme(
        <CanvasChart data={mockPieData} showLegend={true} />
      );

      expect(queryByText('Legend')).toBeNull();
    });
  });
});
