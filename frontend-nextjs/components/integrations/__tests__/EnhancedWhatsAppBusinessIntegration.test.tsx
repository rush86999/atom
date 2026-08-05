/**
 * EnhancedWhatsAppBusinessIntegration Component Tests
 *
 * The Enhanced component is an alias for the real WhatsApp Business
 * integration component (components/integrations/WhatsAppBusinessIntegration.tsx):
 *   export { default } from './WhatsAppBusinessIntegration';
 *
 * Tests verify the real component:
 * - Health check (GET /api/whatsapp/health) → connected/disconnected state
 * - Conversations, messages, and analytics data loading
 * - Connect (OAuth initiate) flow
 * - Message compose dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/integrations/WhatsAppBusinessIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import EnhancedWhatsAppBusinessIntegration from '@/components/integrations/EnhancedWhatsAppBusinessIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const conversations = [
  {
    id: 'c1',
    conversation_id: 'conv1',
    whatsapp_id: 'wa1',
    status: 'active',
    last_message_at: '2024-01-15T10:00:00Z',
    name: 'Rushi Parikh',
    phone_number: '+1234567890',
    message_count: 5,
  },
  {
    id: 'c2',
    conversation_id: 'conv2',
    whatsapp_id: 'wa2',
    status: 'pending',
    last_message_at: '2024-01-14T10:00:00Z',
    phone_number: '+1987654321',
    message_count: 2,
  },
];

const messages = [
  {
    id: 'm1',
    message_id: 'msg1',
    whatsapp_id: 'wa1',
    message_type: 'text',
    content: { body: 'Hello! How can I help?' },
    direction: 'inbound',
    status: 'delivered',
    timestamp: '2024-01-15T10:00:00Z',
  },
];

const analytics = {
  message_statistics: [
    { direction: 'outbound', message_type: 'text', status: 'sent', count: 3 },
    { direction: 'inbound', message_type: 'text', status: 'received', count: 2 },
  ],
  conversation_statistics: {
    total_conversations: 10,
    active_conversations: 4,
  },
  contact_growth: [{ date: '2024-01-15', new_contacts: 4 }],
};

const whatsappHandlers = [
  rest.get('/api/whatsapp/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.get('/api/whatsapp/conversations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, conversations }));
  }),

  rest.get('/api/whatsapp/messages/:whatsappId', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, messages }));
  }),

  rest.get('/api/whatsapp/analytics', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, analytics }));
  }),

  rest.post('/api/whatsapp/send', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/whatsapp/health', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ status: 'unhealthy' }));
    })
  );
};

describe('EnhancedWhatsAppBusinessIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...whatsappHandlers);
  });

  // Test 1: renders component (heading appears after the health check settles)
  test('renders component', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /whatsapp business integration/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setNotConnected();

    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect with meta/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<EnhancedWhatsAppBusinessIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect with meta/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays conversations in the default Conversations tab
  test('displays conversations in the default Conversations tab', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
      expect(screen.getByText('+1234567890')).toBeInTheDocument();
      expect(screen.getByText('Recent Conversations')).toBeInTheDocument();
    });
  });

  // Test 6: displays analytics overview when connected
  test('displays analytics overview when connected', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Total Conversations')).toBeInTheDocument();
      expect(screen.getByText('Active Conversations')).toBeInTheDocument();
      expect(screen.getByText('Messages Sent Today')).toBeInTheDocument();
      expect(screen.getByText('Messages Received Today')).toBeInTheDocument();
    });
  });

  // Test 7: selecting a conversation loads its messages in the Messages tab
  test('selecting a conversation loads messages', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    const conversationCard = await screen.findByText('Rushi Parikh');
    fireEvent.click(conversationCard);

    const messagesTab = screen.getByRole('button', { name: 'Messages' });
    fireEvent.click(messagesTab);

    await waitFor(() => {
      expect(
        screen.getByText('Messages with Rushi Parikh')
      ).toBeInTheDocument();
      expect(screen.getByText('Hello! How can I help?')).toBeInTheDocument();
    });
  });

  // Test 8: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/whatsapp/health', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect with meta/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh button in the Conversations tab
  test('shows refresh button in connected state', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  // Test 10: New Message button opens the compose dialog
  test('opens compose message dialog', async () => {
    render(<EnhancedWhatsAppBusinessIntegration />);

    const newMessageButton = await screen.findByRole('button', {
      name: /new message/i,
    });
    fireEvent.click(newMessageButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /compose new message/i })
      ).toBeInTheDocument();
    });
  });
});
