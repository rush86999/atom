/**
 * BYOKManager Component Tests
 *
 * Tests verify the real BYOKManager component
 * (components/DevStudio/BYOKManager.tsx):
 * - loading spinner while providers are fetched
 * - stats cards (total/active providers, accumulated cost) and provider table
 * - Add API Key modal: pre-selected provider from the row action, key entry,
 *   POST /api/ai/providers/:id/keys with {api_key, key_name} and re-fetch
 * - missing-input validation toast
 * - delete-key flow via DELETE /api/ai/providers/:id/keys/:keyName
 *
 * API: GET /api/ai/providers, POST /api/ai/providers/:id/keys,
 *      DELETE /api/ai/providers/:id/keys/:keyName
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import BYOKManager from '../BYOKManager';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));
jest.mock('../../ui/spinner', () => ({
  Spinner: () => <div data-testid="spinner">Loading...</div>,
}));

const openaiProvider = {
  provider: {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT models',
    cost_per_token: 0.0001,
    supported_tasks: ['chat', 'completion'],
    is_active: true,
  },
  usage: {
    total_requests: 120,
    successful_requests: 115,
    failed_requests: 5,
    cost_accumulated: 0.2,
  },
  has_api_keys: true,
  status: 'active',
};

const anthropicProvider = {
  provider: {
    id: 'anthropic',
    name: 'Anthropic',
    description: 'Claude models',
    cost_per_token: 0.0002,
    supported_tasks: ['chat'],
    is_active: true,
  },
  usage: {
    total_requests: 40,
    successful_requests: 38,
    failed_requests: 2,
    cost_accumulated: 0.1,
  },
  has_api_keys: false,
  status: 'inactive',
};

describe('BYOKManager', () => {
  let postedKeys: any[];
  let deletedKeys: string[];
  let providerFetchCount: number;

  beforeEach(() => {
    jest.clearAllMocks();
    postedKeys = [];
    deletedKeys = [];
    providerFetchCount = 0;

    server.resetHandlers();
    server.use(
      rest.get('/api/ai/providers', (req, res, ctx) => {
        providerFetchCount += 1;
        return res(ctx.status(200), ctx.json({ providers: [openaiProvider, anthropicProvider] }));
      }),
      rest.post('/api/ai/providers/:providerId/keys', async (req, res, ctx) => {
        postedKeys.push({ providerId: req.params.providerId, body: req.body });
        return res(ctx.status(200), ctx.json({ success: true, key_name: 'default' }));
      }),
      rest.delete('/api/ai/providers/:providerId/keys/:keyName', (req, res, ctx) => {
        deletedKeys.push(`${req.params.providerId}/${req.params.keyName}`);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  it('shows a loading spinner before providers arrive', () => {
    render(<BYOKManager />);
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('renders the header, stats cards and provider table', async () => {
    render(<BYOKManager />);

    await screen.findByText('AI Providers (BYOK)');
    expect(screen.getByText('Total Providers')).toBeInTheDocument();
    expect(screen.getByText('Active Providers')).toBeInTheDocument();
    expect(screen.getAllByText('Total Cost').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('$0.3000')).toBeInTheDocument();

    expect(screen.getByText('OpenAI')).toBeInTheDocument();
    expect(screen.getByText('openai')).toBeInTheDocument();
    expect(screen.getByText('Anthropic')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText('inactive')).toBeInTheDocument();
    expect(screen.getByText('$0.0001')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
  });

  it('opens the modal from a row "Add Key" with the provider pre-selected', async () => {
    render(<BYOKManager />);

    const rows = await screen.findAllByRole('row');
    const anthropicRow = rows.find((row) => within(row).queryByText('Anthropic'));
    expect(anthropicRow).toBeTruthy();

    fireEvent.click(within(anthropicRow as HTMLElement).getByRole('button', { name: /add key/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByText('anthropic')).toBeInTheDocument();
  });

  it('validates that a provider and key are required before saving', async () => {
    render(<BYOKManager />);

    fireEvent.click(await screen.findByRole('button', { name: /add api key/i }));
    await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: /save key/i }));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Missing information',
        description: 'Please select a provider and enter an API key',
      })
    );
    expect(postedKeys).toHaveLength(0);
  });

  it('adds an API key via POST and refetches the provider list', async () => {
    render(<BYOKManager />);

    const rows = await screen.findAllByRole('row');
    const anthropicRow = rows.find((row) => within(row).queryByText('Anthropic'));
    fireEvent.click(within(anthropicRow as HTMLElement).getByRole('button', { name: /add key/i }));
    await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('sk-...'), { target: { value: 'sk-ant-xyz' } });
    fireEvent.change(screen.getByPlaceholderText('default'), { target: { value: 'prod' } });

    const fetchesBeforeSave = providerFetchCount;
    fireEvent.click(screen.getByRole('button', { name: /save key/i }));

    await waitFor(() => {
      expect(postedKeys).toHaveLength(1);
    });
    expect(postedKeys[0].providerId).toBe('anthropic');
    expect(postedKeys[0].body).toEqual({ api_key: 'sk-ant-xyz', key_name: 'prod' });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'API Key added' })
      );
    });
    await waitFor(() => expect(providerFetchCount).toBeGreaterThan(fetchesBeforeSave));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('shows an error toast when the key POST fails', async () => {
    server.use(
      rest.post('/api/ai/providers/:providerId/keys', (req, res, ctx) => {
        return res(ctx.status(400), ctx.json({ detail: 'Invalid key format' }));
      })
    );

    render(<BYOKManager />);

    const rows = await screen.findAllByRole('row');
    const anthropicRow = rows.find((row) => within(row).queryByText('Anthropic'));
    fireEvent.click(within(anthropicRow as HTMLElement).getByRole('button', { name: /add key/i }));
    await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('sk-...'), { target: { value: 'bad' } });
    fireEvent.click(screen.getByRole('button', { name: /save key/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error adding key', description: 'Invalid key format' })
      );
    });
  });

  it('deletes an API key via DELETE and shows the success toast', async () => {
    render(<BYOKManager />);

    const rows = await screen.findAllByRole('row');
    const openaiRow = rows.find((row) => within(row).queryByText('OpenAI'));
    fireEvent.click(within(openaiRow as HTMLElement).getByRole('button'));

    await waitFor(() => {
      expect(deletedKeys).toContain('openai/default');
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'API Key deleted' })
    );
    await waitFor(() => expect(providerFetchCount).toBeGreaterThanOrEqual(2));
  });

  it('sends the stored JWT on BYOK calls (round 80)', async () => {
    let authHeader: string | undefined;
    window.localStorage.setItem('auth_token', 'jwt-byok-token');
    server.use(
      rest.get('/api/ai/providers', (req, res, ctx) => {
        authHeader = req.headers.get('authorization') ?? undefined;
        providerFetchCount += 1;
        return res(ctx.status(200), ctx.json({ providers: [openaiProvider, anthropicProvider] }));
      })
    );

    render(<BYOKManager />);
    await screen.findByText('AI Providers (BYOK)');
    await waitFor(() => expect(authHeader).toBe('Bearer jwt-byok-token'));
  });

  it('cancels the modal without posting', async () => {
    render(<BYOKManager />);

    fireEvent.click(await screen.findByRole('button', { name: /add api key/i }));
    await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(postedKeys).toHaveLength(0);
  });
});
