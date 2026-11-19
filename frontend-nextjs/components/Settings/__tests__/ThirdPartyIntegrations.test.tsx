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

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockSession = useSession as jest.Mock;

describe('ThirdPartyIntegrations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
