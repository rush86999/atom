import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/auth-headers";
import {
  CheckCircle,
  AlertTriangle,
  Clock,
  HelpCircle,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { Card, CardContent } from "../ui/card";
import { Badge } from "../ui/badge";
import { Progress } from "../ui/progress";
import { Spinner } from "../ui/spinner";
import { Button } from "../ui/button";
import { authHeaders } from "@/lib/auth-headers";

/**
 * Real integration health, from GET /api/integrations/health-status.
 *
 * The backend reports actual connection state (UserConnection rows,
 * tenant connectors, environment credentials) and — when a credential can
 * be exercised with one read-only call — verifies it against the live
 * provider API, with the real measured response time. Statuses:
 *
 * - healthy      connected + live provider call succeeded
 * - unreachable  connected + live provider call failed (error shown)
 * - connected    connected, credential not exercisable in one call
 *                (subdomain/realm/refresh-flow providers) — unverified
 * - not_connected no connection or credential exists
 */
interface ProviderHealth {
  name: string;
  category: string;
  connected: boolean;
  source: "user_connection" | "tenant_integration" | "env" | "none";
  status: "healthy" | "unreachable" | "connected" | "not_connected";
  verified: boolean;
  response_time_ms?: number | null;
  error?: string | null;
  checked_at?: string | null;
}

interface IntegrationHealthDashboardProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  showDetails?: boolean;
}

const SOURCE_LABELS: Record<ProviderHealth["source"], string> = {
  user_connection: "in-app connection",
  tenant_integration: "tenant connector",
  env: "environment credentials",
  none: "—",
};

const IntegrationHealthDashboard: React.FC<IntegrationHealthDashboardProps> = ({
  autoRefresh = true,
  refreshInterval = 30000, // 30 seconds
  showDetails = true,
}) => {
  const [providers, setProviders] = useState<Record<string, ProviderHealth>>({});
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refreshHealthStatus = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await authFetch("/api/integrations/health-status", {
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(`health-status returned ${response.status}`);
      const data = await response.json();
      setProviders(data?.providers ?? {});
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to refresh integration health:", error);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshHealthStatus();
  }, [refreshHealthStatus]);

  useEffect(() => {
    if (autoRefresh && !loading) {
      const interval = setInterval(refreshHealthStatus, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval, loading, refreshHealthStatus]);

  const entries = Object.entries(providers).sort(([, a], [, b]) => {
    const rank = (s: ProviderHealth["status"]) =>
      s === "healthy" ? 0 : s === "unreachable" ? 1 : s === "connected" ? 2 : 3;
    return rank(a.status) - rank(b.status) || a.name.localeCompare(b.name);
  });

  const connectedCount = entries.filter(([, p]) => p.connected).length;
  const healthyCount = entries.filter(([, p]) => p.status === "healthy").length;
  const unreachableCount = entries.filter(([, p]) => p.status === "unreachable").length;
  const unverifiedCount = entries.filter(([, p]) => p.status === "connected").length;
  const notConnectedCount = entries.filter(([, p]) => p.status === "not_connected").length;
  const totalCount = entries.length;

  const getStatusMeta = (status: ProviderHealth["status"]) => {
    switch (status) {
      case "healthy":
        return {
          icon: CheckCircle,
          iconClass: "text-green-500",
          badge: "success" as const,
          label: "HEALTHY",
        };
      case "unreachable":
        return {
          icon: XCircle,
          iconClass: "text-red-500",
          badge: "destructive" as const,
          label: "UNREACHABLE",
        };
      case "connected":
        return {
          icon: HelpCircle,
          iconClass: "text-yellow-500",
          badge: "warning" as const,
          label: "UNVERIFIED",
        };
      default:
        return {
          icon: Clock,
          iconClass: "text-gray-400",
          badge: "secondary" as const,
          label: "NOT CONNECTED",
        };
    }
  };

  const formatResponseTime = (ms?: number | null) => {
    if (!ms && ms !== 0) return "—";
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <Spinner size="lg" />
        <p className="mt-4 text-gray-500 dark:text-gray-400">Loading integration health status...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Connected</p>
              <div className="text-2xl font-bold">{connectedCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">of {totalCount} known integrations</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Verified healthy</p>
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">{healthyCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Live provider API call succeeded</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Unreachable</p>
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">{unreachableCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Credential rejected or provider failed</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Unverified</p>
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{unverifiedCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Connected, credential not exercisable</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Connected share */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-gray-900 dark:text-gray-100">Connections</h3>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {connectedCount}/{totalCount} connected
              </span>
            </div>
            <Progress
              value={totalCount ? (connectedCount / totalCount) * 100 : 0}
              indicatorClassName={
                connectedCount === totalCount ? "bg-green-600" :
                  connectedCount > totalCount / 2 ? "bg-yellow-500" : "bg-red-600"
              }
              className="h-3"
            />
            <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>{notConnectedCount} not connected</span>
              <span>{healthyCount} verified healthy</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Integration List */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">Integration Status</h3>
          <Button
            size="sm"
            variant="outline"
            onClick={refreshHealthStatus}
            disabled={refreshing}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {lastUpdated && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Last updated: {lastUpdated.toLocaleString()}
          </p>
        )}

        {entries.map(([id, provider]) => {
          const meta = getStatusMeta(provider.status);
          const StatusIcon = meta.icon;
          return (
            <Card key={id} className="hover:shadow-md transition-shadow">
              <CardContent className="pt-6">
                <div className="flex items-start space-x-4">
                  <StatusIcon className={`h-6 w-6 shrink-0 ${meta.iconClass}`} />

                  <div className="flex-1 space-y-2">
                    <div className="flex justify-between items-center w-full">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900 dark:text-gray-100">{provider.name}</span>
                      </div>
                      <div className="flex space-x-2">
                        <Badge variant="secondary">
                          {provider.category}
                        </Badge>
                        <Badge variant={meta.badge}>
                          {meta.label}
                        </Badge>
                      </div>
                    </div>

                    {showDetails && (
                      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-600 dark:text-gray-400">
                        {provider.verified && (
                          <div className="flex items-center space-x-1" title="Real provider API call duration">
                            <Clock className="h-4 w-4" />
                            <span>{formatResponseTime(provider.response_time_ms)}</span>
                          </div>
                        )}
                        <div className="flex items-center space-x-1" title="Where this connection comes from">
                          <span>Source: {SOURCE_LABELS[provider.source]}</span>
                        </div>
                        {provider.status === "unreachable" && provider.error && (
                          <div className="flex items-center space-x-1 text-red-500" title="Provider API error">
                            <AlertTriangle className="h-4 w-4" />
                            <span>{provider.error}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div >

      {/* Status Legend */}
      < Card >
        <CardContent className="pt-6">
          <h4 className="font-bold mb-3 text-gray-900 dark:text-gray-100">Status Legend</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Healthy — connected and a live provider API call succeeded
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <XCircle className="h-5 w-5 text-red-500 shrink-0" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Unreachable — connected but the credential was rejected or the provider failed
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <HelpCircle className="h-5 w-5 text-yellow-500 shrink-0" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Unverified — connected, but the credential needs an interactive flow to test
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Clock className="h-5 w-5 text-gray-400 shrink-0" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Not connected — no connection or stored credential for this integration
              </span>
            </div>
          </div>
        </CardContent>
      </Card >
    </div >
  );
};

export default IntegrationHealthDashboard;
