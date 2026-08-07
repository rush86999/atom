/**
 * VoiceSettings component tests.
 *
 * Covers: loading saved provider + masked API key, provider change clearing
 * the key, saving settings (success message + masking), save failure with the
 * API message, and server-error toast.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import VoiceSettings from '../VoiceSettings';

describe('VoiceSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('service=tts_provider')) {
        return Promise.resolve({ ok: true, json: async () => ({ value: 'elevenlabs' }) });
      }
      if (u.includes('service=elevenlabs_api_key')) {
        return Promise.resolve({ ok: true, json: async () => ({ isConnected: true }) });
      }
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({ message: 'saved' }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('renders the voice settings form with the default provider', async () => {
    render(<VoiceSettings />);
    expect(await screen.findByText('Voice Settings')).toBeInTheDocument();
    expect(screen.getByLabelText(/TTS Provider/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save Voice Settings/ })).toBeInTheDocument();
  });

  it('loads the saved provider and masks the stored API key', async () => {
    render(<VoiceSettings />);
    await waitFor(() => {
      expect((screen.getByLabelText(/TTS Provider/) as HTMLSelectElement).value).toBe('elevenlabs');
    });
    expect((screen.getByLabelText(/API Key/) as HTMLInputElement).value).toBe('********');
  });

  it('shows the error message when the settings fetch fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('offline'));
    render(<VoiceSettings />);
    expect(await screen.findByText('Failed to fetch voice settings.')).toBeInTheDocument();
  });

  it('clears the API key when the provider changes', async () => {
    render(<VoiceSettings />);
    await waitFor(() => {
      expect((screen.getByLabelText(/API Key/) as HTMLInputElement).value).toBe('********');
    });
    const select = screen.getByLabelText(/TTS Provider/) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'deepgram' } });
    expect(select.value).toBe('deepgram');
    expect((screen.getByLabelText(/API Key/) as HTMLInputElement).value).toBe('');
  });

  it('saves the provider and API key, then shows success and masks the key', async () => {
    render(<VoiceSettings />);
    await screen.findByText('Voice Settings');
    const apiKey = screen.getByLabelText(/API Key/) as HTMLInputElement;
    fireEvent.change(apiKey, { target: { value: 'sk-1234' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Voice Settings/ }));
    expect(await screen.findByText('Voice settings saved successfully.')).toBeInTheDocument();
    expect((screen.getByLabelText(/API Key/) as HTMLInputElement).value).toBe('********');
    const posts = (global.fetch as jest.Mock).mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts.map(([, init]) => JSON.parse(init.body).service)).toEqual(['tts_provider', 'elevenlabs_api_key']);
    expect(JSON.parse(posts[1][1].body).secret).toBe('sk-1234');
  });

  it('shows the API error message when saving fails', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('service=tts_provider') && !init) {
        return Promise.resolve({ ok: true, json: async () => ({ value: 'elevenlabs' }) });
      }
      if (u.includes('service=elevenlabs_api_key') && !init) {
        return Promise.resolve({ ok: true, json: async () => ({ isConnected: true }) });
      }
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({ message: 'key rejected' }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    render(<VoiceSettings />);
    await screen.findByText('Voice Settings');
    fireEvent.click(screen.getByRole('button', { name: /Save Voice Settings/ }));
    expect(await screen.findByText('key rejected')).toBeInTheDocument();
  });

  it('shows a server-error message when saving throws', async () => {
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') return Promise.reject(new Error('network'));
      return Promise.resolve({ ok: true, json: async () => ({ value: 'elevenlabs' }) });
    });
    render(<VoiceSettings />);
    await screen.findByText('Voice Settings');
    fireEvent.click(screen.getByRole('button', { name: /Save Voice Settings/ }));
    expect(await screen.findByText('Failed to connect to the server.')).toBeInTheDocument();
  });
});
