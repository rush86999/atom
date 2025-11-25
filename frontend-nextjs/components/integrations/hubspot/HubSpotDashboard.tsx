import React from 'react';
import {
  TrendingUp,
  Users,
  DollarSign,
  Target,
  Mail,
  Activity,
  ArrowUp,
  ArrowDown
} from 'lucide-react';
import { Card, CardContent } from '../../ui/card';
import { Badge } from '../../ui/badge';
import { Progress } from '../../ui/progress';

export interface HubSpotDashboardProps {
  analytics: {
    totalContacts: number;
    totalCompanies: number;
    totalDeals: number;
    totalDealValue: number;
    winRate: number;
    contactGrowth: number;
    companyGrowth: number;
    dealGrowth: number;
    campaignPerformance: number;
    leadConversionRate: number;
    emailOpenRate: number;
    emailClickRate: number;
    monthlyRevenue: number;
    quarterlyGrowth: number;
    topPerformingCampaigns?: Array<{
      name: string;
      performance: number;
      roi: number;
      budget: number;
    }>;
    recentActivities?: Array<{
      type: string;
      description: string;
      timestamp: string;
      contact: string;
    }>;
    pipelineStages?: Array<{
      stage: string;
      count: number;
      value: number;
      probability: number;
    }>;
  };
  loading?: boolean;
}

const HubSpotDashboard: React.FC<HubSpotDashboardProps> = ({ analytics, loading = false }) => {
  const getGrowthColor = (value: number) => {
    if (value > 0) return 'text-green-500';
    if (value < 0) return 'text-red-500';
    return 'text-gray-500';
  };

  const getPerformanceColorScheme = (value: number) => {
    if (value >= 80) return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
    if (value >= 60) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300';
    if (value >= 40) return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300';
    return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(value);
  };

  if (loading) {
    return (
      <div className="p-6 bg-white dark:bg-gray-900 rounded-lg">
        <div className="flex flex-col space-y-4">
          <p className="text-gray-600 dark:text-gray-400">Loading dashboard data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 bg-white dark:bg-gray-900 rounded-lg">
      <div className="flex flex-col space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">HubSpot Analytics Dashboard</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Comprehensive overview of your CRM performance and marketing analytics
          </p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Contacts Metric */}
          <Card className="bg-gray-50 dark:bg-gray-800">
            <CardContent className="pt-6">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Contacts</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{analytics.totalContacts.toLocaleString()}</p>
                  <div className="flex items-center text-xs">
                    {analytics.contactGrowth > 0 ? (
                      <ArrowUp className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.contactGrowth)}`} />
                    ) : (
                      <ArrowDown className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.contactGrowth)}`} />
                    )}
                    <span className={getGrowthColor(analytics.contactGrowth)}>
                      {Math.abs(analytics.contactGrowth)}% from last month
                    </span>
                  </div>
                </div>
                <Users className="h-6 w-6 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          {/* Companies Metric */}
          <Card className="bg-gray-50 dark:bg-gray-800">
            <CardContent className="pt-6">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Companies</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{analytics.totalCompanies.toLocaleString()}</p>
                  <div className="flex items-center text-xs">
                    {analytics.companyGrowth > 0 ? (
                      <ArrowUp className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.companyGrowth)}`} />
                    ) : (
                      <ArrowDown className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.companyGrowth)}`} />
                    )}
                    <span className={getGrowthColor(analytics.companyGrowth)}>
                      {Math.abs(analytics.companyGrowth)}% from last month
                    </span>
                  </div>
                </div>
                <Target className="h-6 w-6 text-purple-500" />
              </div>
            </CardContent>
          </Card>

          {/* Deals Metric */}
          <Card className="bg-gray-50 dark:bg-gray-800">
            <CardContent className="pt-6">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Deals</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{analytics.totalDeals.toLocaleString()}</p>
                  <div className="flex items-center text-xs">
                    {analytics.dealGrowth > 0 ? (
                      <ArrowUp className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.dealGrowth)}`} />
                    ) : (
                      <ArrowDown className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.dealGrowth)}`} />
                    )}
                    <span className={getGrowthColor(analytics.dealGrowth)}>
                      {Math.abs(analytics.dealGrowth)}% from last month
                    </span>
                  </div>
                </div>
                <DollarSign className="h-6 w-6 text-green-500" />
              </div>
            </CardContent>
          </Card>

          {/* Revenue Metric */}
          <Card className="bg-gray-50 dark:bg-gray-800">
            <CardContent className="pt-6">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Monthly Revenue</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatCurrency(analytics.monthlyRevenue)}</p>
                  <div className="flex items-center text-xs">
                    {analytics.quarterlyGrowth > 0 ? (
                      <ArrowUp className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.quarterlyGrowth)}`} />
                    ) : (
                      <ArrowDown className={`mr-1 h-3 w-3 ${getGrowthColor(analytics.quarterlyGrowth)}`} />
                    )}
                    <span className={getGrowthColor(analytics.quarterlyGrowth)}>
                      {Math.abs(analytics.quarterlyGrowth)}% this quarter
                    </span>
                  </div>
                </div>
                <TrendingUp className="h-6 w-6 text-orange-500" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main Performance */}
          <div className="lg:col-span-2 space-y-6">
            {/* Win Rate & Conversion */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <Target className="h-4 w-4 text-green-500" />
                      <p className="font-semibold text-gray-900 dark:text-gray-100">Win Rate</p>
                    </div>
                    <Progress value={analytics.winRate} className="h-3" />
                    <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                      {analytics.winRate.toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Deal conversion success rate
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <Users className="h-4 w-4 text-blue-500" />
                      <p className="font-semibold text-gray-900 dark:text-gray-100">Lead Conversion</p>
                    </div>
                    <Progress value={analytics.leadConversionRate} className="h-3" />
                    <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                      {analytics.leadConversionRate.toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Lead to customer conversion
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Email Performance */}
            <Card className="bg-gray-50 dark:bg-gray-800">
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <div className="flex items-center space-x-2">
                    <Mail className="h-4 w-4 text-purple-500" />
                    <p className="font-semibold text-gray-900 dark:text-gray-100">Email Performance</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <p className="text-sm text-gray-600 dark:text-gray-400">Open Rate</p>
                      <Progress value={analytics.emailOpenRate} className="h-2" />
                      <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {analytics.emailOpenRate.toFixed(1)}%
                      </p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-sm text-gray-600 dark:text-gray-400">Click Rate</p>
                      <Progress value={analytics.emailClickRate} className="h-2" />
                      <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {analytics.emailClickRate.toFixed(1)}%
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Pipeline Stages */}
            {analytics.pipelineStages && analytics.pipelineStages.length > 0 && (
              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-4">
                    <div className="flex items-center space-x-2">
                      <Activity className="h-4 w-4 text-orange-500" />
                      <p className="font-semibold text-gray-900 dark:text-gray-100">Pipeline Stages</p>
                    </div>
                    <div className="space-y-3">
                      {analytics.pipelineStages.map((stage, index) => (
                        <div key={index} className="space-y-1">
                          <div className="flex justify-between items-center mb-1">
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{stage.stage}</p>
                            <Badge variant="secondary" className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                              {stage.count} deals
                            </Badge>
                          </div>
                          <Progress value={stage.probability} className="h-2" />
                          <div className="flex justify-between items-center mt-1">
                            <p className="text-xs text-gray-600 dark:text-gray-400">{stage.probability}% probability</p>
                            <p className="text-xs text-gray-600 dark:text-gray-400">{formatCurrency(stage.value)}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column - Campaigns & Activities */}
          <div className="space-y-6">
            {/* Top Performing Campaigns */}
            {analytics.topPerformingCampaigns && analytics.topPerformingCampaigns.length > 0 && (
              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-4">
                    <p className="font-semibold text-gray-900 dark:text-gray-100">Top Performing Campaigns</p>
                    <div className="space-y-3">
                      {analytics.topPerformingCampaigns.map((campaign, index) => (
                        <div
                          key={index}
                          className="p-3 border border-gray-200 dark:border-gray-700 rounded-md"
                        >
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{campaign.name}</p>
                            <div className="flex justify-between items-center">
                              <Badge className={getPerformanceColorScheme(campaign.performance)}>
                                {campaign.performance}%
                              </Badge>
                              <p className="text-sm text-gray-600 dark:text-gray-400">
                                ROI: {campaign.roi}%
                              </p>
                            </div>
                            <Progress value={campaign.performance} className="h-1" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recent Activities */}
            {analytics.recentActivities && analytics.recentActivities.length > 0 && (
              <Card className="bg-gray-50 dark:bg-gray-800">
                <CardContent className="pt-6">
                  <div className="space-y-4">
                    <p className="font-semibold text-gray-900 dark:text-gray-100">Recent Activities</p>
                    <div className="space-y-2">
                      {analytics.recentActivities.slice(0, 5).map((activity, index) => (
                        <div
                          key={index}
                          className="flex justify-between items-start p-2 border border-gray-200 dark:border-gray-700 rounded-md"
                        >
                          <div className="space-y-0">
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{activity.type}</p>
                            <p className="text-xs text-gray-600 dark:text-gray-400">{activity.description}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-500">{activity.contact}</p>
                          </div>
                          <p className="text-xs text-gray-500 dark:text-gray-500">
                            {new Date(activity.timestamp).toLocaleDateString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Summary Stats */}
        <Card className="bg-gray-50 dark:bg-gray-800">
          <CardContent className="pt-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex flex-col items-center space-y-1">
                <p className="text-2xl font-bold text-green-500">
                  {formatCurrency(analytics.totalDealValue)}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                  Total Deal Value
                </p>
              </div>
              <div className="flex flex-col items-center space-y-1">
                <p className="text-2xl font-bold text-blue-500">
                  {analytics.campaignPerformance.toFixed(1)}%
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                  Campaign Performance
                </p>
              </div>
              <div className="flex flex-col items-center space-y-1">
                <p className="text-2xl font-bold text-purple-500">
                  {(analytics.totalContacts + analytics.totalCompanies).toLocaleString()}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                  Total Records
                </p>
              </div>
              <div className="flex flex-col items-center space-y-1">
                <p className="text-2xl font-bold text-orange-500">
                  {analytics.winRate > 0 ? '↑' : '↓'}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                  Performance Trend
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default HubSpotDashboard;
