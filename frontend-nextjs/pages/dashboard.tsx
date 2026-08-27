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
import { useToast } from "@/components/ui/use-toast";
import { GettingStartedCard } from "@/components/Onboarding/GettingStartedCard";
import {
  ArrowRight,
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
  Zap,
} from "lucide-react";

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
  const workspaceId = "default"; // Consistent with other components

  const integrationIcons: Record<string, any> = {
    zoho: List,
    microsoft: CheckSquare,
    outlook: Mail,
    google: HardDrive,
    gmail: Mail,
    slack: MessageSquare,
    github: Github,
    notion: CheckSquare,
    dropbox: HardDrive,
    box: HardDrive,
    trello: List,
    asana: CheckSquare,
    stripe: CreditCard,
  };

  // Real OAuth connections only — providers the user actually granted via
  // the consent flow (IntegrationToken/OAuthToken store). No hardcoded list.
  const providerMeta: Record<string, { name: string; category: string }> = {
    zoho: { name: "Zoho Suite (CRM · Books · Inventory · Projects · WorkDrive)", category: "business" },
    microsoft: { name: "Microsoft 365", category: "productivity" },
    outlook: { name: "Outlook", category: "communication" },
    google: { name: "Google Workspace", category: "productivity" },
    gmail: { name: "Gmail", category: "communication" },
    slack: { name: "Slack", category: "communication" },
    github: { name: "GitHub", category: "development" },
    notion: { name: "Notion", category: "productivity" },
    dropbox: { name: "Dropbox", category: "storage" },
    box: { name: "Box", category: "storage" },
    trello: { name: "Trello", category: "productivity" },
    asana: { name: "Asana", category: "productivity" },
    linkedin: { name: "LinkedIn", category: "communication" },
    salesforce: { name: "Salesforce", category: "crm" },
    whatsapp: { name: "WhatsApp Business", category: "communication" },
    stripe: { name: "Stripe", category: "finance" },
  };

  const refreshDashboardData = async () => {
    // BUG-102: AbortController + 10s timeout so one hung fetch can't freeze
    // the loading state forever.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      setLoading(true);

      const token = typeof window !== "undefined" ? (localStorage.getItem("auth_token") || localStorage.getItem("token")) : null;
      const headers: Record<string, string> = token ? { "Authorization": `Bearer ${token}` } : {};

      // Real connected integrations: the OAuth grant store. An entry appears
      // here only after the user completed a provider consent flow.
      const tokensRes = await fetch("/api/v1/auth/oauth/tokens", { headers, signal: controller.signal }).catch(() => ({ ok: false } as Response));

      let oauthList: Array<{ provider: string; status: string; expires_at?: string | null }> = [];
      if (tokensRes.ok) {
        const data = await tokensRes.json().catch((): null => null);
        oauthList = Array.isArray(data?.integrations) ? data.integrations : [];
      }

      const updatedIntegrations = oauthList.map((row) => {
        const meta = providerMeta[row.provider] || { name: row.provider, category: "integration" };
        return {
          id: row.provider,
          name: meta.name,
          category: meta.category,
          connected: row.status === "active",
          health: row.status === "active" ? "healthy" : "error",
          expires_at: row.expires_at || null,
          icon: integrationIcons[row.provider] || Activity,
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
        fetch(`/api/v1/accounting/dashboard/summary?workspace_id=${workspaceId}`).catch((): null => null),
        fetch(`/api/sales/dashboard/summary?workspace_id=${workspaceId}`).catch((): null => null)
      ]);

      const safeParseJson = async (res: Response | null) => {
        if (!res || !res.ok) return null;
        try {
          const contentType = res.headers.get("content-type");
          if (contentType && contentType.includes("application/json")) {
            return await res.json();
          }
        } catch (e) {
          console.warn("JSON parse error:", e);
        }
        return null;
      };

      const finData = await safeParseJson(finRes);
      if (finData) setFinancials(finData);

      const salesData = await safeParseJson(salesRes);
      if (salesData) setSales(salesData);

    } catch (error) {
      console.error("Dashboard refresh failed:", error);
      toast({
        title: "Refresh failed",
        description: "Could not fetch latest intelligence data.",
        variant: "error",
      });
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  };

  const handleIntegrationClick = (integrationId: string) => {
    router.push(`/integrations/${integrationId}`);
  };

  const getStatusIcon = (health: string) => {
    return health === "healthy" ? (
      <CheckCircle className="w-5 h-5 text-green-500" />
    ) : (
      <AlertTriangle className="w-5 h-5 text-red-500" />
    );
  };

  const getStatusBadge = (health: string) => {
    // Custom coloring since Shadcn badges are limited
    const className =
      health === "healthy"
        ? "bg-green-500 hover:bg-green-600"
        : "bg-red-500 hover:bg-red-600";

    return (
      <Badge className={className}>
        {health}
      </Badge>
    );
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
        {/* First-job guidance (provider → first agent → first run).
            Auto-hides when all steps are done; dismissible + restorable. */}
        <GettingStartedCard />

        {/* Header */}
        <div className="space-y-2">
          <h1 data-testid="dashboard-welcome-message" className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
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
                <div className="flex justify-between items-center text-sm font-medium text-gray-500 dark:text-gray-400">
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
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Runway: <span className="font-bold text-blue-600">{financials?.runway_months || "0"} months</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-orange-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500 dark:text-gray-400">
                  <span>Sales Pipeline</span>
                  <TrendingUp className="w-4 h-4 text-orange-600" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    ${sales?.pipeline_value?.toLocaleString() || "0"}
                  </span>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {sales?.total_leads > 0 && (
                    <span className="mr-2">
                      Leads: <span className="font-bold text-orange-600">{sales.total_leads}</span>
                    </span>
                  )}
                  Forecast (weighted): <span className="font-bold text-orange-600">${sales?.weighted_forecast?.toLocaleString() || "0"}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-purple-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500 dark:text-gray-400">
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
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Avg. Conversion: <span className="font-bold text-purple-600">{sales?.conversion_rate || "0"}%</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-red-600">
            <CardContent className="pt-6">
              <div className="flex flex-col space-y-2">
                <div className="flex justify-between items-center text-sm font-medium text-gray-500 dark:text-gray-400">
                  <span>Accounts Payable</span>
                  <TrendingDown className="w-4 h-4 text-red-600" />
                </div>
                <div className="flex items-baseline space-x-2">
                  <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    ${financials?.accounts_payable?.toLocaleString() || "0"}
                  </span>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
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
                            <span className="text-gray-500 dark:text-gray-400">Status:</span>
                            {getStatusBadge(integration.health)}
                          </div>
                          <div className="flex justify-between items-center text-sm">
                            <span className="text-gray-500 dark:text-gray-400">Connection:</span>
                            <div className="flex items-center space-x-1">
                              <span>
                                {integration.connected
                                  ? "Connected"
                                  : "Expired"}
                              </span>
                              {integration.connected ? (
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              ) : (
                                <AlertTriangle className="w-4 h-4 text-red-500" />
                              )}
                            </div>
                          </div>
                          {integration.connected && integration.expires_at && (
                            <div className="flex justify-between items-center text-sm">
                              <span className="text-gray-500 dark:text-gray-400">Token expires:</span>
                              <span className="text-gray-500 dark:text-gray-400 text-xs">
                                {new Date(integration.expires_at).toLocaleString()} (auto-renews)
                              </span>
                            </div>
                          )}
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
                <p className="text-gray-600 dark:text-gray-400 text-lg">
                  No integrations connected yet
                </p>
                <Button onClick={() => router.push("/integrations")}>
                  Connect Integrations
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        </div>
    </div>
  );
};

export default DashboardPage;
