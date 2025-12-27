/**
 * Main Integrations Page
 * Display all available ATOM integrations
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
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  status: "complete" | "in-progress" | "planned";
  connected: boolean;
  icon: any;
  color: string;
  lastSync?: string;
  health?: "healthy" | "warning" | "error" | "unknown";
  documentation?: string;
}

const IntegrationsPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const { toast } = useToast();
  const router = useRouter();

  const integrationList: Integration[] = [
    // Storage & File Management
    {
      id: "box",
      name: "Box",
      description: "Secure file storage and collaboration platform",
      category: "storage",
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
      connected: false,
      icon: HardDrive,
      color: "text-blue-600",
      documentation: "https://www.zoho.com/workdrive/api.html",
    },

    // Communication & Collaboration
    {
      id: "slack",
      name: "Slack",
      description: "Team communication and collaboration platform",
      category: "communication",
      status: "complete",
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
      status: "complete",
      connected: false,
      icon: MessageSquare,
      color: "text-purple-600",
      documentation:
        "https://docs.microsoft.com/en-us/microsoftteams/platform/overview",
    },
    {
      id: "gmail",
      name: "Gmail",
      description: "Email communication and organization platform",
      category: "communication",
      status: "complete",
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
      status: "complete",
      connected: false,
      icon: Mail,
      color: "text-blue-600",
      documentation:
        "https://docs.microsoft.com/en-us/graph/api/resources/outlook",
    },

    // Productivity & Project Management
    {
      id: "notion",
      name: "Notion",
      description: "Document management and knowledge base platform",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: Edit,
      color: "text-gray-600",
      documentation: "https://developers.notion.com/",
    },
    {
      id: "jira",
      name: "Jira",
      description: "Project management and issue tracking platform",
      category: "productivity",
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
      connected: false,
      icon: Github,
      color: "text-black",
      documentation: "https://docs.github.com/en/rest",
    },
    {
      id: "gitlab",
      name: "GitLab",
      description: "DevOps platform and code repository management",
      category: "development",
      status: "complete",
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
      status: "complete",
      connected: false,
      icon: Code,
      color: "text-black",
      documentation: "https://vercel.com/docs/api",
    },

    // Finance & Accounting
    {
      id: "stripe",
      name: "Stripe",
      description: "Payment processing and financial management platform",
      category: "finance",
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
      status: "complete",
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
        fetch("/api/integrations/quickbooks/health"),
        fetch("/api/integrations/hubspot/health"),
        fetch("/api/integrations/zendesk/health"),
        fetch("/api/integrations/xero/health"),
        fetch("/api/integrations/salesforce/health"),
        fetch("/api/integrations/microsoft365/health"),
        fetch("/api/integrations/azure/health"),
        fetch("/api/integrations/teams/health"),
        fetch("/api/zoho-workdrive/health"),
      ]);

      const updatedIntegrations = integrationList.map((integration, index) => {
        const healthResponse = healthChecks[index];
        const isHealthy = healthResponse?.ok || false;
        return {
          ...integration,
          connected: isHealthy,
          health: (isHealthy ? "healthy" : "error") as "healthy" | "error",
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
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const handleIntegrationClick = (integration: Integration) => {
    if (integration.status === "complete") {
      // Navigate to integration-specific page
      window.location.href = `/integrations/${integration.id}`;
    } else {
      toast({
        title: "Coming Soon",
        description: `${integration.name} integration is ${integration.status}`,
      });
    }
  };

  const filteredIntegrations =
    selectedCategory === "all"
      ? integrations
      : integrations.filter((i) => i.category === selectedCategory);

  const connectedCount = integrations.filter((i) => i.connected).length;
  const connectionProgress = (connectedCount / integrations.length) * 100;

  useEffect(() => {
    checkIntegrationsHealth();

    // Auto-refresh every 2 minutes
    const interval = setInterval(checkIntegrationsHealth, 120000);
    return () => clearInterval(interval);
  }, []);

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
                  <p className="text-sm text-gray-600">
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
                  <span className="text-gray-600">Connection Progress</span>
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
                  <p className="text-sm text-gray-600">
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
                  <p className="text-sm text-gray-600">Healthy</p>
                </div>
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-yellow-600">
                    {integrations.filter((i) => i.health === "warning").length}
                  </p>
                  <p className="text-sm text-gray-600">Warnings</p>
                </div>
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-red-600">
                    {integrations.filter((i) => i.health === "error").length}
                  </p>
                  <p className="text-sm text-gray-600">Errors</p>
                </div>
                <div className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <p className="text-2xl font-bold text-gray-600">
                    {
                      integrations.filter(
                        (i) => !i.health || i.health === "unknown",
                      ).length
                    }
                  </p>
                  <p className="text-sm text-gray-600">Unknown</p>
                </div>
              </div>

              <p className="text-sm text-center text-gray-500">
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
                className="cursor-pointer hover:shadow-md transition-all hover:-translate-y-0.5"
                onClick={() => handleIntegrationClick(integration)}
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                      <IconComponent className={cn("w-6 h-6", integration.color)} />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg">{integration.name}</h3>
                      <Badge
                        variant={
                          integration.status === "complete"
                            ? "default"
                            : integration.status === "in-progress"
                              ? "secondary"
                              : "outline"
                        }
                        className={
                          integration.status === "complete" ? "bg-green-500 hover:bg-green-600" :
                            integration.status === "in-progress" ? "bg-yellow-500 hover:bg-yellow-600" : ""
                        }
                      >
                        {integration.status}
                      </Badge>
                    </div>
                  </div>
                  {getStatusIcon(integration.health || "unknown")}
                </CardHeader>

                <CardContent className="pt-4">
                  <div className="flex flex-col space-y-4">
                    <p className="text-sm text-gray-600 min-h-[40px]">
                      {integration.description}
                    </p>

                    <div className="h-px bg-gray-100 dark:bg-gray-800" />

                    <div className="flex justify-between items-center">
                      <span className="text-xs text-gray-500">
                        Category: {integration.category}
                      </span>
                      {integration.connected && (
                        <div className="flex items-center space-x-1">
                          <CheckCircle className="w-3 h-3 text-green-500" />
                          <span className="text-xs font-bold text-green-500">
                            Connected
                          </span>
                        </div>
                      )}
                    </div>

                    <Button
                      variant="outline"
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
