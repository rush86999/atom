/**
 * HubSpot Integration Component Tests
 *
 * Test suite for HubSpot integration card/setup component
 */

import React from 'react';

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import HubSpotIntegration from '../hubspot/HubSpotIntegration';

// Mock hubspotApi
jest.mock('../../../lib/hubspotApi', () => ({
  hubspotApi: {
    getAuthStatus: jest.fn(),
    getContacts: jest.fn(),
    getCompanies: jest.fn(),
    getDeals: jest.fn(),
    getCampaigns: jest.fn(),
    getPipelines: jest.fn(),
    getAnalytics: jest.fn(),
    getAIPredictions: jest.fn(),
    connectHubSpot: jest.fn(),
  }
}));

describe('HubSpotIntegration', () => {
  const defaultProps = {
    onConnect: jest.fn(),
    onDisconnect: jest.fn(),
  };

  beforeEach(() => {
    server.resetHandlers();
    jest.clearAllMocks();
  });

  it('renders setup card with HubSpot branding', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: false });

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot Not Connected')).toBeInTheDocument();
    });
  });

  it('shows OAuth connect button', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: false });

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Connect HubSpot Account')).toBeInTheDocument();
    });
  });

  it('shows connection status indicator', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({ contacts: [] });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot CRM')).toBeInTheDocument();
    });
  });

  it('renders configuration options when connected', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({ contacts: [] });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Export Data')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });
  });

  it('handles disconnect action', async () => {
    const user = userEvent.setup();
    const { hubspotApi } = require('../../../lib/hubspotApi');

    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({ contacts: [] });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot CRM')).toBeInTheDocument();
    });
  });

  it('displays stats overview cards', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({
      contacts: [
        { id: '1', firstName: 'John', lastName: 'Doe', email: 'john@example.com' }
      ]
    });
    hubspotApi.getCompanies.mockResolvedValue({
      companies: [
        { id: '1', name: 'Acme Corp' }
      ]
    });
    hubspotApi.getDeals.mockResolvedValue({
      deals: [
        { id: '1', name: 'Deal 1', amount: 10000, stage: 'proposal' }
      ]
    });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Total Contacts')).toBeInTheDocument();
      expect(screen.getByText('Total Companies')).toBeInTheDocument();
      expect(screen.getByText('Active Deals')).toBeInTheDocument();
      expect(screen.getByText('Win Rate')).toBeInTheDocument();
    });
  });

  it('shows tabs for different data types', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({ contacts: [] });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      expect(screen.getByText('Contacts')).toBeInTheDocument();
      expect(screen.getByText('Companies')).toBeInTheDocument();
      expect(screen.getByText('Deals')).toBeInTheDocument();
      expect(screen.getByText('Campaigns')).toBeInTheDocument();
      expect(screen.getByText('Predictive')).toBeInTheDocument();
      expect(screen.getByText('AI Insights')).toBeInTheDocument();
    });
  });

  it('renders search component in overview tab', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({ contacts: [] });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot Search')).toBeInTheDocument();
    });
  });

  it('handles loading state', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<HubSpotIntegration {...defaultProps} />);

    expect(screen.getByText(/loading hubspot integration/i)).toBeInTheDocument();
  });

  it('displays contact counts in badges', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({
      contacts: [
        { id: '1', firstName: 'John', lastName: 'Doe' },
        { id: '2', firstName: 'Jane', lastName: 'Smith' }
      ]
    });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument(); // Contact count badge
    });
  });
});
