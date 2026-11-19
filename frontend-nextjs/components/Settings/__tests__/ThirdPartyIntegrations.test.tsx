/**
 * ThirdPartyIntegrations component tests.
 *
 * Covers: loading previously-saved credentials (masked values), saving Jira
 * and Trello credential sets (success + failure toasts), Stripe/Notion saves,
 * and Connect buttons redirecting to their OAuth starts.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import ThirdPartyIntegrations from '../ThirdPartyIntegrations';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

jest.mock('@/lib/api-client', () => ({
  apiClient: { post: jest.fn() },
}), { virtual: true });

const mockApiPost = (jest.requireMock('@/lib/api-client') as any).apiClient.post as jest.Mock;

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockSession = useSession as jest.Mock;

describe('ThirdPartyIntegrations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiPost.mockResolvedValue({
      data: { connection_id: 'conn_1', account: 'acct_123', mode: 'test' },
    });
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({ message: 'saved' }) });
      }
      const connectedServices = ['trello_api_key', 'jira_username', 'jira_server_url', 'stripe_api_key'];
      const service = new URL(String(u), 'http://x').searchParams.get('service');
      return Promise.resolve({
        ok: true,
        json: async () => ({ isConnected: connectedServices.includes(service), value: 'cached-value' }),
      });
    });
  });

  it('renders all integration sections', async () => {
    render(<ThirdPartyIntegrations />);
    expect(await screen.findByText('Third-Party Integrations')).toBeInTheDocument();
    expect(screen.getByText('Asana Integration')).toBeInTheDocument();
    expect(screen.getByText('Jira Integration')).toBeInTheDocument();
    expect(screen.getByText('Trello Integration')).toBeInTheDocument();
    expect(screen.getByText('Cloud Storage & Collaboration')).toBeInTheDocument();
    expect(screen.getByText('Business & Productivity')).toBeInTheDocument();
  });

  it('pre-fills previously saved credentials with masked values', async () => {
    render(<ThirdPartyIntegrations />);
    await waitFor(() => {
      expect((screen.getByLabelText(/Jira Username/) as HTMLInputElement).value).toBe('cached-value');
    });
    expect((screen.getByLabelText(/Jira Server URL/) as HTMLInputElement).value).toBe('cached-value');
    expect((screen.getByLabelText(/Trello API Key/) as HTMLInputElement).value).toBe('********');
    expect((screen.getByLabelText(/Stripe API Key/) as HTMLInputElement).value).toBe('********');
  });

  it('renders the dedicated Stripe invoice verification controls alongside the legacy Stripe save', async () => {
    render(<ThirdPartyIntegrations />);
    expect(await screen.findByText('Stripe Invoice Verification')).toBeInTheDocument();
    expect(screen.getByLabelText(/Stripe Restricted Key/)).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText(/Stripe Account ID/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save Stripe/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ })).toBeInTheDocument();
  });

  it('verifies a Stripe invoice connection through the shared api client, clears the key, and shows account/mode', async () => {
    render(<ThirdPartyIntegrations />);

    const restrictedKey = screen.getByLabelText(/Stripe Restricted Key/) as HTMLInputElement;
    const accountId = screen.getByLabelText(/Stripe Account ID/) as HTMLInputElement;
    fireEvent.change(restrictedKey, { target: { value: 'rk_test_secret_value' } });
    fireEvent.change(accountId, { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/integrations/stripe/invoice-connection',
        { restricted_key: 'rk_test_secret_value', account_id: 'acct_123' },
        { retry: false }
      );
    });
    await waitFor(() => {
      expect(restrictedKey.value).toBe('');
      expect(screen.getByText('acct_123')).toBeInTheDocument();
      expect(screen.getByText('test')).toBeInTheDocument();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Stripe invoice connection verified.', variant: 'success' })
    );
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
    expect(document.body.textContent).not.toContain('rk_test_secret_value');
  });

  it('accepts a live mode invoice connection when the account matches', async () => {
    mockApiPost.mockResolvedValueOnce({
      data: { connection_id: 'conn_live', account: 'acct_123', mode: 'live' },
    });
    render(<ThirdPartyIntegrations />);

    fireEvent.change(screen.getByLabelText(/Stripe Restricted Key/), { target: { value: 'rk_live_secret' } });
    fireEvent.change(screen.getByLabelText(/Stripe Account ID/), { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(screen.getByText('live')).toBeInTheDocument();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Stripe invoice connection verified.', variant: 'success' })
    );
    expect(document.body.textContent).not.toContain('rk_live_secret');
  });

  it.each([
    ['a blank connection id', { connection_id: '   ', account: 'acct_123', mode: 'test' }],
    ['a mismatched account', { connection_id: 'conn_1', account: 'acct_other', mode: 'test' }],
    ['an unsupported mode', { connection_id: 'conn_1', account: 'acct_123', mode: 'sandbox' }],
  ])('rejects an invoice connection response with %s', async (_label, data) => {
    mockApiPost.mockResolvedValueOnce({ data });
    render(<ThirdPartyIntegrations />);

    const restrictedKey = screen.getByLabelText(/Stripe Restricted Key/) as HTMLInputElement;
    fireEvent.change(restrictedKey, { target: { value: 'rk_test_secret_value' } });
    fireEvent.change(screen.getByLabelText(/Stripe Account ID/), { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to verify Stripe invoice connection.',
          variant: 'error',
        })
      );
    });
    expect(mockToast.toast).not.toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Stripe invoice connection verified.' })
    );
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(restrictedKey.value).toBe('rk_test_secret_value');
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
    expect(document.body.textContent).not.toContain('rk_test_secret_value');
  });

  it('shows a safe Stripe invoice verification failure without exposing or clearing the key', async () => {
    mockApiPost.mockRejectedValueOnce(new Error('rejected rk_test_secret_value'));
    render(<ThirdPartyIntegrations />);

    const restrictedKey = screen.getByLabelText(/Stripe Restricted Key/) as HTMLInputElement;
    fireEvent.change(restrictedKey, { target: { value: 'rk_test_secret_value' } });
    fireEvent.change(screen.getByLabelText(/Stripe Account ID/), { target: { value: 'acct_123' } });
    fireEvent.click(screen.getByRole('button', { name: /Verify Stripe Invoice Connection/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Failed to verify Stripe invoice connection.',
          variant: 'error',
        })
      );
    });
    expect(restrictedKey.value).toBe('rk_test_secret_value');
    expect(JSON.stringify(mockToast.toast.mock.calls)).not.toContain('rk_test_secret_value');
    expect(document.body.textContent).not.toContain('rk_test_secret_value');
  });

  it('keeps saving the legacy Stripe API key through the credentials endpoint', async () => {
    render(<ThirdPartyIntegrations />);

    const legacyKey = screen.getByLabelText(/Stripe API Key/) as HTMLInputElement;
    fireEvent.change(legacyKey, { target: { value: 'sk_test_legacy' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Stripe/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Stripe API Key saved successfully.' })
      );
    });
    const credentialPost = (global.fetch as jest.Mock).mock.calls.find(([url, init]) => (
      init?.method === 'POST' && String(url) === '/api/integrations/credentials'
    ));
    expect(credentialPost).toBeTruthy();
    expect(JSON.parse(credentialPost[1].body)).toEqual({
      service: 'stripe_api_key',
      secret: 'sk_test_legacy',
    });
    expect(legacyKey.value).toBe('********');
    expect(mockApiPost).not.toHaveBeenCalled();
  });

  it('saves Jira credentials and toasts success for each', async () => {
    render(<ThirdPartyIntegrations />);
    fireEvent.click(screen.getByRole('button', { name: /Save Jira Credentials/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Jira Username saved successfully.' })
      );
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Jira API Key saved successfully.' })
    );
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Jira Server URL saved successfully.' })
    );
    const posts = (global.fetch as jest.Mock).mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(3);
    expect(posts.map(([, init]) => JSON.parse(init.body).service)).toEqual([
      'jira_username',
      'jira_api_key',
      'jira_server_url',
    ]);
    expect((screen.getByLabelText(/Jira API Key/) as HTMLInputElement).value).toBe('********');
  });

  it('saves Trello credentials and masks both fields', async () => {
    render(<ThirdPartyIntegrations />);
    const apiKey = screen.getByLabelText(/Trello API Key/) as HTMLInputElement;
    fireEvent.change(apiKey, { target: { value: 'trello-key' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Trello Credentials/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Trello API Key saved successfully.' })
      );
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Trello API Token saved successfully.' })
    );
    expect((screen.getByLabelText(/Trello API Key/) as HTMLInputElement).value).toBe('********');
    expect((screen.getByLabelText(/Trello Token/) as HTMLInputElement).value).toBe('********');
  });

  it('toasts the API error message when a save fails', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: async () => ({ message: 'backend exploded' }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({ isConnected: false }) });
    });
    render(<ThirdPartyIntegrations />);
    fireEvent.click(screen.getByRole('button', { name: /Save Jira Credentials/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'backend exploded', variant: 'error' })
      );
    });
    expect(mockToast.toast).toHaveBeenCalledTimes(3);
  });

  it('redirects to the OAuth start pages when connecting', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<ThirdPartyIntegrations />);
    await screen.findByText('Third-Party Integrations');
    fireEvent.click(screen.getByRole('button', { name: /Connect Asana/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/asana/initiate', '_self');
    fireEvent.click(screen.getByRole('button', { name: /Connect Slack/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/slack/initiate', '_self');
    fireEvent.click(screen.getByRole('button', { name: /Connect Zoom/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/zoom/initiate', '_self');
    fireEvent.click(screen.getByRole('button', { name: /Connect Box/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/box/initiate', '_self');
    fireEvent.click(screen.getByRole('button', { name: /Connect Pocket/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/pocket/oauth/start', '_self');
  });
});
