/**
 * GDriveManager component tests.
 *
 * NOTE: this suite mocks the skill module contract (re-created at
 * not exist in this repository (confirmed via `find` — no src/skills dir).
 * This is a latent missing-import bug; the tests mock that module with its
 * documented contract ({ ok, data, error }) so the component logic is
 * exercised meaningfully.
 *
 * Covers: status fetch (connected/disconnected/error), Connect redirect,
 * disconnect flow with success toast, and the missing-user-id guard.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import GDriveManager from '../GDriveManager';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('../skills/gdriveSkills', () => ({
  getGDriveConnectionStatus: jest.fn(),
  disconnectGDrive: jest.fn(),
}));

import { getGDriveConnectionStatus, disconnectGDrive } from '../skills/gdriveSkills';

const mockSession = useSession as jest.Mock;
const mockGetStatus = getGDriveConnectionStatus as jest.Mock;
const mockDisconnect = disconnectGDrive as jest.Mock;

describe('GDriveManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: false, reason: '' } });
    mockDisconnect.mockResolvedValue({ ok: true });
  });

  it('renders Disconnected state and Connect Drive button', async () => {
    render(<GDriveManager />);
    expect(await screen.findByText('Google Drive')).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Connect Drive/ })).toBeInTheDocument();
    expect(screen.getByText(/Grant ATOM permission/)).toBeInTheDocument();
  });

  it('renders Connected state with a Disconnect button when connected', async () => {
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: true, reason: '' } });
    render(<GDriveManager />);
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disconnect/ })).toBeInTheDocument();
    expect(screen.getByText(/Connected to Google Drive/)).toBeInTheDocument();
  });

  it('shows the status error when the status call fails', async () => {
    mockGetStatus.mockResolvedValue({ ok: false, error: { message: 'status exploded' } });
    render(<GDriveManager />);
    expect(await screen.findByText('status exploded')).toBeInTheDocument();
  });

  it('shows the exception message when the status call throws', async () => {
    mockGetStatus.mockRejectedValue(new Error('network down'));
    render(<GDriveManager />);
    expect(await screen.findByText('network down')).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('opens the Google Drive OAuth redirect with scope=drive', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<GDriveManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Connect Drive/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/google/initiate?user_id=u1&scope=drive', '_self');
  });

  it('disconnects, toasts success, and re-fetches status', async () => {
    mockGetStatus
      .mockResolvedValueOnce({ ok: true, data: { isConnected: true, reason: '' } })
      .mockResolvedValueOnce({ ok: true, data: { isConnected: false, reason: '' } });
    render(<GDriveManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect/ }));
    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalledWith('u1');
    });
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Google Drive disconnected successfully' }));
    });
    expect(await screen.findByRole('button', { name: /Connect Drive/ })).toBeInTheDocument();
  });

  it('toasts the error message when disconnecting fails', async () => {
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: true, reason: '' } });
    mockDisconnect.mockResolvedValue({ ok: false, error: { message: 'revoke failed' } });
    render(<GDriveManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'revoke failed' }));
    });
  });

  it('flags a missing user id instead of navigating', async () => {
    mockSession.mockReturnValue({ data: { user: { id: undefined } }, status: 'authenticated' });
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<GDriveManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Connect Drive/ }));
    await waitFor(() => {
      expect(screen.getByText('User ID is missing.')).toBeInTheDocument();
    });
    expect(openSpy).not.toHaveBeenCalled();
  });
});
