/**
 * CanvasChart Component
 *
 * Mobile-optimized chart component using Victory Native with touch interactions.
 * Supports line, bar, and pie charts with pinch-to-zoom, pan, and data export.
 */

import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Text,
  ActivityIndicator,
  ScrollView,
  Dimensions,
  GestureResponderEvent,
  Pressable,
} from 'react-native';
import { useTheme } from 'react-native-paper';
import * as Haptics from 'expo-haptics';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

import {
  VictoryChart,
  VictoryLine,
  VictoryBar,
  VictoryPie,
  VictoryAxis,
  VictoryTooltip,
  VictoryVoronoiContainer,
  VictoryZoomContainer,
  VictorySelectionContainer,
  VictoryTheme,
  VictoryLabel,
} from 'victory-native';

const { width: screenWidth } = Dimensions.get('window');

// Types
export type ChartType = 'line' | 'bar' | 'pie';

export interface ChartDataPoint {
  x: string | number;
  y: number;
  label?: string;
}

export interface ChartData {
  type: ChartType;
  title?: string;
  data: ChartDataPoint[];
  xKey?: string;
  yKeys?: string[];
  colors?: string[];
  showLegend?: boolean;
  xAxisLabel?: string;
  yAxisLabel?: string;
  gridEnabled?: boolean;
  animationEnabled?: boolean;
}

type NumericDomain = [number, number];
type DateDomain = [Date, Date];
type ChartZoomDomain = {
  x: NumericDomain | DateDomain;
  y: NumericDomain | DateDomain;
};

interface VictoryPoint {
  x?: string | number;
  y?: number;
  label?: string | number;
  datum?: VictoryPoint;
  index?: number | string;
  _x?: string | number;
  _y?: number;
}

interface PointPressEvent {
  target: 'data';
  eventHandlers: {
    onPressIn: (event: unknown, props?: VictoryPoint) => void;
  };
}

const toNumericDomain = (
  domain: NumericDomain | DateDomain,
): NumericDomain => [Number(domain[0]), Number(domain[1])];

const isVictoryPoint = (value: unknown): value is VictoryPoint =>
  typeof value === 'object' &&
  value !== null &&
  ('x' in value || 'datum' in value || '_x' in value);

const getPointFromProps = (props?: VictoryPoint): ChartDataPoint | null => {
  const source = props?.datum ?? props;
  const x = source?.x ?? source?._x ?? props?.x ?? props?._x;
  const y = source?.y ?? source?._y ?? props?.y ?? props?._y;

  if (x === undefined || y === undefined) {
    return null;
  }

  const label = source?.label ?? props?.label;
  return {
    x,
    y,
    label: label !== undefined ? String(label) : String(x),
  };
};

interface CanvasChartProps {
  data: ChartData;
  style?: any;
  onPointPress?: (point: ChartDataPoint) => void;
  onZoomChange?: (zoom: { x: number[]; y: number[] }) => void;
  enableZoom?: boolean;
  enablePan?: boolean;
  enableExport?: boolean;
  portrait?: boolean;
  loading?: boolean;
  empty?: boolean;
  error?: string;
}

/**
 * CanvasChart Component
 *
 * Renders interactive charts with touch gestures, tooltips, and export functionality.
 */
export const CanvasChart: React.FC<CanvasChartProps> = ({
  data,
  style,
  onPointPress,
  onZoomChange,
  enableZoom = true,
  enablePan = true,
  enableExport = true,
  portrait = true,
  loading = false,
  empty = false,
  error = null,
}) => {
  const theme = useTheme();
  const chartRef = useRef<any>(null);

  const [showLegend, setShowLegend] = useState(data.showLegend !== false);
  const [tooltipData, setTooltipData] = useState<ChartDataPoint | null>(null);
  const [zoomDomain, setZoomDomain] = useState<ChartZoomDomain | undefined>();
  const [isExporting, setIsExporting] = useState(false);

  const chartColors = data.colors || [
    theme.colors.primary || '#2196F3',
    '#FF9800',
    '#4CAF50',
    '#9C27B0',
    '#F44336',
  ];

  /**
   * Handle tap on chart point
   */
  const handlePointPress = useCallback((props?: VictoryPoint) => {
    const dataPoint = getPointFromProps(props);
    if (!dataPoint) return;

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    setTooltipData(dataPoint);
    onPointPress?.(dataPoint);
  }, [onPointPress]);

  /**
   * Native data-point event handler. React Native SVG exposes press events
   * directly on the data primitive, so Victory passes the touched point as the
   * second argument to an event handler declared in the `events` contract.
   */
  const handlePointEvent = useCallback((eventOrProps: unknown, props?: VictoryPoint) => {
    if (props) {
      handlePointPress(props);
    } else if (isVictoryPoint(eventOrProps)) {
      handlePointPress(eventOrProps);
    }
  }, [handlePointPress]);

  /**
   * Native Voronoi activation callback. Victory's native Voronoi consumer
   * reports the active data point(s) here after a touch starts or moves.
   */
  const handlePointsActivated = useCallback((points: VictoryPoint[]) => {
    if (points.length > 0) {
      handlePointPress(points[0]);
    }
  }, [handlePointPress]);

  /**
   * Long-press for context menu
   */
  const handleLongPress = useCallback((event: GestureResponderEvent) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    // Could show context menu here
  }, []);

  /**
   * Apply a zoom domain from Victory. Victory domains may contain Dates for
   * time-series charts, while the public CanvasChart callback stays numeric.
   */
  const handleZoomDomainChange = useCallback((domain: ChartZoomDomain) => {
    setZoomDomain(domain);
    onZoomChange?.({
      x: toNumericDomain(domain.x),
      y: toNumericDomain(domain.y),
    });
  }, [onZoomChange]);

  /**
   * Reset zoom
   */
  const resetZoom = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setZoomDomain(undefined);
    onZoomChange?.({ x: [0, 1], y: [0, 1] });
  }, [onZoomChange]);

  const pointPressEvents: PointPressEvent[] = [
    {
      target: 'data',
      eventHandlers: {
        onPressIn: handlePointEvent,
      },
    },
  ];

  /**
   * Export chart data as CSV
   */
  const exportCSV = useCallback(async () => {
    if (!enableExport || data.data.length === 0) return;

    try {
      setIsExporting(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      // Generate CSV content
      const headers = ['X', 'Y', 'Label'];
      const rows = data.data.map(point => [
        String(point.x),
        String(point.y),
        point.label || '',
      ]);

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
      ].join('\n');

      // Write to file
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `chart-data-${timestamp}.csv`;
      const fileUri = FileSystem.documentDirectory + filename;

      await FileSystem.writeAsStringAsync(fileUri, csvContent, {
        encoding: FileSystem.EncodingType.UTF8,
      });

      // Share file
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(fileUri, {
          mimeType: 'text/csv',
          dialogTitle: 'Export Chart Data',
        });
      }
    } catch (err) {
      console.error('Failed to export chart:', err);
    } finally {
      setIsExporting(false);
    }
  }, [data, enableExport]);

  /**
   * Toggle legend visibility
   */
  const toggleLegend = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setShowLegend(prev => !prev);
  }, []);

  // Loading state
  if (loading) {
    return (
      <View style={[styles.container, style]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator testID="activity-indicator" size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.colors.onSurface }]}>
            Loading chart...
          </Text>
        </View>
      </View>
    );
  }

  // Empty state
  if (empty || data.data.length === 0) {
    return (
      <View style={[styles.container, style]}>
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: theme.colors.onSurface }]}>
            No data available
          </Text>
        </View>
      </View>
    );
  }

  // Error state
  if (error) {
    return (
      <View style={[styles.container, style]}>
        <View style={styles.errorContainer}>
          <Text style={[styles.errorText, { color: theme.colors.error }]}>
            {error}
          </Text>
        </View>
      </View>
    );
  }

  /**
   * Render line chart
   */
  const renderLineChart = () => (
    <VictoryChart
      theme={VictoryTheme.material}
      containerComponent={
        enableZoom || enablePan ? (
          <VictoryZoomContainer
            zoomDimension="x"
            zoomDomain={zoomDomain}
            onZoomDomainChange={handleZoomDomainChange}
          />
        ) : (
          <VictoryVoronoiContainer
            labels={({ datum }) => `${datum.x}: ${datum.y}`}
            labelComponent={
              <VictoryTooltip
                flyoutStyle={{
                  fill: theme.colors.surface,
                  stroke: theme.colors.outline,
                  strokeWidth: 1,
                }}
                style={{ fill: theme.colors.onSurface, fontSize: 12 }}
              />
            }
            onActivated={handlePointsActivated}
          />
        )
      }
    >
      <VictoryAxis
        label={data.xAxisLabel}
        style={{
          axisLabel: { padding: 30, fontSize: 12, fill: theme.colors.onSurface },
          tickLabels: { fontSize: 10, fill: theme.colors.onSurface },
        }}
      />
      <VictoryAxis
        dependentAxis
        label={data.yAxisLabel}
        style={{
          axisLabel: { padding: 35, fontSize: 12, fill: theme.colors.onSurface },
          tickLabels: { fontSize: 10, fill: theme.colors.onSurface },
        }}
      />
      <VictoryLine
        data={data.data}
        style={{
          data: {
            stroke: chartColors[0],
            strokeWidth: 2,
          },
          labels: { fontSize: 10 },
        }}
        animate={data.animationEnabled !== false ? { duration: 500 } : false}
      />
    </VictoryChart>
  );

  /**
   * Render bar chart
   */
  const renderBarChart = () => (
    <VictoryChart
      theme={VictoryTheme.material}
      containerComponent={
        <VictoryVoronoiContainer
          labels={({ datum }) => `${datum.x}: ${datum.y}`}
          labelComponent={
            <VictoryTooltip
              flyoutStyle={{
                fill: theme.colors.surface,
                stroke: theme.colors.outline,
                strokeWidth: 1,
              }}
              style={{ fill: theme.colors.onSurface, fontSize: 12 }}
            />
          }
          onActivated={handlePointsActivated}
        />
      }
    >
      <VictoryAxis
        label={data.xAxisLabel}
        style={{
          axisLabel: { padding: 30, fontSize: 12, fill: theme.colors.onSurface },
          tickLabels: { fontSize: 10, fill: theme.colors.onSurface },
        }}
      />
      <VictoryAxis
        dependentAxis
        label={data.yAxisLabel}
        style={{
          axisLabel: { padding: 35, fontSize: 12, fill: theme.colors.onSurface },
          tickLabels: { fontSize: 10, fill: theme.colors.onSurface },
        }}
      />
      <VictoryBar
        data={data.data}
        style={{
          data: {
            fill: ({ index }) => {
              const numericIndex =
                typeof index === 'number' ? index : Number(index);
              const colorIndex = Number.isFinite(numericIndex)
                ? Math.abs(numericIndex) % chartColors.length
                : 0;
              return chartColors[colorIndex];
            },
          },
          labels: { fontSize: 10 },
        }}
        animate={data.animationEnabled !== false ? { duration: 500 } : false}
      />
    </VictoryChart>
  );

  /**
   * Render pie chart
   */
  const renderPieChart = () => (
    <VictoryPie
      data={data.data}
      colorScale={chartColors}
      labels={({ datum }) => `${datum.x}: ${datum.y}`}
      labelComponent={
        <VictoryTooltip
          flyoutStyle={{
            fill: theme.colors.surface,
            stroke: theme.colors.outline,
            strokeWidth: 1,
          }}
          style={{ fill: theme.colors.onSurface, fontSize: 12 }}
        />
      }
      style={{
        labels: {
          fontSize: 10,
          fill: theme.colors.onSurface,
        },
      }}
      events={pointPressEvents}
      animate={data.animationEnabled !== false ? { duration: 500 } : false}
    />
  );

  /**
   * Render legend
   */
  const renderLegend = () => {
    if (!showLegend || data.type === 'pie') return null;

    return (
      <View testID="legend-container" style={styles.legendContainer}>
        {data.data.map((point, index) => (
          <TouchableOpacity
            key={index}
            style={styles.legendItem}
            onPress={() => handlePointPress(point)}
          >
            <View
              style={[
                styles.legendColor,
                { backgroundColor: chartColors[index % chartColors.length] },
              ]}
            />
            <Text style={[styles.legendLabel, { color: theme.colors.onSurface }]}>
              {point.label || String(point.x)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  /**
   * Render chart based on type
   */
  const renderChart = () => {
    const chartStyle = [
      styles.chart,
      portrait ? styles.chartPortrait : styles.chartLandscape,
    ];

    switch (data.type) {
      case 'line':
        return <View testID="chart-wrapper" style={chartStyle}>{renderLineChart()}</View>;
      case 'bar':
        return <View testID="chart-wrapper" style={chartStyle}>{renderBarChart()}</View>;
      case 'pie':
        return <View testID="chart-wrapper" style={chartStyle}>{renderPieChart()}</View>;
      default:
        return <View testID="chart-wrapper" style={chartStyle}>{renderLineChart()}</View>;
    }
  };

  return (
    <View testID="chart-container" style={[styles.container, style]}>
      {/* Title */}
      {data.title && (
        <Text style={[styles.title, { color: theme.colors.onSurface }]}>
          {data.title}
        </Text>
      )}

      {/* Toolbar */}
      <View style={styles.toolbar}>
        {enableZoom && data.type !== 'pie' && (
          <TouchableOpacity
            onPress={resetZoom}
            style={[styles.toolbarButton, { backgroundColor: theme.colors.surfaceVariant }]}
          >
            <Text style={[styles.toolbarButtonText, { color: theme.colors.primary }]}>
              Reset Zoom
            </Text>
          </TouchableOpacity>
        )}

        {showLegend && data.type !== 'pie' && (
          <TouchableOpacity
            onPress={toggleLegend}
            style={[styles.toolbarButton, { backgroundColor: theme.colors.surfaceVariant }]}
          >
            <Text style={[styles.toolbarButtonText, { color: theme.colors.primary }]}>
              Legend
            </Text>
          </TouchableOpacity>
        )}

        {enableExport && (
          <TouchableOpacity
            onPress={exportCSV}
            disabled={isExporting}
            style={[styles.toolbarButton, { backgroundColor: theme.colors.surfaceVariant }]}
          >
            <Text style={[styles.toolbarButtonText, { color: theme.colors.primary }]}>
              {isExporting ? 'Exporting...' : 'Export CSV'}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Chart */}
      <Pressable testID="chart-long-press" onLongPress={handleLongPress}>
        <ScrollView
          horizontal={data.type !== 'pie'}
          showsHorizontalScrollIndicator={true}
        >
          {renderChart()}
        </ScrollView>
      </Pressable>

      {/* Legend */}
      {renderLegend()}

      {/* Tooltip overlay */}
      {tooltipData && (
        <View
          testID="tooltip"
          style={[styles.tooltip, { backgroundColor: theme.colors.surface }]}
        >
          <Text style={[styles.tooltipText, { color: theme.colors.onSurface }]}>
            {tooltipData.label || tooltipData.x}: {tooltipData.y}
          </Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 8,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
  },
  toolbar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  toolbarButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    minWidth: 80,
    alignItems: 'center',
  },
  toolbarButtonText: {
    fontSize: 12,
    fontWeight: '600',
  },
  chart: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  chartPortrait: {
    height: 300,
  },
  chartLandscape: {
    height: 250,
  },
  legendContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 12,
    justifyContent: 'center',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
    marginBottom: 8,
  },
  legendColor: {
    width: 12,
    height: 12,
    borderRadius: 2,
    marginRight: 6,
  },
  legendLabel: {
    fontSize: 12,
  },
  tooltip: {
    position: 'absolute',
    top: 12,
    right: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 4,
  },
  tooltipText: {
    fontSize: 12,
    fontWeight: '500',
  },
  loadingContainer: {
    height: 300,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
  },
  emptyContainer: {
    height: 300,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyText: {
    fontSize: 16,
  },
  errorContainer: {
    height: 300,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorText: {
    fontSize: 14,
  },
});

export default CanvasChart;
