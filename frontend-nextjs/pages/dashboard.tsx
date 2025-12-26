/**
 * Main ATOM Dashboard with Integrations
 */

import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
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
import { useToast } from "@/components/ui/use-toast";
import {
  ArrowRight,
  Clock,
  Settings,
  CheckCircle,
  AlertTriangle,
  HardDrive,
  MessageSquare,
  Mail,
  CheckSquare,
  Github,
  Code,
  CreditCard,
  List,
  Activity,
  RefreshCw,
  LayoutDashboard,
  TrendingUp,
  DollarSign,
  TrendingDown,
  PieChart,
  Target,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const DashboardPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    connected: 0,
    total: 9,
    healthy: 0,
    errors: 0,
  });
  const [financials, setFinancials] = useState<any>(null);
  const [sales, setSales] = useState<any>(null);
  const { toast } = useToast();
  const router = useRouter();
  const workspaceId = "default-workspace"; // Consistent with other components

  const integrationIcons: Record<string, any> = {
    box: HardDrive,
    dropbox: HardDrive,
    gdrive: HardDrive,
    slack: MessageSquare,
    gmail: Mail,
    notion: CheckSquare,
    jira: CheckSquare,
    github: Github,
    nextjs: Code,
    stripe: CreditCard,
    linear: List,
    outlook: Mail,
    asana: CheckSquare,
  };

  const refreshDashboardData = async () => {
    try {
      setLoading(true);

      // 1. Health Checks
      const healthChecks = await Promise.all([
        fetch("/api/integrations/box/health"),
        fetch("/api/integrations/dropbox/health"),
        fetch("/api/integrations/gdrive/health"),
        fetch("/api/integrations/slack/health"),
        fetch("/api/integrations/gmail/health"),
        fetch("/api/integrations/notion/health"),
        fetch("/api/integrations/jira/health"),
        fetch("/api/integrations/github/health"),
        fetch("/api/nextjs/health"),
        fetch("/api/integrations/stripe/health"),
        fetch("/api/integrations/linear/health"),
        fetch("/api/integrations/outlook/health"),
        fetch("/api/integrations/asana/health"),
      ]);

      const integrationList = [
        { id: "box", name: "Box", category: "storage" },
        { id: "dropbox", name: "Dropbox", category: "storage" },
        { id: "gdrive", name: "Google Drive", category: "storage" },
        { id: "slack", name: "Slack", category: "communication" },
        { id: "gmail", name: "Gmail", category: "communication" },
        { id: "notion", name: "Notion", category: "productivity" },
        { id: "jira", name: "Jira", category: "productivity" },
        { id: "github", name: "GitHub", category: "development" },
        { id: "nextjs", name: "Next.js", category: "development" },
        { id: "stripe", name: "Stripe", category: "finance" },
        { id: "linear", name: "Linear", category: "productivity" },
        { id: "outlook", name: "Outlook", category: "communication" },
        { id: "asana", name: "Asana", category: "productivity" },
      ];

      const updatedIntegrations = integrationList.map((integration, index) => {
        const healthResponse = healthChecks[index];
        const connected = healthResponse.ok;
        const health = healthResponse.ok ? "healthy" : "error";

        return {
          ...integration,
          connected,
          health,
          icon: integrationIcons[integration.id] || Activity,
          lastSync: new Date().toISOString(),
        };
      });

      setIntegrations(updatedIntegrations);
      setStats({
        connected: updatedIntegrations.filter((i) => i.connected).length,
        total: updatedIntegrations.length,
        healthy: updatedIntegrations.filter((i) => i.health === "healthy").length,
        errors: updatedIntegrations.filter((i) => i.health === "error").length,
      });

      // 2. Fetch Business Intelligence Summary (Phase 12)
      const [finRes, salesRes] = await Promise.all([
        fetch(`/api/v1/accounting/dashboard/summary?workspace_id=${workspaceId}`),
        fetch(`/api/sales/dashboard/summary?workspace_id=${workspaceId}`)
      ]);

      if (finRes.ok) setFinancials(await finRes.json());
      if (salesRes.ok) setSales(await salesRes.json());

    } catch (error) {
      console.error("Dashboard refresh failed:", error);
      toast({
        title: "Refresh failed",
        description: "Could not fetch latest intelligence data.",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleIntegrationClick = (integrationId: string) => {
    router.push(`/integrations/${integrationId}`);
  };

  const getStatusIcon = (health: string) => {
    switch (health) {
      case "healthy":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "warning":
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case "error":
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (health: string) => {
    const variant =
      health === "healthy"
        ? "default" // Greenish usually
        : health === "warning"
          ? "secondary" // Yellowish
          : "destructive"; // Red

    // Custom coloring since Shadcn badges are limited
    const className =
      health === "healthy"
        ? "bg-green-500 hover:bg-green-600"
        : health === "warning"
          ? "bg-yellow-500 hover:bg-yellow-600"
          : health === "error"
            ? "bg-red-500 hover:bg-red-600"
            : "bg-gray-500 hover:bg-gray-600";

    return (
      <Badge className={className}>
        {health}
      </Badge>
    );
  };

  const getConnectionProgress = () => {
    return (stats.connected / stats.total) * 100;
  };

  const getHealthProgress = () => {
    return (stats.healthy / stats.total) * 100;
  };

  useEffect(() => {
    refreshDashboardData();

    // Auto-refresh every 2 minutes
    const interval = setInterval(refreshDashboardData, 120000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
            ATOM Dashboard
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-400">
            Manage your connected integrations and data pipeline
          </p>
        </div>

        {/* Stats Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="border-l-4 border-l-blue-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500">
                  <span>Cash on Hand</span>
                  <DollarSign className="w-4 h-4 text-blue-600" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    ${financials?.total_cash?.toLocaleString() || "0"}
                  </span>
                  <span className="text-sm font-medium text-green-600">
                    Stable
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  Runway: <span className="font-bold text-blue-600">{financials?.runway_months || "0"} months</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-orange-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500">
                  <span>Sales Pipeline</span>
                  <TrendingUp className="w-4 h-4 text-orange-600" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    ${sales?.pipeline_value?.toLocaleString() || "0"}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  Forecast (weighted): <span className="font-bold text-orange-600">${sales?.weighted_forecast?.toLocaleString() || "0"}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-purple-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500">
                  <span>Active Deals</span>
                  <PieChart className="w-4 h-4 text-purple-600" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    {sales?.active_deals_count || "0"}
                  </span>
                  {sales?.high_risk_deals_count > 0 && (
                    <Badge variant="destructive" className="ml-2 animate-pulse">
                      {sales.high_risk_deals_count} at risk
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-gray-500">
                  Avg. Conversion: <span className="font-bold text-purple-600">{sales?.conversion_rate || "0"}%</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-red-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500">
                  <span>Accounts Payable</span>
                  <TrendingDown className="w-4 h-4 text-red-600" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    ${financials?.accounts_payable?.toLocaleString() || "0"}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  Receivables (AR): <span className="font-bold text-green-600">${financials?.accounts_receivable?.toLocaleString() || "0"}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">
              Quick Actions
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Common tasks and management
            </p>
          </div>

          <div className="flex space-x-4">
            <Button
              variant="outline"
              onClick={() => router.push("/accounting/bills/upload")}
              className="gap-2 border-dashed border-blue-300 hover:border-blue-500"
            >
              <Zap className="w-4 h-4 text-blue-500" />
              Process Invoice
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push("/integrations")}
              className="gap-2"
            >
              <Settings className="w-4 h-4" />
              Config
            </Button>
            <Button
              onClick={refreshDashboardData}
              disabled={loading}
              className="gap-2"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Sync Now
            </Button>
          </div>
        </div>

        {/* Integration Grid */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle>Connected Integrations</CardTitle>
              <CardDescription>
                Click to manage individual integrations
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/integrations")}
              className="gap-2"
            >
              View All
              <ArrowRight className="w-4 h-4" />
            </Button>
          </CardHeader>

          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-4">
              {integrations.map((integration) => {
                const IconComponent = integration.icon;
                return (
                  <Card
                    key={integration.id}
                    className="cursor-pointer hover:shadow-md transition-all hover:-translate-y-0.5"
                    onClick={() => handleIntegrationClick(integration.id)}
                  >
                    <CardContent className="p-6">
                      <div className="flex flex-col space-y-4">
                        <div className="flex justify-between items-start">
                          <div className="flex items-center space-x-3">
                            <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                              <IconComponent className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div>
                              <h3 className="font-bold text-lg">
                                {integration.name}
                              </h3>
                              <Badge variant="secondary" className="mt-1">
                                {integration.category}
                              </Badge>
                            </div>
                          </div>
                          {getStatusIcon(integration.health)}
                        </div>

                        <div className="space-y-2 pt-2">
                          <div className="flex justify-between items-center text-sm">
                            <span className="text-gray-500">Status:</span>
                            {getStatusBadge(integration.health)}
                          </div>
                          <div className="flex justify-between items-center text-sm">
                            <span className="text-gray-500">Connection:</span>
                            <div className="flex items-center space-x-1">
                              <span>
                                {integration.connected
                                  ? "Connected"
                                  : "Disconnected"}
                              </span>
                              {integration.connected ? (
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              ) : (
                                <AlertTriangle className="w-4 h-4 text-red-500" />
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {integrations.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-full">
                  <LayoutDashboard className="w-12 h-12 text-gray-400" />
                </div>
                <p className="text-gray-600 text-lg">
                  No integrations connected yet
                </p>
                <Button onClick={() => router.push("/integrations")}>
                  Connect Integrations
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>
              Latest integration events and syncs
            </CardDescription>
          </CardHeader>

          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
                <div className="flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-gray-500" />
                  <span>Next.js integration connected</span>
                </div>
                <span className="text-sm text-gray-500">2 minutes ago</span>
              </div>

              <div className="flex justify-between items-center py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
                <div className="flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-gray-500" />
                  <span>GitHub repositories synced</span>
                </div>
                <span className="text-sm text-gray-500">15 minutes ago</span>
              </div>

              <div className="flex justify-between items-center py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
                <div className="flex items-center space-x-3">
                  <Clock className="w-4 h-4 text-gray-500" />
                  <span>Slack channels updated</span>
                </div>
                <span className="text-sm text-gray-500">1 hour ago</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DashboardPage;
