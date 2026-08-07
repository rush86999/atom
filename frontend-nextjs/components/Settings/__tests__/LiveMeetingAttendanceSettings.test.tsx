/**
 * LiveMeetingAttendanceSettings component tests.
 *
 * Covers: settings fetch (enabled/disabled), toggle enabling with success
 * toast, toggle failure reverting the switch with error toast, and the
 * enabled-state info box.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import LiveMeetingAttendanceSettings from '../LiveMeetingAttendanceSettings';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockSession = useSession as jest.Mock;

describe('LiveMeetingAttendanceSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ success: true, enabled: false }) });
    });
  });

  it('renders the toggle and description', async () => {
    render(<LiveMeetingAttendanceSettings />);
    expect(await screen.findByLabelText(/Auto-attend Meetings/)).toBeInTheDocument();
    expect(screen.getByText(/Automatically join calendar meetings/)).toBeInTheDocument();
  });

  it('turns the toggle on when the saved setting is enabled', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true, enabled: true }) });
    render(<LiveMeetingAttendanceSettings />);
    const toggle = await screen.findByRole('switch');
    await waitFor(() => {
      expect(toggle).toHaveAttribute('data-state', 'checked');
    });
    expect(screen.getByText(/ATOM will join upcoming Zoom and Teams meetings/)).toBeInTheDocument();
  });

  it('enables auto-attendance and toasts success', async () => {
    render(<LiveMeetingAttendanceSettings />);
    const toggle = await screen.findByRole('switch');
    await waitFor(() => {
      expect(toggle).not.toBeDisabled();
    });
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Auto-attendance enabled', variant: 'success' })
      );
    });
    const posted = (global.fetch as jest.Mock).mock.calls.find(([, init]) => init?.method === 'POST');
    expect(posted[0]).toBe('/api/users/u1/settings/meeting-attendance');
    expect(JSON.parse(posted[1].body)).toEqual({ enabled: true });
  });

  it('reverts the toggle and toasts an error when the update fails', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ success: true, enabled: false }) });
    });
    render(<LiveMeetingAttendanceSettings />);
    const toggle = await screen.findByRole('switch');
    await waitFor(() => {
      expect(toggle).not.toBeDisabled();
    });
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error updating meeting attendance settings' })
      );
    });
    expect(toggle).toHaveAttribute('data-state', 'unchecked');
  });
});
