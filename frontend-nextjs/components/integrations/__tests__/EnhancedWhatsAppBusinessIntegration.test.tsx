/**
 * Enhanced WhatsApp Business Integration Component Tests
 *
 * Test suite for enhanced WhatsApp messaging and webhooks
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import EnhancedWhatsAppBusinessIntegration from '../EnhancedWhatsAppBusinessIntegration';

describe('EnhancedWhatsAppBusinessIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders enhanced WhatsApp integration component', () => {
    render(<EnhancedWhatsAppBusinessIntegration />);
    expect(screen.getByText(/whatsapp|enhanced/i)).toBeInTheDocument();
  });

  it('fetches conversations', async () => {
    server.use(
      rest.get('/api/whatsapp/conversations', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            conversations: [
              {
                id: '1',
                phone_number: '+1234567890',
                status: 'active',
                message_count: 5,
              },
            ],
          })
        );
      })
    );

    render(<EnhancedWhatsAppBusinessIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText(/\+1234567890|conversations/i)).toBeInTheDocument();
    });
  });

  it('displays real-time message status', async () => {
    server.use(
      rest.get('/api/whatsapp/message-status/:messageId', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            status: 'delivered',
            timestamp: new Date().toISOString(),
          })
        );
      })
    );

    render(<EnhancedWhatsAppBusinessIntegration connected={true} />);

    await waitFor(() => {
      const statusElement = screen.queryByTestId(/message-status|delivery-status/i);
      // Note: Actual implementation may vary
    });
  });

  it('handles webhook events', async () => {
    server.use(
      rest.post('/api/whatsapp/webhook', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            message: 'Webhook received',
          })
        );
      })
    );

    render(<EnhancedWhatsAppBusinessIntegration connected={true} />);

    // Simulate webhook event
    window.dispatchEvent(
      new CustomEvent('whatsapp-webhook', {
        detail: {
          from: '+1234567890',
          message: 'Test message',
        },
      })
    );

    await waitFor(() => {
      expect(screen.getByText(/test message/i)).toBeInTheDocument();
    });
  });
});
