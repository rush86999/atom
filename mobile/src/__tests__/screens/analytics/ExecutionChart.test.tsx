/**
 * ExecutionChart Component Tests
 *
 * Coverage wave: ExecutionChart.tsx was at 0% — this suite brings it
 * past the 80% per-file threshold.
 *
 * jest.setup.js provides a bare View stand-in for victory-native; this
 * suite overrides it with a richer mock that actually invokes tickFormat
 * and renders legend labels so the chart's rendering logic is exercised.
 */

import React from 'react';
import { render } from '@testing-library/react-native';

jest.mock('victory-native', () => {
  const React = require('react');
  const { View, Text } = require('react-native');

  const MockVictory = (props: any) => React.createElement(View, props);

  const MockAxis = (props: any) => {
    const rendered = props.tickFormat
      ? [React.createElement(Text, { key: 'tick' }, props.tickFormat('2026-08-14T10:30:00Z'))]
      : [];
    return React.createElement(View, { ...props, children: rendered });
  };

  const MockLegend = (props: any) =>
    React.createElement(
      View,
      { ...props },
      (props.data || []).map((d: any) => React.createElement(Text, { key: d.name }, d.name))
    );

  return {
    VictoryChart: MockVictory,
    VictoryLine: MockVictory,
    VictoryArea: MockVictory,
    VictoryAxis: MockAxis,
    VictoryLegend: MockLegend,
    VictoryVoronoiContainer: MockVictory,
    VictoryTheme: { material: {} },
  };
});

import { ExecutionChart } from '../../../screens/analytics/ExecutionChart';
import { ExecutionTimelineData } from '../../../types/analytics';

const sampleData: ExecutionTimelineData[] = [
  {
    timestamp: '2026-08-14T10:00:00Z',
    count: 12,
    success_count: 10,
    failure_count: 2,
    average_duration_ms: 1200,
  },
  {
    timestamp: '2026-08-14T11:00:00Z',
    count: 8,
    success_count: 7,
    failure_count: 1,
    average_duration_ms: 980,
  },
];

describe('ExecutionChart', () => {
  test('renders "No data available" when data array is empty', () => {
    const { getByText } = render(<ExecutionChart data={[]} />);
    expect(getByText('No data available')).toBeTruthy();
  });

  test('renders "No data available" with custom height for empty data', () => {
    const { getByText, getByTestId } = render(<ExecutionChart data={[]} height={400} />);
    expect(getByText('No data available')).toBeTruthy();
    const container = getByTestId('execution-chart-empty');
    expect(container.props.style).toEqual(
      expect.arrayContaining([expect.objectContaining({ height: 400 })])
    );
  });

  test('renders chart with data, legend labels, and formatted time ticks', () => {
    const { getByTestId, getAllByText } = render(<ExecutionChart data={sampleData} />);
    expect(getByTestId('execution-chart')).toBeTruthy();

    // Legend rendered by default (showLegend = true)
    expect(getAllByText('Success').length).toBeGreaterThan(0);
    expect(getAllByText('Failure').length).toBeGreaterThan(0);

    // tickFormat produces "HH:MM" from an ISO timestamp
    const tick = getAllByText(/^\d{1,2}:\d{2}$/);
    expect(tick.length).toBeGreaterThan(0);
  });

  test('renders chart with custom height', () => {
    const { getByTestId } = render(<ExecutionChart data={sampleData} height={350} />);
    expect(getByTestId('execution-chart')).toBeTruthy();
  });

  test('omits legend when showLegend is false', () => {
    const { queryAllByText } = render(<ExecutionChart data={sampleData} showLegend={false} />);
    expect(queryAllByText('Success').length).toBe(0);
    expect(queryAllByText('Failure').length).toBe(0);
  });

  test('handles data with zero counts without crashing', () => {
    const zeroData: ExecutionTimelineData[] = [
      {
        timestamp: '2026-08-14T09:00:00Z',
        count: 0,
        success_count: 0,
        failure_count: 0,
        average_duration_ms: 0,
      },
    ];
    const { getByTestId } = render(<ExecutionChart data={zeroData} />);
    expect(getByTestId('execution-chart')).toBeTruthy();
  });
});
