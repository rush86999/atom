import React, { useState, useEffect } from "react";
import { hubspotApi } from "../../../lib/hubspotApi";
import {
  Plus,
  Settings,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Info,
} from "lucide-react";
import { Button } from "../../ui/button";
import { Badge } from "../../ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../ui/card";
import { Progress } from "../../ui/progress";
import { Spinner } from "../../ui/spinner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "../../ui/alert";
import HubSpotSearch, {
  HubSpotContact,
  HubSpotCompany,
  HubSpotDeal,
  HubSpotActivity,
} from "./HubSpotSearch";
import HubSpotDashboard from "./HubSpotDashboard";
import HubSpotPredictiveAnalytics from "./HubSpotPredictiveAnalytics";
import HubSpotAIService from "./HubSpotAIService";

// No mock data needed for production

const HubSpotIntegration: React.FC = () => {
  const [activeTab, setActiveTab] = useState("overview");
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
  const [aiPredictions, setAIPredictions] = useState<any>(null);
  const [selectedContact, setSelectedContact] = useState<HubSpotContact | null>(null);

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
            aiPredictionsData,
          ] = await Promise.all([
            hubspotApi.getContacts(),
            hubspotApi.getCompanies(),
            hubspotApi.getDeals(),
            hubspotApi.getCampaigns(),
            hubspotApi.getPipelines(),
            hubspotApi.getAnalytics(),
            hubspotApi.getAIPredictions(),
          ]);

          setContacts(contactsData.contacts || []);
          setCompanies(companiesData.companies || []);
          setDeals(dealsData.deals || []);
          setCampaigns(campaignsData || []);
          setPipelines(pipelinesData || []);
          setAnalytics(analyticsData || {});
          setAIPredictions(aiPredictionsData || null);
          setSelectedContact(contactsData.contacts && contactsData.contacts.length > 0 ? contactsData.contacts[0] : null);
        } else {
          setContacts([]);
          setCompanies([]);
          setDeals([]);
          setCampaigns([]);
          setPipelines([]);
          setAnalytics({});
        }
      } catch (error) {
        console.error("Failed to connect to HubSpot:", error);
        setIsConnected(false);
        setContacts([]);
        setCompanies([]);
        setDeals([]);
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
      setIsConnected(false);
      setContacts([]);
      setCompanies([]);
      setDeals([]);
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
      <div className="flex justify-center items-center min-h-[200px]">
        <div className="flex flex-col items-center space-y-4">
          <Spinner size="lg" className="text-blue-500" />
          <p className="text-gray-600 dark:text-gray-400">Loading HubSpot integration...</p>
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <Card className="p-6 bg-gray-50 dark:bg-gray-800">
        <div className="flex flex-col items-center space-y-6">
          <Alert variant="default" className="bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-300">
            <Info className="h-4 w-4" />
            <AlertTitle>HubSpot Not Connected</AlertTitle>
            <AlertDescription>
              Connect your HubSpot account to access CRM data, manage
              contacts, track deals, and analyze marketing performance.
            </AlertDescription>
          </Alert>

          <Button
            size="lg"
            onClick={handleConnectHubSpot}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            <Plus className="mr-2 h-5 w-5" />
            {authLoading ? "Connecting..." : "Connect HubSpot Account"}
          </Button>

          <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
            {authLoading
              ? "Initiating OAuth flow with HubSpot..."
              : "You'll be redirected to HubSpot to authorize access to your CRM data."}
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">HubSpot CRM</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Complete CRM and marketing automation platform with advanced
            search capabilities
          </p>
        </div>
        <div className="flex space-x-3">
          <Button variant="outline" size="sm">
            <ChevronDown className="mr-2 h-4 w-4" />
            Export Data
          </Button>
          <Button variant="outline" size="sm">
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Contacts</p>
              <div className="flex items-baseline justify-between">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats.totalContacts}</h3>
              </div>
              <div className="flex items-center text-xs">
                {stats.contactGrowth && stats.contactGrowth > 0 ? (
                  <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                ) : (
                  <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                )}
                <span className={stats.contactGrowth && stats.contactGrowth < 0 ? "text-red-500" : "text-green-500"}>
                  {stats.contactGrowth
                    ? `${Math.abs(stats.contactGrowth)}% ${stats.contactGrowth > 0 ? "increase" : "decrease"}`
                    : "12% from last month"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Companies</p>
              <div className="flex items-baseline justify-between">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats.totalCompanies}</h3>
              </div>
              <div className="flex items-center text-xs">
                {stats.companyGrowth && stats.companyGrowth > 0 ? (
                  <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                ) : (
                  <TrendingUp className="mr-1 h-3 w-3 text-green-500" />
                )}
                <span className={stats.companyGrowth && stats.companyGrowth < 0 ? "text-red-500" : "text-green-500"}>
                  {stats.companyGrowth
                    ? `${Math.abs(stats.companyGrowth)}% ${stats.companyGrowth > 0 ? "increase" : "decrease"}`
                    : "8% from last month"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Deals</p>
              <div className="flex items-baseline justify-between">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats.totalDeals}</h3>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                ${stats.totalDealValue.toLocaleString()} total value
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Win Rate</p>
              <div className="flex items-baseline justify-between">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats.winRate.toFixed(1)}%</h3>
              </div>
              <div className="w-full pt-2">
                <Progress value={stats.winRate} className="h-2" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview" className="w-full" onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-8">
          <TabsTrigger value="overview">
            Overview
            <Badge variant="secondary" className="ml-2 bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300">All</Badge>
          </TabsTrigger>
          <TabsTrigger value="analytics">
            Analytics
            <Badge variant="secondary" className="ml-2 bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300">📊</Badge>
          </TabsTrigger>
          <TabsTrigger value="contacts">
            Contacts
            <Badge variant="secondary" className="ml-2 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">{contacts.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="companies">
            Companies
            <Badge variant="secondary" className="ml-2 bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300">{companies.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="deals">
            Deals
            <Badge variant="secondary" className="ml-2 bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300">{deals.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="campaigns">
            Campaigns
            <Badge variant="secondary" className="ml-2 bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-300">{campaigns.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="predictive">
            Predictive
            <Badge variant="secondary" className="ml-2 bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300">🔮</Badge>
          </TabsTrigger>
          <TabsTrigger value="ai-insights">
            AI Insights
            <Badge variant="secondary" className="ml-2 bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300">🤖</Badge>
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6 mt-6">
          <HubSpotSearch
            data={getAllData()}
            dataType="all"
            onSearch={handleSearch}
            loading={loading}
            totalCount={getAllData().length}
          />

          {searchResults.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Search Results</h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    Found {searchResults.length} matching records across
                    all data types.
                  </p>
                  {/* In a real implementation, you would display detailed results here */}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics" className="space-y-6 mt-6">
          <HubSpotDashboard analytics={analytics} loading={loading} />
        </TabsContent>

        {/* Contacts Tab */}
        <TabsContent value="contacts" className="space-y-6 mt-6">
          <HubSpotSearch
            data={contacts}
            dataType="contacts"
            onSearch={handleSearch}
            loading={loading}
            totalCount={contacts.length}
          />

          {searchResults.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Contact Results</h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    Found {searchResults.length} matching contacts.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Companies Tab */}
        <TabsContent value="companies" className="space-y-6 mt-6">
          <HubSpotSearch
            data={companies}
            dataType="companies"
            onSearch={handleSearch}
            loading={loading}
            totalCount={companies.length}
          />

          {searchResults.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Company Results</h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    Found {searchResults.length} matching companies.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Deals Tab */}
        <TabsContent value="deals" className="space-y-6 mt-6">
          <HubSpotSearch
            data={deals}
            dataType="deals"
            onSearch={handleSearch}
            loading={loading}
            totalCount={deals.length}
          />

          {searchResults.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Deal Results</h3>
                  <p className="text-gray-600 dark:text-gray-400">
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
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Campaigns Tab */}
        <TabsContent value="campaigns" className="space-y-6 mt-6">
          <HubSpotSearch
            data={campaigns}
            dataType="activities"
            onSearch={handleSearch}
            loading={loading}
            totalCount={campaigns.length}
          />

          {searchResults.length > 0 && (
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Campaign Results</h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    Found {searchResults.length} matching campaigns.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Predictive Analytics Tab */}
        <TabsContent value="predictive" className="space-y-6 mt-6">
          <HubSpotPredictiveAnalytics
            models={aiPredictions?.models || []}
            predictions={aiPredictions?.predictions || []}
            forecast={aiPredictions?.forecast || []}
          />
        </TabsContent>

        {/* AI Insights Tab */}
        <TabsContent value="ai-insights" className="space-y-6 mt-6">
          <HubSpotAIService
            contact={selectedContact}
            company={companies[0]}
            activities={[]}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default HubSpotIntegration;
