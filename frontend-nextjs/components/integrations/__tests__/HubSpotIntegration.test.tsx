/**
 * HubSpotIntegration Component Tests
 *
 * Tests verify the real HubSpotIntegration component
 * (components/integrations/hubspot/HubSpotIntegration.tsx):
 * - Auth status check via hubspotApi.getAuthStatus()
 * - Disconnected setup card + OAuth connect flow
 * - Connected header, config buttons, stats cards, and tab triggers
 * - Loading state
 *
 * The component talks to the real lib/hubspotApi module (not fetch), so this
 * suite mocks it and drives the resolved values. The ui/spinner module is
 * mocked (its source references React without importing it, which throws
 * "React is not defined" whenever the loading state renders the real
 * Spinner). HubSpotSearch is mocked as a unit boundary so this suite tests
 * HubSpotIntegration's orchestration, not the child's search UI.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import HubSpotIntegration from '../hubspot/HubSpotIntegration';

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
  },
}));

// The ui/spinner module references React without importing it, which throws
// "React is not defined" in the test runtime whenever the loading state
// renders the real Spinner. Mock it to a plain div so the component's own
// "Loading HubSpot integration..." label can still be asserted.
jest.mock('@/components/ui/spinner', () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div data-testid="spinner" className={className} />
  ),
}));

// Unit boundary: HubSpotIntegration renders HubSpotSearch in its default
// Overview tab. The search component has its own suite; stub it here.
jest.mock('@/components/integrations/hubspot/HubSpotSearch', () => {
  return function MockHubSpotSearch(props: any) {
    return (
      <div>
        HubSpot Search
        <button
          type="button"
          data-testid="fire-search"
          onClick={() =>
            props.onSearch(
              [
                { id: 'd1', dealname: 'Big Deal', amount: 10000 },
                { id: 'd2', dealname: 'Bigger Deal', amount: 25000 },
                { id: 'c1', firstname: 'No', lastname: 'Amount' },
              ],
              { stage: 'closedwon' },
              { field: 'amount', direction: 'desc' }
            )
          }
        >
          Fire Search
        </button>
      </div>
    );
  };
});

const connectHubSpotAs = ({ connected }: { connected: boolean }) => {
  const { hubspotApi } = require('../../../lib/hubspotApi');
  hubspotApi.getAuthStatus.mockResolvedValue({ connected });
  if (connected) {
    hubspotApi.getContacts.mockResolvedValue({ contacts: [] });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);
  }
};

describe('HubSpotIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders the loading state while auth status is pending
  it('renders loading state while auth status is pending', () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockImplementation(() => new Promise(() => {})); // never resolves

    render(<HubSpotIntegration />);

    expect(
      screen.getByText(/loading hubspot integration/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  // Test 2: renders the setup card when disconnected
  it('renders setup card with HubSpot branding', async () => {
    connectHubSpotAs({ connected: false });

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot Not Connected')).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /connect hubspot account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button initiates the OAuth flow
  it('connect button initiates OAuth flow', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    connectHubSpotAs({ connected: false });
    hubspotApi.connectHubSpot.mockResolvedValue({
      success: true,
      authUrl: 'https://app.hubspot.com/oauth/authorize',
    });

    render(<HubSpotIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect hubspot account/i,
    });
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(hubspotApi.connectHubSpot).toHaveBeenCalled();
    });
  });

  // Test 4: shows the connected header when connected
  it('shows connection status indicator', async () => {
    connectHubSpotAs({ connected: true });

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /hubspot crm/i })
      ).toBeInTheDocument();
    });
  });

  // Test 5: renders configuration options when connected
  it('renders configuration options when connected', async () => {
    connectHubSpotAs({ connected: true });

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /export data/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /settings/i })
      ).toBeInTheDocument();
    });
  });

  // Test 6: displays stats overview cards
  it('displays stats overview cards', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({
      contacts: [{ id: '1', firstName: 'John', lastName: 'Doe', email: 'john@example.com' }],
    });
    hubspotApi.getCompanies.mockResolvedValue({
      companies: [{ id: '1', name: 'Acme Corp' }],
    });
    hubspotApi.getDeals.mockResolvedValue({
      deals: [{ id: '1', name: 'Deal 1', amount: 10000, stage: 'proposal' }],
    });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Total Contacts')).toBeInTheDocument();
      expect(screen.getByText('Total Companies')).toBeInTheDocument();
      expect(screen.getByText('Active Deals')).toBeInTheDocument();
      expect(screen.getByText('Win Rate')).toBeInTheDocument();
      expect(screen.getByText('$10,000 total value')).toBeInTheDocument();
    });
  });

  // Test 7: shows tabs for the different data types
  it('shows tabs for different data types', async () => {
    connectHubSpotAs({ connected: true });

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^overview/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^analytics/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^contacts/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^companies/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^deals/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^campaigns/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^predictive/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^ai insights/i })).toBeInTheDocument();
    });
  });

  // Test 8: renders the search component in the default overview tab
  it('renders search component in overview tab', async () => {
    connectHubSpotAs({ connected: true });

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot Search')).toBeInTheDocument();
    });
  });

  // Test 9: displays contact counts in the tab badge
  it('displays contact counts in badges', async () => {
    const { hubspotApi } = require('../../../lib/hubspotApi');
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: true });
    hubspotApi.getContacts.mockResolvedValue({
      contacts: [
        { id: '1', firstName: 'John', lastName: 'Doe' },
        { id: '2', firstName: 'Jane', lastName: 'Smith' },
      ],
    });
    hubspotApi.getCompanies.mockResolvedValue({ companies: [] });
    hubspotApi.getDeals.mockResolvedValue({ deals: [] });
    hubspotApi.getCampaigns.mockResolvedValue([]);
    hubspotApi.getPipelines.mockResolvedValue([]);
    hubspotApi.getAnalytics.mockResolvedValue({});
    hubspotApi.getAIPredictions.mockResolvedValue(null);

    render(<HubSpotIntegration />);

    await waitFor(() => {
      const contactsTab = screen.getByRole('button', { name: /^contacts/i });
      // The Contacts tab trigger renders its count badge inline.
      expect(contactsTab).toHaveTextContent('2');
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: search-result panels, auth failure paths
// ---------------------------------------------------------------------------
describe('HubSpotIntegration (extended coverage)', () => {
  let errorSpy: jest.SpyInstance;
  let logSpy: jest.SpyInstance;

  const { hubspotApi } = require('../../../lib/hubspotApi');

  beforeEach(() => {
    jest.clearAllMocks();
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    connectHubSpotAs({ connected: true });
  });

  it('renders search result panels across tabs after a search', async () => {
    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(screen.getByText('HubSpot Search')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('fire-search'));

    // Overview tab summary
    await waitFor(() => {
      expect(screen.getByText(/matching records/i)).toBeInTheDocument();
    });

    // Contacts tab
    fireEvent.click(screen.getByRole('button', { name: /contacts/i }));
    expect(await screen.findByText(/matching contacts/i)).toBeInTheDocument();

    // Companies tab
    fireEvent.click(screen.getByRole('button', { name: /companies/i }));
    expect(await screen.findByText(/matching companies/i)).toBeInTheDocument();

    // Deals tab — total value sums only records with an amount
    fireEvent.click(screen.getByRole('button', { name: /deals/i }));
    expect(await screen.findByText('Deal Results')).toBeInTheDocument();
    expect(screen.getByText(/35,000/)).toBeInTheDocument();

    expect(logSpy).toHaveBeenCalledWith('Applied filters:', { stage: 'closedwon' });
    expect(logSpy).toHaveBeenCalledWith('Sort options:', { field: 'amount', direction: 'desc' });
  });

  it('treats an auth-status rejection as disconnected', async () => {
    hubspotApi.getAuthStatus.mockRejectedValue(new Error('auth down'));

    render(<HubSpotIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to connect to HubSpot:',
        expect.anything()
      );
      expect(screen.getByText('HubSpot Not Connected')).toBeInTheDocument();
    });
  });

  it('resets state when the OAuth initiation fails', async () => {
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: false });
    hubspotApi.connectHubSpot.mockResolvedValue({ success: false });

    render(<HubSpotIntegration />);

    const connect = await screen.findByRole('button', {
      name: /connect hubspot account/i,
    });
    await waitFor(() => {
      expect(() => fireEvent.click(connect)).not.toThrow();
    });
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to connect to HubSpot:',
        expect.anything()
      );
    });
    expect(screen.getByText('HubSpot Not Connected')).toBeInTheDocument();
  });

  it('resets state when the OAuth initiation rejects', async () => {
    hubspotApi.getAuthStatus.mockResolvedValue({ connected: false });
    hubspotApi.connectHubSpot.mockRejectedValue(new Error('oauth down'));

    render(<HubSpotIntegration />);

    const connect = await screen.findByRole('button', {
      name: /connect hubspot account/i,
    });
    expect(() => fireEvent.click(connect)).not.toThrow();
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to connect to HubSpot:',
        expect.anything()
      );
    });
  });
});
