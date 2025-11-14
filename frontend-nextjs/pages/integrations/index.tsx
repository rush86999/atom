/**
 * Main Integrations Page
 * Display all available ATOM integrations
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Divider,
  useColorModeValue,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
} from "@chakra-ui/react";
import {
  // Core Chakra Icons that exist
  TimeIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  StarIcon,
  BuildingIcon,
  SunIcon,
  ViewIcon,
  // Special icons for specific integrations
  EmailIcon,
  ChatIcon,
  EditIcon,
  PhoneIcon,
  ExternalLinkIcon,
  InfoIcon,
  LockIcon,
  UnlockIcon,
  DownloadIcon,
  UploadIcon,
} from "@chakra-ui/icons";

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
  health?: "healthy" | "warning" | "error";
  documentation?: string;
}

const IntegrationsPage: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  const integrationList: Integration[] = [
    // Storage & File Management
    {
      id: "box",
      name: "Box",
      description: "Secure file storage and collaboration platform",
      category: "storage",
      status: "complete",
      connected: false,
      icon: BoxIcon,
      color: "blue",
      documentation: "https://developer.box.com/",
    },
    {
      id: "dropbox",
      name: "Dropbox",
      description: "Cloud storage and file sharing service",
      category: "storage",
      status: "complete",
      connected: false,
      icon: DownloadIcon,
      color: "blue",
      documentation: "https://www.dropbox.com/developers/documentation",
    },
    {
      id: "gdrive",
      name: "Google Drive",
      description: "Cloud storage and document management platform",
      category: "storage",
      status: "complete",
      connected: false,
      icon: ViewIcon,
      color: "green",
      documentation: "https://developers.google.com/drive",
    },
    {
      id: "onedrive",
      name: "OneDrive",
      description: "Microsoft cloud storage and file synchronization service",
      category: "storage",
      status: "complete",
      connected: false,
      icon: DownloadIcon,
      color: "blue",
      documentation: "https://docs.microsoft.com/en-us/graph/api/resources/onedrive",
    },

    // Communication & Collaboration
    {
      id: "slack",
      name: "Slack",
      description: "Team communication and collaboration platform",
      category: "communication",
      status: "complete",
      connected: false,
      icon: ChatIcon,
      color: "purple",
      documentation: "https://api.slack.com/",
    },
    {
      id: "teams",
      name: "Microsoft Teams",
      description: "Team messaging and collaboration platform",
      category: "communication",
      status: "complete",
      connected: false,
      icon: ChatIcon,
      color: "purple",
      documentation: "https://docs.microsoft.com/en-us/microsoftteams/platform/overview",
    },
    {
      id: "gmail",
      name: "Gmail",
      description: "Email communication and organization platform",
      category: "communication",
      status: "complete",
      connected: false,
      icon: EmailIcon,
      color: "red",
      documentation: "https://developers.google.com/gmail/api",
    },
    {
      id: "outlook",
      name: "Outlook",
      description: "Email, calendar, and contact management service",
      category: "communication",
      status: "complete",
      connected: false,
      icon: EmailIcon,
      color: "blue",
      documentation: "https://docs.microsoft.com/en-us/graph/api/resources/outlook",
    },

    // Productivity & Project Management
    {
      id: "notion",
      name: "Notion",
      description: "Document management and knowledge base platform",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: EditIcon,
      color: "gray",
      documentation: "https://developers.notion.com/",
    },
    {
      id: "jira",
      name: "Jira",
      description: "Project management and issue tracking platform",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: SettingsIcon,
      color: "blue",
      documentation: "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
    },
    {
      id: "trello",
      name: "Trello",
      description: "Project management and task tracking tool",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: ViewIcon,
      color: "blue",
      documentation: "https://developer.atlassian.com/cloud/trello/rest/api-group/",
    },
    {
      id: "asana",
      name: "Asana",
      description: "Project management and task tracking platform",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: SettingsIcon,
      color: "green",
      documentation: "https://developers.asana.com/docs",
    },
    {
      id: "linear",
      name: "Linear",
      description: "Issue tracking and project management platform",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: TimeIcon,
      color: "blue",
      documentation: "https://developers.linear.app/",
    },
    {
      id: "google-workspace",
      name: "Google Workspace",
      description: "Complete productivity suite (Docs, Sheets, Slides, Keep, Tasks)",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: EditIcon,
      color: "orange",
      documentation: "https://developers.google.com/workspace",
    },
    {
      id: "microsoft365",
      name: "Microsoft 365",
      description: "Complete productivity suite with Teams, Outlook, and OneDrive",
      category: "productivity",
      status: "complete",
      connected: false,
      icon: SettingsIcon,
      color: "blue",
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
      icon: ViewIcon,
      color: "black",
      documentation: "https://docs.github.com/en/rest",
    },
    {
      id: "gitlab",
      name: "GitLab",
      description: "DevOps platform and code repository management",
      category: "development",
      status: "complete",
      connected: false,
      icon: ViewIcon,
      color: "orange",
      documentation: "https://docs.gitlab.com/ee/api/",
    },
    {
      id: "nextjs",
      name: "Next.js",
      description: "Vercel project management and deployment platform",
      category: "development",
      status: "complete",
      connected: false,
      icon: SettingsIcon,
      color: "black",
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
      icon: StarIcon,
      color: "green",
      documentation: "https://stripe.com/docs/api",
    },
    {
      id: "xero",
      name: "Xero",
      description: "Accounting and financial management platform",
      category: "finance",
      status: "complete",
      connected: false,
      icon: TimeIcon,
      color: "green",
      documentation: "https://developer.xero.com/",
    },
    {
      id: "quickbooks",
      name: "QuickBooks",
      description: "Financial management and accounting platform",
      category: "finance",
      status: "complete",
      connected: false,
      icon: TimeIcon,
      color: "green",
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
      icon: BuildingIcon,
      color: "blue",
      documentation: "https://developer.salesforce.com/docs/api",
    },
    {
      id: "hubspot",
      name: "HubSpot",
      description: "Marketing automation and CRM platform",
      category: "crm",
      status: "complete",
      connected: false,
      icon: StarIcon,
      color: "orange",
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
      icon: ChatIcon,
      color: "green",
      documentation: "https://developers.intercom.com/intercom-api-reference/reference",
    },
    {
      id: "freshdesk",
      name: "Freshdesk",
      description: "Customer support and help desk platform",
      category: "support",
      status: "complete",
      connected: false,
      icon: ChatIcon,
      color: "green",
      documentation: "https://developers.freshdesk.com/api/",
    },
    {
      id: "zendesk",
      name: "Zendesk",
      description: "Customer support and help desk platform",
      category: "support",
      status: "complete",
      connected: false,
      icon: ChatIcon,
      color: "red",
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
      icon: EmailIcon,
      color: "blue",
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
      icon: ViewIcon,
      color: "purple",
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
      icon: SunIcon,
      color: "blue",
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
      ]);

      const updatedIntegrations = integrationList.map((integration, index) => {
        const healthResponse = healthChecks[index];
        return {
          ...integration,
          connected: healthResponse.ok,
          health: healthResponse.ok ? "healthy" : "error",
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
        return <CheckCircleIcon color="green.500" />;
      case "warning":
        return <WarningTwoIcon color="yellow.500" />;
      case "error":
        return <WarningTwoIcon color="red.500" />;
      default:
        return <TimeIcon color="gray.500" />;
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
        status: "info",
        duration: 3000,
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
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={2}>
          <Heading size="2xl">ATOM Integrations Hub</Heading>
          <Text color="gray.600" fontSize="lg">
            Connect your favorite tools and services to ATOM Agent
          </Text>
        </VStack>

        {/* Connection Overview */}
        <Card>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <VStack align="start" spacing={1}>
                  <Text fontWeight="bold" fontSize="xl">
                    {connectedCount} of {integrations.length} Connected
                  </Text>
                  <Text color="gray.600" fontSize="sm">
                    Manage your connected integrations
                  </Text>
                </VStack>
                <Button
                  variant="outline"
                  leftIcon={<TimeIcon />}
                  onClick={checkIntegrationsHealth}
                  isLoading={loading}
                >
                  Refresh Status
                </Button>
              </HStack>

              <Progress
                value={connectionProgress}
                colorScheme={connectionProgress === 100 ? "green" : "blue"}
                size="md"
                borderRadius="md"
              />

              <HStack justify="space-between">
                <Text fontSize="sm" color="gray.600">
                  Connection Progress
                </Text>
                <Text fontSize="sm" fontWeight="bold">
                  {Math.round(connectionProgress)}%
                </Text>
              </HStack>
            </VStack>
          </CardBody>
        </Card>

        {/* Categories Filter */}
        <HStack spacing={4} wrap="wrap">
          {categories.map((category) => (
            <Button
              key={category.id}
              variant={selectedCategory === category.id ? "solid" : "outline"}
              colorScheme={selectedCategory === category.id ? "blue" : "gray"}
              onClick={() => setSelectedCategory(category.id)}
              size="sm"
            >
              {category.name}
              <Badge ml={2} variant="solid" colorScheme="blue">
                {category.count}
              </Badge>
            </Button>
          ))}
        </HStack>

        <Divider />

        {/* Integrations Grid */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
          {filteredIntegrations.map((integration) => (
            <Card
              key={integration.id}
              cursor="pointer"
              onClick={() => handleIntegrationClick(integration)}
              bg={bgColor}
              border="1px"
              borderColor={borderColor}
              _hover={{
                shadow: "md",
                transform: "translateY(-2px)",
                transition: "all 0.2s",
              }}
            >
              <CardHeader>
                <HStack justify="space-between">
                  <HStack>
                    <Icon
                      as={integration.icon}
                      w={8}
                      h={8}
                      color={integration.color}
                    />
                    <VStack align="start" spacing={0}>
                      <Text fontWeight="bold" fontSize="lg">
                        {integration.name}
                      </Text>
                      <Badge
                        colorScheme={
                          integration.status === "complete"
                            ? "green"
                            : integration.status === "in-progress"
                              ? "yellow"
                              : "gray"
                        }
                        size="sm"
                      >
                        {integration.status}
                      </Badge>
                    </VStack>
                  </HStack>
                  {getStatusIcon(integration.health || "unknown")}
                </HStack>
              </CardHeader>

              <CardBody>
                <VStack spacing={4} align="stretch">
                  <Text color="gray.600" fontSize="sm">
                    {integration.description}
                  </Text>

                  <Divider />

                  <HStack justify="space-between">
                    <Text fontSize="xs" color="gray.500">
                      Category: {integration.category}
                    </Text>
                    {integration.connected && (
                      <HStack>
                        <CheckCircleIcon color="green.500" w={3} h={3} />
                        <Text fontSize="xs" color="green.500" fontWeight="bold">
                          Connected
                        </Text>
                      </HStack>
                    )}
                  </HStack>

                  <Button
                    variant="outline"
                    size="sm"
                    leftIcon={<ArrowForwardIcon />}
                    width="full"
                  >
                    {integration.connected ? "Manage" : "Connect"}
                  </Button>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>

        {/* Empty State */}
        {filteredIntegrations.length === 0 && (
          <Card>
            <CardBody>
              <VStack spacing={4}>
                <Icon as={WarningTwoIcon} w={12} h={12} color="gray.400" />
                <Text color="gray.600" textAlign="center">
                  No integrations found in this category
                </Text>
                <Button
                  variant="outline"
                  onClick={() => setSelectedCategory("all")}
                >
                  View All Integrations
                </Button>
              </VStack>
            </CardBody>
          </Card>
        )}
      </VStack>
    </Box>
  );
};

export default IntegrationsPage;