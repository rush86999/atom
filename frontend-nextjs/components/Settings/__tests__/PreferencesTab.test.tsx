/**
 * PreferencesTab component tests.
 *
 * Covers: loading gate, applying the saved theme (dark/light/system via
 * document.documentElement classes), saving preferences (success + failure
 * toasts), and graceful fallback when the preferences API is unreachable.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { toast } from 'sonner';
import { PreferencesTab } from '../PreferencesTab';

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

describe('PreferencesTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    document.documentElement.className = '';
    (window.matchMedia as jest.Mock).mockReturnValue({
      matches: false,
      media: '',
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    });
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      if (u.includes('/api/v1/preferences?user_id=me')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ theme: 'dark', notifications_enabled: false, email_frequency: 'weekly' }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('shows the loader until preferences are loaded', () => {
    global.fetch = jest.fn(() => new Promise(() => {}));
    const { container } = render(<PreferencesTab />);
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('loads saved preferences and applies the saved theme', async () => {
    render(<PreferencesTab />);
    expect(await screen.findByText('Appearance')).toBeInTheDocument();
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('renders the notification switches with saved values', async () => {
    render(<PreferencesTab />);
    await screen.findByText('Appearance');
    expect(screen.getAllByRole('switch')).toHaveLength(1);
  });

  it('applies the light theme and toasts success when saving', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ theme: 'light' }) });
    });
    render(<PreferencesTab />);
    await screen.findByText('Appearance');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('applies the system theme based on prefers-color-scheme', async () => {
    (window.matchMedia as jest.Mock).mockReturnValue({
      matches: true,
      media: '',
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    });
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({ theme: 'system' }) });
    });
    render(<PreferencesTab />);
    await screen.findByText('Appearance');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('toasts success on save and error when the save fails', async () => {
    render(<PreferencesTab />);
    await screen.findByText('Appearance');
    fireEvent.click(screen.getAllByRole('switch')[0]);
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('Saved');
    });

    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    fireEvent.click(screen.getAllByRole('switch')[0]);
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to save setting');
    });
  });

  it('falls back to defaults when the API is unreachable', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('offline'));
    render(<PreferencesTab />);
    expect(await screen.findByText('Appearance')).toBeInTheDocument();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
