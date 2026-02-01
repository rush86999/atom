/**
 * Version Comparison Metrics Component
 *
 * Displays performance metrics comparison across workflow versions.
 * Shows execution count, success rate, execution time, and performance score.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Zap,
  BarChart3,
  GitCommit,
  Calendar,
  RefreshCw,
  Download,
  ArrowUpDown,
  Minus,
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

// Types
interface VersionMetrics {
  workflow_id: string;
  version: string;
  execution_count: number;
  success_rate: number;
  avg_execution_time: number;
  error_count: number;
  last_execution: string | null;
  performance_score: number;
}

interface VersionComparisonMetricsProps {
  workflowId: string;
  workflowName: string;
  versions: string[];
  onVersionSelect?: (version: string) => void;
}

// Metric card component
interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  unit?: string;
  color?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  icon,
  trend,
  trendValue,
  unit = '',
  color = 'text-foreground',
}) => (
  <div className="border rounded-lg p-4">
    <div className="flex items-center justify-between mb-2">
      <span className="text-sm text-muted-foreground">{title}</span>
      <div className={color}>{icon}</div>
    </div>
    <div className="flex items-end justify-between">
      <div>
        <p className={`text-2xl font-bold ${color}`}>
          {value}
          {unit && <span className="text-sm font-normal text-muted-foreground ml-1">{unit}</span>}
        </p>
      </div>
      {trend && trendValue && (
        <div
          className={`flex items-center gap-1 text-sm ${
            trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-muted-foreground'
          }`}
        >
          {trend === 'up' && <TrendingUp className="h-4 w-4" />}
          {trend === 'down' && <TrendingDown className="h-4 w-4" />}
          {trend === 'neutral' && <Minus className="h-4 w-4" />}
          <span>{trendValue}</span>
        </div>
      )}
    </div>
  </div>
);

export const VersionComparisonMetrics: React.FC<VersionComparisonMetricsProps> = ({
  workflowId,
  workflowName,
  versions,
  onVersionSelect,
}) => {
  const { toast } = useToast();

  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<Record<string, VersionMetrics>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedVersions.length > 0) {
      fetchMetrics();
    }
  }, [selectedVersions]);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);

      const metricsData: Record<string, VersionMetrics> = {};

      await Promise.all(
        selectedVersions.map(async (version) => {
          try {
            const response = await fetch(
              `/api/v1/workflows/${workflowId}/versions/${version}/metrics`
            );

            if (!response.ok) {
              // Version might not have metrics yet
              metricsData[version] = {
                workflow_id: workflowId,
                version: version,
                execution_count: 0,
                success_rate: 0,
                avg_execution_time: 0,
                error_count: 0,
                last_execution: null,
                performance_score: 0,
              };
              return;
            }

            const data = await response.json();
            metricsData[version] = data.metrics || {
              workflow_id: workflowId,
              version: version,
              execution_count: 0,
              success_rate: 0,
              avg_execution_time: 0,
              error_count: 0,
              last_execution: null,
              performance_score: 0,
            };
          } catch (err) {
            console.error(`Error fetching metrics for version ${version}:`, err);
          }
        })
      );

      setMetrics(metricsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      toast({
        title: 'Error',
        description: 'Failed to fetch version metrics',
        variant: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleVersionToggle = (version: string) => {
    if (selectedVersions.includes(version)) {
      setSelectedVersions(selectedVersions.filter((v) => v !== version));
    } else {
      if (selectedVersions.length >= 4) {
        toast({
          title: 'Maximum Reached',
          description: 'You can compare up to 4 versions at a time',
          variant: 'error',
        });
        return;
      }
      setSelectedVersions([...selectedVersions, version]);
    }
  };

  const calculateTrend = (currentValue: number, previousValue: number): 'up' | 'down' | 'neutral' => {
    if (previousValue === 0) return 'neutral';
    const change = ((currentValue - previousValue) / previousValue) * 100;
    if (Math.abs(change) < 5) return 'neutral';
    return change > 0 ? 'up' : 'down';
  };

  const getTrendValue = (currentValue: number, previousValue: number): string => {
    if (previousValue === 0) return '';
    const change = Math.abs(((currentValue - previousValue) / previousValue) * 100).toFixed(1);
    return `${change}%`;
  };

  const getPerformanceColor = (score: number): string => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const exportMetrics = () => {
    const data = JSON.stringify(metrics, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflowName}_metrics_comparison.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: 'Exported',
      description: 'Metrics comparison exported successfully',
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Version Performance Comparison
            </CardTitle>
            <CardDescription>{workflowName}</CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {selectedVersions.length > 0 && (
              <Button variant="outline" size="sm" onClick={fetchMetrics} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            )}

            {Object.keys(metrics).length > 0 && (
              <Button variant="outline" size="sm" onClick={exportMetrics}>
                <Download className="h-4 w-4 mr-2" />
                Export
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Version Selector */}
        <div>
          <label className="text-sm font-medium mb-2 block">Select Versions to Compare</label>
          <ScrollArea className="h-[150px] border rounded-lg p-3">
            <div className="flex flex-wrap gap-2">
              {versions.map((version) => {
                const isSelected = selectedVersions.includes(version);
                const hasMetrics = metrics[version];

                return (
                  <Badge
                    key={version}
                    variant={isSelected ? 'default' : 'outline'}
                    className={`cursor-pointer transition-all ${
                      isSelected ? 'shadow-md' : 'hover:bg-muted'
                    }`}
                    onClick={() => handleVersionToggle(version)}
                  >
                    <GitCommit className="h-3 w-3 mr-1" />
                    v{version}
                    {hasMetrics && <CheckCircle className="h-3 w-3 ml-1" />}
                  </Badge>
                );
              })}
            </div>
          </ScrollArea>
          <p className="text-xs text-muted-foreground mt-1">
            {selectedVersions.length} version{selectedVersions.length !== 1 ? 's' : ''} selected
          </p>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Loading metrics...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="p-4 border border-destructive rounded-lg text-destructive">
            <p>{error}</p>
          </div>
        )}

        {/* Metrics Comparison */}
        {selectedVersions.length > 0 && !loading && !error && (
          <div className="space-y-6">
            {/* Performance Score Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {selectedVersions.map((version) => {
                const metric = metrics[version];
                if (!metric) return null;

                const color = getPerformanceColor(metric.performance_score);

                return (
                  <MetricCard
                    key={version}
                    title={`v${version}`}
                    value={metric.performance_score.toFixed(1)}
                    icon={<Zap className={`h-5 w-5 ${color}`} />}
                    trend={
                      selectedVersions.length > 1
                        ? calculateTrend(
                            metric.performance_score,
                            metrics[selectedVersions[0]].performance_score
                          )
                        : undefined
                    }
                    trendValue={
                      selectedVersions.length > 1
                        ? getTrendValue(
                            metric.performance_score,
                            metrics[selectedVersions[0]].performance_score
                          )
                        : undefined
                    }
                    color={color}
                  />
                );
              })}
            </div>

            {/* Detailed Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {selectedVersions.map((version) => {
                const metric = metrics[version];
                if (!metric) return null;

                return (
                  <div key={version} className="border rounded-lg p-4 space-y-4">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b pb-3">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono">
                          v{version}
                        </Badge>
                        <h4 className="font-semibold">Metrics</h4>
                      </div>
                      {metric.last_execution && (
                        <div className="text-xs text-muted-foreground flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {new Date(metric.last_execution).toLocaleDateString()}
                        </div>
                      )}
                    </div>

                    {/* Execution Count */}
                    <MetricCard
                      title="Total Executions"
                      value={metric.execution_count}
                      icon={<Activity className="h-5 w-5 text-blue-500" />}
                      trend={
                        selectedVersions.length > 1
                          ? calculateTrend(
                              metric.execution_count,
                              metrics[selectedVersions[0]].execution_count
                            )
                          : undefined
                      }
                      trendValue={
                        selectedVersions.length > 1
                          ? getTrendValue(
                              metric.execution_count,
                              metrics[selectedVersions[0]].execution_count
                            )
                          : undefined
                      }
                    />

                    {/* Success Rate */}
                    <MetricCard
                      title="Success Rate"
                      value={metric.success_rate.toFixed(1)}
                      icon={<CheckCircle className="h-5 w-5 text-green-500" />}
                      trend={
                        selectedVersions.length > 1
                          ? calculateTrend(
                              metric.success_rate,
                              metrics[selectedVersions[0]].success_rate
                            )
                          : undefined
                      }
                      trendValue={
                        selectedVersions.length > 1
                          ? getTrendValue(
                              metric.success_rate,
                              metrics[selectedVersions[0]].success_rate
                            )
                          : undefined
                      }
                      unit="%"
                    />

                    {/* Average Execution Time */}
                    <MetricCard
                      title="Avg Execution Time"
                      value={metric.avg_execution_time.toFixed(2)}
                      icon={<Clock className="h-5 w-5 text-orange-500" />}
                      trend={
                        selectedVersions.length > 1
                          ? calculateTrend(
                              metric.avg_execution_time,
                              metrics[selectedVersions[0]].avg_execution_time
                            )
                          : undefined
                      }
                      trendValue={
                        selectedVersions.length > 1
                          ? getTrendValue(
                              metric.avg_execution_time,
                              metrics[selectedVersions[0]].avg_execution_time
                            )
                          : undefined
                      }
                      unit="s"
                    />

                    {/* Error Count */}
                    <MetricCard
                      title="Errors"
                      value={metric.error_count}
                      icon={<XCircle className="h-5 w-5 text-red-500" />}
                      trend={
                        selectedVersions.length > 1
                          ? calculateTrend(
                              metric.error_count,
                              metrics[selectedVersions[0]].error_count
                            )
                          : undefined
                      }
                      trendValue={
                        selectedVersions.length > 1
                          ? getTrendValue(
                              metric.error_count,
                              metrics[selectedVersions[0]].error_count
                            )
                          : undefined
                      }
                    />

                    {/* Action Button */}
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => onVersionSelect?.(version)}
                    >
                      View Version Details
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Empty State */}
        {selectedVersions.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <BarChart3 className="h-16 w-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No Versions Selected</p>
            <p className="text-sm">Select one or more versions above to compare their performance metrics</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default VersionComparisonMetrics;
