/**
 * AtomAgentSettings component tests.
 *
 * Covers: loading gate, calendar status fetch + connect redirect, Zapier
 * webhook URL load/save (success + failure toasts), wake-word section with
 * wake word enabled state and toggle, and child section rendering.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import { useWakeWord } from '@/contexts/WakeWordContext';
import AtomAgentSettings from '../AtomAgentSettings';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

jest.mock('@/contexts/WakeWordContext', () => ({
  useWakeWord: jest.fn(),
}));

// Child components bring broken src/skills imports (gdrive/dropbox) and their
// own fetch cycles; stub them so this suite tests AtomAgentSettings itself.
jest.mock('../VoiceSettings', () => () => <div data-testid="voice-settings">Voice Settings</div>);
jest.mock('../GDriveManager', () => () => <div data-testid="gdrive-manager">GDrive</div>);
jest.mock('../DropboxManager', () => () => <div data-testid="dropbox-manager">Dropbox</div>);
jest.mock('../LiveMeetingAttendanceSettings', () => () => <div data-testid="meeting-attendance">Meeting</div>);

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockSession = useSession as jest.Mock;
const mockWakeWord = useWakeWord as jest.Mock;

const authenticated = { data: { user: { id: 'u1', email: 'user@example.com' } }, status: 'authenticated' };

describe('AtomAgentSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue(authenticated);
    mockWakeWord.mockReturnValue({
      isWakeWordEnabled: false,
      toggleWakeWord: jest.fn(),
      isListening: false,
      wakeWordError: null,
    });
    global.fetch = jest.fn().mockImplementation((url: string) => {
      const u = String(url);
      if (u.includes('/api/integrations/calendar/status')) {
        return Promise.resolve({ ok: true, json: async () => ({ isConnected: true }) });
      }
      if (u.includes('/api/integrations/credentials?service=zapier_webhook_url')) {
        return Promise.resolve({ ok: true, json: async () => ({ isConnected: true, value: 'https://hooks.zapier.com/hooks/catch/abc' }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('shows the loading gate while the session is loading', () => {
    mockSession.mockReturnValue({ data: null, status: 'loading' });
    render(<AtomAgentSettings />);
    expect(screen.getByText(/Loading settings/)).toBeInTheDocument();
  });

  it('renders all integration sections and the connected user email', async () => {
    render(<AtomAgentSettings />);
    expect(await screen.findByText('Agent Settings')).toBeInTheDocument();
    expect(screen.getByText('Voice & Wake Word')).toBeInTheDocument();
    expect(screen.getByText('Google Workspace')).toBeInTheDocument();
    expect(screen.getByText('Dropbox Integration')).toBeInTheDocument();
    expect(screen.getByText('Live Meeting Attendance')).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
    expect(screen.getByText('Connected to Google')).toBeInTheDocument();
    expect(screen.getByTestId('voice-settings')).toBeInTheDocument();
    expect(screen.getByTestId('gdrive-manager')).toBeInTheDocument();
    expect(screen.getByTestId('dropbox-manager')).toBeInTheDocument();
    expect(screen.getByTestId('meeting-attendance')).toBeInTheDocument();
  });

  it('loads and pre-fills the saved Zapier webhook URL', async () => {
    render(<AtomAgentSettings />);
    const input = (await screen.findByLabelText(/Zapier Webhook URL/)) as HTMLInputElement;
    expect(input.value).toBe('https://hooks.zapier.com/hooks/catch/abc');
  });

  it('redirects to Google auth when connecting the calendar', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<AtomAgentSettings />);
    fireEvent.click(await screen.findByRole('button', { name: /Reconnect Google/ }));
    expect(openSpy).toHaveBeenCalledWith('/api/auth/google/initiate', '_self');
  });

  it('saves the Zapier webhook URL and toasts success', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/api/integrations/credentials') && init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ isConnected: false }) });
    });
    render(<AtomAgentSettings />);
    const input = (await screen.findByLabelText(/Zapier Webhook URL/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'https://hooks.zapier.com/hooks/catch/xyz' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Webhook URL/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Zapier Webhook URL saved successfully.' }));
    });
    const posted = (global.fetch as jest.Mock).mock.calls.find(([url, init]) => init?.method === 'POST');
    expect(JSON.parse(posted[1].body)).toEqual({ service: 'zapier_webhook_url', secret: 'https://hooks.zapier.com/hooks/catch/xyz' });
  });

  it('toasts an error when saving the webhook URL fails', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/api/integrations/credentials') && init?.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ isConnected: false }) });
    });
    render(<AtomAgentSettings />);
    const input = (await screen.findByLabelText(/Zapier Webhook URL/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'https://hooks.zapier.com/hooks/catch/xyz' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Webhook URL/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to save Zapier Webhook URL.' }));
    });
  });

  it('shows the wake word status when enabled and toggles it', async () => {
    const toggleWakeWord = jest.fn();
    mockWakeWord.mockReturnValue({
      isWakeWordEnabled: true,
      toggleWakeWord,
      isListening: true,
      wakeWordError: null,
    });
    render(<AtomAgentSettings />);
    expect(await screen.findByText(/Listening for "Hey Atom"/)).toBeInTheDocument();
    const wakeSwitch = screen.getByRole('switch', { name: /Wake Word Detection/ });
    fireEvent.click(wakeSwitch);
    expect(toggleWakeWord).toHaveBeenCalled();
  });

  it('renders the wake word error message when present', async () => {
    mockWakeWord.mockReturnValue({
      isWakeWordEnabled: true,
      toggleWakeWord: jest.fn(),
      isListening: false,
      wakeWordError: 'Microphone permission denied',
    });
    render(<AtomAgentSettings />);
    expect(await screen.findByText('Microphone permission denied')).toBeInTheDocument();
  });
});
