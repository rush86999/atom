/**
 * DropboxManager component tests.
 *
 * NOTE: this suite mocks the skill module contract (re-created at
 * not exist in this repository (confirmed via `find` — no src/skills dir).
 * This is a latent missing-import bug; the tests mock that module with its
 * documented contract ({ ok, data, error }) so the component logic is
 * exercised meaningfully.
 *
 * Covers: status fetch (connected/disconnected/failure), Connect redirect,
 * disconnect flow with success toast, and the missing-user-id guard.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import DropboxManager from '../DropboxManager';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('../skills/dropboxSkills', () => ({
  getDropboxConnectionStatus: jest.fn(),
  disconnectDropbox: jest.fn(),
}));

import { getDropboxConnectionStatus, disconnectDropbox } from '../skills/dropboxSkills';

const mockSession = useSession as jest.Mock;
const mockGetStatus = getDropboxConnectionStatus as jest.Mock;
const mockDisconnect = disconnectDropbox as jest.Mock;

describe('DropboxManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: false, reason: '' } });
    mockDisconnect.mockResolvedValue({ ok: true });
  });

  it('renders Disconnected state and Connect Dropbox button', async () => {
    render(<DropboxManager />);
    expect(await screen.findByText('Connection Status')).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Connect Dropbox/ })).toBeInTheDocument();
    expect(screen.getByText(/No Dropbox account connected/)).toBeInTheDocument();
  });

  it('renders Connected state when connected', async () => {
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: true, reason: '' } });
    render(<DropboxManager />);
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(screen.getByText(/Connected to Dropbox account/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disconnect/ })).toBeInTheDocument();
  });

  it('shows the status error message on failed status call', async () => {
    mockGetStatus.mockResolvedValue({ ok: false, error: { message: 'no dropbox' } });
    render(<DropboxManager />);
    expect(await screen.findByText('no dropbox')).toBeInTheDocument();
  });

  it('shows the exception message when the status call throws', async () => {
    mockGetStatus.mockRejectedValue(new Error('timeout'));
    render(<DropboxManager />);
    expect(await screen.findByText('timeout')).toBeInTheDocument();
  });

  it('opens the Dropbox OAuth redirect', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<DropboxManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Connect Dropbox/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/dropbox/initiate?user_id=u1', '_self');
  });

  it('disconnects, toasts success, and refreshes status', async () => {
    mockGetStatus
      .mockResolvedValueOnce({ ok: true, data: { isConnected: true, reason: '' } })
      .mockResolvedValueOnce({ ok: true, data: { isConnected: false, reason: '' } });
    render(<DropboxManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect/ }));
    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalledWith('u1');
    });
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Dropbox disconnected successfully' }));
    });
    expect(await screen.findByRole('button', { name: /Connect Dropbox/ })).toBeInTheDocument();
  });

  it('toasts the error when disconnecting fails', async () => {
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: true, reason: '' } });
    mockDisconnect.mockResolvedValue({ ok: false, error: { message: 'revoke failed' } });
    render(<DropboxManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'revoke failed' }));
    });
  });

  it('flags a missing user id instead of navigating', async () => {
    mockSession.mockReturnValue({ data: { user: { id: undefined } }, status: 'authenticated' });
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<DropboxManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Connect Dropbox/ }));
    await waitFor(() => {
      expect(screen.getByText('User ID is missing.')).toBeInTheDocument();
    });
    expect(openSpy).not.toHaveBeenCalled();
  });
});
