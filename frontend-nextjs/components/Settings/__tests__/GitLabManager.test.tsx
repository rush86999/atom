/**
 * GitLabManager component tests.
 *
 * Covers: connection status fetch (connected user card / disconnected /
 * error), Connect redirect, and disconnect flow with success + failure paths.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import GitLabManager from '../GitLabManager';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockSession = useSession as jest.Mock;

const connectedPayload = {
  success: true,
  connected_services: ['gitlab'],
  service_info: {
    gitlab: {
      user: { id: 'gl-1', name: 'Ada Lovelace', username: 'ada', avatar_url: 'http://avatar/ada.png' },
    },
  },
};

describe('GitLabManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/api/v1/users/u1/services') && init?.method === 'DELETE') {
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      if (u.includes('/api/v1/users/u1/services')) {
        return Promise.resolve({ ok: true, json: async () => ({ success: true, connected_services: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('renders the disconnected state with a Connect button', async () => {
    render(<GitLabManager />);
    expect(await screen.findByText(/GitLab Integration/)).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Connect GitLab/ })).toBeInTheDocument();
  });

  it('shows the connected user card and counters', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => connectedPayload });
    render(<GitLabManager />);
    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('@ada')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disconnect GitLab/ })).toBeInTheDocument();
  });

  it('shows the error message when the status call throws', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('gitlab down'));
    render(<GitLabManager />);
    expect(await screen.findByText('Failed to check GitLab connection')).toBeInTheDocument();
  });

  it('opens the GitLab authorize redirect', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<GitLabManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Connect GitLab/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/gitlab/authorize?user_id=u1', '_self');
  });

  it('disconnects, toasts success, and returns to disconnected state', async () => {
    global.fetch = jest
      .fn()
      .mockImplementation((url: string, init?: RequestInit) => {
        if (init?.method === 'DELETE') {
          return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
        }
        return Promise.resolve({ ok: true, json: async () => connectedPayload });
      });
    render(<GitLabManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect GitLab/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'GitLab disconnected' }));
    });
    expect(await screen.findByRole('button', { name: /Connect GitLab/ })).toBeInTheDocument();
  });

  it('toasts an error when the disconnect request fails', async () => {
    global.fetch = jest
      .fn()
      .mockImplementation((url: string, init?: RequestInit) => {
        if (init?.method === 'DELETE') {
          return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
        }
        return Promise.resolve({ ok: true, json: async () => connectedPayload });
      });
    render(<GitLabManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect GitLab/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Error disconnecting GitLab' }));
    });
    expect(screen.getByText('Failed to disconnect')).toBeInTheDocument();
  });
});
