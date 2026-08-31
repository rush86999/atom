/**
 * Main Integrations Page
 * Display all available ATOM integrations
 */

import React, { useState, useEffect, useRef } from "react";
import { authFetch } from "@/lib/auth-headers";
import { useRouter } from "next/router";
import { authHeaders } from "@/lib/auth-headers";
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
  Search,
  Star,
  Sun,
  Eye,
  User,
  Phone,
  ExternalLink,
  Info,
  Lock,
  Unlock,
  Download,
  Upload,
  Edit,
  ShoppingCart,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  connected: boolean;
  icon: any;
  color: string;
  lastSync?: string;
  health?: "healthy" | "warning" | "error" | "unknown";
  documentation?: string;
}

// Ingestion progress per integration id, from
// /api/integrations/ingestion-status — memory-store records where the
// integration has a poller, hybrid sync state otherwise.
interface IngestionProgress {
  records_ingested: number;
  last_ingested: string | null;
  stream_running: boolean;
  last_synced?: string | null;
  auto_sync_enabled?: boolean;
}

const formatIngestedAge = (iso: string | null): string => {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "never";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

const IntegrationsPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  // Real per-integration connection state from /api/integrations/connection-status
  const connectionStatusRef = useRef<Record<string, { connected: boolean }>>({});
  const [ingestionProgress, setIngestionProgress] = useState<
    Record<string, IngestionProgress>
  >({});
  const { toast } = useToast();
  const router = useRouter();

  const integrationList: Integration[] = [
    // Storage & File Management
    {
      id: "box",
      name: "Box",
      description: "Secure file storage and collaboration platform",
      category: "storage",
      connected: false,
      icon: HardDrive,
      color: "text-blue-600",
      documentation: "https://developer.box.com/",
    },
    {
      id: "dropbox",
      name: "Dropbox",
      description: "Cloud storage and file sharing service",
      category: "storage",
      connected: false,
      icon: Download,
      color: "text-blue-600",
      documentation: "https://www.dropbox.com/developers/documentation",
    },
    {
      id: "gdrive",
      name: "Google Drive",
      description: "Cloud storage and document management platform",
      category: "storage",
      connected: false,
      icon: HardDrive,
      color: "text-green-600",
      documentation: "https://developers.google.com/drive",
    },
    {
      id: "onedrive",
      name: "OneDrive",
      description: "Microsoft cloud storage and file synchronization service",
      category: "storage",
      connected: false,
      icon: Download,
      color: "text-blue-600",
      documentation:
        "https://docs.microsoft.com/en-us/graph/api/resources/onedrive",
    },
    {
      id: "zoho-workdrive",
      name: "Zoho WorkDrive",
      description: "Online file management for teams that work together",
      category: "storage",
      connected: false,
      icon: HardDrive,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/workdrive/api.html",
    },

    // Zoho suite — one Server-based app grant connects all of them (the
    // unified /api/v1/auth/oauth/zoho/initiate flow writes tokens for every
    // service). Cards exist for each app; the Connect button on each detail
    // page runs the same single consent.
    {
      id: "zoho-books",
      name: "Zoho Books",
      description: "Accounting — invoices, expenses and chart of accounts",
      category: "finance",
      connected: false,
      icon: Activity,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/books/api/v3/",
    },
    {
      id: "zoho-inventory",
      name: "Zoho Inventory",
      description: "Inventory — items, stock levels and sales orders",
      category: "ecommerce",
      connected: false,
      icon: Activity,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/inventory/api/v1/",
    },
    {
      id: "zoho-crm",
      name: "Zoho CRM",
      description: "Customer relationship management — leads and deals",
      category: "crm",
      connected: false,
      icon: User,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/crm/developer/docs/api/v7/",
    },
    {
      id: "zoho-projects",
      name: "Zoho Projects",
      description: "Project management — portals, projects and tasks",
      category: "productivity",
      connected: false,
      icon: List,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/projects/api/",
    },
    {
      id: "zoho-mail",
      name: "Zoho Mail",
      description: "Business email and communication",
      category: "communication",
      connected: false,
      icon: Mail,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/mail/help/api/",
    },
    // Forms/Flow expose no public read API (Zoho's official position), so
    // they are webhook-push apps: data ingests when Zoho pushes events,
    // not via the OAuth pull sync the siblings use. Cards light up with
    // the suite grant or their webhook secret env.
    {
      id: "zoho-forms",
      name: "Zoho Forms",
      description: "Form builder — submissions ingest via webhook push",
      category: "productivity",
      connected: false,
      icon: Edit,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/forms/help/",
    },
    {
      id: "zoho-flow",
      name: "Zoho Flow",
      description: "Automation platform — flow events ingest via webhook push",
      category: "productivity",
      connected: false,
      icon: RefreshCw,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/flow/help/",
    },

    // Communication & Collaboration
    {
      id: "telegram",
      name: "Telegram",
      description: "Teammate IM channel — long-polling bot, no public URL needed (see IM Adapter Setup)",
      category: "communication",
      connected: false,
      icon: MessageSquare,
      color: "text-sky-500",
      documentation: "https://core.telegram.org/bots/api",
    },
    {
      id: "slack",
      name: "Slack",
      description: "Team communication and collaboration platform",
      category: "communication",
      connected: false,
      icon: MessageSquare,
      color: "text-purple-600",
      documentation: "https://api.slack.com/",
    },
    {
      id: "teams",
      name: "Microsoft Teams",
      description: "Team messaging and collaboration platform",
      category: "communication",
      connected: false,
      icon: MessageSquare,
      color: "text-purple-600",
      documentation:
        "https://docs.microsoft.com/en-us/microsoftteams/platform/overview",
    },
    {
      id: "whatsapp",
      name: "WhatsApp Business",
      description: "WhatsApp Business messaging — send, receive and search conversations",
      category: "communication",
      connected: false,
      icon: MessageSquare,
      color: "text-green-600",
      documentation: "https://developers.facebook.com/docs/whatsapp",
    },
    {
      id: "gmail",
      name: "Gmail",
      description: "Email communication and organization platform",
      category: "communication",
      connected: false,
      icon: Mail,
      color: "text-red-600",
      documentation: "https://developers.google.com/gmail/api",
    },
    {
      id: "outlook",
      name: "Outlook",
      description: "Email, calendar, and contact management service",
      category: "communication",
      connected: false,
      icon: Mail,
      color: "text-blue-600",
      documentation:
        "https://docs.microsoft.com/en-us/graph/api/resources/outlook",
    },
    {
      id: "shopify",
      name: "Shopify",
      description: "Ecommerce store — agents create product listings and blog posts",
      category: "ecommerce",
      connected: false,
      icon: ShoppingCart,
      color: "text-green-600",
      documentation: "https://shopify.dev/docs/api/admin-graphql",
    },

    // Productivity & Project Management
    {
      id: "notion",
      name: "Notion",
      description: "Document management and knowledge base platform",
      category: "productivity",
      connected: false,
      icon: Edit,
      color: "text-gray-600 dark:text-gray-400",
      documentation: "https://developers.notion.com/",
    },
    {
      id: "monday",
      name: "Monday.com",
      description: "Work OS — automate boards, items and analytics",
      category: "productivity",
      connected: false,
      icon: CheckSquare,
      color: "text-red-500",
      documentation: "https://developer.monday.com/",
    },
    {
      id: "jira",
      name: "Jira",
      description: "Project management and issue tracking platform",
      category: "productivity",
      connected: false,
      icon: Settings,
      color: "text-blue-600",
      documentation:
        "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
    },
    {
      id: "trello",
      name: "Trello",
      description: "Project management and task tracking tool",
      category: "productivity",
      connected: false,
      icon: List,
      color: "text-blue-600",
      documentation:
        "https://developer.atlassian.com/cloud/trello/rest/api-group/",
    },
    {
      id: "asana",
      name: "Asana",
      description: "Project management and task tracking platform",
      category: "productivity",
      connected: false,
      icon: CheckSquare,
      color: "text-green-600",
      documentation: "https://developers.asana.com/docs",
    },
    {
      id: "linear",
      name: "Linear",
      description: "Issue tracking and project management platform",
      category: "productivity",
      connected: false,
      icon: List,
      color: "text-blue-600",
      documentation: "https://developers.linear.app/",
    },
    {
      id: "google-workspace",
      name: "Google Workspace",
      description:
        "Complete productivity suite (Docs, Sheets, Slides, Keep, Tasks)",
      category: "productivity",
      connected: false,
      icon: Edit,
      color: "text-orange-600",
      documentation: "https://developers.google.com/workspace",
    },
    {
      id: "microsoft365",
      name: "Microsoft 365",
      description:
        "Complete productivity suite with Teams, Outlook, and OneDrive",
      category: "productivity",
      connected: false,
      icon: Settings,
      color: "text-blue-600",
      documentation: "https://learn.microsoft.com/en-us/graph/overview",
    },

    // Development & Code Management
    {
      id: "github",
      name: "GitHub",
      description: "Code repository and development platform",
      category: "development",
      connected: false,
      icon: Github,
      color: "text-black dark:text-white",
      documentation: "https://docs.github.com/en/rest",
    },
    {
      id: "gitlab",
      name: "GitLab",
      description: "DevOps platform and code repository management",
      category: "development",
      connected: false,
      icon: Code,
      color: "text-orange-600",
      documentation: "https://docs.gitlab.com/ee/api/",
    },
    {
      id: "nextjs",
      name: "Next.js",
      description: "Vercel project management and deployment platform",
      category: "development",
      connected: false,
      icon: Code,
      color: "text-black dark:text-white",
      documentation: "https://vercel.com/docs/api",
    },

    // Finance & Accounting
    {
      id: "stripe",
      name: "Stripe",
      description: "Payment processing and financial management platform",
      category: "finance",
      connected: false,
      icon: CreditCard,
      color: "text-green-600",
      documentation: "https://stripe.com/docs/api",
    },
    {
      id: "xero",
      name: "Xero",
      description: "Accounting and financial management platform",
      category: "finance",
      connected: false,
      icon: Activity,
      color: "text-green-600",
      documentation: "https://developer.xero.com/",
    },
    {
      id: "quickbooks",
      name: "QuickBooks",
      description: "Financial management and accounting platform",
      category: "finance",
      connected: false,
      icon: Activity,
      color: "text-green-600",
      documentation: "https://developer.intuit.com/app/developer/qbo/docs/api",
    },

    // CRM & Sales
    {
      id: "salesforce",
      name: "Salesforce",
      description: "Customer relationship management and sales platform",
      category: "crm",
      connected: false,
      icon: User,
      color: "text-blue-600",
      documentation: "https://developer.salesforce.com/docs/api",
    },
    {
      id: "hubspot",
      name: "HubSpot",
      description: "Marketing automation and CRM platform",
      category: "crm",
      connected: false,
      icon: Star,
      color: "text-orange-600",
      documentation: "https://developers.hubspot.com/",
    },

    // Customer Support
    {
      id: "intercom",
      name: "Intercom",
      description: "Customer communication and support platform",
      category: "support",
      connected: false,
      icon: MessageSquare,
      color: "text-green-600",
      documentation:
        "https://developers.intercom.com/intercom-api-reference/reference",
    },
    {
      id: "freshdesk",
      name: "Freshdesk",
      description: "Customer support and help desk platform",
      category: "support",
      connected: false,
      icon: MessageSquare,
      color: "text-green-600",
      documentation: "https://developers.freshdesk.com/api/",
    },
    {
      id: "zendesk",
      name: "Zendesk",
      description: "Customer support and help desk platform",
      category: "support",
      connected: false,
      icon: MessageSquare,
      color: "text-red-600",
      documentation: "https://developer.zendesk.com/api_reference/",
    },

    // Marketing & Automation
    {
      id: "mailchimp",
      name: "Mailchimp",
      description: "Email marketing and automation platform",
      category: "marketing",
      connected: false,
      icon: Mail,
      color: "text-blue-600",
      documentation: "https://mailchimp.com/developer/marketing/",
    },

    // Analytics & Business Intelligence
    {
      id: "tableau",
      name: "Tableau",
      description: "Business intelligence and analytics platform",
      category: "analytics",
      connected: false,
      icon: Activity,
      color: "text-purple-600",
      documentation: "https://help.tableau.com/current/api/en-us/api.htm",
    },

    // Cloud & Infrastructure
    {
      id: "azure",
      name: "Microsoft Azure",
      description: "Cloud computing platform for infrastructure and services",
      category: "cloud",
      connected: false,
      icon: Sun,
      color: "text-blue-600",
      documentation: "https://docs.microsoft.com/en-us/rest/api/azure/",
    },
  ];

  const categories = [
    { id: "all", name: "All Integrations", count: integrationList.length },
    {
      id: "storage",
      name: "File Storage",
      count: integrationList.filter((i) => i.category === "storage").length,
    },
    {
      id: "communication",
      name: "Communication",
      count: integrationList.filter((i) => i.category === "communication")
        .length,
    },
    {
      id: "productivity",
      name: "Productivity",
      count: integrationList.filter((i) => i.category === "productivity")
        .length,
    },
    {
      id: "development",
      name: "Development",
      count: integrationList.filter((i) => i.category === "development").length,
    },
    {
      id: "finance",
      name: "Finance",
      count: integrationList.filter((i) => i.category === "finance").length,
    },
    {
      id: "ecommerce",
      name: "E-Commerce",
      count: integrationList.filter((i) => i.category === "ecommerce").length,
    },
    {
      id: "crm",
      name: "CRM",
      count: integrationList.filter((i) => i.category === "crm").length,
    },
    {
      id: "support",
      name: "Support",
      count: integrationList.filter((i) => i.category === "support").length,
    },
    {
      id: "marketing",
      name: "Marketing",
      count: integrationList.filter((i) => i.category === "marketing").length,
    },
    {
      id: "analytics",
      name: "Analytics",
      count: integrationList.filter((i) => i.category === "analytics").length,
    },
    {
      id: "cloud",
      name: "Cloud",
      count: integrationList.filter((i) => i.category === "cloud").length,
    },
  ];

  const checkIntegrationsHealth = async () => {
    try {
      // Map integration IDs to their health-check URLs so results are keyed
      // by ID, not by array position (which was causing misaligned status pills).
      const healthUrls: Record<string, string> = {
        box: "/api/integrations/box/health",
        dropbox: "/api/integrations/dropbox/health",
        "gdrive": "/api/integrations/gdrive/health",
        slack: "/api/integrations/slack/health",
        gmail: "/api/integrations/gmail/health",
        notion: "/api/integrations/notion/health",
        jira: "/api/integrations/jira/health",
        github: "/api/integrations/github/health",
        nextjs: "/api/nextjs/health",
        stripe: "/api/integrations/stripe/health",
        linear: "/api/integrations/linear/health",
        outlook: "/api/integrations/outlook/health",
        asana: "/api/integrations/asana/health",
        quickbooks: "/api/integrations/quickbooks/health",
        hubspot: "/api/integrations/hubspot/health",
        zendesk: "/api/integrations/zendesk/health",
        xero: "/api/integrations/xero/health",
        salesforce: "/api/integrations/salesforce/health",
        "microsoft365": "/api/integrations/microsoft365/health",
        azure: "/api/integrations/azure/health",
        teams: "/api/integrations/teams/health",
        "zoho-workdrive": "/api/zoho-workdrive/health",
                // Zoho suite cards share the WorkDrive health proxy (same backend
        // process; reflects the suite's connectivity on the hub).
        "zoho-books": "/api/zoho-workdrive/health",
        "zoho-inventory": "/api/zoho-workdrive/health",
        "zoho-crm": "/api/zoho-workdrive/health",
        "zoho-projects": "/api/zoho-workdrive/health",
        "zoho-mail": "/api/zoho-workdrive/health",
        // Forms/Flow have their own dependency-light /health routes
        // (webhook-push apps; no OAuth token needed to answer).
        "zoho-forms": "/api/v1/integrations/zoho-forms/health",
        "zoho-flow": "/api/v1/integrations/zoho-flow/health",
        // BUG-072: 8 integrations were missing from this map, causing them
        // to always show "error" / unconnected even when healthy.
        onedrive: "/api/integrations/onedrive/health",
        trello: "/api/integrations/trello/health",
        "google-workspace": "/api/integrations/google-workspace/health",
        gitlab: "/api/integrations/gitlab/health",
        intercom: "/api/integrations/intercom/health",
        freshdesk: "/api/integrations/freshdesk/health",
        mailchimp: "/api/integrations/mailchimp/health",
        tableau: "/api/integrations/tableau/health",
        // Round 80: probe the newer cards too (public endpoints)
        telegram: "/api/telegram/health",
        whatsapp: "/api/whatsapp/health",
        shopify: "/api/integrations/shopify/health",
        monday: "/api/monday/status",
      };

      const healthResults: Record<string, boolean> = {};
      const entries = Object.entries(healthUrls);
      const responses = await Promise.all([
        ...entries.map(async ([id, url]) => {
          try {
            // Several health routes (e.g. /api/zoho-workdrive/health) sit
            // behind router-level auth — send the session's Bearer header
            // so a connected integration isn't reported down.
            const resp = await authFetch(url, { headers: authHeaders() });
            return [id, resp.ok] as const;
          } catch {
            return [id, false] as const;
          }
        }),
        // Real connection state (DB connections + tenant connectors + env
        // credentials). Health probes above only prove a backend route is
        // up — they must NOT decide "connected".
        authFetch("/api/integrations/connection-status", { headers: authHeaders() })
          .then((r) => (r.ok ? r.json() : { providers: {} }))
          .then((d) => ["__connectionStatus", d?.data?.providers ?? d?.providers ?? {}] as const)
          .catch(() => ["__connectionStatus", {}] as const),
        // Memory-ingestion progress (records ingested per integration).
        authFetch("/api/integrations/ingestion-status", { headers: authHeaders() })
          .then((r) => (r.ok ? r.json() : { apps: {} }))
          .then((d) => ["__ingestionStatus", d?.data?.apps ?? d?.apps ?? {}] as const)
          .catch(() => ["__ingestionStatus", {}] as const),
      ]);
      for (const [id, ok] of responses) {
        if (id === "__connectionStatus") {
          connectionStatusRef.current = ok as Record<string, { connected: boolean }>;
        } else if (id === "__ingestionStatus") {
          setIngestionProgress(ok as Record<string, IngestionProgress>);
        } else {
          healthResults[id] = ok as boolean;
        }
      }

      const updatedIntegrations = integrationList.map((integration) => {
        const isConnected =
          connectionStatusRef.current[integration.id]?.connected === true;
        const isHealthy = healthResults[integration.id] ?? false;
        return {
          ...integration,
          // "Connected" reflects real credential/connection state only.
          connected: isConnected,
          health: (isConnected
            ? isHealthy
              ? "healthy"
              : "error"
            : "unknown") as "healthy" | "error" | "unknown",
        };
      });

      setIntegrations(updatedIntegrations);
    } catch (error) {
      console.error("Health check failed:", error);
      setIntegrations(integrationList);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "warning":
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case "error":
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500 dark:text-gray-400" />;
    }
  };

  const handleIntegrationClick = (integration: Integration) => {
    window.location.href = `/integrations/${integration.id}`;
  };

  const filteredIntegrations =
    selectedCategory === "all"
      ? integrations
      : integrations.filter((i) => i.category === selectedCategory);

  const connectedCount = integrations.filter((i) => i.connected).length;
  const connectionProgress =
    integrations.length > 0 ? (connectedCount / integrations.length) * 100 : 0;

  const categoryLabel = (id: string) =>
    categories.find((c) => c.id === id)?.name ?? id;

  useEffect(() => {
    checkIntegrationsHealth();

    // Auto-refresh every 2 minutes
    const interval = setInterval(checkIntegrationsHealth, 120000);
    return () => clearInterval(interval);
  }, []);

  // Deep-link support: /integrations?connect=<provider> highlights and
  // prompts that provider's card. Readiness CTAs on imported workflow
  // templates land here so the user lands on the exact fix.
  const [highlightedIntegration, setHighlightedIntegration] = useState<string | null>(null);
  useEffect(() => {
    if (router.isReady === false) return;
    const raw = router.query.connect;
    const target = Array.isArray(raw) ? raw[0] : raw;
    if (!target) return;
    const match = integrationList.find((i) => i.id === target.toLowerCase());
    router.replace("/integrations", undefined, { shallow: true });
    if (!match) return;
    setHighlightedIntegration(match.id);
    toast({
      title: `Connect ${match.name}`,
      description: "Finish this connection to run your imported workflow.",
    });
    const scrollTimer = setTimeout(() => {
      document
        .getElementById(`integration-${match.id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 150);
    return () => clearTimeout(scrollTimer);
  }, [router.isReady, router.query.connect, router, toast]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
            ATOM Integrations Hub
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-400">
            Connect your favorite tools and services to ATOM Agent
          </p>
        </div>

        {/* Connection Overview */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col space-y-4">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <h2 className="text-xl font-bold">
                    {connectedCount} of {integrations.length} Connected
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Manage your connected integrations
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={checkIntegrationsHealth}
                  disabled={loading}
                  className="gap-2"
                >
                  {loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Refresh Status
                </Button>
              </div>

              <div className="space-y-2">
                <Progress value={connectionProgress} className="h-2" />
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Connection Progress</span>
                  <span className="font-bold">
                    {Math.round(connectionProgress)}%
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Health Monitoring */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col space-y-4">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <h2 className="text-xl font-bold">Integration Health</h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Monitor real-time status of all integrations
                  </p>
                </div>
                <Button
                  onClick={() =>
                    (window.location.href = "/integrations/health")
                  }
                  className="gap-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  View Health Dashboard
                </Button>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-green-600">
                    {integrations.filter((i) => i.health === "healthy").length}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Healthy</p>
                </div>
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-yellow-600">
                    {integrations.filter((i) => i.health === "warning").length}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Warnings</p>
                </div>
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-red-600">
                    {integrations.filter((i) => i.health === "error").length}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Errors</p>
                </div>
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-gray-600 dark:text-gray-400">
                    {
                      integrations.filter(
                        (i) => !i.health || i.health === "unknown",
                      ).length
                    }
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Unknown</p>
                </div>
              </div>

              <p className="text-sm text-center text-gray-500 dark:text-gray-400">
                Click "View Health Dashboard" for detailed monitoring and
                auto-refresh
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Categories Filter */}
        <div className="flex flex-wrap gap-2">
          {categories.map((category) => (
            <Button
              key={category.id}
              variant={selectedCategory === category.id ? "default" : "outline"}
              onClick={() => setSelectedCategory(category.id)}
              size="sm"
              className="gap-2"
            >
              {category.name}
              <Badge variant="secondary" className="ml-1">
                {category.count}
              </Badge>
            </Button>
          ))}
        </div>

        {/* Integrations Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredIntegrations.map((integration) => {
            const IconComponent = integration.icon;
            return (
              <Card
                key={integration.id}
                id={`integration-${integration.id}`}
                className={cn(
                  "cursor-pointer hover:shadow-md transition-all hover:-translate-y-0.5",
                  highlightedIntegration === integration.id &&
                    "ring-2 ring-amber-400 shadow-md",
                )}
                onClick={() => handleIntegrationClick(integration)}
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                      <IconComponent className={cn("w-6 h-6", integration.color)} />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg">{integration.name}</h3>
                    </div>
                  </div>
                  {/* Health is only meaningful once connected — unconnected
                      cards would otherwise show a meaningless "unknown" clock. */}
                  {integration.health &&
                    integration.health !== "unknown" &&
                    getStatusIcon(integration.health)}
                </CardHeader>

                <CardContent className="pt-4">
                  <div className="flex flex-col space-y-4">
                    <p className="text-sm text-gray-600 dark:text-gray-400 min-h-[40px]">
                      {integration.description}
                    </p>

                    <div className="h-px bg-gray-100 dark:bg-gray-800" />

                    <div className="flex justify-between items-center">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {categoryLabel(integration.category)}
                      </span>
                      {integration.connected ? (
                        <div className="flex items-center space-x-1">
                          <CheckCircle className="w-3 h-3 text-green-500" />
                          <span className="text-xs font-bold text-green-500">
                            Connected
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          Not connected
                        </span>
                      )}
                    </div>

                    {/* Ingestion progress: memory records where the
                        integration has a poller, last sync otherwise. */}
                    {(() => {
                      const progress = ingestionProgress[integration.id];
                      if (!progress) return null;
                      if ((progress.records_ingested ?? 0) > 0) {
                        return (
                          <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
                            <span className="font-medium text-gray-700 dark:text-gray-300">
                              {progress.records_ingested.toLocaleString()}{" "}
                              records ingested
                            </span>
                            <span>
                              last {formatIngestedAge(progress.last_ingested)}
                            </span>
                          </div>
                        );
                      }
                      if (progress.last_synced) {
                        return (
                          <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
                            <span className="font-medium text-gray-700 dark:text-gray-300">
                              {progress.auto_sync_enabled ? "Auto-sync on" : "Synced"}
                            </span>
                            <span>
                              {formatIngestedAge(progress.last_synced)}
                            </span>
                          </div>
                        );
                      }
                      return null;
                    })()}

                    <Button
                      variant={integration.connected ? "outline" : "default"}
                      size="sm"
                      className="w-full gap-2"
                    >
                      {integration.connected ? "Manage" : "Connect"}
                      <ArrowRight className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default IntegrationsPage;
