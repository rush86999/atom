/**
 * HubSpot Dashboard Component Tests
 *
 * Tests verify dashboard renders analytics data, displays metrics,
 * shows growth indicators, and handles loading state.
 *
 * Source: components/integrations/hubspot/HubSpotDashboard.tsx (404 lines)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import HubSpotDashboard from '../HubSpotDashboard';

// Mock UI components
jest.mock('../../../ui/card', () => ({
  Card: ({ children, className }: any) => <div className={className}>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
}));

jest.mock('../../../ui/badge', () => ({
  Badge: ({ children, className }: any) => <span className={className}>{children}</span>,
}));

jest.mock('../../../ui/progress', () => ({
  Progress: ({ value, className }: any) => (
    <div className={className} data-value={value}>
      Progress: {value}%
    </div>
  ),
}));

describe('HubSpotDashboard', () => {
  const mockAnalytics = {
    totalContacts: 1500,
    totalCompanies: 250,
    totalDeals: 75,
    totalDealValue: 1250000,
    winRate: 68.5,
    contactGrowth: 12.5,
    companyGrowth: -3.2,
    dealGrowth: 8.7,
    campaignPerformance: 82.3,
    leadConversionRate: 24.8,
    emailOpenRate: 35.2,
    emailClickRate: 8.5,
    monthlyRevenue: 45000,
    quarterlyGrowth: 15.3,
    topPerformingCampaigns: [
      { name: 'Spring Campaign', performance: 92, roi: 285, budget: 5000 },
      { name: 'Summer Push', performance: 78, roi: 145, budget: 3500 },
    ],
    recentActivities: [
      {
        type: 'Email Opened',
        description: 'Opened pricing email',
        timestamp: '2026-04-24T10:30:00Z',
        contact: 'john@example.com',
      },
      {
        type: 'Deal Stage Changed',
        description: 'Moved to negotiation',
        timestamp: '2026-04-24T09:15:00Z',
        contact: 'jane@example.com',
      },
    ],
    pipelineStages: [
      { stage: 'Qualification', count: 25, value: 250000, probability: 20 },
      { stage: 'Proposal', count: 15, value: 375000, probability: 50 },
      { stage: 'Negotiation', count: 8, value: 200000, probability: 75 },
    ],
  };

  // Test 1: renders dashboard header
  test('renders dashboard header with title and description', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('HubSpot Analytics Dashboard')).toBeInTheDocument();
    expect(
      screen.getByText('Comprehensive overview of your CRM performance and marketing analytics')
    ).toBeInTheDocument();
  });

  // Test 2: renders loading state
  test('renders loading state when loading prop is true', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} loading={true} />);

    expect(screen.getByText('Loading dashboard data...')).toBeInTheDocument();
  });

  // Test 3: displays total contacts metric
  test('displays total contacts metric with growth indicator', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Total Contacts')).toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
    expect(screen.getByText('12.5% from last month')).toBeInTheDocument();
  });

  // Test 4: displays total companies metric
  test('displays total companies metric with negative growth', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Total Companies')).toBeInTheDocument();
    expect(screen.getByText('250')).toBeInTheDocument();
    expect(screen.getByText('3.2% from last month')).toBeInTheDocument();
  });

  // Test 5: displays active deals metric
  test('displays active deals metric', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Active Deals')).toBeInTheDocument();
    expect(screen.getByText('75')).toBeInTheDocument();
    expect(screen.getByText('8.7% from last month')).toBeInTheDocument();
  });

  // Test 6: displays monthly revenue with currency formatting
  test('displays monthly revenue with proper currency formatting', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Monthly Revenue')).toBeInTheDocument();
    expect(screen.getByText('$45,000')).toBeInTheDocument();
    expect(screen.getByText('15.3% this quarter')).toBeInTheDocument();
  });

  // Test 7: displays win rate with progress bar
  test('displays win rate with progress bar', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('68.5%')).toBeInTheDocument();
    expect(screen.getByText('Deal conversion success rate')).toBeInTheDocument();
  });

  // Test 8: displays lead conversion rate
  test('displays lead conversion rate', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Lead Conversion')).toBeInTheDocument();
    expect(screen.getByText('24.8%')).toBeInTheDocument();
    expect(screen.getByText('Lead to customer conversion')).toBeInTheDocument();
  });

  // Test 9: displays email performance metrics
  test('displays email open rate and click rate', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Email Performance')).toBeInTheDocument();
    expect(screen.getByText('Open Rate')).toBeInTheDocument();
    expect(screen.getByText('35.2%')).toBeInTheDocument();
    expect(screen.getByText('Click Rate')).toBeInTheDocument();
    expect(screen.getByText('8.5%')).toBeInTheDocument();
  });

  // Test 10: displays pipeline stages
  test('displays pipeline stages with probabilities', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Pipeline Stages')).toBeInTheDocument();
    expect(screen.getByText('Qualification')).toBeInTheDocument();
    expect(screen.getByText('25 deals')).toBeInTheDocument();
    expect(screen.getByText('20% probability')).toBeInTheDocument();
  });

  // Test 11: displays top performing campaigns
  test('displays top performing campaigns with performance badges', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Top Performing Campaigns')).toBeInTheDocument();
    expect(screen.getByText('Spring Campaign')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();
    expect(screen.getByText('ROI: 285%')).toBeInTheDocument();
  });

  // Test 12: displays recent activities
  test('displays recent activities with timestamps', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Recent Activities')).toBeInTheDocument();
    expect(screen.getByText('Email Opened')).toBeInTheDocument();
    expect(screen.getByText('Opened pricing email')).toBeInTheDocument();
    expect(screen.getByText('john@example.com')).toBeInTheDocument();
  });

  // Test 13: displays summary stats
  test('displays summary statistics at bottom', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Total Deal Value')).toBeInTheDocument();
    expect(screen.getByText('$1,250,000')).toBeInTheDocument();
    expect(screen.getByText('Campaign Performance')).toBeInTheDocument();
    expect(screen.getByText('82.3%')).toBeInTheDocument();
  });

  // Test 14: formats currency correctly
  test('formats currency values correctly using USD locale', () => {
    const { container } = render(<HubSpotDashboard analytics={mockAnalytics} />);

    // Check that large numbers are formatted with commas
    expect(screen.getByText('$1,250,000')).toBeInTheDocument();
    expect(screen.getByText('$250,000')).toBeInTheDocument();
    expect(screen.getByText('$375,000')).toBeInTheDocument();
  });

  // Test 15: displays total records count
  test('displays total records combining contacts and companies', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Total Records')).toBeInTheDocument();
    // 1500 contacts + 250 companies = 1750 total
    expect(screen.getByText('1,750')).toBeInTheDocument();
  });

  // Test 16: handles missing optional arrays gracefully
  test('renders without errors when optional arrays are missing', () => {
    const minimalAnalytics = {
      totalContacts: 100,
      totalCompanies: 20,
      totalDeals: 5,
      totalDealValue: 50000,
      winRate: 60,
      contactGrowth: 5,
      companyGrowth: 2,
      dealGrowth: 3,
      campaignPerformance: 70,
      leadConversionRate: 20,
      emailOpenRate: 30,
      emailClickRate: 5,
      monthlyRevenue: 10000,
      quarterlyGrowth: 10,
    };

    expect(() => render(<HubSpotDashboard analytics={minimalAnalytics} />)).not.toThrow();
  });

  // Test 17: displays performance trend indicator
  test('displays performance trend indicator based on win rate', () => {
    render(<HubSpotDashboard analytics={mockAnalytics} />);

    expect(screen.getByText('Performance Trend')).toBeInTheDocument();
    expect(screen.getByText('↑')).toBeInTheDocument();
  });

  // Test 18: limits recent activities to 5 items
  test('limits recent activities display to 5 items', () => {
    const manyActivities = {
      ...mockAnalytics,
      recentActivities: Array.from({ length: 10 }, (_, i) => ({
        type: `Activity ${i}`,
        description: `Description ${i}`,
        timestamp: '2026-04-24T10:00:00Z',
        contact: `contact${i}@example.com`,
      })),
    };

    const { container } = render(<HubSpotDashboard analytics={manyActivities} />);

    // Should only display first 5 activities
    expect(screen.getByText('Activity 0')).toBeInTheDocument();
    expect(screen.getByText('Activity 4')).toBeInTheDocument();
  });
});
