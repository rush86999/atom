/**
 * NextjsManager (NextjsSettings) component tests.
 *
 * Covers: health check on mount (healthy / unhealthy / fetch failure), the
 * health alert contents, the Refresh action, and the Configure Integration
 * toggle panel.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import NextjsSettings from '../NextjsManager';

describe('NextjsSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockImplementation((url: string) => {
      const u = String(url);
      if (u.includes('/api/nextjs/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ services: { nextjs: { status: 'healthy', error: null } } }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('renders the integration card with feature list', async () => {
    render(<NextjsSettings />);
    expect(await screen.findByText('Next.js Integration')).toBeInTheDocument();
    expect(screen.getByText(/Real-time project analytics and monitoring/)).toBeInTheDocument();
    expect(screen.getAllByText(/Vercel/).length).toBeGreaterThan(0);
  });

  it('shows Connected badge and healthy alert when service is healthy', async () => {
    render(<NextjsSettings />);
    expect(await screen.findByText(/Next.js service healthy/)).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('shows Disconnected badge and error details when service is unhealthy', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ services: { nextjs: { status: 'degraded', error: 'connection refused' } } }),
    });
    render(<NextjsSettings />);
    expect(await screen.findByText(/Next.js service unhealthy/)).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(screen.getByText('connection refused')).toBeInTheDocument();
  });

  it('falls back to Disconnected when the health fetch rejects', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('network down'));
    render(<NextjsSettings />);
    expect(await screen.findByText(/Next.js service unhealthy/)).toBeInTheDocument();
    expect(screen.getByText(/Failed to check Next.js service health/)).toBeInTheDocument();
  });

  it('hides the health alert before data arrives', () => {
    global.fetch = jest.fn(() => new Promise(() => {}));
    render(<NextjsSettings />);
    expect(screen.queryByText(/Next.js service/)).not.toBeInTheDocument();
  });

  it('toggles the configure integration panel', async () => {
    render(<NextjsSettings />);
    fireEvent.click(await screen.findByRole('button', { name: /Configure Integration/ }));
    expect(screen.getByText(/configuration panel will be loaded here/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Hide Integration/ }));
    expect(screen.queryByText(/configuration panel will be loaded here/)).not.toBeInTheDocument();
  });

  it('re-fetches health when Refresh is clicked', async () => {
    render(<NextjsSettings />);
    await screen.findByText(/Next.js service healthy/);
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/nextjs/health');
    });
  });
});
