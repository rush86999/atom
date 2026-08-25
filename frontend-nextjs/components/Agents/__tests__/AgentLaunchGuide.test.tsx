/**
 * AgentLaunchGuide tests
 *
 * Locks the guided first-employee launch journey contract:
 * - Role picker drives app MATCHING from the live ingestion registry
 *   (wildcards: sales prefers zoho* -> falls through to salesforce/hubspot)
 * - Connect CTAs per matched app; "Set up" deep-link for apps without a
 *   direct OAuth flow
 * - Auto-hides once every matched app is connected AND a role agent exists
 * - Unconfigured server-side OAuth surfaces env-var guidance instead of a
 *   doomed consent redirect
 * - Hire posts POST /api/agents/custom with the role category and refreshes
 *   the parent list
 * - Sync posts /api/data-ingestion/sync/{app}?agent_id= scoped to the
 *   employee and surfaces fetched/ingested counts
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';

const mockApiClient = {
  get: jest.fn(),
  post: jest.fn(),
};

jest.mock('../../../lib/api', () => ({
  __esModule: true,
  apiClient: mockApiClient,
}));

const mockApi = {
  listTrainingProposals: jest.fn(),
};

jest.mock('../../../lib/maturity-api', () => ({
  __esModule: true,
  listTrainingProposals: mockApi.listTrainingProposals,
}));

import { AgentLaunchGuide } from '../AgentLaunchGuide';

const connectedBoth = {
  data: {
    integrations: [
      { provider: 'zoho', status: 'active' },
      { provider: 'microsoft', status: 'active' },
      { provider: 'google', status: 'active' },
    ],
  },
};

const configuredBoth = { data: { zoho: true, microsoft: true } };
const nothingConnected = {
  data: { integrations: [] as Array<{ provider: string; status: string }> },
};

const fullRegistry = {
  // Axios response shape: response.data is the BaseAPIRouter envelope
  // { success, data }, so the id list lives at .data.data.
  data: {
    data: [
      { id: 'zoho' },
      { id: 'gmail' },
      { id: 'slack' },
      { id: 'shopify' },
      { id: 'zendesk' },
    ],
  },
};

beforeEach(() => {
  jest.resetAllMocks();
  localStorage.clear();
  // Default world: OAuth configured server-side, nothing connected yet,
  // standard ingestion registry available.
  mockApiClient.get.mockImplementation((url: string) => {
    if (url.includes('/oauth/tokens')) return Promise.resolve(nothingConnected);
    if (url.includes('/config-status')) return Promise.resolve(configuredBoth);
    if (url.includes('/available-integrations')) return Promise.resolve(fullRegistry);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  mockApi.listTrainingProposals.mockResolvedValue([]);
});

describe('AgentLaunchGuide', () => {
  test('renders role picker and matched-app steps when nothing is set up', async () => {
    render(<AgentLaunchGuide agents={[]} />);

    await screen.findByTestId('agent-launch-guide');
    expect(screen.getByTestId('launch-role-picker')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-zoho')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-outlook')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-agent')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-ingest')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-train')).toBeInTheDocument();
    expect(screen.getByTestId('connect-zoho-cta')).toBeInTheDocument();
    expect(screen.getByTestId('connect-outlook-cta')).toBeInTheDocument();
    expect(screen.getByTestId('create-agent-cta')).toBeInTheDocument();
    // Ingestion actions stay visible but gated until the employee exists.
    expect(screen.getByTestId('sync-zoho-cta')).toBeDisabled();
  });

  test('app matching swaps in the next CRM preference when zoho is absent', async () => {
    const noZohoRegistry = {
      data: {
        data: [{ id: 'hubspot' }, { id: 'gmail' }, { id: 'slack' }],
      },
    };
    mockApiClient.get.mockImplementation((url: string) => {
      if (url.includes('/oauth/tokens')) return Promise.resolve(nothingConnected);
      if (url.includes('/config-status')) return Promise.resolve(configuredBoth);
      if (url.includes('/available-integrations'))
        return Promise.resolve(noZohoRegistry);
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });

    render(<AgentLaunchGuide agents={[]} />);

    await screen.findByTestId('agent-launch-guide');
    // Sales prefs walk zoho* -> (miss) -> hubspot (hit).
    await waitFor(() => {
      expect(screen.getByTestId('launch-step-hubspot')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('launch-step-zoho')).not.toBeInTheDocument();
    // HubSpot has sync ingestion but no direct OAuth flow -> setup deep-link.
    expect(screen.getByTestId('setup-hubspot-cta')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-hubspot-cta')).not.toBeInTheDocument();
  });

  test('switching role re-matches apps (finance -> zoho + shopify + outlook)', async () => {
    const user = userEvent.setup();
    render(<AgentLaunchGuide agents={[]} />);

    await screen.findByTestId('agent-launch-guide');
    await user.click(screen.getByTestId('launch-role-finance'));

    await waitFor(() => {
      expect(screen.getByTestId('launch-step-shopify')).toBeInTheDocument();
    });
    expect(screen.getByTestId('launch-step-zoho')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-outlook')).toBeInTheDocument();
    expect(screen.queryByTestId('launch-step-gmail')).not.toBeInTheDocument();
  });

  test('auto-hides when every matched app is connected and a Sales agent exists', async () => {
    mockApiClient.get.mockImplementation((url: string) => {
      if (url.includes('/oauth/tokens')) return Promise.resolve(connectedBoth);
      if (url.includes('/config-status')) return Promise.resolve(configuredBoth);
      if (url.includes('/available-integrations')) return Promise.resolve(fullRegistry);
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });

    render(
      <AgentLaunchGuide
        agents={[{ id: 'a1', name: 'Closer', category: 'Sales' }]}
      />
    );

    await waitFor(() => {
      expect(screen.queryByTestId('agent-launch-guide')).not.toBeInTheDocument();
    });
  });

  test('shows env-var guidance instead of consent redirect when provider is unconfigured server-side', async () => {
    mockApiClient.get.mockImplementation((url: string) => {
      if (url.includes('/oauth/tokens')) return Promise.resolve(nothingConnected);
      if (url.includes('/config-status'))
        return Promise.resolve({ data: { zoho: false, microsoft: false } });
      if (url.includes('/available-integrations')) return Promise.resolve(fullRegistry);
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });

    render(<AgentLaunchGuide agents={[]} />);

    await waitFor(() => {
      expect(screen.getByText(/ZOHO_CLIENT_ID/)).toBeInTheDocument();
    });
    expect(screen.getByText(/MICROSOFT_CLIENT_ID/)).toBeInTheDocument();
    expect(screen.queryByTestId('connect-zoho-cta')).not.toBeInTheDocument();
    expect(screen.queryByTestId('connect-outlook-cta')).not.toBeInTheDocument();
  });

  test('hire flow posts the role category and notifies parent', async () => {
    const onAgentsChanged = jest.fn();
    mockApiClient.post.mockResolvedValue({
      data: { success: true, data: { agent_id: 'new-1' } },
    });

    const user = userEvent.setup();
    render(<AgentLaunchGuide agents={[]} onAgentsChanged={onAgentsChanged} />);

    await screen.findByTestId('create-agent-cta');
    await user.click(screen.getByTestId('create-agent-cta'));

    const nameInput = await screen.findByTestId('launch-agent-name-input');
    expect(nameInput).toHaveValue('Sales Development Rep');

    await user.click(screen.getByTestId('launch-agent-submit'));

    await waitFor(() => {
      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/api/agents/custom',
        expect.objectContaining({ category: 'Sales', name: 'Sales Development Rep' })
      );
      expect(onAgentsChanged).toHaveBeenCalled();
    });
  });

  test('sync is scoped to the role employee and reports ingested counts', async () => {
    mockApiClient.post.mockResolvedValue({
      data: {
        success: true,
        integration_id: 'zoho',
        records_fetched: 42,
        records_ingested: 40,
      },
    });

    const user = userEvent.setup();
    render(
      <AgentLaunchGuide
        agents={[{ id: 'agt-9', name: 'Closer', category: 'sales' }]}
      />
    );

    // The guide stays up until the apps are connected; the sync action must
    // carry the agent id so records are tagged for that employee's memory.
    await waitFor(() => {
      expect(screen.getByTestId('sync-zoho-cta')).toBeEnabled();
    });
    await user.click(screen.getByTestId('sync-zoho-cta'));

    await waitFor(() => {
      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/api/data-ingestion/sync/zoho?agent_id=agt-9&force=true'
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('ingest-results')).toHaveTextContent(
        /fetched 42 records, ingested 40/i
      );
    });
  });

  test('shows pending training proposal count on the train step', async () => {
    mockApi.listTrainingProposals.mockResolvedValue([{ id: 'tp-1' }, { id: 'tp-2' }]);

    render(<AgentLaunchGuide agents={[]} />);

    await waitFor(() => {
      expect(screen.getByTestId('pending-training-badge')).toHaveTextContent(
        '2 training proposals waiting'
      );
    });
  });
});
