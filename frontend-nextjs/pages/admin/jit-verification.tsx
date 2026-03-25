import React, { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import {
  RefreshCw,
  Clock,
  AlertTriangle,
  Keyboard,
} from "lucide-react";
import {
  jitVerificationAPI,
  AdminPoller,
} from "@/lib/api-admin";
import { WorkerStatusMonitor } from "@/components/admin/jit-verification/WorkerStatusMonitor";
import { SystemStatusCards } from "@/components/admin/jit-verification/SystemStatusCards";
import { QuickActions } from "@/components/admin/jit-verification/QuickActions";
import { CacheMetricsPanel } from "@/components/admin/jit-verification/CacheMetricsPanel";
import { LatencyDisplay } from "@/components/admin/jit-verification/LatencyDisplay";
import { CacheActions } from "@/components/admin/jit-verification/CacheActions";
import { CitationVerificationPanel } from "@/components/admin/jit-verification/CitationVerificationPanel";
import { VerificationLogs } from "@/components/admin/jit-verification/VerificationLogs";
import { TopCitations } from "@/components/admin/jit-verification/TopCitations";
import {
  ErrorBoundary,
  OfflineIndicator,
  useKeyboardShortcuts,
  KeyboardShortcutsHelp,
} from "@/components/admin/shared";
import type {
  WorkerMetricsResponse,
  CacheStatsResponse,
  HealthCheckResponse,
  SystemHealthStatus,
} from "@/types/jit-verification";

/**
 * JIT Verification Admin Dashboard
 *
 * Provides real-time monitoring and control of the JIT verification system.
 */
function JITVerificationDashboardContent() {
  const [workerMetrics, setWorkerMetrics] = useState<WorkerMetricsResponse | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStatsResponse | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);
  const { toast } = useToast();

  // Keyboard shortcuts
  useKeyboardShortcuts([
    {
      title: "Navigation",
      shortcuts: [
        {
          key: "?",
          description: "Show keyboard shortcuts",
          action: () => setShowKeyboardHelp(true),
        },
        {
          key: "r",
          description: "Refresh dashboard",
          action: handleRefresh,
        },
        {
          key: "a",
          description: "Toggle auto-refresh",
          action: () => setAutoRefresh((prev) => !prev),
        },
      ],
    },
    {
      title: "Tabs",
      shortcuts: [
        {
          key: "1",
          description: "Go to Overview tab",
          action: () => {
            // Tab switching would require ref management
            console.log("Navigate to Overview tab");
          },
        },
        {
          key: "2",
          description: "Go to Worker tab",
          action: () => {
            console.log("Navigate to Worker tab");
          },
        },
        {
          key: "3",
          description: "Go to Cache tab",
          action: () => {
            console.log("Navigate to Cache tab");
          },
        },
        {
          key: "4",
          description: "Go to Citations tab",
          action: () => {
            console.log("Navigate to Citations tab");
          },
        },
        {
          key: "5",
          description: "Go to Logs tab",
          action: () => {
            console.log("Navigate to Logs tab");
          },
        },
        {
          key: "6",
          description: "Go to Top Citations tab",
          action: () => {
            console.log("Navigate to Top Citations tab");
          },
        },
      ],
    },
  ]);

  // Poller for real-time updates
  const poller = new AdminPoller();

  // Fetch all dashboard data
  const fetchDashboardData = async () => {
    try {
      const [workerRes, cacheRes, healthRes] = await Promise.all([
        jitVerificationAPI.getWorkerMetrics(),
        jitVerificationAPI.getCacheStats(),
        jitVerificationAPI.getHealth(),
      ]);

      setWorkerMetrics(workerRes.data);
      setCacheStats(cacheRes.data);
      setHealthStatus(healthRes.data);
    } catch (error: any) {
      console.error("Failed to fetch dashboard data:", error);
      toast({
        title: "Error loading dashboard",
        description: error.userMessage || "Failed to fetch JIT verification data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Initial fetch and setup polling
  useEffect(() => {
    fetchDashboardData();

    // Start polling if auto-refresh is enabled
    if (autoRefresh) {
      poller.start(
        () => Promise.all([
          jitVerificationAPI.getWorkerMetrics(),
          jitVerificationAPI.getCacheStats(),
          jitVerificationAPI.getHealth(),
        ]),
        ([workerRes, cacheRes, healthRes]) => {
          setWorkerMetrics(workerRes.data);
          setCacheStats(cacheRes.data);
          setHealthStatus(healthRes.data);
        },
        10000 // 10 seconds
      );
    }

    return () => {
      poller.stop();
    };
  }, [autoRefresh]);

  // Toggle auto-refresh
  const toggleAutoRefresh = () => {
    const newState = !autoRefresh;
    setAutoRefresh(newState);

    if (newState) {
      poller.start(
        () => Promise.all([
          jitVerificationAPI.getWorkerMetrics(),
          jitVerificationAPI.getCacheStats(),
          jitVerificationAPI.getHealth(),
        ]),
        ([workerRes, cacheRes, healthRes]) => {
          setWorkerMetrics(workerRes.data);
          setCacheStats(cacheRes.data);
          setHealthStatus(healthRes.data);
        },
        10000
      );
      toast({
        title: "Auto-refresh enabled",
        description: "Dashboard will update every 10 seconds",
      });
    } else {
      poller.stop();
      toast({
        title: "Auto-refresh disabled",
        description: "Dashboard will no longer update automatically",
      });
    }
  };

  // Manual refresh
  const handleRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <div className="container mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">JIT Verification</h1>
            <p className="text-muted-foreground mt-1">
              Monitor and manage business fact citation verification
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowKeyboardHelp(true)}
            >
              <Keyboard className="h-4 w-4 mr-2" />
              Shortcuts
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleAutoRefresh}
            >
              {autoRefresh ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Clock className="h-4 w-4 mr-2" />}
              {autoRefresh ? "Auto-refreshing" : "Auto-refresh"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* System Status Cards */}
        <SystemStatusCards
          workerMetrics={workerMetrics}
          cacheStats={cacheStats}
          healthStatus={healthStatus}
        />

        {/* Quick Actions */}
        <QuickActions
          isWorkerRunning={workerMetrics?.running ?? false}
          onUpdate={fetchDashboardData}
        />

        {/* Worker Status Monitor */}
        {workerMetrics && (
          <WorkerStatusMonitor
            metrics={workerMetrics}
            onUpdate={fetchDashboardData}
          />
        )}

        {/* Tabs for different views */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="worker">Worker</TabsTrigger>
            <TabsTrigger value="cache">Cache</TabsTrigger>
            <TabsTrigger value="citations">Citations</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
            <TabsTrigger value="top-citations">Top Citations</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            {/* Performance Metrics */}
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Cache Hit Rate */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Cache Hit Rate</span>
                    <span className="text-sm text-muted-foreground">
                      {cacheStats ? (cacheStats.l1_verification_hit_rate * 100).toFixed(1) : 0}%
                    </span>
                  </div>
                  <Progress value={cacheStats ? cacheStats.l1_verification_hit_rate * 100 : 0} />
                </div>

                {/* Average Verification Time */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Avg Verification Time</span>
                    <span className="text-sm text-muted-foreground">
                      {workerMetrics?.average_verification_time.toFixed(3) || 0}s
                    </span>
                  </div>
                  <Progress value={(workerMetrics?.average_verification_time || 0) * 100} />
                </div>

                {/* Worker Last Run */}
                {workerMetrics?.last_run_duration && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Last Run Duration</span>
                      <span className="text-sm text-muted-foreground">
                        {workerMetrics.last_run_duration.toFixed(2)}s
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="worker" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Worker Metrics</CardTitle>
                <CardDescription>
                  Background verification worker performance
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {workerMetrics && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Verified</p>
                        <p className="text-2xl font-bold text-green-600">
                          {workerMetrics.verified_count}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Failed</p>
                        <p className="text-2xl font-bold text-red-600">
                          {workerMetrics.failed_count}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Stale Facts</p>
                        <p className="text-2xl font-bold text-yellow-600">
                          {workerMetrics.stale_facts}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Total Citations</p>
                        <p className="text-2xl font-bold">
                          {workerMetrics.total_citations}
                        </p>
                      </div>
                    </div>

                    {/* Top Citations */}
                    {workerMetrics.top_citations && workerMetrics.top_citations.length > 0 && (
                      <div className="mt-6">
                        <h4 className="text-sm font-medium mb-3">Top Citations (by access)</h4>
                        <div className="space-y-2">
                          {workerMetrics.top_citations.slice(0, 5).map((citation, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm p-2 rounded bg-secondary/20">
                              <span className="font-mono text-xs truncate flex-1 mr-2">
                                {citation.citation}
                              </span>
                              <Badge variant="secondary">
                                {citation.access_count}x
                              </Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="cache" className="space-y-4">
            {/* Import new components */}
            {cacheStats && (
              <>
                <CacheMetricsPanel stats={cacheStats} />
                <LatencyDisplay stats={cacheStats} />
                <CacheActions />
              </>
            )}
          </TabsContent>

          <TabsContent value="citations" className="space-y-4">
            <CitationVerificationPanel />
          </TabsContent>

          <TabsContent value="logs" className="space-y-4">
            <VerificationLogs />
          </TabsContent>

          <TabsContent value="top-citations" className="space-y-4">
            <TopCitations />
          </TabsContent>
        </Tabs>

        {/* Health Issues */}
        {healthStatus && healthStatus.issues.length > 0 && (
          <Card className="border-yellow-500/50 bg-yellow-500/5">
            <CardHeader>
              <CardTitle className="flex items-center text-yellow-700">
                <AlertTriangle className="h-5 w-5 mr-2" />
                Health Issues Detected
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {healthStatus.issues.map((issue, idx) => (
                  <li key={idx} className="text-sm text-yellow-700">
                    • {issue}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      {/* </div> removed here to let fragment handle sibling help component */}

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsHelp
        open={showKeyboardHelp}
        onClose={() => setShowKeyboardHelp(false)}
        groups={[
          {
            title: "Navigation",
            shortcuts: [
              { key: "?", description: "Show keyboard shortcuts", action: () => { } },
              { key: "r", description: "Refresh dashboard", action: () => { } },
              { key: "a", description: "Toggle auto-refresh", action: () => { } },
            ],
          },
          {
            title: "Tabs",
            shortcuts: [
              { key: "1", description: "Go to Overview tab", action: () => { } },
              { key: "2", description: "Go to Worker tab", action: () => { } },
              { key: "3", description: "Go to Cache tab", action: () => { } },
              { key: "4", description: "Go to Citations tab", action: () => { } },
              { key: "5", description: "Go to Logs tab", action: () => { } },
              { key: "6", description: "Go to Top Citations tab", action: () => { } },
            ],
          },
          ]}
        />
        </div>
      </>
    );
}

// Dynamically import the content component with SSR disabled to avoid prerendering issues
const JITVerificationDashboardContentDynamic = dynamic(() => Promise.resolve(JITVerificationDashboardContent), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-screen">
      <RefreshCw className="h-8 w-8 animate-spin text-primary" />
    </div>
  ),
});

// Wrapper with ErrorBoundary and OfflineIndicator
const JITVerificationDashboard: React.FC = () => {
  return (
    <ErrorBoundary>
      <JITVerificationDashboardContentDynamic />
      <OfflineIndicator />
    </ErrorBoundary>
  );
};

export default JITVerificationDashboard;
