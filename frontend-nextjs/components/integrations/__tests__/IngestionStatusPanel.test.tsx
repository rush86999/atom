/**
 * IngestionStatusPanel Component Tests
 *
 * Tests the real IngestionStatusPanel component
 * (components/integrations/IngestionStatusPanel.tsx), which renders
 * GET /api/integrations/{id}/ingestion-status — the communication memory
 * pipeline's ingestion progress (records ingested, last ingest time,
 * stream state) merged with real connection state:
 *
 * - connected + stream running -> "Syncing" badge with counts
 * - connected + stream stopped -> "Start sync" action POSTs to
 *   /api/integrations/{id}/ingestion/start
 * - not connected              -> explicit "Not connected" state
 * - pipeline unavailable       -> graceful notice, no counts
 *
 * Uses the shared MSW server (tests/mocks/server.ts). Real timers are used
 * throughout (fake timers break MSW + RTL waitFor).
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import IngestionStatusPanel from '../IngestionStatusPanel';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const statusBody = (overrides: Record<string, any> = {}) => ({
  integration_id: 'outlook',
  app_type: 'outlook',
  connected: true,
  connection_source: 'oauth_token',
  ingestion_available: true,
  stream_running: true,
  records_ingested: 2000,
  last_ingested: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  ingestion_status: 'active',
  ...overrides,
});

const mockStatusOk = (
  body: Record<string, any>,
  integrationId = 'outlook'
) =>
  server.use(
    rest.get(`/api/integrations/${integrationId}/ingestion-status`, (_req, res, ctx) =>
      res(ctx.json(body))
    )
  );

describe('IngestionStatusPanel', () => {
  it('renders connected + syncing state with record counts', async () => {
    mockStatusOk(statusBody());

    render(<IngestionStatusPanel integrationId="outlook" />);

    await waitFor(() => {
      expect(screen.getByTestId('ingestion-records')).toHaveTextContent('2.0k');
    });
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Syncing')).toBeInTheDocument();
    expect(screen.getByTestId('ingestion-last')).toHaveTextContent('5m ago');
    // No start action while the stream is running.
    expect(screen.queryByText('Start sync')).not.toBeInTheDocument();
  });

  it('offers Start sync when connected but the stream is stopped', async () => {
    mockStatusOk(statusBody({ stream_running: false }));
    let startCalls = 0;
    server.use(
      rest.post('/api/integrations/outlook/ingestion/start', (_req, res, ctx) => {
        startCalls += 1;
        return res(ctx.json(statusBody({ start_attempted: true })));
      })
    );

    render(<IngestionStatusPanel integrationId="outlook" />);

    await waitFor(() => {
      expect(screen.getByText('Sync stopped')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Start sync'));

    await waitFor(() => {
      expect(startCalls).toBe(1);
    });
  });

  it('surfaces a reconnect hint when start is rejected with 409', async () => {
    mockStatusOk(statusBody({ stream_running: false }));
    server.use(
      rest.post('/api/integrations/outlook/ingestion/start', (_req, res, ctx) =>
        res(ctx.status(409), ctx.json({ detail: 'No active connection' }))
      )
    );

    render(<IngestionStatusPanel integrationId="outlook" />);

    await waitFor(() => {
      expect(screen.getByText('Start sync')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Start sync'));

    await waitFor(() => {
      expect(
        screen.getByText(/reconnect this integration first/i)
      ).toBeInTheDocument();
    });
  });

  it('shows the not-connected state', async () => {
    mockStatusOk(statusBody({ connected: false, connection_source: 'none' }));

    render(<IngestionStatusPanel integrationId="outlook" />);

    await waitFor(() => {
      expect(screen.getByText('Not connected')).toBeInTheDocument();
    });
    expect(screen.getByText(/connect it to ingest data/i)).toBeInTheDocument();
  });

  it('degrades gracefully when the ingestion pipeline is unavailable', async () => {
    mockStatusOk(statusBody({ ingestion_available: false, stream_running: false }));

    render(<IngestionStatusPanel integrationId="outlook" />);

    await waitFor(() => {
      expect(
        screen.getByText(/pipeline is not available/i)
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId('ingestion-records')).not.toBeInTheDocument();
  });

  it('shows hybrid sync state for integrations without a memory poller', async () => {
    mockStatusOk(
      statusBody({
        integration_id: 'salesforce',
        app_type: null,
        stream_running: false,
        records_ingested: 0,
        last_ingested: null,
        last_synced: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        auto_sync_enabled: true,
        sync_frequency_minutes: 15,
      }),
      'salesforce'
    );

    render(<IngestionStatusPanel integrationId="salesforce" />);

    await waitFor(() => {
      expect(screen.getByTestId('ingestion-sync-only')).toBeInTheDocument();
    });
    // No poller for salesforce, so no Start sync action and no record grid.
    expect(screen.queryByText('Start sync')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ingestion-records')).not.toBeInTheDocument();
    expect(screen.getByText(/Auto-sync on \(every 15 min\)/i)).toBeInTheDocument();
  });
});
