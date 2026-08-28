/**
 * PipelineSettingsPanel Component Tests
 *
 * Verifies the real PipelineSettingsPanel (components/shared/PipelineSettingsPanel.tsx):
 * - returns null when closed
 * - shows loading skeletons while fetching, then the three pipeline cards
 *   (sales/projects/finance) with mode badges and cron text from the API
 * - defaults to Scheduled / standard cron when the API returns no pipelines
 * - toggling a pipeline POSTs the full settings and flips the mode + toasts
 * - load failure toasts and falls back to default modes without crashing
 * - save failure toasts without corrupting the rendered modes
 *
 * APIs: GET/POST /api/v1/settings/automations/
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockToast = { success: jest.fn(), error: jest.fn(), info: jest.fn() };

jest.mock('sonner', () => ({
  toast: mockToast,
}));

// imported after the sonner mock so the factory never runs before mockToast exists
import { PipelineSettingsPanel } from '../PipelineSettingsPanel';

const pipelinesPayload = {
  pipelines: {
    sales: { mode: 'real_time', cron: '*/5 * * * *' },
    projects: { mode: 'scheduled', cron: '0 2 * * *' },
    finance: { mode: 'scheduled', cron: '0 0 * * 0' },
  },
};

let savedBody: any = null;

describe('PipelineSettingsPanel', () => {
  beforeEach(() => {
    mockToast.success.mockClear();
    mockToast.error.mockClear();
    savedBody = null;
    server.resetHandlers();
    server.use(
      rest.get('/api/v1/settings/automations/', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(pipelinesPayload))
      ),
      rest.post('/api/v1/settings/automations/', (req, res, ctx) => {
        savedBody = req.body;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  it('renders nothing when closed', () => {
    const { container } = render(<PipelineSettingsPanel isOpen={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows loading skeletons while settings load', async () => {
    server.use(
      rest.get('/api/v1/settings/automations/', (req, res, ctx) =>
        res(ctx.delay(150), ctx.status(200), ctx.json(pipelinesPayload))
      )
    );
    const { container } = render(<PipelineSettingsPanel isOpen={true} />);

    expect(container.querySelectorAll('.animate-pulse').length).toBe(3);
    expect(screen.queryByText('sales Pipeline')).not.toBeInTheDocument();

    await screen.findByText('sales Pipeline');
  });

  it('renders pipeline cards with modes and cron text from the API', async () => {
    render(<PipelineSettingsPanel isOpen={true} />);

    expect(await screen.findByText('sales Pipeline')).toBeInTheDocument();
    expect(screen.getByText('projects Pipeline')).toBeInTheDocument();
    expect(screen.getByText('finance Pipeline')).toBeInTheDocument();

    expect(screen.getByText('Real-Time')).toBeInTheDocument();
    expect(screen.getAllByText('Scheduled').length).toBe(2);
    expect(screen.getByText('Continuous ingestion (60s poll loop)')).toBeInTheDocument();
    expect(screen.getByText('Running on cron: 0 2 * * *')).toBeInTheDocument();
    expect(screen.getByText('Running on cron: 0 0 * * 0')).toBeInTheDocument();

    // toggle buttons reflect the inverse of the current mode
    expect(screen.getByRole('button', { name: /Switch to Scheduled/ })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Switch to Real-Time/ }).length).toBe(2);
  });

  it('defaults to scheduled/standard when the API returns no pipelines', async () => {
    server.use(
      rest.get('/api/v1/settings/automations/', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true }))
      )
    );
    render(<PipelineSettingsPanel isOpen={true} />);

    expect(await screen.findByText('sales Pipeline')).toBeInTheDocument();
    expect(screen.getAllByText('Scheduled').length).toBe(3);
    expect(screen.getAllByText('Running on cron: standard').length).toBe(3);
  });

  it('toggles a pipeline to the new mode, saves and toasts', async () => {
    render(<PipelineSettingsPanel isOpen={true} />);
    await screen.findByText('sales Pipeline');

    fireEvent.click(screen.getByRole('button', { name: /Switch to Scheduled/ }));

    await waitFor(() => {
      expect(savedBody.pipelines.sales.mode).toBe('scheduled');
    });
    // mode flipped: sales badge now Scheduled, cron preserved
    expect(screen.getByText('Running on cron: */5 * * * *')).toBeInTheDocument();
    expect(screen.getAllByText('Scheduled').length).toBe(3);
    expect(screen.queryByText('Real-Time')).not.toBeInTheDocument();
    expect(mockToast.success).toHaveBeenCalledWith('Sales pipeline switched to scheduled');
    // every pipeline is now scheduled → all three buttons offer switching back
    expect(screen.getAllByRole('button', { name: /Switch to Real-Time/ }).length).toBe(3);
  });

  it('does not update local mode when the save request fails', async () => {
    server.use(
      rest.post('/api/v1/settings/automations/', (req, res, ctx) =>
        res(ctx.status(500), ctx.json({}))
      )
    );
    render(<PipelineSettingsPanel isOpen={true} />);
    await screen.findByText('sales Pipeline');

    fireEvent.click(screen.getByRole('button', { name: /Switch to Scheduled/ }));

    // mode unchanged, no success toast
    await waitFor(() => expect(mockToast.error).not.toHaveBeenCalled());
    expect(screen.getByText('Real-Time')).toBeInTheDocument();
    expect(mockToast.success).not.toHaveBeenCalled();
  });

  it('toasts and falls back to defaults when the load request fails', async () => {
    server.use(
      rest.get('/api/v1/settings/automations/', (req, res, ctx) => (res.networkError as any)())
    );
    render(<PipelineSettingsPanel isOpen={true} />);

    expect(await screen.findByText('sales Pipeline')).toBeInTheDocument();
    expect(mockToast.error).toHaveBeenCalledWith('Failed to load sync settings');
    expect(screen.getAllByText('Scheduled').length).toBe(3);
  });

  it('toasts when the save request hits a network error', async () => {
    server.use(
      rest.post('/api/v1/settings/automations/', (req, res, ctx) => (res.networkError as any)())
    );
    render(<PipelineSettingsPanel isOpen={true} />);
    await screen.findByText('sales Pipeline');

    fireEvent.click(screen.getByRole('button', { name: /Switch to Scheduled/ }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to update pipeline settings');
    });
    expect(screen.getByText('Real-Time')).toBeInTheDocument();
  });
});
