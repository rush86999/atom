/**
 * GitHubManager component tests.
 *
 * Covers: connection status fetch (connected/masked token), saving a token
 * (success + failure toasts), empty-token guard, and connect-state button
 * labels.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import GitHubManager from '../GithubManager';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockSession = useSession as jest.Mock;

describe('GitHubManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/api/integrations/credentials') && u.includes('service=github') && !init) {
        return Promise.resolve({ ok: true, json: async () => ({ isConnected: false }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('renders the integration card with Not Connected badge by default', async () => {
    render(<GitHubManager />);
    expect(await screen.findByText('GitHub Integration')).toBeInTheDocument();
    expect(screen.getByText('Not Connected')).toBeInTheDocument();
    expect(screen.getByText('Save Token')).toBeInTheDocument();
  });

  it('masks an existing token when already connected', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: true }),
    });
    render(<GitHubManager />);
    const input = (await screen.findByLabelText(/Personal Access Token/)) as HTMLInputElement;
    expect(input.value).toBe('********');
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Update Token')).toBeInTheDocument();
  });

  it('saves the API key and toasts success on ok', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ isConnected: false }) });
    });
    render(<GitHubManager />);
    const input = (await screen.findByLabelText(/Personal Access Token/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'ghp_12345' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Token/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'GitHub API Key saved successfully.' }));
    });
    const posted = (global.fetch as jest.Mock).mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(posted[1].body)).toEqual({ service: 'github', secret: 'ghp_12345' });
    expect((screen.getByLabelText(/Personal Access Token/) as HTMLInputElement).value).toBe('********');
  });

  it('toasts an error when the save request fails', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ isConnected: false }) });
    });
    render(<GitHubManager />);
    const input = (await screen.findByLabelText(/Personal Access Token/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'ghp_12345' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Token/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to save GitHub API Key.' }));
    });
    expect(screen.getByText('Not Connected')).toBeInTheDocument();
  });

  it('does nothing when saving with an empty token', async () => {
    render(<GitHubManager />);
    await screen.findByLabelText(/Personal Access Token/);
    fireEvent.click(screen.getByRole('button', { name: /Save Token/ }));
    await waitFor(() => {
      expect(global.fetch).not.toHaveBeenCalledWith(
        '/api/integrations/credentials',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });
});
