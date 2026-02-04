/**
 * Mobile Execution Chart Component
 * Touch-friendly chart for visualizing execution metrics
 */

import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import {
  VictoryChart,
  VictoryLine,
  VictoryArea,
  VictoryAxis,
  VictoryTheme,
  VictoryLegend,
  VictoryVoronoiContainer,
} from 'victory-native';
import { ExecutionTimelineData } from '../../types/analytics';

interface ExecutionChartProps {
  data: ExecutionTimelineData[];
  height?: number;
  showLegend?: boolean;
}

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export const ExecutionChart: React.FC<ExecutionChartProps> = ({
  data,
  height = 200,
  showLegend = true,
}) => {
  if (data.length === 0) {
    return (
      <View style={[styles.container, { height }]}>
        <Text style={styles.emptyText}>No data available</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <VictoryChart
        theme={VictoryTheme.material}
        containerComponent={<VictoryVoronoiContainer />}
        height={height}
        width={SCREEN_WIDTH - 32}
        padding={{ left: 50, right: 30, top: 30, bottom: 50 }}
      >
        <VictoryArea
          data={data}
          x="timestamp"
          y="success_count"
          style={{
            data: { fill: '#4CAF50', fillOpacity: 0.3 },
          }}
        />
        <VictoryLine
          data={data}
          x="timestamp"
          y="success_count"
          style={{
            data: { stroke: '#4CAF50', strokeWidth: 2 },
          }}
        />
        <VictoryArea
          data={data}
          x="timestamp"
          y="failure_count"
          style={{
            data: { fill: '#f44336', fillOpacity: 0.3 },
          }}
        />
        <VictoryLine
          data={data}
          x="timestamp"
          y="failure_count"
          style={{
            data: { stroke: '#f44336', strokeWidth: 2 },
          }}
        />
        <VictoryAxis
          dependentAxis
          label="Executions"
          style={{
            axisLabel: { fontSize: 12, padding: 30 },
            tickLabels: { fontSize: 10 },
          }}
        />
        <VictoryAxis
          tickFormat={(tick) => {
            const date = new Date(tick);
            const hours = date.getHours();
            const minutes = date.getMinutes().toString().padStart(2, '0');
            return `${hours}:${minutes}`;
          }}
          style={{
            tickLabels: { fontSize: 10, angle: -45, padding: 5 },
          }}
        />
        {showLegend && (
          <VictoryLegend
            x={SCREEN_WIDTH / 2 - 60}
            y={10}
            orientation="horizontal"
            gutter={20}
            style={{
              labels: { fontSize: 12 },
            }}
            data={[
              { name: 'Success', symbol: { fill: '#4CAF50' } },
              { name: 'Failure', symbol: { fill: '#f44336' } },
            ]}
          />
        )}
      </VictoryChart>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 8,
    marginVertical: 8,
  },
  emptyText: {
    fontSize: 14,
    color: '#999',
    textAlign: 'center',
    paddingVertical: 20,
  },
});

export default ExecutionChart;
