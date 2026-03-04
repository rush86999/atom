/**
 * WhatsApp Realtime Status Component Tests
 *
 * Test suite for WhatsApp connection health and real-time monitoring
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import WhatsAppRealtimeStatus from '../WhatsAppRealtimeStatus';

describe('WhatsAppRealtimeStatus Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders WhatsApp realtime status component', () => {
    render(<WhatsAppRealtimeStatus />);
    expect(screen.getByText(/whatsapp|status|health/i)).toBeInTheDocument();
  });

  it('displays connection health status', async () => {
    server.use(
      rest.get('/api/whatsapp/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            status: 'healthy',
            service: 'WhatsApp Business API',
            timestamp: new Date().toISOString(),
          })
        );
      })
    );

    render(<WhatsAppRealtimeStatus />);

    await waitFor(() => {
      expect(screen.getByText(/healthy|connected/i)).toBeInTheDocument();
    });
  });

  it('shows webhook status', async () => {
    server.use(
      rest.get('/api/whatsapp/webhook-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            webhook_configured: true,
            webhook_url: 'https://example.com/webhook',
          })
        );
      })
    );

    render(<WhatsAppRealtimeStatus />);

    await waitFor(() => {
      expect(screen.getByText(/webhook|configured/i)).toBeInTheDocument();
    });
  });

  it('displays error status on unhealthy connection', async () => {
    server.use(
      rest.get('/api/whatsapp/health', (req, res, ctx) => {
        return res(
          ctx.status(503),
          ctx.json({
            status: 'unhealthy',
            error: 'Connection lost',
          })
        );
      })
    );

    render(<WhatsAppRealtimeStatus />);

    await waitFor(() => {
      expect(screen.getByText(/unhealthy|error|disconnected/i)).toBeInTheDocument();
    });
  });
});
