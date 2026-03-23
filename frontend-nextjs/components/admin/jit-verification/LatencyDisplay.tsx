import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Clock,
  Zap,
  Database,
  TrendingDown,
} from "lucide-react";
import type { CacheStatsResponse } from "@/types/jit-verification";

interface LatencyDisplayProps {
  stats: CacheStatsResponse;
  l2Latency?: number; // Average L2 latency in ms (optional, from metrics)
  s3Latency?: number; // Average S3 check latency in ms (optional, from metrics)
}

/**
 * Latency Display Component
 *
 * Shows cache lookup latencies for different cache levels with visual indicators.
 */
export const LatencyDisplay: React.FC<LatencyDisplayProps> = ({
  stats,
  l2Latency = 5, // Default L2 latency
  s3Latency = 200, // Default S3 latency
}) => {
  const formatLatency = (ms: number): string => {
    if (ms < 1) {
      return `${(ms * 1000).toFixed(0)}µs`;
    }
    return `${ms.toFixed(1)}ms`;
  };

  const getLatencyColor = (ms: number): string => {
    if (ms < 1) return "text-green-600";
    if (ms < 10) return "text-blue-600";
    if (ms < 100) return "text-yellow-600";
    return "text-red-600";
  };

  const getLatencyBadge = (ms: number): "default" | "secondary" | "destructive" => {
    if (ms < 1) return "default";
    if (ms < 10) return "secondary";
    return "destructive";
  };

  const l1Latency = 0.027; // 27µs from backend
  const l2LatencyFormatted = formatLatency(l2Latency);
  const s3LatencyFormatted = formatLatency(s3Latency);

  // Calculate speedup factors
  const l1Speedup = s3Latency / l1Latency;
  const l2Speedup = s3Latency / l2Latency;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5 text-blue-600" />
          Cache Latency
        </CardTitle>
        <CardDescription>
          Lookup speed across cache levels
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* L1 Memory Cache */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-green-600" />
              <span className="text-sm font-medium">L1 Memory Cache</span>
            </div>
            <Badge className={getLatencyBadge(l1Latency)}>
              {formatLatency(l1Latency)}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Type:</span>
              <span className="ml-1 font-medium">In-Memory (LRU)</span>
            </div>
            <div>
              <span className="text-muted-foreground">TTL:</span>
              <span className="ml-1 font-medium">5 minutes</span>
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            <span className={getLatencyColor(l1Latency)}>
              ⚡ Ultra-fast lookup ({l1Speedup.toFixed(0)}x faster than S3)
            </span>
          </div>
        </div>

        {/* L2 Redis Cache */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-medium">L2 Redis Cache</span>
            </div>
            <Badge variant={stats.l2_enabled ? "default" : "secondary"}>
              {stats.l2_enabled ? l2LatencyFormatted : "Disabled"}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Type:</span>
              <span className="ml-1 font-medium">Distributed (Redis)</span>
            </div>
            <div>
              <span className="text-muted-foreground">TTL:</span>
              <span className="ml-1 font-medium">1 hour</span>
            </div>
          </div>

          {stats.l2_enabled && (
            <div className="text-xs text-muted-foreground">
              <span className={getLatencyColor(l2Latency)}>
                🚀 Fast lookup ({l2Speedup.toFixed(0)}x faster than S3)
              </span>
            </div>
          )}
        </div>

        {/* R2/S3 Storage */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-600" />
              <span className="text-sm font-medium">R2/S3 Storage</span>
            </div>
            <Badge variant="destructive">
              {s3LatencyFormatted}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Type:</span>
              <span className="ml-1 font-medium">Cloud Storage</span>
            </div>
            <div>
              <span className="text-muted-foreground">Operation:</span>
              <span className="ml-1 font-medium">head_object</span>
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            <span className={getLatencyColor(s3Latency)}>
              ⚠ Slow network I/O (cache miss penalty)
            </span>
          </div>
        </div>

        {/* Latency Comparison */}
        <div className="pt-4 border-t">
          <h4 className="text-sm font-medium mb-3">Latency Comparison</h4>

          <div className="space-y-3">
            {/* L1 vs L2 vs S3 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted-foreground">L1 Cache</span>
                <span className="font-mono font-medium">{formatLatency(l1Latency)}</span>
              </div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted-foreground">L2 Cache</span>
                <span className="font-mono font-medium">{stats.l2_enabled ? l2LatencyFormatted : "—"}</span>
              </div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted-foreground">R2/S3</span>
                <span className="font-mono font-medium">{s3LatencyFormatted}</span>
              </div>

              {/* Visual comparison bar */}
              <div className="relative h-8 bg-secondary rounded">
                <div
                  className="absolute left-0 top-0 h-full bg-green-500/60 rounded-l"
                  style={{ width: `${(l1Latency / s3Latency) * 100}%` }}
                  title={`L1: ${formatLatency(l1Latency)}`}
                />
                <div
                  className="absolute top-0 h-full bg-blue-500/60"
                  style={{
                    left: `${(l1Latency / s3Latency) * 100}%`,
                    width: `${(l2Latency / s3Latency) * 100}%`,
                  }}
                  title={`L2: ${stats.l2_enabled ? l2LatencyFormatted : "disabled"}`}
                />
                <div
                  className="absolute top-0 right-0 h-full bg-red-500/60 rounded-r"
                  style={{
                    left: `${((l1Latency + (stats.l2_enabled ? l2Latency : 0)) / s3Latency) * 100}%`,
                    width: `100% - ${((l1Latency + (stats.l2_enabled ? l2Latency : 0)) / s3Latency) * 100}%`,
                  }}
                  title={`R2/S3: ${s3LatencyFormatted}`}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Performance Tips */}
        <div className="pt-4 border-t">
          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <p className="text-sm font-medium text-blue-800 mb-2">
              💡 Performance Tip
            </p>
            <p className="text-xs text-blue-700">
              High L1 hit rate (&gt;85%) indicates excellent cache performance.
              Monitor L2 cache to ensure distributed instances are benefiting from shared cache.
            </p>
          </div>
        </div>

        {/* Speedup Summary */}
        <div className="pt-4 border-t">
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center p-3 bg-green-500/10 rounded-lg">
              <p className="text-2xl font-bold text-green-600">
                {l1Speedup.toFixed(0)}x
              </p>
              <p className="text-xs text-muted-foreground">L1 Speedup</p>
            </div>
            {stats.l2_enabled && (
              <div className="text-center p-3 bg-blue-500/10 rounded-lg">
                <p className="text-2xl font-bold text-blue-600">
                  {l2Speedup.toFixed(0)}x
                </p>
                <p className="text-xs text-muted-foreground">L2 Speedup</p>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
