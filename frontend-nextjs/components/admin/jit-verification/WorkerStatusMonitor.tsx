import React from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/components/ui/use-toast";
import {
  Activity,
  CheckCircle2,
  Clock,
  Play,
  Square,
  TrendingUp,
  AlertTriangle,
  FileText,
} from "lucide-react";
import { jitVerificationAPI } from "@/lib/api-admin";
import type { WorkerMetricsResponse } from "@/types/jit-verification";

interface WorkerStatusMonitorProps {
  metrics: WorkerMetricsResponse;
  onUpdate: () => void;
}

/**
 * Worker Status Monitor Component
 *
 * Displays detailed worker metrics and provides worker control actions.
 */
export const WorkerStatusMonitor: React.FC<WorkerStatusMonitorProps> = ({
  metrics,
  onUpdate,
}) => {
  const { toast } = useToast();
  const [loading, setLoading] = React.useState(false);

  const handleStartWorker = async () => {
    setLoading(true);
    try {
      await jitVerificationAPI.startWorker();
      toast({
        title: "Worker started",
        description: "JIT verification worker is now running",
      });
      onUpdate();
    } catch (error: any) {
      toast({
        title: "Failed to start worker",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStopWorker = async () => {
    setLoading(true);
    try {
      await jitVerificationAPI.stopWorker();
      toast({
        title: "Worker stopped",
        description: "JIT verification worker has been stopped",
      });
      onUpdate();
    } catch (error: any) {
      toast({
        title: "Failed to stop worker",
        description: error.userMessage || "An error occurred",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs.toFixed(0)}s`;
  };

  const formatLastRun = (timestamp?: string): string => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  const getNextRun = (): string => {
    if (!metrics.last_run_time) return "Not scheduled";
    const lastRun = new Date(metrics.last_run_time);
    const nextRun = new Date(lastRun.getTime() + 3600000); // 1 hour
    const now = new Date();
    const diffMs = nextRun.getTime() - now.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins <= 0) return "Due now";
    if (diffMins < 60) return `In ${diffMins}m`;
    const diffHours = Math.floor(diffMins / 60);
    return `In ${diffHours}h ${diffMins % 60}m`;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Verification Worker
            </CardTitle>
            <CardDescription>
              Background citation verification and cache updates
            </CardDescription>
          </div>
          <Badge
            variant={metrics.running ? "default" : "secondary"}
            className={metrics.running
              ? "bg-green-500/20 text-green-600 border-green-500/50"
              : "bg-gray-500/20 text-gray-600 border-gray-500/50"
            }
          >
            {metrics.running ? "Running" : "Stopped"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Status Header */}
        <div className="flex items-center justify-between">
          <div>
            {metrics.running ? (
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <span className="text-lg font-semibold text-green-600">
                  Worker Active
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Square className="h-5 w-5 text-gray-600" />
                <span className="text-lg font-semibold text-gray-600">
                  Worker Stopped
                </span>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            {metrics.running ? (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleStopWorker}
                disabled={loading}
              >
                <Square className="h-4 w-4 mr-2" />
                Stop Worker
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleStartWorker}
                disabled={loading}
              >
                <Play className="h-4 w-4 mr-2" />
                Start Worker
              </Button>
            )}
          </div>
        </div>

        {/* Run Information */}
        {metrics.running && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-secondary/20 rounded-lg">
            <div>
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Last Run
              </p>
              <p className="font-semibold">
                {formatLastRun(metrics.last_run_time)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                Duration
              </p>
              <p className="font-semibold">
                {metrics.last_run_duration > 0
                  ? formatDuration(metrics.last_run_duration)
                  : "—"
                }
              </p>
            </div>
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground">Next Run</p>
              <p className="font-semibold">
                {getNextRun()}
              </p>
            </div>
          </div>
        )}

        {/* Verification Metrics */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium">Verification Metrics</h4>

          <div className="grid grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Total</p>
              <p className="text-2xl font-bold">{metrics.total_citations}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Verified</p>
              <p className="text-2xl font-bold text-green-600">
                {metrics.verified_count}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Failed</p>
              <p className="text-2xl font-bold text-red-600">
                {metrics.failed_count}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Stale Facts</p>
              <p className="text-2xl font-bold text-yellow-600">
                {metrics.stale_facts}
              </p>
            </div>
          </div>

          {/* Success Rate */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Success Rate</span>
              <span className="font-medium">
                {metrics.total_citations > 0
                  ? ((metrics.verified_count / metrics.total_citations) * 100).toFixed(1)
                  : "0.0"
                }%
              </span>
            </div>
            <Progress
              value={metrics.total_citations > 0
                ? (metrics.verified_count / metrics.total_citations) * 100
                : 0
              }
              className="h-2"
            />
          </div>

          {/* Average Verification Time */}
          {metrics.average_verification_time > 0 && (
            <div className="flex items-center justify-between text-sm p-3 bg-secondary/10 rounded">
              <span className="text-muted-foreground">Avg Time/Citation</span>
              <span className="font-semibold">
                {metrics.average_verification_time < 1
                  ? `${(metrics.average_verification_time * 1000).toFixed(0)}ms`
                  : `${metrics.average_verification_time.toFixed(2)}s`
                }
              </span>
            </div>
          )}
        </div>

        {/* Top Citations */}
        {metrics.top_citations && metrics.top_citations.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Top Citations (by access)
            </h4>
            <div className="space-y-2">
              {metrics.top_citations.slice(0, 10).map((citation, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-sm p-3 rounded-lg bg-secondary/20 hover:bg-secondary/30 transition-colors"
                >
                  <span className="font-mono text-xs truncate flex-1 mr-4">
                    {citation.citation}
                  </span>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">
                      {citation.access_count}x
                    </Badge>
                    {idx === 0 && (
                      <Badge className="bg-blue-500/20 text-blue-600 border-blue-500/50">
                        Most Accessed
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warning Indicators */}
        {(metrics.stale_facts > 0 || metrics.failed_count > 0) && (
          <div className="flex items-start gap-3 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium text-yellow-800">
                Attention Required
              </p>
              <div className="space-y-1 text-sm text-yellow-700">
                {metrics.stale_facts > 0 && (
                  <p>• {metrics.stale_facts} business facts have outdated citations</p>
                )}
                {metrics.failed_count > 0 && (
                  <p>• {metrics.failed_count} verification failures detected</p>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
