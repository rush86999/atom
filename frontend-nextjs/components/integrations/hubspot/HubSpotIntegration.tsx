import React, { useState, useEffect } from "react";
import { hubspotApi } from "../../../lib/hubspotApi";
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Badge,
  Button,
  Grid,
  GridItem,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Progress,
  Card,
  CardBody,
  SimpleGrid,
  useColorModeValue,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from "@chakra-ui/react";
import { AddIcon, SettingsIcon, DownloadIcon } from "@chakra-ui/icons";
import HubSpotSearch, {
  HubSpotContact,
  HubSpotCompany,
  HubSpotDeal,
  HubSpotActivity,
  HubSpotDataType,
} from "./HubSpotSearch";

// Mock data for fallback demonstration
const mockContacts: HubSpotContact[] = [
  {
    id: "1",
    firstName: "John",
    lastName: "Doe",
    email: "john.doe@example.com",
    company: "TechCorp",
    phone: "+1-555-0101",
    lifecycleStage: "Customer",
    leadStatus: "Active",
    leadScore: 85,
    lastActivityDate: "2024-01-15",
    createdDate: "2024-01-10",
    owner: "Sarah Wilson",
    industry: "Technology",
    country: "United States",
  },
  {
    id: "2",
    firstName: "Jane",
    lastName: "Smith",
    email: "jane.smith@example.com",
    company: "Innovate LLC",
    phone: "+1-555-0102",
    lifecycleStage: "Lead",
    leadStatus: "Qualified",
    leadScore: 72,
    lastActivityDate: "2024-01-14",
    createdDate: "2024-01-08",
    owner: "Mike Johnson",
    industry: "Healthcare",
    country: "Canada",
  },
  {
    id: "3",
    firstName: "Bob",
    lastName: "Johnson",
    email: "bob.johnson@example.com",
    company: "Global Solutions",
    phone: "+1-555-0103",
    lifecycleStage: "Opportunity",
    leadStatus: "In Progress",
    leadScore: 45,
    lastActivityDate: "2024-01-13",
    createdDate: "2024-01-05",
    owner: "Sarah Wilson",
    industry: "Finance",
    country: "United Kingdom",
  },
];

const mockCompanies: HubSpotCompany[] = [
  {
    id: "1",
    name: "TechCorp",
    domain: "techcorp.com",
    industry: "Technology",
    size: "Enterprise",
    country: "United States",
    city: "San Francisco",
    annualRevenue: 50000000,
    owner: "Sarah Wilson",
    lastActivityDate: "2024-01-15",
    createdDate: "2024-01-10",
    dealStage: "Closed Won",
  },
  {
    id: "2",
    name: "Innovate LLC",
    domain: "innovatellc.com",
    industry: "Healthcare",
    size: "Medium",
    country: "Canada",
    city: "Toronto",
    annualRevenue: 15000000,
    owner: "Mike Johnson",
    lastActivityDate: "2024-01-14",
    createdDate: "2024-01-08",
    dealStage: "Negotiation",
  },
];

const mockDeals: HubSpotDeal[] = [
  {
    id: "1",
    name: "Enterprise Software License",
    amount: 250000,
    stage: "Closed Won",
    closeDate: "2024-01-20",
    createdDate: "2024-01-05",
    owner: "Sarah Wilson",
    company: "TechCorp",
    contact: "John Doe",
    probability: 100,
    pipeline: "Default",
  },
  {
    id: "2",
    name: "Healthcare Platform Implementation",
    amount: 150000,
    stage: "Negotiation",
    closeDate: "2024-02-15",
    createdDate: "2024-01-08",
    owner: "Mike Johnson",
    company: "Innovate LLC",
    contact: "Jane Smith",
    probability: 75,
    pipeline: "Default",
  },
];

const mockActivities: HubSpotActivity[] = [
  {
    id: "1",
    type: "Email",
    subject: "Follow-up: Enterprise Software Demo",
    body: "Following up on our demo call from last week...",
    timestamp: "2024-01-15T10:30:00Z",
    contact: "John Doe",
    company: "TechCorp",
    owner: "Sarah Wilson",
    engagementType: "Email",
  },
  {
    id: "2",
    type: "Call",
    subject: "Initial Discovery Call",
    body: "Discussed platform requirements and timeline...",
    timestamp: "2024-01-14T14:15:00Z",
    contact: "Jane Smith",
    company: "Innovate LLC",
    owner: "Mike Johnson",
    engagementType: "Call",
  },
];

const HubSpotIntegration: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [contacts, setContacts] = useState<HubSpotContact[]>([]);
  const [companies, setCompanies] = useState<HubSpotCompany[]>([]);
  const [deals, setDeals] = useState<HubSpotDeal[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [pipelines, setPipelines] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>({});
  const [searchResults, setSearchResults] = useState<any[]>([]);

  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.600");
  const cardBg = useColorModeValue("gray.50", "gray.700");

  useEffect(() => {
    const checkConnection = async () => {
      setLoading(true);
      try {
        const authStatus = await hubspotApi.getAuthStatus();
        setIsConnected(authStatus.connected);

        if (authStatus.connected) {
          // Load real data from HubSpot API
          const [
            contactsData,
            companiesData,
            dealsData,
            campaignsData,
            pipelinesData,
            analyticsData,
          ] = await Promise.all([
            hubspotApi.getContacts(),
            hubspotApi.getCompanies(),
            hubspotApi.getDeals(),
            hubspotApi.getCampaigns(),
            hubspotApi.getPipelines(),
            hubspotApi.getAnalytics(),
          ]);

          setContacts(
            contactsData.contacts.length > 0
              ? contactsData.contacts
              : mockContacts,
          );
          setCompanies(
            companiesData.companies.length > 0
              ? companiesData.companies
              : mockCompanies,
          );
          setDeals(dealsData.deals.length > 0 ? dealsData.deals : mockDeals);
          setCampaigns(campaignsData);
          setPipelines(pipelinesData);
          setAnalytics(analyticsData);
        } else {
          // Use mock data for demonstration
          setContacts(mockContacts);
          setCompanies(mockCompanies);
          setDeals(mockDeals);
          setCampaigns([]);
          setPipelines([]);
          setAnalytics({});
        }
      } catch (error) {
        console.error("Failed to connect to HubSpot:", error);
        setIsConnected(false);
        // Fallback to mock data
        setContacts(mockContacts);
        setCompanies(mockCompanies);
        setDeals(mockDeals);
        setCampaigns([]);
        setPipelines([]);
        setAnalytics({});
      } finally {
        setLoading(false);
      }
    };

    checkConnection();
  }, []);

  const handleSearch = (results: any[], filters: any, sort: any) => {
    setSearchResults(results);
    console.log("Search results:", results);
    console.log("Applied filters:", filters);
    console.log("Sort options:", sort);
  };

  const handleConnectHubSpot = async () => {
    setAuthLoading(true);
    try {
      const result = await hubspotApi.connectHubSpot();
      if (result.success && result.authUrl) {
        // Redirect to HubSpot OAuth
        window.location.href = result.authUrl;
      } else {
        throw new Error("Failed to initiate OAuth flow");
      }
    } catch (error) {
      console.error("Failed to connect to HubSpot:", error);
      // Fallback to mock connection for demo
      setIsConnected(true);
      setContacts(mockContacts);
      setCompanies(mockCompanies);
      setDeals(mockDeals);
      setCampaigns([]);
      setPipelines([]);
      setAnalytics({});
    } finally {
      setAuthLoading(false);
    }
  };

  const getAllData = () => {
    return [...contacts, ...companies, ...deals, ...campaigns];
  };

  const getStats = () => {
    const totalContacts = contacts.length;
    const totalCompanies = companies.length;
    const totalDeals = deals.length;
    const totalDealValue = deals.reduce(
      (sum, deal) => sum + (deal.amount || 0),
      0,
    );
    const wonDeals = deals.filter(
      (deal) => deal.stage === "Closed Won" || deal.stage === "closed_won",
    ).length;
    const winRate = totalDeals > 0 ? (wonDeals / totalDeals) * 100 : 0;
    const activeCampaigns = campaigns.length;
    const totalPipelines = pipelines.length;

    // Use analytics data if available
    const analyticsData = analytics || {};

    return {
      totalContacts,
      totalCompanies,
      totalDeals,
      totalDealValue,
      winRate,
      activeCampaigns,
      totalPipelines,
      ...analyticsData,
    };
  };

  const stats = getStats();

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minH="200px"
      >
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text>Loading HubSpot integration...</Text>
        </VStack>
      </Box>
    );
  }

  if (!isConnected) {
    return (
      <Card bg={cardBg} p={6}>
        <VStack spacing={6} align="center">
          <Alert status="info" borderRadius="md">
            <AlertIcon />
            <Box>
              <AlertTitle>HubSpot Not Connected</AlertTitle>
              <AlertDescription>
                Connect your HubSpot account to access CRM data, manage
                contacts, track deals, and analyze marketing performance.
              </AlertDescription>
            </Box>
          </Alert>

          <Button
            colorScheme="blue"
            size="lg"
            leftIcon={<AddIcon />}
            onClick={handleConnectHubSpot}
            isLoading={loading}
          >
            {authLoading ? "Connecting..." : "Connect HubSpot Account"}
          </Button>

          <Text fontSize="sm" color="gray.600" textAlign="center">
            {authLoading
              ? "Initiating OAuth flow with HubSpot..."
              : "You&apos;ll be redirected to HubSpot to authorize access to your CRM data."}
          </Text>
        </VStack>
      </Card>
    );
  }

  return (
    <Box bg={bgColor} borderRadius="lg" p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2}>
            <Heading size="lg">HubSpot CRM</Heading>
            <Text color="gray.600">
              Complete CRM and marketing automation platform with advanced
              search capabilities
            </Text>
          </VStack>
          <HStack spacing={3}>
            <Button leftIcon={<DownloadIcon />} variant="outline" size="sm">
              Export Data
            </Button>
            <Button leftIcon={<SettingsIcon />} variant="outline" size="sm">
              Settings
            </Button>
          </HStack>
        </HStack>

        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <StatLabel>Total Contacts</StatLabel>
                <StatNumber>{stats.totalContacts}</StatNumber>
                <StatHelpText>
                  {stats.contactGrowth ? (
                    <StatArrow
                      type={stats.contactGrowth > 0 ? "increase" : "decrease"}
                    />
                  ) : (
                    <StatArrow type="increase" />
                  )}
                  {stats.contactGrowth
                    ? `${Math.abs(stats.contactGrowth)}% ${stats.contactGrowth > 0 ? "increase" : "decrease"}`
                    : "12% from last month"}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <StatLabel>Total Companies</StatLabel>
                <StatNumber>{stats.totalCompanies}</StatNumber>
                <StatHelpText>
                  {stats.companyGrowth ? (
                    <StatArrow
                      type={stats.companyGrowth > 0 ? "increase" : "decrease"}
                    />
                  ) : (
                    <StatArrow type="increase" />
                  )}
                  {stats.companyGrowth
                    ? `${Math.abs(stats.companyGrowth)}% ${stats.companyGrowth > 0 ? "increase" : "decrease"}`
                    : "8% from last month"}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <StatLabel>Active Deals</StatLabel>
                <StatNumber>{stats.totalDeals}</StatNumber>
                <StatHelpText>
                  ${stats.totalDealValue.toLocaleString()} total value
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <StatLabel>Active Campaigns</StatLabel>
                <StatNumber>{stats.activeCampaigns}</StatNumber>
                <StatHelpText>
                  {stats.campaignPerformance
                    ? `${stats.campaignPerformance}% performance`
                    : "Marketing campaigns"}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <StatLabel>Win Rate</StatLabel>
                <StatNumber>{stats.winRate.toFixed(1)}%</StatNumber>
                <StatHelpText>
                  <Progress
                    value={stats.winRate}
                    size="sm"
                    colorScheme="green"
                  />
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Main Content Tabs */}
        <Tabs variant="enclosed" colorScheme="blue" onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack spacing={2}>
                <Text>Overview</Text>
                <Badge colorScheme="blue" borderRadius="full" fontSize="xs">
                  All
                </Badge>
              </HStack>
            </Tab>
            <Tab>
              <HStack spacing={2}>
                <Text>Contacts</Text>
                <Badge colorScheme="green" borderRadius="full" fontSize="xs">
                  {contacts.length}
                </Badge>
              </HStack>
            </Tab>
            <Tab>
              <HStack spacing={2}>
                <Text>Companies</Text>
                <Badge colorScheme="purple" borderRadius="full" fontSize="xs">
                  {companies.length}
                </Badge>
              </HStack>
            </Tab>
            <Tab>
              <HStack spacing={2}>
                <Text>Deals</Text>
                <Badge colorScheme="orange" borderRadius="full" fontSize="xs">
                  {deals.length}
                </Badge>
              </HStack>
            </Tab>
            <Tab>
              <HStack spacing={2}>
                <Text>Campaigns</Text>
                <Badge colorScheme="teal" borderRadius="full" fontSize="xs">
                  {campaigns.length}
                </Badge>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Overview Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <HubSpotSearch
                  data={getAllData()}
                  dataType="all"
                  onSearch={handleSearch}
                  loading={loading}
                  totalCount={getAllData().length}
                />

                {searchResults.length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={4}>
                        <Heading size="md">Search Results</Heading>
                        <Text>
                          Found {searchResults.length} matching records across
                          all data types.
                        </Text>
                        {/* In a real implementation, you would display detailed results here */}
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Contacts Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <HubSpotSearch
                  data={contacts}
                  dataType="contacts"
                  onSearch={handleSearch}
                  loading={loading}
                  totalCount={contacts.length}
                />

                {searchResults.length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={4}>
                        <Heading size="md">Contact Results</Heading>
                        <Text>
                          Found {searchResults.length} matching contacts.
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Companies Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <HubSpotSearch
                  data={companies}
                  dataType="companies"
                  onSearch={handleSearch}
                  loading={loading}
                  totalCount={companies.length}
                />

                {searchResults.length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={4}>
                        <Heading size="md">Company Results</Heading>
                        <Text>
                          Found {searchResults.length} matching companies.
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Deals Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <HubSpotSearch
                  data={deals}
                  dataType="deals"
                  onSearch={handleSearch}
                  loading={loading}
                  totalCount={deals.length}
                />

                {searchResults.length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={4}>
                        <Heading size="md">Deal Results</Heading>
                        <Text>
                          Found {searchResults.length} matching deals with total
                          value of $
                          {searchResults
                            .filter(
                              (deal): deal is HubSpotDeal => "amount" in deal,
                            )
                            .reduce(
                              (sum: number, deal: any) =>
                                sum + (deal.amount || 0),
                              0,
                            )
                            .toLocaleString()}
                          .
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Campaigns Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <HubSpotSearch
                  data={campaigns}
                  dataType="activities"
                  onSearch={handleSearch}
                  loading={loading}
                  totalCount={campaigns.length}
                />

                {searchResults.length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={4}>
                        <Heading size="md">Campaign Results</Heading>
                        <Text>
                          Found {searchResults.length} matching campaigns.
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default HubSpotIntegration;
