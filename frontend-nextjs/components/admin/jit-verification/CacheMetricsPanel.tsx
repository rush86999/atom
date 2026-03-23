import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Database,
  TrendingUp,
  TrendingDown,
  Activity,
  HardDrive,
  Zap,
} from "lucide-react";
import type { CacheStatsResponse } from "@/types/jit-verification";

interface CacheMetricsPanelProps {
  stats: CacheStatsResponse;
}

/**
 * Cache Metrics Panel Component
 *
 * Displays comprehensive cache performance metrics including hit rates,
 * cache size, evictions, and latency information.
 */
export const CacheMetricsPanel: React.FC<CacheMetricsPanelProps> = ({
  stats,
}) => {
  const formatPercentage = (value: number): string => {
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatNumber = (value: number): string => {
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}k`;
    }
    return value.toString();
  };

  const getHitRateColor = (rate: number): string => {
    if (rate >= 0.8) return "text-green-600";
    if (rate >= 0.5) return "text-yellow-600";
    return "text-red-600";
  };

  const getHitRateBg = (rate: number): string => {
    if (rate >= 0.8) return "bg-green-500/20";
    if (rate >= 0.5) return "bg-yellow-500/20";
    return "bg-red-500/20";
  };

  const getTrendIcon = (rate: number) => {
    if (rate >= 0.8) return <TrendingUp className="h-4 w-4 text-green-600" />;
    if (rate >= 0.5) return <Activity className="h-4 w-4 text-yellow-600" />;
    return <TrendingDown className="h-4 w-4 text-red-600" />;
  };

  const verificationRate = stats.l1_verification_hit_rate;
  const queryRate = stats.l1_query_hit_rate;
  const overallRate = (verificationRate + queryRate) / 2;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5 text-purple-600" />
              Cache Performance
            </CardTitle>
            <CardDescription>
              Real-time cache metrics and performance indicators
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {stats.l2_enabled && (
              <Badge className="bg-green-500/20 text-green-600 border-green-500/50">
                L2 Active
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Hit Rates Section */}
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Hit Rates
            </h4>

            {/* Overall Hit Rate */}
            <div className="space-y-2">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Overall Hit Rate</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${getHitRateColor(overallRate)}`}>
                      {formatPercentage(overallRate)}
                    </span>
                    {getTrendIcon(overallRate)}
                  </div>
                </div>
                <Progress value={overallRate * 100} className="h-3" />
              </div>

              {/* Verification Cache Hit Rate */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground">L1 Verification</span>
                    <span className={`font-medium ${getHitRateColor(verificationRate)}`}>
                      {formatPercentage(verificationRate)}
                    </span>
                  </div>
                  <Progress value={verificationRate * 100} className="h-2" />
                  <div className="flex items-center justify-between text-xs mt-1">
                    <span className="text-muted-foreground">Hits: {formatNumber(stats.l1_verification_hits)}</span>
                    <span className="text-muted-foreground">Misses: {formatNumber(stats.l1_verification_misses)}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-muted-foreground">L1 Query</span>
                    <span className={`font-medium ${getHitRateColor(queryRate)}`}>
                      {formatPercentage(queryRate)}
                    </span>
                  </div>
                  <Progress value={queryRate * 100} className="h-2" />
                  <div className="flex items-center justify-between text-xs mt-1">
                    <span className="text-muted-foreground">Hits: {formatNumber(stats.l1_query_hits)}</span>
                    <span className="text-muted-foreground">Misses: {formatNumber(stats.l1_query_misses)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Cache Size Section */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium flex items-center gap-2">
            <HardDrive className="h-4 w-4" />
            Cache Size
          </h4>

          <div className="grid grid-cols-2 gap-4">
            {/* Verification Cache */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Verification Cache</span>
                <Badge variant="secondary" className="text-xs">
                  {formatNumber(stats.l1_verification_cache_size)}
                </Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Max Size</span>
                <span className="font-mono text-xs">10k</span>
              </div>
              <Progress
                value={(stats.l1_verification_cache_size / 10000) * 100}
                className="h-1.5"
              />
            </div>

            {/* Query Cache */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Query Cache</span>
                <Badge variant="secondary" className="text-xs">
                  {formatNumber(stats.l1_query_cache_size)}
                </Badge>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Max Size</span>
                <span className="font-mono text-xs">2.5k</span>
              </div>
              <Progress
                value={(stats.l1_query_cache_size / 2500) * 100}
                className="h-1.5"
              />
            </div>
          </div>

          {/* Cache Utilization Badge */}
          <div className="flex items-center justify-between p-3 bg-secondary/20 rounded-lg">
            <span className="text-xs text-muted-foreground">Total Utilization</span>
            <Badge
              variant={stats.l1_verification_cache_size / 10000 > 0.8 ? "destructive" : "secondary"}
            >
              {formatNumber(stats.l1_verification_cache_size + stats.l1_query_cache_size)} entries
            </Badge>
          </div>
        </div>

        {/* Evictions Section */}
        {stats.l1_evictions > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium flex items-center gap-2">
              <Zap className="h-4 w-4" />
              Cache Evictions
            </h4>

            <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-yellow-800">
                  Cache Evictions Active
                </span>
                <Badge className="bg-yellow-500/20 text-yellow-600 border-yellow-500/50">
                  {formatNumber(stats.l1_evictions)} evicted
                </Badge>
              </div>
              <p className="text-xs text-yellow-700">
                LRU cache is evicting entries to maintain size limits. Consider increasing max size if evictions are frequent.
              </p>
            </div>
          </div>
        )}

        {/* Performance Indicators */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium">Performance Indicators</h4>

          <div className="grid grid-cols-3 gap-3">
            {/* Verification Cache Performance */}
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Verification Perf</p>
              <p className={`text-sm font-semibold ${getHitRateColor(verificationRate)}`}>
                {verificationRate >= 0.8 ? "Excellent" : verificationRate >= 0.5 ? "Good" : "Fair"}
              </p>
              <Progress value={verificationRate * 100} className="h-1" />
            </div>

            {/* Query Cache Performance */}
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Query Perf</p>
              <p className={`text-sm font-semibold ${getHitRateColor(queryRate)}`}>
                {queryRate >= 0.8 ? "Excellent" : queryRate >= 0.5 ? "Good" : "Fair"}
              </p>
              <Progress value={queryRate * 100} className="h-1" />
            </div>

            {/* Overall Performance */}
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Overall Perf</p>
              <p className={`text-sm font-semibold ${getHitRateColor(overallRate)}`}>
                {overallRate >= 0.8 ? "Excellent" : overallRate >= 0.5 ? "Good" : "Fair"}
              </p>
              <Progress value={overallRate * 100} className="h-1" />
            </div>
          </div>
        </div>

        {/* L2 Cache Status */}
        <div className="pt-4 border-t">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-medium">L2 Redis Cache</h4>
              <p className="text-xs text-muted-foreground">
                Distributed cache for multiple instances
              </p>
            </div>
            <div className="flex items-center gap-2">
              {stats.l2_enabled ? (
                <Badge className="bg-green-500/20 text-green-600 border-green-500/50">
                  <Zap className="h-3 w-3 mr-1" />
                  Enabled
                </Badge>
              ) : (
                <Badge className="bg-gray-500/20 text-gray-600 border-gray-500/50">
                  Disabled
                </Badge>
              )}
            </div>
          </div>

          {stats.l2_enabled && (
            <p className="text-xs text-muted-foreground mt-2">
              L2 cache provides shared cache across instances with 1-hour TTL for verification results and 30-minute TTL for queries.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
