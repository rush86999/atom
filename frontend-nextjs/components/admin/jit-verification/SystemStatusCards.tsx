import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Activity,
  Database,
  FileText,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import type { WorkerMetricsResponse, CacheStatsResponse, HealthCheckResponse } from "@/types/jit-verification";

interface SystemStatusCardsProps {
  workerMetrics: WorkerMetricsResponse | null;
  cacheStats: CacheStatsResponse | null;
  healthStatus: HealthCheckResponse | null;
}

const formatPercentage = (value?: number): string => {
  if (typeof value !== "number" || isNaN(value)) return "0%";
  return `${(value * 100).toFixed(0)}%`;
};

const formatNumber = (value?: number): string => {
  if (typeof value !== "number" || isNaN(value)) return "0";
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return value.toString();
};

const getStatusIcon = (status: HealthCheckResponse["status"]) => {
  switch (status) {
    case "healthy":
      return <CheckCircle2 className="h-6 w-6" />;
    case "degraded":
      return <AlertTriangle className="h-6 w-6" />;
    case "unhealthy":
      return <AlertCircle className="h-6 w-6" />;
  }
};

// Worker Status Card
const WorkerCard: React.FC<{ metrics: WorkerMetricsResponse | null }> = ({ metrics }) => {
  const isRunning = metrics?.running ?? false;
  const lastRunAgo = metrics?.last_run_time ? new Date(metrics.last_run_time) : null;

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-600" />
            <span className="font-medium text-sm">Worker Status</span>
          </div>
          {isRunning ? (
            <Badge className="bg-green-500/20 text-green-600 border-green-500/50">
              Running
            </Badge>
          ) : (
            <Badge className="bg-gray-500/20 text-gray-600 border-gray-500/50">
              Stopped
            </Badge>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold">
              {isRunning ? "Active" : "Inactive"}
            </span>
            {isRunning ? (
              <CheckCircle2 className="h-6 w-6 text-green-600" />
            ) : (
              <AlertCircle className="h-6 w-6 text-gray-400" />
            )}
          </div>

          {lastRunAgo && (
            <p className="text-xs text-muted-foreground">
              Last run: {lastRunAgo.toLocaleString()}
            </p>
          )}

          {metrics && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Verified</span>
                <span className="font-medium text-green-600">
                  {metrics.verified_count}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Failed</span>
                <span className="font-medium text-red-600">
                  {metrics.failed_count}
                </span>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// Cache Health Card
const CacheCard: React.FC<{ stats: CacheStatsResponse | null }> = ({ stats }) => {
  const hitRate = stats?.l1_verification_hit_rate ?? 0;
  const cacheSize = stats?.l1_verification_cache_size ?? 0;
  const evictions = stats?.l1_evictions ?? 0;

  return (
    <Card className="border-l-4 border-l-purple-500">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-purple-600" />
            <span className="font-medium text-sm">Cache Health</span>
          </div>
          {hitRate >= 0.8 ? (
            <TrendingUp className="h-5 w-5 text-green-600" />
          ) : hitRate >= 0.5 ? (
            <AlertTriangle className="h-5 w-5 text-yellow-600" />
          ) : (
            <TrendingDown className="h-5 w-5 text-red-600" />
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold">{formatPercentage(hitRate)}</span>
          </div>

          <div className="space-y-2">
            <div>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted-foreground">Hit Rate</span>
                <span className="font-medium">{formatPercentage(hitRate)}</span>
              </div>
              <Progress value={hitRate * 100} className="h-1.5" />
            </div>
          </div>

          {stats && (
            <div className="space-y-1 pt-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Cached</span>
                <span className="font-medium">{formatNumber(cacheSize)}</span>
              </div>
              {evictions > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Evictions</span>
                  <span className="font-medium text-yellow-600">{evictions}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// Citations Card
const CitationsCard: React.FC<{ metrics: WorkerMetricsResponse | null }> = ({ metrics }) => {
  const total = metrics?.total_citations ?? 0;
  const verified = metrics?.verified_count ?? 0;
  const stale = metrics?.stale_facts ?? 0;

  return (
    <Card className={`border-l-4 ${stale > 0 ? "border-l-yellow-500" : "border-l-green-500"}`}>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-green-600" />
            <span className="font-medium text-sm">Citations</span>
          </div>
          {stale > 0 ? (
            <AlertTriangle className="h-5 w-5 text-yellow-600" />
          ) : (
            <CheckCircle2 className="h-5 w-5 text-green-600" />
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold">{formatNumber(total)}</span>
          </div>

          {metrics && (
            <div className="space-y-1 pt-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Verified</span>
                <span className="font-medium text-green-600">
                  {formatNumber(verified)}
                </span>
              </div>
              {stale > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Stale</span>
                  <span className="font-medium text-yellow-600">{stale}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// System Health Card
const HealthCard: React.FC<{ health: HealthCheckResponse | null }> = ({ health }) => {
  const status = health?.status ?? "unhealthy";
  const issues = health?.issues ?? [];

  return (
    <Card className={`border-l-4 ${
      status === "healthy"
        ? "border-l-green-500"
        : status === "degraded"
        ? "border-l-yellow-500"
        : "border-l-red-500"
    }`}>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium text-sm">System Health</span>
          </div>
          {getStatusIcon(status)}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold capitalize">{status}</span>
          </div>

          {health && (
            <div className="space-y-2 pt-2">
              {health.worker && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Worker</span>
                  <Badge variant={health.worker.running ? "default" : "secondary"}>
                    {health.worker.running ? "Running" : "Stopped"}
                  </Badge>
                </div>
              )}
              {health.cache && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Cache Hit</span>
                  <span className="font-medium">{health.cache.verification_hit_rate}</span>
                </div>
              )}
            </div>
          )}

          {issues.length > 0 && (
            <div className="pt-2 border-t">
              <p className="text-xs text-muted-foreground mb-1">
                {issues.length} issue{issues.length > 1 ? "s" : ""}
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

/**
 * System Status Cards Component
 *
 * Displays four key system status indicators with visual feedback.
 */
export const SystemStatusCards: React.FC<SystemStatusCardsProps> = ({
  workerMetrics,
  cacheStats,
  healthStatus,
}) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <WorkerCard metrics={workerMetrics} />
      <CacheCard stats={cacheStats} />
      <CitationsCard metrics={workerMetrics} />
      <HealthCard health={healthStatus} />
    </div>
  );
};
