import React, { useState, useEffect } from "react";
import {
  CheckCircle,
  AlertTriangle,
  Clock,
  Settings,
  ExternalLink,
  RefreshCw
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Progress } from "../ui/progress";
import { Spinner } from "../ui/spinner";
import { Button } from "../ui/button";
import { Alert, AlertDescription } from "../ui/alert";

interface IntegrationHealth {
  id: string;
  name: string;
  status: "healthy" | "warning" | "error" | "unknown";
  lastSync?: string;
  responseTime?: number;
  errorCount?: number;
  connected: boolean;
  enabled: boolean;
  category: string;
  is_mock?: boolean;
  endpoints: {
    health: string;
    profile?: string;
    resources?: string;
  };
}

interface IntegrationHealthDashboardProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  showDetails?: boolean;
}

const IntegrationHealthDashboard: React.FC<IntegrationHealthDashboardProps> = ({
  autoRefresh = true,
  refreshInterval = 30000, // 30 seconds
  showDetails = true,
}) => {
  const [integrations, setIntegrations] = useState<IntegrationHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const integrationList: Omit<IntegrationHealth, "status" | "lastSync" | "responseTime" | "errorCount">[] = [
    {
      id: "github",
      name: "GitHub",
      connected: false,
      enabled: true,
      category: "development",
      endpoints: {
        health: "/api/integrations/github/health",
        profile: "/api/integrations/github/profile",
        resources: "/api/integrations/github/resources",
      },
    },
    {
      id: "azure",
      name: "Azure",
      connected: false,
      enabled: true,
      category: "cloud",
      endpoints: {
        health: "/api/integrations/azure/health",
        profile: "/api/integrations/azure/profile",
        resources: "/api/integrations/azure/resources",
      },
    },
    {
      id: "microsoft365",
      name: "Microsoft 365",
      connected: false,
      enabled: true,
      category: "productivity",
      endpoints: {
        health: "/api/integrations/microsoft365/health",
        profile: "/api/integrations/microsoft365/profile",
        resources: "/api/integrations/microsoft365/resources",
      },
    },
    {
      id: "notion",
      name: "Notion",
      connected: false,
      enabled: true,
      category: "productivity",
      endpoints: {
        health: "/api/integrations/notion/health",
        profile: "/api/integrations/notion/profile",
        resources: "/api/integrations/notion/resources",
      },
    },
    {
      id: "salesforce",
      name: "Salesforce",
      connected: false,
      enabled: true,
      category: "crm",
      endpoints: {
        health: "/api/integrations/salesforce/health",
        profile: "/api/integrations/salesforce/profile",
        resources: "/api/integrations/salesforce/resources",
      },
    },
    {
      id: "slack",
      name: "Slack",
      connected: false,
      enabled: true,
      category: "communication",
      endpoints: {
        health: "/api/integrations/slack/health",
        profile: "/api/integrations/slack/profile",
        resources: "/api/integrations/slack/resources",
      },
    },
    {
      id: "stripe",
      name: "Stripe",
      connected: false,
      enabled: true,
      category: "finance",
      endpoints: {
        health: "/api/integrations/stripe/health",
        profile: "/api/integrations/stripe/profile",
        resources: "/api/integrations/stripe/resources",
      },
    },
    {
      id: "teams",
      name: "Microsoft Teams",
      connected: false,
      enabled: true,
      category: "communication",
      endpoints: {
        health: "/api/integrations/teams/health",
        profile: "/api/integrations/teams/profile",
        resources: "/api/integrations/teams/resources",
      },
    },
    {
      id: "zoom",
      name: "Zoom",
      connected: false,
      enabled: true,
      category: "communication",
      endpoints: {
        health: "/api/integrations/zoom/health",
        profile: "/api/integrations/zoom/profile",
        resources: "/api/integrations/zoom/resources",
      },
    },
  ];

  const checkIntegrationHealth = async (integration: Omit<IntegrationHealth, "status" | "lastSync" | "responseTime" | "errorCount">): Promise<IntegrationHealth> => {
    const startTime = Date.now();
    let status: IntegrationHealth["status"] = "unknown";
    let connected = false;
    let errorCount = 0;
    let isMock = false;

    try {
      const response = await fetch(integration.endpoints.health);
      const endTime = Date.now();
      const responseTime = endTime - startTime;

      if (response.ok) {
        try {
          const data = await response.json();
          connected = data.connected || data.status === "healthy";
          status = connected ? "healthy" : "warning";
          isMock = data.is_mock || false;
        } catch (jsonError) {
          // Response was OK but not JSON, treat as healthy but not connected
          status = "warning";
          connected = false;
        }
      } else {
        status = "error";
        errorCount = 1;
      }

      return {
        ...integration,
        status,
        connected,
        lastSync: new Date().toISOString(),
        responseTime,
        errorCount,
        is_mock: isMock,
      };
    } catch (error) {
      console.error(`Health check failed for ${integration.name}:`, error);
      return {
        ...integration,
        status: "error",
        connected: false,
        lastSync: new Date().toISOString(),
        responseTime: Date.now() - startTime,
        errorCount: 1,
        is_mock: false,
      };
    }
  };

  const refreshHealthStatus = async () => {
    setRefreshing(true);
    try {
      const healthPromises = integrationList.map(checkIntegrationHealth);
      const results = await Promise.all(healthPromises);
      setIntegrations(results);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to refresh health status:", error);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshHealthStatus();
  }, []);

  useEffect(() => {
    if (autoRefresh && !loading) {
      const interval = setInterval(refreshHealthStatus, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval, loading]);

  const getStatusColor = (status: IntegrationHealth["status"]) => {
    switch (status) {
      case "healthy":
        return "success";
      case "warning":
        return "warning";
      case "error":
        return "destructive";
      default:
        return "secondary";
    }
  };

  const getStatusIcon = (status: IntegrationHealth["status"]) => {
    switch (status) {
      case "healthy":
        return CheckCircle;
      case "warning":
        return AlertTriangle;
      case "error":
        return AlertTriangle;
      default:
        return Clock;
    }
  };

  const formatResponseTime = (ms?: number) => {
    if (!ms) return "N/A";
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  };

  const formatLastSync = (dateString?: string) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleTimeString();
  };

  const healthyCount = integrations.filter(i => i.status === "healthy").length;
  const warningCount = integrations.filter(i => i.status === "warning").length;
  const errorCount = integrations.filter(i => i.status === "error").length;
  const totalCount = integrations.length;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-8">
        <Spinner size="lg" />
        <p className="mt-4 text-gray-500">Loading integration health status...</p>
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
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Integrations</p>
              <div className="text-2xl font-bold">{totalCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">All configured</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Healthy</p>
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">{healthyCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Running smoothly</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Warnings</p>
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{warningCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Needs attention</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Errors</p>
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">{errorCount}</div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Requires action</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Health Progress */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-gray-900 dark:text-gray-100">Overall Health</h3>
              <span className="text-sm text-gray-500">
                {healthyCount}/{totalCount} healthy
              </span>
            </div>
            <Progress
              value={(healthyCount / totalCount) * 100}
              indicatorClassName={
                healthyCount === totalCount ? "bg-green-600" :
                  healthyCount > totalCount / 2 ? "bg-yellow-500" : "bg-red-600"
              }
              className="h-3"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
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
          <p className="text-sm text-gray-500">
            Last updated: {lastUpdated.toLocaleString()}
          </p>
        )}

        {integrations.map((integration) => {
          const StatusIcon = getStatusIcon(integration.status);
          return (
            <Card
              key={integration.id}
              className="hover:shadow-md transition-shadow"
            >
              <CardContent className="pt-6">
                <div className="flex items-start space-x-4">
                  <StatusIcon
                    className={`h-6 w-6 text-${getStatusColor(integration.status) === 'success' ? 'green' : getStatusColor(integration.status) === 'warning' ? 'yellow' : 'red'}-500`}
                  />

                  <div className="flex-1 space-y-2">
                    <div className="flex justify-between items-center w-full">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900 dark:text-gray-100">{integration.name}</span>
                        {integration.is_mock && (
                          <Badge variant="secondary" className="text-xs bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20 border-yellow-500/20">
                            MOCK
                          </Badge>
                        )}
                      </div>
                      <div className="flex space-x-2">
                        <Badge variant="secondary">
                          {integration.category}
                        </Badge>
                        <Badge
                          variant={getStatusColor(integration.status) as any}
                        >
                          {integration.status.toUpperCase()}
                        </Badge>
                        {integration.connected && (
                          <Badge variant="success">
                            CONNECTED
                          </Badge>
                        )}
                      </div>
                    </div>

                    {showDetails && (
                      <div className="flex space-x-6 text-sm text-gray-600 dark:text-gray-400">
                        <div className="flex items-center space-x-1" title="Last synchronization">
                          <Clock className="h-4 w-4" />
                          <span>{formatLastSync(integration.lastSync)}</span>
                        </div>

                        <div className="flex items-center space-x-1" title="Response time">
                          <Settings className="h-4 w-4" />
                          <span>{formatResponseTime(integration.responseTime)}</span>
                        </div>

                        {integration.errorCount !== undefined && integration.errorCount > 0 && (
                          <div className="flex items-center space-x-1 text-red-500" title="Error count">
                            <AlertTriangle className="h-4 w-4" />
                            <span>{integration.errorCount} errors</span>
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Healthy - Integration is working properly</span>
            </div>
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Warning - Minor issues detected</span>
            </div>
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Error - Integration requires attention</span>
            </div>
          </div>
        </CardContent>
      </Card >
    </div >
  );
};

export default IntegrationHealthDashboard;

