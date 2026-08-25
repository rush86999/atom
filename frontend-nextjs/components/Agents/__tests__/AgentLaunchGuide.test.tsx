/**
 * AgentLaunchGuide tests
 *
 * Locks the guided sales-agent launch journey contract:
 * - Renders all five steps; connect/create CTAs while incomplete
 * - Auto-hides once Zoho + Outlook are connected AND a Sales agent exists
 * - Unconfigured server-side OAuth surfaces env-var guidance instead of a
 *   doomed consent redirect
 * - Create-agent posts POST /api/agents/custom with category "Sales" and
 *   refreshes the parent list
 * - Sync Zoho posts /api/data-ingestion/sync/zoho scoped to the sales agent
 *   and surfaces fetched/ingested counts
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
    ],
  },
};

const configuredBoth = { data: { zoho: true, microsoft: true } };
const nothingConnected = { data: { integrations: [] as Array<{ provider: string; status: string }> } };

beforeEach(() => {
  jest.resetAllMocks();
  localStorage.clear();
  // Default world: OAuth configured server-side, user has connected nothing.
  mockApiClient.get.mockImplementation((url: string) => {
    if (url.includes('/oauth/tokens')) return Promise.resolve(nothingConnected);
    if (url.includes('/config-status')) return Promise.resolve(configuredBoth);
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  mockApi.listTrainingProposals.mockResolvedValue([]);
});

describe('AgentLaunchGuide', () => {
  test('renders all journey steps with CTAs when nothing is set up', async () => {
    render(<AgentLaunchGuide agents={[]} />);

    await waitFor(() => {
      expect(screen.getByTestId('agent-launch-guide')).toBeInTheDocument();
    });
    expect(screen.getByTestId('launch-step-zoho')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-outlook')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-agent')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-ingest')).toBeInTheDocument();
    expect(screen.getByTestId('launch-step-train')).toBeInTheDocument();
    expect(screen.getByTestId('connect-zoho-cta')).toBeInTheDocument();
    expect(screen.getByTestId('connect-outlook-cta')).toBeInTheDocument();
    expect(screen.getByTestId('create-agent-cta')).toBeInTheDocument();
    // Ingestion actions stay visible but gated until the agent exists.
    expect(screen.getByTestId('sync-zoho-cta')).toBeDisabled();
  });

  test('auto-hides when both providers are connected and a Sales agent exists', async () => {
    mockApiClient.get.mockImplementation((url: string) => {
      if (url.includes('/oauth/tokens')) return Promise.resolve(connectedBoth);
      if (url.includes('/config-status')) return Promise.resolve(configuredBoth);
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
      if (url.includes('/oauth/tokens'))
        return Promise.resolve({ data: { integrations: [] } });
      if (url.includes('/config-status'))
        return Promise.resolve({ data: { zoho: false, microsoft: false } });
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

  test('create-agent flow posts category Sales and notifies parent', async () => {
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

  test('sync Zoho is scoped to the sales agent and reports ingested counts', async () => {
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
        agents={[{ id: 'agt-9', name: 'Closer', category: 'Sales' }]}
      />
    );

    // Guide stays up because Outlook/Zoho steps show live status; the sync
    // action must carry the agent id so records are tagged for its memory.
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
        /Fetched 42 records, ingested 40/
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
